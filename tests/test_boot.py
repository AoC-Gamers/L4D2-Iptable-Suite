#!/usr/bin/python3
"""H3 boot-safety tests; all kernel-facing calls are mocked."""
import copy
import json
import io
import time
from contextlib import redirect_stdout
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import boot, engine, fw
from core.store import Store
from core.config import PolicyError


class MemoryStore:
    def __init__(self, **values):
        self.values = values
        self.writes = []

    def get(self, name):
        return self.values.get(name)

    def put(self, name, value):
        self.writes.append((name, copy.deepcopy(value)))
        self.values[name] = copy.deepcopy(value)

    def delete(self, name):
        self.writes.append(('delete:' + name, None))
        self.values.pop(name, None)


def policy(backend='nftables'):
    return {
        'backend': backend,
        'config': {
            'IPTABLES_FRONTEND': 'nft', 'HOST_SERVICES': 'true',
            'SSH_PORT': '2222', 'FAMILY_POLICY': 'dual',
            'ROUTED_POLICY': 'drop', 'SSH_METER_TIMEOUT': '1m',
        },
        'selected': ['ssh_tcp_ssh'],
        'access': {'containers': [], 'forward': [], 'host': []},
        'hooks': [], 'families': {}, 'objects': [],
    }


def installed_for(value, *, boot_id='boot-a', policy_digest=None, objects_digest='kernel-a'):
    return {
        'schema': 1, 'boot_id': boot_id,
        'policy_digest': policy_digest if policy_digest is not None else boot.digest(value),
        'objects_digest': objects_digest, 'backend': value['backend'],
    }


class BootCompatibilityTests(unittest.TestCase):
    def versions(self, v4='iptables v1.8.10 (nf_tables)', v6='ip6tables v1.8.10 (nf_tables)'):
        return {'4': v4, '6': v6}

    def previous(self, versions=None):
        return {'backend': 'iptables', 'config': {'IPTABLES_FRONTEND': 'nft'},
                'versions': versions or self.versions()}

    def live(self, versions=None, frontend='nft'):
        return {'versions': versions or self.versions(), 'frontend': frontend}

    def test_vendor_string_change_with_evaluated_1810_is_accepted(self):
        old = self.previous()
        current = self.versions('iptables v1.8.10-1ubuntu2 (nf_tables)',
                                'ip6tables v1.8.10-1ubuntu2 (nf_tables)')
        result = engine.compatibility(old, self.live(current))
        self.assertEqual(result['decision'], 'evaluated-version')

    def test_unreviewed_version_requires_explicit_maintenance_acceptance(self):
        old = self.previous()
        current = self.versions('iptables v1.8.11 (nf_tables)', 'ip6tables v1.8.11 (nf_tables)')
        with self.assertRaisesRegex(PolicyError, 'not evaluated'):
            engine.compatibility(old, self.live(current))
        result = engine.compatibility(old, self.live(current), accept_version_change=True)
        self.assertEqual(result['decision'], 'operator-maintenance')

    def test_disable_confirmation_does_not_accept_an_unreviewed_version(self):
        changed = self.versions('iptables v1.9.0 (nf_tables)', 'ip6tables v1.9.0 (nf_tables)')
        candidate = {**self.previous(changed), 'disabled': True}
        store = MemoryStore(current=self.previous(), pending={
            'token': 'a' * 32, 'deadline': time.time() + 60, 'candidate': candidate,
        })
        with patch.object(boot, 'record_installed'):
            Store.confirm_locked(store, 'a' * 32)
        self.assertIsNone(store.get('current'))
        self.assertIsNone(store.get('pending'))
        with self.assertRaisesRegex(PolicyError, 'version not evaluated'):
            engine.compatibility(store.get('current'), self.live(changed))

    def test_unevaluated_unchanged_version_needs_recorded_maintenance_acceptance(self):
        versions = self.versions('iptables v1.8.11 (nf_tables)', 'ip6tables v1.8.11 (nf_tables)')
        previous = self.previous(versions)
        with self.assertRaisesRegex(PolicyError, 'not evaluated'):
            engine.compatibility(previous, self.live(versions))
        previous['compatibility'] = engine.compatibility(previous, self.live(versions), accept_version_change=True)
        self.assertEqual(previous['compatibility']['decision'], 'operator-maintenance')
        self.assertEqual(engine.compatibility(previous, self.live(versions))['decision'], 'unchanged')

    def test_frontend_mismatch_is_never_accepted_by_flag(self):
        old = self.previous()
        legacy = self.versions('iptables v1.8.10 (legacy)', 'ip6tables v1.8.10 (legacy)')
        with self.assertRaisesRegex(PolicyError, 'frontend changed'):
            engine.compatibility(old, self.live(legacy, frontend='legacy'), accept_version_change=True)

    def test_ipv4_ipv6_frontend_mix_is_rejected(self):
        mixed = self.versions('iptables v1.8.10 (nf_tables)', 'ip6tables v1.8.10 (legacy)')
        with self.assertRaisesRegex(PolicyError, 'differ'):
            engine.compatibility(None, self.live(mixed, frontend='mixed'), accept_version_change=True)


