"""Independent checks of bounded learning using synthetic route decisions.

The fixture separates arithmetic completion from subsequently observed strain.
It demonstrates a stored, reviewed intervention changing later choices; it does
not measure autonomous discovery or real-world general intelligence.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.intelligence.nodes import Nodes
from kageyoni.intelligence.methods import Methods
from kageyoni.intelligence.learning import Learning
from kageyoni.intelligence.expression import Expression
from kageyoni.persistence.contributions import Contributions
from kageyoni.persistence.migrations import install_learning


class V3AdversarialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'learning.sqlite'
        self.engine = Engine(self.path)
        self.serial = 0
        self.world_event([
            self.record('character', 'walker', name='Synthetic walker', entity_kind='person'),
            self.record('character', 'observer', name='Synthetic observer', entity_kind='person'),
            self.record('character', 'hidden-observer', visibility='gm',
                        name='PRIVATE-OBSERVER-CANARY', entity_kind='person'),
            self.record('character', 'outside-character', name='Initially public association',
                        entity_kind='person'),
            self.record('knowledge', 'method-source', holder='walker',
                        assertion='Synthetic preference for longer scenic routes.', attitude='believes'),
            self.record('resource', 'train-short', holder='walker', name='Training short distance',
                        quantity=2, unit='fixture distance'),
            self.record('resource', 'train-long', holder='walker', name='Training long distance',
                        quantity=9, unit='fixture distance'),
            self.record('resource', 'later-short', holder='walker', name='Heldout short distance',
                        quantity=3, unit='fixture distance'),
            self.record('resource', 'later-long', holder='walker', name='Heldout long distance',
                        quantity=7, unit='fixture distance'),
            self.record('resource', 'old-strain', holder='walker', name='An older observation',
                        quantity=8, unit='fixture strain'),
        ])
        install_learning(self.engine)
        self.node_id = Nodes(self.engine).bind(
            'main', 'walker', 'bind', 1, {'note': 'Synthetic fixture only'}
        )['node_id']
        self.methods = Methods(self.engine)
        self.learning = Learning(self.engine)
        self.expression = Expression(self.engine, self.methods)
        self.contributions = Contributions(self.engine)
        self.base_definition = {
            'name': 'Longer scenic route',
            'operation': {'kind': 'constraint_rank', 'params': self.params('maximize')},
            'rationale': 'An authored fixture preference, not a capability assessment.',
            'domains': ['fixture-routes'],
            'preconditions': ['sources_current', 'claims_match_recorded_fields'],
            'failure_conditions': ['missing_support', 'stale_source'],
            'checking_procedure': ['check_source_fields', 'recompute_scores'],
            'visibility': 'public', 'audience': [],
        }
        created = self.methods.create('main', self.node_id, 'create-method', 1,
                                      self.base_definition, [self.ref('method-source')])
        self.method_id = created['method_id']
        self.method_digest = created['digest']
        self.methods.assign('main', self.node_id, self.method_id, 1, 'assign-method', 1,
                            'experimental', 'Bounded synthetic trial')

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    @staticmethod
    def record(domain, record_id, visibility='public', **data):
        return {'op': 'create', 'domain': domain, 'id': record_id,
                'visibility': visibility, 'status': 'proposed',
                'evidence': [{'note': 'Synthetic learning fixture only'}], 'data': data}

    @staticmethod
    def params(direction):
        return {'criteria': [{'field': 'distance', 'weight': 1,
                              'direction': direction, 'required': True}]}

    def world_event(self, changes, branch='main'):
        self.serial += 1
        return self.engine.apply({
            'api_version': 3, 'branch': branch,
            'expected_revision': self.engine.branch(branch)['revision'],
            'request_id': 'event-' + str(self.serial), 'kind': 'action',
            'actor': 'fixture', 'narrative': 'Synthetic fixture observation',
            'changes': changes,
        })

    def ref(self, record_id, branch='main'):
        record = self.engine.get(branch, record_id)
        return {'domain': record['domain'], 'id': record_id,
                'record_revision': record['version'], 'snapshot_hash': digest(record)}

    def task(self, name='later', context=None, branch='main'):
        prefix = 'train' if name == 'train' else 'later'
        records = [prefix + '-short', prefix + '-long']
        refs = [self.ref(record_id, branch) for record_id in records]
        candidates = []
        for record_id, source in zip(records, refs):
            value = self.engine.get(branch, record_id)['data']['quantity']
            candidates.append({'id': record_id, 'claims': {'distance': {
                'value': value, 'evidence': [{'source_ref': copy.deepcopy(source),
                                             'field_path': ['data', 'quantity']}]}},
                               'counterclaims': {}})
        return {'task_id': name, 'revision': 1, 'domain': 'fixture-routes',
                'objective': 'Select one route using the bounded fixture method.',
                'candidates': candidates, 'source_refs': refs,
                'context': {'tired': True} if context is None else context}

    @staticmethod
    def winner(result):
        return result['artifact']['content']['results'][0]['result']['ranked'][0]['candidate_id']

    def observation(self, source, *, status='not_achieved'):
        return {'status': status,
                'rationale': 'OWNER-OUTCOME-RATIONALE-CANARY: interpretation of a later fixture measurement.',
                'measurements': [{'value': self.engine.get('main', source)['data']['quantity'],
                                  'evidence': {'source_ref': self.ref(source),
                                               'field_path': ['data', 'quantity']}}]}

    def measured_training(self, *, status='not_achieved', visibility='public'):
        trial = self.contributions.run('main', 'walker', 'training-contribution',
                                       self.task('train'), viewer='observer')
        self.assertEqual(self.winner(self.contributions.read('main', trial['contribution_id'])['result']),
                         'train-long')
        self.world_event([self.record('resource', 'observed-strain', visibility=visibility,
                                      holder='walker', name='Later measured strain',
                                      quantity=8, unit='fixture strain')])
        outcome = self.learning.record_outcome('main', trial['contribution_id'],
                                               'training-outcome', 2,
                                               self.observation('observed-strain', status=status))
        return trial, outcome

    def definition(self, *, conditions=None):
        return {'name': 'Shorter route when tired',
                'rationale': 'Proposed response to the later measured strain.',
                'method_id': self.method_id, 'method_revision': 1,
                'task_domain': 'fixture-routes',
                'context_conditions': ([{'key': 'tired', 'equals': True}]
                                       if conditions is None else conditions),
                'operation_params': self.params('minimize'),
                'visibility': 'public', 'audience': []}

    def propose(self, outcome, *, definition=None, request='propose-lesson'):
        return self.learning.propose('main', self.node_id, request,
                                     self.engine.branch('main')['revision'],
                                     definition or self.definition(), [outcome['outcome_id']])

    def qualify(self, lesson, *, request='qualify-lesson', **kwargs):
        return self.learning.review('main', lesson['lesson_id'], lesson['revision'], request,
                                    self.engine.branch('main')['revision'], 'qualified',
                                    'Bounded reviewed fixture intervention', **kwargs)

    def counter_outcome(self, *, visibility='public'):
        trial = self.contributions.run('main', 'walker', 'counter-trial',
                                       self.task('counter-trial'), viewer='observer')
        self.world_event([self.record('resource', 'counter-strain', visibility=visibility,
                                      holder='walker', name='COUNTER-STRAIN-CANARY',
                                      quantity=10, unit='fixture strain')])
        return self.learning.record_outcome(
            'main', trial['contribution_id'], 'counter-outcome',
            self.engine.branch('main')['revision'], self.observation('counter-strain'))

    def test_later_observation_qualified_lesson_changes_heldout_choice_not_base_method(self):
        _, outcome = self.measured_training()
        later = self.task('heldout')
        self.assertEqual(self.winner(self.expression.execute('main', 'walker', later)), 'later-long')
        lesson = self.propose(outcome)
        # Candidate memory has no behavioral authority before review.
        self.assertEqual(self.winner(self.expression.execute('main', 'walker', later)), 'later-long')
        self.qualify(lesson)
        result = self.expression.execute('main', 'walker', later)
        self.assertEqual(self.winner(result), 'later-short')
        self.assertEqual([row['lesson_id'] for row in result['binding']['lessons']],
                         [lesson['lesson_id']])
        base = self.methods.read('main', self.method_id, 1)
        self.assertEqual(base['digest'], self.method_digest)
        self.assertEqual(base['definition']['operation']['params'], self.params('maximize'))
        irrelevant = self.expression.execute('main', 'walker', self.task('unrelated', {'tired': False}))
        self.assertEqual(self.winner(irrelevant), 'later-long')
        self.assertEqual(irrelevant['binding'].get('lessons', []), [])

    def test_public_learning_history_reopens_without_recursive_reexecution(self):
        _, outcome = self.measured_training()
        owner_view = self.learning.read_outcome('main', outcome['outcome_id'])
        public_view = self.learning.read_outcome('main', outcome['outcome_id'], viewer='observer')
        self.assertIn('OWNER-OUTCOME-RATIONALE-CANARY', json.dumps(owner_view))
        self.assertNotIn('OWNER-OUTCOME-RATIONALE-CANARY', json.dumps(public_view))
        self.assertNotIn('rationale', public_view['observation'])
        self.assertEqual(public_view['observation']['measurements'],
                         owner_view['observation']['measurements'])
        lesson = self.propose(outcome)
        self.qualify(lesson)
        expected = self.expression.execute('main', 'walker', self.task(), viewer='observer')
        self.assertEqual(self.winner(expected), 'later-short')
        self.engine.close()
        self.engine = Engine(self.path)
        self.methods = Methods(self.engine)
        self.learning = Learning(self.engine)
        self.expression = Expression(self.engine, self.methods)
        self.contributions = Contributions(self.engine)
        actual = self.expression.execute('main', 'walker', self.task(), viewer='observer')
        self.assertEqual(self.winner(actual), 'later-short')
        self.assertEqual(actual['binding']['lessons'], expected['binding']['lessons'])
        self.assertTrue(self.engine.verify()['ok'])

    def test_calculation_success_and_unrelated_new_event_do_not_make_old_source_an_outcome(self):
        trial = self.contributions.run('main', 'walker', 'training-contribution', self.task('train'))
        self.assertEqual(trial['phase'], 'completed')
        self.world_event([self.record('knowledge', 'unrelated-new-event', holder='observer',
                                      assertion='An unrelated fact changed.', attitude='believes')])
        with self.assertRaises(Rejected):
            self.learning.record_outcome('main', trial['contribution_id'], 'invalid-outcome', 2,
                                         self.observation('old-strain', status='achieved'))

    def test_unknown_observation_cannot_activate_a_lesson(self):
        _, outcome = self.measured_training(status='unknown')
        lesson = self.propose(outcome)
        with self.assertRaises(Rejected):
            self.qualify(lesson)
        self.assertEqual(self.winner(self.expression.execute('main', 'walker', self.task())),
                         'later-long')

    def test_unknown_null_field_is_not_support_for_achieved_outcome(self):
        trial = self.contributions.run('main', 'walker', 'training-contribution',
                                       self.task('train'), viewer='observer')
        self.world_event([self.record('resource', 'null-observation', holder='walker',
                                      name='Later record with unknown availability', quantity=1,
                                      unit='fixture units')])
        observed = {'status': 'achieved', 'rationale': 'This declaration lacks an observed value.',
                    'measurements': [{'value': None, 'evidence': {
                        'source_ref': self.ref('null-observation'),
                        'field_path': ['data', 'availability']}}]}
        with self.assertRaises(Rejected):
            self.learning.record_outcome('main', trial['contribution_id'],
                                         'null-outcome', 2, observed)

    def test_boolean_context_does_not_match_integer_or_absent_context(self):
        _, outcome = self.measured_training()
        lesson = self.propose(outcome)
        self.qualify(lesson)
        self.assertEqual(self.winner(self.expression.execute('main', 'walker', self.task())),
                         'later-short')
        for context in ({'tired': 1}, {}, {'tired': None}):
            with self.subTest(context=context):
                result = self.expression.execute('main', 'walker', self.task('control', context))
                self.assertEqual(self.winner(result), 'later-long')
                self.assertEqual(result['binding'].get('lessons', []), [])

    def test_public_lesson_cannot_expose_private_support(self):
        _, outcome = self.measured_training(visibility='gm')
        lesson = self.propose(outcome)
        self.qualify(lesson)
        owner = self.expression.execute('main', 'walker', self.task())
        self.assertEqual(self.winner(owner), 'later-short')
        public = self.expression.execute('main', 'walker', self.task(), viewer='observer')
        self.assertEqual(self.winner(public), 'later-long')
        self.assertEqual(public['binding'].get('lessons', []), [])
        rendered = json.dumps(public)
        self.assertNotIn(outcome['outcome_id'], rendered)
        self.assertNotIn(lesson['lesson_id'], rendered)
        self.assertNotIn('observed-strain', rendered)

    def test_public_observation_record_does_not_publish_its_hidden_reference(self):
        trial = self.contributions.run('main', 'walker', 'training-contribution',
                                       self.task('train'), viewer='observer')
        self.world_event([self.record('resource', 'public-observation', holder='hidden-observer',
                                      name='An observation with a hidden holder',
                                      quantity=8, unit='fixture strain')])
        observed = {'status': 'not_achieved',
                    'rationale': 'Owner-only interpretation of the hidden association.',
                    'measurements': [{'value': 'hidden-observer', 'evidence': {
                        'source_ref': self.ref('public-observation'),
                        'field_path': ['data', 'holder']}}]}
        outcome = self.learning.record_outcome('main', trial['contribution_id'],
                                               'hidden-reference-outcome', 2, observed)
        lesson = self.propose(outcome)
        self.qualify(lesson)
        self.assertEqual(self.winner(self.expression.execute('main', 'walker', self.task())),
                         'later-short')
        public = self.expression.execute('main', 'walker', self.task(), viewer='observer')
        self.assertEqual(self.winner(public), 'later-long')
        self.assertEqual(public['binding'].get('lessons', []), [])
        self.assertNotIn('hidden-observer', json.dumps(public))
        with self.assertRaises(Rejected):
            self.learning.read_outcome('main', outcome['outcome_id'], viewer='observer')

    def test_revision_of_base_method_does_not_inherit_prior_lesson(self):
        _, outcome = self.measured_training()
        lesson = self.propose(outcome)
        self.qualify(lesson)
        self.assertEqual(self.winner(self.expression.execute('main', 'walker', self.task())),
                         'later-short')
        new_definition = copy.deepcopy(self.base_definition)
        new_definition['name'] = 'Revised scenic method'
        self.methods.revise('main', self.node_id, self.method_id, 1, 'revise-base', 2,
                            new_definition, [self.ref('method-source')])
        self.methods.assign('main', self.node_id, self.method_id, 2, 'assign-revised-base', 2,
                            'experimental', 'New method needs separate lesson qualification',
                            expected_assignment_revision=1)
        result = self.expression.execute('main', 'walker', self.task())
        self.assertEqual(self.winner(result), 'later-long')
        self.assertEqual(result['binding'].get('lessons', []), [])

    def test_contestation_blocks_cached_packet_and_replayed_qualification(self):
        _, outcome = self.measured_training()
        lesson = self.propose(outcome)
        self.qualify(lesson)
        task = self.task('heldout')
        prepared = self.expression.prepare('main', 'walker', task, viewer='observer')
        self.assertEqual(self.winner(self.expression.execute('main', 'walker', task,
                         viewer='observer', prepared=prepared)), 'later-short')
        counter = self.counter_outcome()
        self.learning.review('main', lesson['lesson_id'], 1, 'contest', 3, 'contested',
                             'A later synthetic trial challenges the intervention.',
                             expected_review_revision=1,
                             counter_outcome_ids=[counter['outcome_id']])
        with self.assertRaises(Rejected):
            self.expression.execute('main', 'walker', task, viewer='observer', prepared=prepared)
        # Retry the exact old request, including its original world revision.
        replay = self.learning.review('main', lesson['lesson_id'], 1, 'qualify-lesson', 2,
                                      'qualified', 'Bounded reviewed fixture intervention')
        self.assertTrue(replay['replayed'])
        current = self.expression.execute('main', 'walker', task, viewer='observer')
        self.assertEqual(self.winner(current), 'later-long')
        self.assertEqual(current['binding'].get('lessons', []), [])
        with self.assertRaises(Rejected):
            self.learning.review('main', lesson['lesson_id'], 1, 'revive-old-revision', 3,
                                 'qualified', 'Unchanged old evidence cannot reactivate it.',
                                 expected_review_revision=2)

    def test_private_counterevidence_does_not_leak_through_current_choice(self):
        _, outcome = self.measured_training()
        lesson = self.propose(outcome)
        self.qualify(lesson)
        # Positive control: this viewer could use the lesson before contradiction.
        before = self.expression.execute('main', 'walker', self.task(), viewer='observer')
        self.assertEqual(self.winner(before), 'later-short')
        counter = self.counter_outcome(visibility='gm')
        self.learning.review('main', lesson['lesson_id'], 1, 'private-contest', 3,
                             'contested', 'Private counterevidence requires review.',
                             expected_review_revision=1,
                             counter_outcome_ids=[counter['outcome_id']])
        public = self.expression.execute('main', 'walker', self.task(), viewer='observer')
        self.assertEqual(self.winner(public), 'later-long')
        self.assertEqual(public['binding'].get('lessons', []), [])
        text = json.dumps(public)
        for private in ('COUNTER-STRAIN-CANARY', 'counter-strain', counter['outcome_id']):
            self.assertNotIn(private, text)
        self.assertTrue(self.engine.verify()['ok'])

    def test_repeated_observation_keeps_one_origin_instead_of_independent_votes(self):
        trial, first = self.measured_training()
        second = self.learning.record_outcome('main', trial['contribution_id'],
                                              'repeated-outcome', 2,
                                              self.observation('observed-strain'))
        lesson = self.learning.propose('main', self.node_id, 'two-observations', 2,
                                       self.definition(), [first['outcome_id'], second['outcome_id']])
        stored = self.learning.read('main', lesson['lesson_id'])
        self.assertEqual(stored['origin_contribution_ids'], [trial['contribution_id']])
        self.assertEqual(len(stored['origin_event_ids']), 1)

    def test_cosmetic_revision_cannot_launder_a_contested_intervention(self):
        _, outcome = self.measured_training()
        lesson = self.propose(outcome)
        self.qualify(lesson)
        counter = self.counter_outcome()
        self.learning.review('main', lesson['lesson_id'], 1, 'contest', 3, 'contested',
                             'A later trial challenges the intervention.', expected_review_revision=1,
                             counter_outcome_ids=[counter['outcome_id']])
        cosmetic = self.definition()
        cosmetic['name'] = 'Renamed intervention, unchanged mechanism'
        cosmetic['rationale'] = 'Different prose supplies no new outcome evidence.'
        revised = self.learning.revise('main', self.node_id, lesson['lesson_id'], 1,
                                       'cosmetic-revision', 3, cosmetic, [outcome['outcome_id']])
        with self.assertRaises(Rejected):
            self.qualify(revised, request='qualify-cosmetic')
        current = self.expression.execute('main', 'walker', self.task(), viewer='observer')
        self.assertEqual(self.winner(current), 'later-long')
        self.assertEqual(current['binding'].get('lessons', []), [])

    def test_descendant_lesson_rechecks_ancestor_measurement_field_visibility(self):
        training = self.contributions.run('main', 'walker', 'training-contribution',
                                          self.task('train'), viewer='observer')
        self.world_event([self.record('resource', 'association-observation',
                                      holder='outside-character', name='Observed association',
                                      quantity=8, unit='fixture strain')])
        observed = {'status': 'not_achieved', 'rationale': 'Synthetic association observation.',
                    'measurements': [{'value': 'outside-character', 'evidence': {
                        'source_ref': self.ref('association-observation'),
                        'field_path': ['data', 'holder']}}]}
        first_outcome = self.learning.record_outcome('main', training['contribution_id'],
                                                     'first-outcome', 2, observed)
        ancestor = self.propose(first_outcome)
        self.qualify(ancestor)
        later = self.contributions.run('main', 'walker', 'descendant-trial',
                                       self.task('descendant-trial'), viewer='observer')
        self.assertEqual(self.winner(self.contributions.read('main', later['contribution_id'])['result']),
                         'later-short')
        self.world_event([self.record('resource', 'later-observation', holder='walker',
                                      name='Second trial observation', quantity=2,
                                      unit='fixture strain')])
        later_outcome = self.learning.record_outcome('main', later['contribution_id'],
                                                     'later-outcome', 3,
                                                     self.observation('later-observation', status='achieved'))
        descendant = self.propose(later_outcome, request='descendant-lesson')
        self.qualify(descendant, request='qualify-descendant')
        before = self.expression.execute('main', 'walker', self.task(), viewer='observer')
        self.assertEqual(self.winner(before), 'later-short')
        self.assertEqual(len(before['binding']['lessons']), 2)
        self.world_event([{'op': 'patch', 'id': 'outside-character', 'expected_version': 1,
                           'visibility': 'gm', 'data': {},
                           'evidence': [{'note': 'Synthetic association is now restricted'}]}])
        public = self.expression.execute('main', 'walker', self.task(), viewer='observer')
        self.assertEqual(self.winner(public), 'later-long')
        self.assertEqual(public['binding'].get('lessons', []), [])
        with self.assertRaises(Rejected):
            self.learning.read_outcome('main', later_outcome['outcome_id'], viewer='observer')


if __name__ == '__main__':
    unittest.main()
