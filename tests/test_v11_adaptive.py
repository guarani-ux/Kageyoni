import shutil,tempfile,unittest
from pathlib import Path
from kageyoni.engine import Engine,Rejected
from kageyoni.v11 import AdaptiveLoop,EnforcerRegistry,ProtectedOperations

class AdaptiveV11Tests(unittest.TestCase):
 def setUp(self):
  from kageyoni.resources import campaign_db_path
  self.t=tempfile.TemporaryDirectory();self.db=Path(self.t.name)/'db.sqlite';shutil.copy2(campaign_db_path(),self.db);self.e=Engine(self.db);from kageyoni.persistence.migrations import install_all;install_all(self.e);self.loop=AdaptiveLoop(self.e)
 def tearDown(self):self.e.close();self.t.cleanup()
 def qualify(self,scope):
  r=EnforcerRegistry(self.e)
  for name,expect in [('valid','supported'),('invalid','contradicted')]:
   c=r.create_case(scope=scope,protected_requirement=name,expected_disposition=expect,basis={'fixture':name});r.record_trial(case_id=c['case_id'],enforcer_id='guard',version='1',observed_disposition=expect)
  return r.qualify(enforcer_id='guard',version='1',scope=scope,status='qualified')
 def finish(self,oid,q):
  op=ProtectedOperations(self.e).read(oid)
  self.loop.assess(oid,enforcer_id='guard',qualification_id=q['qualification_id'],protected_requirement=op['requirement_version'],basis={'operation_id':oid},disposition='supported',result={'checked':True})
  ops=ProtectedOperations(self.e);ops.transition(oid,'AUTHORIZED',qualification_id=q['qualification_id']);ops._issue_fixture_execution(oid,evidence_ref='fixture:execution',payload={'checked':True});ops.observe(oid,outcome={'ok':True});ops.verify_observation(oid,receipt={'ok':True});return ops.complete(oid)
 def resolve(self,fid,refs):
  self.loop.investigate(fid,patch={'next_high_value_probe':'fixture probe'});obs=self.loop.observe_frontier(fid,refs=refs,payload={'fixture':True});return self.loop.resolve_frontier(fid,evidence=[obs['observation_id']])
 def test_story_unknown_stays_blocked_without_evidence(self):
  x=self.loop.begin(objective='continue Sciel scene',requirement_version='canon-r1',scope='story',basis={'branch':'main'},included=['scene'],unresolved=[{'ref':'old-promise','blocking':True}]);f=self.loop.open_frontier(x['operation']['operation_id'],kind='hidden_dependency',payload={'consequential_unknowns':['old-promise']});self.loop.investigate(f['frontier_id'],patch={'next_high_value_probe':'retrieve promise history'});obs=self.loop.observe_frontier(f['frontier_id'],refs=['search:no-authoritative-result']);f=self.loop.resolve_frontier(f['frontier_id'],evidence=[obs['observation_id']],remaining_unknowns=[{'ref':'old-promise','blocking':True}]);self.assertEqual(f['state'],'blocked');self.assertEqual(ProtectedOperations(self.e).read(x['operation']['operation_id'])['state'],'BLOCKED')
 def test_artifact_dependency_can_resolve_and_resume(self):
  x=self.loop.begin(objective='deliver artifact',requirement_version='artifact-r1',scope='artifact',basis={'workspace':'pipeline'},included=['draft'],unresolved=[{'ref':'destination','blocking':True}]);f=self.loop.open_frontier(x['operation']['operation_id'],kind='hidden_dependency',payload={'capabilities_missing':['writable destination']});self.loop.investigate(f['frontier_id'],patch={'current_representation':'destination binding'});obs=self.loop.observe_frontier(f['frontier_id'],refs=['destination'],payload={'destination':'/tmp/authorized'});self.loop.resolve_frontier(f['frontier_id'],evidence=[obs['observation_id']]);r=self.loop.resume(x['operation']['operation_id'],f['frontier_id'],basis={'workspace':'pipeline','destination':'/tmp/authorized'},included=['draft','destination']);q=self.qualify('artifact');done=self.finish(r['operation']['operation_id'],q);self.assertEqual(done['state'],'COMPLETED');self.assertEqual(done['objective'],'deliver artifact')
 def test_technical_missing_evidence_reenters_parent_contract(self):
  x=self.loop.begin(objective='repair repository',requirement_version='repo-r1',scope='technical',basis={'repo':'fixture'},included=['patch'],unresolved=[{'ref':'test-result','blocking':True}]);f=self.loop.open_frontier(x['operation']['operation_id'],kind='missing_reality_contact',payload={'next_high_value_probe':'run targeted test'});self.loop.investigate(f['frontier_id'],patch={'current_representation':'patch plus test evidence'});obs=self.loop.observe_frontier(f['frontier_id'],refs=['test-result'],payload={'test':'pass'});self.loop.resolve_frontier(f['frontier_id'],evidence=[obs['observation_id']]);r=self.loop.resume(x['operation']['operation_id'],f['frontier_id'],basis={'repo':'fixture'},included=['patch','test-result']);q=self.qualify('technical');done=self.finish(r['operation']['operation_id'],q);self.assertEqual(done['payload']['requirement_version'],'repo-r1')
 def test_frontier_cannot_rewrite_parent_goal(self):
  x=self.loop.begin(objective='find Voss',requirement_version='r1',scope='story',basis={'branch':'main'},included=[],unresolved=[{'ref':'location','blocking':True}]);f=self.loop.open_frontier(x['operation']['operation_id'],kind='unknown_representation',payload={})
  with self.assertRaises(Rejected):self.loop.investigate(f['frontier_id'],patch={'objective_or_direction':'find someone easier'})
if __name__=='__main__':unittest.main()
