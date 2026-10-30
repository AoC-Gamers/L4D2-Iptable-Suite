#!/usr/bin/python3
"""Logical protocol/port, compatibility, and persistence regressions."""
from pathlib import Path
import copy
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.compiler import generate, nfports
from core.config import Configuration, PolicyError

BASE = {
    'OVPNS2S_INTERFACE':'vpn0', 'OVPNS2S_LOCAL_INTERFACE':'lan0',
    'OVPNS2S_LOCAL_SUBNETS':'192.0.2.0/24', 'OVPNS2S_REMOTE_SUBNETS':'198.51.100.0/24',
    'OVPNS2S_ROUTER_REAL_IP':'192.0.2.1', 'OVPNS2S_ROUTER_ALIAS_IP':'203.0.113.200',
    'ROUTED_POLICY':'unmanaged',
}
def policy(backend='nftables', **values):
    return generate(Configuration(backend, only=['openvpn_sitetosite'], overrides={**BASE, **values}))
def nat(p):
    return '\n'.join(o['text'] for o in p.get('objects', []) if '_nat' in o['name'])
def iprules(p):
    return [r for chains in p['families']['4'].values() for rules in chains.values() for r in rules]

class RouterAliasTCPTests(unittest.TestCase):
    def test_nft_exact_source_interface_destination_and_tcp_port(self):
        rules=[l for l in nat(policy(OVPNS2S_ROUTER_ALIAS_TCP_PORTS='80')).splitlines() if 'dnat to' in l]
        self.assertEqual(len(rules),1)
        self.assertIn('iifname "vpn0" ip saddr 198.51.100.0/24 ip daddr 203.0.113.200 tcp dport '+nfports('80')+' counter dnat to 192.0.2.1',rules[0])
        self.assertNotIn('udp',rules[0]); self.assertNotIn('443',rules[0])
        self.assertNotIn('masquerade',nat(policy(OVPNS2S_ROUTER_ALIAS_TCP_PORTS='80')))
    def test_iptables_equivalent_port_list(self):
        rules=[r for r in iprules(policy('iptables',OVPNS2S_ROUTER_ALIAS_TCP_PORTS='80,8080:8081')) if 'DNAT' in r]
        self.assertEqual(rules,[['-i','vpn0','-s','198.51.100.0/24','-d','203.0.113.200','-p','tcp','-m','multiport','--dports','80,8080:8081','-j','DNAT','--to-destination','192.0.2.1']])
    def test_optional_alias_snat_has_same_selector_both_backends(self):
        p=policy(OVPNS2S_ROUTER_ALIAS_TCP_PORTS='80',OVPNS2S_ROUTER_ALIAS_SNAT='true')
        rules=[l for l in nat(p).splitlines()if 'masquerade'in l]
        self.assertEqual(len(rules),1);self.assertIn('ip daddr 192.0.2.1 oifname "lan0" tcp dport '+nfports('80'),rules[0])
        rules=[r for r in iprules(policy('iptables',OVPNS2S_ROUTER_ALIAS_TCP_PORTS='80',OVPNS2S_ROUTER_ALIAS_SNAT='true'))if 'MASQUERADE'in r]
        self.assertEqual(len(rules),1);self.assertIn('--dports',rules[0]);self.assertIn('tcp',rules[0]);self.assertIn('80',rules[0])
    def test_empty_selector_preserves_unrestricted_legacy_alias(self):
        self.assertEqual(policy(),policy(OVPNS2S_ROUTER_ALIAS_TCP_PORTS=''))
        rule=next(l for l in nat(policy()).splitlines()if 'dnat to'in l)
        self.assertIn('ip daddr 203.0.113.200 counter dnat to 192.0.2.1',rule);self.assertNotIn('tcp',rule)
        self.assertNotIn('-p',next(r for r in iprules(policy('iptables'))if 'DNAT'in r))
    def test_existing_general_nat_filter_and_shared_rules_unchanged(self):
        before=policy(OVPNS2S_ENABLE_NAT='true',OVPNS2S_ALLOW_LAN='true')
        after=policy(OVPNS2S_ENABLE_NAT='true',OVPNS2S_ALLOW_LAN='true',OVPNS2S_ROUTER_ALIAS_TCP_PORTS='80')
        self.assertEqual(before['shared_rules'],after['shared_rules'])
        self.assertEqual([l for l in nat(before).splitlines()if 'masquerade'in l],[l for l in nat(after).splitlines()if 'masquerade'in l])
        self.assertEqual([o for o in before['objects']if o['family']=='inet'],[o for o in after['objects']if o['family']=='inet'])
    def test_invalid_ports_fail_before_generation(self):
        for value in ['0','65536','80;drop','80,','443:80','udp/80']:
            with self.subTest(value=value),self.assertRaises(PolicyError):policy(OVPNS2S_ROUTER_ALIAS_TCP_PORTS=value)
    def test_selected_module_and_alias_required(self):
        with self.assertRaisesRegex(PolicyError,'requires openvpn_sitetosite'):
            Configuration('nftables',only=['tcp_ssh'],overrides={'OVPNS2S_ROUTER_ALIAS_TCP_PORTS':'80'})
        for changes in [{'OVPNS2S_ROUTER_REAL_IP':'','OVPNS2S_ROUTER_ALIAS_IP':''},{'OVPNS2S_ROUTER_ALIAS_IP':''}]:
            with self.assertRaisesRegex(PolicyError,'require a router alias'):policy(OVPNS2S_ROUTER_ALIAS_TCP_PORTS='80',**changes)
    def test_ipv6_and_prefix_as_alias_rejected(self):
        for key,value in [('OVPNS2S_ROUTER_REAL_IP','2001:db8::1'),('OVPNS2S_ROUTER_ALIAS_IP','203.0.113.0/24'),('OVPNS2S_REMOTE_SUBNETS','2001:db8::/64')]:
            with self.subTest(key=key),self.assertRaises(PolicyError):policy(OVPNS2S_ROUTER_ALIAS_TCP_PORTS='80',**{key:value})
    def test_saved_normalized_policy_round_trip(self):
        for backend in ['nftables','iptables']:
            p=policy(backend,OVPNS2S_ROUTER_ALIAS_TCP_PORTS='80')
            restored=generate(Configuration(backend,overrides=p['config'],only=[x.split('_',1)[1] for x in p['selected']],normalized=True,access_data=copy.deepcopy(p['access'])))
            self.assertEqual(p,restored)
if __name__=='__main__':unittest.main(verbosity=2)
