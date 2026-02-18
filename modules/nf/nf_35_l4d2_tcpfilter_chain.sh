#!/bin/bash

nf_35_l4d2_tcpfilter_chain_metadata() {
    cat << 'EOF'
ID=nf_l4d2_tcpfilter_chain
ALIASES=l4d2_tcpfilter_chain
DESCRIPTION=Compatibility shim for ip-only TCPfilter chain when using nftables
REQUIRED_VARS=
OPTIONAL_VARS=ENABLE_L4D2_TCP_PROTECT L4D2_TCP_PROTECTION
DEFAULTS=ENABLE_L4D2_TCP_PROTECT=false L4D2_TCP_PROTECTION=
EOF
}

nf_35_l4d2_tcpfilter_chain_validate() {
    case "${ENABLE_L4D2_TCP_PROTECT:-}" in
        true|false) ;;
        *)
            echo "ERROR: nf_l4d2_tcpfilter_chain: ENABLE_L4D2_TCP_PROTECT must be true or false"
            return 2
            ;;
    esac
}

nf_35_l4d2_tcpfilter_chain_apply() {
    if [ "${ENABLE_L4D2_TCP_PROTECT:-false}" = "true" ] || [ -n "${L4D2_TCP_PROTECTION:-}" ]; then
        echo "INFO: nf_l4d2_tcpfilter_chain: no-op on nftables (handled by nf_l4d2_tcp_protect)"
    fi
}
