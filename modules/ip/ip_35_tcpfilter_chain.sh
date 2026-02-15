#!/bin/bash

ip_35_tcpfilter_chain_metadata() {
    cat << 'EOF'
ID=ip_tcpfilter_chain
DESCRIPTION=Sets up the TCPfilter chain to control new TCP connections
REQUIRED_VARS=ENABLE_TCP_PROTECT LOG_PREFIX_TCP_RCON_BLOCK
OPTIONAL_VARS=TCP_PROTECTION TCP_DOCKER
DEFAULTS=ENABLE_TCP_PROTECT=true LOG_PREFIX_TCP_RCON_BLOCK=TCP_RCON_BLOCK: TCP_PROTECTION= TCP_DOCKER=
EOF
}

ip_35_tcpfilter_chain_validate() {
    case "${ENABLE_TCP_PROTECT:-}" in
        true|false) ;;
        *)
            echo "ERROR: ip_tcpfilter_chain: ENABLE_TCP_PROTECT must be true or false"
            return 2
            ;;
    esac
}

ip_35_tcpfilter_chain_apply() {
    if [ "$ENABLE_TCP_PROTECT" = "true" ] || [ -n "$TCP_PROTECTION" ] || [ -n "$TCP_DOCKER" ]; then
        iptables -N TCPfilter 2>/dev/null || true
        iptables -A TCPfilter -m state --state NEW -m hashlimit --hashlimit-upto 1/sec --hashlimit-burst 5 --hashlimit-mode srcip,dstport --hashlimit-name TCPDOSPROTECT --hashlimit-htable-expire 60000 --hashlimit-htable-max 999999999 -j ACCEPT
        iptables -A TCPfilter -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
        iptables -A TCPfilter -j DROP
    fi
}
