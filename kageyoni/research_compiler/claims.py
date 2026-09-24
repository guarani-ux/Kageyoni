"""
Source & Claim Provenance Graph (Pillars 4 & 8) - Hardened (Gates G2 & G3).

Enforces epistemic status categories, bidirectional lineage tracing,
uncertainty preservation, literal source assertion vs warranted claim separation,
and forward contradiction propagation.
"""

from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set


class EpistemicLaunderingError(ValueError):
    """Raised when an assertion illegally sheds uncertainty, assumption, or provenance."""
    pass


class EpistemicStatus(Enum):
    # Canonical 9 categories from contracts/epistemic_ledger.py
    SOURCE_SUPPLIED_FACT = "SOURCE_SUPPLIED_FACT"
    EVIDENCE_SUPPORTED_CLAIM = "EVIDENCE_SUPPORTED_CLAIM"
    INFERENCE = "INFERENCE"
    ASSUMPTION = "ASSUMPTION"
    HEURISTIC = "HEURISTIC"
    INTERPRETATION = "INTERPRETATION"
    CREATIVE_DECISION = "CREATIVE_DECISION"
    PREFERENCE = "PREFERENCE"
    UNKNOWN = "UNKNOWN"

    # Backward-compatible aliases for research_compiler callers
    SOURCE_FACT = "SOURCE_SUPPLIED_FACT"
    SYNTHESIS = "EVIDENCE_SUPPORTED_CLAIM"
    HYPOTHESIS = "ASSUMPTION"
    CREATIVE_PROPOSITION = "CREATIVE_DECISION"


@dataclass
class SourceRecord:
    source_id: str
    title: str
    provenance: str  # URL, file path, physical document reference
    author_or_institution: str
    direct_excerpt: str
    date_recorded: float
    reliability_tier: str = "PRIMARY_CORROBORATED"  # PRIMARY_CORROBORATED | PRIMARY_UNVERIFIED | SECONDARY | ANECDOTAL
    content_hash: str = ""
    source_says_statement: str = ""  # Literal assertion made by the source

    def __post_init__(self):
        if not self.content_hash and self.direct_excerpt:
            self.content_hash = hashlib.sha256(self.direct_excerpt.encode("utf-8")).hexdigest()
        if not self.source_says_statement and self.direct_excerpt:
            self.source_says_statement = self.direct_excerpt

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "provenance": self.provenance,
            "author_or_institution": self.author_or_institution,
            "direct_excerpt": self.direct_excerpt,
            "date_recorded": self.date_recorded,
            "reliability_tier": self.reliability_tier,
            "content_hash": self.content_hash,
            "source_says_statement": self.source_says_statement,
        }


