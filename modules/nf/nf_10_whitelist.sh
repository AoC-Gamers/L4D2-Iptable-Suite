#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_10_whitelist_metadata() {
    cat << 'EOF'
ID=nf_whitelist
ALIASES=whitelist
DESCRIPTION=Allows full traffic from trusted IPs in the nftables backend
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=WHITELISTED_IPS WHITELISTED_DOMAINS
DEFAULTS=TYPECHAIN=0 WHITELISTED_IPS= WHITELISTED_DOMAINS=
EOF
}

nf_10_whitelist_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_whitelist: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac
}

nf_10_whitelist_is_ipv4() {
    local value="$1"
    [[ "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?$ ]]
}

nf_10_whitelist_is_ipv6() {
    local value="$1"
    [[ "$value" == *:* ]] \
        && [[ "$value" != ::ffff:* ]] \
        && [[ "$value" =~ ^[0-9A-Fa-f:.]+(/[0-9]{1,3})?$ ]]
}

nf_10_whitelist_resolve_domain() {
    local domain="$1"

    getent ahostsv4 "$domain" 2>/dev/null | awk '{print $1}'
    getent ahostsv6 "$domain" 2>/dev/null | awk '$1 !~ /^::ffff:/ {print $1}'

    if command -v host >/dev/null 2>&1; then
        host -t A "$domain" 2>/dev/null | awk '/has address/ {print $4}'
        host -t AAAA "$domain" 2>/dev/null | awk '/has IPv6 address/ {print $5}'
    fi

    if command -v dig >/dev/null 2>&1; then
        dig +short A "$domain" 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'
        dig +short AAAA "$domain" 2>/dev/null | grep -E '^[0-9A-Fa-f:]+$'
    fi
}

nf_10_whitelist_apply() {
    local effective_whitelist chain ip domain resolved_count has_static_whitelist

    effective_whitelist="${WHITELISTED_IPS:-}"

    # Normalize separators from env/custom input (space/comma/semicolon/newline)
    effective_whitelist="${effective_whitelist//,/ }"
    effective_whitelist="${effective_whitelist//;/ }"
    effective_whitelist="${effective_whitelist//$'\n'/ }"

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
            done < <(nf_10_whitelist_resolve_domain "$domain" | sort -u)

            if [ "$resolved_count" -eq 0 ]; then
                if [ "$has_static_whitelist" = "true" ]; then
                    echo "INFO: nf_whitelist: domain '$domain' did not resolve to IPv4/IPv6; using WHITELISTED_IPS fallback"
                else
                    echo "WARNING: nf_whitelist: domain '$domain' did not resolve to IPv4/IPv6 and no WHITELISTED_IPS fallback is configured"
                fi
            fi
        done
    fi

    effective_whitelist="$(for ip in $effective_whitelist; do echo "$ip"; done | awk '!seen[$0]++' | xargs)"
    [ -z "$effective_whitelist" ] && return 0

    local chain
    for chain in $(nf_get_target_chains_for_domain core_allow); do
        for ip in $effective_whitelist; do
            if nf_10_whitelist_is_ipv4 "$ip"; then
                nf_add_rule "$chain" ip saddr "$ip" accept
                continue
            fi

            if nf_10_whitelist_is_ipv6 "$ip"; then
                nf_add_rule "$chain" ip6 saddr "$ip" accept
                continue
            fi

            echo "WARNING: nf_whitelist: skipping invalid IP/CIDR entry '$ip'"
        done
    done
}
