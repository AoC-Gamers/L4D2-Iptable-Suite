#!/usr/bin/python3
"""Public command line. All firewall mutations enter Store's single writer lock."""
import argparse
import difflib
import json
import os
from pathlib import Path
import sys
import subprocess

# -I suppresses user site, PYTHONPATH and environment-based Python customization.
sys.dont_write_bytecode = True

# Verify additional privileged Python code before importing any project module.
# The entrypoint itself must already be trusted by its caller.
if os.geteuid() == 0:
    import stat
    install_root = Path(__file__).resolve().parents[1]
    isolated = Path('/proc/self/uid_map').read_text().strip().split() != ['0', '0', '4294967295']
    for code_path in [install_root, install_root / 'core', *(install_root / 'core').rglob('*')]:
        for item in [code_path, *code_path.parents]:
            info = item.lstat()
            directory = stat.S_ISDIR(info.st_mode)
            owner = info.st_uid == 0 or (isolated and directory and info.st_uid == 65534)
            sticky = directory and owner and bool(info.st_mode & stat.S_ISVTX)
            if stat.S_ISLNK(info.st_mode) or not ((owner and not info.st_mode & 0o022) or sticky):
                print(f'ERROR: untrusted privileged code path: {item}', file=sys.stderr)
                sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import ROOT, Configuration, PolicyError, access_file, require, splitlist, trusted
from core.compiler import generate
from core import engine
from core.store import DEFAULT_STATE, Store
from core.schema import migrate_policy


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir', default=str(DEFAULT_STATE))
    p.add_argument('--backend', choices=('iptables', 'nftables'), default='nftables')
    p.add_argument('operation', nargs='?', default='apply', choices=('validate', 'generate', 'plan', 'check', 'apply', 'confirm', 'rollback', 'disable', 'save', 'load', 'status', 'doctor', 'diagnose', 'boot-prepare', 'boot-guard', 'boot-restore', 'boot-disarm', 'ready', '_watch', '_detach'))
    p.add_argument('--env-file')
    p.add_argument('--set', action='append', default=[], metavar='KEY=VALUE')
    p.add_argument('--only', action='append')
    p.add_argument('--skip', action='append')
    p.add_argument('--profile', action='append')
    p.add_argument('--dry-run', action='store_true', help='Alias for plan: logical validation and candidate generation, no kernel check')
    p.add_argument('--verbose', action='store_true')
    p.add_argument('--timeout', type=int, default=120)
    p.add_argument('--watchdog', choices=('systemd', 'process'), default='systemd')
    p.add_argument('--local', action='store_true', help='Explicit console/boot operation without remote confirmation')
    p.add_argument('--verify-with', help='Trusted executable verifying a fresh administrative connection from outside')
    p.add_argument('--token')
    p.add_argument('--admin-verified', action='store_true', help='Operator confirms a NEW administrative connection was tested')
    p.add_argument('--partial', action='store_true', help='Recompose selected modules on top of the confirmed policy')
    p.add_argument('--remove', help='Recompose without these modules (dependencies must still be satisfied)')
    p.add_argument('--against', help='JSON candidate to compare in offline plan')
    p.add_argument('--accept-version-change', action='store_true', help='Explicit maintenance acceptance of unevaluated iptables version, never frontend changes')
    p.add_argument('--recovery-file', help='Root-owned scoped SSH recovery grants for boot-prepare; absent means console recovery')
    return p


def csvargs(items):
    return None if items is None else [x for item in items for x in splitlist(item)]


def configuration(args, privileged=False, previous=None):
    overrides = {}
    for pair in args.set:
        require('=' in pair, '--set needs KEY=VALUE')
        k, v = pair.split('=', 1)
        overrides[k] = v
    if previous and (args.partial or args.remove):
        previous = migrate_policy(previous)
        require('TYPECHAIN' not in overrides,
                'TYPECHAIN is legacy input only; partial/remove operations use normalized host/container settings')
        require(not args.env_file, 'Partial operation uses confirmed configuration; use --set for explicit updates')
        access_changed = 'ACCESS_POLICY' in overrides
        merged = {**previous['config'], **overrides}
        if access_changed:
            access = access_file(overrides['ACCESS_POLICY'], privileged)
        else:
            # Keep the confirmed parsed ACL; never reopen its former input path.
            access = previous['access']
        merged['ACCESS_POLICY'] = ''
        c = Configuration.from_normalized(
            args.backend, merged, previous['selected'], access, privileged=privileged,
            explicit_keys=overrides.keys(),
        )
        if args.partial:
            require(args.only is not None, '--partial requires --only')
            selected = Configuration.from_normalized(
                args.backend, c.values, csvargs(args.only),
                {'host': [], 'forward': [], 'containers': []}, privileged=privileged,
                explicit_keys=overrides.keys(),
            )
            require(set(selected.selected) <= set(previous['selected']), 'Partial update requires all objects/dependencies already managed')
            allowed = set()
            for i in selected.selected:
                m = c.catalog[i]
                allowed.update(m.get('REQUIRED_VARS', '').split())
                allowed.update(m.get('OPTIONAL_VARS', '').split())
            require(set(overrides) <= allowed, 'Partial operation cannot change core or unrelated configuration')
        if args.remove:
            remove = Configuration.from_normalized(
                args.backend, c.values, splitlist(args.remove),
                {'host': [], 'forward': [], 'containers': []}, privileged=privileged,
                explicit_keys=overrides.keys(),
            )
            remaining = set(previous['selected']) - set(remove.selected)
            require(remaining, 'Use disable to remove the entire suite')
            c = Configuration.from_normalized(
                args.backend, c.values, sorted(remaining), c.access, privileged=privileged,
                explicit_keys=overrides.keys(),
            )
            require(all(g['service'] in c.names for g in c.access['containers']), 'Remove container grants before removing their service')
        return c
    require(not args.partial and not args.remove, 'Partial/removal needs a confirmed policy')
    path = args.env_file
    if path is None and (ROOT / '.env').exists():
        path = str(ROOT / '.env')
    return Configuration(args.backend, path, overrides, csvargs(args.only), csvargs(args.skip), csvargs(args.profile), privileged)


