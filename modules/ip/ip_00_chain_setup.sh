#!/bin/bash

ip_00_chain_setup_metadata() {
    cat << 'EOF'
ID=ip_chain_setup
DESCRIPTION=Sets up cleanup, base policies, and required chains for the iptables backend
REQUIRED_VARS=TYPECHAIN DOCKER_INPUT_COMPAT DOCKER_CHAIN_AUTORECOVER ENABLE_TCP_PROTECT
OPTIONAL_VARS=TCP_PROTECTION TCP_DOCKER
DEFAULTS=TYPECHAIN=0 DOCKER_INPUT_COMPAT=false DOCKER_CHAIN_AUTORECOVER=true ENABLE_TCP_PROTECT=true TCP_PROTECTION= TCP_DOCKER=
EOF
}

ip_00_chain_setup_validate() {
    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: ip_chain_setup: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac
}

ip_00_chain_setup_verify_docker_chains() {
    local iptables_rules
    iptables_rules="$(iptables-save 2>/dev/null || true)"
    grep -q '^:DOCKER-USER ' <<< "$iptables_rules" && grep -q '^:DOCKER-FORWARD ' <<< "$iptables_rules"
}

ip_00_chain_setup_recover_docker_chains_if_needed() {
    if [ "$TYPECHAIN" -eq 0 ] && [ "$DOCKER_INPUT_COMPAT" = "true" ]; then
        if ip_00_chain_setup_verify_docker_chains; then
            echo "OK: Docker chains detected: DOCKER-USER / DOCKER-FORWARD"
            return 0
        fi

        echo "WARNING: Docker chains missing: DOCKER-USER and/or DOCKER-FORWARD"

        if [ "$DOCKER_CHAIN_AUTORECOVER" = "true" ]; then
            echo "INFO: Attempting Docker chain auto-recovery (restart docker service)"
            if command -v systemctl >/dev/null 2>&1; then
                systemctl restart docker
            else
                service docker restart
            fi

            for _ in {1..15}; do
                if ip_00_chain_setup_verify_docker_chains; then
                    break
                fi
                sleep 1
            done

            if ! ip_00_chain_setup_verify_docker_chains && command -v docker >/dev/null 2>&1; then
                echo "INFO: Triggering Docker network init to force chain creation"
                local temp_net="iptables-autofix-$RANDOM"
                if docker network create "$temp_net" >/dev/null 2>&1; then
                    docker network rm "$temp_net" >/dev/null 2>&1 || true
                fi
            fi

            if ip_00_chain_setup_verify_docker_chains; then
                echo "OK: Docker chains recovered successfully"
            else
                echo "ERROR: Docker chains still missing after recovery attempt"
                echo "   Run manually: sudo systemctl restart docker"
            fi
        else
            echo "INFO: Auto-recovery disabled (DOCKER_CHAIN_AUTORECOVER=false)"
        fi
    fi
}

ip_00_chain_setup_apply() {
    DOCKER_COMPAT_INPUT_MODE=false
    if [ "$TYPECHAIN" -eq 0 ] && [ "$DOCKER_INPUT_COMPAT" = "true" ]; then
        DOCKER_COMPAT_INPUT_MODE=true
    fi
    export DOCKER_COMPAT_INPUT_MODE

    if [ "$DOCKER_COMPAT_INPUT_MODE" = "true" ]; then
        echo "INFO: Docker compatibility mode enabled for TYPECHAIN=0"
        iptables -P INPUT ACCEPT
        iptables -P OUTPUT ACCEPT
        iptables -F INPUT

        local chain
        for chain in UDP_GAME_NEW_LIMIT UDP_GAME_NEW_LIMIT_GLOBAL UDP_GAME_ESTABLISHED_LIMIT A2S_LIMITS A2S_PLAYERS_LIMITS A2S_RULES_LIMITS STEAM_GROUP_LIMITS l4d2loginfilter TCPfilter; do
            iptables -F "$chain" 2>/dev/null || true
            iptables -X "$chain" 2>/dev/null || true
        done
    else
        iptables -P INPUT ACCEPT
        iptables -P FORWARD ACCEPT
        iptables -P OUTPUT ACCEPT
        iptables -F
        iptables -X
        iptables -t nat -F
        iptables -t nat -X
        iptables -t mangle -F
        iptables -t mangle -X
    fi

    iptables -P INPUT DROP
    if [ "$DOCKER_COMPAT_INPUT_MODE" != "true" ]; then
        iptables -P FORWARD DROP
    fi
    iptables -P OUTPUT ACCEPT

    iptables -N UDP_GAME_NEW_LIMIT 2>/dev/null || true
    iptables -N UDP_GAME_NEW_LIMIT_GLOBAL 2>/dev/null || true
    iptables -N UDP_GAME_ESTABLISHED_LIMIT 2>/dev/null || true
    iptables -N A2S_LIMITS 2>/dev/null || true
    iptables -N A2S_PLAYERS_LIMITS 2>/dev/null || true
    iptables -N A2S_RULES_LIMITS 2>/dev/null || true
    iptables -N STEAM_GROUP_LIMITS 2>/dev/null || true
    iptables -N l4d2loginfilter 2>/dev/null || true

    if [ "$ENABLE_TCP_PROTECT" = "true" ] || [ -n "$TCP_PROTECTION" ] || [ -n "$TCP_DOCKER" ]; then
        iptables -N TCPfilter 2>/dev/null || true
    fi

    if [ "$TYPECHAIN" -eq 1 ] || [ "$TYPECHAIN" -eq 2 ]; then
        iptables -N DOCKER-USER 2>/dev/null || true
        service docker restart
    fi

    ip_00_chain_setup_recover_docker_chains_if_needed
}
