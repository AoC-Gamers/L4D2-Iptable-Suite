#!/bin/bash

ip_05_loopback_metadata() {
    cat << 'EOF'
ID=ip_loopback
DESCRIPTION=Permite trafico loopback en INPUT y DOCKER segun TYPECHAIN
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
        iptables -N DOCKER 2>/dev/null || true
        iptables -A DOCKER -i lo -j ACCEPT
    fi
}
