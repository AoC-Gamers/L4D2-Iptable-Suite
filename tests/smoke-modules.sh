#!/bin/bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

status=0

validate_module_contract() {
    local file="$1"
    local base
    base="$(basename "$file" .sh)"

    if ! grep -q "^${base}_metadata()" "$file"; then
        echo "ERROR: missing ${base}_metadata in $file"
        status=1
    fi
    if ! grep -q "^${base}_validate()" "$file"; then
        echo "ERROR: missing ${base}_validate in $file"
        status=1
    fi
    if ! grep -q "^${base}_apply()" "$file"; then
        echo "ERROR: missing ${base}_apply in $file"
        status=1
    fi
}

echo "INFO: validating module contract signatures"
while IFS= read -r module_file; do
    validate_module_contract "$module_file"
done < <(find modules/ip modules/nf -maxdepth 1 -type f -name "*.sh" | sort)

if [ "$status" -ne 0 ]; then
    echo "ERROR: module contract validation failed"
    exit "$status"
fi

echo "OK: module contract signatures look good"

if [ "$(id -u)" -eq 0 ]; then
    echo "INFO: running backend dry-runs as root"

    if command -v iptables >/dev/null 2>&1; then
        ./iptables.rules.sh --dry-run --verbose >/tmp/ip_dry_run.log 2>&1 || {
            echo "ERROR: iptables dry-run failed"
            cat /tmp/ip_dry_run.log
            exit 1
        }
        echo "OK: iptables dry-run passed"
    else
        echo "WARNING: iptables not installed, skipping iptables dry-run"
    fi

    if command -v nft >/dev/null 2>&1; then
        ./nftables.rules.sh --dry-run --verbose >/tmp/nf_dry_run.log 2>&1 || {
            echo "ERROR: nftables dry-run failed"
            cat /tmp/nf_dry_run.log
            exit 1
        }
        echo "OK: nftables dry-run passed"
    else
        echo "WARNING: nft not installed, skipping nftables dry-run"
    fi
else
    echo "WARNING: non-root run: skipping backend dry-run checks"
fi

echo "OK: smoke checks completed"
