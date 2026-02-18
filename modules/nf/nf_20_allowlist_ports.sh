#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_20_allowlist_ports_metadata() {
    cat << 'EOF'
ID=nf_allowlist_ports
ALIASES=allowlist_ports
DESCRIPTION=Allows additional UDP/TCP ports in the nftables backend
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=UDP_ALLOW_PORTS TCP_ALLOW_PORTS
DEFAULTS=TYPECHAIN=0 UDP_ALLOW_PORTS= TCP_ALLOW_PORTS=
EOF
}

nf_20_allowlist_ports_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_allowlist_ports: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if [ -n "${UDP_ALLOW_PORTS:-}" ]; then
        nf_validate_ports_spec "$UDP_ALLOW_PORTS" "nf_allowlist_ports: UDP_ALLOW_PORTS" || return $?
    fi

    if [ -n "${TCP_ALLOW_PORTS:-}" ]; then
        nf_validate_ports_spec "$TCP_ALLOW_PORTS" "nf_allowlist_ports: TCP_ALLOW_PORTS" || return $?
    fi
}

nf_20_allowlist_ports_apply() {
    local chain ports_expr

    if [ -n "${UDP_ALLOW_PORTS:-}" ]; then
        ports_expr="$(nf_ports_set_expr "$UDP_ALLOW_PORTS")"
        for chain in $(nf_get_target_chains); do
            nf_add_rule "$chain" udp dport "$ports_expr" accept
        done
    fi

    if [ -n "${TCP_ALLOW_PORTS:-}" ]; then
        ports_expr="$(nf_ports_set_expr "$TCP_ALLOW_PORTS")"
        for chain in $(nf_get_target_chains); do
            nf_add_rule "$chain" tcp dport "$ports_expr" accept
        done
    fi
}
