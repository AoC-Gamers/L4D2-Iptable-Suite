#!/bin/bash
# This module's scoped policy is compiled by core/compiler.py.
# Metadata remains literal and discoverable without importing executable code.
nf_10_whitelist_metadata() {
    cat << 'EOF'
ID=nf_whitelist
ALIASES=whitelist
DESCRIPTION=Allows full traffic from trusted IPs in the nftables backend
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=BYPASS_SOURCE_IPS BYPASS_SOURCE_DOMAINS
DEFAULTS=TYPECHAIN=0 BYPASS_SOURCE_IPS= BYPASS_SOURCE_DOMAINS=
EOF
}
nf_10_whitelist_validate() {
    return 0
}
nf_10_whitelist_apply() {
    echo "ERROR: use the suite entrypoint; scoped VPN/whitelist compilation belongs to the core" >&2
    return 2
}
