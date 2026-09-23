"""
Production Decision Gates Engine (YouTube Media Communications Strategist Protocol)

Implements the 5 pre-publication decision gates, 5 QC classes, and 1 post-publication
learning gate defined in the YouTube Media Communications Strategist SOP.
Fail-closed: Any missing requirement or unverified claim halts the pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class GateStatus(Enum):
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    REVISE = "REVISE"


@dataclass
class GateResult:
    gate_name: str
    status: GateStatus
    passed: bool
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "passed": self.passed,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }


class ProductionGatekeeper:
    """
    Enforces gate verification across the 5 production gates and 5 QC classes.
    """

    @staticmethod
    def evaluate_scope_gate(data: Dict[str, Any]) -> GateResult:
        """
        Gate 1: Scope Authorization Gate
        Required fields:
        - decision_owner / sponsor
        - objective (communication or business outcome)
        - target_audience
        - deliverables
        - schedule / target_publish_window
        - approval_authority
        """
        blockers = []
        required_fields = [
            ("decision_owner", "Accountable sponsor/decision owner must be explicitly named."),
            ("objective", "Objective must state an observable communication or business outcome."),
            ("target_audience", "Target audience must be defined with known context and problem."),
            ("deliverables", "Deliverables list cannot be empty."),
            ("schedule", "Target publish window or timeline must be specified."),
            ("approval_authority", "Approval authority structure must be documented."),
        ]

        for field_name, err_msg in required_fields:
            val = data.get(field_name)
            if not val or (isinstance(val, (list, dict, str)) and len(val) == 0):
                blockers.append(f"SCOPE_DEFICIT: {err_msg}")

        # Check for vague objective anti-pattern
        obj = str(data.get("objective", "")).lower()
        if obj and any(phrase in obj for phrase in ["make it engaging", "go viral", "build hype"]):
            blockers.append("SCOPE_AMBIGUITY: Objective must specify observable outcome, not vague sentiment.")

        passed = len(blockers) == 0
        return GateResult(
            gate_name="Gate 1: Scope Authorization Gate",
            status=GateStatus.PASSED if passed else GateStatus.BLOCKED,
            passed=passed,
            blockers=blockers,
            metadata={"decision_owner": data.get("decision_owner")},
        )

    @staticmethod
    def evaluate_strategy_creative_gate(data: Dict[str, Any]) -> GateResult:
        """
        Gate 2: Strategy + Creative Gate
        Required:
        - content_promise: Explicit contract made with viewer
        - narrative_engine: Defined storytelling vehicle
        - core_message: The one proposition retained
        - packaging_hypotheses: At least 2 materially different Title + Thumbnail concepts
        - evidence_or_access_confirmed: Boolean
        - risk_acceptable: Boolean
        """
        blockers = []

        if not data.get("content_promise"):
            blockers.append("CREATIVE_DEFICIT: Content promise (what the click commits to delivering) is required.")
        if not data.get("narrative_engine"):
            blockers.append("CREATIVE_DEFICIT: Narrative engine (question/transformation/demonstration) is required.")
        if not data.get("core_message"):
            blockers.append("CREATIVE_DEFICIT: Core proposition is required.")

        packaging = data.get("packaging_hypotheses", [])
        if not isinstance(packaging, list) or len(packaging) < 2:
            blockers.append("PACKAGING_DEFICIT: Must propose at least 2 distinct Title/Thumbnail concepts (testing propositions, not just fonts).")

        if not data.get("evidence_or_access_confirmed", False):
            blockers.append("EVIDENCE_DEFICIT: Access to factual evidence or interview subjects not confirmed.")

        if not data.get("risk_acceptable", False):
            blockers.append("RISK_DEFICIT: Creative risk and proportionality have not been reviewed and accepted.")

        passed = len(blockers) == 0
        return GateResult(
            gate_name="Gate 2: Strategy + Creative Gate",
            status=GateStatus.PASSED if passed else GateStatus.BLOCKED,
            passed=passed,
            blockers=blockers,
            metadata={"packaging_variants_count": len(packaging) if isinstance(packaging, list) else 0},
        )

    @staticmethod
    def evaluate_shoot_readiness_gate(data: Dict[str, Any]) -> GateResult:
        """
        Gate 3: Shoot-Readiness Gate
        Required:
        - script_approved: Boolean
        - factual_claims_checked: Boolean
        - talent_and_locations_confirmed: Boolean
        - equipment_and_crew_confirmed: Boolean
        - rights_strategy_viable: Boolean (music, footage, releases)
        - thumbnail_capture_planned: Boolean (capturing stills during shoot)
        - media_backup_capacity_confirmed: Boolean
        """
        blockers = []
        checks = [
            ("script_approved", "Script/run-of-show must be formally approved."),
            ("factual_claims_checked", "All factual claims and statistics in script must be verified."),
            ("talent_and_locations_confirmed", "Talent, locations, and call sheets must be confirmed."),
            ("equipment_and_crew_confirmed", "Crew, camera, audio, and lighting gear must be confirmed."),
            ("rights_strategy_viable", "Releases and third-party rights strategy must be viable prior to shoot."),
            ("thumbnail_capture_planned", "Thumbnail stills must be deliberately scheduled into shot list."),
            ("media_backup_capacity_confirmed", "Secure on-site/off-site media backup storage confirmed."),
        ]

        for check_key, err_msg in checks:
            if not data.get(check_key, False):
                blockers.append(f"SHOOT_READINESS_DEFICIT: {err_msg}")

        passed = len(blockers) == 0
        return GateResult(
            gate_name="Gate 3: Shoot-Readiness Gate",
            status=GateStatus.PASSED if passed else GateStatus.BLOCKED,
            passed=passed,
            blockers=blockers,
        )

    @staticmethod
    def evaluate_content_lock_gate(data: Dict[str, Any]) -> GateResult:
        """
        Gate 4: Content-Lock Gate
        Required:
        - factual_approval_complete: Boolean
        - narrative_changes_closed: Boolean (no further story/structural edits)
        - required_disclosures_present: Boolean (sponsor, commercial, AI)
        - graphics_and_data_verified: Boolean
        - rights_status_documented: Boolean
        """
        blockers = []
        checks = [
            ("factual_approval_complete", "Factual/content accuracy sign-off complete."),
            ("narrative_changes_closed", "Stakeholders agree no substantive narrative changes remain."),
            ("required_disclosures_present", "All statutory and platform disclosures embedded in edit or planned."),
            ("graphics_and_data_verified", "All on-screen charts, figures, and names verified."),
            ("rights_status_documented", "Rights provenance documented in rights register."),
        ]

        for check_key, err_msg in checks:
            if not data.get(check_key, False):
                blockers.append(f"CONTENT_LOCK_DEFICIT: {err_msg}")

        passed = len(blockers) == 0
        return GateResult(
            gate_name="Gate 4: Content-Lock Gate",
            status=GateStatus.PASSED if passed else GateStatus.BLOCKED,
            passed=passed,
            blockers=blockers,
        )

    @staticmethod
    def evaluate_publish_readiness_gate(qc_manifest: Dict[str, Any]) -> GateResult:
        """
        Gate 5: Publish-Readiness Gate (The 5 QC Classes)
        All 5 classes must be 100% green.
        """
        blockers = []
        warnings = []

        # Class 1: Editorial QC
        editorial = qc_manifest.get("editorial_qc", {})
        if not editorial.get("promise_fulfilled", False):
            blockers.append("EDITORIAL_QC: Content fails to fulfill the promise established in title/thumbnail.")
        if not editorial.get("facts_names_numbers_verified", False):
            blockers.append("EDITORIAL_QC: Names, numbers, or facts have not passed final verification.")
        if editorial.get("outdated_placeholders_present", False):
            blockers.append("EDITORIAL_QC: Temp graphics, filler text, or placeholder cuts detected in master.")
        if not editorial.get("opening_and_cta_intentional", False):
            blockers.append("EDITORIAL_QC: Opening pacing or CTA alignment not verified.")

        # Class 2: Technical QC
        technical = qc_manifest.get("technical_qc", {})
        if not technical.get("correct_master_export", False):
            blockers.append("TECHNICAL_QC: Master export verification failed.")
        if not technical.get("av_synchrony_verified", False):
            blockers.append("TECHNICAL_QC: Audio/video synchronization issue detected.")
        if not technical.get("no_audio_clipping", False):
            blockers.append("TECHNICAL_QC: Audio clipping or dropouts detected.")
        loudness = technical.get("integrated_loudness_lufs")
        if loudness is not None and (loudness > -13.0 or loudness < -15.0):
            warnings.append(f"TECHNICAL_LOUDNESS_WARNING: Audio measured at {loudness} LUFS (YouTube standard is -14 LUFS +/- 1 LUFS).")
        if not technical.get("mobile_legibility_verified", False):
            blockers.append("TECHNICAL_QC: On-screen graphics or lower-thirds illegible at mobile screen size.")

        # Class 3: Rights & Compliance QC (Canadian Law & YouTube Policy)
        rights = qc_manifest.get("rights_compliance_qc", {})
        if not rights.get("music_cleared", False):
            blockers.append("RIGHTS_QC: Music synchronization clearance missing (CMRRA publisher or verified safe library).")
        if not rights.get("third_party_media_cleared", False):
            blockers.append("RIGHTS_QC: Third-party footage/images lack documented licence or fair dealing review.")
        if not rights.get("talent_releases_signed", False):
            blockers.append("RIGHTS_QC: Talent or minor releases missing under Alberta PIPA / federal PIPEDA.")
        if rights.get("has_paid_promotion") and not rights.get("paid_promotion_setting_enabled"):
            blockers.append("COMPLIANCE_QC: Branded content present but YouTube paid-promotion setting not enabled.")
        if rights.get("has_realistic_ai_generation") and not rights.get("ai_disclosure_setting_enabled"):
            blockers.append("COMPLIANCE_QC: Realistic AI-altered/generated media present but YouTube AI disclosure not enabled.")

        # Class 4: Accessibility & Localization QC
        access = qc_manifest.get("accessibility_localization_qc", {})
        if not access.get("captions_human_reviewed", False):
            blockers.append("ACCESSIBILITY_QC: Captions must be human-reviewed authored text (auto-captions alone fail QC).")
        if not access.get("video_language_set", False):
            blockers.append("ACCESSIBILITY_QC: Video primary language must be explicitly set.")
        if not access.get("meaningful_non_speech_audio_represented", False):
            blockers.append("ACCESSIBILITY_QC: Significant non-speech audio cues missing in caption tracks (WCAG Level A/AA).")

        # Class 5: Platform & Packaging QC
        platform = qc_manifest.get("platform_packaging_qc", {})
        if not platform.get("title_thumbnail_system_aligned", False):
            blockers.append("PLATFORM_QC: Title and thumbnail must be reviewed as an integrated system.")
        if not platform.get("description_viewer_language_aligned", False):
            blockers.append("PLATFORM_QC: Description must use natural viewer language, not keyword stuffing.")
        if not platform.get("chapters_formatted_correctly", False):
            blockers.append("PLATFORM_QC: Chapters format invalid (must start at 00:00 with at least 3 timestamps).")
        if not platform.get("links_tested", False):
            blockers.append("PLATFORM_QC: Description links have not been verified.")
        if not platform.get("endscreen_space_reserved", False):
            blockers.append("PLATFORM_QC: End-screen cards occlude vital visual information.")

        passed = len(blockers) == 0
        return GateResult(
            gate_name="Gate 5: Publish-Readiness Gate (5 QC Classes)",
            status=GateStatus.PASSED if passed else GateStatus.BLOCKED,
            passed=passed,
            blockers=blockers,
            warnings=warnings,
            metadata={
                "qc_classes_passed": 5 - (1 if any(b.startswith("EDITORIAL") for b in blockers) else 0)
                                      - (1 if any(b.startswith("TECHNICAL") for b in blockers) else 0)
                                      - (1 if any(b.startswith("RIGHTS") or b.startswith("COMPLIANCE") for b in blockers) else 0)
                                      - (1 if any(b.startswith("ACCESSIBILITY") for b in blockers) else 0)
                                      - (1 if any(b.startswith("PLATFORM") for b in blockers) else 0)
            },
        )

    @staticmethod
    def evaluate_learning_gate(report: Dict[str, Any]) -> GateResult:
        """
        Gate 6: Post-Publication Learning Gate
        Required:
        - cadence_interval: immediate, 24h, 48h, 7d, 28d
        - observed_data_separated_from_hypothesis: Boolean
        - retention_curve_analyzed: Boolean (first 30s, dips, spikes)
        - reusable_lesson_documented: String (one sentence altering future work)
        """
        blockers = []
        if not report.get("cadence_interval"):
            blockers.append("LEARNING_DEFICIT: Cadence interval must be specified (+24h, +48h, +7d, +28d).")
        if not report.get("observed_data_separated_from_hypothesis", False):
            blockers.append("LEARNING_DEFICIT: Observed measurement must be separated from causal interpretation.")
        if not report.get("retention_curve_analyzed", False):
            blockers.append("LEARNING_DEFICIT: Retention diagnostics (intro, dips, spikes) must be analyzed.")
        lesson = report.get("reusable_lesson")
        if not lesson or len(str(lesson).strip()) < 10:
            blockers.append("LEARNING_DEFICIT: Must document at least one reusable lesson that alters future decisions.")

        passed = len(blockers) == 0
        return GateResult(
            gate_name="Gate 6: Post-Publication Learning Gate",
            status=GateStatus.PASSED if passed else GateStatus.BLOCKED,
            passed=passed,
            blockers=blockers,
            metadata={"reusable_lesson": report.get("reusable_lesson")},
        )
