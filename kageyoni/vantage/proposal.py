"""
Strategic Proposal & Treatment Generator for Vantage.
Distinguishes the Strategic Rationale (why the video should exist) from
the Audiovisual Execution (what viewers see and hear in the two-column treatment).
Enforces Gate 1 (Scope) and Gate 2 (Strategy + Creative) verification.
"""

from __future__ import annotations
import time
import uuid
from typing import Any, Dict, List, Optional

from contracts.production_gates import ProductionGatekeeper, GateStatus, GateResult
from .models import (
    ApprovalStatus,
    IdeaCandidate,
    ProjectBrief,
    StrategicProposal,
    TreatmentSection,
)


class ProposalGenerator:
    """
    Builds approval-ready proposals and strategy briefs from qualified ideas.
    """

    @classmethod
    def create_proposal(
        cls,
        idea: IdeaCandidate,
        brief: ProjectBrief,
        duration_seconds: int = 480,
    ) -> StrategicProposal:
        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"

        # 1. Strategic Rationale
        strategic_rationale = {
            "why_it_should_exist": (
                f"Addresses the critical gap where {brief.target_audience.get('segment')} lacks practical, "
                f"evidence-grounded clarity on {brief.target_audience.get('problem')}. "
                f"Establishes organizational credibility through direct demonstration rather than marketing assertion."
            ),
            "target_audience_served": (
                f"Primary: {idea.target_audience}. Focuses on those facing {brief.target_audience.get('problem')}, "
                f"moving them from uncertainty to informed confidence."
            ),
            "intended_effect": (
                "Viewers understand the real mechanical principles and organizational efficacy, "
                "increasing willingness to adopt recommended practices and partner with the organization."
            ),
            "relationship_to_org_goals": (
                f"Directly advances: {brief.organizational_goals[0] if brief.organizational_goals else 'Institutional Mission'} "
                f"and contributes to: {idea.organizational_contribution}."
            ),
            "stakeholder_requirements": [
                "Preserve scientific accuracy of all engineering and health data.",
                "Ensure local community and partner voices are accurately represented.",
                "Adhere to organizational brand identity and transparent donor accountability.",
            ] + brief.stakeholder_requests[:2],
            "distribution_approach": (
                "Primary long-form release on YouTube (16:9), supported by modular derivative 9:16 Shorts "
                "and an embedded release in the quarterly organizational briefing."
            ),
            "resources_required": {
                "production_tier": brief.available_resources.get("budget_tier", "MEDIUM"),
                "crew_size": 3,
                "days_of_shooting": 1,
                "post_production_timeline_days": 10,
            },
            "risks_and_mitigations": [
                {
                    "risk": "Technical jargon overwhelms non-specialist viewers.",
                    "mitigation": "Use physical analogies, on-screen motion diagrams, and plain-language SME framing.",
                },
                {
                    "risk": "On-location weather or noise disruptions during outdoor pump demonstration.",
                    "mitigation": "Dual lavalier + shotgun audio redundancy and backup indoor interview setup.",
                },
            ],
            "approvals_required": [
                brief.approval_authority,
                "Subject-Matter Specialist (Factual Accuracy)",
                "Executive Producer (Creative & Budget Lock)",
            ],
            "success_criteria": {
                "primary_retention_target": "50% retention at 50% duration (04:00)",
                "target_ctr": "6.0% - 8.5% within 72 hours of publication",
                "audience_engagement": "High proportion of qualitative comments indicating comprehension",
            },
        }

        # 2. Audiovisual Treatment (What viewers actually see and hear)
        sme_claims = [s.get("fact", "") for s in brief.subject_matter_notes]
        primary_fact = sme_claims[0] if sme_claims else "Field system operates continuously under stress"
        secondary_fact = sme_claims[1] if len(sme_claims) > 1 else "Eliminates recurrent maintenance failures"

        sections = [
            TreatmentSection(
                section_id="S01",
                timecode_range="00:00 - 00:25",
                structural_function="HOOK",
                audio_column=(
                    f"NAT SOUND: Mechanical hum and rushing water. "
                    f"HOST (VO): 'Most systems fail right here. But this community solved it without a diesel generator. Here is the physical proof.'"
                ),
                video_column=(
                    "Tight macro shot of the pump impeller spinning at speed; pull back to wide reveal of the solar array "
                    "in operation. Dynamic text overlay: '0 Gallons of Fuel. 100% Operational.'"
                ),
                claims_addressed=[primary_fact],
                retention_intent="Immediate visual contrast; delivers curiosity without clickbait deception.",
            ),
            TreatmentSection(
                section_id="S02",
                timecode_range="00:25 - 01:30",
                structural_function="ORIENTATION",
                audio_column=(
                    "HOST (On camera): Sets up the core challenge. "
                    "Explains why conventional approaches failed and introduces the field engineer."
                ),
                video_column=(
                    "Medium shot of host on location at the water distribution point. "
                    "B-roll cutaways of previous broken infrastructure and community members collecting water."
                ),
                claims_addressed=[],
                retention_intent="Grounds the problem in human stakes and clear geographical reality.",
            ),
            TreatmentSection(
                section_id="S03",
                timecode_range="01:30 - 04:30",
                structural_function="DEMONSTRATION",
                audio_column=(
                    f"SME (Interview): 'When solar irradiance fluctuates, ordinary pumps stall. "
                    f"Our variable-frequency drive matches the pump curve dynamically.' "
                    f"HOST: 'Let's see what that looks like in the telemetry.'"
                ),
                video_column=(
                    "Over-the-shoulder shot of the SME operating the control panel. "
                    "Animated split screen: physical water pressure gauge next to live telemetry readout."
                ),
                claims_addressed=[primary_fact, secondary_fact],
                retention_intent="Visual demonstration of cause-and-effect replaces abstract discussion.",
            ),
            TreatmentSection(
                section_id="S04",
                timecode_range="04:30 - 06:45",
                structural_function="PROOF",
                audio_column=(
                    "HOST (VO): 'Over twelve months of continuous operation across three seasons, "
                    "the data proved the model held up.' "
                    "COMMUNITY LEAD: Explains the reliability impact on the regional health clinic."
                ),
                video_column=(
                    "Clear, legible motion graphic chart comparing 12-month downtime. "
                    "Cut to live footage of the clinic running clean water taps without interruption."
                ),
                claims_addressed=sme_claims,
                retention_intent="Substantiates all claims with verifiable field evidence and human testimony.",
            ),
            TreatmentSection(
                section_id="S05",
                timecode_range="06:45 - 08:00",
                structural_function="RESOLUTION_AND_CTA",
                audio_column=(
                    "HOST: 'Reliable infrastructure is not magic; it is disciplined engineering. "
                    "To read the verified technical field audit or access the open specifications, click the link below.'"
                ),
                video_column=(
                    "Wide scenic drone shot of the community water point and surrounding landscape. "
                    "On-screen card with URL and visual thumbnail pointing to the downloadable engineering report."
                ),
                claims_addressed=[],
                retention_intent="Strong conclusive payoff with purposeful, action-oriented close.",
            ),
        ]

        audiovisual_execution = {
            "format": "Documentary Field Explainer (16:9 4K)",
            "estimated_duration_seconds": duration_seconds,
            "hook_and_premise": idea.hook,
            "narrative_arc": [
                "01: Hook with physical contrast",
                "02: Context and friction",
                "03: Mechanical demonstration",
                "04: Empirical proof and human consequence",
                "05: Resolution and resource CTA",
            ],
            "visual_grammar": {
                "camera": "Handheld cinema prime lenses for SME interaction; locked gimbal for technical machinery",
                "color_palette": "Naturalistic daylight tones, high contrast on telemetry readouts",
                "sound_design": "Subtle ambient environmental sound, crisp dialogue, warm acoustic score",
            },
            "call_to_action": "Inspect the open technical field report and download the implementation schematics.",
        }

        # Open questions / dependencies
        open_questions = list(idea.unresolved_questions)
        if not brief.deadlines.get("target_publish_window"):
            open_questions.append("Confirm target publication window with communications director.")

        # Gate Evaluations
        gate1_input = {
            "decision_owner": brief.decision_owner,
            "objective": brief.organizational_goals[0] if brief.organizational_goals else "Demonstrate program efficacy",
            "target_audience": idea.target_audience,
            "deliverables": ["Main 16:9 YouTube Video", "9:16 Short", "Thumbnail Assets", "Field Call Sheet"],
            "schedule": brief.deadlines.get("target_publish_window") or "Q4 Production Window",
            "approval_authority": brief.approval_authority,
        }
        gate1_res = ProductionGatekeeper.evaluate_scope_gate(gate1_input)

        gate2_input = {
            "content_promise": f"Explains and proves {primary_fact}",
            "narrative_engine": "Technical demonstration + human impact transformation",
            "core_message": f"Sustainable reliability is achieved through {secondary_fact}",
            "packaging_hypotheses": [
                {"title": "The Zero-Fuel Water Pump That Solved a 10-Year Crisis", "thumbnail": "SME pointing to gauge"},
                {"title": "Why Most Rural Water Systems Fail (And What Actually Works)", "thumbnail": "Split screen broken vs working"},
            ],
            "evidence_or_access_confirmed": len(brief.subject_matter_notes) > 0,
            "risk_acceptable": True,
        }
        gate2_res = ProductionGatekeeper.evaluate_strategy_creative_gate(gate2_input)

        gate_results = {
            "gate_1_scope": gate1_res.to_dict(),
            "gate_2_strategy_creative": gate2_res.to_dict(),
        }

        proposal = StrategicProposal(
            proposal_id=proposal_id,
            project_id=brief.project_id,
            idea_id=idea.idea_id,
            working_title=idea.title,
            strategic_rationale=strategic_rationale,
            audiovisual_execution=audiovisual_execution,
            treatment_sections=sections,
            open_questions=open_questions,
            approval_status=ApprovalStatus.PENDING_APPROVAL if (gate1_res.passed and gate2_res.passed) else ApprovalStatus.DRAFT,
            gate_results=gate_results,
        )
        proposal.content_hash = proposal.calculate_hash()
        return proposal
