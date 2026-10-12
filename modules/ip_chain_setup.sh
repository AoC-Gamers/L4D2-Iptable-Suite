#!/bin/bash

ip_chain_setup_metadata() {
    cat << 'EOF'
ID=ip_chain_setup
ALIASES=chain_setup
DESCRIPTION=Sets up cleanup, base policies, and required chains for the iptables backend
REQUIRED_VARS=TYPECHAIN DOCKER_INPUT_COMPAT DOCKER_CHAIN_AUTORECOVER
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 DOCKER_INPUT_COMPAT=false DOCKER_CHAIN_AUTORECOVER=true
EOF
}

ip_chain_setup_validate() {
    return 0
}

ip_chain_setup_apply() {
    echo "ERROR: infrastructure is owned by core/fw.py; use a suite entrypoint" >&2
    return 2
}
