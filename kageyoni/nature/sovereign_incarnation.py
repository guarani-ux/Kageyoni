"""TECHNIQUE: SOVEREIGN INCARNATION

Class: Composite Entity Technique
Status: Candidate / Qualified

Purpose: Allow an Entity of Kageyoni to convert an objective into sustained, situated agency
inside Kageyoni while never acquiring authority to declare its cognition true or directly
rewrite world state.

Elemental & Nature Dynamics:
- Elements (Cloud, Water, Fire, Ground) represent system and interaction dynamics
  (environmental forces, volatility, friction, substrate stability).
- Natures (Expansion, Compression, Grounding, Continuity, Coupling) represent executable
  cognitive transformations.
- Elements and Natures are decoupled: Grounding participates in Ground, but is not Fire;
  Compression can operate on Cloud representations, but is not Ground itself.

The defining transformation:
Objective + Entity + World → Perception <-> Epistemic State <-> Action Horizon <-> Causal Intervention
                             → World Mutation or Rejection → Differentiation → Continuity

Core Invariants:
1. Δcog ≠ Δworld: Cognitive exploration never mutates physical world state directly.
2. Reality ≠ Belief ≠ Perception: Ground adjudicates causal truth (H_t); entity acts on private state (E_t).
3. Reachability Gap: H_t^{believed} \\ H_t^{actual} and H_t^{actual} \\ H_t^{believed}.
4. Scars are Leased, Scoped, and Defeasible:
   Rejections do not encode permanent trauma as type safety; Scars are valid within scope
   and become SUPERSEDED, INVALIDATED, or OBSOLETE when conditions or capabilities change.
5. Contextual Nature Weights: W_nature = f(Disposition, Experience, Situation, Objective, Deficits).
6. Sovereign Non-Completion: Completion requires authoritative world evidence (RequiredConditions + Evidence).
7. Persistence Boundary: Lossless round-trip fidelity over the represented Entity schema.
"""
from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Set

from kageyoni.engine import Rejected
from kageyoni.gateway import BoundedKageyoniGateway
from .compression import Compression
from .continuity import Continuity
from .control import (
    ControlDecision,
    ControlDirective,
    FailureModeGovernor,
    TransformationControl,
)
from .core import (
    CognitiveDelta,
    CognitiveHypothesis,
    CognitiveState,
    DeficitType,
    EpistemicCategory,
    KnowledgeDeficit,
    NatureType,
)
from .coupling import Coupling
from .expansion import Expansion
from .grounding import Grounding
from .techniques import Technique

if TYPE_CHECKING:
    from kageyoni.entity.instance import EntityInstance
    from kageyoni.entity.state import Scar


class BoundaryViolationError(ValueError):
    """Raised when a proposed intent violates an uncompromised entity personality boundary."""
    pass


class SovereignNonCompletionError(Rejected):
    """Raised when an entity or model attempts self-certified completion without world proof."""
    def __init__(self, message: str, missing_conditions: Optional[list[str]] = None):
        super().__init__(
            message=message,
            rejection_class="HARD_INVARIANT_VIOLATION",
            details={"missing_conditions": missing_conditions or []},
        )
        self.missing_conditions = missing_conditions or []


@dataclass
class IncarnationStepResult:
    """The inspectable output of one step of Sovereign Incarnation."""
    step_id: str
    entity_id: str
    stage: str  # PERCEIVED, ORIENTED, INTENT_FORMED, ACTED, DIFFERENTIATED, COMPLETED, HALTED
    directive: ControlDirective
    action_proposed: Optional[dict[str, Any]] = None
    gateway_result: Optional[dict[str, Any]] = None
    scar_inflicted: Optional[Any] = None
    reachability_gap: set[str] = field(default_factory=set)
    unexplored_affordances: set[str] = field(default_factory=set)
    is_completed: bool = False
    contextual_weights: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "entity_id": self.entity_id,
            "stage": self.stage,
            "directive": self.directive.value,
            "action_proposed": copy.deepcopy(self.action_proposed),
            "gateway_result": copy.deepcopy(self.gateway_result),
            "scar_inflicted": self.scar_inflicted.to_dict() if hasattr(self.scar_inflicted, "to_dict") else None,
            "reachability_gap": sorted(list(self.reachability_gap)),
            "unexplored_affordances": sorted(list(self.unexplored_affordances)),
            "is_completed": self.is_completed,
            "contextual_weights": copy.deepcopy(self.contextual_weights),
            "details": copy.deepcopy(self.details),
        }


