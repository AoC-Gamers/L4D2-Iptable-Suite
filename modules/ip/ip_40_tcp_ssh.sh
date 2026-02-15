#!/bin/bash

ip_40_tcp_ssh_metadata() {
    cat << 'EOF'
ID=ip_tcp_ssh
DESCRIPTION=Applies TCP protection (RCON) and SSH rules in the iptables backend
REQUIRED_VARS=TYPECHAIN ENABLE_TCP_PROTECT GAMESERVERPORTS SSH_PORT LOG_PREFIX_TCP_RCON_BLOCK
OPTIONAL_VARS=TCP_PROTECTION TCP_DOCKER SSH_DOCKER
DEFAULTS=TYPECHAIN=0 ENABLE_TCP_PROTECT=true GAMESERVERPORTS=27015 SSH_PORT=22 LOG_PREFIX_TCP_RCON_BLOCK=TCP_RCON_BLOCK: TCP_PROTECTION= TCP_DOCKER= SSH_DOCKER=
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

    case "${ENABLE_TCP_PROTECT:-}" in
        true|false) ;;
        *)
            echo "ERROR: ip_tcp_ssh: ENABLE_TCP_PROTECT must be true or false"
            return 2
            ;;
    esac
}

ip_40_tcp_ssh_apply() {
    if [ "$ENABLE_TCP_PROTECT" = "true" ]; then
        echo "TCP Protection ENABLED: blocking RCON spam"

        iptables -A INPUT -p tcp -m multiport --dports "$SSH_PORT" -j ACCEPT

        if [ -n "$TCP_PROTECTION" ]; then
            iptables -A INPUT -p tcp -m multiport --dports "$TCP_PROTECTION" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
            iptables -A INPUT -p tcp -m multiport --dports "$TCP_PROTECTION" -j DROP
        else
            iptables -A INPUT -p tcp -m multiport --dports "$GAMESERVERPORTS" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
            iptables -A INPUT -p tcp -m multiport --dports "$GAMESERVERPORTS" -j DROP
        fi

        if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
            if [ -n "$TCP_PROTECTION" ]; then
                iptables -A DOCKER -p tcp -m multiport --dports "$TCP_PROTECTION" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
                iptables -A DOCKER -p tcp -m multiport --dports "$TCP_PROTECTION" -j DROP
            else
                iptables -A DOCKER -p tcp -m multiport --dports "$GAMESERVERPORTS" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
                iptables -A DOCKER -p tcp -m multiport --dports "$GAMESERVERPORTS" -j DROP
            fi
        fi
    else
        echo "TCP Protection DISABLED: no RCON blocks applied"
        if [ -n "$TCP_PROTECTION" ]; then
            iptables -A INPUT -p tcp -m multiport --dports "$TCP_PROTECTION" -j TCPfilter
        fi
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        if [ -n "$TCP_DOCKER" ]; then
            iptables -I DOCKER -p tcp -m multiport --dports "$TCP_DOCKER" -j TCPfilter
        fi
    fi

    iptables -A INPUT -p tcp -m multiport --dports "$SSH_PORT" -j ACCEPT
    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        if [ -n "$SSH_DOCKER" ]; then
            iptables -I DOCKER -p tcp -m multiport --dports "$SSH_DOCKER" -j ACCEPT
        fi
    fi
}
