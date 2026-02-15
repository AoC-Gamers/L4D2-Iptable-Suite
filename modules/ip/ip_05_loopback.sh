#!/bin/bash

ip_05_loopback_metadata() {
    cat << 'EOF'
ID=ip_loopback
DESCRIPTION=Allows loopback traffic in INPUT and DOCKER-USER based on TYPECHAIN
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0
EOF
}

ip_05_loopback_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_loopback: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac
}

ip_05_loopback_apply() {
    iptables -A INPUT -i lo -j ACCEPT

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -N DOCKER-USER 2>/dev/null || true
        iptables -A DOCKER-USER -i lo -j ACCEPT
    fi
}
