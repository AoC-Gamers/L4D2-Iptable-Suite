#!/bin/bash

ip_70_l4d2_a2s_filters_metadata() {
    cat << 'EOF'
ID=ip_l4d2_a2s_filters
ALIASES=l4d2_a2s_filters
DESCRIPTION=Applies A2S/Steam Group filters and login-flood controls for GameServer
REQUIRED_VARS=TYPECHAIN L4D2_GAMESERVER_PORTS LOG_PREFIX_A2S_INFO LOG_PREFIX_A2S_PLAYERS LOG_PREFIX_A2S_RULES LOG_PREFIX_STEAM_GROUP LOG_PREFIX_L4D2_CONNECT LOG_PREFIX_L4D2_RESERVE
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_PORTS=27015 LOG_PREFIX_A2S_INFO=A2S_INFO_FLOOD: LOG_PREFIX_A2S_PLAYERS=A2S_PLAYERS_FLOOD: LOG_PREFIX_A2S_RULES=A2S_RULES_FLOOD: LOG_PREFIX_STEAM_GROUP=STEAM_GROUP_FLOOD: LOG_PREFIX_L4D2_CONNECT=L4D2_CONNECT_FLOOD: LOG_PREFIX_L4D2_RESERVE=L4D2_RESERVE_FLOOD:
EOF
}

ip_70_l4d2_a2s_filters_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_l4d2_a2s_filters: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

}

ip_70_l4d2_a2s_filters_apply_chains() {
    iptables -A A2S_LIMITS -m hashlimit --hashlimit-upto 8/sec --hashlimit-burst 30 --hashlimit-mode dstport --hashlimit-name A2SFilter --hashlimit-htable-expire 5000 -j ACCEPT
    iptables -A A2S_LIMITS -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_A2S_INFO" --log-level 4
    iptables -A A2S_LIMITS -j DROP

    iptables -A A2S_PLAYERS_LIMITS -m hashlimit --hashlimit-upto 8/sec --hashlimit-burst 30 --hashlimit-mode dstport --hashlimit-name A2SPlayersFilter --hashlimit-htable-expire 5000 -j ACCEPT
    iptables -A A2S_PLAYERS_LIMITS -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_A2S_PLAYERS" --log-level 4
    iptables -A A2S_PLAYERS_LIMITS -j DROP

    iptables -A A2S_RULES_LIMITS -m hashlimit --hashlimit-upto 8/sec --hashlimit-burst 30 --hashlimit-mode dstport --hashlimit-name A2SRulesFilter --hashlimit-htable-expire 5000 -j ACCEPT
    iptables -A A2S_RULES_LIMITS -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_A2S_RULES" --log-level 4
    iptables -A A2S_RULES_LIMITS -j DROP

    iptables -A STEAM_GROUP_LIMITS -m hashlimit --hashlimit-upto 1/sec --hashlimit-burst 3 --hashlimit-mode srcip,dstport --hashlimit-name STEAMGROUPFilter --hashlimit-htable-expire 5000 -j ACCEPT
    iptables -A STEAM_GROUP_LIMITS -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_STEAM_GROUP" --log-level 4
    iptables -A STEAM_GROUP_LIMITS -j DROP

    iptables -A l4d2loginfilter -m hashlimit --hashlimit-upto 1/sec --hashlimit-burst 1 --hashlimit-mode srcip,dstip,dstport --hashlimit-name L4D2CONNECTPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -m string --algo bm --string "connect" -j ACCEPT
    iptables -A l4d2loginfilter -m hashlimit --hashlimit-upto 1/sec --hashlimit-burst 1 --hashlimit-mode srcip,dstip,dstport --hashlimit-name L4D2RESERVEPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -m string --algo bm --string "reserve" -j ACCEPT
    iptables -A l4d2loginfilter -m string --algo bm --string "connect" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_L4D2_CONNECT" --log-level 4
    iptables -A l4d2loginfilter -m string --algo bm --string "reserve" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_L4D2_RESERVE" --log-level 4
    iptables -A l4d2loginfilter -j DROP
}

ip_70_l4d2_a2s_filters_apply_for_chain() {
    local chain="$1"

    iptables -A "$chain" -p udp -m multiport --dports "$L4D2_GAMESERVER_PORTS" -m string --algo bm --hex-string '|FFFFFFFF54|' -j A2S_LIMITS
    iptables -A "$chain" -p udp -m multiport --dports "$L4D2_GAMESERVER_PORTS" -m string --algo bm --hex-string '|FFFFFFFF55|' -j A2S_PLAYERS_LIMITS
    iptables -A "$chain" -p udp -m multiport --dports "$L4D2_GAMESERVER_PORTS" -m string --algo bm --hex-string '|FFFFFFFF56|' -j A2S_RULES_LIMITS
    iptables -A "$chain" -p udp -m multiport --dports "$L4D2_GAMESERVER_PORTS" -m string --algo bm --hex-string '|FFFFFFFF00|' -j STEAM_GROUP_LIMITS

    iptables -A "$chain" -p udp -m multiport --dports "$L4D2_GAMESERVER_PORTS" -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF0000|' -j DROP
    iptables -A "$chain" -p udp -m multiport --dports "$L4D2_GAMESERVER_PORTS" -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF71|' -j l4d2loginfilter
}

ip_70_l4d2_a2s_filters_apply() {
    ip_70_l4d2_a2s_filters_apply_chains

    if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
        ip_70_l4d2_a2s_filters_apply_for_chain INPUT
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -N DOCKER-USER 2>/dev/null || true
        ip_70_l4d2_a2s_filters_apply_for_chain DOCKER-USER
    fi
}
