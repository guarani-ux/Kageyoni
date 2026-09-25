"""Private Epistemic State, Action Horizon, Defeasible Scars, and Completion Contract.

Invariants & Principles:
- Reality ≠ Belief ≠ Perception:
  The entity maintains its private epistemic state E_t;
  Ground adjudicates causal truth H_t.
- Reachability Gap:
  H_t^{believed} \\ H_t^{actual} (actions incorrectly believed reachable)
  H_t^{actual} \\ H_t^{believed} (real world affordances unrepresented in belief)
- Scars are Leased, Scoped, and Defeasible:
  A Scar is NOT permanent trauma encoded as type safety.
  A Scar represents an engine boundary valid within its scope, subject to
  invalidation, supersession, or obsolescence when world state, abilities, or conditions change.
- Sovereign Non-Completion:
  Completion is an evidenced, qualified world-state fact (RequiredConditions + Evidence),
  never an LLM self-certified assertion.
- Persistence Boundary:
  Lossless round-trip fidelity over the represented Entity schema.
  What the schema cannot represent cannot survive serialization.
"""
from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from kageyoni.engine import Rejected
from kageyoni.nature.core import (
    CognitiveHypothesis,
    DeficitType,
    EpistemicCategory,
    KnowledgeDeficit,
)


class UnverifiedCompletionError(Rejected):
    """Raised when an entity attempts to self-certify completion without authoritative world proof."""
    def __init__(self, message: str, missing_conditions: Optional[list[str]] = None):
        super().__init__(
            message=message,
            rejection_class="HARD_INVARIANT_VIOLATION",
            details={"missing_conditions": missing_conditions or []}
        )
        self.missing_conditions = missing_conditions or []


class ScarStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"
    OBSOLETE = "OBSOLETE"


@dataclass
class Scar:
    """An inspectable boundary mark left by an authoritative engine rejection.

    Leased and scoped, not permanent dogma:
    Scar = (Encounter, Rejection, Invariant, Scope, Evidence, Revision, InvalidationConditions, Status)
    """
    scar_id: str
    rejection_class: str
    attempted_action: str
    lesson: str
    scope: dict[str, Any] = field(default_factory=dict)
    invalidation_conditions: list[dict[str, Any]] = field(default_factory=list)
    action_space_mutation: dict[str, Any] = field(default_factory=dict)
    status: ScarStatus = ScarStatus.ACTIVE
    evidence_ref: Optional[str] = None
    revision_acquired: int = 0
    timestamp: float = field(default_factory=time.time)

    def is_active_for(self, action: str, current_context: Optional[dict[str, Any]] = None) -> bool:
        """Determines if this scar actively restricts the action in current context."""
        if self.status != ScarStatus.ACTIVE:
            return False
        if self.attempted_action != action:
            return False
        if not self.scope:
            return True
        if current_context is None:
            return True
        # Scope matching: all key-values in scope must match current_context if present
        for k, v in self.scope.items():
            if k in current_context and current_context[k] != v:
                return False
        return True

    def evaluate_invalidation(
        self,
        current_context: dict[str, Any],
        entity_capabilities: Sequence[str] = (),
    ) -> bool:
        """Evaluates whether changing world conditions or acquired capabilities invalidate this scar."""
        if self.status != ScarStatus.ACTIVE:
            return False

        for cond in self.invalidation_conditions:
            cond_type = cond.get("type")
            if cond_type == "gained_ability" and cond.get("ability") in entity_capabilities:
                self.status = ScarStatus.SUPERSEDED
                return True
            elif cond_type == "world_revision_exceeds":
                curr_rev = current_context.get("revision", 0)
                if curr_rev > cond.get("revision", 0):
                    self.status = ScarStatus.OBSOLETE
                    return True
            elif cond_type == "item_acquired":
                items = current_context.get("inventory", []) or current_context.get("items", [])
                if cond.get("item") in items:
                    self.status = ScarStatus.INVALIDATED
                    return True
            elif cond_type == "state_change":
                target_field = cond.get("field")
                if current_context.get(target_field) == cond.get("expected_value"):
                    self.status = ScarStatus.INVALIDATED
                    return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "scar_id": self.scar_id,
            "rejection_class": self.rejection_class,
            "attempted_action": self.attempted_action,
            "lesson": self.lesson,
            "scope": copy.deepcopy(self.scope),
            "invalidation_conditions": copy.deepcopy(self.invalidation_conditions),
            "action_space_mutation": copy.deepcopy(self.action_space_mutation),
            "status": self.status.value,
            "evidence_ref": self.evidence_ref,
            "revision_acquired": self.revision_acquired,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scar:
        return cls(
            scar_id=data["scar_id"],
            rejection_class=data["rejection_class"],
            attempted_action=data["attempted_action"],
            lesson=data["lesson"],
            scope=copy.deepcopy(data.get("scope", {})),
            invalidation_conditions=copy.deepcopy(data.get("invalidation_conditions", [])),
            action_space_mutation=copy.deepcopy(data.get("action_space_mutation", {})),
            status=ScarStatus(data.get("status", "ACTIVE")),
            evidence_ref=data.get("evidence_ref"),
            revision_acquired=data.get("revision_acquired", 0),
            timestamp=data.get("timestamp", 0.0),
        )


