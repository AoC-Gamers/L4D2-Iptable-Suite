#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_70_l4d2_a2s_filters_metadata() {
    cat << 'EOF'
ID=nf_l4d2_a2s_filters
ALIASES=l4d2_a2s_filters
DESCRIPTION=Applies A2S/Steam Group filters and short-flood controls in the nftables backend
REQUIRED_VARS=TYPECHAIN ENABLE_L4D2_A2S_FILTERS L4D2_GAMESERVER_PORTS LOG_PREFIX_A2S_INFO LOG_PREFIX_A2S_PLAYERS LOG_PREFIX_A2S_RULES LOG_PREFIX_STEAM_GROUP LOG_PREFIX_L4D2_CONNECT LOG_PREFIX_L4D2_RESERVE
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 ENABLE_L4D2_A2S_FILTERS=true L4D2_GAMESERVER_PORTS=27015 LOG_PREFIX_A2S_INFO=A2S_INFO_FLOOD: LOG_PREFIX_A2S_PLAYERS=A2S_PLAYERS_FLOOD: LOG_PREFIX_A2S_RULES=A2S_RULES_FLOOD: LOG_PREFIX_STEAM_GROUP=STEAM_GROUP_FLOOD: LOG_PREFIX_L4D2_CONNECT=L4D2_CONNECT_FLOOD: LOG_PREFIX_L4D2_RESERVE=L4D2_RESERVE_FLOOD:
EOF
}

nf_70_l4d2_a2s_filters_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_l4d2_a2s_filters: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    case "${ENABLE_L4D2_A2S_FILTERS:-true}" in
        true|false) ;;
        *)
            echo "ERROR: nf_l4d2_a2s_filters: ENABLE_L4D2_A2S_FILTERS must be true or false"
            return 2
            ;;
    esac

    nf_validate_ports_spec "$L4D2_GAMESERVER_PORTS" "nf_l4d2_a2s_filters: L4D2_GAMESERVER_PORTS" || return $?
}

nf_70_l4d2_a2s_filters_apply() {
    local chain game_ports_expr

    if [ "${ENABLE_L4D2_A2S_FILTERS:-true}" != "true" ]; then
        echo "INFO: nf_l4d2_a2s_filters: disabled (ENABLE_L4D2_A2S_FILTERS=false), skipping"
        return 0
    fi

    game_ports_expr="$(nf_ports_set_expr "$L4D2_GAMESERVER_PORTS")"

    nft add chain inet l4d2_filter a2s_info_limit
    nft add chain inet l4d2_filter a2s_players_limit
    nft add chain inet l4d2_filter a2s_rules_limit
    nft add chain inet l4d2_filter steam_group_limit
    nft add chain inet l4d2_filter login_connect_limit
    nft add chain inet l4d2_filter login_reserve_limit

    nf_add_rule a2s_info_limit meter a2s_info_under '{ ip saddr . udp dport limit rate 8/second burst 30 packets }' accept
    nf_add_rule a2s_info_limit meter a2s_info_over '{ ip saddr . udp dport limit rate over 8/second burst 30 packets }' log prefix "\"$LOG_PREFIX_A2S_INFO \""
    nf_add_rule a2s_info_limit meter a2s_info_over_drop '{ ip saddr . udp dport limit rate over 8/second burst 30 packets }' drop

    nf_add_rule a2s_players_limit meter a2s_players_under '{ ip saddr . udp dport limit rate 8/second burst 30 packets }' accept
    nf_add_rule a2s_players_limit meter a2s_players_over '{ ip saddr . udp dport limit rate over 8/second burst 30 packets }' log prefix "\"$LOG_PREFIX_A2S_PLAYERS \""
    nf_add_rule a2s_players_limit meter a2s_players_over_drop '{ ip saddr . udp dport limit rate over 8/second burst 30 packets }' drop

    nf_add_rule a2s_rules_limit meter a2s_rules_under '{ ip saddr . udp dport limit rate 8/second burst 30 packets }' accept
    nf_add_rule a2s_rules_limit meter a2s_rules_over '{ ip saddr . udp dport limit rate over 8/second burst 30 packets }' log prefix "\"$LOG_PREFIX_A2S_RULES \""
    nf_add_rule a2s_rules_limit meter a2s_rules_over_drop '{ ip saddr . udp dport limit rate over 8/second burst 30 packets }' drop

    nf_add_rule steam_group_limit meter steam_group_under '{ ip saddr . udp dport limit rate 1/second burst 3 packets }' accept
    nf_add_rule steam_group_limit meter steam_group_over '{ ip saddr . udp dport limit rate over 1/second burst 3 packets }' log prefix "\"$LOG_PREFIX_STEAM_GROUP \""
    nf_add_rule steam_group_limit meter steam_group_over_drop '{ ip saddr . udp dport limit rate over 1/second burst 3 packets }' drop

    nf_add_rule login_connect_limit meter login_connect_under '{ ip saddr . ip daddr . udp dport limit rate 1/second burst 1 packets }' accept
    nf_add_rule login_connect_limit meter login_connect_over '{ ip saddr . ip daddr . udp dport limit rate over 1/second burst 1 packets }' log prefix "\"$LOG_PREFIX_L4D2_CONNECT \""
    nf_add_rule login_connect_limit meter login_connect_over_drop '{ ip saddr . ip daddr . udp dport limit rate over 1/second burst 1 packets }' drop

    nf_add_rule login_reserve_limit meter login_reserve_under '{ ip saddr . ip daddr . udp dport limit rate 1/second burst 1 packets }' accept
    nf_add_rule login_reserve_limit meter login_reserve_over '{ ip saddr . ip daddr . udp dport limit rate over 1/second burst 1 packets }' log prefix "\"$LOG_PREFIX_L4D2_RESERVE \""
    nf_add_rule login_reserve_limit meter login_reserve_over_drop '{ ip saddr . ip daddr . udp dport limit rate over 1/second burst 1 packets }' drop

    for chain in $(nf_get_target_chains); do
        nf_add_rule "$chain" udp dport "$game_ports_expr" @th,64,40 0xFFFFFFFF54 jump a2s_info_limit
        nf_add_rule "$chain" udp dport "$game_ports_expr" @th,64,40 0xFFFFFFFF55 jump a2s_players_limit
        nf_add_rule "$chain" udp dport "$game_ports_expr" @th,64,40 0xFFFFFFFF56 jump a2s_rules_limit
        nf_add_rule "$chain" udp dport "$game_ports_expr" @th,64,40 0xFFFFFFFF00 jump steam_group_limit

        nf_add_rule "$chain" udp dport "$game_ports_expr" meta length 1-70 @th,64,48 0xFFFFFFFF0000 drop
        nf_add_rule "$chain" udp dport "$game_ports_expr" meta length 1-70 @th,64,40 0xFFFFFFFF71 @th,104,56 0x636f6e6e656374 jump login_connect_limit
        nf_add_rule "$chain" udp dport "$game_ports_expr" meta length 1-70 @th,64,40 0xFFFFFFFF71 @th,104,56 0x72657365727665 jump login_reserve_limit
        nf_add_rule "$chain" udp dport "$game_ports_expr" meta length 1-70 @th,64,40 0xFFFFFFFF71 drop
    done
}
