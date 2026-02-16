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

    find "$modules_dir" -maxdepth 1 -type f -name "${target_prefix}_*.sh" \
        | sort
}

run_target_modules() {
    local target_prefix="$1"
    local modules_dir="$2"

    declare -ga EXECUTED_MODULES
    declare -ga SKIPPED_MODULES
    EXECUTED_MODULES=()
    SKIPPED_MODULES=()

    mapfile -t module_files < <(discover_target_modules "$target_prefix" "$modules_dir")

    if [ "${#module_files[@]}" -eq 0 ]; then
        echo "INFO: No modules found for prefix '${target_prefix}_' in $modules_dir"
        return 0
    fi

    local module_file module_name fn_meta fn_validate fn_apply
    local metadata module_id module_aliases required_vars defaults

    for module_file in "${module_files[@]}"; do
        # shellcheck disable=SC1090
        . "$module_file"

        module_name="$(basename "$module_file" .sh)"
        fn_meta="${module_name}_metadata"
        fn_validate="${module_name}_validate"
        fn_apply="${module_name}_apply"

        if ! declare -F "$fn_meta" >/dev/null 2>&1; then
            echo "ERROR: Module '$module_name' does not implement '$fn_meta'"
            return 1
        fi

        metadata="$($fn_meta)"
        module_id="$(loader_get_meta "ID" "$metadata" || true)"
        [ -z "$module_id" ] && module_id="$module_name"

        module_aliases="$(loader_get_meta "ALIASES" "$metadata" || true)"

        if ! loader_should_run_module "$module_id" "$module_aliases"; then
            [ "${PRELOAD_VERBOSE:-false}" = "true" ] && echo "⏭️  Skipping module: $module_id"
            SKIPPED_MODULES+=("$module_id")
            continue
        fi

        required_vars="$(loader_get_meta "REQUIRED_VARS" "$metadata" || true)"
        defaults="$(loader_get_meta "DEFAULTS" "$metadata" || true)"

        loader_apply_defaults "$defaults"
        loader_assert_required "$module_id" "$required_vars" || return $?

        if declare -F "$fn_validate" >/dev/null 2>&1; then
            "$fn_validate"
        fi

        if [ "${PRELOAD_DRY_RUN:-false}" = "true" ]; then
            echo "DRY-RUN: [dry-run] Module validated: $module_id"
        else
            if ! declare -F "$fn_apply" >/dev/null 2>&1; then
                echo "ERROR: Module '$module_name' does not implement '$fn_apply'"
                return 1
            fi
            "$fn_apply"
            echo "OK: Module applied: $module_id"
        fi

        EXECUTED_MODULES+=("$module_id")
    done

    return 0
}
