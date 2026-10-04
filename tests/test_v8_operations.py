import base64
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from kageyoni.resources import fixture_path
from kageyoni.engine import Engine, Rejected
from kageyoni.operations import Operations
from kageyoni.persistence.migrations import install_all

class DailyOperationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.engine=Engine(self.root/'engine.sqlite');install_all(self.engine);self.ops=Operations(self.engine)
    def tearDown(self):self.engine.close();self.temp.cleanup()
    def cases(self):
        return [{'content_base64':base64.b64encode(b'abc').decode(),'max_bytes':n,'expected_sha256':hashlib.sha256(b'abc').hexdigest()} for n in [100,1]]
    def propose(self):return self.ops.propose_policy('pipeline.write_file',{'check_order':['size','utf8','sha256']},'Short circuit oversized output')['event_id']
    def test_policy_trial_activation_runtime_rollback(self):
        p=self.propose()
        with self.assertRaises(Rejected):self.ops.activate_policy(p,'invented-trial')
        trial=self.ops.trial_policy(p,self.cases());self.assertTrue(trial['supported'])
        activation=self.ops.activate_policy(p,trial['event_id'])
        receipt=self.ops.check_artifact('pipeline.write_file',b'abc',1,hashlib.sha256(b'abc').hexdigest());self.assertEqual(receipt['checks'],1)
        other=self.ops.check_artifact('unrelated',b'abc',1,hashlib.sha256(b'abc').hexdigest());self.assertEqual(other['checks'],2)
        self.ops.rollback_policy('pipeline.write_file',activation['event_id'])
        self.assertEqual(self.ops.check_artifact('pipeline.write_file',b'abc',1,hashlib.sha256(b'abc').hexdigest())['checks'],2)
        self.assertEqual(len(self.ops._events('artifact_check')),3)
    def test_failed_trial_cannot_activate_or_accept_supplied_flag(self):
        p=self.propose();trial=self.ops.trial_policy(p,self.cases()*1)
        with self.assertRaises(TypeError):self.ops.activate_policy(p,trial['event_id'],passed=True)
        same=self.ops.propose_policy('other',{'check_order':['utf8','size','sha256']},'No change')['event_id']
        bad=self.ops.trial_policy(same,self.cases());self.assertFalse(bad['supported'])
        with self.assertRaises(Rejected):self.ops.activate_policy(same,bad['event_id'])
    def test_settings_budget_preserved_reopen(self):
        self.ops.settings({'max_checks':1});self.assertEqual(self.ops.check_artifact('x',b'a',5,'0'*64)['disposition'],'blocked')
        self.engine.close();self.engine=Engine(self.root/'engine.sqlite');self.ops=Operations(self.engine)
        self.assertEqual(self.ops.settings()['max_checks'],1)
        with self.assertRaises(Rejected):self.ops.settings({'api_key':'secret'})
    def test_portable_export_restore_and_existing_destination_protected(self):
        self.ops.settings({'max_checks':12});bundle=self.root/'bundle.zip';self.ops.export_bundle(bundle)
        result=Operations.import_bundle(bundle,self.root/'imported');restored=Engine(result['path'])
        try:self.assertEqual(Operations(restored).settings()['max_checks'],12);self.assertTrue(restored.verify()['ok'])
        finally:restored.close()
        with self.assertRaises(Rejected):Operations.import_bundle(bundle,self.root/'imported')
        with self.assertRaises(Rejected):self.ops.export_bundle(bundle)
    def test_corruption_and_zip_traversal_fail_without_partial_import(self):
        bundle=self.root/'bundle.zip';self.ops.export_bundle(bundle)
        with zipfile.ZipFile(bundle) as src: files={n:src.read(n) for n in src.namelist()}
        files['engine.sqlite']+=b'corruption'
        with zipfile.ZipFile(self.root/'bad.zip','w') as out:
            for n,data in files.items():out.writestr(n,data)
        with self.assertRaises(Rejected):Operations.import_bundle(self.root/'bad.zip',self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
        with zipfile.ZipFile(self.root/'escape.zip','w') as out:out.writestr('../escaped','x');out.writestr('manifest.json','{}')
        with self.assertRaises(Rejected):Operations.import_bundle(self.root/'escape.zip',self.root/'escape')
        self.assertFalse((self.root/'escaped').exists())
    def test_migrate_copy_preserves_original_old_database(self):
        import shutil
        source=self.root/'old.sqlite';shutil.copy2(fixture_path('recovery/pre-v3-learning.sqlite'),source)
        before=source.read_bytes();target=self.root/'upgraded.sqlite';Operations.migrate_copy(source,target)
        self.assertEqual(source.read_bytes(),before)
        migrated=Engine(target)
        try:self.assertTrue(migrated.verify()['ok']);self.assertEqual(Operations(migrated).settings()['host_available'],False)
        finally:migrated.close()
        with self.assertRaises(Rejected):Operations.migrate_copy(source,target)
    def test_console_real_dispatch_and_menu(self):
        from kageyoni.console import dispatch,menu
        from unittest.mock import patch
        self.assertEqual(dispatch(self.engine,{'action':'settings','arguments':{'values':{'max_checks':18}}})['max_checks'],18)
        with patch('builtins.input',side_effect=['1','0']),patch('builtins.print') as output:menu(self.engine)
        self.assertTrue(output.called)
        with self.assertRaises(Rejected):dispatch(self.engine,{'service':'engine','action':'delete'})

    def test_relocated_artifact_bytes_and_missing_source_rejected(self):
        from kageyoni.application import Application
        from kageyoni.persistence.artifacts import Artifacts
        self.engine.apply(dict(api_version=3,branch='main',expected_revision=0,request_id='character',kind='action',actor='fixture',narrative='Synthetic portable artifact fixture',changes=[dict(op='create',domain='character',id='fixture',data={'name':'Fixture','entity_kind':'person'},status='proposed',visibility='public',evidence=[{'note':'Synthetic fixture'}])]))
        app=Application(self.engine);node=app.nodes.bind('main','fixture','bind',1,{'note':'Synthetic fixture'})
        workspace=self.engine.db.execute("SELECT workspace_id FROM network_workspaces WHERE branch='main'").fetchone()[0]
        artifact=Artifacts(self.engine).put(b'portable bytes','text/plain','artifact',workspace_id=workspace)
        self.ops.export_bundle(self.root/'with-artifact.zip'); restored=Operations.import_bundle(self.root/'with-artifact.zip',self.root/'relocated')
        engine=Engine(restored['path'])
        try:
            store=Artifacts(engine);record=store.read(artifact['artifact_id']);self.assertEqual(record['content'],b'portable bytes')
            self.assertTrue(Path(record['path']).is_relative_to(Path(restored['artifacts'])))
        finally:engine.close()
        Path(artifact['path']).unlink()
        with self.assertRaises(Rejected):self.ops.export_bundle(self.root/'missing.zip')
        self.assertFalse((self.root/'missing.zip').exists())

    def test_live_pipeline_consumes_and_preserves_policy_receipt(self):
        from kageyoni.workspaces.pipeline import Pipelines
        policy=self.propose();trial=self.ops.trial_policy(policy,self.cases());self.ops.activate_policy(policy,trial['event_id'])
        pipelines=Pipelines(self.engine)
        workflow=pipelines.create('main','workflow',[{'id':'write','kind':'write_file','config':{'root':str(self.root),'path':'output.txt','content':'abc','max_bytes':1,'expected_sha256':hashlib.sha256(b'abc').hexdigest()}}])
        result=pipelines.run('main',workflow['pipeline_id'])
        self.assertEqual(result['phase'],'failed');self.assertFalse((self.root/'output.txt').exists())
        checks=self.ops._events('artifact_check');self.assertEqual(checks[-1]['policy_id'],policy);self.assertEqual(checks[-1]['checks'],1)

    def test_import_external_work_unresolved_until_explicit_rebind(self):
        from kageyoni.workspaces.pipeline import Pipelines
        original=self.root/'original-output';original.mkdir()
        workflow=Pipelines(self.engine).create('main','portable-pending',[{'id':'write','kind':'write_file','config':{'root':str(original),'path':'result.txt','content':'abc','expected_sha256':hashlib.sha256(b'abc').hexdigest()}}])
        bundle=self.root/'pending.zip';exported=self.ops.export_bundle(bundle)
        self.assertEqual(len(exported['external_dependencies']),1)
        restored=Operations.import_bundle(bundle,self.root/'pending-restored')
        self.assertEqual(restored['external_state'],'unresolved; explicit rebind required')
        copied=Engine(restored['path'])
        try:
            service=Pipelines(copied)
            with self.assertRaises(Rejected):service.run('main',workflow['pipeline_id'])
            self.assertFalse((original/'result.txt').exists())
            newroot=self.root/'new-output';newroot.mkdir()
            service.rebind('main',workflow['pipeline_id'],{str(original):str(newroot)})
            self.assertEqual(service.run('main',workflow['pipeline_id'])['phase'],'completed')
            self.assertEqual((newroot/'result.txt').read_text(),'abc')
            self.assertFalse((original/'result.txt').exists())
        finally:copied.close()

