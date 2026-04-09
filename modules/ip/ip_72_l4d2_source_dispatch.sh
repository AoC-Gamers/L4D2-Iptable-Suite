#!/bin/bash

ip_72_l4d2_source_dispatch_add_first() {
    local chain="$1"
    shift
    iptables -C "$chain" "$@" 2>/dev/null || iptables -I "$chain" 1 "$@"
}

ip_72_l4d2_source_dispatch_metadata() {
    cat << 'EOF'
ID=ip_l4d2_source_dispatch
ALIASES=l4d2_source_dispatch l4d2_query_dispatch
DESCRIPTION=Inserts early signed Source query dispatch rules before the generic UDP base limiter
REQUIRED_VARS=TYPECHAIN L4D2_GAMESERVER_UDP_PORTS L4D2_SOURCETV_UDP_PORTS
OPTIONAL_VARS=ENABLE_STEAM_GROUP_FILTER STEAM_GROUP_SIGNATURES
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_UDP_PORTS=27015 L4D2_SOURCETV_UDP_PORTS=27020 ENABLE_STEAM_GROUP_FILTER=true STEAM_GROUP_SIGNATURES=69
EOF
}

ip_72_l4d2_source_dispatch_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_l4d2_source_dispatch: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if ! [[ "${L4D2_GAMESERVER_UDP_PORTS:-}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_l4d2_source_dispatch: invalid L4D2_GAMESERVER_UDP_PORTS format"
        return 2
    fi

    if ! [[ "${L4D2_SOURCETV_UDP_PORTS:-}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_l4d2_source_dispatch: invalid L4D2_SOURCETV_UDP_PORTS format"
        return 2
    fi

    case "${ENABLE_STEAM_GROUP_FILTER:-}" in
        true|false) ;;
        *)
            echo "ERROR: ip_l4d2_source_dispatch: ENABLE_STEAM_GROUP_FILTER must be true or false"
            return 2
            ;;
    esac

    local steam_signatures="${STEAM_GROUP_SIGNATURES//[[:space:]]/}"
    if [ -n "$steam_signatures" ] && ! [[ "$steam_signatures" =~ ^[0-9A-Fa-f]{2}(,[0-9A-Fa-f]{2})*$ ]]; then
        echo "ERROR: ip_l4d2_source_dispatch: STEAM_GROUP_SIGNATURES must be comma-separated hex bytes (example: 69,00)"
        return 2
    fi
}

ip_72_l4d2_source_dispatch_assert_chain() {
    local chain="$1"
    if ! iptables -nL "$chain" >/dev/null 2>&1; then
        echo "ERROR: ip_l4d2_source_dispatch: required chain '$chain' is missing"
        echo "ERROR: ip_l4d2_source_dispatch: include l4d2_a2s_filters before l4d2_source_dispatch"
        return 2
    fi
}

ip_72_l4d2_source_dispatch_apply_for_chain() {
    local chain="$1"
    local target_ports
    local steam_signatures_csv steam_sig
    local -a steam_signatures

    target_ports="${L4D2_GAMESERVER_UDP_PORTS},${L4D2_SOURCETV_UDP_PORTS}"
    target_ports="${target_ports//,,/,}"
    target_ports="${target_ports#,}"
    target_ports="${target_ports%,}"

    if [ "${ENABLE_STEAM_GROUP_FILTER}" = "true" ]; then
        steam_signatures_csv="${STEAM_GROUP_SIGNATURES//[[:space:]]/}"
        IFS=',' read -r -a steam_signatures <<< "$steam_signatures_csv"
        for steam_sig in "${steam_signatures[@]}"; do
            [ -z "$steam_sig" ] && continue
            steam_sig="${steam_sig^^}"
            case "$steam_sig" in
                54|55|56|57|69|71) continue ;;
            esac
            ip_72_l4d2_source_dispatch_add_first "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string "|FFFFFFFF${steam_sig}|" -j STEAM_GROUP_LIMITS
        done
    fi

    # Documented signed queries should be dispatched before the generic
    # UDP_NEW_LIMIT path so A2S/login handling does not depend on a RETURN list
    # inside ip_l4d2_udp_base.
    ip_72_l4d2_source_dispatch_add_first "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF69|' -j STEAM_GROUP_LIMITS
    ip_72_l4d2_source_dispatch_add_first "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF57|' -j A2S_LIMITS
    ip_72_l4d2_source_dispatch_add_first "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF56|' -j A2S_RULES_LIMITS
    ip_72_l4d2_source_dispatch_add_first "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF55|' -j A2S_PLAYERS_LIMITS
    ip_72_l4d2_source_dispatch_add_first "$chain" -p udp -m multiport --dports "$target_ports" -m string --algo bm --hex-string '|FFFFFFFF54|' -j A2S_LIMITS
    ip_72_l4d2_source_dispatch_add_first "$chain" -p udp -m multiport --dports "$L4D2_GAMESERVER_UDP_PORTS" -m length --length 1:70 -m string --algo bm --hex-string '|FFFFFFFF71|' -j l4d2loginfilter
}

ip_72_l4d2_source_dispatch_apply() {
    ip_72_l4d2_source_dispatch_assert_chain A2S_LIMITS || return $?
    ip_72_l4d2_source_dispatch_assert_chain A2S_PLAYERS_LIMITS || return $?
    ip_72_l4d2_source_dispatch_assert_chain A2S_RULES_LIMITS || return $?
    ip_72_l4d2_source_dispatch_assert_chain STEAM_GROUP_LIMITS || return $?
    ip_72_l4d2_source_dispatch_assert_chain l4d2loginfilter || return $?

    if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
        ip_72_l4d2_source_dispatch_apply_for_chain INPUT
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -N DOCKER-USER 2>/dev/null || true
        ip_72_l4d2_source_dispatch_apply_for_chain DOCKER-USER
    fi
}
