#!/bin/bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
for backend in iptables nftables; do
    for profile in host-minimal web games vpn-gateway; do
        family=dual
        if [[ "$backend" == iptables && "$profile" == games ]]; then family=ipv4-block-ipv6; fi
        "./$backend.rules.sh" generate --env-file tests/empty.conf --profile "$profile" --set "FAMILY_POLICY=$family" > /dev/null
        printf 'GENERATION PASS %s %s\n' "$backend" "$profile"
    done
done
