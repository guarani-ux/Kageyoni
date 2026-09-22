"""V2 behavior tests over disposable records; no campaign or model calls."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.intelligence.expression import Expression
from kageyoni.intelligence.methods import Methods
from kageyoni.intelligence.nodes import Nodes
from kageyoni.persistence.migrations import install_methods


class ExpressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'synthetic.sqlite'
        self.e = Engine(self.path)
        changes = []
        for character in ('maker', 'reader'):
            changes.append(self.create('character', character, name=character, entity_kind='person'))
        changes.append(self.create('knowledge', 'method-basis', holder='maker', assertion='Synthetic comparison practice', attitude='believes'))
        for identifier, value in (('short-time', 20), ('long-time', 40), ('short-checks', 3), ('long-checks', 5)):
            changes.append(self.create('resource', identifier, holder='maker', name=identifier, quantity=value, unit='fixture'))
        changes.append(dict(self.create('knowledge', 'secret', holder='maker', assertion='PRIVATE_SOURCE_CANARY', attitude='knows'), visibility='gm'))
        self.apply(changes)
        install_methods(self.e)
        self.nodes = Nodes(self.e)
        self.node_id = self.nodes.bind('main', 'maker', 'bind-maker', 1, {'note': 'Synthetic operational fixture'})['node_id']
        self.methods = Methods(self.e)
        self.expression = Expression(self.e, self.methods)
        self.method = self.add_method()
        self.task = self.make_task()

    def tearDown(self):
        self.e.close()
        self.temp.cleanup()

    @staticmethod
    def create(domain, identifier, **data):
        return {'op': 'create', 'domain': domain, 'id': identifier, 'status': 'proposed',
                'visibility': 'public', 'evidence': [{'note': 'OWNER_METADATA_CANARY'}], 'data': data}

    def apply(self, changes):
        revision = self.e.branch('main')['revision']
        return self.e.apply({'api_version': 3, 'branch': 'main', 'expected_revision': revision,
                             'request_id': 'event-' + str(revision), 'kind': 'action', 'actor': 'fixture',
                             'narrative': 'Synthetic fixture only', 'changes': changes})

    def definition(self, *, field='time', direction='minimize', name='Compare bounded costs', operation=None):
        return {'name': name, 'operation': operation or {'kind': 'constraint_rank', 'params': {
                    'criteria': [{'field': field, 'weight': 1, 'direction': direction}], 'max_results': 2}},
                'rationale': 'Try this recorded method on supplied values; meanings are operator hypotheses.',
                'domains': ['planning'], 'preconditions': ['sources_current'],
                'failure_conditions': ['stale_source'], 'checking_procedure': ['check_source_fields'],
                'visibility': 'public'}

    def add_method(self, definition=None, identifier='first', source='method-basis', qualification='experimental'):
        method = self.methods.create('main', self.node_id, 'create-' + identifier,
                                     self.e.branch('main')['revision'], definition or self.definition(),
                                     [self.expression.source_ref('main', source)])
        self.methods.assign('main', self.node_id, method['method_id'], 1, 'assign-' + identifier,
                            self.e.branch('main')['revision'], qualification, 'Synthetic bounded trial')
        return method

    def revise(self, definition):
        method = self.methods.revise('main', self.node_id, self.method['method_id'], 1, 'revise-method',
                                     self.e.branch('main')['revision'], definition,
                                     [self.expression.source_ref('main', 'method-basis')])
        self.methods.assign('main', self.node_id, method['method_id'], 2, 'assign-revision',
                            self.e.branch('main')['revision'], 'experimental', 'Explicit replacement trial',
                            expected_assignment_revision=1)
        return method

    def make_task(self):
        refs = {identifier: self.expression.source_ref('main', identifier)
                for identifier in ('short-time', 'long-time', 'short-checks', 'long-checks')}
        def claim(identifier, value):
            return {'value': value, 'evidence': [{'source_ref': refs[identifier], 'field_path': ['data', 'quantity']}]}
        return {'task_id': 'editing-choice', 'revision': 1, 'domain': 'planning',
                'objective': 'Compare recorded hypothetical plans.', 'source_refs': list(refs.values()),
                'candidates': [
                    {'id': 'short', 'label': 'Short edit', 'claims': {'time': claim('short-time', 20), 'checks': claim('short-checks', 3)}},
                    {'id': 'long', 'label': 'Detailed edit', 'claims': {'time': claim('long-time', 40), 'checks': claim('long-checks', 5)}},
                ]}

    def execute(self, task=None, **kwargs):
        return self.expression.execute('main', 'maker', task or self.task, **kwargs)

    @staticmethod
    def ranking(result):
        return [r['candidate_id'] for r in result['artifact']['content']['results'][0]['result']['ranked']]

    def test_actual_rank_contains_exact_checked_terms(self):
        result = self.execute()
        self.assertEqual(self.ranking(result), ['short', 'long'])
        self.assertEqual(result['artifact']['digest'], digest(result['artifact']['content']))
        term = result['artifact']['content']['results'][0]['result']['ranked'][0]['terms'][0]
        self.assertEqual(term['recorded_value'], 20)
        self.assertEqual(term['evidence'][0]['source_ref']['id'], 'short-time')
        self.assertEqual(term['evidence'][0]['check'], 'exact_match')
        self.assertEqual(result['limits']['semantic_judgment'], 'not_performed')
        self.assertEqual(result['objective_scope'], 'registered_operation')
        self.assertEqual(result['task_objective'], 'unresolved')
        self.assertEqual(self.e.branch('main')['revision'], 1)

    def test_node_rename_and_task_paraphrase_do_not_change_calculation(self):
        before = self.execute()
        self.apply([{'op': 'patch', 'id': 'maker', 'expected_version': 1,
                     'data': {'name': 'Another display name'}, 'evidence': [{'note': 'Synthetic rename'}]}])
        task = deepcopy(self.task)
        task['objective'] = 'A paraphrase of the same comparison.'
        task['candidates'][0]['label'] = 'Different label'
        task['candidates'].reverse()
        after = self.execute(task)
        self.assertEqual(before['artifact'], after['artifact'])
        self.assertNotEqual(before['binding']['task_digest'], after['binding']['task_digest'])

    def test_name_only_method_revision_is_not_differentiation(self):
        before = self.execute()
        self.revise(self.definition(name='A dramatic new name'))
        after = self.execute()
        self.assertEqual(before['artifact'], after['artifact'])
        self.assertNotEqual(before['binding']['methods'], after['binding']['methods'])

    def test_relevant_method_revision_changes_approach(self):
        before = self.execute()
        self.revise(self.definition(field='checks', direction='maximize'))
        after = self.execute()
        self.assertEqual(self.ranking(before), ['short', 'long'])
        self.assertEqual(self.ranking(after), ['long', 'short'])
        self.assertNotEqual(before['artifact']['digest'], after['artifact']['digest'])

    def test_unrelated_citation_cannot_launder_a_number(self):
        task = deepcopy(self.task)
        for candidate in task['candidates']:
            candidate['claims']['time']['value'] = 999
        result = self.execute(task)
        self.assertEqual(result['phase'], 'blocked')
        self.assertIsNone(result['artifact'])
        self.assertEqual(self.expression.prepare('main', 'maker', task)['phase'], 'blocked')

    def test_unmatched_one_candidate_does_not_win_by_low_value(self):
        task = deepcopy(self.task)
        task['candidates'][0]['claims']['time']['value'] = -100
        self.assertEqual(self.ranking(self.execute(task)), ['long'])

    def test_missing_evidence_and_bool_do_not_become_numeric(self):
        task = deepcopy(self.task)
        task['candidates'][0]['claims']['time']['evidence'] = []
        task['candidates'][1]['claims']['time']['value'] = True
        self.assertEqual(self.execute(task)['phase'], 'blocked')

    def test_stale_source_and_stale_prepared_task_rejected(self):
        prepared = self.expression.prepare('main', 'maker', self.task)
        changed = deepcopy(self.task)
        changed['objective'] = 'A materially different requested task.'
        with self.assertRaises(Rejected):
            self.execute(changed, prepared=prepared)
        self.apply([{'op': 'patch', 'id': 'short-time', 'expected_version': 1,
                     'data': {'quantity': 30}, 'evidence': [{'note': 'Synthetic correction'}]}])
        with self.assertRaisesRegex(Rejected, 'source unavailable or stale'):
            self.execute(prepared=prepared)

    def test_stale_method_excluded_and_prepared_rejected(self):
        prepared = self.expression.prepare('main', 'maker', self.task)
        self.apply([{'op': 'patch', 'id': 'method-basis', 'expected_version': 1,
                     'data': {'assertion': 'Changed practice basis'}, 'evidence': [{'note': 'Synthetic correction'}]}])
        self.assertEqual(self.execute()['phase'], 'blocked')
        with self.assertRaises(Rejected):
            self.execute(prepared=prepared)

    def test_private_source_never_enters_public_context(self):
        task = deepcopy(self.task)
        task['source_refs'].append(self.expression.source_ref('main', 'secret'))
        with self.assertRaisesRegex(Rejected, '^source unavailable or stale$'):
            self.execute(task, viewer='reader')
        rendered = json.dumps(self.execute(viewer='reader'))
        self.assertNotIn('PRIVATE_SOURCE_CANARY', rendered)
        self.assertNotIn('OWNER_METADATA_CANARY', rendered)

    def test_private_metadata_path_rejected(self):
        task = deepcopy(self.task)
        task['candidates'][0]['claims']['time'] = {'value': 'OWNER_METADATA_CANARY', 'evidence': [
            {'source_ref': task['source_refs'][0], 'field_path': ['evidence', 0, 'note']}]}
        with self.assertRaisesRegex(Rejected, 'record data'):
            self.execute(task, viewer='reader')

    def test_unassigned_domain_cannot_grant_expertise(self):
        task = deepcopy(self.task)
        task['domain'] = 'unqualified-medical-diagnosis'
        result = self.execute(task)
        self.assertEqual(result['phase'], 'blocked')
        self.assertIsNone(result['artifact'])
        self.assertEqual(result['binding']['methods'], [])

    def test_unknown_guard_waits_and_never_claims_host_execution(self):
        definition = self.definition()
        definition['preconditions'].append('obtain the owner\'s approval')
        self.revise(definition)
        result = self.execute()
        self.assertEqual(result['phase'], 'waiting')
        self.assertFalse(result['checks_passed'])
        self.assertIsNone(result['artifact'])
        self.assertEqual(result['judgment_packet']['mode'], 'manual_or_subscription_native_host')
        self.assertEqual(result['judgment_packet']['execution_claim'], 'No host or external model has run.')

    def test_unknown_operation_is_unfinished_manual_work(self):
        self.revise(self.definition(operation={'kind': 'interpret_symbolism', 'params': {'question': 'What might this mean?'}}))
        result = self.execute()
        self.assertEqual(result['phase'], 'waiting')
        self.assertIsNone(result['artifact'])

    def test_counterexample_detects_conflict_without_proving_truth(self):
        self.revise(self.definition(operation={'kind': 'counterexample_check', 'params': {'fields': ['time']}}))
        task = deepcopy(self.task)
        task['candidates'][0]['counterclaims'] = {'time': deepcopy(task['candidates'][1]['claims']['time'])}
        result = self.execute(task)
        observations = result['artifact']['content']['results'][0]['result']['observations']
        by_id = {row['candidate_id']: row for row in observations}
        self.assertEqual(by_id['short']['fields'][0]['state'], 'conflicting_recorded_values')
        self.assertEqual(by_id['long']['fields'][0]['state'], 'no_supplied_conflict')
        self.assertEqual(result['limits']['semantic_judgment'], 'not_performed')

    def test_all_method_and_task_dependencies_bound(self):
        result = self.execute()
        self.assertEqual({r['id'] for r in result['binding']['sources']},
                         {'method-basis', 'short-time', 'long-time', 'short-checks', 'long-checks'})

    def test_prepare_mutation_and_viewer_change_rejected(self):
        prepared = self.expression.prepare('main', 'maker', self.task)
        with self.assertRaises(Rejected):
            self.execute(viewer='reader', prepared=prepared)
        prepared['task']['candidates'][0]['claims']['time']['value'] = -999
        with self.assertRaises(Rejected):
            self.execute(prepared=prepared)

    def test_reopened_methods_keep_real_operation_behavior(self):
        before = self.execute()
        self.e.close()
        self.e = Engine(self.path)
        self.expression = Expression(self.e)
        after = self.execute()
        self.assertEqual(before, after)

    def test_nonfinite_and_oversized_input_rejected(self):
        for value in (float('inf'), float('nan'), 10**400):
            task = deepcopy(self.task)
            task['candidates'][0]['claims']['time']['value'] = value
            with self.assertRaises(Rejected):
                self.execute(task)
        task = deepcopy(self.task)
        task['candidates'] = [dict(task['candidates'][0], id=str(i)) for i in range(101)]
        with self.assertRaises(Rejected):
            self.execute(task)

    def test_score_precision_preserves_small_but_real_difference(self):
        from kageyoni.execution.operations import run
        operation = {'kind': 'constraint_rank', 'params': {'criteria': [
            {'field': 'large', 'direction': 'maximize', 'weight': 1},
            {'field': 'small', 'direction': 'maximize', 'weight': 1}]}}
        def candidate(identifier, small):
            return {'id': identifier, 'counterclaims': {}, 'claims': {
                field: {'value': value, 'support': 'matched', 'evidence': []}
                for field, value in [('large', 1e30), ('small', small)]}}
        result = run(operation, [candidate('a-lower', 1), candidate('z-higher', 2)])
        self.assertEqual([row['candidate_id'] for row in result['ranked']], ['z-higher', 'a-lower'])


if __name__ == '__main__':
    unittest.main()
