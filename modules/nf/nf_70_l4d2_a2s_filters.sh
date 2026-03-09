#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_70_l4d2_a2s_filters_metadata() {
    cat << 'EOF'
ID=nf_l4d2_a2s_filters
ALIASES=l4d2_a2s_filters
DESCRIPTION=Applies A2S/Steam Group filters and short-flood controls in the nftables backend
REQUIRED_VARS=TYPECHAIN L4D2_GAMESERVER_PORTS L4D2_TV_PORTS LOG_PREFIX_A2S_INFO LOG_PREFIX_A2S_PLAYERS LOG_PREFIX_A2S_RULES LOG_PREFIX_STEAM_GROUP LOG_PREFIX_L4D2_CONNECT LOG_PREFIX_L4D2_RESERVE
OPTIONAL_VARS=A2S_INFO_RATE A2S_INFO_BURST A2S_PLAYERS_RATE A2S_PLAYERS_BURST A2S_RULES_RATE A2S_RULES_BURST STEAM_GROUP_RATE STEAM_GROUP_BURST L4D2_LOGIN_RATE L4D2_LOGIN_BURST ENABLE_STEAM_GROUP_FILTER STEAM_GROUP_SIGNATURES FIREWALL_HOST_ALIAS
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_PORTS=27015 L4D2_TV_PORTS=27020 A2S_INFO_RATE=16 A2S_INFO_BURST=80 A2S_PLAYERS_RATE=12 A2S_PLAYERS_BURST=60 A2S_RULES_RATE=8 A2S_RULES_BURST=40 STEAM_GROUP_RATE=6 STEAM_GROUP_BURST=30 L4D2_LOGIN_RATE=4 L4D2_LOGIN_BURST=16 ENABLE_STEAM_GROUP_FILTER=true STEAM_GROUP_SIGNATURES=00 LOG_PREFIX_A2S_INFO=A2S_INFO_FLOOD: LOG_PREFIX_A2S_PLAYERS=A2S_PLAYERS_FLOOD: LOG_PREFIX_A2S_RULES=A2S_RULES_FLOOD: LOG_PREFIX_STEAM_GROUP=STEAM_GROUP_FLOOD: LOG_PREFIX_L4D2_CONNECT=L4D2_CONNECT_FLOOD: LOG_PREFIX_L4D2_RESERVE=L4D2_RESERVE_FLOOD: FIREWALL_HOST_ALIAS=
EOF
}

nf_70_l4d2_a2s_filters_validate_positive_int() {
    local key="$1"
    local value="$2"

    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "ERROR: nf_l4d2_a2s_filters: $key must be numeric"
        return 2
    fi

    if [ "$value" -le 0 ]; then
        echo "ERROR: nf_l4d2_a2s_filters: $key must be > 0"
        return 2
    fi
}

nf_70_l4d2_a2s_filters_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_l4d2_a2s_filters: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    nf_validate_ports_spec "$L4D2_GAMESERVER_PORTS" "nf_l4d2_a2s_filters: L4D2_GAMESERVER_PORTS" || return $?
    nf_validate_ports_spec "$L4D2_TV_PORTS" "nf_l4d2_a2s_filters: L4D2_TV_PORTS" || return $?

    local key
    for key in \
        A2S_INFO_RATE A2S_INFO_BURST \
        A2S_PLAYERS_RATE A2S_PLAYERS_BURST \
        A2S_RULES_RATE A2S_RULES_BURST \
        STEAM_GROUP_RATE STEAM_GROUP_BURST \
        L4D2_LOGIN_RATE L4D2_LOGIN_BURST; do
        nf_70_l4d2_a2s_filters_validate_positive_int "$key" "${!key:-}" || return $?
    done

    case "${ENABLE_STEAM_GROUP_FILTER:-}" in
        true|false) ;;
        *)
            echo "ERROR: nf_l4d2_a2s_filters: ENABLE_STEAM_GROUP_FILTER must be true or false"
            return 2
            ;;
    esac

    local steam_signatures="${STEAM_GROUP_SIGNATURES//[[:space:]]/}"
    if [ "${ENABLE_STEAM_GROUP_FILTER}" = "true" ]; then
        if [ -z "$steam_signatures" ]; then
            echo "ERROR: nf_l4d2_a2s_filters: STEAM_GROUP_SIGNATURES cannot be empty when ENABLE_STEAM_GROUP_FILTER=true"
            return 2
        fi
        if ! [[ "$steam_signatures" =~ ^[0-9A-Fa-f]{2}(,[0-9A-Fa-f]{2})*$ ]]; then
            echo "ERROR: nf_l4d2_a2s_filters: STEAM_GROUP_SIGNATURES must be comma-separated hex bytes (example: 00,69)"
            return 2
        fi
    fi
}

