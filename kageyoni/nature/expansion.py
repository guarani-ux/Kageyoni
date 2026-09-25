"""1. EXPANSION Nature Transformation

Purpose:
Increase meaningful possibility without silently changing the objective.

Core transformation:
R → {R1, R2, ... Rn}
while preserving:
Objective(Ri) = Objective(R)

Expansion exposes hidden assumptions, generates materially different representations,
produces alternative hypotheses, preserves unresolved alternatives, and generates
discriminating questions. It strictly rejects paraphrasing, objective drift,
and unconstrained combinatorial explosion.
"""
from __future__ import annotations

import difflib
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from .core import (
    CognitiveDelta,
    CognitiveHypothesis,
    CognitiveState,
    DeficitType,
    EpistemicCategory,
    KnowledgeDeficit,
    NatureType,
    ObjectiveDriftError,
)


@dataclass
class CandidateBranch:
    """An expanded alternative representation or operational pathway."""
    branch_id: str
    representation: str
    assumptions_exposed: list[str] = field(default_factory=list)
    discriminating_questions: list[str] = field(default_factory=list)
    material_difference: str = ""
    violates_constraints: list[str] = field(default_factory=list)
    is_valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "representation": self.representation,
            "assumptions_exposed": list(self.assumptions_exposed),
            "discriminating_questions": list(self.discriminating_questions),
            "material_difference": self.material_difference,
            "violates_constraints": list(self.violates_constraints),
            "is_valid": self.is_valid,
        }


@dataclass
class ExpansionResult:
    """The formal output of an Expansion transformation."""
    source_representation: str
    objective: str
    branches: list[CandidateBranch]
    exposed_assumptions: list[str]
    discriminating_questions: list[str]
    rejected_paraphrases: list[str]
    deficits: list[KnowledgeDeficit]
    delta: CognitiveDelta

    @property
    def valid_branches(self) -> list[CandidateBranch]:
        return [b for b in self.branches if b.is_valid]


