#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_00_chain_setup_metadata() {
    cat << 'EOF'
ID=nf_chain_setup
DESCRIPTION=Sets up the nftables ruleset and base chains for L4D2
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0
EOF
}

nf_00_chain_setup_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_chain_setup: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if ! command -v nft >/dev/null 2>&1; then
        echo "ERROR: nf_chain_setup: nft command not found"
        return 3
    fi
}

nf_00_chain_setup_apply() {
    nft flush ruleset
    nft add table inet l4d2_filter

    local input_policy="accept"
    local forward_policy="accept"

    if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
        input_policy="drop"
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        forward_policy="drop"
    fi

    nft add chain inet l4d2_filter input "{ type filter hook input priority 0 ; policy ${input_policy} ; }"
    nft add chain inet l4d2_filter forward "{ type filter hook forward priority 0 ; policy ${forward_policy} ; }"
    nft add chain inet l4d2_filter output "{ type filter hook output priority 0 ; policy accept ; }"

    nft add rule inet l4d2_filter input iifname lo accept
    nft add rule inet l4d2_filter input ct state established,related accept
    nft add rule inet l4d2_filter output accept

    if nf_chain_enabled forward; then
        nft add rule inet l4d2_filter forward ct state established,related accept
    fi
}
