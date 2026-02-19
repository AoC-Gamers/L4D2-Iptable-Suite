#!/bin/bash

ip_31_openvpn_sitetosite_add_rule_first() {
    local chain="$1"
    shift
    iptables -C "$chain" "$@" 2>/dev/null || iptables -I "$chain" 1 "$@"
}

ip_31_openvpn_sitetosite_add_rule_table() {
    local table="$1"
    shift
    local chain="$1"
    shift
    iptables -t "$table" -C "$chain" "$@" 2>/dev/null || iptables -t "$table" -A "$chain" "$@"
}

ip_31_openvpn_sitetosite_expand_list() {
    local raw="$1"
    raw="${raw//,/ }"
    raw="${raw//;/ }"
    raw="${raw//$'\n'/ }"
    for item in $raw; do
        echo "$item"
    done | awk '!seen[$0]++'
}

ip_31_openvpn_sitetosite_validate_cidr_list() {
    local label="$1"
    local raw="$2"
    local cidr
    while IFS= read -r cidr; do
        [ -z "$cidr" ] && continue
        if ! [[ "$cidr" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]]; then
            echo "ERROR: ip_openvpn_sitetosite: $label contains invalid CIDR '$cidr'"
            return 2
        fi
    done < <(ip_31_openvpn_sitetosite_expand_list "$raw")
}

ip_31_openvpn_sitetosite_metadata() {
    cat << 'EOF'
ID=ip_openvpn_sitetosite
ALIASES=openvpn_sitetosite
DESCRIPTION=Applies OpenVPN site-to-site rules in the iptables backend
REQUIRED_VARS=TYPECHAIN OVPNS2S_INTERFACE OVPNS2S_LOCAL_SUBNETS OVPNS2S_REMOTE_SUBNETS
OPTIONAL_VARS=OVPNS2S_INTERFACE OVPNS2S_LOCAL_SUBNETS OVPNS2S_REMOTE_SUBNETS OVPNS2S_ENABLE_NAT OVPNS2S_LOCAL_INTERFACE OVPNS2S_LOG_ENABLED OVPNS2S_LOG_PREFIX
DEFAULTS=TYPECHAIN=0 OVPNS2S_ENABLE_NAT=false OVPNS2S_LOCAL_INTERFACE= OVPNS2S_LOG_ENABLED=false OVPNS2S_LOG_PREFIX=VPN_S2S_TRAFFIC:
EOF
}

ip_31_openvpn_sitetosite_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_openvpn_sitetosite: TYPECHAIN must be 0, 1 or 2 (current: ${TYPECHAIN:-unset})"
            return 2
            ;;
    esac

    if [ -z "${OVPNS2S_INTERFACE:-}" ] || [ -z "${OVPNS2S_LOCAL_SUBNETS:-}" ] || [ -z "${OVPNS2S_REMOTE_SUBNETS:-}" ]; then
        echo "ERROR: ip_openvpn_sitetosite: OVPNS2S_INTERFACE, OVPNS2S_LOCAL_SUBNETS and OVPNS2S_REMOTE_SUBNETS are required"
        return 2
    fi

    ip_31_openvpn_sitetosite_validate_cidr_list "OVPNS2S_LOCAL_SUBNETS" "$OVPNS2S_LOCAL_SUBNETS" || return $?
    ip_31_openvpn_sitetosite_validate_cidr_list "OVPNS2S_REMOTE_SUBNETS" "$OVPNS2S_REMOTE_SUBNETS" || return $?
}

ip_31_openvpn_sitetosite_apply() {
    local local_subnet remote_subnet

    while IFS= read -r remote_subnet; do
        [ -z "$remote_subnet" ] && continue
        ip_31_openvpn_sitetosite_add_rule_first INPUT -i "$OVPNS2S_INTERFACE" -s "$remote_subnet" -j ACCEPT
    done < <(ip_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")

    while IFS= read -r remote_subnet; do
        [ -z "$remote_subnet" ] && continue
        while IFS= read -r local_subnet; do
            [ -z "$local_subnet" ] && continue
            ip_31_openvpn_sitetosite_add_rule_first FORWARD -i "$OVPNS2S_INTERFACE" -s "$remote_subnet" -d "$local_subnet" -j ACCEPT
            ip_31_openvpn_sitetosite_add_rule_first FORWARD -o "$OVPNS2S_INTERFACE" -s "$local_subnet" -d "$remote_subnet" -m state --state ESTABLISHED,RELATED -j ACCEPT
            if [ "$OVPNS2S_LOG_ENABLED" = "true" ]; then
                ip_31_openvpn_sitetosite_add_rule_first FORWARD -i "$OVPNS2S_INTERFACE" -s "$remote_subnet" -d "$local_subnet" -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$OVPNS2S_LOG_PREFIX" --log-level 4
            fi
        done < <(ip_31_openvpn_sitetosite_expand_list "$OVPNS2S_LOCAL_SUBNETS")
    done < <(ip_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")

    if [ "$OVPNS2S_ENABLE_NAT" = "true" ]; then
        if [ -n "$OVPNS2S_LOCAL_INTERFACE" ]; then
            while IFS= read -r remote_subnet; do
                [ -z "$remote_subnet" ] && continue
                ip_31_openvpn_sitetosite_add_rule_table nat POSTROUTING -s "$remote_subnet" -o "$OVPNS2S_LOCAL_INTERFACE" -j MASQUERADE
            done < <(ip_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")
        else
            echo "WARNING: ip_openvpn_sitetosite: OVPNS2S_ENABLE_NAT=true but OVPNS2S_LOCAL_INTERFACE is empty; skipping NAT"
        fi
    fi
}
