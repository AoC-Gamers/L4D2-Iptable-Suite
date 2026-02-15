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

loader_should_run_module() {
    local module_id="$1"

    if [ "${#PRELOAD_ONLY_MODULES[@]:-0}" -gt 0 ]; then
        loader_array_contains "$module_id" "${PRELOAD_ONLY_MODULES[@]}" || return 1
    fi

    if [ "${#PRELOAD_SKIP_MODULES[@]:-0}" -gt 0 ]; then
        loader_array_contains "$module_id" "${PRELOAD_SKIP_MODULES[@]}" && return 1
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
    local metadata module_id required_vars defaults

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

        if ! loader_should_run_module "$module_id"; then
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
