#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_60_l4d2_packet_validation_metadata() {
    cat << 'EOF'
ID=nf_l4d2_packet_validation
ALIASES=l4d2_packet_validation
DESCRIPTION=Validates invalid/malformed UDP packet sizes in the nftables backend
REQUIRED_VARS=TYPECHAIN L4D2_GAMESERVER_PORTS L4D2_TV_PORTS LOG_PREFIX_INVALID_SIZE LOG_PREFIX_MALFORMED
OPTIONAL_VARS=FIREWALL_HOST_ALIAS ENABLE_PACKET_NORMALIZATION_LOGS ENABLE_MALFORMED_FILTER
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_PORTS=27015 L4D2_TV_PORTS=27020 LOG_PREFIX_INVALID_SIZE=INVALID_SIZE: LOG_PREFIX_MALFORMED=MALFORMED: FIREWALL_HOST_ALIAS= ENABLE_PACKET_NORMALIZATION_LOGS=false ENABLE_MALFORMED_FILTER=false
EOF
}

nf_60_l4d2_packet_validation_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_l4d2_packet_validation: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    nf_validate_ports_spec "$L4D2_GAMESERVER_PORTS" "nf_l4d2_packet_validation: L4D2_GAMESERVER_PORTS" || return $?
    nf_validate_ports_spec "$L4D2_TV_PORTS" "nf_l4d2_packet_validation: L4D2_TV_PORTS" || return $?

    case "${ENABLE_PACKET_NORMALIZATION_LOGS:-}" in
        true|false) ;;
        *)
            echo "ERROR: nf_l4d2_packet_validation: ENABLE_PACKET_NORMALIZATION_LOGS must be true or false"
            return 2
            ;;
    esac

    case "${ENABLE_MALFORMED_FILTER:-}" in
        true|false) ;;
        *)
            echo "ERROR: nf_l4d2_packet_validation: ENABLE_MALFORMED_FILTER must be true or false"
            return 2
            ;;
    esac
}

nf_60_l4d2_packet_validation_apply_chain() {
    local chain="$1"
    local ports_expr="$2"
    local log_invalid_size log_malformed

    log_invalid_size="$(nf_build_log_prefix "$LOG_PREFIX_INVALID_SIZE" "INVALID_SIZE" "nf_60_l4d2_packet_validation" "$chain" "drop" "low")"
    log_malformed="$(nf_build_log_prefix "$LOG_PREFIX_MALFORMED" "MALFORMED" "nf_60_l4d2_packet_validation" "$chain" "drop" "medium")"

    if [ "${ENABLE_PACKET_NORMALIZATION_LOGS}" = "true" ]; then
        nf_add_rule "$chain" udp dport "$ports_expr" meta length 0-28 limit rate over 60/minute log prefix "\"$log_invalid_size\""
    fi
    nf_add_rule "$chain" udp dport "$ports_expr" meta length 0-28 drop

    if [ "${ENABLE_PACKET_NORMALIZATION_LOGS}" = "true" ]; then
        nf_add_rule "$chain" udp dport "$ports_expr" meta length 2521-65535 limit rate over 60/minute log prefix "\"$log_invalid_size\""
    fi
    nf_add_rule "$chain" udp dport "$ports_expr" meta length 2521-65535 drop

    if [ "${ENABLE_MALFORMED_FILTER}" = "true" ]; then
        if [ "${ENABLE_PACKET_NORMALIZATION_LOGS}" = "true" ]; then
            nf_add_rule "$chain" udp dport "$ports_expr" meta length 30-32 limit rate over 60/minute log prefix "\"$log_malformed\""
        fi
        nf_add_rule "$chain" udp dport "$ports_expr" meta length 30-32 drop

        if [ "${ENABLE_PACKET_NORMALIZATION_LOGS}" = "true" ]; then
            nf_add_rule "$chain" udp dport "$ports_expr" meta length 46 limit rate over 60/minute log prefix "\"$log_malformed\""
        fi
        nf_add_rule "$chain" udp dport "$ports_expr" meta length 46 drop

        if [ "${ENABLE_PACKET_NORMALIZATION_LOGS}" = "true" ]; then
            nf_add_rule "$chain" udp dport "$ports_expr" meta length 60 limit rate over 60/minute log prefix "\"$log_malformed\""
        fi
        nf_add_rule "$chain" udp dport "$ports_expr" meta length 60 drop
    fi
}

nf_60_l4d2_packet_validation_apply() {
    local chain game_ports_expr tv_ports_expr

    game_ports_expr="$(nf_ports_set_expr "$L4D2_GAMESERVER_PORTS")"
    tv_ports_expr="$(nf_ports_set_expr "$L4D2_TV_PORTS")"

    for chain in $(nf_get_target_chains_for_domain l4d2_udp); do
        nf_60_l4d2_packet_validation_apply_chain "$chain" "$game_ports_expr"
        nf_60_l4d2_packet_validation_apply_chain "$chain" "$tv_ports_expr"
    done
}
