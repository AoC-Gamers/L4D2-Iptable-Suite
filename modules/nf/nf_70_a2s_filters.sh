#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_70_a2s_filters_metadata() {
    cat << 'EOF'
ID=nf_a2s_filters
DESCRIPTION=Filtros A2S/Steam Group y control de flood corto para nftables
REQUIRED_VARS=TYPECHAIN GAMESERVERPORTS LOG_PREFIX_A2S_INFO LOG_PREFIX_A2S_PLAYERS LOG_PREFIX_A2S_RULES LOG_PREFIX_STEAM_GROUP LOG_PREFIX_L4D2_CONNECT LOG_PREFIX_L4D2_RESERVE
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 GAMESERVERPORTS=27015 LOG_PREFIX_A2S_INFO=A2S_INFO_FLOOD: LOG_PREFIX_A2S_PLAYERS=A2S_PLAYERS_FLOOD: LOG_PREFIX_A2S_RULES=A2S_RULES_FLOOD: LOG_PREFIX_STEAM_GROUP=STEAM_GROUP_FLOOD: LOG_PREFIX_L4D2_CONNECT=L4D2_CONNECT_FLOOD: LOG_PREFIX_L4D2_RESERVE=L4D2_RESERVE_FLOOD:
EOF
}

nf_70_a2s_filters_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_a2s_filters: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac
}

nf_70_a2s_filters_apply() {
    local chain game_ports_expr
    game_ports_expr="$(nf_ports_set_expr "$GAMESERVERPORTS")"

    nft add chain inet l4d2_filter a2s_info_limit
    nft add chain inet l4d2_filter a2s_players_limit
    nft add chain inet l4d2_filter a2s_rules_limit
    nft add chain inet l4d2_filter steam_group_limit
    nft add chain inet l4d2_filter login_filter

    nf_add_rule a2s_info_limit limit rate 8/second burst 30 packets accept
    nf_add_rule a2s_info_limit limit rate over 60/minute burst 20 packets log prefix "$LOG_PREFIX_A2S_INFO "
    nf_add_rule a2s_info_limit drop

    nf_add_rule a2s_players_limit limit rate 8/second burst 30 packets accept
    nf_add_rule a2s_players_limit limit rate over 60/minute burst 20 packets log prefix "$LOG_PREFIX_A2S_PLAYERS "
    nf_add_rule a2s_players_limit drop

    nf_add_rule a2s_rules_limit limit rate 8/second burst 30 packets accept
    nf_add_rule a2s_rules_limit limit rate over 60/minute burst 20 packets log prefix "$LOG_PREFIX_A2S_RULES "
    nf_add_rule a2s_rules_limit drop

    nf_add_rule steam_group_limit limit rate 1/second burst 3 packets accept
    nf_add_rule steam_group_limit limit rate over 60/minute burst 20 packets log prefix "$LOG_PREFIX_STEAM_GROUP "
    nf_add_rule steam_group_limit drop

    nf_add_rule login_filter limit rate 1/second burst 1 packets accept
    nf_add_rule login_filter limit rate over 60/minute burst 20 packets log prefix "$LOG_PREFIX_L4D2_CONNECT "
    nf_add_rule login_filter drop

    for chain in $(nf_get_target_chains); do
        nf_add_rule "$chain" udp dport "$game_ports_expr" @th,0,4 0xFFFFFFFF @th,4,1 0x54 jump a2s_info_limit
        nf_add_rule "$chain" udp dport "$game_ports_expr" @th,0,4 0xFFFFFFFF @th,4,1 0x55 jump a2s_players_limit
        nf_add_rule "$chain" udp dport "$game_ports_expr" @th,0,4 0xFFFFFFFF @th,4,1 0x56 jump a2s_rules_limit
        nf_add_rule "$chain" udp dport "$game_ports_expr" @th,0,4 0xFFFFFFFF @th,4,1 0x00 jump steam_group_limit

        nf_add_rule "$chain" udp dport "$game_ports_expr" meta length 1-70 jump login_filter
    done
}
