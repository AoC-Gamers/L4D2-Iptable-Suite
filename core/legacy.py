"""Explicit, fingerprinted handover of exclusively owned nftables tables.

Schema 1 remains the original single inet filter inventory. Schema 2 adds an
explicitly reviewed inet filter table and up to seven ip/ip6 NAT tables.
Inventory is passive; a manifest is operator approval, never ownership
discovery. The snapshot and application still use the ordinary writer/journal/
watchdog.
"""
import json
from pathlib import Path
import re

from . import boot, engine
from .config import BOOT_GUARD_TABLE, require, trusted


def table_name(name):
    require(isinstance(name, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,30}', name),
            'Invalid legacy table name')
    require(name != BOOT_GUARD_TABLE, 'Cannot hand over the independent boot guard')
    return name


def _table_inventory(family, name):
    table_name(name)
    require(family in ('inet', 'ip', 'ip6'), 'Unsupported legacy table family')
    raw = json.loads(engine.command(['nft', '-j', '-s', 'list', 'table', family, name]).stdout)
    tables = [item['table'] for item in raw['nftables'] if 'table' in item]
    require(len(tables) == 1 and tables[0].get('name') == name and
            tables[0].get('family') == family, 'Unexpected legacy table inventory')
    handle = tables[0].get('handle')
    require(type(handle) is int and handle > 0, 'Legacy table handle unavailable')
    for item in raw['nftables']:
        if 'chain' not in item or 'hook' not in item['chain']:
            continue
        chain = item['chain']
        if family == 'inet':
            valid = chain.get('type') == 'filter' and chain['hook'] in ('input', 'forward', 'output')
        else:
            valid = chain.get('type') == 'nat' and chain['hook'] in ('prerouting', 'postrouting')
        require(valid, 'Legacy handover supports only an inet filter or ip/ip6 NAT hooks')
    return {'family': family, 'name': name, 'handle': handle,
            'sha256': boot.digest(boot.clean_kernel(raw))}


def inventory(name, nat_tables=None):
    """Inventory one inet filter table and optionally reviewed IPv4/IPv6 NAT tables."""
    nat_tables = [] if nat_tables is None else list(nat_tables)
    require(len(nat_tables) <= 7, 'Legacy inventory supports at most eight tables')
    inet = _table_inventory('inet', name)
    seen = {('inet', name)}
    entries = [inet]
    for family, nat_name in nat_tables:
        require(family in ('ip', 'ip6'), 'Legacy NAT table family must be ip or ip6')
        nat_name = table_name(nat_name)
        key = (family, nat_name)
        require(key not in seen, 'Duplicate legacy table')
        seen.add(key)
        entries.append(_table_inventory(family, nat_name))
    if not nat_tables:
        # Keep schema 1 byte-for-byte compatible with existing inventory files.
        return {'schema': 1, **inet}
    return {'schema': 2, 'tables': entries}


def load(path):
    path = trusted(Path(path))
    require(path.is_file() and path.stat().st_size <= 16384, 'Invalid legacy manifest file')
    manifest = json.loads(path.read_text())
    validate(manifest)
    return manifest


