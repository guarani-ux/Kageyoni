"""
Source & Claim Provenance Graph (Pillars 4 & 8)

Enforces epistemic status categories, bidirectional lineage tracing,
uncertainty preservation, and forward contradiction propagation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set


class EpistemicStatus(Enum):
    SOURCE_FACT = "SOURCE_FACT"
    SYNTHESIS = "SYNTHESIS"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    CREATIVE_PROPOSITION = "CREATIVE_PROPOSITION"
    UNKNOWN = "UNKNOWN"


@dataclass
class SourceRecord:
    source_id: str
    title: str
    provenance: str  # URL, file path, physical document reference
    author_or_institution: str
    direct_excerpt: str
    date_recorded: float
    reliability_tier: str = "PRIMARY_CORROBORATED"  # PRIMARY_CORROBORATED | PRIMARY_UNVERIFIED | SECONDARY | ANECDOTAL


@dataclass
class ClaimNode:
    claim_id: str
    statement: str
    epistemic_status: EpistemicStatus
    provenance_sources: List[str] = field(default_factory=list)  # IDs of SourceRecords
    confidence_level: str = "HIGH"  # HIGH | MEDIUM | LOW | CONTESTED
    falsification_condition: str = ""  # What specific evidence would break this claim?
    parent_claim_ids: List[str] = field(default_factory=list)
    child_claim_ids: List[str] = field(default_factory=list)
    is_invalidated: bool = False
    invalidation_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "epistemic_status": self.epistemic_status.value,
            "provenance_sources": self.provenance_sources,
            "confidence_level": self.confidence_level,
            "falsification_condition": self.falsification_condition,
            "parent_claim_ids": self.parent_claim_ids,
            "child_claim_ids": self.child_claim_ids,
            "is_invalidated": self.is_invalidated,
            "invalidation_reason": self.invalidation_reason,
        }


class ClaimGraph:
    """
    Directed Acyclic Graph of verified sources and claims with bidirectional traversal.
    """

    def __init__(self):
        self.sources: Dict[str, SourceRecord] = {}
        self.claims: Dict[str, ClaimNode] = {}

    def add_source(self, source: SourceRecord) -> None:
        self.sources[source.source_id] = source

    def add_claim(self, claim: ClaimNode) -> None:
        # Enforce non-empty falsification condition for high-impact claims
        if claim.epistemic_status in (EpistemicStatus.SOURCE_FACT, EpistemicStatus.SYNTHESIS) and not claim.falsification_condition:
            claim.falsification_condition = "Unspecified counter-evidence or direct empirical contradiction."

        # Anti-laundering invariant: If claim has no provenance sources and no parent claims,
        # it CANNOT be designated as SOURCE_FACT
        if claim.epistemic_status == EpistemicStatus.SOURCE_FACT and not claim.provenance_sources:
            raise ValueError(f"EPISTEMIC_LAUNDERING: Claim '{claim.claim_id}' declared as SOURCE_FACT without provenance sources.")

        # Update child references on parents
        for pid in claim.parent_claim_ids:
            if pid in self.claims:
                if claim.claim_id not in self.claims[pid].child_claim_ids:
                    self.claims[pid].child_claim_ids.append(claim.claim_id)

        self.claims[claim.claim_id] = claim

    def invalidate_claim(self, claim_id: str, reason: str) -> List[str]:
        """
        Forward Contradiction Propagation:
        Recursively invalidates the target claim and all downstream dependent child claims.
        Returns the list of all invalidated claim IDs.
        """
        if claim_id not in self.claims:
            return []

        invalidated_ids: List[str] = []
        stack = [(claim_id, reason)]

        while stack:
            current_id, current_reason = stack.pop()
            node = self.claims[current_id]
            if not node.is_invalidated:
                node.is_invalidated = True
                node.invalidation_reason = current_reason
                invalidated_ids.append(current_id)

                # Propagate to all dependent child claims
                for cid in node.child_claim_ids:
                    stack.append((cid, f"Upstream dependency '{current_id}' invalidated: {current_reason}"))

        return invalidated_ids

    def trace_backward_lineage(self, claim_id: str) -> Dict[str, Any]:
        """
        Backward Lineage Walk:
        Traces from any claim back through its parent dependencies to the physical SourceRecords.
        """
        if claim_id not in self.claims:
            raise KeyError(f"Claim '{claim_id}' not found in claim graph.")

        node = self.claims[claim_id]
        lineage = {
            "claim_id": node.claim_id,
            "statement": node.statement,
            "epistemic_status": node.epistemic_status.value,
            "confidence_level": node.confidence_level,
            "is_invalidated": node.is_invalidated,
            "direct_sources": [
                {
                    "source_id": sid,
                    "title": self.sources[sid].title,
                    "provenance": self.sources[sid].provenance,
                    "author": self.sources[sid].author_or_institution,
                }
                for sid in node.provenance_sources if sid in self.sources
            ],
            "parent_lineages": [self.trace_backward_lineage(pid) for pid in node.parent_claim_ids if pid in self.claims],
        }
        return lineage

    def get_established_facts(self) -> List[ClaimNode]:
        """Returns valid, un-invalidated claims backed by high confidence."""
        return [
            c for c in self.claims.values()
            if not c.is_invalidated and c.epistemic_status in (EpistemicStatus.SOURCE_FACT, EpistemicStatus.SYNTHESIS) and c.confidence_level == "HIGH"
        ]

    def get_uncertain_claims(self) -> List[ClaimNode]:
        """Returns claims that carry epistemic uncertainty or low confidence."""
        return [
            c for c in self.claims.values()
            if not c.is_invalidated and (c.epistemic_status in (EpistemicStatus.HYPOTHESIS, EpistemicStatus.INFERENCE, EpistemicStatus.UNKNOWN) or c.confidence_level in ("LOW", "CONTESTED"))
        ]
