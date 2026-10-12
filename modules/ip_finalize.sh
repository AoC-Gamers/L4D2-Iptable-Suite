#!/bin/bash

ip_finalize_metadata() {
    cat << 'EOF'
ID=ip_finalize
ALIASES=finalize
DESCRIPTION=Applies final policies and prints a summary for the iptables backend
REQUIRED_VARS=TYPECHAIN DOCKER_INPUT_COMPAT DOCKER_CHAIN_AUTORECOVER
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 DOCKER_INPUT_COMPAT=false DOCKER_CHAIN_AUTORECOVER=true
EOF
}

ip_finalize_validate() {
    return 0
}

ip_finalize_apply() {
    echo "ERROR: infrastructure is owned by core/fw.py; use a suite entrypoint" >&2
    return 2
}
