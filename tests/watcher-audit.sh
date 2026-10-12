#!/bin/bash
# Deterministically race two watcher runs against a changing saved IP.
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_root="$(mktemp -d)"
pid_a=""
pid_b=""
cleanup() {
    for pid in "$pid_a" "$pid_b"; do
        [[ -n "$pid" ]] || continue
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
    rm -rf "$test_root"
}
trap cleanup EXIT
mkdir -p "$test_root/bin" "$test_root/state" "$test_root/run"
printf '1.1.1.1\n' > "$test_root/state/current-ip"

cat > "$test_root/bin/curl" <<'EOF'
#!/bin/sh
printf '8.8.8.8\n'
EOF
cat > "$test_root/bin/dig" <<'EOF'
#!/bin/sh
printf '8.8.8.8\n'
EOF
cat > "$test_root/bin/flock" <<'EOF'
#!/bin/bash
if [[ "${WATCHER_TAG:-}" == A ]]; then
    : > "$A_READY"
    while [[ ! -e "$RELEASE_A" ]]; do sleep 0.01; done
fi
exec /usr/bin/flock "$@"
EOF
cat > "$test_root/bin/firewall" <<'EOF'
#!/bin/sh
printf 'firewall %s\n' "$*" >> "$ACTION_LOG"
EOF
cat > "$test_root/bin/hook" <<'EOF'
#!/bin/sh
printf 'hook %s %s\n' "$1" "$2" >> "$ACTION_LOG"
EOF
chmod +x "$test_root/bin/"*

common_env=(
    PUBLIC_IP_WATCH_CONFIG="$test_root/missing.conf"
    CURL_BIN="$test_root/bin/curl"
    DIG_BIN="$test_root/bin/dig"
    FLOCK_BIN="$test_root/bin/flock"
    FIREWALL_SCRIPT="$test_root/bin/firewall"
    EXTERNAL_ADMIN_VERIFIER="$test_root/bin/firewall"
    POST_CHANGE_HOOK="$test_root/bin/hook"
    DDNS_HOSTNAME=games.example.test
    DDNS_NAMESERVERS='ns1.example.test ns2.example.test'
    DDNS_MIN_MATCHES=2
    REQUIRE_DDNS_MATCH=true
    STATE_FILE="$test_root/state/current-ip"
    LOCK_FILE="$test_root/run/watch.lock"
    ACTION_LOG="$test_root/actions"
    A_READY="$test_root/a-ready"
    RELEASE_A="$test_root/release-a"
)

env "${common_env[@]}" WATCHER_TAG=A "$project_root/scripts/network/public-ip-watch.sh" > "$test_root/a.log" 2>&1 &
pid_a=$!
for _ in $(seq 1 500); do
    [[ -e "$test_root/a-ready" ]] && break
    sleep 0.01
done
[[ -e "$test_root/a-ready" ]] || { echo 'first watcher did not reach lock barrier' >&2; exit 1; }

env "${common_env[@]}" WATCHER_TAG=B "$project_root/scripts/network/public-ip-watch.sh" > "$test_root/b.log" 2>&1 &
pid_b=$!
wait "$pid_b"
pid_b=""
touch "$test_root/release-a"
wait "$pid_a"
pid_a=""

hook_count="$(grep -c '^hook ' "$test_root/actions" || true)"
[[ "$hook_count" == 1 ]] || {
    cat "$test_root/actions" >&2
    echo "Expected exactly one post-change hook, got $hook_count" >&2
    exit 1
}
dry_run_count="$(grep -c '^firewall --dry-run$' "$test_root/actions" || true)"
reload_count="$(grep -c '^firewall --verify-with ' "$test_root/actions" || true)"
[[ "$dry_run_count" == 1 && "$reload_count" == 1 ]] || {
    cat "$test_root/actions" >&2
    echo "Expected one candidate check and one reload, got $dry_run_count checks and $reload_count reloads" >&2
    exit 1
}
[[ "$(cat "$test_root/state/current-ip")" == 8.8.8.8 ]]
echo 'WATCHER RACE PASS: one reload and one hook for concurrent change'
