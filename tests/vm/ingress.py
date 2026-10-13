#!/usr/bin/env python3
"""Exercise CONTAINER_POLICY=ingress with real Docker iptables-nft rules."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import selectors
import shutil
import socket
import subprocess
import tempfile
import uuid


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('l4s_docker_harness', HERE / 'docker.py')
docker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(docker)

HOST4 = docker.HOST_TEST_IP
PEER4 = docker.CLIENT_TEST_IP
OTHER4 = '198.18.0.3'
HOST6 = docker.HOST_TEST_IP6
PEER6 = docker.CLIENT_TEST_IP6
OTHER6 = 'fd00:198:18:2::3'
PUBLIC = docker.PUBLIC_PORT
PRIVATE = docker.CONTAINER_PORT
UNGRANTED_PUBLIC = PUBLIC + 1
LIVE_PUBLIC = PUBLIC + 2
LIVE_PRIVATE = PRIVATE + 3
EGRESS = docker.EGRESS_ALLOWED


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def add_client_aliases(namespace):
    docker.assert_guest_guard()
    docker.run(['ip', 'netns', 'exec', namespace, 'ip', 'addr', 'add', OTHER4 + '/24', 'dev', 'l4s-client0'])
    docker.run(['ip', 'netns', 'exec', namespace, 'ip', '-6', 'addr', 'add', OTHER6 + '/64', 'dev', 'l4s-client0'])


def peer_tcp(namespace, source, destination, port, payload=b'ingress'):
    family = socket.AF_INET6 if ':' in source else socket.AF_INET
    code = (
        'import socket; '
        f's=socket.socket({family},socket.SOCK_STREAM); s.settimeout(1.5); '
        f's.bind(({source!r},0' + (',0,0' if family == socket.AF_INET6 else '') + ')); '
        f's.connect(({destination!r},{port}' + (',0,0' if family == socket.AF_INET6 else '') + ')); '
        f's.sendall({payload!r}); print(s.recv(100).decode()); s.close()'
    )
    return docker.run(['ip', 'netns', 'exec', namespace, 'python3', '-c', code], check=False, timeout=4)


def peer_udp(namespace, source, destination, port):
    family = socket.AF_INET6 if ':' in source else socket.AF_INET
    code = (
        'import socket; '
        f's=socket.socket({family},socket.SOCK_DGRAM); s.settimeout(.6); '
        f's.bind(({source!r},0' + (',0,0' if family == socket.AF_INET6 else '') + ')); '
        f's.sendto(b"udp",({destination!r},{port}' + (',0,0' if family == socket.AF_INET6 else '') + ')); '
        'print(s.recvfrom(100)[0].decode())'
    )
    return docker.run(['ip', 'netns', 'exec', namespace, 'python3', '-c', code], check=False, timeout=3)


def add_grant(source, source6, container_ip, container_ip6, bridge, public, private):
    return [{
        'group': f'vm-ingress-{public}',
        'source': source + ('/32' if ':' not in source else '/128'),
        'destination': container_ip + '/32', 'input': 'l4s-vm0', 'output': bridge,
        'protocol': 'tcp', 'ports': str(private), 'public_ports': str(public),
        'public_destination': HOST4 + '/32', 'service': 'http_https_protect',
    }, {
        'group': f'vm-ingress6-{public}',
        'source': source6 + '/128', 'destination': container_ip6 + '/128',
        'input': 'l4s-vm0', 'output': bridge, 'protocol': 'tcp',
        'ports': str(private), 'public_ports': str(public),
        'public_destination': HOST6 + '/128', 'service': 'http_https_protect',
    }]


def create_forward_peer(namespace):
    code = (
        'import socket,time\n'
        f's=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(({PEER4!r},{EGRESS})); s.listen(10)\n'
        'print("ready",flush=True)\n'
        'while True:\n'
        ' c,_=s.accept()\n'
        ' try:\n'
        '  c.sendall(b"ready"); data=c.recv(100); c.sendall(b"ack:"+data)\n'
        ' finally: c.close()\n'
    )
    proc = subprocess.Popen(
        ['ip', 'netns', 'exec', namespace, 'python3', '-u', '-c', code],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.stdout.readline().strip() != 'ready':
        raise RuntimeError('Scoped routed peer listener failed to start')
    return proc


def start_live_service(socket_path, env, container):
    code = (
        'import socket,threading\n'
        'def serve(fam,addr):\n'
        ' s=socket.socket(fam,socket.SOCK_STREAM); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)\n'
        ' if fam==socket.AF_INET6: s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)\n'
        f' s.bind((addr,{LIVE_PRIVATE})); s.listen(32)\n'
        ' while True:\n'
        '  c,_=s.accept()\n'
        '  try:\n'
        '   while True:\n'
        '    data=c.recv(4096)\n'
        '    if not data: break\n'
        '    c.sendall(b"live:"+data)\n'
        '  finally: c.close()\n'
        'for fam,addr in ((socket.AF_INET,"0.0.0.0"),(socket.AF_INET6,"::")):\n'
        ' threading.Thread(target=serve,args=(fam,addr),daemon=True).start()\n'
        'threading.Event().wait()\n'
    )
    docker.docker_cmd(socket_path, 'exec', '-d', container, 'python3', '-c', code, env=env)


def create_live_peer(namespace, source):
    code = (
        'import socket,sys\n'
        f's=socket.socket(); s.settimeout(2); s.bind(({source!r},0)); '
        f's.connect(({HOST4!r},{LIVE_PUBLIC})); s.sendall(b"first"); '
        'assert s.recv(100)==b"live:first"; print("READY",flush=True)\n'
        'for line in sys.stdin:\n'
        ' data=line.strip().encode()\n'
        ' if data==b"QUIT": break\n'
        ' s.settimeout(.8)\n'
        ' try:\n'
        '  s.sendall(data); answer=s.recv(100); print("REPLY:"+answer.decode(),flush=True)\n'
        ' except TimeoutError:\n'
        '  print("TIMEOUT",flush=True); break\n'
        ' except OSError as exc:\n'
        '  print("CLOSED:"+str(exc),flush=True); break\n'
        's.close()\n'
    )
    proc = subprocess.Popen(
        ['ip', 'netns', 'exec', namespace, 'python3', '-u', '-c', code],
        text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.stdout.readline().strip() != 'READY':
        err = proc.stderr.read()
        raise RuntimeError(f'Could not establish initial granted TCP session: {err}')
    return proc


def live_peer_request(proc, value, timeout=2):
    proc.stdin.write(value + '\n')
    proc.stdin.flush()
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    events = selector.select(timeout)
    selector.close()
    if not events:
        raise AssertionError('Live TCP probe produced no observation before timeout')
    return proc.stdout.readline().strip()


def iptables_snapshots():
    return {
        'nat4': docker.run(['iptables-nft', '-t', 'nat', '-S']).stdout,
        'nat6': docker.run(['ip6tables-nft', '-t', 'nat', '-S']).stdout,
        'user4': docker.run(['iptables-nft', '-S', 'DOCKER-USER']).stdout,
        'user6': docker.run(['ip6tables-nft', '-S', 'DOCKER-USER']).stdout,
    }


def install_foreign_iptables_fixtures():
    """Seed inert, exact-match VPN NAT and DOCKER-USER rules for preservation checks."""
    for family in ('iptables-nft', 'ip6tables-nft'):
        if docker.run([family, '-t', 'nat', '-S', 'L4S_VM_INGRESS_VPN'], check=False).returncode == 0:
            raise RuntimeError(f'Private guest already contains L4S_VM_INGRESS_VPN in {family}')
        if docker.run([family, '-S', 'DOCKER-USER'], check=False).returncode:
            raise RuntimeError(f'Docker did not create DOCKER-USER in {family}')
    for family in ('iptables-nft', 'ip6tables-nft'):
        docker.run([family, '-t', 'nat', '-N', 'L4S_VM_INGRESS_VPN'])
        docker.run([family, '-t', 'nat', '-A', 'L4S_VM_INGRESS_VPN',
                    '-p', 'tcp', '--dport', '49151', '-j', 'RETURN'])
        docker.run([family, '-I', 'DOCKER-USER', '1', '-p', 'tcp',
                    '--dport', '49151', '-j', 'RETURN'])


def remove_foreign_iptables_fixtures():
    for family in ('iptables-nft', 'ip6tables-nft'):
        docker.run([family, '-D', 'DOCKER-USER', '-p', 'tcp',
                    '--dport', '49151', '-j', 'RETURN'], check=False)
        docker.run([family, '-t', 'nat', '-F', 'L4S_VM_INGRESS_VPN'], check=False)
        docker.run([family, '-t', 'nat', '-X', 'L4S_VM_INGRESS_VPN'], check=False)


def docker_exec(socket_path, env, container, code):
    docker.docker_cmd(socket_path, 'exec', container, 'python3', '-c', code, env=env, timeout=5)


def expect_tcp_denied(namespace, source, destination, port, label):
    result = peer_tcp(namespace, source, destination, port, label.encode())
    if result.returncode == 0 and result.stdout.strip().startswith('tcp:'):
        raise AssertionError(f'{label} unexpectedly reached the published service')


def test_case(args):
    docker.assert_guest_guard()
    suite = docker.root_owned_install(args.suite_root)
    for tool in ('iptables-nft', 'ip6tables-nft', 'nft', 'docker', 'dockerd'):
        if shutil.which(tool) is None:
            raise RuntimeError(f'Required ingress integration tool is unavailable: {tool}')
    if docker.run(['iptables-nft', '-t', 'nat', '-S'], check=False).returncode:
        raise RuntimeError('iptables-nft NAT support is unavailable in the disposable guest')
    if docker.run(['ip6tables-nft', '-t', 'nat', '-S'], check=False).returncode:
        raise RuntimeError('ip6tables-nft NAT support is unavailable in the disposable guest')

    old_forward = docker.run(['sysctl', '-n', 'net.ipv4.ip_forward']).stdout.strip()
    old_v6_all = docker.run(['sysctl', '-n', 'net.ipv6.conf.all.forwarding']).stdout.strip()
    old_v6_default = docker.run(['sysctl', '-n', 'net.ipv6.conf.default.forwarding']).stdout.strip()
    namespace = f'l4s-ingress-{uuid.uuid4().hex[:7]}'
    container_name = f'l4s-ingress-{uuid.uuid4().hex[:8]}'
    sibling_name = f'l4s-ingress-peer-{uuid.uuid4().hex[:8]}'
    image = f'l4s-ingress:{uuid.uuid4().hex[:12]}'
    workdir = Path(tempfile.mkdtemp(prefix='l4s-vm-ingress-', dir='/run'))
    state = workdir / 'state'
    state.mkdir(mode=0o700)
    access_path = workdir / 'access.json'
    peer_process = live_peer = daemon_process = daemon_log = None
    daemon_env = os.environ.copy()
    socket_path = workdir / 'docker.sock'
    namespace_created = interface_created = False
    suite_applied = foreign_created = iptables_fixtures_created = False
    work = argparse.Namespace(docker_backend='iptables', iptables_frontend='nft')
    try:
        for key, value in (
            ('net.ipv4.ip_forward', '1'), ('net.ipv6.conf.all.forwarding', '1'),
            ('net.ipv6.conf.default.forwarding', '1'),
        ):
            docker.assert_guest_guard()
            docker.run(['sysctl', '-q', '-w', f'{key}={value}'])

        interface_created = True
        docker.create_client_namespace(namespace)
        namespace_created = True
        add_client_aliases(namespace)
        daemon_process, daemon_log, socket_path, daemon_env = docker.start_docker_daemon(work, workdir)
        info = docker.docker_cmd(socket_path, 'info', env=daemon_env).stdout.lower()
        if 'swarm: active' in info:
            raise RuntimeError('Docker iptables-nft ingress test cannot run while the private daemon is in Swarm mode')
        docker.assert_guest_guard()
        docker.build_local_python_image(image, workdir, socket_path, daemon_env)
        peer_process = create_forward_peer(namespace)
        docker.assert_guest_guard()
        docker.nft_foreign(True)
        foreign_created = True
        foreign_snapshot = docker.nft_foreign_snapshot()
        docker.assert_guest_guard()

        docker.docker_cmd(
            socket_path, 'run', '-d', '--name', container_name,
            '--publish', f'{HOST4}:{PUBLIC}:{PRIVATE}/tcp',
            '--publish', f'{HOST4}:{PUBLIC}:{PRIVATE}/udp',
            '--publish', f'{HOST4}:{UNGRANTED_PUBLIC}:{PRIVATE}/tcp',
            '--publish', f'{HOST4}:{LIVE_PUBLIC}:{LIVE_PRIVATE}/tcp',
            '--publish', f'[{HOST6}]:{PUBLIC}:{PRIVATE}/tcp',
            '--publish', f'[{HOST6}]:{PUBLIC}:{PRIVATE}/udp',
            '--publish', f'[{HOST6}]:{UNGRANTED_PUBLIC}:{PRIVATE}/tcp',
            '--publish', f'[{HOST6}]:{LIVE_PUBLIC}:{LIVE_PRIVATE}/tcp',
            '--entrypoint', 'python3', image, '/opt/server.py', env=daemon_env,
        )
        start_live_service(socket_path, daemon_env, container_name)
        inspect = json.loads(docker.docker_cmd(socket_path, 'inspect', container_name, env=daemon_env).stdout)[0]
        networks = inspect['NetworkSettings']['Networks']
        network = networks.get('bridge') or next(iter(networks.values()))
        container_ip = network['IPAddress']
        container_ip6 = network['GlobalIPv6Address'].split('%', 1)[0]
        require(container_ip, 'Docker did not assign the ingress container an IPv4 address')
        require(container_ip6, 'Docker did not assign the ingress container an IPv6 address')
        bridge = 'docker0'
        # Send direct-to-container probes through the guest router so they
        # reach the same forward hook as the published DNAT path.
        docker.assert_guest_guard()
        docker.run(['ip', 'netns', 'exec', namespace, 'ip', 'route', 'add',
                    container_ip + '/32', 'via', HOST4])
        docker.run(['ip', 'netns', 'exec', namespace, 'ip', '-6', 'route', 'add',
                    container_ip6 + '/128', 'via', HOST6])

        docker.docker_cmd(
            socket_path, 'run', '-d', '--name', sibling_name, '--network', 'bridge',
            '--entrypoint', 'python3', image, '/opt/server.py', env=daemon_env,
        )
        sibling_inspect = json.loads(docker.docker_cmd(socket_path, 'inspect', sibling_name, env=daemon_env).stdout)[0]
        sibling_net = sibling_inspect['NetworkSettings']['Networks'].get('bridge')
        sibling_ip = sibling_net['IPAddress']
        require(sibling_ip, 'Docker did not assign the same-bridge peer an IPv4 address')

        docker.assert_guest_guard()
        install_foreign_iptables_fixtures()
        iptables_fixtures_created = True

        initial = {'host': [], 'forward': [], 'containers': [
            *add_grant(PEER4, PEER6, container_ip, container_ip6, bridge, PUBLIC, PRIVATE),
            *add_grant(PEER4, PEER6, container_ip, container_ip6, bridge, LIVE_PUBLIC, LIVE_PRIVATE),
        ]}
        docker.write_json(access_path, initial)
        before = iptables_snapshots()
        for family, nat in ((4, before['nat4']), (6, before['nat6'])):
            destination = container_ip if family == 4 else container_ip6
            expected = (
                (f'--dport {PUBLIC}', PRIVATE, '-p tcp'),
                (f'--dport {PUBLIC}', PRIVATE, '-p udp'),
                (f'--dport {UNGRANTED_PUBLIC}', PRIVATE, '-p tcp'),
                (f'--dport {LIVE_PUBLIC}', LIVE_PRIVATE, '-p tcp'),
            )
            lines = nat.splitlines()
            for port_match, target_port, protocol in expected:
                targets = (f'--to-destination {destination}:{target_port}',
                           f'--to-destination [{destination}]:{target_port}')
                require(any(port_match in line and any(target in line for target in targets)
                            and protocol in line for line in lines),
                        f'Docker iptables-nft did not install IPv{family} {protocol} DNAT {port_match} to port {target_port}')
        options = [
            '--only', 'http_https_protect', '--set', 'HOST_SERVICES=false',
            '--set', 'CONTAINER_POLICY=ingress', '--set', 'ROUTED_POLICY=unmanaged',
            '--set', 'DOCKER_BACKEND=iptables', '--set', f'ACCESS_POLICY={access_path}',
            '--set', f'HTTP_HTTPS_PORTS={PRIVATE},{LIVE_PRIVATE}', '--set', 'FAMILY_POLICY=dual',
        ]
        docker.assert_guest_guard()
        docker.suite_command(suite, state, 'nftables', 'apply', 'nft', options)
        suite_applied = True
        require(docker.nft_foreign_snapshot() == foreign_snapshot,
                'Suite changed the unrelated foreign nftables table on first apply')

        for source, host in ((PEER4, HOST4), (PEER6, HOST6)):
            response = peer_tcp(namespace, source, host, PUBLIC, b'published')
            require(response.returncode == 0 and response.stdout.strip() == 'tcp:published',
                    f'Authorized IPv{6 if ":" in source else 4} published TCP and return failed: {response.stderr.strip()}')
            expect_tcp_denied(namespace, OTHER6 if ':' in source else OTHER4, host, PUBLIC,
                              'unauthorized source')
            expect_tcp_denied(namespace, source, host, UNGRANTED_PUBLIC, 'ungranted second publication')
            udp = peer_udp(namespace, source, host, PUBLIC)
            require(udp.returncode != 0, f'IPv{6 if ":" in source else 4} UDP inherited the TCP ingress grant')
            direct = peer_tcp(namespace, source, container_ip6 if ':' in source else container_ip,
                              PRIVATE, b'direct-ip')
            require(direct.returncode != 0, 'Direct container-IP ingress bypassed the published-port grant')

        # Docker's bridge forwarding remains delegated and permits same-bridge traffic.
        egress = (
            'import socket; s=socket.create_connection(("198.18.0.2",' + str(EGRESS) + '),timeout=2); '
            'assert s.recv(10)==b"ready"; s.sendall(b"delegated"); assert s.recv(100)==b"ack:delegated"; s.close()'
        )
        docker_exec(socket_path, daemon_env, container_name, egress)
        local = (
            f'import socket; s=socket.create_connection(({sibling_ip!r},{PRIVATE}),timeout=2); '
            's.sendall(b"bridge"); assert s.recv(100)==b"tcp:bridge"; s.close()'
        )
        docker_exec(socket_path, daemon_env, container_name, local)

        # An already established ORIGINAL flow loses access when its source is removed.
        live_peer = create_live_peer(namespace, PEER4)
        access2 = {'host': [], 'forward': [], 'containers': [
            *add_grant(OTHER4, OTHER6, container_ip, container_ip6, bridge, PUBLIC, PRIVATE),
            *add_grant(OTHER4, OTHER6, container_ip, container_ip6, bridge, LIVE_PUBLIC, LIVE_PRIVATE),
        ]}
        docker.write_json(access_path, access2)
        docker.suite_command(suite, state, 'nftables', 'apply', 'nft', options)
        old_flow = live_peer_request(live_peer, 'revoked')
        require(old_flow == 'TIMEOUT' or old_flow.startswith('CLOSED:'),
                f'Previously authorized original established flow survived ACL revocation: {old_flow}')
        new_source = peer_tcp(namespace, OTHER4, HOST4, PUBLIC, b'new-source')
        require(new_source.returncode == 0 and new_source.stdout.strip() == 'tcp:new-source',
                'Updated authorized source could not reach the published TCP service')
        old_source = peer_tcp(namespace, PEER4, HOST4, PUBLIC, b'old-source')
        require(old_source.returncode != 0, 'Revoked source still reached the published service')

        # Reapplying the unchanged ACL must not duplicate hooks and cannot touch
        # Docker NAT/DOCKER-USER or the foreign table.
        snapshot_after_apply = iptables_snapshots()
        require(snapshot_after_apply == before,
                'Suite ingress application changed Docker iptables-nft NAT or DOCKER-USER rules')
        nft_before_repeat = docker.run(['nft', '-s', 'list', 'table', 'inet', 'firewall_main']).stdout
        foreign_snapshot = docker.nft_foreign_snapshot()
        docker.suite_command(suite, state, 'nftables', 'apply', 'nft', options)
        require(docker.run(['nft', '-s', 'list', 'table', 'inet', 'firewall_main']).stdout == nft_before_repeat,
                'Repeated ingress application was not idempotent')
        require(iptables_snapshots() == snapshot_after_apply,
                'Repeated ingress application changed Docker NAT or DOCKER-USER')
        require(docker.nft_foreign_snapshot() == foreign_snapshot,
                'Suite changed the unrelated foreign nftables table')

        print(json.dumps({
            'status': 'PASS', 'suite_backend': 'nftables',
            'container_policy': 'ingress', 'routed_policy': 'unmanaged',
            'docker_backend': 'iptables', 'iptables_frontend': 'nft',
            'docker_version': docker.docker_version(socket_path),
            'checks': [
                'IPv4/IPv6 published TCP DNAT and reply', 'unauthorized source and ungranted publication denied',
                'same-port UDP denied', 'direct container-IP ingress denied',
                'revoked established ORIGINAL flow denied', 'new ACL source accepted',
                'Docker-delegated egress and reply', 'same-bridge peer traffic',
                'Docker NAT/DOCKER-USER and foreign nftables preserved', 'idempotent apply',
            ],
        }, sort_keys=True))
    finally:
        docker.assert_vm_marker()
        if live_peer is not None:
            try:
                live_peer.stdin.write('QUIT\n')
                live_peer.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            live_peer.terminate()
            live_peer.wait(timeout=3)
        if suite_applied:
            docker.suite_command(suite, state, 'nftables', 'disable', 'nft', check=False)
        if iptables_fixtures_created:
            remove_foreign_iptables_fixtures()
        if daemon_process is not None:
            if daemon_process.poll() is None:
                for name in (sibling_name, container_name):
                    docker.docker_cmd(socket_path, 'rm', '-f', name, check=False, timeout=30, env=daemon_env)
                docker.docker_cmd(socket_path, 'image', 'rm', '-f', image, check=False, timeout=30, env=daemon_env)
            docker.stop_docker_daemon(daemon_process, daemon_log)
        if peer_process is not None:
            peer_process.terminate()
            peer_process.wait(timeout=3)
        if interface_created or docker.run(['ip', 'link', 'show', 'l4s-vm0'], check=False).returncode == 0:
            docker.run(['ip', 'link', 'del', 'l4s-vm0'], check=False)
        if namespace_created or docker.run(['ip', 'netns', 'list'], check=False).stdout.find(namespace) >= 0:
            docker.run(['ip', 'netns', 'del', namespace], check=False)
        if foreign_created:
            docker.nft_foreign(False)
        for key, value in (
            ('net.ipv4.ip_forward', old_forward), ('net.ipv6.conf.all.forwarding', old_v6_all),
            ('net.ipv6.conf.default.forwarding', old_v6_default),
        ):
            docker.run(['sysctl', '-q', '-w', f'{key}={value}'], check=False)
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-root', type=Path, default=docker.DEFAULT_SUITE)
    args = parser.parse_args()
    docker.assert_vm_marker()
    if os.environ.get('DOCKER_HOST'):
        raise RuntimeError('DOCKER_HOST must be unset; remote Docker targets are forbidden')
    test_case(args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
