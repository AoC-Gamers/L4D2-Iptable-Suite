"""Engine I/O: only registered suite objects and exact integration rules."""
import json
import re
import shlex
import subprocess
import time
from .config import BOOT_GUARD_TABLE, PolicyError, require

SAFE_ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C'}


def command(argv, text=None, optional=False, deadline=None):
    timeout = 120
    if deadline is not None:
        timeout = min(timeout, deadline - time.monotonic())
        require(timeout > 0, 'Apply deadline expired before the next firewall operation')
        if argv and argv[0].endswith('-restore'):
            require(timeout >= 1, 'Insufficient deadline budget to acquire the iptables lock safely')
            argv = [*argv]
            wait_at = argv.index('--wait') + 1
            argv[wait_at] = str(max(1, min(10, int(timeout))))
    r = subprocess.run(argv, input=text, text=True, capture_output=True, env=SAFE_ENV, timeout=timeout, check=False)
    if not optional:
        require(r.returncode == 0, f"{' '.join(argv)} failed: {r.stderr.strip()}")
    return r


_frontend = 'auto'


class TransactionBatch(list):
    """Sequence of engine transactions with an optional apply deadline."""
    deadline = None

def ipcmd(f, suffix=''):
    base = 'iptables' if str(f) == '4' else 'ip6tables'
    return base + ('' if _frontend == 'auto' else '-' + _frontend) + suffix


def inspect(backend, frontend='auto'):
    global _frontend
    _frontend = frontend
    tables = command(['nft', '-j', 'list', 'tables'])
    nt = [(x['table']['family'], x['table']['name']) for x in json.loads(tables.stdout)['nftables'] if 'table' in x]
    versions = {str(f): command([ipcmd(f), '--version']).stdout.strip() for f in (4, 6)}
    detected = {'nft' if '(nf_tables)' in value else 'legacy' if '(legacy)' in value else 'unknown' for value in versions.values()}
    effective = next(iter(detected)) if len(detected) == 1 else 'mixed'
    if backend == 'iptables':
        require(effective in ('nft','legacy'), 'IPv4/IPv6 iptables frontends differ or are unknown; migrate explicitly')
    if effective in ('nft','legacy'):
        # Pin binaries for this operation instead of rereading mutable alternatives.
        _frontend = effective
    iprules = {str(f): command([ipcmd(f, '-save')]).stdout for f in (4, 6)}
    docker_nf = any(n == 'docker-bridges' for _, n in nt)
    docker_ip = any(':DOCKER-USER ' in text for text in iprules.values())
    docker = 'mixed' if docker_nf and docker_ip else 'nftables' if docker_nf else 'iptables' if docker_ip else 'none'
    return {'tables': nt, 'versions': versions, 'frontend': effective, 'iprules': iprules, 'docker': docker,
            'nft_version': command(['nft', '--version']).stdout.strip()}


SUPPORTED_IPTABLES_VERSIONS = {'1.8.10'}


def version_identity(versions):
    identities = set()
    for family, name in (('4', 'iptables'), ('6', 'ip6tables')):
        value = versions.get(family, '')
        match = re.fullmatch(re.escape(name) + r' v([0-9]+\.[0-9]+\.[0-9]+)[^()\n]* \((nf_tables|legacy)\)[^\n]*', value)
        require(match, f'Compatibility: unknown IPv{family} iptables version identity')
        identities.add((match[1], 'nft' if match[2] == 'nf_tables' else 'legacy'))
    require(len(identities) == 1, 'Compatibility: IPv4/IPv6 versions or frontends differ')
    return next(iter(identities))


