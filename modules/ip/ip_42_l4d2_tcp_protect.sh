#!/bin/bash

ip_42_l4d2_tcp_protect_metadata() {
    cat << 'EOF'
ID=ip_l4d2_tcp_protect
ALIASES=l4d2_tcp_protect
DESCRIPTION=Applies L4D2 TCP protection (RCON/game ports) in the iptables backend
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=L4D2_GAMESERVER_PORTS L4D2_TCP_PROTECTION LOG_PREFIX_TCP_RCON_BLOCK
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_PORTS=27015 L4D2_TCP_PROTECTION= LOG_PREFIX_TCP_RCON_BLOCK=TCP_RCON_BLOCK:
EOF
}

ip_42_l4d2_tcp_protect_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_l4d2_tcp_protect: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

}

ip_42_l4d2_tcp_protect_apply() {
    local protected_ports

    protected_ports="${L4D2_TCP_PROTECTION:-$L4D2_GAMESERVER_PORTS}"

    echo "L4D2 TCP protection enabled by module inclusion: blocking RCON/game TCP abuse"

    iptables -A INPUT -p tcp -m multiport --dports "$protected_ports" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
    iptables -A INPUT -p tcp -m multiport --dports "$protected_ports" -j DROP

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -A DOCKER-USER -p tcp -m multiport --dports "$protected_ports" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
        iptables -A DOCKER-USER -p tcp -m multiport --dports "$protected_ports" -j DROP
    fi
}
