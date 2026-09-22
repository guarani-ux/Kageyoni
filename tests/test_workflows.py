import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from kageyoni.engine import Engine, Rejected
from kageyoni.seed import seed
from kageyoni.workflows import Workflows
from test_engine import EngineTests, create, patch, ROOT

class WorkflowTests(EngineTests):
    # Avoid inherited test duplication: populated below after class creation.
    def test_transfer_preview_then_commit(self):
        w=Workflows(self.e); before=self.e.state()
        p=w.prepare('transfer_item','main','transfer','gm','Synthetic transfer',item='sword',recipient='b')
        self.assertEqual(before,self.e.state()); self.assertFalse(p['preview']['committed'])
        self.e.apply(p['command']); self.assertEqual(self.e.get('main','custody')['data']['holder'],'b'); self.e.verify()
    def test_time_due_is_not_automatic_resolution(self):
        self.apply([create('schedule','s',clock='clock',due=2,trigger='Election',proposed_effect='Faction wins',phase='pending')])
        p=Workflows(self.e).prepare('advance_time','main','advance','gm','Two days pass',clock='clock',tick=2)
        self.e.apply(p['command']); self.assertEqual(self.e.get('main','s')['data']['phase'],'due'); self.e.verify()
    def test_preview_can_become_stale(self):
        p=Workflows(self.e).prepare('transfer_item','main','transfer','gm','Synthetic transfer',item='sword',recipient='b')
        self.apply([patch('a',condition='tired')]); self.reject(p['command'])
    def test_generic_workflow(self):
        p=Workflows(self.e).prepare('record_decision','main','decision','gm','Synthetic decision',changes=[create('decision','d',actor='a',choice='Wait')])
        self.e.apply(p['command']); self.e.verify()
    def test_unknown_workflow(self):
        with self.assertRaises(Rejected): Workflows(self.e).prepare('invent','main','x','gm','x')
    def test_unknown_workflow_parameter(self):
        with self.assertRaises(Rejected): Workflows(self.e).prepare('advance_time','main','x','gm','x',clock='clock',tick=2,secret_extra=True)
    def test_activity_module_routes_one_resolution(self):
        w = Workflows(self.e)
        proposal = w.prepare(
            'travel', 'main', 'travel-module', 'a', 'Synthetic travel module action',
            action_spec={'actor': 'a', 'difficulty': 10, 'requires_roll': False, 'modifier': 1},
            changes=[],
        )
        self.assertTrue(any(d['ref_id'] == 'kageyoni.travel' for d in proposal['command']['dependencies']))
        receipt = self.e.apply(proposal['command'])
        self.assertTrue(receipt['committed'])
        self.e.verify()

# Use fixture methods but do not re-run the base test suite under this class.
for name in dir(EngineTests):
    if name.startswith('test_') and name not in WorkflowTests.__dict__: setattr(WorkflowTests,name,None)

class FreshSessionTests(unittest.TestCase):
    def test_seed_fork_turn_save_reload_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'world.sqlite'; e=Engine(path); seed(e,ROOT/'sources'); original=e.state()
            e.fork('main','test-scene',1); e.close()
            c=dict(api_version=1,branch='test-scene',expected_revision=0,request_id='test-rest',kind='action',actor='test-gm',narrative='SYNTHETIC TEST: Alexandra rests; this is not canon.',changes=[patch('alexandra',condition='resting; shoulder remains wounded')])
            command=Path(temp)/'command.json'; command.write_text(json.dumps(c))
            def cli(*args):
                p=subprocess.run([sys.executable,'-m','kageyoni','--db',str(path),*args],cwd=ROOT,text=True,capture_output=True)
                self.assertEqual(p.returncode,0,p.stderr); return json.loads(p.stdout)
            receipt=cli('apply','--input',str(command)); self.assertTrue(receipt['committed'])
            cli('verify'); view=cli('context','--branch','test-scene','--domain','character')
            alexandra=next(r for r in view['records'] if r['id']=='alexandra'); self.assertIn('wounded',alexandra['data']['condition'])
            backup=Path(temp)/'saved.sqlite'; cli('backup','--output',str(backup))
            restored=Engine(backup); self.assertEqual(original,restored.state('main')); restored.verify(); restored.close()

# Imported unittest classes otherwise get discovered twice.
del EngineTests
