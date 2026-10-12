"""Explicit, fingerprinted handover of one exclusively owned inet filter table.

Inventory is passive. A manifest is operator approval, never ownership discovery.
The snapshot and application still use the ordinary writer/journal/watchdog.
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


def inventory(name):
    name = table_name(name)
    raw = json.loads(engine.command(['nft', '-j', '-s', 'list', 'table', 'inet', name]).stdout)
    tables = [item['table'] for item in raw['nftables'] if 'table' in item]
    require(len(tables) == 1 and tables[0].get('name') == name and
            tables[0].get('family') == 'inet', 'Unexpected legacy table inventory')
    handle = tables[0].get('handle')
    require(type(handle) is int and handle > 0, 'Legacy table handle unavailable')
    for item in raw['nftables']:
        if 'chain' in item and 'hook' in item['chain']:
            chain = item['chain']
            require(chain.get('type') == 'filter' and chain['hook'] in ('input', 'forward', 'output'),
                    'Legacy handover supports only an inet filter table')
    return {'schema': 1, 'family': 'inet', 'name': name, 'handle': handle,
            'sha256': boot.digest(boot.clean_kernel(raw))}


def load(path):
    path = trusted(Path(path))
    require(path.is_file() and path.stat().st_size <= 4096, 'Invalid legacy manifest file')
    manifest = json.loads(path.read_text())
    validate(manifest)
    return manifest


def validate(manifest):
    require(isinstance(manifest, dict) and set(manifest) ==
            {'schema', 'family', 'name', 'handle', 'sha256'}, 'Invalid legacy manifest fields')
    require(type(manifest['schema']) is int and manifest['schema'] == 1 and
            manifest['family'] == 'inet', 'Unsupported legacy manifest schema/family')
    table_name(manifest['name'])
    require(type(manifest['handle']) is int and manifest['handle'] > 0, 'Invalid legacy handle')
    require(isinstance(manifest['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', manifest['sha256']),
            'Invalid legacy fingerprint')


def verify(manifest):
    validate(manifest)
    require(inventory(manifest['name']) == manifest,
            'Legacy table changed since review; inventory and approve it again')


def prepare(candidate, previous, manifest, live):
    validate(manifest)
    require(previous is None, 'Legacy handover requires no current registered policy')
    require(candidate['backend'] == 'nftables' and not candidate.get('disabled'),
            'Legacy handover requires a complete nftables application')
    config = candidate['config']
    require(config.get('HOST_SERVICES') == 'true' and config.get('CONTAINER_POLICY') == 'off'
            and config.get('ROUTED_POLICY') == 'unmanaged',
            'Legacy handover currently supports host-only, unmanaged routing')
    objects = candidate.get('objects', [])
    require(len(objects) == 1 and objects[0]['family'] == 'inet' and
            objects[0]['name'] == manifest['name'],
            'Legacy handover must replace exactly the reviewed inet table; NAT unsupported')
    verify(manifest)
    snapshot = engine.snapshot({'backend': 'nftables', 'objects': objects}, live)
    verify(manifest)
    require(len(snapshot['objects']) == 1, 'Legacy rollback snapshot unavailable')
    # Check the actual rollback export before the first write, including dynamic sets.
    engine.check(engine.prepare(snapshot, [candidate], live))
    return snapshot


def pin_transaction(transactions, manifest):
    require(len(transactions) == 1 and transactions[0][0] == 'nft', 'Expected one nft transaction')
    old = 'delete table inet ' + manifest['name'] + '\n'
    text = transactions[0][1]
    require(text.startswith(old), 'Missing reviewed legacy deletion')
    # Recreating a same-name table after review must not cause deletion of that object.
    # nft 1.0.9/1.1.3 retains the old table's sets in its evaluation cache
    # after deletion by handle. Destroy by name clears that cache so a same-name
    # meter may change capacity/type. Both commands belong to ONE kernel batch;
    # a stale handle still fails the entire batch, preserving the live table.
    transactions[0] = ('nft', 'delete table inet handle ' + str(manifest['handle']) + '\n'
                       'destroy table inet ' + manifest['name'] + '\n' + text[len(old):])
