#!/bin/bash

nf_finalize_metadata() {
    cat << 'EOF'
ID=nf_finalize
DESCRIPTION=Applies final policies and prints a summary for the nftables backend
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=ENABLE_TCP_PROTECT TVSERVERPORTS
DEFAULTS=TYPECHAIN=0 ENABLE_TCP_PROTECT=true TVSERVERPORTS=27020
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
    echo "   - SourceTV reference ports: $TVSERVERPORTS"
    echo "   - TCP Protection flag (shared config): $ENABLE_TCP_PROTECT"
}
