#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
marker=/run/l4d2-suite-vm.json
[[ "$(id -u)" == 0 ]] || { echo 'Run as root inside the disposable QEMU guest' >&2; exit 2; }
[[ -f "$marker" && ! -L "$marker" ]] || { echo 'Missing regular disposable-VM marker' >&2; exit 2; }
[[ "$(stat -c '%u:%a' "$marker")" == '0:600' ]] || { echo 'VM marker must be root-owned mode 0600' >&2; exit 2; }
[[ "$(systemd-detect-virt --vm)" == qemu || "$(systemd-detect-virt --vm)" == kvm ]] || {
    echo 'Expected to run inside a QEMU/KVM guest' >&2; exit 2;
}
python3 - "$marker" <<'PY'
import json, pathlib, sys
if json.loads(pathlib.Path(sys.argv[1]).read_text()) != {'virtualization': 'qemu', 'disposable': True}:
    raise SystemExit('VM marker does not attest a disposable QEMU guest')
PY

L4S_VM_PARENT_NETNS="$(readlink /proc/self/ns/net)"
export L4S_VM_PARENT_NETNS
L4S_VM_PARENT_RUN="$(stat -Lc '%d:%i' /run)"
export L4S_VM_PARENT_RUN
# The child bash intentionally expands these variables after entering the namespaces.
# shellcheck disable=SC2016
unshare --net --mount --fork bash -c '
    set -euo pipefail
    mount --make-rprivate /
    mount -t tmpfs -o mode=755,nosuid,nodev tmpfs /run
    mkdir -p /run/user/0
    chmod 0700 /run/user/0
    printf %s "{\"virtualization\":\"qemu\",\"disposable\":true}" > /run/l4d2-suite-vm.json
    chown 0:0 /run/l4d2-suite-vm.json
    chmod 0600 /run/l4d2-suite-vm.json
    [[ "$(readlink /proc/self/ns/net)" != "$L4S_VM_PARENT_NETNS" ]] || exit 99
    [[ "$(stat -Lc "%d:%i" /run)" != "$L4S_VM_PARENT_RUN" ]] || exit 98
    ip link set lo up
    exec python3 "$1/docker.py" "${@:2}"
' _ "$script_dir" "$@"
