#!/bin/bash

nf_35_l4d2_tcpfilter_chain_metadata() {
    cat << 'EOF'
ID=nf_l4d2_tcpfilter_chain
ALIASES=l4d2_tcpfilter_chain
DESCRIPTION=Compatibility shim for ip-only TCPfilter chain when using nftables
REQUIRED_VARS=
OPTIONAL_VARS=
DEFAULTS=
EOF
}

nf_35_l4d2_tcpfilter_chain_validate() {
    return 0
}

nf_35_l4d2_tcpfilter_chain_apply() {
    :
}
