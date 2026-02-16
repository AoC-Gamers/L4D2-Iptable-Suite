#!/bin/bash

ip_45_http_https_protect_add_rule() {
    local chain="$1"
    shift
    iptables -C "$chain" "$@" 2>/dev/null || iptables -A "$chain" "$@"
}

ip_45_http_https_protect_metadata() {
    cat << 'EOF'
ID=ip_http_https_protect
DESCRIPTION=Applies basic anti-abuse controls for HTTP/HTTPS ports
REQUIRED_VARS=TYPECHAIN ENABLE_HTTP_PROTECT HTTP_HTTPS_PORTS HTTP_HTTPS_RATE HTTP_HTTPS_BURST LOG_PREFIX_HTTP_HTTPS_ABUSE
OPTIONAL_VARS=HTTP_HTTPS_DOCKER
DEFAULTS=TYPECHAIN=0 ENABLE_HTTP_PROTECT=false HTTP_HTTPS_PORTS=80,443 HTTP_HTTPS_RATE=180/min HTTP_HTTPS_BURST=360 HTTP_HTTPS_DOCKER=80,443 LOG_PREFIX_HTTP_HTTPS_ABUSE=HTTP_HTTPS_ABUSE:
EOF
}

ip_45_http_https_protect_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_http_https_protect: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    case "${ENABLE_HTTP_PROTECT:-false}" in
        true|false) ;;
        *)
            echo "ERROR: ip_http_https_protect: ENABLE_HTTP_PROTECT must be true or false"
            return 2
            ;;
    esac

    if [ -n "${HTTP_HTTPS_PORTS:-}" ] && ! [[ "${HTTP_HTTPS_PORTS}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_http_https_protect: invalid HTTP_HTTPS_PORTS format"
        return 2
    fi

    if [ -n "${HTTP_HTTPS_DOCKER:-}" ] && ! [[ "${HTTP_HTTPS_DOCKER}" =~ ^[0-9]+(:[0-9]+)?(,[0-9]+(:[0-9]+)?)*$ ]]; then
        echo "ERROR: ip_http_https_protect: invalid HTTP_HTTPS_DOCKER format"
        return 2
    fi

    if ! [[ "${HTTP_HTTPS_RATE:-}" =~ ^[0-9]+/(sec|min|hour|day)$ ]]; then
        echo "ERROR: ip_http_https_protect: HTTP_HTTPS_RATE must match '<num>/(sec|min|hour|day)'"
        return 2
    fi

    if ! [[ "${HTTP_HTTPS_BURST:-}" =~ ^[0-9]+$ ]]; then
        echo "ERROR: ip_http_https_protect: HTTP_HTTPS_BURST must be numeric"
        return 2
    fi
}

ip_45_http_https_protect_apply_chain() {
    local chain="$1"
    local ports="$2"
    local hash_name="$3"

    [ -z "$ports" ] && return 0

    ip_45_http_https_protect_add_rule "$chain" -p tcp -m multiport --dports "$ports" -m conntrack --ctstate NEW \
        -m hashlimit --hashlimit-upto "$HTTP_HTTPS_RATE" --hashlimit-burst "$HTTP_HTTPS_BURST" \
        --hashlimit-mode srcip,dstport --hashlimit-name "$hash_name" -j ACCEPT

    ip_45_http_https_protect_add_rule "$chain" -p tcp -m multiport --dports "$ports" -m conntrack --ctstate NEW \
        -m limit --limit 30/min --limit-burst 10 -j LOG --log-prefix "$LOG_PREFIX_HTTP_HTTPS_ABUSE" --log-level 4

    ip_45_http_https_protect_add_rule "$chain" -p tcp -m multiport --dports "$ports" -m conntrack --ctstate NEW -j DROP
}

ip_45_http_https_protect_apply() {
    if [ "${ENABLE_HTTP_PROTECT}" != "true" ]; then
        echo "INFO: ip_http_https_protect: disabled, skipping"
        return 0
    fi

    if [ "$TYPECHAIN" -eq 0 ] || [ "$TYPECHAIN" -eq 2 ]; then
        ip_45_http_https_protect_apply_chain INPUT "$HTTP_HTTPS_PORTS" HTTPHTTPSNEW
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -N DOCKER-USER 2>/dev/null || true
        ip_45_http_https_protect_apply_chain DOCKER-USER "$HTTP_HTTPS_DOCKER" HTTPHTTPSNEWDOCKER
        return 0
    fi

    if iptables -S DOCKER-USER >/dev/null 2>&1; then
        ip_45_http_https_protect_apply_chain DOCKER-USER "$HTTP_HTTPS_DOCKER" HTTPHTTPSNEWDOCKER
    fi
}
