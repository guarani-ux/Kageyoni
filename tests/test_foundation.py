"""Foundation acceptance: disposable synthetic fixtures, never campaign actions."""
import tempfile
from pathlib import Path
import unittest
from kageyoni.engine import Engine, Rejected

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'world.sqlite'
        self.e=Engine(self.path)
        self.e.db.execute('CREATE TABLE caller_marker(value TEXT)')
    def tearDown(self):
        self.e.close();self.tmp.cleanup()
    def command(self, request='one', revision=0):
        return dict(api_version=3,branch='main',expected_revision=revision,request_id=request,
                    kind='action',actor='fixture',narrative='Synthetic fixture only',changes=[
                    dict(op='create',domain='character',id=request,status='proposed',visibility='public',
                         evidence=[{'note':'Synthetic'}],data={'name':request,'entity_kind':'person'})])
    def outer(self):
        self.e.db.execute('BEGIN IMMEDIATE');self.e.db.execute("INSERT INTO caller_marker VALUES('pending')")
    def assert_outer(self):
        self.assertTrue(self.e.db.in_transaction)
        self.assertEqual(self.e.db.execute('SELECT count(*) FROM caller_marker').fetchone()[0],1)
    def test_outer_rollback_removes_world_and_caller_write(self):
        self.outer();self.e.apply(self.command());self.assert_outer();self.e.db.rollback()
        self.assertEqual(self.e.state(),[])
        self.assertEqual(self.e.db.execute('SELECT count(*) FROM caller_marker').fetchone()[0],0)
    def test_preview_preserves_uncommitted_caller(self):
        self.outer();self.e.apply(self.command(),preview=True);self.assert_outer()
        self.assertEqual(self.e.state(),[]);self.e.db.rollback()
    def test_duplicate_preserves_uncommitted_caller(self):
        self.e.apply(self.command());self.outer()
        self.assertTrue(self.e.apply(self.command())['replayed']);self.assert_outer()
        self.e.db.rollback();self.assertEqual(len(self.e.state()),1)
    def test_rejection_preserves_caller(self):
        self.outer()
        with self.assertRaises(Rejected):self.e.apply(self.command(revision=100))
        self.assert_outer();self.e.db.rollback()
    def test_late_failure_rolls_back_only_inner(self):
        self.outer();cmd=self.command();cmd['assumptions']='invalid'
        with self.assertRaises(Rejected):self.e.apply(cmd)
        self.assert_outer();self.assertEqual(self.e.state(),[]);self.e.db.commit()
    def test_standalone_commit_and_preview(self):
        self.e.apply(self.command(),preview=True);self.assertEqual(self.e.state(),[])
        self.e.apply(self.command());self.assertFalse(self.e.db.in_transaction)
        self.e.close();self.e=Engine(self.path);self.assertEqual(len(self.e.state()),1)

