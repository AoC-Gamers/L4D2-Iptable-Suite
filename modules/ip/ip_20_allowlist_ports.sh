#!/bin/bash

ip_20_allowlist_ports_add_first() {
    local chain="$1"
    shift
    iptables -C "$chain" "$@" 2>/dev/null || iptables -I "$chain" 1 "$@"
}

ip_20_allowlist_ports_metadata() {
    cat << 'EOF'
ID=ip_allowlist_ports
DESCRIPTION=Allows additional UDP/TCP ports directly through multiport
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=UDP_ALLOW_PORTS TCP_ALLOW_PORTS
DEFAULTS=TYPECHAIN=0 UDP_ALLOW_PORTS= TCP_ALLOW_PORTS=
EOF
}

ip_20_allowlist_ports_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_allowlist_ports: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac
}

ip_20_allowlist_ports_apply() {
    if [ -n "${UDP_ALLOW_PORTS:-}" ]; then
        if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
            ip_20_allowlist_ports_add_first INPUT -p udp -m multiport --dports "$UDP_ALLOW_PORTS" -j ACCEPT
        fi
        if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
            iptables -N DOCKER 2>/dev/null || true
            ip_20_allowlist_ports_add_first DOCKER -p udp -m multiport --dports "$UDP_ALLOW_PORTS" -j ACCEPT
        fi
    fi

    if [ -n "${TCP_ALLOW_PORTS:-}" ]; then
        if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
            ip_20_allowlist_ports_add_first INPUT -p tcp -m multiport --dports "$TCP_ALLOW_PORTS" -j ACCEPT
        fi
        if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
            iptables -N DOCKER 2>/dev/null || true
            ip_20_allowlist_ports_add_first DOCKER -p tcp -m multiport --dports "$TCP_ALLOW_PORTS" -j ACCEPT
        fi
    fi
}
