#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
CSV_ZIP=""
CSV_DIR=""

usage() {
    cat <<EOF
Usage: $0 [--env-file PATH] [--csv-zip PATH | --csv-dir PATH]

Reads GEO_POLICY_ALLOWED_COUNTRIES / GEO_POLICY_DENIED_COUNTRIES from the env file,
then generates per-country IPv4 prefix files under GEO_POLICY_DATA_DIR.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --csv-zip)
            CSV_ZIP="$2"
            shift 2
            ;;
        --csv-dir)
            CSV_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ -z "$CSV_ZIP" ] && [ -z "$CSV_DIR" ]; then
    echo "ERROR: You must pass --csv-zip or --csv-dir" >&2
    exit 2
fi

set -a
. "$ENV_FILE"
set +a

normalize_csv() {
    local raw="$1"
    raw="${raw//;/,}"
    raw="${raw// /}"
    raw="${raw^^}"
    while [[ "$raw" == *",,"* ]]; do
        raw="${raw//,,/,}"
    done
    raw="${raw#,}"
    raw="${raw%,}"
    echo "$raw"
}

merge_country_lists() {
    local allow_csv deny_csv item out=""
    declare -A seen=()

    allow_csv="$(normalize_csv "${GEO_POLICY_ALLOWED_COUNTRIES:-}")"
    deny_csv="$(normalize_csv "${GEO_POLICY_DENIED_COUNTRIES:-}")"

    IFS=',' read -r -a _items <<< "$allow_csv,$deny_csv"
    for item in "${_items[@]}"; do
        [ -z "$item" ] && continue
        if [ -z "${seen[$item]:-}" ]; then
            seen[$item]=1
            if [ -n "$out" ]; then
                out+=","
            fi
            out+="$item"
        fi
    done

    echo "$out"
}

COUNTRIES="$(merge_country_lists)"
if [ -z "$COUNTRIES" ]; then
    echo "INFO: No GEO_POLICY_ALLOWED_COUNTRIES / GEO_POLICY_DENIED_COUNTRIES defined" >&2
    exit 0
fi

OUTPUT_DIR="$PROJECT_ROOT/${GEO_POLICY_DATA_DIR#./}"
mkdir -p "$OUTPUT_DIR"

cmd=(python3 "$PROJECT_ROOT/scripts/geoip/build_geo_country_sets.py" --output-dir "$OUTPUT_DIR" --countries "$COUNTRIES")
if [ -n "$CSV_ZIP" ]; then
    cmd+=(--csv-zip "$CSV_ZIP")
fi
if [ -n "$CSV_DIR" ]; then
    cmd+=(--csv-dir "$CSV_DIR")
fi

"${cmd[@]}"