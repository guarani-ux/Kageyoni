import unittest
from kageyoni.situations import SituationService, DomainProjection
from kageyoni.situations.catalog import install_defaults
from kageyoni.situations.runtime import WorkflowRun, ExtensionProposal, EvolutionProposal, SituationRuntime
from kageyoni.situations.service import SituationError

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.s = install_defaults(SituationService(participant_evidence_resolver=lambda participant,ref,situation: (participant,ref) in {("sciel","m1"),("alexandra","m2")}))
        self.x = self.s.genesis("campaign", "launch", {"objective": "launch", "audience": "members"})
        self.s.bind_workflow(self.x.situation_id, "campaign.default")
        self.valid_evidence = {"obs:objective", "out:one", "out:two", "m1", "m2"}
        self.r = SituationRuntime(self.s, lambda ref, run: ref in self.valid_evidence, test_mode=True)

    def test_nested_cannot_replace_objective_or_authority(self):
        self.r.start(WorkflowRun("p", self.x.situation_id, "campaign.default", objective="launch", authority=("read", "write")))
        with self.assertRaises(SituationError):
            self.r.start(WorkflowRun("c", self.x.situation_id, "campaign.default", "p", "different", ("read",)))
        with self.assertRaises(SituationError):
            self.r.start(WorkflowRun("c2", self.x.situation_id, "campaign.default", "p", "launch", ("admin",)))

    def test_wait_requires_condition_and_resume_checks_it(self):
        self.r.start(WorkflowRun("wait",self.x.situation_id,"campaign.default",objective="launch"))
        with self.assertRaises(SituationError): self.r.wait("wait","")
        self.r.wait("wait","human decision")
        self.assertEqual("waiting",self.r.runs["wait"].status)
        with self.assertRaises(SituationError): self.r.resume("wait",condition_satisfied=False)
        self.r.resume("wait",condition_satisfied=True)
        self.assertEqual("active",self.r.runs["wait"].status)

    def test_failure_is_not_completion(self):
        self.r.start(WorkflowRun("fail",self.x.situation_id,"campaign.default",objective="launch"))
        self.r.fail("fail","tool error")
        self.assertEqual("failed",self.r.runs["fail"].status)
        self.assertEqual("tool error",self.r.runs["fail"].failure_reason)

    def test_stage_requires_engine_evidence(self):
        self.r.start(WorkflowRun("p", self.x.situation_id, "campaign.default", objective="launch"))
        with self.assertRaises(SituationError):
            self.r.complete_stage("p", "objective", "forged")
        self.r.complete_stage("p", "objective", "obs:objective")
        self.assertIn("objective", self.r.runs["p"].completed_stages)

    def test_extension_promotion_requires_repeat_and_custody(self):
        p = ExtensionProposal("e", self.x.situation_id, "relation", {"from": "audience", "relation": "interprets", "to": "message"})
        self.r.propose_extension(p)
        with self.assertRaises(SituationError):
            self.r.promote_extension("e", ("out:one",))
        with self.assertRaises(SituationError):
            self.r.promote_extension("e", ("fake:one", "fake:two"))
        q = self.r.promote_extension("e", ("out:one", "out:two"))
        self.assertEqual("qualified", q.status)

    def test_recruitment_can_choose_nobody_and_requires_evidence(self):
        self.assertEqual([], self.r.recruit(self.x.situation_id, [{"participant_id": "sciel", "covers": ["composition"], "evidence_refs": ["m1"]}], []))
        self.assertEqual([], self.r.recruit(self.x.situation_id, [{"participant_id": "x", "covers": ["audience"]}], ["audience"]))
        self.assertEqual([], self.r.recruit(self.x.situation_id, [{"participant_id": "x", "covers": ["audience"], "evidence_refs": ["forged"]}], ["audience"]))
        self.assertEqual(["x"], self.r.recruit(self.x.situation_id, [{"participant_id": "x", "covers": ["audience"], "evidence_refs": ["m1"]}], ["audience"]))

    def test_collision_preserves_difference(self):
        a = DomainProjection("a", "sciel", self.x.situation_id, ("relationships", "composition"), ("q",), method_refs=("m1",))
        b = DomainProjection("b", "alexandra", self.x.situation_id, ("relationships", "commitment"), ("q",), method_refs=("m2",))
        self.s.propose_projection(a, established_refs={"m1"})
        self.s.propose_projection(b, established_refs={"m2"})
        z = self.r.collide(["a", "b"])
        self.assertEqual(["relationships"], z["shared"])
        self.assertFalse(z["redundant"])

    def test_evolution_requires_observed_outcome(self):
        with self.assertRaises(SituationError):
            self.r.propose_evolution(EvolutionProposal("p", "workflow", "campaign.default", {"add": "audience_validation"}, ()))
        with self.assertRaises(SituationError):
            self.r.propose_evolution(EvolutionProposal("p2", "workflow", "campaign.default", {"add": "audience_validation"}, ("fake",)))
        self.r.propose_evolution(EvolutionProposal("p3", "workflow", "campaign.default", {"add": "audience_validation"}, ("out:one",)))
        self.assertIn("p3", self.r.evolution)

if __name__ == "__main__":
    unittest.main()
