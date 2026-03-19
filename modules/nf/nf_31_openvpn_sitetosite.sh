#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_31_openvpn_sitetosite_expand_list() {
    local raw="$1"
    raw="${raw//,/ }"
    raw="${raw//;/ }"
    raw="${raw//$'\n'/ }"
    for item in $raw; do
        echo "$item"
    done | awk '!seen[$0]++'
}

nf_31_openvpn_sitetosite_expand_alias_list() {
    local raw="$1"
    raw="${raw//,/ }"
    raw="${raw//$'\n'/ }"
    for item in $raw; do
        echo "$item"
    done | awk '!seen[$0]++'
}

nf_31_openvpn_sitetosite_validate_ipv4() {
    local label="$1"
    local value="$2"

    if ! [[ "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        echo "ERROR: nf_openvpn_sitetosite: $label must be a valid IPv4 address (current: '$value')"
        return 2
    fi
}

nf_31_openvpn_sitetosite_router_alias_entries() {
    local legacy_real="${OVPNS2S_ROUTER_REAL_IP:-}"
    local legacy_alias="${OVPNS2S_ROUTER_ALIAS_IP:-}"

    if [ -n "${OVPNS2S_ROUTER_ALIAS:-}" ]; then
        nf_31_openvpn_sitetosite_expand_alias_list "$OVPNS2S_ROUTER_ALIAS"
    fi

    if [ -n "$legacy_real" ] && [ -n "$legacy_alias" ]; then
        echo "$legacy_real;$legacy_alias"
    fi
}

nf_31_openvpn_sitetosite_validate_cidr_list() {
    local label="$1"
    local raw="$2"
    local cidr
    while IFS= read -r cidr; do
        [ -z "$cidr" ] && continue
        if ! [[ "$cidr" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]]; then
            echo "ERROR: nf_openvpn_sitetosite: $label contains invalid CIDR '$cidr'"
            return 2
        fi
    done < <(nf_31_openvpn_sitetosite_expand_list "$raw")
}

nf_31_openvpn_sitetosite_docker_user_exists() {
    nft list chain ip filter DOCKER-USER >/dev/null 2>&1
}

nf_31_openvpn_sitetosite_cleanup_docker_user_rules() {
    local handles=()
    local handle

    mapfile -t handles < <(
        nft -a list chain ip filter DOCKER-USER 2>/dev/null \
            | awk '/comment "(l4d2|vpn)-s2s-dockeruser-/ {print $NF}' \
            | sort -rn
    )

    for handle in "${handles[@]}"; do
        nft delete rule ip filter DOCKER-USER handle "$handle" 2>/dev/null || true
    done
}

nf_31_openvpn_sitetosite_apply_docker_user_rules() {
    local remote_subnet local_subnet

    if [ -z "${OVPNS2S_LOCAL_INTERFACE:-}" ]; then
        return 0
    fi

    if ! nf_31_openvpn_sitetosite_docker_user_exists; then
        return 0
    fi

    nf_31_openvpn_sitetosite_cleanup_docker_user_rules

    while IFS= read -r remote_subnet; do
        [ -z "$remote_subnet" ] && continue
        while IFS= read -r local_subnet; do
            [ -z "$local_subnet" ] && continue
            nft insert rule ip filter DOCKER-USER \
                iifname "$OVPNS2S_INTERFACE" oifname "$OVPNS2S_LOCAL_INTERFACE" \
                ip saddr "$remote_subnet" ip daddr "$local_subnet" \
                accept comment "vpn-s2s-dockeruser-fwd"
            nft insert rule ip filter DOCKER-USER \
                iifname "$OVPNS2S_LOCAL_INTERFACE" oifname "$OVPNS2S_INTERFACE" \
                ip saddr "$local_subnet" ip daddr "$remote_subnet" \
                ct state established,related \
                accept comment "vpn-s2s-dockeruser-ret"
        done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_LOCAL_SUBNETS")
    done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")
}

nf_31_openvpn_sitetosite_metadata() {
    cat << 'EOF'
ID=nf_openvpn_sitetosite
ALIASES=openvpn_sitetosite
DESCRIPTION=Applies OpenVPN site-to-site rules in the nftables backend
REQUIRED_VARS=TYPECHAIN OVPNS2S_INTERFACE OVPNS2S_LOCAL_SUBNETS OVPNS2S_REMOTE_SUBNETS
OPTIONAL_VARS=OVPNS2S_INTERFACE OVPNS2S_LOCAL_SUBNETS OVPNS2S_REMOTE_SUBNETS OVPNS2S_ENABLE_NAT OVPNS2S_LOCAL_INTERFACE OVPNS2S_ROUTER_REAL_IP OVPNS2S_ROUTER_ALIAS_IP OVPNS2S_ROUTER_ALIAS OVPNS2S_ROUTER_ALIAS_SNAT
DEFAULTS=TYPECHAIN=0 OVPNS2S_ENABLE_NAT=false OVPNS2S_LOCAL_INTERFACE= OVPNS2S_ROUTER_REAL_IP= OVPNS2S_ROUTER_ALIAS_IP= OVPNS2S_ROUTER_ALIAS= OVPNS2S_ROUTER_ALIAS_SNAT=false
EOF
}

nf_31_openvpn_sitetosite_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_openvpn_sitetosite: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if [ -z "${OVPNS2S_INTERFACE:-}" ] || [ -z "${OVPNS2S_LOCAL_SUBNETS:-}" ] || [ -z "${OVPNS2S_REMOTE_SUBNETS:-}" ]; then
        echo "ERROR: nf_openvpn_sitetosite: OVPNS2S_INTERFACE, OVPNS2S_LOCAL_SUBNETS and OVPNS2S_REMOTE_SUBNETS are required"
        return 2
    fi

    nf_31_openvpn_sitetosite_validate_cidr_list "OVPNS2S_LOCAL_SUBNETS" "$OVPNS2S_LOCAL_SUBNETS" || return $?
    nf_31_openvpn_sitetosite_validate_cidr_list "OVPNS2S_REMOTE_SUBNETS" "$OVPNS2S_REMOTE_SUBNETS" || return $?

    if { [ -n "${OVPNS2S_ROUTER_REAL_IP:-}" ] && [ -z "${OVPNS2S_ROUTER_ALIAS_IP:-}" ]; } \
        || { [ -z "${OVPNS2S_ROUTER_REAL_IP:-}" ] && [ -n "${OVPNS2S_ROUTER_ALIAS_IP:-}" ]; }; then
        echo "ERROR: nf_openvpn_sitetosite: OVPNS2S_ROUTER_REAL_IP and OVPNS2S_ROUTER_ALIAS_IP must be set together"
        return 2
    fi

    local alias_entry alias_real alias_ip
    while IFS= read -r alias_entry; do
        [ -z "$alias_entry" ] && continue
        if [[ "$alias_entry" != *";"* ]]; then
            echo "ERROR: nf_openvpn_sitetosite: invalid OVPNS2S_ROUTER_ALIAS entry '$alias_entry' (expected real_ip;alias_ip)"
            return 2
        fi

        alias_real="${alias_entry%%;*}"
        alias_ip="${alias_entry#*;}"

        if [ -z "$alias_real" ] || [ -z "$alias_ip" ]; then
            echo "ERROR: nf_openvpn_sitetosite: invalid OVPNS2S_ROUTER_ALIAS entry '$alias_entry' (empty real/alias IP)"
            return 2
        fi

        nf_31_openvpn_sitetosite_validate_ipv4 "OVPNS2S router real IP" "$alias_real" || return $?
        nf_31_openvpn_sitetosite_validate_ipv4 "OVPNS2S router alias IP" "$alias_ip" || return $?
    done < <(nf_31_openvpn_sitetosite_router_alias_entries)
}

nf_31_openvpn_sitetosite_apply() {
    local local_subnet remote_subnet alias_entry alias_real alias_ip
    local nat_table="vpn_s2s_nat"
    local need_nat_table=false

    if [ "${OVPNS2S_ENABLE_NAT:-false}" = "true" ] || [ -n "$(nf_31_openvpn_sitetosite_router_alias_entries)" ]; then
        need_nat_table=true
    fi

    if nf_chain_enabled input; then
        while IFS= read -r remote_subnet; do
            [ -z "$remote_subnet" ] && continue
            nf_add_rule "$(nf_domain_chain_name input vpn)" iifname "$OVPNS2S_INTERFACE" ip saddr "$remote_subnet" accept
        done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")
    fi

    if nf_chain_enabled forward; then
        while IFS= read -r remote_subnet; do
            [ -z "$remote_subnet" ] && continue
            while IFS= read -r local_subnet; do
                [ -z "$local_subnet" ] && continue
                nf_add_rule "$(nf_domain_chain_name forward vpn)" iifname "$OVPNS2S_INTERFACE" ip saddr "$remote_subnet" ip daddr "$local_subnet" accept
                nf_add_rule "$(nf_domain_chain_name forward vpn)" oifname "$OVPNS2S_INTERFACE" ip saddr "$local_subnet" ip daddr "$remote_subnet" ct state established,related accept
            done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_LOCAL_SUBNETS")
            done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")
    fi

    nf_31_openvpn_sitetosite_apply_docker_user_rules

    if [ "$need_nat_table" = "true" ]; then
        nft delete table ip "$nat_table" 2>/dev/null || true
        nft add table ip "$nat_table"
        nft add chain ip "$nat_table" prerouting '{ type nat hook prerouting priority dstnat; policy accept; }'
        nft add chain ip "$nat_table" postrouting '{ type nat hook postrouting priority srcnat; policy accept; }'
    fi

    while IFS= read -r alias_entry; do
        [ -z "$alias_entry" ] && continue
        alias_real="${alias_entry%%;*}"
        alias_ip="${alias_entry#*;}"

        while IFS= read -r remote_subnet; do
            [ -z "$remote_subnet" ] && continue
            nft add rule ip "$nat_table" prerouting iifname "$OVPNS2S_INTERFACE" ip saddr "$remote_subnet" ip daddr "$alias_ip" dnat to "$alias_real"
        done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")

        if [ "${OVPNS2S_ROUTER_ALIAS_SNAT:-false}" = "true" ]; then
            if [ -n "${OVPNS2S_LOCAL_INTERFACE:-}" ]; then
                while IFS= read -r remote_subnet; do
                    [ -z "$remote_subnet" ] && continue
                    nft add rule ip "$nat_table" postrouting ip saddr "$remote_subnet" ip daddr "$alias_real" oifname "$OVPNS2S_LOCAL_INTERFACE" masquerade
                done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")
            else
                echo "WARNING: nf_openvpn_sitetosite: OVPNS2S_ROUTER_ALIAS_SNAT=true but OVPNS2S_LOCAL_INTERFACE is empty; skipping alias SNAT"
            fi
        fi
    done < <(nf_31_openvpn_sitetosite_router_alias_entries)

    if [ "${OVPNS2S_ENABLE_NAT:-false}" = "true" ] && [ "$need_nat_table" = "true" ]; then
        if [ -n "${OVPNS2S_LOCAL_INTERFACE:-}" ]; then
            while IFS= read -r remote_subnet; do
                [ -z "$remote_subnet" ] && continue
                nft add rule ip "$nat_table" postrouting ip saddr "$remote_subnet" oifname "$OVPNS2S_LOCAL_INTERFACE" masquerade
            done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")
        else
            echo "WARNING: nf_openvpn_sitetosite: OVPNS2S_ENABLE_NAT=true but OVPNS2S_LOCAL_INTERFACE is empty; skipping NAT"
        fi
    fi
}
