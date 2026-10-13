#!/usr/bin/python3
"""Legacy handover validation; kernel calls mocked."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import engine, legacy
from core.config import PolicyError
from core.fw import main


class LegacyTests(unittest.TestCase):
    def raw(self):
        return {'nftables': [{'metainfo': {'version': 'test'}},
                {'table': {'family': 'inet', 'name': 'reviewed', 'handle': 9}},
                {'chain': {'family': 'inet', 'table': 'reviewed', 'name': 'input',
                           'type': 'filter', 'hook': 'input', 'policy': 'drop'}},
                {'rule': {'family': 'inet', 'table': 'reviewed', 'chain': 'input',
                          'expr': [{'counter': {'packets': 2, 'bytes': 120}}, {'accept': None}]}}]}

    def inventory(self, raw=None):
        with patch.object(engine, 'command', return_value=type('Result', (), {'stdout': json.dumps(raw or self.raw())})()):
            return legacy.inventory('reviewed')

    def test_fingerprint_ignores_counters_but_pins_identity_and_policy(self):
        original = self.inventory()
        raw = self.raw()
        raw['nftables'][3]['rule']['expr'][0]['counter']['packets'] = 1000
        self.assertEqual(self.inventory(raw), original)
        raw['nftables'][3]['rule']['expr'][1] = {'drop': None}
        self.assertNotEqual(self.inventory(raw)['sha256'], original['sha256'])
        raw = self.raw(); raw['nftables'][1]['table']['handle'] += 1
        self.assertNotEqual(self.inventory(raw), original)

    def test_unsafe_names_reserved_table_and_nonfilter_hooks_fail(self):
        for name in ('x;flush ruleset', '../table', 'l4d2_boot_guard', ''):
            with self.subTest(name=name), self.assertRaises(PolicyError):
                legacy.table_name(name)
        raw = self.raw(); raw['nftables'][2]['chain']['type'] = 'nat'
        with self.assertRaisesRegex(PolicyError, 'only an inet filter'):
            self.inventory(raw)

    def test_strict_manifest_and_change_detection(self):
        manifest = self.inventory()
        for bad in ({**manifest, 'schema': True}, {**manifest, 'handle': -1},
                    {**manifest, 'sha256': 'wrong'}, {**manifest, 'extra': 'ignored'}):
            with self.subTest(bad=bad), self.assertRaises(PolicyError):
                legacy.validate(bad)
        with patch.object(legacy, 'inventory', return_value={**manifest, 'handle': 10}), \
                self.assertRaisesRegex(PolicyError, 'changed since review'):
            legacy.verify(manifest)

    def test_reject_existing_state_backend_nat_and_forwarding_before_snapshot(self):
        manifest = self.inventory()
        candidate = {'backend': 'nftables', 'config': {'HOST_SERVICES': 'true',
                     'CONTAINER_POLICY': 'off', 'ROUTED_POLICY': 'unmanaged'},
                     'objects': [{'family': 'inet', 'name': 'reviewed'}]}
        variants = [(candidate, candidate), ({**candidate, 'backend': 'iptables'}, None)]
        for key, value in (('HOST_SERVICES', 'false'), ('CONTAINER_POLICY', 'restrict'),
                           ('ROUTED_POLICY', 'drop')):
            item = copy.deepcopy(candidate); item['config'][key] = value
            variants.append((item, None))
        item = copy.deepcopy(candidate); item['objects'].append({'family': 'ip', 'name': 'nat'})
        variants.append((item, None))
        with patch.object(engine, 'snapshot') as snapshot:
            for item, previous in variants:
                with self.subTest(item=item), self.assertRaises(PolicyError):
                    legacy.prepare(item, previous, manifest, {})
            snapshot.assert_not_called()

    def test_schema1_handover_accepts_new_ingress_policy(self):
        manifest = self.inventory()
        candidate = {'backend': 'nftables', 'config': {'HOST_SERVICES': 'true',
                     'CONTAINER_POLICY': 'ingress', 'ROUTED_POLICY': 'unmanaged'},
                     'objects': [{'family': 'inet', 'name': 'reviewed'}]}
        snapshot = {'backend': 'nftables', 'objects': [
            {'family': 'inet', 'name': 'reviewed', 'text': 'table inet reviewed { }'}]}
        live = {'tables': {('inet', 'reviewed')}}
        with patch.object(legacy, 'verify'), patch.object(engine, 'snapshot', return_value=snapshot), \
                patch.object(engine, 'check'):
            self.assertEqual(legacy.prepare(candidate, None, manifest, live), snapshot)

    def test_handle_deletion_is_single_transaction_and_cli_requires_ack(self):
        manifest = self.inventory()
        tx = engine.TransactionBatch([('nft', 'delete table inet reviewed\nadd table inet reviewed\n')])
        legacy.pin_transaction(tx, manifest)
        self.assertEqual(tx, [('nft', 'delete table inet handle 9\ndestroy table inet reviewed\nadd table inet reviewed\n')])
        with patch('core.fw.Store') as store:
            for args in (['apply', '--legacy-manifest', '/root/review.json'],
                         ['disable', '--legacy-manifest', '/root/review.json', '--acknowledge-legacy-ownership'],
                         ['apply', '--local', '--legacy-manifest', '/root/review.json', '--acknowledge-legacy-ownership']):
                with self.subTest(args=args), self.assertRaises(PolicyError):
                    main(args)
            store.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
