"""V3 integration: actual durable history, interruption, upgrade and user interfaces."""
import copy
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from examples.v3_demo import run
from kageyoni.resources import fixture_path
from kageyoni.application import Application
from kageyoni.engine import Engine, Rejected
from kageyoni.persistence.unit_of_work import UnitOfWork


class LearningIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'demo'
        self.summary = run(self.root)
        self.path = self.root / 'synthetic.sqlite'
        self.engine = Engine(self.path)
        self.app = Application(self.engine)

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def outcome_payload(self, request='integration-outcome'):
        payload = json.loads((self.root / 'first-feedback-input.json').read_text())
        payload.update(request_id=request,
                       expected_world_revision=self.engine.branch('main')['revision'])
        return payload

    def test_heldout_choices_and_base_method_control(self):
        self.assertEqual(len(self.summary['checks']), 8)
        self.assertTrue(all(self.summary['checks'].values()))
        self.assertEqual(self.summary['choices']['after-qualified-revision'], 'later-balanced')
        self.assertEqual(self.app.methods.read('main', self.summary['method_id'])['revision'], 1)

    def test_backup_and_restore_preserve_learning_and_result_history(self):
        expected_lessons = self.app.learning.list('main', 'analyst')
        expected_outcomes = self.app.learning.list_outcomes('main', 'analyst')
        expected_receipts = self.app.contributions.list('main')
        backup, restored = self.root / 'backup.sqlite', self.root / 'restored.sqlite'
        self.engine.backup(backup)
        Engine.restore(backup, restored)
        engine = Engine(restored)
        try:
            app = Application(engine)
            self.assertEqual(app.learning.list('main', 'analyst'), expected_lessons)
            self.assertEqual(app.learning.list_outcomes('main', 'analyst'), expected_outcomes)
            self.assertEqual(app.contributions.list('main'), expected_receipts)
            self.assertTrue(engine.verify()['ok'])
        finally:
            engine.close()

    def test_outcome_retry_after_world_advances_is_exact(self):
        original = json.loads((self.root / 'first-feedback-input.json').read_text())
        first = self.app.learning.record_outcome(**original)
        second = self.app.learning.record_outcome(**original)
        self.assertEqual(first['outcome_id'], second['outcome_id'])
        changed = copy.deepcopy(original)
        changed['observation']['rationale'] = 'A changed interpretation under the same request ID'
        with self.assertRaises(Rejected):
            self.app.learning.record_outcome(**changed)

    def test_enclosing_rollback_removes_outcome_and_its_request(self):
        before = self.app.learning.list_outcomes('main', 'analyst')
        with self.assertRaises(RuntimeError):
            with UnitOfWork(self.engine.db):
                self.app.learning.record_outcome(**self.outcome_payload())
                raise RuntimeError('Interruption before outer transaction commit')
        self.assertEqual(self.app.learning.list_outcomes('main', 'analyst'), before)
        saved = self.app.learning.record_outcome(**self.outcome_payload())
        self.assertEqual(self.app.learning.read_outcome('main', saved['outcome_id'])['outcome_id'],
                         saved['outcome_id'])

    def test_process_death_rolls_back_outcome_then_retry_succeeds(self):
        before = self.app.learning.list_outcomes('main', 'analyst')
        payload = self.outcome_payload('crashed-outcome')
        input_path = self.root / 'crash-input.json'
        input_path.write_text(json.dumps(payload))
        code = '''import json,os,sys
from kageyoni.engine import Engine
from kageyoni.application import Application
from kageyoni.persistence.unit_of_work import UnitOfWork
engine=Engine(sys.argv[1])
with UnitOfWork(engine.db):
 Application(engine).learning.record_outcome(**json.load(open(sys.argv[2])))
 os._exit(23)
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.path), str(input_path)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(self.app.learning.list_outcomes('main', 'analyst'), before)
        saved = self.app.learning.record_outcome(**payload)
        self.assertEqual(self.app.learning.read_outcome('main', saved['outcome_id'])['outcome_id'],
                         saved['outcome_id'])

    def test_cli_and_terminal_read_qualified_revision(self):
        lesson_id = self.summary['lesson_id']
        result = subprocess.run([sys.executable, '-m', 'kageyoni', '--db', str(self.path),
                                 'lesson-read', '--input', '-'],
                                input=json.dumps({'lesson_id': lesson_id}), capture_output=True,
                                text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['revision'], 2)
        import terminal
        app = terminal.App(self.root / 'terminal-settings', self.path)
        try:
            with patch.object(app, 'choose', return_value=4), \
                 patch.object(app, 'ask', side_effect=[lesson_id, '']), \
                 patch.object(app, 'show') as show:
                app.learning()
                self.assertEqual(show.call_args.args[0]['revision'], 2)
        finally:
            app.session.close()


class LearningMigrationTests(unittest.TestCase):
    def test_failed_migration_rolls_back_and_can_retry(self):
        from kageyoni.persistence import migrations
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            engine = Engine(root / 'world.sqlite')
            try:
                migrations.install_contributions(engine)
                good = migrations.LEARNING_MIGRATION
                broken = root / 'broken.sql'
                broken.write_text(good.read_text() + '\nINVALID STATEMENT;\n')
                tables = {r[0] for r in engine.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                with patch.object(migrations, 'LEARNING_MIGRATION', broken):
                    with self.assertRaises(sqlite3.Error):
                        migrations.install_learning(engine)
                self.assertEqual(tables, {r[0] for r in engine.db.execute("SELECT name FROM sqlite_master WHERE type='table'")})
                self.assertIsNone(engine.db.execute('SELECT 1 FROM migration_checks WHERE version=12').fetchone())
                self.assertTrue(list(root.glob('world.sqlite.pre-v12-*.bak')))
                migrations.install_learning(engine)
                self.assertTrue(engine.verify()['ok'])
            finally:
                engine.close()

    def test_v2_campaign_migration_preserves_existing_rows_and_pending_decisions(self):
        from kageyoni.decisions import fingerprint
        from kageyoni.engine import encoded
        source = fixture_path('recovery/pre-v3-learning.sqlite')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'campaign.sqlite'
            shutil.copy2(source, path)
            engine = Engine(path)
            try:
                tables = [r[0] for r in engine.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                          if r[0] not in ('engine_versions', 'migration_checks')]
                def rows(table):
                    return sorted(encoded(dict(row)) for row in engine.db.execute('SELECT * FROM "' + table.replace('"', '""') + '"'))
                before = {table: rows(table) for table in tables}
                before_fingerprint = fingerprint(engine, 'main')
                before_node = Application(engine).nodes.read('main', 'sciel')
                app = Application(engine, migrate_learning=True)
                self.assertEqual({table: rows(table) for table in tables}, before)
                self.assertEqual(fingerprint(engine, 'main'), before_fingerprint)
                self.assertEqual(app.nodes.read('main', 'sciel'), before_node)
                self.assertEqual(engine.branch('main')['revision'], 60)
                self.assertEqual(app.learning.list('main', 'sciel'), [])
                self.assertEqual(app.learning.list_outcomes('main', 'sciel'), [])
                self.assertTrue(engine.verify()['ok'])
            finally:
                engine.close()

