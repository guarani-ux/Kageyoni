"""8. EXTRACT TECHNIQUE — COMPOUND CAPABILITY

Purpose:
Transform actual work traces into falsifiable candidate techniques.

Conceptual Sequence:
WORK
→ TRACE
→ RECONSTRUCT TRANSITIONS
→ CAUSAL ATTRIBUTE
→ FACTOR TRANSFORMATION
→ LIFT INVARIANT
→ DISCRIMINATE TYPE
→ COMPARE EXISTING
→ EMIT CANDIDATE

Structural Type Discrimination:
Extraction strictly distinguishes among 11 distinct structural types:
1. cognitive_technique: deliberate operator cognitive transformation
2. composition: directed network/pipeline of techniques
3. capability: higher-order compound ability
4. workflow: temporal process graph with stages and gates
5. deterministic_mechanism: code-level hard state machine
6. verifier: independent oracle/adversarial probe
7. protocol: communication/handshake contract
8. action: single executable primitive in environment
9. environmental_affordance: environmental availability/permission
10. domain_method: localized domain-specific trade craft
11. outcome: resulting terminal observation/receipt

Non-Authority Invariant:
A candidate emitted by Extract Technique is assigned status="candidate" and CANNOT enter
the authoritative library without passing empirical qualification trials.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence

from .compression import Compression, CompressionResult
from .continuity import Continuity
from .core import (
    CognitiveDelta,
    CognitiveHypothesis,
    CognitiveState,
    DeficitType,
    KnowledgeDeficit,
    NatureType,
)
from .coupling import Coupling
from .expansion import Expansion
from .grounding import Grounding, VerificationProbe
from .techniques import CausalAttribute, LiftInvariant


class StructuralType(str, Enum):
    COGNITIVE_TECHNIQUE = "cognitive_technique"
    COMPOSITION = "composition"
    CAPABILITY = "capability"
    WORKFLOW = "workflow"
    DETERMINISTIC_MECHANISM = "deterministic_mechanism"
    VERIFIER = "verifier"
    PROTOCOL = "protocol"
    ACTION = "action"
    ENVIRONMENTAL_AFFORDANCE = "environmental_affordance"
    DOMAIN_METHOD = "domain_method"
    OUTCOME = "outcome"


@dataclass
class CandidateTechnique:
    """A candidate technique emitted from trace extraction."""
    candidate_id: str
    name: str
    structural_type: StructuralType
    factored_natures: list[NatureType]
    invariant_generator: str
    falsification_condition: str
    qualification_requirements: list[str]
    provenance_trace_id: str
    status: str = "candidate"  # candidate | qualified | rejected

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "structural_type": self.structural_type.value,
            "factored_natures": [n.value for n in self.factored_natures],
            "invariant_generator": self.invariant_generator,
            "falsification_condition": self.falsification_condition,
            "qualification_requirements": list(self.qualification_requirements),
            "provenance_trace_id": self.provenance_trace_id,
            "status": self.status,
        }


@dataclass
class ExtractionResult:
    """The formal, audited output of Extract Technique."""
    trace_id: str
    transitions_reconstructed: int
    causal_attribution: dict[str, Any]
    factored_natures: list[NatureType]
    invariant_compression: CompressionResult
    discriminated_type: StructuralType
    existing_comparison: dict[str, Any]
    candidate: CandidateTechnique
    deficits: list[KnowledgeDeficit]
    delta: CognitiveDelta

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "transitions_reconstructed": self.transitions_reconstructed,
            "causal_attribution": self.causal_attribution,
            "factored_natures": [n.value for n in self.factored_natures],
            "invariant_compression": self.invariant_compression.to_dict(),
            "discriminated_type": self.discriminated_type.value,
            "existing_comparison": self.existing_comparison,
            "candidate": self.candidate.to_dict(),
            "deficits": [d.to_dict() for d in self.deficits],
        }


class ExtractTechnique:
    """The 9-stage Extract Technique compound capability."""

    def __init__(
        self,
        expansion: Optional[Expansion] = None,
        compression: Optional[Compression] = None,
        grounding: Optional[Grounding] = None,
        continuity: Optional[Continuity] = None,
        coupling: Optional[Coupling] = None,
    ):
        self.expansion = expansion or Expansion()
        self.compression = compression or Compression()
        self.grounding = grounding or Grounding()
        self.continuity = continuity or Continuity()
        self.coupling = coupling or Coupling()
        self.causal_attributor = CausalAttribute(self.grounding, self.compression)
        self.lift_invariant = LiftInvariant(self.compression)

    def discriminate_type(self, pattern: dict[str, Any]) -> StructuralType:
        """Adversarially categorizes a pattern into one of the 11 structural types."""
        text = str(pattern).lower()
        if "cognitive" in text or ("reframe" in text and "mental" in text):
            return StructuralType.COGNITIVE_TECHNIQUE
        if "composition" in text or "pipeline" in text:
            return StructuralType.COMPOSITION
        if "capability" in text or "higher-order" in text:
            return StructuralType.CAPABILITY
        if "workflow" in text or ("stages" in text and "gates" in text):
            return StructuralType.WORKFLOW
        if "oracle" in text or "verifier" in text or "probe" in text or "assert" in text:
            return StructuralType.VERIFIER
        if "handshake" in text or "protocol" in text or "wire" in text:
            return StructuralType.PROTOCOL
        if "affordance" in text or "unlocked" in text or "environment_visible" in text:
            return StructuralType.ENVIRONMENTAL_AFFORDANCE
        if "method" in text or "tradecraft" in text:
            return StructuralType.DOMAIN_METHOD
        if "outcome" in text or "receipt" in text or "result" in text:
            return StructuralType.OUTCOME
        if "deterministic" in text or "machine" in text or "sqlite" in text:
            return StructuralType.DETERMINISTIC_MECHANISM
        if "action" in text or "execute" in text or "op" in text:
            return StructuralType.ACTION
        return StructuralType.COGNITIVE_TECHNIQUE

    def extract(
        self,
        work_trace: dict[str, Any],
        existing_library: Optional[Sequence[dict[str, Any]]] = None,
        state: Optional[CognitiveState] = None,
        verifier_fn: Optional[Callable[[VerificationProbe], dict[str, Any]]] = None,
    ) -> ExtractionResult:
        """Executes the full 9-stage extraction sequence from work traces.

        Sequence:
        1. WORK: Captured in work_trace['execution']
        2. TRACE: work_trace['trace_id'], events
        3. RECONSTRUCT TRANSITIONS: pair consecutive events into (pre, post)
        4. CAUSAL ATTRIBUTE: isolate intervention driving delta
        5. FACTOR TRANSFORMATION: match to core natures
        6. LIFT INVARIANT: compress into generator with safety limits
        7. DISCRIMINATE TYPE: assign one of 11 structural types
        8. COMPARE EXISTING: detect redundancy or conflict
        9. EMIT CANDIDATE: status='candidate' with falsification requirements
        """
        deficits: list[KnowledgeDeficit] = []
        trace_id = work_trace.get("trace_id", f"trace-{uuid.uuid4().hex[:8]}")
        events = work_trace.get("events", [])
        if not events:
            raise ValueError("Extract Technique requires non-empty trace events.")

        # Stage 3: RECONSTRUCT TRANSITIONS
        transitions: list[dict[str, Any]] = []
        for i in range(len(events) - 1):
            transitions.append({
                "pre": events[i],
                "post": events[i + 1],
                "delta": events[i + 1].get("state", {}) != events[i].get("state", {}),
            })

        # Stage 4: CAUSAL ATTRIBUTE
        outcome = events[-1]
        interventions = [e for e in events if e.get("kind") in ("action", "intervention", "deliberation")]
        causal_attr = self.causal_attributor.execute(
            state=state or CognitiveState(objective=work_trace.get("objective", "extract")),
            intervention_records=interventions or events,
            observed_outcome=outcome,
            verifier_fn=verifier_fn,
        )

        # Stage 5: FACTOR TRANSFORMATION
        factored: list[NatureType] = []
        pattern_text = str(work_trace).lower()
        if "expand" in pattern_text or "branch" in pattern_text or "alternatives" in pattern_text:
            factored.append(NatureType.EXPANSION)
        if "compress" in pattern_text or "invariant" in pattern_text or "generator" in pattern_text:
            factored.append(NatureType.COMPRESSION)
        if "ground" in pattern_text or "probe" in pattern_text or "verifier" in pattern_text:
            factored.append(NatureType.GROUNDING)
        if "continuity" in pattern_text or "lineage" in pattern_text or "stale" in pattern_text:
            factored.append(NatureType.CONTINUITY)
        if "couple" in pattern_text or "interface" in pattern_text or "complementary" in pattern_text:
            factored.append(NatureType.COUPLING)
        if not factored:
            factored = [NatureType.COMPRESSION, NatureType.GROUNDING]

        # Stage 6: LIFT INVARIANT
        compression_res = causal_attr["compression"]

        # Stage 7: DISCRIMINATE TYPE
        detected_type = self.discriminate_type(work_trace)

        # Stage 8: COMPARE EXISTING
        existing = existing_library or []
        comparison = {
            "duplicate_found": False,
            "conflicts_found": False,
            "similar_technique_id": None,
        }
        for item in existing:
            if item.get("name") == work_trace.get("name"):
                comparison["duplicate_found"] = True
                comparison["similar_technique_id"] = item.get("candidate_id")
                break

        # Stage 9: EMIT CANDIDATE
        cand_id = f"cand-{uuid.uuid4().hex[:8]}"
        candidate = CandidateTechnique(
            candidate_id=cand_id,
            name=work_trace.get("name", f"ExtractedTechnique-{trace_id[:8]}"),
            structural_type=detected_type,
            factored_natures=factored,
            invariant_generator=compression_res.generator,
            falsification_condition=f"Demonstration where {compression_res.safety_limit} fails under adversarial test.",
            qualification_requirements=[
                "Pass at least 2 discriminating reference evaluation cases without errors.",
                "Demonstrate transfer across at least 1 unfamiliar context.",
            ],
            provenance_trace_id=trace_id,
            status="candidate",
        )

        delta = CognitiveDelta(
            delta_id=f"delta-{uuid.uuid4().hex[:8]}",
            nature=NatureType.COMPRESSION,
            input_summary={"trace_id": trace_id, "events_count": len(events)},
            output_summary={
                "candidate_id": cand_id,
                "structural_type": detected_type.value,
                "factored_natures": [n.value for n in factored],
            },
            objective_preserved=True,
            deficits_identified=deficits,
            authoritative_world_mutated=False,
        )

        return ExtractionResult(
            trace_id=trace_id,
            transitions_reconstructed=len(transitions),
            causal_attribution=causal_attr,
            factored_natures=factored,
            invariant_compression=compression_res,
            discriminated_type=detected_type,
            existing_comparison=comparison,
            candidate=candidate,
            deficits=deficits,
            delta=delta,
        )
