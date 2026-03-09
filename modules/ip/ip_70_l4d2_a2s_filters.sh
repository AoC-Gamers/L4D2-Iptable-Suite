#!/bin/bash

ip_70_l4d2_a2s_filters_metadata() {
    cat << 'EOF'
ID=ip_l4d2_a2s_filters
ALIASES=l4d2_a2s_filters
DESCRIPTION=Applies A2S/Steam Group filters and login-flood controls for GameServer
REQUIRED_VARS=TYPECHAIN L4D2_GAMESERVER_PORTS L4D2_TV_PORTS LOG_PREFIX_A2S_INFO LOG_PREFIX_A2S_PLAYERS LOG_PREFIX_A2S_RULES LOG_PREFIX_STEAM_GROUP LOG_PREFIX_L4D2_CONNECT LOG_PREFIX_L4D2_RESERVE
OPTIONAL_VARS=A2S_INFO_RATE A2S_INFO_BURST A2S_PLAYERS_RATE A2S_PLAYERS_BURST A2S_RULES_RATE A2S_RULES_BURST STEAM_GROUP_RATE STEAM_GROUP_BURST L4D2_LOGIN_RATE L4D2_LOGIN_BURST ENABLE_STEAM_GROUP_FILTER STEAM_GROUP_SIGNATURES
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_PORTS=27015 L4D2_TV_PORTS=27020 A2S_INFO_RATE=16 A2S_INFO_BURST=80 A2S_PLAYERS_RATE=12 A2S_PLAYERS_BURST=60 A2S_RULES_RATE=8 A2S_RULES_BURST=40 STEAM_GROUP_RATE=6 STEAM_GROUP_BURST=30 L4D2_LOGIN_RATE=4 L4D2_LOGIN_BURST=16 ENABLE_STEAM_GROUP_FILTER=true STEAM_GROUP_SIGNATURES=00 LOG_PREFIX_A2S_INFO=A2S_INFO_FLOOD: LOG_PREFIX_A2S_PLAYERS=A2S_PLAYERS_FLOOD: LOG_PREFIX_A2S_RULES=A2S_RULES_FLOOD: LOG_PREFIX_STEAM_GROUP=STEAM_GROUP_FLOOD: LOG_PREFIX_L4D2_CONNECT=L4D2_CONNECT_FLOOD: LOG_PREFIX_L4D2_RESERVE=L4D2_RESERVE_FLOOD:
EOF
}

ip_70_l4d2_a2s_filters_validate_positive_int() {
    local key="$1"
    local value="$2"

    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "ERROR: ip_l4d2_a2s_filters: $key must be numeric"
        return 2
    fi

    if [ "$value" -le 0 ]; then
        echo "ERROR: ip_l4d2_a2s_filters: $key must be > 0"
        return 2
    fi
}

