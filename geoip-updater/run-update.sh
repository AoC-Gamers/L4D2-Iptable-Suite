#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/workspace}"
ENV_FILE="${ENV_FILE:-$WORKSPACE_ROOT/.env}"
DOWNLOAD_DIR="${DOWNLOAD_DIR:-/tmp/maxmind}"
GEOIPUPDATE_ACCOUNT_ID="${GEOIPUPDATE_ACCOUNT_ID:-${MAXMIND_ACCOUNT_ID:-}}"
GEOIPUPDATE_LICENSE_KEY="${GEOIPUPDATE_LICENSE_KEY:-${MAXMIND_LICENSE_KEY:-}}"
GEOIPUPDATE_EDITION_IDS="${GEOIPUPDATE_EDITION_IDS:-${MAXMIND_EDITION_ID:-GeoLite2-Country-CSV}}"
MAXMIND_DOWNLOAD_URL="${MAXMIND_DOWNLOAD_URL:-}"
KEEP_ARCHIVE="${KEEP_ARCHIVE:-false}"

pick_csv_edition() {
    local editions="$1"
    local item trimmed

    for item in $editions; do
        trimmed="$item"
        trimmed="${trimmed//,/}"
        [ -z "$trimmed" ] && continue
        case "$trimmed" in
            GeoLite2-Country-CSV|GeoIP2-Country-CSV)
                echo "$trimmed"
                return 0
                ;;
        esac
    done

    return 1
}

CSV_EDITION_ID="$(pick_csv_edition "$GEOIPUPDATE_EDITION_IDS" || true)"
if [ -z "$CSV_EDITION_ID" ]; then
    CSV_EDITION_ID="GeoLite2-Country-CSV"
fi

if [ -z "$GEOIPUPDATE_LICENSE_KEY" ] && [ -z "$MAXMIND_DOWNLOAD_URL" ]; then
    echo "ERROR: Set GEOIPUPDATE_LICENSE_KEY or MAXMIND_DOWNLOAD_URL in geoip-updater/.env" >&2
    exit 2
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Env file not found: $ENV_FILE" >&2
    exit 2
fi

mkdir -p "$DOWNLOAD_DIR"
archive_path="$DOWNLOAD_DIR/${CSV_EDITION_ID}.zip"

if [ -z "$MAXMIND_DOWNLOAD_URL" ]; then
    MAXMIND_DOWNLOAD_URL="https://download.maxmind.com/app/geoip_download?edition_id=${CSV_EDITION_ID}&license_key=${GEOIPUPDATE_LICENSE_KEY}&suffix=zip"
fi

echo "INFO: Downloading MaxMind archive"
if [ -n "$GEOIPUPDATE_ACCOUNT_ID" ]; then
    echo "INFO: Using MaxMind account ID: $GEOIPUPDATE_ACCOUNT_ID"
fi
echo "INFO: CSV edition selected: $CSV_EDITION_ID"
curl -fsSL "$MAXMIND_DOWNLOAD_URL" -o "$archive_path"

echo "INFO: Generating country prefix files from archive"
bash "$WORKSPACE_ROOT/scripts/geoip/update_geo_country_sets.sh" --env-file "$ENV_FILE" --csv-zip "$archive_path"

if [ "$KEEP_ARCHIVE" != "true" ]; then
    rm -f "$archive_path"
fi

echo "OK: GeoIP country prefix files updated"