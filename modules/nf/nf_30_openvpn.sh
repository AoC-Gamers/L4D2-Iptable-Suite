#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_30_openvpn_metadata() {
    cat << 'EOF'
ID=nf_openvpn
DESCRIPTION=Applies base OpenVPN rules in the nftables backend
REQUIRED_VARS=TYPECHAIN VPN_PORT VPN_SUBNET VPN_INTERFACE
OPTIONAL_VARS=VPN_PROTO VPN_PORT VPN_SUBNET VPN_INTERFACE VPN_LAN_SUBNET
DEFAULTS=TYPECHAIN=0 VPN_PROTO=udp VPN_PORT=1194 VPN_SUBNET=10.8.0.0/24 VPN_INTERFACE=tun0 VPN_LAN_SUBNET=192.168.1.0/24
EOF
}

nf_30_openvpn_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_openvpn: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if ! [[ "${VPN_PORT}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: nf_openvpn: VPN_PORT must be numeric"
        return 2
    fi

    if [ -z "${VPN_SUBNET:-}" ] || [ -z "${VPN_INTERFACE:-}" ]; then
        echo "ERROR: nf_openvpn: VPN_SUBNET and VPN_INTERFACE are required"
        return 2
    fi
}

nf_30_openvpn_apply() {
    VPN_PROTO="$(echo "$VPN_PROTO" | tr 'A-Z' 'a-z')"

    if nf_chain_enabled input; then
        nf_add_rule input "$VPN_PROTO" dport "$VPN_PORT" accept
        nf_add_rule input iifname "$VPN_INTERFACE" ip saddr "$VPN_SUBNET" accept
    fi

    if nf_chain_enabled forward; then
        nf_add_rule forward iifname "$VPN_INTERFACE" ip saddr "$VPN_SUBNET" ip daddr "$VPN_LAN_SUBNET" accept
        nf_add_rule forward oifname "$VPN_INTERFACE" ip daddr "$VPN_SUBNET" ct state established,related accept
    fi
}
