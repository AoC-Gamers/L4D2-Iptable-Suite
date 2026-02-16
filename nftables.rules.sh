#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root or with sudo."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
MODULES_ROOT_DIR="${MODULES_ROOT_DIR:-$PROJECT_ROOT/modules}"
MODULES_NF_DIR="${MODULES_NF_DIR:-$MODULES_ROOT_DIR/nf}"

# Preserve effective paths before preload/env merge so empty values in .env
# cannot break module discovery.
REQUESTED_MODULES_ROOT_DIR="$MODULES_ROOT_DIR"
REQUESTED_MODULES_NF_DIR="$MODULES_NF_DIR"

if [ ! -f "$MODULES_ROOT_DIR/common_loader.sh" ] || [ ! -f "$MODULES_ROOT_DIR/preload.sh" ] || [ ! -f "$MODULES_ROOT_DIR/postload.sh" ]; then
    echo "ERROR: Missing loader files in $MODULES_ROOT_DIR"
    exit 1
fi

# shellcheck disable=SC1090
. "$MODULES_ROOT_DIR/common_loader.sh"
# shellcheck disable=SC1090
. "$MODULES_ROOT_DIR/preload.sh"
# shellcheck disable=SC1090
. "$MODULES_ROOT_DIR/postload.sh"

if [ ! -d "$MODULES_NF_DIR" ]; then
    echo "ERROR: Missing nf modules directory: $MODULES_NF_DIR"
    exit 1
fi

run_preload "nftables" "$@"

if [ -z "${MODULES_ROOT_DIR:-}" ]; then
    MODULES_ROOT_DIR="$REQUESTED_MODULES_ROOT_DIR"
fi

if [ -z "${MODULES_NF_DIR:-}" ]; then
    MODULES_NF_DIR="$REQUESTED_MODULES_NF_DIR"
fi

if [ ! -d "$MODULES_NF_DIR" ]; then
    echo "ERROR: Missing nf modules directory after preload: $MODULES_NF_DIR"
    exit 1
fi

run_target_modules "nf" "$MODULES_NF_DIR"
run_postload "nftables"