ip_70_l4d2_a2s_filters_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_l4d2_a2s_filters: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    local key
    for key in \
        A2S_INFO_RATE A2S_INFO_BURST \
        A2S_PLAYERS_RATE A2S_PLAYERS_BURST \
        A2S_RULES_RATE A2S_RULES_BURST \
        STEAM_GROUP_RATE STEAM_GROUP_BURST \
        L4D2_LOGIN_RATE L4D2_LOGIN_BURST; do
        ip_70_l4d2_a2s_filters_validate_positive_int "$key" "${!key:-}" || return $?
    done

    case "${ENABLE_STEAM_GROUP_FILTER:-}" in
        true|false) ;;
        *)
            echo "ERROR: ip_l4d2_a2s_filters: ENABLE_STEAM_GROUP_FILTER must be true or false"
            return 2
            ;;
    esac

    local steam_signatures="${STEAM_GROUP_SIGNATURES//[[:space:]]/}"
    if [ "${ENABLE_STEAM_GROUP_FILTER}" = "true" ]; then
        if [ -z "$steam_signatures" ]; then
            echo "ERROR: ip_l4d2_a2s_filters: STEAM_GROUP_SIGNATURES cannot be empty when ENABLE_STEAM_GROUP_FILTER=true"
            return 2
        fi
        if ! [[ "$steam_signatures" =~ ^[0-9A-Fa-f]{2}(,[0-9A-Fa-f]{2})*$ ]]; then
            echo "ERROR: ip_l4d2_a2s_filters: STEAM_GROUP_SIGNATURES must be comma-separated hex bytes (example: 00,69)"
            return 2
        fi
    fi

    if ! [[ "${L4D2_GAMESERVER_PORTS}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_l4d2_a2s_filters: invalid L4D2_GAMESERVER_PORTS format"
        return 2
    fi

    if ! [[ "${L4D2_TV_PORTS}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_l4d2_a2s_filters: invalid L4D2_TV_PORTS format"
        return 2
    fi
}

ip_70_l4d2_a2s_filters_apply_chains() {
    iptables -A A2S_LIMITS -m hashlimit --hashlimit-upto "${A2S_INFO_RATE}/sec" --hashlimit-burst "$A2S_INFO_BURST" --hashlimit-mode dstport --hashlimit-name A2SFilter --hashlimit-htable-expire 5000 -j ACCEPT
    iptables -A A2S_LIMITS -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_A2S_INFO" --log-level 4
    iptables -A A2S_LIMITS -j DROP

    iptables -A A2S_PLAYERS_LIMITS -m hashlimit --hashlimit-upto "${A2S_PLAYERS_RATE}/sec" --hashlimit-burst "$A2S_PLAYERS_BURST" --hashlimit-mode dstport --hashlimit-name A2SPlayersFilter --hashlimit-htable-expire 5000 -j ACCEPT
    iptables -A A2S_PLAYERS_LIMITS -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_A2S_PLAYERS" --log-level 4
    iptables -A A2S_PLAYERS_LIMITS -j DROP

    iptables -A A2S_RULES_LIMITS -m hashlimit --hashlimit-upto "${A2S_RULES_RATE}/sec" --hashlimit-burst "$A2S_RULES_BURST" --hashlimit-mode dstport --hashlimit-name A2SRulesFilter --hashlimit-htable-expire 5000 -j ACCEPT
    iptables -A A2S_RULES_LIMITS -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_A2S_RULES" --log-level 4
    iptables -A A2S_RULES_LIMITS -j DROP

    iptables -A STEAM_GROUP_LIMITS -m hashlimit --hashlimit-upto "${STEAM_GROUP_RATE}/sec" --hashlimit-burst "$STEAM_GROUP_BURST" --hashlimit-mode srcip,dstport --hashlimit-name STEAMGROUPFilter --hashlimit-htable-expire 5000 -j ACCEPT
    iptables -A STEAM_GROUP_LIMITS -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_STEAM_GROUP" --log-level 4
    iptables -A STEAM_GROUP_LIMITS -j DROP

    iptables -A l4d2loginfilter -m hashlimit --hashlimit-upto "${L4D2_LOGIN_RATE}/sec" --hashlimit-burst "$L4D2_LOGIN_BURST" --hashlimit-mode srcip,dstip,dstport --hashlimit-name L4D2CONNECTPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -m string --algo bm --string "connect" -j ACCEPT
    iptables -A l4d2loginfilter -m hashlimit --hashlimit-upto "${L4D2_LOGIN_RATE}/sec" --hashlimit-burst "$L4D2_LOGIN_BURST" --hashlimit-mode srcip,dstip,dstport --hashlimit-name L4D2RESERVEPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -m string --algo bm --string "reserve" -j ACCEPT
    iptables -A l4d2loginfilter -m string --algo bm --string "connect" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_L4D2_CONNECT" --log-level 4
    iptables -A l4d2loginfilter -m string --algo bm --string "reserve" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_L4D2_RESERVE" --log-level 4
    iptables -A l4d2loginfilter -j DROP
}

ip_70_l4d2_a2s_filters_apply_for_chain() {
    local chain="$1"
    local target_ports
    local steam_signatures_csv steam_sig
    local -a steam_signatures
    target_ports="${L4D2_GAMESERVER_PORTS},${L4D2_TV_PORTS}"
    target_ports="${target_ports//,,/,}"
    target_ports="${target_ports#,}"
    target_ports="${target_ports%,}"

    iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF54|' -j A2S_LIMITS
    iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF55|' -j A2S_PLAYERS_LIMITS
    iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF56|' -j A2S_RULES_LIMITS

    if [ "${ENABLE_STEAM_GROUP_FILTER}" = "true" ]; then
        steam_signatures_csv="${STEAM_GROUP_SIGNATURES//[[:space:]]/}"
        IFS=',' read -r -a steam_signatures <<< "$steam_signatures_csv"
        for steam_sig in "${steam_signatures[@]}"; do
            [ -z "$steam_sig" ] && continue
            steam_sig="${steam_sig^^}"
            iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string "|FFFFFFFF${steam_sig}|" -j STEAM_GROUP_LIMITS
        done
    fi

    iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF0000|' -j DROP
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
