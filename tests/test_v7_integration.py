"""V5–V7 actual destination trial, with no mocked qualification or checker."""
import json
from pathlib import Path
import tempfile
import unittest
from kageyoni.engine import Engine,Rejected
from kageyoni.workspaces.repository import Repository
from examples.v7_demo import run

class DestinationIntegrationTests(unittest.TestCase):
    def test_actual_trial_qualification_exact_promotion_and_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'demo';report=run(root)
            self.assertTrue(all(report['controls'].values()));self.assertTrue(report['verification']['ok'])
            e=Engine(root/'synthetic.sqlite')
            try:
                candidate=report['candidate'];self.assertEqual(Repository(e).read('main',candidate['candidate_id'])['phase'],'promoted')
                self.assertEqual((root/'delivered'/'calc.py').read_text(),'def add(a,b): return a+b\n')
                from kageyoni.intelligence.transfer import Transfers
                from kageyoni.persistence.artifacts import Artifacts
                tid=candidate['request']['qualification_id'];transfer=Transfers(e).read(tid)
                checks=[dict(name='exact_candidate_unittest',passed=True)]
                forged=dict(transfer_id=tid,destination_domain='repository',candidate_id='invented',candidate_digest=candidate['candidate_digest'],check_digest='invented',checks=checks)
                artifact=Artifacts(e).put(json.dumps(forged),'application/json','forged-trial',workspace_id=transfer['workspace_id'])
                with self.assertRaises(Rejected):Transfers(e).record_trial(tid,'forged-trial',artifact['artifact_id'],checks,'Approval without executed candidate must fail')
            finally:e.close()

class RepositoryMethodIntegrationTests(unittest.TestCase):
    def test_mapped_method_runs_and_unknown_guard_or_metric_stays_unresolved(self):
        import copy,hashlib
        from kageyoni.application import Application
        from kageyoni.intelligence.transfer import Transfers
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'demo';report=run(root);e=Engine(root/'synthetic.sqlite')
            try:
                repo=Repository(e);app=Application(e);transfers=Transfers(e)
                candidate=report['candidate'];effect=candidate['attempts'][-1]['method_effect']
                self.assertEqual(effect['phase'],'completed');self.assertEqual(effect['result']['ranked'][0]['terms'][0]['recorded_value'],2)
                transfer=transfers.read(candidate['request']['qualification_id'])
                original=app.methods.read('main',transfer['method_id'],transfer['method_revision'])
                for case in ('guard','metric'):
                    definition=copy.deepcopy(original['definition'])
                    if case=='guard':definition['preconditions'].append('judge_unrecorded_aesthetic_quality')
                    method=app.methods.create('main',transfer['node_id'],'new-method-'+case,e.branch('main')['revision'],definition,original['source_refs'])
                    app.methods.assign('main',transfer['node_id'],method['method_id'],1,'new-assignment-'+case,e.branch('main')['revision'],'experimental','Synthetic negative method guard trial')
                    mapped=transfers.propose(transfer['workspace_id'],method['method_id'],1,'negative-transfer-'+case,dict(destination_domain='repository',roles={},destination_roles=[],destination_relationships=[],field_map={'checks':'aesthetic_quality' if case=='metric' else 'checks'}))
                    code=(root/'source'/'calc.py').read_bytes()
                    prepared=repo.prepare('main','negative-repair-'+case,root/'source',root/('candidate-'+case),[dict(path='calc.py',before_sha256=hashlib.sha256(code).hexdigest(),content='def add(a,b): return a+b\n')],['python','-m','unittest','discover'],mapped['transfer_id'])
                    checked=repo.check('main',prepared['candidate_id']);self.assertEqual(checked['attempts'][-1]['tests'],2)
                    self.assertEqual(checked['attempts'][-1]['method_effect']['phase'],'waiting');self.assertEqual(checked['phase'],'failed')
                    with self.assertRaises(Rejected):repo.trial_artifact('main',prepared['candidate_id'],'unresolved-'+case)
            finally:e.close()


class CollectivePipelineIntegrationTests(unittest.TestCase):
    def test_collective_artifact_consumed_as_actual_downstream_bytes(self):
        from examples.v6_demo import run as seed
        from tests.test_v6_composition import make_drafts
        from kageyoni.intelligence.network import Network
        from kageyoni.persistence.migrations import install_pipelines
        from kageyoni.workspaces.pipeline import Pipelines
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'demo';seed(root);e=Engine(root/'synthetic.sqlite')
            try:
                install_pipelines(e);drafts,workspaces,transfers=make_drafts(e)
                text='\n'.join(d['text'] for d in drafts)
                composition=Network(e).compose('main','pipeline-composition',workspaces[0],[d['draft_id'] for d in drafts],dict(text=text,uses=[dict(draft_id=d['draft_id'],quote=d['text']) for d in drafts],rationale='Authored actual-source compilation'))
                artifact=composition['artifact'];p=Pipelines(e)
                flow=p.create('main','consume-collective',[
                    dict(id='read',kind='artifact_read',config=dict(artifact_id=artifact['artifact_id'],expected_sha256=artifact['digest'],composition_id=composition['composition_id'])),
                    dict(id='deliver',kind='write_file',config=dict(root=str(root),path='collective.md',content_from='read',expected_sha256=artifact['digest']),dependencies=[dict(task_id='read',type='USES')])])
                result=p.run('main',flow['pipeline_id']);self.assertEqual(result['phase'],'completed');self.assertEqual((root/'collective.md').read_text(encoding='utf-8'),text)
                self.assertEqual(result['tasks']['read']['attempts'][0]['composition_id'],composition['composition_id'])
            finally:e.close()

