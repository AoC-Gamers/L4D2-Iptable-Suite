#!/usr/bin/env python3
"""Exercise explicit S2S forwarding through real Docker iptables-nft."""
import argparse
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import uuid


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('l4s_docker_harness', HERE / 'docker.py')
docker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(docker)

LAN_HOST = docker.HOST_TEST_IP
LAN_PEER = docker.CLIENT_TEST_IP
LAN_CIDR = '198.18.0.0/24'
OUTSIDE_PEER = '198.19.0.2'
OUTSIDE_CIDR = '198.19.0.0/24'
VPN_HOST = '10.8.0.1'
VPN_PEER = '10.8.0.2'
VPN_CIDR = '10.8.0.0/24'
LAN_TCP_PORT = 18444
VPN_TCP_PORT = 18445
FOREIGN_COMMENT = 'L4S_VM_S2S_FOREIGN_DROP'
OWN_PREFIX = 'l4d2-suite:s2s:'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def create_vpn_namespace(name):
    docker.assert_guest_guard()
    docker.run(['ip', 'netns', 'add', name])
    docker.run(['ip', 'link', 'add', 'tun-test', 'type', 'veth', 'peer', 'name', 'l4s-vpn0'])
    docker.run(['ip', 'link', 'set', 'l4s-vpn0', 'netns', name])
    docker.run(['ip', 'addr', 'add', VPN_HOST + '/24', 'dev', 'tun-test'])
    docker.run(['ip', 'link', 'set', 'tun-test', 'up'])
    docker.run(['ip', 'netns', 'exec', name, 'ip', 'link', 'set', 'lo', 'up'])
    docker.run(['ip', 'netns', 'exec', name, 'ip', 'addr', 'add', VPN_PEER + '/24', 'dev', 'l4s-vpn0'])
    docker.run(['ip', 'netns', 'exec', name, 'ip', 'link', 'set', 'l4s-vpn0', 'up'])
    docker.run(['ip', 'netns', 'exec', name, 'ip', 'route', 'replace', 'default', 'via', VPN_HOST, 'dev', 'l4s-vpn0'])