class Expansion:
    """The Expansion Nature Transformation engine."""

    def __init__(self, paraphrase_similarity_threshold: float = 0.85):
        self.similarity_threshold = paraphrase_similarity_threshold

    def is_paraphrase(self, text_a: str, text_b: str) -> bool:
        """Adversarial check: Rejects cosmetic rephrasings that offer zero material distinction."""
        a = " ".join(text_a.strip().lower().split())
        b = " ".join(text_b.strip().lower().split())
        if a == b:
            return True
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        return ratio >= self.similarity_threshold

    def transform(
        self,
        state: CognitiveState,
        candidate_generators: Optional[Sequence[dict[str, Any]]] = None,
        max_branches: int = 5,
    ) -> ExpansionResult:
        """Transforms a cognitive state by expanding its representations into multiple viable branches.

        Guarantees:
        1. Objective(Ri) == Objective(R): Raises ObjectiveDriftError if any candidate alters objective.
        2. Paraphrases are detected and rejected.
        3. Hard constraints are applied to prune invalid branches.
        4. Exposed assumptions and discriminating questions are explicitly surfaced.
        """
        raw_repr = (
            state.representations[-1]["content"]
            if state.representations
            else state.raw_intent or state.objective
        )
        objective = state.objective

        exposed_assumptions: list[str] = []
        discriminating_questions: list[str] = []
        rejected_paraphrases: list[str] = []
        branches: list[CandidateBranch] = []
        deficits: list[KnowledgeDeficit] = []

        # Analyze hidden assumptions in the current representation
        exposed_assumptions.extend(self._extract_implicit_assumptions(raw_repr, objective))

        if candidate_generators:
            for item in candidate_generators:
                # 1. Enforce Objective Invariance
                cand_obj = item.get("objective", objective)
                if cand_obj != objective:
                    raise ObjectiveDriftError(
                        f"Expansion attempted to alter objective from '{objective}' to '{cand_obj}'. "
                        "Expansion must strictly preserve Objective(Ri) = Objective(R)."
                    )

                text = item.get("representation", "")
                diff = item.get("material_difference", "")

                # 2. Adversarial Paraphrase Detection
                if self.is_paraphrase(raw_repr, text) and not diff:
                    rejected_paraphrases.append(text)
                    continue

                is_dup = False
                for existing in branches:
                    if self.is_paraphrase(existing.representation, text) and not diff:
                        rejected_paraphrases.append(text)
                        is_dup = True
                        break
                if is_dup:
                    continue

                # 3. Constraint checking
                violates: list[str] = list(item.get("violates_constraints", []))
                for c in state.active_constraints:
                    c_lower = c.lower()
                    if c_lower.startswith("prohibited:") or "hard_engine_constraint" in c_lower:
                        forbidden_part = c.split(":", 1)[-1].strip().lower()
                        if forbidden_part and forbidden_part in text.lower():
                            violates.append(c)
                        elif "budget" in forbidden_part and ("overbudget" in diff.lower() or "overbudget" in text.lower()):
                            violates.append(c)

                branch_assumptions = item.get("assumptions", [])
                branch_questions = item.get("discriminating_questions", [])
                exposed_assumptions.extend(branch_assumptions)
                discriminating_questions.extend(branch_questions)

                branch = CandidateBranch(
                    branch_id=f"branch-{uuid.uuid4().hex[:8]}",
                    representation=text,
                    assumptions_exposed=branch_assumptions,
                    discriminating_questions=branch_questions,
                    material_difference=diff,
                    violates_constraints=violates,
                    is_valid=len(violates) == 0,
                )
                branches.append(branch)

                if len(branches) >= max_branches:
                    break

        # If zero candidate branches were produced or all were rejected paraphrases
        if not branches:
            # Generate default exploratory branches
            default_branches = self._generate_default_branches(raw_repr, objective)
            for db in default_branches:
                branches.append(db)
                exposed_assumptions.extend(db.assumptions_exposed)
                discriminating_questions.extend(db.discriminating_questions)

        # If evidence cannot discriminate branches, record an explicit deficit
        if len([b for b in branches if b.is_valid]) > 1:
            deficits.append(
                KnowledgeDeficit(
                    deficit_type=DeficitType.VERIFIER_DEFICIT,
                    description=f"{len(branches)} competing branches remain unresolved without discriminating evidence.",
                    impacted_representation=raw_repr,
                    required_to_resolve="External probe or empirical test to discriminate competing branches.",
                )
            )

        # Create Cognitive Delta
        delta = CognitiveDelta(
            delta_id=f"delta-{uuid.uuid4().hex[:8]}",
            nature=NatureType.EXPANSION,
            input_summary={"representation": raw_repr, "objective": objective},
            output_summary={
                "branches_count": len(branches),
                "valid_count": len([b for b in branches if b.is_valid]),
                "paraphrases_rejected": len(rejected_paraphrases),
            },
            objective_preserved=True,
            deficits_identified=deficits,
            authoritative_world_mutated=False,
        )

        # Update Cognitive State
        state.representations.append({
            "source": "EXPANSION",
            "branches": [b.to_dict() for b in branches],
            "rejected_paraphrases": rejected_paraphrases,
        })
        for b in branches:
            if b.is_valid:
                hyp = CognitiveHypothesis(
                    hypothesis_id=f"hyp-{uuid.uuid4().hex[:8]}",
                    statement=b.representation,
                    epistemic_status=EpistemicCategory.ASSUMPTION,
                    confidence="UNVERIFIED",
                    falsification_condition=f"Evidence demonstrating {b.material_difference} is invalid.",
                    discriminating_questions=b.discriminating_questions,
                )
                state.add_hypothesis(hyp)
        for d in deficits:
            state.record_deficit(d)

        return ExpansionResult(
            source_representation=raw_repr,
            objective=objective,
            branches=branches,
            exposed_assumptions=list(dict.fromkeys(exposed_assumptions)),
            discriminating_questions=list(dict.fromkeys(discriminating_questions)),
            rejected_paraphrases=rejected_paraphrases,
            deficits=deficits,
            delta=delta,
        )

    def _extract_implicit_assumptions(self, repr_text: str, objective: str) -> list[str]:
        assumptions = []
        text = repr_text.lower()
        if "single" in text or "only" in text:
            assumptions.append("Assumes single-path or monotonic solution exists.")
        if "fast" in text or "immediately" in text:
            assumptions.append("Assumes operational latency can be compressed without safety penalty.")
        if "must" in text:
            assumptions.append("Assumes stated constraint is physically immutable rather than policy-bound.")
        if not assumptions:
            assumptions.append("Assumes current environment invariants are stationary.")
        return assumptions

    def _generate_default_branches(self, repr_text: str, objective: str) -> list[CandidateBranch]:
        return [
            CandidateBranch(
                branch_id=f"branch-{uuid.uuid4().hex[:8]}",
                representation=f"Direct Execution: {repr_text}",
                assumptions_exposed=["Assumes direct environment access and immediate precondition satisfaction."],
                discriminating_questions=["Are all required resources and authority tokens available right now?"],
                material_difference="Relies on zero-staging immediate execution.",
            ),
            CandidateBranch(
                branch_id=f"branch-{uuid.uuid4().hex[:8]}",
                representation=f"Decomposed Staging: Pre-verify preconditions before {repr_text}",
                assumptions_exposed=["Assumes potential failure risk justifies staging overhead."],
                discriminating_questions=["Does the environment reject unprepared calls with irreversible penalty?"],
                material_difference="Introduces bounded precondition verification stage.",
            ),
        ]
