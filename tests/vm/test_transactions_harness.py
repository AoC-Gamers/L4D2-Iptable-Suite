#!/usr/bin/python3
"""No-Netfilter regression for the VM harness's intentional lock window."""
import contextlib
import importlib.util
import signal
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name('transactions.py')
REPO_ROOT = MODULE_PATH.parents[2]
sys.path.insert(0, str(REPO_ROOT))
SPEC = importlib.util.spec_from_file_location('vm_transactions', MODULE_PATH)
transactions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transactions)


class FakeStore:
    def __init__(self):
        self.writer_held_by_worker = False
        self.values = {}
        self.lock_attempted_while_worker_held = False

    @contextlib.contextmanager
    def lock(self):
        if self.writer_held_by_worker:
            self.lock_attempted_while_worker_held = True
            raise AssertionError('harness blocked on writer lock held by SIGKILL worker')
        yield

    def get(self, key):
        return self.values.get(key)

    def put(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


class FakeChild:
    pid = 424242

    def poll(self):
        return None

    def kill(self):
        raise AssertionError('test unexpectedly killed the fake worker')


class TransactionHarnessLockTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        current = {'backend': 'nftables', 'config': {'SSH_BURST': '21'}, 'objects': []}
        self.baseline = transactions.canonical_digest(current)
        self.store.values.update({
            'current': current,
            'pending': None,
            transactions.MANIFEST: {'phase': 'fresh-ssh-confirmed'},
        })
        pending = {
            'token': 'a' * 32,
            'deadline_monotonic': 100.0,
            'previous': current,
            'candidate': {'backend': 'nftables', 'config': {'SSH_BURST': '23'}, 'objects': []},
        }
        self.pending = pending
        self.committed = {'pid': FakeChild.pid, 'token': pending['token'],
                          'deadline_monotonic': pending['deadline_monotonic']}

    def test_post_commit_worker_can_be_manifested_and_killed_without_lock_deadlock(self):
        def spawn(*args, **kwargs):
            self.store.values['pending'] = self.pending
            self.store.values['vm-worker-committed'] = self.committed
            self.store.writer_held_by_worker = True
            return FakeChild()

        def proc_cmdline(path):
            if str(path) == f'/proc/{FakeChild.pid}/cmdline':
                return f'/usr/bin/python3\0-I\0{MODULE_PATH.resolve()}\0_worker\0'.encode()
            raise AssertionError(f'unexpected /proc read: {path}')

        killed = []

        def fake_kill(pid, sig):
            killed.append((pid, sig))
            if sig == signal.SIGKILL:
                self.store.writer_held_by_worker = False

        with (
            patch.object(transactions, 'store', return_value=self.store),
            patch.object(transactions.subprocess, 'Popen', side_effect=spawn),
            patch.object(transactions, 'timer_state', return_value='l4d2-rollback.timer'),
            patch.object(transactions, 'policy_live', return_value={}),
            patch.object(transactions.Path, 'read_bytes', proc_cmdline),
            patch.object(transactions.os, 'kill', side_effect=fake_kill),
        ):
            transactions.launch_kill_worker()
            self.assertEqual(self.store.values[transactions.MANIFEST]['phase'], 'worker-committed')
            transactions.kill_committed_worker()

        self.assertFalse(self.store.lock_attempted_while_worker_held)
        self.assertEqual(self.store.values[transactions.MANIFEST]['phase'], 'worker-killed')
        self.assertEqual(killed, [(FakeChild.pid, 0), (FakeChild.pid, signal.SIGKILL)])

    def test_legacy_foreign_signature_normalizes_counters_only(self):
        from core import engine
        policy = {
            'backend': 'iptables',
            'config': {'IPTABLES_FRONTEND': 'legacy'},
            'families': {'4': {'filter': {'L4S_OWN': []}}},
            'hooks': [['filter', 'INPUT', 'L4S_OWN']],
        }
        save = '''*filter
:INPUT ACCEPT [0:0]
:FORWARD DROP [0:0]
:OUTPUT ACCEPT [0:0]
:FOREIGN - [0:0]
:L4S_OWN - [0:0]
-A INPUT -j FOREIGN
-A INPUT -m comment --comment l4d2-suite:integration -j L4S_OWN
-A FOREIGN -j ACCEPT
-A L4S_OWN -j DROP
COMMIT
'''

        def signature(ipv4_save):
            live = {'frontend': 'legacy', 'iprules': {'4': ipv4_save, '6': '*filter\nCOMMIT\n'}}
            with patch.object(engine, 'inspect', return_value=live):
                return transactions.foreign_iptables_signature(policy)

        before = signature(save)
        counters_changed = save.replace(':INPUT ACCEPT [0:0]', ':INPUT ACCEPT [14:920]')
        counters_changed = counters_changed.replace(':FORWARD DROP [0:0]', ':FORWARD DROP [3:61]')
        counters_changed = counters_changed.replace(':OUTPUT ACCEPT [0:0]', ':OUTPUT ACCEPT [8:700]')
        counters_changed = counters_changed.replace(':FOREIGN - [0:0]', ':FOREIGN - [5:500]')
        self.assertEqual(before['digest'], signature(counters_changed)['digest'])

        changed_builtin_policy = save.replace(':FORWARD DROP [0:0]', ':FORWARD ACCEPT [0:0]')
        self.assertNotEqual(before['digest'], signature(changed_builtin_policy)['digest'])

        modified_foreign_rule = save.replace('-A FOREIGN -j ACCEPT', '-A FOREIGN -j DROP')
        self.assertNotEqual(before['digest'], signature(modified_foreign_rule)['digest'])

        # The exact suite hook is excluded; a different target remains visible
        # as an unowned rule and changes the signature.
        self.assertEqual(before['chains'], 4)
        self.assertEqual(before['rules'], 2)
        changed_suite_hook = save.replace(
            '-A INPUT -m comment --comment l4d2-suite:integration -j L4S_OWN',
            '-A INPUT -m comment --comment l4d2-suite:integration -j L4S_OTHER',
        )
        self.assertNotEqual(before['digest'], signature(changed_suite_hook)['digest'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
