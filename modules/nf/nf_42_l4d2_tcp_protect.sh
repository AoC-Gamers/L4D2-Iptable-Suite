#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_42_l4d2_tcp_protect_metadata() {
    cat << 'EOF'
ID=nf_l4d2_tcp_protect
DESCRIPTION=Applies L4D2 TCP protection (RCON/game ports) in the nftables backend
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=ENABLE_L4D2_TCP_PROTECT L4D2_GAMESERVER_PORTS L4D2_TCP_PROTECTION LOG_PREFIX_TCP_RCON_BLOCK
DEFAULTS=TYPECHAIN=0 ENABLE_L4D2_TCP_PROTECT=false L4D2_GAMESERVER_PORTS=27015 L4D2_TCP_PROTECTION= LOG_PREFIX_TCP_RCON_BLOCK=TCP_RCON_BLOCK:
EOF
}

nf_42_l4d2_tcp_protect_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_l4d2_tcp_protect: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    case "${ENABLE_L4D2_TCP_PROTECT:-false}" in
        true|false) ;;
        *)
            echo "ERROR: nf_l4d2_tcp_protect: ENABLE_L4D2_TCP_PROTECT must be true or false"
            return 2
            ;;
    esac

    if [ "${ENABLE_L4D2_TCP_PROTECT:-false}" = "true" ] && [ -z "${L4D2_TCP_PROTECTION:-}" ]; then
        nf_validate_ports_spec "$L4D2_GAMESERVER_PORTS" "nf_l4d2_tcp_protect: L4D2_GAMESERVER_PORTS" || return $?
    fi

    if [ -n "${L4D2_TCP_PROTECTION:-}" ]; then
        nf_validate_ports_spec "$L4D2_TCP_PROTECTION" "nf_l4d2_tcp_protect: L4D2_TCP_PROTECTION" || return $?
    fi
}

nf_42_l4d2_tcp_protect_apply() {
    local chain protected_ports_expr

    [ "${ENABLE_L4D2_TCP_PROTECT:-false}" = "true" ] || return 0

    protected_ports_expr="$(nf_ports_set_expr "${L4D2_TCP_PROTECTION:-$L4D2_GAMESERVER_PORTS}")"

    for chain in $(nf_get_target_chains); do
        nf_add_rule "$chain" tcp dport "$protected_ports_expr" limit rate over 60/minute burst 20 packets log prefix "\"$LOG_PREFIX_TCP_RCON_BLOCK \""
        nf_add_rule "$chain" tcp dport "$protected_ports_expr" drop
    done
}
