import json,sqlite3,tempfile,unittest
from pathlib import Path
from kageyoni.engine import Engine,Rejected
from kageyoni.seed import seed

ROOT=Path(__file__).resolve().parents[1]
EVID=[{'note':'fixture evidence'}]
def create(d,i,**data): return {'op':'create','domain':d,'id':i,'data':data,'status':'proposed','visibility':'public','evidence':EVID}
class CausalIntegration(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.e=Engine(Path(self.t.name)/'x.sqlite')
  changes=[create('location','harbor',name='Harbor',kind='island'),create('character','actor',name='Actor',entity_kind='person',location='harbor'),create('character','family-a',name='Family member A',entity_kind='person',location='harbor'),create('environment','storm',location='harbor',feature='Storm',kind='weather',rule='concealment',duration='1 day',ending_condition='calm')]
  self.e.apply({'api_version':1,'branch':'main','expected_revision':0,'request_id':'seed','kind':'import','actor':'fixture','narrative':'fixture','changes':changes})
 def tearDown(self): self.e.close(); self.t.cleanup()
 def test_property_rule_event_consequence_and_choice(self):
  self.e.define_property('person.perception',1,'Perception','Noticing relevant signals','number',['person'],{},'active')
  self.e.set_property('main','actor','person.perception',1,'known',7,epistemic_status='proposed')
  self.e.add_rule('navigation',1,'Navigation',['person.perception'],['route.access'],True,{'kind':'threshold'},[('person.perception',1,'reads')])
  r=self.e.apply({'api_version':1,'branch':'main','expected_revision':1,'request_id':'event-1','kind':'action','actor':'actor','narrative':'Actor studies the storm','changes':[],'dependencies':[{'kind':'rule','ref_id':'navigation','version':'1','usage':'reads'}],'consequences':[{'id':'c1','subject_id':'harbor','effect':{'route':'obscured'},'trigger':{'condition':'storm'} }],'choice':{'id':'choice1','actor_id':'actor','intent':'cross harbor','method':'study weather','agency_state':'available','options':[{'id':'wait'},{'id':'cross'}],'selected':{'id':'wait'},'knowledge':{'known':['storm'],'hidden':['reef']}}})
  self.assertEqual(self.e.db.execute('select count(*) from event_dependencies').fetchone()[0],1)
  self.assertEqual(self.e.db.execute('select count(*) from consequences').fetchone()[0],1)
  self.assertEqual(self.e.db.execute('select agency_state from choices').fetchone()[0],'available')
  self.e.verify()
 def test_wrong_property_type_rejected(self):
  self.e.define_property('person.endurance',1,'Endurance','sustain effort','number',['person'],{},'active')
  with self.assertRaises(Rejected): self.e.set_property('main','actor','person.endurance',1,'known','high')
 def test_v1_upgrade(self):
  old=Path(self.t.name)/'old.sqlite'; con=sqlite3.connect(old); con.executescript('PRAGMA foreign_keys=ON; CREATE TABLE schema_version(version INTEGER PRIMARY KEY); INSERT INTO schema_version VALUES(1); CREATE TABLE branches(id TEXT PRIMARY KEY,parent TEXT,fork_revision INTEGER,revision INTEGER NOT NULL DEFAULT 0); INSERT INTO branches VALUES(\'main\',NULL,NULL,0); CREATE TABLE events(id TEXT,branch TEXT,revision INTEGER,request_id TEXT,payload_hash TEXT,command_json TEXT,kind TEXT,actor TEXT,narrative TEXT,clock_id TEXT,tick REAL,causes_json TEXT,prev_hash TEXT,event_hash TEXT,receipt_json TEXT,created_at TEXT); CREATE TABLE records(branch TEXT,id TEXT,domain TEXT,version INTEGER,status TEXT,visibility TEXT,audience_json TEXT,evidence_json TEXT,updated_event TEXT,PRIMARY KEY(branch,id));'); con.commit(); con.close(); upgraded=Engine(old); self.assertEqual(upgraded.db.execute('select version from schema_version').fetchone()[0],2); self.assertIsNotNone(upgraded.db.execute("select name from sqlite_master where name='property_values'").fetchone()); upgraded.close()
