"""5. COUPLING Nature Transformation

Purpose:
Discover relationships among separate structures that create operational possibilities unavailable to the structures independently.

Core transformation:
A + B + Relationship → C_candidate

Coupling compares interfaces (provides vs requires), detects structural complementarity,
exposes incompatibilities and conflicting invariants, constructs candidate compositions,
and mandates an explicit emergent mechanism explaining why the composite succeeds
where components independently fail.

Anti-Spuriousness Invariants:
1. Rejects superficial similarity mistaken for compatibility.
2. Refuses to silently distort or modify components to force a fit.
3. Blocks declaring emergent capability without an articulated causal mechanism.
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


class IncompatibleInterfaceError(ValueError):
    """Raised when components have conflicting invariants or incompatible interfaces."""
    pass


class SpuriousCouplingError(ValueError):
    """Raised when a proposed coupling lacks a causal mechanism for emergence."""
    pass


@dataclass
class ComponentInterface:
    """The structural contract of an element participating in coupling."""
    component_id: str
    kind: str  # technique | representation | evidence | tool | agent | workflow | capability
    provides: set[str] = field(default_factory=set)
    requires: set[str] = field(default_factory=set)
    invariants: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "kind": self.kind,
            "provides": sorted(self.provides),
            "requires": sorted(self.requires),
            "invariants": list(self.invariants),
            "failure_modes": list(self.failure_modes),
        }


@dataclass
class CandidateComposition:
    """A synthesized compound structure created by coupling."""
    composition_id: str
    component_a: str
    component_b: str
    relationship: str
    emergent_capability: str
    emergent_mechanism: str
    shared_invariants: list[str]
    unresolved_requirements: list[str] = field(default_factory=list)
    is_valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "composition_id": self.composition_id,
            "component_a": self.component_a,
            "component_b": self.component_b,
            "relationship": self.relationship,
            "emergent_capability": self.emergent_capability,
            "emergent_mechanism": self.emergent_mechanism,
            "shared_invariants": list(self.shared_invariants),
            "unresolved_requirements": list(self.unresolved_requirements),
            "is_valid": self.is_valid,
        }


@dataclass
class CouplingResult:
    """The formal, audited output of a Coupling transformation."""
    component_a: str
    component_b: str
    relationship: str
    is_compatible: bool
    composition: Optional[CandidateComposition]
    complementary_points: list[str]
    incompatibilities: list[str]
    deficits: list[KnowledgeDeficit]
    delta: CognitiveDelta

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_a": self.component_a,
            "component_b": self.component_b,
            "relationship": self.relationship,
            "is_compatible": self.is_compatible,
            "composition": self.composition.to_dict() if self.composition else None,
            "complementary_points": list(self.complementary_points),
            "incompatibilities": list(self.incompatibilities),
            "deficits": [d.to_dict() for d in self.deficits],
        }


class Coupling:
    """The Coupling Nature Transformation engine."""

    def analyze_interfaces(
        self,
        a: ComponentInterface,
        b: ComponentInterface,
    ) -> tuple[list[str], list[str]]:
        """Compares provides/requires and invariant sets to find complementarity and frictions."""
        complementary = []
        incompatible = []

        # Check if A satisfies B's requirements
        a_satisfies_b = a.provides & b.requires
        if a_satisfies_b:
            complementary.append(
                f"Component '{a.component_id}' provides requirements for '{b.component_id}': {sorted(a_satisfies_b)}"
            )

        # Check if B satisfies A's requirements
        b_satisfies_a = b.provides & a.requires
        if b_satisfies_a:
            complementary.append(
                f"Component '{b.component_id}' provides requirements for '{a.component_id}': {sorted(b_satisfies_a)}"
            )

        # Check for invariant conflicts (e.g. read_only vs mutating, async vs blocking)
        for inv_a in a.invariants:
            for inv_b in b.invariants:
                if self._are_invariants_conflicting(inv_a, inv_b):
                    incompatible.append(
                        f"Invariant conflict between '{a.component_id}' ({inv_a}) and '{b.component_id}' ({inv_b})"
                    )

        # Check for ungrounded circular dependency
        if (a.requires & b.requires) and not (a.provides or b.provides):
            incompatible.append("Both components require prerequisites that neither provides (deadlock risk).")

        return complementary, incompatible

    def couple(
        self,
        a: ComponentInterface,
        b: ComponentInterface,
        relationship: str,
        claimed_emergent_capability: str,
        emergent_mechanism: str,
        state: Optional[CognitiveState] = None,
    ) -> CouplingResult:
        """Couples two structures into a candidate compound composition.

        Audits:
        1. Confirms interface compatibility and rejects invariant clashes.
        2. Mandates explicit causal mechanism for emergence (rejects spurious assertion).
        3. Identifies remaining unresolved requirements.
        """
        deficits: list[KnowledgeDeficit] = []

        # 1. Require causal mechanism for emergence
        if not emergent_mechanism or len(emergent_mechanism.strip()) < 10:
            raise SpuriousCouplingError(
                f"Coupling between '{a.component_id}' and '{b.component_id}' rejected: "
                "No causal mechanism provided explaining how the relationship produces "
                f"emergent capability '{claimed_emergent_capability}'."
            )

        # 2. Analyze Interfaces
        complementary, incompatibilities = self.analyze_interfaces(a, b)

        # If incompatible invariants exist, fail or mark invalid
        if incompatibilities:
            deficit = KnowledgeDeficit(
                deficit_type=DeficitType.SEMANTIC_BINDING_DEFICIT,
                description=f"Incompatible interface friction in coupling: {'; '.join(incompatibilities)}",
                impacted_representation=f"{a.component_id} + {b.component_id}",
                required_to_resolve="Reconcile or isolate conflicting invariants before composition.",
            )
            deficits.append(deficit)
            if state is not None:
                state.record_deficit(deficit)

            delta = CognitiveDelta(
                delta_id=f"delta-{uuid.uuid4().hex[:8]}",
                nature=NatureType.COUPLING,
                input_summary={"a": a.component_id, "b": b.component_id, "rel": relationship},
                output_summary={"is_compatible": False, "incompatibilities": incompatibilities},
                objective_preserved=True,
                deficits_identified=deficits,
                authoritative_world_mutated=False,
            )

            return CouplingResult(
                component_a=a.component_id,
                component_b=b.component_id,
                relationship=relationship,
                is_compatible=False,
                composition=None,
                complementary_points=complementary,
                incompatibilities=incompatibilities,
                deficits=deficits,
                delta=delta,
            )

        # 3. Calculate remaining unresolved requirements
        all_reqs = (a.requires | b.requires)
        all_provs = (a.provides | b.provides)
        unresolved = sorted(all_reqs - all_provs)
        if unresolved:
            deficits.append(
                KnowledgeDeficit(
                    deficit_type=DeficitType.INPUT_DEFICIT,
                    description=f"Composite requires external dependencies: {unresolved}",
                    impacted_representation=f"Composite[{a.component_id},{b.component_id}]",
                    required_to_resolve=f"External provider for {unresolved}",
                )
            )

        # 4. Synthesize Candidate Composition
        comp_id = f"comp-{uuid.uuid4().hex[:8]}"
        comp = CandidateComposition(
            composition_id=comp_id,
            component_a=a.component_id,
            component_b=b.component_id,
            relationship=relationship,
            emergent_capability=claimed_emergent_capability,
            emergent_mechanism=emergent_mechanism,
            shared_invariants=list(dict.fromkeys(a.invariants + b.invariants)),
            unresolved_requirements=unresolved,
            is_valid=True,
        )

        delta = CognitiveDelta(
            delta_id=f"delta-{uuid.uuid4().hex[:8]}",
            nature=NatureType.COUPLING,
            input_summary={"a": a.component_id, "b": b.component_id, "rel": relationship},
            output_summary={
                "composition_id": comp_id,
                "is_compatible": True,
                "emergent_capability": claimed_emergent_capability,
            },
            objective_preserved=True,
            deficits_identified=deficits,
            authoritative_world_mutated=False,
        )

        if state is not None:
            state.candidate_compositions.append(comp.to_dict())
            for d in deficits:
                state.record_deficit(d)

        return CouplingResult(
            component_a=a.component_id,
            component_b=b.component_id,
            relationship=relationship,
            is_compatible=True,
            composition=comp,
            complementary_points=complementary,
            incompatibilities=[],
            deficits=deficits,
            delta=delta,
        )

    def _are_invariants_conflicting(self, inv_a: str, inv_b: str) -> bool:
        low_a = inv_a.lower()
        low_b = inv_b.lower()
        if "read_only" in low_a and "mutating" in low_b:
            return True
        if "mutating" in low_a and "read_only" in low_b:
            return True
        if "synchronous" in low_a and "async_only" in low_b:
            return True
        if "non-interactive" in low_a and "requires_interaction" in low_b:
            return True
        return False
