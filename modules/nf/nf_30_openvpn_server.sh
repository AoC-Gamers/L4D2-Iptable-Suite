#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_30_openvpn_server_metadata() {
    cat << 'EOF'
ID=nf_openvpn_server
ALIASES=openvpn_server
DESCRIPTION=Applies base OpenVPN server rules in the nftables backend
REQUIRED_VARS=TYPECHAIN OVPNSRV_PORT OVPNSRV_SUBNET OVPNSRV_INTERFACE
OPTIONAL_VARS=OVPNSRV_PROTO OVPNSRV_PORT OVPNSRV_SUBNET OVPNSRV_INTERFACE OVPNSRV_LAN_SUBNET
DEFAULTS=TYPECHAIN=0 OVPNSRV_PROTO=udp OVPNSRV_PORT=1194 OVPNSRV_SUBNET=10.8.0.0/24 OVPNSRV_INTERFACE=tun0 OVPNSRV_LAN_SUBNET=192.168.1.0/24
EOF
}

nf_30_openvpn_server_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_openvpn_server: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if ! [[ "${OVPNSRV_PORT}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: nf_openvpn_server: OVPNSRV_PORT must be numeric"
        return 2
    fi

    if [ -z "${OVPNSRV_SUBNET:-}" ] || [ -z "${OVPNSRV_INTERFACE:-}" ]; then
        echo "ERROR: nf_openvpn_server: OVPNSRV_SUBNET and OVPNSRV_INTERFACE are required"
        return 2
    fi
}

nf_30_openvpn_server_apply() {
    OVPNSRV_PROTO="$(echo "$OVPNSRV_PROTO" | tr 'A-Z' 'a-z')"

    if nf_chain_enabled input; then
        nf_add_rule input "$OVPNSRV_PROTO" dport "$OVPNSRV_PORT" accept
        nf_add_rule input iifname "$OVPNSRV_INTERFACE" ip saddr "$OVPNSRV_SUBNET" accept
    fi

    if nf_chain_enabled forward; then
        nf_add_rule forward iifname "$OVPNSRV_INTERFACE" ip saddr "$OVPNSRV_SUBNET" ip daddr "$OVPNSRV_LAN_SUBNET" accept
        nf_add_rule forward oifname "$OVPNSRV_INTERFACE" ip daddr "$OVPNSRV_SUBNET" ct state established,related accept
    fi
}
