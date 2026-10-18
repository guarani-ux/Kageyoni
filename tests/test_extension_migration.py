"""Explicit lifecycle storage upgrade, backup and drift refusal."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from kageyoni.engine import Engine,Rejected
from kageyoni.persistence.migrations import install_causal_delivery,install_extensions,_install_component


class ExtensionMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'world.sqlite'
        self.engine=Engine(self.path);install_causal_delivery(self.engine)
    def tearDown(self):self.engine.close();self.temp.cleanup()
    def test_extension_upgrade_preserves_native_history_and_verified_predecessor(self):
        e=self.engine;before=(e.state('main'),e.branch('main')['revision'])
        install_extensions(e);assert e.verify()['ok'] and e.validate_registry()['ok']
        self.assertEqual((e.state('main'),e.branch('main')['revision']),before)
        backup=next(self.path.parent.glob('*.pre-v30-*.bak'))
        with sqlite3.connect(backup.resolve().as_uri()+'?mode=ro',uri=True) as db:
            self.assertEqual(db.execute('SELECT max(version) FROM migration_checks').fetchone()[0],29)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='extension_versions'").fetchone())
        install_extensions(e);self.assertEqual(len(list(self.path.parent.glob('*.pre-v30-*.bak'))),1)
    def test_partial_extension_upgrade_rolls_back_and_checksum_drift_refuses(self):
        script=self.path.parent/'bad.sql';script.write_text('CREATE TABLE extension_partial(id);\nINSERT INTO absent VALUES(1);\n')
        with self.assertRaises(sqlite3.OperationalError):_install_component(self.engine,script,30,29,'extension_lifecycle_interface')
        self.assertIsNone(self.engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='extension_partial'").fetchone())
        assert self.engine.verify()['ok'];install_extensions(self.engine)
        self.engine.db.execute('UPDATE migration_checks SET checksum=? WHERE version=30',('0'*64,))
        with self.assertRaises(Rejected):self.engine.verify()
