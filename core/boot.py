"""Explicit boot protection, kernel-backed readiness and bounded recovery access.

The early nftables barrier is independent of the selected policy engine and of
Docker's chains. Its ownership is separate from ordinary transaction snapshots.
"""
import hashlib
import json
import secrets
from pathlib import Path

from . import engine
from .config import BOOT_GUARD_TABLE, require, trusted, network, interface, ports

TABLE = BOOT_GUARD_TABLE


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def clean_kernel(value):
    if isinstance(value, dict):
        dynamic = 'dynamic' in value.get('flags', [])
        return {k: clean_kernel(v) for k, v in value.items()
                if k not in ('handle', 'packets', 'bytes', 'expires', 'metainfo')
                and not (dynamic and k in ('elem', 'elements'))}
    if isinstance(value, list):
        return [clean_kernel(v) for v in value if not (isinstance(v, dict) and 'metainfo' in v)]
    return value


def fingerprint(policy, live=None):
    live = live or engine.inspect(policy['backend'], policy['config'].get('IPTABLES_FRONTEND', 'auto'))
    engine.require_owned_present(policy, live)
    if policy['backend'] == 'nftables':
        objects = []
        for obj in policy['objects']:
            raw = engine.command(['nft', '-j', '-s', 'list', 'table', obj['family'], obj['name']]).stdout
            objects.append(clean_kernel(json.loads(raw)))
        return digest(objects)
    result = {}
    for family, tables in policy['families'].items():
        parsed = engine.parse_save(live['iprules'][family])
        result[family] = {}
        for table, chains in tables.items():
            rules = parsed[table]['rules']
            result[family][table] = {chain: [r[2:] for r in rules if r[1] == chain] for chain in chains}
            for t, parent, target in policy.get('hooks', []):
                if t == table and target in chains:
                    actual = [r for r in rules if r[1] == parent]
                    require(actual and actual[0] == engine.hook_rule(parent, target),
                            f'Readiness: IPv{family} {table}/{parent} hook missing or displaced')
    return digest(result)


def invalidate(store):
    store.delete('installed')


def record_installed(store, policy):
    if policy.get('disabled'):
        invalidate(store)
        return
    live = engine.inspect(policy['backend'], policy['config'].get('IPTABLES_FRONTEND', 'auto'))
    engine.preflight(policy, policy, live)
    value = {'schema': 1, 'boot_id': boot_id(), 'policy_digest': digest(policy),
             'objects_digest': fingerprint(policy, live), 'backend': policy['backend']}
    store.put('installed', value)


def guard_present():
    result = engine.command(['nft', '-j', 'list', 'tables'])
    return any(x.get('table', {}).get('family') == 'inet' and x.get('table', {}).get('name') == TABLE
               for x in json.loads(result.stdout)['nftables'])


def verify(store, allow_guard=False):
    require(not store.get('pending'), 'Readiness: an unconfirmed transaction is pending')
    policy = store.get('current')
    installed = store.get('installed')
    require(policy and installed, 'Readiness: no verified installed policy for this boot')
    require(installed.get('boot_id') == boot_id(), 'Readiness: installation belongs to another boot')
    require(installed.get('policy_digest') == digest(policy), 'Readiness: policy digest differs from installed version')
    live = engine.inspect(policy['backend'], policy['config'].get('IPTABLES_FRONTEND', 'auto'))
    engine.preflight(policy, policy, live)
    require(installed.get('objects_digest') == fingerprint(policy, live), 'Readiness: managed kernel rules changed')
    require(allow_guard or not guard_present(), 'Readiness: early barrier is still active')
    return {'ready': True, 'boot_id': boot_id(), 'policy_digest': digest(policy), 'backend': policy['backend']}


def recovery_rows(path, policy):
    trusted(path)
    rows = json.loads(Path(path).read_text())
    require(isinstance(rows, list) and 1 <= len(rows) <= 32, 'Boot recovery requires 1..32 scoped SSH grants')
    require(policy['config']['HOST_SERVICES'] == 'true' and any(x.endswith('_tcp_ssh') for x in policy['selected']),
            'Boot recovery requires selected host SSH; container-only setups must use console recovery')
    ssh_ports = ports(policy['config']['SSH_PORT'])
    for row in rows:
        require(isinstance(row, dict) and set(row) == {'source', 'destination', 'input', 'ports'}
                and all(isinstance(v, str) for v in row.values()), 'Invalid boot recovery grant fields')
        source, destination = network(row['source']), network(row['destination'])
        require(source.version == destination.version and source.prefixlen > 0
                and destination.num_addresses == 1, 'Recovery needs scoped source and one destination of the same family')
        interface(row['input'])
        require(all(any(c <= a <= b <= d for c, d in ssh_ports) for a, b in ports(row['ports'])),
                'Recovery ports must be a subset of configured host SSH ports')
    return rows


