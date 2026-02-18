#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_45_http_https_protect_metadata() {
    cat << 'EOF'
ID=nf_http_https_protect
ALIASES=http_https_protect
DESCRIPTION=Applies basic anti-abuse controls for HTTP/HTTPS ports
REQUIRED_VARS=TYPECHAIN HTTP_HTTPS_PORTS HTTP_HTTPS_RATE HTTP_HTTPS_BURST LOG_PREFIX_HTTP_HTTPS_ABUSE
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 HTTP_HTTPS_PORTS=80,443 HTTP_HTTPS_RATE=180/minute HTTP_HTTPS_BURST=360 LOG_PREFIX_HTTP_HTTPS_ABUSE=HTTP_HTTPS_ABUSE:
EOF
}

nf_45_http_https_protect_normalize_rate() {
    local raw_rate="$1"
    case "$raw_rate" in
        */sec) echo "${raw_rate%/sec}/second" ;;
        */min) echo "${raw_rate%/min}/minute" ;;
        */hour|*/day|*/second|*/minute) echo "$raw_rate" ;;
        *) echo "$raw_rate" ;;
    esac
}

nf_45_http_https_protect_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_http_https_protect: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    if [ -n "${HTTP_HTTPS_PORTS:-}" ]; then
        nf_validate_ports_spec "$HTTP_HTTPS_PORTS" "nf_http_https_protect: HTTP_HTTPS_PORTS" || return $?
    fi

    local normalized_rate
    normalized_rate="$(nf_45_http_https_protect_normalize_rate "${HTTP_HTTPS_RATE:-}")"
    if ! [[ "$normalized_rate" =~ ^[0-9]+/(second|minute|hour|day)$ ]]; then
        echo "ERROR: nf_http_https_protect: HTTP_HTTPS_RATE must match '<num>/(sec|min|second|minute|hour|day)'"
        return 2
    fi

    if ! [[ "${HTTP_HTTPS_BURST:-}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: nf_http_https_protect: HTTP_HTTPS_BURST must be numeric"
        return 2
    fi
}

nf_45_http_https_protect_apply() {
    local chain ports_expr normalized_rate

    ports_expr="$(nf_ports_set_expr "$HTTP_HTTPS_PORTS")"
    normalized_rate="$(nf_45_http_https_protect_normalize_rate "$HTTP_HTTPS_RATE")"

    for chain in $(nf_get_target_chains); do
        nf_add_rule "$chain" tcp dport "$ports_expr" ct state new limit rate "$normalized_rate" burst "$HTTP_HTTPS_BURST" packets accept
        nf_add_rule "$chain" tcp dport "$ports_expr" ct state new limit rate over 30/minute burst 10 packets log prefix "\"$LOG_PREFIX_HTTP_HTTPS_ABUSE \""
        nf_add_rule "$chain" tcp dport "$ports_expr" ct state new drop
    done
}
