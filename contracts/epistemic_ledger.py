"""
contracts/epistemic_ledger.py
Foundational Epistemic Integrity Ledger for Reliable Communication.

Folded into kageyoni.research_compiler.claims (Slice CP-03).
Provides full backward compatibility while delegating all graph operations,
anti-laundering checks, and epistemic category validations to the canonical ClaimGraph.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Literal

from kageyoni.research_compiler.claims import (
    EpistemicStatus as CanonicalEpistemicStatus,
    EpistemicLaunderingError,
    ClaimGraph,
    ClaimNode,
    SourceRecord,
)

EPISTEMIC_STATUSES = (
    "SOURCE_SUPPLIED_FACT",
    "EVIDENCE_SUPPORTED_CLAIM",
    "INFERENCE",
    "ASSUMPTION",
    "HEURISTIC",
    "INTERPRETATION",
    "CREATIVE_DECISION",
    "PREFERENCE",
    "UNKNOWN",
)

EpistemicStatus = Literal[
    "SOURCE_SUPPLIED_FACT",
    "EVIDENCE_SUPPORTED_CLAIM",
    "INFERENCE",
    "ASSUMPTION",
    "HEURISTIC",
    "INTERPRETATION",
    "CREATIVE_DECISION",
    "PREFERENCE",
    "UNKNOWN",
]


@dataclass(frozen=True)
class EpistemicStatement:
    statement_id: str
    proposition: str
    status: EpistemicStatus
    provenance_source: str | None = None
    warrant_or_reasoning: str | None = None
    uncertainties: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()

    def __post_init__(self):
        if self.status not in EPISTEMIC_STATUSES:
            raise EpistemicLaunderingError(f"Invalid epistemic status: '{self.status}'. Must be one of {EPISTEMIC_STATUSES}")
        if self.status == "SOURCE_SUPPLIED_FACT" and not self.provenance_source:
            raise EpistemicLaunderingError("SOURCE_SUPPLIED_FACT requires an identifiable provenance_source.")
        if self.status == "EVIDENCE_SUPPORTED_CLAIM" and not self.warrant_or_reasoning:
            raise EpistemicLaunderingError("EVIDENCE_SUPPORTED_CLAIM requires an identifiable warrant_or_reasoning.")
        if self.status == "INFERENCE" and not self.dependencies:
            raise EpistemicLaunderingError("INFERENCE requires explicitly declared parent dependencies.")

    def digest(self) -> str:
        payload = {
            "statement_id": self.statement_id,
            "proposition": self.proposition,
            "status": self.status,
            "provenance_source": self.provenance_source,
            "warrant_or_reasoning": self.warrant_or_reasoning,
            "uncertainties": self.uncertainties,
            "dependencies": self.dependencies,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def to_claim_node(self) -> ClaimNode:
        """Converts an EpistemicStatement to a canonical ClaimNode."""
        status = CanonicalEpistemicStatus(self.status)
        return ClaimNode(
            claim_id=self.statement_id,
            statement=self.proposition,
            epistemic_status=status,
            provenance_sources=[self.provenance_source] if self.provenance_source else [],
            parent_claim_ids=list(self.dependencies),
            evidence_establishes_claim=self.warrant_or_reasoning or self.proposition,
            uncertainties=list(self.uncertainties),
        )

    @classmethod
    def from_claim_node(cls, node: ClaimNode, provenance_source: str | None = None) -> EpistemicStatement:
        """Constructs an EpistemicStatement from a canonical ClaimNode."""
        prov = provenance_source or (node.provenance_sources[0] if node.provenance_sources else None)
        return cls(
            statement_id=node.claim_id,
            proposition=node.statement,
            status=node.epistemic_status.value,
            provenance_source=prov,
            warrant_or_reasoning=node.evidence_establishes_claim,
            uncertainties=tuple(node.uncertainties),
            dependencies=tuple(node.parent_claim_ids),
        )


class EpistemicLedger:
    """
    Tracks propositions across transformations, ensuring uncertainty and provenance are preserved.
    Delegates graph custody to the canonical ClaimGraph.
    """
    def __init__(self, graph: ClaimGraph | None = None):
        self.graph = graph or ClaimGraph()
        self._statements: dict[str, EpistemicStatement] = {}

    def record(self, statement: EpistemicStatement) -> EpistemicStatement:
        # Ensure provenance source exists in canonical graph
        if statement.provenance_source and statement.provenance_source not in self.graph.sources:
            src = SourceRecord(
                source_id=statement.provenance_source,
                title=statement.provenance_source,
                provenance=statement.provenance_source,
                author_or_institution="ledger_adapter",
                direct_excerpt="",
                date_recorded=0.0,
                reliability_tier="PRIMARY_UNVERIFIED",
                source_says_statement="",
            )
            self.graph.add_source(src)

        # Mirror statement in canonical ClaimGraph
        claim_node = statement.to_claim_node()
        self.graph.add_claim(claim_node)
        self._statements[statement.statement_id] = statement
        return statement

    def transform(
        self,
        *,
        source_id: str,
        target_id: str,
        new_proposition: str,
        new_status: EpistemicStatus,
        reasoning: str,
        provenance_source: str | None = None,
        uncertainties: tuple[str, ...] | None = None,
    ) -> EpistemicStatement:
        """Derives a downstream statement while preventing illegal status promotions."""
        parent = self._statements.get(source_id)
        if not parent:
            raise KeyError(f"Parent statement '{source_id}' not found in ledger.")

        target_prov = provenance_source or parent.provenance_source
        prov_sources = [target_prov] if target_prov else []

        # Delegate transition validation to ClaimGraph canonical rules
        self.graph.validate_transition(
            current_status=parent.status,
            new_status=new_status,
            warrant_or_reasoning=reasoning,
            provenance_sources=prov_sources,
            dependencies=[parent.statement_id],
        )

        child = EpistemicStatement(
            statement_id=target_id,
            proposition=new_proposition,
            status=new_status,
            provenance_source=target_prov,
            warrant_or_reasoning=reasoning,
            uncertainties=uncertainties if uncertainties is not None else parent.uncertainties,
            dependencies=(parent.statement_id,),
        )
        return self.record(child)

    def verify_no_laundering(self) -> bool:
        """Audits the full graph to ensure no assumption or creative preference was promoted to factual truth."""
        return self.graph.verify_no_laundering()

