#!/usr/bin/python3
"""Real Netfilter tests. MUST run inside tests/isolated-run.sh."""
import copy
import json
import os
from pathlib import Path
import signal
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import Configuration, PolicyError, ROOT
from core.compiler import generate, short
from core.store import Store
from core import engine

assert os.readlink('/proc/self/ns/net') != os.environ['SUITE_HOST_NETNS'], 'Host network forbidden'
STATE = Path(os.environ['SUITE_TEST_STATE'])
FRONTEND = os.environ.get('SUITE_TEST_FRONTEND','auto')


def run(*argv, text=None):
    r = subprocess.run(argv, input=text, text=True, capture_output=True, check=True)
    return r.stdout


class Peer:
    def __init__(self, interface, subnet):
        self.p = subprocess.Popen(['unshare', '--net', 'python3', '-u', '-c', 'import time; print("ready", flush=True); time.sleep(3600)'], stdout=subprocess.PIPE, text=True)
        assert self.p.stdout.readline().strip() == 'ready'
        self.interface = interface
        run('ip', 'link', 'add', interface, 'type', 'veth', 'peer', 'name', interface+'p')
        run('ip', 'link', 'set', interface+'p', 'netns', str(self.p.pid))
        run('sysctl','-q','-w','net.ipv6.conf.all.disable_ipv6=0')
        run('sysctl','-q','-w','net.ipv6.conf.default.disable_ipv6=0')
        self.cmd('sysctl','-q','-w','net.ipv6.conf.all.disable_ipv6=0')
        self.cmd('sysctl','-q','-w','net.ipv6.conf.default.disable_ipv6=0')
        self.subnet = subnet
        run('ip', 'addr', 'add', f'10.{subnet}.0.1/24', 'dev', interface)
        run('ip', '-6', 'addr', 'add', f'fd00:{subnet}::1/64', 'dev', interface, 'nodad')
        run('ip', 'link', 'set', interface, 'up')
        self.cmd('ip', 'link', 'set', 'lo', 'up')
        self.cmd('ip', 'addr', 'add', f'10.{subnet}.0.2/24', 'dev', interface+'p')
        self.cmd('ip', 'addr', 'add', f'10.{subnet}.0.3/24', 'dev', interface+'p')
        self.cmd('ip', '-6', 'addr', 'add', f'fd00:{subnet}::2/64', 'dev', interface+'p', 'nodad')
        self.cmd('ip', '-6', 'addr', 'add', f'fd00:{subnet}::3/64', 'dev', interface+'p', 'nodad')
        self.cmd('ip', 'link', 'set', interface+'p', 'up')
        self.cmd('ip', 'route', 'add', 'default', 'via', f'10.{subnet}.0.1')
        self.cmd('ip', '-6', 'route', 'add', 'default', 'via', f'fd00:{subnet}::1')

    def cmd(self, *args, text=None):
        return run('nsenter', '-t', str(self.p.pid), '-n', *args, text=text)

    def python(self, code):
        return self.cmd('python3', '-c', code)

    def tcp(self, port, family=4, source=None, dest=None):
        dest = dest or (f'10.{self.subnet}.0.1' if family == 4 else f'fd00:{self.subnet}::1')
        source = source or (f'10.{self.subnet}.0.2' if family == 4 else f'fd00:{self.subnet}::2')
        code = f'''import socket
s=socket.socket(socket.AF_INET{6 if family == 6 else ''},socket.SOCK_STREAM)
s.settimeout(.35)
s.bind(({source!r},0))
try:
 s.connect(({dest!r},{port})); print('OK')
except OSError: print('BLOCK')
finally: s.close()
'''
        return self.python(code).strip() == 'OK'

    def udp(self, port, payloads, family=4, options=False):
        dest = f'10.{self.subnet}.0.1' if family == 4 else f'fd00:{self.subnet}::1'
        code = f'''import socket,json
s=socket.socket(socket.AF_INET{6 if family == 6 else ''},socket.SOCK_DGRAM)
s.settimeout(.02)
if {options!r}: s.setsockopt(socket.IPPROTO_IP,socket.IP_OPTIONS,b'\x01'*4)
result=[]
for h in { [p.hex() for p in payloads]!r}:
 s.sendto(bytes.fromhex(h),({dest!r},{port}))
 try: s.recvfrom(65535);result.append(True)
 except OSError: result.append(False)
print(json.dumps(result))
'''
        return json.loads(self.python(code))

    def close(self):
        self.p.terminate(); self.p.wait()
        self.p.stdout.close()


