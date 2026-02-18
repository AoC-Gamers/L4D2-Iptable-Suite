#!/bin/bash

nf_35_l4d2_tcpfilter_chain_metadata() {
    cat << 'EOF'
ID=nf_l4d2_tcpfilter_chain
ALIASES=l4d2_tcpfilter_chain
DESCRIPTION=Compatibility shim for ip-only TCPfilter chain when using nftables
REQUIRED_VARS=
OPTIONAL_VARS=L4D2_TCP_PROTECTION
DEFAULTS=L4D2_TCP_PROTECTION=
EOF
}

nf_35_l4d2_tcpfilter_chain_validate() {
    return 0
}

nf_35_l4d2_tcpfilter_chain_apply() {
    if [ -n "${L4D2_TCP_PROTECTION:-}" ]; then
        echo "INFO: nf_l4d2_tcpfilter_chain: no-op on nftables (handled by nf_l4d2_tcp_protect)"
    fi
}
