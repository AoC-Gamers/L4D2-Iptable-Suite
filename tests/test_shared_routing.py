import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import engine, boot


COMMENT = 'l4d2-suite:s2s:0123456789abcdef'
RULE = ('iifname "tun0" oifname "br-test" ip saddr 10.1.0.0/24 '
        'ip daddr 192.0.2.0/24 counter accept comment "' + COMMENT + '"')
DESC = {'family': 'ip', 'table': 'filter', 'chain': 'DOCKER-USER', 'comment': COMMENT, 'text': RULE}


def output(*rules):
    return ' chain DOCKER-USER {\n' + ''.join(f'  {rule} # handle {i}\n' for i, rule in enumerate(rules, 10)) + '}\n'


def forward_json(target='DOCKER-USER', first=True):
    expr = [{'counter': None}, {'jump': {'target': target}}]
    rules = [{'family': 'ip', 'table': 'filter', 'chain': 'FORWARD',
              'expr': expr if first else [{'drop': None}]}]
    if not first:
        rules.append({'family': 'ip', 'table': 'filter', 'chain': 'FORWARD', 'expr': expr})
    return {'nftables': [{'chain': {'family': 'ip', 'table': 'filter', 'name': 'FORWARD'}}]
            + [{'rule': rule} for rule in rules]}


