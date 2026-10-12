#!/usr/bin/python3
"""H2 normalized-state regressions; no kernel or host state access."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.compiler import generate
from core.config import Configuration, PolicyError
from core.fw import configuration, parser
from core.schema import migrate_policy
from core.store import Store


EMPTY_ACCESS = {'host': [], 'forward': [], 'containers': []}


class H2Tests(unittest.TestCase):
    def grant_file(self, directory):
        path = Path(directory) / 'access.json'
        path.write_text(json.dumps({
            'containers': [{
                'group': 'admin', 'source': '198.51.100.0/24',
                'destination': '10.20.0.0/24', 'protocol': 'tcp',
                'ports': '22', 'input': 'br-test', 'output': 'eth-test',
                'public_destination': '203.0.113.10', 'public_ports': '2222',
                'service': 'tcp_ssh',
            }],
        }))
        return path

    def make_policy(self, backend, host_services, acl_path):
        config = Configuration(
            backend, only=['tcp_ssh', 'http_https_protect'],
            path=None,
            overrides={
                'HOST_SERVICES': host_services,
                'CONTAINER_POLICY': 'restrict',
                'ROUTED_POLICY': 'drop',
                'ACCESS_POLICY': str(acl_path),
                'HTTP_HTTPS_PORTS': '8080',
            },
        )
        return generate(config)

    def test_canonical_config_accepts_legacy_once_and_omits_it(self):
        legacy = Configuration('nftables', overrides={'TYPECHAIN': '2'})
        self.assertEqual(legacy.values['HOST_SERVICES'], 'true')
        self.assertEqual(legacy.values['CONTAINER_POLICY'], 'restrict')
        self.assertNotIn('TYPECHAIN', legacy.values)

        modern = Configuration('nftables', overrides={
            'HOST_SERVICES': 'false', 'CONTAINER_POLICY': 'restrict',
        })
        self.assertEqual(modern.values['HOST_SERVICES'], 'false')
        self.assertNotIn('TYPECHAIN', modern.values)

        with self.assertRaisesRegex(PolicyError, 'Ambiguous TYPECHAIN'):
            Configuration('nftables', overrides={
                'TYPECHAIN': '0', 'HOST_SERVICES': 'false',
            })

    def test_vpn_server_and_sitetosite_defaults_stay_canonical_for_both_engines(self):
        for backend in ('nftables', 'iptables'):
            for module, overrides in (
                ('openvpn_server', {}),
                ('openvpn_sitetosite', {
                    'OVPNS2S_INTERFACE': 'tun0',
                    'OVPNS2S_LOCAL_SUBNETS': '192.0.2.0/24',
                    'OVPNS2S_REMOTE_SUBNETS': '198.51.100.0/24',
                }),
            ):
                with self.subTest(backend=backend, module=module):
                    config = Configuration(backend, only=[module], overrides=overrides)
                    policy = generate(config)
                    self.assertEqual(policy['schema'], 2)
                    self.assertNotIn('TYPECHAIN', config.values)
                    self.assertNotIn('TYPECHAIN', policy['config'])

    def test_compiler_rejects_noncanonical_bundle_before_apply_journal(self):
        config = Configuration('nftables', only=['openvpn_server'])
        # Simulate a future config/default regression. Generation is the
        # pre-apply boundary, before Store can write a pending recovery record.
        config.values['TYPECHAIN'] = '0'
        with self.assertRaisesRegex(PolicyError, 'Schema 2 policy must not contain TYPECHAIN'):
            generate(config)

    def test_schema1_preserves_effective_modern_dimensions_over_injected_typechain(self):
        old = {
            'schema': 1, 'backend': 'nftables', 'selected': ['nf_tcp_ssh'],
            'config': {
                'TYPECHAIN': '0', 'HOST_SERVICES': 'false',
                'CONTAINER_POLICY': 'restrict', 'ROUTED_POLICY': 'drop',
                'ACCESS_POLICY': '/path/that/must/not/be/reopened',
                'BYPASS_SOURCE_DOMAINS': '',
            },
            'access': {'host': [], 'forward': [], 'containers': []},
            'objects': [],
        }
        migrated = migrate_policy(old)
        self.assertEqual(migrated['schema'], 2)
        self.assertEqual(migrated['config']['HOST_SERVICES'], 'false')
        self.assertEqual(migrated['config']['CONTAINER_POLICY'], 'restrict')
        self.assertEqual(migrated['config']['ACCESS_POLICY'], '')
        self.assertNotIn('TYPECHAIN', migrated['config'])
        self.assertEqual(old['config']['TYPECHAIN'], '0')  # input was not mutated

    def test_schema1_translates_typechain_only_and_unknown_schema_fails_closed(self):
        old = {
            'schema': 1, 'backend': 'iptables', 'selected': ['ip_tcp_ssh'],
            'config': {'TYPECHAIN': '1', 'ACCESS_POLICY': '', 'BYPASS_SOURCE_DOMAINS': ''},
            'access': EMPTY_ACCESS, 'families': {'4': {}, '6': {}}, 'hooks': [],
        }
        migrated = migrate_policy(old)
        self.assertEqual(migrated['config']['HOST_SERVICES'], 'false')
        self.assertEqual(migrated['config']['CONTAINER_POLICY'], 'restrict')
        with self.assertRaisesRegex(PolicyError, 'Unsupported policy schema'):
            migrate_policy({**old, 'schema': 77})

    def test_modern_container_only_and_host_both_partial_remove_save_load_both_backends(self):
        for backend in ('nftables', 'iptables'):
            for host_services in ('false', 'true'):
                with self.subTest(backend=backend, host_services=host_services), tempfile.TemporaryDirectory() as d:
                    acl_path = self.grant_file(d)
                    policy = self.make_policy(backend, host_services, acl_path)
                    self.assertEqual(policy['schema'], 2)
                    self.assertEqual(policy['config']['HOST_SERVICES'], host_services)
                    self.assertEqual(policy['config']['CONTAINER_POLICY'], 'restrict')
                    self.assertNotIn('TYPECHAIN', policy['config'])
                    self.assertEqual(policy['config']['ACCESS_POLICY'], '')
                    self.assertEqual(len(policy['access']['containers']), 1)
                    acl_path.unlink()

                    args = parser().parse_args([
                        '--backend', backend, 'apply', '--partial', '--only', 'tcp_ssh',
                        '--set', 'SSH_RATE=30/minute',
                    ])
                    partial = configuration(args, previous=policy)
                    self.assertEqual(partial.values['HOST_SERVICES'], host_services)
                    self.assertEqual(partial.values['CONTAINER_POLICY'], 'restrict')
                    self.assertEqual(partial.access, policy['access'])
                    self.assertEqual(partial.values['SSH_RATE'], '30/min' if backend == 'iptables' else '30/minute')
                    self.assertNotIn('TYPECHAIN', partial.values)

                    remove_args = parser().parse_args([
                        '--backend', backend, 'apply', '--remove', 'http_https_protect',
                    ])
                    removed = configuration(remove_args, previous=policy)
                    self.assertEqual(set(removed.selected), {'nf_tcp_ssh' if backend == 'nftables' else 'ip_tcp_ssh'})
                    self.assertEqual(removed.access, policy['access'])
                    self.assertEqual(removed.values['HOST_SERVICES'], host_services)

                    # save/load storage preserves the parsed ACL and can be
                    # recompiled without the original policy file.
                    saved = generate(removed)
                    store = object.__new__(Store)
                    store.path = Path(d) / 'state'
                    store.path.mkdir()
                    with patch('core.store.trusted'):
                        store.put('persisted', saved)
                        loaded = store.get('persisted')
                    self.assertEqual(loaded, saved)
                    reloaded = Configuration.from_normalized(
                        backend, loaded['config'], loaded['selected'], loaded['access'],
                    )
                    self.assertEqual(generate(reloaded), loaded)

    def test_store_migrates_current_persisted_pending_in_memory_and_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            store = object.__new__(Store)
            store.path = Path(d)
            common = {
                'schema': 1, 'backend': 'nftables', 'selected': ['nf_tcp_ssh'],
                'config': {'TYPECHAIN': '0', 'HOST_SERVICES': 'false',
                           'CONTAINER_POLICY': 'restrict', 'ROUTED_POLICY': 'drop',
                           'ACCESS_POLICY': '/must/not/read', 'BYPASS_SOURCE_DOMAINS': ''},
                'access': {'host': [], 'forward': [], 'containers': []},
                'objects': [],
            }
            for name in ('current', 'persisted'):
                (store.path / f'{name}.json').write_text(json.dumps(common))
            snapshot = {'kernel': {'sentinel': ['keep', 1]}}
            pending = {
                'token': 'fixture-token', 'previous': common, 'candidate': common,
                'snapshot': snapshot,
            }
            pending_path = store.path / 'pending.json'
            pending_path.write_text(json.dumps(pending))
            raw_pending = pending_path.read_text()

            with patch('core.store.trusted'):
                current = store.get('current')
                persisted = store.get('persisted')
                in_pending = store.get('pending')
                store.put('current', current)
                store.put('persisted', persisted)
                round_trip = store.get('current')
            self.assertEqual(current['schema'], 2)
            self.assertEqual(persisted['schema'], 2)
            self.assertEqual(in_pending['previous']['schema'], 2)
            self.assertEqual(in_pending['candidate']['schema'], 2)
            self.assertEqual(in_pending['snapshot'], snapshot)
            self.assertEqual(pending_path.read_text(), raw_pending)
            self.assertEqual(round_trip['config']['HOST_SERVICES'], 'false')

    def test_normalized_state_never_resolves_dns_or_reopens_policy_file(self):
        access = {'host': [], 'forward': [], 'containers': []}
        config = {
            'HOST_SERVICES': 'false', 'CONTAINER_POLICY': 'restrict',
            'ROUTED_POLICY': 'drop', 'ACCESS_POLICY': '/not/accessible',
            'BYPASS_SOURCE_IPS': '', 'BYPASS_SOURCE_DOMAINS': '',
        }
        with patch('socket.getaddrinfo', side_effect=AssertionError('DNS must not run')):
            c = Configuration.from_normalized('nftables', config, ['tcp_ssh'], access)
        self.assertEqual(c.values['ACCESS_POLICY'], '')
        self.assertEqual(c.values['BYPASS_SOURCE_IPS'], '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