def show(policy, args):
    if args.operation == 'generate':
        print(json.dumps(policy, sort_keys=True, indent=2))
        return
    v = policy['config']
    print('Logical composition and generation OK. Kernel check NOT performed.')
    print('Backend:', policy['backend'], '| families:', v['FAMILY_POLICY'])
    print('State capacity per meter/hashlimit:', v['STATE_CAPACITY'])
    print('Modules: core +', ', '.join(policy['selected']))
    print('Host services:', v['HOST_SERVICES'], '| routed:', v['ROUTED_POLICY'], '| containers:', v['CONTAINER_POLICY'])
    print('No services will be restarted. No global table flushes or shared policies will change.')
    if v['PRIVILEGED_BYPASS'] == 'true':
        print('PRIVILEGED HOST BYPASS:', v['BYPASS_SOURCE_IPS'])
    for key in sorted(v):
        if v[key] and (key.endswith('_PORTS') or key in ('SSH_PORT', 'OVPNSRV_PORT', 'ADMIN_SOURCES')):
            print(key + '=' + v[key])
    for section, grants in policy['access'].items():
        for g in grants:
            print(section + ': ' + json.dumps(g, sort_keys=True))
    if policy['backend'] == 'nftables':
        print('Objects replaced atomically (delete existing version + create in same transaction):')
        for obj in policy['objects']:
            print(obj['family'], obj['name'])
            print(obj['text'])
    else:
        print('Objects replaced per table and family (--noflush; shared hook inserted first on initial installation):')
        print(json.dumps(policy['families'], sort_keys=True, indent=2))
    if args.against:
        old = json.loads(Path(args.against).read_text())
        before = json.dumps(old, sort_keys=True, indent=2).splitlines()
        after = json.dumps(policy, sort_keys=True, indent=2).splitlines()
        print('\n'.join(difflib.unified_diff(before, after, fromfile=args.against, tofile='candidate')))
        if old['backend'] == 'nftables':
            oldobjs = {(o['family'], o['name']) for o in old['objects']}
            newobjs = {(o['family'], o['name']) for o in policy['objects']}
            print('Deleted objects:', sorted(oldobjs - newobjs))
        else:
            def keys(p):
                return {(f,t,c) for f,ts in p['families'].items() for t,cs in ts.items() for c in cs}
            print('Deleted owned chains:', sorted(keys(old) - keys(policy)))


