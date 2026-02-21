#!/bin/bash

ip_40_tcp_ssh_metadata() {
    cat << 'EOF'
ID=ip_tcp_ssh
ALIASES=tcp_ssh
DESCRIPTION=Applies base SSH rules in the iptables backend
REQUIRED_VARS=TYPECHAIN SSH_PORT
OPTIONAL_VARS=SSH_DOCKER SSH_RATE SSH_BURST LOG_PREFIX_SSH_ABUSE
DEFAULTS=TYPECHAIN=0 SSH_PORT=22 SSH_DOCKER= SSH_RATE=60/min SSH_BURST=20 LOG_PREFIX_SSH_ABUSE=SSH_ABUSE:
EOF
}

ip_40_tcp_ssh_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_tcp_ssh: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if ! [[ "${SSH_RATE:-}" =~ ^[0-9]+/(sec|min|hour|day)$ ]]; then
        echo "ERROR: ip_tcp_ssh: SSH_RATE must match '<num>/(sec|min|hour|day)'"
        return 2
    fi

    if ! [[ "${SSH_BURST:-}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: ip_tcp_ssh: SSH_BURST must be numeric"
        return 2
    fi

}

ip_40_tcp_ssh_apply() {
    iptables -N SSHfilter 2>/dev/null || true
    iptables -F SSHfilter 2>/dev/null || true

    iptables -A SSHfilter -m conntrack --ctstate NEW -m hashlimit --hashlimit-upto "$SSH_RATE" --hashlimit-burst "$SSH_BURST" --hashlimit-mode srcip,dstport --hashlimit-name SSH_RATE_LIMIT -j ACCEPT
    iptables -A SSHfilter -m conntrack --ctstate NEW -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$LOG_PREFIX_SSH_ABUSE" --log-level 4
    iptables -A SSHfilter -m conntrack --ctstate NEW -j DROP

    iptables -A INPUT -p tcp -m multiport --dports "$SSH_PORT" -m conntrack --ctstate NEW -j SSHfilter
    iptables -A INPUT -p tcp -m multiport --dports "$SSH_PORT" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        if [ -n "$SSH_DOCKER" ]; then
            iptables -A DOCKER-USER -p tcp -m multiport --dports "$SSH_DOCKER" -m conntrack --ctstate NEW -j SSHfilter
            iptables -A DOCKER-USER -p tcp -m multiport --dports "$SSH_DOCKER" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
        fi
    fi
}
