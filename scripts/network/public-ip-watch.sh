#!/bin/bash
set -Eeuo pipefail

PROGRAM_NAME="l4d2-public-ip-watch"
CONFIG_FILE="${PUBLIC_IP_WATCH_CONFIG:-/etc/default/l4d2-public-ip-watch}"

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_READER="$SCRIPT_ROOT/core/read_config.py"
if [[ ! -f "$CONFIG_READER" ]]; then
    CONFIG_READER=/opt/l4d2-firewall/core/read_config.py
fi
if [ -r "$CONFIG_FILE" ]; then
    config_values="$(mktemp)"
    trap 'rm -f "$config_values"' EXIT
    /usr/bin/python3 -I "$CONFIG_READER" "$CONFIG_FILE" --allowed NOIP_CHECK_URL,NOIP_USER_AGENT,HTTP_TIMEOUT_SECONDS,DDNS_HOSTNAME,DDNS_NAMESERVERS,DDNS_MIN_MATCHES,REQUIRE_DDNS_MATCH,FIREWALL_SCRIPT,FIREWALL_ENV_FILE,POST_CHANGE_HOOK,STATE_FILE,LOCK_FILE,EXTERNAL_ADMIN_VERIFIER > "$config_values"
    while IFS= read -r -d '' key && IFS= read -r -d '' value; do
        printf -v "$key" '%s' "$value"
    done < "$config_values"
    rm -f "$config_values"
    trap - EXIT
fi
EXTERNAL_ADMIN_VERIFIER="${EXTERNAL_ADMIN_VERIFIER:-}"

NOIP_CHECK_URL="${NOIP_CHECK_URL:-http://ip1.dynupdate.no-ip.com/}"
NOIP_USER_AGENT="${NOIP_USER_AGENT:-AoC-Gamers L4D2-Public-IP-Watch/1.0 admin@aoc-gamers.com}"
HTTP_TIMEOUT_SECONDS="${HTTP_TIMEOUT_SECONDS:-15}"
DDNS_HOSTNAME="${DDNS_HOSTNAME:-}"
DDNS_NAMESERVERS="${DDNS_NAMESERVERS:-ns1.no-ip.com ns2.no-ip.com ns3.no-ip.com ns4.no-ip.com}"
DDNS_MIN_MATCHES="${DDNS_MIN_MATCHES:-2}"
REQUIRE_DDNS_MATCH="${REQUIRE_DDNS_MATCH:-true}"
FIREWALL_SCRIPT="${FIREWALL_SCRIPT:-}"
FIREWALL_ENV_FILE="${FIREWALL_ENV_FILE:-}"
POST_CHANGE_HOOK="${POST_CHANGE_HOOK:-}"
STATE_FILE="${STATE_FILE:-/var/lib/l4d2-public-ip-watch/current-ip}"
LOCK_FILE="${LOCK_FILE:-/run/l4d2-public-ip-watch/watch.lock}"
CURL_BIN="${CURL_BIN:-/usr/bin/curl}"
DIG_BIN="${DIG_BIN:-/usr/bin/dig}"
FLOCK_BIN="${FLOCK_BIN:-/usr/bin/flock}"

MODE="run"
FORCE=false

log_message() {
    local level="$1"
    shift
    printf '%s %s[%s]: %s\n' "$(date -Is)" "$PROGRAM_NAME" "$level" "$*"
}

usage() {
    cat <<'EOF'
Usage: public-ip-watch.sh [--check|--dry-run|--force]

  --check    Query the public IP and authoritative DDNS only; change no state.
  --dry-run  Evaluate whether an action is needed, but do not reload or save.
  --force    Reload nftables even if the stored and observed IPs are equal.
EOF
}

is_ipv4() {
    local value="$1"
    local a b c d extra octet

    IFS=. read -r a b c d extra <<< "$value"
    [ -z "${extra:-}" ] || return 1

    for octet in "$a" "$b" "$c" "$d"; do
        [[ "$octet" =~ ^[0-9]{1,3}$ ]] || return 1
        [ "$((10#$octet))" -le 255 ] || return 1
    done
}

