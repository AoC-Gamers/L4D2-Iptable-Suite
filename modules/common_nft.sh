#!/bin/bash

nf_get_target_chains() {
    case "${TYPECHAIN:-0}" in
        0)
            echo "input"
            ;;
        1)
            echo "forward"
            ;;
        2)
            echo "input forward"
            ;;
        *)
            return 2
            ;;
    esac
}

nf_chain_enabled() {
    local target="$1"
    local c
    for c in $(nf_get_target_chains); do
        if [ "$c" = "$target" ]; then
            return 0
        fi
    done
    return 1
}

nf_add_rule() {
    local chain="$1"
    shift
    nft add rule inet l4d2_filter "$chain" "$@"
}

nf_build_log_prefix() {
    local _legacy_prefix="$1"
    local attack="$2"
    local module="$3"
    local chain="$4"
    local action="${5:-drop}"
    local severity="${6:-medium}"

    local safe_host
    safe_host="${FIREWALL_HOST_ALIAS:-}"
    safe_host="${safe_host// /_}"

    local prefix="FW_EVT attack=${attack} backend=nft module=${module} chain=${chain} action=${action} severity=${severity}"
    if [ -n "$safe_host" ]; then
        prefix="${prefix} host=${safe_host}"
    fi

    printf "%s: " "$prefix"
}

nf_ports_normalize() {
    local raw="$1"
    local value="$raw"
    value="${value//;/,}"
    value="${value// /}"
    value="${value//$'\t'/}"
    value="${value//$'\n'/}"
    while [[ "$value" == *",,"* ]]; do
        value="${value//,,/,}"
    done
    value="${value#,}"
    value="${value%,}"
    value="${value//:/-}"
    echo "$value"
}

nf_ports_set_expr() {
    local normalized
    normalized="$(nf_ports_normalize "$1")"
    echo "{ $normalized }"
}

nf_validate_ports_spec() {
    local raw="$1"
    local label="$2"
    local normalized
    local item start end

    normalized="$(nf_ports_normalize "$raw")"

    if [ -z "$normalized" ]; then
        return 0
    fi

    if ! [[ "$normalized" =~ ^[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*$ ]]; then
        echo "ERROR: ${label}: invalid port expression '$raw'"
        return 2
    fi

    IFS=',' read -r -a _nf_items <<< "$normalized"
    for item in "${_nf_items[@]}"; do
        if [[ "$item" == *"-"* ]]; then
            start="${item%-*}"
            end="${item#*-}"
            if [ "$start" -gt "$end" ]; then
                echo "ERROR: ${label}: invalid range '$item' (start > end)"
                return 2
            fi
        else
            start="$item"
            end="$item"
        fi

        if [ "$start" -lt 1 ] || [ "$end" -gt 65535 ]; then
            echo "ERROR: ${label}: ports must be in range 1-65535 ('$item')"
            return 2
        fi
    done

    return 0
}
