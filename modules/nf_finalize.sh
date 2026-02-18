#!/bin/bash

nf_finalize_metadata() {
    cat << 'EOF'
ID=nf_finalize
DESCRIPTION=Applies final policies and prints a summary for the nftables backend
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=ENABLE_L4D2_TCP_PROTECT L4D2_TV_PORTS
DEFAULTS=TYPECHAIN=0 ENABLE_L4D2_TCP_PROTECT=true L4D2_TV_PORTS=27020
EOF
}

nf_finalize_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_finalize: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac
}

nf_finalize_apply() {
    echo "OK: nftables rules applied successfully"
    echo "   - Chain type: $TYPECHAIN (0=input, 1=forward, 2=both)"
    echo "   - SourceTV reference ports: $L4D2_TV_PORTS"
    echo "   - TCP Protection flag (shared config): $ENABLE_L4D2_TCP_PROTECT"
}
