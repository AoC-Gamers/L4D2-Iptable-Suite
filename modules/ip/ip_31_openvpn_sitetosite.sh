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

ip_31_openvpn_sitetosite_expand_alias_list() {
    local raw="$1"
    raw="${raw//,/ }"
    raw="${raw//$'\n'/ }"
    for item in $raw; do
        echo "$item"
    done | awk '!seen[$0]++'
}

ip_31_openvpn_sitetosite_validate_ipv4() {
    local label="$1"
    local value="$2"

    if ! [[ "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        echo "ERROR: ip_openvpn_sitetosite: $label must be a valid IPv4 address (current: '$value')"
        return 2
    fi
}

ip_31_openvpn_sitetosite_router_alias_entries() {
    local legacy_real="${OVPNS2S_ROUTER_REAL_IP:-}"
    local legacy_alias="${OVPNS2S_ROUTER_ALIAS_IP:-}"

    if [ -n "${OVPNS2S_ROUTER_ALIAS:-}" ]; then
        ip_31_openvpn_sitetosite_expand_alias_list "$OVPNS2S_ROUTER_ALIAS"
    fi

    if [ -n "$legacy_real" ] && [ -n "$legacy_alias" ]; then
        echo "$legacy_real;$legacy_alias"
    fi
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
OPTIONAL_VARS=OVPNS2S_INTERFACE OVPNS2S_LOCAL_SUBNETS OVPNS2S_REMOTE_SUBNETS OVPNS2S_ENABLE_NAT OVPNS2S_LOCAL_INTERFACE OVPNS2S_LOG_ENABLED OVPNS2S_LOG_PREFIX OVPNS2S_ROUTER_REAL_IP OVPNS2S_ROUTER_ALIAS_IP OVPNS2S_ROUTER_ALIAS OVPNS2S_ROUTER_ALIAS_SNAT
DEFAULTS=TYPECHAIN=0 OVPNS2S_ENABLE_NAT=false OVPNS2S_LOCAL_INTERFACE= OVPNS2S_LOG_ENABLED=false OVPNS2S_LOG_PREFIX=VPN_S2S_TRAFFIC: OVPNS2S_ROUTER_REAL_IP= OVPNS2S_ROUTER_ALIAS_IP= OVPNS2S_ROUTER_ALIAS= OVPNS2S_ROUTER_ALIAS_SNAT=false
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

    if { [ -n "${OVPNS2S_ROUTER_REAL_IP:-}" ] && [ -z "${OVPNS2S_ROUTER_ALIAS_IP:-}" ]; } \
        || { [ -z "${OVPNS2S_ROUTER_REAL_IP:-}" ] && [ -n "${OVPNS2S_ROUTER_ALIAS_IP:-}" ]; }; then
        echo "ERROR: ip_openvpn_sitetosite: OVPNS2S_ROUTER_REAL_IP and OVPNS2S_ROUTER_ALIAS_IP must be set together"
        return 2
    fi

    local alias_entry alias_real alias_ip
    while IFS= read -r alias_entry; do
        [ -z "$alias_entry" ] && continue
        if [[ "$alias_entry" != *";"* ]]; then
            echo "ERROR: ip_openvpn_sitetosite: invalid OVPNS2S_ROUTER_ALIAS entry '$alias_entry' (expected real_ip;alias_ip)"
            return 2
        fi

        alias_real="${alias_entry%%;*}"
        alias_ip="${alias_entry#*;}"

        if [ -z "$alias_real" ] || [ -z "$alias_ip" ]; then
            echo "ERROR: ip_openvpn_sitetosite: invalid OVPNS2S_ROUTER_ALIAS entry '$alias_entry' (empty real/alias IP)"
            return 2
        fi

        ip_31_openvpn_sitetosite_validate_ipv4 "OVPNS2S router real IP" "$alias_real" || return $?
        ip_31_openvpn_sitetosite_validate_ipv4 "OVPNS2S router alias IP" "$alias_ip" || return $?
    done < <(ip_31_openvpn_sitetosite_router_alias_entries)
}

ip_31_openvpn_sitetosite_apply() {
    local local_subnet remote_subnet alias_entry alias_real alias_ip

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

    while IFS= read -r alias_entry; do
        [ -z "$alias_entry" ] && continue
        alias_real="${alias_entry%%;*}"
        alias_ip="${alias_entry#*;}"

        while IFS= read -r remote_subnet; do
            [ -z "$remote_subnet" ] && continue
            ip_31_openvpn_sitetosite_add_rule_table nat PREROUTING -i "$OVPNS2S_INTERFACE" -s "$remote_subnet" -d "$alias_ip" -j DNAT --to-destination "$alias_real"
        done < <(ip_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")

        if [ "${OVPNS2S_ROUTER_ALIAS_SNAT:-false}" = "true" ]; then
            if [ -n "${OVPNS2S_LOCAL_INTERFACE:-}" ]; then
                while IFS= read -r remote_subnet; do
                    [ -z "$remote_subnet" ] && continue
                    ip_31_openvpn_sitetosite_add_rule_table nat POSTROUTING -s "$remote_subnet" -d "$alias_real" -o "$OVPNS2S_LOCAL_INTERFACE" -j MASQUERADE
                done < <(ip_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")
            else
                echo "WARNING: ip_openvpn_sitetosite: OVPNS2S_ROUTER_ALIAS_SNAT=true but OVPNS2S_LOCAL_INTERFACE is empty; skipping alias SNAT"
            fi
        fi
    done < <(ip_31_openvpn_sitetosite_router_alias_entries)

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
