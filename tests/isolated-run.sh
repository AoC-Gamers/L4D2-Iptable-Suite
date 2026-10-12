#!/bin/bash
# Creates a disposable user+network namespace. Never enters the host network.
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for dependency in unshare mount nft iptables ip6tables ip iptables-restore python3; do
    command -v "$dependency" >/dev/null || { echo "Required dependency missing: $dependency" >&2; exit 1; }
done
namespace_args=(--user --map-root-user --net --mount --fork)
if [[ "${1:-}" == --root-net ]]; then
    [[ "$(id -u)" == 0 ]] || { echo '--root-net requires root in a disposable container/VM' >&2; exit 1; }
    namespace_args=(--net --mount --fork)
    shift
fi
test_script="${1:-tests/integration.py}"
case "$test_script" in tests/integration.py|tests/check-engine.py|tests/transaction-flows.py|tests/policy-flows.py|tests/docker-topology-flows.py) ;; *) exit 2 ;; esac
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
mkdir "$staging/repo"
git -c safe.directory="$project_root" -C "$project_root" ls-files -z | while IFS= read -r -d '' file; do
    [[ "$file" == reports/* || "$file" == .env ]] && continue
    mkdir -p "$staging/repo/$(dirname "$file")"
    cp "$project_root/$file" "$staging/repo/$file"
done
# Include the new files before their first commit as well.
cp -r "$project_root/core" "$staging/repo/"
cp -r "$project_root/tests" "$staging/repo/"
chmod -R go-w "$staging"
SUITE_HOST_NETNS="$(readlink /proc/self/ns/net)"
SUITE_HOST_RUN="$(stat -Lc '%d:%i' /run)"
export SUITE_HOST_NETNS SUITE_HOST_RUN
# shellcheck disable=SC2016 # expansion intentionally happens inside namespace
unshare "${namespace_args[@]}" bash -c '
    set -euo pipefail
    [[ "$(readlink /proc/self/ns/net)" != "$SUITE_HOST_NETNS" ]] || exit 99
    # Net namespaces still share filesystem locks. Keep xtables.lock private too.
    mount -t tmpfs -o mode=755 tmpfs /run
    [[ "$(stat -Lc "%d:%i" /run)" != "$SUITE_HOST_RUN" ]] || exit 98
    ip link set lo up
    cd "$1/repo"
    export SUITE_TEST_STATE="$1/state"
    exec python3 -I "$2"
' _ "$staging" "$test_script"
