"""
Source & Claim Provenance Graph (Pillars 4 & 8) - Hardened (Gates G2 & G3).

Enforces epistemic status categories, bidirectional lineage tracing,
uncertainty preservation, literal source assertion vs warranted claim separation,
and forward contradiction propagation.
Topology is authoritatively owned by kageyoni.graph.CausalDAG; ClaimNode parent_claim_ids
and child_claim_ids are dynamic compatibility views projected from CausalDAG.
"""

from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from collections.abc import MutableSequence
from typing import Dict, List, Optional, Any, Set

from kageyoni.graph import CausalDAG, CycleDetectedError


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


class ClaimEdgeList(MutableSequence):
    """Sequence view; bound mutations use the graph's checked topology owner."""
    def __init__(self, node_id, edge_type, graph, initial=None):
        self.node_id, self.edge_type, self.graph = node_id, edge_type, graph
        self._initial = list(initial or [])

    @property
    def _is_bound_to_dag(self):
        return self.graph is not None and self.node_id in self.graph._dag

    def _values(self):
        if not self._is_bound_to_dag:
            return self._initial
        node = self.graph._dag.get_node(self.node_id)
        return sorted(node.dependencies if self.edge_type == "parents" else node.dependents)

    def __len__(self): return len(self._values())
    def __getitem__(self, index): return self._values()[index]
    def __iter__(self): return iter(self._values())
    def __repr__(self): return repr(self._values())
    def __eq__(self, other): return list(self) == list(other)
    def __setitem__(self, index, value):
        values = list(self); values[index] = value; self._replace(values)
    def __delitem__(self, index):
        values = list(self); del values[index]; self._replace(values)
    def insert(self, index, value):
        values = list(self); values.insert(index, value); self._replace(values)

    def _replace(self, values):
        if not self._is_bound_to_dag:
            self._initial = list(values)
            return
        dag = self.graph._dag
        for value in values:
            dag.get_node(value)
            parent, child = (value, self.node_id) if self.edge_type == "parents" else (self.node_id, value)
            if parent == child or dag._is_reachable(child, parent):
                raise CycleDetectedError(f"CYCLE_DETECTED: {parent} -> {child}")
        old = set(self)
        for value in old - set(values):
            parent, child = (value, self.node_id) if self.edge_type == "parents" else (self.node_id, value)
            dag.remove_edge(parent, child)
        for value in set(values) - old:
            parent, child = (value, self.node_id) if self.edge_type == "parents" else (self.node_id, value)
            dag.add_edge(parent, child)


class ClaimNode:
    """
    Epistemic claim record. Parent and child lineages are compatibility
    projections derived from the authoritative CausalDAG.
    """

    def __init__(
        self,
        claim_id: str,
        statement: str,
        epistemic_status: EpistemicStatus | str,
        provenance_sources: Optional[List[str]] = None,
        confidence_level: str = "UNSPECIFIED",
        falsification_condition: str = "",
        parent_claim_ids: Optional[List[str]] = None,
        child_claim_ids: Optional[List[str]] = None,
        is_invalidated: bool = False,
        invalidation_reason: Optional[str] = None,
        evidence_establishes_claim: str = "",
        modality: str = "UNSPECIFIED",
        quantifier: str = "UNSPECIFIED",
        uncertainties: Optional[List[str]] = None,
        graph: Optional[Any] = None,
    ):
        self.claim_id = claim_id
        self.statement = statement
        self.epistemic_status = epistemic_status if isinstance(epistemic_status, EpistemicStatus) else EpistemicStatus(epistemic_status)
        self.provenance_sources = list(provenance_sources or [])
        self.confidence_level = confidence_level
        self.falsification_condition = falsification_condition
        self._graph = graph
        self._parent_claim_ids = ClaimEdgeList(claim_id, "parents", graph, initial=parent_claim_ids)
        self._child_claim_ids = ClaimEdgeList(claim_id, "children", graph, initial=child_claim_ids)
        self.is_invalidated = is_invalidated
        self.invalidation_reason = invalidation_reason
        self.evidence_establishes_claim = evidence_establishes_claim or statement
        self.modality = modality
        self.quantifier = quantifier
        self.uncertainties = list(uncertainties or [])

    @property
    def is_invalidated(self):
        if self._graph is not None and self.claim_id in self._graph._dag:
            return self._graph._dag.get_node(self.claim_id).status == "INVALIDATED"
        return self._is_invalidated

    @is_invalidated.setter
    def is_invalidated(self, value):
        if self._graph is not None and self.claim_id in self._graph._dag:
            self._graph._dag.get_node(self.claim_id).status = "INVALIDATED" if value else "VALID"
        else:
            self._is_invalidated = value

    @property
    def invalidation_reason(self):
        if self._graph is not None and self.claim_id in self._graph._dag:
            return self._graph._dag.get_node(self.claim_id).invalidation_reason
        return self._invalidation_reason

    @invalidation_reason.setter
    def invalidation_reason(self, value):
        if self._graph is not None and self.claim_id in self._graph._dag:
            self._graph._dag.get_node(self.claim_id).invalidation_reason = value
        else:
            self._invalidation_reason = value

    @property
    def parent_claim_ids(self) -> ClaimEdgeList:
        return self._parent_claim_ids

    @parent_claim_ids.setter
    def parent_claim_ids(self, val: List[str]):
        self._parent_claim_ids._replace(val)

    @property
    def child_claim_ids(self) -> ClaimEdgeList:
        return self._child_claim_ids

    @child_claim_ids.setter
    def child_claim_ids(self, val: List[str]):
        self._child_claim_ids._replace(val)

    def _bind_graph(self, graph: Any) -> None:
        self._graph = graph
        self._parent_claim_ids.graph = graph
        self._child_claim_ids.graph = graph
        # Clear local duplicate edge storage now that CausalDAG is authoritative owner
        self._parent_claim_ids._initial.clear()
        self._child_claim_ids._initial.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "epistemic_status": self.epistemic_status.value,
            "provenance_sources": self.provenance_sources,
            "confidence_level": self.confidence_level,
            "falsification_condition": self.falsification_condition,
            "parent_claim_ids": list(self.parent_claim_ids),
            "child_claim_ids": list(self.child_claim_ids),
            "is_invalidated": self.is_invalidated,
            "invalidation_reason": self.invalidation_reason,
            "evidence_establishes_claim": self.evidence_establishes_claim,
            "modality": self.modality,
            "quantifier": self.quantifier,
            "uncertainties": list(self.uncertainties),
        }


