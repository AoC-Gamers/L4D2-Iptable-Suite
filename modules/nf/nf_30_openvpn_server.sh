#!/bin/bash
# This module's scoped policy is compiled by core/compiler.py.
# Metadata remains literal and discoverable without importing executable code.
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
    return 0
}
nf_30_openvpn_server_apply() {
    echo "ERROR: use the suite entrypoint; scoped VPN/whitelist compilation belongs to the core" >&2
    return 2
}
