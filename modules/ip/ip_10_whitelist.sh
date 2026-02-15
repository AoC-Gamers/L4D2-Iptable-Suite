#!/bin/bash

ip_10_whitelist_metadata() {
    cat << 'EOF'
ID=ip_whitelist
DESCRIPTION=Allows full traffic from IPs listed in WHITELISTED_IPS
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=WHITELISTED_IPS
DEFAULTS=TYPECHAIN=0 WHITELISTED_IPS=
EOF
}

ip_10_whitelist_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_whitelist: TYPECHAIN must be 0, 1 or 2 (current: ${TYPECHAIN:-unset})"
            return 2
            ;;
    esac
}

ip_10_whitelist_apply() {
    if [ -z "${WHITELISTED_IPS:-}" ]; then
        echo "INFO: ip_whitelist: no WHITELISTED_IPS configured"
        return 0
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -N DOCKER-USER 2>/dev/null || true
    fi

    local ip
    for ip in $WHITELISTED_IPS; do
        if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
            iptables -C INPUT -s "$ip" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -s "$ip" -j ACCEPT
        fi

        if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
            iptables -C DOCKER-USER -s "$ip" -j ACCEPT 2>/dev/null || iptables -I DOCKER-USER 1 -s "$ip" -j ACCEPT
        fi
    done
}