def compatibility(previous, live, accept_version_change=False):
    new_version, frontend = version_identity(live['versions'])
    require(live.get('frontend', frontend) == frontend, 'Compatibility: inconsistent effective frontend')
    if not previous or not previous.get('versions'):
        require(new_version in SUPPORTED_IPTABLES_VERSIONS or accept_version_change,
                'Compatibility: iptables version not evaluated; use explicit --accept-version-change maintenance flow')
        return {'decision': 'evaluated-version' if new_version in SUPPORTED_IPTABLES_VERSIONS else 'operator-maintenance',
                'previous': None, 'current': live['versions'], 'frontend': frontend}
    old_version, old_frontend = version_identity(previous['versions'])
    pinned = previous.get('config', {}).get('IPTABLES_FRONTEND', old_frontend)
    require(frontend == old_frontend == pinned, 'iptables frontend changed; explicit migration required')
    equal = previous['versions'] == live['versions']
    acceptance = previous.get('compatibility', {})
    accepted = (acceptance.get('decision') == 'operator-maintenance'
                and acceptance.get('current') == live['versions']
                and acceptance.get('frontend') == frontend)
    known_equal = equal and (new_version in SUPPORTED_IPTABLES_VERSIONS or accepted)
    evaluated = old_version in SUPPORTED_IPTABLES_VERSIONS and new_version in SUPPORTED_IPTABLES_VERSIONS
    require(known_equal or evaluated or accept_version_change,
            'iptables backend/version changed and transition is not evaluated; use --accept-version-change explicitly in maintenance')
    return {'decision': 'unchanged' if known_equal else 'evaluated-version' if evaluated else 'operator-maintenance',
            'previous': previous['versions'], 'current': live['versions'], 'frontend': frontend}


def preflight(policy, previous, live, accept_version_change=False):
    require(not previous or previous['backend'] == policy['backend'], 'Backend change requires disabling old suite and an explicit migration')
    if policy['backend'] == 'nftables' and not policy.get('disabled'):
        require(not any(obj.get('family') == 'inet' and obj.get('name') == BOOT_GUARD_TABLE
                        for obj in policy.get('objects', [])),
                f'nftables table inet {BOOT_GUARD_TABLE} is reserved for the boot guard')
    v = policy['config']
    if previous and policy['backend'] == 'iptables':
        if policy.get('disabled'):
            expected = previous.get('config', {}).get('IPTABLES_FRONTEND')
            if expected not in ('nft', 'legacy'):
                old_versions = previous.get('versions', {})
                markers = {'nft' if '(nf_tables)' in value else 'legacy' if '(legacy)' in value else 'unknown'
                           for value in old_versions.values()}
                expected = next(iter(markers)) if len(markers) == 1 else 'unknown'
            require(expected in ('nft', 'legacy') and live.get('frontend') == expected,
                    'iptables frontend changed; refusing to disable through a different engine')
        else:
            compatibility(previous, live, accept_version_change)
    if not previous and policy['backend'] == 'iptables' and not policy.get('disabled'):
        compatibility(None, live, accept_version_change)
    if policy['access']['containers'] and not policy.get('disabled'):
        docker = live['docker']
        require(docker != 'none', 'No Docker integration objects detected; start/configure Docker separately before applying')
        require(docker != 'mixed', 'Ambiguous Docker backends: nft tables plus DOCKER-USER; migrate explicitly')
        require(v['DOCKER_BACKEND'] in ('auto', docker), 'Declared Docker backend differs from kernel objects')
        require(policy['backend'] != 'iptables' or docker == 'iptables', 'iptables suite with native nft Docker unsupported')
        if docker == 'iptables' and policy['backend'] == 'iptables':
            diagnostic = docker_forward_diagnostic(live, ('4', '6'), previous if previous and not previous.get('disabled') else None)
            require(diagnostic['ok'], 'Docker integration preflight failed: ' + '; '.join(diagnostic['errors']))
    if policy['backend'] == 'nftables' and policy['access']['forward'] and not policy.get('disabled'):
        require(live['docker'] not in ('iptables', 'mixed'), 'Native nft routed grants with Docker iptables may encounter FORWARD DROP; use iptables suite or migrate Docker explicitly')
    if policy['backend'] == 'nftables':
        registered = {(x['family'], x['name']) for x in (previous or {}).get('objects', [])}
        for obj in policy['objects']:
            key = (obj['family'], obj['name'])
            require(key not in live['tables'] or key in registered, f"Object not owned: {key}; explicit legacy migration required")
    else:
        old = (previous or {}).get('families', {})
        for f, tables in policy['families'].items():
            live_tables = parse_save(live['iprules'][f])
            for t, chains in tables.items():
                for chain in chains:
                    require(chain not in live_tables.get(t, {}).get('chains', {}) or chain in old.get(f, {}).get(t, {}), f"Chain not registered: {f}/{t}/{chain}")
    # Never silently run beside an old layout with broad/bypassing rules.
    if previous and policy['backend'] == 'iptables' and not policy.get('disabled'):
        # At boot, the confirmed journal may outlive the kernel ruleset. Permit
        # a full restore only when none of the registered suite chains exist;
        # if any do exist, keep requiring intact first-position integration.
        registered = previous.get('families', {})
        owned_present = False
        for f, tables in registered.items():
            parsed = parse_save(live['iprules'][f])
            owned_present |= any(
                chain in parsed.get(table, {}).get('chains', {})
                for table, chains in tables.items() for chain in chains
            )
        if owned_present:
            for f in ('4','6'):
                parsed = parse_save(live['iprules'][f])
                for table, parent, c in previous.get('hooks', []):
                    # Removing the last container grant must remain possible if
                    # Docker has gone away or its own hook has changed. The
                    # candidate no longer relies on DOCKER-USER in that case.
                    if parent == 'DOCKER-USER' and not policy.get('access', {}).get('containers'):
                        continue
                    rs = [r for r in parsed.get(table, {}).get('rules', []) if r[1] == parent]
                    if c not in previous.get('families', {}).get(f, {}).get(table, {}):
                        continue
                    require(rs and rs[0] == hook_rule(parent, c), f'Suite integration missing or no longer first: IPv{f} {table}/{parent}; operator review required')
    if not previous:
        require(not any(':UDP_GAME_NEW_LIMIT ' in x or ':SSHfilter ' in x for x in live['iprules'].values()), 'Legacy suite detected; follow migration guide before claiming new objects')


