#!/usr/bin/env python3
"""Offline regressions for H3 unit-disable and cleanup ownership checks."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).with_name('closure_boot.py')
SPEC = importlib.util.spec_from_file_location('l4s_closure_boot_cleanup', SOURCE)
boot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(boot)


class DisableManagedUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.etc = self.root / 'etc-systemd'
        self.run = self.root / 'run-systemd'
        self.etc.mkdir()
        self.run.mkdir()
        self.roots = (self.etc, self.run)

    def tearDown(self):
        self.temp.cleanup()

    def test_disable_requires_command_success_and_exact_disabled_state(self):
        calls = []

        def command(argv, *, check=True, **_kwargs):
            argv = [str(item) for item in argv]
            calls.append(argv)
            if argv[:2] == ['systemctl', 'disable']:
                return subprocess.CompletedProcess(argv, 1, '', 'disable failed')
            return subprocess.CompletedProcess(argv, 1, 'disabled\n', '')

        with patch.object(boot, 'run', side_effect=command):
            with self.assertRaises(boot.H3Error):
                boot.disable_managed_unit('demo.service', enablement_roots=self.roots)
        self.assertEqual(calls, [['systemctl', 'disable', 'demo.service']])

        for state in ('static', 'indirect', 'enabled-runtime', 'masked', 'not-found'):
            with self.subTest(state=state):
                calls.clear()

                def report_state(argv, *, check=True, **_kwargs):
                    argv = [str(item) for item in argv]
                    calls.append(argv)
                    if argv[:2] == ['systemctl', 'disable']:
                        return subprocess.CompletedProcess(argv, 0, '', '')
                    if argv[:2] == ['systemctl', 'is-enabled']:
                        return subprocess.CompletedProcess(argv, 1, state + '\n', '')
                    self.fail(f'Unexpected command: {argv}')

                with patch.object(boot, 'run', side_effect=report_state):
                    with self.assertRaises(boot.H3Error):
                        boot.disable_managed_unit('demo.service', enablement_roots=self.roots)

    def test_disable_rejects_residual_enablement_symlink_in_any_root(self):
        for root in self.roots:
            with self.subTest(root=root):
                link_dir = root / 'multi-user.target.wants'
                link_dir.mkdir()
                unit_file = self.root / 'demo.service'
                unit_file.write_text('[Unit]\nDescription=fixture\n')
                link = link_dir / 'demo.service'
                link.symlink_to(unit_file)

                def command(argv, *, check=True, **_kwargs):
                    argv = [str(item) for item in argv]
                    if argv[:2] == ['systemctl', 'disable']:
                        return subprocess.CompletedProcess(argv, 0, '', '')
                    if argv[:2] == ['systemctl', 'is-enabled']:
                        return subprocess.CompletedProcess(argv, 1, 'disabled\n', '')
                    self.fail(f'Unexpected command: {argv}')

                with patch.object(boot, 'run', side_effect=command):
                    with self.assertRaises(boot.H3Error):
                        boot.disable_managed_unit('demo.service', enablement_roots=self.roots)
                self.assertTrue(link.is_symlink())
                link.unlink()

    def test_success_requires_no_symlinks_and_disabled_state(self):
        link_dir = self.etc / 'multi-user.target.wants'
        link_dir.mkdir()
        unit_file = self.root / 'demo.service'
        unit_file.write_text('[Unit]\nDescription=fixture\n')
        link = link_dir / 'demo.service'
        link.symlink_to(unit_file)

        def command(argv, *, check=True, **_kwargs):
            argv = [str(item) for item in argv]
            if argv[:2] == ['systemctl', 'disable']:
                link.unlink()
                return subprocess.CompletedProcess(argv, 0, '', '')
            if argv[:2] == ['systemctl', 'is-enabled']:
                return subprocess.CompletedProcess(argv, 1, 'disabled\n', '')
            self.fail(f'Unexpected command: {argv}')

        with patch.object(boot, 'run', side_effect=command):
            boot.disable_managed_unit('demo.service', enablement_roots=self.roots)
        self.assertFalse(link.exists())


class CleanupDisableOrderingTests(unittest.TestCase):
    def test_disable_failure_keeps_unit_file_and_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unit_root = root / 'systemd'
            unit_root.mkdir()
            unit = 'l4d2-firewall.service'
            target = unit_root / unit
            content = b'[Unit]\nDescription=test\n'
            target.write_bytes(content)
            digest = hashlib.sha256(content).hexdigest()
            manifest = {
                'phase': 'post-reboot-verified',
                'units': {unit: digest},
                'owned_files': {},
                'baseline_state': {},
            }

            def command(argv, *, check=True, **_kwargs):
                argv = [str(item) for item in argv]
                return subprocess.CompletedProcess(argv, 0, '', '')

            output = io.StringIO()
            with patch.object(boot, 'SYSTEMD_UNIT_ROOT', unit_root), \
                    patch.object(boot, 'manifest', return_value=manifest), \
                    patch.object(boot, 'store_json', return_value=None), \
                    patch.object(boot, 'run', side_effect=command), \
                    patch.object(boot, 'disable_managed_unit', side_effect=boot.H3Error('disable failed')), \
                    contextlib.redirect_stdout(output):
                with self.assertRaises(boot.H3Error):
                    boot.cleanup()

            self.assertTrue(target.exists(), 'cleanup deleted a unit despite disable failure')
            self.assertNotIn('units_removed', output.getvalue())


if __name__ == '__main__':
    unittest.main(verbosity=2)
