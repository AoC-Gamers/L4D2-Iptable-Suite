#!/usr/bin/python3
"""Real OpenVPN client/server routed through both compiled firewall backends.

Run only in the disposable QEMU VM with tests/vm/clients.sh. The harness
rechecks the VM marker, then creates a nested disposable network namespace so
the VM's own firewall and routes remain untouched.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
MARKER = Path('/run/l4d2-suite-vm.json')


def run(argv, *, check=True, **kwargs):
    return subprocess.run(argv, check=check, text=True, capture_output=True, **kwargs)


def guard():
    if os.geteuid() != 0:
        raise SystemExit('REFUSED: run as root inside the disposable QEMU VM')
    try:
        info = MARKER.stat()
        data = json.loads(MARKER.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f'REFUSED: invalid VM marker: {exc}') from exc
    if (info.st_uid, info.st_mode & 0o777) != (0, 0o600) or data != {'virtualization': 'qemu', 'disposable': True}:
        raise SystemExit('REFUSED: QEMU marker must be root-owned 0600 JSON declaring a disposable qemu guest')
    virt = run(['systemd-detect-virt', '--vm'], check=False)
    if virt.returncode or virt.stdout.strip() not in ('qemu', 'kvm'):
        raise SystemExit(f"REFUSED: expected QEMU/KVM guest, detected {virt.stdout.strip()!r}")


def isolated_main():
    guard()
    original_netns = os.readlink('/proc/self/ns/net')
    if os.environ.get('SUITE_VM_INNER') != '1':
        work = tempfile.mkdtemp(prefix='l4d2-vm-clients-')
        try:
            script = Path(__file__).resolve()
            child = [
                'unshare', '--net', '--mount', '--fork', 'bash', '-c',
                'set -euo pipefail; marker="$4"; mount --make-rprivate /; mount -t tmpfs -o mode=755 tmpfs /run; '
                'printf "%s\\n" "$marker" >/run/l4d2-suite-vm.json; chmod 600 /run/l4d2-suite-vm.json; '
                'ip link set lo up; export SUITE_VM_INNER=1 SUITE_VM_HOST_NETNS="$1" SUITE_HOST_NETNS="$1" '
                'SUITE_TEST_STATE="$2/state"; exec /usr/bin/python3 -I "$3"',
                '_', original_netns, work, str(script), MARKER.read_text(),
            ]
            completed = run(child, check=False)
            sys.stdout.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            return completed.returncode
        finally:
            shutil.rmtree(work, ignore_errors=True)

    if os.readlink('/proc/self/ns/net') == os.environ.get('SUITE_VM_HOST_NETNS'):
        raise SystemExit('REFUSED: nested network namespace was not created')
    missing = [x for x in ('openvpn', 'openssl', 'ip', 'nft', 'iptables', 'ip6tables', 'nsenter') if not shutil.which(x)]
    if missing:
        raise SystemExit('Missing guest dependencies: ' + ', '.join(missing))
    sys.path.insert(0, str(ROOT/'tests'))
    sys.path.insert(0, str(ROOT))
    import integration  # tests/integration.py supplies isolated veth peers and engine helpers
    return run_openvpn_flow(integration)


def make_certificates(work):
    pki = work / 'pki'
    ccd = work / 'ccd'
    pki.mkdir(mode=0o700)
    ccd.mkdir(mode=0o700)
    run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2',
         '-subj', '/CN=Suite VM Test CA', '-keyout', str(pki/'ca.key'), '-out', str(pki/'ca.crt')])
    for name, usage in (('server', 'serverAuth'), ('client', 'clientAuth')):
        run(['openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-subj', f'/CN=suite-{name}',
             '-keyout', str(pki/f'{name}.key'), '-out', str(pki/f'{name}.csr')])
        ext = pki / f'{name}.ext'
        ext.write_text(f'basicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage={usage}\n')
        ext.chmod(0o600)
        run(['openssl', 'x509', '-req', '-in', str(pki/f'{name}.csr'), '-CA', str(pki/'ca.crt'),
             '-CAkey', str(pki/'ca.key'), '-CAcreateserial', '-days', '2', '-extfile', str(ext),
             '-out', str(pki/f'{name}.crt')])
    return pki, ccd


def tcp_from_namespace(pid, source, destination, port):
    code = f'''import socket
s=socket.socket(socket.AF_INET6 if ':' in {source!r} else socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1.5); s.bind(({source!r},0))
try:
 s.connect(({destination!r},{port})); print(s.recv(100).decode())
except OSError: print('BLOCK')
finally: s.close()
'''
    result = subprocess.run(['nsenter', '-t', str(pid), '-n', 'python3', '-c', code],
                            text=True, capture_output=True, check=True)
    return result.stdout.strip()


def tcp_from_vpn(peer, source, destination, port):
    return tcp_from_namespace(peer.p.pid, source, destination, port)


def peer_run(peer, argv):
    return subprocess.run(['nsenter', '-t', str(peer.p.pid), '-n', *argv], text=True, capture_output=True, check=False)


def forward_drop_count(integration, fixture, backend):
    if backend == 'nftables':
        text = run(['nft', 'list', 'chain', 'inet', 'firewall_main', 'forward']).stdout
        counts = re.findall(r'counter packets (\d+) bytes \d+ drop\b', text)
        if not counts:
            raise AssertionError('Could not read nft forward drop counter')
        return int(counts[-1])
    current = fixture.store.get('current')
    hook = next(chain for table, parent, chain in current.get('hooks', []) if table == 'filter' and parent == 'FORWARD')
    text = integration.run(integration.engine.ipcmd(4, '-save'), '-c')
    counts = []
    for line in text.splitlines():
        match = re.match(r'\[(\d+):\d+\]\s+-A\s+' + re.escape(hook) + r'(?:\s|$)', line)
        if match and '-j DROP' in line:
            counts.append(int(match.group(1)))
    if not counts:
        raise AssertionError(f'Could not read iptables forward drop counter for {hook}')
    return counts[-1]


def wait_for_tunnel(peer, proc, log, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f'OpenVPN client exited {proc.returncode}: {log.read_text(errors="replace")[-4000:]}')
        result = peer_run(peer, ['ip', '-o', 'addr', 'show', 'dev', 'tun0'])
        if result.returncode == 0 and '10.8.0.2/24' in result.stdout:
            return
        time.sleep(.2)
    raise AssertionError(f'OpenVPN tunnel did not come up: {log.read_text(errors="replace")[-4000:]}')


def run_openvpn_flow(integration):
    state = Path(os.environ['SUITE_TEST_STATE'])
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    fixture = integration.KernelTests()
    integration.KernelTests.setUpClass()
    setup_done = False
    try:
        fixture.setUp()
        setup_done = True
        with tempfile.TemporaryDirectory(prefix='openvpn-pki-', dir=state) as d:
            work = Path(d)
            pki, ccd = make_certificates(work)
            (ccd/'suite-client').write_text(
                'ifconfig-push 10.8.0.2 255.255.255.0\n'
                'ifconfig-ipv6-push fd42:8::2/64 fd42:8::1\n'
                'iroute 10.88.0.0 255.255.255.0\n'
            )
            (ccd/'suite-client').chmod(0o600)
            server_conf = work/'server.conf'
            server_conf.write_text('\n'.join([
                'port 1194', 'proto udp4', 'dev tun0', 'topology subnet',
                'server 10.8.0.0 255.255.255.0', 'server-ipv6 fd42:8::/64',
                f'ca {pki}/ca.crt', f'cert {pki}/server.crt', f'key {pki}/server.key',
                'dh none', 'tls-server', 'verify-client-cert require', 'client-config-dir ' + str(ccd),
                'route 10.88.0.0 255.255.255.0',
                'push "route 10.30.0.0 255.255.255.0"', 'push "route-ipv6 fd00:30::/64"',
                'keepalive 5 30', 'persist-key', 'persist-tun', 'verb 3',
            ])+'\n')
            server_conf.chmod(0o600)
            client_conf = work/'client.conf'
            client_conf.write_text('\n'.join([
                'client', 'dev tun0', 'proto udp4', 'remote 10.20.0.1 1194', 'nobind',
                f'ca {pki}/ca.crt', f'cert {pki}/client.crt', f'key {pki}/client.key',
                'remote-cert-tls server', 'connect-retry 1 5', 'verb 3',
            ])+'\n')
            client_conf.chmod(0o600)
            server_log, client_log = work/'server.log', work/'client.log'
            with server_log.open('w') as sout, client_log.open('w') as cout:
                server = subprocess.Popen(['openvpn', '--config', str(server_conf)], stdout=sout, stderr=subprocess.STDOUT)
                client = None
                try:
                    time.sleep(.6)
                    if server.poll() is not None:
                        raise AssertionError(f'OpenVPN server failed: {server_log.read_text(errors="replace")}')
                    client = subprocess.Popen(['nsenter', '-t', str(fixture.peer.p.pid), '-n', 'openvpn', '--config', str(client_conf)], stdout=cout, stderr=subprocess.STDOUT)
                    wait_for_tunnel(fixture.peer, client, client_log)
                    v6 = peer_run(fixture.peer, ['ip', '-o', '-6', 'addr', 'show', 'dev', 'tun0'])
                    if 'fd42:8::2/64' not in v6.stdout:
                        raise AssertionError('OpenVPN client did not receive the configured IPv6 tunnel address: '+v6.stdout)
                    run(['ip', 'addr', 'add', '10.8.0.254/32', 'dev', 'tun0'])
                    access = make_access(state)
                    for backend in ('nftables', 'iptables'):
                        fixture.apply(backend, 'vpn-gateway', OVPNSRV_SUBNET='10.8.0.0/24',
                                      OVPNSRV_LAN_SUBNET='10.30.0.0/24', OVPNSRV_ENABLE_NAT='false',
                                      OVPNSRV_ROUTER_REAL_IP='10.30.0.2', OVPNSRV_ROUTER_ALIAS_IP='10.8.0.254',
                                      ACCESS_POLICY=str(access))
                        selfcheck = tcp_from_vpn(fixture.peer, '10.8.0.2', '10.30.0.2', 18443)
                        if selfcheck != '10.8.0.2':
                            raise AssertionError(f'{backend} IPv4 grant failed or source was NATed: {selfcheck!r}')
                        if tcp_from_vpn(fixture.peer, '10.8.0.2', '10.30.0.2', 18444) != 'BLOCK':
                            raise AssertionError(f'{backend} IPv4 grant leaked to an unapproved port')
                        alias = tcp_from_vpn(fixture.peer, '10.8.0.2', '10.8.0.254', 18443)
                        if alias != '10.8.0.2':
                            raise AssertionError(f'{backend} router alias DNAT failed or changed the return source: {alias!r}')
                        v6result = tcp_from_vpn(fixture.peer, 'fd42:8::2', 'fd00:30::2', 18443)
                        if v6result != 'fd42:8::2':
                            raise AssertionError(f'{backend} IPv6 grant failed or source was NATed: {v6result!r}')
                        fixture.disable()
                        print(f'PASS: {backend} OpenVPN IPv4/IPv6 scoped grants, denied port and router alias DNAT')
                    run_s2s_alias_flow(integration, fixture, state)
                finally:
                    if client is not None:
                        client.terminate()
                        try: client.wait(timeout=3)
                        except subprocess.TimeoutExpired: client.kill(); client.wait()
                    server.terminate()
                    try: server.wait(timeout=3)
                    except subprocess.TimeoutExpired: server.kill(); server.wait()
                    fixture.disable()
        return 0
    finally:
        if setup_done:
            fixture.tearDown()
        integration.KernelTests.tearDownClass()


def make_access(state):
    path = state/'openvpn-access.json'
    path.write_text(json.dumps({'forward': [
        {'group':'vpn-v4', 'source':'10.8.0.2/32', 'destination':'10.30.0.2/32', 'input':'tun0', 'output':'lan0', 'protocol':'tcp', 'ports':'18443'},
        {'group':'vpn-v6', 'source':'fd42:8::2/128', 'destination':'fd00:30::2/128', 'input':'tun0', 'output':'lan0', 'protocol':'tcp', 'ports':'18443'},
    ]}))
    path.chmod(0o600)
    return path


def run_s2s_alias_flow(integration, fixture, state):
    from core.compiler import generate
    from core.config import Configuration
    access = state/'openvpn-s2s-access.json'
    access.write_text(json.dumps({'forward': [
        {'group':'site-v4', 'source':'10.88.0.2/32', 'destination':'10.30.0.2/32', 'input':'tun0', 'output':'lan0', 'protocol':'tcp', 'ports':'18443'},
    ]}))
    access.chmod(0o600)
    site = subprocess.Popen(['unshare', '--net', 'python3', '-u', '-c',
                              'import time; print("ready", flush=True); time.sleep(3600)'],
                             stdout=subprocess.PIPE, text=True)
    try:
        if site.stdout.readline().strip() != 'ready':
            raise AssertionError('Could not create the remote site host namespace')
        run(['ip', 'link', 'add', 's2s-client0', 'type', 'veth', 'peer', 'name', 's2s-site0'])
        run(['ip', 'link', 'set', 's2s-client0', 'netns', str(fixture.peer.p.pid)])
        run(['ip', 'link', 'set', 's2s-site0', 'netns', str(site.pid)])
        peer_run(fixture.peer, ['ip', 'addr', 'add', '10.88.0.1/24', 'dev', 's2s-client0'])
        peer_run(fixture.peer, ['ip', 'link', 'set', 's2s-client0', 'up'])
        peer_run(fixture.peer, ['sysctl', '-q', '-w', 'net.ipv4.ip_forward=1'])
        run(['nsenter', '-t', str(site.pid), '-n', 'ip', 'link', 'set', 'lo', 'up'])
        run(['nsenter', '-t', str(site.pid), '-n', 'ip', 'addr', 'add', '10.88.0.2/24', 'dev', 's2s-site0'])
        run(['nsenter', '-t', str(site.pid), '-n', 'ip', 'addr', 'add', '10.88.0.3/24', 'dev', 's2s-site0'])
        run(['nsenter', '-t', str(site.pid), '-n', 'ip', 'link', 'set', 's2s-site0', 'up'])
        run(['nsenter', '-t', str(site.pid), '-n', 'ip', 'route', 'add', '10.30.0.0/24', 'via', '10.88.0.1'])
        for backend in ('nftables', 'iptables'):
            candidate = generate(Configuration(backend, only=['tcp_ssh', 'openvpn_sitetosite'], overrides={
                'IPTABLES_FRONTEND':integration.FRONTEND,
                'FAMILY_POLICY':'dual', 'ROUTED_POLICY':'drop', 'SSH_PORT':'22222',
                'OVPNS2S_INTERFACE':'tun0', 'OVPNS2S_LOCAL_SUBNETS':'10.30.0.0/24',
                'OVPNS2S_REMOTE_SUBNETS':'10.88.0.0/24', 'OVPNS2S_LOCAL_INTERFACE':'lan0',
                'OVPNS2S_ROUTER_ALIAS':'10.30.0.2;10.30.0.254',
                'OVPNS2S_ENABLE_NAT':'false', 'ACCESS_POLICY':str(access),
            }, privileged=True))
            with fixture.store.lock():
                fixture.store.apply_locked(candidate, local=True)
            direct = tcp_from_namespace(site.pid, '10.88.0.2', '10.30.0.2', 18443)
            if direct != '10.88.0.2':
                raise AssertionError(f'{backend} routed S2S grant failed or changed source: {direct!r}')
            alias = tcp_from_namespace(site.pid, '10.88.0.2', '10.30.0.254', 18443)
            if alias != '10.88.0.2':
                raise AssertionError(f'{backend} S2S router alias DNAT failed or changed source: {alias!r}')
            before_drop = forward_drop_count(integration, fixture, backend)
            denied = tcp_from_namespace(site.pid, '10.88.0.3', '10.30.0.2', 18443)
            after_drop = forward_drop_count(integration, fixture, backend)
            if denied != 'BLOCK' or after_drop <= before_drop:
                raise AssertionError(f'{backend} denied S2S source did not hit the firewall forward drop: result={denied!r}, counters={before_drop}->{after_drop}')
            fixture.disable()
            print(f'PASS: {backend} authenticated S2S route, router alias DNAT, and forward-drop of ungranted routed source')
    finally:
        site.terminate()
        try: site.wait(timeout=3)
        except subprocess.TimeoutExpired: site.kill(); site.wait()
        site.stdout.close()


if __name__ == '__main__':
    guard()
    raise SystemExit(isolated_main())
