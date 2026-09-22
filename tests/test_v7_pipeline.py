import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from kageyoni.engine import Engine,Rejected
from kageyoni.workspaces.pipeline import Pipelines,verify_pipelines
from kageyoni.workspaces.repository import Repository,tree_digest

ROOT=Path(__file__).resolve().parents[1]
class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.path=self.root/'engine.sqlite';self.e=Engine(self.path)
        self.e.db.executescript((ROOT/'migration_016.sql').read_text())
        self.e.db.execute("INSERT INTO migration_checks VALUES(16,15,'migration_016.sql',?,'4',CURRENT_TIMESTAMP)",(hashlib.sha256((ROOT/'migration_016.sql').read_bytes()).hexdigest(),));self.e.db.commit();self.p=Pipelines(self.e)
    def tearDown(self):self.e.close();self.temp.cleanup()
    def write(self,id='write',deps=None):
        content='exact value';return dict(id=id,kind='write_file',config=dict(root=str(self.root),path=id+'.txt',content=content,expected_sha256=hashlib.sha256(content.encode()).hexdigest()),dependencies=deps or [])
    def test_all_dependency_types_block_then_pass_actual_value(self):
        for kind in ('DEPENDS_ON','REQUIRES','AFTER','USES'):
            flow=self.p.create('main',kind,[dict(id='review',kind='manual',config={}),self.write(kind,[dict(task_id='review',type=kind)])])
            pid=flow['pipeline_id'];r=self.p.run('main',pid);self.assertEqual(r['phase'],'waiting');self.assertFalse((self.root/(kind+'.txt')).exists())
            self.p.resume_manual('main',pid,'review',{'disposition':'completed','value':{'decision':'proceed'}},'Observed owner decision')
            r=self.p.run('main',pid);self.assertEqual(r['phase'],'completed');self.assertEqual((self.root/(kind+'.txt')).read_text(),'exact value')
    def test_manual_pending_failed_and_downstream_value(self):
        task=self.write();task['config'].pop('content');task['config']['content_from']='review';task['dependencies']=[dict(task_id='review',type='REQUIRES')]
        f=self.p.create('main','manual-values',[dict(id='review',kind='manual',config={}),task]);pid=f['pipeline_id'];self.p.run('main',pid)
        for disposition in ('waiting','failed'):
            self.p.resume_manual('main',pid,'review',dict(disposition=disposition,value='exact value'),'Explicit observation')
            self.assertNotEqual(self.p.run('main',pid)['phase'],'completed');self.assertFalse((self.root/'write.txt').exists())
        self.p.resume_manual('main',pid,'review',dict(disposition='completed',value='exact value'),'Observed result')
        self.assertEqual(self.p.run('main',pid)['phase'],'completed');self.assertEqual((self.root/'write.txt').read_text(),'exact value')
    def test_failed_upstream_value_rejected(self):
        task=self.write();task['config'].pop('content');task['config']['content_from']='review';task['dependencies']=[dict(task_id='review',type='REQUIRES')]
        f=self.p.create('main','bad-output',[dict(id='review',kind='manual',config={}),task]);pid=f['pipeline_id'];self.p.run('main',pid)
        self.p.resume_manual('main',pid,'review',dict(disposition='completed',value='wrong value'),'Observed result')
        self.assertEqual(self.p.run('main',pid)['phase'],'failed');self.assertFalse((self.root/'write.txt').exists())
    def test_failure_and_actual_retry_attempt(self):
        flow=self.p.create('main','retry',[self.write()]);pid=flow['pipeline_id']
        with patch('kageyoni.workspaces.pipeline.os.open',side_effect=OSError('fixture failure')):r=self.p.run('main',pid)
        self.assertEqual(r['phase'],'failed');r=self.p.run('main',pid)
        self.assertEqual(r['phase'],'completed');self.assertEqual(len(r['tasks']['write']['attempts']),2)
    def test_process_death_after_write_reconcile_no_repeat(self):
        flow=self.p.create('main','death',[self.write()]);pid=flow['pipeline_id']
        code="""import os,sys
from kageyoni.engine import Engine
from kageyoni.workspaces.pipeline import Pipelines
e=Engine(sys.argv[1]);p=Pipelines(e)
p._after_effect=lambda *args:os._exit(29)
p.run('main',sys.argv[2])
"""
        result=subprocess.run([sys.executable,'-c',code,str(self.path),pid],cwd=ROOT,timeout=20)
        self.assertEqual(result.returncode,29);self.assertEqual((self.root/'write.txt').read_text(),'exact value')
        with self.assertRaises(Rejected):self.p.run('main',pid)
        r=self.p.reconcile('main',pid);self.assertEqual(r['phase'],'completed');self.assertEqual(len(r['tasks']['write']['attempts']),1)
        self.assertEqual(self.p.run('main',pid)['phase'],'completed')
    def test_partial_write_not_completed(self):
        flow=self.p.create('main','partial',[self.write()]);pid=flow['pipeline_id']
        def corrupt(*args):(self.root/'write.txt').write_text('wrong');raise RuntimeError('interrupted')
        with patch.object(self.p,'_after_effect',side_effect=corrupt):self.p.run('main',pid)
        r=self.p.reconcile('main',pid);self.assertEqual(r['phase'],'waiting');self.assertEqual(r['tasks']['write']['phase'],'recoverable');self.assertNotIn('result',r['tasks']['write'])

    def test_conflicting_partial_effect_can_reconcile_after_owner_correction(self):
        flow=self.p.create('main','partial-recover',[self.write()]);pid=flow['pipeline_id']
        def corrupt(*args):(self.root/'write.txt').write_text('wrong');raise RuntimeError('interrupted')
        with patch.object(self.p,'_after_effect',side_effect=corrupt):self.p.run('main',pid)
        first=self.p.reconcile('main',pid);self.assertEqual(first['tasks']['write']['phase'],'recoverable')
        (self.root/'write.txt').write_text('exact value')
        fixed=self.p.reconcile('main',pid);self.assertEqual(fixed['phase'],'completed');self.assertEqual(fixed['tasks']['write']['phase'],'completed')

    def test_completed_output_is_reaudited_in_present_tense(self):
        flow=self.p.create('main','current-audit',[self.write()]);pid=flow['pipeline_id']
        done=self.p.run('main',pid);self.assertEqual(done['phase'],'completed')
        (self.root/'write.txt').write_text('changed outside engine')
        audited=self.p.run('main',pid);self.assertEqual(audited['phase'],'reconcile_required')
        self.assertEqual(audited['tasks']['write']['phase'],'completed')
        self.assertEqual(audited['tasks']['write']['current_verification']['status'],'diverged')
        (self.root/'write.txt').write_text('exact value')
        restored=self.p.reconcile('main',pid);self.assertEqual(restored['phase'],'completed')
        self.assertEqual(restored['tasks']['write']['current_verification']['status'],'verified')
    def test_preexisting_identical_file_not_claimed(self):
        (self.root/'write.txt').write_text('exact value');f=self.p.create('main','existing',[self.write()]);r=self.p.run('main',f['pipeline_id'])
        self.assertEqual(r['phase'],'waiting');self.assertEqual(r['tasks']['write']['attempts'],[])
    def test_cycle_unknown_type_path_escape_rejected(self):
        for task in (self.write(deps=[dict(task_id='write',type='REQUIRES')]),dict(self.write(),config=dict(self.write()['config'],path='../escape'))):
            with self.assertRaises(Rejected):self.p.create('main','bad',[task])
    def test_budget_and_version_resume(self):
        f=self.p.create('main','budget',[self.write('a'),self.write('b')]);pid=f['pipeline_id'];r=self.p.run('main',pid,max_steps=1)
        self.assertEqual(r['phase'],'waiting');self.assertFalse((self.root/'b.txt').exists())
        self.e.db.execute("UPDATE engine_versions SET version='99' WHERE component='pipeline_interface'");self.e.db.commit()
        with self.assertRaises(Rejected):self.p.run('main',pid)
    def test_reopen_receipts_and_integrity(self):
        f=self.p.create('main','reopen',[self.write()]);r=self.p.run('main',f['pipeline_id']);self.e.close();self.e=Engine(self.path)
        self.assertEqual(Pipelines(self.e).read('main',f['pipeline_id']),r);self.assertTrue(verify_pipelines(self.e))

