#!/usr/bin/python3
"""Kernel syntax/capability check only, separate from traffic integration."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import Configuration
from core.compiler import generate
from core import engine
assert os.readlink('/proc/self/ns/net') != os.environ['SUITE_HOST_NETNS']
frontend=os.environ.get('SUITE_TEST_FRONTEND','auto')
for backend in ('iptables','nftables'):
    live=engine.inspect(backend,frontend)
    for profile in ('host-minimal','web','games','vpn-gateway'):
        values={'IPTABLES_FRONTEND':frontend}
        if backend=='iptables' and profile=='games':values['FAMILY_POLICY']='ipv4-block-ipv6'
        if profile=='vpn-gateway':values.update({'OVPNSRV_ENABLE_NAT':'true','OVPNSRV_LAN_INTERFACE':'lan0'})
        policy=generate(Configuration(backend,profiles=[profile],overrides=values,privileged=True))
        engine.check(engine.prepare(policy,[policy],live))
        print('KERNEL CHECK PASS',backend,frontend,profile,flush=True)
    values={'IPTABLES_FRONTEND':frontend,'OVPNS2S_INTERFACE':'tun0','OVPNS2S_LOCAL_SUBNETS':'192.0.2.0/24','OVPNS2S_REMOTE_SUBNETS':'198.51.100.0/24','OVPNS2S_ROUTER_REAL_IP':'192.0.2.1','OVPNS2S_ROUTER_ALIAS_IP':'203.0.113.1','OVPNS2S_ROUTER_ALIAS_SNAT':'true','OVPNS2S_LOCAL_INTERFACE':'lan0'}
    policy=generate(Configuration(backend,only=['openvpn_sitetosite'],overrides=values,privileged=True))
    engine.check(engine.prepare(policy,[policy],live))
    print('KERNEL CHECK PASS',backend,frontend,'VPN S2S DNAT/SNAT',flush=True)
