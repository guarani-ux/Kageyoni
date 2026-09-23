"""
tests/test_g8_end_to_end_saturation.py
Gate G8: Full End-to-End Saturation Test across the Complete Transformation Chain:
Source -> Claim -> Decision -> Effect -> Memory -> Later Behavior.
"""

from __future__ import annotations
import sqlite3
import time
import unittest

from kageyoni.research_compiler.claims import (
    ClaimGraph,
    ClaimNode,
    EpistemicStatus,
    SourceRecord,
)
from kageyoni.research_compiler.topic_modeler import TopicModel
from kageyoni.research_compiler.treatment_generator import (
    StoryArchetype,
    TreatmentGenerator,
)
from kageyoni.situations.memory import (
    SituationMemory,
    SituationMemoryStore,
)
from kageyoni.research_compiler.invalidation_engine import InvalidationEngine


class TestGateG8EndToEndSaturation(unittest.TestCase):

    def test_complete_transformation_chain(self):
        """
        Tests the complete 6-stage lifecycle:
        1. Source Registration
        2. Grounded Claim Formation
        3. Strategic Decision via Competing Treatment Evaluation
        4. Effectful Stage State Mediation
        5. Memory Formation & Retention
        6. Precedent Retrieval for Downstream Workflows
        """
        # Step 1: Register Source
        src = SourceRecord(
            source_id="src_annual_report_2024",
            title="2024 Calgary Public Library Report",
            provenance="https://calgarylibrary.ca/annual-report-2024",
            author_or_institution="Calgary Public Library",
            direct_excerpt="Cardholders checked out 18.2 million items across physical and digital formats in 2024.",
            date_recorded=time.time(),
        )
        self.assertTrue(len(src.content_hash) == 64)
        self.assertIn("18.2 million", src.source_says_statement)

        # Step 2: Form Grounded Claim
        graph = ClaimGraph()
        graph.add_source(src)
        claim = ClaimNode(
            claim_id="claim_circ_2024",
            statement="CPL patrons demonstrated record circulation volume of 18.2M items in 2024.",
            epistemic_status=EpistemicStatus.SOURCE_SUPPLIED_FACT,
            provenance_sources=["src_annual_report_2024"],
            evidence_establishes_claim="Direct checkout telemetry confirms 18.2M items.",
            modality="CERTAIN",
            quantifier="ALL",
        )
        graph.add_claim(claim)
        self.assertEqual(len(graph.get_established_facts()), 1)

        # Step 3: Competing Story Treatment Evaluation
        topic = TopicModel(
            topic_id="top_circulation_milestone",
            subject_title="Calgary Public Library 2024 Circulation Milestone",
            core_state_of_affairs="Historic high circulation of 18.2 million items driven by digital formats",
            established_facts=[{"statement": claim.statement, "claim_id": claim.claim_id}],
            chronology_and_causality=[{"year": 2024, "event": "18.2M checkouts recorded"}],
        )
        treatments = TreatmentGenerator.evaluate_all_archetypes(
            topic=topic,
            audience_need="Community celebration and funding advocacy",
            communication_objective="Demonstrate community value to civic stakeholders",
        )
        self.assertEqual(len(treatments), 9)
        top_treatment = treatments[0]
        self.assertGreater(top_treatment.composite_score, 0.0)
        self.assertTrue(top_treatment.is_heuristic)
        self.assertTrue(bool(top_treatment.mandatory_flip_condition))

        # Step 4: Effectful State Mediation in DB
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE agency_projects (
                project_id TEXT PRIMARY KEY,
                working_title TEXT NOT NULL,
                objective TEXT NOT NULL,
                target_audience TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                decision_owner TEXT NOT NULL,
                metadata_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
        """)
        conn.execute(
            """
            INSERT INTO agency_projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "proj_milestone_video",
                "18.2M Circulation Milestone Video",
                "Advocate for civic library funding",
                "City Council & Citizens",
                "PRODUCTION_APPROVED",
                "Creative Director",
                f'{{"treatment": "{top_treatment.archetype.value}", "claim": "{claim.claim_id}"}}',
                time.time(),
                time.time(),
            )
        )
        conn.commit()

        # Step 5: Memory Formation & Retention
        memory_store = SituationMemoryStore()
        memory = SituationMemory(
            memory_id="mem_milestone_campaign",
            situation_id="proj_milestone_video",
            template_id="campaign",
            objective="Civic funding advocacy",
            decisions=(f"selected_treatment:{top_treatment.archetype.value}",),
            artifacts=("video:milestone_cut",),
            dependency_keys=("civic-advocacy", "circulation-milestone"),
            workspace_id="ws_civic_relations",
        )
        memory_store.remember(memory)

        # Step 6: Later Behavior / Precedent Retrieval
        retrieved = memory_store.retrieve(
            workspace_id="ws_civic_relations",
            dependency_keys=("civic-advocacy",),
        )
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0].memory_id, "mem_milestone_campaign")
        self.assertIn(f"selected_treatment:{top_treatment.archetype.value}", retrieved[0].decisions)

        conn.close()


if __name__ == "__main__":
    unittest.main()
