#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_42_l4d2_tcp_protect_metadata() {
    cat << 'EOF'
ID=nf_l4d2_tcp_protect
ALIASES=l4d2_tcp_protect
DESCRIPTION=Applies L4D2 TCP protection (RCON/game ports) in the nftables backend
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=L4D2_GAMESERVER_PORTS LOG_PREFIX_TCP_RCON_BLOCK FIREWALL_HOST_ALIAS
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_PORTS=27015 LOG_PREFIX_TCP_RCON_BLOCK=TCP_RCON_BLOCK: FIREWALL_HOST_ALIAS=
EOF
}

nf_42_l4d2_tcp_protect_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_l4d2_tcp_protect: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    nf_validate_ports_spec "$L4D2_GAMESERVER_PORTS" "nf_l4d2_tcp_protect: L4D2_GAMESERVER_PORTS" || return $?
}

nf_42_l4d2_tcp_protect_apply() {
    local chain protected_ports_expr log_tcp_rcon
    local meter_under meter_over_log meter_over_drop
    local tcp_rate="600/minute"
    local tcp_burst="200"

    protected_ports_expr="$(nf_ports_set_expr "$L4D2_GAMESERVER_PORTS")"

    for chain in $(nf_get_target_chains_for_domain l4d2_tcp); do
        log_tcp_rcon="$(nf_build_log_prefix "$LOG_PREFIX_TCP_RCON_BLOCK" "TCP_RCON_BLOCK" "nf_42_l4d2_tcp_protect" "$chain" "drop" "high")"
        meter_under="${chain}_tcp_under"
        meter_over_log="${chain}_tcp_over_log"
        meter_over_drop="${chain}_tcp_over_drop"

        nft add rule "$NF_TABLE_FAMILY" "$NF_TABLE_NAME" "$chain" tcp dport "$protected_ports_expr" ct state new meter "$meter_under" "{ ip saddr . tcp dport limit rate ${tcp_rate} burst ${tcp_burst} packets }" accept
        nft add rule "$NF_TABLE_FAMILY" "$NF_TABLE_NAME" "$chain" tcp dport "$protected_ports_expr" ct state new meter "$meter_over_log" "{ ip saddr . tcp dport limit rate over ${tcp_rate} burst ${tcp_burst} packets }" log prefix "\"$log_tcp_rcon\""
        nft add rule "$NF_TABLE_FAMILY" "$NF_TABLE_NAME" "$chain" tcp dport "$protected_ports_expr" ct state new meter "$meter_over_drop" "{ ip saddr . tcp dport limit rate over ${tcp_rate} burst ${tcp_burst} packets }" drop
    done
}
