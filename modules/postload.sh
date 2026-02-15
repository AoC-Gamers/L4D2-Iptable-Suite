#!/bin/bash

run_postload() {
    local backend="$1"

    local executed_count=0
    local skipped_count=0
    if declare -p EXECUTED_MODULES >/dev/null 2>&1 && [ "${#EXECUTED_MODULES[@]}" -gt 0 ]; then
        executed_count="${#EXECUTED_MODULES[@]}"
    fi
    if declare -p SKIPPED_MODULES >/dev/null 2>&1 && [ "${#SKIPPED_MODULES[@]}" -gt 0 ]; then
        skipped_count="${#SKIPPED_MODULES[@]}"
    fi

    echo "OK: Modular execution finished"
    echo "   - Backend: $backend"
    echo "   - Dry-run: ${PRELOAD_DRY_RUN:-false}"
    echo "   - Modules executed: $executed_count"
    echo "   - Modules skipped: $skipped_count"

    if declare -p EXECUTED_MODULES >/dev/null 2>&1 && [ "${#EXECUTED_MODULES[@]}" -gt 0 ]; then
        echo "   - Module list: ${EXECUTED_MODULES[*]}"
    fi
    if declare -p SKIPPED_MODULES >/dev/null 2>&1 && [ "${#SKIPPED_MODULES[@]}" -gt 0 ]; then
        echo "   - Skipped list: ${SKIPPED_MODULES[*]}"
    fi
}
