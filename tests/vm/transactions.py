#!/usr/bin/python3
"""Guest-side QEMU integration checks for the production transaction path.

Run only in explicit phases from the VM orchestrator; see
docs/security/vm-transactions.md. This intentionally uses the installed suite
and its production state directory.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time

INSTALL = Path('/opt/l4d2-firewall')
STATE_PATH = Path('/var/lib/l4d2-firewall')
MARKER = Path('/run/l4d2-suite-vm.json')
MANIFEST = 'vm-transactions'
UNIT = 'l4d2-firewall.service'
CLI = INSTALL / 'ipp.sh'


def fail(message):
    raise RuntimeError(message)


def run(argv, *, check=True, timeout=30):
    result = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        fail(f"command failed ({result.returncode}): {' '.join(argv)}\n{result.stdout}{result.stderr}")
    return result


def safe_guest():
    if os.geteuid() != 0:
        fail('Run as root inside the disposable guest')
    virtualization = run(['systemd-detect-virt', '--vm']).stdout.strip()
    if virtualization not in ('qemu', 'kvm'):
        fail(f'Expected a QEMU/KVM guest, detected {virtualization!r}')
    try:
        info = MARKER.lstat()
    except FileNotFoundError:
        fail(f'Missing orchestrator marker {MARKER}')
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        fail(f'{MARKER} must be a root-owned regular file with mode 0600')
    try:
        marker = json.loads(MARKER.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(f'Invalid QEMU marker: {exc}')
    if marker != {'virtualization': 'qemu', 'disposable': True}:
        fail(f'Unexpected QEMU marker contents: {marker!r}')
    if INSTALL.resolve() != Path('/opt/l4d2-firewall') or not CLI.is_file():
        fail(f'Expected installed suite at {INSTALL}')
    # Reuse the suite's exact trust-boundary checks before running privileged code.
    sys.path.insert(0, str(INSTALL))
    from core.config import trusted
    trusted(INSTALL)
    trusted(CLI)
    trusted(INSTALL / 'core' / 'fw.py')
    if Path('/proc/1/comm').read_text().strip() != 'systemd':
        fail('The guest must boot with systemd as PID 1')
    running = run(['systemctl', 'is-system-running'], check=False)
    if running.returncode not in (0, 1):
        fail(f'systemd is unavailable: {running.stdout.strip()} {running.stderr.strip()}')
    unit = run(['systemctl', 'show', '--property=ExecStart', '--value', UNIT], check=False)
    if unit.returncode or '/opt/l4d2-firewall/core/fw.py' not in unit.stdout or 'load --local' not in unit.stdout:
        fail(f'{UNIT} is not the expected production restore unit: {unit.stdout.strip()} {unit.stderr.strip()}')


def store():
    from core.store import Store
    return Store(STATE_PATH)


def read_manifest(s):
    value = s.get(MANIFEST)
    if value is None:
        fail('No VM transaction manifest; run bootstrap first')
    return value


def write_manifest(s, manifest):
    with s.lock():
        s.put(MANIFEST, manifest)


def write_manifest_unlocked(s, manifest):
    # Used only while the SIGKILL worker intentionally holds writer.lock.
    # atomic_json still protects readers from a partial manifest.
    s.put(MANIFEST, manifest)


def canonical_digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def require_ssh_connection():
    value = os.environ.get('SSH_CONNECTION', '').strip()
    fields = value.split()
    if len(fields) != 4:
        fail('This phase must run from an authenticated SSH session (SSH_CONNECTION missing)')
    return fields


def cli(*args, timeout=45):
    return run([str(CLI), *args], timeout=timeout)


def policy_live(policy):
    sys.path.insert(0, str(INSTALL))
    from core import engine
    live = engine.inspect(policy['backend'], policy['config'].get('IPTABLES_FRONTEND', 'auto'))
    engine.preflight(policy, policy, live)
    if policy['backend'] == 'nftables':
        present = set(map(tuple, live['tables']))
        expected = {(item['family'], item['name']) for item in policy['objects']}
        if not expected <= present:
            fail(f'Missing confirmed nftables objects: {sorted(expected - present)}')
    else:
        if live['frontend'] != policy['config'].get('IPTABLES_FRONTEND'):
            fail(f"Resolved iptables frontend differs: policy={policy['config'].get('IPTABLES_FRONTEND')!r}, live={live['frontend']!r}")
        parsed = {family: engine.parse_save(text) for family, text in live['iprules'].items()}
        for family, tables in policy['families'].items():
            for table, chains in tables.items():
                missing = set(chains) - set(parsed[family].get(table, {}).get('chains', {}))
                if missing:
                    fail(f'Missing confirmed iptables chains IPv{family}/{table}: {sorted(missing)}')
    return live


def foreign_iptables_signature(policy):
    """Hash save-state outside registered chains and exact suite integration hooks."""
    sys.path.insert(0, str(INSTALL))
    from core import engine
    live = engine.inspect('iptables', policy['config'].get('IPTABLES_FRONTEND', 'auto'))
    if live['frontend'] != policy['config'].get('IPTABLES_FRONTEND'):
        fail(f"Foreign-rule check selected {live['frontend']!r}, expected {policy['config'].get('IPTABLES_FRONTEND')!r}")
    hooks = {}
    for table, parent, target in policy.get('hooks', []):
        hooks.setdefault(table, set()).add(tuple(engine.hook_rule(parent, target)))
    snapshot = []
    for family, text in sorted(live['iprules'].items()):
        parsed = engine.parse_save(text)
        for table, state in sorted(parsed.items()):
            owned = set(policy.get('families', {}).get(family, {}).get(table, {}))
            chains = sorted(line for name, line in state['chains'].items() if name not in owned)
            rules = [rule for rule in state['rules']
                     if rule[1] not in owned and tuple(rule) not in hooks.get(table, set())]
            if chains or rules:
                snapshot.append({'family': family, 'table': table, 'chains': chains, 'rules': rules})
    payload = json.dumps(snapshot, sort_keys=True, separators=(',', ':'))
    return {'digest': hashlib.sha256(payload.encode()).hexdigest(),
            'tables': len(snapshot), 'chains': sum(len(item['chains']) for item in snapshot),
            'rules': sum(len(item['rules']) for item in snapshot)}


def timer_state(token):
    unit = f'l4d2-rollback-{token}.timer'
    state = run(['systemctl', 'show', '--property=ActiveState', '--value', unit], check=False).stdout.strip()
    if state != 'active':
        fail(f'Production rollback timer is not active: {unit}={state!r}')
    return unit


def wait_for_rollback(s, token, grace=30):
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        pending = s.get('pending')
        rollback = s.get('last-rollback')
        if pending is None and rollback and rollback.get('token') == token:
            return rollback
        time.sleep(0.25)
    pending = s.get('pending')
    rollback = s.get('last-rollback')
    fail(f'Production systemd timer did not finish rollback {token} within {grace}s: pending={bool(pending)} rollback={rollback!r}')


def bootstrap():
    s = store()
    with s.lock():
        if any(s.get(key) is not None for key in ('current', 'pending', 'persisted')):
            fail('Refusing non-empty production state; prepare a fresh disposable guest')
        if s.get(MANIFEST) is not None:
            fail('VM transaction manifest already exists')
    # The guest-only source address is the QEMU user-network host. The host
    # orchestrator must verify actual SSH reachability before confirming later.
    cli('--backend', 'nftables', 'apply', '--local', '--set', 'ADMIN_SOURCES=10.0.2.2/32')
    cli('save')
    run(['systemctl', 'enable', UNIT])
    with s.lock():
        current = s.get('current')
        persisted = s.get('persisted')
        if current is None or current != persisted or current.get('backend') != 'nftables':
            fail('Bootstrap did not create the expected confirmed/persisted nftables policy')
    policy_live(current)
    write_manifest(s, {'phase': 'bootstrapped', 'baseline_digest': canonical_digest(current)})
    print(json.dumps({'phase': 'bootstrapped', 'baseline_digest': canonical_digest(current), 'unit_enabled': True}))


def arm_fresh_ssh():
    connection = require_ssh_connection()
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        current = s.get('current')
        if manifest.get('phase') != 'bootstrapped' or not current or s.get('pending'):
            fail('Fresh-SSH test requires the clean bootstrapped baseline')
        expected = canonical_digest(current)
    result = cli('--backend', 'nftables', 'apply', '--timeout', '120', '--set', 'ADMIN_SOURCES=10.0.2.2/32', '--set', 'SSH_BURST=21')
    with s.lock():
        pending = s.get('pending')
        if not pending:
            fail('Timed apply returned without a pending journal')
        token = pending['token']
        if pending['candidate']['config'].get('SSH_BURST') != '21':
            fail('Timed candidate did not contain the intended SSH policy change')
    timer = timer_state(token)
    write_manifest(s, {'phase': 'fresh-ssh-pending', 'baseline_digest': expected, 'apply_ssh_connection': connection,
                       'token': token, 'timer': timer, 'apply_output': result.stdout.strip()})
    print(json.dumps({'phase': 'fresh-ssh-pending', 'token': token, 'timer': timer,
                      'instruction': 'Open a separate authenticated SSH connection and run confirm-ssh TOKEN there.'}))


def confirm_fresh_ssh(token):
    connection = require_ssh_connection()
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        pending = s.get('pending')
        if manifest.get('phase') != 'fresh-ssh-pending' or not pending or token != manifest.get('token'):
            fail('Fresh-SSH confirmation does not match the pending test transaction')
        if connection == manifest['apply_ssh_connection']:
            fail('Confirmation must use a distinct SSH connection from the applicator session')
        if pending['token'] != token:
            fail('Pending transaction token changed')
    cli('--backend', 'nftables', 'confirm', '--token', token, '--admin-verified')
    cli('save')
    with s.lock():
        current = s.get('current')
        if s.get('pending') is not None or not current or current['config'].get('SSH_BURST') != '21':
            fail('Fresh-SSH confirmation did not durably confirm the candidate')
    policy_live(current)
    write_manifest(s, {'phase': 'fresh-ssh-confirmed', 'confirmed_digest': canonical_digest(current),
                       'confirm_ssh_connection': connection})
    print(json.dumps({'phase': 'fresh-ssh-confirmed', 'confirmed_digest': canonical_digest(current)}))


def arm_abandoned_session():
    connection = require_ssh_connection()
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        current = s.get('current')
        if manifest.get('phase') != 'worker-rolled-back' or not current or s.get('pending'):
            fail('Abandoned-session test requires the completed SIGKILL rollback result')
        baseline = canonical_digest(current)
    cli('--backend', 'nftables', 'apply', '--timeout', '12', '--set', 'ADMIN_SOURCES=10.0.2.2/32', '--set', 'SSH_BURST=22')
    with s.lock():
        pending = s.get('pending')
        if not pending or pending['candidate']['config'].get('SSH_BURST') != '22':
            fail('Abandoned-session candidate was not armed')
        token = pending['token']
    timer = timer_state(token)
    write_manifest(s, {'phase': 'abandoned-session-pending', 'baseline_digest': baseline,
                       'apply_ssh_connection': connection, 'token': token, 'timer': timer,
                       'deadline_monotonic': pending['deadline_monotonic']})
    print(json.dumps({'phase': 'abandoned-session-pending', 'token': token, 'timer': timer,
                      'deadline_monotonic': pending['deadline_monotonic'],
                      'instruction': 'Terminate this SSH session/applicator; do not confirm. Verify after deadline from VM console.'}))


def worker():
    """Apply candidate, then stall after the real engine commit for SIGKILL."""
    sys.path.insert(0, str(INSTALL))
    from core.compiler import generate
    from core.config import Configuration
    from core import engine
    s = store()
    candidate = generate(Configuration('nftables', profiles=['host-minimal'], overrides={
        'ADMIN_SOURCES': '10.0.2.2/32', 'SSH_BURST': '23',
    }, privileged=True))
    execute = engine.execute

    def execute_then_pause(tx):
        execute(tx)
        pending = s.get('pending')
        if not pending or pending['candidate'].get('config', {}).get('SSH_BURST') != '23':
            fail('Worker cannot find its durable candidate journal after commit')
        s.put('vm-worker-committed', {'pid': os.getpid(), 'token': pending['token'],
                                      'deadline_monotonic': pending['deadline_monotonic']})
        while True:
            time.sleep(60)

    engine.execute = execute_then_pause
    with s.lock():
        s.apply_locked(candidate, timeout=30, watchdog='systemd')
    fail('Fault-injection worker unexpectedly returned')


def launch_kill_worker():
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        current = s.get('current')
        if manifest.get('phase') != 'fresh-ssh-confirmed' or not current or s.get('pending'):
            fail('SIGKILL test requires the confirmed fresh-SSH result')
        baseline = canonical_digest(current)
        s.delete('vm-worker-committed')
    command = [sys.executable, '-I', str(Path(__file__).resolve()), '_worker']
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True,
                             env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    committed = None
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if child.poll() is not None:
            fail(f'SIGKILL worker exited before its commit marker (status {child.returncode})')
        committed = s.get('vm-worker-committed')
        if committed:
            break
        time.sleep(0.1)
    if not committed:
        child.kill()
        fail('SIGKILL worker did not reach the post-commit pause within 60 seconds')
    pending = s.get('pending')
    current = s.get('current')
    if not pending or pending.get('token') != committed['token']:
        child.kill()
        fail('Worker commit marker and durable pending journal do not match')
    if not current or canonical_digest(current) != baseline or canonical_digest(pending.get('previous')) != baseline:
        child.kill()
        fail('Confirmed predecessor was not durable before the worker commit')
    if child.pid != committed['pid']:
        child.kill()
        fail('Worker PID marker does not match the spawned worker')
    timer = timer_state(committed['token'])
    policy_live(pending['candidate'])
    write_manifest_unlocked(s, {'phase': 'worker-committed', 'baseline_digest': baseline,
                                'token': committed['token'], 'pid': child.pid, 'timer': timer,
                                'deadline_monotonic': pending['deadline_monotonic']})
    print(json.dumps({'phase': 'worker-committed', 'pid': child.pid, 'token': committed['token'],
                      'timer': timer, 'deadline_monotonic': pending['deadline_monotonic'],
                      'instruction': 'Run kill-committed-worker to SIGKILL this stalled applicator.'}))


def kill_committed_worker():
    s = store()
    # The worker holds writer.lock until it is killed. These durable JSON reads
    # are atomic and must not be wrapped in Store.lock here.
    manifest = read_manifest(s)
    pending = s.get('pending')
    if manifest.get('phase') != 'worker-committed' or not pending or pending.get('token') != manifest.get('token'):
        fail('No post-commit worker is armed for SIGKILL')
    pid = manifest['pid']
    if (s.get('vm-worker-committed') or {}).get('pid') != pid:
        fail('Worker commit marker changed; refusing to signal a different PID')
    timer_state(manifest['token'])
    try:
        argv = Path(f'/proc/{pid}/cmdline').read_bytes().decode().split('\x00')
    except FileNotFoundError:
        fail(f'Committed worker PID {pid} is already gone')
    if str(Path(__file__).resolve()) not in argv or '_worker' not in argv:
        fail(f'Recorded PID {pid} is not the isolated transaction worker: {argv!r}')
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        fail(f'Committed worker PID {pid} is already gone')
    os.kill(pid, signal.SIGKILL)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            state = Path(f'/proc/{pid}/stat').read_text().split()[2]
        except FileNotFoundError:
            break
        if state == 'Z':
            break
        time.sleep(0.05)
    else:
        fail(f'Worker PID {pid} did not exit after SIGKILL')
    manifest['phase'] = 'worker-killed'
    write_manifest(s, manifest)
    print(json.dumps({'phase': 'worker-killed', 'pid': pid, 'token': manifest['token']}))


def verify_killed_worker_rollback():
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        if manifest.get('phase') != 'worker-killed':
            fail('SIGKILL rollback verification requires a killed post-commit worker')
        token = manifest['token']
        if time.monotonic() < manifest['deadline_monotonic']:
            fail('Rollback deadline has not elapsed; wait until after the recorded monotonic deadline')
    wait_for_rollback(s, token)
    with s.lock():
        pending = s.get('pending')
        current = s.get('current')
        rollback = s.get('last-rollback')
        if pending is not None or not rollback or rollback.get('token') != token:
            fail(f'Production systemd timer has not rolled back killed worker {token}: pending={bool(pending)} rollback={rollback!r}')
        if not current or canonical_digest(current) != manifest['baseline_digest']:
            fail('SIGKILL rollback did not restore the exactly confirmed predecessor')
        s.delete('vm-worker-committed')
    policy_live(current)
    write_manifest(s, {'phase': 'worker-rolled-back', 'rollback_token': token,
                       'restored_digest': canonical_digest(current)})
    print(json.dumps({'phase': 'worker-rolled-back', 'rollback_token': token,
                      'restored_digest': canonical_digest(current)}))


def verify_abandoned_rollback():
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        if manifest.get('phase') != 'abandoned-session-pending':
            fail('No abandoned-session transaction to verify')
        token = manifest['token']
        if time.monotonic() < manifest['deadline_monotonic']:
            fail('Rollback deadline has not elapsed; wait until after the recorded monotonic deadline')
    wait_for_rollback(s, token)
    with s.lock():
        pending = s.get('pending')
        current = s.get('current')
        rollback = s.get('last-rollback')
        if pending is not None or not rollback or rollback.get('token') != token:
            fail(f'Production timer has not rolled back token {token}: pending={bool(pending)} rollback={rollback!r}')
        if not current or canonical_digest(current) != manifest['baseline_digest']:
            fail('Rollback did not restore the exactly confirmed predecessor')
    policy_live(current)
    write_manifest(s, {'phase': 'abandoned-session-rolled-back', 'rollback_token': token,
                       'restored_digest': canonical_digest(current)})
    print(json.dumps({'phase': 'abandoned-session-rolled-back', 'rollback_token': token,
                      'restored_digest': canonical_digest(current)}))


def prepare_reboot():
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        current = s.get('current')
        if manifest.get('phase') != 'abandoned-session-rolled-back' or not current or s.get('pending'):
            fail('Reboot test requires completed rollback test and a confirmed policy')
    cli('save')
    run(['systemctl', 'enable', UNIT])
    with s.lock():
        current = s.get('current')
        persisted = s.get('persisted')
        if current != persisted:
            fail('Persisted policy differs from confirmed policy before reboot')
    digest = canonical_digest(current)
    write_manifest(s, {'phase': 'reboot-prepared', 'persisted_digest': digest})
    print(json.dumps({'phase': 'reboot-prepared', 'persisted_digest': digest,
                      'instruction': 'Orchestrator reboot the guest, recreate the root-owned /run marker, then run post-reboot.'}))


def verify_post_reboot():
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        if manifest.get('phase') != 'reboot-prepared':
            fail('Reboot phase was not prepared')
        current = s.get('current')
        persisted = s.get('persisted')
        if not current or current != persisted or canonical_digest(current) != manifest['persisted_digest']:
            fail('Boot unit did not restore the same confirmed persisted policy')
    service = run(['systemctl', 'show', '--property=Result', '--value', UNIT]).stdout.strip()
    active = run(['systemctl', 'show', '--property=ActiveState', '--value', UNIT]).stdout.strip()
    if service != 'success' or active != 'active':
        fail(f'Boot unit did not complete successfully: Result={service!r}, ActiveState={active!r}')
    policy_live(current)
    write_manifest(s, {'phase': 'post-reboot-verified', 'persisted_digest': canonical_digest(persisted),
                       'service_result': service, 'service_active_state': active})
    print(json.dumps({'phase': 'post-reboot-verified', 'persisted_digest': canonical_digest(persisted),
                      'unit_result': service, 'unit_active_state': active}))


def cleanup():
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        if manifest.get('phase') != 'post-reboot-verified' or s.get('pending'):
            fail('Cleanup requires a verified reboot and no pending transaction')
    cli('--backend', 'nftables', 'disable', '--local')
    run(['systemctl', 'disable', UNIT])
    with s.lock():
        s.delete('persisted')
        s.put(MANIFEST, {'phase': 'nft-cleaned'})
    print('Disposable guest nftables state disabled and test persistence removed.')


def bootstrap_legacy():
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        if manifest.get('phase') != 'nft-cleaned':
            fail('Legacy bootstrap requires successful nftables post-reboot verification and cleanup')
        if any(s.get(key) is not None for key in ('current', 'pending', 'persisted')):
            fail('Refusing non-empty production state before legacy bootstrap')
    cli('--backend', 'iptables', 'apply', '--local', '--set', 'ADMIN_SOURCES=10.0.2.2/32',
        '--set', 'IPTABLES_FRONTEND=legacy')
    cli('save')
    run(['systemctl', 'enable', UNIT])
    with s.lock():
        current = s.get('current')
        persisted = s.get('persisted')
        if (not current or current != persisted or current.get('backend') != 'iptables'
                or current.get('config', {}).get('IPTABLES_FRONTEND') != 'legacy'):
            fail('Bootstrap did not create the expected confirmed/persisted iptables-legacy policy')
    live = policy_live(current)
    if live['frontend'] != 'legacy':
        fail(f"iptables-legacy requested but resolved {live['frontend']!r}")
    digest = canonical_digest(current)
    write_manifest(s, {'phase': 'legacy-bootstrapped', 'baseline_digest': digest})
    print(json.dumps({'phase': 'legacy-bootstrapped', 'baseline_digest': digest,
                      'backend': 'iptables', 'frontend': live['frontend'], 'unit_enabled': True}))


def prepare_reboot_legacy():
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        current = s.get('current')
        if manifest.get('phase') != 'legacy-bootstrapped' or not current or s.get('pending'):
            fail('Legacy reboot test requires a clean confirmed iptables-legacy policy')
    cli('save')
    run(['systemctl', 'enable', UNIT])
    with s.lock():
        current = s.get('current')
        persisted = s.get('persisted')
        if current != persisted or current.get('config', {}).get('IPTABLES_FRONTEND') != 'legacy':
            fail('Persisted legacy policy differs from confirmed policy')
    digest = canonical_digest(current)
    write_manifest(s, {'phase': 'legacy-reboot-prepared', 'persisted_digest': digest})
    print(json.dumps({'phase': 'legacy-reboot-prepared', 'persisted_digest': digest,
                      'backend': 'iptables', 'frontend': 'legacy',
                      'instruction': 'Orchestrator reboot the guest, recreate the root-owned /run marker, then run post-reboot-legacy.'}))


def verify_post_reboot_legacy():
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        if manifest.get('phase') != 'legacy-reboot-prepared':
            fail('Legacy reboot phase was not prepared')
        current = s.get('current')
        persisted = s.get('persisted')
        if (not current or current != persisted or current.get('backend') != 'iptables'
                or current.get('config', {}).get('IPTABLES_FRONTEND') != 'legacy'
                or canonical_digest(current) != manifest['persisted_digest']):
            fail('Boot unit did not restore the same persisted iptables-legacy policy')
    service = run(['systemctl', 'show', '--property=Result', '--value', UNIT]).stdout.strip()
    active = run(['systemctl', 'show', '--property=ActiveState', '--value', UNIT]).stdout.strip()
    if service != 'success' or active != 'active':
        fail(f'Legacy boot unit did not complete successfully: Result={service!r}, ActiveState={active!r}')
    live = policy_live(current)
    if live['frontend'] != 'legacy':
        fail(f"Persisted iptables-legacy policy resolved to {live['frontend']!r} after reboot")
    digest = canonical_digest(persisted)
    write_manifest(s, {'phase': 'legacy-post-reboot-verified', 'persisted_digest': digest,
                       'service_result': service, 'service_active_state': active})
    print(json.dumps({'phase': 'legacy-post-reboot-verified', 'persisted_digest': digest,
                      'backend': 'iptables', 'frontend': live['frontend'],
                      'unit_result': service, 'unit_active_state': active}))


def cleanup_legacy():
    s = store()
    with s.lock():
        manifest = read_manifest(s)
        if manifest.get('phase') != 'legacy-post-reboot-verified' or s.get('pending'):
            fail('Legacy cleanup requires a verified reboot and no pending transaction')
        current = s.get('current')
        if not current or current.get('backend') != 'iptables':
            fail('Legacy cleanup has no registered current policy')
    foreign_before = foreign_iptables_signature(current)
    cli('--backend', 'iptables', 'disable', '--local')
    from core import engine
    live_after = engine.inspect('iptables', 'legacy')
    if live_after['frontend'] != 'legacy':
        fail(f"Cleanup check resolved {live_after['frontend']!r} instead of legacy")
    for family, tables in current['families'].items():
        parsed = engine.parse_save(live_after['iprules'][family])
        for table, chains in tables.items():
            remaining = set(chains) & set(parsed.get(table, {}).get('chains', {}))
            if remaining:
                fail(f'Legacy cleanup left owned chains IPv{family}/{table}: {sorted(remaining)}')
    foreign_after = foreign_iptables_signature(current)
    if foreign_after != foreign_before:
        fail(f'Legacy cleanup changed foreign iptables state: before={foreign_before!r}, after={foreign_after!r}')
    run(['systemctl', 'disable', UNIT])
    with s.lock():
        s.delete('persisted')
        s.delete(MANIFEST)
    print(json.dumps({'phase': 'legacy-cleaned', 'foreign_rules_before': foreign_before,
                      'foreign_rules_after': foreign_after, 'unit_disabled': True}))


PHASES = {
    'bootstrap': (bootstrap, 0),
    'arm-fresh-ssh': (arm_fresh_ssh, 0),
    'confirm-fresh-ssh': (confirm_fresh_ssh, 1),
    'arm-kill-worker': (launch_kill_worker, 0),
    'kill-committed-worker': (kill_committed_worker, 0),
    'verify-killed-worker-rollback': (verify_killed_worker_rollback, 0),
    'arm-abandoned-session': (arm_abandoned_session, 0),
    'verify-abandoned-rollback': (verify_abandoned_rollback, 0),
    'prepare-reboot': (prepare_reboot, 0),
    'post-reboot': (verify_post_reboot, 0),
    'cleanup': (cleanup, 0),
    'bootstrap-legacy': (bootstrap_legacy, 0),
    'prepare-reboot-legacy': (prepare_reboot_legacy, 0),
    'post-reboot-legacy': (verify_post_reboot_legacy, 0),
    'cleanup-legacy': (cleanup_legacy, 0),
}


def main(argv):
    if len(argv) == 2 and argv[1] == '_worker':
        safe_guest()
        worker()
        return
    if len(argv) < 2 or argv[1] not in PHASES:
        fail(f"Usage: {argv[0]} {{{','.join(PHASES)}}} [token]")
    phase = argv[1]
    func, arity = PHASES[phase]
    if len(argv) != 2 + arity:
        fail(f'Phase {phase} expects {arity} argument(s)')
    safe_guest()
    func(*argv[2:])


if __name__ == '__main__':
    try:
        main(sys.argv)
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
