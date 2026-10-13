#!/usr/bin/python3
"""Explicit legacy handover: real kernel/traffic, isolated-run.sh only."""
import importlib.util
import copy
import json
from pathlib import Path
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('integration', ROOT / 'tests/integration.py')
i = importlib.util.module_from_spec(spec)
spec.loader.exec_module(i)
from core import engine, legacy
from core.config import PolicyError
from core.compiler import generate


class LegacyFlows(unittest.TestCase):
    """Kernel handover flows; S2S NAT tests cover table transactions, not packet translation."""
    @classmethod
    def setUpClass(cls):
        i.KernelTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        i.KernelTests.tearDownClass()

    def setUp(self):
        self.f = i.KernelTests(); self.f.setUp()
        self.store = self.f.store
        self.nat_keys = []
        i.run('nft', '-f', '-', text='''table inet reviewed {
 chain input { type filter hook input priority 0; policy drop;
  iifname "lo" accept
  ct state established,related accept
  tcp dport 18081 meter http_https_input_web_under_v4 size 65535 { ip saddr . tcp dport timeout 5m limit rate 180/minute burst 360 packets } accept
  tcp dport { 22222,18081 } accept
 }
}
''')
        self.manifest = legacy.inventory('reviewed')
        self.candidate = generate(self.f.config('nftables', NF_TABLE_NAME='reviewed', ROUTED_POLICY='unmanaged'))

    def tearDown(self):
        self.f.tearDown()
        live = set(engine.inspect('nftables', i.FRONTEND)['tables'])
        for family, name in self.nat_keys:
            if (family, name) in live:
                i.run('nft', 'delete', 'table', family, name)
        if ('inet', 'reviewed') in engine.inspect('nftables', i.FRONTEND)['tables']:
            i.run('nft', 'delete', 'table', 'inet', 'reviewed')

    def enable_s2s_nat(self):
        """Use compiler S2S NAT objects; this tests table lifecycle, not VPN packet translation."""
        i.run('nft', '-f', '-', text='''table ip vpn_s2s_nat {
 chain postrouting { type nat hook postrouting priority 100; policy accept;
  ip daddr 198.51.100.0/24 counter masquerade
 }
}
table ip6 vpn_s2s_nat6 {
 chain postrouting { type nat hook postrouting priority 100; policy accept;
  ip6 daddr 2001:db8:ffff::/64 counter masquerade
 }
}
''')
        self.nat_keys = [('ip', 'vpn_s2s_nat'), ('ip6', 'vpn_s2s_nat6'),
                         ('ip', 'reviewed_nat4'), ('ip6', 'reviewed_nat6')]
        self.manifest = legacy.inventory('reviewed', self.nat_keys[:2])
        def generate_s2s(local, remote):
            return generate(self.f.config(
                # Preserve the fixture's web grant while adding S2S NAT modules.
                'nftables', MODULES_ONLY='tcp_ssh http_https_protect openvpn_sitetosite',
                NF_TABLE_NAME='reviewed', ROUTED_POLICY='unmanaged',
                OVPNS2S_INTERFACE='tun0', OVPNS2S_LOCAL_INTERFACE='lan0',
                OVPNS2S_LOCAL_SUBNETS=local, OVPNS2S_REMOTE_SUBNETS=remote,
                OVPNS2S_ENABLE_NAT='true'))
        # The compiler currently checks every local destination against each
        # source family, so compile one family at a time and combine its NAT
        # table objects for this transaction-only dual-family fixture.
        self.candidate = generate_s2s('192.0.2.0/24', '10.8.0.0/24')
        ipv6 = generate_s2s('2001:db8:1::/64', '2001:db8:2::/64')
        self.candidate['objects'].append(next(obj for obj in ipv6['objects'] if obj['family'] == 'ip6'))
        self.assertEqual({(obj['family'], obj['name']) for obj in self.candidate['objects']
                          if obj['family'] in ('ip', 'ip6')},
                         {('ip', 'reviewed_nat4'), ('ip6', 'reviewed_nat6')})

    def apply(self, **options):
        return self.store.apply_locked(self.candidate, watchdog='process',
                                       legacy_manifest=self.manifest, **options)

    def assert_reviewed_policies_restored(self):
        restored = legacy.inventory('reviewed', self.nat_keys[:2])
        self.assertEqual(restored['schema'], 2)
        def identity(manifest):
            return [(x['family'], x['name'], x['sha256']) for x in manifest['tables']]
        self.assertEqual(identity(restored), identity(self.manifest))

    def test_default_reject_and_review_drift_preserve_rules(self):
        before = i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed')
        path = i.STATE / 'reviewed-manifest.json'
        path.write_text(json.dumps(self.manifest)); path.chmod(0o600)
        try:
            # Exercise the operator's CLI check path, without nesting locks.
            result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'core/fw.py'),
                '--state-dir', str(i.STATE), 'check', '--backend', 'nftables',
                '--profile', 'web', '--set', 'NF_TABLE_NAME=reviewed',
                '--set', 'ROUTED_POLICY=unmanaged', '--legacy-manifest', str(path),
                '--acknowledge-legacy-ownership'], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Kernel candidate check passed', result.stdout)
            self.assertEqual(before, i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed'))
        finally:
            path.unlink()
        with self.store.lock():
            with self.assertRaisesRegex(PolicyError, 'Object not owned'):
                self.store.apply_locked(self.candidate, local=True)
            broken = copy.deepcopy(self.candidate)
            broken['objects'][0]['text'] += 'invalid nft syntax\n'
            with self.assertRaises(PolicyError):
                self.store.apply_locked(broken, watchdog='process', legacy_manifest=self.manifest)
            self.assertEqual(before, i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed'))
            self.assertIsNone(self.store.get('pending'))
            i.run('nft', 'add', 'rule', 'inet', 'reviewed', 'input', 'tcp', 'dport', '64999', 'drop')
            changed = i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed')
            self.assertNotEqual(before, changed)
            with self.assertRaisesRegex(PolicyError, 'changed since review'):
                self.apply(timeout=i.CONFIRM_TIMEOUT)
            self.assertEqual(changed, i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed'))
            self.assertIsNone(self.store.get('pending'))

    def test_expiry_restores_legacy_policy_and_preserves_foreign_changes(self):
        self.assertTrue(self.f.peer.tcp(18081)); self.assertFalse(self.f.peer.tcp(18080))
        with self.store.lock():
            token = self.apply(timeout=i.EXPIRY_TIMEOUT)
            with self.assertRaisesRegex(PolicyError, 'Unconfirmed change'):
                self.store.apply_locked(self.candidate, local=True)
        self.assertTrue(self.f.peer.tcp(18080)); self.assertFalse(self.f.peer.tcp(18081))
        i.run('nft', 'add', 'table', 'inet', 'new_outsider')
        try:
            self.f.wait_for_rollback(token)
            self.assertIsNone(self.store.get('current'))
            self.assertEqual(legacy.inventory('reviewed')['sha256'], self.manifest['sha256'])
            self.assertTrue(self.f.peer.tcp(18081)); self.assertFalse(self.f.peer.tcp(18080))
            self.assertIn(('inet', 'new_outsider'), engine.inspect('nftables', i.FRONTEND)['tables'])
        finally:
            i.run('nft', 'delete', 'table', 'inet', 'new_outsider')

    def test_nat_candidate_syntax_failure_preserves_every_reviewed_table(self):
        self.enable_s2s_nat()
        before = {key: i.run('nft', '-s', 'list', 'table', *key)
                  for key in self.nat_keys[:2] + [('inet', 'reviewed')]}
        broken = copy.deepcopy(self.candidate)
        nat = next(obj for obj in broken['objects'] if obj['family'] == 'ip')
        nat['text'] += 'this is invalid nft syntax\n'
        with self.store.lock(), self.assertRaises(PolicyError):
            self.store.apply_locked(broken, watchdog='process', legacy_manifest=self.manifest)
        self.assertIsNone(self.store.get('pending'))
        for key, text in before.items():
            self.assertEqual(i.run('nft', '-s', 'list', 'table', *key), text)
        for key in self.nat_keys[2:]:
            self.assertNotIn(key, engine.inspect('nftables', i.FRONTEND)['tables'])

    def test_stale_nat_handle_aborts_whole_filter_and_nat_candidate_batch(self):
        self.enable_s2s_nat()
        before_filter = i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed')
        before_v6 = i.run('nft', '-s', 'list', 'table', 'ip6', 'vpn_s2s_nat6')
        live = engine.inspect('nftables', i.FRONTEND)
        snapshot = legacy.prepare(self.candidate, None, self.manifest, live)
        tx = engine.prepare(self.candidate, [self.candidate, snapshot], live)
        legacy.pin_transaction(tx, self.manifest)
        old_nat_handle = next(item['handle'] for item in self.manifest['tables'] if item['family'] == 'ip')
        i.run('nft', 'delete', 'table', 'ip', 'vpn_s2s_nat')
        i.run('nft', '-f', '-', text='''table ip vpn_s2s_nat {
 chain postrouting { type nat hook postrouting priority 100; policy accept;
  ip daddr 198.51.100.1 counter masquerade
 }
}
''')
        replacement = i.run('nft', '-s', 'list', 'table', 'ip', 'vpn_s2s_nat')
        replacement_handle = next(item['handle'] for item in legacy.inventory(
            'reviewed', self.nat_keys[:2])['tables'] if item['family'] == 'ip')
        self.assertNotEqual(replacement_handle, old_nat_handle)
        with self.assertRaises(PolicyError):
            engine.check(tx)
        with self.assertRaises(PolicyError):
            engine.execute(tx)
        self.assertEqual(i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed'), before_filter)
        self.assertEqual(i.run('nft', '-s', 'list', 'table', 'ip', 'vpn_s2s_nat'), replacement)
        self.assertEqual(i.run('nft', '-s', 'list', 'table', 'ip6', 'vpn_s2s_nat6'), before_v6)
        tables = set(engine.inspect('nftables', i.FRONTEND)['tables'])
        self.assertIn(('ip6', 'vpn_s2s_nat6'), tables)
        self.assertNotIn(('ip', 'reviewed_nat4'), tables)
        self.assertNotIn(('ip6', 'reviewed_nat6'), tables)

    def test_apply_replaces_old_s2s_nat_tables_in_one_batch(self):
        self.enable_s2s_nat()
        batches = []
        execute = engine.execute
        def record(tx):
            batches.append(list(tx))
            return execute(tx)
        with self.store.lock(), patch.object(engine, 'execute', side_effect=record):
            token = self.apply(timeout=i.CONFIRM_TIMEOUT)
            tables = set(engine.inspect('nftables', i.FRONTEND)['tables'])
            self.assertNotIn(('ip', 'vpn_s2s_nat'), tables)
            self.assertNotIn(('ip6', 'vpn_s2s_nat6'), tables)
            self.assertIn(('ip', 'reviewed_nat4'), tables)
            self.assertIn(('ip6', 'reviewed_nat6'), tables)
            self.assertEqual(len(batches), 1)
            text = batches[0][0][1]
            for family, name in self.nat_keys[:2]:
                entry = next(item for item in self.manifest['tables'] if item['family'] == family)
                self.assertIn(f'delete table {family} handle {entry["handle"]}', text)
                self.assertIn(f'destroy table {family} {name}', text)
            self.assertIn('add table ip reviewed_nat4', text)
            self.assertIn('add table ip6 reviewed_nat6', text)
            self.assertTrue(self.store.rollback_locked(token))
        self.assert_reviewed_policies_restored()

    def test_killed_applicator_still_restores_legacy(self):
        self.enable_s2s_nat()
        before_filter = i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed')
        before_outsider = i.run('nft', '-s', 'list', 'table', 'inet', 'outsider')
        code = f'''import sys,os,signal,json
sys.path.insert(0,{str(ROOT)!r})
from core.store import Store
from core import engine
s=Store({str(i.STATE)!r})
real=engine.execute
def killed(tx):
 real(tx)
 os.kill(os.getpid(),signal.SIGKILL)
engine.execute=killed
with s.lock():s.apply_locked(json.loads({json.dumps(self.candidate)!r}),timeout={i.EXPIRY_TIMEOUT},watchdog='process',legacy_manifest=json.loads({json.dumps(self.manifest)!r}))
'''
        result = subprocess.run(['python3', '-I', '-B', '-c', code], check=False)
        self.assertEqual(result.returncode, -signal.SIGKILL)
        self.f.wait_for_rollback(self.store.get('pending')['token'])
        self.assert_reviewed_policies_restored()
        self.assertEqual(i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed'), before_filter)
        self.assertEqual(i.run('nft', '-s', 'list', 'table', 'inet', 'outsider'), before_outsider)
        tables = set(engine.inspect('nftables', i.FRONTEND)['tables'])
        self.assertNotIn(('ip', 'reviewed_nat4'), tables)
        self.assertNotIn(('ip6', 'reviewed_nat6'), tables)
        self.assertTrue(self.f.peer.tcp(18081))

    def test_confirmation_idempotence_and_selective_disable(self):
        self.enable_s2s_nat()
        with self.store.lock():
            token = self.apply(timeout=i.CONFIRM_TIMEOUT)
            self.assertTrue(self.f.peer.tcp(22222))
            self.store.confirm_locked(token)
            self.assertIsNotNone(self.store.get('current'))
            self.store.apply_locked(self.candidate, local=True)
            with self.assertRaisesRegex(PolicyError, 'no current registered'):
                self.apply(timeout=i.CONFIRM_TIMEOUT)
        self.assertTrue(self.f.peer.tcp(18080)); self.assertFalse(self.f.peer.tcp(18081))
        self.f.disable()
        self.assertNotIn(('inet', 'reviewed'), engine.inspect('nftables', i.FRONTEND)['tables'])
        tables = set(engine.inspect('nftables', i.FRONTEND)['tables'])
        self.assertNotIn(('ip', 'reviewed_nat4'), tables)
        self.assertNotIn(('ip6', 'reviewed_nat6'), tables)

    def test_change_after_watchdog_arm_is_not_overwritten(self):
        real_arm = self.store.arm
        def arm_then_change(*args):
            real_arm(*args)
            i.run('nft', 'add', 'rule', 'inet', 'reviewed', 'input', 'tcp', 'dport', '64999', 'drop')
        with self.store.lock(), patch.object(self.store, 'arm', side_effect=arm_then_change):
            with self.assertRaisesRegex(PolicyError, 'changed since review'):
                self.apply(timeout=i.CONFIRM_TIMEOUT)
        self.assertIsNone(self.store.get('pending'))
        self.assertIn('64999', i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed'))
        self.assertTrue(self.f.peer.tcp(18081)); self.assertFalse(self.f.peer.tcp(18080))

    def test_stale_handle_batch_cannot_delete_replacement_table(self):
        live = engine.inspect('nftables', i.FRONTEND)
        tx = engine.prepare(self.candidate, [self.candidate], live)
        legacy.pin_transaction(tx, self.manifest)
        i.run('nft', 'delete', 'table', 'inet', 'reviewed')
        i.run('nft', '-f', '-', text='table inet reviewed {\n chain replacement { tcp dport 64999 drop; }\n}\n')
        replacement = legacy.inventory('reviewed')
        self.assertNotEqual(replacement['handle'], self.manifest['handle'])
        with self.assertRaises(PolicyError):
            engine.check(tx)
        with self.assertRaises(PolicyError):
            engine.execute(tx)
        self.assertEqual(legacy.inventory('reviewed'), replacement)


if __name__ == '__main__':
    unittest.main(verbosity=2)