@dataclass
class SourceRecord:
    source_id: str
    title: str
    provenance: str
    author_or_institution: str
    direct_excerpt: str
    date_recorded: float
    reliability_tier: str = "PRIMARY_CORROBORATED"
    content_hash: str = ""
    source_says_statement: str = ""

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


class ClaimGraph:
    """
    Directed Acyclic Graph of verified sources and claims.
    Topology is authoritatively owned by CausalDAG.
    ClaimNode edge lists are compatibility views projected from CausalDAG.
    """

    def __init__(self):
        self.sources: Dict[str, SourceRecord] = {}
        self.claims: Dict[str, ClaimNode] = {}
        self._dag = CausalDAG()

    def add_source(self, source: SourceRecord) -> None:
        self.sources[source.source_id] = source

    def add_claim(self, claim: ClaimNode) -> None:
        canonical_status = claim.epistemic_status.value
        if canonical_status in (
            EpistemicStatus.SOURCE_SUPPLIED_FACT.value,
            EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM.value,
        ) and not claim.falsification_condition:
            claim.falsification_condition = "Unspecified counter-evidence or direct empirical contradiction."

        if canonical_status == EpistemicStatus.SOURCE_SUPPLIED_FACT.value and not claim.provenance_sources:
            raise EpistemicLaunderingError(f"EPISTEMIC_LAUNDERING: Claim '{claim.claim_id}' declared as SOURCE_SUPPLIED_FACT without provenance sources.")

        for sid in claim.provenance_sources:
            if sid not in self.sources:
                raise ValueError(f"UNGROUNDED_CLAIM: Provenance source '{sid}' referenced by claim '{claim.claim_id}' does not exist in graph.")

        parents = list(claim.parent_claim_ids)
        missing = [pid for pid in parents if pid not in self._dag]
        # Preserve forward references, but never publish placeholders on failure.
        if claim.claim_id in parents:
            raise ValueError("CYCLE_DETECTED: self dependency")
        for pid in parents:
            if pid in self._dag and claim.claim_id in self._dag and self._dag._is_reachable(claim.claim_id, pid):
                raise ValueError("CYCLE_DETECTED: claim update")
        payload = claim.to_dict()
        for field in ("parent_claim_ids", "child_claim_ids", "is_invalidated", "invalidation_reason"):
            payload.pop(field)  # Topology and validity belong to the DAG node.
        for pid in missing:
            self._dag.add_node(pid, "claim")
        try:
            self._dag.add_node(claim.claim_id, "claim", payload, dependencies=parents,
                               status="INVALIDATED" if claim.is_invalidated else "VALID")
        except Exception:
            for pid in missing:
                self._dag.remove_node(pid)
            raise

        # Bind graph so child_claim_ids and parent_claim_ids project live from _dag
        claim._bind_graph(self)
        self.claims[claim.claim_id] = claim

    def invalidate_claim(self, claim_id: str, reason: str) -> List[str]:
        """
        Forward Contradiction Propagation:
        Recursively invalidates the target claim and all downstream dependent child claims.
        Delegated to CausalDAG for guaranteed topological order and cycle detection.
        """
        if claim_id not in self.claims:
            return []

        invalidated_ids = self._dag.invalidate(claim_id, reason=reason)
        return invalidated_ids

    def invalidate_claim_with_cascade(
        self,
        claim_id: str,
        reason: str,
        db: Optional[Any] = None,
    ) -> Any:
        from .invalidation_engine import InvalidationEngine
        engine = InvalidationEngine(db)
        return engine.invalidate_claim_with_cascade(self, claim_id, reason)

    def trace_backward_lineage(self, claim_id: str) -> Dict[str, Any]:
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
        curr = current_status.value if isinstance(current_status, EpistemicStatus) else str(current_status)
        target = new_status.value if isinstance(new_status, EpistemicStatus) else str(new_status)

        warranted = {
            EpistemicStatus.SOURCE_SUPPLIED_FACT.value,
            EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM.value,
        }

        if curr == EpistemicStatus.ASSUMPTION.value and target in warranted:
            raise EpistemicLaunderingError(
                f"Laundering detected: Cannot promote ASSUMPTION to {target} without external warrant and empirical provenance."
            )

        if curr == EpistemicStatus.CREATIVE_DECISION.value and target in warranted:
            raise EpistemicLaunderingError(
                f"Laundering detected: CREATIVE_DECISION cannot be promoted to {target}."
            )

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

        if target == EpistemicStatus.SOURCE_SUPPLIED_FACT.value and not provenance_sources:
            raise EpistemicLaunderingError("SOURCE_SUPPLIED_FACT requires an identifiable provenance_source.")
        if target == EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM.value and not warrant_or_reasoning:
            raise EpistemicLaunderingError("EVIDENCE_SUPPORTED_CLAIM requires an identifiable warrant_or_reasoning.")

    def get_established_facts(self) -> List[ClaimNode]:
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