def parse_save(text):
    tables = {}
    current = None
    for line in text.splitlines():
        if line.startswith('*'):
            current = tables.setdefault(line[1:], {'chains': {}, 'rules': []})
        elif line.startswith(':') and current is not None:
            chain = line.split()[0][1:]
            current['chains'][chain] = line
        elif line.startswith('-A ') and current is not None:
            current['rules'].append(shlex.split(line))
    return tables


def hook_rule(parent, target):
    return ['-A', parent, '-m', 'comment', '--comment', 'l4d2-suite:integration', '-j', target]


def _jump_targets(rule, chain):
    """Return jump/goto operations in one parsed iptables-save rule."""
    result = []
    i = 2
    while i < len(rule):
        token = rule[i]
        if token in ('-j', '--jump', '-g', '--goto') and i + 1 < len(rule):
            result.append((token, rule[i + 1]))
            i += 2
        elif token.startswith('--jump='):
            result.append(('--jump', token.split('=', 1)[1]))
            i += 1
        elif token.startswith('--goto='):
            result.append(('--goto', token.split('=', 1)[1]))
            i += 1
        else:
            i += 1
    return [(operation, target) for operation, target in result if target == chain]


def _unconditional_jump(rule, source, target):
    """Accept only a plain jump plus inert comment/counter syntax."""
    if len(rule) < 3 or rule[:2] != ['-A', source]:
        return False
    tokens = list(rule[2:])
    if len(tokens) >= 3 and tokens[0] == '-c' and all(x.isdecimal() for x in tokens[1:3]):
        tokens = tokens[3:]
    jumps = 0
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == '-m' and i + 1 < len(tokens) and tokens[i + 1] == 'comment':
            if i + 3 >= len(tokens) or tokens[i + 2] != '--comment':
                return False
            i += 4
            continue
        if token in ('-j', '--jump') and i + 1 < len(tokens) and tokens[i + 1] == target:
            jumps += 1
            i += 2
            continue
        if token == '--jump=' + target:
            jumps += 1
            i += 1
            continue
        return False
    return jumps == 1


