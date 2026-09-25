"""Entity Modeling Models for Kageyoni Sovereign Incarnation.

Deconstructs entity agency into four formal, composable modeling models:
1. CapabilityModel: Operational techniques, tools, action bindings, costs, and condition limits.
2. ReasoningModel: Epistemic orientation, dynamic contextual nature weights, intensity, and governors.
   Note: Nature weights are NOT fixed character constants (W_nature ≠ CharacterConstant).
   W_nature = f(Disposition, Experience, CurrentSituation, Objective, EpistemicState).
3. UnderstandingModel: Epistemic horizon, private ontology, perceptual filters, unknowns, and contradictions.
4. PersonalityModel: Interiority, core drives, uncompromised boundaries, relational stances, and rejection temperament.

Unified in EntitySpecification.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set

from kageyoni.nature.core import DeficitType, KnowledgeDeficit, NatureType


@dataclass
class CapabilityModel:
    """Operational abilities, techniques, tool/action bindings, costs, and limits."""
    active_capabilities: dict[str, dict[str, Any]] = field(default_factory=dict)
    latent_capabilities: dict[str, dict[str, Any]] = field(default_factory=dict)
    mastery_levels: dict[str, str] = field(default_factory=dict)
    costs_and_limits: dict[str, dict[str, Any]] = field(default_factory=dict)
    supported_verbs: list[str] = field(default_factory=lambda: ["inspect", "move", "execute_action"])

    def is_supported(self, verb: str) -> bool:
        return verb in self.supported_verbs or verb in self.active_capabilities

    def get_capability_details(self, cap_id: str) -> Optional[dict[str, Any]]:
        return self.active_capabilities.get(cap_id) or self.latent_capabilities.get(cap_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_capabilities": copy.deepcopy(self.active_capabilities),
            "latent_capabilities": copy.deepcopy(self.latent_capabilities),
            "mastery_levels": copy.deepcopy(self.mastery_levels),
            "costs_and_limits": copy.deepcopy(self.costs_and_limits),
            "supported_verbs": list(self.supported_verbs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityModel:
        return cls(
            active_capabilities=copy.deepcopy(data.get("active_capabilities", {})),
            latent_capabilities=copy.deepcopy(data.get("latent_capabilities", {})),
            mastery_levels=copy.deepcopy(data.get("mastery_levels", {})),
            costs_and_limits=copy.deepcopy(data.get("costs_and_limits", {})),
            supported_verbs=list(data.get("supported_verbs", ["inspect", "move", "execute_action"])),
        )


@dataclass
class ReasoningModel:
    """Epistemic orientation, dynamic contextual nature weights, intensity, and governors.

    Rejects the trap of W_nature = CharacterConstant (e.g. Axiom is not 'CompressionAgent').
    Nature weights are dynamically evaluated:
    W_nature = f(Disposition, Experience, CurrentSituation, Objective, EpistemicState).
    """
    base_disposition: dict[str, float] = field(default_factory=lambda: {
        NatureType.EXPANSION.value: 0.20,
        NatureType.COMPRESSION.value: 0.20,
        NatureType.GROUNDING.value: 0.20,
        NatureType.CONTINUITY.value: 0.20,
        NatureType.COUPLING.value: 0.20,
    })
    intensity_bias: float = 0.70
    max_consecutive_failures: int = 3
    hypothesis_confidence_threshold: float = 0.65
    falsification_first: bool = True

    def compute_contextual_weights(
        self,
        current_situation: Optional[dict[str, Any]] = None,
        deficits: Sequence[KnowledgeDeficit] = (),
        recent_scars_count: int = 0,
    ) -> dict[NatureType, float]:
        """Dynamically computes nature weights from disposition, situation, deficits, and experience."""
        weights = {NatureType(k): v for k, v in self.base_disposition.items()}
        sit = current_situation or {}

        # 1. Epistemic Deficits exert primary demand
        for d in deficits:
            if d.deficit_type == DeficitType.INPUT_DEFICIT:
                weights[NatureType.EXPANSION] += 0.35
            elif d.deficit_type == DeficitType.VERIFIER_DEFICIT:
                weights[NatureType.GROUNDING] += 0.35
            elif d.deficit_type == DeficitType.SEMANTIC_BINDING_DEFICIT:
                weights[NatureType.COMPRESSION] += 0.35

        # 2. Situational Dynamics
        # Unexplored territory / open routes -> demand Expansion
        if sit.get("has_unexplored_routes") or sit.get("high_uncertainty"):
            weights[NatureType.EXPANSION] += 0.25

        # Contradictions / unverified claims / physical barriers -> demand Grounding
        if sit.get("has_contradictions") or sit.get("is_contested_barrier"):
            weights[NatureType.GROUNDING] += 0.30

        # High revision churn / state transition -> demand Continuity
        if sit.get("revision_changed") or sit.get("temporal_gap"):
            weights[NatureType.CONTINUITY] += 0.30

        # Multiple observed cases / repetitive observations -> demand Compression
        if sit.get("multi_case_observations") or sit.get("entropy_elevated"):
            weights[NatureType.COMPRESSION] += 0.25

        # Multi-party presence / complementary components -> demand Coupling
        if sit.get("copresent_allies") or sit.get("composite_mechanism"):
            weights[NatureType.COUPLING] += 0.25

        # 3. Accumulated Friction (Recent Scars) -> elevates Grounding & Compression over Expansion
        if recent_scars_count > 0:
            weights[NatureType.GROUNDING] += 0.15 * recent_scars_count
            weights[NatureType.EXPANSION] = max(0.05, weights[NatureType.EXPANSION] - 0.10 * recent_scars_count)

        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            return {k: round(v / total, 4) for k, v in weights.items()}
        return weights

    def get_preferred_nature(
        self,
        deficits: Sequence[KnowledgeDeficit] = (),
        current_situation: Optional[dict[str, Any]] = None,
        recent_scars_count: int = 0,
    ) -> NatureType:
        weights = self.compute_contextual_weights(current_situation, deficits, recent_scars_count)
        sorted_natures = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
        return sorted_natures[0][0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_disposition": copy.deepcopy(self.base_disposition),
            "intensity_bias": self.intensity_bias,
            "max_consecutive_failures": self.max_consecutive_failures,
            "hypothesis_confidence_threshold": self.hypothesis_confidence_threshold,
            "falsification_first": self.falsification_first,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasoningModel:
        disposition = data.get("base_disposition") or data.get("nature_weights", {})
        return cls(
            base_disposition=copy.deepcopy(disposition),
            intensity_bias=data.get("intensity_bias", 0.7),
            max_consecutive_failures=data.get("max_consecutive_failures", 3),
            hypothesis_confidence_threshold=data.get("hypothesis_confidence_threshold", 0.65),
            falsification_first=data.get("falsification_first", True),
        )


@dataclass
class UnderstandingModel:
    """Epistemic horizon, private ontology, perceptual filters, unknowns, and contradictions."""
    epistemic_horizon: list[str] = field(default_factory=list)
    private_ontology: dict[str, str] = field(default_factory=dict)
    perceptual_filters: list[str] = field(default_factory=list)
    unknowns: list[dict[str, Any]] = field(default_factory=list)
    contradictions: list[dict[str, Any]] = field(default_factory=list)

    def comprehends(self, domain: str) -> bool:
        if not self.epistemic_horizon:
            return True
        return domain in self.epistemic_horizon

    def preserve_unknown(self, ref: str, statement: str, blocking: bool = False) -> None:
        self.unknowns.append({"ref": ref, "statement": statement, "blocking": blocking})

    def preserve_contradiction(self, ref: str, thesis: str, antithesis: str) -> None:
        self.contradictions.append({"ref": ref, "thesis": thesis, "antithesis": antithesis})

    def to_dict(self) -> dict[str, Any]:
        return {
            "epistemic_horizon": list(self.epistemic_horizon),
            "private_ontology": copy.deepcopy(self.private_ontology),
            "perceptual_filters": list(self.perceptual_filters),
            "unknowns": copy.deepcopy(self.unknowns),
            "contradictions": copy.deepcopy(self.contradictions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnderstandingModel:
        return cls(
            epistemic_horizon=list(data.get("epistemic_horizon", [])),
            private_ontology=copy.deepcopy(data.get("private_ontology", {})),
            perceptual_filters=list(data.get("perceptual_filters", [])),
            unknowns=copy.deepcopy(data.get("unknowns", [])),
            contradictions=copy.deepcopy(data.get("contradictions", [])),
        )


@dataclass
class PersonalityModel:
    """Interiority, core drives, uncompromised boundaries, relational stances, and rejection temperament."""
    core_drives: list[str] = field(default_factory=list)
    uncompromising_boundaries: list[str] = field(default_factory=list)
    relational_stances: dict[str, str] = field(default_factory=dict)
    rejection_temperament: str = "analytical_restructure"
    dialogue_style: str = "measured"

    def violates_boundary(self, proposed_narrative_or_intent: str) -> bool:
        low = proposed_narrative_or_intent.lower()
        for b in self.uncompromising_boundaries:
            if b.lower() in low:
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "core_drives": list(self.core_drives),
            "uncompromising_boundaries": list(self.uncompromising_boundaries),
            "relational_stances": copy.deepcopy(self.relational_stances),
            "rejection_temperament": self.rejection_temperament,
            "dialogue_style": self.dialogue_style,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersonalityModel:
        return cls(
            core_drives=list(data.get("core_drives", [])),
            uncompromising_boundaries=list(data.get("uncompromising_boundaries", [])),
            relational_stances=copy.deepcopy(data.get("relational_stances", {})),
            rejection_temperament=data.get("rejection_temperament", "analytical_restructure"),
            dialogue_style=data.get("dialogue_style", "measured"),
        )


@dataclass
class EntitySpecification:
    """Declarative specification uniting all four models into an Entity of Kageyoni."""
    entity_id: str
    name: str
    canonical_role: str
    will_ref: Optional[str] = None
    capability_model: CapabilityModel = field(default_factory=CapabilityModel)
    reasoning_model: ReasoningModel = field(default_factory=ReasoningModel)
    understanding_model: UnderstandingModel = field(default_factory=UnderstandingModel)
    personality_model: PersonalityModel = field(default_factory=PersonalityModel)
    techniques: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "canonical_role": self.canonical_role,
            "will_ref": self.will_ref,
            "capability_model": self.capability_model.to_dict(),
            "reasoning_model": self.reasoning_model.to_dict(),
            "understanding_model": self.understanding_model.to_dict(),
            "personality_model": self.personality_model.to_dict(),
            "techniques": list(self.techniques),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntitySpecification:
        return cls(
            entity_id=data["entity_id"],
            name=data["name"],
            canonical_role=data.get("canonical_role", "sovereign"),
            will_ref=data.get("will_ref"),
            capability_model=CapabilityModel.from_dict(data.get("capability_model", {})),
            reasoning_model=ReasoningModel.from_dict(data.get("reasoning_model", {})),
            understanding_model=UnderstandingModel.from_dict(data.get("understanding_model", {})),
            personality_model=PersonalityModel.from_dict(data.get("personality_model", {})),
            techniques=list(data.get("techniques", [])),
        )
