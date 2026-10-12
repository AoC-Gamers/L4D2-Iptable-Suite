#!/bin/bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
python3 -I tests/test_core.py
python3 -I tests/test_geoip.py
bash tests/http-https-protect.sh
for backend in iptables nftables; do
    "./$backend.rules.sh" validate --env-file tests/empty.conf --profile web
done
printf 'Logical/unit/generation checks passed. Kernel and traffic checks require tests/isolated-run.sh.\n'
