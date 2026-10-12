#!/bin/bash
# This module's scoped policy is compiled by core/compiler.py.
# Metadata remains literal and discoverable without importing executable code.
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
    return 0
}
ip_31_openvpn_sitetosite_apply() {
    echo "ERROR: use the suite entrypoint; scoped VPN/whitelist compilation belongs to the core" >&2
    return 2
}
