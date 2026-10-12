#!/usr/bin/env python3
"""Offline ownership regressions for the H3 guest boot harness."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import copy
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

    def test_boot_wait_refreshes_network_ownership_before_phase_save(self):
        boot.save_manifest({'phase': 'reboot-prepared', 'network_boot_id': 'old',
                            'owned_files': {}})

        def network_unit_booted():
            state = boot.manifest()
            state['network_boot_id'] = 'current'
            state['network_identity'] = {'ifindex': 7}
            state['owned_files'][str(boot.NETWORK_REGISTRY)] = 'new-digest'
            boot.save_manifest(state)
            return 'running'

        with patch.object(boot, 'wait_for_boot_jobs', side_effect=network_unit_booted):
            phase_state, state = boot.wait_for_boot_manifest('reboot-prepared')
        self.assertEqual(phase_state, 'running')
        self.assertEqual(state['network_boot_id'], 'current')
        self.assertEqual(state['network_identity'], {'ifindex': 7})
        self.assertEqual(state['owned_files'][str(boot.NETWORK_REGISTRY)], 'new-digest')

    def test_early_network_unit_waits_for_per_boot_safety_marker(self):
        content = boot.network_unit_content()
        self.assertIn('Requires=l4d2-suite-vm-marker.service l4d2-firewall-guard.service', content)
        self.assertIn('After=local-fs.target l4d2-suite-vm-marker.service l4d2-firewall-guard.service', content)

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

    def test_fixture_symlink_is_preserved_and_reported(self):
        state = boot.manifest()
        access = self.state / 'closure-h3-access.json'
        target = self.root / 'operator-file'
        target.write_text('operator data')
        access.symlink_to(target)
        with self.assertRaises(boot.H3Error):
            boot.remove_owned_manifest_file(state, access)
        self.assertTrue(access.is_symlink())
        self.assertEqual(target.read_text(), 'operator data')

    def test_restrict_probe_saves_digest_written_by_policy_update(self):
        calibrated = {'phase': 'docker-probe-calibrated',
                      'owned_files': {str(boot.ACCESS): 'digest-before'}}
        updated = {'phase': 'docker-probe-calibrated',
                   'owned_files': {str(boot.ACCESS): 'digest-after'}}
        saved = []
        with patch.object(boot, 'manifest', side_effect=[calibrated, updated]), \
                patch.object(boot, 'create_probe_network'), \
                patch.object(boot, 'apply_docker_policy'), \
                patch.object(boot, 'require_no_guard'), \
                patch.object(boot, 'published_probe', return_value='H3-CONTAINER'), \
                patch.object(boot, 'published_udp_probe', return_value='H3-UDP'), \
                patch.object(boot, 'save_manifest', side_effect=lambda state: saved.append(copy.deepcopy(state))), \
                patch.object(boot, 'verify_preservation'):
            boot.restrict_probe()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]['owned_files'][str(boot.ACCESS)], 'digest-after')
        self.assertEqual(saved[0]['phase'], 'docker-probe-restricted')

    def test_response_after_guard_release_is_inconclusive_not_exposure(self):
        with patch.object(boot, 'guard_identity', side_effect=['guard-handle-7', None]):
            observation = boot.observe_guarded_probe('tcp', lambda: 'H3-CONTAINER')
        self.assertEqual(observation['classification'], 'guard-transition')
        self.assertTrue(observation['response'])
        boot.require_no_guarded_exposure(observation)

    def test_response_with_same_guard_at_both_probe_edges_fails(self):
        with patch.object(boot, 'guard_identity', side_effect=['guard-handle-7', 'guard-handle-7']):
            observation = boot.observe_guarded_probe('udp', lambda: 'H3-UDP')
        self.assertEqual(observation['classification'], 'response-with-guard-at-both-edges')
        with self.assertRaises(boot.H3Error):
            boot.require_no_guarded_exposure(observation)

    def test_response_during_atomic_guard_rearm_still_fails(self):
        with patch.object(boot, 'guard_identity', side_effect=['guard-handle-7', 'guard-handle-8']):
            observation = boot.observe_guarded_probe('tcp', lambda: 'H3-CONTAINER')
        self.assertEqual(observation['classification'], 'response-with-guard-at-both-edges')
        with self.assertRaises(boot.H3Error):
            boot.require_no_guarded_exposure(observation)

    def test_blocked_probe_requires_same_guard_identity_at_both_edges(self):
        with patch.object(boot, 'guard_identity', side_effect=['guard-handle-7', 'guard-handle-7']):
            observation = boot.observe_guarded_probe('tcp', lambda: '')
        self.assertEqual(observation['classification'], 'blocked-with-stable-guard')

    def test_guard_query_uses_table_handle_and_does_not_hide_command_errors(self):
        payload = json.dumps({'nftables': [
            {'table': {'family': 'inet', 'name': boot.GUARD_TABLE[1], 'handle': 77}},
        ]})
        with patch.object(boot, 'run', return_value=subprocess.CompletedProcess(
                [], 0, payload, '')):
            self.assertTrue(boot.guard_identity())
        with patch.object(boot, 'run', return_value=subprocess.CompletedProcess(
                [], 1, '', 'permission denied')):
            with self.assertRaises(boot.H3Error):
                boot.guard_identity()

    def test_sentinel_recreation_accepts_new_handle_but_keeps_semantics(self):
        def dump(handle):
            table = {'family': boot.FOREIGN_TABLE[0], 'name': boot.FOREIGN_TABLE[1],
                     'comment': boot.FOREIGN_COMMENT, 'handle': handle}
            return json.dumps({'nftables': [{'table': table}]})

        def list_tables(handle):
            return subprocess.CompletedProcess([], 0, dump(handle), '')

        first, second = [], []
        for handle, target in ((101, first), (902, second)):
            with patch.object(boot, 'run', side_effect=[list_tables(handle), list_tables(handle)]):
                target.append(boot.sentinel_state())
        self.assertEqual(first[0]['semantic_digest'], second[0]['semantic_digest'])
        self.assertNotEqual(first[0]['handle'], second[0]['handle'])

    def test_sentinel_extra_nft_objects_are_rejected(self):
        table = {'family': boot.FOREIGN_TABLE[0], 'name': boot.FOREIGN_TABLE[1],
                 'comment': boot.FOREIGN_COMMENT, 'handle': 101}
        listed = subprocess.CompletedProcess([], 0,
            json.dumps({'nftables': [{'table': table}]}), '')
        content = subprocess.CompletedProcess([], 0, json.dumps({'nftables': [
            {'table': table},
            {'chain': {'family': table['family'], 'table': table['name'], 'name': 'foreign'}},
        ]}), '')
        with patch.object(boot, 'run', side_effect=[listed, content]):
            with self.assertRaises(boot.H3Error):
                boot.sentinel_state()

    def test_reboot_sentinel_handle_refresh_is_scoped_to_new_boot(self):
        state = {'sentinel_digest': 'semantic', 'sentinel_handle': 101,
                 'sentinel_boot_id': 'boot-old', 'external_files': {}}
        with patch.object(boot, 'EXTERNAL_FIREWALL_FILES', ()), \
                patch.object(boot, 'sentinel_state', return_value={
                    'semantic_digest': 'semantic', 'handle': 902}), \
                patch.object(boot, 'boot_id', return_value='boot-new'):
            boot.verify_preservation(state, after_reboot=True)
        self.assertEqual(state['sentinel_handle'], 902)
        self.assertEqual(state['sentinel_boot_id'], 'boot-new')
        with patch.object(boot, 'EXTERNAL_FIREWALL_FILES', ()), \
                patch.object(boot, 'sentinel_state', return_value={
                    'semantic_digest': 'semantic', 'handle': 903}), \
                patch.object(boot, 'boot_id', return_value='boot-new'):
            with self.assertRaises(boot.H3Error):
                boot.verify_preservation(state)

    def test_reboot_does_not_adopt_preexisting_matching_sentinel(self):
        table = {'family': boot.FOREIGN_TABLE[0], 'name': boot.FOREIGN_TABLE[1],
                 'comment': boot.FOREIGN_COMMENT, 'handle': 902}
        listing = subprocess.CompletedProcess([], 0, json.dumps({'nftables': [{'table': table}]}), '')
        state = {'sentinel_digest': boot.hash_bytes(json.dumps(
                    {'family': table['family'], 'name': table['name'], 'comment': table['comment']},
                    sort_keys=True, separators=(',', ':')).encode()),
                 'sentinel_handle': 101, 'sentinel_boot_id': 'boot-old', 'external_files': {}}
        with patch.object(boot, 'EXTERNAL_FIREWALL_FILES', ()), \
                patch.object(boot, 'run', return_value=listing), \
                patch.object(boot, 'boot_id', return_value='boot-new'):
            with self.assertRaisesRegex(boot.H3Error, 'Unexpected pre-existing H3 sentinel'):
                boot.verify_preservation(state, after_reboot=True)

    def test_failed_reboot_assertion_keeps_failure_manifest_and_backup(self):
        state = {'phase': 'failed-reboot-prepared', 'persisted_backup': 'exact-bytes',
                 'persisted_backup_sha256': 'digest', 'invalid_persisted_sha256': 'bad-digest'}
        original = copy.deepcopy(state)
        with patch.object(boot, 'save_manifest') as save, \
                patch.object(boot, 'verify_preservation') as verify:
            with self.assertRaisesRegex(boot.H3Error, 'Unsupported-persistence boot assertion failed'):
                boot.finalize_failed_reboot(state, boot.H3Error('sentinel missing'), 'boot-new', {})
        self.assertEqual(state, original)
        save.assert_not_called()
        verify.assert_not_called()

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
