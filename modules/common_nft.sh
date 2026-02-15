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

nf_ports_normalize() {
    local raw="$1"
    local value="${raw// /}"
    value="${value//:/-}"
    echo "$value"
}

nf_ports_set_expr() {
    local normalized
    normalized="$(nf_ports_normalize "$1")"
    echo "{ $normalized }"
}
