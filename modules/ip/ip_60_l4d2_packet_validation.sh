#!/bin/bash

ip_60_l4d2_packet_validation_metadata() {
    cat << 'EOF'
ID=ip_l4d2_packet_validation
ALIASES=l4d2_packet_validation
DESCRIPTION=Validates invalid/malformed UDP packet sizes for GameServer and SourceTV
REQUIRED_VARS=TYPECHAIN ENABLE_L4D2_PACKET_VALIDATION L4D2_GAMESERVER_PORTS L4D2_TV_PORTS LOG_PREFIX_INVALID_SIZE LOG_PREFIX_MALFORMED
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 ENABLE_L4D2_PACKET_VALIDATION=true L4D2_GAMESERVER_PORTS=27015 L4D2_TV_PORTS=27020 LOG_PREFIX_INVALID_SIZE=INVALID_SIZE: LOG_PREFIX_MALFORMED=MALFORMED:
EOF
}

ip_60_l4d2_packet_validation_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_l4d2_packet_validation: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    case "${ENABLE_L4D2_PACKET_VALIDATION:-}" in
        true|false) ;;
        *)
            echo "ERROR: ip_l4d2_packet_validation: ENABLE_L4D2_PACKET_VALIDATION must be true or false"
            return 2
            ;;
    esac
}

ip_60_l4d2_packet_validation_apply_for_chain() {
    local chain="$1"
    local ports="$2"

    iptables -A "$chain" -p udp -m multiport --dports "$ports" -m length --length 0:28 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_INVALID_SIZE" --log-level 4
    iptables -A "$chain" -p udp -m multiport --dports "$ports" -m length --length 0:28 -j DROP

    iptables -A "$chain" -p udp -m multiport --dports "$ports" -m length --length 2521:65535 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_INVALID_SIZE" --log-level 4
    iptables -A "$chain" -p udp -m multiport --dports "$ports" -m length --length 2521:65535 -j DROP

    iptables -A "$chain" -p udp -m multiport --dports "$ports" -m length --length 30:32 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A "$chain" -p udp -m multiport --dports "$ports" -m length --length 30:32 -j DROP

    iptables -A "$chain" -p udp -m multiport --dports "$ports" -m length --length 46:46 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A "$chain" -p udp -m multiport --dports "$ports" -m length --length 46:46 -j DROP

    iptables -A "$chain" -p udp -m multiport --dports "$ports" -m length --length 60:60 -m limit --limit 60/min -j LOG --log-prefix "$LOG_PREFIX_MALFORMED" --log-level 4
    iptables -A "$chain" -p udp -m multiport --dports "$ports" -m length --length 60:60 -j DROP
}

ip_60_l4d2_packet_validation_apply() {
    if [ "$ENABLE_L4D2_PACKET_VALIDATION" != "true" ]; then
        echo "INFO: ip_l4d2_packet_validation: disabled (ENABLE_L4D2_PACKET_VALIDATION=false), skipping"
        return 0
    fi

    if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
        ip_60_l4d2_packet_validation_apply_for_chain INPUT "$L4D2_GAMESERVER_PORTS"
        ip_60_l4d2_packet_validation_apply_for_chain INPUT "$L4D2_TV_PORTS"
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -N DOCKER-USER 2>/dev/null || true
        ip_60_l4d2_packet_validation_apply_for_chain DOCKER-USER "$L4D2_GAMESERVER_PORTS"
        ip_60_l4d2_packet_validation_apply_for_chain DOCKER-USER "$L4D2_TV_PORTS"
    fi
}