nf_70_l4d2_a2s_filters_apply() {
    local chain game_ports_expr all_query_ports_expr
    local steam_signatures_csv steam_sig
    local -a steam_signatures
    local log_a2s_info log_a2s_players log_a2s_rules log_steam_group log_connect log_reserve log_login_short

    game_ports_expr="$(nf_ports_set_expr "$L4D2_GAMESERVER_PORTS")"
    all_query_ports_expr="{ $(nf_ports_normalize "$L4D2_GAMESERVER_PORTS"), $(nf_ports_normalize "$L4D2_TV_PORTS") }"

    nft add chain inet l4d2_filter a2s_info_limit
    nft add chain inet l4d2_filter a2s_players_limit
    nft add chain inet l4d2_filter a2s_rules_limit
    nft add chain inet l4d2_filter steam_group_limit
    nft add chain inet l4d2_filter login_connect_limit
    nft add chain inet l4d2_filter login_reserve_limit
    nft add chain inet l4d2_filter login_short_limit

    log_a2s_info="$(nf_build_log_prefix "$LOG_PREFIX_A2S_INFO" "A2S_INFO_FLOOD" "nf_70_l4d2_a2s_filters" "a2s_info_limit" "drop" "medium")"
    log_a2s_players="$(nf_build_log_prefix "$LOG_PREFIX_A2S_PLAYERS" "A2S_PLAYERS_FLOOD" "nf_70_l4d2_a2s_filters" "a2s_players_limit" "drop" "medium")"
    log_a2s_rules="$(nf_build_log_prefix "$LOG_PREFIX_A2S_RULES" "A2S_RULES_FLOOD" "nf_70_l4d2_a2s_filters" "a2s_rules_limit" "drop" "high")"
    log_steam_group="$(nf_build_log_prefix "$LOG_PREFIX_STEAM_GROUP" "STEAM_GROUP_FLOOD" "nf_70_l4d2_a2s_filters" "steam_group_limit" "drop" "medium")"
    log_connect="$(nf_build_log_prefix "$LOG_PREFIX_L4D2_CONNECT" "L4D2_CONNECT_FLOOD" "nf_70_l4d2_a2s_filters" "login_connect_limit" "drop" "high")"
    log_reserve="$(nf_build_log_prefix "$LOG_PREFIX_L4D2_RESERVE" "L4D2_RESERVE_FLOOD" "nf_70_l4d2_a2s_filters" "login_reserve_limit" "drop" "high")"
    log_login_short="$(nf_build_log_prefix "$LOG_PREFIX_L4D2_CONNECT" "L4D2_LOGIN_FLOOD" "nf_70_l4d2_a2s_filters" "login_short_limit" "drop" "high")"

    nf_add_rule a2s_info_limit meter a2s_info_under "{ ip saddr . udp dport limit rate ${A2S_INFO_RATE}/second burst ${A2S_INFO_BURST} packets }" accept
    nf_add_rule a2s_info_limit meter a2s_info_over "{ ip saddr . udp dport limit rate over ${A2S_INFO_RATE}/second burst ${A2S_INFO_BURST} packets }" log prefix "\"$log_a2s_info\""
    nf_add_rule a2s_info_limit meter a2s_info_over_drop "{ ip saddr . udp dport limit rate over ${A2S_INFO_RATE}/second burst ${A2S_INFO_BURST} packets }" drop

    nf_add_rule a2s_players_limit meter a2s_players_under "{ ip saddr . udp dport limit rate ${A2S_PLAYERS_RATE}/second burst ${A2S_PLAYERS_BURST} packets }" accept
    nf_add_rule a2s_players_limit meter a2s_players_over "{ ip saddr . udp dport limit rate over ${A2S_PLAYERS_RATE}/second burst ${A2S_PLAYERS_BURST} packets }" log prefix "\"$log_a2s_players\""
    nf_add_rule a2s_players_limit meter a2s_players_over_drop "{ ip saddr . udp dport limit rate over ${A2S_PLAYERS_RATE}/second burst ${A2S_PLAYERS_BURST} packets }" drop

    nf_add_rule a2s_rules_limit meter a2s_rules_under "{ ip saddr . udp dport limit rate ${A2S_RULES_RATE}/second burst ${A2S_RULES_BURST} packets }" accept
    nf_add_rule a2s_rules_limit meter a2s_rules_over "{ ip saddr . udp dport limit rate over ${A2S_RULES_RATE}/second burst ${A2S_RULES_BURST} packets }" log prefix "\"$log_a2s_rules\""
    nf_add_rule a2s_rules_limit meter a2s_rules_over_drop "{ ip saddr . udp dport limit rate over ${A2S_RULES_RATE}/second burst ${A2S_RULES_BURST} packets }" drop

    nf_add_rule steam_group_limit meter steam_group_under "{ ip saddr . udp dport limit rate ${STEAM_GROUP_RATE}/second burst ${STEAM_GROUP_BURST} packets }" accept
    nf_add_rule steam_group_limit meter steam_group_over "{ ip saddr . udp dport limit rate over ${STEAM_GROUP_RATE}/second burst ${STEAM_GROUP_BURST} packets }" log prefix "\"$log_steam_group\""
    nf_add_rule steam_group_limit meter steam_group_over_drop "{ ip saddr . udp dport limit rate over ${STEAM_GROUP_RATE}/second burst ${STEAM_GROUP_BURST} packets }" drop

    nf_add_rule login_connect_limit meter login_connect_under "{ ip saddr . ip daddr . udp dport limit rate ${L4D2_LOGIN_RATE}/second burst ${L4D2_LOGIN_BURST} packets }" accept
    nf_add_rule login_connect_limit meter login_connect_over "{ ip saddr . ip daddr . udp dport limit rate over ${L4D2_LOGIN_RATE}/second burst ${L4D2_LOGIN_BURST} packets }" log prefix "\"$log_connect\""
    nf_add_rule login_connect_limit meter login_connect_over_drop "{ ip saddr . ip daddr . udp dport limit rate over ${L4D2_LOGIN_RATE}/second burst ${L4D2_LOGIN_BURST} packets }" drop

    nf_add_rule login_reserve_limit meter login_reserve_under "{ ip saddr . ip daddr . udp dport limit rate ${L4D2_LOGIN_RATE}/second burst ${L4D2_LOGIN_BURST} packets }" accept
    nf_add_rule login_reserve_limit meter login_reserve_over "{ ip saddr . ip daddr . udp dport limit rate over ${L4D2_LOGIN_RATE}/second burst ${L4D2_LOGIN_BURST} packets }" log prefix "\"$log_reserve\""
    nf_add_rule login_reserve_limit meter login_reserve_over_drop "{ ip saddr . ip daddr . udp dport limit rate over ${L4D2_LOGIN_RATE}/second burst ${L4D2_LOGIN_BURST} packets }" drop

    nf_add_rule login_short_limit meter login_short_under "{ ip saddr . ip daddr . udp dport limit rate ${L4D2_LOGIN_RATE}/second burst ${L4D2_LOGIN_BURST} packets }" accept
    nf_add_rule login_short_limit meter login_short_over "{ ip saddr . ip daddr . udp dport limit rate over ${L4D2_LOGIN_RATE}/second burst ${L4D2_LOGIN_BURST} packets }" log prefix "\"$log_login_short\""
    nf_add_rule login_short_limit meter login_short_over_drop "{ ip saddr . ip daddr . udp dport limit rate over ${L4D2_LOGIN_RATE}/second burst ${L4D2_LOGIN_BURST} packets }" drop

    for chain in $(nf_get_target_chains); do
        nf_add_rule "$chain" udp dport "$all_query_ports_expr" @th,64,40 0xFFFFFFFF54 jump a2s_info_limit
        nf_add_rule "$chain" udp dport "$all_query_ports_expr" @th,64,40 0xFFFFFFFF55 jump a2s_players_limit
        nf_add_rule "$chain" udp dport "$all_query_ports_expr" @th,64,40 0xFFFFFFFF56 jump a2s_rules_limit
        if [ "${ENABLE_STEAM_GROUP_FILTER}" = "true" ]; then
            steam_signatures_csv="${STEAM_GROUP_SIGNATURES//[[:space:]]/}"
            IFS=',' read -r -a steam_signatures <<< "$steam_signatures_csv"
            for steam_sig in "${steam_signatures[@]}"; do
                [ -z "$steam_sig" ] && continue
                steam_sig="${steam_sig^^}"
                nf_add_rule "$chain" udp dport "$all_query_ports_expr" @th,64,40 "0xFFFFFFFF${steam_sig}" jump steam_group_limit
            done
        fi

        nf_add_rule "$chain" udp dport "$all_query_ports_expr" meta length 1-70 @th,64,48 0xFFFFFFFF0000 drop
        nf_add_rule "$chain" udp dport "$game_ports_expr" meta length 1-140 @th,64,40 0xFFFFFFFF71 @th,104,56 0x636f6e6e656374 jump login_connect_limit
        nf_add_rule "$chain" udp dport "$game_ports_expr" meta length 1-140 @th,64,40 0xFFFFFFFF71 @th,104,56 0x72657365727665 jump login_reserve_limit
        nf_add_rule "$chain" udp dport "$game_ports_expr" meta length 1-140 @th,64,40 0xFFFFFFFF71 jump login_short_limit
    done
}
