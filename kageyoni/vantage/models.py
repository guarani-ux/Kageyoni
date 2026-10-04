"""
Data models for Vantage: Organizational Video Development & Production System.
"""

from __future__ import annotations
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EpistemicNodeStatus(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    CONTESTED = "CONTESTED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    UNRESOLVED = "UNRESOLVED"


class IdeaQualificationStatus(str, Enum):
    QUALIFIED = "QUALIFIED"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"


class ApprovalStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"


@dataclass
class ProjectBrief:
    project_id: str
    working_title: str
    organization: str
    decision_owner: str
    approval_authority: str
    target_audience: Dict[str, Any]
    organizational_goals: List[str] = field(default_factory=list)
    campaign_priorities: List[str] = field(default_factory=list)
    stakeholder_requests: List[str] = field(default_factory=list)
    subject_matter_notes: List[Dict[str, Any]] = field(default_factory=list)
    existing_content: List[str] = field(default_factory=list)
    trends: List[Dict[str, Any]] = field(default_factory=list)
    available_resources: Dict[str, Any] = field(default_factory=dict)
    deadlines: Dict[str, Any] = field(default_factory=dict)
    missing_information: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "working_title": self.working_title,
            "organization": self.organization,
            "decision_owner": self.decision_owner,
            "approval_authority": self.approval_authority,
            "target_audience": self.target_audience,
            "organizational_goals": self.organizational_goals,
            "campaign_priorities": self.campaign_priorities,
            "stakeholder_requests": self.stakeholder_requests,
            "subject_matter_notes": self.subject_matter_notes,
            "existing_content": self.existing_content,
            "trends": self.trends,
            "available_resources": self.available_resources,
            "deadlines": self.deadlines,
            "missing_information": self.missing_information,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectBrief:
        return cls(**data)


@dataclass
class IdeaCandidate:
    idea_id: str
    title: str
    premise: str
    hook: str
    target_audience: str
    organizational_contribution: str
    supporting_evidence: List[str]
    production_implications: str
    unresolved_questions: List[str]
    scores: Dict[str, float]
    status: IdeaQualificationStatus
    trend_alignment: Optional[str] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "idea_id": self.idea_id,
            "title": self.title,
            "premise": self.premise,
            "hook": self.hook,
            "target_audience": self.target_audience,
            "organizational_contribution": self.organizational_contribution,
            "supporting_evidence": self.supporting_evidence,
            "production_implications": self.production_implications,
            "trend_alignment": self.trend_alignment,
            "unresolved_questions": self.unresolved_questions,
            "scores": self.scores,
            "status": self.status.value,
            "rejection_reason": self.rejection_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IdeaCandidate:
        d = dict(data)
        d["status"] = IdeaQualificationStatus(d["status"])
        return cls(**d)


@dataclass
class TreatmentSection:
    section_id: str
    timecode_range: str
    structural_function: str  # HOOK, ORIENTATION, STAKES, DEMONSTRATION, PROOF, RESOLUTION, CTA
    audio_column: str
    video_column: str
    claims_addressed: List[str] = field(default_factory=list)
    retention_intent: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "timecode_range": self.timecode_range,
            "structural_function": self.structural_function,
            "audio_column": self.audio_column,
            "video_column": self.video_column,
            "claims_addressed": self.claims_addressed,
            "retention_intent": self.retention_intent,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TreatmentSection:
        return cls(**data)


@dataclass
class StrategicProposal:
    proposal_id: str
    project_id: str
    idea_id: str
    working_title: str
    strategic_rationale: Dict[str, Any]
    audiovisual_execution: Dict[str, Any]
    treatment_sections: List[TreatmentSection]
    open_questions: List[str]
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    content_hash: str = ""
    gate_results: Dict[str, Any] = field(default_factory=dict)

    def calculate_hash(self) -> str:
        payload = {
            "idea_id": self.idea_id,
            "working_title": self.working_title,
            "strategic_rationale": self.strategic_rationale,
            "audiovisual_execution": self.audiovisual_execution,
            "treatment_sections": [s.to_dict() for s in self.treatment_sections],
            "open_questions": self.open_questions,
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "project_id": self.project_id,
            "idea_id": self.idea_id,
            "working_title": self.working_title,
            "strategic_rationale": self.strategic_rationale,
            "audiovisual_execution": self.audiovisual_execution,
            "treatment_sections": [s.to_dict() for s in self.treatment_sections],
            "open_questions": self.open_questions,
            "approval_status": self.approval_status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "content_hash": self.content_hash or self.calculate_hash(),
            "gate_results": self.gate_results,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrategicProposal:
        d = dict(data)
        d["approval_status"] = ApprovalStatus(d["approval_status"])
        d["treatment_sections"] = [
            TreatmentSection.from_dict(s) for s in d.get("treatment_sections", [])
        ]
        return cls(**d)


@dataclass
class CallSheet:
    call_sheet_id: str
    shoot_date: Optional[str]
    call_time: Optional[str]
    location_name: Optional[str]
    location_address: Optional[str]
    crew_roster: List[Dict[str, Any]] = field(default_factory=list)
    talent_roster: List[Dict[str, Any]] = field(default_factory=list)
    schedule_blocks: List[Dict[str, str]] = field(default_factory=list)
    safety_notes: Optional[str] = None
    missing_prerequisites: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_sheet_id": self.call_sheet_id,
            "shoot_date": self.shoot_date,
            "call_time": self.call_time,
            "location_name": self.location_name,
            "location_address": self.location_address,
            "crew_roster": self.crew_roster,
            "talent_roster": self.talent_roster,
            "schedule_blocks": self.schedule_blocks,
            "safety_notes": self.safety_notes,
            "missing_prerequisites": self.missing_prerequisites,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CallSheet:
        return cls(**data)


@dataclass
class ProductionPlan:
    plan_id: str
    project_id: str
    shot_plan: List[Dict[str, Any]]
    interview_guide: List[Dict[str, Any]]
    schedule: List[Dict[str, str]]
    resource_requirements: Dict[str, Any]
    call_sheet: CallSheet
    status: EpistemicNodeStatus = EpistemicNodeStatus.VALID
    unresolved_items: List[str] = field(default_factory=list)
    gate_results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "project_id": self.project_id,
            "shot_plan": self.shot_plan,
            "interview_guide": self.interview_guide,
            "schedule": self.schedule,
            "resource_requirements": self.resource_requirements,
            "call_sheet": self.call_sheet.to_dict(),
            "status": self.status.value,
            "unresolved_items": self.unresolved_items,
            "gate_results": self.gate_results,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProductionPlan:
        d = dict(data)
        d["status"] = EpistemicNodeStatus(d["status"])
        d["call_sheet"] = CallSheet.from_dict(d["call_sheet"])
        return cls(**d)


@dataclass
class TitleOption:
    angle_type: str  # Curiosity/Investigation, Practical/Utility, Stakes/Transformation
    title: str
    rationale: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "angle_type": self.angle_type,
            "title": self.title,
            "rationale": self.rationale,
        }


@dataclass
class ThumbnailDirection:
    concept_name: str
    visual_scene: str
    focal_subject: str
    emotional_expression: str
    background_contrast: str
    text_copy_max_3_words: str
    mobile_legibility_notes: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "concept_name": self.concept_name,
            "visual_scene": self.visual_scene,
            "focal_subject": self.focal_subject,
            "emotional_expression": self.emotional_expression,
            "background_contrast": self.background_contrast,
            "text_copy_max_3_words": self.text_copy_max_3_words,
            "mobile_legibility_notes": self.mobile_legibility_notes,
        }


