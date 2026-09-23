"""
Script-Ready Intelligence Package Compiler (Pillars 8, 9 & Traceability)

Compiles the authoritative, 10-section upstream artifact consumed by writers/directors.
Enforces uncertainty propagation, backward lineage tracing, and forward falsifiability.
"""

from __future__ import annotations
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from .claims import ClaimGraph, ClaimNode, EpistemicStatus
from .topic_modeler import TopicModel
from .treatment_generator import CompetingTreatment


@dataclass
class AudienceModel:
    target_segment: str
    prior_knowledge_baseline: str
    active_misconceptions: List[str]
    practical_and_emotional_stakes: str
    reception_friction: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_segment": self.target_segment,
            "prior_knowledge_baseline": self.prior_knowledge_baseline,
            "active_misconceptions": self.active_misconceptions,
            "practical_and_emotional_stakes": self.practical_and_emotional_stakes,
            "reception_friction": self.reception_friction,
        }


@dataclass
class ScriptReadyPackage:
    package_id: str
    compiled_at: float
    subject_title: str

    # 10 Mandatory Sections
    topic_model: Dict[str, Any]
    evidence_map: Dict[str, Any]
    audience_model: Dict[str, Any]
    communication_problem: Dict[str, Any]
    story_territory: Dict[str, Any]
    competing_treatments: List[Dict[str, Any]]
    creative_decision: Dict[str, Any]
    narrative_ingredients: Dict[str, Any]
    constraints: Dict[str, Any]
    open_questions: Dict[str, Any]

    # Traceability Metadata
    uncertainty_warnings: List[str] = field(default_factory=list)
    lineage_chains: Dict[str, Any] = field(default_factory=dict)
    is_falsified: bool = False
    falsification_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "compiled_at": self.compiled_at,
            "subject_title": self.subject_title,
            "topic_model": self.topic_model,
            "evidence_map": self.evidence_map,
            "audience_model": self.audience_model,
            "communication_problem": self.communication_problem,
            "story_territory": self.story_territory,
            "competing_treatments": self.competing_treatments,
            "creative_decision": self.creative_decision,
            "narrative_ingredients": self.narrative_ingredients,
            "constraints": self.constraints,
            "open_questions": self.open_questions,
            "uncertainty_warnings": self.uncertainty_warnings,
            "lineage_chains": self.lineage_chains,
            "is_falsified": self.is_falsified,
            "falsification_notes": self.falsification_notes,
        }


class ScriptReadyCompiler:
    """
    Compiles the final upstream package and enforces structural invariants.
    """

    @classmethod
    def compile_package(
        cls,
        subject_title: str,
        topic: TopicModel,
        graph: ClaimGraph,
        audience: AudienceModel,
        comm_problem: Dict[str, Any],
        story_territory: Dict[str, Any],
        treatments: List[CompetingTreatment],
        narrative_ingredients: Dict[str, Any],
        constraints: Dict[str, Any],
        open_questions: Dict[str, Any],
    ) -> ScriptReadyPackage:
        package_id = f"pkg_{uuid.uuid4().hex[:10]}"

        # Validation: Verify all 10 sections are non-empty
        sections = [
            ("topic_model", topic.core_state_of_affairs),
            ("audience_model", audience.target_segment),
            ("communication_problem", comm_problem.get("current_state")),
            ("story_territory", story_territory.get("core_frictions")),
            ("competing_treatments", treatments),
            ("narrative_ingredients", narrative_ingredients.get("essential_facts")),
            ("constraints", constraints.get("must_not_claim")),
            ("open_questions", open_questions.get("research_gaps")),
        ]

        for sec_name, sec_val in sections:
            if not sec_val or (isinstance(sec_val, (list, dict, str)) and len(sec_val) == 0):
                raise ValueError(f"PACKAGE_DEFICIT: Mandatory section '{sec_name}' is missing or empty.")

        # Selected Creative Decision: top-ranked treatment
        selected_treatment = treatments[0] if treatments else None
        if not selected_treatment:
            raise ValueError("PACKAGE_DEFICIT: At least one scored competing treatment is required.")

        creative_decision = {
            "selected_archetype": selected_treatment.archetype.value,
            "composite_score": selected_treatment.composite_score,
            "strategic_rationale": selected_treatment.hypothesis,
            "mandatory_flip_condition": selected_treatment.mandatory_flip_condition,
        }

        # Pillar 8: Uncertainty Propagation
        # Any uncertain claim must propagate explicit warning into the creative package
        uncertain_claims = graph.get_uncertain_claims()
        uncertainty_warnings = []
        for uc in uncertain_claims:
            uncertainty_warnings.append(
                f"UNCERTAINTY_PROPAGATED: Claim '{uc.claim_id}' ({uc.statement}) has status {uc.epistemic_status.value} with {uc.confidence_level} confidence. Must NOT be presented as settled fact in script."
            )

        # Evidence Map
        evidence_map = {
            "claims_count": len(graph.claims),
            "sources_count": len(graph.sources),
            "established_facts_count": len(graph.get_established_facts()),
            "uncertain_claims_count": len(uncertain_claims),
            "claims": [c.to_dict() for c in graph.claims.values()],
            "sources": [s.to_dict() for s in graph.sources.values()],
        }

        # Pillar 9 & Traceability: Build Lineage Chains
        # Trace backward from creative decision to claims to sources
        lineage_chains = {}
        for c in graph.get_established_facts():
            lineage_chains[c.claim_id] = graph.trace_backward_lineage(c.claim_id)

        return ScriptReadyPackage(
            package_id=package_id,
            compiled_at=time.time(),
            subject_title=subject_title,
            topic_model=topic.to_dict(),
            evidence_map=evidence_map,
            audience_model=audience.to_dict(),
            communication_problem=comm_problem,
            story_territory=story_territory,
            competing_treatments=[t.to_dict() for t in treatments],
            creative_decision=creative_decision,
            narrative_ingredients=narrative_ingredients,
            constraints=constraints,
            open_questions=open_questions,
            uncertainty_warnings=uncertainty_warnings,
            lineage_chains=lineage_chains,
        )

    @classmethod
    def propagate_forward_contradiction(
        cls,
        package: ScriptReadyPackage,
        graph: ClaimGraph,
        invalidated_claim_id: str,
        reason: str,
    ) -> List[str]:
        """
        Forward Falsifiability:
        When a claim is invalidated by contradictory evidence, update the package
        state, mark as falsified, and list affected lineage chains.
        """
        affected = graph.invalidate_claim(invalidated_claim_id, reason)
        if affected:
            package.is_falsified = True
            package.falsification_notes.append(
                f"CONTRADICTION_PROPAGATED: Claim '{invalidated_claim_id}' and {len(affected)-1} dependent nodes invalidated: {reason}"
            )
            # Re-evaluate evidence map
            package.evidence_map["claims"] = [c.to_dict() for c in graph.claims.values()]
            package.evidence_map["uncertain_claims_count"] = len(graph.get_uncertain_claims())
        return affected
