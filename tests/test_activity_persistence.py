"""Actual predecessor upgrade and rollback; no campaign fixtures invented."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kageyoni.engine import Engine, Rejected
from kageyoni.persistence.migrations import install_action_dispatch, install_activities, _install_component
from kageyoni.resources import schema_path


class ActivityMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kageyoni-activities-')
        self.path = Path(self.temp.name) / 'world.sqlite'
        self.engine = Engine(self.path)
        install_action_dispatch(self.engine)

    def tearDown(self):
        self.engine.close(); self.temp.cleanup()

    def test_upgrade_preserves_history_and_verified_backup(self):
        self.engine.apply({'api_version': 3, 'branch': 'main', 'request_id': 'one-real-synthetic-event', 'expected_revision': 0,
            'actor': 'fixture', 'kind': 'scene', 'narrative': 'Synthetic predecessor event', 'changes': [
                {'op': 'create', 'domain': 'location', 'id': 'room', 'data': {'name': 'Room', 'kind': 'room'}, 'visibility': 'public', 'status': 'proposed', 'evidence': [{'note': 'synthetic'}]}]})
        before = self.engine.state('main'); revision = self.engine.branch('main')['revision']
        self.assertTrue(self.engine.verify()['ok'])
        install_activities(self.engine)
        self.assertEqual(self.engine.state('main'), before)
        self.assertEqual(self.engine.branch('main')['revision'], revision)
        self.assertTrue(self.engine.verify()['ok'])
        backup = next(self.path.parent.glob('*.pre-v26-*.bak'))
        db = sqlite3.connect(backup.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0], 25)
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='activity_runs'").fetchone())
        finally:
            db.close()
        install_activities(self.engine)
        self.assertEqual(len(list(self.path.parent.glob('*.pre-v26-*.bak'))), 1)

    def test_failed_migration_rolls_back_without_losing_predecessor(self):
        bad = self.path.parent / 'intentional-failure.sql'
        bad.write_text('CREATE TABLE must_rollback(id INTEGER);\nINSERT INTO nonexistent_table VALUES(1);\n')
        with self.assertRaises(sqlite3.OperationalError):
            _install_component(self.engine, bad, 26, 25, 'activity_interface')
        self.assertIsNone(self.engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='must_rollback'").fetchone())
        self.assertEqual(self.engine.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0], 25)
        self.assertTrue(self.engine.verify()['ok'])

    def test_verifier_rejects_changed_migration_checksum(self):
        install_activities(self.engine)
        self.engine.db.execute("UPDATE migration_checks SET checksum=? WHERE version=26", ('0' * 64,))
        with self.assertRaises(Rejected):
            self.engine.verify()