def _validate_entry(entry, families):
    require(isinstance(entry, dict) and set(entry) == {'family', 'name', 'handle', 'sha256'},
            'Invalid legacy table entry')
    require(entry['family'] in families, 'Invalid legacy table family')
    table_name(entry['name'])
    require(type(entry['handle']) is int and entry['handle'] > 0, 'Invalid legacy handle')
    require(isinstance(entry['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', entry['sha256']),
            'Invalid legacy fingerprint')


def tables(manifest):
    """Return normalized reviewed table entries for either manifest schema."""
    validate(manifest)
    if manifest['schema'] == 1:
        return [{'family': 'inet', 'name': manifest['name'], 'handle': manifest['handle'],
                 'sha256': manifest['sha256']}]
    return manifest['tables']


def owned_keys(manifest):
    return tuple((entry['family'], entry['name']) for entry in tables(manifest))


def validate(manifest):
    require(isinstance(manifest, dict), 'Invalid legacy manifest fields')
    if type(manifest.get('schema')) is int and manifest['schema'] == 1:
        require(set(manifest) == {'schema', 'family', 'name', 'handle', 'sha256'},
                'Invalid legacy manifest fields')
        require(manifest['family'] == 'inet', 'Unsupported legacy manifest schema/family')
        table_name(manifest['name'])
        require(type(manifest['handle']) is int and manifest['handle'] > 0, 'Invalid legacy handle')
        require(isinstance(manifest['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', manifest['sha256']),
                'Invalid legacy fingerprint')
        return
    require(type(manifest.get('schema')) is int and manifest['schema'] == 2 and
            set(manifest) == {'schema', 'tables'}, 'Unsupported legacy manifest schema/family')
    entries = manifest['tables']
    require(isinstance(entries, list) and 2 <= len(entries) <= 8,
            'Schema 2 requires an inet table and at most seven NAT tables')
    for index, entry in enumerate(entries):
        _validate_entry(entry, ('inet',) if index == 0 else ('ip', 'ip6'))
    require(entries[0]['family'] == 'inet', 'Schema 2 must explicitly review one inet filter table')
    keys = [(entry['family'], entry['name']) for entry in entries]
    require(len(set(keys)) == len(keys), 'Duplicate legacy table')


def verify(manifest):
    validate(manifest)
    if manifest['schema'] == 1:
        current = inventory(manifest['name'])
    else:
        inet = tables(manifest)[0]
        nat = [(entry['family'], entry['name']) for entry in tables(manifest)[1:]]
        current = inventory(inet['name'], nat)
    require(current == manifest, 'Legacy table changed since review; inventory and approve it again')


def prepare(candidate, previous, manifest, live):
    validate(manifest)
    require(previous is None, 'Legacy handover requires no current registered policy')
    require(candidate['backend'] == 'nftables' and not candidate.get('disabled'),
            'Legacy handover requires a complete nftables application')
    config = candidate['config']
    require(config.get('HOST_SERVICES') == 'true' and
            config.get('CONTAINER_POLICY') in ('off', 'ingress') and
            config.get('ROUTED_POLICY') == 'unmanaged',
            'Legacy handover supports host services, off/ingress containers and unmanaged routing')
    objects = candidate.get('objects', [])
    inet = tables(manifest)[0]
    require(sum(obj.get('family') == 'inet' for obj in objects) == 1 and
            any(obj.get('family') == 'inet' and obj.get('name') == inet['name'] for obj in objects),
            'Legacy handover must replace exactly the reviewed inet filter table')
    if manifest['schema'] == 1:
        require(len(objects) == 1, 'Legacy handover requires schema 2 for additional NAT objects')
    else:
        require(all(obj.get('family') in ('inet', 'ip', 'ip6') for obj in objects),
                'Legacy handover candidate contains an unsupported table family')
    verify(manifest)
    # Snapshot every explicitly reviewed table, including legacy NAT names that
    # differ from the candidate compiler's suite-owned NAT names.
    prior = {'backend': 'nftables', 'objects': [
        {'family': entry['family'], 'name': entry['name']} for entry in tables(manifest)]}
    snapshot = engine.snapshot(prior, live)
    verify(manifest)
    require(len(snapshot['objects']) == len(tables(manifest)), 'Legacy rollback snapshot unavailable')
    engine.check(engine.prepare(snapshot, [candidate, snapshot], live))
    return snapshot


def pin_transaction(transactions, manifest):
    """Pin reviewed-table deletion by handle in the single candidate batch."""
    validate(manifest)
    require(len(transactions) == 1 and transactions[0][0] == 'nft', 'Expected one nft transaction')
    text = transactions[0][1]
    entries = tables(manifest)
    names = {f"delete table {entry['family']} {entry['name']}" for entry in entries}
    lines = text.splitlines()
    require(names <= set(lines), 'Missing reviewed legacy deletion')
    lines = [line for line in lines if line not in names]
    pinned = []
    for entry in entries:
        pinned.extend((f"delete table {entry['family']} handle {entry['handle']}",
                       f"destroy table {entry['family']} {entry['name']}"))
    transactions[0] = ('nft', '\n'.join([*pinned, *lines]) + '\n')
