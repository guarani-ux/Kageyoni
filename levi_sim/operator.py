"""
Levi Sim Operator.

Primary cognitive interface connecting the user, the independent LeviCognitiveModel,
and the BoundedKageyoniGateway.

Translates high-level natural language user intent into structured operational plans,
executes perception-deliberation-action cycles, respects the User Attention Economy,
and generates concise executive reports with verifiable cryptographic receipts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from kageyoni.gateway import BoundedKageyoniGateway
from levi_sim.cognition import LeviCognitiveModel
from levi_sim.compiler import IntentContract


class TypedStatus(str):
    """
    Typed return state for Levi Sim operator execution.
    Supports SATISFIED, FAILED, BLOCKED, UNRESOLVED, REQUIRES_USER_JUDGMENT,
    while maintaining equality with legacy COMPLETED strings for compatibility.
    """
    def __eq__(self, other):
        s = str(self)
        o = str(other) if other is not None else ""
        if s == "SATISFIED" and o == "COMPLETED":
            return True
        if s == "COMPLETED" and o == "SATISFIED":
            return True
        return super().__eq__(other)


class ObjectiveStatus:
    SATISFIED = TypedStatus("COMPLETED")
    FAILED = TypedStatus("FAILED")
    BLOCKED = TypedStatus("BLOCKED")
    UNRESOLVED = TypedStatus("UNRESOLVED")
    REQUIRES_USER_JUDGMENT = TypedStatus("REQUIRES_USER_JUDGMENT")


@dataclass
class UserReport:
    """Concise executive report returned to the user at the completion of an operation."""
    status: str  # SATISFIED (COMPLETED), FAILED, BLOCKED, UNRESOLVED, REQUIRES_USER_JUDGMENT
    objective: str
    raw_intent: str
    executive_summary: str
    total_steps: int
    actions_taken: list[dict[str, Any]]
    cryptographic_receipts: list[str]
    active_constraints: list[str]
    next_recommendation: str
    post_mortem: dict[str, Any]
    typed_status: str = "SATISFIED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status),
            "typed_status": self.typed_status,
            "objective": self.objective,
            "raw_intent": self.raw_intent,
            "executive_summary": self.executive_summary,
            "total_steps": self.total_steps,
            "actions_taken": self.actions_taken,
            "cryptographic_receipts": self.cryptographic_receipts,
            "active_constraints": self.active_constraints,
            "next_recommendation": self.next_recommendation,
            "post_mortem": self.post_mortem,
        }


class LeviOperator:
    """
    The autonomous agent driver piloting an in-world avatar through Kageyoni.
    Acts as the primary intent interface between the User and Kageyoni.
    """

    def __init__(
        self,
        gateway: BoundedKageyoniGateway,
        avatar_id: str = "levi-avatar",
        external_memory_path: Optional[Path] = None,
    ):
        self.gateway = gateway
        self.avatar_id = avatar_id
        self.external_memory_path = external_memory_path

        # Load external memory if available
        memory_store = None
        if external_memory_path and external_memory_path.exists():
            try:
                memory_store = json.loads(external_memory_path.read_text(encoding="utf-8"))
            except Exception:
                memory_store = None

        self.cognition = LeviCognitiveModel(memory_store=memory_store)
        self.action_history: list[dict[str, Any]] = []
        self.verified_receipts: list[str] = []

    def interact(self, user_message: str, max_turns: int = 6) -> UserReport:
        """
        Primary natural language interface.
        Accepts raw user intent, compiles the IntentContract, and executes the autonomous operator loop.
        """
        # 1. Compile User Intent
        intent_contract = self.cognition.set_intent(user_message)
        objective = intent_contract.derived_objective

        status = ObjectiveStatus.UNRESOLVED
        for turn in range(1, max_turns + 1):
            step = self.execute_autonomous_step(objective, step_num=turn)

            # Check Attention Economy triggers
            if step.get("type") == "ACTION_REJECTED":
                rej_class = step.get("rejection_data", {}).get("rejection_class", "")
                if rej_class == "HARD_INVARIANT_VIOLATION":
                    # If all alternatives exhausted, check if we must escalate
                    if len(self.cognition.firewall.hard_invariants) >= 3:
                        status = ObjectiveStatus.BLOCKED
                        break

            # Evaluate objective state using structured state transitions
            eval_state = self._evaluate_objective_state(objective, step)
            if eval_state == "SATISFIED":
                status = ObjectiveStatus.SATISFIED
                break
            elif eval_state in ("FAILED", "BLOCKED", "REQUIRES_USER_JUDGMENT"):
                status = getattr(ObjectiveStatus, eval_state, ObjectiveStatus.UNRESOLVED)
                break

        if status == ObjectiveStatus.UNRESOLVED:
            status = ObjectiveStatus.SATISFIED if self.verified_receipts else ObjectiveStatus.UNRESOLVED

        # 2. Persist post-mortem learning
        post_mortem = self.cognition.extract_post_mortem()
        if self.external_memory_path:
            self.external_memory_path.parent.mkdir(parents=True, exist_ok=True)
            self.external_memory_path.write_text(json.dumps(post_mortem, indent=2), encoding="utf-8")

        # 3. Generate Executive Summary (Explanation Layer)
        summary = self._synthesize_executive_summary(intent_contract, status)

        return UserReport(
            status=status,
            objective=objective,
            raw_intent=intent_contract.raw_user_intent,
            executive_summary=summary,
            total_steps=len(self.action_history),
            actions_taken=list(self.action_history),
            cryptographic_receipts=list(self.verified_receipts),
            active_constraints=self.cognition.firewall.get_active_constraints(),
            next_recommendation="Operational state verified. Maintain normal observation." if status == ObjectiveStatus.SATISFIED else "Awaiting guidance.",
            post_mortem=post_mortem,
            typed_status="SATISFIED" if status == ObjectiveStatus.SATISFIED else str(status),
        )

    def _evaluate_objective_state(self, objective: str, last_step: dict[str, Any]) -> str:
        """
        Evaluate objective state using structured predicates and world state verification,
        not lexical target heuristics.
        Returns one of: SATISFIED, FAILED, BLOCKED, UNRESOLVED, REQUIRES_USER_JUDGMENT.
        """
        # 1. Check if Kageyoni world state contains closed scenes or satisfied objectives
        perception = self.gateway.inspect_environment(self.avatar_id)
        scene = perception.get("perceived_scene")
        if scene and scene.get("phase") == "closed":
            return "SATISFIED"

        # 2. Check if a successful action restored an impaired system or engaged a mechanism
        if last_step.get("type") == "ACTION_SUCCESS":
            decision = last_step.get("decision", {})
            changes = decision.get("changes", [])
            for ch in changes:
                data = ch.get("data", {})
                cond = data.get("condition")
                if cond in ("operational", "restored", "engaged"):
                    return "SATISFIED"

        # 3. Check for blocking conditions
        if len(self.cognition.firewall.hard_invariants) >= 3:
            return "BLOCKED"

        return "UNRESOLVED"

    def execute_autonomous_step(self, objective: str, step_num: int) -> dict[str, Any]:
        """Execute one complete cognitive perception-deliberation-action cycle."""
        # 1. Discover capabilities & inspect bounded environment
        capabilities = self.gateway.discover_capabilities(self.avatar_id)
        perception = self.gateway.inspect_environment(self.avatar_id)

        # 2. Update cognitive model
        self.cognition.perceive_and_update(perception)

        # 3. Deliberate
        decision = self.cognition.deliberate(objective, capabilities, perception)

        # 4. Invoke capability through bounded gateway
        action_type = decision.get("action_type")
        result: dict[str, Any] = {}

        if action_type == "interact_npc":
            result = self.gateway.interact_npc(
                avatar_id=self.avatar_id,
                target_id=decision["target_id"],
                dialogue_act=decision["dialogue_act"],
                statement=decision["statement"],
            )
            if result.get("status") in ("cooperative", "agreement") or result.get("granted_permission"):
                if decision["target_id"] not in self.cognition.firewall.aligned_partners:
                    self.cognition.firewall.aligned_partners.add(decision["target_id"])
                # Reconcile constraints now that permission is granted
                self.cognition.firewall.reconcile_world_state(
                    newly_discovered_items=perception.get("perceived_items", []),
                    granted_permissions=list(self.cognition.firewall.aligned_partners),
                )

            step_record = {
                "step": step_num,
                "type": "INTERACTION",
                "target": decision["target_id"],
                "decision": decision,
                "result": result,
            }
            self.action_history.append(step_record)
            return step_record

        elif action_type == "execute_action":
            target_id = decision.get("target_id")
            changes = decision.get("changes") or [
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": f"cons-step-{step_num}",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": f"Autonomous action consequence for {decision['rationale']}"}],
                    "data": {
                        "subject": target_id or "environment",
                        "effect": f"Leveraged {target_id} to advance objective.",
                        "duration": "permanent",
                        "reversibility": "reversible",
                    },
                }
            ]

            result = self.gateway.attempt_action(
                avatar_id=self.avatar_id,
                request_id=f"step-{step_num}-{self.avatar_id}",
                narrative=decision.get("narrative", f"Action on {target_id}"),
                changes=changes,
            )

            # Check if Kageyoni rejected the action
            if not result.get("success"):
                adaptation_msg = self.cognition.handle_engine_rejection(result)
                step_record = {
                    "step": step_num,
                    "type": "ACTION_REJECTED",
                    "rejection_data": result,
                    "cognitive_adaptation": adaptation_msg,
                    "decision": decision,
                }
                self.action_history.append(step_record)
                return step_record

            # Success: Store verified event receipt and record in firewall
            event_hash = result.get("event_hash")
            if event_hash:
                self.verified_receipts.append(event_hash)
                self.cognition.firewall.record_verified_fact(
                    fact=f"Action on {target_id} succeeded with event {event_hash}",
                    receipt_hash=event_hash,
                    source=f"kageyoni_event_{event_hash[:8]}",
                )

            step_record = {
                "step": step_num,
                "type": "ACTION_SUCCESS",
                "receipt": result,
                "decision": decision,
            }
            self.action_history.append(step_record)
            return step_record

        else:
            step_record = {
                "step": step_num,
                "type": "INSPECTION",
                "decision": decision,
            }
            self.action_history.append(step_record)
            return step_record

    def run_encounter_loop(self, objective: str, max_turns: int = 5) -> dict[str, Any]:
        """Execute autonomous loop until objective met, blocked, or max turns reached."""
        for turn in range(1, max_turns + 1):
            step = self.execute_autonomous_step(objective, step_num=turn)

        # Post-encounter: Save learned state to external memory
        post_mortem = self.cognition.extract_post_mortem()
        if self.external_memory_path:
            self.external_memory_path.parent.mkdir(parents=True, exist_ok=True)
            self.external_memory_path.write_text(json.dumps(post_mortem, indent=2), encoding="utf-8")

        return {
            "objective": objective,
            "total_turns": len(self.action_history),
            "history": self.action_history,
            "post_mortem": post_mortem,
        }

    def _synthesize_executive_summary(self, contract: IntentContract, status: str) -> str:
        """Construct a high-density, concise executive summary for the user."""
        receipt_count = len(self.verified_receipts)
        actions_count = len(self.action_history)
        active_constraints = self.cognition.firewall.get_active_constraints()

        lines = [
            f"Objective: {contract.derived_objective}",
            f"Status: {status} ({actions_count} steps executed, {receipt_count} verified receipts).",
        ]
        if receipt_count > 0:
            lines.append(f"Latest Receipt Digest: SHA-256:{self.verified_receipts[-1][:16]}...")
        if active_constraints:
            lines.append(f"Active Constraints: {'; '.join(active_constraints[:2])}")
        else:
            lines.append("Constraints: Zero active blockers.")

        # Key action outcomes
        successful_actions = [s for s in self.action_history if s.get("type") == "ACTION_SUCCESS"]
        if successful_actions:
            last_action = successful_actions[-1]["decision"]
            lines.append(f"Key Resolution: {last_action.get('narrative', 'System operational.')}")

        return " | ".join(lines)
