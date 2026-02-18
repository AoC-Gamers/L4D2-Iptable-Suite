#!/bin/bash

ip_30_openvpn_add_rule_first() {
    local chain="$1"
    shift
    iptables -C "$chain" "$@" 2>/dev/null || iptables -I "$chain" 1 "$@"
}

ip_30_openvpn_add_rule_table() {
    local table="$1"
    shift
    local chain="$1"
    shift
    iptables -t "$table" -C "$chain" "$@" 2>/dev/null || iptables -t "$table" -A "$chain" "$@"
}

ip_30_openvpn_metadata() {
    cat << 'EOF'
ID=ip_openvpn
ALIASES=openvpn
DESCRIPTION=Applies OpenVPN rules in the iptables backend (host/DOCKER-USER)
REQUIRED_VARS=TYPECHAIN VPN_PORT VPN_SUBNET VPN_INTERFACE
OPTIONAL_VARS=VPN_PROTO VPN_PORT VPN_SUBNET VPN_INTERFACE VPN_DOCKER_INTERFACE VPN_LAN_SUBNET VPN_LAN_INTERFACE VPN_ENABLE_NAT VPN_LOG_ENABLED VPN_LOG_PREFIX VPN_ROUTER_REAL_IP VPN_ROUTER_ALIAS_IP
DEFAULTS=TYPECHAIN=0 VPN_PROTO=udp VPN_PORT=1194 VPN_SUBNET=10.8.0.0/24 VPN_INTERFACE=tun0 VPN_DOCKER_INTERFACE= VPN_LAN_SUBNET=192.168.1.0/24 VPN_LAN_INTERFACE= VPN_ENABLE_NAT=false VPN_LOG_ENABLED=false VPN_LOG_PREFIX=VPN_TRAFFIC: VPN_ROUTER_REAL_IP= VPN_ROUTER_ALIAS_IP=
EOF
}

ip_30_openvpn_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_openvpn: TYPECHAIN must be 0, 1 or 2 (current: ${TYPECHAIN:-unset})"
            return 2
            ;;
    esac

    if ! [[ "${VPN_PORT}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: ip_openvpn: VPN_PORT must be numeric"
        return 2
    fi
    if [ -z "${VPN_SUBNET:-}" ] || [ -z "${VPN_INTERFACE:-}" ]; then
        echo "ERROR: ip_openvpn: VPN_SUBNET and VPN_INTERFACE are required"
        return 2
    fi
}

ip_30_openvpn_apply() {
    VPN_PROTO="$(echo "${VPN_PROTO}" | tr 'A-Z' 'a-z')"

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -N DOCKER-USER 2>/dev/null || true
    fi

    ip_30_openvpn_add_rule_first INPUT -p "$VPN_PROTO" --dport "$VPN_PORT" -j ACCEPT
    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        ip_30_openvpn_add_rule_first DOCKER-USER -p "$VPN_PROTO" --dport "$VPN_PORT" -j ACCEPT
    fi

    if [ "$VPN_LOG_ENABLED" = "true" ]; then
        ip_30_openvpn_add_rule_first INPUT -p "$VPN_PROTO" --dport "$VPN_PORT" -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$VPN_LOG_PREFIX" --log-level 4
        if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
            ip_30_openvpn_add_rule_first DOCKER-USER -p "$VPN_PROTO" --dport "$VPN_PORT" -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$VPN_LOG_PREFIX" --log-level 4
        fi
    fi

    ip_30_openvpn_add_rule_first INPUT -i "$VPN_INTERFACE" -s "$VPN_SUBNET" -j ACCEPT
    if [ -n "$VPN_DOCKER_INTERFACE" ]; then
        ip_30_openvpn_add_rule_first INPUT -i "$VPN_DOCKER_INTERFACE" -s "$VPN_SUBNET" -j ACCEPT
    fi

    if [ -n "$VPN_ROUTER_REAL_IP" ] && [ -n "$VPN_ROUTER_ALIAS_IP" ]; then
        ip_30_openvpn_add_rule_table nat PREROUTING -i "$VPN_INTERFACE" -d "$VPN_ROUTER_ALIAS_IP" -j DNAT --to-destination "$VPN_ROUTER_REAL_IP"
        if [ -n "$VPN_DOCKER_INTERFACE" ]; then
            ip_30_openvpn_add_rule_table nat PREROUTING -i "$VPN_DOCKER_INTERFACE" -d "$VPN_ROUTER_ALIAS_IP" -j DNAT --to-destination "$VPN_ROUTER_REAL_IP"
        fi
    fi

    if [ -n "$VPN_LAN_SUBNET" ]; then
        ip_30_openvpn_add_rule_first FORWARD -i "$VPN_INTERFACE" -s "$VPN_SUBNET" -d "$VPN_LAN_SUBNET" -j ACCEPT
        ip_30_openvpn_add_rule_first FORWARD -o "$VPN_INTERFACE" -s "$VPN_LAN_SUBNET" -d "$VPN_SUBNET" -m state --state ESTABLISHED,RELATED -j ACCEPT

        if [ -n "$VPN_DOCKER_INTERFACE" ]; then
            ip_30_openvpn_add_rule_first FORWARD -i "$VPN_DOCKER_INTERFACE" -s "$VPN_SUBNET" -d "$VPN_LAN_SUBNET" -j ACCEPT
            ip_30_openvpn_add_rule_first FORWARD -o "$VPN_DOCKER_INTERFACE" -s "$VPN_LAN_SUBNET" -d "$VPN_SUBNET" -m state --state ESTABLISHED,RELATED -j ACCEPT
        fi

        if [ "$VPN_LOG_ENABLED" = "true" ]; then
            ip_30_openvpn_add_rule_first FORWARD -i "$VPN_INTERFACE" -s "$VPN_SUBNET" -d "$VPN_LAN_SUBNET" -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$VPN_LOG_PREFIX" --log-level 4
            if [ -n "$VPN_DOCKER_INTERFACE" ]; then
                ip_30_openvpn_add_rule_first FORWARD -i "$VPN_DOCKER_INTERFACE" -s "$VPN_SUBNET" -d "$VPN_LAN_SUBNET" -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$VPN_LOG_PREFIX" --log-level 4
            fi
        fi
    else
        echo "WARNING: ip_openvpn: VPN_LAN_SUBNET is empty; skipping forwarding rules"
    fi

    if [ "$VPN_ENABLE_NAT" = "true" ]; then
        if [ -n "$VPN_LAN_INTERFACE" ]; then
            ip_30_openvpn_add_rule_first FORWARD -i "$VPN_INTERFACE" -s "$VPN_SUBNET" -o "$VPN_LAN_INTERFACE" -j ACCEPT
            ip_30_openvpn_add_rule_first FORWARD -o "$VPN_INTERFACE" -d "$VPN_SUBNET" -i "$VPN_LAN_INTERFACE" -m state --state ESTABLISHED,RELATED -j ACCEPT
            ip_30_openvpn_add_rule_table nat POSTROUTING -s "$VPN_SUBNET" -o "$VPN_LAN_INTERFACE" -j MASQUERADE
        else
            echo "WARNING: ip_openvpn: VPN_ENABLE_NAT=true but VPN_LAN_INTERFACE is empty; skipping NAT"
        fi
    fi
}
