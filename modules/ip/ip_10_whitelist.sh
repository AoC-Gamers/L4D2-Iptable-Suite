#!/bin/bash
# This module's scoped policy is compiled by core/compiler.py.
# Metadata remains literal and discoverable without importing executable code.
ip_10_whitelist_metadata() {
    cat << 'EOF'
ID=ip_whitelist
ALIASES=whitelist
DESCRIPTION=Allows full traffic from IPs listed in BYPASS_SOURCE_IPS
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=BYPASS_SOURCE_IPS BYPASS_SOURCE_DOMAINS
DEFAULTS=TYPECHAIN=0 BYPASS_SOURCE_IPS= BYPASS_SOURCE_DOMAINS=
EOF
}
ip_10_whitelist_validate() {
    return 0
}
ip_10_whitelist_apply() {
    echo "ERROR: use the suite entrypoint; scoped VPN/whitelist compilation belongs to the core" >&2
    return 2
}