@dataclass
class ClaimNode:
    claim_id: str
    statement: str
    epistemic_status: EpistemicStatus
    provenance_sources: List[str] = field(default_factory=list)  # IDs of SourceRecords
    confidence_level: str = "UNSPECIFIED"  # HIGH | MEDIUM | LOW | CONTESTED | UNSPECIFIED
    falsification_condition: str = ""  # What specific evidence would break this claim?
    parent_claim_ids: List[str] = field(default_factory=list)
    child_claim_ids: List[str] = field(default_factory=list)
    is_invalidated: bool = False
    invalidation_reason: Optional[str] = None
    evidence_establishes_claim: str = ""  # What the warranted analysis specifically concludes
    modality: str = "UNSPECIFIED"  # POSSIBLE | PROBABLE | CERTAIN | UNSPECIFIED
    quantifier: str = "UNSPECIFIED"  # SOME | MANY | MOST | ALL | UNSPECIFIED
    uncertainties: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.evidence_establishes_claim and self.statement:
            self.evidence_establishes_claim = self.statement

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
            "evidence_establishes_claim": self.evidence_establishes_claim,
            "modality": self.modality,
            "quantifier": self.quantifier,
            "uncertainties": list(self.uncertainties),
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
        canonical_status = claim.epistemic_status.value
        if canonical_status in (
            EpistemicStatus.SOURCE_SUPPLIED_FACT.value,
            EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM.value,
        ) and not claim.falsification_condition:
            claim.falsification_condition = "Unspecified counter-evidence or direct empirical contradiction."

        # Anti-laundering invariant: If claim has no provenance sources and no parent claims,
        # it CANNOT be designated as SOURCE_SUPPLIED_FACT
        if canonical_status == EpistemicStatus.SOURCE_SUPPLIED_FACT.value and not claim.provenance_sources:
            raise EpistemicLaunderingError(f"EPISTEMIC_LAUNDERING: Claim '{claim.claim_id}' declared as SOURCE_SUPPLIED_FACT without provenance sources.")

        # Grounding check: verify that all referenced provenance_sources actually exist in self.sources
        for sid in claim.provenance_sources:
            if sid not in self.sources:
                raise ValueError(f"UNGROUNDED_CLAIM: Provenance source '{sid}' referenced by claim '{claim.claim_id}' does not exist in graph.")

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
        Guarantees cycle detection and safe propagation without infinite loops.
        Returns the list of all invalidated claim IDs.
        """
        if claim_id not in self.claims:
            return []

        invalidated_ids: List[str] = []
        visited: Set[str] = set()
        stack = [(claim_id, reason)]

        while stack:
            current_id, current_reason = stack.pop()
            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id in self.claims:
                node = self.claims[current_id]
                node.is_invalidated = True
                node.invalidation_reason = current_reason
                invalidated_ids.append(current_id)

                # Propagate to all dependent child claims
                for cid in node.child_claim_ids:
                    if cid not in visited and cid in self.claims:
                        stack.append((cid, f"Upstream dependency '{current_id}' invalidated: {current_reason}"))

        return invalidated_ids

    def invalidate_claim_with_cascade(
        self,
        claim_id: str,
        reason: str,
        db: Optional[Any] = None,
    ) -> Any:
        """
        Consolidates graph invalidation with downstream store cascading and UnitOfWork protection.
        """
        from .invalidation_engine import InvalidationEngine
        engine = InvalidationEngine(db)
        return engine.invalidate_claim_with_cascade(self, claim_id, reason)

    def trace_backward_lineage(self, claim_id: str) -> Dict[str, Any]:
        """
        Backward Lineage Walk:
        Traces from any claim back through its parent dependencies to physical SourceRecords.
        """
        if claim_id not in self.claims:
            raise KeyError(f"Claim '{claim_id}' not found in claim graph.")

        node = self.claims[claim_id]
        lineage = {
            "claim_id": node.claim_id,
            "statement": node.statement,
            "evidence_establishes_claim": node.evidence_establishes_claim,
            "epistemic_status": node.epistemic_status.value,
            "confidence_level": node.confidence_level,
            "modality": node.modality,
            "quantifier": node.quantifier,
            "uncertainties": list(node.uncertainties),
            "is_invalidated": node.is_invalidated,
            "direct_sources": [
                {
                    "source_id": sid,
                    "title": self.sources[sid].title,
                    "provenance": self.sources[sid].provenance,
                    "author": self.sources[sid].author_or_institution,
                    "content_hash": self.sources[sid].content_hash,
                    "source_says_statement": self.sources[sid].source_says_statement,
                    "direct_excerpt": self.sources[sid].direct_excerpt,
                }
                for sid in node.provenance_sources if sid in self.sources
            ],
            "parent_lineages": [self.trace_backward_lineage(pid) for pid in node.parent_claim_ids if pid in self.claims],
        }
        return lineage

    @staticmethod
    def validate_transition(
        current_status: str | EpistemicStatus,
        new_status: str | EpistemicStatus,
        warrant_or_reasoning: Optional[str] = None,
        provenance_sources: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
    ) -> None:
        """
        Validates transition between epistemic statuses enforcing strict warrants.
        Replaces keyword-based heuristics with structural verification.
        """
        curr = current_status.value if isinstance(current_status, EpistemicStatus) else str(current_status)
        target = new_status.value if isinstance(new_status, EpistemicStatus) else str(new_status)

        warranted = {
            EpistemicStatus.SOURCE_SUPPLIED_FACT.value,
            EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM.value,
        }

        # 1. Assumption promotion gate
        if curr == EpistemicStatus.ASSUMPTION.value and target in warranted:
            raise EpistemicLaunderingError(
                f"Laundering detected: Cannot promote ASSUMPTION to {target} without external warrant and empirical provenance."
            )

        # 2. Creative decision promotion gate
        if curr == EpistemicStatus.CREATIVE_DECISION.value and target in warranted:
            raise EpistemicLaunderingError(
                f"Laundering detected: CREATIVE_DECISION cannot be promoted to {target}."
            )

        # 3. Unknown resolution gate (replaces keyword heuristics with structural warrants)
        if curr == EpistemicStatus.UNKNOWN.value and target != EpistemicStatus.UNKNOWN.value:
            if not warrant_or_reasoning or len(warrant_or_reasoning.strip()) < 10:
                raise EpistemicLaunderingError(
                    "Laundering detected: UNKNOWN state cannot be resolved without explicit, substantive warrant."
                )
            if target in warranted and not provenance_sources:
                raise EpistemicLaunderingError(
                    f"Laundering detected: UNKNOWN state cannot be promoted to {target} without verified provenance sources."
                )
            if target == EpistemicStatus.INFERENCE.value and (not dependencies or len(dependencies) == 0):
                raise EpistemicLaunderingError(
                    "Laundering detected: INFERENCE cannot be derived without declared valid dependencies."
                )

        # 4. Target requirement gates
        if target == EpistemicStatus.SOURCE_SUPPLIED_FACT.value and not provenance_sources:
            raise EpistemicLaunderingError("SOURCE_SUPPLIED_FACT requires an identifiable provenance_source.")
        if target == EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM.value and not warrant_or_reasoning:
            raise EpistemicLaunderingError("EVIDENCE_SUPPORTED_CLAIM requires an identifiable warrant_or_reasoning.")

    def get_established_facts(self) -> List[ClaimNode]:
        """Returns valid, un-invalidated claims backed by high confidence or verified source facts."""
        return [
            c for c in self.claims.values()
            if not c.is_invalidated
            and (
                (
                    c.epistemic_status.value == EpistemicStatus.SOURCE_SUPPLIED_FACT.value
                    and c.confidence_level not in ("LOW", "CONTESTED")
                )
                or (
                    c.epistemic_status.value == EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM.value
                    and c.confidence_level == "HIGH"
                )
            )
        ]

    def get_uncertain_claims(self) -> List[ClaimNode]:
        """Returns claims that carry epistemic uncertainty or low confidence."""
        return [
            c for c in self.claims.values()
            if not c.is_invalidated
            and (
                c.epistemic_status.value in (
                    EpistemicStatus.ASSUMPTION.value,
                    EpistemicStatus.INFERENCE.value,
                    EpistemicStatus.HEURISTIC.value,
                    EpistemicStatus.UNKNOWN.value,
                )
                or c.confidence_level in ("LOW", "CONTESTED")
                or len(c.uncertainties) > 0
            )
        ]

    def verify_no_laundering(self) -> bool:
        """Audits the full graph to ensure no assumption or ungrounded proposition was laundered into factual truth."""
        warranted = {
            EpistemicStatus.SOURCE_SUPPLIED_FACT.value,
            EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM.value,
        }
        for claim in self.claims.values():
            if claim.epistemic_status.value in warranted:
                for pid in claim.parent_claim_ids:
                    parent = self.claims.get(pid)
                    if parent and parent.epistemic_status.value in (
                        EpistemicStatus.ASSUMPTION.value,
                        EpistemicStatus.UNKNOWN.value,
                    ):
                        return False
        return True
