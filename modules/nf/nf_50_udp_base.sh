#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_50_udp_base_metadata() {
    cat << 'EOF'
ID=nf_udp_base
DESCRIPTION=Applies base UDP/state/ICMP rules in the nftables backend
REQUIRED_VARS=TYPECHAIN GAMESERVERPORTS TVSERVERPORTS CMD_LIMIT LOG_PREFIX_UDP_NEW_LIMIT LOG_PREFIX_UDP_EST_LIMIT LOG_PREFIX_ICMP_FLOOD
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 GAMESERVERPORTS=27015 TVSERVERPORTS=27020 CMD_LIMIT=100 LOG_PREFIX_UDP_NEW_LIMIT=UDP_NEW_LIMIT: LOG_PREFIX_UDP_EST_LIMIT=UDP_EST_LIMIT: LOG_PREFIX_ICMP_FLOOD=ICMP_FLOOD:
EOF
}

nf_50_udp_base_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_udp_base: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if ! [[ "${CMD_LIMIT}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: nf_udp_base: CMD_LIMIT must be numeric"
        return 2
    fi

    if [ "$CMD_LIMIT" -lt 10 ] || [ "$CMD_LIMIT" -gt 10000 ]; then
        echo "ERROR: nf_udp_base: CMD_LIMIT must be between 10 and 10000"
        return 2
    fi

    nf_validate_ports_spec "$GAMESERVERPORTS" "nf_udp_base: GAMESERVERPORTS" || return $?
    nf_validate_ports_spec "$TVSERVERPORTS" "nf_udp_base: TVSERVERPORTS" || return $?
}

nf_50_udp_base_apply() {
    local cmd_limit_leeway=$((CMD_LIMIT + 10))
    local cmd_limit_upper=$((CMD_LIMIT + 30))
    local game_ports_expr tv_ports_expr all_udp_ports_expr chain

    game_ports_expr="$(nf_ports_set_expr "$GAMESERVERPORTS")"
    tv_ports_expr="$(nf_ports_set_expr "$TVSERVERPORTS")"

    nft add chain inet l4d2_filter udp_new_limit
    nft add chain inet l4d2_filter udp_new_limit_global
    nft add chain inet l4d2_filter udp_established_limit

    nf_add_rule udp_new_limit meter udp_new_src_under '{ ip saddr . udp dport limit rate 1/second burst 3 packets }' jump udp_new_limit_global
    nf_add_rule udp_new_limit meter udp_new_src_over '{ ip saddr . udp dport limit rate over 1/second burst 3 packets }' log prefix "$LOG_PREFIX_UDP_NEW_LIMIT "
    nf_add_rule udp_new_limit meter udp_new_src_over_drop '{ ip saddr . udp dport limit rate over 1/second burst 3 packets }' drop

    nf_add_rule udp_new_limit_global meter udp_new_global_under '{ udp dport limit rate 10/second burst 20 packets }' accept
    nf_add_rule udp_new_limit_global meter udp_new_global_over '{ udp dport limit rate over 10/second burst 20 packets }' log prefix "$LOG_PREFIX_UDP_NEW_LIMIT "
    nf_add_rule udp_new_limit_global meter udp_new_global_over_drop '{ udp dport limit rate over 10/second burst 20 packets }' drop

    nf_add_rule udp_established_limit meter udp_est_under '{ ip saddr . udp sport . udp dport limit rate '"${cmd_limit_leeway}"'/second burst '"${cmd_limit_upper}"' packets }' accept
    nf_add_rule udp_established_limit meter udp_est_over '{ ip saddr . udp sport . udp dport limit rate over '"${cmd_limit_leeway}"'/second burst '"${cmd_limit_upper}"' packets }' log prefix "$LOG_PREFIX_UDP_EST_LIMIT "
    nf_add_rule udp_established_limit meter udp_est_over_drop '{ ip saddr . udp sport . udp dport limit rate over '"${cmd_limit_leeway}"'/second burst '"${cmd_limit_upper}"' packets }' drop

    all_udp_ports_expr="{ $(nf_ports_normalize "$GAMESERVERPORTS"), $(nf_ports_normalize "$TVSERVERPORTS") }"

    for chain in $(nf_get_target_chains); do
        nf_add_rule "$chain" udp dport "$all_udp_ports_expr" ct state new jump udp_new_limit
        nf_add_rule "$chain" udp dport "$all_udp_ports_expr" ct state established jump udp_established_limit

        nf_add_rule "$chain" udp sport 53 ct state established,related accept
        nf_add_rule "$chain" ip protocol icmp limit rate 20/second burst 2 packets accept
        nf_add_rule "$chain" ip protocol icmp limit rate over 30/minute burst 10 packets log prefix "$LOG_PREFIX_ICMP_FLOOD "
        nf_add_rule "$chain" ip protocol icmp drop
    done
}
