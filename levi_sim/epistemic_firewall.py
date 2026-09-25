"""
Epistemic Firewall for Levi Sim.

Strictly enforces cognitive boundaries between:
- User Statements (directives, intents)
- Levi Hypotheses (working models)
- Levi Beliefs (deductive inferences)
- Kageyoni Observations (gateway perceptions)
- Kageyoni Facts (verified cryptographic receipts)
- Dynamic Constraints (rejections that obsolete on state change)
- Hard Invariants (immutable physical laws / scars)
- Unknowns (explicit knowledge deficits)

Anti-omniscience: Model inferences can never masquerade as physical facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class EpistemicCategory(str, Enum):
    USER_INTENT = "USER_INTENT"
    KAGEYONI_FACT = "KAGEYONI_FACT"
    KAGEYONI_OBSERVATION = "KAGEYONI_OBSERVATION"
    LEVI_HYPOTHESIS = "LEVI_HYPOTHESIS"
    LEVI_BELIEF = "LEVI_BELIEF"
    DYNAMIC_CONSTRAINT = "DYNAMIC_CONSTRAINT"
    HARD_INVARIANT = "HARD_INVARIANT"
    UNKNOWN_DEFICIT = "UNKNOWN_DEFICIT"


@dataclass
class StructuredPredicate:
    """Predicate evaluating whether world state satisfies a prerequisite."""
    target_id: Optional[str] = None
    domain: Optional[str] = None
    field: str = "condition"
    expected_value: Any = None
    operator: str = "=="  # "==", "!=", "in", "active"

    def is_satisfied_by(self, records: list[dict[str, Any]]) -> bool:
        for r in records:
            if self.target_id and r.get("id") != self.target_id:
                continue
            if self.domain and r.get("domain") != self.domain:
                continue
            data = r.get("data", r)
            val = data.get(self.field)
            if self.operator == "==" and val == self.expected_value:
                return True
            if self.operator == "!=" and val != self.expected_value:
                return True
            if self.operator == "in" and isinstance(self.expected_value, (list, set, tuple)) and val in self.expected_value:
                return True
            if self.operator == "active" and val in ("active", "applied_active", "operational", "unlocked", "open"):
                return True
        return False


@dataclass
class DynamicConstraint:
    """An engine rejection that can become obsolete when prerequisite world state changes."""
    message: str
    rejection_class: str
    prerequisite_needed: Optional[str] = None
    required_predicate: Optional[StructuredPredicate] = None
    is_obsolete: bool = False
    obsoleted_by_event: Optional[str] = None

    def mark_obsolete(self, satisfying_event: str):
        self.is_obsolete = True
        self.obsoleted_by_event = satisfying_event


@dataclass
class EpistemicEntry:
    category: EpistemicCategory
    statement: str
    source: str
    receipt_hash: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EpistemicFirewall:
    """
    Manages Levi Sim's internal epistemic state with strict verification firewalls.
    """

    def __init__(self, external_scars: Optional[list[str]] = None):
        self.entries: list[EpistemicEntry] = []
        self.dynamic_constraints: list[DynamicConstraint] = []
        self.hard_invariants: list[str] = []
        self.scars: list[str] = list(external_scars or [])
        self.aligned_partners: Set[str] = set()

    def record_user_intent(self, raw_intent: str):
        self.entries.append(EpistemicEntry(
            category=EpistemicCategory.USER_INTENT,
            statement=raw_intent,
            source="user_interface",
        ))

    def record_observation(self, observation: str, source_record_id: str):
        self.entries.append(EpistemicEntry(
            category=EpistemicCategory.KAGEYONI_OBSERVATION,
            statement=observation,
            source=source_record_id,
        ))

    def record_verified_fact(self, fact: str, receipt_hash: str, source: str):
        self.entries.append(EpistemicEntry(
            category=EpistemicCategory.KAGEYONI_FACT,
            statement=fact,
            source=source,
            receipt_hash=receipt_hash,
        ))

    def record_hypothesis(self, hypothesis: str, rationale: str):
        self.entries.append(EpistemicEntry(
            category=EpistemicCategory.LEVI_HYPOTHESIS,
            statement=hypothesis,
            source="levi_abduction",
            metadata={"rationale": rationale},
        ))

    def record_belief(self, belief: str, basis: str):
        self.entries.append(EpistemicEntry(
            category=EpistemicCategory.LEVI_BELIEF,
            statement=belief,
            source="levi_deduction",
            metadata={"basis": basis},
        ))

    def record_unknown(self, deficit_description: str):
        self.entries.append(EpistemicEntry(
            category=EpistemicCategory.UNKNOWN_DEFICIT,
            statement=deficit_description,
            source="epistemic_audit",
        ))

    def record_engine_rejection(
        self,
        message: str,
        rejection_class: str,
        prerequisite_hint: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> DynamicConstraint | None:
        """
        Metabolize an engine rejection.
        - If PREREQUISITE_MISSING or TEMPORARY_STATE_BLOCK: store as DynamicConstraint (can obsolete).
        - If HARD_INVARIANT_VIOLATION: store as Hard Invariant and immutable scar.
        """
        if rejection_class in ("PREREQUISITE_MISSING", "TEMPORARY_STATE_BLOCK"):
            predicate = None
            if details:
                target_id = details.get("required_record") or details.get("target_id")
                field = details.get("field", "condition")
                expected = details.get("expected") or details.get("required_equals")
                if target_id or expected:
                    predicate = StructuredPredicate(
                        target_id=target_id,
                        field=field,
                        expected_value=expected,
                        operator="==" if expected is not None else "active",
                    )
            dc = DynamicConstraint(
                message=message,
                rejection_class=rejection_class,
                prerequisite_needed=prerequisite_hint or message,
                required_predicate=predicate,
            )
            self.dynamic_constraints.append(dc)
            self.entries.append(EpistemicEntry(
                category=EpistemicCategory.DYNAMIC_CONSTRAINT,
                statement=f"Temporary block: {message} (Prerequisite: {dc.prerequisite_needed})",
                source="kageyoni_gateway",
            ))
            return dc
        else:
            self.hard_invariants.append(message)
            scar = f"SCAR: Prohibited action rejected: '{message}'."
            if scar not in self.scars:
                self.scars.append(scar)
            self.entries.append(EpistemicEntry(
                category=EpistemicCategory.HARD_INVARIANT,
                statement=f"Hard physical invariant: {message}",
                source="kageyoni_gateway",
            ))
            return None

    def reconcile_world_state(
        self,
        newly_discovered_items: Optional[list[dict[str, Any]]] = None,
        granted_permissions: Optional[list[str]] = None,
        observations: Optional[list[dict[str, Any]]] = None,
    ):
        """
        Check if any active DynamicConstraints are obsoleted by new inventory, world state, or permissions.
        Evaluates structured predicates without scenario-specific lexical matching.
        """
        records = list(observations or []) + list(newly_discovered_items or [])
        granted = set(granted_permissions or [])

        for dc in self.dynamic_constraints:
            if dc.is_obsolete:
                continue

            # 1. Structured Predicate evaluation against physical observations
            if dc.required_predicate and dc.required_predicate.is_satisfied_by(records):
                dc.mark_obsolete(f"Predicate satisfied: {dc.required_predicate.target_id}.{dc.required_predicate.field}=={dc.required_predicate.expected_value}")
                continue

            # 2. Check if granted permissions satisfy authorization requirements
            if granted and dc.required_predicate and dc.required_predicate.target_id in granted:
                dc.mark_obsolete(f"Granted authorization by: {dc.required_predicate.target_id}")
                continue

            # 3. Fallback: if any observed record changed state to active/applied_active/operational/unlocked
            for r in records:
                data = r.get("data", r)
                cond = str(data.get("condition", ""))
                rid = r.get("id", "")
                if cond in ("applied_active", "operational", "unlocked", "open", "active"):
                    if rid and (rid in dc.message or (dc.prerequisite_needed and rid in dc.prerequisite_needed)):
                        dc.mark_obsolete(f"Prerequisite state transition observed: {rid}.condition='{cond}'")
                        break

    def get_active_constraints(self) -> list[str]:
        """Return list of active, non-obsolete constraints."""
        active = [dc.message for dc in self.dynamic_constraints if not dc.is_obsolete]
        active.extend(self.hard_invariants)
        return active

    def is_action_blocked(self, action_signature: str) -> tuple[bool, Optional[str]]:
        """Check if an action is currently blocked by an active constraint."""
        sig_lower = action_signature.lower()
        for dc in self.dynamic_constraints:
            if not dc.is_obsolete and any(k in sig_lower for k in dc.message.lower().split()):
                return True, f"Active dynamic constraint: {dc.message}"
        for hi in self.hard_invariants:
            if any(k in sig_lower for k in hi.lower().split()):
                return True, f"Hard invariant: {hi}"
        return False, None

    def export_summary(self) -> dict[str, Any]:
        """Export high-density structured summary of epistemic state."""
        return {
            "facts": [e.statement for e in self.entries if e.category == EpistemicCategory.KAGEYONI_FACT],
            "observations": [e.statement for e in self.entries if e.category == EpistemicCategory.KAGEYONI_OBSERVATION],
            "hypotheses": [e.statement for e in self.entries if e.category == EpistemicCategory.LEVI_HYPOTHESIS],
            "beliefs": [e.statement for e in self.entries if e.category == EpistemicCategory.LEVI_BELIEF],
            "unknowns": [e.statement for e in self.entries if e.category == EpistemicCategory.UNKNOWN_DEFICIT],
            "active_constraints": self.get_active_constraints(),
            "scars": list(self.scars),
            "aligned_partners": list(self.aligned_partners),
        }