def start_lan_server(namespace):
    code = (
        'import socket,threading,time\n'
        'def serve(addr):\n'
        f' s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind((addr,{LAN_TCP_PORT})); s.listen(8)\n'
        ' while True:\n'
        '  c,peer=s.accept()\n'
        '  try:\n'
        '   data=c.recv(100); c.sendall((peer[0]+"|"+data.decode()).encode())\n'
        '  finally: c.close()\n'
        f'threads=[threading.Thread(target=serve,args=(addr,),daemon=True) for addr in ({LAN_PEER!r},{OUTSIDE_PEER!r})]\n'
        'for t in threads: t.start()\n'
        'print("ready",flush=True); time.sleep(3600)\n'
    )
    process = subprocess.Popen(
        ['ip', 'netns', 'exec', namespace, 'python3', '-u', '-c', code],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if process.stdout.readline().strip() != 'ready':
        raise RuntimeError('LAN TCP test server failed to start')
    return process


def start_vpn_listener(namespace):
    code = (
        'import socket,time; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); '
        f's.bind(({VPN_PEER!r},{VPN_TCP_PORT})); s.listen(4); print("ready",flush=True); time.sleep(3600)'
    )
    process = subprocess.Popen(
        ['ip', 'netns', 'exec', namespace, 'python3', '-u', '-c', code],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if process.stdout.readline().strip() != 'ready':
        raise RuntimeError('VPN TCP test listener failed to start')
    return process


def tcp_probe(namespace, source, destination, port, payload='s2s'):
    code = (
        'import socket\ns=socket.socket(); s.settimeout(1.2); '
        f's.bind(({source!r},0))\n'
        'try:\n'
        f' s.connect(({destination!r},{port})); print("CONNECTED",flush=True)\n'
        'except OSError as e: print("CONNECT_BLOCKED:"+type(e).__name__)\n'
        'else:\n'
        f' try: s.sendall({payload.encode()!r}); print("REPLY:"+s.recv(100).decode())\n'
        ' except OSError as e: print("CONNECTED_READ_ERROR:"+type(e).__name__)\n'
        'finally: s.close()\n'
    )
    output = docker.run(['ip', 'netns', 'exec', namespace, 'python3', '-c', code], timeout=4).stdout.strip()
    return output.splitlines()[-1] if output else ''


def expect_blocked(namespace, source, destination, port, label):
    result = tcp_probe(namespace, source, destination, port, label)
    require(result.startswith('CONNECT_BLOCKED:'),
            f'{label} completed TCP connect or failed only after connect: {result!r}')


def ping_peer(namespace, destination):
    code = r'''import socket,struct
def checksum(data):
 total=0
 for i in range(0,len(data)-1,2): total+=(data[i]<<8)+data[i+1]
 if len(data)%2: total+=data[-1]<<8
 total=(total>>16)+(total&0xffff); total+=(total>>16)
 return (~total)&0xffff
ident=0x4c53; payload=b'l4d2-s2s-icmp'
head=struct.pack('!BBHHH',8,0,0,ident,1)
value=checksum(head+payload); packet=struct.pack('!BBHHH',8,0,value,ident,1)+payload
s=socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_ICMP); s.settimeout(2)
s.sendto(packet,(TARGET,0)); data,peer=s.recvfrom(2048); offset=(data[0]&15)*4
kind,code=data[offset],data[offset+1]
print(peer[0],kind,code)
'''.replace('TARGET', repr(destination))
    result = docker.run(['ip', 'netns', 'exec', namespace, 'python3', '-c', code], timeout=4)
    require(result.returncode == 0 and result.stdout.strip() == f'{destination} 0 0',
            f'Routed ICMP to LAN failed: {result.stderr.strip()} {result.stdout.strip()}')


def create_foreign_drop():
    docker.assert_guest_guard()
    docker.run([
        'nft', 'add', 'rule', 'ip', 'filter', 'DOCKER-USER',
        'iifname', '"tun-test"', 'oifname', '"l4s-vm0"',
        'ip', 'saddr', VPN_CIDR, 'ip', 'daddr', LAN_CIDR,
        'counter', 'drop', 'comment', f'"{FOREIGN_COMMENT}"',
    ])


def nft_chain(family, table, chain):
    # Handles let the mixed native-nft/iptables-nft chain be compared without
    # assuming the iptables frontend can render native rules or their comments.
    return docker.run(['nft', '-a', '-s', 'list', 'chain', family, table, chain]).stdout


def chain_rules(text):
    return [line.strip() for line in text.splitlines()
            if not line.lstrip().startswith(('table ', 'chain '))
            and re.search(r'# handle [0-9]+\s*$', line)]


def firewall_snapshot():
    return {
        'user': nft_chain('ip', 'filter', 'DOCKER-USER'),
        'forward': nft_chain('ip', 'filter', 'FORWARD'),
        'nat': docker.run(['iptables-nft', '-t', 'nat', '-S']).stdout,
    }


def shared_lines():
    return [line for line in chain_rules(nft_chain('ip', 'filter', 'DOCKER-USER'))
            if OWN_PREFIX in line]


def foreign_rule_lines():
    return [line for line in chain_rules(nft_chain('ip', 'filter', 'DOCKER-USER'))
            if FOREIGN_COMMENT in line]


def assert_shared_precedes_foreign(foreign_handle_line):
    lines = chain_rules(nft_chain('ip', 'filter', 'DOCKER-USER'))
    own = [i for i, line in enumerate(lines) if OWN_PREFIX in line]
    foreign = [i for i, line in enumerate(lines) if line == foreign_handle_line]
    require(len(own) == 2, f'Expected exactly two owned S2S rules, got {len(own)}: {lines!r}')
    require(len(foreign) == 1, f'Original foreign DOCKER-USER rule handle moved/changed: {lines!r}')
    require(max(own) < foreign[0], 'Owned S2S grants were not inserted before Docker-USER drop')


def assert_nat_table(present):
    result = docker.run(['nft', 'list', 'table', 'ip', 'firewall_main_nat4'], check=False)
    require((result.returncode == 0) == present,
            f'Suite S2S NAT table presence expected={present}, got rc={result.returncode}')
    if present:
        require('masquerade' in result.stdout, 'S2S NAT table has no masquerade rule')


def nat_masquerade_count():
    result = docker.run(['nft', 'list', 'table', 'ip', 'firewall_main_nat4'])
    return sum('masquerade' in line for line in result.stdout.splitlines())


def timed_shared_nat_rollback(suite, state, timeout=15):
    """Expire an unconfirmed wider S2S candidate after its applicator exits."""
    sys.path.insert(0, str(suite))
    from core.store import Store

    store = Store(state)
    baseline = store.get('current')
    require(baseline and len(baseline.get('shared_rules', [])) == 2,
            'Timed rollback needs the confirmed two-rule S2S baseline')
    baseline_nat = nat_masquerade_count()
    require(baseline_nat == 1, f'Expected one baseline S2S masquerade rule, got {baseline_nat}')

    args = [
        str(suite / 'ipp.sh'), '--state-dir', str(state), '--backend', 'nftables', 'apply',
        '--timeout', str(timeout), '--watchdog', 'process', '--only', 'openvpn_sitetosite',
        '--set', 'HOST_SERVICES=false', '--set', 'ROUTED_POLICY=unmanaged',
        '--set', 'CONTAINER_POLICY=off', '--set', 'IPTABLES_FRONTEND=nft',
        '--set', 'OVPNS2S_INTERFACE=tun-test', '--set', 'OVPNS2S_LOCAL_INTERFACE=l4s-vm0',
        '--set', f'OVPNS2S_LOCAL_SUBNETS={LAN_CIDR}',
        '--set', f'OVPNS2S_REMOTE_SUBNETS={VPN_CIDR},10.9.0.0/24',
        '--set', 'OVPNS2S_ENABLE_NAT=true', '--set', 'OVPNS2S_ALLOW_LAN=true',
    ]
    docker.assert_guest_guard()
    applied = docker.run(args, timeout=40)
    require('Applied with timed rollback.' in applied.stdout,
            f'Timed candidate was not left unconfirmed: {applied.stdout!r}')
    pending = store.get('pending')
    require(pending and pending['candidate'].get('shared_rules')
            and len(pending['candidate']['shared_rules']) == 4,
            'Unconfirmed candidate journal does not contain all four shared S2S grants')
    token = pending['token']
    require(len(shared_lines()) == 4,
            f'Unconfirmed candidate did not install four shared rules: {shared_lines()!r}')
    require(nat_masquerade_count() == 2,
            'Unconfirmed candidate did not install its additional S2S NAT rule')
    require(len(foreign_rule_lines()) == 1,
            'Unconfirmed candidate changed the foreign DOCKER-USER rule')

    deadline = time.monotonic() + timeout + 35
    while time.monotonic() < deadline:
        pending = store.get('pending')
        rollback = store.get('last-rollback')
        if pending is None and rollback and rollback.get('token') == token:
            break
        time.sleep(0.25)
    else:
        raise AssertionError(f'Process watchdog did not roll back expired S2S candidate {token}')

    require(store.get('current') == baseline,
            'Watchdog rollback did not restore the exact prior confirmed S2S policy')
    require(len(shared_lines()) == 2,
            f'Watchdog rollback did not remove only candidate shared rules: {shared_lines()!r}')
    require(nat_masquerade_count() == baseline_nat,
            'Watchdog rollback did not restore the baseline S2S NAT rule set')
    require(len(foreign_rule_lines()) == 1,
            'Watchdog rollback removed the foreign DOCKER-USER rule')
    return token


def test_case(args):
    docker.assert_guest_guard()
    suite = docker.root_owned_install(args.suite_root)
    for tool in ('ip', 'iptables-nft', 'iptables-nft-save', 'nft', 'docker', 'dockerd'):
        if shutil.which(tool) is None:
            raise RuntimeError(f'Required S2S routing integration tool is unavailable: {tool}')
    if os.environ.get('DOCKER_HOST'):
        raise RuntimeError('DOCKER_HOST must be unset; remote Docker targets are forbidden')

    old_forward = docker.run(['sysctl', '-n', 'net.ipv4.ip_forward']).stdout.strip()
    lan_ns = 'l4s-s2s-lan-' + uuid.uuid4().hex[:6]
    vpn_ns = 'l4s-s2s-vpn-' + uuid.uuid4().hex[:6]
    workdir = Path(tempfile.mkdtemp(prefix='l4s-vm-s2s-', dir='/run'))
    state = workdir / 'state'
    state.mkdir(mode=0o700)
    daemon_args = argparse.Namespace(docker_backend='iptables', iptables_frontend='nft')
    daemon_process = daemon_log = None
    socket_path = workdir / 'docker.sock'
    daemon_env = os.environ.copy()
    lan_server = vpn_listener = None
    lan_created = vpn_created = False
    suite_applied = foreign_created = False
    options = [
        '--only', 'openvpn_sitetosite', '--set', 'HOST_SERVICES=false',
        '--set', 'ROUTED_POLICY=unmanaged', '--set', 'CONTAINER_POLICY=off',
        '--set', 'OVPNS2S_INTERFACE=tun-test', '--set', 'OVPNS2S_LOCAL_INTERFACE=l4s-vm0',
        '--set', f'OVPNS2S_LOCAL_SUBNETS={LAN_CIDR}', '--set', f'OVPNS2S_REMOTE_SUBNETS={VPN_CIDR}',
        '--set', 'OVPNS2S_ENABLE_NAT=true', '--set', 'OVPNS2S_ALLOW_LAN=true',
    ]
    try:
        docker.assert_guest_guard()
        docker.run(['sysctl', '-q', '-w', 'net.ipv4.ip_forward=1'])
        docker.create_client_namespace(lan_ns)
        lan_created = True
        docker.run(['ip', 'netns', 'exec', lan_ns, 'ip', 'addr', 'add', OUTSIDE_PEER + '/24', 'dev', 'l4s-client0'])
        docker.run(['ip', 'netns', 'exec', lan_ns, 'ip', 'route', 'add', VPN_CIDR, 'via', LAN_HOST, 'dev', 'l4s-client0'])
        docker.run(['ip', 'route', 'add', OUTSIDE_CIDR, 'via', LAN_PEER, 'dev', 'l4s-vm0'])
        create_vpn_namespace(vpn_ns)
        vpn_created = True
        docker.assert_guest_guard()
        daemon_process, daemon_log, socket_path, daemon_env = docker.start_docker_daemon(daemon_args, workdir)
        require('swarm: active' not in docker.docker_cmd(socket_path, 'info', env=daemon_env).stdout.lower(),
                'Private Docker daemon is unexpectedly in Swarm mode')
        docker.assert_guest_guard()
        docker.run(['iptables-nft', '-P', 'FORWARD', 'DROP'])
        require(docker.run(['iptables-nft', '-S', 'FORWARD']).stdout.startswith('-P FORWARD DROP'),
                'Docker did not provide the expected FORWARD policy DROP')
        forward_rules = [line for line in docker.run(['iptables-nft', '-S', 'FORWARD']).stdout.splitlines()
                         if line.startswith('-A FORWARD ')]
        user_links = [i for i, line in enumerate(forward_rules) if line == '-A FORWARD -j DOCKER-USER']
        require(len(user_links) == 1 and user_links[0] == 0,
                f'Docker FORWARD must jump to DOCKER-USER first: {forward_rules!r}')
        require(docker.run(['iptables-nft', '-S', 'DOCKER-USER'], check=False).returncode == 0,
                'Docker iptables-nft did not create DOCKER-USER without containers')
        lan_server = start_lan_server(lan_ns)
        vpn_listener = start_vpn_listener(vpn_ns)
        create_foreign_drop()
        foreign_created = True
        foreign_snapshot = firewall_snapshot()
        require(len(foreign_rule_lines()) == 1,
                f'Expected exactly one native nft foreign fixture: {foreign_rule_lines()!r}')
        foreign_nft_lines = chain_rules(foreign_snapshot['user'])
        require(len(foreign_nft_lines) == 1,
                f'Expected the foreign fixture to be the sole initial DOCKER-USER rule: {foreign_nft_lines!r}')
        # iptables-nft's comment match is not printed as a native nft comment.
        # Record its stable nft handle before insertion of suite-owned rules.
        foreign_rule = foreign_nft_lines[0]
        assert_nat_table(False)

        docker.assert_guest_guard()
        docker.suite_command(suite, state, 'nftables', 'apply', 'nft', options)
        suite_applied = True
        assert_shared_precedes_foreign(foreign_rule)
        require(len(shared_lines()) == 2, 'iptables-nft-save does not show exactly two owned S2S comments')
        assert_nat_table(True)
        applied_snapshot = firewall_snapshot()
        require(applied_snapshot['forward'] == foreign_snapshot['forward'],
                'Applying suite policy changed Docker FORWARD chain/policy')
        require(applied_snapshot['nat'] == foreign_snapshot['nat'],
                'Applying suite policy changed Docker iptables NAT')
        require(foreign_rule in chain_rules(applied_snapshot['user']),
                'Applying suite policy changed foreign DOCKER-USER fixture')

        response = tcp_probe(vpn_ns, VPN_PEER, LAN_PEER, LAN_TCP_PORT, 'vpn-to-lan')
        require(response == 'REPLY:198.18.0.1|vpn-to-lan',
                f'VPN->LAN TCP/reply or masquerade source failed: {response!r}')
        ping_peer(vpn_ns, LAN_PEER)
        expect_blocked(lan_ns, LAN_PEER, VPN_PEER, VPN_TCP_PORT, 'LAN-initiated-new')
        expect_blocked(vpn_ns, VPN_PEER, OUTSIDE_PEER, LAN_TCP_PORT, 'destination-outside-local-CIDR')

        docker.assert_guest_guard()
        docker.suite_command(suite, state, 'nftables', 'apply', 'nft', options)
        assert_shared_precedes_foreign(foreign_rule)
        require(len(shared_lines()) == 2, 'Repeated apply duplicated owned S2S DOCKER-USER rules')
        require(firewall_snapshot()['forward'] == foreign_snapshot['forward'],
                'Repeated apply changed Docker FORWARD chain/policy')
        require(firewall_snapshot()['nat'] == foreign_snapshot['nat'],
                'Repeated apply changed Docker iptables NAT')

        rollback_token = timed_shared_nat_rollback(suite, state)
        rolled_back_snapshot = firewall_snapshot()
        require(rolled_back_snapshot['forward'] == foreign_snapshot['forward'],
                'Watchdog rollback changed Docker FORWARD chain/policy')
        require(rolled_back_snapshot['nat'] == foreign_snapshot['nat'],
                'Watchdog rollback changed Docker iptables NAT')
        require(tcp_probe(vpn_ns, VPN_PEER, LAN_PEER, LAN_TCP_PORT, 'after-watchdog')
                == 'REPLY:198.18.0.1|after-watchdog',
                f'S2S traffic did not recover after watchdog rollback {rollback_token}')

        docker.assert_guest_guard()
        docker.suite_command(suite, state, 'nftables', 'disable', 'nft')
        suite_applied = False
        require(not shared_lines(), 'Disable left owned S2S DOCKER-USER rules behind')
        assert_nat_table(False)
        disabled_snapshot = firewall_snapshot()
        require(disabled_snapshot['forward'] == foreign_snapshot['forward'],
                'Disable changed Docker FORWARD chain/policy')
        require(disabled_snapshot['nat'] == foreign_snapshot['nat'], 'Disable changed Docker iptables NAT')
        require(len(foreign_rule_lines()) == 1
                and foreign_rule in chain_rules(disabled_snapshot['user']),
                'Disable removed or changed the foreign DOCKER-USER fixture')
        expect_blocked(vpn_ns, VPN_PEER, LAN_PEER, LAN_TCP_PORT, 'S2S-after-disable')

        print(json.dumps({
            'status': 'PASS', 'suite_backend': 'nftables', 'docker_backend': 'iptables',
            'iptables_frontend': 'nft', 'docker_version': docker.docker_version(socket_path),
            'checks': [
                'real Docker DOCKER-USER with FORWARD policy DROP',
                'VPN-to-LAN TCP, reply and source masquerade', 'VPN-to-LAN ICMP echo/reply',
                'LAN-initiated new VPN connection denied', 'destination outside local CIDR denied',
                'exactly two idempotent owned S2S rules before foreign drop',
                'expired timed S2S candidate rolled back shared rules and NAT after its applicator exited',
                'disable removed only suite S2S permissions and NAT',
                'foreign DOCKER-USER drop preserved and blocks after disable',
            ],
        }, sort_keys=True))
    finally:
        docker.assert_vm_marker()
        if suite_applied:
            docker.suite_command(suite, state, 'nftables', 'disable', 'nft', check=False)
        if foreign_created:
            for line in foreign_rule_lines():
                handle = line.rsplit('# handle ', 1)[-1]
                if handle.isdigit():
                    docker.run(['nft', 'delete', 'rule', 'ip', 'filter', 'DOCKER-USER', 'handle', handle],
                               check=False)
        if lan_server is not None:
            lan_server.terminate()
            lan_server.wait(timeout=3)
        if vpn_listener is not None:
            vpn_listener.terminate()
            vpn_listener.wait(timeout=3)
        if daemon_process is not None:
            docker.stop_docker_daemon(daemon_process, daemon_log)
        docker.run(['ip', 'link', 'del', 'tun-test'], check=False)
        docker.run(['ip', 'link', 'del', 'l4s-vm0'], check=False)
        if vpn_created or vpn_ns in docker.run(['ip', 'netns', 'list']).stdout:
            docker.run(['ip', 'netns', 'del', vpn_ns], check=False)
        if lan_created or lan_ns in docker.run(['ip', 'netns', 'list']).stdout:
            docker.run(['ip', 'netns', 'del', lan_ns], check=False)
        docker.run(['sysctl', '-q', '-w', f'net.ipv4.ip_forward={old_forward}'], check=False)
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-root', type=Path, default=docker.DEFAULT_SUITE)
    args = parser.parse_args()
    docker.assert_guest_guard()
    test_case(args)


if __name__ == '__main__':
    raise SystemExit(main())
