#!/bin/bash

ip_40_tcp_ssh_metadata() {
    cat << 'EOF'
ID=ip_tcp_ssh
DESCRIPTION=Applies TCP protection (RCON) and SSH rules in the iptables backend
REQUIRED_VARS=TYPECHAIN ENABLE_L4D2_TCP_PROTECT L4D2_GAMESERVER_PORTS SSH_PORT LOG_PREFIX_TCP_RCON_BLOCK
OPTIONAL_VARS=L4D2_TCP_PROTECTION TCP_DOCKER SSH_DOCKER SSH_REQUIRE_WHITELIST WHITELISTED_IPS WHITELISTED_DOMAINS
DEFAULTS=TYPECHAIN=0 ENABLE_L4D2_TCP_PROTECT=true L4D2_GAMESERVER_PORTS=27015 SSH_PORT=22 LOG_PREFIX_TCP_RCON_BLOCK=TCP_RCON_BLOCK: L4D2_TCP_PROTECTION= TCP_DOCKER= SSH_DOCKER= SSH_REQUIRE_WHITELIST=false WHITELISTED_IPS= WHITELISTED_DOMAINS=
EOF
}

ip_40_tcp_ssh_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_tcp_ssh: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    case "${ENABLE_L4D2_TCP_PROTECT:-}" in
        true|false) ;;
        *)
            echo "ERROR: ip_tcp_ssh: ENABLE_L4D2_TCP_PROTECT must be true or false"
            return 2
            ;;
    esac

    case "${SSH_REQUIRE_WHITELIST:-false}" in
        true|false) ;;
        *)
            echo "ERROR: ip_tcp_ssh: SSH_REQUIRE_WHITELIST must be true or false"
            return 2
            ;;
    esac

    if [ "${SSH_REQUIRE_WHITELIST:-false}" = "true" ] && [ -z "${WHITELISTED_IPS:-}" ] && [ -z "${WHITELISTED_DOMAINS:-}" ]; then
        echo "ERROR: ip_tcp_ssh: SSH_REQUIRE_WHITELIST=true requires WHITELISTED_IPS and/or WHITELISTED_DOMAINS"
        return 2
    fi
}

ip_40_tcp_ssh_apply() {
    local allow_public_ssh

    allow_public_ssh=true
    if [ "${SSH_REQUIRE_WHITELIST:-false}" = "true" ]; then
        allow_public_ssh=false
        echo "SSH protection: public SSH disabled, only WHITELISTED_IPS/WHITELISTED_DOMAINS can access"
    fi

    if [ "$allow_public_ssh" = "true" ]; then
        iptables -A INPUT -p tcp -m multiport --dports "$SSH_PORT" -j ACCEPT
    fi

    if [ "$ENABLE_L4D2_TCP_PROTECT" = "true" ]; then
        echo "TCP Protection ENABLED: blocking RCON spam"

        if [ -n "$L4D2_TCP_PROTECTION" ]; then
            iptables -A INPUT -p tcp -m multiport --dports "$L4D2_TCP_PROTECTION" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
            iptables -A INPUT -p tcp -m multiport --dports "$L4D2_TCP_PROTECTION" -j DROP
        else
            iptables -A INPUT -p tcp -m multiport --dports "$L4D2_GAMESERVER_PORTS" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
            iptables -A INPUT -p tcp -m multiport --dports "$L4D2_GAMESERVER_PORTS" -j DROP
        fi

        if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
            if [ -n "$L4D2_TCP_PROTECTION" ]; then
                iptables -A DOCKER-USER -p tcp -m multiport --dports "$L4D2_TCP_PROTECTION" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
                iptables -A DOCKER-USER -p tcp -m multiport --dports "$L4D2_TCP_PROTECTION" -j DROP
            else
                iptables -A DOCKER-USER -p tcp -m multiport --dports "$L4D2_GAMESERVER_PORTS" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
                iptables -A DOCKER-USER -p tcp -m multiport --dports "$L4D2_GAMESERVER_PORTS" -j DROP
            fi
        fi
    else
        echo "TCP Protection DISABLED: no RCON blocks applied"
        if [ -n "$L4D2_TCP_PROTECTION" ]; then
            iptables -A INPUT -p tcp -m multiport --dports "$L4D2_TCP_PROTECTION" -j TCPfilter
        fi
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        if [ -n "$TCP_DOCKER" ]; then
            iptables -I DOCKER-USER -p tcp -m multiport --dports "$TCP_DOCKER" -j TCPfilter
        fi
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        if [ -n "$SSH_DOCKER" ] && [ "$allow_public_ssh" = "true" ]; then
            iptables -I DOCKER-USER -p tcp -m multiport --dports "$SSH_DOCKER" -j ACCEPT
        fi
    fi
}
