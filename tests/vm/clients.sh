#!/bin/bash
# Disposable QEMU guest only. The Python harness repeats this guard.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MARKER=/run/l4d2-suite-vm.json
[[ -f "$MARKER" && "$(stat -c '%u:%a' "$MARKER")" == '0:600' ]] || {
    echo "REFUSED: missing root-owned mode-0600 QEMU guest marker $MARKER" >&2
    exit 2
}
[[ "$(id -u)" == 0 ]] || { echo 'REFUSED: run as root inside the disposable VM' >&2; exit 2; }
virt="$(systemd-detect-virt --vm 2>/dev/null || true)"
[[ "$virt" == qemu || "$virt" == kvm ]] || { echo "REFUSED: expected QEMU/KVM guest, detected '$virt'" >&2; exit 2; }
exec /usr/bin/python3 -I "$ROOT/tests/vm/clients.py"
