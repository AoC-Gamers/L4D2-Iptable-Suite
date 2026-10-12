#!/usr/bin/env python3
"""Disposable-QEMU integration test for the suite and a real Docker daemon."""
import argparse
import difflib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import time
import uuid

MARKER = Path('/run/l4d2-suite-vm.json')
DEFAULT_SUITE = Path('/opt/l4d2-firewall')
HOST_TEST_IP = '198.18.0.1'
CLIENT_TEST_IP = '198.18.0.2'
HOST_TEST_IP6 = 'fd00:198:18:2::1'
CLIENT_TEST_IP6 = 'fd00:198:18:2::2'
CONTAINER_TEST_CIDR6 = 'fd00:198:18:1::/64'
DOCKER_TEST_IPV6_POOL = {'base': 'fd00:198:19::/48', 'size': 64}
PUBLIC_PORT = 18080
CONTAINER_PORT = 18443
EGRESS_ALLOWED = 18444
EGRESS_BLOCKED = 18445


class SkipCase(Exception):
    pass


def run(argv, *, input_text=None, timeout=60, check=True, env=None):
    result = subprocess.run(
        [str(x) for x in argv], input=input_text, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        check=False, env=env,
    )
    if check and result.returncode:
        raise RuntimeError(f"{argv[0]} failed ({result.returncode}): {result.stderr.strip()}")
    return result


def assert_vm_marker():
    if os.geteuid() != 0:
        raise RuntimeError('Run as root inside the disposable QEMU guest')
    info = MARKER.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        raise RuntimeError(f'{MARKER} must be a root-owned regular file with mode 0600')
    marker = json.loads(MARKER.read_text())
    if marker != {'virtualization': 'qemu', 'disposable': True}:
        raise RuntimeError('VM safety marker does not attest a disposable QEMU guest')
    virtualization = run(['systemd-detect-virt', '--vm']).stdout.strip()
    if virtualization not in ('qemu', 'kvm'):
        raise RuntimeError(f'Expected QEMU/KVM guest, detected {virtualization!r}')
    parent_netns = os.environ.get('L4S_VM_PARENT_NETNS')
    parent_run = os.environ.get('L4S_VM_PARENT_RUN')
    if not parent_netns or not parent_run:
        raise RuntimeError('Run through tests/vm/docker.sh so Docker is confined to nested namespaces')
    if os.readlink('/proc/self/ns/net') == parent_netns:
        raise RuntimeError('Docker harness is not in its private network namespace')
    run_info = Path('/run').stat()
    if f'{run_info.st_dev}:{run_info.st_ino}' == parent_run:
        raise RuntimeError('Docker harness /run is not a private mount')


def require_guest():
    assert_vm_marker()
    if os.environ.get('DOCKER_HOST'):
        raise RuntimeError('DOCKER_HOST must be unset; remote Docker targets are forbidden')
    for binary in ('docker', 'dockerd'):
        if shutil.which(binary) is None:
            raise SkipCase(f'{binary} is not installed in this guest')


def assert_guest_guard():
    # Re-check immediately before starting the private daemon or changing firewall state.
    assert_vm_marker()


def root_owned_install(path):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError(f'Untrusted suite install path: {item}')
    if not path.is_dir():
        raise RuntimeError(f'Suite install path is not a directory: {path}')
    return path