is_public_ipv4() {
    local value="$1"
    local a b c d

    is_ipv4 "$value" || return 1
    IFS=. read -r a b c d <<< "$value"
    a=$((10#$a)); b=$((10#$b)); c=$((10#$c)); d=$((10#$d))

    # Reject non-routable, shared, documentation, benchmark and multicast
    # ranges. The No-IP detector should never return one of these.
    [ "$a" -ne 0 ] || return 1
    [ "$a" -ne 10 ] || return 1
    [ "$a" -ne 127 ] || return 1
    [ "$a" -lt 224 ] || return 1
    ! { [ "$a" -eq 100 ] && [ "$b" -ge 64 ] && [ "$b" -le 127 ]; } || return 1
    ! { [ "$a" -eq 169 ] && [ "$b" -eq 254 ]; } || return 1
    ! { [ "$a" -eq 172 ] && [ "$b" -ge 16 ] && [ "$b" -le 31 ]; } || return 1
    ! { [ "$a" -eq 192 ] && [ "$b" -eq 168 ]; } || return 1
    ! { [ "$a" -eq 192 ] && [ "$b" -eq 0 ] && [ "$c" -eq 2 ]; } || return 1
    ! { [ "$a" -eq 198 ] && { [ "$b" -eq 18 ] || [ "$b" -eq 19 ]; }; } || return 1
    ! { [ "$a" -eq 198 ] && [ "$b" -eq 51 ] && [ "$c" -eq 100 ]; } || return 1
    ! { [ "$a" -eq 203 ] && [ "$b" -eq 0 ] && [ "$c" -eq 113 ]; } || return 1
}

discover_public_ip() {
    local response ip

    response="$($CURL_BIN -4fsS \
        --max-time "$HTTP_TIMEOUT_SECONDS" \
        --retry 1 \
        --user-agent "$NOIP_USER_AGENT" \
        "$NOIP_CHECK_URL")" || return 1

    ip="$(printf '%s' "$response" | tr -d '[:space:]')"
    is_public_ipv4 "$ip" || return 1
    printf '%s\n' "$ip"
}

verify_authoritative_ddns() {
    local public_ip="$1"
    local nameserver answer
    local queried=0
    local matches=0
    local -a observed=()

    [ -n "$DDNS_HOSTNAME" ] || {
        log_message ERROR "DDNS_HOSTNAME is required when REQUIRE_DDNS_MATCH=true"
        return 1
    }

    if ! [[ "$DDNS_MIN_MATCHES" =~ ^[1-9][0-9]*$ ]]; then
        log_message ERROR "DDNS_MIN_MATCHES must be a positive integer"
        return 1
    fi

    for nameserver in $DDNS_NAMESERVERS; do
        queried=$((queried + 1))
        while IFS= read -r answer; do
            [ -n "$answer" ] || continue
            is_public_ipv4 "$answer" || continue
            observed+=("$nameserver=$answer")
            if [ "$answer" = "$public_ip" ]; then
                matches=$((matches + 1))
                break
            fi
        done < <("$DIG_BIN" +time=3 +tries=1 +short A "$DDNS_HOSTNAME" "@$nameserver" 2>/dev/null || true)
    done

    if [ "$matches" -ge "$DDNS_MIN_MATCHES" ]; then
        log_message INFO "DDNS confirmed $DDNS_HOSTNAME=$public_ip by $matches/$queried authoritative servers"
        return 0
    fi

    log_message WARNING "DDNS not yet consistent with WAN IP $public_ip (matches=$matches/$queried; observed=${observed[*]:-none})"
    return 1
}

read_saved_ip() {
    local saved=""

    if [ -r "$STATE_FILE" ]; then
        IFS= read -r saved < "$STATE_FILE" || true
    fi

    if [ -n "$saved" ] && ! is_public_ipv4 "$saved"; then
        log_message WARNING "Ignoring invalid state in $STATE_FILE"
        saved=""
    fi

    printf '%s\n' "$saved"
}

write_saved_ip() {
    local value="$1"
    local state_dir temporary

    state_dir="$(dirname "$STATE_FILE")"
    mkdir -p "$state_dir"
    temporary="$(mktemp "$state_dir/.current-ip.XXXXXX")"
    printf '%s\n' "$value" > "$temporary"
    chmod 600 "$temporary"
    mv -f "$temporary" "$STATE_FILE"
}

run_firewall_reload() {
    local -a env_args=()

    [ -n "$FIREWALL_SCRIPT" ] || {
        log_message ERROR "FIREWALL_SCRIPT is not configured"
        return 1
    }
    [ -x "$FIREWALL_SCRIPT" ] || {
        log_message ERROR "Firewall script is not executable: $FIREWALL_SCRIPT"
        return 1
    }

    if [ -n "$FIREWALL_ENV_FILE" ]; then
        [ -r "$FIREWALL_ENV_FILE" ] || {
            log_message ERROR "Firewall environment file is not readable: $FIREWALL_ENV_FILE"
            return 1
        }
        env_args=(--env-file "$FIREWALL_ENV_FILE")
    fi

    if [[ -z "$EXTERNAL_ADMIN_VERIFIER" || ! -x "$EXTERNAL_ADMIN_VERIFIER" ]]; then
        log_message ERROR "Configure EXTERNAL_ADMIN_VERIFIER to test a NEW administrative connection from outside before unattended reload"
        return 1
    fi
    /usr/bin/python3 -I "$CONFIG_READER" "$FIREWALL_SCRIPT" --trusted-path
    /usr/bin/python3 -I "$CONFIG_READER" "$EXTERNAL_ADMIN_VERIFIER" --trusted-path
    log_message INFO "Generating and logically validating nftables candidate before reload"
    "$FIREWALL_SCRIPT" "${env_args[@]}" --dry-run

    log_message INFO "Reapplying nftables after confirmed public IP change"
    "$FIREWALL_SCRIPT" "${env_args[@]}" --verify-with "$EXTERNAL_ADMIN_VERIFIER"
}

run_post_change_hook() {
    local previous_ip="$1"
    local current_ip="$2"

    [ -n "$POST_CHANGE_HOOK" ] || return 0
    [ -x "$POST_CHANGE_HOOK" ] || {
        log_message ERROR "POST_CHANGE_HOOK is not executable: $POST_CHANGE_HOOK"
        return 1
    }

    /usr/bin/python3 -I "$CONFIG_READER" "$POST_CHANGE_HOOK" --trusted-path
    log_message INFO "Running post-change hook: $POST_CHANGE_HOOK"
    "$POST_CHANGE_HOOK" "$previous_ip" "$current_ip"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --check)
            MODE="check"
            ;;
        --dry-run)
            MODE="dry-run"
            ;;
        --force)
            FORCE=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
    shift
