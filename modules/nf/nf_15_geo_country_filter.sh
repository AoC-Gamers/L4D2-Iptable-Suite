#!/bin/bash

# shellcheck disable=SC1090
. "${PROJECT_ROOT:-.}/modules/common_nft.sh"

nf_15_geo_country_filter_metadata() {
    cat << 'EOF'
ID=nf_geo_country_filter
ALIASES=geo_country_filter geo_filter
DESCRIPTION=Applies IPv4 geo allow/deny policy for L4D2 UDP ports in the nftables backend
REQUIRED_VARS=TYPECHAIN L4D2_GAMESERVER_UDP_PORTS L4D2_SOURCETV_UDP_PORTS GEO_POLICY_MODE GEO_POLICY_DATA_DIR GEO_POLICY_MANUAL_ALLOW_FILE GEO_POLICY_MANUAL_DENY_FILE
OPTIONAL_VARS=GEO_POLICY_ALLOWED_COUNTRIES GEO_POLICY_DENIED_COUNTRIES
DEFAULTS=TYPECHAIN=0 L4D2_GAMESERVER_UDP_PORTS=27015 L4D2_SOURCETV_UDP_PORTS=27020 GEO_POLICY_MODE=off GEO_POLICY_ALLOWED_COUNTRIES=CL,AR,PE,CO,MX,BO,US GEO_POLICY_DENIED_COUNTRIES= GEO_POLICY_DATA_DIR=./geoip/generated/countries GEO_POLICY_MANUAL_ALLOW_FILE=./geoip/manual/allow_ipv4.txt GEO_POLICY_MANUAL_DENY_FILE=./geoip/manual/deny_ipv4.txt
EOF
}

