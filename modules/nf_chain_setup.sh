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

nf_chain_setup_apply() {
    local domain
    local input_domains="core_allow vpn admin l4d2_tcp web l4d2_udp"
    local forward_domains="core_allow docker_egress vpn admin l4d2_tcp web l4d2_udp"

    nft delete table "$NF_TABLE_FAMILY" "$NF_TABLE_NAME" 2>/dev/null || true
    nft delete table inet l4d2_filter 2>/dev/null || true
    nft delete table ip vpn_s2s_nat 2>/dev/null || true
    nft delete table ip l4d2_s2s_nat 2>/dev/null || true

    nft add table "$NF_TABLE_FAMILY" "$NF_TABLE_NAME"

    local input_policy="accept"
    local forward_policy="accept"

    if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
        input_policy="drop"
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        forward_policy="drop"
    fi

    nft add chain "$NF_TABLE_FAMILY" "$NF_TABLE_NAME" input "{ type filter hook input priority 0 ; policy ${input_policy} ; }"
    nft add chain "$NF_TABLE_FAMILY" "$NF_TABLE_NAME" forward "{ type filter hook forward priority 0 ; policy ${forward_policy} ; }"
    nft add chain "$NF_TABLE_FAMILY" "$NF_TABLE_NAME" output "{ type filter hook output priority 0 ; policy accept ; }"

    for domain in $input_domains; do
        nf_add_chain "$(nf_domain_chain_name input "$domain")"
    done

    for domain in $forward_domains; do
        nf_add_chain "$(nf_domain_chain_name forward "$domain")"
    done

    nf_add_rule input iifname lo accept
    nf_add_rule input ct state established,related accept
    if nf_chain_enabled forward; then
        nf_add_rule forward ct state established,related accept
    fi
    nf_add_rule output accept

    for domain in $input_domains; do
        nf_add_rule input jump "$(nf_domain_chain_name input "$domain")"
    done

    for domain in $forward_domains; do
        nf_add_rule forward jump "$(nf_domain_chain_name forward "$domain")"
    done
}
