#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_40_tcp_ssh_metadata() {
    cat << 'EOF'
ID=nf_tcp_ssh
DESCRIPTION=Applies TCP protection and base SSH rules in the nftables backend
REQUIRED_VARS=TYPECHAIN ENABLE_TCP_PROTECT GAMESERVERPORTS SSH_PORT
OPTIONAL_VARS=TCP_PROTECTION SSH_DOCKER LOG_PREFIX_TCP_RCON_BLOCK
DEFAULTS=TYPECHAIN=0 ENABLE_TCP_PROTECT=true GAMESERVERPORTS=27015 SSH_PORT=22 TCP_PROTECTION= SSH_DOCKER= LOG_PREFIX_TCP_RCON_BLOCK=TCP_RCON_BLOCK:
EOF
}

nf_40_tcp_ssh_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_tcp_ssh: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    case "${ENABLE_TCP_PROTECT:-}" in
        true|false) ;;
        *)
            echo "ERROR: nf_tcp_ssh: ENABLE_TCP_PROTECT must be true or false"
            return 2
            ;;
    esac
}

nf_40_tcp_ssh_apply() {
    local chain protected_ports_expr ssh_ports_expr

    protected_ports_expr="$(nf_ports_set_expr "${TCP_PROTECTION:-$GAMESERVERPORTS}")"
    ssh_ports_expr="$(nf_ports_set_expr "$SSH_PORT")"

    for chain in $(nf_get_target_chains); do
        nf_add_rule "$chain" tcp dport "$ssh_ports_expr" accept

        if [ "$ENABLE_TCP_PROTECT" = "true" ]; then
            nf_add_rule "$chain" tcp dport "$protected_ports_expr" limit rate over 60/minute burst 20 packets log prefix "$LOG_PREFIX_TCP_RCON_BLOCK "
            nf_add_rule "$chain" tcp dport "$protected_ports_expr" drop
        fi
    done
}
