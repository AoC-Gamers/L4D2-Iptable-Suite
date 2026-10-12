"""Engine I/O: only registered suite objects and exact integration rules."""
import json
import shlex
import subprocess
from .config import PolicyError, require

SAFE_ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C'}


def command(argv, text=None, optional=False):
    r = subprocess.run(argv, input=text, text=True, capture_output=True, env=SAFE_ENV, timeout=120, check=False)
    if not optional:
        require(r.returncode == 0, f"{' '.join(argv)} failed: {r.stderr.strip()}")
    return r


_frontend = 'auto'

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


def preflight(policy, previous, live):
    require(not previous or previous['backend'] == policy['backend'], 'Backend change requires disabling old suite and an explicit migration')
    v = policy['config']
    if previous and policy['backend'] == 'iptables':
        require(previous.get('versions', live['versions']) == live['versions'], 'iptables backend/version changed; migrate explicitly')
    if policy['access']['containers']:
        docker = live['docker']
        require(docker != 'none', 'No Docker integration objects detected; start/configure Docker separately before applying')
        require(docker != 'mixed', 'Ambiguous Docker backends: nft tables plus DOCKER-USER; migrate explicitly')
        require(v['DOCKER_BACKEND'] in ('auto', docker), 'Declared Docker backend differs from kernel objects')
        require(policy['backend'] != 'iptables' or docker == 'iptables', 'iptables suite with native nft Docker unsupported')
        if docker == 'iptables':
            for f in ('4', '6'):
                if f == '6' and v['FAMILY_POLICY'] != 'dual':
                    continue
                text = live['iprules'][f]
                require(':DOCKER-USER ' in text and '-A FORWARD -j DOCKER-USER' in text, f"Missing/reordered Docker integration in IPv{f}; no service restart attempted")
    if policy['backend'] == 'nftables' and policy['access']['forward']:
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
        for f in ('4','6'):
            parsed = parse_save(live['iprules'][f])
            for table, parent, c in previous.get('hooks', []):
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
        return [('nft', nft_transaction(target, union, live))]
    result = []
    for f in ('4', '6'):
        result += [(ipcmd(f, '-restore'), t) for t in ip_transaction(target, union, live, f)]
    return result


def check(transactions):
    for engine, text in transactions:
        argv = ['nft', '-c', '-f', '-'] if engine == 'nft' else [engine, '--wait', '10', '--test', '--noflush']
        command(argv, text)


def execute(transactions):
    for engine, text in transactions:
        argv = ['nft', '-f', '-'] if engine == 'nft' else [engine, '--wait', '10', '--noflush']
        command(argv, text)


def require_owned_present(policy, live):
    """Partial operations require a complete existing managed dependency graph."""
    if policy['backend'] == 'nftables':
        require(all((o['family'],o['name']) in live['tables'] for o in policy['objects']), 'Partial operation requires all registered tables to exist')
    else:
        for f, tables in policy['families'].items():
            parsed = parse_save(live['iprules'][f])
            for t, chains in tables.items():
                require(set(chains) <= set(parsed.get(t,{}).get('chains',{})), 'Partial operation requires all registered chains to exist')
