#!/bin/bash

run_preload() {
    local backend="$1"
    shift

    PRELOAD_BACKEND="$backend"
    PRELOAD_DRY_RUN=false
    PRELOAD_VERBOSE=false
    PRELOAD_ENV_FILE="${PRELOAD_ENV_FILE:-${PROJECT_ROOT:-.}/.env}"

    declare -gA CLI_SET_VARS
    declare -ga PRELOAD_ONLY_MODULES
    declare -ga PRELOAD_SKIP_MODULES
    declare -ga PRELOAD_EXTRA_ARGS
    CLI_SET_VARS=()
    PRELOAD_ONLY_MODULES=()
    PRELOAD_SKIP_MODULES=()
    PRELOAD_EXTRA_ARGS=()

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --env-file)
                if [ "$#" -lt 2 ]; then
                    echo "ERROR: Missing value for --env-file"
                    return 2
                fi
                PRELOAD_ENV_FILE="$2"
                shift 2
                ;;
            --set)
                if [ "$#" -lt 2 ]; then
                    echo "ERROR: Missing value for --set"
                    return 2
                fi
                if [[ "$2" != *=* ]]; then
                    echo "ERROR: Invalid --set format (expected KEY=VALUE): $2"
                    return 2
                fi
                local key="${2%%=*}"
                local value="${2#*=}"
                CLI_SET_VARS["$key"]="$value"
                shift 2
                ;;
            --only)
                if [ "$#" -lt 2 ]; then
                    echo "ERROR: Missing value for --only"
                    return 2
                fi
                PRELOAD_ONLY_MODULES+=("$2")
                shift 2
                ;;
            --skip)
                if [ "$#" -lt 2 ]; then
                    echo "ERROR: Missing value for --skip"
                    return 2
                fi
                PRELOAD_SKIP_MODULES+=("$2")
                shift 2
                ;;
            --dry-run)
                PRELOAD_DRY_RUN=true
                shift
                ;;
            --verbose)
                PRELOAD_VERBOSE=true
                shift
                ;;
            --legacy|--modular)
                shift
                ;;
            *)
                PRELOAD_EXTRA_ARGS+=("$1")
                shift
                ;;
        esac
    done

    if [ -f "$PRELOAD_ENV_FILE" ]; then
        set -a
        . "$PRELOAD_ENV_FILE"
        set +a
        [ "$PRELOAD_VERBOSE" = "true" ] && echo "INFO: Loaded env file: $PRELOAD_ENV_FILE"
    else
        echo "WARNING: Env file not found: $PRELOAD_ENV_FILE"
    fi

    local var_name
    for var_name in "${!CLI_SET_VARS[@]}"; do
        export "$var_name=${CLI_SET_VARS[$var_name]}"
    done

    [ "$PRELOAD_VERBOSE" = "true" ] && echo "INFO: Preload ready for backend: $backend"
    return 0
}
