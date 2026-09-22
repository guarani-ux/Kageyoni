import unittest
from kageyoni.situations import SituationService, DomainProjection
from kageyoni.situations.catalog import install_defaults
from kageyoni.situations.service import SituationError

class SituationArchitectureTests(unittest.TestCase):
    def setUp(self): self.s=install_defaults(SituationService())
    def test_genesis_preserves_unknowns(self):
        x=self.s.genesis("production_brief","make a video",{"objective":"launch","audience":None,"deliverables":["video"],"constraints":[]})
        self.assertIn("audience",x.unknowns)
    def test_genesis_does_not_invent(self):
        x=self.s.genesis("research","investigate",{"question":"why?"})
        self.assertNotIn("sources",x.objects)
    def test_workflow_applicability(self):
        x=self.s.genesis("research","q",{"question":"q"})
        with self.assertRaises(SituationError): self.s.bind_workflow(x.situation_id,"campaign.default")
        self.s.bind_workflow(x.situation_id,"research.default")
    def test_domain_requires_established_evidence(self):
        x=self.s.genesis("campaign","c",{"objective":"o","audience":"a"})
        p=DomainProjection("p","sciel",x.situation_id,("relationships",),("what changes between elements?",))
        with self.assertRaises(SituationError): self.s.propose_projection(p,established_refs=set())
    def test_reopen_from_shared_store(self):
        from kageyoni.situations.storage import MemorySituationStore
        store=MemorySituationStore(); a=install_defaults(SituationService(store)); x=a.genesis("research","q",{"question":"q"})
        b=SituationService(store)
        self.assertEqual(x.situation_id, b.snapshot(x.situation_id)["situation_id"])

    def test_domain_accepts_evidenced_projection(self):
        x=self.s.genesis("campaign","c",{"objective":"o","audience":"a"})
        p=DomainProjection("p","sciel",x.situation_id,("relationships",),("q",),method_refs=("method:composition",))
        self.s.propose_projection(p,established_refs={"method:composition"})
        self.assertIn("p",self.s.projections)

if __name__=="__main__": unittest.main()
