#!/usr/bin/python3
"""Real transaction recovery regressions. Run only through isolated-run.sh."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import Configuration
from core.compiler import generate
from core import engine
from core.fw import main
from core.store import Store

assert os.readlink('/proc/self/ns/net') != os.environ['SUITE_HOST_NETNS'], 'Host network forbidden'
STATE = Path(os.environ['SUITE_TEST_STATE'])
FRONTEND = os.environ.get('SUITE_TEST_FRONTEND', 'auto')


def run(*argv):
    return subprocess.run(argv, text=True, capture_output=True, check=True).stdout


class TransactionFlowTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(STATE)
        with self.store.lock():
            self.store.rollback_locked()
            if self.store.get('current'):
                current = self.store.get('current')
                self.store.apply_locked({**current, 'disabled': True}, local=True)
            self.store.delete('persisted')

    def tearDown(self):
        with self.store.lock():
            self.store.rollback_locked()
            current = self.store.get('current')
            if current:
                self.store.apply_locked({**current, 'disabled': True}, local=True)
            self.store.delete('persisted')

    def candidate(self, backend):
        return generate(Configuration(backend, profiles=['host-minimal'], overrides={
            'SSH_PORT': '22222', 'IPTABLES_FRONTEND': FRONTEND,
        }, privileged=True))

    def assert_frontend(self, policy, live):
        if policy['backend'] == 'iptables' and FRONTEND in ('nft', 'legacy'):
            self.assertEqual(policy['config']['IPTABLES_FRONTEND'], FRONTEND)
            self.assertEqual(live['frontend'], FRONTEND)

    def test_disable_removes_owned_objects_when_docker_is_absent(self):
        for backend in ('nftables', 'iptables'):
            candidate = self.candidate(backend)
            with self.store.lock():
                self.store.apply_locked(candidate, local=True)
                current = self.store.get('current')
                live = engine.inspect(backend, current['config'].get('IPTABLES_FRONTEND', 'auto'))
                self.assert_frontend(current, live)
                # Model confirmed container grants while the Docker daemon and
                # its integration objects have disappeared.
                current['access']['containers'] = [{'service': 'tcp_ssh'}]
                if backend == 'nftables':
                    current['access']['forward'] = [{'service': 'synthetic-forward-grant'}]
                self.store.put('current', current)
                self.assertEqual(live['docker'], 'none')
            if backend == 'nftables':
                real_inspect = engine.inspect
                def synthetic_docker(*args, **kwargs):
                    result = real_inspect(*args, **kwargs)
                    result['docker'] = 'iptables'
                    return result
                with patch.object(engine, 'inspect', side_effect=synthetic_docker):
                    main(['--state-dir', str(STATE), '--backend', backend, 'disable', '--local'])
            else:
                main(['--state-dir', str(STATE), '--backend', backend, 'disable', '--local'])
            self.assertIsNone(self.store.get('current'))
            if backend == 'nftables':
                after = engine.inspect(backend)
                for obj in candidate['objects']:
                    self.assertNotIn((obj['family'], obj['name']), after['tables'])
            else:
                after = engine.inspect(backend, candidate['config'].get('IPTABLES_FRONTEND', 'auto'))
                for family, tables in candidate['families'].items():
                    parsed = engine.parse_save(after['iprules'][family])
                    for table, chains in tables.items():
                        for chain in chains:
                            self.assertNotIn(chain, parsed.get(table, {}).get('chains', {}))

    def test_load_restores_confirmed_state_when_kernel_objects_are_empty(self):
        for backend in ('nftables', 'iptables'):
            candidate = self.candidate(backend)
            with self.store.lock():
                self.store.apply_locked(candidate, local=True)
                current = self.store.get('current')
                live = engine.inspect(backend, current['config'].get('IPTABLES_FRONTEND', 'auto'))
                self.assert_frontend(current, live)
                self.store.put('persisted', current)
                emptying = engine.prepare(None, [current], live)
                engine.check(emptying)
                engine.execute(emptying)
                if backend == 'nftables':
                    now = engine.inspect(backend)
                    for obj in current['objects']:
                        self.assertNotIn((obj['family'], obj['name']), now['tables'])
                else:
                    now = engine.inspect(backend, current['config'].get('IPTABLES_FRONTEND', 'auto'))
                    for family, tables in current['families'].items():
                        parsed = engine.parse_save(now['iprules'][family])
                        for table, chains in tables.items():
                            for chain in chains:
                                self.assertNotIn(chain, parsed.get(table, {}).get('chains', {}))
            main(['--state-dir', str(STATE), '--backend', backend, 'load', '--local'])
            restored = self.store.get('current')
            self.assertIsNotNone(restored)
            if backend == 'nftables':
                now = engine.inspect(backend)
                for obj in restored['objects']:
                    self.assertIn((obj['family'], obj['name']), now['tables'])
            else:
                now = engine.inspect(backend, restored['config'].get('IPTABLES_FRONTEND', 'auto'))
                for family, tables in restored['families'].items():
                    parsed = engine.parse_save(now['iprules'][family])
                    for table, chains in tables.items():
                        self.assertTrue(set(chains) <= set(parsed.get(table, {}).get('chains', {})))
            main(['--state-dir', str(STATE), '--backend', backend, 'disable', '--local'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
