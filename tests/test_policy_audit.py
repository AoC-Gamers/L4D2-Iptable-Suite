#!/usr/bin/python3
"""Compiler regressions for bounded iptables hashlimit state."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.compiler import generate
from core.config import Configuration


class HashlimitCapacityTests(unittest.TestCase):
    def candidate(self, backend, capacity=16):
        return generate(Configuration(
            backend,
            only=['tcp_ssh', 'http_https_protect', 'l4d2_tcp_protect'],
            overrides={
                'SSH_PORT': '22222',
                'HTTP_HTTPS_PORTS': '18080',
                'L4D2_GAMESERVER_TCP_PORTS': '18081',
                'STATE_CAPACITY': str(capacity),
                'FAMILY_POLICY': 'ipv4-block-ipv6',
            },
            privileged=False,
        ))

    def test_iptables_capacity_overrides_module_defaults_for_every_hashlimit(self):
        candidate = self.candidate('iptables')
        rules = [
            rule
            for family in candidate['families'].values()
            for tables in family.values()
            for chain_rules in tables.values()
            for rule in chain_rules
            if '--hashlimit-name' in rule
        ]
        self.assertTrue(rules, 'expected generated hashlimit rules')
        for rule in rules:
            with self.subTest(rule=rule):
                for flag in ('--hashlimit-htable-size', '--hashlimit-htable-max'):
                    self.assertIn(flag, rule)
                    self.assertEqual(rule[rule.index(flag) + 1], '16')
                self.assertIn('--hashlimit-htable-expire', rule)

    def test_other_backend_is_unchanged(self):
        candidate = self.candidate('nftables')
        text = '\n'.join(obj['text'] for obj in candidate['objects'])
        self.assertIn(' size 16 {', text)

    def test_iptables_refill_expiry_replaces_module_expiry(self):
        candidate = generate(Configuration(
            'iptables',
            only=['tcp_ssh', 'http_https_protect'],
            overrides={
                'SSH_RATE': '1/hour', 'SSH_BURST': '20',
                'HTTP_HTTPS_RATE': '1/hour', 'HTTP_HTTPS_BURST': '10',
            },
            privileged=False,
        ))
        rules = [
            rule
            for family in candidate['families'].values()
            for tables in family.values()
            for chain_rules in tables.values()
            for rule in chain_rules
            if '--hashlimit-name' in rule
        ]
        expiries = {rule[rule.index('--hashlimit-htable-expire') + 1] for rule in rules}
        self.assertEqual(expiries, {'72000000', '36000000'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