class RelocatedRecoveryTests(unittest.TestCase):
    def test_pending_restored_pipeline_requires_explicit_new_root(self):
        import hashlib
        from kageyoni.workspaces.pipeline import Pipelines
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'original';run(root);e=Engine(root/'synthetic.sqlite')
            other=Path(temp)/'relocated';other.mkdir();newroot=other/'outputs';newroot.mkdir()
            try:
                content='portable pending work';sha=hashlib.sha256(content.encode()).hexdigest()
                flow=Pipelines(e).create('main','portable',[dict(id='write',kind='write_file',config=dict(root=str(root),path='pending.txt',content=content,expected_sha256=sha))])
                backup=Path(temp)/'backup.sqlite';e.backup(backup)
                Engine.restore(backup,other/'engine.sqlite')
            finally:e.close()
            restored=Engine(other/'engine.sqlite');p=Pipelines(restored)
            try:
                with self.assertRaises(Rejected):p.run('main',flow['pipeline_id'])
                self.assertFalse((root/'pending.txt').exists());self.assertFalse((newroot/'pending.txt').exists())
                p.rebind('main',flow['pipeline_id'],{str(root):str(newroot)})
                result=p.run('main',flow['pipeline_id']);self.assertEqual(result['phase'],'completed')
                self.assertEqual((newroot/'pending.txt').read_text(),content);self.assertFalse((root/'pending.txt').exists())
                self.assertTrue(result['rebindings']);self.assertEqual(len(result['tasks']['write']['attempts']),1)
            finally:restored.close()
    def test_uncertain_effect_must_match_new_root_then_reconcile_without_repeat(self):
        import hashlib,shutil
        from unittest.mock import patch
        from kageyoni.workspaces.pipeline import Pipelines
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'original';run(root);e=Engine(root/'synthetic.sqlite')
            other=Path(temp)/'relocated';other.mkdir()
            content='durable effect';sha=hashlib.sha256(content.encode()).hexdigest()
            try:
                p=Pipelines(e);flow=p.create('main','uncertain',[dict(id='write',kind='write_file',config=dict(root=str(root),path='uncertain.txt',content=content,expected_sha256=sha))])
                with patch.object(p,'_after_effect',side_effect=RuntimeError('interrupted')):p.run('main',flow['pipeline_id'])
                backup=Path(temp)/'backup.sqlite';e.backup(backup);Engine.restore(backup,other/'engine.sqlite')
            finally:e.close()
            restored=Engine(other/'engine.sqlite');p=Pipelines(restored)
            try:
                with self.assertRaises(Rejected):p.rebind('main',flow['pipeline_id'],{str(root):str(other)})
                shutil.copy2(root/'uncertain.txt',other/'uncertain.txt')
                p.rebind('main',flow['pipeline_id'],{str(root):str(other)})
                result=p.reconcile('main',flow['pipeline_id']);self.assertEqual(result['phase'],'completed');self.assertEqual(len(result['tasks']['write']['attempts']),1)
                self.assertEqual(result['tasks']['write']['attempts'][0]['phase'],'reconciled')
            finally:restored.close()
    def test_repository_rebind_verifies_relocated_trees_and_preserves_history(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'original';report=run(root);e=Engine(root/'synthetic.sqlite')
            other=Path(temp)/'relocated';other.mkdir()
            try:
                backup=Path(temp)/'backup.sqlite';e.backup(backup);Engine.restore(backup,other/'engine.sqlite')
            finally:e.close()
            restored=Engine(other/'engine.sqlite');repo=Repository(restored);cid=report['candidate']['candidate_id']
            try:
                historical=repo.read('main',cid)
                with self.assertRaises(Rejected):repo.reconcile('main',cid)
                for name in ('source','candidate','delivered'):shutil.copytree(root/name,other/name)
                (other/'candidate'/'calc.py').write_text('wrong candidate')
                with self.assertRaises(Rejected):repo.rebind('main',cid,other/'source',other/'candidate',other/'delivered')
                shutil.copy2(root/'candidate'/'calc.py',other/'candidate'/'calc.py')
                rebound=repo.rebind('main',cid,other/'source',other/'candidate',other/'delivered')
                self.assertEqual(rebound['attempts'],historical['attempts']);self.assertEqual(rebound['candidate_digest'],historical['candidate_digest'])
                self.assertEqual(rebound['origin_database'],str((other/'engine.sqlite').resolve()))
                self.assertEqual(repo.reconcile('main',cid)['phase'],'promoted')
            finally:restored.close()
