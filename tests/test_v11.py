import tempfile,shutil,unittest
from pathlib import Path
from kageyoni.engine import Engine,Rejected
from kageyoni.persistence.migrations import install_all
from kageyoni.v11 import EnforcerRegistry,AssessmentLedger,FrontierManager,ProtectedOperations,ContextPackets,Warrant

class V11Tests(unittest.TestCase):
 def setUp(self):
  from kageyoni.resources import campaign_db_path
  self.t=tempfile.TemporaryDirectory();self.db=Path(self.t.name)/'v11.sqlite';shutil.copy2(campaign_db_path(),self.db);self.e=Engine(self.db);install_all(self.e)
 def tearDown(self):self.e.close();self.t.cleanup()
 def qualify(self,scope='story'):
  r=EnforcerRegistry(self.e)
  a=r.create_case(scope=scope,protected_requirement='valid-neighbor',expected_disposition='supported',basis={'fixture':'valid'})
  b=r.create_case(scope=scope,protected_requirement='invalid-neighbor',expected_disposition='contradicted',basis={'fixture':'invalid'})
  r.record_trial(case_id=a['case_id'],enforcer_id='semantic.guard',version='1',observed_disposition='supported')
  r.record_trial(case_id=b['case_id'],enforcer_id='semantic.guard',version='1',observed_disposition='contradicted')
  return r.qualify(enforcer_id='semantic.guard',version='1',scope=scope,status='qualified')
 def assessed(self,objective='A',scope='story'):
  q=self.qualify(scope);ops=ProtectedOperations(self.e);o=ops.declare(objective=objective,requirement_version='r1',scope=scope);ops.transition(o['operation_id'],'PREPARED')
  a=AssessmentLedger(self.e).record(enforcer_id='semantic.guard',qualification_id=q['qualification_id'],scope=scope,protected_requirement='r1',basis={'operation_id':o['operation_id'],'requirement_version':'r1'},disposition='supported',result={'fixture':True})
  o=ops.transition(o['operation_id'],'ASSESSED',patch={'assessment_id':a['assessment_id']});return ops,o,q
 def test_cannot_self_label_qualified_without_trials(self):
  with self.assertRaises(Rejected):EnforcerRegistry(self.e).qualify(enforcer_id='shortcut',version='1',scope='story',status='qualified')
 def test_wrong_trial_blocks_qualification(self):
  r=EnforcerRegistry(self.e);a=r.create_case(scope='story',protected_requirement='x',expected_disposition='supported',basis={'x':1});b=r.create_case(scope='story',protected_requirement='y',expected_disposition='contradicted',basis={'y':1});r.record_trial(case_id=a['case_id'],enforcer_id='bad',version='1',observed_disposition='contradicted');r.record_trial(case_id=b['case_id'],enforcer_id='bad',version='1',observed_disposition='contradicted')
  with self.assertRaises(Rejected):r.qualify(enforcer_id='bad',version='1',scope='story',status='qualified')
 def test_unqualified_cannot_authorize(self):
  ops,o,q=self.assessed()
  with self.assertRaises(Rejected):ops.transition(o['operation_id'],'AUTHORIZED')
 def test_scoped_qualification_authorizes(self):
  ops,o,q=self.assessed();x=ops.transition(o['operation_id'],'AUTHORIZED',qualification_id=q['qualification_id']);self.assertEqual(x['state'],'AUTHORIZED')
 def test_wrong_scope_rejected(self):
  ops,o,q=self.assessed(scope='story');q2=self.qualify('research')
  with self.assertRaises(Rejected):ops.transition(o['operation_id'],'AUTHORIZED',qualification_id=q2['qualification_id'])
 def test_cannot_change_objective(self):
  ops=ProtectedOperations(self.e);o=ops.declare(objective='A',requirement_version='r1',scope='story')
  with self.assertRaises(Rejected):ops.transition(o['operation_id'],'PREPARED',patch={'objective':'B'})
 def test_cannot_change_requirement_version(self):
  ops=ProtectedOperations(self.e);o=ops.declare(objective='A',requirement_version='r1',scope='story')
  with self.assertRaises(Rejected):ops.transition(o['operation_id'],'PREPARED',patch={'requirement_version':'r2'})
 def test_completion_requires_verification(self):
  ops,o,q=self.assessed();o=ops.transition(o['operation_id'],'AUTHORIZED',qualification_id=q['qualification_id']);o=ops._issue_fixture_execution(o['operation_id'],evidence_ref='fixture:execution',payload={'test':True})
  with self.assertRaises(Rejected):ops.transition(o['operation_id'],'COMPLETED')
 def test_full_protected_path(self):
  ops,o,q=self.assessed();o=ops.transition(o['operation_id'],'AUTHORIZED',qualification_id=q['qualification_id']);o=ops._issue_fixture_execution(o['operation_id'],evidence_ref='fixture:execution',payload={'test':True});o=ops.observe(o['operation_id'],outcome={'ok':True});o=ops.verify_observation(o['operation_id'],receipt={'check':'pass'});o=ops.complete(o['operation_id']);self.assertEqual(o['state'],'COMPLETED')
 def test_uncertain_external_effect_cannot_complete(self):
  ops,o,q=self.assessed();ops.transition(o['operation_id'],'AUTHORIZED',qualification_id=q['qualification_id']);o=ops._issue_fixture_execution(o['operation_id'],evidence_ref='fixture:execution');o=ops.transition(o['operation_id'],'UNCERTAIN')
  with self.assertRaises(Rejected):ops.transition(o['operation_id'],'COMPLETED')
 def test_context_unknown_blocks_commit_claim(self):
  c=ContextPackets(self.e).create(scope='story',basis={'branch':'main'},included=[],unresolved=[{'ref':'old-promise','blocking':True}],excluded=[]);self.assertFalse(c['sufficient_for_commit'])
 def test_context_nonblocking_unknown_preserved(self):
  c=ContextPackets(self.e).create(scope='story',basis={'branch':'main'},included=[],unresolved=[{'ref':'weather','blocking':False}],excluded=[]);self.assertTrue(c['sufficient_for_commit']);self.assertEqual(len(c['unresolved']),1)
 def test_frontier_preserves_parent_objective(self):
  f=FrontierManager(self.e).open(objective='find Voss',kind='missing_capability',payload={'capabilities_missing':['trace']})
  with self.assertRaises(Rejected):FrontierManager(self.e).transition(f['frontier_id'],'investigating',patch={'objective_or_direction':'find someone else'})
 def test_frontier_can_change_representation(self):
  f=FrontierManager(self.e).open(objective='find Voss',kind='unknown_representation',payload={});x=FrontierManager(self.e).transition(f['frontier_id'],'investigating',patch={'current_representation':'network graph'});self.assertEqual(x['payload']['current_representation'],'network graph')
 def test_assessment_requires_qualified_enforcer(self):
  q=EnforcerRegistry(self.e).qualify(enforcer_id='g',version='1',scope='story',status='shadow',evidence=['x'],metrics={})
  with self.assertRaises(Rejected):AssessmentLedger(self.e).record(enforcer_id='g',qualification_id=q['qualification_id'],scope='story',protected_requirement='canon',basis={'x':1},disposition='supported',result={})
 def test_assessment_records_unresolved(self):
  q=self.qualify();a=AssessmentLedger(self.e).record(enforcer_id='semantic.guard',qualification_id=q['qualification_id'],scope='story',protected_requirement='knowledge',basis={'record':'x'},disposition='unresolved',result={'next_probe':'retrieve event'});self.assertEqual(a['disposition'],'unresolved')
 def test_global_verify_covers_v11(self):self.assertTrue(self.e.verify()['ok'])
 def test_tampered_operation_detected(self):
  ops=ProtectedOperations(self.e);o=ops.declare(objective='A',requirement_version='r1',scope='story');self.e.db.execute("update v11_operations set payload_json='{}' where operation_id=?",(o['operation_id'],))
  with self.assertRaises(Rejected):self.e.verify()
 def test_warrant_issue_and_staleness(self):
  ledger = AssessmentLedger(self.e)
  w = ledger.issue_warrant(claim_id='claim:test-1', evidence_refs=['ev:1', 'ev:2'], scope='story')
  self.assertEqual(w.claim_id, 'claim:test-1')
  self.assertEqual(w.evidence_refs, ('ev:1', 'ev:2'))
  self.assertFalse(w.is_stale(w.revision))
  self.assertTrue(w.is_stale(w.revision + 1))
  self.assertTrue(w.digest)
  d = w.as_dict()
  self.assertEqual(d['claim_id'], 'claim:test-1')
 def test_warrant_requires_valid_evidence_refs(self):
  with self.assertRaises(Rejected):
   Warrant(warrant_id='w1', claim_id='c1', evidence_refs=[], scope='story', revision=1)

if __name__=='__main__':unittest.main()
