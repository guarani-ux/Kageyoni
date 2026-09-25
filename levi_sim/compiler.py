"""
Levi Sim Intent Compiler.

Transforms natural language user input into a formal, immutable IntentContract.
Strictly separates raw user intent from Levi Sim's interpretation to prevent objective drift.
Identifies invariants, constraints, hypotheses, unknowns, and delegated scope.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class IntentContract:
    """
    Immutable representation of compiled user intent.
    Preserves original phrasing and establishes boundaries for autonomous execution.
    """
    raw_user_intent: str
    derived_objective: str
    invariants: Tuple[str, ...]
    explicit_constraints: Tuple[str, ...]
    working_hypotheses: Tuple[str, ...]
    critical_unknowns: Tuple[str, ...]
    relevant_actors: Tuple[str, ...]
    delegated_scope: Tuple[str, ...]
    escalation_triggers: Tuple[str, ...]
    verification_needs: Tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_user_intent": self.raw_user_intent,
            "derived_objective": self.derived_objective,
            "invariants": list(self.invariants),
            "explicit_constraints": list(self.explicit_constraints),
            "working_hypotheses": list(self.working_hypotheses),
            "critical_unknowns": list(self.critical_unknowns),
            "relevant_actors": list(self.relevant_actors),
            "delegated_scope": list(self.delegated_scope),
            "escalation_triggers": list(self.escalation_triggers),
            "verification_needs": list(self.verification_needs),
        }


class IntentCompiler:
    """
    Compiles natural language into an IntentContract.
    Does not invent requirements; surfaces knowledge deficits explicitly.
    """

    def compile(self, user_prompt: str) -> IntentContract:
        raw_text = user_prompt.strip()
        text_lower = raw_text.lower()

        # 1. Derive Actionable Objective
        derived_obj = self._extract_objective(raw_text)

        # 2. Extract Invariants (Non-negotiables)
        invariants: list[str] = [
            "Preserve human agency and avoid unnecessary casualties",
            "Maintain causal fidelity and truth boundaries",
            "Do not fabricate authority or forge receipts",
        ]
        if "without damage" in text_lower or "safely" in text_lower or "do not harm" in text_lower:
            invariants.append("Zero physical harm or destructive collateral")

        # 3. Extract Explicit Constraints from Prompt
        constraints: list[str] = []
        if "without" in text_lower:
            matches = re.findall(r"without\s+([^,.;]+)", raw_text, re.IGNORECASE)
            for m in matches:
                constraints.append(f"Prohibited: {m.strip()}")
        if "do not" in text_lower:
            matches = re.findall(r"do not\s+([^,.;]+)", raw_text, re.IGNORECASE)
            for m in matches:
                constraints.append(f"Prohibited: {m.strip()}")

        # 4. Formulate Working Hypotheses & Unknowns
        hypotheses: list[str] = []
        unknowns: list[str] = []

        if any(w in text_lower for w in ["why", "stopped communicating", "dark", "silent", "investigate"]):
            hypotheses.append("Communication failure may be caused by infrastructure damage, power loss, or quarantine.")
            unknowns.append("Root cause of communication silence (hardware fault, hazard, or human action).")
            unknowns.append("Physical status and readiness of local personnel.")

        if any(w in text_lower for w in ["help", "assist", "repair", "restore"]):
            hypotheses.append("Restoration likely requires local physical affordances or component replacement.")
            unknowns.append("Location and condition of necessary repair supplies or keys.")

        # 5. Extract Relevant Actors
        actors: list[str] = []
        for word in ["elder", "guard", "archivist", "settler", "engineer", "technician", "operator"]:
            if word in text_lower:
                actors.append(word)

        # 6. Establish Delegated Execution Scope
        delegated_scope = [
            "inspect_environment",
            "discover_capabilities",
            "query_observable_records",
            "interact_and_negotiate_with_npcs",
            "use_available_tools_and_affordances",
            "execute_reversible_repairs",
        ]

        # 7. Establish Escalation Triggers
        escalation_triggers = [
            "destructive_irreversible_action",
            "unauthorized_breach_of_vital_records",
            "unresolvable_goal_conflict",
            "hard_engine_block_with_zero_alternatives",
        ]

        # 8. Verification Needs
        verification_needs = [
            "Authoritative Kageyoni SHA-256 event receipt for state mutations",
            "Verified operational status of target system",
        ]

        return IntentContract(
            raw_user_intent=raw_text,
            derived_objective=derived_obj,
            invariants=tuple(invariants),
            explicit_constraints=tuple(constraints),
            working_hypotheses=tuple(hypotheses),
            critical_unknowns=tuple(unknowns),
            relevant_actors=tuple(actors),
            delegated_scope=tuple(delegated_scope),
            escalation_triggers=tuple(escalation_triggers),
            verification_needs=tuple(verification_needs),
        )

    def _extract_objective(self, prompt: str) -> str:
        """Extract or distill a direct actionable objective from natural language."""
        cleaned = prompt.replace("Levi Sim,", "").replace("Levi,", "").strip()
        sentences = [s.strip() for s in re.split(r"[.!?]", cleaned) if s.strip()]
        if not sentences:
            return cleaned
        return sentences[0]

    def check_drift(self, contract: IntentContract, current_action_goal: str) -> bool:
        """Check if an autonomous sub-goal has drifted from the initial user intent."""
        # Simple containment check: ensure goal does not directly contradict initial intent keywords
        action_lower = current_action_goal.lower()
        if "destroy" in action_lower and "preserve" in contract.derived_objective.lower():
            return True
        return False
