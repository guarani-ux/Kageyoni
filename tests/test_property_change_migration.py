"""v27 -> checked opt-in lifecycle storage, without fictional history."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from kageyoni.engine import Engine,Rejected
from kageyoni.persistence.migrations import install_activity_queue,install_property_changes,_install_component

class PropertyChangeMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'world.sqlite'
        self.engine=Engine(self.path);install_activity_queue(self.engine)
    def tearDown(self):self.engine.close();self.temp.cleanup()
    def test_property_lifecycle_upgrade_preserves_predecessor_and_verified_backup(self):
        e=self.engine;state=e.state('main');revision=e.branch('main')['revision'];assert e.verify()['ok']
        install_property_changes(e);assert e.verify()['ok'];assert e.validate_registry()['ok']
        self.assertEqual(e.state('main'),state);self.assertEqual(e.branch('main')['revision'],revision)
        backup=next(self.path.parent.glob('*.pre-v28-*.bak'));db=sqlite3.connect(backup.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            self.assertEqual(db.execute('SELECT max(version) FROM migration_checks').fetchone()[0],27)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='property_effects'").fetchone())
        finally:db.close()
        install_property_changes(e);self.assertEqual(len(list(self.path.parent.glob('*.pre-v28-*.bak'))),1)
    def test_partial_migration_rollback_and_checksum_refusal(self):
        bad=self.path.parent/'bad.sql';bad.write_text('CREATE TABLE should_rollback(id);\nINSERT INTO missing VALUES(1);\n')
        with self.assertRaises(sqlite3.OperationalError):_install_component(self.engine,bad,28,27,'property_change_interface')
        self.assertIsNone(self.engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='should_rollback'").fetchone())
        assert self.engine.verify()['ok'];install_property_changes(self.engine)
        self.engine.db.execute("UPDATE migration_checks SET checksum=? WHERE version=28",('0'*64,))
        with self.assertRaises(Rejected):self.engine.verify()
