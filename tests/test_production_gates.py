"""
Unit tests for Production Decision Gates Engine (YouTube SOP Protocol).
"""

import unittest
from contracts.production_gates import ProductionGatekeeper, GateStatus


class TestProductionGates(unittest.TestCase):

    def setUp(self):
        self.valid_scope = {
            "decision_owner": "Elijah Flowers-Nelson",
            "objective": "Increase Grade 3-6 literacy program attendance by 25% across 5 library branches.",
            "target_audience": "Grade 3-6 students and their parents in Calgary urban communities.",
            "deliverables": ["60s YouTube Short", "3m Long-Form Explainer", "Thumbnail Set"],
            "schedule": "Q4 Fall Campaign, publish window October 15-20",
            "approval_authority": "Director of Community Engagement & Media Production Specialist",
        }

        self.valid_creative = {
            "content_promise": "Reveals the 3 hidden tools inside Calgary Public Library that make reading effortless for struggling students.",
            "narrative_engine": "Challenge/Transformation journey following a student unable to find grade-level books.",
            "core_message": "Library cards unlock personalized reading coaches and specialized graphic novel collections.",
            "packaging_hypotheses": [
                {"title": "The Secret Library Trick Every 4th Grader Needs", "thumbnail": "Focal close-up of struggling student holding mystery book"},
                {"title": "How Calgary Kids Are Reading 2x Faster", "thumbnail": "Before/After reading score comparison graphic"}
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

        self.valid_content_lock = {
            "factual_approval_complete": True,
            "narrative_changes_closed": True,
            "required_disclosures_present": True,
            "graphics_and_data_verified": True,
            "rights_status_documented": True,
        }

        self.valid_qc_manifest = {
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

    def test_scope_gate_passes_valid(self):
        result = ProductionGatekeeper.evaluate_scope_gate(self.valid_scope)
        self.assertTrue(result.passed)
        self.assertEqual(result.status, GateStatus.PASSED)
        self.assertEqual(len(result.blockers), 0)

    def test_scope_gate_blocks_vague_objective(self):
        invalid_scope = dict(self.valid_scope)
        invalid_scope["objective"] = "Make it engaging and go viral on TikTok"
        result = ProductionGatekeeper.evaluate_scope_gate(invalid_scope)
        self.assertFalse(result.passed)
        self.assertEqual(result.status, GateStatus.BLOCKED)
        self.assertTrue(any("SCOPE_AMBIGUITY" in b for b in result.blockers))

    def test_scope_gate_blocks_missing_fields(self):
        incomplete = {"decision_owner": "Elijah"}
        result = ProductionGatekeeper.evaluate_scope_gate(incomplete)
        self.assertFalse(result.passed)
        self.assertGreaterEqual(len(result.blockers), 4)

    def test_creative_gate_requires_two_packaging_hypotheses(self):
        invalid_creative = dict(self.valid_creative)
        invalid_creative["packaging_hypotheses"] = [{"title": "Only One Title"}]
        result = ProductionGatekeeper.evaluate_strategy_creative_gate(invalid_creative)
        self.assertFalse(result.passed)
        self.assertTrue(any("PACKAGING_DEFICIT" in b for b in result.blockers))

    def test_shoot_readiness_blocks_unplanned_thumbnail(self):
        invalid_shoot = dict(self.valid_shoot)
        invalid_shoot["thumbnail_capture_planned"] = False
        result = ProductionGatekeeper.evaluate_shoot_readiness_gate(invalid_shoot)
        self.assertFalse(result.passed)
        self.assertTrue(any("Thumbnail stills must be deliberately scheduled" in b for b in result.blockers))

    def test_content_lock_blocks_open_narrative(self):
        invalid_lock = dict(self.valid_content_lock)
        invalid_lock["narrative_changes_closed"] = False
        result = ProductionGatekeeper.evaluate_content_lock_gate(invalid_lock)
        self.assertFalse(result.passed)
        self.assertTrue(any("narrative changes remain" in b for b in result.blockers))

    def test_publish_readiness_all_green_passes(self):
        result = ProductionGatekeeper.evaluate_publish_readiness_gate(self.valid_qc_manifest)
        self.assertTrue(result.passed)
        self.assertEqual(result.status, GateStatus.PASSED)
        self.assertEqual(result.metadata["qc_classes_passed"], 5)

    def test_publish_readiness_fails_on_uncleared_music(self):
        manifest = dict(self.valid_qc_manifest)
        manifest["rights_compliance_qc"] = dict(manifest["rights_compliance_qc"])
        manifest["rights_compliance_qc"]["music_cleared"] = False
        result = ProductionGatekeeper.evaluate_publish_readiness_gate(manifest)
        self.assertFalse(result.passed)
        self.assertTrue(any("RIGHTS_QC: Music synchronization" in b for b in result.blockers))

    def test_publish_readiness_fails_on_unflagged_ai(self):
        manifest = dict(self.valid_qc_manifest)
        manifest["rights_compliance_qc"] = dict(manifest["rights_compliance_qc"])
        manifest["rights_compliance_qc"]["has_realistic_ai_generation"] = True
        manifest["rights_compliance_qc"]["ai_disclosure_setting_enabled"] = False
        result = ProductionGatekeeper.evaluate_publish_readiness_gate(manifest)
        self.assertFalse(result.passed)
        self.assertTrue(any("Realistic AI-altered/generated media present but YouTube AI disclosure not enabled" in b for b in result.blockers))

    def test_publish_readiness_fails_on_unreviewed_captions(self):
        manifest = dict(self.valid_qc_manifest)
        manifest["accessibility_localization_qc"] = dict(manifest["accessibility_localization_qc"])
        manifest["accessibility_localization_qc"]["captions_human_reviewed"] = False
        result = ProductionGatekeeper.evaluate_publish_readiness_gate(manifest)
        self.assertFalse(result.passed)
        self.assertTrue(any("ACCESSIBILITY_QC: Captions must be human-reviewed" in b for b in result.blockers))

    def test_learning_gate_requires_reusable_lesson(self):
        report = {
            "cadence_interval": "+48h",
            "observed_data_separated_from_hypothesis": True,
            "retention_curve_analyzed": True,
            "reusable_lesson": "",
        }
        result = ProductionGatekeeper.evaluate_learning_gate(report)
        self.assertFalse(result.passed)
        self.assertTrue(any("LEARNING_DEFICIT" in b for b in result.blockers))

        report["reusable_lesson"] = "Grade 3-6 viewers drop by 40% when voiceover exceeds 15 seconds without on-screen visual proof."
        result_valid = ProductionGatekeeper.evaluate_learning_gate(report)
        self.assertTrue(result_valid.passed)


if __name__ == "__main__":
    unittest.main()