class NodeTests(unittest.TestCase):
    def setUp(self):
        from kageyoni.application import Application
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'world.sqlite';self.e=Engine(self.path)
        changes=[]
        for id,visibility in [('a','public'),('b','public'),('secret','gm')]:
            changes.append(dict(op='create',domain='character',id=id,status='proposed',visibility=visibility,
                                evidence=[{'note':'Synthetic'}],data={'name':id,'entity_kind':'person'}))
        self.e.apply(dict(api_version=3,branch='main',expected_revision=0,request_id='fixture',kind='action',actor='fixture',narrative='Synthetic',changes=changes))
        self.app=Application(self.e,migrate=True)
    def tearDown(self):self.e.close();self.tmp.cleanup()
    def bind(self,character='a',request='bind',**kwargs):
        return self.app.nodes.bind('main',character,request,1,{'note':'owner-only provenance canary'},**kwargs)
    def test_persistence_without_story_event(self):
        from kageyoni.application import Application
        receipt=self.bind();before=self.app.nodes.read('main','a');self.e.close()
        self.e=Engine(self.path);self.app=Application(self.e)
        self.assertEqual(self.app.nodes.read('main','a'),before)
        self.assertEqual(self.e.branch('main')['revision'],1)
        self.assertEqual(self.e.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
        self.assertEqual(receipt['node_id'],before['node_id'])
    def test_request_idempotency_and_conflict(self):
        one=self.bind();two=self.bind();self.assertTrue(two['replayed']);self.assertEqual(one['node_id'],two['node_id'])
        with self.assertRaises(Rejected):self.bind(character='b')
        with self.assertRaises(Rejected):self.bind(request='second')
        self.assertEqual(len(self.app.nodes.list('main')),1)
    def test_unknown_stale_and_nonowner(self):
        with self.assertRaises(Rejected):self.bind(character='missing')
        with self.assertRaises(Rejected):self.bind(viewer='a')
        with self.assertRaises(Rejected):self.app.nodes.bind('main','a','stale',0,{'note':'x'})
        self.assertEqual(self.app.nodes.list('main'),[])
    def test_hidden_character_and_private_source_excluded(self):
        import json
        self.bind();self.bind('secret','secret-bind')
        visible=self.app.nodes.list('main',viewer='b');self.assertEqual([r['character_id'] for r in visible],['a'])
        rendered=json.dumps(self.app.nodes.read('main','a',viewer='b'))
        self.assertNotIn('provenance canary',rendered);self.assertNotIn('operational_history',rendered)
        with self.assertRaises(Rejected):self.app.nodes.read('main','secret',viewer='b')
    def test_branch_explicit_identity_link_no_history_copy(self):
        one=self.bind();self.e.fork('main','other',1)
        self.assertEqual(self.app.nodes.list('other'),[])
        self.app.nodes.bind('other','a','fork-bind',0,{'note':'explicit link'},node_id=one['node_id'])
        child=self.app.nodes.read('other','a');self.assertEqual(child['node_id'],one['node_id'])
        self.assertEqual(len(child['operational_history']),1)
        self.assertEqual(child['operational_history'][0]['receipt']['branch'],'other')
        with self.assertRaises(Rejected):self.app.nodes.bind('other','b','wrong-person',0,{'note':'x'},node_id=one['node_id'])
    def test_world_and_node_rollback_together(self):
        from kageyoni.persistence.unit_of_work import UnitOfWork
        with self.assertRaises(RuntimeError):
            with UnitOfWork(self.e.db):
                self.bind()
                command=TransactionTests.command(self,request='new',revision=1)
                self.e.apply(command)
                raise RuntimeError('crash before commit')
        self.assertEqual(self.app.nodes.list('main'),[]);self.assertIsNone(self.e.get('main','new'))
        self.assertEqual(self.e.branch('main')['revision'],1)
    def test_backup_restore_nodes_and_world(self):
        from kageyoni.application import Application
        self.bind();backup=Path(self.tmp.name)/'backup.sqlite';restored=Path(self.tmp.name)/'restored.sqlite'
        self.e.backup(backup);Engine.restore(backup,restored);r=Engine(restored)
        try:self.assertEqual(Application(r).nodes.read('main','a'),self.app.nodes.read('main','a'))
        finally:r.close()
    def test_migration_checksum_refused(self):
        from kageyoni.persistence.migrations import install_nodes
        self.e.db.execute("UPDATE migration_checks SET checksum='tampered' WHERE version=9")
        with self.assertRaises(Rejected):install_nodes(self.e)
    def test_interrupted_migration_atomic_retry(self):
        from unittest.mock import patch
        from kageyoni.persistence import migrations
        p=Path(self.tmp.name)/'fresh.sqlite';e=Engine(p)
        bad=Path(self.tmp.name)/'bad.sql';bad.write_text(migrations.MIGRATION.read_text()+'\nINVALID SQL;\n')
        try:
            with patch.object(migrations,'MIGRATION',bad):
                with self.assertRaises(Exception):migrations.install_nodes(e)
            self.assertIsNone(e.db.execute("SELECT 1 FROM sqlite_master WHERE name='network_nodes'").fetchone())
            self.assertIsNone(e.db.execute('SELECT 1 FROM migration_checks WHERE version=9').fetchone())
            self.assertTrue(list(p.parent.glob('fresh.sqlite.pre-v9-*.bak')))
            migrations.install_nodes(e);self.assertTrue(e.verify()['ok'])
        finally:e.close()

class OutcomeTests(unittest.TestCase):
    def test_wait_failure_block_and_success_are_distinct(self):
        from kageyoni.processes.outcomes import Result,Disposition as D,Objective as O,close_required
        for state in (D.FAILED,D.BLOCKED,D.WAITING,D.CANCELLED):
            r=Result(state,reason='requires attention',resume_condition='human response' if state==D.WAITING else None)
            self.assertEqual(close_required([r],checks_passed=True).disposition,state)
        r=Result(D.COMPLETED,O.ACHIEVED,reason='value checked',checks_passed=True,output=3)
        parent=close_required([r],checks_passed=True,objective=O.ACHIEVED,output=r.output)
        self.assertEqual(parent.output,3);self.assertEqual(parent.objective,O.ACHIEVED)
    def test_untyped_or_unchecked_completion_rejected(self):
        from kageyoni.processes.outcomes import Result,Disposition as D,close_required
        with self.assertRaises(Rejected):Result(D.COMPLETED,reason='looks good')
        with self.assertRaises(Rejected):Result(D.WAITING,reason='human')
        with self.assertRaises(Rejected):close_required([{'status':'completed'}],checks_passed=True)
        with self.assertRaises(Rejected):Result('completed',reason='untyped',checks_passed=True)

class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'cli.sqlite'
        e=Engine(self.path)
        e.apply(TransactionTests.command(self));e.close()
    def tearDown(self):self.tmp.cleanup()
    def cli(self, operation, payload=None, viewer=None):
        import subprocess,sys,json
        command=[sys.executable,'-m','kageyoni','--db',str(self.path),operation]
        if payload is not None:command+=['--input','-']
        if viewer:command+=['--viewer',viewer]
        return subprocess.run(command,input=json.dumps(payload) if payload is not None else None,text=True,capture_output=True)
    def test_real_cli_init_bind_read_and_rejections(self):
        import json
        self.assertEqual(self.cli('node-init').returncode,0)
        payload={'character_id':'one','expected_revision':1,'request_id':'cli-bind','source':{'note':'fixture'}}
        result=self.cli('node-bind',payload);self.assertEqual(result.returncode,0,result.stderr)
        node=json.loads(result.stdout)['node_id']
        read=self.cli('node-read',{'character_id':'one'});self.assertEqual(json.loads(read.stdout)['node_id'],node)
        self.assertNotEqual(self.cli('node-bind',dict(payload,request_id='bad',expected_revision=0)).returncode,0)
        self.assertNotEqual(self.cli('node-init',viewer='one').returncode,0)
    def test_menu_bind_and_read(self):
        import terminal
        from unittest.mock import patch
        app=terminal.App(Path(self.tmp.name)/'settings',self.path)
        try:
            with patch.object(app,'ask',side_effect=['INSTALL','fixture note']),patch.object(app,'choose',return_value=2),patch.object(app,'pick_record',return_value={'id':'one'}),patch.object(app,'show') as show:
                app.nodes();self.assertIn('node_id',show.call_args.args[0])
            with patch.object(app,'choose',return_value=1),patch.object(app,'pick_record',return_value={'id':'one'}),patch.object(app,'show') as show:
                app.nodes();self.assertEqual(show.call_args.args[0]['world']['character']['id'],'one')
        finally:app.session.close()
    def test_concurrent_same_request_single_identity(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from kageyoni.application import Application
        e=Engine(self.path);Application(e,migrate=True);e.close()
        barrier=Barrier(2)
        def bind():
            engine=Engine(self.path)
            try:
                app=Application(engine);barrier.wait(timeout=5)
                return app.nodes.bind('main','one','same-request',1,{'note':'concurrent fixture'})
            finally:engine.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(bind) for _ in range(2)];results=[f.result(timeout=10) for f in futures]
        self.assertEqual(results[0]['node_id'],results[1]['node_id'])
        self.assertEqual(sum(r['replayed'] for r in results),1)
    def test_tampered_node_receipt_detected(self):
        from kageyoni.application import Application
        e=Engine(self.path)
        try:
            app=Application(e,migrate=True);app.nodes.bind('main','one','bind',1,{'note':'fixture'})
            e.db.execute("UPDATE network_events SET receipt_json='{}'")
            with self.assertRaises(Rejected):e.verify()
        finally:e.close()

class RecoveryTests(unittest.TestCase):
    def test_historical_upgrade_preserves_tables_and_decision_fingerprint(self):
        import shutil
        from kageyoni.application import Application
        from kageyoni.decisions import fingerprint
        from kageyoni.resources import fixture_path
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'previous.sqlite';shutil.copy2(fixture_path('personality-fixture.sqlite'),p)
            e=Engine(p)
            try:
                names=[r[0] for r in e.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                def snapshot():return {n:[tuple(r) for r in e.db.execute('SELECT * FROM "'+n+'"')] for n in names if n not in ('engine_versions','migration_checks')}
                before=snapshot();fp=fingerprint(e,'main');Application(e,migrate=True)
                self.assertEqual(snapshot(),before);self.assertEqual(fingerprint(e,'main'),fp)
            finally:e.close()
    def test_process_death_before_commit_preserves_prior_state(self):
        import subprocess,sys
        from kageyoni.application import Application
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'crash.sqlite';e=Engine(p);e.apply(TransactionTests.command(self));Application(e,migrate=True);e.close()
            code="""import os,sys
from kageyoni.engine import Engine
from kageyoni.application import Application
from kageyoni.persistence.unit_of_work import UnitOfWork
e=Engine(sys.argv[1]);app=Application(e)
with UnitOfWork(e.db):
 app.nodes.bind('main','one','interrupted',1,{'note':'fixture'})
 os._exit(17)
"""
            r=subprocess.run([sys.executable,'-c',code,str(p)]);self.assertEqual(r.returncode,17)
            e=Engine(p)
            try:
                app=Application(e);self.assertEqual(app.nodes.list('main'),[])
                app.nodes.bind('main','one','interrupted',1,{'note':'fixture'})
                self.assertEqual(len(app.nodes.list('main')),1);self.assertTrue(e.verify()['ok'])
            finally:e.close()
    def test_backup_refuses_active_transaction_without_losing_work(self):
        with tempfile.TemporaryDirectory() as temp:
            e=Engine(Path(temp)/'world.sqlite')
            try:
                e.db.execute('BEGIN IMMEDIATE');e.apply(TransactionTests.command(self))
                with self.assertRaises(Rejected):e.backup(Path(temp)/'unsafe.sqlite')
                self.assertTrue(e.db.in_transaction);e.db.rollback();self.assertEqual(e.state(),[])
            finally:e.close()
    def test_deferred_constraint_failure_rolls_back_owned_unit(self):
        import sqlite3
        from kageyoni.persistence.unit_of_work import UnitOfWork
        with tempfile.TemporaryDirectory() as temp:
            e=Engine(Path(temp)/'world.sqlite')
            try:
                e.db.execute('CREATE TABLE fixture_parent(id TEXT PRIMARY KEY)')
                e.db.execute('CREATE TABLE fixture_child(id TEXT REFERENCES fixture_parent(id) DEFERRABLE INITIALLY DEFERRED)')
                with self.assertRaises(sqlite3.IntegrityError):
                    with UnitOfWork(e.db):e.db.execute("INSERT INTO fixture_child VALUES('missing')")
                self.assertFalse(e.db.in_transaction);self.assertEqual(e.db.execute('SELECT count(*) FROM fixture_child').fetchone()[0],0)
            finally:e.close()
