#!/usr/bin/python3
"""Isolated adversarial policy flows; run only through isolated-run.sh."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('integration', ROOT / 'tests/integration.py')
integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integration)

from core.compiler import generate
from core.config import Configuration, PolicyError


class PolicyFlowTests(unittest.TestCase):
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
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def configuration(self, backend, selected, **overrides):
        values = {'IPTABLES_FRONTEND': integration.FRONTEND, **overrides}
        return Configuration(backend, only=selected, overrides=values, privileged=True)

    def apply(self, backend, selected, **overrides):
        candidate = generate(self.configuration(backend, selected, **overrides))
        with self.fixture.store.lock():
            self.fixture.store.apply_locked(candidate, local=True)
        return candidate

    def add_source_addresses(self):
        for suffix in range(4, 28):
            self.fixture.peer.cmd('ip', 'addr', 'add', f'10.20.0.{suffix}/24', 'dev', 'wan0p')

    def test_hashlimit_capacity_blocks_new_sources_at_configured_limit(self):
        self.add_source_addresses()
        for backend in ('nftables', 'iptables'):
            for module, port in (('http_https_protect', 18080), ('l4d2_tcp_protect', 18081)):
                with self.subTest(backend=backend, module=module):
                    self.fixture.disable()
                    selected = ['tcp_ssh', module]
                    overrides = {'SSH_PORT': '22222', 'STATE_CAPACITY': '16'}
                    if module == 'http_https_protect':
                        overrides.update({'HTTP_HTTPS_PORTS': str(port), 'HTTP_HTTPS_RATE': '600/minute', 'HTTP_HTTPS_BURST': '200'})
                    else:
                        overrides['L4D2_GAMESERVER_TCP_PORTS'] = str(port)
                    self.apply(backend, selected, **overrides)
                    observed = [
                        self.fixture.peer.tcp(port, source=f'10.20.0.{suffix}')
                        for suffix in range(4, 28)
                    ]
                    self.assertEqual(sum(observed), 16, (backend, module, observed))
                    self.assertEqual(observed[:16], [True] * 16)
                    self.assertEqual(observed[16:], [False] * 8)

    def test_container_grant_and_opposite_protocol_bypass_are_scoped(self):
        for backend in ('nftables', 'iptables'):
            for protocol in ('udp', 'tcp'):
                with self.subTest(backend=backend, protocol=protocol):
                    self.fixture.disable()
                    self.fixture.docker_fixture('iptables')
                    try:
                        grant = {
                            'group': 'web', 'source': '10.20.0.2/32', 'destination': '10.30.0.2/32',
                            'input': 'wan0', 'output': 'lan0', 'protocol': protocol, 'ports': '18443',
                            'public_ports': '18080', 'public_destination': '10.20.0.1/32',
                            'service': 'allowlist_ports',
                        }
                        policy_path = integration.STATE / 'audit-access.json'
                        policy_path.write_text(json.dumps({'containers': [grant]}))
                        policy_path.chmod(0o600)
                        self.apply(
                            backend, ['allowlist_ports'], HOST_SERVICES='false',
                            CONTAINER_POLICY='restrict', ACCESS_POLICY=str(policy_path),
                            BYPASS_TCP_PORTS='18443', BYPASS_UDP_PORTS='18443',
                        )
                        self.assertFalse(self.fixture.peer.tcp(22222), (backend, protocol, 'host service leaked'))
                        udp = self.fixture.peer.udp(18080, [b'probe'])[0]
                        tcp = self.fixture.peer.tcp(18080)
                        self.assertEqual((tcp, udp), (protocol == 'tcp', protocol == 'udp'))
                    finally:
                        self.fixture.disable()
                        self.fixture.docker_fixture('iptables', False)

    def test_same_service_grants_keep_source_scopes_independent(self):
        grants = [
            {
                'group': 'web', 'source': f'{source}/32', 'destination': '10.30.0.2/32',
                'input': 'wan0', 'output': 'lan0', 'protocol': 'tcp', 'ports': '18443',
                'public_ports': '18080', 'public_destination': '10.20.0.1/32',
                'service': 'http_https_protect',
            }
            for source in ('10.20.0.2', '10.20.0.3')
        ]
        for backend in ('nftables', 'iptables'):
            self.fixture.disable()
            self.fixture.docker_fixture('iptables')
            try:
                policy_path = integration.STATE / 'audit-access.json'
                policy_path.write_text(json.dumps({'containers': grants}))
                policy_path.chmod(0o600)
                self.apply(
                    backend, ['http_https_protect'], HOST_SERVICES='false',
                    CONTAINER_POLICY='restrict', ACCESS_POLICY=str(policy_path),
                )
                outcome = [
                    self.fixture.peer.tcp(18080, source=f'10.20.0.{suffix}')
                    for suffix in (2, 3, 4)
                ]
                self.assertEqual(outcome, [True, True, False], (backend, outcome))
            finally:
                self.fixture.disable()
                self.fixture.docker_fixture('iptables', False)

    def test_meter_timeouts_derive_and_reject_explicit_empty_values(self):
        selected = ['tcp_ssh', 'http_https_protect']
        for backend in ('nftables', 'iptables'):
            config = self.configuration(
                backend, selected, SSH_RATE='1/hour', SSH_BURST='20',
                HTTP_HTTPS_RATE='1/hour', HTTP_HTTPS_BURST='10',
            )
            candidate = generate(config)
            self.assertEqual(config.values['SSH_METER_TIMEOUT'], '72000s')
            self.assertEqual(config.values['NFT_HTTP_HTTPS_METER_TIMEOUT'], '36000s')
            if backend == 'nftables':
                text = '\n'.join(obj['text'] for obj in candidate['objects'])
                self.assertIn('timeout 72000s', text)
                self.assertIn('timeout 36000s', text)
            else:
                rules = [
                    rule for tables in candidate['families'].values()
                    for chains in tables.values() for entries in chains.values()
                    for rule in entries
                ]
                flattened = ' '.join(str(rule) for rule in rules)
                self.assertIn('72000000', flattened)
                self.assertIn('36000000', flattened)
            for key in ('SSH_METER_TIMEOUT', 'NFT_HTTP_HTTPS_METER_TIMEOUT'):
                with self.subTest(backend=backend, key=key):
                    with self.assertRaises(PolicyError):
                        self.configuration(backend, selected, **{key: ''})


if __name__ == '__main__':
    unittest.main(verbosity=2)