nf_15_geo_country_filter_resolve_path() {
    local path="$1"

    if [ -z "$path" ]; then
        echo ""
        return 0
    fi

    case "$path" in
        /*) echo "$path" ;;
        *) echo "${PROJECT_ROOT:-.}/${path#./}" ;;
    esac
}

nf_15_geo_country_filter_normalize_country_csv() {
    local raw="$1"
    local item trimmed out=""

    raw="${raw//;/,}"
    IFS=',' read -r -a _geo_items <<< "$raw"
    for item in "${_geo_items[@]}"; do
        trimmed="$item"
        trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [ -z "$trimmed" ] && continue
        trimmed="${trimmed^^}"
        if [ -n "$out" ]; then
            out+=","
        fi
        out+="$trimmed"
    done

    echo "$out"
}

nf_15_geo_country_filter_has_entries() {
    local file="$1"

    [ -f "$file" ] || return 1

    awk '
        /^[[:space:]]*#/ {next}
        /^[[:space:]]*$/ {next}
        {found=1; exit}
        END {exit(found ? 0 : 1)}
    ' "$file"
}

nf_15_geo_country_filter_validate_country_csv() {
    local label="$1"
    local value="$2"

    [ -z "$value" ] && return 0
    if ! [[ "$value" =~ ^[A-Z]{2}(,[A-Z]{2})*$ ]]; then
        echo "ERROR: nf_geo_country_filter: $label must be ISO country codes separated by commas"
        return 2
    fi
}

nf_15_geo_country_filter_validate_country_files() {
    local label="$1"
    local countries_csv="$2"
    local data_dir="$3"
    local code

    [ -z "$countries_csv" ] && return 0

    IFS=',' read -r -a _geo_codes <<< "$countries_csv"
    for code in "${_geo_codes[@]}"; do
        [ -f "$data_dir/${code}.ipv4.txt" ] && continue
        echo "ERROR: nf_geo_country_filter: missing country file for $label code '$code' at $data_dir/${code}.ipv4.txt"
        return 2
    done
}

nf_15_geo_country_filter_validate() {
    local mode allow_csv deny_csv data_dir allow_file

    case "${TYPECHAIN:-}" in
        0|1|2) ;;
        *)
            echo "ERROR: nf_geo_country_filter: TYPECHAIN must be 0, 1 or 2"
            return 2
            ;;
    esac

    nf_validate_ports_spec "$L4D2_GAMESERVER_UDP_PORTS" "nf_geo_country_filter: L4D2_GAMESERVER_UDP_PORTS" || return $?
    nf_validate_ports_spec "$L4D2_SOURCETV_UDP_PORTS" "nf_geo_country_filter: L4D2_SOURCETV_UDP_PORTS" || return $?

    mode="${GEO_POLICY_MODE,,}"
    case "$mode" in
        off|allowlist|denylist) ;;
        *)
            echo "ERROR: nf_geo_country_filter: GEO_POLICY_MODE must be off, allowlist or denylist"
            return 2
            ;;
    esac

    [ "$mode" = "off" ] && return 0

    allow_csv="$(nf_15_geo_country_filter_normalize_country_csv "${GEO_POLICY_ALLOWED_COUNTRIES:-}")"
    deny_csv="$(nf_15_geo_country_filter_normalize_country_csv "${GEO_POLICY_DENIED_COUNTRIES:-}")"
    data_dir="$(nf_15_geo_country_filter_resolve_path "${GEO_POLICY_DATA_DIR:-}")"
    allow_file="$(nf_15_geo_country_filter_resolve_path "${GEO_POLICY_MANUAL_ALLOW_FILE:-}")"

    nf_15_geo_country_filter_validate_country_csv "GEO_POLICY_ALLOWED_COUNTRIES" "$allow_csv" || return $?
    nf_15_geo_country_filter_validate_country_csv "GEO_POLICY_DENIED_COUNTRIES" "$deny_csv" || return $?

    if [ -n "$allow_csv" ] || [ -n "$deny_csv" ]; then
        if [ ! -d "$data_dir" ]; then
            echo "ERROR: nf_geo_country_filter: GEO_POLICY_DATA_DIR does not exist: $data_dir"
            return 2
        fi
    fi

    nf_15_geo_country_filter_validate_country_files "allowlist" "$allow_csv" "$data_dir" || return $?
    nf_15_geo_country_filter_validate_country_files "denylist" "$deny_csv" "$data_dir" || return $?

    if [ "$mode" = "allowlist" ] && [ -z "$allow_csv" ] && ! nf_15_geo_country_filter_has_entries "$allow_file"; then
        echo "ERROR: nf_geo_country_filter: allowlist mode requires GEO_POLICY_ALLOWED_COUNTRIES and/or entries in GEO_POLICY_MANUAL_ALLOW_FILE"
        return 2
    fi
}

nf_15_geo_country_filter_create_set_from_files() {
    local set_name="$1"
    shift

    local tmp_file entry_count=0 file cidr
    tmp_file="$(mktemp)"

    {
        echo "add set $NF_TABLE_FAMILY $NF_TABLE_NAME $set_name { type ipv4_addr; flags interval; }"
        for file in "$@"; do
            [ -f "$file" ] || continue
            while IFS= read -r cidr; do
                cidr="${cidr%%#*}"
                cidr="${cidr#"${cidr%%[![:space:]]*}"}"
                cidr="${cidr%"${cidr##*[![:space:]]}"}"
                [ -z "$cidr" ] && continue
                echo "add element $NF_TABLE_FAMILY $NF_TABLE_NAME $set_name { $cidr }"
                entry_count=$((entry_count + 1))
            done < "$file"
        done
    } > "$tmp_file"

    if [ "$entry_count" -eq 0 ]; then
        rm -f "$tmp_file"
        return 1
    fi

    nft -f "$tmp_file"
    rm -f "$tmp_file"
    return 0
}

nf_15_geo_country_filter_apply() {
    local mode data_dir allow_file deny_file
    local all_ports_expr chain code file
    local gate_chain="geo_country_gate_v4"
    local manual_allow_set="geo_manual_allow_v4"
    local manual_deny_set="geo_manual_deny_v4"
    local country_allow_set="geo_country_allow_v4"
    local country_deny_set="geo_country_deny_v4"
    local manual_allow_loaded=false
    local manual_deny_loaded=false
    local country_allow_loaded=false
    local country_deny_loaded=false
    local -a allow_country_files=()
    local -a deny_country_files=()

    mode="${GEO_POLICY_MODE,,}"
    if [ "$mode" = "off" ]; then
        echo "INFO: nf_geo_country_filter: GEO_POLICY_MODE=off; geo filter disabled"
        return 0
    fi

    data_dir="$(nf_15_geo_country_filter_resolve_path "$GEO_POLICY_DATA_DIR")"
    allow_file="$(nf_15_geo_country_filter_resolve_path "$GEO_POLICY_MANUAL_ALLOW_FILE")"
    deny_file="$(nf_15_geo_country_filter_resolve_path "$GEO_POLICY_MANUAL_DENY_FILE")"

    IFS=',' read -r -a _allow_codes <<< "$(nf_15_geo_country_filter_normalize_country_csv "${GEO_POLICY_ALLOWED_COUNTRIES:-}")"
    for code in "${_allow_codes[@]}"; do
        [ -z "$code" ] && continue
        file="$data_dir/${code}.ipv4.txt"
        [ -f "$file" ] && allow_country_files+=("$file")
    done

    IFS=',' read -r -a _deny_codes <<< "$(nf_15_geo_country_filter_normalize_country_csv "${GEO_POLICY_DENIED_COUNTRIES:-}")"
    for code in "${_deny_codes[@]}"; do
        [ -z "$code" ] && continue
        file="$data_dir/${code}.ipv4.txt"
        [ -f "$file" ] && deny_country_files+=("$file")
    done

    if nf_15_geo_country_filter_create_set_from_files "$manual_deny_set" "$deny_file"; then
        manual_deny_loaded=true
    fi

    if nf_15_geo_country_filter_create_set_from_files "$manual_allow_set" "$allow_file"; then
        manual_allow_loaded=true
    fi

    if [ "${#deny_country_files[@]}" -gt 0 ] && nf_15_geo_country_filter_create_set_from_files "$country_deny_set" "${deny_country_files[@]}"; then
        country_deny_loaded=true
    fi

    if [ "${#allow_country_files[@]}" -gt 0 ] && nf_15_geo_country_filter_create_set_from_files "$country_allow_set" "${allow_country_files[@]}"; then
        country_allow_loaded=true
    fi

    nf_add_chain "$gate_chain"

    if [ "$manual_deny_loaded" = "true" ]; then
        nf_add_rule "$gate_chain" ip saddr "@$manual_deny_set" drop
    fi

    if [ "$manual_allow_loaded" = "true" ]; then
        nf_add_rule "$gate_chain" ip saddr "@$manual_allow_set" return
    fi

    if [ "$mode" = "denylist" ]; then
        if [ "$country_deny_loaded" = "true" ]; then
            nf_add_rule "$gate_chain" ip saddr "@$country_deny_set" drop
        fi
        nf_add_rule "$gate_chain" return
    else
        if [ "$country_allow_loaded" = "true" ]; then
            nf_add_rule "$gate_chain" ip saddr "@$country_allow_set" return
        fi
        nf_add_rule "$gate_chain" drop
    fi

    all_ports_expr="{ $(nf_ports_normalize "$L4D2_GAMESERVER_UDP_PORTS"), $(nf_ports_normalize "$L4D2_SOURCETV_UDP_PORTS") }"
    for chain in $(nf_get_target_chains_for_domain l4d2_udp); do
        nf_add_rule "$chain" meta nfproto ipv4 udp dport "$all_ports_expr" jump "$gate_chain"
    done

    echo "INFO: nf_geo_country_filter: applied mode=$mode manual_allow=$manual_allow_loaded manual_deny=$manual_deny_loaded country_allow=$country_allow_loaded country_deny=$country_deny_loaded"
}