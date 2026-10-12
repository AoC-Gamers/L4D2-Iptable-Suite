#!/usr/bin/env python3
"""Guest-side fail-closed boot tests for H3.

Every mutating phase requires the QEMU attestation marker and a root-owned
installation at /opt/l4d2-firewall. The host runner, not this script, controls
QEMU startup, SSH and reboot boundaries. See docs/security/closure-h3-testing.md.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import secrets
import sysconfig
import tarfile
import time
import uuid
import shutil

INSTALL = Path('/opt/l4d2-firewall')
STATE = Path('/var/lib/l4d2-firewall')
MARKER = Path('/run/l4d2-suite-vm.json')
MANIFEST = STATE / 'closure-h3-test.json'
RECOVERY = STATE / 'closure-h3-recovery.json'
ACCESS = STATE / 'closure-h3-access.json'
PROBE_HELPER = STATE / 'closure-h3-probe.py'
NETWORK_REGISTRY = Path('/run/l4d2-h3-network-owner.json')
NETNS_DIR = Path('/run/netns')
CLI = INSTALL / 'core/fw.py'
GUARD_TABLE = ('inet', 'l4d2_boot_guard')
FOREIGN_TABLE = ('inet', 'l4d2_h3_foreign_sentinel')
FOREIGN_COMMENT = 'l4d2-h3-test-foreign-sentinel'
EXTERNAL_FIREWALL_FILES = (Path('/etc/nftables.conf'), Path('/etc/iptables/rules.v6'))
PROBE_NETNS = 'l4d2-h3-probe'
PROBE_IFACE = 'h3host0'
PROBE_PEER = 'h3peer0'
PROBE_HOST = '198.18.0.1'
PROBE_CLIENT = '198.18.0.2'
PROBE_PORT = 18481
SOCKET_UNIT = 'l4d2-h3-probe.socket'
SERVICE_UNIT = 'l4d2-h3-probe.service'
NETWORK_UNIT = 'l4d2-h3-probe-network.service'
DOCKER_UNIT = Path('/etc/systemd/system/docker.service')
DOCKER_SOCKET = '/var/run/docker.sock'
DOCKER_NETWORK = 'l4d2-h3-closure'
DOCKER_BRIDGE = 'h3br0'
DOCKER_ADDRESS = '172.29.0.10'
DOCKER_PUBLIC_PORT = 18482
DOCKER_PRIVATE_PORT = 18443
DOCKER_UDP_PUBLIC_PORT = 18483
DOCKER_UDP_PRIVATE_PORT = 18444
DOCKER_IMAGE = 'l4d2-h3-local:latest'
DOCKER_NAME = 'l4d2-h3-probe'
DOCKER_DROPIN = Path('/etc/systemd/system/docker.service.d/10-l4d2-firewall.conf')
FULL_DROPIN = Path('/etc/systemd/system/l4d2-firewall.service.d/10-docker.conf')
DOCKER_PAUSE = Path('/etc/systemd/system/docker.service.d/99-h3-restart-window.conf')
UNIT_FILES = (
    SOCKET_UNIT,
    SERVICE_UNIT,
)


class H3Error(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise H3Error(message)


def run(argv, *, check=True, timeout=30, input_text=None, env=None):
    try:
        result = subprocess.run(
            [str(arg) for arg in argv], text=True, input=input_text,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
            env=env, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise H3Error(f'Command failed or timed out: {argv[0]}: {exc}') from exc
    if check and result.returncode:
        raise H3Error(f"Command failed ({result.returncode}): {' '.join(map(str, argv))}\n"
                       f'{result.stdout}{result.stderr}')
    return result


def safe_guest() -> None:
    require(os.geteuid() == 0, 'Run only as root inside the disposable QEMU guest')
    virtualization = run(['systemd-detect-virt', '--vm']).stdout.strip()
    require(virtualization in ('qemu', 'kvm'), f'Expected QEMU/KVM, got {virtualization!r}')
    try:
        info = MARKER.lstat()
        marker = json.loads(MARKER.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise H3Error(f'Missing or invalid QEMU safety marker: {exc}') from exc
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o600,
            f'{MARKER} must be a root-owned regular file with mode 0600')
    require(marker == {'virtualization': 'qemu', 'disposable': True}, 'Unexpected QEMU safety marker')
    require(Path('/proc/1/comm').read_text().strip() == 'systemd', 'systemd must be PID 1')
    require(INSTALL.resolve() == Path('/opt/l4d2-firewall') and CLI.is_file(),
            'Expected the installed trusted suite at /opt/l4d2-firewall')
    sys.path.insert(0, str(INSTALL))
    from core.config import trusted
    trusted(INSTALL)
    trusted(INSTALL / 'core')
    trusted(CLI)
    for name in ('l4d2-firewall-guard.service', 'l4d2-firewall.service', 'l4d2-firewall-ready.service'):
        source = INSTALL / 'systemd' / name
        require(source.is_file(), f'Missing H3 production unit template: {source}')
        trusted(source)
    require(not os.environ.get('DOCKER_HOST'), 'DOCKER_HOST must be unset; remote Docker targets are forbidden')


def cli(*args, check=True, timeout=60):
    return run(['/usr/bin/python3', '-I', str(CLI), *args], check=check, timeout=timeout)


def store_json(name):
    path = STATE / f'{name}.json'
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None


def write_json(path: Path, value) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.h3-tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temp, path)


def path_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def require_absent(path: Path, description: str) -> None:
    require(not path_exists(path), f'Refusing pre-existing {description}: {path}')


def read_owned_regular(path: Path, *, mode=0o600) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise H3Error(f'Cannot safely open owned fixture {path}: {exc}') from exc
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0
                and stat.S_IMODE(info.st_mode) == mode,
                f'Owned fixture has unexpected type, owner or mode: {path}')
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b''.join(chunks)
    finally:
        os.close(fd)


def write_new_owned_file(path: Path, content: bytes, *, mode=0o600) -> str:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    info = os.fstat(fd)
    try:
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0,
                f'New owned fixture is not a root-owned regular file: {path}')
        view = memoryview(content)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        try:
            current = path.lstat()
            if (current.st_dev, current.st_ino) == (info.st_dev, info.st_ino):
                path.unlink()
        except (OSError, ValueError):
            pass
        raise
    else:
        os.close(fd)
    return hashlib.sha256(content).hexdigest()


def owned_file_digest(state, path: Path) -> str:
    expected = state.get('owned_files', {}).get(str(path))
    require(isinstance(expected, str) and len(expected) == 64,
            f'No ownership digest recorded for fixture {path}')
    mode = state.get('owned_file_modes', {}).get(str(path), 0o600)
    digest_value = hashlib.sha256(read_owned_regular(path, mode=mode)).hexdigest()
    require(digest_value == expected, f'Refusing to overwrite or remove modified fixture {path}')
    return expected


def write_new_manifest_file(state, path: Path, content: bytes, *, mode=0o600) -> None:
    require_absent(path, 'H3 fixture file')
    require_absent(path.with_name(path.name + '.h3-tmp'), 'H3 fixture temporary file')
    digest_value = write_new_owned_file(path, content, mode=mode)
    state.setdefault('owned_files', {})[str(path)] = digest_value
    state.setdefault('owned_file_modes', {})[str(path)] = mode
    save_manifest(state)


def replace_owned_json(state, path: Path, value) -> None:
    owned_file_digest(state, path)
    payload = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    temp = path.with_name(path.name + '.h3-update')
    require_absent(temp, 'H3 fixture update file')
    digest_value = write_new_owned_file(temp, payload, mode=0o600)
    try:
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    require(hashlib.sha256(read_owned_regular(path)).hexdigest() == digest_value,
            f'Updated fixture failed its ownership check: {path}')
    state.setdefault('owned_files', {})[str(path)] = digest_value
    state.setdefault('owned_file_modes', {})[str(path)] = 0o600
    save_manifest(state)


def manifest():
    try:
        value = json.loads(read_owned_regular(MANIFEST).decode())
    except (OSError, json.JSONDecodeError) as exc:
        raise H3Error(f'Missing or invalid H3 test manifest: {exc}') from exc
    require(isinstance(value, dict), 'Invalid H3 test manifest type')
    return value


def save_manifest(value):
    if path_exists(MANIFEST):
        read_owned_regular(MANIFEST)
    write_json(MANIFEST, value)


def hash_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def file_state(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode):
        payload = {'kind': 'symlink', 'target': os.readlink(path)}
    elif stat.S_ISREG(info.st_mode):
        payload = {'kind': 'file', 'sha256': hash_bytes(path.read_bytes())}
    else:
        payload = {'kind': 'other'}
    payload.update({'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid})
    return payload


def sentinel_state(create=False):
    listed = run(['nft', '-j', '-s', 'list', 'tables']).stdout
    entries = json.loads(listed).get('nftables', [])
    present = any(item.get('table', {}).get('family') == FOREIGN_TABLE[0]
                  and item.get('table', {}).get('name') == FOREIGN_TABLE[1] for item in entries)
    if not present:
        if not create:
            return None
        run(['nft', '-f', '-'], input_text=(
            f'add table {FOREIGN_TABLE[0]} {FOREIGN_TABLE[1]} {{ comment "{FOREIGN_COMMENT}"; }}\n'))
    raw = json.loads(run(['nft', '-j', '-s', 'list', 'table', *FOREIGN_TABLE]).stdout)
    tables = [entry['table'] for entry in raw.get('nftables', []) if 'table' in entry]
    require(len(tables) == 1 and tables[0].get('comment') == FOREIGN_COMMENT,
            'Sentinel table is not owned by this H3 test; refusing to adopt it')
    return hash_bytes(json.dumps(tables[0], sort_keys=True, separators=(',', ':')).encode())


def verify_preservation(state, *, after_reboot=False):
    for path in EXTERNAL_FIREWALL_FILES:
        require(file_state(path) == state.get('external_files', {}).get(str(path)),
                f'External firewall configuration changed during H3 test: {path}')
    current = sentinel_state(create=after_reboot)
    if after_reboot and current is not None:
        require(current == state.get('sentinel_digest'), 'Sentinel table changed over reboot')
    elif current is not None:
        require(current == state.get('sentinel_digest'), 'Unowned nftables sentinel table changed')
    elif not after_reboot:
        raise H3Error('Foreign sentinel table disappeared before reboot')


def install_unit(name, text):
    target = Path('/etc/systemd/system') / name
    require(not target.exists() and not target.is_symlink(), f'Refusing to replace pre-existing unit {target}')
    write_new_owned_file(target, text.encode(), mode=0o644)
    return hashlib.sha256(text.encode()).hexdigest()


def install_production_units():
    for name in ('l4d2-firewall-guard.service', 'l4d2-firewall.service', 'l4d2-firewall-ready.service'):
        target = Path('/etc/systemd/system') / name
        require(target.is_file() and not target.is_symlink(), f'Runner must install production unit {target}')
        require(target.read_bytes() == (INSTALL / 'systemd' / name).read_bytes(),
                f'Installed production unit differs from trusted template: {target}')
    protected_socket = (INSTALL / 'systemd/examples/protected-socket.conf').read_text()
    protected_service = (INSTALL / 'systemd/examples/protected-service.conf').read_text()
    owned = {}
    require(not (Path('/etc/systemd/system') / NETWORK_UNIT).exists()
            and not (Path('/etc/systemd/system') / NETWORK_UNIT).is_symlink(),
            f'Refusing pre-existing H3 network unit {NETWORK_UNIT}')
    owned[NETWORK_UNIT] = install_unit(NETWORK_UNIT, f'''[Unit]
Description=Disposable H3 veth probe network
DefaultDependencies=no
Requires=l4d2-firewall-guard.service
After=local-fs.target l4d2-firewall-guard.service
Before=network-pre.target l4d2-firewall.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/python3 -I {INSTALL / 'tests/vm/closure_boot.py'} create-probe-network
''')
    owned[SOCKET_UNIT] = install_unit(SOCKET_UNIT, '''[Unit]\nDescription=H3 disposable protected socket probe\n'''
                + protected_socket + f'''\n[Unit]
Requires={NETWORK_UNIT}
After={NETWORK_UNIT}

[Socket]
ListenStream=198.18.0.1:18481
Accept=no

[Install]
WantedBy=sockets.target
''')
    owned[SERVICE_UNIT] = install_unit(SERVICE_UNIT, '''[Unit]\nDescription=H3 disposable protected service probe\n'''
                + protected_service + '''\n[Service]\nType=simple\nExecStart=/usr/bin/python3 -I /var/lib/l4d2-firewall/closure-h3-probe.py\nRestart=no\n''')
    probe_payload = (
        'import socket\n'
        's=socket.fromfd(3, socket.AF_INET, socket.SOCK_STREAM)\n'
        'while True:\n'
        ' c,_=s.accept()\n'
        ' try: c.recv(128); c.sendall(b"H3-READY\\n")\n'
        ' finally: c.close()\n'
    ).encode()
    state = manifest()
    write_new_manifest_file(state, PROBE_HELPER, probe_payload, mode=0o700)
    run(['systemctl', 'daemon-reload'])
    return owned


def ssh_recovery():
    parts = os.environ.get('SSH_CONNECTION', '').split()
    require(len(parts) == 4, 'This phase needs SSH_CONNECTION from the authenticated runner SSH session')
    source, _source_port, destination, ssh_port = parts
    from core.config import network
    src, dst = network(source), network(destination)
    require(src.version == dst.version, 'SSH source and guest address families differ')
    result = run(['ip', '-o', 'route', 'get', source]).stdout.split()
    require('dev' in result, 'Cannot determine SSH recovery interface')
    input_iface = result[result.index('dev') + 1]
    return [{'source': str(src),
             'destination': str(dst),
             'input': input_iface, 'ports': ssh_port}]


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def probe_interface_identity():
    result = run(['ip', '-j', '-d', 'link', 'show', 'dev', PROBE_IFACE], check=False)
    if result.returncode:
        return None
    try:
        links = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise H3Error(f'Invalid ip link identity output: {exc}') from exc
    require(isinstance(links, list) and len(links) == 1, 'Unexpected probe interface query result')
    link = links[0]
    kind = link.get('linkinfo', {}).get('info_kind')
    require(link.get('ifname') == PROBE_IFACE and kind == 'veth',
            f'Probe interface name is occupied by a non-veth resource: {PROBE_IFACE}')
    identity = {'ifindex': link.get('ifindex'), 'address': link.get('address'), 'kind': kind}
    require(isinstance(identity['ifindex'], int) and isinstance(identity['address'], str),
            'Probe interface identity is incomplete')
    return identity


def probe_netns_identity():
    path = NETNS_DIR / PROBE_NETNS
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0,
            f'Probe namespace name is occupied by an unexpected resource: {path}')
    return {'dev': info.st_dev, 'ino': info.st_ino}


def current_probe_identity():
    namespace = probe_netns_identity()
    interface = probe_interface_identity()
    if namespace is None and interface is None:
        return None
    require(namespace is not None and interface is not None,
            'Only one probe network resource exists; preserving partial/unowned resources')
    return {'netns': namespace, 'host_veth': interface}


def read_network_registry():
    try:
        record = json.loads(read_owned_regular(NETWORK_REGISTRY).decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise H3Error(f'Invalid probe network ownership registry: {exc}') from exc
    require(isinstance(record, dict) and record.get('schema') == 1,
            'Unsupported probe network ownership registry')
    return record


def network_phase_can_create(state, current_boot):
    phase = state.get('phase')
    if phase == 'bootstrap-in-progress' and not state.get('network_boot_id'):
        return True
    return (phase in ('failed-reboot-prepared', 'reboot-prepared')
            and state.get('network_boot_id') != current_boot)


def create_probe_network():
    state = manifest()
    current_boot = boot_id()
    existing = current_probe_identity()
    if path_exists(NETWORK_REGISTRY):
        registry = read_network_registry()
        require(registry.get('owner') == state.get('owner_token'),
                'Probe network registry belongs to another test; preserving resources')
        require(registry.get('identity') == existing and existing is not None,
                'Probe network identity changed; preserving resources')
        owned_file_digest(state, NETWORK_REGISTRY)
        require(state.get('network_identity') == existing,
                'Manifest and probe network registry identities differ; preserving resources')
        require(registry.get('boot_id') == current_boot,
                'Probe network registry crossed a boot boundary unexpectedly; preserving resources')
        return
    require(existing is None, 'Probe network names are occupied without this test ownership registry')
    require(network_phase_can_create(state, current_boot),
            'Probe network ownership registry is absent outside initial setup or an authorized reboot')
    run(['ip', 'netns', 'add', PROBE_NETNS])
    run(['ip', 'link', 'add', PROBE_IFACE, 'type', 'veth', 'peer', 'name', PROBE_PEER])
    run(['ip', 'link', 'set', PROBE_PEER, 'netns', PROBE_NETNS])
    run(['ip', 'addr', 'add', f'{PROBE_HOST}/24', 'dev', PROBE_IFACE])
    run(['ip', 'link', 'set', PROBE_IFACE, 'up'])
    run(['ip', 'netns', 'exec', PROBE_NETNS, 'ip', 'link', 'set', 'lo', 'up'])
    run(['ip', 'netns', 'exec', PROBE_NETNS, 'ip', 'addr', 'add', f'{PROBE_CLIENT}/24', 'dev', PROBE_PEER])
    run(['ip', 'netns', 'exec', PROBE_NETNS, 'ip', 'link', 'set', PROBE_PEER, 'up'])
    identity = current_probe_identity()
    require(identity is not None, 'Probe network creation did not produce both owned resources')
    registry_bytes = (json.dumps({'schema': 1, 'owner': state['owner_token'],
                                  'boot_id': current_boot, 'identity': identity},
                                 sort_keys=True, indent=2) + '\n').encode()
    state.setdefault('owned_files', {})[str(NETWORK_REGISTRY)] = write_new_owned_file(
        NETWORK_REGISTRY, registry_bytes)
    state.setdefault('owned_file_modes', {})[str(NETWORK_REGISTRY)] = 0o600
    state['network_identity'] = identity
    state['network_boot_id'] = current_boot
    save_manifest(state)


def remove_probe_network(state):
    require(path_exists(NETWORK_REGISTRY), 'Probe network ownership registry is missing; preserving network')
    registry = read_network_registry()
    current = current_probe_identity()
    owned_file_digest(state, NETWORK_REGISTRY)
    require(registry.get('owner') == state.get('owner_token')
            and registry.get('identity') == current
            and state.get('network_identity') == current,
            'Probe network ownership/identity changed; preserving network and registry')
    if current is not None:
        run(['ip', 'link', 'del', PROBE_IFACE])
        run(['ip', 'netns', 'del', PROBE_NETNS])
    require(current_probe_identity() is None, 'Probe network remained after owned cleanup')
    NETWORK_REGISTRY.unlink()


def remove_owned_manifest_file(state, path: Path):
    if not path_exists(path):
        return
    owned_file_digest(state, path)
    path.unlink()


def probe():
    code = (
        'import socket; s=socket.socket(); s.settimeout(1.2); '
        f's.connect(({PROBE_HOST!r},{PROBE_PORT})); s.sendall(b"probe"); '
        'print(s.recv(100).decode().strip()); s.close()'
    )
    result = run(['ip', 'netns', 'exec', PROBE_NETNS, '/usr/bin/python3', '-c', code], check=False, timeout=4)
    return result.stdout.strip() if result.returncode == 0 else 'BLOCK'


def tcp_probe(port, timeout=0.5):
    code = (
        'import socket; s=socket.socket(); s.settimeout(' + repr(timeout) + '); '
        f's.connect(({PROBE_HOST!r},{port})); s.sendall(b"h3"); '
        'print(s.recv(100).decode()); s.close()'
    )
    result = run(['ip', 'netns', 'exec', PROBE_NETNS, '/usr/bin/python3', '-c', code],
                 check=False, timeout=max(3, timeout + 1))
    return result.stdout.strip() if result.returncode == 0 else 'BLOCK'


def require_guard(nft_binary='nft'):
    result = run([nft_binary, '-j', 'list', 'tables'])
    tables = json.loads(result.stdout).get('nftables', [])
    present = any(item.get('table', {}).get('family') == GUARD_TABLE[0]
                  and item.get('table', {}).get('name') == GUARD_TABLE[1] for item in tables)
    require(present, 'The owned H3 boot barrier table is missing')


def require_no_guard():
    result = run(['nft', '-j', 'list', 'tables'])
    tables = json.loads(result.stdout).get('nftables', [])
    present = any(item.get('table', {}).get('family') == GUARD_TABLE[0]
                  and item.get('table', {}).get('name') == GUARD_TABLE[1] for item in tables)
    require(not present, 'The H3 boot barrier unexpectedly remains installed after verified readiness')


def require_blocked_readiness(nft_binary='nft'):
    result = cli('ready', check=False)
    require(result.returncode != 0, 'ready unexpectedly succeeded while the boot barrier was active')
    require_guard(nft_binary)
    run(['systemctl', 'stop', SOCKET_UNIT, SERVICE_UNIT], check=False)
    run(['systemctl', 'reset-failed', 'l4d2-firewall-ready.service', SOCKET_UNIT, SERVICE_UNIT], check=False)
    start = run(['systemctl', 'start', SOCKET_UNIT], check=False, timeout=20)
    require(start.returncode != 0,
            'Protected socket start unexpectedly succeeded before readiness: '
            f'rc={start.returncode}, stdout={start.stdout.strip()!r}, stderr={start.stderr.strip()!r}')
    require(probe() == 'BLOCK', 'Host probe reached protected service while boot barrier was active')


def ensure_full_ready():
    require_no_guard()
    if run(['systemctl', 'is-active', '--quiet', 'l4d2-firewall.service'], check=False).returncode != 0:
        run(['systemctl', 'reset-failed', 'l4d2-firewall.service'], check=False)
        run(['systemctl', 'start', 'l4d2-firewall.service'], timeout=60)
    require(run(['systemctl', 'is-active', '--quiet', 'l4d2-firewall.service'], check=False).returncode == 0,
            'Full restore unit is not active before the next guarded transition')
    ready = json.loads(cli('ready').stdout)
    require(ready.get('ready'), 'The current firewall policy is not ready before the next guarded transition')


def boot_systemd_snapshot():
    units = ('l4d2-firewall-guard.service', 'l4d2-firewall.service',
             'l4d2-firewall-ready.service', 'docker.service', NETWORK_UNIT, SOCKET_UNIT)
    sections = []
    for unit in units:
        result = run(['systemctl', 'show', '--no-pager',
                      '--property=Id,ActiveState,SubState,Result,ExecMainStatus,Job', unit],
                     check=False, timeout=10)
        sections.append(f'[{unit}]\n{result.stdout}{result.stderr}')
    journal = run(['journalctl', '-b', '--no-pager', '--lines=100',
                   *sum((['-u', unit] for unit in units), [])],
                  check=False, timeout=20)
    sections.append('[journal]\n' + journal.stdout + journal.stderr)
    return '\n'.join(sections)[-18000:]


def wait_for_boot_jobs(timeout=180):
    try:
        result = subprocess.run(['systemctl', 'is-system-running', '--wait'],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        diagnostics = boot_systemd_snapshot()
        raise H3Error(f'Systemd boot jobs did not settle within {timeout}s.\n{diagnostics}') from exc
    state = result.stdout.strip()
    if state not in ('running', 'degraded'):
        diagnostics = boot_systemd_snapshot()
        raise H3Error(f'Systemd boot did not reach a settled running/degraded state '
                       f'(exit={result.returncode}, state={state!r}, stderr={result.stderr.strip()!r}).\n'
                       f'{diagnostics}')
    return state


def sigkill_after_barrier_before_empty_rollback():
    """Kill a test-only wrapper after nft commits the barrier, before restore continues."""
    from core.store import Store
    from core.boot import boot_id

    current = store_json('current')
    require(current and not current.get('disabled'), 'SIGKILL window requires a confirmed active suite policy')
    store = Store(STATE)
    with store.lock():
        require(store.get('pending') is None, 'Cannot inject the empty-previous rollback over a real transaction')
        store.put('pending', {
            'token': secrets.token_hex(16), 'deadline': time.time() - 1,
            'deadline_monotonic': time.monotonic() - 1, 'boot_id': boot_id(),
            'previous': None, 'snapshot': None, 'candidate': current,
        })
    nft = Path(shutil.which('nft') or '')
    require(str(nft) != '.' and nft.is_file() and not nft.is_symlink(),
            'SIGKILL test needs a regular nft executable path')
    real = nft.with_name(nft.name + '.h3-real')
    marker = Path('/run/l4d2-h3-after-barrier')
    require(not real.exists() and not marker.exists(), 'SIGKILL test path is already occupied')
    wrapper = '''#!/usr/bin/python3
import subprocess, sys, time
real = ''' + repr(str(real)) + '''
marker = ''' + repr(str(marker)) + '''
args = sys.argv[1:]
data = sys.stdin.buffer.read() if '-' in args else None
p = subprocess.run([real, *args], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
sys.stdout.buffer.write(p.stdout); sys.stderr.buffer.write(p.stderr)
if p.returncode == 0 and '-c' not in args and data and b'add table inet l4d2_boot_guard' in data:
    open(marker, 'w').write('committed\\n')
    time.sleep(90)
sys.exit(p.returncode)
'''
    proc = None
    os.replace(nft, real)
    try:
        nft.write_text(wrapper)
        nft.chmod(0o755)
        proc = subprocess.Popen(['/usr/bin/python3', '-I', str(CLI), 'boot-restore'],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=True)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and proc.poll() is None and not marker.exists():
            time.sleep(0.05)
        require(marker.exists(), 'boot-restore did not reach the deterministic post-barrier pause')
        os.killpg(proc.pid, __import__('signal').SIGKILL)
        proc.communicate(timeout=5)
        proc = None
    finally:
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid, __import__('signal').SIGKILL)
            proc.communicate(timeout=5)
        nft.unlink(missing_ok=True)
        os.replace(real, nft)
        marker.unlink(missing_ok=True)
    require_guard()
    require(store_json('pending') is not None and store_json('current') is not None,
            'SIGKILL unexpectedly cleared the transaction journal or current policy')
    pending = store_json('pending')
    cli('rollback', '--token', pending['token'])
    require(store_json('current') is None and store_json('pending') is None,
            'Empty-prior rollback did not leave the suite policy absent')
    require_guard()
    require(probe() == 'BLOCK', 'Boot barrier was removed by rollback to an empty prior snapshot')
    require(cli('ready', check=False).returncode != 0,
            'Readiness succeeded between empty-prior rollback and durable policy restore')
    # The subsequent boot restore reapplies the durable policy, then releases
    # only its independent barrier.
    cli('boot-restore')
    ensure_full_ready()
    require(store_json('pending') is None, 'Expired empty-previous journal survived recovery')


def bootstrap_preflight():
    for path, label in (
        (MANIFEST, 'H3 bootstrap manifest'),
        (NETWORK_REGISTRY, 'H3 network ownership registry'),
        (ACCESS, 'H3 access policy fixture'),
        (RECOVERY, 'H3 recovery fixture'),
        (PROBE_HELPER, 'H3 protected probe helper'),
        (Path('/etc/systemd/system') / NETWORK_UNIT, 'H3 network unit'),
        (Path('/etc/systemd/system') / SOCKET_UNIT, 'H3 socket unit'),
        (Path('/etc/systemd/system') / SERVICE_UNIT, 'H3 probe service unit'),
    ):
        require_absent(path, label)
        require_absent(path.with_name(path.name + '.h3-tmp'), label + ' temporary')
        require_absent(path.with_name(path.name + '.h3-update'), label + ' update temporary')
    require(current_probe_identity() is None,
            'Probe network names are already occupied; refusing bootstrap without deleting them')


def bootstrap():
    bootstrap_preflight()
    require(store_json('pending') is None and store_json('boot-policy') is None,
            'H3 bootstrap requires no pending transaction or existing boot protection')
    current, persisted = store_json('current'), store_json('persisted')
    require(not current or current.get('disabled'), 'H3 bootstrap requires the suite disabled at baseline')
    require(not persisted or persisted.get('disabled'), 'H3 bootstrap requires no active persisted suite policy')
    baseline = {}
    for name in ('current', 'pending', 'persisted', 'installed', 'boot-policy'):
        path = STATE / f'{name}.json'
        baseline[name] = base64.b64encode(path.read_bytes()).decode() if path.exists() else None
    require(sentinel_state() is None, 'Refusing pre-existing H3 nftables sentinel name')
    external_files = {str(path): file_state(path) for path in EXTERNAL_FIREWALL_FILES}
    state = {'phase': 'bootstrap-in-progress', 'owner_token': secrets.token_hex(16),
             'owned_files': {}, 'baseline_state': baseline, 'external_files': external_files}
    save_manifest(state)
    sentinel_digest = sentinel_state(create=True)
    create_probe_network()
    state = manifest()
    write_new_manifest_file(state, ACCESS, (json.dumps({'host': [{
        'group': 'h3-probe', 'source': f'{PROBE_CLIENT}/32', 'destination': f'{PROBE_HOST}/32',
        'protocol': 'tcp', 'ports': str(PROBE_PORT), 'input': PROBE_IFACE,
    }]}, sort_keys=True, indent=2) + '\n').encode())
    write_new_manifest_file(state, RECOVERY,
                            (json.dumps(ssh_recovery(), sort_keys=True, indent=2) + '\n').encode())
    owned_units = install_production_units()
    state = manifest()
    cli('--backend', 'nftables', 'apply', '--local', '--profile', 'host-minimal',
        '--set', 'HOST_SERVICES=true', '--set', 'SSH_PORT=22', '--set', 'ADMIN_SOURCES=10.0.2.2/32',
        '--set', f'ACCESS_POLICY={ACCESS}')
    cli('save')
    prepared = cli('boot-prepare', '--recovery-file', str(RECOVERY))
    result = json.loads(prepared.stdout)
    require(result.get('prepared') and result.get('recovery_grants') == 1, 'boot-prepare did not register scoped recovery')
    run(['systemctl', 'enable', 'l4d2-firewall-guard.service', 'l4d2-firewall.service'])
    run(['systemctl', 'enable', SOCKET_UNIT])
    run(['systemctl', 'daemon-reload'])
    run(['systemd-analyze', 'verify', '/etc/systemd/system/l4d2-firewall-guard.service',
         '/etc/systemd/system/l4d2-firewall.service', '/etc/systemd/system/l4d2-firewall-ready.service',
         '/etc/systemd/system/' + NETWORK_UNIT, '/etc/systemd/system/' + SOCKET_UNIT,
         '/etc/systemd/system/' + SERVICE_UNIT])
    # Establish an active, verified baseline before testing the separate early
    # guard. Otherwise a protected socket could legitimately start the full
    # restore dependency and release the barrier during the negative probe.
    run(['systemctl', 'start', 'l4d2-firewall.service'])
    run(['systemctl', 'start', 'l4d2-firewall-ready.service'])
    require(run(['systemctl', 'is-active', '--quiet', 'l4d2-firewall.service'], check=False).returncode == 0,
            'Full restore unit is not active after bootstrap')
    require(json.loads(cli('ready').stdout).get('ready'), 'Bootstrapped firewall is not ready')
    state = manifest()
    state.update({'phase': 'boot-prepared', 'boot_id': boot_id(),
                  'policy_digest': result['policy_digest'], 'probe_host': PROBE_HOST,
                  'probe_port': PROBE_PORT, 'units': owned_units,
                  'sentinel_digest': sentinel_digest})
    save_manifest(state)
    verify_preservation(manifest())
    print(json.dumps({'phase': 'bootstrap', 'policy_digest': result['policy_digest'],
                      'recovery_grants': result['recovery_grants'], 'guard_enabled': True}))


def stage_guard():
    state = manifest()
    require(state.get('phase') in ('boot-prepared', 'boot-ready', 'reboot-prepared'), 'H3 gate phase out of order')
    create_probe_network()
    cli('boot-guard')
    require_guard()
    require_blocked_readiness()
    state['phase'] = 'guard-staged'
    save_manifest(state)
    verify_preservation(state)
    print(json.dumps({'phase': 'stage-guard', 'barrier_denied_probe': True,
                      'protected_socket_denied_before_ready': True, 'probe': 'BLOCK'}))


def verify_ready():
    state = manifest()
    require(state.get('phase') == 'guard-staged', 'Verify readiness after the runner has observed the guard')
    create_probe_network()
    cli('boot-restore')
    ready = json.loads(cli('ready').stdout)
    require(ready.get('ready'), 'ready did not verify the restored policy')
    require_no_guard()
    run(['systemctl', 'reset-failed', 'l4d2-firewall-ready.service', SOCKET_UNIT, SERVICE_UNIT], check=False)
    run(['systemctl', 'start', SOCKET_UNIT])
    require(probe() == 'H3-READY', 'Authorized host grant was not restored after readiness')
    state['phase'] = 'boot-ready'
    save_manifest(state)
    verify_preservation(state)
    print(json.dumps({'phase': 'verify-ready', 'authorized_probe_after_ready': True,
                      'ready_verified': True, 'barrier_released': True}))


def failure_cases():
    state = manifest()
    require(state.get('phase') in ('boot-ready', 'reboot-prepared'), 'H3 failure tests require ready baseline')
    create_probe_network()
    invalid = cli('--backend', 'nftables', 'apply', '--local', '--set', 'NF_TABLE_FAMILY=invalid', check=False)
    require(invalid.returncode != 0, 'Invalid firewall candidate was accepted')
    cli('boot-guard')
    require_guard()
    require_blocked_readiness()
    sigkill_after_barrier_before_empty_rollback()
    cli('boot-guard')
    require_guard()
    require_blocked_readiness()
    persisted = STATE / 'persisted.json'
    original = persisted.read_bytes()
    try:
        for case in ('missing', 'corrupt', 'unsupported'):
            if case == 'missing':
                persisted.unlink()
            elif case == 'corrupt':
                persisted.write_text('{broken json\n')
                persisted.chmod(0o600)
            else:
                persisted.write_text('{"schema":999,"config":{}}\n')
                persisted.chmod(0o600)
            failed = run(['systemctl', 'restart', 'l4d2-firewall.service'], check=False, timeout=40)
            require(failed.returncode != 0, f'Full restore unit unexpectedly accepted {case} persisted state')
            require_guard()
            run(['systemctl', 'reset-failed', 'l4d2-firewall.service'], check=False)
            require_blocked_readiness()
    finally:
        fd = os.open(persisted, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, original)
            os.fsync(fd)
        finally:
            os.close(fd)
    nft = Path(shutil.which('nft') or '')
    require(str(nft) != '.' and nft.is_file() and not nft.is_symlink(), 'Could not identify trusted guest nft binary')
    backup_binary = nft.with_name(nft.name + '.h3-temporary-missing')
    require(not backup_binary.exists() and not backup_binary.is_symlink(), 'Refusing to overwrite nft test backup path')
    os.replace(nft, backup_binary)
    try:
        failed = run(['systemctl', 'restart', 'l4d2-firewall.service'], check=False, timeout=40)
        require(failed.returncode != 0, 'Full restore unexpectedly succeeded without its required nft binary')
        require_guard(backup_binary)
        # Keep nft absent while observing the barrier. Restoring it first lets
        # the failed full unit retry successfully through socket dependencies,
        # which legitimately releases the guard and invalidates this assertion.
        require_blocked_readiness(backup_binary)
    finally:
        os.replace(backup_binary, nft)
    run(['systemctl', 'start', 'l4d2-firewall.service'])
    # Docker's Requires/After drop-in can stop the full restore unit along
    # with dockerd. Verify that a fresh restore completed before treating the
    # guarded restart as successful.
    ensure_full_ready()
    run(['systemctl', 'reset-failed', 'l4d2-firewall-ready.service', SOCKET_UNIT, SERVICE_UNIT], check=False)
    run(['systemctl', 'start', SOCKET_UNIT])
    require(probe() == 'H3-READY', 'Policy did not recover after restoring exact persisted bytes')
    state['phase'] = 'boot-ready'
    save_manifest(state)
    verify_preservation(state)
    print(json.dumps({'phase': 'failure-cases', 'invalid_candidate_kept_guard': True,
                      'sigkill_then_empty_previous_rollback_kept_guard_until_restore': True,
                      'missing_corrupt_unsupported_persisted_failed_closed': True,
                      'missing_required_binary_failed_closed': True,
                      'exact_state_restore_recovered': True}))


def docker_command(*args, check=True, timeout=90):
    return run(['docker', '--host', f'unix://{DOCKER_SOCKET}', *args], check=check, timeout=timeout)


def install_test_docker_service(workdir):
    load = run(['systemctl', 'show', '--property=LoadState', '--value', 'docker.service'], check=False)
    require(load.stdout.strip() in ('', 'not-found'),
            f'Refusing to replace pre-existing Docker service (LoadState={load.stdout.strip()!r})')
    require(not DOCKER_UNIT.exists() and not DOCKER_UNIT.is_symlink(),
            f'Refusing pre-existing test Docker unit path {DOCKER_UNIT}')
    require(Path('/usr/local/bin/dockerd').is_file() and Path('/usr/local/bin/docker').is_file(),
            'The runner must install the pinned Docker binaries in the disposable guest')
    data = workdir / 'data'
    exec_root = workdir / 'exec'
    pidfile = workdir / 'dockerd.pid'
    text = f'''[Unit]
Description=Disposable H3 closure Docker daemon
After=network.target

[Service]
Type=notify
ExecStart=/usr/local/bin/dockerd --host=unix:///var/run/docker.sock --live-restore --firewall-backend=iptables --data-root={data} --exec-root={exec_root} --pidfile={pidfile}
Restart=no
TimeoutStartSec=120
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
'''
    DOCKER_UNIT.write_text(text)
    DOCKER_UNIT.chmod(0o644)
    return hashlib.sha256(DOCKER_UNIT.read_bytes()).hexdigest()


def published_probe(port=DOCKER_PUBLIC_PORT, timeout=1.5):
    code = f'''import socket
s=socket.socket()
s.settimeout({timeout})
s.connect(({PROBE_HOST!r},{port}))
s.sendall(b"GET / HTTP/1.0\\r\\nHost: closure\\r\\nConnection: close\\r\\n\\r\\n")
parts=[]
while True:
 try:
  part=s.recv(4096)
 except socket.timeout:
  break
 if not part:
  break
 parts.append(part)
s.close()
print(b"".join(parts).decode(errors="replace"))
'''
    result = run(['ip', 'netns', 'exec', PROBE_NETNS, '/usr/bin/python3', '-c', code],
                 check=False, timeout=5)
    return result.stdout if result.returncode == 0 else ''


def published_udp_probe(port=DOCKER_UDP_PUBLIC_PORT, timeout=0.7):
    code = f'''import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.settimeout({timeout})
s.sendto(b"h3-udp-probe", ({PROBE_HOST!r},{port}))
try:
 data,_=s.recvfrom(256)
 print(data.decode(errors="replace"))
except OSError:
 pass
s.close()
'''
    result = run(['ip', 'netns', 'exec', PROBE_NETNS, '/usr/bin/python3', '-c', code],
                 check=False, timeout=3)
    return result.stdout.strip() if result.returncode == 0 else ''


def make_http_image(workdir):
    """Build and import a local minimal Python image; no registry is contacted."""
    spec = importlib.util.spec_from_file_location('l4d2_h3_docker_helpers', INSTALL / 'tests/vm/docker.py')
    require(spec is not None and spec.loader is not None, 'Cannot load the local Docker image helper')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    rootfs = workdir / 'python-rootfs'
    rootfs.mkdir(mode=0o700)
    binary = Path(sys.executable).resolve()
    stdlib = Path(sysconfig.get_paths()['stdlib']).resolve()
    require(binary.is_file() and stdlib.is_dir(), 'Guest Python runtime is unavailable for local image')
    helper.copy_runtime_dependency(binary, rootfs)
    python3 = rootfs / 'usr/bin/python3'
    python3.parent.mkdir(parents=True, exist_ok=True)
    require(not python3.exists() and not python3.is_symlink(), 'Python runtime target already exists in test rootfs')
    python3.symlink_to('/' + binary.relative_to(rootfs).as_posix() if binary.is_relative_to(rootfs) else '/' + str(binary).lstrip('/'))
    lib_target = rootfs / stdlib.as_posix().lstrip('/')
    lib_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(stdlib, lib_target, symlinks=True)
    for dependency in helper.python_dependencies(binary, stdlib):
        helper.copy_runtime_dependency(dependency, rootfs)
    app = rootfs / 'opt/h3-server.py'
    app.parent.mkdir(parents=True, exist_ok=True)
    app.write_text(
        'import socket, threading\n'
        'def tcp_server():\n'
        ' s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("0.0.0.0",18443)); s.listen(32)\n'
        ' while True:\n'
        '  c,_=s.accept()\n'
        '  try:\n'
        '   c.recv(4096); body=b"H3-CONTAINER"; c.sendall(b"HTTP/1.1 200 OK\\r\\nContent-Length: 12\\r\\nConnection: close\\r\\n\\r\\n"+body)\n'
        '  finally: c.close()\n'
        'def udp_server():\n'
        ' u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); u.bind(("0.0.0.0",18444))\n'
        ' while True:\n'
        '  _,addr=u.recvfrom(4096); u.sendto(b"H3-UDP",addr)\n'
        'threading.Thread(target=udp_server,daemon=True).start()\n'
        'threading.Thread(target=tcp_server,daemon=True).start()\n'
        'threading.Event().wait()\n'
    )
    archive = workdir / 'h3-python-rootfs.tar'
    with tarfile.open(archive, 'w') as output:
        for child in sorted(rootfs.iterdir()):
            output.add(child, arcname=child.name, recursive=True)
    docker_command('import', str(archive), DOCKER_IMAGE, timeout=180)
    smoke = docker_command('run', '--rm', '--entrypoint', 'python3', DOCKER_IMAGE,
                           '-c', 'import socket;print("h3-image-ok")', timeout=60)
    require(smoke.stdout.strip() == 'h3-image-ok', 'Local Docker image smoke check failed')


def apply_docker_policy(source, public_destination, input_iface):
    cli('boot-disarm', '--local')
    state = manifest()
    replace_owned_json(state, ACCESS, {
        'host': [{
            'group': 'h3-probe', 'source': f'{PROBE_CLIENT}/32', 'destination': f'{PROBE_HOST}/32',
            'protocol': 'tcp', 'ports': str(PROBE_PORT), 'input': PROBE_IFACE,
        }],
        'containers': [{
            'group': 'h3-docker-tcp', 'source': source, 'destination': f'{DOCKER_ADDRESS}/32',
            'protocol': 'tcp', 'ports': str(DOCKER_PRIVATE_PORT), 'input': input_iface,
            'output': DOCKER_BRIDGE, 'public_destination': public_destination,
            'public_ports': str(DOCKER_PUBLIC_PORT), 'service': 'http_https_protect',
        }, {
            'group': 'h3-docker-udp', 'source': source, 'destination': f'{DOCKER_ADDRESS}/32',
            'protocol': 'udp', 'ports': str(DOCKER_UDP_PRIVATE_PORT), 'input': input_iface,
            'output': DOCKER_BRIDGE, 'public_destination': public_destination,
            'public_ports': str(DOCKER_UDP_PUBLIC_PORT), 'service': 'allowlist_ports',
        }],
    })
    cli('--backend', 'nftables', 'apply', '--local', '--profile', 'web',
        '--only', 'tcp_ssh,http_https_protect,allowlist_ports',
        '--set', 'HOST_SERVICES=true', '--set', 'SSH_PORT=22', '--set', 'ADMIN_SOURCES=10.0.2.2/32',
        '--set', 'CONTAINER_POLICY=restrict', '--set', f'ACCESS_POLICY={ACCESS}')
    cli('save')
    cli('boot-prepare', '--recovery-file', str(RECOVERY))
    cli('boot-guard')
    cli('boot-restore')
    cli('ready')


def docker_container_state():
    return docker_command('inspect', '--format', '{{.Id}} {{.State.Running}}', DOCKER_NAME).stdout.strip()


def calibrate_probe():
    state = manifest()
    require(state.get('phase') in ('boot-ready', 'post-reboot-verified'),
            'Docker restart test requires a ready persisted baseline')
    require(not os.environ.get('DOCKER_HOST'), 'Remote Docker targets are forbidden')
    workdir = STATE / 'closure-h3-docker'
    require(not workdir.exists() and not workdir.is_symlink(), 'Refusing pre-existing H3 Docker work directory')
    workdir.mkdir(mode=0o700)
    state['units']['docker.service'] = install_test_docker_service(workdir)
    save_manifest(state)
    run(['systemctl', 'daemon-reload'])
    run(['systemd-analyze', 'verify', 'docker.service'])
    run(['systemctl', 'enable', 'docker.service'])
    run(['systemctl', 'start', 'docker.service'], timeout=120)
    require(run(['systemctl', 'is-active', '--quiet', 'docker.service'], check=False).returncode == 0,
            'The test-owned Docker service did not become active')
    require(Path(DOCKER_SOCKET).exists(), f'Expected local Docker socket {DOCKER_SOCKET}')
    live_restore = docker_command('info', '--format', '{{.LiveRestoreEnabled}}').stdout.strip().lower()
    require(live_restore == 'true', f'Docker live-restore must be enabled, got {live_restore!r}')
    require(docker_command('network', 'ls', '--format', '{{.Name}}').stdout.splitlines().count(DOCKER_NETWORK) == 0,
            'Refusing pre-existing H3 Docker network')
    require(docker_command('ps', '-a', '--format', '{{.Names}}').stdout.splitlines().count(DOCKER_NAME) == 0,
            'Refusing pre-existing H3 Docker container')
    require(docker_command('image', 'ls', '--format', '{{.Repository}}:{{.Tag}}').stdout.splitlines().count(DOCKER_IMAGE) == 0,
            'Refusing pre-existing H3 Docker image')

    make_http_image(workdir)
    docker_command('network', 'create', '--driver', 'bridge', '--subnet', '172.29.0.0/24',
                   '--opt', f'com.docker.network.bridge.name={DOCKER_BRIDGE}', DOCKER_NETWORK)
    docker_command('run', '-d', '--name', DOCKER_NAME, '--restart=always', '--network', DOCKER_NETWORK,
                   '--ip', DOCKER_ADDRESS, '--publish', f'{DOCKER_PUBLIC_PORT}:{DOCKER_PRIVATE_PORT}/tcp',
                   '--publish', f'{DOCKER_UDP_PUBLIC_PORT}:{DOCKER_UDP_PRIVATE_PORT}/udp',
                   '--entrypoint', '/usr/bin/python3', DOCKER_IMAGE, '/opt/h3-server.py')
    before_id = docker_container_state().split()[0]
    require(before_id, 'Docker test container did not start')
    create_probe_network()

    require(DOCKER_DROPIN.parent.is_dir() or not DOCKER_DROPIN.parent.exists(),
            'Unexpected Docker drop-in parent path')
    for path in (DOCKER_DROPIN, FULL_DROPIN, DOCKER_PAUSE):
        require(not path.exists() and not path.is_symlink(), f'Refusing to replace pre-existing Docker test drop-in {path}')
    DOCKER_DROPIN.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    FULL_DROPIN.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    docker_text = (INSTALL / 'systemd/examples/docker.service.d/10-l4d2-firewall.conf').read_text()
    full_text = (INSTALL / 'systemd/examples/l4d2-firewall.service.d/10-docker.conf').read_text()
    nft_path = shutil.which('nft')
    require(nft_path is not None, 'The guest nft executable is required to assert Docker ExecStop ordering')
    pause_text = (f'[Service]\nExecStartPre=/usr/bin/sleep 4\n'
                  f'ExecStopPost={nft_path} list table inet l4d2_boot_guard\n')
    DOCKER_DROPIN.write_text(docker_text)
    FULL_DROPIN.write_text(full_text)
    DOCKER_PAUSE.write_text(pause_text)
    for path in (DOCKER_DROPIN, FULL_DROPIN, DOCKER_PAUSE):
        path.chmod(0o644)
    owned = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in (DOCKER_DROPIN, FULL_DROPIN, DOCKER_PAUSE)}
    run(['systemctl', 'daemon-reload'])
    run(['systemd-analyze', 'verify', '/etc/systemd/system/docker.service',
         '/etc/systemd/system/l4d2-firewall.service'])
    # First allow only the external QEMU hostfwd source/destination so the host
    # runner can prove that its positive probe channel is live.
    ssh = os.environ.get('SSH_CONNECTION', '').split()
    require(len(ssh) == 4, 'Docker calibration requires the authenticated QEMU SSH connection')
    input_iface = run(['ip', '-o', 'route', 'get', ssh[0]]).stdout.split()
    require('dev' in input_iface, 'Cannot determine QEMU SSH interface for the calibration grant')
    apply_docker_policy('10.0.2.2/32', f'{ssh[2]}/32', input_iface[input_iface.index('dev') + 1])
    require_no_guard()
    state = manifest()
    state['phase'] = 'docker-probe-calibrated'
    state['docker_dropins'] = owned
    state['docker_network'] = DOCKER_NETWORK
    state['docker_container'] = DOCKER_NAME
    state['docker_image'] = DOCKER_IMAGE
    state['docker_workdir'] = str(workdir)
    state['docker_container_id'] = before_id
    state['docker_input_iface'] = input_iface[input_iface.index('dev') + 1]
    state['docker_guest_ssh_destination'] = ssh[2]
    save_manifest(state)
    verify_preservation(state)
    print(json.dumps({'phase': 'calibrate-probe', 'hostfwd_port': DOCKER_PUBLIC_PORT,
                      'guest_udp_port': DOCKER_UDP_PUBLIC_PORT,
                      'body': 'H3-CONTAINER', 'udp_body': 'H3-UDP',
                      'live_restore': True, 'container_id': before_id}))


def restrict_probe():
    state = manifest()
    require(state.get('phase') == 'docker-probe-calibrated', 'Run Docker positive-channel calibration first')
    create_probe_network()
    apply_docker_policy(f'{PROBE_CLIENT}/32', f'{PROBE_HOST}/32', PROBE_IFACE)
    require_no_guard()
    require('H3-CONTAINER' in published_probe(DOCKER_PUBLIC_PORT),
            'Positive container probe failed after restricting the grant to the nested veth client')
    require(published_udp_probe() == 'H3-UDP',
            'Positive UDP container probe failed after restricting the grant to the nested veth client')
    state['phase'] = 'docker-probe-restricted'
    save_manifest(state)
    verify_preservation(state)
    print(json.dumps({'phase': 'restrict-probe', 'veth_positive': True, 'veth_udp_positive': True,
                      'external_source_removed': True, 'hostfwd_probe_expected': 'BLOCK'}))


def docker_restart():
    state = manifest()
    require(state.get('phase') == 'docker-probe-restricted',
            'Docker restart requires calibrated and source-restricted probe paths')
    # The runner probes the hostfwd port throughout this phase. Any external
    # response after restriction is a failure; internal veth stays a positive control.
    require('H3-CONTAINER' in published_probe(DOCKER_PUBLIC_PORT),
            'Internal positive-control container probe failed before restart')
    require(published_udp_probe() == 'H3-UDP',
            'Internal UDP positive-control container probe failed before restart')
    before_id = docker_container_state().split()[0]
    require(before_id == state.get('docker_container_id'), 'Container identity changed before restart')
    require(docker_command('info', '--format', '{{.LiveRestoreEnabled}}').stdout.strip().lower() == 'true',
            'Docker live-restore is no longer enabled')
    require_guard_absent = run(['nft', '-j', 'list', 'tables']).stdout
    require(GUARD_TABLE[1] not in require_guard_absent, 'Unexpected stale H3 barrier before Docker restart')
    # Do not pre-arm the guard: the test-only ExecStopPost assertion runs
    # before the next ExecStartPre, proving that the production ExecStop hook
    # itself installed the barrier. The four-second delay leaves a probe window.
    proc = subprocess.Popen(['systemctl', 'restart', 'docker.service'],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    blocked_during_guard = 0
    deadline = time.monotonic() + 45
    while proc.poll() is None and time.monotonic() < deadline:
        raw_result = run(['nft', '-j', 'list', 'tables'], check=False)
        if raw_result.returncode == 0:
            tables = json.loads(raw_result.stdout).get('nftables', [])
            active = any(item.get('table', {}).get('family') == GUARD_TABLE[0]
                         and item.get('table', {}).get('name') == GUARD_TABLE[1] for item in tables)
            if active:
                require(published_probe(DOCKER_PUBLIC_PORT, timeout=0.35) == '',
                        'Published container port responded while boot barrier was active')
                require(published_udp_probe(timeout=0.25) == '',
                        'Published UDP container port responded while boot barrier was active')
                blocked_during_guard += 1
        time.sleep(0.12)
    if proc.poll() is None:
        proc.kill()
        proc.communicate(timeout=5)
        raise H3Error('Docker restart exceeded 45 seconds')
    stdout, stderr = proc.communicate(timeout=5)
    require(proc.returncode == 0, f'Docker systemd restart failed: {stdout}{stderr}')
    require(blocked_during_guard >= 2,
            f'No sustained guard window observed during Docker restart (blocked probes={blocked_during_guard})')
    cli('ready')
    require_no_guard()
    after_state = docker_container_state().split()
    require(after_state == [before_id, 'true'], f'Live-restored restart=always container changed: {after_state!r}')
    require('H3-CONTAINER' in published_probe(DOCKER_PUBLIC_PORT),
            'Published container service did not recover after Docker restart')
    require(published_udp_probe() == 'H3-UDP',
            'Published UDP container service did not recover after Docker restart')
    state['phase'] = 'docker-restart-verified'
    state['guarded_denied_probes'] = blocked_during_guard
    save_manifest(state)
    verify_preservation(state)
    print(json.dumps({'phase': 'docker-restart', 'live_restore': True,
                      'restart_always_container_same_id': True,
                      'execstop_barrier_asserted_before_next_start': True,
                      'guarded_denied_probes': blocked_during_guard,
                      'published_port_restored': True,
                      'published_udp_port_restored': True}))


def pre_reboot():
    state = manifest()
    require(state.get('phase') in ('boot-ready', 'docker-restart-verified'),
            'Prepare reboot only after H3 gate and Docker verification')
    # Keep the independent full restore dependency active before arming the
    # barrier; otherwise starting the protected socket could legitimately
    # trigger a missing full restore and release the guard during this check.
    ensure_full_ready()
    cli('save')
    run(['systemctl', 'enable', 'l4d2-firewall-guard.service', 'l4d2-firewall.service'])
    cli('boot-guard')
    require_guard()
    require_blocked_readiness()
    state['phase'] = 'reboot-prepared'
    state['pre_reboot_boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    save_manifest(state)
    verify_preservation(state)
    print(json.dumps({'phase': 'pre-reboot', 'pre_reboot_boot_id': state['pre_reboot_boot_id'],
                      'guard_persisted_before_reboot': True}))


def pre_failed_reboot():
    state = manifest()
    require(state.get('phase') == 'docker-restart-verified',
            'Invalid-persistence reboot requires a verified Docker baseline')
    ensure_full_ready()
    persisted_path = STATE / 'persisted.json'
    require(persisted_path.is_file() and not persisted_path.is_symlink(),
            'Cannot inject unsupported persistence without a regular saved policy file')
    original = persisted_path.read_bytes()
    persisted = json.loads(original)
    require(persisted.get('schema') != 999, 'Saved policy already has the injected unsupported schema')
    state['persisted_backup'] = base64.b64encode(original).decode('ascii')
    state['persisted_backup_sha256'] = hash_bytes(original)
    cli('save')
    # Save can update the durable bytes, so capture the exact final known-good
    # representation that the failed boot must not overwrite.
    original = persisted_path.read_bytes()
    persisted = json.loads(original)
    state['persisted_backup'] = base64.b64encode(original).decode('ascii')
    state['persisted_backup_sha256'] = hash_bytes(original)
    state['failed_reboot_boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    state['phase'] = 'failed-reboot-prepared'
    save_manifest(state)
    cli('boot-guard')
    require_guard()
    persisted['schema'] = 999
    write_json(persisted_path, persisted)
    state['invalid_persisted_sha256'] = hash_bytes(persisted_path.read_bytes())
    save_manifest(state)
    verify_preservation(state)
    print(json.dumps({'phase': 'pre-failed-reboot', 'boot_id': state['failed_reboot_boot_id'],
                      'persisted_schema': 999, 'guard_armed': True}))


def _restore_persisted_backup(state):
    raw = base64.b64decode(state.get('persisted_backup', ''), validate=True)
    require(hash_bytes(raw) == state.get('persisted_backup_sha256'),
            'Saved known-good persisted policy backup failed its digest check')
    path = STATE / 'persisted.json'
    temporary = path.with_name(path.name + '.h3-restore')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(raw)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    directory = os.open(STATE, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    require(path.read_bytes() == raw, 'Could not restore exact persisted policy bytes')


def post_failed_reboot():
    state = manifest()
    require(state.get('phase') == 'failed-reboot-prepared',
            'Failed-boot verification requires the prepared unsupported-persistence reboot')
    current_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    require(current_boot != state.get('failed_reboot_boot_id'), 'Kernel boot ID did not change for the failed restore')
    observations = {}
    recovery_error = None
    try:
        observations['systemd_boot_state'] = wait_for_boot_jobs()
        guard_active = run(['systemctl', 'is-active', '--quiet', 'l4d2-firewall-guard.service'], check=False)
        observations['guard_active'] = guard_active.returncode == 0
        require(observations['guard_active'], 'Boot guard unit did not remain active after unsupported persistence')
        require_guard()
        for unit, prefix in (('l4d2-firewall.service', 'full'), ('docker.service', 'docker')):
            for field in ('ActiveState', 'SubState', 'Result'):
                shown = run(['systemctl', 'show', f'--property={field}', '--value', unit])
                observations[f'{prefix}_{field.lower()}'] = shown.stdout.strip()
        full_active = run(['systemctl', 'is-active', '--quiet', 'l4d2-firewall.service'], check=False)
        require(full_active.returncode != 0
                and observations['full_activestate'] not in ('activating', 'deactivating'),
                f'Full restore became active on unsupported persisted schema: {observations!r}')
        docker_active = run(['systemctl', 'is-active', '--quiet', 'docker.service'], check=False)
        observations['docker_active'] = docker_active.returncode == 0
        require(not observations['docker_active']
                and observations['docker_activestate'] not in ('activating', 'deactivating'),
                f'Docker did not remain blocked by failed restore: {observations!r}')
        socket_active = run(['systemctl', 'is-active', '--quiet', SOCKET_UNIT], check=False)
        observations['protected_socket_active'] = socket_active.returncode == 0
        require(not observations['protected_socket_active'], 'Protected socket activated before a valid restore')
        require(cli('ready', check=False).returncode != 0, 'Readiness accepted unsupported persisted schema')
        require(probe() == 'BLOCK', 'Authorized host probe escaped the barrier after restore failure')
        require(tcp_probe(DOCKER_PUBLIC_PORT) == 'BLOCK', 'Veth TCP path escaped the barrier after restore failure')
        require(published_udp_probe() == '', 'Veth UDP path escaped the barrier after restore failure')
        verify_preservation(state, after_reboot=True)
    except Exception as exc:
        recovery_error = H3Error(f'{exc}\nBoot failure diagnostics:\n{boot_systemd_snapshot()}')
    finally:
        _restore_persisted_backup(state)

    # Recover the guest even when an assertion failed so the later valid-boot
    # check and exact cleanup do not inherit deliberately corrupted state.
    run(['systemctl', 'reset-failed', 'docker.service', 'l4d2-firewall.service',
         'l4d2-firewall-ready.service', SOCKET_UNIT], check=False)
    run(['systemctl', 'start', 'l4d2-firewall.service'], timeout=120)
    run(['systemctl', 'start', 'l4d2-firewall-ready.service'], timeout=60)
    run(['systemctl', 'start', SOCKET_UNIT], timeout=30)
    ensure_full_ready()
    require(probe() == 'H3-READY', 'Host service did not recover after restoring exact persistence bytes')
    require(docker_container_state().split() == [state['docker_container_id'], 'true'],
            'Docker container did not recover after restoring exact persistence bytes')
    require('H3-CONTAINER' in published_probe(DOCKER_PUBLIC_PORT),
            'TCP container positive control did not recover after valid restore')
    require(published_udp_probe() == 'H3-UDP',
            'UDP container positive control did not recover after valid restore')
    state['phase'] = 'docker-restart-verified'
    state['failed_reboot_boot_id_after'] = current_boot
    state['failed_reboot_observations'] = observations
    state.pop('persisted_backup', None)
    state.pop('persisted_backup_sha256', None)
    state.pop('invalid_persisted_sha256', None)
    save_manifest(state)
    verify_preservation(state)
    if recovery_error is not None:
        raise H3Error(f'Unsupported-persistence boot assertion failed after guest recovery: {recovery_error}') from recovery_error
    print(json.dumps({'phase': 'post-failed-reboot', 'boot_id_changed': True,
                      'guard_retained': True, 'restore_failed_closed': True,
                      'protected_socket_blocked': True, 'fresh_ssh_session': True,
                      'exact_persistence_restored': True, 'service_recovered': True,
                      'units': observations}))


def post_reboot():
    state = manifest()
    require(state.get('phase') == 'reboot-prepared', 'Post-reboot check requires a prepared H3 reboot')
    try:
        systemd_boot_state = wait_for_boot_jobs()
        current_boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        require(current_boot != state.get('pre_reboot_boot_id'), 'Kernel boot ID did not change')
        for unit in ('l4d2-firewall-guard.service', 'l4d2-firewall.service'):
            active = run(['systemctl', 'is-active', '--quiet', unit], check=False)
            require(active.returncode == 0, f'Production boot unit did not complete: {unit}')
        require(run(['systemctl', 'is-active', '--quiet', NETWORK_UNIT], check=False).returncode == 0,
                'The test network was not recreated automatically during boot')
        require(run(['systemctl', 'is-active', '--quiet', SOCKET_UNIT], check=False).returncode == 0,
                'The protected socket was not activated automatically during boot')
        run(['systemctl', 'start', 'l4d2-firewall-ready.service'])
        ready_result = run(['systemctl', 'show', '--property=Result', '--value', 'l4d2-firewall-ready.service'])
        ready_exit = run(['systemctl', 'show', '--property=ExecMainStatus', '--value', 'l4d2-firewall-ready.service'])
        require(ready_result.stdout.strip() == 'success' and ready_exit.stdout.strip() == '0',
                'Readiness oneshot did not report a successful current-boot verification')
        result = json.loads(cli('ready').stdout)
        require(result.get('ready') and result.get('boot_id') == current_boot,
                'Readiness does not attest to the current kernel boot')
        require_no_guard()
        verify_preservation(state, after_reboot=True)
        run(['systemctl', 'reset-failed', 'l4d2-firewall-ready.service', SERVICE_UNIT], check=False)
        require(probe() == 'H3-READY', 'Persisted authorized service grant is not reachable after reboot')
        if state.get('docker_container_id'):
            docker_state = docker_container_state().split()
            require(docker_state == [state['docker_container_id'], 'true'],
                    f'Live-restored restart=always container did not survive reboot: {docker_state!r}')
            require('H3-CONTAINER' in published_probe(DOCKER_PUBLIC_PORT),
                    'Restricted internal container path was not restored after reboot')
            require(published_udp_probe() == 'H3-UDP',
                    'Restricted internal UDP container path was not restored after reboot')
        state['phase'] = 'post-reboot-verified'
        state['post_reboot_boot_id'] = current_boot
        save_manifest(state)
        verify_preservation(state)
    except Exception as exc:
        raise H3Error(f'{exc}\nBoot diagnostics:\n{boot_systemd_snapshot()}') from exc
    print(json.dumps({'phase': 'post-reboot', 'boot_id_changed': True,
                      'systemd_boot_state': systemd_boot_state,
                      'guard_unit_active': True, 'restore_ready': True, 'protected_probe_restored': True}))


def cleanup():
    state = manifest()
    errors = []
    if state.get('docker_container') and Path(DOCKER_SOCKET).exists():
        for argv in (('rm', '-f', state['docker_container']), ('network', 'rm', state.get('docker_network', DOCKER_NETWORK)),
                     ('image', 'rm', state.get('docker_image', DOCKER_IMAGE))):
            result = docker_command(*argv, check=False, timeout=90)
            if result.returncode and 'no such' not in (result.stdout + result.stderr).lower():
                errors.append(f'Docker cleanup {argv[0]}: {result.stderr.strip()}')
    if 'docker.service' in state.get('units', {}):
        # Preserve the barrier while shutting down the live-restore daemon,
        # even though the test-owned ExecStop drop-in is removed below.
        guarded = cli('boot-guard', check=False)
        require(guarded.returncode == 0,
                'Cannot safely shut down test Docker without arming boot guard: ' + guarded.stderr.strip())
        require_guard()
    for raw_path, expected_hash in state.get('docker_dropins', {}).items():
        path = Path(raw_path)
        if path.exists() and not path.is_symlink():
            if hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash:
                path.unlink()
            else:
                errors.append(f'refusing to remove modified Docker test drop-in {path}')
    run(['systemctl', 'daemon-reload'], check=False)
    if 'docker.service' in state.get('units', {}):
        stopped = run(['systemctl', 'stop', 'docker.service'], check=False, timeout=45)
        if stopped.returncode and run(['systemctl', 'is-active', '--quiet', 'docker.service'], check=False).returncode == 0:
            errors.append('test Docker service did not stop; retaining its data directory')
        run(['systemctl', 'disable', 'docker.service'], check=False)
    for unit in (SOCKET_UNIT, SERVICE_UNIT, NETWORK_UNIT, 'l4d2-firewall-ready.service', 'l4d2-firewall.service',
                 'l4d2-firewall-guard.service'):
        result = run(['systemctl', 'stop', unit], check=False, timeout=20)
        if result.returncode and 'not loaded' not in (result.stdout + result.stderr).lower():
            errors.append(f'stop {unit}: {result.stderr.strip()}')
    if store_json('boot-policy'):
        result = cli('boot-disarm', '--local', check=False)
        if result.returncode:
            errors.append('boot-disarm: ' + result.stderr.strip())
    if store_json('current'):
        result = cli('--backend', 'nftables', 'disable', '--local', check=False)
        if result.returncode:
            errors.append('disable: ' + result.stderr.strip())
    # Do not erase recovery state if a product-owned barrier or policy failed
    # to cleanly disarm; leave the manifest for explicit guest-side recovery.
    if any(error.startswith(('boot-disarm:', 'disable:')) for error in errors):
        raise H3Error('; '.join(errors))
    run(['systemctl', 'disable', SOCKET_UNIT,
         'l4d2-firewall.service', 'l4d2-firewall-guard.service'], check=False)
    for unit, expected_hash in state.get('units', {}).items():
        path = Path('/etc/systemd/system') / unit
        if path.exists() and not path.is_symlink():
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual == expected_hash:
                path.unlink()
            else:
                errors.append(f'refusing to remove modified test unit {path}')
    if ('docker.service' in state.get('units', {}) and not DOCKER_UNIT.exists()
            and run(['systemctl', 'is-active', '--quiet', 'docker.service'], check=False).returncode != 0):
        workdir = Path(state.get('docker_workdir', str(STATE / 'closure-h3-docker')))
        if workdir == STATE / 'closure-h3-docker' and workdir.is_dir() and not workdir.is_symlink():
            shutil.rmtree(workdir)
    run(['systemctl', 'daemon-reload'], check=False)
    try:
        remove_probe_network(state)
    except H3Error as exc:
        errors.append(str(exc))
    for path in (RECOVERY, ACCESS, PROBE_HELPER):
        try:
            remove_owned_manifest_file(state, path)
        except H3Error as exc:
            errors.append(str(exc))
    current_sentinel = sentinel_state()
    if current_sentinel is not None:
        if current_sentinel != state.get('sentinel_digest'):
            raise H3Error('Refusing to delete a modified nftables sentinel table')
        run(['nft', '-f', '-'], input_text=f'delete table {FOREIGN_TABLE[0]} {FOREIGN_TABLE[1]}\n')
    for path in EXTERNAL_FIREWALL_FILES:
        require(file_state(path) == state.get('external_files', {}).get(str(path)),
                f'External firewall configuration changed during H3 cleanup: {path}')
    require(sentinel_state() is None, 'H3 sentinel table remained after exact-owner cleanup')
    if errors:
        raise H3Error('; '.join(errors))
    # Preserve the exact pre-test transaction files; cleanup runs only after
    # both the suite policy and the independent barrier have been removed.
    for key, encoded in state.get('baseline_state', {}).items():
        path = STATE / f'{key}.json'
        if encoded is None:
            path.unlink(missing_ok=True)
        else:
            raw = base64.b64decode(encoded, validate=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            try:
                os.write(fd, raw)
                os.fsync(fd)
            finally:
                os.close(fd)
    MANIFEST.unlink(missing_ok=True)
    print(json.dumps({'phase': 'cleanup', 'units_removed': True, 'test_state_removed': True,
                      'prior_manifest_phase': state.get('phase')}))


PHASES = {
    'bootstrap': bootstrap,
    'create-probe-network': create_probe_network,
    'stage-guard': stage_guard,
    'verify-ready': verify_ready,
    'failure-cases': failure_cases,
    'calibrate-probe': calibrate_probe,
    'restrict-probe': restrict_probe,
    'docker-restart': docker_restart,
    'pre-failed-reboot': pre_failed_reboot,
    'post-failed-reboot': post_failed_reboot,
    'pre-reboot': pre_reboot,
    'post-reboot': post_reboot,
    'cleanup': cleanup,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=sorted(PHASES))
    args = parser.parse_args(argv)
    safe_guest()
    PHASES[args.phase]()


if __name__ == '__main__':
    try:
        main()
    except (H3Error, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(2)