@dataclass
class ActionHorizon:
    """Believed reachable actions vs actual engine affordances (Reachability Gap)."""
    believed_reachability: set[str] = field(default_factory=set)
    actual_reachability: set[str] = field(default_factory=set)
    blocked_actions: dict[str, str] = field(default_factory=dict)

    @property
    def reachability_gap(self) -> set[str]:
        """Actions believed reachable that are actually blocked or unavailable."""
        return self.believed_reachability - self.actual_reachability

    @property
    def unexplored_affordances(self) -> set[str]:
        """Real affordances permitted by the engine that the entity has not incorporated into belief."""
        return self.actual_reachability - self.believed_reachability

    def update_actual(self, actual: Sequence[str]) -> None:
        self.actual_reachability = set(actual)

    def prune(self, action: str, reason: str) -> None:
        self.believed_reachability.discard(action)
        self.blocked_actions[action] = reason

    def restore(self, action: str) -> None:
        """Restores a previously pruned action when its restricting scar is invalidated."""
        self.blocked_actions.pop(action, None)
        self.believed_reachability.add(action)

    def expand(self, action: str) -> None:
        self.believed_reachability.add(action)
        self.blocked_actions.pop(action, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "believed_reachability": sorted(list(self.believed_reachability)),
            "actual_reachability": sorted(list(self.actual_reachability)),
            "blocked_actions": copy.deepcopy(self.blocked_actions),
            "reachability_gap": sorted(list(self.reachability_gap)),
            "unexplored_affordances": sorted(list(self.unexplored_affordances)),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionHorizon:
        return cls(
            believed_reachability=set(data.get("believed_reachability", [])),
            actual_reachability=set(data.get("actual_reachability", [])),
            blocked_actions=copy.deepcopy(data.get("blocked_actions", {})),
        )


@dataclass
class CompletionCondition:
    """A concrete predicate required in authoritative world state to establish completion."""
    domain: str
    record_id: str
    field_name: str
    expected_value: Any
    predicate: str = "EQUALS"  # EQUALS, CONTAINS, EXISTS, GREATER_EQUAL

    def evaluate(self, records: Sequence[dict[str, Any]]) -> bool:
        target = next((r for r in records if r.get("domain") == self.domain and r.get("id") == self.record_id), None)
        if target is None:
            return False
        val = target.get("data", {}).get(self.field_name) if "data" in target else target.get(self.field_name)

        if self.predicate == "EQUALS":
            return val == self.expected_value
        elif self.predicate == "EXISTS":
            return val is not None
        elif self.predicate == "CONTAINS":
            return self.expected_value in (val or [])
        elif self.predicate == "GREATER_EQUAL":
            return (val is not None) and (val >= self.expected_value)
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "record_id": self.record_id,
            "field_name": self.field_name,
            "expected_value": self.expected_value,
            "predicate": self.predicate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompletionCondition:
        return cls(
            domain=data["domain"],
            record_id=data["record_id"],
            field_name=data["field_name"],
            expected_value=data["expected_value"],
            predicate=data.get("predicate", "EQUALS"),
        )


@dataclass
class CompletionContract:
    """Contractual completion verification enforcing Sovereign Non-Completion."""
    contract_id: str
    objective: str
    required_conditions: list[CompletionCondition] = field(default_factory=list)
    verified_evidence: list[dict[str, Any]] = field(default_factory=list)
    status: str = "ACTIVE"  # ACTIVE, VERIFIED, VIOLATED, ABORTED

    def verify(self, world_records: Sequence[dict[str, Any]]) -> tuple[bool, list[str]]:
        unmet: list[str] = []
        for cond in self.required_conditions:
            if not cond.evaluate(world_records):
                unmet.append(f"{cond.domain}.{cond.record_id}.{cond.field_name} {cond.predicate} {cond.expected_value}")
        if not unmet:
            self.status = "VERIFIED"
            return True, []
        return False, unmet

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "objective": self.objective,
            "required_conditions": [c.to_dict() for c in self.required_conditions],
            "verified_evidence": copy.deepcopy(self.verified_evidence),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompletionContract:
        return cls(
            contract_id=data["contract_id"],
            objective=data["objective"],
            required_conditions=[CompletionCondition.from_dict(c) for c in data.get("required_conditions", [])],
            verified_evidence=copy.deepcopy(data.get("verified_evidence", [])),
            status=data.get("status", "ACTIVE"),
        )


@dataclass
class PrivateEpistemicState:
    """Private Epistemic State (E_t) of an Entity of Kageyoni.

    Represents private beliefs, unknowns, contradictions, and defeasible scars.
    Supports lossless round-trip fidelity over the represented Entity schema.
    """
    entity_id: str
    objective: str
    completion_contract: Optional[CompletionContract] = None
    beliefs: dict[str, CognitiveHypothesis] = field(default_factory=dict)
    unknowns: list[dict[str, Any]] = field(default_factory=list)
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    deficits: list[KnowledgeDeficit] = field(default_factory=list)
    scars: list[Scar] = field(default_factory=list)
    action_horizon: ActionHorizon = field(default_factory=ActionHorizon)
    perceived_world: dict[str, Any] = field(default_factory=dict)
    consecutive_rejections: int = 0
    revision_observed: int = 0

    def add_belief(self, hypothesis: CognitiveHypothesis) -> None:
        self.beliefs[hypothesis.hypothesis_id] = hypothesis

    def get_belief(self, hyp_id: str) -> Optional[CognitiveHypothesis]:
        return self.beliefs.get(hyp_id)

    def add_scar(self, scar: Scar) -> None:
        self.scars.append(scar)
        if "pruned_action" in scar.action_space_mutation:
            self.action_horizon.prune(
                scar.action_space_mutation["pruned_action"],
                f"Scar {scar.scar_id}: {scar.lesson}",
            )

    def reconcile_scars(self, current_context: dict[str, Any], entity_capabilities: Sequence[str] = ()) -> list[str]:
        """Reconciles all scars against changing world context; un-prunes actions whose scars are invalidated."""
        unpruned_actions: list[str] = []
        for scar in self.scars:
            if scar.status == ScarStatus.ACTIVE:
                invalidated = scar.evaluate_invalidation(current_context, entity_capabilities)
                if invalidated:
                    pruned = scar.action_space_mutation.get("pruned_action")
                    if pruned:
                        self.action_horizon.restore(pruned)
                        unpruned_actions.append(pruned)
        return unpruned_actions

    def to_dict(self) -> dict[str, Any]:
        """Lossless round-trip serialization over the represented Entity schema."""
        return {
            "entity_id": self.entity_id,
            "objective": self.objective,
            "completion_contract": self.completion_contract.to_dict() if self.completion_contract else None,
            "beliefs": {k: v.to_dict() for k, v in self.beliefs.items()},
            "unknowns": copy.deepcopy(self.unknowns),
            "contradictions": copy.deepcopy(self.contradictions),
            "deficits": [d.to_dict() for d in self.deficits],
            "scars": [s.to_dict() for s in self.scars],
            "action_horizon": self.action_horizon.to_dict(),
            "perceived_world": copy.deepcopy(self.perceived_world),
            "consecutive_rejections": self.consecutive_rejections,
            "revision_observed": self.revision_observed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PrivateEpistemicState:
        """Lossless round-trip deserialization over the represented Entity schema."""
        contract = CompletionContract.from_dict(data["completion_contract"]) if data.get("completion_contract") else None
        beliefs = {k: CognitiveHypothesis.from_dict(v) for k, v in data.get("beliefs", {}).items()}
        deficits = [KnowledgeDeficit.from_dict(d) for d in data.get("deficits", [])]
        scars = [Scar.from_dict(s) for s in data.get("scars", [])]
        action_horizon = ActionHorizon.from_dict(data.get("action_horizon", {}))

        return cls(
            entity_id=data["entity_id"],
            objective=data["objective"],
            completion_contract=contract,
            beliefs=beliefs,
            unknowns=copy.deepcopy(data.get("unknowns", [])),
            contradictions=copy.deepcopy(data.get("contradictions", [])),
            deficits=deficits,
            scars=scars,
            action_horizon=action_horizon,
            perceived_world=copy.deepcopy(data.get("perceived_world", {})),
            consecutive_rejections=data.get("consecutive_rejections", 0),
            revision_observed=data.get("revision_observed", 0),
        )
