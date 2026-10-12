#!/bin/bash
# This module's scoped policy is compiled by core/compiler.py.
# Metadata remains literal and discoverable without importing executable code.
ip_30_openvpn_server_metadata() {
    cat << 'EOF'
ID=ip_openvpn_server
ALIASES=openvpn_server
DESCRIPTION=Applies OpenVPN server rules in the iptables backend (host/DOCKER-USER)
REQUIRED_VARS=TYPECHAIN OVPNSRV_PORT OVPNSRV_SUBNET OVPNSRV_INTERFACE
OPTIONAL_VARS=OVPNSRV_PROTO OVPNSRV_PORT OVPNSRV_SUBNET OVPNSRV_INTERFACE OVPNSRV_DOCKER_INTERFACE OVPNSRV_LAN_SUBNET OVPNSRV_LAN_INTERFACE OVPNSRV_ENABLE_NAT OVPNSRV_LOG_ENABLED OVPNSRV_LOG_PREFIX OVPNSRV_ROUTER_REAL_IP OVPNSRV_ROUTER_ALIAS_IP
DEFAULTS=TYPECHAIN=0 OVPNSRV_PROTO=udp OVPNSRV_PORT=1194 OVPNSRV_SUBNET=10.8.0.0/24 OVPNSRV_INTERFACE=tun0 OVPNSRV_DOCKER_INTERFACE= OVPNSRV_LAN_SUBNET=192.168.1.0/24 OVPNSRV_LAN_INTERFACE= OVPNSRV_ENABLE_NAT=false OVPNSRV_LOG_ENABLED=false OVPNSRV_LOG_PREFIX=VPN_SERVER_TRAFFIC: OVPNSRV_ROUTER_REAL_IP= OVPNSRV_ROUTER_ALIAS_IP=
EOF
}
ip_30_openvpn_server_validate() {
    return 0
}
ip_30_openvpn_server_apply() {
    echo "ERROR: use the suite entrypoint; scoped VPN/whitelist compilation belongs to the core" >&2
    return 2
}
