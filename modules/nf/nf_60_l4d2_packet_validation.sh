#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_60_l4d2_packet_validation_metadata() {
    cat << 'EOF'
ID=nf_l4d2_packet_validation
DESCRIPTION=Validates invalid/malformed UDP packet sizes in the nftables backend
REQUIRED_VARS=TYPECHAIN ENABLE_L4D2_PACKET_VALIDATION L4D2_GAMESERVER_PORTS L4D2_TV_PORTS LOG_PREFIX_INVALID_SIZE LOG_PREFIX_MALFORMED
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 ENABLE_L4D2_PACKET_VALIDATION=true L4D2_GAMESERVER_PORTS=27015 L4D2_TV_PORTS=27020 LOG_PREFIX_INVALID_SIZE=INVALID_SIZE: LOG_PREFIX_MALFORMED=MALFORMED:
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

    case "${ENABLE_L4D2_PACKET_VALIDATION:-true}" in
        true|false) ;;
        *)
            echo "ERROR: nf_l4d2_packet_validation: ENABLE_L4D2_PACKET_VALIDATION must be true or false"
            return 2
            ;;
    esac

    nf_validate_ports_spec "$L4D2_GAMESERVER_PORTS" "nf_l4d2_packet_validation: L4D2_GAMESERVER_PORTS" || return $?
    nf_validate_ports_spec "$L4D2_TV_PORTS" "nf_l4d2_packet_validation: L4D2_TV_PORTS" || return $?
}

nf_60_l4d2_packet_validation_apply_chain() {
    local chain="$1"
    local ports_expr="$2"

    nf_add_rule "$chain" udp dport "$ports_expr" meta length 0-28 limit rate over 60/minute log prefix "\"$LOG_PREFIX_INVALID_SIZE \""
    nf_add_rule "$chain" udp dport "$ports_expr" meta length 0-28 drop

    nf_add_rule "$chain" udp dport "$ports_expr" meta length 2521-65535 limit rate over 60/minute log prefix "\"$LOG_PREFIX_INVALID_SIZE \""
    nf_add_rule "$chain" udp dport "$ports_expr" meta length 2521-65535 drop

    nf_add_rule "$chain" udp dport "$ports_expr" meta length 30-32 limit rate over 60/minute log prefix "\"$LOG_PREFIX_MALFORMED \""
    nf_add_rule "$chain" udp dport "$ports_expr" meta length 30-32 drop

    nf_add_rule "$chain" udp dport "$ports_expr" meta length 46 limit rate over 60/minute log prefix "\"$LOG_PREFIX_MALFORMED \""
    nf_add_rule "$chain" udp dport "$ports_expr" meta length 46 drop

    nf_add_rule "$chain" udp dport "$ports_expr" meta length 60 limit rate over 60/minute log prefix "\"$LOG_PREFIX_MALFORMED \""
    nf_add_rule "$chain" udp dport "$ports_expr" meta length 60 drop
}

nf_60_l4d2_packet_validation_apply() {
    local chain game_ports_expr tv_ports_expr

    if [ "${ENABLE_L4D2_PACKET_VALIDATION:-true}" != "true" ]; then
        echo "INFO: nf_l4d2_packet_validation: disabled (ENABLE_L4D2_PACKET_VALIDATION=false), skipping"
        return 0
    fi

    game_ports_expr="$(nf_ports_set_expr "$L4D2_GAMESERVER_PORTS")"
    tv_ports_expr="$(nf_ports_set_expr "$L4D2_TV_PORTS")"

    for chain in $(nf_get_target_chains); do
        nf_60_l4d2_packet_validation_apply_chain "$chain" "$game_ports_expr"
        nf_60_l4d2_packet_validation_apply_chain "$chain" "$tv_ports_expr"
    done
}
