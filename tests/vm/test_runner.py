#!/usr/bin/env python3
"""Offline regression tests for the QEMU host runner (no VM or Netfilter)."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch


RUNNER_PATH = Path(__file__).with_name('run.py')
SPEC = importlib.util.spec_from_file_location('l4s_vm_runner', RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class MemoryLog:
    def __init__(self):
        self.lines = []

    def write(self, line):
        self.lines.append(line)


class RunnerTests(unittest.TestCase):
    def test_slirp_handshake_without_application_bytes_is_not_exposure(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.recv.side_effect = runner.socket.timeout()
        with patch.object(runner.socket, 'create_connection', return_value=connection):
            self.assertIsNone(runner.external_tcp_response(22464))
        connection.recv.side_effect = [b'fixture-response', b'']
        with patch.object(runner.socket, 'create_connection', return_value=connection):
            self.assertEqual(runner.external_tcp_response(22464), b'fixture-response')

    def test_probe_summary_measures_real_gaps_and_protocol_coverage(self):
        samples = [
            {'protocol': 'tcp', 'started_monotonic': 10.0, 'duration_seconds': 0.4,
             'stage': 'docker-restart', 'exposed': False},
            {'protocol': 'udp', 'started_monotonic': 10.4, 'duration_seconds': 0.5,
             'stage': 'docker-restart', 'exposed': False},
            {'protocol': 'tcp', 'started_monotonic': 11.0, 'duration_seconds': 0.4,
             'stage': 'failed-reboot', 'exposed': False},
            {'protocol': 'udp', 'started_monotonic': 11.4, 'duration_seconds': 0.5,
             'stage': 'failed-reboot', 'exposed': True},
        ]
        summary = runner.external_probe_summary(samples)
        self.assertEqual(summary['tcp']['max_start_gap_seconds'], 1.0)
        self.assertEqual(summary['udp']['max_duration_seconds'], 0.5)
        self.assertEqual(summary['udp']['exposed'], 1)
        self.assertEqual(summary['tcp']['stages'], ['docker-restart', 'failed-reboot'])

    def guest(self):
        with patch.object(runner, 'executable', side_effect=lambda name: name):
            return runner.Guest(key=Path('/tmp/key'), known_hosts=Path('/tmp/known'), port=22462, log=MemoryLog())

    def test_transaction_parses_raw_token_then_keeps_it_out_of_logs(self):
        guest = self.guest()
        token = 'deadbeef0123456789abcdef'
        replies = [
            json.dumps({'phase': 'fresh-ssh-pending', 'token': token}),
            json.dumps({'phase': 'fresh-ssh-confirmed'}),
        ]
        commands = []

        def fake_ssh(command, **kwargs):
            commands.append((command, kwargs))
            return subprocess.CompletedProcess([], 0, replies.pop(0).encode(), b'')

        with patch.object(guest, 'ssh', side_effect=fake_ssh):
            armed = guest.tx('arm-fresh-ssh')
            confirmed = guest.tx('confirm-fresh-ssh', token, secrets=(token,))

        self.assertEqual(armed['token'], token)
        self.assertEqual(confirmed['phase'], 'fresh-ssh-confirmed')
        self.assertIn(token, guest.tokens)
        self.assertIn(token, commands[1][0])  # passed to a fresh, nonmultiplexed SSH invocation
        self.assertFalse(any(token in line for line in guest.log.lines))

    def test_cleanup_plaintext_is_accepted_only_for_cleanup_phases(self):
        guest = self.guest()
        message = 'Disposable guest nftables state disabled and test persistence removed.'
        with patch.object(guest, 'ssh', return_value=subprocess.CompletedProcess([], 0, message.encode(), b'')):
            self.assertEqual(guest.tx('cleanup'), {'phase': 'cleanup', 'cleanup': 'complete'})
        with patch.object(guest, 'ssh', return_value=subprocess.CompletedProcess([], 0, message.encode(), b'')):
            with self.assertRaises(runner.RunnerError):
                guest.tx('bootstrap')

    def test_legacy_cleanup_requires_actual_json_phase(self):
        guest = self.guest()
        payload = json.dumps({'phase': 'legacy-cleaned', 'unit_disabled': True})
        with patch.object(guest, 'ssh', return_value=subprocess.CompletedProcess([], 0, payload.encode(), b'')):
            self.assertEqual(guest.tx('cleanup-legacy'), {'phase': 'legacy-cleaned', 'unit_disabled': True})
        invented_plaintext = 'Disposable guest iptables-legacy state disabled and test persistence removed.'
        with patch.object(guest, 'ssh', return_value=subprocess.CompletedProcess([], 0, invented_plaintext.encode(), b'')):
            with self.assertRaises(runner.RunnerError):
                guest.tx('cleanup-legacy')

    def test_qemu_network_is_loopback_forward_only_and_disk_uses_overlay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, overlay, seed = (root/'base.img', root/'overlay.qcow2', root/'seed.iso')
            for path in (base, overlay, seed):
                path.write_bytes(b'test')
            args = types.SimpleNamespace(memory=4096, cpus=4, qemu_data_dir=None, bios=None,
                                         machine=None, cpu=None)
            with patch.object(runner, 'executable', return_value='/usr/bin/qemu-system-x86_64'), \
                 patch.object(runner.os, 'access', return_value=False):
                command, _ = runner.qemu_arguments(args, base, overlay, seed, root, 22463)
            rendered = ' '.join(command)
            self.assertIn('hostfwd=tcp:127.0.0.1:22463-:22', rendered)
            self.assertIn('hostfwd=tcp:127.0.0.1:22464-:18482', rendered)
            self.assertIn('hostfwd=udp:127.0.0.1:22465-:18483', rendered)
            self.assertIn(f'file={overlay},if=virtio,format=qcow2', rendered)
            self.assertNotIn(str(base), rendered)
            self.assertNotRegex(rendered, r'\b(?:tap|bridge|socket)=')

    def test_overlay_is_a_private_qcow2_backed_by_immutable_base_and_grown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base, overlay = root/'base.img', root/'overlay.qcow2'
            base.write_bytes(b'immutable base')
            calls = []
            def fake_command(argv, **kwargs):
                calls.append(argv)
                if argv[1] == 'create':
                    overlay.write_bytes(b'overlay only')
            with patch.object(runner, 'executable', return_value='qemu-img'), \
                 patch.object(runner, 'host_command', side_effect=fake_command):
                runner.create_overlay(base, overlay)
            self.assertEqual(base.read_bytes(), b'immutable base')
            self.assertEqual(calls[0], ['qemu-img', 'create', '-q', '-f', 'qcow2', '-F', 'qcow2', '-b', str(base), str(overlay)])
            self.assertEqual(calls[1], ['qemu-img', 'resize', str(overlay), '12G'])
            self.assertEqual(overlay.stat().st_mode & 0o777, 0o600)

    def test_ssh_does_not_use_agent_or_forward_credentials(self):
        guest = self.guest()
        for argv in (guest.base_ssh, guest.base_scp):
            self.assertIn('IdentitiesOnly=yes', argv)
            self.assertIn('IdentityAgent=none', argv)
            self.assertIn('ForwardAgent=no', argv)

    def test_git_manifest_excludes_env_and_arbitrary_untracked_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'tracked.py').write_text('tracked\n')
            (root/'untracked-secret.py').write_text('not sent\n')
            (root/'.env').write_text('secret=value\n')
            completed = subprocess.CompletedProcess([], 0, b'tracked.py\0.env\0', b'')
            with patch.object(runner, 'ROOT', root), patch.object(runner, 'host_command', return_value=completed):
                self.assertEqual(runner.tracked_files(), ['tracked.py'])

    def test_guard_marker_and_guest_packages_are_configured(self):
        config = runner.cloud_config('ssh-ed25519 AAAA public', 'iid-test')
        self.assertIn('chmod 0600', config)
        self.assertIn('"virtualization":"qemu","disposable":true', config)
        self.assertIn('  - name: suiteunit', config)
        self.assertIn("    groups: ''", config)
        self.assertIn('    sudo: null', config)
        self.assertIn('    lock_passwd: true', config)
        self.assertIn('    shell: /usr/sbin/nologin', config)
        for required in ('openvpn', 'openssh-server', 'nftables', 'iptables', 'git', 'xt_u32'):
            self.assertIn(required, config)

    def test_every_unit_case_runs_unprivileged_without_omissions(self):
        cases = runner.unit_cases()
        self.assertTrue(cases)
        self.assertEqual({identity for _command, identity in cases}, {runner.UNIT_USER})
        self.assertEqual({command for command, _identity in cases}, {
            'python3 -I tests/test_core.py',
            'python3 -I tests/test_geoip.py',
            'python3 -I tests/test_transactions.py',
            'python3 -I tests/test_configuration_audit.py',
            'python3 -I tests/test_policy_audit.py',
            'python3 -I tests/test_docker_topology.py',
            'python3 -I tests/test_h2.py',
            'python3 -I tests/test_boot.py',
            'python3 -I tests/vm/test_transactions_harness.py',
            'python3 -I tests/vm/test_boot_harness.py',
            'bash tests/watcher-audit.sh',
            'bash tests/http-https-protect.sh',
            'bash tests/public-ip-watch.sh',
            'bash tests/generate.sh',
        })
        self.assertNotEqual(runner.UNIT_ROOT, runner.INSTALL_ROOT)
        for command, identity in cases:
            guest_command = runner.unit_execution_command(command, identity)
            self.assertIn('sudo -n -u suiteunit', guest_command)
            self.assertIn('id -u', guest_command)
            self.assertIn('sudo -n true', guest_command)
            self.assertIn('/home/suiteunit/l4d2-unit', guest_command)

    def test_guest_must_validate_cloud_init_schema_before_status_wait(self):
        source = RUNNER_PATH.read_text(encoding='utf-8')
        validate = source.index("guest.run_guest('validate cloud-init schema'")
        status = source.index("guest.ssh('sudo -n cloud-init status --wait'")
        self.assertLess(validate, status)
        self.assertIn("'cloud-init schema --system'", source[validate:status])

    def test_product_trust_stays_rooted_and_unit_copy_uses_dedicated_account(self):
        guest = self.guest()
        archive = Path('/tmp/suite.tar.gz')
        with patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'', b'')), \
             patch.object(guest, 'ssh', return_value=subprocess.CompletedProcess([], 0, b'', b'')) as ssh:
            guest.install_suite(archive)
        command = ssh.call_args.args[0]
        self.assertIn("trusted('/opt/l4d2-firewall')", command)
        self.assertIn('tar --no-same-owner -xzf', command)
        self.assertIn('sudo -n -u suiteunit -- tar --no-same-owner', command)
        self.assertIn('chown -R suiteunit:suiteunit /home/suiteunit/l4d2-unit', command)
        self.assertIn('test "$(sudo -n stat -c %U:%G /home/suiteunit/l4d2-unit)" = suiteunit:suiteunit', command)
        self.assertIn('! sudo -n true >/dev/null 2>&1', command)

    def test_runner_log_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            log = runner.Log(Path(directory) / 'runner.log')
            try:
                self.assertEqual((Path(directory) / 'runner.log').stat().st_mode & 0o777, 0o600)
                self.assertEqual(Path(directory).stat().st_mode & 0o777, 0o700)
            finally:
                log.close()

    def test_serial_redacts_rollback_unit_token_but_keeps_image_hash(self):
        token = 'abcdef0123456789abcdef0123456789'
        image_hash = 'a' * 64
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'qemu-serial.log'
            artifacts = root / 'artifacts'
            artifacts.mkdir(mode=0o700)
            source.write_text(f'l4d2-rollback-{token}.timer verified image sha256={image_hash}\n')
            guest = self.guest()
            runner.copy_serial(source, artifacts, guest)
            saved = (artifacts / 'serial.log').read_text()
            self.assertNotIn(token, saved)
            self.assertIn('l4d2-rollback-[redacted].timer', saved)
            self.assertIn(image_hash, saved)
            self.assertEqual((artifacts / 'serial.log').stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main(verbosity=2)
