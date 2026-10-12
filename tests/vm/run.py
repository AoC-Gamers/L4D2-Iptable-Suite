#!/usr/bin/env python3
"""Provision a disposable QEMU guest and run the complete VM validation suite.

The host runner only owns its QEMU child process. Guest firewalls, systemd, and
Docker are changed only inside the freshly-created QEMU overlay. Networking is
QEMU user-mode networking with SSH and probe forwards bound to loopback.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[2]
IMAGE_URL = 'https://cloud-images.ubuntu.com/noble/20260926/noble-server-cloudimg-amd64.img'
IMAGE_SHA256 = '6a81c37564db9b1ee84e141922625e1d7c5b389b99bb3c572e0243607d5bb4d2'
DOCKER_URL = 'https://download.docker.com/linux/static/stable/x86_64/docker-29.8.2.tgz'
DOCKER_SHA256 = '995d1ef289677f74fd58d8d2c35727b6a4ee389c69db8638a3e42d0487aa5b0f'
MARKER_JSON = '{"virtualization":"qemu","disposable":true}'
INSTALL_ROOT = '/opt/l4d2-firewall'
UNIT_USER = 'suiteunit'
UNIT_ROOT = f'/home/{UNIT_USER}/l4d2-unit'
SSH_USER = 'ubuntu'
SSH_HOST = '127.0.0.1'
TX_RESULT_PHASE = {
    'bootstrap': 'bootstrapped',
    'arm-fresh-ssh': 'fresh-ssh-pending',
    'confirm-fresh-ssh': 'fresh-ssh-confirmed',
    'arm-kill-worker': 'worker-committed',
    'kill-committed-worker': 'worker-killed',
    'verify-killed-worker-rollback': 'worker-rolled-back',
    'arm-abandoned-session': 'abandoned-session-pending',
    'verify-abandoned-rollback': 'abandoned-session-rolled-back',
    'prepare-reboot': 'reboot-prepared',
    'post-reboot': 'post-reboot-verified',
    'cleanup': 'cleanup',
    'bootstrap-legacy': 'legacy-bootstrapped',
    'prepare-reboot-legacy': 'legacy-reboot-prepared',
    'post-reboot-legacy': 'legacy-post-reboot-verified',
    'cleanup-legacy': 'legacy-cleaned',
}


class RunnerError(RuntimeError):
    pass


class Log:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.stream = self.path.open('a', encoding='utf-8')
        self.path.chmod(0o600)

    def write(self, message: str) -> None:
        line = f'{dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")} {message}'
        print(line, flush=True)
        self.stream.write(line + '\n')
        self.stream.flush()

    def close(self) -> None:
        self.stream.close()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path, digest: str, description: str) -> Path:
    try:
        info = path.stat()
    except OSError as exc:
        raise RunnerError(f'{description} is not readable: {path}: {exc}') from exc
    if not path.is_file() or info.st_size == 0:
        raise RunnerError(f'{description} must be a non-empty regular file: {path}')
    actual = sha256(path)
    if actual != digest:
        raise RunnerError(f'{description} SHA-256 mismatch: expected {digest}, got {actual}')
    return path.resolve()


def download(url: str, target: Path, expected: str, description: str) -> Path:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.partial')
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'l4d2-suite-vm-runner/1'})
        with urllib.request.urlopen(request, timeout=30) as response, partial.open('wb') as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        actual = sha256(partial)
        if actual != expected:
            raise RunnerError(f'{description} SHA-256 mismatch: expected {expected}, got {actual}')
        os.replace(partial, target)
        return target.resolve()
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RunnerError(f'Required host executable is missing from PATH: {name}')
    return path


def host_command(argv: list[str], *, timeout: int = 60, check: bool = True,
                 input_data: bytes | None = None) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(argv, input=input_data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RunnerError(f'Host command failed or timed out: {argv[0]}: {exc}') from exc
    if check and result.returncode:
        stderr = result.stderr.decode(errors='replace')[-4000:]
        raise RunnerError(f'Host command failed ({result.returncode}): {argv[0]}: {stderr}')
    return result


def command_output(argv: list[str], *, timeout: int = 30) -> str:
    result = host_command(argv, timeout=timeout)
    return result.stdout.decode(errors='replace')


def cloud_config(public_key: str, instance: str) -> str:
    marker_script = '''#!/bin/sh
set -eu
virt="$(/usr/bin/systemd-detect-virt --vm)"
case "$virt" in qemu|kvm) ;; *) echo "Refusing marker on $virt" >&2; exit 1 ;; esac
tmp="$(/usr/bin/mktemp /run/.l4d2-suite-vm.XXXXXX)"
/usr/bin/printf '%s\\n' '{"virtualization":"qemu","disposable":true}' >"$tmp"
/usr/bin/chown root:root "$tmp"
/usr/bin/chmod 0600 "$tmp"
/usr/bin/mv -f "$tmp" /run/l4d2-suite-vm.json
'''
    marker_unit = '''[Unit]
Description=Attest this runner-owned disposable QEMU guest
DefaultDependencies=no
After=local-fs.target
Before=network-pre.target multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/l4d2-suite-vm-marker
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
'''
    return f'''#cloud-config
hostname: l4d2-suite-vm
manage_etc_hosts: true
ssh_pwauth: false
disable_root: true
package_update: true
package_upgrade: false
users:
  - default
  - name: suiteunit
    gecos: Disposable unprivileged unit-test account
    groups: ''
    sudo: null
    lock_passwd: true
    shell: /usr/sbin/nologin
ssh_authorized_keys:
  - {json.dumps(public_key)}
packages:
  - ca-certificates
  - curl
  - git
  - iproute2
  - iptables
  - nftables
  - openssh-server
  - openssl
  - openvpn
  - python3
  - kmod
  - systemd
  - util-linux
write_files:
  - path: /etc/sudoers.d/90-l4d2-vm-runner
    owner: root:root
    permissions: '0440'
    content: |
      ubuntu ALL=(ALL) NOPASSWD:ALL
      Defaults:ubuntu env_keep += "SSH_CONNECTION"
  - path: /usr/local/sbin/l4d2-suite-vm-marker
    owner: root:root
    permissions: '0755'
    content: |
{''.join('      '+line+'\n' for line in marker_script.splitlines())}  - path: /etc/systemd/system/l4d2-suite-vm-marker.service
    owner: root:root
    permissions: '0644'
    content: |
{''.join('      '+line+'\n' for line in marker_unit.splitlines())}runcmd:
  - [systemctl, daemon-reload]
  - [systemctl, enable, --now, l4d2-suite-vm-marker.service]
  - [systemctl, enable, ssh.service]
  - [modprobe, ip6_tables]
  - [modprobe, ip6table_nat]
  - [modprobe, xt_u32]
'''


def make_seed(work: Path, public_key: str, instance: str) -> Path:
    user_data = work / 'user-data'
    metadata = work / 'meta-data'
    user_data.write_text(cloud_config(public_key, instance), encoding='utf-8')
    metadata.write_text(f'instance-id: {instance}\nlocal-hostname: l4d2-suite-vm\n', encoding='utf-8')
    seed = work / 'seed.iso'
    host_command([executable('genisoimage'), '-quiet', '-output', str(seed), '-volid', 'cidata',
                  '-joliet', '-rock', str(user_data), str(metadata)], timeout=60)
    return seed


def tracked_files() -> list[str]:
    result = host_command(['git', '-C', str(ROOT), 'ls-files', '-z'], timeout=20)
    names = [name for name in result.stdout.decode().split('\0') if name]
    # Include tracked and staged files only. Never sweep arbitrary untracked
    # workspace files, which could contain local credentials.
    unique = sorted(set(names))
    return [name for name in unique
            if PurePosixPath(name).name != '.env'
            and not name.startswith(('reports/', 'tmp/', '.git/'))]


def make_suite_archive(work: Path) -> Path:
    archive_path = work / 'suite.tar.gz'
    with tarfile.open(archive_path, mode='w:gz', compresslevel=6) as archive:
        for relative in tracked_files():
            source = ROOT / relative
            if source.is_file() or source.is_symlink():
                archive.add(source, arcname=relative, recursive=False)
    return archive_path


def qemu_arguments(args, base: Path, overlay: Path, seed: Path, work: Path, port: int) -> tuple[list[str], dict[str, str]]:
    qemu = executable('qemu-system-x86_64')
    command = [qemu, '-name', 'l4d2-suite-disposable-test', '-nodefaults',
               '-display', 'none', '-monitor', 'none', '-serial', f'file:{work / "serial.log"}',
               '-m', str(args.memory), '-smp', str(args.cpus)]
    if os.access('/dev/kvm', os.R_OK | os.W_OK):
        command += ['-accel', 'kvm']
    else:
        command += ['-accel', 'tcg,thread=multi']
    data_dir = args.qemu_data_dir or os.environ.get('QEMU_DATA_DIR')
    bios = args.bios or os.environ.get('QEMU_BIOS_PATH')
    if data_dir:
        data_path = Path(data_dir).expanduser().resolve()
        if not data_path.is_dir():
            raise RunnerError(f'QEMU data directory does not exist: {data_path}')
        command += ['-L', str(data_path)]
    if bios:
        bios_path = Path(bios).expanduser().resolve()
        if not bios_path.is_file():
            raise RunnerError(f'QEMU BIOS image does not exist: {bios_path}')
        command += ['-bios', str(bios_path)]
    if args.machine:
        command += ['-machine', args.machine]
    if args.cpu:
        command += ['-cpu', args.cpu]
    command += [
        '-drive', f'file={overlay},if=virtio,format=qcow2',
        '-drive', f'file={seed},if=virtio,format=raw,readonly=on',
        '-netdev', f'user,id=net0,hostfwd=tcp:127.0.0.1:{port}-:22,hostfwd=tcp:127.0.0.1:{getattr(args, "probe_port", 22464)}-:18482,hostfwd=udp:127.0.0.1:{getattr(args, "udp_probe_port", 22465)}-:18483',
        '-device', 'virtio-net-pci,netdev=net0,romfile=',
    ]
    qemu_env = os.environ.copy()
    if 'QEMU_MODULE_DIR' in os.environ:
        modules = Path(os.environ['QEMU_MODULE_DIR']).expanduser().resolve()
        if not modules.is_dir():
            raise RunnerError(f'QEMU module directory does not exist: {modules}')
        qemu_env['QEMU_MODULE_DIR'] = str(modules)
    return command, qemu_env


def create_overlay(base: Path, overlay: Path) -> None:
    qemu_img = executable('qemu-img')
    host_command([qemu_img, 'create', '-q', '-f', 'qcow2', '-F', 'qcow2', '-b', str(base), str(overlay)], timeout=90)
    host_command([qemu_img, 'resize', str(overlay), '12G'], timeout=60)
    overlay.chmod(0o600)


class Guest:
    def __init__(self, *, key: Path, known_hosts: Path, port: int, log: Log):
        self.key = key
        self.known_hosts = known_hosts
        self.port = port
        self.log = log
        self.tokens: set[str] = set()
        self.artifacts = getattr(log, 'path', None)
        self.artifacts = self.artifacts.parent if self.artifacts is not None else None
        self.output_counter = 0
        self.base_ssh = [
            executable('ssh'), '-F', '/dev/null', '-i', str(key), '-p', str(port),
            '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'ConnectionAttempts=1',
            '-o', 'ControlMaster=no', '-o', 'ControlPath=none', '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none', '-o', 'ForwardAgent=no',
            '-o', f'UserKnownHostsFile={known_hosts}', f'{SSH_USER}@{SSH_HOST}',
        ]
        self.base_scp = [
            executable('scp'), '-F', '/dev/null', '-i', str(key), '-P', str(port),
            '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'ControlMaster=no',
            '-o', 'ControlPath=none', '-o', 'StrictHostKeyChecking=accept-new',
            '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none', '-o', 'ForwardAgent=no',
            '-o', f'UserKnownHostsFile={known_hosts}',
        ]

    def sanitize(self, text: str, secrets: tuple[str, ...] = ()) -> str:
        for secret in (*self.tokens, *secrets):
            if secret:
                text = text.replace(secret, '[redacted]')
        text = re.sub(r'(?i)(l4d2-rollback-)[A-Za-z0-9_-]{16,}', r'\1[redacted]', text)
        text = re.sub(r'(?i)(token["\s:=]+)[A-Za-z0-9_-]{16,}', r'\1[redacted]', text)
        return text

    def save_output(self, label: str, stdout: bytes, stderr: bytes,
                    secrets: tuple[str, ...] = ()) -> Path | None:
        if self.artifacts is None:
            return None
        self.output_counter += 1
        slug = re.sub(r'[^A-Za-z0-9._-]+', '-', label.lower()).strip('-')[:64] or 'guest-command'
        path = self.artifacts / f'case-{self.output_counter:03d}-{slug}.log'
        out = self.sanitize(stdout.decode(errors='replace'), secrets)
        err = self.sanitize(stderr.decode(errors='replace'), secrets)
        path.write_text(f'--- stdout ---\n{out}\n--- stderr ---\n{err}\n', encoding='utf-8')
        path.chmod(0o600)
        return path

    def ssh(self, command: str, *, label: str, timeout: int = 60,
            check: bool = True, secrets: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run([*self.base_ssh, command], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RunnerError(f'Guest command timed out ({label}, {timeout}s)') from exc
        if check and result.returncode:
            stderr = self.sanitize(result.stderr.decode(errors='replace')[-5000:], secrets)
            stdout = self.sanitize(result.stdout.decode(errors='replace')[-3000:], secrets)
            saved = self.save_output(label, result.stdout, result.stderr, secrets)
            suffix = f' Full sanitized output: {saved}' if saved else ''
            raise RunnerError(f'Guest command failed ({label}, rc={result.returncode}):\n{stdout}\n{stderr}{suffix}')
        return result

    def root_shell(self, script: str, *, label: str, timeout: int = 120,
                   check: bool = True) -> subprocess.CompletedProcess:
        command = 'sudo -n /usr/bin/bash -c ' + shlex.quote(script)
        return self.ssh(command, label=label, timeout=timeout, check=check)

    def run_guest(self, label: str, command: str, *, timeout: int = 300) -> str:
        self.log.write(f'START {label}')
        result = self.root_shell(
            f'/usr/bin/timeout --foreground --kill-after=15 {timeout}s /usr/bin/bash -lc {shlex.quote(command)}',
            label=label, timeout=timeout + 30, check=False,
        )
        saved = self.save_output(label, result.stdout, result.stderr)
        raw_output = self.sanitize(result.stdout.decode(errors='replace')).strip()
        error_output = self.sanitize(result.stderr.decode(errors='replace')).strip()
        output = '\n'.join(part for part in (raw_output, error_output) if part)
        if result.returncode:
            raise RunnerError(f'{label} failed with exit status {result.returncode}; see sanitized log {saved}')
        if output:
            if any(line.lstrip().startswith('SKIP:') for line in output.splitlines()):
                raise RunnerError(f'{label} reported SKIP; skip is not an acceptable pass')
            for line in output.splitlines()[-30:]:
                self.log.write(f'{label}: {line}')
        self.log.write(f'PASS {label}')
        return output

    def wait_ready(self, timeout: int, *, boot_id: str | None = None,
                   qemu_process: subprocess.Popen | None = None) -> str:
        deadline = time.monotonic() + timeout
        last_error = ''
        while time.monotonic() < deadline:
            if qemu_process is not None and qemu_process.poll() is not None:
                raise RunnerError(f'QEMU exited during guest readiness (rc={qemu_process.returncode})')
            try:
                result = self.ssh(
                    'sudo -n /usr/bin/bash -c ' + shlex.quote(
                        'test -f /run/l4d2-suite-vm.json && test "$(stat -c %u:%a /run/l4d2-suite-vm.json)" = 0:600 && cat /proc/sys/kernel/random/boot_id'
                    ),
                    label='guest readiness', timeout=12,
                )
                value = result.stdout.decode().strip()
                if value and (boot_id is None or value != boot_id):
                    return value
            except RunnerError as exc:
                last_error = str(exc)
            time.sleep(2)
        raise RunnerError(f'Guest did not become ready within {timeout}s; last error: {last_error}')

    def install_docker(self, archive: Path) -> None:
        remote = f'/tmp/l4d2-docker-{uuid.uuid4().hex}.tgz'
        self.log.write('START install Docker static archive (checksum-verified)')
        try:
            result = subprocess.run([*self.base_scp, str(archive), f'{SSH_USER}@{SSH_HOST}:{remote}'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, check=False)
            if result.returncode:
                raise RunnerError('Secure copy of Docker archive failed: ' + result.stderr.decode(errors='replace')[-3000:])
            verify_and_install = (
                f"printf '%s  %s\\n' {shlex.quote(DOCKER_SHA256)} {shlex.quote(remote)} | sha256sum -c - "
                f"&& tar --no-same-owner -xzf {shlex.quote(remote)} -C /usr/local/bin --strip-components=1 docker "
                f"&& rm -f {shlex.quote(remote)} "
                "&& /usr/local/bin/dockerd --version | grep -F '29.8.2' "
                "&& /usr/local/bin/docker --version | grep -F '29.8.2'"
            )
            output = self.root_shell(verify_and_install, label='install Docker static 29.8.2', timeout=90)
            self.log.write(output.stdout.decode(errors='replace').strip())
            self.log.write('PASS install Docker static archive')
        except BaseException:
            try:
                self.root_shell(f'rm -f {shlex.quote(remote)}', label='remove partial Docker archive', timeout=20, check=False)
            except BaseException:
                pass
            raise

    def install_suite(self, archive: Path) -> None:
        remote = f'/tmp/l4d2-suite-{uuid.uuid4().hex}.tar.gz'
        self.log.write('START install root-owned product tree and writable unprivileged unit copy')
        uploaded = subprocess.run([*self.base_scp, str(archive), f'{SSH_USER}@{SSH_HOST}:{remote}'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, check=False)
        if uploaded.returncode:
            raise RunnerError('Secure copy of suite archive failed: ' + uploaded.stderr.decode(errors='replace')[-3000:])
        command = (
            'set -euo pipefail; '
            f'sudo -n install -d -o root -g root -m 0755 {INSTALL_ROOT}; '
            f'sudo -n tar --no-same-owner -xzf {shlex.quote(remote)} -C {INSTALL_ROOT}; '
            f'sudo -n find {INSTALL_ROOT} -type d -exec chmod go-w {{}} +; '
            f'sudo -n find {INSTALL_ROOT} -type f -exec chmod go-w {{}} +; '
            f'sudo -n install -o root -g root -m 0644 {INSTALL_ROOT}/systemd/l4d2-firewall*.service /etc/systemd/system/; '
            'sudo -n systemctl daemon-reload; '
            f'cd {INSTALL_ROOT} && sudo -n git init -q && sudo -n git add -A; '
            f'sudo -n /usr/bin/python3 -I -c "import sys;sys.path.insert(0,\'{INSTALL_ROOT}\');from core.config import trusted;trusted(\'{INSTALL_ROOT}\')"; '
            f'sudo -n install -d -o {UNIT_USER} -g {UNIT_USER} -m 0755 {UNIT_ROOT}; '
            f'sudo -n -u {UNIT_USER} -- tar --no-same-owner -xzf {shlex.quote(remote)} -C {UNIT_ROOT}; '
            f'sudo -n chown -R {UNIT_USER}:{UNIT_USER} {UNIT_ROOT}; '
            f'sudo -n chmod -R u+rwX {UNIT_ROOT}; '
            f'sudo -n -u {UNIT_USER} -- /usr/bin/bash -c '
            + shlex.quote('test "$(id -u)" -ne 0 && command -v sudo >/dev/null && ! sudo -n true >/dev/null 2>&1') + '; '
            f'sudo -n rm -f {shlex.quote(remote)}; '
            f'test "$(sudo -n stat -c %U:%G {UNIT_ROOT})" = {UNIT_USER}:{UNIT_USER}'
        )
        try:
            result = self.ssh(command, label='install root-owned suite and unprivileged unit copy', timeout=180)
            self.log.write(result.stdout.decode(errors='replace').strip() or 'both source trees and trust verified')
            self.log.write('PASS install root-owned product tree and writable unprivileged unit copy')
        except BaseException:
            try:
                self.root_shell(f'rm -f {shlex.quote(remote)}', label='remove partial suite archive', timeout=20, check=False)
            except BaseException:
                pass
            raise

    def tx(self, phase: str, *arguments: str, timeout: int = 90,
           secrets: tuple[str, ...] = ()) -> dict:
        safe_phase = phase
        self.log.write(f'START production transaction phase {safe_phase}')
        args = ' '.join(shlex.quote(value) for value in (phase, *arguments))
        script = (
            'set -eu; '
            'exec sudo -n env SSH_CONNECTION="$SSH_CONNECTION" '
            f'/usr/bin/timeout --foreground --kill-after=10 {timeout}s '
            f'/usr/bin/python3 -I {INSTALL_ROOT}/tests/vm/transactions.py {args}'
        )
        result = self.ssh(script, label=f'transaction {phase}', timeout=timeout + 20,
                          secrets=tuple(self.tokens) + secrets)
        output = result.stdout.decode(errors='replace').strip()
        try:
            payload = json.loads(output.splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            cleanup_output = {
                'cleanup': 'Disposable guest nftables state disabled and test persistence removed.',
            }
            if phase in cleanup_output and output == cleanup_output[phase]:
                payload = {'phase': phase, 'cleanup': 'complete'}
            else:
                raise RunnerError(f'Transaction phase {phase} did not return its expected result') from exc
        for name in ('token', 'rollback_token'):
            value = payload.get(name)
            if isinstance(value, str) and value:
                self.tokens.add(value)
        if payload.get('phase') != TX_RESULT_PHASE.get(phase):
            raise RunnerError(f'Transaction phase {phase} returned an unexpected result')
        self.log.write(f'PASS production transaction phase {phase}')
        return payload

    def reboot(self, label: str, timeout: int) -> None:
        old_id = self.ssh(
            'cat /proc/sys/kernel/random/boot_id', label=f'read pre-{label} boot id', timeout=15,
        ).stdout.decode().strip()
        result = self.ssh(
            'sudo -n /usr/bin/systemctl reboot', label=f'request {label}', timeout=20,
            check=False,
        )
        # The SSH transport normally ends with 255 after systemd tears it down.
        if result.returncode == 0:
            self.log.write(f'{label}: reboot command returned before transport closed')
        # Starting a new SSH command can race with the reboot request. Wait until
        # the old system disappears, then require a different boot ID and marker.
        deadline = time.monotonic() + timeout
        saw_disconnect = result.returncode != 0
        last_error = ''
        while time.monotonic() < deadline:
            try:
                probe = self.ssh('cat /proc/sys/kernel/random/boot_id', label=f'wait {label}', timeout=8)
                current_id = probe.stdout.decode().strip()
                if current_id != old_id:
                    saw_disconnect = True
                    self.wait_ready(min(120, max(20, int(deadline-time.monotonic()))), boot_id=old_id)
                    self.log.write(f'PASS {label}; boot id changed')
                    return
            except RunnerError as exc:
                saw_disconnect = True
                last_error = str(exc)
            time.sleep(2)
        if not saw_disconnect:
            raise RunnerError(f'{label} did not disconnect/reboot guest')
        raise RunnerError(f'{label} did not return with a new boot id: {last_error}')


def check_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            sock.bind(('127.0.0.1', port))
        except OSError as exc:
            raise RunnerError(f'Loopback SSH forwarding port 127.0.0.1:{port} is unavailable: {exc}') from exc


def check_udp_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError as exc:
            raise RunnerError(f'Loopback UDP probe port 127.0.0.1:{port} is unavailable: {exc}') from exc


def copy_serial(path: Path, artifacts: Path, guest: Guest | None = None) -> None:
    if path.is_file():
        output = path.read_text(encoding='utf-8', errors='replace')
        if guest is not None:
            output = guest.sanitize(output)
        target = artifacts / 'serial.log'
        target.write_text(output, encoding='utf-8')
        target.chmod(0o600)


def unit_cases() -> list[tuple[str, str]]:
    """Return every offline unit command and its guest execution identity."""
    return [
        ('python3 -I tests/test_core.py', UNIT_USER),
        ('python3 -I tests/test_geoip.py', UNIT_USER),
        ('python3 -I tests/test_transactions.py', UNIT_USER),
        ('python3 -I tests/test_configuration_audit.py', UNIT_USER),
        ('python3 -I tests/test_policy_audit.py', UNIT_USER),
        ('python3 -I tests/test_docker_topology.py', UNIT_USER),
        ('python3 -I tests/test_h2.py', UNIT_USER),
        ('python3 -I tests/test_boot.py', UNIT_USER),
        ('python3 -I tests/vm/test_transactions_harness.py', UNIT_USER),
        ('python3 -I tests/vm/test_boot_harness.py', UNIT_USER),
        ('python3 -I tests/vm/test_boot_cleanup.py', UNIT_USER),
        ('bash tests/watcher-audit.sh', UNIT_USER),
        ('bash tests/http-https-protect.sh', UNIT_USER),
        ('bash tests/public-ip-watch.sh', UNIT_USER),
        ('bash tests/generate.sh', UNIT_USER),
    ]


def unit_execution_command(command: str, identity: str) -> str:
    script = (
        'set -euo pipefail; '
        'if [ "$(id -u)" -eq 0 ]; then echo "unit test must not run as root" >&2; exit 97; fi; '
        'command -v sudo >/dev/null 2>&1 || { echo "sudo isolation check unavailable" >&2; exit 98; }; '
        'if sudo -n true >/dev/null 2>&1; then echo "unit account unexpectedly has sudo" >&2; exit 99; fi; '
        f'cd {shlex.quote(UNIT_ROOT)}; '
        f'exec {command}'
    )
    return f'sudo -n -u {shlex.quote(identity)} -- /usr/bin/bash -lc {shlex.quote(script)}'


def run_tests(guest: Guest, logger: Log) -> None:
    for cmd, identity in unit_cases():
        guest_command = unit_execution_command(cmd, identity)
        guest.run_guest(f'unit ({identity}) {cmd}', guest_command, timeout=180)

    for frontend in ('nft', 'legacy'):
        for name, script in (
            ('check', 'tests/check-engine.py'),
            ('integration', 'tests/integration.py'),
            ('transaction', 'tests/transaction-flows.py'),
            ('policy', 'tests/policy-flows.py'),
            ('Docker topology', 'tests/docker-topology-flows.py'),
            ('normalized state lifecycle', 'tests/h2-flows.py'),
            ('early barrier packets', 'tests/boot-flows.py'),
        ):
            command = f'cd {INSTALL_ROOT} && env SUITE_TEST_FRONTEND={frontend} bash tests/isolated-run.sh --root-net {script}'
            # Integration includes real watchdog expiry, kernel writes and
            # traffic for both engines; TCG is slower than hardware KVM.
            guest.run_guest(f'{name} frontend={frontend}', command,
                            timeout=1200 if name == 'integration' else 600)

    guest.run_guest('OpenVPN client flows', f'cd {INSTALL_ROOT} && tests/vm/clients.sh', timeout=360)
    guest.run_guest('offline GeoIP updater and traffic', f'cd {INSTALL_ROOT} && tests/vm/geoip.sh', timeout=240)

    docker_cases = (
        ('iptables', 'iptables', 'nft'),
        ('iptables', 'iptables', 'legacy'),
        ('nftables', 'iptables', 'nft'),
        ('nftables', 'iptables', 'legacy'),
        ('nftables', 'nftables', 'nft'),
    )
    for suite_backend, docker_backend, frontend in docker_cases:
        case = f'docker suite={suite_backend} daemon={docker_backend} frontend={frontend}'
        command = (f'cd {INSTALL_ROOT} && tests/vm/docker.sh --suite-backend {suite_backend} '
                   f'--docker-backend {docker_backend} --iptables-frontend {frontend}')
        # Exit 77 (SKIP) is a failure: this fixed matrix may not go green by omission.
        guest.run_guest(case, command, timeout=900)

    logger.write('PASS complete kernel, client, GeoIP and Docker matrices')


def run_transactions(guest: Guest, logger: Log) -> None:
    guest.tx('bootstrap')
    armed = guest.tx('arm-fresh-ssh', timeout=150)
    token = armed.get('token')
    if not isinstance(token, str) or not token:
        raise RunnerError('arm-fresh-ssh did not return a confirmation token')
    # tx() uses a new SSH subprocess with ControlMaster explicitly disabled.
    guest.tx('confirm-fresh-ssh', token, timeout=120, secrets=(token,))

    guest.tx('arm-kill-worker', timeout=100)
    guest.tx('kill-committed-worker', timeout=60)
    logger.write('WAIT systemd rollback after SIGKILL (bounded 40s)')
    time.sleep(40)
    guest.tx('verify-killed-worker-rollback', timeout=90)

    guest.tx('arm-abandoned-session', timeout=60)
    logger.write('WAIT systemd rollback after abandoned SSH session (bounded 20s)')
    time.sleep(20)
    guest.tx('verify-abandoned-rollback', timeout=90)
    guest.tx('prepare-reboot')
    guest.reboot('nftables persistence reboot', timeout=300)
    guest.tx('post-reboot', timeout=120)
    guest.tx('cleanup', timeout=120)

    guest.tx('bootstrap-legacy', timeout=150)
    guest.tx('prepare-reboot-legacy', timeout=90)
    guest.reboot('iptables-legacy persistence reboot', timeout=300)
    guest.tx('post-reboot-legacy', timeout=120)
    guest.tx('cleanup-legacy', timeout=120)
    logger.write('PASS production transaction lifecycle, deadlines, SSH reconnection, SIGKILL and both reboots')



def external_probe(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.4) as connection:
            connection.settimeout(0.4)
            connection.sendall(b'GET / HTTP/1.0\r\nHost: probe\r\n\r\n')
            response = b''
            while len(response) < 8192:
                chunk = connection.recv(8192)
                if not chunk:
                    break
                response += chunk
            return b'H3-CONTAINER' in response
    except OSError:
        return False


def external_tcp_response(port):
    try:
        connection = socket.create_connection(('127.0.0.1', port), timeout=0.4)
    except OSError:
        return None
    response = bytearray()
    with connection:
        try:
            connection.settimeout(0.4)
            connection.sendall(b'GET / HTTP/1.0\r\nHost: probe\r\n\r\n')
            while len(response) < 8192:
                chunk = connection.recv(8192)
                if not chunk:
                    break
                response.extend(chunk)
        except OSError:
            # SLIRP can complete a hostfwd handshake locally while the guest
            # drops traffic. Only bytes received from the fixture prove that
            # its application was reached through this proxy channel.
            pass
    return bytes(response) or None


def external_udp_response(port):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.settimeout(0.5)
        try:
            connection.bind(('127.0.0.1', 0))
            connection.sendto(b'h3-udp-probe', ('127.0.0.1', port))
            response, _ = connection.recvfrom(4096)
            return response
        except OSError:
            return None


def run_boot_closure(guest: Guest, logger: Log, probe_port: int, udp_probe_port: int) -> None:
    stage = {'name': 'setup'}
    def phase(name, timeout=240):
        stage['name'] = name
        command = ('sudo -n env SSH_CONNECTION="$SSH_CONNECTION" '
                   f'/usr/bin/timeout --foreground --kill-after=15 {timeout}s '
                   f'/usr/bin/python3 -I {INSTALL_ROOT}/tests/vm/closure_boot.py ' + shlex.quote(name))
        logger.write('START boot closure ' + name)
        result = guest.ssh(command, label='boot closure ' + name, timeout=timeout + 30)
        guest.save_output('boot closure ' + name, result.stdout, result.stderr)
        output = result.stdout.decode(errors='replace')
        logger.write('PASS boot closure ' + name)
        try:
            payload = json.loads(output.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as exc:
            raise RunnerError('Boot closure phase did not return JSON: ' + name) from exc
        if payload.get('phase') != name:
            raise RunnerError('Unexpected boot closure phase: ' + name)
    for name in ('bootstrap', 'stage-guard', 'verify-ready', 'failure-cases', 'calibrate-probe'):
        phase(name)
    if not any(external_probe(probe_port) for _ in range(5)):
        raise RunnerError('External TCP positive control could not reach the actual container')
    if not any(external_udp_response(udp_probe_port) == b'H3-UDP' for _ in range(5)):
        raise RunnerError('External UDP positive control could not reach the actual container')
    phase('restrict-probe')
    if external_tcp_response(probe_port) is not None or external_udp_response(udp_probe_port) is not None:
        raise RunnerError('Restricted external TCP/UDP source still reached the container')
    stop = threading.Event()
    samples = []
    def monitor():
        while not stop.is_set():
            for protocol, probe, port in (('tcp', external_tcp_response, probe_port),
                                          ('udp', external_udp_response, udp_probe_port)):
                started = time.monotonic()
                sample = {'utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                          'protocol': protocol, 'stage': stage['name'],
                          'started_monotonic': started}
                sample['exposed'] = probe(port) is not None
                sample['duration_seconds'] = time.monotonic() - started
                samples.append(sample)
            stop.wait(0.05)
    worker = threading.Thread(target=monitor, name='external-container-probe', daemon=True)
    worker.start()
    try:
        phase('docker-restart')
        phase('pre-failed-reboot')
        stage['name'] = 'failed-reboot'
        guest.reboot('unsupported persisted-schema fail-closed reboot', timeout=300)
        phase('post-failed-reboot', timeout=360)
        phase('pre-reboot')
        stage['name'] = 'valid-reboot'
        guest.reboot('valid early barrier and Docker live-restore reboot', timeout=300)
        phase('post-reboot', timeout=360)
    finally:
        stop.set()
        worker.join(timeout=2)
        path = logger.path.parent / 'external-probes.json'
        path.write_text(json.dumps(samples, indent=2) + '\n')
        path.chmod(0o600)
        summary = external_probe_summary(samples)
        summary_path = logger.path.parent / 'external-probe-summary.json'
        summary_path.write_text(json.dumps(summary, indent=2) + '\n')
        summary_path.chmod(0o600)
    if not samples or any(sample['exposed'] for sample in samples):
        raise RunnerError('Unauthorized TCP/UDP container response during boot/Docker transition; see external-probes.json')
    if not {'tcp', 'udp'} <= {sample['protocol'] for sample in samples}:
        raise RunnerError('External TCP/UDP transition monitor did not sample both protocols')
    for protocol, values in summary.items():
        if values['max_start_gap_seconds'] > 3:
            raise RunnerError(f'External {protocol} probe gap exceeded the declared 3-second sampling bound')
        if not {'docker-restart', 'failed-reboot', 'valid-reboot'} <= set(values['stages']):
            raise RunnerError(f'External {protocol} probe missed a required transition')
    logger.write(f'PASS external probes: {len(samples)} TCP/UDP attempts, no unauthorized response')
    phase('cleanup')
    logger.write('PASS early boot barrier, kernel readiness, restoration failures and Docker restart/reboot')


def external_probe_summary(samples):
    result = {}
    for protocol in ('tcp', 'udp'):
        rows = [row for row in samples if row['protocol'] == protocol]
        result[protocol] = {
            'attempts': len(rows), 'exposed': sum(row['exposed'] for row in rows),
            'max_start_gap_seconds': max((b['started_monotonic'] - a['started_monotonic']
                                         for a, b in zip(rows, rows[1:])), default=0),
            'max_duration_seconds': max((row['duration_seconds'] for row in rows), default=0),
            'stages': sorted({row['stage'] for row in rows}),
        }
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, help='cached Noble cloud image; SHA-256 is still verified')
    parser.add_argument('--docker-archive', '--dockerarchive', dest='docker_archive', type=Path,
                        help='cached Docker 29.8.2 static archive; SHA-256 is still verified')
    parser.add_argument('--ssh-port', '--port', dest='ssh_port', type=int, default=22462,
                        help='127.0.0.1-only guest SSH forward (default 22462)')
    parser.add_argument('--probe-port', type=int, default=22464, help='loopback-only external container probe forward')
    parser.add_argument('--udp-probe-port', type=int, default=22465,
                        help='loopback-only external UDP container probe forward')
    parser.add_argument('--boot-timeout', type=int, default=900, help='maximum seconds for cloud-init and SSH readiness')
    parser.add_argument('--memory', type=int, default=4096, help='guest memory in MiB')
    parser.add_argument('--cpus', type=int, default=4, help='guest vCPU count')
    parser.add_argument('--machine', help='optional QEMU machine name')
    parser.add_argument('--cpu', help='optional QEMU CPU model')
    parser.add_argument('--qemu-data-dir', type=Path, help='QEMU data directory (or QEMU_DATA_DIR)')
    parser.add_argument('--bios', type=Path, help='QEMU BIOS image (or QEMU_BIOS_PATH)')
    parser.add_argument('--artifacts-dir', type=Path, default=ROOT/'tmp'/'vm-runner-artifacts')
    parser.add_argument('--work-root', '--workdir', dest='work_root', type=Path,
                        default=ROOT/'tmp'/'vm-runner-work')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if (not all(1024 <= port <= 65535 for port in (args.ssh_port, args.probe_port, args.udp_probe_port))
            or len({args.ssh_port, args.probe_port, args.udp_probe_port}) != 3
            or args.memory < 2048 or args.cpus < 1):
        raise RunnerError('SSH/TCP/UDP loopback ports must be distinct and 1024-65535; memory at least 2048 MiB and CPUs positive')
    args.artifacts_dir = args.artifacts_dir.expanduser().resolve()
    args.work_root = args.work_root.expanduser().resolve()
    args.artifacts_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.work_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    artifacts = args.artifacts_dir / run_id
    artifacts.mkdir(mode=0o700)
    work = Path(tempfile.mkdtemp(prefix=run_id+'-', dir=args.work_root))
    logger = Log(artifacts/'runner.log')
    qemu_process: subprocess.Popen | None = None
    qemu_log = None
    serial_path = work/'serial.log'
    guest: Guest | None = None
    success = False
    try:
        check_port_available(args.ssh_port)
        check_port_available(args.probe_port)
        check_udp_port_available(args.udp_probe_port)
        for dependency in ('qemu-img', 'genisoimage', 'ssh', 'scp', 'ssh-keygen'):
            executable(dependency)
        image = (require_file(args.image.expanduser(), IMAGE_SHA256, 'Ubuntu Noble cloud image')
                 if args.image else download(IMAGE_URL, work/'noble-server-cloudimg-amd64.img', IMAGE_SHA256, 'Ubuntu Noble cloud image'))
        docker_archive = (require_file(args.docker_archive.expanduser(), DOCKER_SHA256, 'Docker static archive')
                          if args.docker_archive else download(DOCKER_URL, work/'docker-29.8.2.tgz', DOCKER_SHA256, 'Docker static archive'))
        logger.write(f'IMAGE verified sha256={IMAGE_SHA256}')
        logger.write(f'DOCKER archive verified sha256={DOCKER_SHA256}')
        overlay = work/'guest-overlay.qcow2'
        create_overlay(image, overlay)
        key = work/'id_ed25519'
        host_command([executable('ssh-keygen'), '-q', '-t', 'ed25519', '-N', '', '-C', f'l4d2-vm-{run_id}', '-f', str(key)], timeout=15)
        key.chmod(0o600)
        public_key = key.with_suffix('.pub').read_text(encoding='ascii').strip()
        known_hosts = work/'known_hosts'
        known_hosts.touch(mode=0o600)
        known_hosts.chmod(0o600)
        seed = make_seed(work, public_key, 'iid-l4d2-' + run_id)
        suite_archive = make_suite_archive(work)
        command, qemu_env = qemu_arguments(args, image, overlay, seed, work, args.ssh_port)
        logger.write('START disposable QEMU with loopback-only SSH forwarding')
        qemu_log = (artifacts/'qemu.log').open('wb')
        qemu_process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=qemu_log,
                                        stderr=subprocess.STDOUT, env=qemu_env, close_fds=True)
        guest = Guest(key=key, known_hosts=known_hosts, port=args.ssh_port, log=logger)
        logger.write(f'QEMU pid owned by runner: {qemu_process.pid}; accelerator={"kvm" if os.access("/dev/kvm", os.R_OK | os.W_OK) else "tcg"}')
        guest.wait_ready(args.boot_timeout, qemu_process=qemu_process)
        logger.write('SSH and disposable-VM marker verified')
        guest.run_guest('validate cloud-init schema', 'cloud-init schema --system', timeout=60)
        guest.ssh('sudo -n cloud-init status --wait', label='cloud-init provisioning', timeout=args.boot_timeout)
        guest.install_docker(docker_archive)
        guest.install_suite(suite_archive)
        guest.run_guest(
            'guest versions',
            f'cd {INSTALL_ROOT} && printf "kernel=" && uname -r && systemd --version | head -n 1 '
            '&& nft --version && iptables --version && openvpn --version | head -n 1 '
            '&& docker --version && dockerd --version',
            timeout=60,
        )
        run_tests(guest, logger)
        run_transactions(guest, logger)
        run_boot_closure(guest, logger, args.probe_port, args.udp_probe_port)
        logger.write('PASS runner completed all required validation cases; no SKIP case accepted')
        success = True
    except BaseException as exc:
        logger.write('FAIL ' + str(exc).replace('\n', ' ')[:5000])
        raise
    finally:
        if qemu_process is not None and qemu_process.poll() is None:
            # Only signal the QEMU child this runner started; never search by name/PID.
            qemu_process.terminate()
            try:
                qemu_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                qemu_process.kill()
                qemu_process.wait(timeout=10)
        if qemu_log is not None:
            qemu_log.close()
        copy_serial(serial_path, artifacts, guest)
        try:
            work.relative_to(args.work_root)
        except ValueError:
            raise RunnerError('Refusing to clean work data outside the configured work root')
        shutil.rmtree(work, ignore_errors=True)
        logger.write(f'ARTIFACTS {artifacts}')
        logger.close()
    return 0 if success else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except RunnerError as exc:
        print(f'vm-runner: {exc}', file=sys.stderr)
        raise SystemExit(2)