class BootReadinessTests(unittest.TestCase):
    def ready_store(self, value=None, **installed_fields):
        value = value or policy()
        return MemoryStore(current=value, installed=installed_for(value, **installed_fields))

    def run_verify(self, store, *, objects_digest='kernel-a', guarded=False):
        with (patch.object(boot, 'boot_id', return_value='boot-a'),
              patch.object(engine, 'inspect', return_value={'tables': [], 'iprules': {}}),
              patch.object(engine, 'preflight'),
              patch.object(boot, 'fingerprint', return_value=objects_digest),
              patch.object(boot, 'guard_present', return_value=guarded)):
            return boot.verify(store)

    def test_readiness_requires_current_boot_policy_and_kernel_fingerprint(self):
        store = self.ready_store()
        self.assertTrue(self.run_verify(store)['ready'])
        cases = [
            (self.ready_store(boot_id='boot-old'), 'another boot'),
            (self.ready_store(policy_digest='changed'), 'policy digest differs'),
            (self.ready_store(objects_digest='changed'), 'managed kernel rules changed'),
        ]
        for invalid, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(PolicyError, message):
                self.run_verify(invalid)
        with self.assertRaisesRegex(PolicyError, 'barrier is still active'):
            self.run_verify(self.ready_store(), guarded=True)

    def test_pending_transaction_blocks_readiness_before_inspection(self):
        value = policy()
        store = MemoryStore(current=value, installed=installed_for(value), pending={'token': 'pending'})
        with patch.object(engine, 'inspect') as inspect:
            with self.assertRaisesRegex(PolicyError, 'transaction is pending'):
                boot.verify(store)
        inspect.assert_not_called()

    def test_nft_fingerprint_ignores_volatile_counters_and_dynamic_elements_only(self):
        kernel = {
            'nftables': [
                {'table': {'family': 'inet', 'name': 'managed'}},
                {'set': {'family': 'inet', 'table': 'managed', 'name': 'meter',
                         'flags': ['dynamic'], 'elem': [{'elem': {'val': '198.51.100.8', 'expires': 50}}]}},
                {'set': {'family': 'inet', 'table': 'managed', 'name': 'acl',
                         'flags': ['interval'], 'elem': [{'elem': {'val': '203.0.113.0/24'}}]}},
                {'rule': {'family': 'inet', 'table': 'managed', 'chain': 'input',
                          'handle': 9, 'packets': 17, 'bytes': 2048,
                          'expr': [{'accept': None}], 'metainfo': {'version': 1}}},
            ]
        }
        changed_runtime = copy.deepcopy(kernel)
        changed_runtime['nftables'][1]['set']['elem'].append(
            {'elem': {'val': '198.51.100.9', 'expires': 20}})
        changed_runtime['nftables'][3]['rule']['packets'] = 900
        changed_runtime['nftables'][3]['rule']['bytes'] = 65000
        changed_acl = copy.deepcopy(changed_runtime)
        changed_acl['nftables'][2]['set']['elem'][0]['elem']['val'] = '203.0.114.0/24'
        value = policy()
        value['objects'] = [{'family': 'inet', 'name': 'managed'}]
        live = {'tables': [('inet', 'managed')], 'iprules': {}}

        def nft_output(_argv):
            return SimpleNamespace(stdout=json.dumps(kernel))

        with patch.object(engine, 'require_owned_present'), patch.object(engine, 'command', side_effect=nft_output):
            initial = boot.fingerprint(value, live)
            outputs = [json.dumps(changed_runtime), json.dumps(changed_acl)]
            with patch.object(engine, 'command', side_effect=[SimpleNamespace(stdout=outputs[0])]):
                runtime = boot.fingerprint(value, live)
            with patch.object(engine, 'command', side_effect=[SimpleNamespace(stdout=outputs[1])]):
                acl = boot.fingerprint(value, live)
        self.assertEqual(initial, runtime)
        self.assertNotEqual(initial, acl)

    def test_iptables_readiness_rejects_displaced_owned_hook_and_acl_drift(self):
        value = policy('iptables')
        value['families'] = {'4': {'filter': {'L4S_INPUT'}}, '6': {'filter': {'L4S_INPUT'}}}
        value['hooks'] = [['filter', 'INPUT', 'L4S_INPUT']]
        hook = ' '.join(engine.hook_rule('INPUT', 'L4S_INPUT'))
        good4 = f'*filter\n:INPUT ACCEPT [0:0]\n:L4S_INPUT - [0:0]\n{hook}\n-A L4S_INPUT -s 198.51.100.0/24 -j ACCEPT\nCOMMIT\n'
        good6 = f'*filter\n:INPUT ACCEPT [0:0]\n:L4S_INPUT - [0:0]\n{hook}\n-A L4S_INPUT -j DROP\nCOMMIT\n'
        live = {'iprules': {'4': good4, '6': good6}}
        first = boot.fingerprint(value, live)
        changed_acl = {'iprules': {'4': good4.replace('198.51.100.0/24', '203.0.113.0/24'), '6': good6}}
        self.assertNotEqual(first, boot.fingerprint(value, changed_acl))
        displaced = {'iprules': {'4': good4.replace(hook + '\n', '-A INPUT -j ACCEPT\n' + hook + '\n'), '6': good6}}
        with self.assertRaisesRegex(PolicyError, 'hook missing or displaced'):
            boot.fingerprint(value, displaced)


