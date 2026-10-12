#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_chain_setup_metadata() {
    cat << 'EOF'
ID=nf_chain_setup
ALIASES=chain_setup
DESCRIPTION=Sets up the modular nftables ruleset, base hooks, and domain chains
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=NF_TABLE_FAMILY NF_TABLE_NAME
DEFAULTS=TYPECHAIN=0 NF_TABLE_FAMILY=inet NF_TABLE_NAME=firewall_main
EOF
}

nf_chain_setup_validate() {
    return 0
}

nf_chain_setup_apply() {
    echo "ERROR: infrastructure is owned by core/fw.py; use a suite entrypoint" >&2
    return 2
}
