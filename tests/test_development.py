"""V3 consequence -> reviewed lesson -> changed later operation, on synthetic data."""
from copy import deepcopy
import json
import unittest

import test_expression as fixtures
from kageyoni.engine import Engine, Rejected, digest
from kageyoni.intelligence.development import context_matches
from kageyoni.intelligence.expression import Expression
from kageyoni.intelligence.methods import Methods
from kageyoni.persistence.contributions import Contributions
from kageyoni.persistence.migrations import install_learning


class DevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ExpressionTests(methodName='runTest')
        self.fixture.setUp()
        install_learning(self.e)
        from kageyoni.intelligence.learning import Learning
        self.learning = Learning(self.e)
        self.task = deepcopy(self.fixture.task)
        self.task['context'] = {'priority': 'detail'}
        receipt = Contributions(self.e).run('main', 'maker', 'development-source', self.task)
        self.origin = receipt['contribution_id']
        self.outcome = self.observe(self.origin, 'source', 1)

    @property
    def e(self):
        return self.fixture.e

    def tearDown(self):
        self.fixture.tearDown()

    def observe(self, contribution_id, label, value):
        identifier = 'feedback-' + label
        self.fixture.apply([self.fixture.create('resource', identifier, holder='maker',
                                               name='Synthetic later feedback', quantity=value, unit='fixture')])
        source = self.fixture.expression.source_ref('main', identifier)
        return self.learning.record_outcome('main', contribution_id, 'outcome-' + label,
            self.e.branch('main')['revision'], {
                'status': 'not_achieved', 'rationale': 'Operator interprets synthetic later feedback; no causal proof claimed.',
                'measurements': [{'value': value, 'evidence': {'source_ref': source, 'field_path': ['data', 'quantity']}}],
            })

    def definition(self, *, direction='maximize', name='Prioritize detailed checking in this context'):
        return {'name': name, 'rationale': 'A bounded operator-reviewed response to synthetic later feedback.',
                'method_id': self.fixture.method['method_id'], 'method_revision': 1,
                'task_domain': 'planning', 'context_conditions': [{'key': 'priority', 'equals': 'detail'}],
                'operation_params': {'criteria': [{'field': 'checks', 'weight': 1, 'direction': direction}], 'max_results': 2},
                'visibility': 'gm'}

    def propose(self, label='one', definition=None):
        return self.learning.propose('main', self.fixture.node_id, 'lesson-' + label,
            self.e.branch('main')['revision'], definition or self.definition(), [self.outcome['outcome_id']])

    def qualify(self, label='one', definition=None):
        lesson = self.propose(label, definition)
        self.learning.review('main', lesson['lesson_id'], 1, 'qualify-' + label,
            self.e.branch('main')['revision'], 'qualified', 'Qualified only for an evidenced bounded trial.')
        return lesson

    def execute(self, task=None, **kwargs):
        return self.fixture.expression.execute('main', 'maker', task or self.task, **kwargs)

    @staticmethod
    def ranking(result):
        return fixtures.ExpressionTests.ranking(result)

    def test_real_qualified_lesson_changes_fixed_method_and_fixed_task(self):
        before = self.execute()
        stored_before = self.fixture.methods.read('main', self.fixture.method['method_id'])
        world_before = self.e.state()
        lesson = self.qualify()
        after = self.execute()
        self.assertEqual(self.ranking(before), ['short', 'long'])
        self.assertEqual(self.ranking(after), ['long', 'short'])
        self.assertEqual(before['binding']['task_digest'], after['binding']['task_digest'])
        self.assertEqual(before['binding']['methods'], after['binding']['methods'])
        self.assertEqual(before['binding']['world_revision'], after['binding']['world_revision'])
        self.assertEqual(stored_before, self.fixture.methods.read('main', self.fixture.method['method_id']))
        self.assertEqual(world_before, self.e.state())
        self.assertEqual(after['binding']['lessons'][0]['lesson_id'], lesson['lesson_id'])
        self.assertEqual(after['task_objective'], 'unresolved')
        self.assertEqual(after['development']['applications'][0]['base_operation']['params']['criteria'][0]['field'], 'time')
        self.assertEqual(after['development']['applications'][0]['effective_operation']['params']['criteria'][0]['field'], 'checks')

    def test_recording_and_proposing_alone_do_not_change_behavior(self):
        before = self.execute()
        self.propose()
        after = self.execute()
        self.assertEqual(before['artifact'], after['artifact'])
        self.assertNotIn('lessons', after['binding'])

    def test_irrelevant_or_extended_context_gets_base_behavior(self):
        self.qualify()
        for context in ({}, {'priority': 'speed'}, {'priority': 'detail', 'extra': True}, {'priority': None}):
            with self.subTest(context=context):
                task = deepcopy(self.task)
                task['context'] = context
                result = self.execute(task)
                self.assertEqual(self.ranking(result), ['short', 'long'])
                self.assertNotIn('lessons', result['binding'])

    def test_context_types_and_absence_are_not_conflated(self):
        self.assertFalse(context_matches([{'key': 'mode', 'equals': True}], {'mode': 1}))
        self.assertFalse(context_matches([{'key': 'mode', 'equals': False}], {'mode': 0}))
        self.assertFalse(context_matches([{'key': 'mode', 'equals': None}], {}))
        self.assertTrue(context_matches([{'key': 'mode', 'equals': None}], {'mode': None}))

    def test_conflicting_qualified_lessons_block_instead_of_last_wins(self):
        one = self.qualify('one')
        two = self.qualify('two', self.definition(direction='minimize'))
        result = self.execute()
        self.assertEqual(result['phase'], 'blocked')
        self.assertIsNone(result['artifact'])
        self.assertEqual({row['lesson_id'] for row in result['binding']['lessons']}, {one['lesson_id'], two['lesson_id']})
        self.assertEqual(len(result['development']['conflicts']), 1)

    def test_equivalent_lessons_apply_one_transform_with_all_provenance(self):
        self.qualify('one')
        self.qualify('two', self.definition(name='Same intervention from the same experience'))
        result = self.execute()
        self.assertEqual(self.ranking(result), ['long', 'short'])
        self.assertEqual(len(result['development']['applications']), 1)
        self.assertEqual(len(result['development']['applications'][0]['lesson_ids']), 2)
        self.assertEqual(result['development']['conflicts'], [])

    def test_qualification_invalidates_prior_prepared_packet(self):
        prepared = self.fixture.expression.prepare('main', 'maker', self.task)
        self.qualify()
        with self.assertRaisesRegex(Rejected, 'prepared contribution'):
            self.execute(prepared=prepared)

    def test_contradicted_lesson_stops_affecting_later_choice(self):
        lesson = self.qualify()
        self.assertEqual(self.ranking(self.execute()), ['long', 'short'])
        later = Contributions(self.e).run('main', 'maker', 'counter-source', self.task)
        counter = self.observe(later['contribution_id'], 'counter', 0)
        self.learning.review('main', lesson['lesson_id'], 1, 'contest-one', self.e.branch('main')['revision'],
            'contested', 'Contrary synthetic observation suspends the prior interpretation.',
            expected_review_revision=1, counter_outcome_ids=[counter['outcome_id']])
        result = self.execute()
        self.assertEqual(self.ranking(result), ['short', 'long'])
        self.assertNotIn('lessons', result['binding'])

    def test_retired_lesson_stops_affecting_later_choice(self):
        lesson = self.qualify()
        self.learning.review('main', lesson['lesson_id'], 1, 'retire-one', self.e.branch('main')['revision'],
            'retired', 'Operator retires this bounded interpretation.', expected_review_revision=1)
        self.assertEqual(self.ranking(self.execute()), ['short', 'long'])

    def test_revised_lesson_binds_retained_counterevidence_separately(self):
        lesson = self.qualify()
        later = Contributions(self.e).run('main', 'maker', 'counter-source', self.task)
        counter = self.observe(later['contribution_id'], 'counter', 0)
        self.learning.review('main', lesson['lesson_id'], 1, 'contest-one', self.e.branch('main')['revision'],
            'contested', 'Preserve this contrary observation.', expected_review_revision=1,
            counter_outcome_ids=[counter['outcome_id']])
        definition = self.definition()
        definition['operation_params']['criteria'].append({'field': 'time', 'weight': 0.1, 'direction': 'minimize'})
        self.learning.revise('main', self.fixture.node_id, lesson['lesson_id'], 1, 'revise-lesson',
            self.e.branch('main')['revision'], definition, [self.outcome['outcome_id']])
        self.learning.review('main', lesson['lesson_id'], 2, 'qualify-revision', self.e.branch('main')['revision'],
            'qualified', 'Revised bounded intervention retains the prior contrary outcome.')
        result = self.execute()
        binding = result['binding']['lessons'][0]
        self.assertEqual(binding['revision'], 2)
        self.assertEqual(binding['qualification'], 'qualified')
        self.assertEqual(binding['counterevidence_digest'], digest([counter['outcome_id']]))
        self.assertEqual([ref['id'] for ref in result['binding']['historical_sources']], ['feedback-counter'])
        self.assertNotIn('feedback-counter', [ref['id'] for ref in result['binding']['sources']])

    def test_exact_method_revision_pin_prevents_accidental_reuse(self):
        self.qualify()
        self.fixture.revise(self.fixture.definition(name='Revised method identity, same operation'))
        result = self.execute()
        self.assertEqual(self.ranking(result), ['short', 'long'])
        self.assertNotIn('lessons', result['binding'])

    def test_hidden_lesson_excluded_without_provenance_leak(self):
        self.qualify(definition=self.definition(name='PRIVATE_LESSON_CANARY'))
        result = self.execute(viewer='reader')
        self.assertEqual(self.ranking(result), ['short', 'long'])
        self.assertNotIn('PRIVATE_LESSON_CANARY', json.dumps(result))
        self.assertNotIn('lessons', result['binding'])

    def test_changed_feedback_requires_requalification_before_application(self):
        self.qualify()
        self.fixture.apply([{'op': 'patch', 'id': 'feedback-source', 'expected_version': 1,
                             'data': {'quantity': 9}, 'evidence': [{'note': 'Synthetic feedback correction'}]}])
        result = self.execute()
        self.assertEqual(self.ranking(result), ['short', 'long'])
        self.assertNotIn('lessons', result['binding'])

    def test_reopening_preserves_actual_developed_operation(self):
        self.qualify()
        before = self.execute()
        self.e.close()
        self.fixture.e = Engine(self.fixture.path)
        self.fixture.methods = Methods(self.e)
        self.fixture.expression = Expression(self.e)
        after = self.execute()
        self.assertEqual(before, after)
        self.assertEqual(self.ranking(after), ['long', 'short'])

    def test_context_rejects_nested_nonfinite_and_excess_inputs(self):
        for context in ({'mode': {}}, {'mode': float('nan')}, {str(i): i for i in range(33)}):
            task = deepcopy(self.task)
            task['context'] = context
            with self.assertRaises(Rejected):
                self.execute(task)


if __name__ == '__main__':
    unittest.main()