class SharedRoutingTests(unittest.TestCase):
    def policy(self, rules=True):
        p = {'backend': 'nftables', 'objects': [], 'config': {'DOCKER_BACKEND': 'auto'},
             'access': {'forward': False, 'containers': [{'output': 'br-test'}]}}
        if rules:
            p['shared_rules'] = [DESC.copy()]
        return p

    def command(self, argv, **kwargs):
        if argv[:5] == ['nft', '-j', '-s', 'list', 'chain']:
            return SimpleNamespace(returncode=0, stdout=json.dumps(forward_json()))
        if argv[:4] == ['nft', '-a', '-s', 'list']:
            return SimpleNamespace(returncode=0, stdout=output(RULE))
        raise AssertionError(argv)

    def test_preflight_requires_docker_nft_frontend_and_existing_chain(self):
        p = self.policy()
        live = {'tables': [], 'docker': 'iptables', 'frontend': 'nft', 'iprules': {}}
        with patch.object(engine, 'command', side_effect=self.command):
            engine.preflight(p, None, live)
            with self.assertRaisesRegex(Exception, 'Shared routing requires Docker'):
                engine.preflight(p, None, {**live, 'frontend': 'legacy'})
            with patch.object(engine, '_chain_exists', return_value=False):
                with self.assertRaisesRegex(Exception, 'existing nft chain'):
                    engine.preflight(p, None, live)

    def test_preflight_rejects_missing_or_late_docker_forward_link(self):
        with patch.object(engine, 'command', return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps(forward_json(first=False)))):
            with self.assertRaisesRegex(Exception, 'must jump unconditionally'):
                engine._require_docker_user_link('ip')

    def test_snapshot_captures_only_registered_owned_rule(self):
        foreign = 'ct state established counter accept comment "vpn-old"'
        p = self.policy()
        with patch.object(engine, 'command', side_effect=self.command):
            snap = engine.snapshot(p, {'tables': []})
        self.assertEqual(snap['shared_rules'], [DESC])
        self.assertNotIn('handle', snap['shared_rules'][0]['text'])
        self.assertNotIn(foreign, str(snap))

    def test_snapshot_omits_missing_owned_rule_for_restore_state(self):
        p = self.policy()
        with patch.object(engine, 'command', return_value=SimpleNamespace(returncode=0, stdout=output())):
            snap = engine.snapshot(p, {'tables': []})
        self.assertEqual(snap['shared_rules'], [])

    def test_kernel_canonical_forms_compare_by_strict_rule_fields(self):
        host_rule = RULE.replace('10.1.0.0/24', '10.1.0.1/32')
        canonical = ('iifname tun0 oifname "br-test" ip saddr 10.1.0.1 '
                     'ip daddr 192.0.2.0/24 counter packets 4 bytes 64 accept comment "' + COMMENT + '"')
        self.assertEqual(engine._rule_semantics(canonical), engine._rule_semantics(host_rule))
        reply = host_rule.replace('counter accept', 'ct direction reply ct state established,related counter accept')
        reply_braces = host_rule.replace('counter accept',
                                    'ct direction reply ct state { established, related } counter accept')
        self.assertEqual(engine._rule_semantics(reply), engine._rule_semantics(reply_braces))
        with self.assertRaisesRegex(Exception, 'Unsafe shared routing rule literal'):
            engine._rule_semantics(RULE + ' counter drop')

    def test_transaction_deletes_only_exact_registered_handle_and_reinstalls(self):
        p = self.policy()
        foreign = 'ct state established counter accept comment "vpn-old"'
        def cmd(argv, **kwargs):
            return SimpleNamespace(returncode=0, stdout=output(RULE, foreign))
        with patch.object(engine, 'command', side_effect=cmd):
            batch = engine.nft_transaction(p, [p], {'tables': []})
        self.assertIn('delete rule ip filter DOCKER-USER handle 10', batch)
        self.assertNotIn('handle 11', batch)
        self.assertIn('insert rule ip filter DOCKER-USER ' + RULE, batch)
        self.assertEqual(batch.count('insert rule'), 1)

    def test_new_marker_collision_is_not_adopted_or_deleted(self):
        previous = self.policy(rules=False)
        candidate = self.policy()
        with patch.object(engine, 'command', side_effect=self.command):
            with self.assertRaisesRegex(Exception, 'Unregistered shared rule marker collision'):
                engine.nft_transaction(candidate, [previous, candidate], {'tables': []})

    def test_initial_rollback_removes_only_pending_candidate_rules(self):
        candidate = self.policy()
        with patch.object(engine, 'command', side_effect=self.command):
            batch = engine.nft_transaction(None, [None, candidate, None], {'tables': []}, rollback=True)
        self.assertIn('delete rule ip filter DOCKER-USER handle 10', batch)
        self.assertNotIn('insert rule', batch)

    def test_explicit_rollback_restores_snapshot_copy(self):
        previous = self.policy()
        candidate = self.policy(rules=False)
        snapshot = {'backend': 'nftables', 'objects': [], 'shared_rules': [DESC.copy()]}
        target_copy = {'backend': 'nftables', 'objects': [], 'shared_rules': [DESC.copy()]}
        with patch.object(engine, 'command', side_effect=self.command):
            batch = engine.nft_transaction(target_copy, [previous, candidate, snapshot], {'tables': []}, rollback=True)
        self.assertIn('delete rule ip filter DOCKER-USER handle 10', batch)
        self.assertIn('insert rule ip filter DOCKER-USER ' + RULE, batch)

    def test_three_item_apply_union_does_not_grant_candidate_ownership(self):
        previous = self.policy(rules=False)
        candidate = self.policy()
        trailing = {'backend': 'nftables', 'objects': [], 'shared_rules': []}
        with patch.object(engine, 'command', side_effect=self.command):
            with self.assertRaisesRegex(Exception, 'Unregistered shared rule marker collision'):
                engine.nft_transaction(trailing, [previous, candidate, trailing], {'tables': []})

    def test_malformed_or_duplicate_owned_inventory_aborts_before_batch(self):
        p = self.policy()
        malformed = SimpleNamespace(returncode=0, stdout=' accept comment "' + COMMENT + '"\n')
        with patch.object(engine, 'command', return_value=malformed):
            with self.assertRaisesRegex(Exception, 'Malformed shared routing'):
                engine.nft_transaction(p, [p], {'tables': []})
        duplicate = SimpleNamespace(returncode=0, stdout=output(RULE, RULE))
        with patch.object(engine, 'command', return_value=duplicate):
            with self.assertRaisesRegex(Exception, 'Ambiguous shared rule'):
                engine.nft_transaction(p, [p], {'tables': []})

    def test_readiness_requires_exact_shared_rule_and_fingerprint_includes_it(self):
        p = self.policy()
        live = {'tables': []}
        with patch.object(engine, 'command', side_effect=self.command):
            engine.require_owned_present(p, live)
            with patch.object(engine, 'command', return_value=SimpleNamespace(returncode=0, stdout=output())):
                with self.assertRaisesRegex(Exception, 'Readiness: shared routing rule missing'):
                    engine.require_owned_present(p, live)
        with patch.object(engine, 'require_owned_present'), \
                patch.object(engine, 'command', return_value=SimpleNamespace(stdout='{}')), \
                patch.object(engine, '_inventory_chain', return_value=[{'comment': COMMENT, 'text': RULE, 'handle': 10}]):
            one = boot.fingerprint(p, live)
        changed = {**DESC, 'text': RULE.replace('10.1.0.0/24', '10.2.0.0/24')}
        p2 = {**p, 'shared_rules': [changed]}
        with patch.object(engine, 'require_owned_present'), \
                patch.object(engine, 'command', return_value=SimpleNamespace(stdout='{}')), \
                patch.object(engine, '_inventory_chain', return_value=[{'comment': COMMENT, 'text': changed['text'], 'handle': 11}]):
            two = boot.fingerprint(p2, live)
        self.assertNotEqual(one, two)

    def test_readiness_rejects_foreign_terminal_rule_before_shared_rule(self):
        p = self.policy()
        blocked = 'counter drop comment "operator-deny"'
        with patch.object(engine, 'command', return_value=SimpleNamespace(
                returncode=0, stdout=output(blocked, RULE))):
            with self.assertRaisesRegex(Exception, 'foreign terminal rule precedes shared routing'):
                engine.require_owned_present(p, {'tables': []})

    def test_fingerprint_ignores_kernel_counter_values_and_canonical_spelling(self):
        p = self.policy()
        kernel = ('iifname tun0 oifname br-test ip saddr 10.1.0.0/24 ip daddr 192.0.2.0/24 '
                  'counter packets 91 bytes 4096 accept comment "' + COMMENT + '"')
        live = {'tables': []}
        with patch.object(engine, 'require_owned_present'), \
                patch.object(engine, 'command', return_value=SimpleNamespace(stdout='{}')), \
                patch.object(engine, '_inventory_chain', return_value=[{'comment': COMMENT, 'text': RULE, 'handle': 10}]):
            original = boot.fingerprint(p, live)
        with patch.object(engine, 'require_owned_present'), \
                patch.object(engine, 'command', return_value=SimpleNamespace(stdout='{}')), \
                patch.object(engine, '_inventory_chain', return_value=[{'comment': COMMENT, 'text': kernel, 'handle': 37}]):
            normalized = boot.fingerprint(p, live)
        self.assertEqual(original, normalized)


if __name__ == '__main__':
    unittest.main()
