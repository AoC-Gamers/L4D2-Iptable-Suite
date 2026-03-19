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
                    echo "INFO: nf_whitelist: domain '$domain' did not resolve to IPv4; using WHITELISTED_IPS fallback"
                else
                    echo "WARNING: nf_whitelist: domain '$domain' did not resolve to IPv4 and no WHITELISTED_IPS fallback is configured"
                fi
            fi
        done
    fi

    effective_whitelist="$(for ip in $effective_whitelist; do echo "$ip"; done | awk '!seen[$0]++' | xargs)"
    [ -z "$effective_whitelist" ] && return 0

    local chain
    for chain in $(nf_get_target_chains_for_domain core_allow); do
        for ip in $effective_whitelist; do
            # Accept single IPv4 and IPv4 CIDR only
            if ! [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?$ ]]; then
                echo "WARNING: nf_whitelist: skipping invalid IPv4/CIDR entry '$ip'"
                continue
            fi
            nf_add_rule "$chain" ip saddr "$ip" accept
        done
    done
}
