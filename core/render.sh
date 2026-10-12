#!/bin/bash
# Trusted selected module code runs here; engine commands only record a candidate.
set -euo pipefail
nft() {
    if [[ "${1:-}" == list || "${1:-}" == -a ]]; then return 1; fi
    python3 "$PROJECT_ROOT/core/record.py" nft "$@"
}
iptables() {
    if [[ "${1:-}" == -S || " $* " == *' -C '* ]]; then return 1; fi
    python3 "$PROJECT_ROOT/core/record.py" iptables "$@"
}
systemctl() { echo 'Services cannot be controlled by modules' >&2; return 1; }
service() { systemctl "$@"; }
docker() { echo 'Docker cannot be controlled by modules' >&2; return 1; }
for module in "$@"; do
    # shellcheck disable=SC1090
    . "$module"
done
for module in "$@"; do
    name="$(basename "$module" .sh)"
    "${name}_validate"
done
if [[ "$SUITE_PHASE" == generate ]]; then
    for module in "$@"; do
        name="$(basename "$module" .sh)"
        "${name}_apply"
    done
fi
