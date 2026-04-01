#!/bin/bash

ip_42_l4d2_tcp_protect_metadata() {
    cat << 'EOF'
ID=ip_l4d2_tcp_protect
ALIASES=l4d2_tcp_protect
DESCRIPTION=Applies L4D2 TCP protection (RCON/game ports) in the iptables backend
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=L4D2_GAMESERVER_PORTS LOG_PREFIX_TCP_RCON_BLOCK
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_PORTS=27015 LOG_PREFIX_TCP_RCON_BLOCK=TCP_RCON_BLOCK:
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
    local tcp_rate="600/min"
    local tcp_burst="200"
    local input_hashlimit_name="L4D2TCPINPUT"
    local docker_hashlimit_name="L4D2TCPDOCKER"

    protected_ports="$L4D2_GAMESERVER_PORTS"

    echo "L4D2 TCP protection enabled by module inclusion: rate-limiting NEW TCP by source/destination port"

    iptables -A INPUT -p tcp -m multiport --dports "$protected_ports" -m conntrack --ctstate NEW -m hashlimit --hashlimit-upto "$tcp_rate" --hashlimit-burst "$tcp_burst" --hashlimit-mode srcip,dstport --hashlimit-name "$input_hashlimit_name" --hashlimit-htable-expire 60000 --hashlimit-htable-max 999999 -j ACCEPT
    iptables -A INPUT -p tcp -m multiport --dports "$protected_ports" -m conntrack --ctstate NEW -m hashlimit --hashlimit-above "$tcp_rate" --hashlimit-burst "$tcp_burst" --hashlimit-mode srcip,dstport --hashlimit-name "$input_hashlimit_name" --hashlimit-htable-expire 60000 --hashlimit-htable-max 999999 -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
    iptables -A INPUT -p tcp -m multiport --dports "$protected_ports" -m conntrack --ctstate NEW -j DROP

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -A DOCKER-USER -p tcp -m multiport --dports "$protected_ports" -m conntrack --ctstate NEW -m hashlimit --hashlimit-upto "$tcp_rate" --hashlimit-burst "$tcp_burst" --hashlimit-mode srcip,dstport --hashlimit-name "$docker_hashlimit_name" --hashlimit-htable-expire 60000 --hashlimit-htable-max 999999 -j ACCEPT
        iptables -A DOCKER-USER -p tcp -m multiport --dports "$protected_ports" -m conntrack --ctstate NEW -m hashlimit --hashlimit-above "$tcp_rate" --hashlimit-burst "$tcp_burst" --hashlimit-mode srcip,dstport --hashlimit-name "$docker_hashlimit_name" --hashlimit-htable-expire 60000 --hashlimit-htable-max 999999 -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
        iptables -A DOCKER-USER -p tcp -m multiport --dports "$protected_ports" -m conntrack --ctstate NEW -j DROP
    fi
}
