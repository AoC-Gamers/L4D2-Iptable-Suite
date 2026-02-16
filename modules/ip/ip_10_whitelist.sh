#!/bin/bash

ip_10_whitelist_metadata() {
    cat << 'EOF'
ID=ip_whitelist
DESCRIPTION=Allows full traffic from IPs listed in WHITELISTED_IPS
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=WHITELISTED_IPS WHITELISTED_DOMAINS
DEFAULTS=TYPECHAIN=0 WHITELISTED_IPS= WHITELISTED_DOMAINS=
EOF
}

ip_10_whitelist_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_whitelist: TYPECHAIN must be 0, 1 or 2 (current: ${TYPECHAIN:-unset})"
            return 2
            ;;
    esac
}

ip_10_whitelist_apply() {
    local effective_whitelist domain resolved_count ip has_static_whitelist

    effective_whitelist="${WHITELISTED_IPS:-}"
    has_static_whitelist=false
    if [ -n "${WHITELISTED_IPS:-}" ]; then
        has_static_whitelist=true
    fi

    if [ -n "${WHITELISTED_DOMAINS:-}" ]; then
        for domain in $WHITELISTED_DOMAINS; do
            resolved_count=0

            while IFS= read -r ip; do
                [ -z "$ip" ] && continue
                effective_whitelist="$effective_whitelist $ip"
                resolved_count=$((resolved_count + 1))
            done < <(getent ahostsv4 "$domain" 2>/dev/null | awk '{print $1}' | sort -u)

            if [ "$resolved_count" -eq 0 ] && command -v host >/dev/null 2>&1; then
                while IFS= read -r ip; do
                    [ -z "$ip" ] && continue
                    effective_whitelist="$effective_whitelist $ip"
                    resolved_count=$((resolved_count + 1))
                done < <(host -t A "$domain" 2>/dev/null | awk '/has address/ {print $4}' | sort -u)
            fi

            if [ "$resolved_count" -eq 0 ] && command -v dig >/dev/null 2>&1; then
                while IFS= read -r ip; do
                    [ -z "$ip" ] && continue
                    effective_whitelist="$effective_whitelist $ip"
                    resolved_count=$((resolved_count + 1))
                done < <(dig +short A "$domain" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | sort -u)
            fi

            if [ "$resolved_count" -eq 0 ]; then
                if [ "$has_static_whitelist" = "true" ]; then
                    echo "INFO: ip_whitelist: domain '$domain' did not resolve to IPv4; using WHITELISTED_IPS fallback"
                else
                    echo "WARNING: ip_whitelist: domain '$domain' did not resolve to IPv4 and no WHITELISTED_IPS fallback is configured"
                fi
            fi
        done
    fi

    effective_whitelist="$(for ip in $effective_whitelist; do echo "$ip"; done | awk '!seen[$0]++' | xargs)"

    if [ -z "$effective_whitelist" ]; then
        echo "INFO: ip_whitelist: no WHITELISTED_IPS/WHITELISTED_DOMAINS configured"
        return 0
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -N DOCKER-USER 2>/dev/null || true
    fi

    for ip in $effective_whitelist; do
        if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
            iptables -C INPUT -s "$ip" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -s "$ip" -j ACCEPT
        fi

        if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
            iptables -C DOCKER-USER -s "$ip" -j ACCEPT 2>/dev/null || iptables -I DOCKER-USER 1 -s "$ip" -j ACCEPT
        fi
    done
}
