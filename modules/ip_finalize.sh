#!/bin/bash

ip_finalize_metadata() {
    cat << 'EOF'
ID=ip_finalize
ALIASES=finalize
DESCRIPTION=Applies final policies and prints a summary for the iptables backend
REQUIRED_VARS=TYPECHAIN DOCKER_INPUT_COMPAT DOCKER_CHAIN_AUTORECOVER
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 DOCKER_INPUT_COMPAT=false DOCKER_CHAIN_AUTORECOVER=true
EOF
}

ip_finalize_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_finalize: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac
}

ip_finalize_apply() {
    iptables -A INPUT -j DROP
    if [ "${DOCKER_INPUT_COMPAT:-false}" != "true" ]; then
        iptables -A FORWARD -j DROP
    fi
    iptables -A OUTPUT -j ACCEPT

    if declare -F ip_chain_setup_recover_docker_chains_if_needed >/dev/null 2>&1; then
        ip_chain_setup_recover_docker_chains_if_needed
    fi

    echo "OK: iptables rules applied successfully"
    if [ -n "${L4D2_SOURCETV_UDP_PORTS:-}" ]; then
        echo "   - SourceTV separated: Ports $L4D2_SOURCETV_UDP_PORTS"
    fi
    if [ -n "${L4D2_GAMESERVER_TCP_PORTS:-}" ]; then
        echo "   - TCP Protection reference ports: $L4D2_GAMESERVER_TCP_PORTS"
    fi
    echo "   - Chain type: $TYPECHAIN (0=INPUT, 1=DOCKER-USER, 2=BOTH)"
    echo "   - Docker INPUT compatibility: $DOCKER_INPUT_COMPAT"
    echo "   - Docker chain auto-recover: $DOCKER_CHAIN_AUTORECOVER"
}
