"""The opt-in causal metadata upgrade preserves native facts and rejects drift."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kageyoni.engine import Engine, Rejected
from kageyoni.persistence.migrations import install_property_changes, install_causal_delivery, _install_component


class CausalDeliveryMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'world.sqlite'
        self.engine = Engine(self.path)
        install_property_changes(self.engine)

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def test_causal_delivery_upgrade_preserves_native_state_and_predecessor_backup(self):
        e = self.engine
        before = (e.state('main'), e.branch('main')['revision'])
        install_causal_delivery(e)
        self.assertTrue(e.verify()['ok'])
        self.assertTrue(e.validate_registry()['ok'])
        self.assertEqual((e.state('main'), e.branch('main')['revision']), before)
        backup = next(self.path.parent.glob('*.pre-v29-*.bak'))
        with sqlite3.connect(backup.resolve().as_uri() + '?mode=ro', uri=True) as db:
            self.assertEqual(db.execute('SELECT max(version) FROM migration_checks').fetchone()[0], 28)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='causal_roots'").fetchone())
        install_causal_delivery(e)
        self.assertEqual(len(list(self.path.parent.glob('*.pre-v29-*.bak'))), 1)

    def test_partial_causal_upgrade_rolls_back_and_checksum_drift_refuses(self):
        bad = self.path.parent / 'partial.sql'
        bad.write_text('CREATE TABLE causal_partial(id);\nINSERT INTO absent VALUES(1);\n')
        with self.assertRaises(sqlite3.OperationalError):
            _install_component(self.engine, bad, 29, 28, 'causal_delivery_interface')
        self.assertIsNone(self.engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='causal_partial'").fetchone())
        self.assertTrue(self.engine.verify()['ok'])
        install_causal_delivery(self.engine)
        self.engine.db.execute('UPDATE migration_checks SET checksum=? WHERE version=29', ('0' * 64,))
        with self.assertRaises(Rejected):
            self.engine.verify()