class Server:
    def __init__(self, port, udp=False, family=4):
        self.s = socket.socket(socket.AF_INET6 if family == 6 else socket.AF_INET, socket.SOCK_DGRAM if udp else socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if family == 6:
            self.s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        self.s.bind(('::' if family == 6 else '0.0.0.0', port))
        self.s.settimeout(.1)
        if not udp: self.s.listen(256)
        self.done = False
        def serve():
            while not self.done:
                try:
                    if udp:
                        data, address = self.s.recvfrom(65535); self.s.sendto(data or b'ok', address)
                    else:
                        c, _ = self.s.accept(); c.close()
                except (TimeoutError, OSError): pass
        self.t = threading.Thread(target=serve, daemon=True); self.t.start()
    def close(self):
        self.done=True; self.s.close(); self.t.join()


class KernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.peer = Peer('wan0', 20)
        cls.lan = Peer('lan0', 30)
        server_code = '''import socket,select
socks=[]
for f in (socket.AF_INET,socket.AF_INET6):
 for kind in (socket.SOCK_STREAM,socket.SOCK_DGRAM):
  for port in (18443,18444):
   s=socket.socket(f,kind)
   s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
   if f==socket.AF_INET6:s.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
   s.bind(('::' if f==socket.AF_INET6 else '0.0.0.0',port))
   if kind==socket.SOCK_STREAM:s.listen(128)
   socks.append(s)
print('ready',flush=True)
while True:
 for s in select.select(socks,[],[])[0]:
  if s.type==socket.SOCK_STREAM:
   c,a=s.accept()
   try:c.sendall(a[0].encode())
   except OSError:pass
   c.close()
  else:data,a=s.recvfrom(65535);s.sendto(data,a)
'''
        cls.lanserver=subprocess.Popen(['nsenter','-t',str(cls.lan.p.pid),'-n','python3','-u','-c',server_code],stdout=subprocess.PIPE,text=True)
        assert cls.lanserver.stdout.readline().strip()=='ready'
        cls.servers = [Server(p, udp, f) for f in (4,6) for p,udp in ((18080,False),(18081,False),(22222,False),(27015,True),(27020,True))]
        print('VERSIONS:', engine.inspect('nftables',FRONTEND)['versions'], run('nft','--version').strip(), run('uname','-r').strip(), flush=True)
        run('sysctl','-q','-w','net.ipv4.ip_forward=1')
        run('sysctl','-q','-w','net.ipv6.conf.all.forwarding=1')

    @classmethod
    def tearDownClass(cls):
        for s in cls.servers: s.close()
        cls.lanserver.terminate(); cls.lanserver.wait(); cls.lanserver.stdout.close()
        cls.lan.close()
        cls.peer.close()

    def setUp(self):
        self.store = Store(STATE)
        with self.store.lock():
            self.store.rollback_locked()
            current=self.store.get('current')
            if current:
                self.store.apply_locked({**current,'disabled':True},local=True)
        # A foreign rule with a counter and independent persistence sentinel.
        run('nft','-f','-', text='add table inet outsider\nadd chain inet outsider observe { type filter hook input priority -20; policy accept; }\nadd rule inet outsider observe tcp dport 65000 counter drop\n')
        self.foreign = run('nft','-s','list','table','inet','outsider')
        self.file = STATE / 'third-party.conf'; self.file.write_text('foreign config\n'); self.file.chmod(0o600)

    def tearDown(self):
        with self.store.lock():
            self.store.rollback_locked()
            current = self.store.get('current')
            if current:
                self.store.apply_locked({**current,'disabled':True},local=True)
        self.assertEqual(run('nft','-s','list','table','inet','outsider'),self.foreign)
        self.assertEqual(self.file.read_text(),'foreign config\n')
        run('nft','delete','table','inet','outsider')
        self.store.delete('persisted')

    def config(self, backend, profile='web', **values):
        return Configuration(backend, profiles=[profile], overrides={'IPTABLES_FRONTEND':FRONTEND,'SSH_PORT':'22222','HTTP_HTTPS_PORTS':'18080',**values}, privileged=True)

    def apply(self, backend, profile='web', **values):
        p = generate(self.config(backend, profile, **values))
        with self.store.lock():
            self.store.apply_locked(p,local=True)
        return p

    def disable(self):
        with self.store.lock():
            p=self.store.get('current')
            if p: self.store.apply_locked({**p,'disabled':True}, local=True)

    def test_01_invalid_composition_and_kernel_candidate_preserve_active(self):
        for backend in ('nftables','iptables'):
            self.apply(backend)
            before = self.rules(backend)
            for opts in ({'SSH_PORT':'99999'}, {'MODULES_ONLY':'typo'}):
                with self.assertRaises(PolicyError): generate(self.config(backend, **opts))
                self.assertEqual(self.rules(backend), before)
            bad = copy.deepcopy(self.store.get('current'))
            if backend=='nftables': bad['objects'][0]['text']+='add rule inet firewall_main input nonsense\n'
            else: bad['families']['6']['filter'][short('input')].append(['--invalid-option'])
            with self.store.lock(), self.assertRaises(PolicyError): self.store.apply_locked(bad,local=True)
            self.assertEqual(self.rules(backend), before)
            self.disable()

    def rules(self, backend):
        if backend=='nftables': return run('nft','-s','list','ruleset')
        return tuple(re.sub(r'\[\d+:\d+\]', '[0:0]', '\n'.join(line for line in run(cmd).splitlines() if not line.startswith('#'))) for cmd in (engine.ipcmd(4,'-save'),engine.ipcmd(6,'-save')))

    def test_02_web_admin_both_families_and_idempotence(self):
        for backend in ('nftables','iptables'):
            self.apply(backend)
            for f in (4,6):
                self.assertTrue(self.peer.tcp(18080,f), (backend,f,'web'))
                self.assertTrue(self.peer.tcp(22222,f), (backend,f,'SSH'))
                self.assertFalse(self.peer.tcp(18081,f), (backend,f,'blocked'))
            self.apply(backend)
            if backend=='nftables':
                self.assertEqual(run('nft','list','tables').count('table inet firewall_main'),1)
            else:
                self.assertIn(self.store.get('current')['config']['IPTABLES_FRONTEND'],('nft','legacy'))
                for cmd in (engine.ipcmd(4,'-save'),engine.ipcmd(6,'-save')):
                    self.assertEqual(run(cmd).count('--comment "l4d2-suite:integration"'),2)
            self.disable()

    def test_03_ssh_per_source_and_logs_bounded(self):
        for backend in ('nftables','iptables'):
            self.apply(backend,SSH_RATE='1/hour',SSH_BURST='1')
            self.assertTrue(self.peer.tcp(22222))
            self.assertFalse(self.peer.tcp(22222))
            self.assertTrue(self.peer.tcp(22222, source='10.20.0.3'))
            # 40 new connections in a tight burst, independently of handshake timeout.
            self.peer.python('''import socket,time
sockets=[]
for i in range(40):
 s=socket.socket();s.setblocking(False);s.connect_ex(('10.20.0.1',22222));sockets.append(s)
time.sleep(.1)
''')
            if backend=='nftables':
                rules = json.loads(run('nft','-j','list','chain','inet','firewall_main','input_admin'))['nftables']
                logs=[];drops=[]
                for item in rules:
                    r=item.get('rule',{}); ex=r.get('expr',[])
                    count=sum(x.get('counter',{}).get('packets',0) for x in ex)
                    if any('log' in x for x in ex): logs.append(count)
                    if any('drop' in x for x in ex): drops.append(count)
                self.assertTrue(logs and sum(logs)<=12, logs)
                self.assertGreater(sum(drops),20,drops)
            else:
                text=run(engine.ipcmd(4,'-save'),'-c')
                lines=[x for x in text.splitlines() if '-j LOG' in x and 'SSH_ABUSE' in x]
                count=sum(int(x.split(']')[0][1:].split(':')[0]) for x in lines)
                self.assertLessEqual(count,12)
            self.disable()

    def test_04_game_udp_established_validation_a2s_and_tv(self):
        for backend in ('nftables','iptables'):
            vals={'L4D2_CMD_LIMIT':'10','ENABLE_PACKET_NORMALIZATION_LOGS':'true','A2S_INFO_RATE':'1','A2S_INFO_BURST':'1'}
            if backend=='iptables': vals['FAMILY_POLICY']='ipv4-block-ipv6'
            self.apply(backend,'games',**vals)
            for f in ((4,6) if backend=='nftables' else (4,)):
                # Empty and oversize datagrams must not be accepted via established shortcut.
                result=self.peer.udp(27015,[b'x'*100,b'',b'x'*3000,b'x'*100],f)
                self.assertEqual(result,[True,False,False,True],(backend,f,result))
                a2s=b'\xff'*4+b'TSource Engine Query\x00'
                result=self.peer.udp(27015,[a2s]*4,f)
                self.assertEqual(result[0],True)
                self.assertLess(sum(result),4,(backend,f,result))
                self.assertTrue(self.peer.udp(27020,[b'\xff'*4+b'qconnect'+b'x'*11],f)[0],(backend,f,'TV handshake'))
                self.assertTrue(self.peer.udp(27015,[b'\xff'*4+b'qconnect'+b'x'*11],f)[0],(backend,f,'Game login'))
                result=self.peer.udp(27015,[b'x'*100]*120,f)
                self.assertLess(sum(result),120,(backend,f,'established bypass'))
                if f == 4:
                    self.assertEqual(self.peer.udp(27015,[b'x'*100,b''],options=True),[True,False], (backend,'IPv4 options must not bypass UDP length checks'))
            self.disable()

    def test_05_timed_rollback_and_explicit_confirmation(self):
        for backend in ('nftables','iptables'):
            self.apply(backend)
            self.assertTrue(self.peer.tcp(18080)) # Snapshot populated dynamic meters too.
            old=self.store.get('current')
            candidate=generate(self.config(backend,HTTP_HTTPS_PORTS='18081'))
            with self.store.lock():
                token=self.store.apply_locked(candidate,timeout=2,watchdog='process')
            self.assertTrue(self.peer.tcp(18081))
            time.sleep(2.4)
            self.assertFalse(self.peer.tcp(18081))
            self.assertEqual(self.store.get('current'),old)
            with self.store.lock():
                token=self.store.apply_locked(candidate,timeout=5,watchdog='process')
                self.store.confirm_locked(token)
            self.assertIsNone(self.store.get('pending'))
            self.assertTrue(self.peer.tcp(18081))
            self.disable()

    def test_06_interrupted_applicator_watchdog_survives(self):
        for backend in ('nftables','iptables'):
            self.apply(backend)
            old=self.store.get('current')
            code=f'''import os,signal,sys
sys.path.insert(0,{str(ROOT)!r})
from core.store import Store
from core.config import Configuration
from core.compiler import generate
from core import engine
s=Store({str(STATE)!r})
real=engine.execute
def interrupted(tx):
 real(tx)
 os.kill(os.getpid(),signal.SIGKILL)
engine.execute=interrupted
p=generate(Configuration({backend!r},profiles=['web'],overrides={{'IPTABLES_FRONTEND':{FRONTEND!r},'SSH_PORT':'22222','HTTP_HTTPS_PORTS':'18081'}},privileged=True))
with s.lock():s.apply_locked(p,timeout=2,watchdog='process')
'''
            r=subprocess.run(['python3','-I','-c',code],check=False)
            self.assertEqual(r.returncode,-signal.SIGKILL)
            time.sleep(2.5)
            self.assertEqual(self.store.get('current'),old)
            self.assertTrue(self.peer.tcp(18080))
            self.assertFalse(self.peer.tcp(18081))
            self.disable()

    def test_07_partial_table_failure_restores_both_families(self):
        from unittest.mock import patch
        self.apply('iptables')
        before=self.rules('iptables')
        candidate=generate(self.config('iptables',HTTP_HTTPS_PORTS='18081'))
        real=engine.execute
        def fail_after_first(tx):
            real(tx[:1])
            raise PolicyError('simulated applicator interruption after REAL IPv4 commit')
        with self.store.lock():
            with patch.object(engine,'execute',side_effect=fail_after_first):
                # Allow rollback to call the real writer; fault is only on initial apply.
                count=[0]
                def once(tx):
                    count[0]+=1
                    if count[0]==1: return fail_after_first(tx)
                    return real(tx)
                with patch.object(engine,'execute',side_effect=once), self.assertRaises(PolicyError):
                    self.store.apply_locked(candidate,local=True)
        self.assertEqual(self.rules('iptables'),before)

    def test_08_save_reload_and_selective_removal(self):
        from core.fw import main
        for backend in ('nftables','iptables'):
            self.apply(backend)
            with self.store.lock():self.store.put('persisted',self.store.get('current'))
            self.disable()
            main(['--state-dir',str(STATE),'--backend',backend,'load','--local'])
            self.assertTrue(self.peer.tcp(18080))
            main(['--state-dir',str(STATE),'--backend',backend,'apply','--remove','http_https_protect','--local'])
            self.assertFalse(self.peer.tcp(18080))
            self.assertTrue(self.peer.tcp(22222))
            main(['--state-dir',str(STATE),'--backend',backend,'apply','--partial','--only','tcp_ssh','--set','SSH_PORT=18081','--local'])
            self.assertTrue(self.peer.tcp(18081))
            self.disable()

    def test_09_concurrent_writers_preserve_one_pending_change(self):
        for backend in ('nftables','iptables'):
            self.apply(backend)
            args=['python3','-I','core/fw.py','--state-dir',str(STATE),'--backend',backend,'apply','--env-file','tests/empty.conf','--profile','web','--set','SSH_PORT=22222','--set','IPTABLES_FRONTEND='+FRONTEND,'--timeout','5','--watchdog','process']
            procs=[subprocess.Popen([*args,'--set',f'HTTP_HTTPS_PORTS={port}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for port in (18080,18081)]
            codes=[]
            for p in procs:
                output,error=p.communicate();codes.append(p.returncode)
            self.assertEqual(sorted(codes),[0,2])
            self.assertIsNotNone(self.store.get('pending'))
            with self.store.lock():self.store.rollback_locked()
            self.disable()

    def test_10_native_gateway_scoped_dual_without_docker(self):
        access={'forward':[]}
        for f in (4,6):
            access['forward'].append({'group':'vpn-users','source':'10.20.0.2/32' if f==4 else 'fd00:20::2/128',
                'destination':'10.30.0.2/32' if f==4 else 'fd00:30::2/128','input':'wan0','output':'lan0','protocol':'tcp','ports':'18443'})
        path=STATE/'access.json';path.write_text(json.dumps(access));path.chmod(0o600)
        for backend in ('nftables','iptables'):
            self.apply(backend,'host-minimal',ACCESS_POLICY=str(path))
            for f in (4,6):
                dest='10.30.0.2' if f==4 else 'fd00:30::2'
                self.assertTrue(self.peer.tcp(18443,f,dest=dest),(backend,f))
                self.assertFalse(self.peer.tcp(18444,f,dest=dest),(backend,f))
                self.assertFalse(self.peer.tcp(18443,f,source='10.20.0.3' if f==4 else 'fd00:20::3',dest=dest))
                # A routed network grant does not authorize access to host's same port.
                self.assertFalse(self.peer.tcp(18080,f))
            self.disable()

    def docker_fixture(self, backend, create=True):
        # A kernel-real Docker chain topology, NOT an actual Docker daemon.
        if backend=='iptables':
            for f in (4,6):
                cmd=engine.ipcmd(f)
                pub='10.20.0.1' if f==4 else 'fd00:20::1'
                target='10.30.0.2:18443' if f==4 else '[fd00:30::2]:18443'
                if create:
                    run(cmd,'-N','DOCKER-USER')
                    run(cmd,'-A','DOCKER-USER','-j','RETURN')
                    run(cmd,'-I','FORWARD','1','-j','DOCKER-USER')
                    run(cmd,'-A','FORWARD','-m','conntrack','--ctstate','DNAT','-j','ACCEPT')
                    run(cmd,'-P','FORWARD','DROP')
                    for proto in ('tcp','udp'):
                        run(cmd,'-t','nat','-A','PREROUTING','-i','wan0','-d',pub,'-p',proto,'--dport','18080','-j','DNAT','--to-destination',target)
                else:
                    run(cmd,'-D','FORWARD','-j','DOCKER-USER')
                    run(cmd,'-D','FORWARD','-m','conntrack','--ctstate','DNAT','-j','ACCEPT')
                    run(cmd,'-F','DOCKER-USER');run(cmd,'-X','DOCKER-USER')
                    run(cmd,'-P','FORWARD','ACCEPT')
                    for proto in ('tcp','udp'):
                        run(cmd,'-t','nat','-D','PREROUTING','-i','wan0','-d',pub,'-p',proto,'--dport','18080','-j','DNAT','--to-destination',target)
        else:
            for f in (4,6):
                family='ip' if f==4 else 'ip6'
                if not create:
                    run('nft','delete','table',family,'docker-bridges');continue
                pub='10.20.0.1' if f==4 else 'fd00:20::1'
                target='10.30.0.2:18443' if f==4 else '[fd00:30::2]:18443'
                text=f'add table {family} docker-bridges\nadd chain {family} docker-bridges forward {{ type filter hook forward priority 0; policy drop; }}\nadd rule {family} docker-bridges forward ct status dnat accept\nadd chain {family} docker-bridges prerouting {{ type nat hook prerouting priority -100; policy accept; }}\n'
                for proto in ('tcp','udp'):
                    text+=f'add rule {family} docker-bridges prerouting iifname "wan0" {family} daddr {pub} {proto} dport 18080 dnat to {target}\n'
                run('nft','-f','-',text=text)

    def test_11_dnat_protocol_independence_and_docker_topologies(self):
        access={'containers':[]}
        for f in (4,6):
            access['containers'].append({'group':'web','source':'10.20.0.0/24' if f==4 else 'fd00:20::/64',
                'destination':'10.30.0.2/32' if f==4 else 'fd00:30::2/128','input':'wan0','output':'lan0',
                'public_destination':'10.20.0.1/32' if f==4 else 'fd00:20::1/128','protocol':'tcp','ports':'18443',
                'public_ports':'18080','service':'http_https_protect'})
        path=STATE/'access.json';path.write_text(json.dumps(access));path.chmod(0o600)
        for suite,docker in (('iptables','iptables'),('nftables','iptables'),('nftables','nftables')):
            self.docker_fixture(docker)
            try:
                before=engine.inspect(suite,FRONTEND)
                self.apply(suite,CONTAINER_POLICY='restrict',ACCESS_POLICY=str(path))
                for f in (4,6):
                    self.assertTrue(self.peer.tcp(18080,f),(suite,docker,f))
                    self.assertFalse(self.peer.udp(18080,[b'quic-probe'],f)[0],(suite,docker,f,'UDP must not inherit TCP permission'))
                    self.assertFalse(self.peer.tcp(18443,f,dest='10.30.0.2' if f==4 else 'fd00:30::2'), 'direct routed access must not bypass publication scope')
                self.disable()
                # Suite leaves Docker fixture objects/policies intact.
                after=engine.inspect(suite,FRONTEND)
                self.assertEqual(before['tables'],after['tables'])
            finally:
                self.disable();self.docker_fixture(docker,False)

    def test_12_rollback_preserves_foreign_changes_made_while_pending(self):
        for backend in ('nftables','iptables'):
            self.apply(backend)
            p=generate(self.config(backend,HTTP_HTTPS_PORTS='18081'))
            with self.store.lock():token=self.store.apply_locked(p,timeout=30,watchdog='process')
            run(engine.ipcmd(4),'-I','INPUT','1','-p','tcp','--dport','64999','-j','DROP')
            with self.store.lock():self.store.rollback_locked(token)
            self.assertIn('--dport 64999 -j DROP',run(engine.ipcmd(4,'-save')))
            run(engine.ipcmd(4),'-D','INPUT','-p','tcp','--dport','64999','-j','DROP')
            self.disable()

    def test_13_game_container_remapping_and_roles(self):
        for backend in ('iptables','nftables'):
            self.docker_fixture('iptables')
            try:
                for role in ('gameserver','sourcetv'):
                    grant={'group':'game-users','source':'10.20.0.0/24','destination':'10.30.0.2/32',
                        'input':'wan0','output':'lan0','protocol':'udp','ports':'18443','public_ports':'18080',
                        'public_destination':'10.20.0.1/32','service':'l4d2_udp_base','role':role}
                    path=STATE/'access.json';path.write_text(json.dumps({'containers':[grant]}));path.chmod(0o600)
                    self.apply(backend,'games',HOST_SERVICES='false',CONTAINER_POLICY='restrict',ACCESS_POLICY=str(path),FAMILY_POLICY='ipv4-block-ipv6' if backend=='iptables' else 'dual')
                    self.assertTrue(self.peer.udp(18080,[b'\xff'*4+b'qconnect'+b'x'*11])[0],(backend,role,'login'))
                    self.assertTrue(self.peer.udp(18080,[b'\xff'*4+b'TSource Engine Query\x00'])[0],(backend,role,'A2S'))
                    self.assertFalse(self.peer.udp(18080,[b'x'*3000])[0],(backend,role,'validation'))
                    self.assertFalse(self.peer.tcp(18080),(backend,role,'TCP must remain blocked'))
                    self.disable()
            finally:
                self.disable();self.docker_fixture('iptables',False)

    def test_14_vpn_nat_does_not_grant_routing(self):
        grant={'group':'vpn-users','source':'10.20.0.2/32','destination':'10.30.0.2/32',
            'input':'wan0','output':'lan0','protocol':'tcp','ports':'18443'}
        path=STATE/'access.json';path.write_text(json.dumps({'forward':[grant]}));path.chmod(0o600)
        values={'OVPNSRV_INTERFACE':'wan0','OVPNSRV_SUBNET':'10.20.0.0/24',
            'OVPNSRV_LAN_SUBNET':'10.30.0.0/24','OVPNSRV_LAN_INTERFACE':'lan0','OVPNSRV_ENABLE_NAT':'true'}
        for backend in ('nftables','iptables'):
            self.apply(backend,'vpn-gateway',**values)
            self.assertFalse(self.peer.tcp(18443,dest='10.30.0.2'))
            self.apply(backend,'vpn-gateway',ACCESS_POLICY=str(path),**values)
            self.assertTrue(self.peer.tcp(18443,dest='10.30.0.2'))
            address=self.peer.python("import socket;s=socket.create_connection(('10.30.0.2',18443),1);print(s.recv(100).decode());s.close()").strip()
            self.assertEqual(address,'10.30.0.1','NAT source must be scoped output interface')
            self.assertFalse(self.peer.tcp(18444,dest='10.30.0.2'))
            self.disable()

    def test_15_partial_requires_objects_and_privileged_inputs_are_trusted(self):
        from core.fw import main
        from core.config import trusted
        self.apply('nftables')
        path=STATE/'unsafe.conf';path.write_text('SSH_PORT=22222');path.chmod(0o666)
        with self.assertRaises(PolicyError):trusted(path)
        path.chmod(0o600)
        run('nft','delete','table','inet','firewall_main')
        with self.assertRaises(PolicyError):
            main(['--state-dir',str(STATE),'apply','--partial','--only','tcp_ssh','--set','SSH_PORT=18081','--local'])
        self.assertNotIn('table inet firewall_main',run('nft','list','tables'))

    def test_16_external_verifier_new_connection_and_failure_rollback(self):
        for backend in ('nftables','iptables'):
            self.apply(backend)
            candidate=generate(self.config(backend,HTTP_HTTPS_PORTS='18081'))
            verifier=STATE/'verify-admin'
            verifier.write_text('#!/bin/sh\nexit 9\n');verifier.chmod(0o700)
            with self.store.lock(), self.assertRaises(PolicyError):
                self.store.apply_locked(candidate,timeout=5,watchdog='process',verifier=str(verifier))
            self.assertTrue(self.peer.tcp(18080))
            self.assertFalse(self.peer.tcp(18081))
            # An independent namespace makes a fresh TCP connection; the test
            # models the verifier contract, without claiming SSH authentication.
            verifier.write_text(f'''#!/bin/sh
exec nsenter -t {self.peer.p.pid} -n python3 -I -c "import socket; s=socket.create_connection(('10.20.0.1',18081),1); s.close()"
''')
            with self.store.lock():
                self.assertIsNone(self.store.apply_locked(candidate,timeout=5,watchdog='process',verifier=str(verifier)))
            self.assertIsNone(self.store.get('pending'))
            self.assertTrue(self.peer.tcp(18081))
            self.disable()

    def test_17_docker_absence_and_unowned_name_preserve_active(self):
        self.apply('nftables',NF_TABLE_NAME='suite_custom')
        before=self.rules('nftables')
        run('nft','add','table','inet','unowned')
        with_foreign=self.rules('nftables')
        try:
            candidate=generate(self.config('nftables',NF_TABLE_NAME='unowned'))
            with self.store.lock(),self.assertRaises(PolicyError):
                self.store.apply_locked(candidate,local=True)
            self.assertEqual(self.rules('nftables'),with_foreign)
        finally:run('nft','delete','table','inet','unowned')
        grant={'group':'web','source':'10.20.0.0/24','destination':'10.30.0.2/32',
            'input':'wan0','output':'lan0','protocol':'tcp','ports':'18443','public_ports':'18080',
            'public_destination':'10.20.0.1/32','service':'http_https_protect'}
        path=STATE/'access.json';path.write_text(json.dumps({'containers':[grant]}));path.chmod(0o600)
        candidate=generate(self.config('nftables',NF_TABLE_NAME='suite_custom',CONTAINER_POLICY='restrict',ACCESS_POLICY=str(path)))
        with self.store.lock(), self.assertRaises(PolicyError):
            self.store.apply_locked(candidate,local=True)
        self.assertEqual(self.rules('nftables'),before)


if __name__=='__main__':
    unittest.main(verbosity=2)
