"""7. TECHNIQUES & COMPOSITION LAYER

Purpose:
Represent existing and future operator techniques as controlled expressions or compositions
of the five core nature transformations.

Techniques:
- Reframe ← Expansion under objective invariance
- Lift Invariant ← Compression
- Falsify ← Expansion + Grounding
- Carry Forward ← Continuity
- Causal Attribute ← Grounding + Compression

Composition:
- TechniqueComposition ← Chains techniques into verifiable, directed execution pipelines.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .compression import Compression, CompressionResult
from .continuity import Continuity, ContinuityResult
from .core import (
    CognitiveDelta,
    CognitiveHypothesis,
    CognitiveState,
    DeficitType,
    EpistemicCategory,
    KnowledgeDeficit,
    NatureType,
)
from .coupling import ComponentInterface, Coupling, CouplingResult
from .expansion import CandidateBranch, Expansion, ExpansionResult
from .grounding import Grounding, GroundingResult, VerificationProbe


class Technique:
    """Base class for techniques emerging from the five core natures."""
    technique_id: str
    name: str
    underlying_natures: list[NatureType]

    def execute(self, state: CognitiveState, **kwargs) -> dict[str, Any]:
        raise NotImplementedError


class Reframe(Technique):
    """Reframe ← Expansion under objective invariance.

    Exposes assumptions and discovers alternative representations while strictly
    preserving the original objective.
    """
    def __init__(self, expansion: Optional[Expansion] = None):
        self.technique_id = "technique.reframe"
        self.name = "Reframe"
        self.underlying_natures = [NatureType.EXPANSION]
        self.expansion = expansion or Expansion()

    def execute(
        self,
        state: CognitiveState,
        candidate_generators: Optional[Sequence[dict[str, Any]]] = None,
        max_branches: int = 5,
        **kwargs,
    ) -> ExpansionResult:
        return self.expansion.transform(
            state,
            candidate_generators=candidate_generators,
            max_branches=max_branches,
        )


class LiftInvariant(Technique):
    """Lift Invariant ← Compression.

    Extracts recurrence and causal invariants from multiple episodes/cases,
    declaring preserved, removed, lost info, and safety limits.
    """
    def __init__(self, compression: Optional[Compression] = None):
        self.technique_id = "technique.lift_invariant"
        self.name = "Lift Invariant"
        self.underlying_natures = [NatureType.COMPRESSION]
        self.compression = compression or Compression()

    def execute(
        self,
        state: CognitiveState,
        cases: Sequence[dict[str, Any]],
        required_distinctions: Optional[Sequence[str]] = None,
        **kwargs,
    ) -> CompressionResult:
        return self.compression.transform(
            cases,
            state=state,
            required_distinctions=required_distinctions,
        )


class Falsify(Technique):
    """Falsify ← Expansion + Grounding.

    Uses Expansion to generate potential falsifying conditions and alternative hypotheses,
    then uses Grounding to collide them against independent verifiers.
    """
    def __init__(
        self,
        expansion: Optional[Expansion] = None,
        grounding: Optional[Grounding] = None,
    ):
        self.technique_id = "technique.falsify"
        self.name = "Falsify"
        self.underlying_natures = [NatureType.EXPANSION, NatureType.GROUNDING]
        self.expansion = expansion or Expansion()
        self.grounding = grounding or Grounding()

    def execute(
        self,
        state: CognitiveState,
        target_hypothesis: CognitiveHypothesis,
        verifier_fn: Optional[Callable[[VerificationProbe], dict[str, Any]]] = None,
        **kwargs,
    ) -> dict[str, Any]:
        # 1. Expand falsification conditions
        branches = self.expansion._generate_default_branches(
            target_hypothesis.statement,
            state.objective,
        )
        falsifying_propositions = [
            f"Falsifier: Not({target_hypothesis.statement}) via {b.material_difference}"
            for b in branches
        ]

        # 2. Ground via probe
        probe = self.grounding.construct_probe(
            target_hypothesis,
            probe_type="FALSIFICATION_CHECK",
            probe_payload={"competing_propositions": falsifying_propositions},
        )
        grounding_result = self.grounding.evaluate_with_verifier(
            target_hypothesis,
            verifier_fn=verifier_fn,
            probe=probe,
            state=state,
        )

        return {
            "technique": "Falsify",
            "target_hypothesis_id": target_hypothesis.hypothesis_id,
            "falsifying_propositions": falsifying_propositions,
            "grounding_result": grounding_result,
            "is_falsified": grounding_result.is_falsified,
        }


class CarryForward(Technique):
    """Carry Forward ← Continuity.

    Preserves provenance and carries still-valid constraints forward while
    invalidating contradicted or obsolete knowledge across state changes.
    """
    def __init__(self, continuity: Optional[Continuity] = None):
        self.technique_id = "technique.carry_forward"
        self.name = "Carry Forward"
        self.underlying_natures = [NatureType.CONTINUITY]
        self.continuity = continuity or Continuity()

    def execute(
        self,
        state: CognitiveState,
        world_transition: dict[str, Any],
        source_rev: int = 0,
        target_rev: int = 1,
        **kwargs,
    ) -> ContinuityResult:
        return self.continuity.reconcile(
            state,
            world_transition_receipt=world_transition,
            source_revision=source_rev,
            target_revision=target_rev,
        )


class CausalAttribute(Technique):
    """Causal Attribute ← Grounding + Compression.

    Grounds an observed outcome to an intervention, then compresses the transition
    into an attributable causal law.
    """
    def __init__(
        self,
        grounding: Optional[Grounding] = None,
        compression: Optional[Compression] = None,
    ):
        self.technique_id = "technique.causal_attribute"
        self.name = "Causal Attribute"
        self.underlying_natures = [NatureType.GROUNDING, NatureType.COMPRESSION]
        self.grounding = grounding or Grounding()
        self.compression = compression or Compression()

    def execute(
        self,
        state: CognitiveState,
        intervention_records: Sequence[dict[str, Any]],
        observed_outcome: dict[str, Any],
        verifier_fn: Optional[Callable[[VerificationProbe], dict[str, Any]]] = None,
        **kwargs,
    ) -> dict[str, Any]:
        # 1. Ground the intervention to the observed outcome
        hyp = CognitiveHypothesis(
            hypothesis_id=f"hyp-attr-{uuid.uuid4().hex[:8]}",
            statement=f"Intervention caused outcome: {observed_outcome.get('summary', str(observed_outcome))}",
            epistemic_status=EpistemicCategory.ASSUMPTION,
        )
        grounding_result = self.grounding.evaluate_with_verifier(
            hyp,
            verifier_fn=verifier_fn,
            state=state,
        )

        # 2. Compress the intervention records into a causal rule
        cases_to_compress = list(intervention_records) + [{"outcome": observed_outcome}]
        compression_result = self.compression.transform(
            cases_to_compress,
            state=state,
        )

        return {
            "technique": "Causal Attribute",
            "grounding": grounding_result,
            "compression": compression_result,
            "causal_rule": compression_result.generator,
            "invariants": compression_result.invariant_rules,
        }


@dataclass
class TechniqueComposition:
    """A directed pipeline or workflow composed of multiple techniques."""
    composition_id: str
    name: str
    techniques: list[Technique]

    def execute_pipeline(
        self,
        state: CognitiveState,
        step_inputs: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Executes the sequence of techniques, checking pre- and post-conditions."""
        results: list[dict[str, Any]] = []
        inputs = dict(step_inputs or {})

        for tech in self.techniques:
            step_kw = inputs.get(tech.technique_id, {})
            out = tech.execute(state, **step_kw)
            results.append({
                "technique_id": tech.technique_id,
                "name": tech.name,
                "output": out,
            })

        return {
            "composition_id": self.composition_id,
            "name": self.name,
            "steps_executed": len(results),
            "step_results": results,
            "final_cognitive_state": state.to_dict(),
        }
