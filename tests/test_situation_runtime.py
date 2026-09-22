import unittest
from kageyoni.situations import SituationService, DomainProjection
from kageyoni.situations.catalog import install_defaults
from kageyoni.situations.runtime import *
from kageyoni.situations.service import SituationError

class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.s=install_defaults(SituationService()); self.x=self.s.genesis("campaign","launch",{"objective":"launch","audience":"members"}); self.s.bind_workflow(self.x.situation_id,"campaign.default"); self.r=SituationRuntime(self.s)
 def test_nested_cannot_replace_objective_or_authority(self):
  self.r.start(WorkflowRun("p",self.x.situation_id,"campaign.default",objective="launch",authority=("read","write")))
  with self.assertRaises(SituationError): self.r.start(WorkflowRun("c",self.x.situation_id,"campaign.default","p","different",("read",)))
  with self.assertRaises(SituationError): self.r.start(WorkflowRun("c2",self.x.situation_id,"campaign.default","p","launch",("admin",)))
 def test_stage_requires_observation(self):
  self.r.start(WorkflowRun("p",self.x.situation_id,"campaign.default",objective="launch"))
  with self.assertRaises(SituationError): self.r.complete_stage("p","objective",{})
 def test_extensions_start_local_and_need_repeat_for_promotion(self):
  p=ExtensionProposal("e",self.x.situation_id,"relation",{"from":"audience","relation":"interprets","to":"message"})
  self.r.propose_extension(p)
  with self.assertRaises(SituationError): self.r.promote_extension("e",("one",))
  q=self.r.promote_extension("e",("one","two")); self.assertEqual("qualified",q.status)
 def test_recruitment_can_choose_nobody(self): self.assertEqual([],self.r.recruit(self.x.situation_id,[{"participant_id":"sciel","covers":["composition"],"evidence_refs":["m"]}],[]))
 def test_recruitment_requires_evidenced_relevance(self): self.assertEqual([],self.r.recruit(self.x.situation_id,[{"participant_id":"x","covers":["audience"]}],["audience"]))
 def test_collision_preserves_difference_and_detects_redundancy(self):
  a=DomainProjection("a","sciel",self.x.situation_id,("relationships","composition"),("q",),method_refs=("m1",)); b=DomainProjection("b","alexandra",self.x.situation_id,("relationships","commitment"),("q",),method_refs=("m2",)); self.s.propose_projection(a,established_refs={"m1"}); self.s.propose_projection(b,established_refs={"m2"}); z=self.r.collide(["a","b"]); self.assertEqual(["relationships"],z["shared"]); self.assertFalse(z["redundant"])
 def test_evolution_cannot_be_learned_from_completion_alone(self):
  with self.assertRaises(SituationError): self.r.propose_evolution(EvolutionProposal("p","workflow","campaign.default",{"add":"audience_validation"},()))

if __name__=="__main__": unittest.main()
