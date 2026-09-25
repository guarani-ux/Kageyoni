"""Core types, deficits, epistemic boundaries, and non-authority invariants.

Fundamental Invariants:
1. Δcog ≠ Δworld: Cognitive transformations never mutate the authoritative Kageyoni world ledger.
2. Cognitive Output ≠ Verified Fact: Cognitive transformations cannot self-certify.
3. Explicit Deficit Representation: Unknowns and missing verifiers are represented
   via VERIFIER_DEFICIT, INPUT_DEFICIT, and SEMANTIC_BINDING_DEFICIT.
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


class EpistemicCategory(str, Enum):
    """Canonical epistemic categories separating statements by warranted basis."""
    SOURCE_SUPPLIED_FACT = "SOURCE_SUPPLIED_FACT"
    EVIDENCE_SUPPORTED_CLAIM = "EVIDENCE_SUPPORTED_CLAIM"
    INFERENCE = "INFERENCE"
    ASSUMPTION = "ASSUMPTION"
    HEURISTIC = "HEURISTIC"
    INTERPRETATION = "INTERPRETATION"
    CREATIVE_DECISION = "CREATIVE_DECISION"
    PREFERENCE = "PREFERENCE"
    UNKNOWN = "UNKNOWN"


class EpistemicLaunderingError(ValueError):
    """Raised when cognitive reasoning attempts to promote an unverified hypothesis to a fact."""
    pass


class ObjectiveDriftError(ValueError):
    """Raised when a cognitive transformation silently alters the invariant objective."""
    pass


class DeficitType(str, Enum):
    """Explicitly declared deficits in knowledge, verification, or semantics."""
    VERIFIER_DEFICIT = "VERIFIER_DEFICIT"
    INPUT_DEFICIT = "INPUT_DEFICIT"
    SEMANTIC_BINDING_DEFICIT = "SEMANTIC_BINDING_DEFICIT"


@dataclass(frozen=True)
class KnowledgeDeficit:
    """An explicit representation of missing verification or input."""
    deficit_type: DeficitType
    description: str
    impacted_representation: str
    required_to_resolve: str
    declared_at: float = field(default_factory=lambda: 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "deficit_type": self.deficit_type.value,
            "description": self.description,
            "impacted_representation": self.impacted_representation,
            "required_to_resolve": self.required_to_resolve,
            "declared_at": self.declared_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeDeficit:
        return cls(
            deficit_type=DeficitType(data["deficit_type"]),
            description=data["description"],
            impacted_representation=data.get("impacted_representation", ""),
            required_to_resolve=data.get("required_to_resolve", ""),
            declared_at=data.get("declared_at", 0.0),
        )


@dataclass
class CognitiveHypothesis:
    """A working proposition produced by cognitive transformation."""
    hypothesis_id: str
    statement: str
    epistemic_status: EpistemicCategory = EpistemicCategory.ASSUMPTION
    confidence: str = "UNVERIFIED"  # UNVERIFIED | LOW | MEDIUM | HIGH | CONTESTED
    falsification_condition: str = ""
    discriminating_questions: list[str] = field(default_factory=list)
    provenance_sources: list[str] = field(default_factory=list)
    parent_hypothesis_ids: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    is_invalidated: bool = False
    invalidation_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "epistemic_status": self.epistemic_status.value,
            "confidence": self.confidence,
            "falsification_condition": self.falsification_condition,
            "discriminating_questions": list(self.discriminating_questions),
            "provenance_sources": list(self.provenance_sources),
            "parent_hypothesis_ids": list(self.parent_hypothesis_ids),
            "uncertainties": list(self.uncertainties),
            "is_invalidated": self.is_invalidated,
            "invalidation_reason": self.invalidation_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CognitiveHypothesis:
        ep_status = data.get("epistemic_status", EpistemicCategory.ASSUMPTION.value)
        if isinstance(ep_status, str):
            ep_status = EpistemicCategory(ep_status)
        return cls(
            hypothesis_id=data["hypothesis_id"],
            statement=data["statement"],
            epistemic_status=ep_status,
            confidence=data.get("confidence", "UNVERIFIED"),
            falsification_condition=data.get("falsification_condition", ""),
            discriminating_questions=list(data.get("discriminating_questions", [])),
            provenance_sources=list(data.get("provenance_sources", [])),
            parent_hypothesis_ids=list(data.get("parent_hypothesis_ids", [])),
            uncertainties=list(data.get("uncertainties", [])),
            is_invalidated=data.get("is_invalidated", False),
            invalidation_reason=data.get("invalidation_reason"),
        )


@dataclass
class CognitiveState:
    """Deliberative mental state store belonging strictly to the cognitive operator."""
    objective: str
    raw_intent: str = ""
    representations: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[CognitiveHypothesis] = field(default_factory=list)
    invariants: list[dict[str, Any]] = field(default_factory=list)
    active_constraints: list[str] = field(default_factory=list)
    unresolved_uncertainties: list[str] = field(default_factory=list)
    contradictions: dict[str, list[Any]] = field(default_factory=dict)
    probes: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    candidate_compositions: list[dict[str, Any]] = field(default_factory=list)
    deficits: list[KnowledgeDeficit] = field(default_factory=list)
    provenance_log: list[dict[str, Any]] = field(default_factory=list)

    def clone(self) -> CognitiveState:
        return copy.deepcopy(self)

    def add_hypothesis(self, hypothesis: CognitiveHypothesis) -> None:
        self.hypotheses.append(hypothesis)

    def record_deficit(self, deficit: KnowledgeDeficit) -> None:
        self.deficits.append(deficit)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "raw_intent": self.raw_intent,
            "representations": self.representations,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "invariants": self.invariants,
            "active_constraints": self.active_constraints,
            "unresolved_uncertainties": self.unresolved_uncertainties,
            "contradictions": self.contradictions,
            "probes": self.probes,
            "observations": self.observations,
            "candidate_compositions": self.candidate_compositions,
            "deficits": [d.to_dict() for d in self.deficits],
            "provenance_log": self.provenance_log,
        }


class NatureType(str, Enum):
    EXPANSION = "EXPANSION"
    COMPRESSION = "COMPRESSION"
    GROUNDING = "GROUNDING"
    CONTINUITY = "CONTINUITY"
    COUPLING = "COUPLING"


@dataclass
class CognitiveDelta:
    """Record of a cognitive transformation step.

    Crucially: Δcog ≠ Δworld. A delta represents changes to internal mental representation,
    never mutations to physical Kageyoni database tables.
    """
    delta_id: str
    nature: NatureType
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    objective_preserved: bool
    deficits_identified: list[KnowledgeDeficit] = field(default_factory=list)
    authoritative_world_mutated: bool = False  # MUST ALWAYS BE FALSE
    timestamp: float = field(default_factory=lambda: 0.0)

    def verify_no_world_authority(self) -> bool:
        """Enforces that cognitive delta claims zero direct world authority."""
        return not self.authoritative_world_mutated
