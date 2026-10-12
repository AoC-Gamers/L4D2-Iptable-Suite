"""Declarative configuration and composition; no firewall access or shell evaluation."""
import ipaddress
import math
import json
import os
from pathlib import Path
import re
import shlex
import stat

ROOT = Path(__file__).resolve().parents[1]
BOOT_GUARD_TABLE = 'l4d2_boot_guard'


class PolicyError(Exception):
    pass


def require(ok, message):
    if not ok:
        raise PolicyError(message)


def isolated_userns():
    # A non-initial user namespace cannot administer the host's network namespace.
    return Path('/proc/self/uid_map').read_text().strip().split() != ['0', '0', '4294967295']


def isolated_network():
    if isolated_userns():
        return True
    try:
        return os.readlink('/proc/self/ns/net') != os.readlink('/proc/1/ns/net')
    except OSError:
        return False


def trusted(path):
    """Root code/data must not be replaceable through a writable ancestor."""
    path = Path(path).absolute()
    for item in [path, *path.parents]:
        s = item.lstat()
        require(not stat.S_ISLNK(s.st_mode), f"Symlink not trusted: {item}")
        # A sticky directory (e.g. /tmp) cannot replace an owned child.
        sticky = stat.S_ISDIR(s.st_mode) and bool(s.st_mode & stat.S_ISVTX) and (s.st_uid == 0 or (isolated_userns() and s.st_uid == 65534))
        isolated = isolated_userns()
        ancestor = isolated and stat.S_ISDIR(s.st_mode) and s.st_uid == 65534
        require(((s.st_uid == 0 or ancestor) and not s.st_mode & 0o022) or sticky,
                f"Root ownership and no group/world write required: {item}")
    return path


def assignments(text):
    values = {}
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        require(bool(re.fullmatch(r'[A-Z][A-Z0-9_]*=.*', line)), f"Line {n}: expected KEY=VALUE")
        k, raw = line.split('=', 1)
        require(k not in values, f"Line {n}: duplicate key {k}")
        require(not any(c in raw for c in ('$', '`', '\\', '\x00')), f"Line {n}: shell expansion is forbidden")
        try:
            words = shlex.split(raw, comments=True)
        except ValueError as e:
            raise PolicyError(f"Line {n}: {e}") from e
        require(len(words) <= 1, f"Line {n}: quote values containing spaces")
        values[k] = words[0] if words else ''
    return values


def metadata(backend):
    prefix = 'nf' if backend == 'nftables' else 'ip'
    result = {}
    for path in sorted((ROOT / 'modules' / prefix).glob('*.sh')):
        # Reading a literal heredoc does not execute unselected modules.
        text = path.read_text()
        match = re.search(r"cat << 'EOF'\n(.*?)\nEOF", text, re.S)
        require(match is not None, f"Missing literal metadata: {path}")
        m = dict(line.split('=', 1) for line in match[1].splitlines() if '=' in line)
        m['path'] = str(path)
        m['function'] = path.stem
        m['defaults'] = dict(pair.split('=', 1) for pair in m.get('DEFAULTS', '').split())
        result[m['ID']] = m
    return result


CORE_DEFAULTS = {
    'PROFILE': 'host-minimal', 'MODULES_ONLY': '', 'MODULES_EXCLUDE': '',
    'FAMILY_POLICY': 'dual', 'NF_TABLE_NAME': 'firewall_main', 'NF_TABLE_FAMILY': 'inet',
    'HOST_SERVICES': 'true', 'ROUTED_POLICY': 'drop', 'CONTAINER_POLICY': 'off',
    'DOCKER_BACKEND': 'auto', 'IPTABLES_FRONTEND': 'auto', 'ACCESS_POLICY': '', 'PRIVILEGED_BYPASS': 'false',
    'STATE_CAPACITY': '8192', 'SSH_METER_TIMEOUT': '1m', 'ADMIN_SOURCES': '',
    'BYPASS_SOURCE_IPS': '', 'BYPASS_SOURCE_DOMAINS': '', 'DNS_ALLOWED_CIDRS': '',
    'GEO_IPV6_POLICY': '', 'DOCKER_INPUT_COMPAT': 'false', 'DOCKER_CHAIN_AUTORECOVER': 'false',
}
PROFILES = {
    'host-minimal': ['tcp_ssh'], 'web': ['tcp_ssh', 'http_https_protect'],
    'games': ['tcp_ssh', 'l4d2_packet_validation', 'l4d2_a2s_filters', 'l4d2_udp_base'],
    'vpn-gateway': ['tcp_ssh', 'openvpn_server'],
}
GAME = {'l4d2_udp_base', 'l4d2_packet_validation', 'l4d2_a2s_filters'}