def docker_forward_diagnostic(live, families=('4', '6'), previous=None):
    """Read-only structural diagnosis for iptables Docker forwarding.

    Docker's FORWARD chain must reach DOCKER-USER through one unconditional,
    first rule. When a registered suite hook is already installed there, it must
    remain the unique first rule in DOCKER-USER. The function only inspects the
    supplied iptables-save snapshots; it never repairs topology.
    """
    report = {'ok': True, 'families': {}, 'errors': []}
    for family in families:
        parsed = parse_save(live.get('iprules', {}).get(str(family), ''))
        rules = parsed.get('filter', {}).get('rules', [])
        chains = parsed.get('filter', {}).get('chains', {})
        forward = [rule for rule in rules if len(rule) >= 2 and rule[1] == 'FORWARD']
        links = [(index, rule) for index, rule in enumerate(forward) if _jump_targets(rule, 'DOCKER-USER')]
        errors = []
        if 'FORWARD' not in chains:
            errors.append('filter/FORWARD chain is absent')
        if 'DOCKER-USER' not in chains:
            errors.append('filter/DOCKER-USER chain is absent')
        if len(links) != 1:
            errors.append(f'expected one FORWARD jump to DOCKER-USER, found {len(links)}')
        elif links[0][0] != 0:
            errors.append(f'FORWARD rule {links[0][0] + 1} jumps to DOCKER-USER; it must be first')
        elif not _unconditional_jump(links[0][1], 'FORWARD', 'DOCKER-USER'):
            errors.append('first FORWARD link to DOCKER-USER is conditional or has unsupported syntax')

        own_target = None
        if previous:
            own_hooks = [h for h in previous.get('hooks', []) if h[:2] == ['filter', 'DOCKER-USER']]
            prior_chains = previous.get('families', {}).get(str(family), {}).get('filter', {})
            for _table, _parent, target in own_hooks:
                if target not in prior_chains or target not in chains:
                    continue  # No registered object in this family: restore can recreate it.
                own_target = target
                own_rule = hook_rule('DOCKER-USER', target)
                duser_rules = [rule for rule in rules if len(rule) >= 2 and rule[1] == 'DOCKER-USER']
                count = duser_rules.count(own_rule)
                if count != 1:
                    errors.append(f'DOCKER-USER has {count} exact suite hooks to {target}; expected one')
                elif not duser_rules or duser_rules[0] != own_rule:
                    errors.append(f'DOCKER-USER rule 1 is not the suite hook to {target}')
                break

        status = {
            'ok': not errors,
            'forward_chain': 'present' if 'FORWARD' in chains else 'absent',
            'docker_user_chain': 'present' if 'DOCKER-USER' in chains else 'absent',
            'forward_link_count': len(links),
            'forward_link_position': links[0][0] + 1 if links else None,
            'suite_hook_target': own_target,
            'errors': errors,
        }
        report['families'][str(family)] = status
        report['errors'].extend([f'IPv{family}: {message}' for message in errors])
    report['ok'] = not report['errors']
    return report


def actual_hooks(policy, live):
    hooks = [list(x) for x in policy.get('hooks', [])]
    if live['docker'] == 'iptables' and policy['access']['containers']:
        hooks = [[t, 'DOCKER-USER' if p == 'FORWARD' and t == 'filter' else p, c] for t, p, c in hooks]
    return hooks


def snapshot(policy, live):
    if not policy:
        return None
    snap = {'backend': policy['backend']}
    if policy['backend'] == 'nftables':
        snap['objects'] = []
        for obj in policy['objects']:
            if (obj['family'], obj['name']) in live['tables']:
                # Stateless export excludes counters/expiration values; kernel accepts it as a declaration.
                text = command(['nft', '-s', 'list', 'table', obj['family'], obj['name']]).stdout
                snap['objects'].append({**obj, 'text': text})
    else:
        snap['families'] = {}
        snap['hooks'] = policy['hooks']
        for f, tables in policy['families'].items():
            parsed = parse_save(live['iprules'][f])
            snap['families'][f] = {}
            for t, chains in tables.items():
                rules = parsed.get(t, {}).get('rules', [])
                snap['families'][f][t] = {c: [r[2:] for r in rules if r[1] == c] for c in chains if c in parsed.get(t, {}).get('chains', {})}
    return snap