def main(argv=None):
    from core import boot
    args = parser().parse_args(argv)
    if args.dry_run:
        args.operation = 'plan'
    require(2 <= args.timeout <= 3600, 'Timeout must be 2..3600 seconds')
    require(not args.accept_version_change or args.operation in ('check', 'apply', 'load'), 'Version acceptance is only available during check/apply/load maintenance')
    require(not args.recovery_file or args.operation == 'boot-prepare', '--recovery-file is only accepted by boot-prepare')
    if os.geteuid() == 0:
        # All Python code and shell helpers are part of the root trust boundary.
        for p in [ROOT, ROOT / 'core', *(ROOT / 'core').glob('*.py')]:
            trusted(p)
    if args.operation in ('validate', 'generate', 'plan'):
        require(not args.partial and not args.remove, 'Use apply --partial/--remove with confirmed state')
        c = configuration(args, privileged=os.geteuid() == 0)
        policy = generate(c)
        if args.operation == 'validate':
            print('Logical validation and generation OK; kernel and traffic NOT checked.')
        else:
            show(policy, args)
        return
    if args.operation == 'diagnose':
        require(os.geteuid() == 0, 'Passive kernel diagnosis requires root')
        require(not args.env_file and not args.partial and not args.remove and args.only is None and args.skip is None and args.profile is None, 'diagnose does not load policy configuration or state')
        frontend = 'auto'
        for pair in args.set:
            require(pair in ('IPTABLES_FRONTEND=auto', 'IPTABLES_FRONTEND=nft', 'IPTABLES_FRONTEND=legacy'), 'diagnose only accepts IPTABLES_FRONTEND')
            frontend = pair.split('=', 1)[1]
        live = engine.inspect(args.backend, frontend)
        print(json.dumps({'versions': live['versions'], 'frontend': live['frontend'], 'docker': live['docker'],
                          'docker_forward': engine.docker_forward_diagnostic(live)}, indent=2))
        return
    require(not args.accept_version_change or args.operation in ('check', 'apply', 'load'), 'Version acceptance is only available during check/apply/load maintenance')
    store = Store(args.state_dir)
    if args.operation == '_detach':
        require(args.token, 'Watchdog needs token')
        store.detach(args.token)
        return
    if args.operation == '_watch':
        require(args.token, 'Watchdog needs token')
        store.watch(args.token)
        return
    with store.lock():
        if args.operation in ('boot-prepare', 'boot-guard', 'boot-restore', 'boot-disarm', 'ready'):
            require(not args.accept_version_change and not args.env_file and not args.set and not args.partial and not args.remove
                    and args.only is None and args.skip is None and args.profile is None,
                    'Boot operations use the prepared confirmed policy, not configuration overrides')
            if args.operation == 'boot-prepare':
                result = boot.prepare(store, args.recovery_file)
            elif args.operation == 'boot-guard':
                result = boot.guard(store)
            elif args.operation == 'boot-restore':
                result = boot.restore(store)
            elif args.operation == 'boot-disarm':
                require(args.local, 'boot-disarm requires explicit --local console maintenance; disable protected units first')
                result = boot.disarm(store)
            else:
                result = boot.verify(store)
            print(json.dumps(result, sort_keys=True))
            return
        if args.operation == 'rollback':
            print('Restored previous suite objects.' if store.rollback_locked(args.token) else 'No matching pending change.')
            return
        store.rollback_locked(expired_only=True)
        if args.operation == 'confirm':
            require(args.token and args.admin_verified, 'Use confirm --token TOKEN --admin-verified after testing a NEW administrative connection')
            store.confirm_locked(args.token)
            print('New suite policy confirmed.')
            return
        if args.operation == 'status':
            print(json.dumps({'current': store.get('current'), 'pending': store.get('pending'), 'last-rollback': store.get('last-rollback')}, indent=2))
            return
        if args.operation == 'doctor':
            require(not args.env_file, 'doctor does not load service configuration; use --set IPTABLES_FRONTEND=legacy|nft|auto')
            frontend = 'auto'
            for pair in args.set:
                require(pair in ('IPTABLES_FRONTEND=auto','IPTABLES_FRONTEND=nft','IPTABLES_FRONTEND=legacy'), 'doctor only accepts --set IPTABLES_FRONTEND=auto|nft|legacy')
                frontend = pair.split('=',1)[1]
            live = engine.inspect(args.backend, frontend)
            print(json.dumps({k:v for k,v in live.items() if k != 'iprules'}, indent=2))
            return
        previous = store.get('current')
        if args.operation == 'save':
            require(previous and not store.get('pending'), 'Save requires a confirmed policy')
            boot.require_scope(store, previous)
            store.put('persisted', previous)
            boot.saved(store, previous)
            print('Saved suite policy to', store.path / 'persisted.json', '(system firewall files untouched)')
            return
        if args.operation == 'load':
            candidate = store.get('persisted')
            require(candidate, 'No persisted suite policy')
        elif args.operation == 'disable':
            require(previous, 'No registered suite policy to disable')
            candidate = {**previous, 'disabled': True}
        else:
            candidate = generate(configuration(args, privileged=True, previous=previous))
        if args.operation == 'check':
            live = engine.inspect(candidate['backend'], candidate['config'].get('IPTABLES_FRONTEND', 'auto'))
            engine.preflight(candidate, previous, live, accept_version_change=args.accept_version_change)
            if candidate['backend'] == 'iptables':
                candidate['hooks'] = engine.actual_hooks(candidate, live)
            engine.check(engine.prepare(candidate, [previous, candidate], live))
            print('Kernel candidate check passed; traffic NOT tested.')
            return
        if args.partial or args.remove:
            live = engine.inspect(candidate['backend'], candidate['config'].get('IPTABLES_FRONTEND', 'auto'))
            engine.require_owned_present(previous, live)
        token = store.apply_locked(candidate, args.timeout, args.watchdog, args.local, args.verify_with, args.accept_version_change)
        if token:
            print('Applied with timed rollback. Test a NEW administrative connection, then run:')
            print(f'./{candidate["backend"]}.rules.sh confirm --token {token} --admin-verified')
            print('Confirmation expires in', args.timeout, 'seconds. Suite state:', store.path)
        else:
            print('Applied and confirmed' + (' explicitly for console/boot.' if args.local else ' by external verifier.'))


if __name__ == '__main__':
    try:
        main()
    except (PolicyError, ValueError, OSError, KeyError, subprocess.TimeoutExpired) as e:
        print('ERROR:', e, file=sys.stderr)
        sys.exit(2)
