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

nf_31_openvpn_sitetosite_metadata() {
    cat << 'EOF'
ID=nf_openvpn_sitetosite
ALIASES=openvpn_sitetosite
DESCRIPTION=Applies OpenVPN site-to-site rules in the nftables backend
REQUIRED_VARS=TYPECHAIN OVPNS2S_INTERFACE OVPNS2S_LOCAL_SUBNETS OVPNS2S_REMOTE_SUBNETS
OPTIONAL_VARS=OVPNS2S_INTERFACE OVPNS2S_LOCAL_SUBNETS OVPNS2S_REMOTE_SUBNETS
DEFAULTS=TYPECHAIN=0
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
}

nf_31_openvpn_sitetosite_apply() {
    local local_subnet remote_subnet

    if nf_chain_enabled input; then
        while IFS= read -r remote_subnet; do
            [ -z "$remote_subnet" ] && continue
            nf_add_rule input iifname "$OVPNS2S_INTERFACE" ip saddr "$remote_subnet" accept
        done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")
    fi

    if nf_chain_enabled forward; then
        while IFS= read -r remote_subnet; do
            [ -z "$remote_subnet" ] && continue
            while IFS= read -r local_subnet; do
                [ -z "$local_subnet" ] && continue
                nf_add_rule forward iifname "$OVPNS2S_INTERFACE" ip saddr "$remote_subnet" ip daddr "$local_subnet" accept
                nf_add_rule forward oifname "$OVPNS2S_INTERFACE" ip saddr "$local_subnet" ip daddr "$remote_subnet" ct state established,related accept
            done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_LOCAL_SUBNETS")
        done < <(nf_31_openvpn_sitetosite_expand_list "$OVPNS2S_REMOTE_SUBNETS")
    fi
}
