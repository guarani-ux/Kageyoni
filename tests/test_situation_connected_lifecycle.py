import unittest
from kageyoni.situations import SituationService,DomainProjection
from kageyoni.situations.catalog import install_defaults
from kageyoni.situations.runtime import SituationRuntime,WorkflowRun,ExtensionProposal,EvolutionProposal
from kageyoni.situations.service import SituationError

class ConnectedLifecycleTests(unittest.TestCase):
 def test_campaign_lifecycle(self):
  valid={"obs:objective","out:1","out:2","method:sciel","method:alexandra"}
  resolver=lambda ref,run: ref in valid
  participant=lambda p,ref,sid: (p,ref) in {("sciel","method:sciel"),("alexandra","method:alexandra")}
  s=install_defaults(SituationService(participant_evidence_resolver=participant))
  x=s.genesis("campaign","launch",{"objective":"launch","audience":"members"}); s.bind_workflow(x.situation_id,"campaign.default")
  r=SituationRuntime(s,resolver); parent=WorkflowRun("p",x.situation_id,"campaign.default",objective="launch",authority=("read","write")); r.start(parent)
  r.complete_stage("p","objective","obs:objective")
  r.wait("p","approval"); self.assertEqual("waiting",r.runs["p"].status); r.resume("p",condition_satisfied=True)
  r.propose_extension(ExtensionProposal("e",x.situation_id,"relation",{"from":"audience","relation":"interprets","to":"message"}))
  with self.assertRaises(SituationError): r.promote_extension("e",("out:1",))
  promoted=r.promote_extension("e",("out:1","out:2")); self.assertEqual("qualified",promoted.status)
  with self.assertRaises(SituationError): r.propose_evolution(EvolutionProposal("bad","workflow","campaign.default",{"add":"validation"},("fake",)))
  r.propose_evolution(EvolutionProposal("good","workflow","campaign.default",{"add":"validation"},("out:1",)))
  self.assertEqual([],r.recruit(x.situation_id,[{"participant_id":"sciel","covers":["composition"],"evidence_refs":["method:sciel"]}],[]))
  self.assertEqual(["sciel"],r.recruit(x.situation_id,[{"participant_id":"sciel","covers":["composition"],"evidence_refs":["method:sciel"]}],["composition"]))
  a=DomainProjection("a","sciel",x.situation_id,("relationships","composition"),("q",),method_refs=("method:sciel",))
  b=DomainProjection("b","alexandra",x.situation_id,("relationships","commitment"),("q",),method_refs=("method:alexandra",))
  s.propose_projection(a,established_refs={"method:sciel"}); s.propose_projection(b,established_refs={"method:alexandra"})
  collision=r.collide(["a","b"]); self.assertEqual(["relationships"],collision["shared"]); self.assertFalse(collision["redundant"])
  c=DomainProjection("c","sciel",x.situation_id,("relationships","composition"),("q2",),method_refs=("method:sciel",)); s.propose_projection(c,established_refs={"method:sciel"})
  self.assertTrue(r.collide(["a","c"])["redundant"])

if __name__=="__main__": unittest.main()
