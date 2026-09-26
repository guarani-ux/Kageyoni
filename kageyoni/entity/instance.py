"""Persistent Entity Instance for Kageyoni.

Decouples durable entity state from ephemeral LLM inference sessions:
- The Entity and its unfinished objective exist independently of LLM context windows.
- Any model acts merely as a temporary cognitive engine inhabiting the Entity.
- State serialization and reconciliation preserves scars, beliefs, and horizons across sessions
  with lossless round-trip fidelity over the represented Entity schema.
"""
from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from kageyoni.engine import Rejected
from kageyoni.nature.core import (
    CognitiveHypothesis,
    DeficitType,
    EpistemicCategory,
    KnowledgeDeficit,
    NatureType,
)
from .models import EntitySpecification
from .state import (
    ActionHorizon,
    CompletionCondition,
    CompletionContract,
    PrivateEpistemicState,
    Scar,
    ScarStatus,
    UnverifiedCompletionError,
)


class EntityInstance:
    """An instantiated, persistent Entity of Kageyoni."""

    def __init__(
        self,
        spec: EntitySpecification,
        initial_objective: str,
        completion_contract: Optional[CompletionContract] = None,
        epistemic_state: Optional[PrivateEpistemicState] = None,
    ):
        self.spec = spec
        if epistemic_state is not None:
            self.state = epistemic_state
        else:
            self.state = PrivateEpistemicState(
                entity_id=spec.entity_id,
                objective=initial_objective,
                completion_contract=completion_contract,
            )
            # Initialize believed reachability from capability verbs
            for verb in self.spec.capability_model.supported_verbs:
                self.state.action_horizon.expand(verb)

    @property
    def entity_id(self) -> str:
        return self.spec.entity_id

    @property
    def objective(self) -> str:
        return self.state.objective

    def update_actual_reachability(self, actual_verbs: Sequence[str]) -> None:
        """Update actual reachability discovered from Kageyoni world engine."""
        self.state.action_horizon.update_actual(actual_verbs)

    def reconcile_perception(self, perceived_world: dict[str, Any]) -> None:
        """Reconcile observed world slice into private epistemic state."""
        self.state.perceived_world = copy.deepcopy(perceived_world)
        self.state.revision_observed = perceived_world.get("revision", self.state.revision_observed)

        # Update available routes/items/NPCs into beliefs
        for item in perceived_world.get("perceived_items", []):
            hyp_id = f"item-belief-{item['id']}"
            if hyp_id not in self.state.beliefs:
                self.state.add_belief(CognitiveHypothesis(
                    hypothesis_id=hyp_id,
                    statement=f"Item {item.get('name')} is present with condition {item.get('condition')}",
                    epistemic_status=EpistemicCategory.EVIDENCE_SUPPORTED_CLAIM,
                    confidence="HIGH",
                ))

        # Update available physical affordances into ActionHorizon
        available = perceived_world.get("available_affordances", [])
        if available:
            self.state.action_horizon.update_actual(available)
            for act in available:
                if act not in self.state.action_horizon.blocked_actions:
                    self.state.action_horizon.expand(act)

        # Prune demonstrated negative constraints from ActionHorizon
        for restricted in perceived_world.get("restricted_actions", []):
            if restricted in self.state.action_horizon.believed_reachability:
                loc = perceived_world.get("current_location") or "current_scope"
                self.state.action_horizon.prune(
                    restricted,
                    f"Active negative constraint in {loc}",
                )

    def reconcile_scars(self, current_context: dict[str, Any]) -> list[str]:
        """Re-evaluates active scars against current world context and restores invalidated affordances."""
        active_caps = list(self.spec.capability_model.active_capabilities.keys())
        return self.state.reconcile_scars(current_context, active_caps)

    def evaluate_completion(self, world_records: Sequence[dict[str, Any]]) -> dict[str, Any]:
        """
        Evaluate objective completion contract against authoritative world records.
        Sovereign Non-Completion: Completion can never be declared purely in narration.
        """
        if not self.state.completion_contract:
            raise UnverifiedCompletionError(
                f"Entity '{self.entity_id}' cannot claim completion without a registered CompletionContract.",
                missing_conditions=["ContractMissing"],
            )

        ok, unmet = self.state.completion_contract.verify(world_records)
        if not ok:
            raise UnverifiedCompletionError(
                f"Sovereign Non-Completion: Contract '{self.state.completion_contract.contract_id}' "
                f"unverified. Missing conditions: {unmet}",
                missing_conditions=unmet,
            )

        return {
            "status": "COMPLETED",
            "contract_id": self.state.completion_contract.contract_id,
            "objective": self.state.objective,
            "evidence": copy.deepcopy(self.state.completion_contract.verified_evidence),
        }

    def metabolize_rejection(
        self,
        rejection: dict[str, Any],
        scope: Optional[dict[str, Any]] = None,
        invalidation_conditions: Optional[list[dict[str, Any]]] = None,
    ) -> Scar:
        """
        Rejection Metabolization:
        Translates raw engine rejection codes into structured, defeasible scars
        with explicit scopes and invalidation conditions.
        """
        rejection_class = rejection.get("rejection_class", "HARD_INVARIANT_VIOLATION")
        msg = rejection.get("message", "Unknown rejection")
        action = rejection.get("attempted_action", "unknown_action")
        curr_rev = self.state.revision_observed

        scar_id = rejection.get("scar_id") or f"scar-{self.entity_id}-{uuid.uuid4().hex[:6]}"
        lesson = ""
        action_mutation: dict[str, Any] = {}
        inv_conds = list(invalidation_conditions or [])
        scar_scope = dict(scope or {})

        if rejection_class in ("HARD_INVARIANT_VIOLATION", "NEGATIVE_CONSTRAINT_VIOLATION"):
            lesson = f"Physical law invariant violated by '{action}' within scope {scar_scope}: {msg}"
            action_mutation = {"pruned_action": action, "requires_scope_invalidation": True}
            # Open semantic deficit to reframe approach
            self.state.deficits.append(KnowledgeDeficit(
                deficit_type=DeficitType.SEMANTIC_BINDING_DEFICIT,
                description=f"Action '{action}' hit hard invariant within scope {scar_scope}. Re-evaluation required.",
                impacted_representation=action,
                required_to_resolve="Re-evaluate physical boundary constraints",
            ))

        elif rejection_class == "PREREQUISITE_MISSING":
            lesson = f"Prerequisite requirement missing for '{action}': {msg}"
            action_mutation = {"pruned_action": action, "requires_prerequisite": True}
            # If missing key or item, add invalidation condition when that item is acquired
            if not inv_conds:
                inv_conds.append({"type": "state_change", "field": "prerequisite_acquired", "expected_value": True})
            self.state.deficits.append(KnowledgeDeficit(
                deficit_type=DeficitType.INPUT_DEFICIT,
                description=f"Missing prerequisite for '{action}': {msg}",
                impacted_representation=action,
                required_to_resolve="Acquire missing prerequisite",
            ))

        elif rejection_class == "INSUFFICIENT_AUTHORITY":
            lesson = f"Authority boundary encountered for '{action}': {msg}"
            action_mutation = {"pruned_action": action, "requires_authority": True}
            if not inv_conds:
                inv_conds.append({"type": "state_change", "field": "authority_granted", "expected_value": True})
            self.state.deficits.append(KnowledgeDeficit(
                deficit_type=DeficitType.VERIFIER_DEFICIT,
                description=f"Lacks authority for '{action}'. Delegation or alignment required.",
                impacted_representation=action,
                required_to_resolve="Obtain authority warrant or delegation",
            ))

        elif rejection_class == "TEMPORARY_STATE_BLOCK":
            lesson = f"Temporary state timing block for '{action}': {msg}"
            action_mutation = {"retry_after_sync": True}
            if not inv_conds:
                inv_conds.append({"type": "world_revision_exceeds", "revision": curr_rev})

        elif rejection_class == "MALFORMED_REQUEST":
            lesson = f"Representation schema invalid for '{action}': {msg}"
            action_mutation = {"repair_schema": True}
            self.state.deficits.append(KnowledgeDeficit(
                deficit_type=DeficitType.SEMANTIC_BINDING_DEFICIT,
                description=f"Malformed proposal structure for '{action}': {msg}",
                impacted_representation=action,
                required_to_resolve="Repair proposal data schema",
            ))

        scar = Scar(
            scar_id=scar_id,
            rejection_class=rejection_class,
            attempted_action=action,
            lesson=lesson,
            scope=scar_scope,
            invalidation_conditions=inv_conds,
            action_space_mutation=action_mutation,
            status=ScarStatus.ACTIVE,
            revision_acquired=curr_rev,
        )

        self.state.add_scar(scar)
        self.state.consecutive_rejections += 1
        return scar

    def reset_rejections(self) -> None:
        self.state.consecutive_rejections = 0

    def encounter(self, gateway: Any, affordance: str) -> dict[str, Any]:
        """
        Closed-loop encounter step:
        Directly collides intent against Ground through the Gateway.
        1. Checks believed reachability (fails closed at epistemic membrane if unrepresented or blocked).
        2. Enacts affordance directly against Ground via gateway.enact().
        3. If Ground rejects, automatically metabolizes rejection into private epistemic state & scars.
        4. If Ground accepts, reconciles perception and resets rejections.
        """
        # 1. Epistemic gate: fail closed if action is outside believed reachability
        if affordance not in self.state.action_horizon.believed_reachability:
            reason = self.state.action_horizon.blocked_actions.get(
                affordance, f"Action '{affordance}' is outside believed reachability."
            )
            return {
                "success": False,
                "error_type": "EPISTEMIC_HORIZON_REJECTION",
                "rejection_class": "NEGATIVE_CONSTRAINT_VIOLATION",
                "message": reason,
                "attempted_action": affordance,
            }

        # 2. Enact directly against Gateway
        result = gateway.enact(self.entity_id, affordance)

        # 3. Metabolize rejection or reconcile success
        if not result.get("success"):
            loc = self.state.perceived_world.get("current_location")
            self.metabolize_rejection(
                result,
                scope={"location": loc} if loc else None,
            )
        else:
            self.reconcile_perception(gateway.inspect_environment(self.entity_id))
            self.reset_rejections()

        return result

    def select_affordance(self) -> Optional[str]:
        """
        Differentiates reachable affordances based on teleological alignment
        with the CompletionContract and resolution of active KnowledgeDeficits.
        """
        reachable = sorted(list(self.state.action_horizon.believed_reachability))
        if not reachable:
            return None
        if len(reachable) == 1:
            return reachable[0]

        situated = {
            a["action_name"]: a for a in self.state.perceived_world.get("situated_affordances", [])
        }

        # 1. Target criteria from unmet CompletionContract conditions
        target_locations = set()
        if self.state.completion_contract:
            for cond in self.state.completion_contract.required_conditions:
                if cond.domain == "character" and cond.record_id == self.entity_id and cond.field_name == "location":
                    target_locations.add(cond.expected_value)

        # 2. Deficit targets
        deficit_representations = {
            d.impacted_representation for d in self.state.deficits if d.impacted_representation
        }

        def score(action_name: str) -> tuple[int, str]:
            meta = situated.get(action_name, {})
            dest = meta.get("destination")

            # Tier 1: Direct CompletionCondition advance
            if dest and dest in target_locations:
                return (100, action_name)

            # Tier 2: Deficit resolution / information seeking
            if any(dr in action_name or (dest and dr in dest) for dr in deficit_representations):
                return (50, action_name)

            # Tier 3: Inert valid affordance
            return (1, action_name)

        ranked = sorted(reachable, key=score, reverse=True)
        return ranked[0]

    def step(self, gateway: Any) -> dict[str, Any]:
        """
        Autonomous encounter cycle:
        Selects highest-relevance affordance and executes an encounter against Ground.
        """
        affordance = self.select_affordance()
        if not affordance:
            return {
                "success": False,
                "error_type": "NO_VIABLE_AFFORDANCE",
                "message": "Action horizon contains no reachable affordances to select.",
            }
        return self.encounter(gateway, affordance)

    def serialize(self) -> dict[str, Any]:
        """Lossless round-trip serialization over the represented Entity schema."""
        return {
            "specification": self.spec.to_dict(),
            "epistemic_state": self.state.to_dict(),
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> EntityInstance:
        """Lossless round-trip deserialization over the represented Entity schema."""
        spec = EntitySpecification.from_dict(data["specification"])
        state = PrivateEpistemicState.from_dict(data["epistemic_state"])
        return cls(
            spec=spec,
            initial_objective=state.objective,
            completion_contract=state.completion_contract,
            epistemic_state=state,
        )
