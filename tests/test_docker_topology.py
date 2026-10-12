#!/usr/bin/python3
"""Structural Docker iptables integration checks; no kernel access."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import engine
from core.config import PolicyError


def save(rules4='', rules6=''):
    template = '*filter\n:FORWARD DROP [0:0]\n:DOCKER-USER - [0:0]\n:L4S_DOCKER - [0:0]\n{rules}\nCOMMIT\n'
    return {'iprules': {'4': template.format(rules=rules4), '6': template.format(rules=rules6)}}


def topology(rules4='', rules6=''):
    live = save(rules4, rules6)
    return engine.docker_forward_diagnostic(live, ('4', '6'))


class DockerTopologyTests(unittest.TestCase):
    valid = '-A FORWARD -m comment --comment docker-hook -j DOCKER-USER\n-A FORWARD -m conntrack --ctstate DNAT -j ACCEPT'

    def test_unique_unconditional_first_jump_per_family(self):
        report = topology(self.valid, '-A FORWARD --jump=DOCKER-USER')
        self.assertTrue(report['ok'], report)
        self.assertEqual(report['families']['4']['forward_link_position'], 1)
        self.assertEqual(report['families']['6']['forward_link_count'], 1)

    def test_rejects_accept_before_link(self):
        report = topology('-A FORWARD -j ACCEPT\n-A FORWARD -j DOCKER-USER', self.valid)
        self.assertFalse(report['ok'])
        self.assertIn('must be first', report['families']['4']['errors'][0])

    def test_rejects_conditioned_jump_goto_and_unsupported_prefix(self):
        cases = (
            '-A FORWARD -m conntrack --ctstate DNAT -j DOCKER-USER',
            '-A FORWARD -g DOCKER-USER',
            '-A FORWARD -m mark --mark 1 -j DOCKER-USER',
        )
        for rule in cases:
            with self.subTest(rule=rule):
                report = topology(rule, self.valid)
                self.assertFalse(report['families']['4']['ok'], report)

    def test_rejects_duplicate_and_comment_lookalike(self):
        duplicate = '-A FORWARD -j DOCKER-USER\n-A FORWARD --jump DOCKER-USER'
        report = topology(duplicate, self.valid)
        self.assertFalse(report['families']['4']['ok'])
        self.assertIn('found 2', report['families']['4']['errors'][0])
        lookalike = '-A FORWARD -m comment --comment "jump DOCKER-USER" -j ACCEPT'
        report = topology(lookalike, self.valid)
        self.assertFalse(report['families']['4']['ok'])
        self.assertIn('found 0', report['families']['4']['errors'][0])

    def test_checks_each_requested_family_and_required_chains(self):
        report = topology(self.valid, '')
        self.assertTrue(report['families']['4']['ok'])
        self.assertFalse(report['families']['6']['ok'])
        self.assertTrue(any('IPv6' in error for error in report['errors']))

    def test_existing_suite_hook_must_be_unique_and_first_in_docker_user(self):
        previous = {
            'backend': 'iptables',
            'families': {'4': {'filter': {'L4S_DOCKER': {}}}, '6': {'filter': {'L4S_DOCKER': {}}}},
            'hooks': [['filter', 'DOCKER-USER', 'L4S_DOCKER']],
        }
        own = engine.hook_rule('DOCKER-USER', 'L4S_DOCKER')
        valid = save('-A FORWARD -j DOCKER-USER\n-A DOCKER-USER -m comment --comment l4d2-suite:integration -j L4S_DOCKER',
                     '-A FORWARD -j DOCKER-USER\n-A DOCKER-USER -m comment --comment l4d2-suite:integration -j L4S_DOCKER')
        self.assertTrue(engine.docker_forward_diagnostic(valid, ('4', '6'), previous)['ok'])
        moved = save('-A FORWARD -j DOCKER-USER\n-A DOCKER-USER -j ACCEPT\n-A DOCKER-USER -m comment --comment l4d2-suite:integration -j L4S_DOCKER',
                     '-A FORWARD -j DOCKER-USER\n-A DOCKER-USER -m comment --comment l4d2-suite:integration -j L4S_DOCKER')
        self.assertFalse(engine.docker_forward_diagnostic(moved, ('4', '6'), previous)['ok'])
        duplicate = save('-A FORWARD -j DOCKER-USER\n' + ' '.join(own),
                         '-A FORWARD -j DOCKER-USER\n' + ' '.join(own) + '\n' + ' '.join(own))
        report = engine.docker_forward_diagnostic(duplicate, ('4', '6'), previous)
        self.assertFalse(report['families']['6']['ok'])
        self.assertIn('has 2 exact suite hooks', report['families']['6']['errors'][0])

    def test_native_nft_suite_does_not_require_iptables_rule_order(self):
        policy = {
            'backend': 'nftables', 'config': {'DOCKER_BACKEND': 'iptables'},
            'access': {'containers': [{'service': 'http_https_protect'}], 'forward': []},
            'objects': [],
        }
        live = {**save('-A FORWARD -j ACCEPT\n-A FORWARD -j DOCKER-USER', ''),
                'docker': 'iptables', 'tables': []}
        engine.preflight(policy, None, live)

    def test_disable_and_container_removal_remain_available_without_docker(self):
        disabled = {
            'backend': 'iptables', 'disabled': True,
            'config': {'DOCKER_BACKEND': 'auto'},
            'access': {'containers': [{'service': 'http_https_protect'}], 'forward': []},
            'families': {'4': {}, '6': {}}, 'hooks': [],
        }
        disabled_previous = {
            'backend': 'iptables', 'config': {'IPTABLES_FRONTEND': 'nft'},
            'versions': {'4': 'iptables v1.8.10 (nf_tables)', '6': 'ip6tables v1.8.10 (nf_tables)'},
        }
        engine.preflight(disabled, disabled_previous, {'docker': 'none', 'frontend': 'nft',
                                                        'versions': dict(disabled_previous['versions']),
                                                        'iprules': {'4': '', '6': ''}})

        previous = {
            'backend': 'iptables', 'versions': {'4': 'ip', '6': 'ip6'},
            'families': {'4': {'filter': {'L4S_DOCKER': {}}}, '6': {'filter': {'L4S_DOCKER': {}}}},
            'hooks': [['filter', 'DOCKER-USER', 'L4S_DOCKER']],
        }
        removed = {
            'backend': 'iptables', 'config': {}, 'access': {'containers': [], 'forward': []},
            'families': {'4': {'filter': {}}, '6': {'filter': {}}}, 'hooks': [],
        }
        live = {'docker': 'none', 'frontend': 'nft', 'versions': dict(previous['versions']),
                'iprules': {'4': '*filter\n:FORWARD DROP [0:0]\n:L4S_DOCKER - [0:0]\nCOMMIT\n',
                            '6': '*filter\n:FORWARD DROP [0:0]\n:L4S_DOCKER - [0:0]\nCOMMIT\n'}}
        engine.preflight(removed, previous, live)


if __name__ == '__main__':
    unittest.main(verbosity=2)
