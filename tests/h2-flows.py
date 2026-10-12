#!/usr/bin/python3
"""Real H2 apply/save/load/partial/remove and legacy-state flows.

Run only through tests/isolated-run.sh. Uses an iptables-shaped Docker fixture,
not a Docker daemon; Netfilter changes stay inside the disposable namespace.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location('integration', ROOT / 'tests/integration.py')
integration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(integration)
from core.fw import main
from core.config import PolicyError


STATE = Path(os.environ['SUITE_TEST_STATE'])
BACKEND_NAMES = {'nftables': 'nf_http_https_protect', 'iptables': 'ip_http_https_protect'}


class H2KernelFlows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.readlink('/proc/self/ns/net') == os.environ['SUITE_HOST_NETNS']:
            raise AssertionError('Host network namespace is forbidden')
        integration.KernelTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        integration.KernelTests.tearDownClass()

    def setUp(self):
        self.fixture = integration.KernelTests()
        self.fixture_active = False
        self.docker = False

    def tearDown(self):
        if not self.fixture_active:
            return
        try:
            self.fixture.disable()
        finally:
            try:
                if self.docker:
                    self.fixture.docker_fixture('iptables', False)
            finally:
                self.fixture.tearDown()

    def grants(self):
        return {'containers': [
            {
                'group': 'web',
                'source': '10.20.0.0/24' if family == 4 else 'fd00:20::/64',
                'destination': '10.30.0.2/32' if family == 4 else 'fd00:30::2/128',
                'input': 'wan0',
                'output': 'lan0',
                'public_destination': '10.20.0.1/32' if family == 4 else 'fd00:20::1/128',
                'protocol': 'tcp',
                'ports': '18443',
                'public_ports': '18080',
                'service': 'http_https_protect',
            }
            for family in (4, 6)
        ]}

    def invoke(self, backend, operation, *args):
        return main(['--state-dir', str(STATE), '--backend', backend, operation, *args])

    def apply(self, backend, host_services, access_path, *args, local=True):
        options = [
            '--profile', 'web',
            '--set', f'IPTABLES_FRONTEND={integration.FRONTEND}',
            '--set', f'HOST_SERVICES={host_services}',
            '--set', 'CONTAINER_POLICY=restrict',
            '--set', f'ACCESS_POLICY={access_path}',
            '--set', 'SSH_PORT=22222',
            '--set', 'HTTP_HTTPS_PORTS=18080',
            *args,
        ]
        if local:
            options.append('--local')
        return self.invoke(backend, 'apply', *options)

    def assert_traffic(self, backend, host_services, *, ssh=True):
        for family in (4, 6):
            opened = self.can_connect(18080, family)
            self.assertTrue(opened, (backend, family, 'published container TCP'))
            self.assertFalse(self.fixture.peer.udp(18080, [b'udp-not-granted'], family)[0],
                             (backend, family, 'UDP must remain denied'))
            self.assertFalse(
                self.fixture.peer.tcp(18443, family,
                                      dest='10.30.0.2' if family == 4 else 'fd00:30::2'),
                (backend, family, 'direct container port must remain denied'),
            )
            expected_ssh = host_services == 'true' and ssh
            self.assertEqual(self.can_connect(22222, family) if expected_ssh else self.fixture.peer.tcp(22222, family),
                             expected_ssh, (backend, family, 'host SSH scope'))

    def can_connect(self, port, family):
        # The first IPv6 flow may pay the veth neighbor-discovery delay.
        for attempt in range(4):
            if self.fixture.peer.tcp(port, family):
                return True
            if attempt < 3:
                time.sleep(0.1)
        return False

    @staticmethod
    def schema1(bundle):
        legacy = copy.deepcopy(bundle)
        legacy['schema'] = 1
        # Old injected TYPECHAIN=0 can coexist with modern effective fields.
        legacy['config']['TYPECHAIN'] = '0'
        legacy['config']['ACCESS_POLICY'] = '/must/not/be/reopened'
        return legacy

    def test_apply_save_load_partial_remove_and_schema1_recovery(self):
        for backend in ('nftables', 'iptables'):
            for host_services in ('false', 'true'):
                with self.subTest(backend=backend, host_services=host_services):
                    self.fixture.setUp()
                    self.fixture_active = True
                    self.docker = False
                    try:
                        self.fixture.docker_fixture('iptables')
                        self.docker = True
                        acl_path = STATE / f'h2-access-{backend}-{host_services}.json'
                        acl_path.write_text(json.dumps(self.grants()))
                        acl_path.chmod(0o600)

                        self.apply(backend, host_services, acl_path)
                        current = self.fixture.store.get('current')
                        self.assertEqual(current['schema'], 2)
                        self.assertNotIn('TYPECHAIN', current['config'])
                        self.assertEqual(current['config']['HOST_SERVICES'], host_services)
                        self.assertEqual(current['config']['CONTAINER_POLICY'], 'restrict')
                        self.assertEqual(len(current['access']['containers']), 2)
                        self.assert_traffic(backend, host_services)

                        # Removing a module still referenced by the confirmed
                        # ACL must fail before any rules or durable state move.
                        current_path = STATE / 'current.json'
                        pending_path = STATE / 'pending.json'
                        current_before = current_path.read_bytes()
                        pending_before = pending_path.read_bytes() if pending_path.exists() else None
                        rules_before = self.fixture.rules(backend)
                        with self.assertRaisesRegex(PolicyError, 'Remove container grants before removing their service'):
                            self.invoke(backend, 'apply', '--remove', 'http_https_protect', '--local')
                        self.assertEqual(current_path.read_bytes(), current_before)
                        self.assertEqual(pending_path.read_bytes() if pending_path.exists() else None,
                                         pending_before)
                        self.assertEqual(self.fixture.rules(backend), rules_before)

                        self.invoke(backend, 'save')
                        persisted = self.fixture.store.get('persisted')
                        self.assertEqual(persisted['schema'], 2)
                        self.invoke(backend, 'disable', '--local')
                        self.assertIsNone(self.fixture.store.get('current'))
                        self.invoke(backend, 'load', '--local')
                        self.assert_traffic(backend, host_services)

                        self.invoke(backend, 'apply', '--partial', '--only', 'http_https_protect',
                                    '--set', 'HTTP_HTTPS_RATE=25/minute', '--local')
                        partial = self.fixture.store.get('current')
                        self.assertEqual(partial['config']['HOST_SERVICES'], host_services)
                        self.assertEqual(partial['access'], persisted['access'])
                        self.assert_traffic(backend, host_services)

                        self.invoke(backend, 'apply', '--remove', 'tcp_ssh', '--local')
                        removed = self.fixture.store.get('current')
                        self.assertEqual(removed['selected'], [BACKEND_NAMES[backend]])
                        self.assertEqual(removed['access'], persisted['access'])
                        self.assert_traffic(backend, host_services, ssh=False)
                        self.invoke(backend, 'save')

                        # Create a live pending transaction, then downgrade only
                        # the bundle envelopes. Its kernel snapshot is retained.
                        self.invoke(backend, 'apply', '--partial', '--only', 'http_https_protect',
                                    '--set', 'HTTP_HTTPS_RATE=26/minute', '--timeout', '120',
                                    '--watchdog', 'process')
                        pending = self.fixture.store.get('pending')
                        self.assertIsNotNone(pending)
                        token = pending['token']
                        pending['previous'] = self.schema1(pending['previous'])
                        pending['candidate'] = self.schema1(pending['candidate'])
                        original_snapshot = copy.deepcopy(pending['snapshot'])
                        current = self.schema1(self.fixture.store.get('current'))
                        persisted = self.schema1(self.fixture.store.get('persisted'))
                        legacy_pending = json.dumps(pending, sort_keys=True).encode() + b'\n'
                        (STATE / 'current.json').write_text(json.dumps(current))
                        (STATE / 'persisted.json').write_text(json.dumps(persisted))
                        (STATE / 'pending.json').write_bytes(legacy_pending)

                        migrated_current = self.fixture.store.get('current')
                        migrated_persisted = self.fixture.store.get('persisted')
                        migrated_pending = self.fixture.store.get('pending')
                        self.assertEqual(migrated_current['schema'], 2)
                        self.assertEqual(migrated_persisted['schema'], 2)
                        self.assertEqual(migrated_pending['previous']['schema'], 2)
                        self.assertEqual(migrated_pending['candidate']['schema'], 2)
                        self.assertEqual(migrated_current['access'], current['access'])
                        self.assertEqual(migrated_pending['previous']['access'], current['access'])
                        self.assertEqual(migrated_pending['snapshot'], original_snapshot)
                        self.assertEqual((STATE / 'pending.json').read_bytes(), legacy_pending,
                                         'in-memory migration must not rewrite the pending journal')

                        self.invoke(backend, 'rollback', '--token', token)
                        recovered = self.fixture.store.get('current')
                        self.assertEqual(recovered['schema'], 2)
                        self.assertEqual(recovered['access'], current['access'])
                        self.assertIsNone(self.fixture.store.get('pending'))
                        self.assert_traffic(backend, host_services, ssh=False)
                        self.invoke(backend, 'load', '--local')
                        self.invoke(backend, 'save')
                        self.assertEqual(self.fixture.store.get('persisted')['schema'], 2)
                        self.assert_traffic(backend, host_services, ssh=False)

                        # A coherent ACL update removes the HTTP grant before
                        # removing the only remaining owner of that service.
                        empty_acl = STATE / f'h2-empty-access-{backend}-{host_services}.json'
                        empty_acl.write_text(json.dumps({'containers': []}))
                        empty_acl.chmod(0o600)
                        self.apply(backend, host_services, empty_acl)
                        self.invoke(backend, 'apply', '--remove', 'http_https_protect',
                                    '--set', f'ACCESS_POLICY={empty_acl}', '--local')
                        final = self.fixture.store.get('current')
                        self.assertEqual(final['selected'],
                                         ['nf_tcp_ssh' if backend == 'nftables' else 'ip_tcp_ssh'])
                        self.assertEqual(final['access']['containers'], [])
                        self.assertIsNone(self.fixture.store.get('pending'))
                    finally:
                        self.fixture.disable()
                        if self.docker:
                            self.fixture.docker_fixture('iptables', False)
                            self.docker = False
                        self.fixture.tearDown()
                        self.fixture_active = False


if __name__ == '__main__':
    unittest.main(verbosity=2)
