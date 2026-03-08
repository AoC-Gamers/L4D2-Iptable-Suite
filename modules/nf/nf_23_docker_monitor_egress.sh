#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_23_docker_monitor_egress_metadata() {
    cat << 'EOF'
ID=nf_docker_monitor_egress
ALIASES=docker_monitor_egress
DESCRIPTION=Allows monitoring egress (e.g. Prometheus/node-exporter) from Docker subnets to selected LAN targets
REQUIRED_VARS=TYPECHAIN
OPTIONAL_VARS=DOCKER_MONITOR_EGRESS_SUBNETS DOCKER_MONITOR_EGRESS_TARGETS DOCKER_MONITOR_EGRESS_TCP_PORTS
DEFAULTS=TYPECHAIN=0 DOCKER_MONITOR_EGRESS_SUBNETS=172.16.0.0/12 DOCKER_MONITOR_EGRESS_TARGETS= DOCKER_MONITOR_EGRESS_TCP_PORTS=9100
EOF
}

nf_23_docker_monitor_egress_is_ipv4_cidr() {
    local cidr="$1"
    local ip prefix a b c d octet

    [[ "$cidr" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]] || return 1

    ip="${cidr%/*}"
    prefix="${cidr#*/}"

    IFS='.' read -r a b c d <<< "$ip"
    for octet in "$a" "$b" "$c" "$d"; do
        [ "$octet" -ge 0 ] && [ "$octet" -le 255 ] || return 1
    done

    [ "$prefix" -ge 0 ] && [ "$prefix" -le 32 ]
}

nf_23_docker_monitor_egress_is_ipv4() {
    local ip="$1"
    local a b c d octet

    [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
    IFS='.' read -r a b c d <<< "$ip"
    for octet in "$a" "$b" "$c" "$d"; do
        [ "$octet" -ge 0 ] && [ "$octet" -le 255 ] || return 1
    done
}

nf_23_docker_monitor_egress_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_docker_monitor_egress: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    local raw_subnets="${DOCKER_MONITOR_EGRESS_SUBNETS:-}"
    local raw_targets="${DOCKER_MONITOR_EGRESS_TARGETS:-}"
    local item trimmed

    IFS=',' read -r -a _subnets <<< "$raw_subnets"
    for item in "${_subnets[@]}"; do
        trimmed="$item"
        trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [ -z "$trimmed" ] && continue

        nf_23_docker_monitor_egress_is_ipv4_cidr "$trimmed" || {
            echo "ERROR: nf_docker_monitor_egress: invalid CIDR '$trimmed' in DOCKER_MONITOR_EGRESS_SUBNETS"
            return 2
        }
    done

    IFS=',' read -r -a _targets <<< "$raw_targets"
    for item in "${_targets[@]}"; do
        trimmed="$item"
        trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [ -z "$trimmed" ] && continue

        nf_23_docker_monitor_egress_is_ipv4 "$trimmed" || {
            echo "ERROR: nf_docker_monitor_egress: invalid IPv4 '$trimmed' in DOCKER_MONITOR_EGRESS_TARGETS"
            return 2
        }
    done

    if [ -n "${DOCKER_MONITOR_EGRESS_TCP_PORTS:-}" ]; then
        nf_validate_ports_spec "$DOCKER_MONITOR_EGRESS_TCP_PORTS" "nf_docker_monitor_egress: DOCKER_MONITOR_EGRESS_TCP_PORTS" || return $?
    fi
}

nf_23_docker_monitor_egress_apply() {
    nf_chain_enabled forward || return 0

    local ports_expr item_s item_t subnet target
    local has_target=false
    ports_expr="$(nf_ports_set_expr "${DOCKER_MONITOR_EGRESS_TCP_PORTS:-9100}")"

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

            nf_add_rule forward ip saddr "$subnet" ip daddr "$target" tcp dport "$ports_expr" accept
        done
    done

    if [ "$has_target" = "false" ]; then
        echo "INFO: nf_docker_monitor_egress: no DOCKER_MONITOR_EGRESS_TARGETS defined; nothing to apply"
    fi
}
