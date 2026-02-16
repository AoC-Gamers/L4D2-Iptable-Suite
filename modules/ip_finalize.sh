#!/bin/bash

ip_finalize_metadata() {
    cat << 'EOF'
ID=ip_finalize
DESCRIPTION=Applies final policies and prints a summary for the iptables backend
REQUIRED_VARS=TYPECHAIN DOCKER_INPUT_COMPAT ENABLE_TCP_PROTECT TVSERVERPORTS DOCKER_CHAIN_AUTORECOVER
OPTIONAL_VARS=
DEFAULTS=TYPECHAIN=0 DOCKER_INPUT_COMPAT=false ENABLE_TCP_PROTECT=true TVSERVERPORTS=27020 DOCKER_CHAIN_AUTORECOVER=true
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
    echo "   - SourceTV separated: Ports $TVSERVERPORTS"
    echo "   - TCP Protection: $ENABLE_TCP_PROTECT"
    echo "   - Chain type: $TYPECHAIN (0=INPUT, 1=DOCKER-USER, 2=BOTH)"
    echo "   - Docker INPUT compatibility: $DOCKER_INPUT_COMPAT"
    echo "   - Docker chain auto-recover: $DOCKER_CHAIN_AUTORECOVER"
}
