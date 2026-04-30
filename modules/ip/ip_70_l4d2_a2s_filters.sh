#!/bin/bash

ip_70_l4d2_a2s_filters_metadata() {
    cat << 'EOF'
ID=ip_l4d2_a2s_filters
ALIASES=l4d2_a2s_filters
DESCRIPTION=Applies A2S discovery-safe filters, Steam Group compatibility filters, and login-flood controls for GameServer
REQUIRED_VARS=TYPECHAIN L4D2_GAMESERVER_UDP_PORTS L4D2_SOURCETV_UDP_PORTS LOG_PREFIX_A2S_INFO LOG_PREFIX_A2S_PLAYERS LOG_PREFIX_A2S_RULES LOG_PREFIX_STEAM_GROUP LOG_PREFIX_L4D2_CONNECT LOG_PREFIX_L4D2_RESERVE
OPTIONAL_VARS=A2S_PROTECTION_MODE ENABLE_A2S_DISCOVERY_SAFE A2S_DISCOVERY_OBSERVE_ONLY A2S_DISCOVERY_SRC_RATE A2S_DISCOVERY_SRC_BURST A2S_DISCOVERY_GLOBAL_RATE A2S_DISCOVERY_GLOBAL_BURST A2S_PING_SRC_RATE A2S_PING_SRC_BURST A2S_INFO_RATE A2S_INFO_BURST A2S_PLAYERS_RATE A2S_PLAYERS_BURST A2S_RULES_RATE A2S_RULES_BURST STEAM_GROUP_RATE STEAM_GROUP_BURST L4D2_LOGIN_RATE L4D2_LOGIN_BURST ENABLE_STEAM_GROUP_FILTER STEAM_GROUP_SIGNATURES
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_UDP_PORTS=27015 L4D2_SOURCETV_UDP_PORTS=27020 A2S_PROTECTION_MODE=balanced ENABLE_A2S_DISCOVERY_SAFE=true A2S_DISCOVERY_OBSERVE_ONLY=false ENABLE_STEAM_GROUP_FILTER=true STEAM_GROUP_SIGNATURES=69 LOG_PREFIX_A2S_INFO=A2S_INFO_FLOOD: LOG_PREFIX_A2S_PLAYERS=A2S_PLAYERS_FLOOD: LOG_PREFIX_A2S_RULES=A2S_RULES_FLOOD: LOG_PREFIX_STEAM_GROUP=STEAM_GROUP_FLOOD: LOG_PREFIX_L4D2_CONNECT=L4D2_CONNECT_FLOOD: LOG_PREFIX_L4D2_RESERVE=L4D2_RESERVE_FLOOD:
EOF
}

ip_70_l4d2_a2s_filters_set_default() {
    local key="$1"
    local value="$2"

    if [ -z "${!key:-}" ]; then
        export "$key=$value"
    fi
}