def guard_text(policy, rows, owner):
    lines = [f'add table inet {TABLE} {{ comment "l4d2-suite:boot:{owner}"; }}',
             f'add chain inet {TABLE} input {{ type filter hook input priority -310; policy accept; }}',
             f'add chain inet {TABLE} forward {{ type filter hook forward priority -310; policy accept; }}']
    def rule(chain, text):
        lines.append(f'add rule inet {TABLE} {chain} {text}')
    rule('input', 'iifname "lo" counter accept')
    rule('input', 'ct state invalid counter drop')
    rule('input', 'icmp type { destination-unreachable, time-exceeded, parameter-problem } counter accept')
    rule('input', 'icmpv6 type { destination-unreachable, packet-too-big, time-exceeded, parameter-problem } counter accept')
    rule('input', 'ip6 hoplimit 255 icmpv6 type { nd-router-solicit, nd-router-advert, nd-neighbor-solicit, nd-neighbor-advert } counter accept')
    # Replies to connections initiated by this host do not expose listeners.
    rule('input', 'ct direction reply ct state established,related counter accept')
    for row in rows:
        family = 'ip' if network(row['source']).version == 4 else 'ip6'
        portset = '{ ' + row['ports'].replace(':', '-') + ' }'
        rule('input', f'iifname "{row["input"]}" {family} saddr {row["source"]} {family} daddr {row["destination"]} tcp dport {portset} counter accept')
    # The suite owns host input policy, including a closed host-only core.
    rule('input', 'counter drop')
    if policy['config']['FAMILY_POLICY'] == 'ipv4-block-ipv6':
        rule('forward', 'meta nfproto ipv6 counter drop')
    if policy['config']['ROUTED_POLICY'] == 'drop':
        rule('forward', 'counter drop')
    else:
        # Match the exact container zones the full compiler restricts, including
        # direct routed access, established flows and live-restored containers.
        for zone in sorted({g['output'] for g in policy['access']['containers']}):
            rule('forward', f'iifname "{zone}" counter drop')
            rule('forward', f'oifname "{zone}" counter drop')
    return '\n'.join(lines) + '\n'


def prepare(store, recovery_file):
    require(not store.get('pending'), 'Boot prepare requires no pending transaction')
    policy = store.get('current')
    persisted = store.get('persisted')
    require(policy and persisted and digest(policy) == digest(persisted), 'Boot prepare requires saved confirmed current policy')
    require(not guard_present(), 'Disarm the existing boot barrier explicitly before changing its scope')
    verify(store)
    rows = recovery_rows(recovery_file, policy) if recovery_file else []
    owner = secrets.token_hex(16)
    text = guard_text(policy, rows, owner)
    engine.command(['nft', '-c', '-f', '-'], text)
    store.put('boot-policy', {'schema': 1, 'owner': owner, 'policy_digest': digest(policy),
                              'text': text, 'text_digest': digest(text), 'recovery': rows})
    return {'prepared': True, 'policy_digest': digest(policy), 'recovery_grants': len(rows)}


def require_scope(store, policy):
    value = store.get('boot-policy')
    if not value:
        return
    value = manifest(store)
    require(not policy.get('disabled'), 'Boot protection is configured; disarm explicitly from console before disabling')
    require(guard_text(policy, value['recovery'], value['owner']) == value['text'],
            'Boot scope changed; disarm, review and prepare boot protection explicitly from console')
    if value['recovery']:
        ssh = ports(policy['config'].get('SSH_PORT', '22'))
        require(policy['config']['HOST_SERVICES'] == 'true'
                and any(x.endswith('_tcp_ssh') for x in policy['selected'])
                and all(any(c <= a <= b <= d for c, d in ssh)
                        for row in value['recovery'] for a, b in ports(row['ports'])),
                'Boot recovery SSH scope changed; explicitly prepare the new recovery route')


def saved(store, policy):
    value = store.get('boot-policy')
    if value:
        require_scope(store, policy)
        value['policy_digest'] = digest(policy)
        store.put('boot-policy', value)


def manifest(store):
    value = store.get('boot-policy')
    require(value and value.get('schema') == 1 and value.get('text_digest') == digest(value.get('text')),
            'Boot barrier manifest missing, corrupt or unsupported; protected units must remain stopped')
    require(isinstance(value.get('owner'), str) and len(value['owner']) == 32,
            'Invalid boot barrier ownership record')
    return value


def require_guard_owned(value):
    raw = json.loads(engine.command(['nft', '-j', 'list', 'table', 'inet', TABLE]).stdout)
    tables = [x['table'] for x in raw['nftables'] if 'table' in x]
    require(len(tables) == 1 and tables[0].get('comment') == 'l4d2-suite:boot:' + value['owner'],
            'Boot barrier table is not registered to this suite; refusing adoption or deletion')


def guard(store):
    value = manifest(store)
    invalidate(store)
    text = value['text']
    if guard_present():
        require_guard_owned(value)
        text = f'delete table inet {TABLE}\n' + text
    engine.command(['nft', '-c', '-f', '-'], text)
    engine.command(['nft', '-f', '-'], text)
    return {'barrier': True, 'boot_id': boot_id()}


def release(store):
    value = manifest(store)
    verify(store, allow_guard=True)
    require(guard_present(), 'Cannot release a missing boot barrier')
    require_guard_owned(value)
    engine.command(['nft', '-f', '-'], f'delete table inet {TABLE}\n')
    return verify(store)


def restore(store):
    # Keep this object out of Store snapshots: rollback to empty must not remove
    # boot protection. Re-arm it even when restoration previously succeeded.
    guard(store)
    store.rollback_locked(expired_only=True)
    policy = store.get('persisted')
    require(policy, 'Boot restore: required persisted policy is missing')
    require(digest(policy) == manifest(store)['policy_digest'], 'Boot restore: persisted policy differs from prepared scope; prepare explicitly')
    store.apply_locked(policy, local=True)
    return release(store)


def disarm(store):
    require(not store.get('pending'), 'Cannot disarm boot protection with a pending transaction')
    value = manifest(store)
    if guard_present():
        require_guard_owned(value)
        engine.command(['nft', '-f', '-'], f'delete table inet {TABLE}\n')
    store.delete('boot-policy')
    invalidate(store)
    return {'disarmed': True, 'ready': False}
