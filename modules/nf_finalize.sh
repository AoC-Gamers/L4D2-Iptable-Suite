#!/bin/bash

nf_finalize_metadata() {
    cat << 'EOF'
ID=nf_finalize
ALIASES=finalize
DESCRIPTION=Applies final policies and prints a summary for the nftables backend
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0
EOF
}

nf_finalize_validate() {
    return 0
}

nf_finalize_apply() {
    echo "ERROR: infrastructure is owned by core/fw.py; use a suite entrypoint" >&2
    return 2
}
