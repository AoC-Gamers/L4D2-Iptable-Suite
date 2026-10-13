#!/usr/bin/python3
"""Schema-2 passive inventory and atomic legacy NAT handover unit tests."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import boot, engine, legacy
from core.config import PolicyError
from core.store import Store


class LegacyNatTests(unittest.TestCase):
    def raw(self, family, name, chain='prerouting', kind='nat'):
        return {'nftables': [{'metainfo': {'version': 'test'}},
                {'table': {'family': family, 'name': name, 'handle': 21}},
                {'chain': {'family': family, 'table': name, 'name': 'hook',
                           'type': kind, 'hook': chain, 'prio': -100}},
                {'rule': {'family': family, 'table': name, 'chain': 'hook',
                          'expr': [{'counter': {'packets': 1, 'bytes': 44}}, {'accept': None}]}}]}

    def command_inventory(self, mapping):
        def command(argv, **_kwargs):
            key = (argv[-2], argv[-1])
            return type('Result', (), {'stdout': json.dumps(mapping[key])})()
        return patch.object(engine, 'command', side_effect=command)

    def manifest(self):
        mapping = {
            ('inet', 'reviewed'): self.raw('inet', 'reviewed', 'input', 'filter'),
            ('ip', 'vpn_s2s_nat'): self.raw('ip', 'vpn_s2s_nat', 'prerouting', 'nat'),
            ('ip6', 'v6_nat'): self.raw('ip6', 'v6_nat', 'postrouting', 'nat'),
        }
        with self.command_inventory(mapping):
            return legacy.inventory('reviewed', [('ip', 'vpn_s2s_nat'), ('ip6', 'v6_nat')])

    def test_schema2_inventory_fingerprints_every_explicit_table(self):
        manifest = self.manifest()
        self.assertEqual(manifest['schema'], 2)
        self.assertEqual([(x['family'], x['name']) for x in manifest['tables']],
                         [('inet', 'reviewed'), ('ip', 'vpn_s2s_nat'), ('ip6', 'v6_nat')])
        self.assertTrue(all(x['handle'] == 21 and len(x['sha256']) == 64 for x in manifest['tables']))
        self.assertEqual(legacy.owned_keys(manifest),
                         (('inet', 'reviewed'), ('ip', 'vpn_s2s_nat'), ('ip6', 'v6_nat')))

    def test_only_nat_prerouting_and_postrouting_hooks_are_inventoryable(self):
        bad = self.raw('ip', 'bad_nat', 'input', 'nat')
        mapping = {('inet', 'reviewed'): self.raw('inet', 'reviewed', 'input', 'filter'),
                   ('ip', 'bad_nat'): bad}
        with self.command_inventory(mapping), \
                self.assertRaisesRegex(PolicyError, 'ip/ip6 NAT hooks'):
            legacy.inventory('reviewed', [('ip', 'bad_nat')])
        bad = self.raw('ip6', 'bad_nat', 'prerouting', 'filter')
        mapping = {('inet', 'reviewed'): self.raw('inet', 'reviewed', 'input', 'filter'),
                   ('ip6', 'bad_nat'): bad}
        with self.command_inventory(mapping), \
                self.assertRaises(PolicyError):
            legacy.inventory('reviewed', [('ip6', 'bad_nat')])

    def test_inventory_bounds_and_manifest_shape_are_strict(self):
        with self.assertRaisesRegex(PolicyError, 'at most eight'):
            legacy.inventory('reviewed', [('ip', f'nat{i}') for i in range(8)])
        manifest = self.manifest()
        invalid = [
            {**manifest, 'unexpected': True},
            {**manifest, 'tables': manifest['tables'][:1]},
            {**manifest, 'tables': [manifest['tables'][0], {**manifest['tables'][1], 'family': 'inet'}, manifest['tables'][2]]},
            {**manifest, 'tables': [manifest['tables'][0], manifest['tables'][1], manifest['tables'][1]]},
            {**manifest, 'tables': [manifest['tables'][0], {**manifest['tables'][1], 'handle': True}, manifest['tables'][2]]},
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(PolicyError):
                legacy.validate(item)

    def test_schema2_prepare_snapshots_all_old_names_and_allows_ingress_only(self):
        manifest = self.manifest()
        candidate = {'backend': 'nftables', 'config': {'HOST_SERVICES': 'true',
                     'CONTAINER_POLICY': 'ingress', 'ROUTED_POLICY': 'unmanaged'},
                     'objects': [{'family': 'inet', 'name': 'reviewed'},
                                 {'family': 'ip', 'name': 'firewall_nat4'},
                                 {'family': 'ip6', 'name': 'firewall_nat6'}]}
        snapshot = {'backend': 'nftables', 'objects': [
            {'family': 'inet', 'name': 'reviewed', 'text': 'table inet reviewed { }'},
            {'family': 'ip', 'name': 'vpn_s2s_nat', 'text': 'table ip vpn_s2s_nat { }'},
            {'family': 'ip6', 'name': 'v6_nat', 'text': 'table ip6 v6_nat { }'}]}
        with patch.object(legacy, 'verify'), patch.object(engine, 'snapshot', return_value=snapshot) as take, \
                patch.object(engine, 'check') as check:
            result = legacy.prepare(candidate, None, manifest, {'tables': set(legacy.owned_keys(manifest))})
        self.assertEqual(result, snapshot)
        self.assertEqual([ (x['family'], x['name']) for x in take.call_args.args[0]['objects']],
                         [('inet', 'reviewed'), ('ip', 'vpn_s2s_nat'), ('ip6', 'v6_nat')])
        check.assert_called_once()

        rejected = copy.deepcopy(candidate)
        rejected['config']['CONTAINER_POLICY'] = 'restrict'
        with patch.object(engine, 'snapshot') as take:
            with self.assertRaises(PolicyError):
                legacy.prepare(rejected, None, manifest, {})
            take.assert_not_called()

    def test_candidate_batch_replaces_legacy_nat_names_with_handle_pinned_deletes(self):
        manifest = self.manifest()
        text = ('delete table inet reviewed\n'
                'delete table ip firewall_nat4\n'
                'delete table ip6 firewall_nat6\n'
                'delete table ip vpn_s2s_nat\n'
                'delete table ip6 v6_nat\n'
                'table inet reviewed { }\n'
                'table ip firewall_nat4 { }\n'
                'table ip6 firewall_nat6 { }\n')
        tx = engine.TransactionBatch([('nft', text)])
        legacy.pin_transaction(tx, manifest)
        rendered = tx[0][1]
        for key in ('delete table inet handle 21', 'destroy table inet reviewed',
                    'delete table ip handle 21', 'destroy table ip vpn_s2s_nat',
                    'delete table ip6 handle 21', 'destroy table ip6 v6_nat'):
            self.assertIn(key, rendered)
        self.assertIn('table ip firewall_nat4 { }', rendered)
        self.assertIn('table ip6 firewall_nat6 { }', rendered)
        self.assertEqual(rendered.count('delete table ip vpn_s2s_nat'), 0)

    def test_common_rollback_union_restores_old_nat_names_and_removes_candidate_names(self):
        manifest = self.manifest()
        snapshot = {'backend': 'nftables', 'objects': [
            {'family': 'inet', 'name': 'reviewed', 'text': 'table inet reviewed { }'},
            {'family': 'ip', 'name': 'vpn_s2s_nat', 'text': 'table ip vpn_s2s_nat { }'}]}
        candidate = {'backend': 'nftables', 'config': {}, 'objects': [
            {'family': 'inet', 'name': 'reviewed'}, {'family': 'ip', 'name': 'firewall_nat4'}]}
        pending = {'token': 'token', 'candidate': candidate, 'previous': None,
                   'snapshot': snapshot, 'legacy_manifest': manifest}

        class DummyStore:
            def get(self, key):
                return pending if key == 'pending' else None
            def delete(self, key):
                pass
            def put(self, key, value):
                pass

        live = {'tables': {('inet', 'reviewed'), ('ip', 'firewall_nat4')}}
        with patch.object(engine, 'inspect', return_value=live), \
                patch.object(engine, 'prepare', return_value=engine.TransactionBatch([('nft', 'tx')])) as prepare, \
                patch.object(engine, 'check'), patch.object(engine, 'execute'), \
                patch.object(boot, 'invalidate'):
            self.assertTrue(Store.rollback_locked(DummyStore(), 'token'))
        union = prepare.call_args.args[1]
        self.assertIn(snapshot, union)
        self.assertIn(candidate, union)

    def test_cli_accepts_repeated_nat_tables_but_only_for_inventory(self):
        from core.fw import parser
        args = parser().parse_args(['legacy-inventory', '--legacy-table', 'reviewed',
                                    '--legacy-nat-table', 'ip:vpn_s2s_nat',
                                    '--legacy-nat-table', 'ip6:v6_nat'])
        self.assertEqual(args.legacy_nat_table, ['ip:vpn_s2s_nat', 'ip6:v6_nat'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
