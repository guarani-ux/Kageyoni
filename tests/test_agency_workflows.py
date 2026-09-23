"""
Unit tests for AgencyWorkflows (Sovereign Media Engine Host Workflows).
"""

import tempfile
import time
import unittest
from pathlib import Path

from kageyoni.engine import Engine
from kageyoni.workflows import Workflows
from contracts.production_gates import GateStatus
from kageyoni.research_compiler.claims import SourceRecord, ClaimNode, EpistemicStatus
from kageyoni.research_compiler.package_compiler import AudienceModel


class TestAgencyWorkflows(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_agency.sqlite"
        self.engine = Engine(self.db_path)
        self.workflows = Workflows(self.engine)

        self.valid_brief = {
            "project_id": "cpl_literacy_2026",
            "working_title": "Grade 3-6 Literacy Outreach Campaign",
            "decision_owner": "Elijah Flowers-Nelson",
            "objective": "Increase Grade 3-6 literacy program attendance by 25% across 5 library branches.",
            "target_audience": "Grade 3-6 students and parents in Calgary communities.",
            "deliverables": ["60s YouTube Short", "3m Long-Form Explainer", "Thumbnail Set"],
            "schedule": "Q4 Fall Campaign, publish window October 15-20",
            "approval_authority": "Director of Community Engagement & Media Production Specialist",
        }

        self.valid_creative = {
            "content_promise": "Reveals the 3 hidden tools inside Calgary Public Library that make reading effortless.",
            "narrative_engine": "Challenge/Transformation journey following a student finding grade-level books.",
            "core_message": "Library cards unlock personalized reading coaches and specialized graphic novel collections.",
            "packaging_hypotheses": [
                {"title": "The Secret Library Trick Every 4th Grader Needs", "thumbnail": "Focal student close-up"},
                {"title": "How Calgary Kids Are Reading 2x Faster", "thumbnail": "Before/After graphic"}
            ],
            "evidence_or_access_confirmed": True,
            "risk_acceptable": True,
        }

        self.valid_shoot = {
            "script_approved": True,
            "factual_claims_checked": True,
            "talent_and_locations_confirmed": True,
            "equipment_and_crew_confirmed": True,
            "rights_strategy_viable": True,
            "thumbnail_capture_planned": True,
            "media_backup_capacity_confirmed": True,
        }

        self.valid_lock = {
            "factual_approval_complete": True,
            "narrative_changes_closed": True,
            "required_disclosures_present": True,
            "graphics_and_data_verified": True,
            "rights_status_documented": True,
        }

        self.valid_qc = {
            "editorial_qc": {
                "promise_fulfilled": True,
                "facts_names_numbers_verified": True,
                "outdated_placeholders_present": False,
                "opening_and_cta_intentional": True,
            },
            "technical_qc": {
                "correct_master_export": True,
                "av_synchrony_verified": True,
                "no_audio_clipping": True,
                "integrated_loudness_lufs": -14.0,
                "mobile_legibility_verified": True,
            },
            "rights_compliance_qc": {
                "music_cleared": True,
                "third_party_media_cleared": True,
                "talent_releases_signed": True,
                "has_paid_promotion": False,
                "paid_promotion_setting_enabled": False,
                "has_realistic_ai_generation": False,
                "ai_disclosure_setting_enabled": False,
            },
            "accessibility_localization_qc": {
                "captions_human_reviewed": True,
                "video_language_set": True,
                "meaningful_non_speech_audio_represented": True,
            },
            "platform_packaging_qc": {
                "title_thumbnail_system_aligned": True,
                "description_viewer_language_aligned": True,
                "chapters_formatted_correctly": True,
                "links_tested": True,
                "endscreen_space_reserved": True,
            },
        }

    def tearDown(self):
        self.engine.close()
        self.temp_dir.cleanup()

    def test_workflow_competitive_analysis(self):
        report = self.workflows.agency.run_competitive_analysis(
            target_name="Calgary Public Library",
            peer_names=["Toronto Public Library", "Edmonton Public Library", "Vancouver Public Library"],
            focus_area="YouTube & Digital Strategy",
        )
        self.assertIn("analysis_id", report)
        self.assertEqual(report["target"], "Calgary Public Library")
        self.assertIn("Calgary Public Library", report["telemetry"])
        self.assertIn("TPL", report["rhetorical_audit"])
        self.assertEqual(report["tribunal"]["final_verdict"], "APPROVED WITH CONDITIONS")

        # Verify durable SQLite persistence
        row = self.engine.db.execute("SELECT * FROM agency_competitive_analyses WHERE analysis_id=?", (report["analysis_id"],)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["target_name"], "Calgary Public Library")

    def test_workflow_5_gate_video_production_lifecycle(self):
        agency = self.workflows.agency

        # Gate 1: Scope
        p1 = agency.start_video_production(self.valid_brief)
        self.assertEqual(p1["stage"], "SCOPED")
        self.assertTrue(p1["gate_result"]["passed"])

        # Gate 2: Creative
        p2 = agency.advance_creative_gate(p1["project_id"], self.valid_creative)
        self.assertEqual(p2["stage"], "CREATIVE_APPROVED")
        self.assertTrue(p2["gate_result"]["passed"])

        # Gate 3: Shoot
        p3 = agency.advance_shoot_gate(p1["project_id"], self.valid_shoot)
        self.assertEqual(p3["stage"], "SHOOT_LOCKED")
        self.assertTrue(p3["gate_result"]["passed"])

        # Gate 4: Content Lock
        p4 = agency.advance_content_lock_gate(p1["project_id"], self.valid_lock)
        self.assertEqual(p4["stage"], "CONTENT_LOCKED")
        self.assertTrue(p4["gate_result"]["passed"])

        # Gate 5: Publish Readiness
        p5 = agency.audit_publish_readiness(p1["project_id"], self.valid_qc)
        self.assertEqual(p5["stage"], "PUBLISH_ELIGIBLE")
        self.assertTrue(p5["gate_result"]["passed"])

        # Verify all gates were recorded in database
        gates = self.engine.db.execute("SELECT gate_name, status, passed FROM agency_gate_records WHERE project_id=?", (p1["project_id"],)).fetchall()
        self.assertEqual(len(gates), 5)
        for g in gates:
            self.assertEqual(g["passed"], 1)

    def test_workflow_fails_closed_on_vague_objective(self):
        bad_brief = dict(self.valid_brief)
        bad_brief["objective"] = "Make it engaging and go viral"
        res = self.workflows.agency.start_video_production(bad_brief)
        self.assertEqual(res["stage"], "INTAKE_BLOCKED")
        self.assertFalse(res["gate_result"]["passed"])

    def test_workflow_video_deconstruction(self):
        self.workflows.agency.start_video_production(self.valid_brief)
        sections = [
            {
                "timecode_in": "00:00:00",
                "timecode_out": "00:00:12",
                "structural_job": "HOOK",
                "spoken_audio": "Did you know your library card gives you free access to a full music recording studio?",
                "visual_proof": "Host plugs XLR microphone into audio console inside Calgary Public Library studio.",
            },
            {
                "timecode_in": "00:00:12",
                "timecode_out": "00:00:45",
                "structural_job": "DEMONSTRATION",
                "spoken_audio": "For over thirty minutes we walked through the entire collection of equipment explaining every possible nuance of how audio engineering works for all kinds of community members across the city without showing what they actually do with it.",
                "visual_proof": "Generic b-roll of empty library hallway and static shelves.",
            }
        ]

        res = self.workflows.agency.deconstruct_video("cpl_literacy_2026", sections)
        self.assertEqual(res["sections_deconstructed"], 2)
        # Second section must trigger the retention dip hazard!
        self.assertEqual(res["hazards_identified"], 1)

        rows = self.engine.db.execute("SELECT * FROM agency_section_records WHERE project_id=?", ("cpl_literacy_2026",)).fetchall()
        self.assertEqual(len(rows), 2)

    def test_compile_research_package_workflow(self):
        src = SourceRecord(
            source_id="src_test",
            title="Test Source",
            provenance="Audited Log",
            author_or_institution="CPL",
            direct_excerpt="26,600 student participants.",
            date_recorded=time.time(),
            reliability_tier="PRIMARY_CORROBORATED",
        )
        clm1 = ClaimNode(
            claim_id="clm_reach",
            statement="CPL reached 26,600 students.",
            epistemic_status=EpistemicStatus.SOURCE_FACT,
            provenance_sources=["src_test"],
            confidence_level="HIGH",
            falsification_condition="Audit records show <20k",
        )
        clm2 = ClaimNode(
            claim_id="clm_synth",
            statement="Synthesized outcome from reach.",
            epistemic_status=EpistemicStatus.SYNTHESIS,
            provenance_sources=["src_test"],
            confidence_level="HIGH",
            parent_claim_ids=["clm_reach"],
            falsification_condition="Zero retention impact",
        )
        audience = AudienceModel(
            target_segment="Parents of Grade 3-6 students",
            prior_knowledge_baseline="Believe library is only books",
            active_misconceptions=["'No tech programs exist'"],
            practical_and_emotional_stakes="Child literacy success",
            reception_friction="Lack of time",
        )
        comm_problem = {
            "current_state": "Parents do not know about modern services",
            "desired_shift": "Register for library programs",
            "decision_to_enable": "Program attendance",
        }
        story_territory = {
            "core_frictions": ["Perception of obsolescence"],
            "transformations": ["Skeptical parent to active library visitor"],
            "human_stakes": ["Reading confidence"],
            "potential_scenes_and_locales": ["Central Library Teen Lab"],
        }
        narrative_ingredients = {
            "essential_facts": ["26,600 students reached", "Free access"],
            "compulsory_scenes_or_proofs": ["Tour of creative studio"],
            "voices_and_perspectives": ["Library staff"],
            "visual_metaphors": ["Keys unlocking creative doors"],
            "unanswered_dramatic_questions": ["Will the student find the right book?"],
        }
        constraints = {
            "must_not_claim": ["Guaranteed A+ grades"],
            "must_not_omit": ["Free card requirement"],
            "ethical_and_privacy_boundaries": ["Minor privacy"],
        }
        open_questions = {
            "research_gaps": ["Branch-specific attendance distribution"],
            "field_discovery_requirements": ["Confirm weekend staff capacity"],
        }

        # 1. Compile via host workflow
        pkg = self.workflows.agency.compile_research_package(
            subject_title="CPL Literacy Outreach",
            sources=[src],
            claims=[clm1, clm2],
            audience=audience,
            comm_problem=comm_problem,
            story_territory=story_territory,
            narrative_ingredients=narrative_ingredients,
            constraints=constraints,
            open_questions=open_questions,
            project_id=self.valid_brief["project_id"],
        )

        self.assertIsNotNone(pkg.package_id)
        self.assertEqual(pkg.subject_title, "CPL Literacy Outreach")
        self.assertEqual(len(pkg.competing_treatments), 9)

        # 2. Verify SQLite persistence via get_research_package
        persisted = self.workflows.agency.get_research_package(pkg.package_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["subject_title"], "CPL Literacy Outreach")
        self.assertEqual(persisted["project_id"], self.valid_brief["project_id"])
        self.assertIn("clm_reach", persisted["lineage_chains"])

        # 3. Verify forward contradiction propagation through host workflow
        inval_res = self.workflows.agency.invalidate_claim_in_package(
            package_id=pkg.package_id,
            invalidated_claim_id="clm_reach",
            reason="Physical audit logs reveal undercount",
        )
        self.assertTrue(inval_res["is_falsified"])
        self.assertIn("clm_reach", inval_res["affected_claims"])
        self.assertIn("clm_synth", inval_res["affected_claims"])

        # 4. Check DB update reflects falsification
        updated = self.workflows.agency.get_research_package(pkg.package_id)
        self.assertTrue(updated["is_falsified"])
        self.assertGreater(len(updated["falsification_notes"]), 0)


if __name__ == "__main__":
    unittest.main()
