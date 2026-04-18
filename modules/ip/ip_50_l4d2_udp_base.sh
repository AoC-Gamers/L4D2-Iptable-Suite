#!/bin/bash

ip_50_l4d2_udp_base_metadata() {
    cat << 'EOF'
ID=ip_l4d2_udp_base
ALIASES=l4d2_udp_base
DESCRIPTION=Applies base UDP/state/ICMP rules for GameServer and SourceTV services
REQUIRED_VARS=TYPECHAIN L4D2_GAMESERVER_UDP_PORTS L4D2_SOURCETV_UDP_PORTS L4D2_CMD_LIMIT LOG_PREFIX_UDP_NEW_LIMIT LOG_PREFIX_UDP_EST_LIMIT LOG_PREFIX_ICMP_FLOOD
OPTIONAL_VARS=ENABLE_UDP_BASELINE_LOGS UDP_NEW_SRC_RATE UDP_NEW_SRC_BURST UDP_NEW_GLOBAL_RATE UDP_NEW_GLOBAL_BURST ENABLE_UDP_NEW_FFFFFFFF_BYPASS ENABLE_STEAM_GROUP_FILTER STEAM_GROUP_SIGNATURES ENABLE_UDP_NEW_LARGE_FILTER UDP_NEW_LARGE_DROP_MIN_LEN
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_UDP_PORTS=27015 L4D2_SOURCETV_UDP_PORTS=27020 L4D2_CMD_LIMIT=100 LOG_PREFIX_UDP_NEW_LIMIT=UDP_NEW_LIMIT: LOG_PREFIX_UDP_EST_LIMIT=UDP_EST_LIMIT: LOG_PREFIX_ICMP_FLOOD=ICMP_FLOOD: ENABLE_UDP_BASELINE_LOGS=false UDP_NEW_SRC_RATE=8 UDP_NEW_SRC_BURST=24 UDP_NEW_GLOBAL_RATE=240 UDP_NEW_GLOBAL_BURST=960 ENABLE_UDP_NEW_FFFFFFFF_BYPASS=true ENABLE_STEAM_GROUP_FILTER=true STEAM_GROUP_SIGNATURES=69 ENABLE_UDP_NEW_LARGE_FILTER=false UDP_NEW_LARGE_DROP_MIN_LEN=1024
EOF
}

ip_50_l4d2_udp_base_validate_positive_int() {
    local key="$1"
    local value="$2"

    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "ERROR: ip_l4d2_udp_base: $key must be numeric"
        return 2
    fi

    if [ "$value" -le 0 ]; then
        echo "ERROR: ip_l4d2_udp_base: $key must be > 0"
        return 2
    fi
}

ip_50_l4d2_udp_base_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_l4d2_udp_base: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if ! [[ "${L4D2_CMD_LIMIT}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: ip_l4d2_udp_base: L4D2_CMD_LIMIT must be numeric"
        return 2
    fi

    if [ "$L4D2_CMD_LIMIT" -lt 10 ] || [ "$L4D2_CMD_LIMIT" -gt 10000 ]; then
        echo "ERROR: ip_l4d2_udp_base: L4D2_CMD_LIMIT must be between 10 and 10000"
        return 2
    fi

    local key
    for key in UDP_NEW_SRC_RATE UDP_NEW_SRC_BURST UDP_NEW_GLOBAL_RATE UDP_NEW_GLOBAL_BURST UDP_NEW_LARGE_DROP_MIN_LEN; do
        ip_50_l4d2_udp_base_validate_positive_int "$key" "${!key:-}" || return $?
    done

    if [ "$UDP_NEW_LARGE_DROP_MIN_LEN" -lt 69 ] || [ "$UDP_NEW_LARGE_DROP_MIN_LEN" -gt 65535 ]; then
        echo "ERROR: ip_l4d2_udp_base: UDP_NEW_LARGE_DROP_MIN_LEN must be between 69 and 65535"
        return 2
    fi

    if [ -n "${L4D2_GAMESERVER_UDP_PORTS:-}" ] && ! [[ "${L4D2_GAMESERVER_UDP_PORTS}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_l4d2_udp_base: invalid L4D2_GAMESERVER_UDP_PORTS format"
        return 2
    fi

    if [ -n "${L4D2_SOURCETV_UDP_PORTS:-}" ] && ! [[ "${L4D2_SOURCETV_UDP_PORTS}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_l4d2_udp_base: invalid L4D2_SOURCETV_UDP_PORTS format"
        return 2
    fi

    case "${ENABLE_UDP_BASELINE_LOGS:-}" in
        true|false) ;;
        *)
            echo "ERROR: ip_l4d2_udp_base: ENABLE_UDP_BASELINE_LOGS must be true or false"
            return 2
            ;;
    esac

    case "${ENABLE_UDP_NEW_FFFFFFFF_BYPASS:-}" in
        true|false) ;;
        *)
            echo "ERROR: ip_l4d2_udp_base: ENABLE_UDP_NEW_FFFFFFFF_BYPASS must be true or false"
            return 2
            ;;
    esac

    case "${ENABLE_UDP_NEW_LARGE_FILTER:-}" in
        true|false) ;;
        *)
            echo "ERROR: ip_l4d2_udp_base: ENABLE_UDP_NEW_LARGE_FILTER must be true or false"
            return 2
            ;;
    esac

    case "${ENABLE_STEAM_GROUP_FILTER:-}" in
        true|false) ;;
        *)
            echo "ERROR: ip_l4d2_udp_base: ENABLE_STEAM_GROUP_FILTER must be true or false"
            return 2
            ;;
    esac

    local steam_signatures="${STEAM_GROUP_SIGNATURES//[[:space:]]/}"
    if [ -n "$steam_signatures" ] && ! [[ "$steam_signatures" =~ ^[0-9A-Fa-f]{2}(,[0-9A-Fa-f]{2})*$ ]]; then
        echo "ERROR: ip_l4d2_udp_base: STEAM_GROUP_SIGNATURES must be comma-separated hex bytes (example: 69,00)"
        return 2
    fi
}

