.DEFAULT_GOAL := help

COMPOSE ?= docker compose
SUDO ?= sudo
ROOT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
GEOIP_UPDATER_COMPOSE := geoip-updater/docker-compose.yml
LOG_SUMMARY_COMPOSE := log-summary/docker-compose.yml
GEOIP_LOCK_FILE ?= /tmp/l4d2-geoip-refresh.lock
FIREWALL_LOG_FILE ?= /var/log/firewall-suite.log

.PHONY: help
help:
	@printf "Available targets:\n"
	@printf "  %-22s %s\n" "geoip-update" "Download MaxMind CSV and regenerate allowed country prefixes"
	@printf "  %-22s %s\n" "geoip-apply" "Reload nftables with current GeoIP-generated files"
	@printf "  %-22s %s\n" "geoip-refresh" "Run updater and then reload nftables"
	@printf "  %-22s %s\n" "geoip-refresh-safe" "Run geoip-refresh under flock for cron-safe execution"
	@printf "  %-22s %s\n" "geoip-list" "List generated country prefix files"
	@printf "  %-22s %s\n" "geoip-check" "Validate GeoIP updater compose and shell scripts"
	@printf "  %-22s %s\n" "geoip-check-ip" "Check whether IP/CIDR is allowed or denied by the GeoIP policy"
	@printf "  %-22s %s\n" "geoip-show" "Show live nftables geo allowlist objects"
	@printf "  %-22s %s\n" "status" "Show GeoIP policy, generated files, and live firewall geo state"
	@printf "  %-22s %s\n" "firewall-nft" "Apply nftables backend"
	@printf "  %-22s %s\n" "firewall-ip" "Apply iptables backend"
	@printf "  %-22s %s\n" "firewall-validate" "Validate main shell scripts with bash -n"
	@printf "  %-22s %s\n" "http-https-test" "Verify per-source HTTP/HTTPS nftables rules"
	@printf "  %-22s %s\n" "public-ip-watch-test" "Run isolated public-IP watcher tests"
	@printf "  %-22s %s\n" "public-ip-watch-install" "Install and enable the 10-minute systemd watcher"
	@printf "  %-22s %s\n" "public-ip-watch-status" "Show timer, service, state, and current WAN/DDNS"
	@printf "  %-22s %s\n" "log-summary-up" "Build and start the log-summary stack"
	@printf "  %-22s %s\n" "log-summary-down" "Stop the log-summary stack"
	@printf "  %-22s %s\n" "logs-clear" "Truncate the firewall log file with sudo"
	@printf "  %-22s %s\n" "logs-backup-clear" "Backup and then truncate the firewall log file with sudo"

.PHONY: geoip-update
geoip-update:
	cd $(ROOT_DIR) && $(COMPOSE) -f $(GEOIP_UPDATER_COMPOSE) run --rm geoip-updater

.PHONY: geoip-apply
geoip-apply:
	cd $(ROOT_DIR) && $(SUDO) ./nftables.rules.sh

.PHONY: geoip-refresh
geoip-refresh:
	$(MAKE) geoip-update
	$(MAKE) geoip-apply

.PHONY: geoip-refresh-safe
geoip-refresh-safe:
	cd $(ROOT_DIR) && flock -n $(GEOIP_LOCK_FILE) $(MAKE) geoip-refresh

.PHONY: geoip-list
geoip-list:
	cd $(ROOT_DIR) && ls -1 geoip/generated/countries | sort

.PHONY: geoip-check
geoip-check:
	cd $(ROOT_DIR) && bash -n geoip-updater/run-update.sh
	cd $(ROOT_DIR) && bash -n scripts/geoip/update_geo_country_sets.sh
	cd $(ROOT_DIR) && bash -n modules/nf/nf_15_geo_country_filter.sh
	cd $(ROOT_DIR) && python3 -m py_compile scripts/geoip/check_geo_policy_ip.py
	cd $(ROOT_DIR) && $(COMPOSE) -f $(GEOIP_UPDATER_COMPOSE) config >/tmp/geoip-updater-compose.out

.PHONY: geoip-check-ip
geoip-check-ip:
	@if [ -z "$(IP)" ]; then \
		printf "Usage: make geoip-check-ip IP=179.6.17.240[/28]\n"; \
		printf "Optional: RESOLVE_DOMAINS=1 includes BYPASS_SOURCE_DOMAINS DNS results.\n"; \
		exit 2; \
	fi
	cd $(ROOT_DIR) && python3 scripts/geoip/check_geo_policy_ip.py --env-file .env $(if $(RESOLVE_DOMAINS),--resolve-domains,) "$(IP)"

