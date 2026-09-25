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
class DynamicConstraint:
    """An engine rejection that can become obsolete when prerequisite world state changes."""
    message: str
    rejection_class: str
    prerequisite_needed: Optional[str] = None
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
    ) -> DynamicConstraint | None:
        """
        Metabolize an engine rejection.
        - If PREREQUISITE_MISSING or TEMPORARY_STATE_BLOCK: store as DynamicConstraint (can obsolete).
        - If HARD_INVARIANT_VIOLATION: store as Hard Invariant and immutable scar.
        """
        if rejection_class in ("PREREQUISITE_MISSING", "TEMPORARY_STATE_BLOCK"):
            dc = DynamicConstraint(
                message=message,
                rejection_class=rejection_class,
                prerequisite_needed=prerequisite_hint or message,
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

    def reconcile_world_state(self, newly_discovered_items: list[dict[str, Any]], granted_permissions: list[str]):
        """
        Check if any active DynamicConstraints are obsoleted by new inventory or granted permissions.
        Requirement 7: Do NOT permanently seal dynamic constraints that might change when world state changes.
        """
        for dc in self.dynamic_constraints:
            if dc.is_obsolete:
                continue
            prereq = (dc.prerequisite_needed or "").lower()

            # Check if sterilization or decontamination prerequisite is satisfied
            if "steriliz" in prereq or "quarantine" in prereq:
                applied = any(item.get("condition") == "applied_active" for item in newly_discovered_items)
                if applied:
                    dc.mark_obsolete("Sterilization decontaminant applied and active")

            # Check if authorization prerequisite is satisfied
            if "authoriz" in prereq or "certif" in prereq or "permission" in prereq:
                has_permission = bool(granted_permissions)
                if has_permission:
                    dc.mark_obsolete(f"Granted authorization by NPC: {granted_permissions[0]}")

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
