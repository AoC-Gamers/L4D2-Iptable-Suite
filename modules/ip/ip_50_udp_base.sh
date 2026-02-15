#!/bin/bash

ip_50_udp_base_metadata() {
    cat << 'EOF'
ID=ip_udp_base
DESCRIPTION=Applies base UDP/state/ICMP rules for GameServer and SourceTV services
REQUIRED_VARS=TYPECHAIN GAMESERVERPORTS TVSERVERPORTS CMD_LIMIT LOG_PREFIX_UDP_NEW_LIMIT LOG_PREFIX_UDP_EST_LIMIT LOG_PREFIX_ICMP_FLOOD
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 GAMESERVERPORTS=27015 TVSERVERPORTS=27020 CMD_LIMIT=100 LOG_PREFIX_UDP_NEW_LIMIT=UDP_NEW_LIMIT: LOG_PREFIX_UDP_EST_LIMIT=UDP_EST_LIMIT: LOG_PREFIX_ICMP_FLOOD=ICMP_FLOOD:
EOF
}

ip_50_udp_base_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_udp_base: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if ! [[ "${CMD_LIMIT}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: ip_udp_base: CMD_LIMIT must be numeric"
        return 2
    fi

    if [ "$CMD_LIMIT" -lt 10 ] || [ "$CMD_LIMIT" -gt 10000 ]; then
        echo "ERROR: ip_udp_base: CMD_LIMIT must be between 10 and 10000"
        return 2
    fi

    if [ -n "${GAMESERVERPORTS:-}" ] && ! [[ "${GAMESERVERPORTS}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_udp_base: invalid GAMESERVERPORTS format"
        return 2
    fi

    if [ -n "${TVSERVERPORTS:-}" ] && ! [[ "${TVSERVERPORTS}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_udp_base: invalid TVSERVERPORTS format"
        return 2
    fi
}

ip_50_udp_base_apply() {
    local cmd_limit_leeway=$((CMD_LIMIT + 10))
    local cmd_limit_upper=$((CMD_LIMIT + 30))

    iptables -A UDP_GAME_NEW_LIMIT -m hashlimit --hashlimit-upto 1/s --hashlimit-burst 3 --hashlimit-mode srcip,dstport --hashlimit-name L4D2_NEW_HASHLIMIT --hashlimit-htable-expire 5000 -j UDP_GAME_NEW_LIMIT_GLOBAL
    iptables -A UDP_GAME_NEW_LIMIT -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_UDP_NEW_LIMIT" --log-level 4
    iptables -A UDP_GAME_NEW_LIMIT -j DROP

    iptables -A UDP_GAME_NEW_LIMIT_GLOBAL -m hashlimit --hashlimit-upto 10/s --hashlimit-burst 20 --hashlimit-mode dstport --hashlimit-name L4D2_NEW_HASHLIMIT_GLOBAL --hashlimit-htable-expire 5000 -j ACCEPT
    iptables -A UDP_GAME_NEW_LIMIT_GLOBAL -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_UDP_NEW_LIMIT" --log-level 4
    iptables -A UDP_GAME_NEW_LIMIT_GLOBAL -j DROP

    iptables -A UDP_GAME_ESTABLISHED_LIMIT -m hashlimit --hashlimit-upto ${cmd_limit_leeway}/s --hashlimit-burst ${cmd_limit_upper} --hashlimit-mode srcip,srcport,dstport --hashlimit-name L4D2_ESTABLISHED_HASHLIMIT -j ACCEPT
    iptables -A UDP_GAME_ESTABLISHED_LIMIT -m limit --limit 60/min --limit-burst 20 -j LOG --log-prefix "$LOG_PREFIX_UDP_EST_LIMIT" --log-level 4
    iptables -A UDP_GAME_ESTABLISHED_LIMIT -j DROP

    local chain
    for chain in INPUT DOCKER-USER; do
        if [ "$chain" = "DOCKER-USER" ] && [ "$TYPECHAIN" -eq 0 ]; then
            continue
        fi
        if [ "$chain" = "INPUT" ] && [ "$TYPECHAIN" -eq 1 ]; then
            continue
        fi

        iptables -A "$chain" -p udp -m multiport --dports "$GAMESERVERPORTS" -m state --state NEW -j UDP_GAME_NEW_LIMIT
        iptables -A "$chain" -p udp -m multiport --dports "$TVSERVERPORTS" -m state --state NEW -j UDP_GAME_NEW_LIMIT

        iptables -A "$chain" -p udp -m multiport --dports "$GAMESERVERPORTS" -m state --state ESTABLISHED -j UDP_GAME_ESTABLISHED_LIMIT
        iptables -A "$chain" -p udp -m multiport --dports "$TVSERVERPORTS" -m state --state ESTABLISHED -j UDP_GAME_ESTABLISHED_LIMIT
    done

    iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -A DOCKER-USER -m state --state ESTABLISHED,RELATED -j ACCEPT
    fi

    iptables -A INPUT -p udp --sport 53 -m state --state ESTABLISHED,RELATED -j ACCEPT
    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -A DOCKER-USER -p udp --sport 53 -m state --state ESTABLISHED,RELATED -j ACCEPT
    fi

    if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -A INPUT -p icmp -m hashlimit --hashlimit-upto 20/sec --hashlimit-burst 2 --hashlimit-mode dstip --hashlimit-name PINGPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -j ACCEPT
        iptables -A INPUT -p icmp -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$LOG_PREFIX_ICMP_FLOOD" --log-level 4
        iptables -A INPUT -p icmp -j DROP
    fi
    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -A DOCKER-USER -p icmp -m hashlimit --hashlimit-upto 20/sec --hashlimit-burst 2 --hashlimit-mode dstip --hashlimit-name PINGPROTECT --hashlimit-htable-expire 1000 --hashlimit-htable-max 1048576 -j ACCEPT
        iptables -A DOCKER-USER -p icmp -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$LOG_PREFIX_ICMP_FLOOD" --log-level 4
        iptables -A DOCKER-USER -p icmp -j DROP
    fi
}
