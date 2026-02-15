#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_10_whitelist_metadata() {
    cat << 'EOF'
ID=nf_whitelist
DESCRIPTION=Permite trafico completo de IPs confiables en nftables
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=WHITELISTED_IPS
DEFAULTS=TYPECHAIN=0 WHITELISTED_IPS=
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
    [ -z "${WHITELISTED_IPS:-}" ] && return 0

    local chain ip
    for chain in $(nf_get_target_chains); do
        for ip in $WHITELISTED_IPS; do
            nf_add_rule "$chain" ip saddr "$ip" accept
        done
    done
}
