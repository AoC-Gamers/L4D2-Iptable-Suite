#!/bin/bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$project_root"

# shellcheck source=../modules/nf/nf_45_http_https_protect.sh
. "$project_root/modules/nf/nf_45_http_https_protect.sh"

declare -a captured_rules=()

nf_add_rule() {
    captured_rules+=("$*")
}

TYPECHAIN=2
HTTP_HTTPS_PORTS="80,443"
HTTP_HTTPS_RATE="240/min"
HTTP_HTTPS_BURST=480
LOG_PREFIX_HTTP_HTTPS_ABUSE="HTTP_HTTPS_ABUSE:"

nf_45_http_https_protect_validate
nf_45_http_https_protect_apply

if [ "${#captured_rules[@]}" -ne 6 ]; then
    printf 'ERROR: expected 6 rules, got %s\n' "${#captured_rules[@]}" >&2
    exit 1
fi

assert_rule() {
    local expected="$1"
    local actual="$2"

    if [ "$actual" != "$expected" ]; then
        printf 'ERROR: unexpected rule\nexpected: %s\nactual:   %s\n' "$expected" "$actual" >&2
        exit 1
    fi
}

assert_rule \
    'input_web tcp dport { 80,443 } ct state new meter http_https_input_web_under { ip saddr . tcp dport limit rate 240/minute burst 480 packets } accept' \
    "${captured_rules[0]}"
assert_rule \
    'input_web tcp dport { 80,443 } ct state new meter http_https_input_web_over_log { ip saddr . tcp dport limit rate over 30/minute burst 10 packets } log prefix "HTTP_HTTPS_ABUSE: "' \
    "${captured_rules[1]}"
assert_rule \
    'input_web tcp dport { 80,443 } ct state new drop' \
    "${captured_rules[2]}"
assert_rule \
    'forward_web ct original proto-dst { 80,443 } ct state new meter http_https_forward_web_under { ip saddr . ct original proto-dst limit rate 240/minute burst 480 packets } accept' \
    "${captured_rules[3]}"
assert_rule \
    'forward_web ct original proto-dst { 80,443 } ct state new meter http_https_forward_web_over_log { ip saddr . ct original proto-dst limit rate over 30/minute burst 10 packets } log prefix "HTTP_HTTPS_ABUSE: "' \
    "${captured_rules[4]}"
assert_rule \
    'forward_web ct original proto-dst { 80,443 } ct state new drop' \
    "${captured_rules[5]}"

for rule in "${captured_rules[@]}"; do
    if [[ "$rule" == *' ct state new limit rate '* ]]; then
        printf 'ERROR: found a global HTTP/HTTPS limiter: %s\n' "$rule" >&2
        exit 1
    fi
done

if [[ "${captured_rules[3]}" == 'forward_web tcp dport '* ]]; then
    printf 'ERROR: forwarded traffic must match the pre-DNAT destination port\n' >&2
    exit 1
fi

printf 'OK: HTTP/HTTPS limits are scoped by source IP and destination port\n'