def splitlist(value):
    return [x for x in re.split(r'[,;\s]+', value) if x]


def ports(value):
    require(bool(re.fullmatch(r'[0-9]+(?::[0-9]+)?(?:,[0-9]+(?::[0-9]+)?)*', value)), 'Invalid port list')
    out = []
    for p in value.split(','):
        ends = [int(i) for i in p.split(':')]
        require(all(1 <= i <= 65535 for i in ends) and ends[0] <= ends[-1], 'Invalid port range')
        out.append((ends[0], ends[-1]))
    require(sum(1 if a == b else 2 for a, b in out) <= 15, 'At most 15 multiport entries (range counts twice)')
    return out


def duration(value):
    require(bool(re.fullmatch(r'[1-9][0-9]{0,6}[smhdw]', value)), 'Invalid duration')
    return int(value[:-1]) * {'s':1,'m':60,'h':3600,'d':86400,'w':604800}[value[-1]]


def network(value):
    try:
        return ipaddress.ip_network(value, strict=True)
    except ValueError as e:
        raise PolicyError(f"Invalid IP/CIDR: {value}") from e


def interface(value):
    require(bool(re.fullmatch(r'[a-zA-Z0-9_.:-]{1,15}', value)), f"Invalid interface: {value}")
    return value


def access_file(path, privileged=False):
    if not path:
        return {'host': [], 'forward': [], 'containers': []}
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if privileged:
        trusted(p)
    return validate_access(json.loads(p.read_text()))


def validate_access(data):
    require(isinstance(data, dict) and set(data) <= {'host', 'forward', 'containers'}, 'Invalid access policy sections')
    for section in ('host', 'forward', 'containers'):
        data.setdefault(section, [])
        require(isinstance(data[section], list) and len(data[section]) <= 256, 'Too many grants')
        for g in data[section]:
            require(isinstance(g, dict) and all(isinstance(v, str) for v in g.values()), 'Grant must be an object with string values')
            keys = {'group', 'source', 'destination', 'protocol', 'ports', 'input'}
            if section != 'host':
                keys |= {'output'}
            if section == 'containers':
                keys |= {'public_destination', 'public_ports', 'service'}
            if section == 'containers' and g.get('service') == 'l4d2_udp_base':
                keys.add('role')
                require(g.get('role') in ('gameserver', 'sourcetv'), 'Game container grant requires role=gameserver or sourcetv')
            require(isinstance(g, dict) and set(g) == keys, f"{section} grant needs exactly {sorted(keys)}")
            require(bool(re.fullmatch(r'[a-zA-Z0-9_-]{1,32}', g['group'])), 'Invalid group')
            s, d = network(g['source']), network(g['destination'])
            require(s.version == d.version, 'Grant families must match')
            require(g['protocol'] in ('tcp', 'udp'), 'Only explicit tcp/udp grants supported')
            ports(g['ports'])
            interface(g['input'])
            if section != 'host':
                interface(g['output'])
            if section == 'containers':
                pub = network(g['public_destination'])
                require(pub.version == s.version and pub.prefixlen == pub.max_prefixlen, 'Public destination must be one address')
                ports(g['public_ports'])
                private, public = ports(g['ports']), ports(g['public_ports'])
                require(len(private) == len(public) and all(b-a == d-c for (a,b),(c,d) in zip(private,public)), 'Public/internal ranges must align with equal lengths')
                require(g['service'] in ('tcp_ssh', 'http_https_protect', 'l4d2_udp_base', 'allowlist_ports', 'openvpn_server'), 'Unsupported container service')
                require(g['protocol'] == ('udp' if g['service'] == 'l4d2_udp_base' else g['protocol']), 'Game service requires UDP')
                if g['service'] in ('tcp_ssh', 'http_https_protect'):
                    require(g['protocol'] == 'tcp', 'Administrative/web module requires TCP; grant QUIC independently')
    return data


