#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_22_docker_dns_egress_metadata() {
    cat << 'EOF'
ID=nf_docker_dns_egress
ALIASES=docker_dns_egress
DESCRIPTION=Allows DNS egress (UDP/TCP 53) from Docker bridge subnets on FORWARD chain
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=DOCKER_DNS_EGRESS_SUBNETS
DEFAULTS=TYPECHAIN=0 DOCKER_DNS_EGRESS_SUBNETS=172.16.0.0/12
EOF
}

nf_22_docker_dns_egress_is_ipv4_cidr() {
    local cidr="$1"
    local ip prefix a b c d octet

    [[ "$cidr" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]] || return 1

    ip="${cidr%/*}"
    prefix="${cidr#*/}"

    IFS='.' read -r a b c d <<< "$ip"
    for octet in "$a" "$b" "$c" "$d"; do
        [ "$octet" -ge 0 ] && [ "$octet" -le 255 ] || return 1
    done

    [ "$prefix" -ge 0 ] && [ "$prefix" -le 32 ]
}

nf_22_docker_dns_egress_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_docker_dns_egress: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    local raw="${DOCKER_DNS_EGRESS_SUBNETS:-}"
    local item trimmed

    IFS=',' read -r -a _subnets <<< "$raw"
    for item in "${_subnets[@]}"; do
        trimmed="$item"
        trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [ -z "$trimmed" ] && continue

        nf_22_docker_dns_egress_is_ipv4_cidr "$trimmed" || {
            echo "ERROR: nf_docker_dns_egress: invalid CIDR '$trimmed' in DOCKER_DNS_EGRESS_SUBNETS"
            return 2
        }
    done
}

nf_22_docker_dns_egress_apply() {
    nf_chain_enabled forward || return 0

    local item trimmed
    IFS=',' read -r -a _subnets <<< "${DOCKER_DNS_EGRESS_SUBNETS:-}"

    for item in "${_subnets[@]}"; do
        trimmed="$item"
        trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [ -z "$trimmed" ] && continue

        nf_add_rule forward ip saddr "$trimmed" udp dport 53 accept
        nf_add_rule forward ip saddr "$trimmed" tcp dport 53 accept
    done
}
