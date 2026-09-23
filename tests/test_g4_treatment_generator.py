"""
tests/test_g4_treatment_generator.py
Adversarial Verification for Gate G4: Dynamic Treatment Scoring & Heuristic Labeling.
"""

from __future__ import annotations
import unittest

from kageyoni.research_compiler.topic_modeler import TopicModel
from kageyoni.research_compiler.treatment_generator import (
    StoryArchetype,
    TreatmentGenerator,
)


class TestGateG4TreatmentGenerator(unittest.TestCase):

    def test_explicit_heuristic_labeling(self):
        """Verifies that all treatments carry explicit heuristic markers."""
        topic = TopicModel(
            topic_id="top_01",
            subject_title="Peer Competitive Library Benchmarks",
            core_state_of_affairs="Benchmarking Canadian urban public libraries across 2024 metrics",
        )
        treatments = TreatmentGenerator.evaluate_all_archetypes(
            topic=topic,
            audience_need="Executive strategic insights",
            communication_objective="Board presentation",
        )
        self.assertEqual(len(treatments), 9)
        for t in treatments:
            self.assertTrue(t.is_heuristic)
            self.assertIn("heuristic", t.heuristic_warrant.lower())
            self.assertIn("Peer Competitive Library Benchmarks", t.hypothesis)

    def test_dynamic_generation_differs_by_topic_content(self):
        """Proves that hypotheses and scores change dynamically with topic inputs rather than being hardcoded."""
        topic_a = TopicModel(
            topic_id="top_library",
            subject_title="Public Library AI Search Architecture",
            core_state_of_affairs="Implementation of semantic search for regional patrons",
            active_tensions=[{"description": "Privacy preservation vs personalized recommendation"}],
            chronology_and_causality=[{"step": 1, "action": "Ingest catalogue"}, {"step": 2, "action": "Vectorize"}],
        )
        topic_b = TopicModel(
            topic_id="top_municipal",
            subject_title="Municipal Transit Budget Deficits",
            core_state_of_affairs="Operational shortfalls in urban rail transit",
            contradictions=[{"gap": "Projected ridership vs actual post-pandemic volume"}],
            stakeholders_and_perspectives=[{"name": "Commuters"}, {"name": "Transit Authority"}],
        )

        treatments_a = TreatmentGenerator.evaluate_all_archetypes(
            topic=topic_a,
            audience_need="Technical implementation clarity",
            communication_objective="Engineering roadmapping",
        )
        treatments_b = TreatmentGenerator.evaluate_all_archetypes(
            topic=topic_b,
            audience_need="Accountability and financial transparency",
            communication_objective="Public consultation",
        )

        hypotheses_a = {t.archetype: t.hypothesis for t in treatments_a}
        hypotheses_b = {t.archetype: t.hypothesis for t in treatments_b}

        # Hypotheses must differ and mention respective topics
        for arch in StoryArchetype:
            self.assertNotEqual(hypotheses_a[arch], hypotheses_b[arch])
            self.assertIn("Public Library AI Search Architecture", hypotheses_a[arch])
            self.assertIn("Municipal Transit Budget Deficits", hypotheses_b[arch])

    def test_ranking_responds_to_topic_characteristics(self):
        """Topic with high tensions elevates tension-revelation or investigative over process-oriented."""
        topic_high_tension = TopicModel(
            topic_id="top_tension",
            subject_title="Whistleblower Audit Scandal",
            core_state_of_affairs="Severe discrepancy between audited books and secret bank accounts",
            active_tensions=[{"description": "Declared surplus vs offshore deficit"}],
            contradictions=[{"audit_mismatch": "Auditor signed off while treasury was emptied"}],
        )

        treatments = TreatmentGenerator.evaluate_all_archetypes(
            topic=topic_high_tension,
            audience_need="Investigative truth",
            communication_objective="Expose corruption",
        )

        # Top 3 treatments should include TENSION_REVELATION or INVESTIGATIVE
        top_3_archetypes = [t.archetype for t in treatments[:3]]
        self.assertTrue(
            StoryArchetype.TENSION_REVELATION in top_3_archetypes or StoryArchetype.INVESTIGATIVE in top_3_archetypes,
            f"Expected TENSION_REVELATION or INVESTIGATIVE in top 3, got: {top_3_archetypes}"
        )


if __name__ == "__main__":
    unittest.main()
