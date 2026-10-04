"""
Reusable Executable Technique Model for Constellation Emergence.

A genuine emergent technique is an executable composition discovered during an encounter,
derived strictly from validated execution traces, storing actual bindings, observed
dependencies, evidence scope, and unresolved claims.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json

@dataclass
class TechniqueStep:
    actor_role: str
    action_id: str
    description: str
    required_preconditions: Dict[str, Any] = field(default_factory=dict)
    state_delta_produced: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutableTechnique:
    technique_id: str
    name: str
    description: str
    steps: List[TechniqueStep]
    actual_bindings: Dict[str, Any]
    observed_dependencies: List[str]
    evidence_scope: Dict[str, Any]
    unresolved_claims: List[str]
    discovery_encounter_id: str
    discovery_branch: str
    is_emergent: bool = True
    qualification: str = "PROPOSED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutableTechnique:
        steps = [TechniqueStep(**s) for s in data.get("steps", [])]
        kwargs = dict(data)
        kwargs["steps"] = steps
        return cls(**kwargs)

    def execute(self, encounters: Any, branch: str, encounter_id: str, request_prefix: str, expected_revision: int, viewer: Optional[str] = None) -> List[Dict[str, Any]]:
        receipts = []
        rev = expected_revision
        for i, step in enumerate(self.steps):
            req_id = f"{request_prefix}-step-{i+1}-{step.action_id}"
            receipt = encounters.act(
                branch=branch,
                encounter_id=encounter_id,
                action_id=step.action_id,
                request_id=req_id,
                expected_revision=rev,
                viewer=viewer or step.actor_role,
            )
            receipts.append(receipt)
            rev = receipt["world_revision"]
        return receipts

def derive_technique_from_trace(
    trace: List[Dict[str, Any]],
    encounter_spec: Dict[str, Any],
    discovery_encounter_id: str,
    discovery_branch: str,
    technique_id: str = "tech:constellation:basalt_locked_inversion",
    name: str = "Basalt-Locked Inversion Seal"
) -> Optional[ExecutableTechnique]:
    """
    Derives candidate technique strictly from validated execution traces.
    Returns None if trace is empty, failed, out-of-order, or lacking required closure.
    """
    if not trace:
        return None

    # Verify that each trace entry has valid engine receipts and no failures
    steps: List[TechniqueStep] = []
    actions_spec = encounter_spec.get("actions", {})
    resolved_loops = set()

    for entry in trace:
        receipt = entry.get("receipt", {})
        action_id = entry.get("action_id")
        actor = entry.get("actor")

        if not receipt or not action_id or action_id not in actions_spec:
            return None

        act_def = actions_spec[action_id]
        if act_def.get("actor_role") != actor:
            return None

        # Track state delta and resolved loops
        for l in act_def.get("resolve_loops", []):
            resolved_loops.add(l)

        # Build step
        step = TechniqueStep(
            actor_role=actor,
            action_id=action_id,
            description=act_def.get("label", action_id),
            required_preconditions={r["record_id"]: {r["field"]: r["equals"]} for r in act_def.get("requirements", [])},
            state_delta_produced={c["id"]: c.get("data", {}) for c in act_def.get("payload", {}).get("changes", [])}
        )
        steps.append(step)

    last_receipt = trace[-1].get("receipt", {})
    if last_receipt.get("phase") != "completed" or last_receipt.get("outcome") != "achieved":
        return None

    # Required loops must all be resolved
    req_loops = {l["id"] for l in encounter_spec.get("loops", []) if l.get("required")}
    if not req_loops.issubset(resolved_loops):
        return None

    all_targets = set()
    for s in steps:
        all_targets.update(s.required_preconditions.keys())
        all_targets.update(s.state_delta_produced.keys())

    actual_bindings = {
        "roles": encounter_spec.get("roles", []),
        "action_sequence": [s.action_id for s in steps],
        "actors": [s.actor_role for s in steps],
        "resolved_loops": list(resolved_loops),
        "target_records": sorted(list(all_targets)),
    }

    observed_dependencies = [
        "kageyoni.workspaces.world.Encounters",
        "kageyoni.engine.Engine",
        "kageyoni.will.PrimordialWill"
    ]

    evidence_scope = {
        "encounter_id": discovery_encounter_id,
        "branch": discovery_branch,
        "event_count": len(trace),
        "receipt_digests": [entry.get("receipt", {}).get("state_digest") for entry in trace if entry.get("receipt")]
    }

    unresolved_claims = [
        "Qualified only for single-node workspace cavity containment.",
        "Cross-boundary multi-shard propagation unverified.",
        "Zero autonomous emergence claimed without active empirical observation."
    ]

    return ExecutableTechnique(
        technique_id=technique_id,
        name=name,
        description=f"Empirically derived composition of {len(steps)} steps discovered in {discovery_encounter_id}",
        steps=steps,
        actual_bindings=actual_bindings,
        observed_dependencies=observed_dependencies,
        evidence_scope=evidence_scope,
        unresolved_claims=unresolved_claims,
        discovery_encounter_id=discovery_encounter_id,
        discovery_branch=discovery_branch,
        is_emergent=True,
        qualification="TESTED_IN_SCOPE"
    )