def quote_args(args):
    # iptables-restore reads double quotes; POSIX single quote escaping is NOT its grammar.
    return ' '.join('"' + a.replace('\\', '\\\\').replace('"', '\\"') + '"' if any(c.isspace() or c in '\\"' for c in a) else a for a in args)


def nft_transaction(target, union, live):
    keys = {(o['family'], o['name']) for p in union if p for o in p.get('objects', [])}
    lines = [f'delete table {f} {n}' for f,n in sorted(keys) if (f,n) in live['tables']]
    lines += [o['text'] for o in (target or {}).get('objects', [])]
    return '\n'.join(lines) + '\n'


def ip_transaction(target, union, live, f):
    parsed = parse_save(live['iprules'][str(f)])
    oldtables = {}
    hooks = set()
    for p in union:
        if not p:
            continue
        for t, chains in p.get('families', {}).get(str(f), {}).items():
            oldtables.setdefault(t, set()).update(chains)
        hooks.update(tuple(h) for h in p.get('hooks', []))
    newtables = (target or {}).get('families', {}).get(str(f), {})
    result = []
    for t in sorted(set(oldtables) | set(newtables), key=lambda t: (t != 'filter', t)):
        rules = parsed.get(t, {}).get('rules', [])
        present = parsed.get(t, {}).get('chains', {})
        desired = newtables.get(t, {})
        owned = oldtables.get(t, set()) | set(desired)
        lines = ['*' + t]
        for c in sorted(owned):
            if c in desired:
                lines.append(':' + c + ' - [0:0]')
            if c in present or c in desired:
                lines.append('-F ' + c)
        wanted_hooks = {tuple(h) for h in (target or {}).get('hooks', [])}
        for table, parent, c in sorted(hooks | wanted_hooks):
            if table != t:
                continue
            exact = hook_rule(parent, c)
            count = rules.count(exact)
            # Idempotence: leave the one existing integration in place.
            if (table, parent, c) in wanted_hooks and count == 1:

                continue
            for _ in range(count):
                lines.append(quote_args(['-D', *exact[1:]]))
            if (table, parent, c) in wanted_hooks:
                lines.append(quote_args(['-I', parent, '1', *exact[2:]]))
        for c, rs in desired.items():
            lines += [quote_args(['-A', c, *r]) for r in rs]
        for c in sorted(owned - set(desired)):
            if c in present:
                # Foreign references must fail the transaction rather than delete foreign rules.
                lines.append('-X ' + c)
        lines.append('COMMIT')
        result.append('\n'.join(lines) + '\n')
    return result


def prepare(target, union, live):
    backend = target['backend'] if target else next(p['backend'] for p in union if p)
    if backend == 'nftables':
        return TransactionBatch([('nft', nft_transaction(target, union, live))])
    result = []
    for f in ('4', '6'):
        result += [(ipcmd(f, '-restore'), t) for t in ip_transaction(target, union, live, f)]
    return TransactionBatch(result)


def check(transactions):
    for engine, text in transactions:
        argv = ['nft', '-c', '-f', '-'] if engine == 'nft' else [engine, '--wait', '10', '--test', '--noflush']
        command(argv, text)


def execute(transactions):
    deadline = getattr(transactions, 'deadline', None)
    for engine, text in transactions:
        argv = ['nft', '-f', '-'] if engine == 'nft' else [engine, '--wait', '10', '--noflush']
        command(argv, text, deadline=deadline)


def require_owned_present(policy, live):
    """Partial operations require a complete existing managed dependency graph."""
    if policy['backend'] == 'nftables':
        require(all((o['family'],o['name']) in live['tables'] for o in policy['objects']), 'Partial operation requires all registered tables to exist')
    else:
        for f, tables in policy['families'].items():
            parsed = parse_save(live['iprules'][f])
            for t, chains in tables.items():
                require(set(chains) <= set(parsed.get(t,{}).get('chains',{})), 'Partial operation requires all registered chains to exist')