def write_json(path, value):
    temp = path.with_name(path.name + '.l4s-tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, (json.dumps(value, indent=2, sort_keys=True) + '\n').encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temp, path)


def docker_cmd(socket_path, *args, **kwargs):
    return run(['docker', '--host', f'unix://{socket_path}', *args], **kwargs)


def docker_version(socket_path):
    return docker_cmd(socket_path, 'version', '--format', '{{.Server.Version}}').stdout.strip()


def version_tuple(value):
    match = re.match(r'(\d+)\.(\d+)', value)
    return tuple(map(int, match.groups())) if match else (0, 0)


def make_daemon_path(workdir, frontend):
    shim = workdir / 'bin'
    shim.mkdir(mode=0o700, exist_ok=True)
    if frontend == 'none':
        return os.environ.copy()
    for family in ('iptables', 'ip6tables'):
        for suffix in ('', '-restore', '-save'):
            name = family + suffix
            target = Path('/usr/sbin') / f'{family}-{frontend}{suffix}'
            if not target.exists():
                raise SkipCase(f'{target.name} is not installed in this guest')
            link = shim / name
            if link.exists() or link.is_symlink():
                if not link.is_symlink() or link.resolve() != target.resolve():
                    raise RuntimeError(f'Unexpected executable in private Docker PATH: {link}')
            else:
                link.symlink_to(target)
    env = os.environ.copy()
    env['PATH'] = str(shim) + os.pathsep + env.get('PATH', '/usr/sbin:/usr/bin:/sbin:/bin')
    return env


def start_docker_daemon(args, workdir):
    socket_path = workdir / 'docker.sock'
    frontend = args.iptables_frontend if args.docker_backend == 'iptables' else 'none'
    env = make_daemon_path(workdir, frontend)
    daemon_path = shutil.which('dockerd', path=env['PATH'])
    config = {
        'data-root': str(workdir / 'data'),
        'exec-root': str(workdir / 'exec'),
        'pidfile': str(workdir / 'dockerd.pid'),
        'hosts': [f'unix://{socket_path}'],
        'iptables': True,
        'ip6tables': True,
        'firewall-backend': args.docker_backend,
        'ipv6': True,
        'fixed-cidr-v6': CONTAINER_TEST_CIDR6,
        'default-address-pools': [
            {'base': '172.30.0.0/16', 'size': 24},
            DOCKER_TEST_IPV6_POOL,
        ],
    }
    if args.docker_backend == 'nftables':
        config['experimental'] = True
    config_path = workdir / 'daemon.json'
    write_json(config_path, config)
    assert_guest_guard()
    log = (workdir / 'dockerd.log').open('w')
    process = subprocess.Popen(
        [daemon_path, '--config-file', str(config_path)], env=env,
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError(f'dockerd exited early; see {workdir / "dockerd.log"}')
            if socket_path.exists():
                probe = docker_cmd(socket_path, 'info', check=False, timeout=3, env=env)
                if probe.returncode == 0:
                    return process, log, socket_path, env
            time.sleep(1)
        raise RuntimeError(f'dockerd did not become ready; see {workdir / "dockerd.log"}')
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log.close()
        raise


def stop_docker_daemon(process, log):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if log is not None:
        log.close()


def copy_runtime_dependency(path, rootfs):
    source = Path(path)
    target = rootfs / source.as_posix().lstrip('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        return
    if source.is_symlink():
        link_text = os.readlink(source)
        target.symlink_to(link_text)
        linked_source = Path(link_text) if os.path.isabs(link_text) else source.parent / link_text
        copy_runtime_dependency(linked_source, rootfs)
    else:
        shutil.copy2(source, target)


def python_dependencies(binary, stdlib):
    dependencies = {binary}
    candidates = [binary, *(p for p in (stdlib / 'lib-dynload').glob('*') if p.is_file() and '.so' in p.name)]
    for candidate in candidates:
        result = run(['ldd', candidate], check=False)
        if result.returncode:
            continue
        for line in result.stdout.splitlines():
            match = re.search(r'=>\s+(/\S+)', line) or re.match(r'\s*(/\S+)\s+\(', line)
            if match:
                dependencies.add(Path(match.group(1)))
    return dependencies


def build_local_python_image(name, workdir, socket_path, daemon_env):
    rootfs = workdir / 'python-rootfs'
    rootfs.mkdir()
    binary = Path(sys.executable).resolve()
    stdlib = Path(sysconfig.get_paths()['stdlib']).resolve()
    if not binary.is_file() or not stdlib.is_dir():
        raise SkipCase('Guest Python interpreter/stdlib is unavailable for local image import')
    binary_target = rootfs / binary.as_posix().lstrip('/')
    binary_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, binary_target)
    interpreter_link = binary_target.parent / 'python3'
    if not interpreter_link.exists():
        interpreter_link.symlink_to(binary_target.name)
    stdlib_target = rootfs / stdlib.as_posix().lstrip('/')
    stdlib_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(stdlib, stdlib_target, symlinks=True)
    for dependency in python_dependencies(binary, stdlib):
        copy_runtime_dependency(dependency, rootfs)
    chroot_smoke = run([
        'chroot', rootfs, '/usr/bin/python3', '-c',
        'import socket,ssl; print("python-rootfs-ok")',
    ], check=False, timeout=10)
    if chroot_smoke.returncode:
        raise RuntimeError(f'Generated Python rootfs is not executable: {chroot_smoke.stderr.strip()}')
    app = rootfs / 'opt/server.py'
    app.parent.mkdir(parents=True, exist_ok=True)
    app.write_text(
        'import socket, threading\n'
        'def tcp_server(family,address):\n'
        ' s=socket.socket(family,socket.SOCK_STREAM); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)\n'
        ' if family==socket.AF_INET6: s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)\n'
        ' s.bind((address,18443)); s.listen(32)\n'
        ' while True:\n'
        '  c,_=s.accept()\n'
        '  try:\n'
        '   data=c.recv(4096); c.sendall(b"tcp:"+data)\n'
        '  finally: c.close()\n'
        'def udp_server(family,address):\n'
        ' s=socket.socket(family,socket.SOCK_DGRAM)\n'
        ' if family==socket.AF_INET6: s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)\n'
        ' s.bind((address,18443))\n'
        ' while True:\n'
        '  data,addr=s.recvfrom(4096); s.sendto(b"udp:"+data,addr)\n'
        'for family,address in ((socket.AF_INET,"0.0.0.0"),(socket.AF_INET6,"::")):\n'
        ' threading.Thread(target=tcp_server,args=(family,address),daemon=True).start()\n'
        ' threading.Thread(target=udp_server,args=(family,address),daemon=True).start()\n'
        'threading.Event().wait()\n'
    )
    archive = workdir / 'python-rootfs.tar'
    with tarfile.open(archive, 'w') as output:
        for child in sorted(rootfs.iterdir()):
            output.add(child, arcname=child.name, recursive=True)
    docker_cmd(socket_path, 'import', archive, name, timeout=180, env=daemon_env)
    docker_cmd(socket_path, 'run', '--rm', '--entrypoint', 'python3', name, '-c',
               'import socket,ssl; print("python-image-ok")', env=daemon_env)
    return archive


def create_client_namespace(name):
    assert_guest_guard()
    run(['ip', 'netns', 'add', name])
    run(['ip', 'link', 'add', 'l4s-vm0', 'type', 'veth', 'peer', 'name', 'l4s-client0'])
    run(['ip', 'link', 'set', 'l4s-client0', 'netns', name])
    run(['ip', 'addr', 'add', HOST_TEST_IP + '/24', 'dev', 'l4s-vm0'])
    run(['ip', '-6', 'addr', 'add', HOST_TEST_IP6 + '/64', 'dev', 'l4s-vm0'])
    run(['ip', 'link', 'set', 'l4s-vm0', 'up'])
    run(['ip', 'netns', 'exec', name, 'ip', 'link', 'set', 'lo', 'up'])
    run(['ip', 'netns', 'exec', name, 'ip', 'addr', 'add', CLIENT_TEST_IP + '/24', 'dev', 'l4s-client0'])
    run(['ip', 'netns', 'exec', name, 'ip', '-6', 'addr', 'add', CLIENT_TEST_IP6 + '/64', 'dev', 'l4s-client0'])
    run(['ip', 'netns', 'exec', name, 'ip', 'link', 'set', 'l4s-client0', 'up'])
    run(['sysctl', '-q', '-w', 'net.ipv4.ip_forward=1'])
    run(['sysctl', '-q', '-w', 'net.ipv6.conf.all.forwarding=1'])
    run(['sysctl', '-q', '-w', 'net.ipv6.conf.default.forwarding=1'])
def peer_python(namespace, source):
    code = (
        'import socket; s=socket.socket(); s.settimeout(1); s.bind(("198.18.0.2",0)); '
        f's.connect(({HOST_TEST_IP!r},{PUBLIC_PORT})); s.sendall({source!r}); '
        'print(s.recv(100).decode()); s.close()'
    )
    return run(['ip', 'netns', 'exec', namespace, 'python3', '-c', code]).stdout.strip()


def peer_udp(namespace, payload):
    code = (
        'import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(.5); '
        's.bind(("198.18.0.2",0)); '
        f's.sendto({payload!r},({HOST_TEST_IP!r},{PUBLIC_PORT})); '
        'print(s.recvfrom(100)[0].decode())'
    )
    return run(['ip', 'netns', 'exec', namespace, 'python3', '-c', code], check=False, timeout=3)


def peer_python6(namespace, payload):
    code = (
        'import socket; s=socket.socket(socket.AF_INET6); s.settimeout(2); '
        f's.bind(({CLIENT_TEST_IP6!r},0,0,0)); '
        f's.connect(({HOST_TEST_IP6!r},{PUBLIC_PORT},0,0)); s.sendall({payload!r}); '
        'print(s.recv(100).decode()); s.close()'
    )
    return run(['ip', 'netns', 'exec', namespace, 'python3', '-c', code]).stdout.strip()


def peer_udp6(namespace, payload):
    code = (
        'import socket; s=socket.socket(socket.AF_INET6,socket.SOCK_DGRAM); s.settimeout(.5); '
        f's.bind(({CLIENT_TEST_IP6!r},0,0,0)); '
        f's.sendto({payload!r},({HOST_TEST_IP6!r},{PUBLIC_PORT},0,0)); '
        'print(s.recvfrom(100)[0].decode())'
    )
    return run(['ip', 'netns', 'exec', namespace, 'python3', '-c', code], check=False, timeout=3)


def docker_exec_expect(socket_path, daemon_env, container, code, allowed):
    result = docker_cmd(socket_path, 'exec', container, 'python3', '-c', code,
                        check=False, timeout=5, env=daemon_env)
    if (result.returncode == 0) != allowed:
        raise AssertionError(f'container egress allowed={allowed}, got rc={result.returncode}: {result.stderr.strip()}')


def iptables_foreign(frontend):
    for family in ('iptables', 'ip6tables'):
        binary = f'{family}-{frontend}'
        if run([binary, '-S', 'L4S_VM_FOREIGN'], check=False).returncode == 0:
            raise SkipCase(f'Guest already has the test foreign-chain name in {family}; use a fresh namespace')
        run([binary, '-N', 'L4S_VM_FOREIGN'])
        run([binary, '-A', 'L4S_VM_FOREIGN', '-p', 'tcp', '--dport', '49151', '-j', 'RETURN'])
        run([binary, '-I', 'INPUT', '1', '-j', 'L4S_VM_FOREIGN'])


def remove_iptables_foreign(frontend):
    for family in ('iptables', 'ip6tables'):
        binary = f'{family}-{frontend}'
        run([binary, '-D', 'INPUT', '-j', 'L4S_VM_FOREIGN'], check=False)
        run([binary, '-F', 'L4S_VM_FOREIGN'], check=False)
        run([binary, '-X', 'L4S_VM_FOREIGN'], check=False)


def nft_foreign(create):
    if create:
        if 'inet l4s_vm_foreign' in run(['nft', 'list', 'tables']).stdout:
            raise SkipCase('Guest already has the test foreign table name; use a fresh VM snapshot')
        text = (
            'add table inet l4s_vm_foreign\n'
            'add chain inet l4s_vm_foreign input { type filter hook input priority -300; policy accept; }\n'
            'add rule inet l4s_vm_foreign input tcp dport 49151 counter accept\n'
        )
        run(['nft', '-f', '-'], input_text=text)
    else:
        run(['nft', 'delete', 'table', 'inet', 'l4s_vm_foreign'], check=False)


def nft_foreign_snapshot():
    text = run(['nft', '-s', 'list', 'table', 'inet', 'l4s_vm_foreign']).stdout
    if not re.search(
        r'\btype\s+filter\s+hook\s+input\s+priority\s+(?:raw|-300)\s*;\s*policy\s+accept\s*;',
        text,
    ):
        raise AssertionError(f'Foreign nftables input base-chain hook/policy changed:\n{text}')
    if not re.search(
        r'\btcp\s+dport\s+49151\s+counter(?:\s+packets\s+\d+\s+bytes\s+\d+)?\s+accept\b',
        text,
    ):
        raise AssertionError(f'Foreign nftables TCP rule attributes changed:\n{text}')
    return re.sub(r'counter packets \d+ bytes \d+', 'counter', text)


def iptables_rules(frontend):
    return run([f'iptables-{frontend}-save']).stdout


def assert_iptable_foreign(frontend):
    for family in ('iptables', 'ip6tables'):
        text = run([f'{family}-{frontend}-save']).stdout
        lines = [line for line in text.splitlines() if 'L4S_VM_FOREIGN' in line]
        if not any(line.startswith(':L4S_VM_FOREIGN ') for line in lines) or not any(
            line.startswith('-A L4S_VM_FOREIGN ') and '-p tcp' in line
            and '--dport 49151' in line and '-j RETURN' in line
            for line in lines
        ) or not any(
            line.startswith('-A INPUT ') and '-j L4S_VM_FOREIGN' in line
            for line in lines
        ):
            raise AssertionError(
                f'Suite changed the foreign {family} chain, rule, or INPUT hook: {lines!r}'
            )


def suite_command(root, state, backend, operation, frontend, args=(), check=True):
    command = [
        str(root / 'ipp.sh'), '--state-dir', str(state), '--backend', backend,
        operation, '--local', '--set', f'IPTABLES_FRONTEND={frontend}', *args,
    ]
    assert_vm_marker()
    return run(command, timeout=90, check=check)


def prepare_access(path, container_ip, container_ip6, bridge, limited_egress):
    grants = {'containers': [{
            'group': 'vm-audit-web', 'source': CLIENT_TEST_IP + '/32',
            'destination': container_ip + '/32', 'input': 'l4s-vm0',
            'output': bridge, 'protocol': 'tcp', 'ports': str(CONTAINER_PORT),
            'public_ports': str(PUBLIC_PORT), 'public_destination': HOST_TEST_IP + '/32',
            'service': 'http_https_protect',
        }, {
            'group': 'vm-audit-web-v6', 'source': CLIENT_TEST_IP6 + '/128',
            'destination': container_ip6 + '/128', 'input': 'l4s-vm0',
            'output': bridge, 'protocol': 'tcp', 'ports': str(CONTAINER_PORT),
            'public_ports': str(PUBLIC_PORT), 'public_destination': HOST_TEST_IP6 + '/128',
            'service': 'http_https_protect',
        }]}
    if limited_egress:
        grants['forward'] = [{
            'group': 'vm-audit-egress', 'source': container_ip + '/32',
            'destination': CLIENT_TEST_IP + '/32', 'input': bridge,
            'output': 'l4s-vm0', 'protocol': 'tcp', 'ports': str(EGRESS_ALLOWED),
        }]
    write_json(path, grants)


def normalize_iptables(frontend):
    return normalize_rule_dump(iptables_rules(frontend))


def normalize_rule_dump(text):
    text = re.sub(r'\[\d+:\d+\]', '[0:0]', text)
    return re.sub(r'^# (?:Generated by|Completed on) .*\n?', '', text, flags=re.M)


def test_case(args):
    assert_guest_guard()
    suite = root_owned_install(args.suite_root)
    if args.suite_backend == 'iptables' and args.docker_backend != 'iptables':
        raise SkipCase('iptables suite requires Docker iptables backend in the same frontend')
    if args.docker_backend == 'nftables' and args.suite_backend != 'nftables':
        raise SkipCase('iptables suite with native nftables Docker is unsupported')
    old_forward = run(['sysctl', '-n', 'net.ipv4.ip_forward']).stdout.strip()
    old_v6_forward_all = run(['sysctl', '-n', 'net.ipv6.conf.all.forwarding']).stdout.strip()
    old_v6_forward_default = run(['sysctl', '-n', 'net.ipv6.conf.default.forwarding']).stdout.strip()
    docker_name = f'l4s-vm-audit-{uuid.uuid4().hex[:10]}'
    namespace = f'l4s-audit-{uuid.uuid4().hex[:5]}'
    workdir = Path(tempfile.mkdtemp(prefix='l4s-vm-docker-', dir='/run'))
    state = workdir / 'state'
    state.mkdir(mode=0o700)
    access_path = workdir / 'access.json'
    peer = None
    imported_image = f'l4d2-suite-vm-audit:{uuid.uuid4().hex[:12]}'
    foreign_ready = False
    foreign_nft_snapshot = None
    suite_applied = False
    namespace_created = False
    interface_created = False
    daemon_process = None
    daemon_log = None
    socket_path = workdir / 'docker.sock'
    daemon_env = os.environ.copy()
    try:
        daemon_version = run(['dockerd', '--version']).stdout
        daemon_version_match = re.search(r'\bversion\s+(\d+\.\d+)', daemon_version)
        if not daemon_version_match:
            raise RuntimeError(f'Cannot parse dockerd version: {daemon_version.strip()}')
        if args.docker_backend == 'nftables' and version_tuple(daemon_version_match.group(1)) < (29, 0):
            raise SkipCase('Docker nftables firewall backend requires Engine 29.0.0 or newer (experimental)')
        if args.docker_backend == 'iptables':
            # Validate both families before dockerd is started; PATH shims keep
            # this choice private to this daemon and avoid alternatives changes.
            make_daemon_path(workdir, args.iptables_frontend)
        if old_forward != '1':
            assert_guest_guard()
            run(['sysctl', '-q', '-w', 'net.ipv4.ip_forward=1'])
        if old_v6_forward_all != '1':
            assert_guest_guard()
            run(['sysctl', '-q', '-w', 'net.ipv6.conf.all.forwarding=1'])
        if old_v6_forward_default != '1':
            assert_guest_guard()
            run(['sysctl', '-q', '-w', 'net.ipv6.conf.default.forwarding=1'])
        # Docker must see the published IPv6 bind address before it programs
        # port publishing; create the peer link before starting its daemon.
        interface_created = True
        create_client_namespace(namespace)
        namespace_created = True
        daemon_process, daemon_log, socket_path, daemon_env = start_docker_daemon(args, workdir)
        version = docker_version(socket_path)
        if args.docker_backend == 'nftables' and version_tuple(version) < (29, 0):
            raise SkipCase('Docker nftables firewall backend requires Engine 29.0.0 or newer (experimental)')
        info = docker_cmd(socket_path, 'info', env=daemon_env).stdout.lower()
        if 'swarm: active' in info:
            raise SkipCase('Docker nftables firewall backend is unavailable in Swarm mode')
        assert_guest_guard()
        build_local_python_image(imported_image, workdir, socket_path, daemon_env)
        peer = create_peer_process(namespace)
        assert_guest_guard()
        if args.suite_backend == 'iptables':
            iptables_foreign(args.iptables_frontend)
        else:
            nft_foreign(True)
            foreign_nft_snapshot = nft_foreign_snapshot()
        foreign_ready = True
        assert_guest_guard()
        container = run([
            'docker', '--host', f'unix://{socket_path}', 'run', '-d', '--name', docker_name,
            '--publish', f'{HOST_TEST_IP}:{PUBLIC_PORT}:{CONTAINER_PORT}/tcp',
            '--publish', f'{HOST_TEST_IP}:{PUBLIC_PORT}:{CONTAINER_PORT}/udp',
            '--publish', f'[{HOST_TEST_IP6}]:{PUBLIC_PORT}:{CONTAINER_PORT}/tcp',
            '--publish', f'[{HOST_TEST_IP6}]:{PUBLIC_PORT}:{CONTAINER_PORT}/udp',
            '--entrypoint', 'python3', imported_image, '/opt/server.py',
        ], env=daemon_env).stdout.strip()
        inspect = json.loads(docker_cmd(socket_path, 'inspect', container, env=daemon_env).stdout)[0]
        networks = inspect['NetworkSettings']['Networks']
        net = networks.get('bridge') or next(iter(networks.values()))
        container_ip = net['IPAddress']
        container_ip6 = net['GlobalIPv6Address']
        bridge = 'docker0'
        if not container_ip:
            raise RuntimeError('Docker did not assign the test container an IPv4 address')
        if not container_ip6:
            raise RuntimeError('Docker did not assign the test container an IPv6 address')
        container_ip6 = container_ip6.split('%', 1)[0]
        limited_egress = args.suite_backend == 'iptables' or args.docker_backend == 'nftables'
        prepare_access(access_path, container_ip, container_ip6, bridge, limited_egress)
        frontend = args.iptables_frontend if args.docker_backend == 'iptables' else 'nft'
        routed_policy = 'drop' if limited_egress else 'unmanaged'
        options = [
            '--only', 'http_https_protect', '--set', 'HOST_SERVICES=false',
            '--set', 'CONTAINER_POLICY=restrict', '--set', f'ROUTED_POLICY={routed_policy}',
            '--set', f'DOCKER_BACKEND={args.docker_backend}', '--set', f'ACCESS_POLICY={access_path}',
            '--set', f'HTTP_HTTPS_PORTS={CONTAINER_PORT}', '--set', 'FAMILY_POLICY=dual',
        ]
        suite_command(suite, state, args.suite_backend, 'apply', frontend, options)
        suite_applied = True
        if peer_python(namespace, b'container-reply') != 'tcp:container-reply':
            raise AssertionError('Published TCP flow or return path failed')
        if peer_python6(namespace, b'container-reply-v6') != 'tcp:container-reply-v6':
            raise AssertionError('Published IPv6 TCP flow or return path failed')
        udp_denied = peer_udp(namespace, b'udp-must-be-denied')
        if udp_denied.returncode == 0:
            raise AssertionError('UDP inherited the TCP container grant')
        udp6_denied = peer_udp6(namespace, b'udp-v6-must-be-denied')
        if udp6_denied.returncode == 0:
            raise AssertionError('IPv6 UDP inherited the IPv6 TCP container grant')

        # The forward grant is exact to one destination port; the adjacent
        # listener is deliberately live so a firewall pass cannot look like a
        # service failure.
        if limited_egress:
            egress = (
                f'import socket; s=socket.create_connection(("198.18.0.2",{EGRESS_ALLOWED}),timeout=2); '
                'assert s.recv(10)==b"ready"; s.sendall(b"egress"); s.close()'
            )
            docker_exec_expect(socket_path, daemon_env, docker_name, egress, True)
            blocked_egress = (
                'import socket; s=socket.socket(); s.settimeout(.5); '
                f's.connect(("198.18.0.2",{EGRESS_BLOCKED})); s.close()'
            )
            docker_exec_expect(socket_path, daemon_env, docker_name, blocked_egress, False)

        if args.suite_backend == 'iptables':
            before = normalize_iptables(frontend)
            v6_before = normalize_rule_dump(run([f'ip6tables-{frontend}-save']).stdout)
            suite_command(suite, state, args.suite_backend, 'apply', frontend, options)
            after = normalize_iptables(frontend)
            if after != before:
                delta = ''.join(difflib.unified_diff(
                    before.splitlines(True), after.splitlines(True),
                    fromfile='before-apply', tofile='after-apply',
                ))
                raise AssertionError(f'Repeated apply changed iptables rules or duplicated integration:\n{delta}')
            v6_after = normalize_rule_dump(run([f'ip6tables-{frontend}-save']).stdout)
            if v6_after != v6_before:
                raise AssertionError('Repeated apply changed IPv6 iptables rules or duplicated integration')
            assert_iptable_foreign(frontend)
            integration_count = before.count('--comment "l4d2-suite:integration"')
            v6_count = v6_before.count('--comment "l4d2-suite:integration"')
            if integration_count != 2 or v6_count != 2:
                raise AssertionError(
                    f'Expected two suite hooks per family, got IPv4={integration_count}, IPv6={v6_count}'
                )
        else:
            table = run(['nft', '-s', 'list', 'table', 'inet', 'firewall_main']).stdout
            suite_command(suite, state, args.suite_backend, 'apply', frontend, options)
            if run(['nft', '-s', 'list', 'table', 'inet', 'firewall_main']).stdout != table:
                raise AssertionError('Repeated apply changed nftables suite rules unexpectedly')
            if nft_foreign_snapshot() != foreign_nft_snapshot:
                raise AssertionError('Suite apply changed the foreign nftables table structure')

        suite_command(suite, state, args.suite_backend, 'disable', frontend)
        suite_applied = False
        if peer_python(namespace, b'after-disable') != 'tcp:after-disable':
            raise AssertionError('Disabling suite interrupted Docker published TCP flow')
        if peer_python6(namespace, b'after-disable-v6') != 'tcp:after-disable-v6':
            raise AssertionError('Disabling suite interrupted Docker published IPv6 TCP flow')
        if peer_udp(namespace, b'after-disable').returncode != 0:
            raise AssertionError('Docker UDP publication did not survive suite disable')
        if peer_udp6(namespace, b'after-disable-v6').returncode != 0:
            raise AssertionError('Docker IPv6 UDP publication did not survive suite disable')
        if args.suite_backend == 'iptables':
            assert_iptable_foreign(frontend)
        elif nft_foreign_snapshot() != foreign_nft_snapshot:
            raise AssertionError('Suite disable changed the foreign nftables table structure')
        if args.docker_backend == 'iptables':
            nat = run([f'iptables-{args.iptables_frontend}', '-t', 'nat', '-S']).stdout
            if f'--to-destination {container_ip}:{CONTAINER_PORT}' not in nat:
                raise AssertionError('Disabling suite removed Docker DNAT publication')
            nat6 = run([f'ip6tables-{args.iptables_frontend}', '-t', 'nat', '-S']).stdout
            if f'--to-destination [{container_ip6}]:{CONTAINER_PORT}' not in nat6 and f'--to-destination {container_ip6}:{CONTAINER_PORT}' not in nat6:
                raise AssertionError('Disabling suite removed Docker IPv6 DNAT publication')
        else:
            docker_rules = run(['nft', '-s', 'list', 'table', 'ip', 'docker-bridges']).stdout
            if f'dnat to {container_ip}:{CONTAINER_PORT}' not in docker_rules:
                raise AssertionError('Disabling suite removed Docker nftables publication')
            docker_rules6 = run(['nft', '-s', 'list', 'table', 'ip6', 'docker-bridges']).stdout
            if not re.search(
                r'\bdnat(?:\s+ip6)?\s+to\s+\[?'
                + re.escape(container_ip6)
                + r'\]?:' + str(CONTAINER_PORT) + r'\b',
                docker_rules6,
            ):
                raise AssertionError(
                    'Docker nftables IPv6 DNAT rule not found after suite disable:\n'
                    + docker_rules6
                )
        print(json.dumps({
            'status': 'PASS', 'suite_backend': args.suite_backend,
            'docker_backend': args.docker_backend,
            'iptables_frontend': args.iptables_frontend if args.docker_backend == 'iptables' else None,
            'docker_version': version, 'image': 'guest-generated Python stdlib rootfs imported locally',
            'checks': [
                'IPv4/IPv6 DNAT remap', 'IPv4/IPv6 TCP return',
                'IPv4/IPv6 TCP/UDP isolation',
                'scoped egress' if limited_egress else 'egress delegated to Docker (not suite-scoped)',
                'foreign rules', 'idempotent apply', 'disable preserves Docker',
            ],
        }, sort_keys=True))
    finally:
        assert_vm_marker()
        if suite_applied:
            suite_command(suite, state, args.suite_backend, 'disable', args.iptables_frontend, check=False)
        if daemon_process is not None:
            if daemon_process.poll() is None:
                docker_cmd(socket_path, 'rm', '-f', docker_name, check=False, timeout=30, env=daemon_env)
                if imported_image:
                    docker_cmd(socket_path, 'image', 'rm', '-f', imported_image,
                               check=False, timeout=30, env=daemon_env)
            stop_docker_daemon(daemon_process, daemon_log)
        if peer is not None:
            peer.terminate()
            peer.wait(timeout=3)
        if interface_created or run(['ip', 'link', 'show', 'l4s-vm0'], check=False).returncode == 0:
            run(['ip', 'link', 'del', 'l4s-vm0'], check=False)
        if namespace_created or run(['ip', 'netns', 'list'], check=False).stdout.find(namespace) >= 0:
            run(['ip', 'netns', 'del', namespace], check=False)
        if foreign_ready:
            if args.suite_backend == 'iptables':
                remove_iptables_foreign(args.iptables_frontend)
            else:
                nft_foreign(False)
        run(['sysctl', '-q', '-w', f'net.ipv4.ip_forward={old_forward}'], check=False)
        run(['sysctl', '-q', '-w', f'net.ipv6.conf.all.forwarding={old_v6_forward_all}'], check=False)
        run(['sysctl', '-q', '-w', f'net.ipv6.conf.default.forwarding={old_v6_forward_default}'], check=False)
        shutil.rmtree(workdir, ignore_errors=True)


def create_peer_process(namespace):
    server = (
        'import socket,threading,time\n'
        'def serve(s):\n'
        ' while True:\n'
        '  c,_=s.accept()\n'
        '  try: c.sendall(b"ready"); c.recv(100)\n'
        '  finally: c.close()\n'
        'listeners=[]\n'
        f'for p in ({EGRESS_ALLOWED},{EGRESS_BLOCKED}):\n'
        ' s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("198.18.0.2",p)); s.listen(10); listeners.append(s)\n'
        'for s in listeners: threading.Thread(target=serve,args=(s,),daemon=True).start()\n'
        'print("ready",flush=True); time.sleep(3600)\n'
    )
    process = subprocess.Popen(
        ['ip', 'netns', 'exec', namespace, 'python3', '-u', '-c', server],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if process.stdout.readline().strip() != 'ready':
        raise RuntimeError('External egress peer listener failed to start')
    return process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-root', type=Path, default=DEFAULT_SUITE)
    parser.add_argument('--suite-backend', choices=('iptables', 'nftables'), required=True)
    parser.add_argument('--docker-backend', choices=('iptables', 'nftables'), required=True)
    parser.add_argument('--iptables-frontend', choices=('nft', 'legacy'), default='nft')
    args = parser.parse_args()
    try:
        require_guest()
        test_case(args)
    except SkipCase as error:
        print(f'SKIP: {error}', file=sys.stderr)
        return 77
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