ip_50_l4d2_udp_base_apply() {
    local cmd_limit_leeway=$((L4D2_CMD_LIMIT + 10))
    local cmd_limit_upper=$((L4D2_CMD_LIMIT + 30))
    local steam_signatures_csv steam_sig
    local -a steam_signatures

    if [ "${ENABLE_UDP_NEW_FFFFFFFF_BYPASS}" = "true" ]; then
        # Only bypass signatures that have an actual downstream classifier.
        # Everything else should stay under the generic NEW limiter instead of
        # falling through to the INPUT/DOCKER-USER default DROP policy.
        iptables -A UDP_GAME_NEW_LIMIT -m string --algo bm --hex-string '|FFFFFFFF54|' -j RETURN
        iptables -A UDP_GAME_NEW_LIMIT -m string --algo bm --hex-string '|FFFFFFFF55|' -j RETURN
        iptables -A UDP_GAME_NEW_LIMIT -m string --algo bm --hex-string '|FFFFFFFF56|' -j RETURN
        # L4D2 login/connect classifiers only apply to GameServer ports. SourceTV
        # also sends FFFFFFFF71 connect handshakes, but those should stay under
        # the generic NEW limiter so short legitimate TV packets are accepted.
        iptables -A UDP_GAME_NEW_LIMIT -p udp -m multiport --dports "$L4D2_GAMESERVER_UDP_PORTS" -m string --algo bm --hex-string '|FFFFFFFF71|' -j RETURN

        if [ "${ENABLE_STEAM_GROUP_FILTER}" = "true" ]; then
            steam_signatures_csv="${STEAM_GROUP_SIGNATURES//[[:space:]]/}"
            IFS=',' read -r -a steam_signatures <<< "$steam_signatures_csv"
            for steam_sig in "${steam_signatures[@]}"; do
                [ -z "$steam_sig" ] && continue
                steam_sig="${steam_sig^^}"
                case "$steam_sig" in
                    54|55|56|71) continue ;;
                esac
                iptables -A UDP_GAME_NEW_LIMIT -m string --algo bm --hex-string "|FFFFFFFF${steam_sig}|" -j RETURN
            done
        fi
    fi

    if [ "${ENABLE_UDP_NEW_LARGE_FILTER}" = "true" ]; then
        if [ "${ENABLE_UDP_BASELINE_LOGS}" = "true" ]; then
            iptables -A UDP_GAME_NEW_LIMIT -m length --length "${UDP_NEW_LARGE_DROP_MIN_LEN}:65535" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_UDP_NEW_LIMIT" --log-level 4
        fi
        iptables -A UDP_GAME_NEW_LIMIT -m length --length "${UDP_NEW_LARGE_DROP_MIN_LEN}:65535" -j DROP
    fi

    iptables -A UDP_GAME_NEW_LIMIT -m hashlimit --hashlimit-upto "${UDP_NEW_SRC_RATE}/s" --hashlimit-burst "$UDP_NEW_SRC_BURST" --hashlimit-mode srcip,dstport --hashlimit-name L4D2_NEW_HASHLIMIT --hashlimit-htable-expire 5000 -j UDP_GAME_NEW_LIMIT_GLOBAL
    if [ "${ENABLE_UDP_BASELINE_LOGS}" = "true" ]; then
        iptables -A UDP_GAME_NEW_LIMIT -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_UDP_NEW_LIMIT" --log-level 4
    fi
    iptables -A UDP_GAME_NEW_LIMIT -j DROP

    iptables -A UDP_GAME_NEW_LIMIT_GLOBAL -m hashlimit --hashlimit-upto "${UDP_NEW_GLOBAL_RATE}/s" --hashlimit-burst "$UDP_NEW_GLOBAL_BURST" --hashlimit-mode dstport --hashlimit-name L4D2_NEW_HASHLIMIT_GLOBAL --hashlimit-htable-expire 5000 -j ACCEPT
    if [ "${ENABLE_UDP_BASELINE_LOGS}" = "true" ]; then
        iptables -A UDP_GAME_NEW_LIMIT_GLOBAL -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_UDP_NEW_LIMIT" --log-level 4
    fi
    iptables -A UDP_GAME_NEW_LIMIT_GLOBAL -j DROP

    iptables -A UDP_GAME_ESTABLISHED_LIMIT -m hashlimit --hashlimit-upto ${cmd_limit_leeway}/s --hashlimit-burst ${cmd_limit_upper} --hashlimit-mode srcip,srcport,dstport --hashlimit-name L4D2_ESTABLISHED_HASHLIMIT -j ACCEPT
    if [ "${ENABLE_UDP_BASELINE_LOGS}" = "true" ]; then
        iptables -A UDP_GAME_ESTABLISHED_LIMIT -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_UDP_EST_LIMIT" --log-level 4
    fi
    iptables -A UDP_GAME_ESTABLISHED_LIMIT -j DROP

    local chain
    for chain in INPUT DOCKER-USER; do
        if [ "$chain" = "DOCKER-USER" ] && [ "$TYPECHAIN" -eq 0 ]; then
            continue
        fi
        if [ "$chain" = "INPUT" ] && [ "$TYPECHAIN" -eq 1 ]; then
            continue
        fi

        iptables -A "$chain" -p udp -m multiport --dports "$L4D2_GAMESERVER_UDP_PORTS" -m state --state NEW -j UDP_GAME_NEW_LIMIT
        iptables -A "$chain" -p udp -m multiport --dports "$L4D2_SOURCETV_UDP_PORTS" -m state --state NEW -j UDP_GAME_NEW_LIMIT

        iptables -A "$chain" -p udp -m multiport --dports "$L4D2_GAMESERVER_UDP_PORTS" -m state --state ESTABLISHED -j UDP_GAME_ESTABLISHED_LIMIT
        iptables -A "$chain" -p udp -m multiport --dports "$L4D2_SOURCETV_UDP_PORTS" -m state --state ESTABLISHED -j UDP_GAME_ESTABLISHED_LIMIT
    done

    iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -A DOCKER-USER -m state --state ESTABLISHED,RELATED -j ACCEPT
    fi

    iptables -A INPUT -p udp --sport 53 -m state --state ESTABLISHED,RELATED -j ACCEPT
    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -A DOCKER-USER -p udp --sport 53 -m state --state ESTABLISHED,RELATED -j ACCEPT
    fi

    if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -A INPUT -p icmp -m hashlimit --hashlimit-upto 20/sec --hashlimit-burst 2 --hashlimit-mode dstip --hashlimit-name PINGPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -j ACCEPT
        iptables -A INPUT -p icmp -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$LOG_PREFIX_ICMP_FLOOD" --log-level 4
        iptables -A INPUT -p icmp -j DROP
    fi
    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -A DOCKER-USER -p icmp -m hashlimit --hashlimit-upto 20/sec --hashlimit-burst 2 --hashlimit-mode dstip --hashlimit-name PINGPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -j ACCEPT
        iptables -A DOCKER-USER -p icmp -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$LOG_PREFIX_ICMP_FLOOD" --log-level 4
        iptables -A DOCKER-USER -p icmp -j DROP
    fi
}
