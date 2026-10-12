#!/usr/bin/python3
"""Regressions for CLI selection and GeoIP updater identity handling."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.config import Configuration


class SelectionTests(unittest.TestCase):
    def generate(self, *args):
        return subprocess.run(
            [sys.executable, '-I', str(ROOT / 'core/fw.py'), 'generate', *args],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )

    def test_explicit_empty_only_is_core_only_even_with_profile(self):
        with tempfile.NamedTemporaryFile(mode='w') as empty:
            empty.flush()
            result = self.generate('--env-file', empty.name, '--only', '', '--profile', 'games')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['selected'], [])

    def test_empty_file_module_list_still_uses_default_profile(self):
        c = Configuration('nftables', overrides={'MODULES_ONLY': ''})
        self.assertEqual(c.names, {'tcp_ssh'})

    def test_explicit_empty_only_replaces_file_module_list(self):
        with tempfile.NamedTemporaryFile(mode='w') as config:
            config.write('MODULES_ONLY=games\n')
            config.flush()
            result = self.generate('--env-file', config.name, '--only', '')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['selected'], [])

    def test_geoip_updater_rejects_wrong_mount_owner_before_download(self):
        with tempfile.TemporaryDirectory() as owner_mismatch:
            workspace = '/'
            if os.geteuid() == 0:
                os.chown(owner_mismatch, 65534, 65534)
                workspace = owner_mismatch
            result = subprocess.run(
                ['bash', str(ROOT / 'geoip-updater/run-update.sh')],
                cwd=ROOT,
                env={**os.environ, 'WORKSPACE_ROOT': workspace, 'ENV_FILE': '/missing'},
                text=True, capture_output=True, check=False,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn('must run as bind-mount owner', result.stderr)
        self.assertNotIn('Downloading MaxMind archive', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
