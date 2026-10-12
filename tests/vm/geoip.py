#!/usr/bin/python3
"""Offline run-update.sh -> GeoLite CSV parser -> actual GeoIP packet policy.

Requires /run/l4d2-suite-vm.json on a disposable QEMU/KVM guest. The harness
repeats the marker check and does all Netfilter/namespace work in a nested netns.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

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


def main():
    guard()
    host_netns = os.readlink('/proc/self/ns/net')
    if os.environ.get('SUITE_VM_INNER') != '1':
        # Keep all links, routes, and firewall tables out of the VM host namespace.
        temp = tempfile.mkdtemp(prefix='l4d2-vm-geoip-', dir='/root')
        try:
            child = ['unshare', '--net', '--mount', '--fork', 'bash', '-c',
                     'set -euo pipefail; marker="$4"; mount --make-rprivate /; mount -t tmpfs -o mode=755 tmpfs /run; '
                     'printf "%s\\n" "$marker" >/run/l4d2-suite-vm.json; chmod 600 /run/l4d2-suite-vm.json; '
                     'ip link set lo up; export SUITE_VM_INNER=1 SUITE_VM_HOST_NETNS="$1" SUITE_HOST_NETNS="$1" '
                     'SUITE_TEST_STATE="$2/state"; exec /usr/bin/python3 -I "$3"',
                     '_', host_netns, temp, str(Path(__file__).resolve()), MARKER.read_text()]
            result = run(child, check=False)
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            return result.returncode
        finally:
            shutil.rmtree(temp, ignore_errors=True)
    if os.readlink('/proc/self/ns/net') == os.environ.get('SUITE_VM_HOST_NETNS'):
        raise SystemExit('REFUSED: nested network namespace was not created')
    missing = [x for x in ('curl', 'ip', 'nft', 'iptables', 'ip6tables', 'nsenter') if not shutil.which(x)]
    if missing:
        raise SystemExit('Missing guest dependencies: ' + ', '.join(missing))
    sys.path.insert(0, str(ROOT/'tests'))
    sys.path.insert(0, str(ROOT))
    import integration
    return run_geoip_flow(integration)


def make_fixture_zip(path):
    import zipfile
    locations = (
        'geoname_id,locale_code,continent_code,continent_name,country_iso_code,country_name\n'
        '101,en,SA,South America,AR,Argentina\n'
        '202,en,NA,North America,US,United States\n'
    )
    blocks = (
        'network,geoname_id,registered_country_geoname_id,represented_country_geoname_id,is_anonymous_proxy,is_satellite_provider\n'
        '198.51.100.0/24,101,,,0,0\n'
        '203.0.113.0/24,202,,,0,0\n'
    )
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('GeoLite2-Country-CSV_20261011/GeoLite2-Country-Locations-en.csv', locations)
        archive.writestr('GeoLite2-Country-CSV_20261011/GeoLite2-Country-Blocks-IPv4.csv', blocks)


def udp_probe(peer, source):
    code = f'''import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(.7); s.bind(({source!r},0))
try:
 s.sendto(b"\\xff\\xff\\xff\\xffTSource Engine Query\\x00",("10.20.0.1",27015)); print(s.recvfrom(2048)[0].hex())
except OSError: print("BLOCK")
finally: s.close()
'''
    result = peer.python(code).strip()
    return result != 'BLOCK'


def run_geoip_flow(integration):
    state = Path(os.environ['SUITE_TEST_STATE'])
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    fixture = integration.KernelTests()
    integration.KernelTests.setUpClass()
    try:
        fixture.setUp()
        # /root is intentionally used: the privileged generator rejects writable
        # ancestors such as /tmp, while this scratch directory is private/root-owned.
        with tempfile.TemporaryDirectory(prefix='geoip-offline-', dir='/root') as d:
            work = Path(d)
            archive = work/'fixture.zip'
            make_fixture_zip(archive)
            output = work/'generated'
            env_file = work/'updater.env'
            env_file.write_text(
                'GEO_POLICY_ALLOWED_COUNTRIES=AR\n'
                'GEO_POLICY_DENIED_COUNTRIES=US\n'
                f'GEO_POLICY_DATA_DIR={output}\n'
            )
            env_file.chmod(0o600)
            env = {
                **os.environ,
                'WORKSPACE_ROOT': str(ROOT), 'ENV_FILE': str(env_file),
                'DOWNLOAD_DIR': str(work/'download'), 'MAXMIND_DOWNLOAD_URL': archive.as_uri(),
                'KEEP_ARCHIVE': 'true', 'GEOIPUPDATE_LICENSE_KEY': '', 'MAXMIND_LICENSE_KEY': '',
            }
            completed = run(['bash', str(ROOT/'geoip-updater/run-update.sh')], check=False, env=env)
            if completed.returncode:
                raise AssertionError(f'Offline updater failed ({completed.returncode}):\n{completed.stdout}\n{completed.stderr}')
            ar = output/'AR.ipv4.txt'
            us = output/'US.ipv4.txt'
            if '198.51.100.0/24' not in ar.read_text() or '203.0.113.0/24' not in us.read_text():
                raise AssertionError('Updater output did not contain the two fixture country prefixes')
            # Present the synthetic country addresses as directly routed client sources.
            run(['ip', 'addr', 'add', '198.51.100.1/24', 'dev', 'wan0'])
            run(['ip', 'addr', 'add', '203.0.113.1/24', 'dev', 'wan0'])
            fixture.peer.cmd('ip', 'addr', 'add', '198.51.100.2/24', 'dev', 'wan0p')
            fixture.peer.cmd('ip', 'addr', 'add', '203.0.113.2/24', 'dev', 'wan0p')
            from core.compiler import generate
            from core.config import Configuration
            policy = generate(Configuration('nftables', only=[
                'l4d2_udp_base', 'l4d2_packet_validation', 'l4d2_a2s_filters', 'geo_country_filter',
            ], overrides={
                'FAMILY_POLICY':'dual', 'GEO_IPV6_POLICY':'deny', 'GEO_POLICY_MODE':'denylist', 'GEO_POLICY_DENIED_COUNTRIES':'US',
                'GEO_POLICY_ALLOWED_COUNTRIES':'AR', 'GEO_POLICY_DATA_DIR':str(output),
                'GEO_POLICY_MANUAL_ALLOW_FILE':str(ROOT/'geoip/manual/allow_ipv4.txt'),
                'GEO_POLICY_MANUAL_DENY_FILE':str(ROOT/'geoip/manual/deny_ipv4.txt'),
            }, privileged=True))
            with fixture.store.lock():
                fixture.store.apply_locked(policy, local=True)
            outcome = {
                'synthetic-AR-source': udp_probe(fixture.peer, '198.51.100.2'),
                'synthetic-US-source': udp_probe(fixture.peer, '203.0.113.2'),
                'unlisted-source': udp_probe(fixture.peer, '10.20.0.2'),
            }
            if outcome != {'synthetic-AR-source': True, 'synthetic-US-source': False, 'unlisted-source': True}:
                raise AssertionError(f'Generated GeoIP policy traffic mismatch: {outcome}')
            print('PASS: local ZIP download -> run-update.sh -> CSV generation -> nft GeoIP traffic policy')
            print('NOTE: UDP query payload is a synthetic Source A2S-shaped probe; no L4D2 client/server is claimed.')
        fixture.tearDown()
        return 0
    finally:
        integration.KernelTests.tearDownClass()


if __name__ == '__main__':
    raise SystemExit(main())