.PHONY: geoip-show
geoip-show:
	cd $(ROOT_DIR) && $(SUDO) -n nft list ruleset | grep -E 'geo_country_(allow|deny|gate)_v4|geo_manual_(allow|deny)_v4' | head -n 20

.PHONY: status
status:
	@cd $(ROOT_DIR) && printf "Geo policy from .env:\n" && grep -E '^GEO_POLICY_' .env || true
	@cd $(ROOT_DIR) && printf "\nGenerated country files:\n" && ls -1 geoip/generated/countries | sort || true
	@cd $(ROOT_DIR) && printf "\nLive firewall geo objects:\n" && ($(SUDO) -n nft list ruleset | grep -E 'geo_country_(allow|deny|gate)_v4|geo_manual_(allow|deny)_v4' | head -n 20) || printf "nft ruleset unavailable with current privileges\n"

.PHONY: firewall-nft
firewall-nft:
	cd $(ROOT_DIR) && $(SUDO) ./nftables.rules.sh

.PHONY: firewall-ip
firewall-ip:
	cd $(ROOT_DIR) && $(SUDO) ./iptables.rules.sh

.PHONY: firewall-validate
firewall-validate:
	cd $(ROOT_DIR) && bash -n nftables.rules.sh
	cd $(ROOT_DIR) && bash -n iptables.rules.sh
	cd $(ROOT_DIR) && bash -n scripts/network/public-ip-watch.sh
	cd $(ROOT_DIR) && bash -n tests/http-https-protect.sh

.PHONY: http-https-test
http-https-test:
	cd $(ROOT_DIR) && bash ./tests/http-https-protect.sh

.PHONY: public-ip-watch-test
public-ip-watch-test:
	cd $(ROOT_DIR) && ./tests/public-ip-watch.sh

.PHONY: public-ip-watch-install
public-ip-watch-install:
	$(SUDO) install -o root -g root -m 0755 $(ROOT_DIR)scripts/network/public-ip-watch.sh /usr/local/sbin/l4d2-public-ip-watch
	$(SUDO) install -o root -g root -m 0644 $(ROOT_DIR)systemd/l4d2-public-ip-watch.service /etc/systemd/system/l4d2-public-ip-watch.service
	$(SUDO) install -o root -g root -m 0644 $(ROOT_DIR)systemd/l4d2-public-ip-watch.timer /etc/systemd/system/l4d2-public-ip-watch.timer
	@if $(SUDO) test -e /etc/default/l4d2-public-ip-watch; then \
		printf "Keeping existing /etc/default/l4d2-public-ip-watch\n"; \
	else \
		$(SUDO) install -o root -g root -m 0600 $(ROOT_DIR)config/l4d2-public-ip-watch.env.example /etc/default/l4d2-public-ip-watch; \
	fi
	$(SUDO) systemctl daemon-reload
	$(SUDO) systemctl enable --now l4d2-public-ip-watch.timer

.PHONY: public-ip-watch-status
public-ip-watch-status:
	$(SUDO) /usr/local/sbin/l4d2-public-ip-watch --check
	$(SUDO) systemctl --no-pager status l4d2-public-ip-watch.timer
	@$(SUDO) sh -c 'printf "Saved IP: "; cat /var/lib/l4d2-public-ip-watch/current-ip 2>/dev/null || printf "unset\n"'

.PHONY: log-summary-up
log-summary-up:
	cd $(ROOT_DIR) && $(COMPOSE) -f $(LOG_SUMMARY_COMPOSE) up -d --build

.PHONY: log-summary-down
log-summary-down:
	cd $(ROOT_DIR) && $(COMPOSE) -f $(LOG_SUMMARY_COMPOSE) down

.PHONY: logs-clear
logs-clear:
	@if [ ! -e "$(FIREWALL_LOG_FILE)" ]; then \
		printf "Log file not found: %s\n" "$(FIREWALL_LOG_FILE)"; \
		exit 2; \
	fi
	$(SUDO) truncate -s 0 "$(FIREWALL_LOG_FILE)"
	@printf "OK: truncated %s\n" "$(FIREWALL_LOG_FILE)"

.PHONY: logs-backup-clear
logs-backup-clear:
	@if [ ! -e "$(FIREWALL_LOG_FILE)" ]; then \
		printf "Log file not found: %s\n" "$(FIREWALL_LOG_FILE)"; \
		exit 2; \
	fi
	$(SUDO) cp -p "$(FIREWALL_LOG_FILE)" "$(FIREWALL_LOG_FILE).$$(date +%F-%H%M%S).bak"
	$(SUDO) truncate -s 0 "$(FIREWALL_LOG_FILE)"
	@printf "OK: backed up and truncated %s\n" "$(FIREWALL_LOG_FILE)"
