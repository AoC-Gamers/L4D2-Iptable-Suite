#!/bin/bash

ip_22_docker_dns_egress_add_first() {
    local chain="$1"
    shift
    iptables -C "$chain" "$@" 2>/dev/null || iptables -I "$chain" 1 "$@"
}

ip_22_docker_dns_egress_metadata() {
    cat << 'EOF'
ID=ip_docker_dns_egress
ALIASES=docker_dns_egress
DESCRIPTION=Allows DNS egress (UDP/TCP 53) from Docker bridge subnets in DOCKER-USER
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=DOCKER_DNS_EGRESS_SUBNETS
DEFAULTS=TYPECHAIN=0 DOCKER_DNS_EGRESS_SUBNETS=172.16.0.0/12
EOF
}

ip_22_docker_dns_egress_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_docker_dns_egress: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac
}

ip_22_docker_dns_egress_apply() {
    if [ "$TYPECHAIN" -eq 0 ]; then
        return 0
    fi

    iptables -N DOCKER-USER 2>/dev/null || true

    local item trimmed
    IFS=',' read -r -a _subnets <<< "${DOCKER_DNS_EGRESS_SUBNETS:-}"
    for item in "${_subnets[@]}"; do
        trimmed="$item"
        trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [ -z "$trimmed" ] && continue

        ip_22_docker_dns_egress_add_first DOCKER-USER -s "$trimmed" -p udp --dport 53 -j ACCEPT
        ip_22_docker_dns_egress_add_first DOCKER-USER -s "$trimmed" -p tcp --dport 53 -j ACCEPT
    done
}
