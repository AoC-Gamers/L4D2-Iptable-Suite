#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_40_tcp_ssh_metadata() {
    cat << 'EOF'
ID=nf_tcp_ssh
ALIASES=tcp_ssh
DESCRIPTION=Applies base SSH rules in the nftables backend
REQUIRED_VARS=TYPECHAIN SSH_PORT
OPTIONAL_VARS=SSH_DOCKER SSH_RATE SSH_BURST LOG_PREFIX_SSH_ABUSE
DEFAULTS=TYPECHAIN=0 SSH_PORT=22 SSH_DOCKER= SSH_RATE=60/minute SSH_BURST=20 LOG_PREFIX_SSH_ABUSE=SSH_ABUSE:
EOF
}

nf_40_tcp_ssh_normalize_rate() {
    local raw_rate="$1"
    case "$raw_rate" in
        */sec) echo "${raw_rate%/sec}/second" ;;
        */min) echo "${raw_rate%/min}/minute" ;;
        */hour|*/day|*/second|*/minute) echo "$raw_rate" ;;
        *) echo "$raw_rate" ;;
    esac
}

nf_40_tcp_ssh_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_tcp_ssh: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    local normalized_rate
    normalized_rate="$(nf_40_tcp_ssh_normalize_rate "${SSH_RATE:-}")"
    if ! [[ "$normalized_rate" =~ ^[0-9]+/(second|minute|hour|day)$ ]]; then
        echo "ERROR: nf_tcp_ssh: SSH_RATE must match '<num>/(sec|min|second|minute|hour|day)'"
        return 2
    fi

    if ! [[ "${SSH_BURST:-}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: nf_tcp_ssh: SSH_BURST must be numeric"
        return 2
    fi

}

nf_40_tcp_ssh_apply() {
    local chain ssh_ports_expr normalized_rate

    ssh_ports_expr="$(nf_ports_set_expr "$SSH_PORT")"
    normalized_rate="$(nf_40_tcp_ssh_normalize_rate "$SSH_RATE")"

    for chain in $(nf_get_target_chains); do
        nf_add_rule "$chain" tcp dport "$ssh_ports_expr" ct state new limit rate "$normalized_rate" burst "$SSH_BURST" packets accept
        nf_add_rule "$chain" tcp dport "$ssh_ports_expr" ct state new limit rate over 30/minute burst 10 packets log prefix "\"$LOG_PREFIX_SSH_ABUSE \""
        nf_add_rule "$chain" tcp dport "$ssh_ports_expr" ct state new drop
        nf_add_rule "$chain" tcp dport "$ssh_ports_expr" ct state established,related accept
    done
}
