#!/usr/bin/python3
"""Pure logical tests. These do not claim kernel or traffic validation."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import Configuration, PolicyError, ROOT, assignments, network, ports
from core.compiler import generate
from core.store import remaining


class ConfigurationTests(unittest.TestCase):
    def test_parser_literal_and_empty(self):
        self.assertEqual(assignments('SSH_PORT="22"\nMODULES_ONLY=""\n'), {'SSH_PORT': '22', 'MODULES_ONLY': ''})

    def test_parser_rejects_execution_and_duplicates(self):
        for value in ('SSH_PORT=$(id)', 'SSH_PORT=`id`', 'SSH_PORT=22\nSSH_PORT=23', 'export SSH_PORT=22', 'SSH_PORT="unterminated'):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                assignments(value)

    def test_complete_ips_and_prefixes(self):
        for ip in ('300.0.0.1', '1.2.3.4/33', '::/129', 'fe80::x', '192.0.2.1/24'):
            with self.subTest(ip=ip), self.assertRaises(PolicyError):
                network(ip)

    def test_ports(self):
        for value in ('0', '65536', '100:22', '22;drop', '22,', '22-23'):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                ports(value)
        self.assertEqual(ports('22,80:443'), [(22,22), (80,443)])

    def test_default_minimal_not_all(self):
        for backend in ('iptables', 'nftables'):
            c = Configuration(backend)
            self.assertEqual(c.names, {'tcp_ssh'})

    def test_web_does_not_load_optional_modules(self):
        c = Configuration('nftables', profiles=['web'])
        self.assertEqual(c.names, {'tcp_ssh', 'http_https_protect'})
        self.assertNotIn('OVPNSRV_SUBNET', c.values)
        self.assertNotIn('L4D2_GAMESERVER_UDP_PORTS', c.values)

    def test_typo_exclusion_conflict_dependency(self):
        for opts in ({'only':['typo']}, {'skip':['typo']}, {'only':['openvpn_server','openvpn_sitetosite']}, {'only':['l4d2_udp_base']}, {'skip':['chain_setup']}):
            with self.subTest(opts=opts), self.assertRaises(PolicyError):
                Configuration('nftables', **opts)

    def test_conflict_resolved_after_exclusion(self):
        c = Configuration('nftables', only=['openvpn_server','openvpn_sitetosite'], skip=['openvpn_sitetosite'])
        self.assertEqual(c.names, {'openvpn_server'})

    def test_cli_replaces_file_selection(self):
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write('MODULES_ONLY=openvpn_server\nSSH_PORT=2222\n'); f.flush()
            c = Configuration('nftables', path=f.name, only=['tcp_ssh'], overrides={'SSH_PORT':'23'})
            self.assertEqual(c.names, {'tcp_ssh'})
            self.assertEqual(c.values['SSH_PORT'], '23')

    def test_intentionally_empty_required_not_defaulted(self):
        with self.assertRaises(PolicyError):
            Configuration('nftables', overrides={'SSH_PORT':''})

    def test_security_options_rejected(self):
        for v in ({'SSH_DOCKER':'2222'}, {'BYPASS_SOURCE_IPS':'192.0.2.1'}, {'NF_TABLE_NAME':'x;flush ruleset'}, {'NF_TABLE_NAME':'l4d2_boot_guard'}, {'NF_TABLE_FAMILY':'ip'}, {'DOCKER_CHAIN_AUTORECOVER':'true'}, {'ENABLE_MALFORMED_FILTER':'maybe'}, {'SSH_PORT':'99999'}, {'SSH_RATE':'0/second'}, {'LOG_PREFIX_SSH_ABUSE':'"; drop'}, {'OVPNSRV_INTERFACE':'tun+'}):
            with self.subTest(v=v), self.assertRaises(PolicyError):
                Configuration('nftables', overrides=v)

    def test_iptables_game_family_decision(self):
        with self.assertRaises(PolicyError):
            Configuration('iptables', profiles=['games'])
        Configuration('iptables', profiles=['games'], overrides={'FAMILY_POLICY':'ipv4-block-ipv6'})

    def test_unselected_module_never_executes(self):
        # A disabled module's executable top-level code is never sourced.
        m = ROOT / 'modules/nf/nf_10_whitelist.sh'
        marker = ROOT / 'tmp/disabled-executed'
        previous = m.read_text()
        try:
            m.write_text(previous + '\ntouch ' + str(marker) + '\n')
            generate(Configuration('nftables', profiles=['web']))
            self.assertFalse(marker.exists())
        finally:
            m.write_text(previous)
            marker.unlink(missing_ok=True)

    def test_dns_closed_on_failure_or_unexpected_answer(self):
        v = {'BYPASS_SOURCE_DOMAINS':'admin.example', 'PRIVILEGED_BYPASS':'true', 'DNS_ALLOWED_CIDRS':'192.0.2.0/24'}
        with patch('socket.getaddrinfo', side_effect=OSError('offline')), self.assertRaises(PolicyError):
            Configuration('nftables', only=['whitelist'], overrides=v)
        with patch('socket.getaddrinfo', return_value=[(2,1,6,'',('203.0.113.1',0))]), self.assertRaises(PolicyError):
            Configuration('nftables', only=['whitelist'], overrides=v)

    def test_invalid_access_scope(self):
        with tempfile.NamedTemporaryFile(mode='w') as f:
            json.dump({'host':[{'source':'192.0.2.0/24'}]},f); f.flush()
            with self.assertRaises(PolicyError):
                Configuration('nftables', overrides={'ACCESS_POLICY':f.name})

    def test_access_rejects_unexpected_types(self):
        with tempfile.NamedTemporaryFile(mode='w') as f:
            for value in ([None], ['tcp'], [{'source':123}]):
                f.seek(0);f.truncate();json.dump({'host':value},f);f.flush()
                with self.subTest(value=value), self.assertRaises(PolicyError):
                    Configuration('nftables',overrides={'ACCESS_POLICY':f.name})

    def test_state_lifetime_covers_refill_in_both_engines(self):
        for backend in ('iptables','nftables'):
            c=Configuration(backend,overrides={'SSH_RATE':'1/hour','SSH_BURST':'2'})
            self.assertEqual(c.values['SSH_METER_TIMEOUT'],'7200s')
            with self.assertRaises(PolicyError):
                Configuration(backend,overrides={'SSH_RATE':'1/hour','SSH_BURST':'2','SSH_METER_TIMEOUT':'1m'})
            vals={'FAMILY_POLICY':'ipv4-block-ipv6'} if backend=='iptables' else {}
            c=Configuration(backend,profiles=['games'],overrides=vals)
            self.assertEqual(c.values['NFT_LOGIN_METER_TIMEOUT'],'4s')
            if backend=='iptables':
                p=generate(c)
                login=[r for chain in p['families']['4']['filter'].values() for r in chain if '--hashlimit-name' in r and '4000' in r]
                self.assertGreaterEqual(len(login),2)

    def test_overlapping_tcp_service_controls_rejected(self):
        with self.assertRaises(PolicyError):
            Configuration('nftables',profiles=['web'],overrides={'SSH_PORT':'443'})

    def test_rollback_deadline_is_monotonic_and_boot_scoped(self):
        with patch('core.store.time.monotonic',return_value=50), patch('core.store.time.time',return_value=999999):
            self.assertEqual(remaining({'deadline':1,'deadline_monotonic':60}),10)
            self.assertLess(remaining({'deadline_monotonic':60,'boot_id':'another-boot'}),0)

    def test_generated_web_dual_and_bounded(self):
        policy = generate(Configuration('nftables', profiles=['web']))
        text = '\n'.join(o['text'] for o in policy['objects'])
        self.assertIn('ip6 saddr', text)
        self.assertIn('meter ssh_input_admin_under_v4 size 8192', text)
        self.assertNotIn('limit rate over 30/minute', text)
        self.assertIn('icmpv6 type packet-too-big', text)
        self.assertNotIn('flush ruleset', text)

    def test_udp_validation_precedes_terminal_accept(self):
        text = generate(Configuration('nftables', profiles=['games']))['objects'][0]['text']
        start = text.index('input_l4d2_udp udp dport')
        validate = text.index('udp length 0-8', start)
        classify = text.index('0xFFFFFFFF54 jump', validate) if '0xFFFFFFFF54 jump' in text else text.index('0xFFFFFFFF54 counter jump', validate)
        base = text.index('ct state new counter jump udp_new_limit', classify)
        established = text.index('input ct state established,related', base)
        self.assertLess(validate, classify)
        self.assertLess(classify, base)
        self.assertLess(base, established)


if __name__ == '__main__':
    unittest.main(verbosity=2)
