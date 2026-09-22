"""Real local repair, exact-byte promotion, downstream values, and DAG recovery.

All world observations are explicitly synthetic; local code tests are executed.
"""
import argparse
import hashlib
import json
from pathlib import Path
from kageyoni.engine import Engine, digest, Rejected
from kageyoni.application import Application
from kageyoni.workspaces.registry import Registry
from kageyoni.workspaces.repository import Repository
from kageyoni.workspaces.pipeline import Pipelines
from kageyoni.intelligence.transfer import Transfers
from examples.v2_demo import run as seed


def run(destination):
    root=Path(destination);seed(root)
    engine=Engine(root/'synthetic.sqlite')
    try:
        from kageyoni.persistence.migrations import install_pipelines
        install_pipelines(engine);app=Application(engine)
        workspace=Registry(engine).open('main','analyst','repository','repository-workspace')
        mid=engine.db.execute('SELECT method_id FROM method_revisions LIMIT 1').fetchone()[0]
        transfer=Transfers(engine).propose(workspace['workspace_id'],mid,3,'repository-transfer',dict(destination_domain='repository',roles={},destination_roles=[],destination_relationships=[],field_map={'checks':'checks'}))
        tid=transfer['transfer_id']
        source=root/'source';source.mkdir()
        code='def add(a,b): return a-b\n';(source/'calc.py').write_bytes(code.encode('utf-8'))
        (source/'test_calc.py').write_bytes(b'import unittest\nfrom calc import add\nclass Test(unittest.TestCase):\n def test_add(self): self.assertEqual(add(2,3),5)\n def test_negative(self): self.assertEqual(add(-2,3),1)\n')
        repo=Repository(engine)
        candidate=repo.prepare('main','actual-repair',source,root/'candidate',[dict(path='calc.py',before_sha256=hashlib.sha256(code.encode()).hexdigest(),content='def add(a,b): return a+b\n')],['python','-m','unittest','discover'],tid)
        checked=repo.check('main',candidate['candidate_id'])
        premature_blocked=False
        try:repo.promote('main',candidate['candidate_id'],root/'premature')
        except Rejected:premature_blocked=True
        trial=repo.trial_artifact('main',candidate['candidate_id'],'actual-test-evidence')
        qualified=Transfers(engine).record_trial(tid,'checked-repair-trial',trial['artifact']['artifact_id'],trial['checks'],'Actual local unittest result. Bounded evidence for this candidate, not general coding competence.')
        promoted=repo.promote('main',candidate['candidate_id'],root/'delivered')
        content='Verified candidate '+promoted['promoted_digest']
        pipeline=Pipelines(engine);flow=pipeline.create('main','release-note',[
            dict(id='decision',kind='manual',config={}),
            dict(id='receipt',kind='write_file',config=dict(root=str(root),path='release-note.txt',content_from='decision',expected_sha256=hashlib.sha256(content.encode()).hexdigest()),dependencies=[dict(task_id='decision',type='REQUIRES')])])
        waiting=pipeline.run('main',flow['pipeline_id'])
        pipeline.resume_manual('main',flow['pipeline_id'],'decision',dict(disposition='waiting',resume_condition='Owner review pending'),'Review has not occurred')
        still_waiting=pipeline.run('main',flow['pipeline_id'])
        pipeline.resume_manual('main',flow['pipeline_id'],'decision',dict(disposition='completed',value=content),'Owner accepts this synthetic local fixture result')
        completed=pipeline.run('main',flow['pipeline_id'])
        controls=dict(mapped_method_executed=checked['attempts'][-1]['method_effect']['phase']=='completed' and checked['attempts'][-1]['method_effect']['result']['ranked'][0]['terms'][0]['recorded_value']==2,actual_tests_pass=checked['phase']=='checked' and checked['attempts'][-1]['tests']==2,unqualified_promotion_blocked=premature_blocked,exact_promotion=promoted['promoted_digest']==checked['candidate_digest'],manual_pending_blocks=waiting['phase']==still_waiting['phase']=='waiting',downstream_consumes_output=(root/'release-note.txt').read_text()==content and completed['phase']=='completed')
        assert all(controls.values()),controls
        report=dict(synthetic=True,controls=controls,candidate=promoted,transfer=qualified,pipeline=completed,verification=engine.verify(),limits='One local arithmetic repair. Semantic transfer judgment attributed; no general repository competence or model advantage established.')
        (root/'v7-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    finally:engine.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    result=run(parser.parse_args().output);print(json.dumps(result['controls'],indent=2))