class SovereignIncarnation(Technique):
    """Composite Entity Technique realizing sustained, governed agency inside Kageyoni."""

    def __init__(
        self,
        expansion: Optional[Expansion] = None,
        compression: Optional[Compression] = None,
        grounding: Optional[Grounding] = None,
        continuity: Optional[Continuity] = None,
        coupling: Optional[Coupling] = None,
        control: Optional[TransformationControl] = None,
    ):
        self.technique_id = "technique.sovereign_incarnation"
        self.name = "Sovereign Incarnation"
        self.underlying_natures = [
            NatureType.EXPANSION,
            NatureType.COMPRESSION,
            NatureType.GROUNDING,
            NatureType.CONTINUITY,
            NatureType.COUPLING,
        ]
        self.expansion = expansion or Expansion()
        self.compression = compression or Compression()
        self.grounding = grounding or Grounding()
        self.continuity = continuity or Continuity()
        self.coupling = coupling or Coupling()
        self.control = control or TransformationControl()

    def execute_lifecycle_step(
        self,
        entity: EntityInstance,
        gateway: BoundedKageyoniGateway,
        proposed_action: Optional[dict[str, Any]] = None,
        claim_completion_requested: bool = False,
    ) -> IncarnationStepResult:
        """
        Executes one full cycle of the non-linear Sovereign Incarnation lifecycle:
        PERCEIVE → ORIENT → FORM_INTENT → ACT → ENCOUNTER → DIFFERENTIATE → CONTINUE / HALT
        """
        step_id = f"step-inc-{uuid.uuid4().hex[:8]}"

        # =====================================================================
        # 1. PERCEIVE
        # =====================================================================
        env = gateway.inspect_environment(entity.entity_id)
        caps = gateway.discover_capabilities(entity.entity_id)

        # Update entity reachability and perceived world slice
        actual_verbs = caps.get("core_actions", [])
        entity.update_actual_reachability(actual_verbs)
        entity.reconcile_perception(env)

        # =====================================================================
        # 2. ORIENT
        # =====================================================================
        # Re-evaluate active scars: if world state or capabilities changed, un-prune actions!
        entity.reconcile_scars(env)

        reachability_gap = entity.state.action_horizon.reachability_gap
        unexplored = entity.state.action_horizon.unexplored_affordances

        # Contextual Nature Weighting: W_nature = f(Disposition, Experience, Situation, Objective, Deficits)
        situation_factors = {
            "has_unexplored_routes": bool(env.get("perceived_routes")),
            "high_uncertainty": len(entity.state.unknowns) > 0,
            "has_contradictions": len(entity.state.contradictions) > 0,
            "revision_changed": env.get("revision", 0) > entity.state.revision_observed,
            "copresent_allies": len(env.get("perceived_npcs", [])) > 0,
        }
        recent_scars_count = len([s for s in entity.state.scars if getattr(s, "status", None) == "ACTIVE"])
        contextual_weights = entity.spec.reasoning_model.compute_contextual_weights(
            current_situation=situation_factors,
            deficits=entity.state.deficits,
            recent_scars_count=recent_scars_count,
        )
        serializable_weights = {k.value: v for k, v in contextual_weights.items()}

        # Check if completion is being asserted
        if claim_completion_requested:
            from kageyoni.entity.state import UnverifiedCompletionError
            try:
                world_records = gateway.query_records(entity.entity_id)
                comp_result = entity.evaluate_completion(world_records)
                return IncarnationStepResult(
                    step_id=step_id,
                    entity_id=entity.entity_id,
                    stage="COMPLETED",
                    directive=ControlDirective.HALT_SUFFICIENT,
                    is_completed=True,
                    reachability_gap=reachability_gap,
                    unexplored_affordances=unexplored,
                    contextual_weights=serializable_weights,
                    details=comp_result,
                )
            except UnverifiedCompletionError as exc:
                # Sovereign Non-Completion: Narrative assertion is NOT world evidence!
                entity.metabolize_rejection({
                    "rejection_class": "HARD_INVARIANT_VIOLATION",
                    "message": exc.message,
                    "attempted_action": "claim_completion",
                }, scope=env)
                raise SovereignNonCompletionError(exc.message, exc.missing_conditions)

        # Check 3-Strike Governor
        if entity.state.consecutive_rejections >= entity.spec.reasoning_model.max_consecutive_failures:
            return IncarnationStepResult(
                step_id=step_id,
                entity_id=entity.entity_id,
                stage="HALTED",
                directive=ControlDirective.HALT_THREE_STRIKE_ABORT,
                reachability_gap=reachability_gap,
                unexplored_affordances=unexplored,
                contextual_weights=serializable_weights,
                details={
                    "reason": f"Halted by 3-Strike Governor ({entity.state.consecutive_rejections} consecutive rejections).",
                    "recent_scars": [s.to_dict() for s in entity.state.scars[-3:]],
                },
            )

        # =====================================================================
        # 3. FORM INTENT & ACT (If proposed)
        # =====================================================================
        if proposed_action is None:
            # Pure cognitive perception and differentiation step
            return IncarnationStepResult(
                step_id=step_id,
                entity_id=entity.entity_id,
                stage="DIFFERENTIATED",
                directive=ControlDirective.PROCEED,
                reachability_gap=reachability_gap,
                unexplored_affordances=unexplored,
                contextual_weights=serializable_weights,
                details={
                    "consecutive_rejections": entity.state.consecutive_rejections,
                    "deficits_open": len(entity.state.deficits),
                    "scars_count": len(entity.state.scars),
                },
            )

        action_intent = proposed_action

        # Check personality boundary violation
        narrative = action_intent.get("narrative", "")
        if entity.spec.personality_model.violates_boundary(narrative):
            raise BoundaryViolationError(
                f"Action '{narrative}' violates uncompromising boundary of {entity.spec.name}."
            )

        # Check against active, scoped scars (defeats dogma, respects active scope)
        action_name = action_intent.get("action_name") or action_intent.get("kind", "action")
        for scar in entity.state.scars:
            if scar.is_active_for(action_name, env):
                raise Rejected(
                    f"Action '{action_name}' is currently blocked within scope by Scar '{scar.scar_id}': {scar.lesson}",
                    rejection_class=scar.rejection_class,
                )

        # =====================================================================
        # 4. ACT & 5. ENCOUNTER
        # =====================================================================
        request_id = f"req-{entity.entity_id}-{uuid.uuid4().hex[:6]}"
        changes = action_intent.get("changes", [])
        kind = action_intent.get("kind", "action")

        gateway_res = gateway.attempt_action(
            avatar_id=entity.entity_id,
            request_id=request_id,
            narrative=narrative,
            changes=changes,
            kind=kind,
        )

        # =====================================================================
        # 6. DIFFERENTIATE (Metabolize Outcome)
        # =====================================================================
        scar_inflicted: Optional[Any] = None
        directive = ControlDirective.PROCEED

        if gateway_res.get("success"):
            # Success! Grounding corroborated
            entity.reset_rejections()
            entity.state.revision_observed = gateway_res.get("revision", entity.state.revision_observed)

            # Record corroborated action in beliefs
            entity.state.add_belief(CognitiveHypothesis(
                hypothesis_id=f"hyp-act-{request_id}",
                statement=f"Executed '{narrative}' committed at revision {gateway_res.get('revision')}",
                epistemic_status=EpistemicCategory.EVIDENCE_SUPPORTED_CLAIM,
                confidence="HIGH",
            ))

            # Check if completion contract is now fulfilled
            if entity.state.completion_contract:
                try:
                    world_records = gateway.query_records(entity.entity_id)
                    ok, unmet = entity.state.completion_contract.verify(world_records)
                    if ok:
                        return IncarnationStepResult(
                            step_id=step_id,
                            entity_id=entity.entity_id,
                            stage="COMPLETED",
                            directive=ControlDirective.HALT_SUFFICIENT,
                            action_proposed=action_intent,
                            gateway_result=gateway_res,
                            is_completed=True,
                            reachability_gap=reachability_gap,
                            unexplored_affordances=unexplored,
                            contextual_weights=serializable_weights,
                            details={"contract_verified": True},
                        )
                except Exception:
                    pass

        else:
            # Rejection Metabolization with scope!
            rejection_data = {
                "rejection_class": gateway_res.get("rejection_class", "HARD_INVARIANT_VIOLATION"),
                "message": gateway_res.get("message", "Gateway action rejected"),
                "attempted_action": action_name,
            }
            current_scope = {
                "location": env.get("current_location"),
                "scene": env.get("perceived_scene", {}).get("name") if env.get("perceived_scene") else None,
            }
            scar_inflicted = entity.metabolize_rejection(rejection_data, scope=current_scope)

            if entity.state.consecutive_rejections >= entity.spec.reasoning_model.max_consecutive_failures:
                directive = ControlDirective.HALT_THREE_STRIKE_ABORT
            else:
                directive = ControlDirective.SWITCH_NATURE

        # =====================================================================
        # 7. CONTINUE / EMIT RESULT
        # =====================================================================
        return IncarnationStepResult(
            step_id=step_id,
            entity_id=entity.entity_id,
            stage="DIFFERENTIATED" if gateway_res.get("success") else "REJECTED_METABOLIZED",
            directive=directive,
            action_proposed=action_intent,
            gateway_result=gateway_res,
            scar_inflicted=scar_inflicted,
            reachability_gap=entity.state.action_horizon.reachability_gap,
            unexplored_affordances=entity.state.action_horizon.unexplored_affordances,
            is_completed=False,
            contextual_weights=serializable_weights,
            details={
                "consecutive_rejections": entity.state.consecutive_rejections,
                "deficits_open": len(entity.state.deficits),
                "scars_count": len(entity.state.scars),
            },
        )
