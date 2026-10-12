"""Small policy compiler around the existing service modules."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from .config import ROOT, GAME, PolicyError, require, network, ports, splitlist, duration


def short(name):
    return 'L4S_' + hashlib.sha256(name.encode()).hexdigest()[:16]


def run_modules(config, names, target, changes=None, phase='generate'):
    v = dict(config.values)
    v.update(changes or {})
    v['TYPECHAIN'] = '0' if target == 'host' else '1'
    env = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C', 'PROJECT_ROOT': str(ROOT), 'SUITE_PHASE': phase, **v}
    paths = [config.catalog[i]['path'] for i in config.selected if i.split('_', 1)[1] in names]
    # Semantic ordering: validate all packets, then classify, then baseline limits.
    def order(p):
        if '60_l4d2' in p:
            return (0, p)
        if '70_l4d2' in p:
            return (1, p)
        if '50_l4d2' in p:
            return (2, p)
        return (-1, p)
    paths.sort(key=order)
    if not paths:
        return []
    with tempfile.TemporaryDirectory(prefix='l4s-generate-') as d:
        record = Path(d) / 'commands.jsonl'
        env['SUITE_RECORD'] = str(record)
        r = subprocess.run(['/bin/bash', str(ROOT / 'core/render.sh'), *paths], env=env, cwd=ROOT,
                           text=True, capture_output=True, timeout=120, check=False)
        require(r.returncode == 0, f"Module {phase} failed: {r.stdout}{r.stderr}")
        return [json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []


def validate_modules(config):
    special = {'loopback', 'whitelist', 'openvpn_server', 'openvpn_sitetosite', 'l4d2_tcpfilter_chain'}
    run_modules(config, config.names - special, 'host', phase='validate')


class Compiler:
    def __init__(self, config):
        self.c = config
        self.v = config.values
        self.nft = config.backend == 'nftables'
        self.table = self.v['NF_TABLE_NAME']
        self.objects = {}
        self.ip = {4: {'filter': {}}, 6: {'filter': {}}}
        self.hooks = []
        self.nf_chains = set()

    def chain(self, logical, family=4, table='filter', base=None):
        if self.nft:
            key = ('inet', self.table) if table == 'filter' else ('ip' if family == 4 else 'ip6', self.table + '_nat' + str(family))
            self.objects.setdefault(key, [])
            name = logical
            if (key, name) not in self.nf_chains:
                self.nf_chains.add((key, name))
                spec = f' {{ type {"filter" if table == "filter" else "nat"} hook {base} priority {"-5" if table == "filter" else "100" if base == "postrouting" else "-100"}; policy {"drop" if base == "input" else "accept"}; }}' if base else ''
                self.objects[key].append(f'add chain {key[0]} {key[1]} {name}{spec}')
            return name
        name = short(logical)
        self.ip[family].setdefault(table, {}).setdefault(name, [])
        return name

    def add(self, chain, nf, ip, family=None, table='filter'):
        families = [family] if family else [4, 6]
        if self.nft:
            name = self.chain(chain, family or 4, table)
            key = ('inet', self.table) if table == 'filter' else ('ip' if family == 4 else 'ip6', self.table + '_nat' + str(family))
            if family and table == 'filter':
                nf = f'meta nfproto ipv{family} ' + nf
            self.objects[key].append(f'add rule {key[0]} {key[1]} {name} {nf}')
        else:
            for f in families:
                name = self.chain(chain, f, table)
                self.ip[f][table][name].append(ip)

    def guard(self, g, reply=False, original=False):
        f = network(g['source']).version
        addr = 'ip' if f == 4 else 'ip6'
        src, dst = (g['destination'], g['source']) if reply else (g['source'], g['destination'])
        i = g['output'] if reply else g['input']
        nf = f'iifname "{i}" {addr} saddr {src} {addr} daddr {dst}'
        ip = ['-i', i, '-s', src, '-d', dst]
        if 'output' in g:
            out = g['input'] if reply else g['output']
            nf += f' oifname "{out}"'
            ip += ['-o', out]
        proto = g['protocol']
        nf += f' meta l4proto {proto}'
        ip += ['-p', proto]
        if reply:
            nf += ' ' + proto + ' sport ' + nfports(g['ports']) + ' ct direction reply ct state established,related'
            ip += ['-m', 'multiport', '--sports', g['ports'], '-m', 'conntrack', '--ctdir', 'REPLY', '--ctstate', 'ESTABLISHED,RELATED']
        else:
            nf += ' ' + proto + ' dport ' + nfports(g['ports'])
            ip += ['-m', 'multiport', '--dports', g['ports']]
        if original:
            nf += f' ct status dnat ct original {addr} daddr {g["public_destination"].split("/")[0]}'
            ip += ['-m', 'conntrack', '--ctstate', 'DNAT', '--ctorigdst', g['public_destination'].split('/')[0]]
        return f, nf, ip

    def core(self):
        self.chain('input', base='input')
        self.chain('forward', base='forward')
        self.add('input', 'iifname "lo" counter accept', ['-i', 'lo', '-j', 'ACCEPT'])
        self.add('input', 'ct state invalid counter drop', ['-m', 'conntrack', '--ctstate', 'INVALID', '-j', 'DROP'])
        # Network errors, PMTU, and neighbor discovery are independent of services.
        self.add('input', 'icmp type { destination-unreachable, time-exceeded, parameter-problem } counter accept',
                 ['-p', 'icmp', '--icmp-type', 'destination-unreachable', '-j', 'ACCEPT'], 4)
        if not self.nft:
            for t in ('time-exceeded', 'parameter-problem'):
                self.add('input', '', ['-p', 'icmp', '--icmp-type', t, '-j', 'ACCEPT'], 4)
        for t in ('destination-unreachable', 'packet-too-big', 'time-exceeded', 'parameter-problem'):
            self.add('input', f'icmpv6 type {t} counter accept', ['-p', 'ipv6-icmp', '--icmpv6-type', t, '-j', 'ACCEPT'], 6)
        for t in ('router-solicitation', 'router-advertisement', 'neighbour-solicitation', 'neighbour-advertisement'):
            nft_t = {'router-solicitation': 'nd-router-solicit', 'router-advertisement': 'nd-router-advert', 'neighbour-solicitation': 'nd-neighbor-solicit', 'neighbour-advertisement': 'nd-neighbor-advert'}[t]
            self.add('input', f'ip6 hoplimit 255 icmpv6 type {nft_t} counter accept',
                     ['-p', 'ipv6-icmp', '--icmpv6-type', t, '-m', 'hl', '--hl-eq', '255', '-j', 'ACCEPT'], 6)
        for f in (4, 6):
            proto = 'icmp' if f == 4 else 'icmpv6'
            self.add('input', f'{proto} type echo-request limit rate 20/second burst 20 packets counter accept',
                     ['-p', 'icmp' if f == 4 else 'ipv6-icmp', '--icmp-type' if f == 4 else '--icmpv6-type', 'echo-request', '-m', 'limit', '--limit', '20/sec', '--limit-burst', '20', '-j', 'ACCEPT'], f)
        for f in (4, 6):
            self.add('input', ('icmp' if f == 4 else 'icmpv6') + ' type echo-request counter drop', ['-p', 'icmp' if f == 4 else 'ipv6-icmp', '--icmp-type' if f == 4 else '--icmpv6-type', 'echo-request', '-j', 'DROP'], f)
        if self.v['FAMILY_POLICY'] == 'ipv4-block-ipv6':
            self.add('input', 'counter drop', ['-j', 'DROP'], 6)
            self.add('forward', 'counter drop', ['-j', 'DROP'], 6)
        for f in (4, 6):
            proto = 'icmp' if f == 4 else 'icmpv6'
            self.add('forward', f'meta l4proto {proto} ct state related counter accept', ['-p', 'icmp' if f == 4 else 'ipv6-icmp', '-m', 'conntrack', '--ctstate', 'RELATED', '-j', 'ACCEPT'], f)
        self.add('forward', 'ct state invalid counter drop', ['-m', 'conntrack', '--ctstate', 'INVALID', '-j', 'DROP'])
        if self.nft:
            for domain in ('core_allow', 'vpn', 'admin', 'l4d2_tcp', 'web', 'l4d2_udp', 'docker_egress'):
                for hook in ('input', 'forward'):
                    self.chain(hook + '_' + domain)
        else:
            self.hooks = [('filter', 'INPUT', short('input')),
                          ('filter', 'FORWARD', short('forward'))]

    def module_records(self, records, target, context='host'):
        if self.nft:
            self.nft_records(records, target, context)
        else:
            self.iptables_records(records, target, context)

    def nft_records(self, records, target, context):
        prefix = 'input' if target == 'host' else 'forward'
        suffix = '' if target == 'host' else '_' + context
        def rename(text):
            if suffix:
                # Rename only identifiers, never packet fields/strings.
                for old in sorted(names, key=len, reverse=True):
                    text = re.sub(r'(?<![\w])' + re.escape(old) + r'(?![\w])', old + suffix, text)
            return text
        names = set()
        for rec in records:
            if rec[:3] == ['nft', 'add', 'chain']:
                names.add(rec[5])
            if rec[:3] == ['nft', 'add', 'rule']:
                names.add(rec[5])
                expr = ' '.join(rec[6:])
                names.update(re.findall(r'\bmeter (\w+)', expr))
        # Family-specific copies of per-source meters; explicit size + timeout.
        for rec in records:
            if rec[0] == 'nft-file':
                for line in rec[1].splitlines():
                    require(line.startswith(('add set inet ' + self.table + ' ', 'add element inet ' + self.table + ' ')), 'Foreign GeoIP object')
                    self.objects[('inet', self.table)].append(line)
                continue
            require(rec[:2] == ['nft', 'add'], f"Forbidden generator operation: {rec[:3]}")
            require(rec[3:5] == ['inet', self.table], 'Module writes foreign table')
            if rec[2] == 'chain':
                self.chain(rename(rec[5]))
                continue
            require(rec[2] == 'rule', 'Unexpected nft generator command')
            if rec[5].startswith(('input_', 'forward_')) and not rec[5].startswith(prefix + '_'):
                continue
            chain = rename(rec[5])
            expr = rename(' '.join(rec[6:]))
            if target != 'host':
                expr = expr.replace('meta l4proto tcp ct original proto-dst', 'tcp dport').replace('ct original proto-dst', 'tcp dport')
            if ' log prefix ' in expr:
                # Detection and drop live in separate rules. Logs have a scalar budget,
                # not per-attacker unlimited aggregate output nor "rate over".
                expr = re.sub(r'meter \w+ \{.*?\}', '', expr)
                expr = re.sub(r'limit rate (?:over )?\S+(?: burst \d+ packets)?', '', expr)
                expr = expr.replace('log prefix ', 'limit rate 30/minute burst 10 packets counter log prefix ')
            elif 'meter ' in expr:
                expr = re.sub(r'meter (\w+) \{', r'meter \1 size ' + self.v['STATE_CAPACITY'] + ' {', expr)
                if ' timeout ' not in expr:
                    expr = expr.replace(' limit rate ', ' timeout 1m limit rate ')
            # Every rule has a counter for reachable-policy assertions.
            if ' counter ' not in ' ' + expr + ' ':
                expr = re.sub(r'\b(accept|drop|return|jump)\b', r'counter \1', expr, count=1)
            admin_sources = splitlist(self.v['ADMIN_SOURCES']) if target == 'host' and rec[5] == 'input_admin' else []
            if 'meter ' in expr and 'ip saddr' in expr:
                for f in (4, 6):
                    e = expr if f == 4 else expr.replace('ip saddr', 'ip6 saddr').replace('ip daddr', 'ip6 daddr')
                    e = re.sub(r'meter (\w+)', lambda m: 'meter ' + m[1] + '_v' + str(f), e)
                    if admin_sources:
                        for src in admin_sources:
                            if network(src).version == f:
                                self.add(chain, f'{"ip" if f == 4 else "ip6"} saddr {src} ' + e, [], f)
                    else:
                        self.add(chain, e, [], f)
            elif admin_sources:
                for src in admin_sources:
                    f = network(src).version
                    self.add(chain, f'{"ip" if f == 4 else "ip6"} saddr {src} ' + expr, [], f)
            else:
                self.add(chain, expr, [])
        # Fail closed if meter allocation fails (including capacity exhaustion).
        for rec in records:
            if rec[:3] == ['nft', 'add', 'chain'] and 'limit' in rec[5]:
                self.add(rename(rec[5]), 'counter drop', [])

    def iptables_records(self, records, target, context):
        prefix = 'INPUT' if target == 'host' else 'DOCKER-USER'
        logical = 'input' if target == 'host' else context
        own = {}
        def cname(n):
            if n == prefix:
                return logical
            return context + '_' + n
        for rec in records:
            require(rec[0] == 'iptables', 'Unexpected generator')
            a = rec[1:]
            require('-t' not in a, 'Service module attempted NAT/shared table write')
            op, chain, *rule = a
            if chain in ('INPUT', 'FORWARD', 'OUTPUT', 'DOCKER-USER') and chain != prefix:
                continue
            if op == '-N':
                if chain != 'DOCKER-USER':
                    own.setdefault(cname(chain), [])
            elif op == '-F':
                own[cname(chain)] = []
            elif op in ('-A', '-I'):
                if op == '-I' and rule[0] == '1':
                    rule = rule[1:]
                own.setdefault(cname(chain), []).append(rule)
            else:
                raise PolicyError(f"Forbidden iptables generator op: {op}")
        allnames = {key[len(context)+1:]: key for key in own if key.startswith(context + '_')}
        for key, rules in own.items():
            for rule in rules:
                for flag in ('-j', '-g'):
                    if flag in rule:
                        n = rule.index(flag) + 1
                        if rule[n] in allnames:
                            rule[n] = short(allnames[rule[n]])
                if '--hashlimit-name' in rule:
                    n = rule.index('--hashlimit-name') + 1
                    raw_name = rule[n]
                    rule[n] = short(context + rule[n])
                    timeout = None
                    if raw_name.startswith('SSH_'):
                        timeout = self.v['SSH_METER_TIMEOUT']
                    elif raw_name.startswith('HTTPHTTPS'):
                        timeout = self.v['NFT_HTTP_HTTPS_METER_TIMEOUT']
                    elif raw_name.startswith('L4D2_ESTABLISHED'):
                        timeout = self.v['NFT_UDP_EST_METER_TIMEOUT']
                    elif raw_name.startswith(('A2S','STEAMGROUP')):
                        timeout = self.v['NFT_A2S_METER_TIMEOUT']
                    elif raw_name.startswith(('L4D2CONNECT','L4D2RESERVE')):
                        timeout = self.v['NFT_LOGIN_METER_TIMEOUT']
                    elif raw_name.startswith('L4D2_NEW_'):
                        timeout = self.v['NFT_UDP_NEW_METER_TIMEOUT']
                    if timeout:
                        expiry = str(duration(timeout) * 1000)
                        if '--hashlimit-htable-expire' in rule:
                            rule[rule.index('--hashlimit-htable-expire') + 1] = expiry
                        else:
                            rule += ['--hashlimit-htable-expire', expiry]
                    # hashlimit defaults its bucket count from host RAM. The
                    # kernel raises htable-max to at least htable-size, so a
                    # configured max alone is not an effective state bound.
                    for flag, value in (
                        ('--hashlimit-htable-size', self.v['STATE_CAPACITY']),
                        ('--hashlimit-htable-max', self.v['STATE_CAPACITY']),
                    ):
                        if flag in rule:
                            rule[rule.index(flag) + 1] = value
                        else:
                            rule += [flag, value]
                    if '--hashlimit-htable-expire' not in rule:
                        rule += ['--hashlimit-htable-expire', '60000']
                for f in (4, 6):
                    if f == 6 and (self.c.names & GAME):
                        continue
                    admin_sources = splitlist(self.v['ADMIN_SOURCES']) if key == 'input' and '--dports' in rule and rule[rule.index('--dports') + 1] == self.v.get('SSH_PORT') else []
                    if admin_sources:
                        for src in admin_sources:
                            if network(src).version == f:
                                self.add(key, '', ['-s', src, *rule], f)
                    else:
                        self.add(key, '', rule[:], f)

    def grants(self):
        for section in ('host', 'forward'):
            for g in self.c.access[section]:
                f, nf, ip = self.guard(g)
                if f == 6:
                    require(self.v['FAMILY_POLICY'] == 'dual', 'IPv6 grants conflict with blocked IPv6')
                # Scoped host grants explicitly override service control, visible in plan.
                self.add('input' if section == 'host' else 'forward', nf + ' counter accept', ip + ['-j', 'ACCEPT'], f)
                if section == 'forward':
                    f, nf, ip = self.guard(g, reply=True)
                    self.add('forward', nf + ' counter accept', ip + ['-j', 'ACCEPT'], f)
        if self.v['PRIVILEGED_BYPASS'] == 'true':
            for src in splitlist(self.v['BYPASS_SOURCE_IPS']):
                f = network(src).version
                self.add('input', f'{"ip" if f == 4 else "ip6"} saddr {src} counter accept', ['-s', src, '-j', 'ACCEPT'], f)

    def vpn(self):
        v = self.v
        if 'openvpn_server' in self.c.names and v['HOST_SERVICES'] == 'true':
            p = v['OVPNSRV_PROTO']
            self.add('input', f'{p} dport {v["OVPNSRV_PORT"]} counter accept', ['-p', p, '--dport', v['OVPNSRV_PORT'], '-j', 'ACCEPT'])
        for scope, module in (('OVPNSRV', 'openvpn_server'), ('OVPNS2S', 'openvpn_sitetosite')):
            if module not in self.c.names:
                continue
            srcs = splitlist(v[scope + ('_SUBNET' if scope == 'OVPNSRV' else '_REMOTE_SUBNETS')])
            iface = v[scope + '_INTERFACE']
            out = v.get(scope + ('_LAN_INTERFACE' if scope == 'OVPNSRV' else '_LOCAL_INTERFACE'), '')
            aliases = []
            if v.get(scope + '_ROUTER_REAL_IP') or v.get(scope + '_ROUTER_ALIAS_IP'):
                require(v.get(scope + '_ROUTER_REAL_IP') and v.get(scope + '_ROUTER_ALIAS_IP'), 'Router real/alias must be set together')
                aliases.append((v[scope + '_ROUTER_REAL_IP'], v[scope + '_ROUTER_ALIAS_IP']))
            if scope == 'OVPNS2S':
                aliases += [tuple(p.split(';')) for p in v.get(scope + '_ROUTER_ALIAS', '').split(',') if p]
            for src in srcs:
                f = network(src).version
                addr = 'ip' if f == 4 else 'ip6'
                if v.get(scope + '_ENABLE_NAT') == 'true':
                    dest = v.get('OVPNSRV_LAN_SUBNET') if scope == 'OVPNSRV' else None
                    dests = [dest] if dest else splitlist(v['OVPNS2S_LOCAL_SUBNETS'])
                    for dst in dests:
                        require(network(dst).version == f, 'NAT family mismatch')
                        self.chain('postrouting', f, 'nat', 'postrouting')
                        self.add('postrouting', f'{addr} saddr {src} {addr} daddr {dst} oifname "{out}" counter masquerade', ['-s', src, '-d', dst, '-o', out, '-j', 'MASQUERADE'], f, 'nat')
                        if not self.nft:
                            self.hooks.append(('nat', 'POSTROUTING', short('postrouting')))
                for real, alias in aliases:
                    require(f == 4 and network(real).version == 4 and network(alias).version == 4, 'Router aliases support IPv4 only')
                    self.chain('prerouting', f, 'nat', 'prerouting')
                    self.add('prerouting', f'iifname "{iface}" ip saddr {src} ip daddr {alias} counter dnat to {real}', ['-i', iface, '-s', src, '-d', alias, '-j', 'DNAT', '--to-destination', real], f, 'nat')
                    if not self.nft:
                        self.hooks.append(('nat', 'PREROUTING', short('prerouting')))
                    if v.get(scope + '_ROUTER_ALIAS_SNAT') == 'true':
                        require(out, 'Alias SNAT needs output interface')
                        self.chain('postrouting', f, 'nat', 'postrouting')
                        self.add('postrouting', f'ip saddr {src} ip daddr {real} oifname "{out}" counter masquerade', ['-s', src, '-d', real, '-o', out, '-j', 'MASQUERADE'], f, 'nat')
                        if not self.nft:
                            self.hooks.append(('nat', 'POSTROUTING', short('postrouting')))

    def containers(self):
        for index, g in enumerate(self.c.access['containers']):
            context = 'container' + str(index)
            service = g['service']
            changes = {}
            variables = {'tcp_ssh': 'SSH_PORT', 'http_https_protect': 'HTTP_HTTPS_PORTS', 'allowlist_ports': 'BYPASS_' + g['protocol'].upper() + '_PORTS', 'l4d2_udp_base': 'L4D2_GAMESERVER_UDP_PORTS'}
            game_names = {service}
            if service == 'l4d2_udp_base':
                game_names = GAME
                other = next(str(p) for p in (65535,65534,65533) if not any(a <= p <= b for a,b in ports(g['ports'])))
                changes['L4D2_GAMESERVER_UDP_PORTS'] = g['ports'] if g['role'] == 'gameserver' else other
                changes['L4D2_SOURCETV_UDP_PORTS'] = g['ports'] if g['role'] == 'sourcetv' else other
            if service == 'openvpn_server':
                self.chain(context)
                self.add(context, 'counter accept', ['-j', 'ACCEPT'])
                dest = context
            else:
                if service != 'l4d2_udp_base':
                    changes[variables[service]] = g['ports']
                # SSH always uses host INPUT historically; compiler redirects to this chain.
                target = 'host' if service == 'tcp_ssh' else 'container'
                records = run_modules(self.c, game_names, target, changes)
                if service == 'tcp_ssh':
                    records = [r if r[0] != 'iptables' or len(r) < 3 or r[2] != 'INPUT' else [*r[:2], 'DOCKER-USER', *r[3:]] for r in records]
                    if self.nft:
                        records = [[x.replace('input_admin', 'forward_admin') if isinstance(x, str) else x for x in r] for r in records]
                self.module_records(records, 'container', context)
                dest = ('forward_' + {'tcp_ssh': 'admin', 'http_https_protect': 'web', 'allowlist_ports': 'core_allow', 'l4d2_udp_base':'l4d2_udp'}[service] + '_' + context) if self.nft else context
                self.add(dest, 'ct state established,related counter accept', ['-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])
                self.add(dest, 'counter drop', ['-j', 'DROP'])
            for (a, b), (c, d) in zip(ports(g['public_ports']), ports(g['ports'])):
                public = str(a) if a == b else f'{a}-{b}'
                ippublic = str(a) if a == b else f'{a}:{b}'
                scoped = {**g, 'ports': str(c) if c == d else f'{c}:{d}'}
                f, nf, ip = self.guard(scoped, original=True)
                self.add('forward', nf + f' ct original proto-dst {public} counter jump {dest}', ip + ['--ctorigdstport', ippublic, '-j', short(dest)], f)
                f, nf, ip = self.guard(scoped, reply=True, original=True)
                self.add('forward', nf + f' ct original proto-dst {public} counter accept', ip + ['--ctorigdstport', ippublic, '-j', 'ACCEPT'], f)

    def build(self):
        validate_modules(self.c)
        self.core()
        self.grants()
        self.vpn()
        special = {'loopback', 'whitelist', 'openvpn_server', 'openvpn_sitetosite', 'l4d2_tcpfilter_chain', 'docker_dns_egress', 'docker_monitor_egress'}
        # Legacy egress options lack zones/destinations; require scoped forward grants.
        require(not self.c.names & {'docker_dns_egress', 'docker_monitor_egress'}, 'Migrate Docker egress modules to forward grants with interfaces, source and destination')
        if self.v['HOST_SERVICES'] == 'true':
            if 'geo_country_filter' in self.c.names and self.v.get('GEO_POLICY_MODE') != 'off' and self.v.get('GEO_IPV6_POLICY') == 'deny':
                self.add('input_l4d2_udp', 'udp dport ' + nfports(self.v['L4D2_GAMESERVER_UDP_PORTS'] + ',' + self.v['L4D2_SOURCETV_UDP_PORTS']) + ' counter drop', [], 6)
            records = run_modules(self.c, self.c.names - special, 'host')
            self.module_records(records, 'host')
            if self.nft:
                for d in ('core_allow', 'vpn', 'admin', 'l4d2_tcp', 'web', 'l4d2_udp'):
                    self.add('input', 'counter jump input_' + d, [])
            # Game UDP has already reached all per-packet controls.
        self.add('input', 'ct state established,related counter accept', ['-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])
        self.add('input', 'counter drop', ['-j', 'DROP'])
        self.containers()
        if self.v['ROUTED_POLICY'] == 'drop':
            self.add('forward', 'counter drop', ['-j', 'DROP'])
        else:
            # Restrict only configured container zones while other routing is delegated.
            for g in self.c.access['containers']:
                self.add('forward', f'oifname "{g["output"]}" counter drop', ['-o', g['output'], '-j', 'DROP'])
                self.add('forward', f'iifname "{g["output"]}" counter drop', ['-i', g['output'], '-j', 'DROP'])
            self.add('forward', 'counter return', ['-j', 'RETURN'])
        if self.nft:
            objects = [{'family': f, 'name': n, 'text': '\n'.join([f'add table {f} {n}', *lines]) + '\n'} for (f,n), lines in self.objects.items()]
            result = {'backend': self.c.backend, 'objects': objects}
        else:
            result = {'backend': self.c.backend, 'families': {str(f): tables for f, tables in self.ip.items()}, 'hooks': [list(h) for h in sorted(set(self.hooks))]}
        result.update({'config': self.v, 'selected': self.c.selected, 'access': self.c.access, 'schema': 2})
        return result


def nfports(value):
    return '{ ' + value.replace(':', '-') + ' }'


def generate(config):
    return Compiler(config).build()
