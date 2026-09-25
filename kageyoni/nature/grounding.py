"""3. GROUNDING Nature Transformation

Purpose:
Bind representations to conditions capable of independently resisting them.

Core process:
Claim/Hypothesis
→ Discriminating Condition
→ Independent Probe/Verifier
→ Evidence
→ Epistemic Update

Grounding distinguishes hypothesis, observation, belief, and verified fact.
It constructs probes, binds to authoritative verifiers, preserves negative and inconclusive
evidence, and exposes VERIFIER_DEFICIT when independent verification is unavailable.

Critical Invariant:
Grounding NEVER performs Hypothesis → Fact through internal reasoning alone.
Any attempt to self-certify an externally consequential conclusion without an authoritative
verifier receipt raises EpistemicLaunderingError.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .core import (
    CognitiveDelta,
    CognitiveHypothesis,
    CognitiveState,
    DeficitType,
    EpistemicCategory,
    EpistemicLaunderingError,
    KnowledgeDeficit,
    NatureType,
)


@dataclass
class VerificationProbe:
    """A constructed test probe to collide a hypothesis against independent resistance."""
    probe_id: str
    target_hypothesis_id: str
    discriminating_condition: str
    probe_type: str  # GATEWAY_CHECK | CODE_EXECUTION | DATABASE_INVARIANT | MANUAL_AUDIT
    probe_payload: dict[str, Any]
    expected_if_true: Any
    falsifying_if_observed: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "target_hypothesis_id": self.target_hypothesis_id,
            "discriminating_condition": self.discriminating_condition,
            "probe_type": self.probe_type,
            "probe_payload": self.probe_payload,
            "expected_if_true": self.expected_if_true,
            "falsifying_if_observed": self.falsifying_if_observed,
        }


@dataclass
class GroundingResult:
    """The result of colliding cognitive hypotheses with independent probes/evidence."""
    hypothesis_id: str
    original_status: EpistemicCategory
    updated_status: EpistemicCategory
    confidence: str
    probe: Optional[VerificationProbe]
    evidence_receipt: Optional[dict[str, Any]]
    disposition: str  # SUPPORTED | CONTRADICTED | INCONCLUSIVE | UNVERIFIED_DEFICIT
    is_falsified: bool
    deficits: list[KnowledgeDeficit]
    delta: CognitiveDelta

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "original_status": self.original_status.value,
            "updated_status": self.updated_status.value,
            "confidence": self.confidence,
            "probe": self.probe.to_dict() if self.probe else None,
            "evidence_receipt": self.evidence_receipt,
            "disposition": self.disposition,
            "is_falsified": self.is_falsified,
            "deficits": [d.to_dict() for d in self.deficits],
        }


class Grounding:
    """The Grounding Nature Transformation engine."""

    def construct_probe(
        self,
        hypothesis: CognitiveHypothesis,
        probe_type: str = "GATEWAY_CHECK",
        probe_payload: Optional[dict[str, Any]] = None,
    ) -> VerificationProbe:
        """Constructs an independent probe capable of falsifying or corroborating the hypothesis."""
        disc_cond = (
            hypothesis.falsification_condition
            or (hypothesis.discriminating_questions[0] if hypothesis.discriminating_questions else "")
            or f"Physical contradiction of: {hypothesis.statement}"
        )
        return VerificationProbe(
            probe_id=f"probe-{uuid.uuid4().hex[:8]}",
            target_hypothesis_id=hypothesis.hypothesis_id,
            discriminating_condition=disc_cond,
            probe_type=probe_type,
            probe_payload=probe_payload or {"statement": hypothesis.statement},
            expected_if_true=True,
            falsifying_if_observed=False,
        )

    def evaluate_with_verifier(
        self,
        hypothesis: CognitiveHypothesis,
        verifier_fn: Optional[Callable[[VerificationProbe], dict[str, Any]]] = None,
        probe: Optional[VerificationProbe] = None,
        state: Optional[CognitiveState] = None,
    ) -> GroundingResult:
        """Executes a grounding evaluation by presenting the probe to an external verifier.

        Enforces:
        - If verifier_fn is None, raises VERIFIER_DEFICIT; does NOT assume truth.
        - If verifier_fn returns a receipt, updates epistemic status accordingly.
        - Rejects internal self-certification to SOURCE_SUPPLIED_FACT or KAGEYONI_FACT.
        """
        active_probe = probe or self.construct_probe(hypothesis)
        deficits: list[KnowledgeDeficit] = []

        # 1. Check for missing verifier
        if verifier_fn is None:
            deficit = KnowledgeDeficit(
                deficit_type=DeficitType.VERIFIER_DEFICIT,
                description=f"No independent verifier available for hypothesis: '{hypothesis.statement}'",
                impacted_representation=hypothesis.hypothesis_id,
                required_to_resolve=f"Independent verifier capable of evaluating probe: {active_probe.discriminating_condition}",
            )
            deficits.append(deficit)
            if state is not None:
                state.record_deficit(deficit)

            delta = CognitiveDelta(
                delta_id=f"delta-{uuid.uuid4().hex[:8]}",
                nature=NatureType.GROUNDING,
                input_summary={"hypothesis_id": hypothesis.hypothesis_id},
                output_summary={"disposition": "UNVERIFIED_DEFICIT", "verifier_present": False},
                objective_preserved=True,
                deficits_identified=deficits,
                authoritative_world_mutated=False,
            )

            return GroundingResult(
                hypothesis_id=hypothesis.hypothesis_id,
                original_status=hypothesis.epistemic_status,
                updated_status=hypothesis.epistemic_status,
                confidence="UNVERIFIED",
                probe=active_probe,
                evidence_receipt=None,
                disposition="UNVERIFIED_DEFICIT",
                is_falsified=False,
                deficits=deficits,
                delta=delta,
            )

        # 2. Execute External Verifier
        receipt = verifier_fn(active_probe)

        # Verify receipt structure
        if not isinstance(receipt, dict) or "disposition" not in receipt:
            raise ValueError("External verifier returned malformed receipt missing 'disposition'.")

        disp = receipt["disposition"]  # supported | contradicted | inconclusive
        is_falsified = (disp == "contradicted")

        # 3. Apply Anti-Laundering Governance
        # Internal model reasoning alone can never declare a statement to be SOURCE_SUPPLIED_FACT
        claimed_category = receipt.get("category", EpistemicCategory.EVIDENCE_SUPPORTED_CLAIM)
        if claimed_category == EpistemicCategory.SOURCE_SUPPLIED_FACT:
            if not receipt.get("source_provenance_id"):
                raise EpistemicLaunderingError(
                    "Epistemic laundering violation: Cannot promote to SOURCE_SUPPLIED_FACT "
                    "without verifiable physical source provenance."
                )

        if disp == "supported":
            new_status = EpistemicCategory.EVIDENCE_SUPPORTED_CLAIM
            new_confidence = "HIGH" if (receipt.get("definitive") or "proves" in str(receipt.get("reason", "")).lower()) else "MEDIUM"
        elif disp == "contradicted":
            new_status = EpistemicCategory.ASSUMPTION
            new_confidence = "FALSIFIED"
            hypothesis.is_invalidated = True
            hypothesis.invalidation_reason = f"Falsified by external verifier receipt: {receipt.get('reason', 'Contradiction observed')}"
        else:  # inconclusive
            new_status = EpistemicCategory.ASSUMPTION
            new_confidence = "CONTESTED"

        hypothesis.epistemic_status = new_status
        hypothesis.confidence = new_confidence

        delta = CognitiveDelta(
            delta_id=f"delta-{uuid.uuid4().hex[:8]}",
            nature=NatureType.GROUNDING,
            input_summary={"hypothesis_id": hypothesis.hypothesis_id},
            output_summary={"disposition": disp, "new_status": new_status.value, "receipt": receipt},
            objective_preserved=True,
            deficits_identified=deficits,
            authoritative_world_mutated=False,
        )

        if state is not None:
            state.probes.append(active_probe.to_dict())
            state.observations.append({
                "probe_id": active_probe.probe_id,
                "disposition": disp,
                "receipt": receipt,
            })

        return GroundingResult(
            hypothesis_id=hypothesis.hypothesis_id,
            original_status=hypothesis.epistemic_status,
            updated_status=new_status,
            confidence=new_confidence,
            probe=active_probe,
            evidence_receipt=receipt,
            disposition=disp.upper(),
            is_falsified=is_falsified,
            deficits=deficits,
            delta=delta,
        )
