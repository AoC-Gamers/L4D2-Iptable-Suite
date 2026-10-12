#!/usr/bin/python3
"""Transaction edge regressions; mocked I/O only, no host firewall access."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import engine
from core.config import PolicyError
from core.fw import configuration, parser
from core.store import Store


class TransactionTests(unittest.TestCase):
    def test_disable_does_not_require_docker_discovery(self):
        policy = {
            'backend': 'nftables', 'disabled': True,
            'config': {'DOCKER_BACKEND': 'auto'},
            'access': {'containers': [{'service': 'http_https_protect'}], 'forward': [{}]},
            'objects': [],
        }
        engine.preflight(policy, {'backend': 'nftables', 'objects': []},
                         {'docker': 'iptables', 'tables': []})

    def test_empty_kernel_allows_restore_but_moved_hook_still_fails(self):
        previous = {
            'backend': 'iptables',
            'versions': {'4': 'iptables v1.8.10 (nf_tables)', '6': 'ip6tables v1.8.10 (nf_tables)'},
            'families': {'4': {'filter': {'L4S_INPUT': {}}}, '6': {'filter': {'L4S_INPUT': {}}}},
            'hooks': [['filter', 'INPUT', 'L4S_INPUT']],
        }
        policy = {
            'backend': 'iptables', 'config': {}, 'access': {'containers': [], 'forward': []},
            'families': previous['families'], 'hooks': previous['hooks'],
        }
        empty = {'versions': dict(previous['versions']), 'iprules': {'4': '', '6': ''}, 'docker': 'none'}
        engine.preflight(policy, previous, empty)
        moved = {
            **empty,
            'iprules': {
                '4': '*filter\n:INPUT ACCEPT [0:0]\n:L4S_INPUT - [0:0]\n-A INPUT -j OTHER\n-A INPUT -m comment --comment l4d2-suite:integration -j L4S_INPUT\nCOMMIT\n',
                '6': '',
            },
        }
        with self.assertRaisesRegex(PolicyError, 'integration missing or no longer first'):
            engine.preflight(policy, previous, moved)

    def test_disable_allows_version_drift_but_active_apply_rejects_it(self):
        previous = {
            'backend': 'iptables', 'config': {'IPTABLES_FRONTEND': 'nft'},
            'versions': {'4': 'iptables v1.8.9 (nf_tables)', '6': 'ip6tables v1.8.9 (nf_tables)'},
            'families': {'4': {}, '6': {}}, 'hooks': [],
        }
        live = {'frontend': 'nft', 'versions': {'4': 'iptables v1.8.10 (nf_tables)', '6': 'ip6tables v1.8.10 (nf_tables)'}, 'iprules': {'4': '', '6': ''}, 'docker': 'none'}
        disabled = {'backend': 'iptables', 'disabled': True, 'config': {}, 'access': {'containers': [], 'forward': []}, 'families': {'4': {}, '6': {}}, 'hooks': []}
        engine.preflight(disabled, previous, live)
        active = {**disabled, 'disabled': False}
        with self.assertRaisesRegex(PolicyError, 'backend/version changed'):
            engine.preflight(active, previous, live)
        with self.assertRaisesRegex(PolicyError, 'frontend changed'):
            engine.preflight(disabled, previous, {**live, 'frontend': 'legacy'})

    def test_remove_can_replace_acl_without_ignoring_override(self):
        with tempfile.TemporaryDirectory() as d:
            acl = Path(d) / 'empty.json'
            acl.write_text(json.dumps({'host': [], 'forward': [], 'containers': []}))
            previous = {
                'config': {'ACCESS_POLICY': '', 'PROFILE': 'web'},
                'selected': ['tcp_ssh', 'http_https_protect'],
                'access': {'host': [], 'forward': [], 'containers': [{'service': 'http_https_protect'}]},
            }
            args = parser().parse_args(['--backend', 'nftables', 'apply', '--remove', 'http_https_protect', '--set', f'ACCESS_POLICY={acl}'])
            candidate = configuration(args, previous=previous)
            self.assertNotIn('http_https_protect', candidate.selected)
            self.assertEqual(candidate.access, {'host': [], 'forward': [], 'containers': []})

    def test_arm_failure_discards_journal_without_netfilter_write(self):
        with tempfile.TemporaryDirectory() as d:
            s = object.__new__(Store)
            s.path = Path(d)
            candidate = {'backend': 'nftables', 'config': {}, 'objects': [], 'access': {'containers': [], 'forward': []}}
            with patch('core.store.trusted'), patch.object(engine, 'inspect', return_value={'tables': [], 'versions': {}, 'iprules': {}, 'docker': 'none'}), \
                    patch.object(engine, 'preflight'), patch.object(engine, 'snapshot', return_value=None), \
                    patch.object(engine, 'prepare', return_value=engine.TransactionBatch([('nft', '')])), \
                    patch.object(engine, 'check'), patch.object(engine, 'execute') as execute, \
                    patch.object(s, 'arm', side_effect=RuntimeError('timer unavailable')):
                with self.assertRaisesRegex(RuntimeError, 'timer unavailable'):
                    with s.lock():
                        s.apply_locked(candidate, timeout=2)
                execute.assert_not_called()
                self.assertIsNone(s.get('pending'))

    def test_apply_deadline_passed_during_execution_restores(self):
        with tempfile.TemporaryDirectory() as d:
            s = object.__new__(Store)
            s.path = Path(d)
            candidate = {'backend': 'nftables', 'config': {}, 'objects': [], 'access': {'containers': [], 'forward': []}}
            rollback = []
            with patch('core.store.trusted'), patch.object(engine, 'inspect', return_value={'tables': [], 'versions': {}, 'iprules': {}, 'docker': 'none'}), \
                    patch.object(engine, 'preflight'), patch.object(engine, 'snapshot', return_value=None), \
                    patch.object(engine, 'prepare', return_value=engine.TransactionBatch([('nft', '')])), \
                    patch.object(engine, 'check'), patch.object(engine, 'execute', side_effect=lambda tx: time.sleep(2.1)), \
                    patch.object(s, 'rollback_locked', side_effect=lambda token=None, expired_only=False: (rollback.append(token) if token else None) or True):
                with self.assertRaisesRegex(PolicyError, 'exceeded its confirmation deadline'):
                    with s.lock():
                        s.apply_locked(candidate, timeout=2, local=True)
            self.assertEqual(len(rollback), 1)

    def test_restore_wait_budget_cannot_outlive_apply_deadline(self):
        with patch.object(engine.subprocess, 'run') as run_command:
            run_command.return_value.returncode = 0
            run_command.return_value.stderr = ''
            with self.assertRaisesRegex(PolicyError, 'Insufficient deadline budget'):
                engine.command(['iptables-nft-restore', '--wait', '10', '--noflush'], text='*filter\nCOMMIT\n', deadline=time.monotonic() + 0.5)
            run_command.assert_not_called()
            engine.command(['iptables-nft-restore', '--wait', '10', '--noflush'], text='*filter\nCOMMIT\n', deadline=time.monotonic() + 3)
            argv = run_command.call_args.args[0]
            self.assertEqual(argv[argv.index('--wait') + 1], '2')

    def test_command_timeout_is_bounded_by_apply_deadline(self):
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            engine.command(['/usr/bin/python3', '-c', 'import time; time.sleep(2)'], deadline=started + 0.2)
        self.assertLess(time.monotonic() - started, 1.5)


if __name__ == '__main__':
    unittest.main()
