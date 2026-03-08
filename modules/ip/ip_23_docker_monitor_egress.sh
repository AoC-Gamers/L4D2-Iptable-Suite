#!/bin/bash

ip_23_docker_monitor_egress_add_first() {
    local chain="$1"
    shift
    iptables -C "$chain" "$@" 2>/dev/null || iptables -I "$chain" 1 "$@"
}

ip_23_docker_monitor_egress_is_ipv4() {
    local ip="$1"
    local a b c d octet

    [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
    IFS='.' read -r a b c d <<< "$ip"
    for octet in "$a" "$b" "$c" "$d"; do
        [ "$octet" -ge 0 ] && [ "$octet" -le 255 ] || return 1
    done
}

ip_23_docker_monitor_egress_metadata() {
    cat << 'EOF'
ID=ip_docker_monitor_egress
ALIASES=docker_monitor_egress
DESCRIPTION=Allows monitoring egress (e.g. Prometheus/node-exporter) from Docker subnets to selected LAN targets
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=DOCKER_MONITOR_EGRESS_SUBNETS DOCKER_MONITOR_EGRESS_TARGETS DOCKER_MONITOR_EGRESS_TCP_PORTS
DEFAULTS=TYPECHAIN=0 DOCKER_MONITOR_EGRESS_SUBNETS=172.16.0.0/12 DOCKER_MONITOR_EGRESS_TARGETS= DOCKER_MONITOR_EGRESS_TCP_PORTS=9100
EOF
}

ip_23_docker_monitor_egress_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_docker_monitor_egress: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    local item trimmed
    IFS=',' read -r -a _targets <<< "${DOCKER_MONITOR_EGRESS_TARGETS:-}"
    for item in "${_targets[@]}"; do
        trimmed="$item"
        trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [ -z "$trimmed" ] && continue

        ip_23_docker_monitor_egress_is_ipv4 "$trimmed" || {
            echo "ERROR: ip_docker_monitor_egress: invalid IPv4 '$trimmed' in DOCKER_MONITOR_EGRESS_TARGETS"
            return 2
        }
    done
}

ip_23_docker_monitor_egress_apply() {
    if [ "$TYPECHAIN" -eq 0 ]; then
        return 0
    fi

    iptables -N DOCKER-USER 2>/dev/null || true

    local dports subnet target item_s item_t
    local has_target=false

    dports="${DOCKER_MONITOR_EGRESS_TCP_PORTS:-9100}"
    dports="${dports//;/,}"
    dports="${dports// /}"
    dports="${dports//$'\t'/}"
    dports="${dports//$'\n'/}"
    dports="${dports//-/:}"

    IFS=',' read -r -a _subnets <<< "${DOCKER_MONITOR_EGRESS_SUBNETS:-}"
    IFS=',' read -r -a _targets <<< "${DOCKER_MONITOR_EGRESS_TARGETS:-}"

    for item_t in "${_targets[@]}"; do
        target="$item_t"
        target="${target#"${target%%[![:space:]]*}"}"
        target="${target%"${target##*[![:space:]]}"}"
        [ -z "$target" ] && continue
        has_target=true

        for item_s in "${_subnets[@]}"; do
            subnet="$item_s"
            subnet="${subnet#"${subnet%%[![:space:]]*}"}"
            subnet="${subnet%"${subnet##*[![:space:]]}"}"
            [ -z "$subnet" ] && continue

            ip_23_docker_monitor_egress_add_first DOCKER-USER \
                -s "$subnet" -d "$target" -p tcp -m multiport --dports "$dports" -j ACCEPT
        done
    done

    if [ "$has_target" = "false" ]; then
        echo "INFO: ip_docker_monitor_egress: no DOCKER_MONITOR_EGRESS_TARGETS defined; nothing to apply"
    fi
}
