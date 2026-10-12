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
    @classmethod
    def setUpClass(cls):
        i.KernelTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        i.KernelTests.tearDownClass()

    def setUp(self):
        self.f = i.KernelTests(); self.f.setUp()
        self.store = self.f.store
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
        if ('inet', 'reviewed') in engine.inspect('nftables', i.FRONTEND)['tables']:
            i.run('nft', 'delete', 'table', 'inet', 'reviewed')

    def apply(self, **options):
        return self.store.apply_locked(self.candidate, watchdog='process',
                                       legacy_manifest=self.manifest, **options)

    def test_default_reject_and_review_drift_preserve_rules(self):
        before = i.run('nft', '-s', 'list', 'table', 'inet', 'reviewed')
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

    def test_killed_applicator_still_restores_legacy(self):
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
        self.assertEqual(legacy.inventory('reviewed')['sha256'], self.manifest['sha256'])
        self.assertTrue(self.f.peer.tcp(18081))

    def test_confirmation_idempotence_and_selective_disable(self):
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
