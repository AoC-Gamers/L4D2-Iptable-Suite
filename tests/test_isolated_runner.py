#!/usr/bin/python3
"""Runner orchestration regressions using fake tools; no kernel operations."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IsolatedRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.bin = self.root / 'bin'
        (self.repo / 'tests').mkdir(parents=True)
        (self.repo / 'core').mkdir()
        self.bin.mkdir()
        shutil.copyfile(ROOT / 'tests/isolated-run.sh', self.repo / 'tests/isolated-run.sh')
        (self.repo / 'tests/integration.py').write_text('# tracked test\n')
        (self.repo / 'core/fixture.py').write_text('# tracked code\n')
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'add', 'core', 'tests'], check=True)
        # These files must never enter the privileged source tree.
        (self.repo / 'core/__pycache__').mkdir(mode=0o777)
        (self.repo / 'core/__pycache__/ignored.pyc').write_bytes(b'cache')
        (self.repo / 'tests/private-fixture.py').write_text('raise RuntimeError()\n')
        for name in ('mount', 'nft', 'iptables', 'ip6tables', 'ip', 'iptables-restore'):
            tool = self.bin / name
            tool.write_text('#!/bin/sh\nexit 91\n')
            tool.chmod(0o700)
        # Inspect the prepared fixture instead of creating a namespace or running engines.
        tool = self.bin / 'unshare'
        tool.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
repo = pathlib.Path(sys.argv[-2]) / 'repo'
print(json.dumps({
 'accept': os.environ['SUITE_TEST_ACCEPT_VERSION_CHANGE'],
 'umask': os.umask(0o077),
 'files': sorted(str(p.relative_to(repo)) for p in repo.rglob('*') if p.is_file()),
 'unsafe': [str(p) for p in repo.rglob('*') if p.stat().st_mode & 0o022],
 'no_bytecode': 'exec python3 -I -B "$2"' in sys.argv[-4],
}))
''')
        tool.chmod(0o700)

    def run_fixture(self, *args, inherited_accept='1'):
        env = {**os.environ, 'PATH': str(self.bin) + ':' + os.environ['PATH'],
               'SUITE_TEST_ACCEPT_VERSION_CHANGE': inherited_accept}
        # Reproduce the ordinary user umask that previously produced unsafe caches.
        return subprocess.run(['bash', '-c', 'umask 0002; exec bash "$@"', '_',
                               str(self.repo / 'tests/isolated-run.sh'), *args],
                              env=env, text=True, capture_output=True)

    def test_safe_staging_and_no_implicit_version_acceptance(self):
        result = self.run_fixture('tests/integration.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['accept'], '0')
        self.assertEqual(report['umask'], 0o077)
        self.assertEqual(report['unsafe'], [])
        self.assertTrue(report['no_bytecode'])
        self.assertEqual(report['files'], ['core/fixture.py', 'tests/integration.py',
                                           'tests/isolated-run.sh'])

    def test_explicit_acceptance_is_visible(self):
        result = self.run_fixture('--accept-version-change', 'tests/integration.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['accept'], '1')
        self.assertIn('TEST ONLY', result.stderr)

    def test_unknown_options_and_extra_scripts_fail(self):
        for args in (('--accept-typo',), ('tests/integration.py', 'tests/policy-flows.py')):
            with self.subTest(args=args):
                self.assertEqual(self.run_fixture(*args).returncode, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