class Configuration:
    def __init__(self, backend, path=None, overrides=None, only=None, skip=None, profiles=None,
                 privileged=False, normalized=False, access_data=None, explicit_keys=None):
        self.backend = backend
        self.catalog = metadata(backend)
        if path and privileged:
            trusted(path)
        supplied = assignments(Path(path).read_text()) if path else {}
        supplied.update(overrides or {})
        input_keys = set(supplied)
        self.explicit = set(input_keys if explicit_keys is None else explicit_keys)
        known = set(CORE_DEFAULTS)
        known.add('TYPECHAIN')  # Accepted only at the user-input boundary.
        # Both engines share the accepted vocabulary. Unsupported options are rejected below.
        for be in ('iptables', 'nftables'):
            for m in metadata(be).values():
                known.update(m.get('REQUIRED_VARS', '').split())
                known.update(m.get('OPTIONAL_VARS', '').split())
                known.update(m['defaults'])
        require(not (set(supplied) - known), f"Unknown options: {sorted(set(supplied) - known)}")
        self.values = dict(CORE_DEFAULTS)
        self.values.update(supplied)
        v = self.values
        if normalized:
            require('TYPECHAIN' not in supplied, 'Normalized configuration cannot contain TYPECHAIN')
            require(not supplied.get('ACCESS_POLICY'), 'Normalized configuration stores parsed access grants, not an ACCESS_POLICY path')
            require(access_data is not None, 'Normalized configuration requires its parsed access policy')
        elif 'TYPECHAIN' in supplied:
            require(v['TYPECHAIN'] in ('0', '1', '2'), 'TYPECHAIN must be 0/1/2')
            translated = {'HOST_SERVICES': 'false' if v['TYPECHAIN'] == '1' else 'true',
                          'CONTAINER_POLICY': 'off' if v['TYPECHAIN'] == '0' else 'restrict'}
            for k, value in translated.items():
                require(k not in supplied or v[k] == value, f"Ambiguous TYPECHAIN/{k}; remove TYPECHAIN")
                v[k] = value
            supplied.pop('TYPECHAIN')
            v.pop('TYPECHAIN', None)
        aliases = {}
        for ident, m in self.catalog.items():
            for a in [ident, *m.get('ALIASES', '').split()]:
                require(a not in aliases, f"Ambiguous alias {a}")
                aliases[a] = ident
        prefix = 'nf' if backend == 'nftables' else 'ip'
        core = {'chain_setup', 'finalize', 'loopback', 'ip_loopback', prefix + '_chain_setup', prefix + '_finalize'}
        def resolve(items):
            result = set()
            for item in items:
                if item in core:
                    continue
                require(item in aliases, f"Unknown module: {item}")
                result.add(aliases[item])
            return result
        # CLI replaces selection in file, including an intentional empty --only.
        selection = only if only is not None else splitlist(v['MODULES_ONLY'])
        chosen_profiles = profiles if profiles is not None else splitlist(v['PROFILE'])
        selected = resolve(selection)
        # An explicit empty CLI selection means core-only. An absent CLI
        # selection with MODULES_ONLY unset/empty retains profile fallback.
        if only is None and not selection:
            require(chosen_profiles, 'Specify a profile or explicit module list')
            for profile in chosen_profiles:
                require(profile in PROFILES, f"Unknown profile: {profile}")
                selected |= resolve(PROFILES[profile])
        excluded = resolve(skip if skip is not None else splitlist(v['MODULES_EXCLUDE']))
        require(not (core & set(skip or splitlist(v['MODULES_EXCLUDE']))), 'Core cannot be excluded')
        selected -= excluded
        self.selected = sorted(selected, key=lambda x: Path(self.catalog[x]['path']).name)
        names = {x.removeprefix(prefix + '_') for x in selected}
        require(not {'openvpn_server', 'openvpn_sitetosite'} <= names, 'Conflicting VPN adaptations')
        require(not (names & GAME) or GAME <= names, 'Game modules require validation, A2S and UDP base together')
        require('l4d2_tcpfilter_chain' not in names or 'l4d2_tcp_protect' in names, 'tcpfilter requires l4d2_tcp_protect')
        self.names = names
        for ident in self.selected:
            # Shared VPN options must have the same explicit defaults in both engines.
            if ident.endswith(('openvpn_server', 'openvpn_sitetosite')):
                peer = metadata('iptables' if backend == 'nftables' else 'nftables')
                alternate = ('ip_' if backend == 'nftables' else 'nf_') + ident.split('_', 1)[1]
                for k, value in peer[alternate]['defaults'].items():
                    # TYPECHAIN is a schema-1/input compatibility field. The
                    # renderer injects it into its private module environment;
                    # never import a peer module's legacy default into the
                    # canonical schema-2 bundle.
                    if k != 'TYPECHAIN':
                        v.setdefault(k, value)
            for k, value in self.catalog[ident]['defaults'].items():
                if k != 'TYPECHAIN' and k not in v:
                    v[k] = value
        # Derived optional defaults preserve intentionally empty values.
        for suffix in ('SRC_RATE', 'SRC_BURST', 'GLOBAL_RATE', 'GLOBAL_BURST'):
            if 'UDP_NEW_' + suffix in v:
                v.setdefault('SOURCETV_UDP_NEW_' + suffix, v['UDP_NEW_' + suffix])
        for ident in self.selected:
            for k in self.catalog[ident].get('REQUIRED_VARS', '').split():
                if k == 'TYPECHAIN':  # Render adapter supplies this per target.
                    continue
                require(v.get(k, '') != '', f'{ident} requires nonempty {k}')
        if self.names & GAME:
            for key, value in {'NFT_UDP_NEW_METER_TIMEOUT':'5s','NFT_UDP_EST_METER_TIMEOUT':'5s','NFT_A2S_METER_TIMEOUT':'5s','NFT_LOGIN_METER_TIMEOUT':'1s'}.items():
                v.setdefault(key,value)
        if 'http_https_protect' in self.names:
            v.setdefault('NFT_HTTP_HTTPS_METER_TIMEOUT','5m')
        self.validate()
        self.access = validate_access(access_data) if normalized else access_file(v['ACCESS_POLICY'], privileged)
        # ACCESS_POLICY is an input path. Persist the parsed ACL separately so
        # later partial operations never reopen a mutable file.
        v['ACCESS_POLICY'] = ''
        require(not self.access['containers'] or v['CONTAINER_POLICY'] == 'restrict', 'Container grants require CONTAINER_POLICY=restrict')
        require(not self.access['forward'] or v['ROUTED_POLICY'] == 'drop', 'Forward grants require ROUTED_POLICY=drop')
        if v['FAMILY_POLICY'] != 'dual':
            require(all(network(g['source']).version == 4 for section in self.access.values() for g in section), 'IPv6 grants conflict with ipv4-block-ipv6')
        for g in self.access['containers']:
            require(g['service'] in names, f"Container service {g['service']} must be selected")
            if g['service'] == 'openvpn_server':
                require(g['protocol'] == v['OVPNSRV_PROTO'], 'Container VPN protocol differs from OVPNSRV_PROTO')
        if privileged:
            for p in [ROOT, ROOT / 'core', ROOT / 'modules', ROOT / 'modules/common_nft.sh', ROOT / 'core/render.sh', *[Path(self.catalog[i]['path']) for i in self.selected]]:
                trusted(p)
        self.validate_geo(privileged)
        self.resolve_dns()

    @classmethod
    def from_normalized(cls, backend, config, selected, access, privileged=False, explicit_keys=None):
        """Revalidate canonical state without interpreting legacy input again."""
        values = dict(config)
        values['ACCESS_POLICY'] = ''
        return cls(backend, overrides=values, only=selected, privileged=privileged,
                   normalized=True, access_data=access, explicit_keys=explicit_keys)

    def validate(self):
        v = self.values
        require(v['FAMILY_POLICY'] in ('dual', 'ipv4-block-ipv6'), 'FAMILY_POLICY must be dual or ipv4-block-ipv6')
        require(v['NF_TABLE_FAMILY'] == 'inet', 'Only NF_TABLE_FAMILY=inet supported')
        require(bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,30}', v['NF_TABLE_NAME'])), 'Invalid table name')
        require(v['NF_TABLE_NAME'] != BOOT_GUARD_TABLE,
                f'NF_TABLE_NAME={BOOT_GUARD_TABLE} is reserved for the boot guard')
        require(v['ROUTED_POLICY'] in ('drop', 'unmanaged'), 'Invalid routed policy')
        require(v['CONTAINER_POLICY'] in ('off', 'restrict'), 'Invalid container policy')
        require(v['IPTABLES_FRONTEND'] in ('auto', 'legacy', 'nft'), 'IPTABLES_FRONTEND must be auto/legacy/nft')
        require(v['DOCKER_BACKEND'] in ('auto', 'iptables', 'nftables', 'none'), 'Invalid Docker backend')
        require(v['DOCKER_CHAIN_AUTORECOVER'] == 'false', 'Docker restart removed; set DOCKER_CHAIN_AUTORECOVER=false')
        require(v['DOCKER_INPUT_COMPAT'] == 'false', 'DOCKER_INPUT_COMPAT retired; use CONTAINER_POLICY explicitly')
        if self.backend == 'iptables' and self.names & GAME:
            require(v['FAMILY_POLICY'] == 'ipv4-block-ipv6', 'iptables game payload matching supports IPv4 only; choose ipv4-block-ipv6 or nftables dual')
        require(not v['BYPASS_SOURCE_IPS'] or ('whitelist' in self.names and v['PRIVILEGED_BYPASS'] == 'true'), 'BYPASS_SOURCE_IPS needs whitelist and explicit PRIVILEGED_BYPASS=true')
        require(not v['BYPASS_SOURCE_DOMAINS'] or ('whitelist' in self.names and v['PRIVILEGED_BYPASS'] == 'true' and v['DNS_ALLOWED_CIDRS']), 'DNS bypass requires explicit privilege and DNS_ALLOWED_CIDRS')
        for k, value in v.items():
            require('\n' not in value and '\x00' not in value, f"Invalid multiline value {k}")
            if k.startswith('LOG_PREFIX_') or k.endswith('_LOG_PREFIX') or k == 'FIREWALL_LOG_HOST_ALIAS':
                require(bool(re.fullmatch(r'[A-Za-z0-9_ :.=/-]{0,28}', value)), f"Unsafe/long log prefix {k}")
            if value and (k.endswith('_PORTS') or k in ('SSH_PORT', 'SSH_DOCKER', 'TCP_DOCKER', 'UDP_DOCKER', 'OVPNSRV_PORT')):
                ports(value)
            if k.startswith('ENABLE_') or k.endswith(('_ENABLED', '_ENABLE_NAT', '_ALIAS_SNAT')) or k in ('HOST_SERVICES', 'PRIVILEGED_BYPASS'):
                require(value in ('true', 'false'), f"{k} must be true/false")
            if value and (k.endswith('_INTERFACE') or k in ('OVPNSRV_INTERFACE', 'OVPNS2S_INTERFACE')):
                interface(value)
            if value and (k.endswith(('_SUBNET', '_SUBNETS', '_TARGETS')) or k in ('BYPASS_SOURCE_IPS', 'ADMIN_SOURCES', 'DNS_ALLOWED_CIDRS')):
                for x in splitlist(value):
                    network(x)
            if value and k.endswith(('_REAL_IP', '_ALIAS_IP')):
                try:
                    ipaddress.IPv4Address(value)
                except ValueError as e:
                    raise PolicyError(f'{k} must be a plain IPv4 address') from e
            if k.endswith('_TIMEOUT'):
                require(bool(re.fullmatch(r'[1-9][0-9]{0,4}[smhdw]', value)), f"Invalid duration {k}")
            if k.endswith(('_BURST', '_RATE')) and k not in ('SSH_RATE', 'HTTP_HTTPS_RATE'):
                require(bool(re.fullmatch(r'[0-9]{1,7}', value)) and int(value) <= 1000000, f"Invalid numeric {k}")
        if 'OVPNSRV_PORT' in v:
            require(v['OVPNSRV_PORT'].isdigit() and 1 <= int(v['OVPNSRV_PORT']) <= 65535, 'OVPNSRV_PORT must be one port')
        for key in ('SSH_BURST', 'HTTP_HTTPS_BURST'):
            if key in v:
                require(int(v[key]) > 0, f'{key} must be positive')
        require(16 <= int(v['STATE_CAPACITY']) <= 65535, 'STATE_CAPACITY must be 16..65535')
        for key in ('SSH_RATE', 'HTTP_HTTPS_RATE'):
            if key in v:
                require(bool(re.fullmatch(r'[1-9][0-9]{0,5}/(s|sec|second|min|minute|hour|day)', v[key])), f"Invalid {key}")
                v[key] = v[key].replace('/s', '/sec') if v[key].endswith('/s') else v[key]
                if self.backend == 'iptables':
                    v[key] = v[key].replace('/second', '/sec').replace('/minute', '/min')
        for rate_key, burst_key, timeout_key in (('SSH_RATE','SSH_BURST','SSH_METER_TIMEOUT'), ('HTTP_HTTPS_RATE','HTTP_HTTPS_BURST','NFT_HTTP_HTTPS_METER_TIMEOUT')):
            if rate_key not in v:
                continue
            count, unit = v[rate_key].split('/')
            seconds = {'s':1,'sec':1,'second':1,'min':60,'minute':60,'hour':3600,'day':86400}[unit]
            minimum = math.ceil(int(v[burst_key]) * seconds / int(count))
            if timeout_key not in self.explicit and duration(v[timeout_key]) < minimum:
                v[timeout_key] = str(minimum) + 's'
            require(minimum <= duration(v[timeout_key]) <= 86400, f'{timeout_key} must cover full token refill and be <=24h')
        if self.names & GAME:
            require(v['L4D2_CMD_LIMIT'].isdigit() and 10 <= int(v['L4D2_CMD_LIMIT']) <= 10000, 'L4D2_CMD_LIMIT must be 10..10000')
            groups = {
                'NFT_A2S_METER_TIMEOUT': ('A2S_INFO','A2S_PLAYERS','A2S_RULES','STEAM_GROUP'),
                'NFT_LOGIN_METER_TIMEOUT': ('L4D2_LOGIN',),
                'NFT_UDP_NEW_METER_TIMEOUT': ('UDP_NEW_SRC','UDP_NEW_GLOBAL','SOURCETV_UDP_NEW_SRC','SOURCETV_UDP_NEW_GLOBAL'),
            }
            for timeout_key, rates in groups.items():
                minimum = max([1, *[math.ceil(int(v[k+'_BURST']) / int(v[k+'_RATE'])) for k in rates if int(v[k+'_RATE']) and int(v[k+'_BURST'])]])
                if timeout_key not in self.explicit and duration(v[timeout_key]) < minimum:
                    v[timeout_key] = str(minimum) + 's'
                require(minimum <= duration(v[timeout_key]) <= 86400, f'{timeout_key} must cover full token refill and be <=24h')
            minimum = math.ceil((int(v['L4D2_CMD_LIMIT']) + 30) / (int(v['L4D2_CMD_LIMIT']) + 10))
            require(minimum <= duration(v['NFT_UDP_EST_METER_TIMEOUT']) <= 86400, 'Invalid established UDP state lifetime')
        for k in ('OVPNSRV_PROTO',):
            require(v.get(k, 'udp') in ('tcp', 'udp'), f"Invalid {k}")
        # No silent interpretation of global Docker port lists.
        for k in ('SSH_DOCKER', 'TCP_DOCKER', 'UDP_DOCKER'):
            require(not v.get(k), f"{k} needs migration to explicit containers grants (public and internal ports)")
        if 'geo_country_filter' in self.names and v.get('GEO_POLICY_MODE') != 'off':
            require(v['FAMILY_POLICY'] != 'dual' or v['GEO_IPV6_POLICY'] == 'deny', 'GeoIP is IPv4 only; set GEO_IPV6_POLICY=deny explicitly or block IPv6 services')
            for k in ('GEO_POLICY_ALLOWED_COUNTRIES', 'GEO_POLICY_DENIED_COUNTRIES'):
                require(bool(re.fullmatch(r'(?:[A-Z]{2}(?:,[A-Z]{2})*)?', v.get(k, ''))), f"Invalid {k}")
        if self.names & GAME:
            require(not v.get('BYPASS_UDP_PORTS'), 'Game controls conflict with unrestricted BYPASS_UDP_PORTS; use scoped access')
            gp, tp = ports(v['L4D2_GAMESERVER_UDP_PORTS']), ports(v['L4D2_SOURCETV_UDP_PORTS'])
            require(not any(max(a,c) <= min(b,d) for a,b in gp for c,d in tp), 'GameServer and SourceTV ports overlap')
        controlled = []
        for module, key in (('tcp_ssh','SSH_PORT'), ('http_https_protect','HTTP_HTTPS_PORTS'), ('l4d2_tcp_protect','L4D2_GAMESERVER_TCP_PORTS')):
            if module in self.names and v.get(key):
                require(not any(max(a,c) <= min(b,d) for a,b in ports(v[key]) for c,d in controlled), 'TCP service controls overlap; assign distinct ports')
                controlled += ports(v[key])
        if 'allowlist_ports' in self.names and v.get('BYPASS_TCP_PORTS'):
            require(not any(max(a,c) <= min(b,d) for a,b in ports(v['BYPASS_TCP_PORTS']) for c,d in controlled), 'TCP allowlist overlaps a controlled service')
        for k in ('OVPNSRV_LOG_ENABLED', 'OVPNS2S_LOG_ENABLED'):
            require(v.get(k, 'false') == 'false', f"{k} unsupported; use explicit scoped counters")
        require(not v.get('OVPNSRV_DOCKER_INTERFACE'), 'VPN in Docker: use containers grants; tunnel forwarding requires host deployment')
        for scope in ('OVPNSRV', 'OVPNS2S'):
            if v.get(scope + '_ENABLE_NAT') == 'true':
                require(v.get(scope + ('_LAN_INTERFACE' if scope == 'OVPNSRV' else '_LOCAL_INTERFACE')), 'NAT requires explicit output interface')
        alias = v.get('OVPNS2S_ROUTER_ALIAS', '')
        for pair in splitlist(alias.replace(';', '|')):
            fields = pair.split('|')
            require(len(fields) == 2 and all('/' not in x and network(x).version == 4 and network(x).num_addresses == 1 for x in fields), 'Invalid router alias pair')

    def validate_geo(self, privileged):
        v = self.values
        if 'geo_country_filter' not in self.names or v.get('GEO_POLICY_MODE') == 'off':
            return
        def resolved(value):
            p = Path(value)
            return p if p.is_absolute() else ROOT / p
        data = resolved(v['GEO_POLICY_DATA_DIR'])
        files = [resolved(v[k]) for k in ('GEO_POLICY_MANUAL_ALLOW_FILE', 'GEO_POLICY_MANUAL_DENY_FILE') if v.get(k)]
        for code in splitlist(v.get('GEO_POLICY_ALLOWED_COUNTRIES','') + ',' + v.get('GEO_POLICY_DENIED_COUNTRIES','')):
            files.append(data / (code + '.ipv4.txt'))
        for p in files:
            require(p.is_file(), f'Missing GeoIP data: {p}')
            if privileged:
                trusted(p)
            for line in p.read_text().splitlines():
                value = line.split('#', 1)[0].strip()
                if value:
                    require(network(value).version == 4, f'GeoIP must contain canonical IPv4 CIDRs: {p}')

    def resolve_dns(self):
        import socket
        v = self.values
        allowed = [network(x) for x in splitlist(v['DNS_ALLOWED_CIDRS'])]
        resolved = splitlist(v['BYPASS_SOURCE_IPS'])
        for domain in splitlist(v['BYPASS_SOURCE_DOMAINS']):
            require(bool(re.fullmatch(r'[A-Za-z0-9.-]{1,253}', domain)), 'Invalid DNS name')
            try:
                ips = {row[4][0] for row in socket.getaddrinfo(domain, None)}
            except OSError as e:
                raise PolicyError(f"DNS failed for {domain}: {e}") from e
            require(ips and len(ips) <= 32, 'Unexpected DNS answer count')
            for ip in ips:
                a = ipaddress.ip_address(ip)
                require(any(a.version == n.version and a in n for n in allowed), f"DNS answer outside DNS_ALLOWED_CIDRS: {domain}")
                resolved.append(ip)
        v['BYPASS_SOURCE_IPS'] = ' '.join(sorted(set(resolved)))
        v['BYPASS_SOURCE_DOMAINS'] = ''