ip_70_l4d2_a2s_filters_apply_profile() {
    local mode="${A2S_PROTECTION_MODE:-balanced}"
    mode="${mode,,}"
    export A2S_PROTECTION_MODE="$mode"

    case "$mode" in
        visibility)
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_SRC_RATE 120
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_SRC_BURST 600
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_GLOBAL_RATE 1500
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_GLOBAL_BURST 6000
            ip_70_l4d2_a2s_filters_set_default A2S_PING_SRC_RATE 120
            ip_70_l4d2_a2s_filters_set_default A2S_PING_SRC_BURST 600
            ip_70_l4d2_a2s_filters_set_default A2S_INFO_RATE 120
            ip_70_l4d2_a2s_filters_set_default A2S_INFO_BURST 600
            ip_70_l4d2_a2s_filters_set_default STEAM_GROUP_RATE 60
            ip_70_l4d2_a2s_filters_set_default STEAM_GROUP_BURST 300
            ip_70_l4d2_a2s_filters_set_default A2S_PLAYERS_RATE 24
            ip_70_l4d2_a2s_filters_set_default A2S_PLAYERS_BURST 120
            ip_70_l4d2_a2s_filters_set_default A2S_RULES_RATE 14
            ip_70_l4d2_a2s_filters_set_default A2S_RULES_BURST 70
            ;;
        balanced)
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_SRC_RATE 80
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_SRC_BURST 400
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_GLOBAL_RATE 900
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_GLOBAL_BURST 3600
            ip_70_l4d2_a2s_filters_set_default A2S_PING_SRC_RATE 80
            ip_70_l4d2_a2s_filters_set_default A2S_PING_SRC_BURST 400
            ip_70_l4d2_a2s_filters_set_default A2S_INFO_RATE 75
            ip_70_l4d2_a2s_filters_set_default A2S_INFO_BURST 375
            ip_70_l4d2_a2s_filters_set_default STEAM_GROUP_RATE 30
            ip_70_l4d2_a2s_filters_set_default STEAM_GROUP_BURST 150
            ip_70_l4d2_a2s_filters_set_default A2S_PLAYERS_RATE 24
            ip_70_l4d2_a2s_filters_set_default A2S_PLAYERS_BURST 120
            ip_70_l4d2_a2s_filters_set_default A2S_RULES_RATE 12
            ip_70_l4d2_a2s_filters_set_default A2S_RULES_BURST 60
            ;;
        strict)
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_SRC_RATE 30
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_SRC_BURST 160
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_GLOBAL_RATE 450
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_GLOBAL_BURST 1800
            ip_70_l4d2_a2s_filters_set_default A2S_PING_SRC_RATE 30
            ip_70_l4d2_a2s_filters_set_default A2S_PING_SRC_BURST 160
            ip_70_l4d2_a2s_filters_set_default A2S_INFO_RATE 30
            ip_70_l4d2_a2s_filters_set_default A2S_INFO_BURST 160
            ip_70_l4d2_a2s_filters_set_default STEAM_GROUP_RATE 15
            ip_70_l4d2_a2s_filters_set_default STEAM_GROUP_BURST 80
            ip_70_l4d2_a2s_filters_set_default A2S_PLAYERS_RATE 16
            ip_70_l4d2_a2s_filters_set_default A2S_PLAYERS_BURST 80
            ip_70_l4d2_a2s_filters_set_default A2S_RULES_RATE 8
            ip_70_l4d2_a2s_filters_set_default A2S_RULES_BURST 40
            ;;
        custom)
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_SRC_RATE 80
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_SRC_BURST 400
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_GLOBAL_RATE 900
            ip_70_l4d2_a2s_filters_set_default A2S_DISCOVERY_GLOBAL_BURST 3600
            ip_70_l4d2_a2s_filters_set_default A2S_PING_SRC_RATE 80
            ip_70_l4d2_a2s_filters_set_default A2S_PING_SRC_BURST 400
            ip_70_l4d2_a2s_filters_set_default A2S_INFO_RATE 16
            ip_70_l4d2_a2s_filters_set_default A2S_INFO_BURST 80
            ip_70_l4d2_a2s_filters_set_default STEAM_GROUP_RATE 6
            ip_70_l4d2_a2s_filters_set_default STEAM_GROUP_BURST 30
            ip_70_l4d2_a2s_filters_set_default A2S_PLAYERS_RATE 12
            ip_70_l4d2_a2s_filters_set_default A2S_PLAYERS_BURST 60
            ip_70_l4d2_a2s_filters_set_default A2S_RULES_RATE 8
            ip_70_l4d2_a2s_filters_set_default A2S_RULES_BURST 40
            ;;
        *)
            echo "ERROR: ip_l4d2_a2s_filters: A2S_PROTECTION_MODE must be visibility, balanced, strict or custom"
            return 2
            ;;
    esac

    ip_70_l4d2_a2s_filters_set_default L4D2_LOGIN_RATE 4
    ip_70_l4d2_a2s_filters_set_default L4D2_LOGIN_BURST 16
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

ip_70_l4d2_a2s_filters_validate_bool() {
    local key="$1"
    local value="$2"

    case "$value" in
        true|false) ;;
        *)
            echo "ERROR: ip_l4d2_a2s_filters: $key must be true or false"
            return 2
            ;;
    esac
}