class RepositoryTests(unittest.TestCase):
    setUp=PipelineTests.setUp
    tearDown=PipelineTests.tearDown
    # Repository mechanics isolated from separately integration-tested V5 qualification.
    def candidate(self,code='def add(a,b): return a+b\n'):
        source=self.root/'source';source.mkdir();(source/'calc.py').write_text('def add(a,b): return a-b\n')
        (source/'test_calc.py').write_text('import unittest\nfrom calc import add\nclass Test(unittest.TestCase):\n def test_add(self): self.assertEqual(add(2,3),5)\n')
        repo=Repository(self.e)
        self.method_patch=patch.object(repo,'_method_effect',return_value={'phase':'completed','scope':'isolated mechanics fixture'});self.method_patch.start();self.addCleanup(self.method_patch.stop)
        self.qualification_patch=patch.object(repo,'_qualified_candidate',return_value=None);self.qualification_patch.start();self.addCleanup(self.qualification_patch.stop)
        with patch.object(repo,'_qualification',return_value='fixture-qualified'):
            c=repo.prepare('main','repair',str(source),str(self.root/'candidate'),[dict(path='calc.py',before_sha256=hashlib.sha256((source/'calc.py').read_bytes()).hexdigest(),content=code)],['python','-m','unittest','discover'],'fixture')
        return repo,c
    def test_actual_repair_test_promote(self):
        repo,c=self.candidate()
        with patch.object(repo,'_qualification',return_value='fixture-qualified'):
            checked=repo.check('main',c['candidate_id']);self.assertEqual(checked['phase'],'checked')
            promoted=repo.promote('main',c['candidate_id'],self.root/'delivered');self.assertEqual(promoted['promoted_digest'],tree_digest(self.root/'delivered'))
    def test_mutation_between_check_promotion_rejected(self):
        repo,c=self.candidate()
        with patch.object(repo,'_qualification',return_value='fixture-qualified'):
            repo.check('main',c['candidate_id']);(self.root/'candidate'/'calc.py').write_text('def add(a,b): return 0\n')
            with self.assertRaises(Rejected):repo.promote('main',c['candidate_id'],self.root/'bad')
    def test_failed_test_and_timeout_are_failures(self):
        repo,c=self.candidate('def add(a,b): return 0\n')
        with patch.object(repo,'_qualification',return_value='fixture-qualified'):
            r=repo.check('main',c['candidate_id']);self.assertEqual(r['phase'],'failed')
            with patch('kageyoni.workspaces.repository.subprocess.run',side_effect=subprocess.TimeoutExpired('unittest',0.01)):
                r=repo.check('main',c['candidate_id'],timeout_seconds=.01)
            self.assertEqual(r['phase'],'failed');self.assertEqual(len(r['attempts']),2)
