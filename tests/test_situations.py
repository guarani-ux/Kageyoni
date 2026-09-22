import unittest
from kageyoni.situations import SituationService, DomainProjection
from kageyoni.situations.catalog import install_defaults
from kageyoni.situations.service import SituationError

class SituationArchitectureTests(unittest.TestCase):
 def setUp(self): self.s=install_defaults(SituationService(participant_evidence_resolver=lambda participant,ref,situation: participant=="sciel" and ref=="method:composition"))
 def test_genesis_preserves_unknowns(self):
  x=self.s.genesis("production_brief","make a video",{"objective":"launch","audience":None,"deliverables":["video"],"constraints":[]}); self.assertIn("audience",x.unknowns)
 def test_genesis_preserves_contradiction_without_choosing(self):
  x=self.s.genesis("campaign","c",{"objective":"o","audience":{"__alternatives__":["members","nonmembers"]}}); self.assertEqual(["members","nonmembers"],x.contradictions["audience"]); self.assertIsNone(x.objects["audience"]); self.assertIn("audience",x.unknowns)
 def test_genesis_does_not_invent(self):
  x=self.s.genesis("research","investigate",{"question":"why?"}); self.assertNotIn("sources",x.objects)
 def test_workflow_applicability(self):
  x=self.s.genesis("research","q",{"question":"q"})
  with self.assertRaises(SituationError): self.s.bind_workflow(x.situation_id,"campaign.default")
  self.s.bind_workflow(x.situation_id,"research.default")
 def test_domain_requires_established_evidence(self):
  x=self.s.genesis("campaign","c",{"objective":"o","audience":"a"}); p=DomainProjection("p","sciel",x.situation_id,("relationships",),("q",))
  with self.assertRaises(SituationError): self.s.propose_projection(p,established_refs=set())
 def test_domain_accepts_bound_evidence(self):
  x=self.s.genesis("campaign","c",{"objective":"o","audience":"a"}); p=DomainProjection("p","sciel",x.situation_id,("relationships",),("q",),method_refs=("method:composition",)); self.s.propose_projection(p,established_refs={"method:composition"}); self.assertIn("p",self.s.projections)
 def test_domain_cannot_borrow_other_participant_evidence(self):
  x=self.s.genesis("campaign","c",{"objective":"o","audience":"a"}); p=DomainProjection("borrowed","alexandra",x.situation_id,("relationships",),("q",),method_refs=("method:composition",))
  with self.assertRaises(SituationError): self.s.propose_projection(p,established_refs={"method:composition"})
if __name__=="__main__": unittest.main()
