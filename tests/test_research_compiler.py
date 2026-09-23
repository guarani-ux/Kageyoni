"""
Unit tests for Upstream Research-to-Creative Cognitive Compiler.
Verifies the 9 Hardening Pillars, bidirectional traceability, and uncertainty propagation.
"""

import time
import unittest
from kageyoni.research_compiler.claims import (
    ClaimGraph,
    ClaimNode,
    SourceRecord,
    EpistemicStatus,
)
from kageyoni.research_compiler.topic_modeler import TopicModeler, TopicModel
from kageyoni.research_compiler.adversarial import AdversarialAuditor
from kageyoni.research_compiler.treatment_generator import (
    TreatmentGenerator,
    StoryArchetype,
    CompetingTreatment,
)
from kageyoni.research_compiler.package_compiler import (
    ScriptReadyCompiler,
    ScriptReadyPackage,
    AudienceModel,
)


class TestResearchCompiler(unittest.TestCase):

    def setUp(self):
        self.graph = ClaimGraph()

        # Add physical source records
        self.src1 = SourceRecord(
            source_id="src_cpl_audit_2024",
            title="Calgary Public Library Services Ecosystem Audit",
            provenance="C:\\Users\\flowe\\OneDrive\\Desktop\\Calgary Public Library Services Ecosystem Audit.docx",
            author_or_institution="Calgary Public Library Operations",
            direct_excerpt="Grade 3-6 educational literacy programs reached over 26,600 student participants across 12 programs.",
            date_recorded=time.time(),
            reliability_tier="PRIMARY_CORROBORATED",
        )
        self.src2 = SourceRecord(
            source_id="src_reading_research",
            title="Discourse Comprehension and Cognitive Reading Bridges",
            provenance="Kintsch & van Dijk (1978) / Canadian Literacy Framework",
            author_or_institution="Academic Reading Studies",
            direct_excerpt="Visual intimidation increases sharply between Grade 3 and 4 as illustrations are removed from curriculum texts.",
            date_recorded=time.time(),
            reliability_tier="PRIMARY_CORROBORATED",
        )
        self.graph.add_source(self.src1)
        self.graph.add_source(self.src2)

        # Add verified claims
        self.claim1 = ClaimNode(
            claim_id="clm_student_reach",
            statement="CPL literacy programs reached over 26,600 student participants with a 37% CTR improvement.",
            epistemic_status=EpistemicStatus.SOURCE_FACT,
            provenance_sources=["src_cpl_audit_2024"],
            confidence_level="HIGH",
            falsification_condition="If audited attendance logs show fewer than 20,000 unique students.",
        )
        self.claim2 = ClaimNode(
            claim_id="clm_visual_friction",
            statement="Grade 4 reading resistance is triggered by the sudden absence of visual support in text.",
            epistemic_status=EpistemicStatus.SOURCE_FACT,
            provenance_sources=["src_reading_research"],
            confidence_level="HIGH",
            falsification_condition="If reading latency tests demonstrate identical friction on illustrated texts.",
        )
        # Child synthesis claim
        self.claim3 = ClaimNode(
            claim_id="clm_graphic_novel_bridge",
            statement="Graphic novels act as an empirical bridge to restore reading fluency for struggling 4th graders.",
            epistemic_status=EpistemicStatus.SYNTHESIS,
            provenance_sources=["src_reading_research"],
            confidence_level="HIGH",
            parent_claim_ids=["clm_visual_friction"],
            falsification_condition="If comprehension scores fail to improve after 60 days of graphic novel access.",
        )
        # Uncertain hypothesis claim
        self.claim_hypo = ClaimNode(
            claim_id="clm_audiobook_parity",
            statement="Audiobooks provide 100% equivalent vocabulary acquisition as print reading for struggling readers.",
            epistemic_status=EpistemicStatus.HYPOTHESIS,
            provenance_sources=[],
            confidence_level="CONTESTED",
            falsification_condition="Comparative vocabulary retention tests.",
        )

        self.graph.add_claim(self.claim1)
        self.graph.add_claim(self.claim2)
        self.graph.add_claim(self.claim3)
        self.graph.add_claim(self.claim_hypo)

        self.audience = AudienceModel(
            target_segment="Parents of Grade 3-6 students struggling with reading in Calgary urban communities.",
            prior_knowledge_baseline="Parents believe their child has lost interest in books or lacks discipline.",
            active_misconceptions=["'Graphic novels don't count as real reading'", "'Library cards only offer old physical books'"],
            practical_and_emotional_stakes="Parental guilt and anxiety over student report cards and falling behind in school.",
            reception_friction="Skepticism that a free public library service can rival private paid tutoring.",
        )

        self.comm_problem = {
            "current_state": "Parents do not understand that reading resistance is visual friction, and unaware CPL offers free reading coaches.",
            "desired_shift": "Shift from parental anxiety to empowered library card utilization and graphic novel bridge adoption.",
            "decision_to_enable": "Parent registers for a library card and attends Saturday drop-in reading coaching.",
        }

        self.story_territory = {
            "core_frictions": ["The sudden disappearance of pictures in 4th grade books creates cognitive intimidation."],
            "transformations": ["From a child avoiding chapter books in shame to confidently reading graphic novels."],
            "human_stakes": ["Academic confidence, self-worth, family reading stress."],
        }

        self.narrative_ingredients = {
            "essential_facts": ["26,600 students reached", "Free access with card", "3-step reading bridge"],
            "compulsory_scenes_or_proofs": ["Demonstration of illustrated vs unillustrated text cognitive load"],
            "voices_and_perspectives": ["Student, Parent, Children's Librarian"],
        }

        self.constraints = {
            "must_not_claim": ["Do not claim graphic novels permanently replace text chapter books.", "Do not promise instant overnight grade increases."],
            "must_not_omit": ["Must explicitly state that library cards and coaching are 100% free."],
        }

        self.open_questions = {
            "research_gaps": ["Exact breakdown of graphic novel borrowing rates in East vs West Calgary branches."],
        }

    def test_claim_graph_anti_laundering(self):
        """Pillar 4: Prohibits declaring SOURCE_FACT without provenance sources."""
        laundered = ClaimNode(
            claim_id="clm_fake",
            statement="Everyone in Calgary loves the library.",
            epistemic_status=EpistemicStatus.SOURCE_FACT,
            provenance_sources=[],  # Empty!
        )
        with self.assertRaises(ValueError):
            self.graph.add_claim(laundered)

    def test_backward_lineage_walk(self):
        """Pillar 4 & Traceability: Verifies child synthesis traces backward to physical source records."""
        lineage = self.graph.trace_backward_lineage("clm_graphic_novel_bridge")
        self.assertEqual(lineage["claim_id"], "clm_graphic_novel_bridge")
        self.assertEqual(lineage["epistemic_status"], "SYNTHESIS")
        self.assertEqual(len(lineage["parent_lineages"]), 1)

        parent = lineage["parent_lineages"][0]
        self.assertEqual(parent["claim_id"], "clm_visual_friction")
        self.assertEqual(len(parent["direct_sources"]), 1)
        self.assertEqual(parent["direct_sources"][0]["source_id"], "src_reading_research")
        self.assertIn("Kintsch", parent["direct_sources"][0]["provenance"])

    def test_forward_contradiction_propagation(self):
        """Pillar 8 & Traceability: Contradictory evidence invalidates parent and all downstream children."""
        # Invalidate parent claim
        invalidated = self.graph.invalidate_claim(
            "clm_visual_friction",
            "New 2026 empirical study disproves visual friction hypothesis."
        )
        self.assertIn("clm_visual_friction", invalidated)
        self.assertIn("clm_graphic_novel_bridge", invalidated)  # Child MUST be invalidated!

        self.assertTrue(self.graph.claims["clm_visual_friction"].is_invalidated)
        self.assertTrue(self.graph.claims["clm_graphic_novel_bridge"].is_invalidated)
        self.assertIn("Upstream dependency", self.graph.claims["clm_graphic_novel_bridge"].invalidation_reason)

    def test_topic_modeler_builds_prior_to_audience(self):
        """Pillar 3: Subject modeling must succeed before audience/creative decisions."""
        topic = TopicModeler.build_topic_model(
            topic_id="top_youth_literacy",
            subject_title="Calgary Youth Literacy & Cognitive Reading Bridge",
            core_state_of_affairs="Calgary elementary students face literacy transitions between Grade 3 and 4 as school curricula remove illustrations, creating visual intimidation.",
            graph=self.graph,
            stakeholders=[{"name": "Students", "stance": "Intimidated"}, {"name": "Parents", "stance": "Anxious"}],
            active_tensions=[{"tension": "Text reading drills vs Graphic novel reading joy"}],
        )
        self.assertGreaterEqual(len(topic.established_facts), 2)
        self.assertGreaterEqual(topic.information_value_score, 0.35)

    def test_adversarial_auditor(self):
        """Pillar 5: Adversarial auditor flags selection bias and probes counter-evidence."""
        topic = TopicModeler.build_topic_model(
            topic_id="top_youth_literacy",
            subject_title="Calgary Youth Literacy & Cognitive Reading Bridge",
            core_state_of_affairs="Calgary elementary students face literacy transitions between Grade 3 and 4.",
            graph=self.graph,
        )
        audit = AdversarialAuditor.audit_topic(topic, self.graph)
        self.assertIsNotNone(audit.vulnerability_rating)
        self.assertTrue(len(audit.findings) > 0)

    def test_competing_treatments_evaluates_nine_archetypes(self):
        """Pillar 6: Evaluates all 9 canonical story archetypes and scores them."""
        topic = TopicModeler.build_topic_model(
            topic_id="top_youth_literacy",
            subject_title="Calgary Youth Literacy & Cognitive Reading Bridge",
            core_state_of_affairs="Calgary elementary students face literacy transitions.",
            graph=self.graph,
            stakeholders=[{"name": "Students"}, {"name": "Parents"}],
            active_tensions=[{"tension": "Friction vs Joy"}],
        )
        treatments = TreatmentGenerator.evaluate_all_archetypes(
            topic=topic,
            audience_need="Solve reading friction for struggling Grade 4 child.",
            communication_objective="Drive program attendance and card signups.",
        )
        self.assertEqual(len(treatments), 9)
        top = treatments[0]
        self.assertIn(top.archetype, (StoryArchetype.PROBLEM_SOLUTION, StoryArchetype.CHARACTER_DRIVEN))
        self.assertGreater(top.composite_score, 0.5)
        self.assertTrue(len(top.mandatory_flip_condition) > 10)

    def test_script_ready_package_compilation_and_uncertainty_propagation(self):
        """Pillars 8 & 9: Complete 10-section package compiles and propagates uncertainty warnings."""
        topic = TopicModeler.build_topic_model(
            topic_id="top_youth_literacy",
            subject_title="Calgary Youth Literacy & Cognitive Reading Bridge",
            core_state_of_affairs="Calgary elementary students face literacy transitions.",
            graph=self.graph,
            stakeholders=[{"name": "Students"}, {"name": "Parents"}],
            active_tensions=[{"tension": "Friction vs Joy"}],
        )
        treatments = TreatmentGenerator.evaluate_all_archetypes(
            topic=topic,
            audience_need="Solve reading friction.",
            communication_objective="Drive card signups.",
        )

        pkg = ScriptReadyCompiler.compile_package(
            subject_title="CPL Grade 3-6 Literacy Initiative",
            topic=topic,
            graph=self.graph,
            audience=self.audience,
            comm_problem=self.comm_problem,
            story_territory=self.story_territory,
            treatments=treatments,
            narrative_ingredients=self.narrative_ingredients,
            constraints=self.constraints,
            open_questions=self.open_questions,
        )

        self.assertIsNotNone(pkg.package_id)
        self.assertEqual(pkg.creative_decision["selected_archetype"], treatments[0].archetype.value)

        # Pillar 8: Verify uncertainty warning for clm_audiobook_parity was propagated!
        self.assertTrue(any("clm_audiobook_parity" in w for w in pkg.uncertainty_warnings))
        self.assertTrue(any("Must NOT be presented as settled fact" in w for w in pkg.uncertainty_warnings))

        # Test Forward Contradiction Propagation on Package
        affected = ScriptReadyCompiler.propagate_forward_contradiction(
            package=pkg,
            graph=self.graph,
            invalidated_claim_id="clm_visual_friction",
            reason="Laboratory replication study failed.",
        )
        self.assertTrue(pkg.is_falsified)
        self.assertTrue(len(pkg.falsification_notes) > 0)
        self.assertIn("clm_graphic_novel_bridge", affected)


if __name__ == "__main__":
    unittest.main()
