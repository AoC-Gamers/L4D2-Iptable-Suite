#!/bin/bash
# Persistence and selective management use the same writer as both entrypoints.
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -eq 0 ]]; then
    cat <<'EOF'
Usage: ipp.sh [--backend iptables|nftables] OPERATION [options]
  status / doctor                  inspect registered policy and environment
  save                             save confirmed suite policy only
  load                             reload saved suite policy with timed rollback
  disable                          remove registered suite objects only
  apply --remove MODULES           recompose without modules
  apply --partial --only MODULES --set KEY=VALUE
  confirm --token TOKEN --admin-verified
  rollback
See docs/security/operations.md. Global firewall cleanup is not provided.
EOF
    exit 0
fi
exec /usr/bin/python3 -I "$script_dir/core/fw.py" "$@"
