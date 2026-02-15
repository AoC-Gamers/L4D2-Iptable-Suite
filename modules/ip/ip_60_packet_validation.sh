#!/bin/bash

ip_60_packet_validation_metadata() {
    cat << 'EOF'
ID=ip_packet_validation
DESCRIPTION=Validacion de tamanos UDP invalidos/malformados para GameServer y SourceTV
REQUIRED_VARS=TYPECHAIN GAMESERVERPORTS TVSERVERPORTS LOG_PREFIX_INVALID_SIZE LOG_PREFIX_MALFORMED
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 GAMESERVERPORTS=27015 TVSERVERPORTS=27020 LOG_PREFIX_INVALID_SIZE=INVALID_SIZE: LOG_PREFIX_MALFORMED=MALFORMED:
EOF
}

ip_60_packet_validation_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_packet_validation: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac
}

ip_60_packet_validation_apply_for_chain() {
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

ip_60_packet_validation_apply() {
    if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
        ip_60_packet_validation_apply_for_chain INPUT "$GAMESERVERPORTS"
        ip_60_packet_validation_apply_for_chain INPUT "$TVSERVERPORTS"
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -N DOCKER 2>/dev/null || true
        ip_60_packet_validation_apply_for_chain DOCKER "$GAMESERVERPORTS"
        ip_60_packet_validation_apply_for_chain DOCKER "$TVSERVERPORTS"
    fi
}
