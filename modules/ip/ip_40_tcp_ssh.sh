#!/bin/bash

ip_40_tcp_ssh_metadata() {
    cat << 'EOF'
ID=ip_tcp_ssh
DESCRIPTION=Applies base SSH rules in the iptables backend
REQUIRED_VARS=TYPECHAIN SSH_PORT
OPTIONAL_VARS=SSH_DOCKER SSH_REQUIRE_WHITELIST WHITELISTED_IPS WHITELISTED_DOMAINS
DEFAULTS=TYPECHAIN=0 SSH_PORT=22 SSH_DOCKER= SSH_REQUIRE_WHITELIST=false WHITELISTED_IPS= WHITELISTED_DOMAINS=
EOF
}

ip_40_tcp_ssh_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_tcp_ssh: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    case "${SSH_REQUIRE_WHITELIST:-false}" in
        true|false) ;;
        *)
            echo "ERROR: ip_tcp_ssh: SSH_REQUIRE_WHITELIST must be true or false"
            return 2
            ;;
    esac

    if [ "${SSH_REQUIRE_WHITELIST:-false}" = "true" ] && [ -z "${WHITELISTED_IPS:-}" ] && [ -z "${WHITELISTED_DOMAINS:-}" ]; then
        echo "ERROR: ip_tcp_ssh: SSH_REQUIRE_WHITELIST=true requires WHITELISTED_IPS and/or WHITELISTED_DOMAINS"
        return 2
    fi
}

ip_40_tcp_ssh_apply() {
    local allow_public_ssh

    allow_public_ssh=true
    if [ "${SSH_REQUIRE_WHITELIST:-false}" = "true" ]; then
        allow_public_ssh=false
        echo "SSH protection: public SSH disabled, only WHITELISTED_IPS/WHITELISTED_DOMAINS can access"
    fi

    if [ "$allow_public_ssh" = "true" ]; then
        iptables -A INPUT -p tcp -m multiport --dports "$SSH_PORT" -j ACCEPT
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        if [ -n "$SSH_DOCKER" ] && [ "$allow_public_ssh" = "true" ]; then
            iptables -I DOCKER-USER -p tcp -m multiport --dports "$SSH_DOCKER" -j ACCEPT
        fi
    fi
}
