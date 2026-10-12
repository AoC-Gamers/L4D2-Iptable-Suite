#!/usr/bin/env python3
"""Offline ownership regressions for the H3 guest boot harness."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).with_name('closure_boot.py')
SPEC = importlib.util.spec_from_file_location('l4s_closure_boot', SOURCE)
boot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(boot)


def test_read_owned(path, *, mode=0o600):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        boot.require(boot.stat.S_ISREG(info.st_mode)
                     and boot.stat.S_IMODE(info.st_mode) == mode,
                     f'Unsafe fixture in test: {path}')
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                return b''.join(chunks)
            chunks.append(chunk)
    finally:
        os.close(fd)


def test_write_new(path, content, *, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        view = memoryview(content)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    return boot.hash_bytes(content)


def test_netns_identity():
    path = boot.NETNS_DIR / boot.PROBE_NETNS
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    return {'dev': info.st_dev, 'ino': info.st_ino}


class FakeIP:
    def __init__(self, netns_dir):
        self.netns_dir = netns_dir
        self.interface = None
        self.calls = []

    def __call__(self, argv, *, check=True, **_kwargs):
        argv = [str(part) for part in argv]
        self.calls.append(argv)
        if argv[:6] == ['ip', '-j', '-d', 'link', 'show', 'dev']:
            if self.interface is None:
                return subprocess.CompletedProcess(argv, 1, '', 'not found')
            payload = [{
                'ifname': boot.PROBE_IFACE,
                'ifindex': self.interface['ifindex'],
                'address': self.interface['address'],
                'linkinfo': {'info_kind': self.interface['kind']},
            }]
            return subprocess.CompletedProcess(argv, 0, json.dumps(payload), '')
        if argv[:3] == ['ip', 'netns', 'add']:
            self.netns_dir.mkdir(parents=True, exist_ok=True)
            (self.netns_dir / argv[3]).touch()
        elif argv[:3] == ['ip', 'netns', 'del']:
            (self.netns_dir / argv[3]).unlink(missing_ok=True)
        elif argv[:3] == ['ip', 'link', 'add']:
            self.interface = {'ifindex': 42, 'address': '02:00:00:00:00:42', 'kind': 'veth'}
        elif argv[:3] == ['ip', 'link', 'del']:
            self.interface = None
        return subprocess.CompletedProcess(argv, 0, '', '')


class BootHarnessOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.run_dir = self.root / 'run'
        self.netns_dir = self.run_dir / 'netns'
        self.manifest_path = self.state / 'closure-h3-test.json'
        self.registry_path = self.run_dir / 'l4d2-h3-network-owner.json'
        self.ip = FakeIP(self.netns_dir)
        self.patches = [
            patch.object(boot, 'STATE', self.state),
            patch.object(boot, 'MANIFEST', self.manifest_path),
            patch.object(boot, 'NETWORK_REGISTRY', self.registry_path),
            patch.object(boot, 'NETNS_DIR', self.netns_dir),
            patch.object(boot, 'run', side_effect=self.ip),
            patch.object(boot, 'read_owned_regular', side_effect=test_read_owned),
            patch.object(boot, 'write_new_owned_file', side_effect=test_write_new),
            patch.object(boot, 'probe_netns_identity', side_effect=test_netns_identity),
            patch.object(boot, 'boot_id', return_value='boot-A'),
        ]
        for item in self.patches:
            item.start()
        boot.save_manifest({'phase': 'bootstrap-in-progress', 'owner_token': 'owner-1',
                            'owned_files': {}, 'owned_file_modes': {}})

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_network_is_created_once_and_reused_only_for_matching_identity(self):
        boot.create_probe_network()
        add_calls = [call for call in self.ip.calls if call[:3] in (
            ['ip', 'netns', 'add'], ['ip', 'link', 'add'])]
        self.assertEqual(len(add_calls), 2)
        registry_before = self.registry_path.read_bytes()
        boot.create_probe_network()
        add_calls = [call for call in self.ip.calls if call[:3] in (
            ['ip', 'netns', 'add'], ['ip', 'link', 'add'])]
        self.assertEqual(len(add_calls), 2)
        self.assertEqual(self.registry_path.read_bytes(), registry_before)
        self.ip.interface['address'] = '02:00:00:00:00:99'
        with self.assertRaises(boot.H3Error):
            boot.create_probe_network()
        self.assertFalse(any(call[:3] in (['ip', 'netns', 'del'], ['ip', 'link', 'del'])
                             for call in self.ip.calls))

    def test_unregistered_names_and_missing_same_boot_registry_are_preserved(self):
        self.netns_dir.mkdir(parents=True)
        (self.netns_dir / boot.PROBE_NETNS).touch()
        with self.assertRaises(boot.H3Error):
            boot.create_probe_network()
        self.assertTrue((self.netns_dir / boot.PROBE_NETNS).exists())
        self.assertFalse(any(call[:3] in (['ip', 'netns', 'del'], ['ip', 'link', 'del'])
                             for call in self.ip.calls))
        (self.netns_dir / boot.PROBE_NETNS).unlink()
        with patch.object(boot, 'boot_id', return_value='boot-A'):
            state = boot.manifest()
            state['phase'] = 'reboot-prepared'
            state['network_boot_id'] = 'boot-A'
            boot.save_manifest(state)
            with self.assertRaises(boot.H3Error):
                boot.create_probe_network()

    def test_only_authorized_new_boot_can_recreate_registry(self):
        state = boot.manifest()
        state.update({'phase': 'reboot-prepared', 'network_boot_id': 'boot-before'})
        boot.save_manifest(state)
        boot.create_probe_network()
        current = boot.manifest()
        self.assertEqual(current['network_boot_id'], 'boot-A')
        self.assertEqual(current['phase'], 'reboot-prepared')

    def test_cleanup_removes_only_matching_network_and_host_first(self):
        boot.create_probe_network()
        state = boot.manifest()
        boot.remove_probe_network(state)
        deletions = [call[:3] for call in self.ip.calls
                     if call[:3] in (['ip', 'netns', 'del'], ['ip', 'link', 'del'])]
        self.assertEqual(deletions, [['ip', 'link', 'del'], ['ip', 'netns', 'del']])
        self.assertFalse(self.registry_path.exists())

    def test_modified_owned_file_cannot_be_replaced_or_removed(self):
        state = boot.manifest()
        access = self.state / 'closure-h3-access.json'
        boot.write_new_manifest_file(state, access, b'{"host": []}\n')
        state = boot.manifest()
        access.write_bytes(b'operator-owned\n')
        with self.assertRaises(boot.H3Error):
            boot.replace_owned_json(state, access, {'host': []})
        with self.assertRaises(boot.H3Error):
            boot.remove_owned_manifest_file(state, access)
        self.assertEqual(access.read_bytes(), b'operator-owned\n')

    def test_bootstrap_preflight_rejects_fixture_paths_and_network_names(self):
        with patch.object(boot, 'MANIFEST', self.root / 'preexisting-manifest'):
            boot.MANIFEST.write_text('do not replace')
            with self.assertRaises(boot.H3Error):
                boot.bootstrap_preflight()
            self.assertEqual(boot.MANIFEST.read_text(), 'do not replace')
        boot.MANIFEST.unlink()
        self.netns_dir.mkdir(parents=True)
        (self.netns_dir / boot.PROBE_NETNS).touch()
        with self.assertRaises(boot.H3Error):
            boot.bootstrap_preflight()
        self.assertTrue((self.netns_dir / boot.PROBE_NETNS).exists())

    def test_real_owned_reader_rejects_symlinks_and_unowned_uid(self):
        target = self.root / 'target'
        target.write_text('fixture')
        link = self.root / 'link'
        link.symlink_to(target)
        self.patches[5].stop()
        with self.assertRaises(boot.H3Error):
            boot.read_owned_regular(link)
        if os.geteuid() != 0:
            target.chmod(0o600)
            with self.assertRaises(boot.H3Error):
                boot.read_owned_regular(target)


if __name__ == '__main__':
    unittest.main(verbosity=2)
