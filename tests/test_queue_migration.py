"""Actual predecessor upgrade, preservation, rollback and lease verification."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from kageyoni.engine import Engine, Rejected
from kageyoni.persistence.migrations import install_activities,install_activity_queue,_install_component


class QueueMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='kageyoni-queue-migration-')
        self.path=Path(self.temp.name)/'world.sqlite';self.engine=Engine(self.path)
        install_activities(self.engine)

    def tearDown(self):self.engine.close();self.temp.cleanup()

    def test_queue_upgrade_preserves_verified_v26_and_backup(self):
        before=self.engine.state('main');revision=self.engine.branch('main')['revision']
        self.assertTrue(self.engine.verify()['ok'])
        install_activity_queue(self.engine)
        self.assertTrue(self.engine.verify()['ok']);self.assertEqual(before,self.engine.state('main'))
        self.assertEqual(revision,self.engine.branch('main')['revision'])
        backup=next(self.path.parent.glob('*.pre-v27-*.bak'))
        db=sqlite3.connect(backup.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            self.assertEqual(db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0],26)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='activity_queue'").fetchone())
        finally:db.close()
        install_activity_queue(self.engine);self.assertEqual(len(list(self.path.parent.glob('*.pre-v27-*.bak'))),1)

    def test_queue_failure_rolls_back_and_checksum_corruption_rejects(self):
        bad=self.path.parent/'bad.sql';bad.write_text('CREATE TABLE must_rollback(id);\nINSERT INTO absent_table VALUES(1);\n')
        with self.assertRaises(sqlite3.OperationalError):_install_component(self.engine,bad,27,26,'activity_queue_interface')
        self.assertIsNone(self.engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='must_rollback'").fetchone())
        self.assertTrue(self.engine.verify()['ok'])
        install_activity_queue(self.engine)
        self.engine.db.execute("UPDATE migration_checks SET checksum=? WHERE version=27",('0'*64,))
        with self.assertRaises(Rejected):self.engine.verify()
