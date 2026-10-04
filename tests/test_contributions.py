"""Cross-layer V2 tests: public interfaces, actual SQLite recovery, atomic outputs."""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kageyoni.resources import fixture_path
from kageyoni.engine import Engine, Rejected
from kageyoni.application import Application
from kageyoni.persistence.unit_of_work import UnitOfWork
from examples.v2_demo import run

class ContributionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'demo'
        self.summary=run(self.root);self.path=self.root/'synthetic.sqlite'
        self.e=Engine(self.path);self.app=Application(self.e)
        self.task=json.loads((self.root/'task.json').read_text())
    def tearDown(self):self.e.close();self.tmp.cleanup()
    def execute(self,request='integration'):
        return self.app.contributions.run('main','analyst',request,self.task)
    def test_controlled_comparison_actual_outputs(self):
        self.assertTrue(all(self.summary['controls'].values()))
        self.assertEqual(set(self.summary['controls']),{'name_invariant','paraphrase_invariant','operation_changes_choice'})
    def test_unchecked_execution_cannot_be_saved_as_complete(self):
        from kageyoni.intelligence.expression import Expression
        result=self.app.expression.execute('main','analyst',self.task)
        result['checks_passed']=False
        before=self.e.db.execute('SELECT count(*) FROM contributions').fetchone()[0]
        with patch.object(Expression,'execute',return_value=result):
            with self.assertRaises(Rejected):self.execute('unchecked')
        self.assertEqual(self.e.db.execute('SELECT count(*) FROM contributions').fetchone()[0],before)
    def test_receipt_artifact_reopen_and_restore(self):
        receipt=self.execute();expected=self.app.contributions.read('main',receipt['contribution_id'])
        self.e.close();self.e=Engine(self.path);self.app=Application(self.e)
        self.assertEqual(expected,self.app.contributions.read('main',receipt['contribution_id']))
        backup=self.root/'backup.sqlite';restored=self.root/'restored.sqlite'
        self.e.backup(backup);Engine.restore(backup,restored);r=Engine(restored)
        try:self.assertEqual(expected,Application(r).contributions.read('main',receipt['contribution_id']))
        finally:r.close()
    def test_exact_retry_and_changed_request(self):
        first=self.execute();second=self.execute()
        self.assertEqual(first['contribution_id'],second['contribution_id']);self.assertTrue(second['replayed'])
        changed=dict(self.task,objective='changed requirement')
        with self.assertRaises(Rejected):self.app.contributions.run('main','analyst','integration',changed)
    def test_output_and_receipt_rollback_together(self):
        count=self.e.db.execute('SELECT count(*) FROM contributions').fetchone()[0]
        with self.assertRaises(RuntimeError):
            with UnitOfWork(self.e.db):
                self.execute();raise RuntimeError('simulated interruption before commit')
        self.assertEqual(self.e.db.execute('SELECT count(*) FROM contributions').fetchone()[0],count)
        self.assertFalse(self.execute()['replayed'])
    def test_process_death_before_commit_leaves_no_output_receipt(self):
        code="""import os,sys,json
from kageyoni.engine import Engine
from kageyoni.application import Application
from kageyoni.persistence.unit_of_work import UnitOfWork
e=Engine(sys.argv[1]);app=Application(e)
with UnitOfWork(e.db):
 app.contributions.run('main','analyst','crashed',json.load(open(sys.argv[2])))
 os._exit(23)
"""
        r=subprocess.run([sys.executable,'-c',code,str(self.path),str(self.root/'task.json')],timeout=15)
        self.assertEqual(r.returncode,23)
        self.assertIsNone(self.e.db.execute("SELECT * FROM contributions WHERE request_id='crashed'").fetchone())
        self.assertFalse(self.execute('crashed')['replayed'])
    def test_immutable_contribution_and_digest_validation(self):
        receipt=self.execute()
        with self.assertRaises(sqlite3.IntegrityError):self.e.db.execute("UPDATE contributions SET result_hash='bad'")
        self.e.db.execute('DROP TRIGGER contributions_no_update')
        self.e.db.execute("UPDATE contributions SET result_hash='bad' WHERE contribution_id=?",(receipt['contribution_id'],))
        with self.assertRaises(Rejected):self.e.verify()
    def test_cli_and_menu_read_real_artifact(self):
        receipt=self.execute()
        task_payload=dict(character_id='analyst',request_id='cli-contribution',task=self.task)
        r=subprocess.run([sys.executable,'-m','kageyoni','--db',str(self.path),'contribute','--input','-'],input=json.dumps(task_payload),text=True,capture_output=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['phase'],'completed')
        import terminal
        app=terminal.App(self.root/'terminal-settings',self.path)
        try:
            with patch.object(app,'choose',return_value=8),patch.object(app,'ask',return_value=receipt['contribution_id']),patch.object(app,'show') as show:
                app.methods();self.assertEqual(show.call_args.args[0]['result']['phase'],'completed')
        finally:app.session.close()
    def test_installed_v1_upgrade_preserves_node_and_world(self):
        import shutil
        p=self.root/'v1.sqlite'
        origin=fixture_path('recovery/pre-v2-methods.sqlite')
        shutil.copy2(origin,p);e=Engine(p)
        try:
            app=Application(e);before=app.nodes.read('main','sciel')
            from kageyoni.decisions import fingerprint
            before_fingerprint=fingerprint(e,'main')
            Application(e,migrate_methods=True)
            self.assertEqual(app.nodes.read('main','sciel'),before)
            self.assertEqual(fingerprint(e,'main'),before_fingerprint)
            self.assertEqual(e.branch('main')['revision'],60)
            self.assertEqual(e.db.execute('SELECT count(*) FROM method_revisions').fetchone()[0],0)
            self.assertEqual(e.db.execute('SELECT count(*) FROM contributions').fetchone()[0],0)
        finally:e.close()

class V2MigrationTests(unittest.TestCase):
    def test_each_new_migration_failure_is_atomic_and_retryable(self):
        from kageyoni.persistence import migrations
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'world.sqlite';e=Engine(p)
            try:
                migrations.install_nodes(e)
                for constant,version,table,installer in [
                    ('METHOD_MIGRATION',10,'method_revisions',migrations.install_methods),
                    ('CONTRIBUTION_MIGRATION',11,'contributions',migrations.install_contributions)]:
                    good=getattr(migrations,constant);bad=Path(temp)/('broken'+str(version)+'.sql')
                    bad.write_text(good.read_text()+'\nINVALID STATEMENT;\n')
                    with patch.object(migrations,constant,bad):
                        with self.assertRaises(sqlite3.Error):installer(e)
                    self.assertIsNone(e.db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone())
                    self.assertIsNone(e.db.execute('SELECT 1 FROM migration_checks WHERE version=?',(version,)).fetchone())
                    self.assertTrue(list(Path(temp).glob('world.sqlite.pre-v'+str(version)+'-*.bak')))
                    installer(e);self.assertTrue(e.verify()['ok'])
            finally:e.close()
    def test_new_component_checksum_mismatch_refuses_existing_install(self):
        with tempfile.TemporaryDirectory() as temp:
            e=Engine(Path(temp)/'world.sqlite')
            try:
                Application(e,migrate_methods=True)
                e.db.execute("UPDATE migration_checks SET checksum='bad' WHERE version=10")
                with self.assertRaises(Rejected):Application(e,migrate_methods=True)
            finally:e.close()

