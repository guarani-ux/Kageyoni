"""Independent V2 failure scenarios; all worlds and methods are synthetic.

These tests exercise trust and applicability boundaries, not the claimed
intelligence or usefulness of a character. No campaign data is opened.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.intelligence.nodes import Nodes
from kageyoni.intelligence.methods import Methods
from kageyoni.intelligence.expression import Expression
from kageyoni.persistence.contributions import Contributions
from kageyoni.persistence.migrations import install_contributions


class V2AdversarialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'adversarial.sqlite'
        self.engine = Engine(self.path)
        self.serial = 0
        records = [
            self.record('character', 'a', name='Fixture A', entity_kind='person'),
            self.record('character', 'b', name='Fixture B', entity_kind='person'),
            self.record('character', 'hidden-holder', visibility='gm',
                        name='PRIVATE-HOLDER-CANARY', entity_kind='person'),
            self.record('knowledge', 'method-source', holder='a',
                        assertion='Synthetic proposed quantity-comparison procedure.',
                        attitude='believes'),
            self.record('resource', 'low-stock', holder='a', name='Low stock',
                        quantity=2, unit='fixture units'),
            self.record('resource', 'high-stock', holder='a', name='High stock',
                        quantity=9, unit='fixture units'),
            self.record('resource', 'hidden-stock', visibility='gm', holder='a',
                        name='PRIVATE-STOCK-CANARY', quantity=777,
                        unit='fixture units'),
            self.record('resource', 'public-secret-reference', holder='hidden-holder',
                        name='Public resource with a hidden owner', quantity=4,
                        unit='fixture units'),
        ]
        # A record may be public while its provenance is owner-only.
        records[4]['evidence'] = [{'note': 'PRIVATE-PROVENANCE-CANARY', 'value': 991}]
        self.world_event(records)
        install_contributions(self.engine)
        self.node_id = Nodes(self.engine).bind(
            'main', 'a', 'fixture-bind', 1, {'note': 'Synthetic fixture only'}
        )['node_id']
        self.methods = Methods(self.engine)
        self.expression = Expression(self.engine, self.methods)
        self.contributions = Contributions(self.engine)

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    @staticmethod
    def record(domain, record_id, visibility='public', **data):
        return {'op': 'create', 'domain': domain, 'id': record_id,
                'visibility': visibility, 'status': 'proposed',
                'evidence': [{'note': 'Synthetic adversarial fixture only'}],
                'data': data}

    def world_event(self, changes, branch='main'):
        self.serial += 1
        return self.engine.apply({
            'api_version': 3, 'branch': branch,
            'expected_revision': self.engine.branch(branch)['revision'],
            'request_id': 'fixture-event-' + str(self.serial),
            'kind': 'action', 'actor': 'fixture', 'narrative': 'Synthetic fixture',
            'changes': changes,
        })

    def ref(self, record_id, branch='main'):
        record = self.engine.get(branch, record_id)
        return {'domain': record['domain'], 'id': record_id,
                'record_revision': record['version'], 'snapshot_hash': digest(record)}

    def method(self, *, kind='constraint_rank', preconditions=None,
               failure_conditions=None, checking_procedure=None, source='method-source'):
        self.serial += 1
        definition = {
            'name': 'Synthetic method ' + str(self.serial),
            'operation': {'kind': kind, 'params': (
                {'criteria': [{'field': 'stock', 'weight': 1,
                               'direction': 'maximize', 'required': True}]}
                if kind == 'constraint_rank' else {'fields': ['stock']})},
            'rationale': 'Explicit operator-authored trial, not demonstrated mastery.',
            'domains': ['fixture-choice'],
            'preconditions': preconditions if preconditions is not None else
                ['task_domain_matches', 'sources_current'],
            'failure_conditions': failure_conditions if failure_conditions is not None else
                ['missing_support', 'stale_source'],
            'checking_procedure': checking_procedure if checking_procedure is not None else
                ['check_source_fields'],
            'roles': ['candidate', 'observation'],
            'relationships': [{'source': 'observation', 'relation': 'supports',
                               'target': 'candidate'}],
            'visibility': 'public', 'audience': [],
        }
        receipt = self.methods.create(
            'main', self.node_id, 'method-create-' + str(self.serial),
            self.engine.branch('main')['revision'], definition, [self.ref(source)]
        )
        assignment_args = dict(
            branch='main', node_id=self.node_id, method_id=receipt['method_id'],
            method_revision=1, request_id='method-assign-' + str(self.serial),
            expected_world_revision=self.engine.branch('main')['revision'],
            qualification='experimental', rationale='Bounded synthetic trial only',
        )
        assignment = self.methods.assign(**assignment_args)
        return receipt, assignment_args, assignment

    def task(self, *, source='high-stock', value=9, field_path=None):
        ref = self.ref(source)
        return {
            'task_id': 'fixture-task', 'revision': 1, 'domain': 'fixture-choice',
            'objective': 'Compare recorded quantities without establishing expertise.',
            'source_refs': [ref],
            'candidates': [{'id': 'candidate', 'label': 'Fixture candidate',
                            'claims': {'stock': {'value': value, 'evidence': [{
                                'source_ref': copy.deepcopy(ref),
                                'field_path': field_path or ['data', 'quantity'],
                            }]}}, 'counterclaims': {}}],
        }

    def test_valid_trial_and_invented_value_cannot_share_a_success(self):
        self.method(preconditions=['claims_match_recorded_fields'])
        valid = self.expression.execute('main', 'a', self.task(), viewer='b')
        self.assertEqual(valid['phase'], 'completed')
        # Merely citing a valid source does not support a fabricated number.
        invalid = self.expression.execute('main', 'a', self.task(value=9000), viewer='b')
        self.assertNotEqual(invalid['phase'], 'completed')
        self.assertIsNone(invalid.get('artifact'))

    def test_owner_provenance_is_not_a_public_claim_source(self):
        self.method(preconditions=['claims_match_recorded_fields'])
        task = self.task(source='low-stock', value=991,
                         field_path=['evidence', 0, 'value'])
        # The raw public record contains this number; its public projection does not.
        with self.assertRaises(Rejected) as failure:
            self.expression.execute('main', 'a', task, viewer='b')
        self.assertNotIn('PRIVATE-PROVENANCE-CANARY', str(failure.exception))

    def test_hidden_reference_from_public_record_cannot_become_claim(self):
        self.method(kind='counterexample_check',
                    preconditions=['claims_match_recorded_fields'],
                    failure_conditions=['stale_source'],
                    checking_procedure=['compare_counterclaims'])
        task = self.task(source='public-secret-reference', value='hidden-holder',
                         field_path=['data', 'holder'])
        invalid = self.expression.execute('main', 'a', task, viewer='b')
        self.assertNotEqual(invalid['phase'], 'completed')
        self.assertIsNone(invalid.get('artifact'))

    def test_owner_packet_cannot_be_reused_by_another_viewer(self):
        self.method()
        task = self.task(source='hidden-stock', value=777)
        prepared = self.expression.prepare('main', 'a', task)
        self.assertEqual(self.expression.execute('main', 'a', task,
                         prepared=prepared)['phase'], 'completed')
        with self.assertRaises(Rejected):
            self.expression.execute('main', 'a', task, viewer='b', prepared=prepared)

    def test_forged_packet_cannot_replace_method_even_with_recomputed_fingerprint(self):
        self.method()
        task = self.task()
        original = self.expression.prepare('main', 'a', task, viewer='b')
        self.assertEqual(self.expression.execute('main', 'a', task, viewer='b',
                         prepared=original)['phase'], 'completed')
        forged = copy.deepcopy(original)
        forged['methods'][0]['definition']['operation']['params']['criteria'][0][
            'direction'] = 'minimize'
        forged.pop('fingerprint')
        forged['fingerprint'] = digest(forged)
        with self.assertRaises(Rejected):
            self.expression.execute('main', 'a', task, viewer='b', prepared=forged)

    def test_changed_source_hides_prior_contribution_but_owner_keeps_receipt(self):
        self.method()
        saved = self.contributions.run('main', 'a', 'save-public', self.task(), viewer='b')
        self.assertEqual(self.contributions.read('main', saved['contribution_id'],
                         viewer='b')['receipt']['phase'], 'completed')
        self.world_event([{'op': 'patch', 'id': 'high-stock', 'expected_version': 1,
                           'visibility': 'gm', 'data': {},
                           'evidence': [{'note': 'Synthetic visibility change'}]}])
        with self.assertRaises(Rejected):
            self.contributions.read('main', saved['contribution_id'], viewer='b')
        self.assertEqual(self.contributions.read('main', saved['contribution_id'])
                         ['receipt']['artifact_digest'], saved['artifact_digest'])
        self.assertTrue(self.engine.verify()['ok'])

    def test_unknown_guard_waits_and_saved_wait_is_readable_and_replayable(self):
        self.method(preconditions=['obtain explicit owner approval before choosing'])
        task = self.task()
        result = self.expression.execute('main', 'a', task, viewer='b')
        self.assertEqual(result['phase'], 'waiting')
        self.assertIsNone(result.get('artifact'))
        one = self.contributions.run('main', 'a', 'save-wait', task, viewer='b')
        self.assertEqual(self.contributions.read('main', one['contribution_id'],
                         viewer='b')['receipt']['phase'], 'waiting')
        two = self.contributions.run('main', 'a', 'save-wait', task, viewer='b')
        self.assertTrue(two['replayed'])
        self.assertEqual(one['contribution_id'], two['contribution_id'])

    def test_waiting_receipt_rechecks_method_source_not_only_task_sources(self):
        self.method(preconditions=['obtain explicit owner approval before choosing'])
        saved = self.contributions.run('main', 'a', 'method-source-wait',
                                       self.task(), viewer='b')
        self.assertEqual(saved['phase'], 'waiting')
        self.world_event([{'op': 'patch', 'id': 'method-source', 'expected_version': 1,
                           'visibility': 'gm', 'data': {},
                           'evidence': [{'note': 'Synthetic privacy change'}]}])
        with self.assertRaises(Rejected):
            self.contributions.read('main', saved['contribution_id'], viewer='b')
        historical = self.contributions.read('main', saved['contribution_id'])
        self.assertEqual(historical['receipt']['phase'], 'waiting')
        self.assertEqual(historical['receipt']['result_digest'], saved['result_digest'])

    def test_registered_but_inapplicable_guard_is_not_assumed_satisfied(self):
        self.method(kind='counterexample_check', preconditions=['numeric_criteria'],
                    failure_conditions=['stale_source'],
                    checking_procedure=['compare_counterclaims'])
        result = self.expression.execute('main', 'a', self.task(), viewer='b')
        self.assertEqual(result['phase'], 'waiting')
        self.assertIsNone(result.get('artifact'))

    def test_replayed_old_assignment_does_not_undo_revocation(self):
        created, original, assignment = self.method()
        self.assertEqual(self.expression.execute('main', 'a', self.task(), viewer='b')
                         ['phase'], 'completed')
        self.methods.assign(
            'main', self.node_id, created['method_id'], 1, 'revoke-method', 1,
            'revoked', 'Synthetic trial revoked', expected_assignment_revision=1)
        replayed = self.methods.assign(**original)
        self.assertTrue(replayed['replayed'])
        self.assertEqual(self.expression.execute('main', 'a', self.task(), viewer='b')
                         ['phase'], 'blocked')

    def test_unassigned_private_draft_cannot_suppress_active_public_revision(self):
        created, _, _ = self.method()
        original = self.methods.read('main', created['method_id'], 1)
        private_draft = copy.deepcopy(original['definition'])
        private_draft['name'] = 'PRIVATE-DRAFT-CANARY'
        private_draft['visibility'] = 'gm'
        self.methods.revise(
            'main', self.node_id, created['method_id'], 1, 'private-draft', 1,
            private_draft, [self.ref('hidden-stock')])
        eligible = self.methods.eligible('main', 'a', 'fixture-choice', viewer='b')
        self.assertEqual([(m['method_id'], m['revision']) for m in eligible],
                         [(created['method_id'], 1)])
        result = self.expression.execute('main', 'a', self.task(), viewer='b')
        self.assertEqual(result['phase'], 'completed')
        self.assertNotIn('PRIVATE-DRAFT-CANARY', json.dumps(result))

    def test_explicit_shared_node_on_fork_does_not_inherit_methods(self):
        self.method()
        self.engine.fork('main', 'alternate', 1)
        Nodes(self.engine).bind('alternate', 'a', 'bind-alternate', 0,
                               {'note': 'Explicit identity link only'}, node_id=self.node_id)
        fork_task = self.task()
        fork_task['source_refs'] = [self.ref('high-stock', 'alternate')]
        fork_task['candidates'][0]['claims']['stock']['evidence'][0]['source_ref'] = (
            copy.deepcopy(fork_task['source_refs'][0]))
        result = self.expression.execute('alternate', 'a', fork_task, viewer='b')
        self.assertEqual(result['phase'], 'blocked')
        self.assertEqual(self.expression.execute('main', 'a', self.task(), viewer='b')
                         ['phase'], 'completed')


if __name__ == '__main__':
    unittest.main()
