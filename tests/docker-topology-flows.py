#!/usr/bin/python3
"""H1 real-Netfilter topology and packet regressions; isolated namespace only."""
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
from core.config import PolicyError


class DockerTopologyFlows(unittest.TestCase):
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
        self.access_path = integration.STATE / 'h1-access.json'
        self.grant = {
            'group': 'h1-web', 'source': '10.20.0.2/32', 'destination': '10.30.0.2/32',
            'input': 'wan0', 'output': 'lan0', 'protocol': 'tcp', 'ports': '18443',
            'public_destination': '10.20.0.1/32', 'public_ports': '18080',
            'service': 'http_https_protect',
        }
        self.access_path.write_text(json.dumps({'containers': [self.grant]}))
        self.access_path.chmod(0o600)

    def tearDown(self):
        self.fixture.disable()
        self.access_path.unlink(missing_ok=True)
        self.fixture.tearDown()

    def apply(self):
        self.fixture.apply(
            'iptables', 'web', HOST_SERVICES='false', CONTAINER_POLICY='restrict',
            DOCKER_BACKEND='iptables', ACCESS_POLICY=str(self.access_path),
        )

    def test_valid_topology_routes_only_authorized_source(self):
        self.fixture.docker_fixture('iptables')
        try:
            self.apply()
            self.assertTrue(self.fixture.peer.tcp(18080, source='10.20.0.2'))
            self.assertFalse(self.fixture.peer.tcp(18080, source='10.20.0.3'))
            for family in ('4', '6'):
                report = integration.engine.docker_forward_diagnostic(
                    {'iprules': {f: integration.run(integration.engine.ipcmd(f, '-save')) for f in ('4', '6')}},
                    (family,), self.fixture.store.get('current'),
                )
                self.assertTrue(report['ok'], report)
        finally:
            self.fixture.disable()
            self.fixture.docker_fixture('iptables', False)

    def test_forward_accept_before_docker_is_rejected_without_writes(self):
        self.fixture.docker_fixture('iptables')
        try:
            for family in (4, 6):
                integration.run(integration.engine.ipcmd(family), '-I', 'FORWARD', '1', '-j', 'ACCEPT')
            before = self.fixture.rules('iptables')
            with self.assertRaisesRegex(PolicyError, 'FORWARD rule 2 jumps to DOCKER-USER'):
                self.apply()
            self.assertEqual(self.fixture.rules('iptables'), before)
        finally:
            for family in (4, 6):
                integration.run(integration.engine.ipcmd(family), '-D', 'FORWARD', '-j', 'ACCEPT')
            self.fixture.docker_fixture('iptables', False)

    def test_moved_suite_hook_is_rejected_without_reordering_foreign_rule(self):
        self.fixture.docker_fixture('iptables')
        try:
            self.apply()
            for family in (4, 6):
                integration.run(integration.engine.ipcmd(family), '-I', 'DOCKER-USER', '1', '-j', 'ACCEPT')
            before = self.fixture.rules('iptables')
            with self.assertRaisesRegex(PolicyError, 'suite hook'):
                self.apply()
            self.assertEqual(self.fixture.rules('iptables'), before)
        finally:
            for family in (4, 6):
                integration.run(integration.engine.ipcmd(family), '-D', 'DOCKER-USER', '-j', 'ACCEPT')
            self.fixture.disable()
            self.fixture.docker_fixture('iptables', False)

    def test_disable_remains_available_after_docker_chains_disappear(self):
        self.fixture.docker_fixture('iptables')
        try:
            self.apply()
            self.fixture.docker_fixture('iptables', False)
            self.fixture.disable()
            self.assertIsNone(self.fixture.store.get('current'))
            for family in (4, 6):
                saved = integration.run(integration.engine.ipcmd(family, '-save'))
                self.assertNotIn('L4S_DOCKER', saved)
        finally:
            self.fixture.disable()


if __name__ == '__main__':
    unittest.main(verbosity=2)
