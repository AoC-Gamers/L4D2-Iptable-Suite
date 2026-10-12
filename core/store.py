"""One writer lock, durable journal, independent timed rollback."""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from .config import ROOT, PolicyError, require, trusted, isolated_userns, isolated_network
from . import engine
from .schema import canonical_for_storage, migrate_record, migrate_policy

DEFAULT_STATE = Path('/var/lib/l4d2-firewall')


def atomic_json(path, data):
    path = Path(path)
    tmp = path.with_name(path.name + '.' + secrets.token_hex(8))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, sort_keys=True, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        tmp.unlink(missing_ok=True)


def remaining(pending):
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if pending.get('boot_id', boot_id) != boot_id:
        return -1
    if 'deadline_monotonic' in pending:
        return pending['deadline_monotonic'] - time.monotonic()
    return pending['deadline'] - time.time()


class Store:
    def __init__(self, path=DEFAULT_STATE):
        self.path = Path(path).absolute()
        if self.path != DEFAULT_STATE:
            require(isolated_network(), 'Custom state directory allowed only in a disposable network namespace')
        require(os.geteuid() == 0, 'Engine/state operations require root (use an isolated namespace for tests)')
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        trusted(self.path)

    def get(self, name):
        p = self.path / (name + '.json')
        if not p.exists():
            return None
        trusted(p)
        return migrate_record(name, json.loads(p.read_text()))

    def put(self, name, value):
        atomic_json(self.path / (name + '.json'), canonical_for_storage(name, value))

    def delete(self, name):
        (self.path / (name + '.json')).unlink(missing_ok=True)
        fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @contextlib.contextmanager
    def lock(self):
        fd = os.open(self.path / 'writer.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def arm(self, token, timeout, mode):
        args = ['/usr/bin/python3', '-I', str(ROOT / 'core/fw.py'), '--state-dir', str(self.path), 'rollback', '--token', token]
        if mode == 'systemd':
            engine.command(['systemd-run', '--quiet', '--unit=l4d2-rollback-' + token, '--on-active=' + str(timeout) + 's', '--timer-property=AccuracySec=1s', *args])
        else:
            require(isolated_network(), 'Process watchdog only allowed in disposable network namespaces; production requires systemd timer')
            engine.command(['/usr/bin/python3', '-I', str(ROOT / 'core/fw.py'), '--state-dir', str(self.path), '_detach', '--token', token])

    def detach(self, token):
        # Double fork detaches from the applicator without a Popen lifetime or
        # lock descriptor. Production uses the system manager instead.
        fd = os.open(self.path / 'watchdog.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        first = os.fork()
        if first == 0:
            os.setsid()
            if os.fork() != 0:
                os._exit(0)
            os.dup2(fd, 1)
            os.dup2(fd, 2)
            nullfd = os.open('/dev/null', os.O_RDONLY)
            os.dup2(nullfd, 0)
            # Close inherited writer lock and every other descriptor.
            os.closerange(3, 65536)
            os.execve('/usr/bin/python3', ['/usr/bin/python3', '-I', str(ROOT / 'core/fw.py'), '--state-dir', str(self.path), '_watch', '--token', token], engine.SAFE_ENV)
        os.close(fd)
        os.waitpid(first, 0)

    def rollback_locked(self, token=None, expired_only=False):
        from . import boot
        pending = self.get('pending')
        if not pending:
            return False
        if token and token != pending['token']:
            return False
        if expired_only and remaining(pending) > 0:
            return False
        live = engine.inspect(pending['candidate']['backend'], pending['candidate']['config'].get('IPTABLES_FRONTEND', 'auto'))
        tx = engine.prepare(pending['snapshot'], [pending['previous'], pending['candidate']], live)
        engine.check(tx)
        boot.invalidate(self)
        engine.execute(tx)
        if pending['previous']:
            self.put('current', pending['previous'])
        else:
            self.delete('current')
        self.put('last-rollback', {'token': pending['token'], 'at': time.time()})
        self.delete('pending')
        if pending['previous']:
            try:
                boot.record_installed(self, pending['previous'])
            except (PolicyError, OSError, ValueError, subprocess.SubprocessError):
                # A snapshot from an empty boot is not an installed policy.
                # Recovery still succeeds, but consumers remain unavailable.
                boot.invalidate(self)
        return True

    def confirm_locked(self, token):
        from . import boot
        pending = self.get('pending')
        require(pending and secrets.compare_digest(token, pending['token']), 'Unknown pending confirmation token')
        if remaining(pending) <= 0:
            self.rollback_locked(token)
            require(False, 'Confirmation expired; previous suite policy restored')
        # Journal is retained until current is durable. On interruption the timer can
        # still restore previous state; current alone never disarms rollback.
        if pending['candidate'].get('disabled'):
            self.delete('current')
        else:
            self.put('current', pending['candidate'])
        boot.record_installed(self, pending['candidate'])
        self.delete('pending')

    def apply_locked(self, candidate, timeout=120, watchdog='systemd', local=False, verifier=None, accept_version_change=False):
        from . import boot
        # A journal must remain readable by recovery before the first kernel
        # write; reject malformed compiler/state bundles at this boundary too.
        candidate = migrate_policy(candidate)
        self.rollback_locked(expired_only=True)
        require(not self.get('pending'), 'Unconfirmed change pending; confirm or rollback first')
        previous = self.get('current')
        live = engine.inspect(candidate['backend'], candidate['config'].get('IPTABLES_FRONTEND', 'auto'))
        boot.require_scope(self, candidate)
        engine.preflight(candidate, previous, live, accept_version_change=accept_version_change)
        if candidate['backend'] == 'iptables':
            # Persist the resolved frontend so an alternatives change cannot send
            # the independent rollback to a different Netfilter implementation.
            candidate['config']['IPTABLES_FRONTEND'] = live['frontend']
            candidate['hooks'] = engine.actual_hooks(candidate, live)
            if not candidate.get('disabled'):
                decision = engine.compatibility(previous, live, accept_version_change)
                candidate['compatibility'] = (previous['compatibility']
                    if decision['decision'] == 'unchanged' and previous and previous.get('compatibility')
                    else decision)
            candidate['versions'] = live['versions']
        snap = engine.snapshot(previous, live)
        tx = engine.prepare(None if candidate.get('disabled') else candidate, [previous, candidate], live)
        engine.check(tx)  # Nothing active changes before every table/family has checked.
        token = secrets.token_hex(16)
        deadline = time.time() + timeout
        monotonic_deadline = time.monotonic() + timeout
        tx.deadline = monotonic_deadline
        self.put('pending', {'token': token, 'deadline': deadline, 'deadline_monotonic': monotonic_deadline, 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'previous': previous, 'snapshot': snap, 'candidate': candidate})
        execution_started = False
        try:
            if not local:
                self.arm(token, timeout, watchdog)
            boot.invalidate(self)
            execution_started = True
            engine.execute(tx)
            if remaining(self.get('pending')) <= 0:
                require(False, 'Apply exceeded its confirmation deadline; previous suite policy restored')
            if verifier:
                trusted(verifier)
                r = subprocess.run([verifier], env={**engine.SAFE_ENV, 'SUITE_CONFIRM_TOKEN': token}, timeout=max(1, int(remaining(self.get('pending'))) - 1), check=False)
                require(r.returncode == 0, 'External administrative connection verifier failed')
            if local or verifier:
                self.confirm_locked(token)
                return None
        except BaseException:
            # A watchdog setup failure precedes every Netfilter write. Deleting
            # the journal is sufficient and avoids rewriting live policy.
            if execution_started:
                self.rollback_locked(token)
            else:
                self.delete('pending')
            raise
        return token

    def watch(self, token):
        while True:
            pending = self.get('pending')
            if not pending or pending['token'] != token:
                return
            seconds = remaining(pending)
            if seconds <= 0:
                with self.lock():
                    self.rollback_locked(token, expired_only=True)
                return
            time.sleep(min(seconds, 1))
