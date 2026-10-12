#!/usr/bin/python3
"""Guest-only systemd rollback after an explicit legacy handover and SSH exit."""
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from transactions import safe_guest, store, require_ssh_connection, timer_state

TABLE = 'suite_legacy_vm'
RECORD = 'vm-legacy-handover'


def main(phase):
    safe_guest()  # Must precede every kernel or production-state operation.
    from core import engine, legacy
    from core.config import Configuration, require
    from core.compiler import generate
    s = store()
    with s.lock():
        if phase == 'arm':
            require(not any(s.get(key) for key in ('current', 'pending', 'persisted', 'boot-policy', RECORD)),
                    'Legacy test requires empty guest suite state')
            require(('inet', TABLE) not in engine.inspect('nftables')['tables'], 'Legacy fixture already exists')
            connection = require_ssh_connection()
            require(connection[0] == '10.0.2.2', 'Unexpected QEMU SSH client')
            engine.command(['nft', '-f', '-'], f'''table inet {TABLE} {{
 chain input {{ type filter hook input priority 0; policy drop;
  iifname "lo" accept
  ct state established,related accept
  ip saddr 10.0.2.2 tcp dport 22 accept
  tcp dport 64001 counter accept
 }}
}}
''')
            manifest = legacy.inventory(TABLE)
            candidate = generate(Configuration('nftables', profiles=['host-minimal'], overrides={
                'NF_TABLE_NAME': TABLE, 'ROUTED_POLICY': 'unmanaged',
                'SSH_PORT': '22', 'ADMIN_SOURCES': '10.0.2.2/32'}, privileged=True))
            token = s.apply_locked(candidate, timeout=30, legacy_manifest=manifest)
            timer_state(token)
            s.put(RECORD, {'manifest': manifest, 'token': token, 'connection': connection})
        elif phase == 'probe':
            record = s.get(RECORD)
            require(record and require_ssh_connection() != record['connection'],
                    'A fresh authenticated SSH connection is required')
            require(s.get('pending') and s.get('pending')['token'] == record['token'],
                    'Expected a still-pending legacy handover')
            timer_state(record['token'])
            require(legacy.inventory(TABLE)['sha256'] != record['manifest']['sha256'],
                    'Candidate was not installed')
        elif phase == 'verify':
            record = s.get(RECORD)
            require(record, 'Missing guest legacy test record')
        else:
            raise RuntimeError('Unknown legacy test phase')
    if phase == 'verify':
        deadline = time.monotonic() + 90
        # Observe the systemd timer; this helper must not run recovery itself.
        while s.get('pending') and time.monotonic() < deadline:
            time.sleep(.2)
        with s.lock():
            require(not s.get('pending') and not s.get('current'), 'Systemd did not restore empty suite state')
            require(s.get('last-rollback')['token'] == record['token'], 'Wrong rollback observed')
            require(legacy.inventory(TABLE)['sha256'] == record['manifest']['sha256'],
                    'Legacy policy was not restored')
            engine.command(['nft', 'delete', 'table', 'inet', TABLE])
            s.delete(RECORD)
            s.delete('last-rollback')
    print(json.dumps({'phase': phase, 'passed': True}))


if __name__ == '__main__':
    main(sys.argv[1])
