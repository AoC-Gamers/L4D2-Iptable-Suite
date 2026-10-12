#!/bin/bash

loader_get_meta() {
    local search_key="$1"
    local metadata="$2"
    local line key value

    while IFS= read -r line; do
        [ -z "$line" ] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ "$line" != *=* ]] && continue

        key="${line%%=*}"
        value="${line#*=}"

        if [ "$key" = "$search_key" ]; then
            echo "$value"
            return 0
        fi
    done <<< "$metadata"

    return 1
}

loader_array_contains() {
    local needle="$1"
    shift
    local item
    for item in "$@"; do
        if [ "$item" = "$needle" ]; then
            return 0
        fi
    done
    return 1
}

loader_id_matches() {
    local module_id="$1"
    local module_aliases="$2"
    local candidate="$3"

    if [ "$candidate" = "$module_id" ]; then
        return 0
    fi

    local alias
    for alias in $module_aliases; do
        if [ "$candidate" = "$alias" ]; then
            return 0
        fi
    done

    return 1
}

loader_should_run_module() {
    local module_id="$1"
    local module_aliases="${2:-}"
    local only_count=0
    local skip_count=0

    if declare -p PRELOAD_ONLY_MODULES >/dev/null 2>&1; then
        only_count="${#PRELOAD_ONLY_MODULES[@]}"
    fi

    if declare -p PRELOAD_SKIP_MODULES >/dev/null 2>&1; then
        skip_count="${#PRELOAD_SKIP_MODULES[@]}"
    fi

    if [ "$only_count" -gt 0 ]; then
        local only_match=false
        local wanted
        for wanted in "${PRELOAD_ONLY_MODULES[@]}"; do
            if loader_id_matches "$module_id" "$module_aliases" "$wanted"; then
                only_match=true
                break
            fi
        done
        [ "$only_match" = "true" ] || return 1
    fi

    if [ "$skip_count" -gt 0 ]; then
        local skipped
        for skipped in "${PRELOAD_SKIP_MODULES[@]}"; do
            if loader_id_matches "$module_id" "$module_aliases" "$skipped"; then
                return 1
            fi
        done
    fi

    return 0
}

loader_apply_defaults() {
    local defaults="$1"
    local pair key value

    for pair in $defaults; do
        [[ "$pair" != *=* ]] && continue
        key="${pair%%=*}"
        value="${pair#*=}"

        if [ -z "${!key:-}" ]; then
            export "$key=$value"
        fi
    done
}

loader_assert_required() {
    local module_id="$1"
    local required_vars="$2"
    local key

    for key in $required_vars; do
        if [ -z "${!key:-}" ]; then
            echo "ERROR: Module '$module_id' requires variable '$key' (missing after CLI/.env/default merge)"
            return 2
        fi
    done

    return 0
}

discover_target_modules() {
    local target_prefix="$1"
    local modules_dir="$2"

    local search_dirs=()
    search_dirs+=("$modules_dir")

    if [ -n "${MODULES_ROOT_DIR:-}" ] && [ "$MODULES_ROOT_DIR" != "$modules_dir" ]; then
        search_dirs+=("$MODULES_ROOT_DIR")
    fi

    find "${search_dirs[@]}" -maxdepth 1 -type f -name "${target_prefix}_*.sh" \
        | sort -u \
        | awk -F/ '
            {
                fname=$NF
                pr=500
                if (fname ~ /_chain_setup\.sh$/) {
                    pr=0
                } else if (fname ~ /_finalize\.sh$/) {
                    pr=999
                }
                printf "%03d|%s|%s\n", pr, fname, $0
            }
        ' \
        | sort -t'|' -k1,1n -k2,2 \
        | cut -d'|' -f3-
}

run_target_modules() {
    echo "ERROR: direct modular application retired; use core/fw.py via the entrypoints" >&2
    return 2
}
