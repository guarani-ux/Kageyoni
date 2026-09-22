import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from kageyoni.engine import Engine
from scripts.verified_checkpoint import checkpoint
class DurableCampaignTests(unittest.TestCase):
 def test_large_history_reopen_backup_and_repeat_read(self):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'campaign.sqlite';e=Engine(path)
   for n in range(12):
    e.apply(dict(api_version=2,branch='main',expected_revision=n,request_id=f'large-{n}',kind='action',actor='gm',narrative='Synthetic durability fixture',changes=[dict(op='create',id=f'actor-{n}',domain='character',status='confirmed',visibility='public',data=dict(name=f'Fixture {n}',entity_kind='person',identity='x'*100000),evidence=[{"note":"Synthetic durability fixture"}])]))
   e.verify();e.close()
   for _ in range(2):
    receipt=checkpoint(path,Path(td)/f'backup-{_}.sqlite');self.assertEqual(receipt['revision'],12)
   with self.assertRaises(Exception):checkpoint(path,Path(td)/'backup-0.sqlite')
 def test_legacy_builtin_combat_registration_upgrades_and_routes(self):
  from kageyoni.workflows import Workflows
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'legacy.sqlite';e=Engine(p)
   e.register_module('kageyoni.combat','1','Kageyoni Play',['combat'],['branch revision'],['apply'],[],{'runtime_schema':'3','workflow_api':'2'})
   e.close();e=Engine(p)
   w=Workflows(e);proposal=w.prepare('combat','main','test-routing','gm','Synthetic bounded combat routing',action_spec={'feasible':True,'judgment':{'by':'gm','rationale':'Synthetic fixture only'},'mechanical':False},changes=[])
   self.assertTrue(e.apply(proposal['command'])['committed']);e.verify();e.close()
