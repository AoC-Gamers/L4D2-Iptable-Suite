#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WATCH_SCRIPT="$PROJECT_ROOT/scripts/network/public-ip-watch.sh"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

mkdir -p "$TEST_ROOT/bin" "$TEST_ROOT/state" "$TEST_ROOT/run"

cat > "$TEST_ROOT/bin/curl" <<'EOF'
#!/bin/bash
cat "$MOCK_PUBLIC_IP_FILE"
EOF

cat > "$TEST_ROOT/bin/dig" <<'EOF'
#!/bin/bash
cat "$MOCK_DDNS_IP_FILE"
EOF

cat > "$TEST_ROOT/bin/firewall" <<'EOF'
#!/bin/bash
printf '%s\n' "$*" >> "$MOCK_ACTION_LOG"
if [ "${MOCK_FIREWALL_FAIL_APPLY:-false}" = "true" ] && [[ " $* " != *" --dry-run "* ]]; then
    exit 42
fi
EOF

chmod +x "$TEST_ROOT/bin/curl" "$TEST_ROOT/bin/dig" "$TEST_ROOT/bin/firewall"

export PUBLIC_IP_WATCH_CONFIG="$TEST_ROOT/missing.conf"
export CURL_BIN="$TEST_ROOT/bin/curl"
export DIG_BIN="$TEST_ROOT/bin/dig"
export FLOCK_BIN=/usr/bin/flock
export MOCK_PUBLIC_IP_FILE="$TEST_ROOT/public-ip"
export MOCK_DDNS_IP_FILE="$TEST_ROOT/ddns-ip"
export MOCK_ACTION_LOG="$TEST_ROOT/actions"
export DDNS_HOSTNAME=valparaiso.dns.aoc-gamers.com
export DDNS_NAMESERVERS="ns1.test ns2.test"
export DDNS_MIN_MATCHES=2
export REQUIRE_DDNS_MATCH=true
export FIREWALL_SCRIPT="$TEST_ROOT/bin/firewall"
export FIREWALL_ENV_FILE=""
export STATE_FILE="$TEST_ROOT/state/current-ip"
export LOCK_FILE="$TEST_ROOT/run/watch.lock"

assert_equals() {
    local expected="$1"
    local actual="$2"
    local label="$3"

    if [ "$expected" != "$actual" ]; then
        printf 'FAIL: %s (expected=%s actual=%s)\n' "$label" "$expected" "$actual" >&2
        exit 1
    fi
}

action_count() {
    if [ -f "$MOCK_ACTION_LOG" ]; then
        wc -l < "$MOCK_ACTION_LOG"
    else
        echo 0
    fi
}

printf '%s\n' 186.79.158.146 > "$MOCK_PUBLIC_IP_FILE"
printf '%s\n' 186.79.158.146 > "$MOCK_DDNS_IP_FILE"
"$WATCH_SCRIPT" >/dev/null
assert_equals 186.79.158.146 "$(cat "$STATE_FILE")" "first run initializes state"
assert_equals 0 "$(action_count)" "first run does not reload"

"$WATCH_SCRIPT" >/dev/null
assert_equals 0 "$(action_count)" "unchanged IP does not reload"

printf '%s\n' 186.79.159.147 > "$MOCK_PUBLIC_IP_FILE"
printf '%s\n' 186.79.159.147 > "$MOCK_DDNS_IP_FILE"
"$WATCH_SCRIPT" >/dev/null
assert_equals 186.79.159.147 "$(cat "$STATE_FILE")" "confirmed change advances state"
assert_equals 2 "$(action_count)" "confirmed change validates and reloads"

printf '%s\n' 186.79.160.148 > "$MOCK_PUBLIC_IP_FILE"
printf '%s\n' 186.79.159.147 > "$MOCK_DDNS_IP_FILE"
"$WATCH_SCRIPT" >/dev/null
assert_equals 186.79.159.147 "$(cat "$STATE_FILE")" "DNS mismatch defers state change"
assert_equals 2 "$(action_count)" "DNS mismatch does not reload"

printf '%s\n' 186.79.160.148 > "$MOCK_DDNS_IP_FILE"
export MOCK_FIREWALL_FAIL_APPLY=true
if "$WATCH_SCRIPT" >/dev/null 2>&1; then
    echo "FAIL: firewall apply failure must be reported" >&2
    exit 1
fi
assert_equals 186.79.159.147 "$(cat "$STATE_FILE")" "failed reload keeps previous state"
assert_equals 4 "$(action_count)" "failed reload is attempted after validation"

echo "OK: public IP watcher tests passed"
