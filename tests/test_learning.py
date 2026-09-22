"""V3 storage and recovery boundaries on synthetic fixtures."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import unittest

import test_development as fixtures
from kageyoni.engine import Engine, Rejected
from kageyoni.intelligence.learning import Learning, verify_learning
from kageyoni.persistence.contributions import Contributions
from kageyoni.persistence.unit_of_work import UnitOfWork


class LearningStorageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DevelopmentTests(methodName='runTest')
        self.fixture.setUp()

    @property
    def e(self):
        return self.fixture.e

    @property
    def learning(self):
        return self.fixture.learning

    def tearDown(self):
        self.fixture.tearDown()

    def count(self, table):
        return self.e.db.execute('SELECT count(*) FROM ' + table).fetchone()[0]

    def propose(self, label='storage'):
        return self.fixture.propose(label)

    def review(self, lesson, request='review-storage', **overrides):
        args = dict(branch='main', lesson_id=lesson['lesson_id'], lesson_revision=lesson['revision'],
                    request_id=request, expected_world_revision=self.e.branch('main')['revision'],
                    status='qualified', rationale='Operator authorizes a scoped synthetic trial.')
        args.update(overrides)
        return self.learning.review(**args)

    def test_idempotent_proposal_conflict_and_review_history(self):
        lesson = self.propose()
        repeated = self.propose()
        self.assertTrue(repeated['replayed'])
        self.assertEqual(lesson['lesson_id'], repeated['lesson_id'])
        changed = self.fixture.definition(name='Conflicting request name')
        with self.assertRaises(Rejected):
            self.fixture.propose('storage', changed)
        self.review(lesson)
        self.review(lesson, request='retire', status='retired', expected_review_revision=1)
        old = self.review(lesson)
        self.assertTrue(old['replayed'])
        self.assertEqual(self.learning.read('main', lesson['lesson_id'])['status'], 'retired')
        self.assertEqual(self.count('lesson_revisions'), 1)
        self.assertEqual(self.count('lesson_reviews'), 2)
        self.assertEqual(verify_learning(self.e)['lesson_reviews'], 2)

    def test_review_compare_and_swap_and_new_revision_requires_review(self):
        lesson = self.propose(); self.review(lesson)
        with self.assertRaises(Rejected):
            self.review(lesson, request='lost-cas')
        revision = self.learning.revise('main', self.fixture.fixture.node_id, lesson['lesson_id'], 1,
             'storage-revision', self.e.branch('main')['revision'], self.fixture.definition(direction='minimize'),
             [self.fixture.outcome['outcome_id']])
        self.assertEqual(self.learning.read('main', lesson['lesson_id'])['status'], 'proposed')
        self.assertEqual(self.learning.read('main', lesson['lesson_id'], 1)['status'], 'qualified')
        with self.assertRaises(Rejected):
            self.review(lesson, request='old-revision-review', expected_review_revision=1)
        self.review(revision, request='new-revision-review')
        self.assertEqual(self.learning.read('main', lesson['lesson_id'])['review_revision'], 1)

    def test_learning_writes_rollback_as_one_outer_unit(self):
        before = {table: self.count(table) for table in ('learning_outcomes', 'lesson_revisions', 'lesson_reviews', 'learning_events')}
        world = self.e.state()
        with self.assertRaises(RuntimeError):
            with UnitOfWork(self.e.db):
                lesson = self.propose(); self.review(lesson)
                raise RuntimeError('Synthetic interrupted workflow')
        self.assertEqual({table: self.count(table) for table in before}, before)
        self.assertEqual(self.e.state(), world)
        self.assertFalse(self.e.db.in_transaction)

    def test_immutable_records_and_backup_restore(self):
        lesson = self.propose(); self.review(lesson)
        before = self.learning.read('main', lesson['lesson_id'])
        for table in ('learning_outcomes', 'lesson_revisions', 'lesson_reviews', 'learning_events'):
            with self.assertRaises(sqlite3.IntegrityError):
                self.e.db.execute('DELETE FROM ' + table)
        backup = Path(self.e.path).with_name('v3-backup.sqlite')
        restored = Path(self.e.path).with_name('v3-restored.sqlite')
        self.e.backup(backup); Engine.restore(backup, restored)
        engine = Engine(restored)
        try:
            self.assertEqual(Learning(engine).read('main', lesson['lesson_id']), before)
            self.assertTrue(engine.verify()['ok'])
        finally:
            engine.close()

    def test_assignment_reauthorization_does_not_silently_revive_lesson(self):
        lesson = self.propose(); self.review(lesson)
        f = self.fixture.fixture
        self.assertEqual(self.fixture.ranking(self.fixture.execute()), ['long', 'short'])
        f.methods.assign('main', f.node_id, f.method['method_id'], 1, 'revoke-base', self.e.branch('main')['revision'],
                         'revoked', 'Synthetic suspension', expected_assignment_revision=1)
        f.methods.assign('main', f.node_id, f.method['method_id'], 1, 'reauthorize-base', self.e.branch('main')['revision'],
                         'experimental', 'New bounded trial permission', expected_assignment_revision=2)
        self.assertFalse(self.learning.read('main', lesson['lesson_id'])['assignment_current'])
        self.assertEqual(self.fixture.ranking(self.fixture.execute()), ['short', 'long'])
        self.review(lesson, request='explicit-re-review', expected_review_revision=1)
        self.assertEqual(self.fixture.ranking(self.fixture.execute()), ['long', 'short'])

    def test_one_stale_support_preserves_other_origin_and_allows_scoped_revision(self):
        second_trial = Contributions(self.e).run('main', 'maker', 'independent-trial', self.fixture.task)
        second = self.fixture.observe(second_trial['contribution_id'], 'second-origin', 2)
        lesson = self.learning.propose('main', self.fixture.fixture.node_id, 'two-origins', self.e.branch('main')['revision'],
                                      self.fixture.definition(), [self.fixture.outcome['outcome_id'], second['outcome_id']])
        self.review(lesson)
        initial = self.learning.read('main', lesson['lesson_id'])
        self.assertEqual(len(initial['origin_contribution_ids']), 2)
        record = self.e.get('main', 'feedback-source')
        self.fixture.fixture.apply([dict(op='patch', id='feedback-source', expected_version=record['version'],
                                   evidence=[{'note': 'Synthetic observation correction'}], data={'quantity': 99})])
        self.assertFalse(self.learning.read('main', lesson['lesson_id'])['source_fresh'])
        self.assertEqual(self.fixture.ranking(self.fixture.execute()), ['short', 'long'])
        self.assertFalse(self.learning.read_outcome('main', self.fixture.outcome['outcome_id'])['source_fresh'])
        self.assertTrue(self.learning.read_outcome('main', second['outcome_id'])['source_fresh'])
        revision = self.learning.revise('main', self.fixture.fixture.node_id, lesson['lesson_id'], 1,
            'narrow-support', self.e.branch('main')['revision'], self.fixture.definition(), [second['outcome_id']])
        self.review(revision, request='qualify-narrowed-support')
        self.assertEqual(self.fixture.ranking(self.fixture.execute()), ['long', 'short'])
        self.assertEqual(self.count('learning_outcomes'), 2)
        self.assertEqual(len(self.learning.read('main', lesson['lesson_id'], 1)['outcome_ids']), 2)
        self.assertTrue(self.e.verify()['ok'])

    def test_known_null_observation_rejected_and_unknown_not_qualified(self):
        f = self.fixture.fixture
        f.apply([f.create('resource', 'null-feedback', holder='maker', name='No available observation',
                         quantity=1, unit='fixture')])
        source = f.expression.source_ref('main', 'null-feedback')
        observation = {'status': 'achieved', 'rationale': 'A null field cannot establish an observation.',
                       'measurements': [{'value': None, 'evidence': {'source_ref': source, 'field_path': ['data', 'availability']}}]}
        with self.assertRaises(Rejected):
            self.learning.record_outcome('main', self.fixture.origin, 'null-outcome', self.e.branch('main')['revision'], observation)
        observation['status'] = 'unknown'
        unknown = self.learning.record_outcome('main', self.fixture.origin, 'unknown-null', self.e.branch('main')['revision'], observation)
        lesson = self.learning.propose('main', f.node_id, 'null-lesson', self.e.branch('main')['revision'],
                                      self.fixture.definition(), [unknown['outcome_id']])
        with self.assertRaisesRegex(Rejected, 'unknown outcome'):
            self.review(lesson)

    def test_nonowner_cannot_record_or_qualify(self):
        with self.assertRaises(Rejected):
            self.learning.propose('main', self.fixture.fixture.node_id, 'nonowner-proposal', self.e.branch('main')['revision'],
                 self.fixture.definition(), [self.fixture.outcome['outcome_id']], viewer='reader')
        lesson = self.propose()
        with self.assertRaises(Rejected):
            self.review(lesson, viewer='reader')
        self.assertEqual(self.count('lesson_reviews'), 0)

    def test_content_tampering_detected_without_historical_reexecution(self):
        lesson = self.propose(); self.review(lesson)
        self.e.db.execute('DROP TRIGGER lesson_reviews_no_update')
        self.e.db.execute("UPDATE lesson_reviews SET rationale='Changed after qualification'")
        with self.assertRaisesRegex(Rejected, 'digest'):
            verify_learning(self.e)


if __name__ == '__main__':
    unittest.main()