class PassiveDiagnosisTests(unittest.TestCase):
    def test_diagnose_does_not_open_store_or_recover_a_pending_change(self):
        live = {'versions': {}, 'frontend': 'nft', 'docker': 'none', 'iprules': {'4': '', '6': ''}}
        output = io.StringIO()
        with patch.object(fw.os, 'geteuid', return_value=0), patch.object(fw, 'trusted'), \
                patch.object(fw.engine, 'inspect', return_value=live), patch.object(fw, 'Store') as store, \
                redirect_stdout(output):
            fw.main(['--backend', 'iptables', 'diagnose'])
        store.assert_not_called()
        self.assertIn('docker_forward', json.loads(output.getvalue()))


class BootManifestTests(unittest.TestCase):
    def test_guard_orders_after_optional_nftables_manager_before_network(self):
        unit = (ROOT / 'systemd/l4d2-firewall-guard.service').read_text()
        self.assertIn('After=local-fs.target nftables.service', unit)
        self.assertIn('Before=network-pre.target docker.service l4d2-firewall.service', unit)
        self.assertNotIn('Requires=nftables.service', unit)

    def test_corrupt_manifest_fails_before_any_firewall_command(self):
        store = MemoryStore(**{'boot-policy': {'schema': 1, 'owner': 'a' * 32,
                                               'text': 'add table inet other',
                                               'text_digest': 'corrupt'}})
        with patch.object(engine, 'command') as command:
            with self.assertRaisesRegex(PolicyError, 'manifest missing, corrupt'):
                boot.guard(store)
        command.assert_not_called()
        self.assertEqual(store.writes, [])

    def test_foreign_guard_table_cannot_be_adopted_or_deleted(self):
        value = {'owner': 'a' * 32}
        raw = {'nftables': [{'table': {'family': 'inet', 'name': boot.TABLE,
                                       'comment': 'operator-owned'}}]}
        with patch.object(engine, 'command', return_value=SimpleNamespace(stdout=json.dumps(raw))) as command:
            with self.assertRaisesRegex(PolicyError, 'not registered to this suite'):
                boot.require_guard_owned(value)
        command.assert_called_once_with(['nft', '-j', 'list', 'table', 'inet', boot.TABLE])

    def test_manifest_scope_changes_rejected_but_rate_only_changes_are_saved(self):
        current = policy()
        owner = 'b' * 32
        rows = []
        text = boot.guard_text(current, rows, owner)
        manifest = {'schema': 1, 'owner': owner, 'policy_digest': boot.digest(current),
                    'text': text, 'text_digest': boot.digest(text), 'recovery': rows}
        store = MemoryStore(**{'boot-policy': manifest})

        changed_rate = copy.deepcopy(current)
        changed_rate['config']['SSH_METER_TIMEOUT'] = '10m'
        boot.require_scope(store, changed_rate)
        boot.saved(store, changed_rate)
        self.assertEqual(store.get('boot-policy')['policy_digest'], boot.digest(changed_rate))
        self.assertEqual(store.get('boot-policy')['text'], text)

        changed_scope = copy.deepcopy(changed_rate)
        changed_scope['config']['FAMILY_POLICY'] = 'ipv4-block-ipv6'
        writes_before = len(store.writes)
        with self.assertRaisesRegex(PolicyError, 'Boot scope changed'):
            boot.saved(store, changed_scope)
        self.assertEqual(len(store.writes), writes_before)

    def test_prepare_accepts_narrow_ssh_recovery_or_console_only(self):
        current = policy()
        owner = 'c' * 32
        recovery = [{'source': '198.51.100.8/32', 'destination': '192.0.2.10',
                     'input': 'wan0', 'ports': '2222'}]
        with tempfile.TemporaryDirectory() as directory:
            recovery_path = Path(directory) / 'recovery.json'
            recovery_path.write_text(json.dumps(recovery))
            stores = [MemoryStore(current=current, persisted=copy.deepcopy(current)),
                      MemoryStore(current=current, persisted=copy.deepcopy(current))]
            with (patch.object(boot, 'trusted'), patch.object(boot, 'guard_present', return_value=False),
                  patch.object(boot, 'verify', return_value={'ready': True}),
                  patch.object(boot.secrets, 'token_hex', return_value=owner),
                  patch.object(engine, 'command', return_value=SimpleNamespace(stdout='')) as command):
                result = boot.prepare(stores[0], str(recovery_path))
                saved = stores[0].get('boot-policy')
                self.assertTrue(result['prepared'])
                self.assertIn('ip saddr 198.51.100.8/32 ip daddr 192.0.2.10 tcp dport { 2222 } counter accept', saved['text'])
                self.assertEqual(result['recovery_grants'], 1)

                console = boot.prepare(stores[1], None)
                self.assertEqual(console['recovery_grants'], 0)
                self.assertEqual(stores[1].get('boot-policy')['recovery'], [])
            self.assertEqual(command.call_count, 2)
            self.assertTrue(all(call.args[0] == ['nft', '-c', '-f', '-'] for call in command.call_args_list))

    def test_recovery_rejects_unscoped_sources_and_ports_outside_host_ssh(self):
        current = policy()
        rows = [{'source': '0.0.0.0/0', 'destination': '192.0.2.10',
                 'input': 'wan0', 'ports': '22'}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recovery.json'
            path.write_text(json.dumps(rows))
            with patch.object(boot, 'trusted'):
                with self.assertRaisesRegex(PolicyError, 'scoped source'):
                    boot.recovery_rows(path, current)
                rows[0]['source'] = '198.51.100.8/32'
                path.write_text(json.dumps(rows))
                with self.assertRaisesRegex(PolicyError, 'subset of configured host SSH ports'):
                    boot.recovery_rows(path, current)

    def test_snapshot_does_not_capture_independent_boot_guard_table(self):
        value = policy()
        value['objects'] = [{'family': 'inet', 'name': 'managed', 'text': 'add table inet managed\n'}]
        live = {'tables': [('inet', 'managed'), ('inet', boot.TABLE)]}
        with patch.object(engine, 'command', return_value=SimpleNamespace(stdout='add table inet managed\n')) as command:
            snapshot = engine.snapshot(value, live)
        self.assertEqual([obj['name'] for obj in snapshot['objects']], ['managed'])
        command.assert_called_once_with(['nft', '-s', 'list', 'table', 'inet', 'managed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
