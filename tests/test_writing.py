"""NONCANONICAL writing integration: evidence, agency, delivery and continuity."""
import copy,json,shutil,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from kageyoni.engine import Engine,Rejected
from kageyoni import writing as w, personality as p, decisions as d
from kageyoni.workflows import Workflows
from examples.personality_journey import setup,event,change,spec
ROOT=Path(__file__).resolve().parents[1]

def review():return dict(by='fixture-gm',rationale='Reviewed source fidelity, perspective, voice, open agency and scene pacing.',checks={k:True for k in w.CONTRACT['review']})

class WritingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'fixture.sqlite';self.e=Engine(self.path);setup(self.e)
 def tearDown(self):self.e.close();self.tmp.cleanup()
 def brief(self,**kw):
  q=dict(form='narration',audience='mira',purpose='Orient and leave the crossing choice open',scene='scene',focus=['water','guard.secret']);q.update(kw)
  return w.brief(self.e,'main',**q)
 def publish(self,b=None,**kw):
  b=b or self.brief();args=dict(branch='main',request_id='present',expected_revision=b['revision'],brief_spec=b['request'],brief_hash=b['brief_hash'],text='Mira watches the rising water. The crossing remains a choice.',claims=[],review=review());args.update(kw)
  return w.publish(self.e,**args)
 def dialogue(self):
  rhetoric=dict(purpose='Offer company without pressure',strategy='An indirect invitation',subtext='I care whether you face this alone',listener_assumptions=[dict(listener='oren',interpretation='Perhaps Oren wants company',basis=[])])
  p.dialogue_propose(self.e,'main',spec(self.e),dict(id='turn',listeners=['oren'],act='invite',text='Want company for the next inspection?',mode='spoken',visibility='public'),[],dict(by='fixture-gm',rationale='Ordinary invitation'),rhetoric=rhetoric)
  return d.commit(self.e,'main','conversation','mira',True,'NONCANONICAL invitation')
 def receive(self,**kw):
  args=dict(branch='main',request_id='response',expected_revision=self.e.branch('main')['revision'],listener='oren',turn='turn',interpretation='Oren suspects criticism rather than an invitation',certainty='tentative',response='He withdraws for a moment',review=review());args.update(kw);return w.receive(self.e,**args)
 def test_all_forms_use_grounded_briefs_and_session_surfaces_craft(self):
  before=self.e.state();clock=self.e.get('main','clock')
  for form in w.FORMS:
   b=self.brief(form=form);self.assertEqual(b['guidance']['version'],'1');self.assertIn(form,b['guidance']['forms'])
   self.assertIn('guard.secret',json.dumps(b['private_focus']));self.assertNotIn('SECRET_FACTION_ORDER',json.dumps(b['audience_facts']))
  self.assertEqual(self.e.state(),before);self.assertEqual(self.e.get('main','clock'),clock)
  self.assertEqual(Workflows(self.e).open_session()['writing_contract']['review'],w.CONTRACT['review'])
 def test_publish_is_private_presentation_not_world_change_or_knowledge(self):
  before=[r for r in self.e.state()];b=self.brief();r=self.publish(b)
  self.assertEqual([x for x in self.e.state() if x['domain']!='writing_delivery'],before)
  self.assertEqual(self.e.get('main','clock')['data']['tick'],0)
  visible=json.dumps(self.e.context('main',viewer='mira'));self.assertNotIn('SECRET_FACTION_ORDER',visible)
  self.assertNotIn('delivery:present',json.dumps(self.e.context('main',viewer='oren')))
  self.assertEqual(len(self.brief()['previous_deliveries']),1)
  self.assertTrue(self.publish(b)['replayed'])
  with self.assertRaisesRegex(Rejected,'changed content'):self.publish(b,text='Changed retry')
  self.assertTrue(self.e.replay('main')['complete'])
 def test_hidden_and_subjective_sources_cannot_certify_fact(self):
  for source in ('guard.secret','mira.rumor'):
   b=self.brief(focus=[source])
   with self.assertRaises(Rejected):self.publish(b,claims=[dict(status='fact',statement='A certainty',basis=[dict(id=source,version=1)])])
  self.assertIsNone(self.e.get('main','delivery:present'))
  b=self.brief(focus=['mira.rumor']);self.publish(b,claims=[dict(status='belief',statement='Mira believes the traveler',basis=[dict(id='mira.rumor',version=1)])])
 def test_forged_stale_and_failed_review_leave_no_partial_delivery(self):
  b=self.brief()
  with self.assertRaisesRegex(Rejected,'altered'):self.publish(b,brief_hash='forged')
  bad=review();bad['checks']['agency']=False
  with self.assertRaisesRegex(Rejected,'incomplete'):self.publish(b,review=bad)
  with self.assertRaisesRegex(Rejected,'interface'):self.publish(b,interface_version='99')
  event(self.e,[change(self.e,'water',feature='storm')])
  with self.assertRaisesRegex(Rejected,'stale'):self.publish(b)
  self.assertIsNone(self.e.get('main','delivery:present'))
 def test_rhetoric_reception_and_misunderstanding_feed_later_context(self):
  receipt=self.dialogue();cmd=json.loads(self.e.db.execute('SELECT command_json FROM events WHERE id=?',(receipt['event_id'],)).fetchone()[0])
  self.assertEqual(cmd['judgment']['dialogue_grounding']['rhetoric']['purpose'],'Offer company without pressure')
  self.receive();b=p.brief(self.e,'main','oren')
  self.assertIn('suspects criticism',b['receptions'][0]['data']['interpretation'])
  self.assertEqual(self.e.get('main','mira.oren')['data']['feeling'],'uncertain')
  self.assertFalse(any(r['domain']=='knowledge' and r['data']['holder']=='oren' for r in self.e.state()))
  next_scene=d.propose(self.e,'main',spec(self.e,'reply',actor='oren'))
  self.assertEqual(len(next_scene['assessment']['personality']['brief']['receptions']),1)
  self.assertNotIn('suspects criticism',json.dumps(self.e.context('main',viewer='mira')))
 def test_no_unheard_reception_or_omniscient_listener_model(self):
  with self.assertRaises(Rejected):self.receive()
  self.dialogue()
  with self.assertRaises(Rejected):self.receive(listener='guard')
  rhetoric=dict(purpose='Ask',strategy='Direct',subtext='Concern',listener_assumptions=[dict(listener='oren',interpretation='Knows the secret',basis=[dict(id='guard.secret',version=1)])])
  with self.assertRaisesRegex(Rejected,'unavailable'):w.validate_rhetoric(self.e,'main','mira',{'interlocutors':['oren']},rhetoric)
 def test_corrections_preserve_originals_and_latest_reception(self):
  self.dialogue();self.receive();old=self.e.get('main','reception:response')
  self.receive(request_id='reconsidered',supersedes='reception:response',interpretation='Oren now sees an invitation')
  self.assertEqual(self.e.get('main','reception:response'),old)
  self.assertEqual(len(p.brief(self.e,'main','oren')['receptions']),1)
  with self.assertRaisesRegex(Rejected,'immutable'):event(self.e,[change(self.e,'reception:response',interpretation='erase original')])
  self.publish();before=self.e.get('main','delivery:present')
  self.publish(request_id='corrected',supersedes='delivery:present',text='A clarified account')
  self.assertEqual(self.e.get('main','delivery:present'),before)
 def test_event_history_preserves_visible_evidence_and_recording_order(self):
  event_receipt=event(self.e,[change(self.e,'water',feature='storm')])
  b=self.brief(form='history',event_ids=[event_receipt['event_id']])
  self.assertEqual(b['event_evidence'][0]['changes'][0]['data']['feature'],'storm')
  self.assertEqual(b['event_evidence'][0]['recording_revision'],self.e.branch('main')['revision'])
  self.publish(b,claims=[dict(status='belief',statement='The recorded account describes a storm',basis=[dict(id='water',version=2)])])
  deps=self.e.impact('record','water','2');self.assertIn('event_id',json.dumps(deps))
 def test_branch_snapshot_reopen_replay_preserve_deliveries_and_reception(self):
  self.dialogue();self.receive();self.publish();self.e.fork('main','other',self.e.branch('main')['revision']);self.e.register_snapshot('main')
  self.e.close();self.e=Engine(self.path)
  self.assertEqual(self.e.replay('main')['records'],self.e.state('main'))
  self.assertEqual(self.e.replay('other')['records'],self.e.state('other'))
  self.assertEqual(self.e.get('other','delivery:present')['data']['text'],self.e.get('main','delivery:present')['data']['text'])
 def test_failed_apply_rolls_back_and_retry_publishes_once(self):
  b=self.brief();original=self.e._validate_world
  def fail(branch):original(branch);raise RuntimeError('interrupted before commit')
  with patch.object(self.e,'_validate_world',fail),self.assertRaises(RuntimeError):self.publish(b)
  self.assertIsNone(self.e.get('main','delivery:present'))
  self.publish(b);self.assertTrue(self.publish(b)['replayed'])
 def test_upgrade_actual_v7_and_interrupted_migration(self):
  from kageyoni.resources import fixture_path
  old=Path(self.tmp.name)/'old.sqlite';shutil.copy2(fixture_path('recovery/pre-writing-v1.sqlite'),old)
  read=Path.read_text
  def bad(path,*a,**kw):
   s=read(path,*a,**kw);return s+'\nINVALID SQL;' if path.name=='migration_008.sql' else s
  with patch.object(Path,'read_text',bad),self.assertRaises(sqlite3.Error):Engine(old)
  c=sqlite3.connect(old);self.assertEqual(c.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0],7);c.close()
  e=Engine(old)
  try:self.assertEqual(len(e.state()),165);self.assertEqual(e.branch('main')['revision'],1);self.assertTrue(e.verify()['ok'])
  finally:e.close()
 def test_v7_pending_fixture_survives_upgrade(self):
  from kageyoni.resources import fixture_path
  old=Path(self.tmp.name)/'pending.sqlite';shutil.copy2(fixture_path('personality-fixture.sqlite'),old)
  e=Engine(old)
  try:
   result=d.commit(e,'main','resume-fixture','mira',True,'NONCANONICAL old decision resumed')
   self.assertEqual(result['revision'],5);self.assertTrue(e.verify()['ok'])
  finally:e.close()

if __name__=='__main__':unittest.main()