done

for required_bin in "$CURL_BIN" "$DIG_BIN" "$FLOCK_BIN"; do
    [ -x "$required_bin" ] || {
        log_message ERROR "Required executable not found: $required_bin"
        exit 1
    }
done

# Private root-owned parents make the following shell file operations safe from
# unprivileged symlink replacement. A shared sticky /tmp parent is insufficient.
if [[ "$EUID" == 0 && "$MODE" == run ]]; then
    for state_path in "$STATE_FILE" "$LOCK_FILE"; do
        mkdir -p "$(dirname "$state_path")"
        /usr/bin/python3 -I "$CONFIG_READER" "$(dirname "$state_path")" --trusted-path --private-directory
        if [[ -e "$state_path" || -L "$state_path" ]]; then
            /usr/bin/python3 -I "$CONFIG_READER" "$state_path" --trusted-path
        fi
    done
fi

current_ip="$(discover_public_ip)" || {
    log_message WARNING "Could not obtain a valid public IPv4 address from $NOIP_CHECK_URL; retrying on the next timer run"
    exit 0
}

if [ "$REQUIRE_DDNS_MATCH" = "true" ]; then
    verify_authoritative_ddns "$current_ip" || exit 0
elif [ "$REQUIRE_DDNS_MATCH" != "false" ]; then
    log_message ERROR "REQUIRE_DDNS_MATCH must be true or false"
    exit 1
fi

previous_ip="$(read_saved_ip)"

if [ "$MODE" = "check" ]; then
    log_message INFO "Check complete: public=$current_ip saved=${previous_ip:-unset}"
    exit 0
fi

lock_dir="$(dirname "$LOCK_FILE")"
mkdir -p "$lock_dir"
exec 9>"$LOCK_FILE"
if ! "$FLOCK_BIN" -n 9; then
    log_message INFO "Another instance is already running; skipping"
    exit 0
fi

if [ -z "$previous_ip" ] && [ "$FORCE" = "false" ]; then
    if [ "$MODE" = "dry-run" ]; then
        log_message INFO "Dry run: would initialize state with $current_ip without reloading nftables"
    else
        write_saved_ip "$current_ip"
        log_message INFO "Initialized public IP state with $current_ip; no reload required"
    fi
    exit 0
fi

if [ "$current_ip" = "$previous_ip" ] && [ "$FORCE" = "false" ]; then
    log_message INFO "Public IP unchanged at $current_ip"
    exit 0
fi

if [ "$MODE" = "dry-run" ]; then
    log_message INFO "Dry run: would process public IP change ${previous_ip:-unset} -> $current_ip"
    exit 0
fi

log_message NOTICE "Confirmed public IP change ${previous_ip:-unset} -> $current_ip"
run_firewall_reload
run_post_change_hook "${previous_ip:-}" "$current_ip"
write_saved_ip "$current_ip"
log_message NOTICE "Public IP change handled successfully; state updated to $current_ip"
