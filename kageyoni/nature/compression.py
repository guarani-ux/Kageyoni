"""2. COMPRESSION Nature Transformation

Purpose:
Discover the smallest useful structure that preserves what downstream work requires.

Core transformation:
{X1, X2, ... Xn} → G
where G is a candidate invariant, generator, reusable transformation, or compressed representation.

Compression identifies recurrence, separates incidental properties from causal structure,
extracts invariants, and searches for generators. It strictly avoids confusing summarization
with generator extraction, refuses to collapse mutually incompatible cases, preserves
failure conditions, and explicitly declares preserved, removed, lost_info, and safety_limit.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from .core import (
    CognitiveDelta,
    CognitiveState,
    DeficitType,
    KnowledgeDeficit,
    NatureType,
)


class DestructiveCompressionError(ValueError):
    """Raised when compression would destroy critical invariants, failure conditions, or distinctions."""
    pass


class IncompatibleCasesError(ValueError):
    """Raised when an attempt is made to collapse mutually contradictory cases into false universality."""
    pass


@dataclass
class CompressionResult:
    """The formal, audited output of a Compression transformation."""
    generator: str
    invariant_rules: list[str]
    preserved: list[str]
    removed: list[str]
    lost_info: list[str]
    safety_limit: str
    source_count: int
    deficits: list[KnowledgeDeficit]
    delta: CognitiveDelta

    def to_dict(self) -> dict[str, Any]:
        return {
            "generator": self.generator,
            "invariant_rules": list(self.invariant_rules),
            "preserved": list(self.preserved),
            "removed": list(self.removed),
            "lost_info": list(self.lost_info),
            "safety_limit": self.safety_limit,
            "source_count": self.source_count,
            "deficits": [d.to_dict() for d in self.deficits],
        }


class Compression:
    """The Compression Nature Transformation engine."""

    def transform(
        self,
        cases: Sequence[dict[str, Any]],
        state: Optional[CognitiveState] = None,
        required_distinctions: Optional[Sequence[str]] = None,
        preserve_failure_conditions: bool = True,
    ) -> CompressionResult:
        """Compresses multiple operational instances, episodes, or representations into a minimal invariant/generator.

        Audits:
        1. Checks for mutually contradictory invariants among cases.
        2. Ensures failure conditions are preserved rather than erased.
        3. Formulates a generator function/rule, not a superficial text summary.
        4. Explicitly declares preserved, removed, lost_info, and safety_limit.
        """
        if not cases:
            raise ValueError("Compression requires at least one input instance.")

        source_count = len(cases)
        deficits: list[KnowledgeDeficit] = []

        # 1. Incompatibility Detection: Check for contradictory failure modes or invariant conflicts
        self._check_case_compatibility(cases)

        # 2. Extract shared invariants vs incidental variance
        shared_keys = set(cases[0].keys())
        for c in cases[1:]:
            shared_keys &= set(c.keys())

        preserved: list[str] = []
        removed: list[str] = []
        lost_info: list[str] = []
        invariant_rules: list[str] = []

        # Inspect failure conditions across cases
        all_failure_conditions: set[str] = set()
        for c in cases:
            fc = c.get("failure_conditions") or c.get("failures") or []
            if isinstance(fc, (list, set, tuple)):
                all_failure_conditions.update(fc)
            elif isinstance(fc, str) and fc:
                all_failure_conditions.add(fc)

        if preserve_failure_conditions and all_failure_conditions:
            for f in sorted(all_failure_conditions):
                preserved.append(f"FAILURE_CONDITION: {f}")
                invariant_rules.append(f"Guard against {f}")

        # Check required distinctions
        if required_distinctions:
            for req in required_distinctions:
                present = any(req in c for c in cases) or any(req in str(c.values()) for c in cases)
                if not present:
                    deficits.append(
                        KnowledgeDeficit(
                            deficit_type=DeficitType.INPUT_DEFICIT,
                            description=f"Required distinction '{req}' not fully represented across cases.",
                            impacted_representation=str(cases[:2]),
                            required_to_resolve="Supply additional contrasting cases demonstrating distinction.",
                        )
                    )

        # Separate causal properties from incidental parameters
        incidental_keys = set()
        causal_keys = set()
        for k in shared_keys:
            vals = [str(c[k]) for c in cases]
            if len(set(vals)) == 1:
                causal_keys.add(k)
                preserved.append(f"Invariant property '{k}' = {vals[0]}")
                invariant_rules.append(f"Invariant: {k} must equal {vals[0]}")
            else:
                incidental_keys.add(k)
                removed.append(f"Incidental parameter variance in '{k}' (values: {set(vals)})")
                lost_info.append(f"Specific episode values for '{k}' stripped in favor of parameterized generator.")

        # Identify unique non-shared keys
        all_keys = set().union(*[c.keys() for c in cases])
        non_shared = all_keys - shared_keys
        for nk in non_shared:
            removed.append(f"Non-universal key '{nk}' dropped from core invariant.")
            lost_info.append(f"Context-specific property '{nk}' removed.")

        # Construct Candidate Generator
        generator_name = cases[0].get("name") or cases[0].get("kind") or "generic_transformation"
        generator_expr = (
            f"Generator[{generator_name}]("
            f"invariants=[{', '.join(sorted(causal_keys))}], "
            f"parameters=[{', '.join(sorted(incidental_keys))}], "
            f"guarded_failures=[{', '.join(sorted(all_failure_conditions))}])"
        )

        safety_limit = (
            f"Cannot compress past {len(causal_keys)} core invariants and "
            f"{len(all_failure_conditions)} failure guards without inducing behavioral collapse or false universality."
        )

        delta = CognitiveDelta(
            delta_id=f"delta-{uuid.uuid4().hex[:8]}",
            nature=NatureType.COMPRESSION,
            input_summary={"case_count": source_count},
            output_summary={
                "generator": generator_expr,
                "invariants_extracted": len(invariant_rules),
                "preserved_count": len(preserved),
                "removed_count": len(removed),
            },
            objective_preserved=True,
            deficits_identified=deficits,
            authoritative_world_mutated=False,
        )

        # If state provided, record extracted invariants
        if state is not None:
            state.invariants.append({
                "generator": generator_expr,
                "invariant_rules": invariant_rules,
                "safety_limit": safety_limit,
            })
            for d in deficits:
                state.record_deficit(d)

        return CompressionResult(
            generator=generator_expr,
            invariant_rules=invariant_rules,
            preserved=preserved,
            removed=removed,
            lost_info=lost_info,
            safety_limit=safety_limit,
            source_count=source_count,
            deficits=deficits,
            delta=delta,
        )

    def _check_case_compatibility(self, cases: Sequence[dict[str, Any]]) -> None:
        """Adversarial check: Rejects collapsing cases that hold direct mutual contradictions."""
        contradictions = []
        for i, c1 in enumerate(cases):
            for c2 in cases[i + 1:]:
                # Check explicit contradiction markers
                if c1.get("target_id") and c2.get("target_id") and c1["target_id"] == c2["target_id"]:
                    if c1.get("expected_state") and c2.get("expected_state") and c1["expected_state"] != c2["expected_state"]:
                        contradictions.append(
                            f"Contradictory state requirement on {c1['target_id']}: "
                            f"{c1['expected_state']} vs {c2['expected_state']}"
                        )
                if c1.get("disposition") and c2.get("disposition") and c1["disposition"] != c2["disposition"]:
                    if c1.get("scope") == c2.get("scope") and c1.get("requirement") == c2.get("requirement"):
                        contradictions.append(
                            f"Contradictory empirical dispositions for {c1.get('scope')}: "
                            f"{c1['disposition']} vs {c2['disposition']}"
                        )

        if contradictions:
            raise IncompatibleCasesError(
                "Compression rejected: Attempted to collapse mutually contradictory cases into false universality. "
                + "; ".join(contradictions)
            )
