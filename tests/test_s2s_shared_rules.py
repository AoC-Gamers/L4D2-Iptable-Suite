#!/usr/bin/python3
"""OpenVPN site-to-site Docker-USER grant descriptor regressions."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.compiler import generate
from core.config import Configuration, PolicyError


BASE = {
    'OVPNS2S_INTERFACE': 'tun0',
    'OVPNS2S_LOCAL_INTERFACE': 'enp34s0',
    'OVPNS2S_LOCAL_SUBNETS': '192.168.1.0/24 2001:db8:1::/64',
    'OVPNS2S_REMOTE_SUBNETS': '10.8.0.0/24 2001:db8:8::/64',
    'ROUTED_POLICY': 'unmanaged',
}


def policy(backend='nftables', **overrides):
    return generate(Configuration(
        backend, only=['openvpn_sitetosite'], overrides={**BASE, **overrides},
    ))


class S2SSharedRulesTests(unittest.TestCase):
    def test_opt_in_emits_exact_dual_stack_docker_user_descriptors(self):
        result = policy(OVPNS2S_ALLOW_LAN='true')
        self.assertEqual(result['schema'], 3)
        rules = result['shared_rules']
        self.assertEqual(len(rules), 4)
        self.assertEqual({row['family'] for row in rules}, {'ip', 'ip6'})
        for row in rules:
            self.assertEqual(set(row), {'family', 'table', 'chain', 'comment', 'text'})
            self.assertEqual(row['table'], 'filter')
            self.assertEqual(row['chain'], 'DOCKER-USER')
            self.assertRegex(row['comment'], r'^l4d2-suite:s2s:[0-9a-f]{16}$')
            self.assertIn(f'comment "{row["comment"]}"', row['text'])
            self.assertIn('counter accept', row['text'])

        v4 = [row['text'] for row in rules if row['family'] == 'ip']
        v6 = [row['text'] for row in rules if row['family'] == 'ip6']
        for texts, family, local, remote in (
            (v4, 'ip', '192.168.1.0/24', '10.8.0.0/24'),
            (v6, 'ip6', '2001:db8:1::/64', '2001:db8:8::/64'),
        ):
            outbound = next(text for text in texts if 'iifname "tun0"' in text)
            reply = next(text for text in texts if 'iifname "enp34s0"' in text)
            self.assertIn(f'iifname "tun0" oifname "enp34s0" {family} saddr {remote} {family} daddr {local}', outbound)
            self.assertNotIn('ct direction', outbound)
            self.assertIn(f'iifname "enp34s0" oifname "tun0" {family} saddr {local} {family} daddr {remote}', reply)
            self.assertIn('ct direction reply ct state { established, related }', reply)

        # Descriptor identity is deterministic and direction-specific.
        self.assertEqual(rules, policy(OVPNS2S_ALLOW_LAN='true')['shared_rules'])
        self.assertEqual(len({row['comment'] for row in rules}), len(rules))
        own_filter = '\n'.join(obj['text'] for obj in result['objects'] if obj['name'] == 'firewall_main')
        self.assertNotIn('iifname "tun0"', own_filter)
        self.assertNotIn('oifname "enp34s0"', own_filter)

    def test_default_off_omits_shared_rules_and_nat_remains_independent(self):
        ipv4 = {
            'OVPNS2S_LOCAL_SUBNETS': '192.168.1.0/24',
            'OVPNS2S_REMOTE_SUBNETS': '10.8.0.0/24',
        }
        without_opt_in = policy(OVPNS2S_ENABLE_NAT='true', **ipv4)
        self.assertEqual(without_opt_in['schema'], 2)
        self.assertNotIn('shared_rules', without_opt_in)
        nat_text = '\n'.join(obj['text'] for obj in without_opt_in['objects'])
        self.assertIn('masquerade', nat_text)

        with_opt_in = policy(OVPNS2S_ENABLE_NAT='true', OVPNS2S_ALLOW_LAN='true', **ipv4)
        self.assertEqual(len(with_opt_in['shared_rules']), 2)
        nat_after = '\n'.join(obj['text'] for obj in with_opt_in['objects'])
        self.assertEqual(nat_text, nat_after)

    def test_other_backend_is_rejected_explicitly(self):
        with self.assertRaisesRegex(PolicyError, 'requires the nftables backend'):
            policy(backend='iptables', OVPNS2S_ALLOW_LAN='true')

    def test_requires_sitetosite_module(self):
        with self.assertRaisesRegex(PolicyError, 'requires openvpn_sitetosite'):
            generate(Configuration('nftables', only=['tcp_ssh'], overrides={
                'OVPNS2S_ALLOW_LAN': 'true', 'ROUTED_POLICY': 'unmanaged',
            }))

    def test_requires_unmanaged_routing(self):
        with self.assertRaisesRegex(PolicyError, 'requires ROUTED_POLICY=unmanaged'):
            policy(OVPNS2S_ALLOW_LAN='true', ROUTED_POLICY='drop')

    def test_requires_distinct_local_interface_and_tunnel(self):
        for value in ('', 'tun0'):
            with self.subTest(local_interface=value), self.assertRaisesRegex(
                PolicyError, 'LOCAL_INTERFACE distinct from OVPNS2S_INTERFACE',
            ):
                policy(OVPNS2S_ALLOW_LAN='true', OVPNS2S_LOCAL_INTERFACE=value)

    def test_requires_matching_local_and_remote_address_families(self):
        with self.assertRaisesRegex(PolicyError, 'same address families'):
            policy(OVPNS2S_ALLOW_LAN='true', OVPNS2S_LOCAL_SUBNETS='192.168.1.0/24',
                   OVPNS2S_REMOTE_SUBNETS='2001:db8:8::/64')

    def test_allow_lan_value_is_strict_boolean(self):
        with self.assertRaisesRegex(PolicyError, 'OVPNS2S_ALLOW_LAN must be true/false'):
            policy(OVPNS2S_ALLOW_LAN='yes')


if __name__ == '__main__':
    unittest.main()
