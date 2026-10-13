#!/usr/bin/python3
"""Container ingress policy generation regressions; no kernel access."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.compiler import generate
from core.config import Configuration, PolicyError


def grant(source, destination, public_destination, bridge):
    return {
        'group': 'web', 'source': source, 'destination': destination,
        'protocol': 'tcp', 'ports': '8443', 'input': 'enp1s0',
        'output': bridge, 'public_destination': public_destination,
        'public_ports': '443', 'service': 'http_https_protect',
    }


def config(backend='nftables', container_policy='ingress', routed_policy='unmanaged',
           containers=None, forward=None):
    return Configuration.from_normalized(
        backend,
        {
            'HOST_SERVICES': 'false', 'CONTAINER_POLICY': container_policy,
            'ROUTED_POLICY': routed_policy, 'HTTP_HTTPS_PORTS': '8443',
        },
        ['http_https_protect'],
        {'host': [], 'forward': forward or [], 'containers': containers or []},
    )


class ContainerIngressTests(unittest.TestCase):
    def test_dual_stack_grants_precede_unique_bridge_guards_and_delegate_other_routes(self):
        policy = generate(config(containers=[
            grant('198.51.100.0/24', '10.20.0.0/24', '203.0.113.10', 'br-web'),
            grant('2001:db8:1::/64', '2001:db8:20::/64', '2001:db8::10', 'br-web'),
            grant('192.0.2.0/24', '10.30.0.0/24', '203.0.113.11', 'br-other'),
        ]))
        text = policy['objects'][0]['text']
        self.assertIn(
            'add chain inet firewall_main forward '
            '{ type filter hook forward priority -5; policy accept; }', text,
        )

        for bridge in ('br-web', 'br-other'):
            same_bridge = f'iifname "{bridge}" oifname "{bridge}" counter return'
            egress_reply = (
                f'oifname "{bridge}" ct direction reply '
                'ct state { established, related } ct status != dnat counter return'
            )
            ingress_drop = f'oifname "{bridge}" counter drop'
            self.assertEqual(text.count(same_bridge), 1)
            self.assertEqual(text.count(egress_reply), 1)
            self.assertEqual(text.count(ingress_drop), 1)
            self.assertNotIn(f'iifname "{bridge}" counter drop', text)
            self.assertLess(text.index(same_bridge), text.index(egress_reply))
            self.assertLess(text.index(egress_reply), text.index(ingress_drop))

        # Both IPv4 and IPv6 exact DNAT grant paths are composed before the
        # bridge guards; they are not replaced by a bridge-wide accept.
        self.assertIn('meta nfproto ipv4', text)
        self.assertIn('meta nfproto ipv6', text)
        self.assertIn('ct original proto-dst 443', text)
        self.assertIn('ct status dnat', text)
        self.assertLess(text.index('ct original proto-dst 443'), text.index('iifname "br-web" oifname'))

        final_return = 'add rule inet firewall_main forward counter return'
        self.assertEqual(text.count(final_return), 1)
        self.assertGreater(text.index(final_return), text.index('oifname "br-other" counter drop'))
        self.assertEqual(policy['config']['ROUTED_POLICY'], 'unmanaged')
        self.assertEqual(policy['config']['CONTAINER_POLICY'], 'ingress')

    def test_restrict_output_remains_drop_in_both_directions(self):
        policy = generate(config(
            container_policy='restrict', routed_policy='unmanaged',
            containers=[grant('198.51.100.0/24', '10.20.0.0/24', '203.0.113.10', 'br-web')],
        ))
        text = policy['objects'][0]['text']
        self.assertIn('oifname "br-web" counter drop', text)
        self.assertIn('iifname "br-web" counter drop', text)
        self.assertNotIn('ct direction reply ct state { established, related } ct status != dnat', text)

    def test_ingress_rejects_iptables_backend(self):
        with self.assertRaisesRegex(PolicyError, 'requires the nftables backend'):
            config(backend='iptables', containers=[
                grant('198.51.100.0/24', '10.20.0.0/24', '203.0.113.10', 'br-web'),
            ])

    def test_ingress_requires_unmanaged_routing(self):
        with self.assertRaisesRegex(PolicyError, 'requires ROUTED_POLICY=unmanaged'):
            config(routed_policy='drop', containers=[
                grant('198.51.100.0/24', '10.20.0.0/24', '203.0.113.10', 'br-web'),
            ])

    def test_ingress_requires_container_grants(self):
        with self.assertRaisesRegex(PolicyError, 'requires nonempty container grants'):
            config(containers=[])

    def test_ingress_rejects_forward_grants(self):
        container = grant('198.51.100.0/24', '10.20.0.0/24', '203.0.113.10', 'br-web')
        forward = {
            'group': 'vpn', 'source': '10.8.0.0/24', 'destination': '192.0.2.0/24',
            'protocol': 'tcp', 'ports': '443', 'input': 'tun0', 'output': 'enp1s0',
        }
        with self.assertRaisesRegex(PolicyError, 'Forward grants require ROUTED_POLICY=drop'):
            config(containers=[container], forward=[forward])


if __name__ == '__main__':
    unittest.main()
