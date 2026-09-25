"""6. TRANSFORMATION CONTROL Layer

Purpose:
Govern selection, intensity, combination, termination, and switching among the five natures.

Transformation Control determines:
- WHAT transformation is currently needed based on epistemic deficits;
- WHEN it should begin;
- HOW strongly it should operate (intensity/budget/depth);
- WHEN another nature should be coupled with it;
- WHEN the current transformation has produced sufficient value;
- WHEN continued transformation becomes wasteful or dangerous;
- and WHEN external verification or human judgment is required.

Regulates Predictable Failure Modes:
- EXPANSION → search-space explosion
- COMPRESSION → false universality / destructive abstraction
- GROUNDING → verification paralysis
- CONTINUITY → stale-state accumulation
- COUPLING → spurious relationships

Governor Principle:
Prefers the smallest sufficient operation. Never invokes all five natures simply because they exist.
Enforces the 3-Strike Governor: halts local iteration on 3 consecutive failures.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence

from .compression import Compression, CompressionResult
from .continuity import Continuity, ContinuityResult
from .core import (
    CognitiveDelta,
    CognitiveHypothesis,
    CognitiveState,
    DeficitType,
    EpistemicCategory,
    KnowledgeDeficit,
    NatureType,
)
from .coupling import ComponentInterface, Coupling, CouplingResult
from .expansion import CandidateBranch, Expansion, ExpansionResult
from .grounding import Grounding, GroundingResult, VerificationProbe


class ControlDirective(str, Enum):
    PROCEED = "PROCEED"
    SWITCH_NATURE = "SWITCH_NATURE"
    COUPLE_NATURES = "COUPLE_NATURES"
    HALT_SUFFICIENT = "HALT_SUFFICIENT"
    HALT_EXPULSION_EXPLOSION = "HALT_EXPULSION_EXPLOSION"
    HALT_DESTRUCTIVE_ABSTRACTION = "HALT_DESTRUCTIVE_ABSTRACTION"
    HALT_VERIFICATION_PARALYSIS = "HALT_VERIFICATION_PARALYSIS"
    HALT_STALE_ACCUMULATION = "HALT_STALE_ACCUMULATION"
    HALT_SPURIOUS_COUPLING = "HALT_SPURIOUS_COUPLING"
    HALT_THREE_STRIKE_ABORT = "HALT_THREE_STRIKE_ABORT"
    REQUIRES_USER_JUDGMENT = "REQUIRES_USER_JUDGMENT"
    REQUIRES_EXTERNAL_GATEWAY = "REQUIRES_EXTERNAL_GATEWAY"


@dataclass
class FailureModeGovernor:
    """Monitors and suppresses failure modes across all 5 natures."""
    max_expansion_branches: int = 5
    max_grounding_attempts: int = 3
    max_stale_revisions: int = 3
    max_consecutive_failures: int = 3
    current_failures: int = 0
    grounding_attempt_counter: dict[str, int] = field(default_factory=dict)

    def record_attempt(self, success: bool) -> None:
        if success:
            self.current_failures = 0
        else:
            self.current_failures += 1

    def should_abort_three_strikes(self) -> bool:
        return self.current_failures >= self.max_consecutive_failures


@dataclass
class ControlDecision:
    """Decision emitted by Transformation Control."""
    decision_id: str
    selected_nature: NatureType
    intensity: float  # 0.0 to 1.0
    directive: ControlDirective
    rationale: str
    coupled_nature: Optional[NatureType] = None
    deficit_addressed: Optional[DeficitType] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "selected_nature": self.selected_nature.value,
            "intensity": self.intensity,
            "directive": self.directive.value,
            "rationale": self.rationale,
            "coupled_nature": self.coupled_nature.value if self.coupled_nature else None,
            "deficit_addressed": self.deficit_addressed.value if self.deficit_addressed else None,
        }


class TransformationControl:
    """High-level governor orchestrating the 5 natures with minimal sufficient force."""

    def __init__(
        self,
        expansion: Optional[Expansion] = None,
        compression: Optional[Compression] = None,
        grounding: Optional[Grounding] = None,
        continuity: Optional[Continuity] = None,
        coupling: Optional[Coupling] = None,
        governor: Optional[FailureModeGovernor] = None,
    ):
        self.expansion = expansion or Expansion()
        self.compression = compression or Compression()
        self.grounding = grounding or Grounding()
        self.continuity = continuity or Continuity()
        self.coupling = coupling or Coupling()
        self.governor = governor or FailureModeGovernor()
        self.history: list[ControlDecision] = []

    def assess_need(self, state: CognitiveState) -> ControlDecision:
        """Determines WHAT transformation is needed based on state structure and deficits."""
        # Check 3-Strike Rule first
        if self.governor.should_abort_three_strikes():
            return ControlDecision(
                decision_id=f"ctrl-{uuid.uuid4().hex[:8]}",
                selected_nature=NatureType.GROUNDING,
                intensity=0.0,
                directive=ControlDirective.HALT_THREE_STRIKE_ABORT,
                rationale="Three consecutive transformation repairs failed. Triggering Root Cause Architecture Assessment.",
            )

        # 1. Stale-state check (Continuity needed?)
        unresolved_count = len(state.unresolved_uncertainties)
        if unresolved_count > 5:
            return ControlDecision(
                decision_id=f"ctrl-{uuid.uuid4().hex[:8]}",
                selected_nature=NatureType.CONTINUITY,
                intensity=0.7,
                directive=ControlDirective.PROCEED,
                rationale=f"High unresolved uncertainty ({unresolved_count} items); Continuity sweep needed to reconcile.",
                deficit_addressed=DeficitType.INPUT_DEFICIT,
            )

        # 2. Deficits check
        for d in state.deficits:
            if d.deficit_type == DeficitType.VERIFIER_DEFICIT:
                return ControlDecision(
                    decision_id=f"ctrl-{uuid.uuid4().hex[:8]}",
                    selected_nature=NatureType.GROUNDING,
                    intensity=0.8,
                    directive=ControlDirective.REQUIRES_EXTERNAL_GATEWAY,
                    rationale=f"Verifier deficit on '{d.impacted_representation}'. Grounding probe or gateway required.",
                    deficit_addressed=DeficitType.VERIFIER_DEFICIT,
                )
            if d.deficit_type == DeficitType.SEMANTIC_BINDING_DEFICIT:
                return ControlDecision(
                    decision_id=f"ctrl-{uuid.uuid4().hex[:8]}",
                    selected_nature=NatureType.COUPLING,
                    intensity=0.6,
                    directive=ControlDirective.PROCEED,
                    rationale=f"Semantic binding deficit on '{d.impacted_representation}'. Coupling needed to align interfaces.",
                    deficit_addressed=DeficitType.SEMANTIC_BINDING_DEFICIT,
                )

        # 3. Working hypotheses unverified? (Grounding needed?)
        unverified_hyps = [h for h in state.hypotheses if h.confidence == "UNVERIFIED" and not h.is_invalidated]
        if unverified_hyps:
            # Check for verification paralysis
            target = unverified_hyps[0]
            count = self.governor.grounding_attempt_counter.get(target.hypothesis_id, 0)
            if count >= self.governor.max_grounding_attempts:
                return ControlDecision(
                    decision_id=f"ctrl-{uuid.uuid4().hex[:8]}",
                    selected_nature=NatureType.GROUNDING,
                    intensity=0.2,
                    directive=ControlDirective.REQUIRES_USER_JUDGMENT,
                    rationale=f"Verification paralysis detected: {count} failed verification attempts on hypothesis {target.hypothesis_id}.",
                )
            return ControlDecision(
                decision_id=f"ctrl-{uuid.uuid4().hex[:8]}",
                selected_nature=NatureType.GROUNDING,
                intensity=0.8,
                directive=ControlDirective.PROCEED,
                rationale=f"Unverified hypothesis detected: '{target.statement[:50]}...'. Grounding required.",
                deficit_addressed=DeficitType.VERIFIER_DEFICIT,
            )

        # 4. Overcrowded representations / episodes? (Compression needed?)
        if len(state.representations) >= 4 and not state.invariants:
            return ControlDecision(
                decision_id=f"ctrl-{uuid.uuid4().hex[:8]}",
                selected_nature=NatureType.COMPRESSION,
                intensity=0.7,
                directive=ControlDirective.PROCEED,
                rationale="Multiple representations accumulated without extracted invariants. Compression required.",
            )

        # 5. Narrow framing or zero hypotheses? (Expansion needed?)
        if not state.hypotheses and state.objective:
            return ControlDecision(
                decision_id=f"ctrl-{uuid.uuid4().hex[:8]}",
                selected_nature=NatureType.EXPANSION,
                intensity=0.8,
                directive=ControlDirective.PROCEED,
                rationale="Zero hypotheses under active objective. Expansion required to reveal possibilities.",
            )

        # 6. Default: Sufficient value reached
        return ControlDecision(
            decision_id=f"ctrl-{uuid.uuid4().hex[:8]}",
            selected_nature=NatureType.CONTINUITY,
            intensity=0.1,
            directive=ControlDirective.HALT_SUFFICIENT,
            rationale="Current cognitive state is bounded, grounded, and stable. Halting transformations.",
        )

    def execute_controlled_step(
        self,
        state: CognitiveState,
        verifier_fn: Optional[Callable[[VerificationProbe], dict[str, Any]]] = None,
        cases_to_compress: Optional[Sequence[dict[str, Any]]] = None,
        world_transition: Optional[dict[str, Any]] = None,
        components_to_couple: Optional[tuple[ComponentInterface, ComponentInterface, str, str, str]] = None,
    ) -> ControlDecision:
        """Executes one minimal sufficient cognitive transformation governed by assessed need."""
        decision = self.assess_need(state)
        self.history.append(decision)

        if decision.directive in (
            ControlDirective.HALT_SUFFICIENT,
            ControlDirective.HALT_THREE_STRIKE_ABORT,
            ControlDirective.REQUIRES_USER_JUDGMENT,
            ControlDirective.REQUIRES_EXTERNAL_GATEWAY,
        ):
            return decision

        try:
            if decision.selected_nature == NatureType.EXPANSION:
                self.expansion.transform(state, max_branches=self.governor.max_expansion_branches)
                self.governor.record_attempt(True)

            elif decision.selected_nature == NatureType.COMPRESSION:
                if cases_to_compress:
                    self.compression.transform(cases_to_compress, state=state)
                    self.governor.record_attempt(True)
                else:
                    self.governor.record_attempt(False)

            elif decision.selected_nature == NatureType.GROUNDING:
                unverified = [h for h in state.hypotheses if h.confidence == "UNVERIFIED" and not h.is_invalidated]
                if unverified:
                    target = unverified[0]
                    self.governor.grounding_attempt_counter[target.hypothesis_id] = (
                        self.governor.grounding_attempt_counter.get(target.hypothesis_id, 0) + 1
                    )
                    self.grounding.evaluate_with_verifier(target, verifier_fn=verifier_fn, state=state)
                    self.governor.record_attempt(True)
                else:
                    self.governor.record_attempt(False)

            elif decision.selected_nature == NatureType.CONTINUITY:
                if world_transition:
                    self.continuity.reconcile(state, world_transition)
                    self.governor.record_attempt(True)
                else:
                    self.governor.record_attempt(True)

            elif decision.selected_nature == NatureType.COUPLING:
                if components_to_couple:
                    a, b, rel, cap, mech = components_to_couple
                    self.coupling.couple(a, b, rel, cap, mech, state=state)
                    self.governor.record_attempt(True)
                else:
                    self.governor.record_attempt(False)

        except Exception as exc:
            self.governor.record_attempt(False)
            raise exc

        return decision
