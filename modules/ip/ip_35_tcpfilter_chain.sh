#!/bin/bash

ip_35_tcpfilter_chain_metadata() {
    cat << 'EOF'
ID=ip_l4d2_tcpfilter_chain
ALIASES=l4d2_tcpfilter_chain
DESCRIPTION=Sets up the TCPfilter chain to control new TCP connections
REQUIRED_VARS=
OPTIONAL_VARS=LOG_PREFIX_TCP_RCON_BLOCK TCP_DOCKER
DEFAULTS=LOG_PREFIX_TCP_RCON_BLOCK=TCP_RCON_BLOCK: TCP_DOCKER=
EOF
}

ip_35_tcpfilter_chain_validate() {
    return 0
}

ip_35_tcpfilter_chain_apply() {
    if [ -n "${TCP_DOCKER:-}" ]; then
        iptables -N TCPfilter 2>/dev/null || true
        iptables -A TCPfilter -m state --state NEW -m hashlimit --hashlimit-upto 1/sec --hashlimit-burst 5 --hashlimit-mode srcip,dstport --hashlimit-name TCPDOSPROTECT --hashlimit-htable-expire 60000 --hashlimit-htable-max 999999999 -j ACCEPT
        iptables -A TCPfilter -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_TCP_RCON_BLOCK" --log-level 4
        iptables -A TCPfilter -j DROP
    fi
}
