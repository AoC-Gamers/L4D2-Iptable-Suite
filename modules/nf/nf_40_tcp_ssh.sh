#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_40_tcp_ssh_metadata() {
    cat << 'EOF'
ID=nf_tcp_ssh
DESCRIPTION=Applies TCP protection and base SSH rules in the nftables backend
REQUIRED_VARS=TYPECHAIN SSH_PORT ENABLE_L4D2_TCP_PROTECT L4D2_GAMESERVER_PORTS
OPTIONAL_VARS=L4D2_TCP_PROTECTION SSH_DOCKER LOG_PREFIX_TCP_RCON_BLOCK SSH_REQUIRE_WHITELIST WHITELISTED_IPS WHITELISTED_DOMAINS
DEFAULTS=TYPECHAIN=0 SSH_PORT=22 ENABLE_L4D2_TCP_PROTECT=true L4D2_GAMESERVER_PORTS=27015 L4D2_TCP_PROTECTION= SSH_DOCKER= LOG_PREFIX_TCP_RCON_BLOCK=TCP_RCON_BLOCK: SSH_REQUIRE_WHITELIST=false WHITELISTED_IPS= WHITELISTED_DOMAINS=
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

    case "${ENABLE_L4D2_TCP_PROTECT:-}" in
        true|false) ;;
        *)
            echo "ERROR: nf_tcp_ssh: ENABLE_L4D2_TCP_PROTECT must be true or false"
            return 2
            ;;
    esac

    nf_validate_ports_spec "$L4D2_GAMESERVER_PORTS" "nf_tcp_ssh: L4D2_GAMESERVER_PORTS" || return $?

    if [ -n "${L4D2_TCP_PROTECTION:-}" ]; then
        nf_validate_ports_spec "$L4D2_TCP_PROTECTION" "nf_tcp_ssh: L4D2_TCP_PROTECTION" || return $?
    fi

    case "${SSH_REQUIRE_WHITELIST:-false}" in
        true|false) ;;
        *)
            echo "ERROR: nf_tcp_ssh: SSH_REQUIRE_WHITELIST must be true or false"
            return 2
            ;;
    esac

    if [ "${SSH_REQUIRE_WHITELIST:-false}" = "true" ] && [ -z "${WHITELISTED_IPS:-}" ] && [ -z "${WHITELISTED_DOMAINS:-}" ]; then
        echo "ERROR: nf_tcp_ssh: SSH_REQUIRE_WHITELIST=true requires WHITELISTED_IPS and/or WHITELISTED_DOMAINS"
        return 2
    fi
}

nf_40_tcp_ssh_apply() {
    local chain protected_ports_expr ssh_ports_expr allow_public_ssh

    protected_ports_expr="$(nf_ports_set_expr "${L4D2_TCP_PROTECTION:-$L4D2_GAMESERVER_PORTS}")"
    ssh_ports_expr="$(nf_ports_set_expr "$SSH_PORT")"
    allow_public_ssh=true

    if [ "${SSH_REQUIRE_WHITELIST:-false}" = "true" ]; then
        allow_public_ssh=false
        echo "SSH protection: public SSH disabled, only WHITELISTED_IPS/WHITELISTED_DOMAINS can access"
    fi

    for chain in $(nf_get_target_chains); do
        if [ "$allow_public_ssh" = "true" ]; then
            nf_add_rule "$chain" tcp dport "$ssh_ports_expr" accept
        fi

        if [ "$ENABLE_L4D2_TCP_PROTECT" = "true" ]; then
            nf_add_rule "$chain" tcp dport "$protected_ports_expr" limit rate over 60/minute burst 20 packets log prefix "\"$LOG_PREFIX_TCP_RCON_BLOCK \""
            nf_add_rule "$chain" tcp dport "$protected_ports_expr" drop
        fi
    done
}
