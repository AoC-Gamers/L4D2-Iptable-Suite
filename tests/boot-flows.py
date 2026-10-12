#!/usr/bin/python3
"""Real early-barrier packets and empty rollback; isolated namespaces only."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('integration', ROOT / 'tests/integration.py')
i = importlib.util.module_from_spec(spec)
spec.loader.exec_module(i)
from core import boot
from core.config import PolicyError


def udp(peer, payload, family):
    source = '10.20.0.2' if family == 4 else 'fd00:20::2'
    destination = '10.20.0.1' if family == 4 else 'fd00:20::1'
    code = f'''import socket
s=socket.socket(socket.AF_INET{6 if family == 6 else ''}, socket.SOCK_DGRAM)
s.settimeout(.3); s.bind(({source!r},0)); s.sendto({payload!r},({destination!r},27015))
try: print(s.recvfrom(1024)[0] == {payload!r})
except OSError: print(False)
finally: s.close()
'''
    return peer.python(code).strip() == 'True'


class BootFlows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        i.KernelTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        i.KernelTests.tearDownClass()

    def test_guard_dual_stack_recovery_and_empty_rollback(self):
        for backend in ('nftables', 'iptables'):
            with self.subTest(backend=backend):
                f = i.KernelTests()
                f.setUp()
                try:
                    acl = i.STATE / 'boot-access.json'
                    rows = []
                    grants = []
                    for source, destination in (('10.20.0.2/32', '10.20.0.1/32'), ('fd00:20::2/128', 'fd00:20::1/128')):
                        rows.append({'source': source, 'destination': destination, 'input': 'wan0', 'ports': '22222'})
                        grants.append({'group': 'udp-probe', 'source': source, 'destination': destination, 'input': 'wan0', 'protocol': 'udp', 'ports': '27015'})
                    acl.write_text(json.dumps({'host': grants})); acl.chmod(0o600)
                    f.apply(backend, ACCESS_POLICY=str(acl))
                    s = f.store
                    recovery = i.STATE / 'boot-recovery.json'
                    recovery.write_text(json.dumps(rows)); recovery.chmod(0o600)
                    with s.lock():
                        s.put('persisted', s.get('current'))
                        boot.prepare(s, str(recovery))
                        boot.guard(s)
                        with self.assertRaises(PolicyError):
                            boot.verify(s)
                    for family in (4, 6):
                        self.assertTrue(f.peer.tcp(22222, family), (backend, family, 'scoped recovery'))
                        self.assertFalse(f.peer.tcp(18080, family), (backend, family, 'guarded web'))
                        self.assertFalse(udp(f.peer, b'guard', family))
                    for family, address in ((4, '10.30.0.2'), (6, 'fd00:30::2')):
                        code = f'import socket; s=socket.socket(socket.AF_INET{6 if family == 6 else ""}, socket.SOCK_STREAM); s.settimeout(1); s.connect(({address!r},18443)); print(bool(s.recv(100))); s.close()'
                        self.assertEqual(i.run('python3', '-c', code).strip(), 'True', (backend, family, 'host-initiated reply through guard'))
                    with s.lock():
                        candidate = copy.deepcopy(s.get('current'))
                        s.put('pending', {'token': 'a' * 32, 'deadline': time.time()-1,
                                         'previous': None, 'candidate': candidate, 'snapshot': None})
                        s.rollback_locked()
                        self.assertIsNone(s.get('current'))
                        self.assertTrue(boot.guard_present())
                    self.assertFalse(f.peer.tcp(18080))
                    with s.lock():
                        boot.restore(s)
                        self.assertTrue(boot.verify(s)['ready'])
                    for family in (4, 6):
                        self.assertTrue(f.peer.tcp(18080, family))
                        self.assertTrue(udp(f.peer, b'restored', family), (backend, family, 'restored UDP'))
                    with s.lock():
                        boot.disarm(s)
                finally:
                    # Explicitly remove only the registered barrier before the
                    # ordinary fixture performs selective policy cleanup.
                    with f.store.lock():
                        if f.store.get('boot-policy'):
                            boot.disarm(f.store)
                    f.tearDown()


if __name__ == '__main__':
    unittest.main(verbosity=2)