ip_70_l4d2_a2s_filters_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_l4d2_a2s_filters: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    ip_70_l4d2_a2s_filters_apply_profile || return $?

    local key
    for key in \
        A2S_DISCOVERY_SRC_RATE A2S_DISCOVERY_SRC_BURST \
        A2S_DISCOVERY_GLOBAL_RATE A2S_DISCOVERY_GLOBAL_BURST \
        A2S_PING_SRC_RATE A2S_PING_SRC_BURST \
        A2S_INFO_RATE A2S_INFO_BURST \
        A2S_PLAYERS_RATE A2S_PLAYERS_BURST \
        A2S_RULES_RATE A2S_RULES_BURST \
        STEAM_GROUP_RATE STEAM_GROUP_BURST \
        L4D2_LOGIN_RATE L4D2_LOGIN_BURST; do
        ip_70_l4d2_a2s_filters_validate_positive_int "$key" "${!key:-}" || return $?
    done

    ip_70_l4d2_a2s_filters_validate_bool ENABLE_A2S_DISCOVERY_SAFE "${ENABLE_A2S_DISCOVERY_SAFE:-}" || return $?
    ip_70_l4d2_a2s_filters_validate_bool A2S_DISCOVERY_OBSERVE_ONLY "${A2S_DISCOVERY_OBSERVE_ONLY:-}" || return $?
    ip_70_l4d2_a2s_filters_validate_bool ENABLE_STEAM_GROUP_FILTER "${ENABLE_STEAM_GROUP_FILTER:-}" || return $?

    local steam_signatures="${STEAM_GROUP_SIGNATURES//[[:space:]]/}"
    if [ "${ENABLE_STEAM_GROUP_FILTER}" = "true" ]; then
        if [ -z "$steam_signatures" ]; then
            echo "ERROR: ip_l4d2_a2s_filters: STEAM_GROUP_SIGNATURES cannot be empty when ENABLE_STEAM_GROUP_FILTER=true"
            return 2
        fi
        if ! [[ "$steam_signatures" =~ ^[0-9A-Fa-f]{2}(,[0-9A-Fa-f]{2})*$ ]]; then
            echo "ERROR: ip_l4d2_a2s_filters: STEAM_GROUP_SIGNATURES must be comma-separated hex bytes (example: 69,00)"
            return 2
        fi
    fi

    if ! [[ "${L4D2_GAMESERVER_UDP_PORTS}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_l4d2_a2s_filters: invalid L4D2_GAMESERVER_UDP_PORTS format"
        return 2
    fi

    if ! [[ "${L4D2_SOURCETV_UDP_PORTS}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_l4d2_a2s_filters: invalid L4D2_SOURCETV_UDP_PORTS format"
        return 2
    fi
}

ip_70_l4d2_a2s_filters_ensure_chain() {
    local chain="$1"

    iptables -N "$chain" 2>/dev/null || iptables -F "$chain"
}

ip_70_l4d2_a2s_filters_discovery_terminal_action() {
    if [ "${A2S_DISCOVERY_OBSERVE_ONLY}" = "true" ]; then
        echo ACCEPT
    else
        echo DROP
    fi
}

ip_70_l4d2_a2s_filters_add_log_and_terminal() {
    local chain="$1"
    local prefix="$2"
    local terminal="$3"

    iptables -A "$chain" -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$prefix" --log-level 4
    iptables -A "$chain" -j "$terminal"
}

ip_70_l4d2_a2s_filters_apply_discovery_chains() {
    local discovery_terminal
    discovery_terminal="$(ip_70_l4d2_a2s_filters_discovery_terminal_action)"

    iptables -A A2S_DISCOVERY_INFO \
        -m hashlimit --hashlimit-upto "${A2S_DISCOVERY_SRC_RATE}/sec" \
        --hashlimit-burst "$A2S_DISCOVERY_SRC_BURST" \
        --hashlimit-mode srcip,dstport \
        --hashlimit-name A2SInfoDiscoverySrc \
        --hashlimit-htable-expire 30000 \
        -j A2S_DISCOVERY_INFO_GLOBAL
    ip_70_l4d2_a2s_filters_add_log_and_terminal A2S_DISCOVERY_INFO "$LOG_PREFIX_A2S_INFO" "$discovery_terminal"

    iptables -A A2S_DISCOVERY_INFO_GLOBAL \
        -m hashlimit --hashlimit-upto "${A2S_DISCOVERY_GLOBAL_RATE}/sec" \
        --hashlimit-burst "$A2S_DISCOVERY_GLOBAL_BURST" \
        --hashlimit-mode dstport \
        --hashlimit-name A2SInfoDiscoveryGlobal \
        --hashlimit-htable-expire 30000 \
        -j ACCEPT
    ip_70_l4d2_a2s_filters_add_log_and_terminal A2S_DISCOVERY_INFO_GLOBAL "$LOG_PREFIX_A2S_INFO" "$discovery_terminal"

    iptables -A A2S_DISCOVERY_PING \
        -m hashlimit --hashlimit-upto "${A2S_PING_SRC_RATE}/sec" \
        --hashlimit-burst "$A2S_PING_SRC_BURST" \
        --hashlimit-mode srcip,dstport \
        --hashlimit-name A2SPingDiscoverySrc \
        --hashlimit-htable-expire 30000 \
        -j A2S_DISCOVERY_PING_GLOBAL
    ip_70_l4d2_a2s_filters_add_log_and_terminal A2S_DISCOVERY_PING "$LOG_PREFIX_STEAM_GROUP" "$discovery_terminal"

    iptables -A A2S_DISCOVERY_PING_GLOBAL \
        -m hashlimit --hashlimit-upto "${A2S_DISCOVERY_GLOBAL_RATE}/sec" \
        --hashlimit-burst "$A2S_DISCOVERY_GLOBAL_BURST" \
        --hashlimit-mode dstport \
        --hashlimit-name A2SPingDiscoveryGlobal \
        --hashlimit-htable-expire 30000 \
        -j ACCEPT
    ip_70_l4d2_a2s_filters_add_log_and_terminal A2S_DISCOVERY_PING_GLOBAL "$LOG_PREFIX_STEAM_GROUP" "$discovery_terminal"
}

ip_70_l4d2_a2s_filters_apply_chains() {
    local chain
    for chain in \
        A2S_LIMITS A2S_PLAYERS_LIMITS A2S_RULES_LIMITS STEAM_GROUP_LIMITS \
        A2S_DISCOVERY_INFO A2S_DISCOVERY_INFO_GLOBAL \
        A2S_DISCOVERY_PING A2S_DISCOVERY_PING_GLOBAL \
        l4d2loginfilter; do
        ip_70_l4d2_a2s_filters_ensure_chain "$chain"
    done

    ip_70_l4d2_a2s_filters_apply_discovery_chains

    # Legacy A2S_INFO path kept for compatibility when discovery-safe mode is disabled.
    iptables -A A2S_LIMITS -m hashlimit --hashlimit-upto "${A2S_INFO_RATE}/sec" --hashlimit-burst "$A2S_INFO_BURST" --hashlimit-mode srcip,dstport --hashlimit-name A2SFilter --hashlimit-htable-expire 5000 -j ACCEPT
    ip_70_l4d2_a2s_filters_add_log_and_terminal A2S_LIMITS "$LOG_PREFIX_A2S_INFO" DROP

    iptables -A A2S_PLAYERS_LIMITS -m hashlimit --hashlimit-upto "${A2S_PLAYERS_RATE}/sec" --hashlimit-burst "$A2S_PLAYERS_BURST" --hashlimit-mode srcip,dstport --hashlimit-name A2SPlayersFilter --hashlimit-htable-expire 5000 -j ACCEPT
    ip_70_l4d2_a2s_filters_add_log_and_terminal A2S_PLAYERS_LIMITS "$LOG_PREFIX_A2S_PLAYERS" DROP

    iptables -A A2S_RULES_LIMITS -m hashlimit --hashlimit-upto "${A2S_RULES_RATE}/sec" --hashlimit-burst "$A2S_RULES_BURST" --hashlimit-mode srcip,dstport --hashlimit-name A2SRulesFilter --hashlimit-htable-expire 5000 -j ACCEPT
    ip_70_l4d2_a2s_filters_add_log_and_terminal A2S_RULES_LIMITS "$LOG_PREFIX_A2S_RULES" DROP

    # Compatibility path for Steam/legacy signatures other than discovery-safe 0x69.
    iptables -A STEAM_GROUP_LIMITS -m hashlimit --hashlimit-upto "${STEAM_GROUP_RATE}/sec" --hashlimit-burst "$STEAM_GROUP_BURST" --hashlimit-mode srcip,dstport --hashlimit-name STEAMGROUPFilter --hashlimit-htable-expire 5000 -j ACCEPT
    ip_70_l4d2_a2s_filters_add_log_and_terminal STEAM_GROUP_LIMITS "$LOG_PREFIX_STEAM_GROUP" DROP

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
    target_ports="${L4D2_GAMESERVER_UDP_PORTS},${L4D2_SOURCETV_UDP_PORTS}"
    target_ports="${target_ports//,,/,}"
    target_ports="${target_ports#,}"
    target_ports="${target_ports%,}"

    if [ "${ENABLE_A2S_DISCOVERY_SAFE}" = "true" ]; then
        # A2S_INFO (0x54) is critical for Steam/server-browser visibility and
        # may include a challenge appended after the base query. Keep it on a
        # dedicated, permissive-but-capped path instead of the generic A2S chain.
        iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF54|' -j A2S_DISCOVERY_INFO

        # A2A_PING (0x69) is deprecated but still seen in some tooling. Treat it
        # as discovery-compatible traffic while keeping a separate cap.
        iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF69|' -j A2S_DISCOVERY_PING
    else
        iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF54|' -j A2S_LIMITS
    fi

    iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF55|' -j A2S_PLAYERS_LIMITS
    iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF56|' -j A2S_RULES_LIMITS

    if [ "${ENABLE_STEAM_GROUP_FILTER}" = "true" ]; then
        steam_signatures_csv="${STEAM_GROUP_SIGNATURES//[[:space:]]/}"
        IFS=',' read -r -a steam_signatures <<< "$steam_signatures_csv"
        for steam_sig in "${steam_signatures[@]}"; do
            [ -z "$steam_sig" ] && continue
            steam_sig="${steam_sig^^}"
            case "$steam_sig" in
                54|55|56|71) continue ;;
                69)
                    [ "${ENABLE_A2S_DISCOVERY_SAFE}" = "true" ] && continue
                    ;;
            esac
            iptables -A "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string "|FFFFFFFF${steam_sig}|" -j STEAM_GROUP_LIMITS
        done
    fi

    iptables -A "$chain" -p udp -m multiport --dports "$L4D2_GAMESERVER_UDP_PORTS" -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF71|' -j l4d2loginfilter
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