@dataclass
class ShortsTreatment:
    vertical_aspect_ratio: str  # "9:16"
    target_duration_seconds: int
    hook_seconds_0_to_2: str
    narrative_progression: str
    on_screen_captions_plan: str
    pre_shoot_derivative_instructions: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vertical_aspect_ratio": self.vertical_aspect_ratio,
            "target_duration_seconds": self.target_duration_seconds,
            "hook_seconds_0_to_2": self.hook_seconds_0_to_2,
            "narrative_progression": self.narrative_progression,
            "on_screen_captions_plan": self.on_screen_captions_plan,
            "pre_shoot_derivative_instructions": self.pre_shoot_derivative_instructions,
        }


@dataclass
class PlatformPackaging:
    packaging_id: str
    project_id: str
    youtube_titles: List[TitleOption]
    thumbnail_directions: List[ThumbnailDirection]
    description_opening: str
    chapters: List[Dict[str, str]]
    sources_and_citations: List[str]
    links: List[str]
    statutory_disclosures: List[str]
    shorts_treatment: ShortsTreatment
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    status: EpistemicNodeStatus = EpistemicNodeStatus.VALID
    qc_manifest: Dict[str, Any] = field(default_factory=dict)
    gate_results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packaging_id": self.packaging_id,
            "project_id": self.project_id,
            "youtube_titles": [t.to_dict() for t in self.youtube_titles],
            "thumbnail_directions": [td.to_dict() for td in self.thumbnail_directions],
            "description_opening": self.description_opening,
            "chapters": self.chapters,
            "sources_and_citations": self.sources_and_citations,
            "links": self.links,
            "statutory_disclosures": self.statutory_disclosures,
            "shorts_treatment": self.shorts_treatment.to_dict(),
            "approval_status": self.approval_status.value,
            "status": self.status.value,
            "qc_manifest": self.qc_manifest,
            "gate_results": self.gate_results,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlatformPackaging:
        d = dict(data)
        d["approval_status"] = ApprovalStatus(d["approval_status"])
        d["status"] = EpistemicNodeStatus(d["status"])
        d["youtube_titles"] = [TitleOption(**t) for t in d.get("youtube_titles", [])]
        d["thumbnail_directions"] = [
            ThumbnailDirection(**td) for td in d.get("thumbnail_directions", [])
        ]
        d["shorts_treatment"] = ShortsTreatment(**d.get("shorts_treatment", {}))
        return cls(**d)


@dataclass
class PerformanceAnalysis:
    analysis_id: str
    project_id: str
    published_video_title: str
    time_window: str
    pre_publication_expectations: Dict[str, Any]
    observed_metrics: Dict[str, Any]
    observations: List[str]
    retention_diagnostics: Dict[str, Any]
    explanations: List[Dict[str, str]]
    packaging_revisions: List[str]
    editing_or_derivative_revisions: List[str]
    subsequent_idea_candidates: List[str]
    reusable_lesson: str
    gate_result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "project_id": self.project_id,
            "published_video_title": self.published_video_title,
            "time_window": self.time_window,
            "pre_publication_expectations": self.pre_publication_expectations,
            "observed_metrics": self.observed_metrics,
            "observations": self.observations,
            "retention_diagnostics": self.retention_diagnostics,
            "explanations": self.explanations,
            "packaging_revisions": self.packaging_revisions,
            "editing_or_derivative_revisions": self.editing_or_derivative_revisions,
            "subsequent_idea_candidates": self.subsequent_idea_candidates,
            "reusable_lesson": self.reusable_lesson,
            "gate_result": self.gate_result,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PerformanceAnalysis:
        return cls(**data)
