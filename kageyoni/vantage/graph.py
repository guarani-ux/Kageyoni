"""
Epistemic Dependency Graph & Invalidation Frontier for Vantage.
Maintains strict causal lineage between inputs, claims, decisions, and deliverables.
Prevents unearned approvals and ensures targeted, non-destructive invalidation.
Topology is authoritatively owned by kageyoni.graph.CausalDAG; GraphNode dependencies
and dependents are compatibility projections derived from CausalDAG.
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from kageyoni.graph import CausalDAG
from .models import EpistemicNodeStatus, ApprovalStatus


class GraphNode:
    """
    Domain deliverable node. Edge collections (dependencies, dependents)
    are dynamic compatibility projections from the authoritative CausalDAG.
    """

    def __init__(
        self,
        node_id: str,
        node_type: str,
        title: str,
        status: EpistemicNodeStatus | str = EpistemicNodeStatus.VALID,
        approval_status: ApprovalStatus | str = ApprovalStatus.DRAFT,
        content_hash: str = "",
        payload: Optional[Dict[str, Any]] = None,
        dependencies: Optional[Set[str]] = None,
        dependents: Optional[Set[str]] = None,
        invalidation_reason: Optional[str] = None,
        last_updated: Optional[float] = None,
        graph: Optional[Any] = None,
    ):
        self.node_id = node_id
        self.node_type = node_type
        self.title = title
        self.status = status if isinstance(status, EpistemicNodeStatus) else EpistemicNodeStatus(status)
        self.approval_status = approval_status if isinstance(approval_status, ApprovalStatus) else ApprovalStatus(approval_status)
        self.content_hash = content_hash
        self.payload = payload or {}
        self.invalidation_reason = invalidation_reason
        self.last_updated = last_updated if last_updated is not None else time.time()
        self._dependencies = set(dependencies or [])
        self._dependents = set(dependents or [])
        self._graph = graph

    @property
    def dependencies(self) -> Set[str]:
        if self._graph is not None and self.node_id in self._graph._dag:
            return self._graph._dag.get_node(self.node_id).dependencies
        return self._dependencies

    @dependencies.setter
    def dependencies(self, val: Set[str]):
        self._dependencies = set(val)

    @property
    def dependents(self) -> Set[str]:
        if self._graph is not None and self.node_id in self._graph._dag:
            return self._graph._dag.get_node(self.node_id).dependents
        return self._dependents

    @dependents.setter
    def dependents(self, val: Set[str]):
        self._dependents = set(val)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "title": self.title,
            "status": self.status.value,
            "approval_status": self.approval_status.value,
            "content_hash": self.content_hash,
            "payload": self.payload,
            "dependencies": sorted(list(self.dependencies)),
            "dependents": sorted(list(self.dependents)),
            "invalidation_reason": self.invalidation_reason,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GraphNode:
        d = dict(data)
        d["status"] = EpistemicNodeStatus(d["status"])
        d["approval_status"] = ApprovalStatus(d["approval_status"])
        d["dependencies"] = set(d.get("dependencies", []))
        d["dependents"] = set(d.get("dependents", []))
        return cls(**d)


@dataclass
class InvalidationReceipt:
    root_node_id: str
    reason: str
    affected_nodes: List[str]
    revoked_approvals: List[str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_node_id": self.root_node_id,
            "reason": self.reason,
            "affected_nodes": self.affected_nodes,
            "revoked_approvals": self.revoked_approvals,
            "timestamp": self.timestamp,
        }


class EpistemicDependencyGraph:
    """
    Directed Acyclic Graph governing causal dependency, invalidation propagation,
    and approval validity across all media production deliverables.
    Topology is owned solely by CausalDAG.
    """

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.invalidation_history: List[InvalidationReceipt] = []
        self._dag = CausalDAG()

    def add_node(
        self,
        node_id: str,
        node_type: str,
        title: str,
        status: EpistemicNodeStatus = EpistemicNodeStatus.VALID,
        approval_status: ApprovalStatus = ApprovalStatus.DRAFT,
        content_hash: str = "",
        payload: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
    ) -> GraphNode:
        # Pre-validate dependencies exist before altering any state
        if dependencies:
            for dep_id in dependencies:
                if dep_id not in self.nodes:
                    raise KeyError(f"Parent node '{dep_id}' does not exist in graph.")

        is_new = node_id not in self.nodes
        added_dag_node = False
        added_edges = []
        try:
            if is_new:
                self._dag.add_node(node_id, node_type, payload or {}, status=status.value)
                added_dag_node = True
            if dependencies:
                for dep_id in dependencies:
                    self._dag.add_edge(dep_id, node_id)
                    added_edges.append((dep_id, node_id))
        except Exception:
            # Atomic rollback: preserve both domain records and topology untouched on failure
            for p, c in added_edges:
                self._dag.remove_edge(p, c)
            if added_dag_node:
                self._dag.remove_node(node_id)
            raise

        if not is_new:
            node = self.nodes[node_id]
            node.node_type = node_type
            node.title = title
            node.status = status
            node.approval_status = approval_status
            node.content_hash = content_hash
            node.payload = payload or {}
            node.last_updated = time.time()
        else:
            node = GraphNode(
                node_id=node_id,
                node_type=node_type,
                title=title,
                status=status,
                approval_status=approval_status,
                content_hash=content_hash,
                payload=payload or {},
                graph=self,
            )
            self.nodes[node_id] = node

        return node

    def add_dependency(self, child_id: str, parent_id: str) -> None:
        if child_id not in self.nodes:
            raise KeyError(f"Child node '{child_id}' does not exist in graph.")
        if parent_id not in self.nodes:
            raise KeyError(f"Parent node '{parent_id}' does not exist in graph.")

        # CausalDAG is the SOLE authoritative owner of edge topology
        self._dag.add_edge(parent_id, child_id)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self.nodes.get(node_id)

    def invalidate(
        self,
        root_node_id: str,
        reason: str,
        target_status: EpistemicNodeStatus = EpistemicNodeStatus.STALE,
    ) -> InvalidationReceipt:
        """
        Cascades invalidation forward via CausalDAG.
        Revokes approvals on invalidated nodes to prevent silent passes.
        """
        if root_node_id not in self.nodes:
            raise KeyError(f"Node '{root_node_id}' not found.")

        affected = self._dag.invalidate(root_node_id, reason=reason)
        revoked_approvals: List[str] = []

        now = time.time()
        for nid in affected:
            node = self.nodes[nid]
            node.status = target_status
            self._dag.get_node(nid).status = target_status.value
            if nid == root_node_id:
                node.invalidation_reason = reason
            else:
                node.invalidation_reason = f"Upstream dependency '{root_node_id}' invalidated: {reason}"
            node.last_updated = now

            if node.approval_status == ApprovalStatus.APPROVED:
                node.approval_status = ApprovalStatus.STALE
                revoked_approvals.append(nid)

        receipt = InvalidationReceipt(
            root_node_id=root_node_id,
            reason=reason,
            affected_nodes=affected,
            revoked_approvals=revoked_approvals,
            timestamp=now,
        )
        self.invalidation_history.append(receipt)
        return receipt

    def grant_approval(self, node_id: str, approved_by: str, current_hash: str) -> bool:
        if node_id not in self.nodes:
            return False

        node = self.nodes[node_id]
        # Dependencies projected live from authoritative CausalDAG
        for dep_id in node.dependencies:
            dep = self.nodes[dep_id]
            if dep.status != EpistemicNodeStatus.VALID:
                return False

        node.approval_status = ApprovalStatus.APPROVED
        node.content_hash = current_hash
        node.invalidation_reason = None
        node.last_updated = time.time()
        return True

    def get_unresolved_nodes(self) -> List[GraphNode]:
        return [
            n for n in self.nodes.values()
            if n.status in (EpistemicNodeStatus.UNKNOWN, EpistemicNodeStatus.UNRESOLVED, EpistemicNodeStatus.BLOCKED)
        ]

    def get_stale_or_contested_nodes(self) -> List[GraphNode]:
        return [
            n for n in self.nodes.values()
            if n.status in (EpistemicNodeStatus.STALE, EpistemicNodeStatus.CONTESTED)
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "invalidation_history": [r.to_dict() for r in self.invalidation_history],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EpistemicDependencyGraph:
        graph = cls()
        nodes_dict = data.get("nodes", {})
        # 1. Reconstruct domain nodes and CausalDAG nodes with exact saved status
        for nid, ndata in nodes_dict.items():
            node = GraphNode.from_dict(ndata)
            node._graph = graph
            graph.nodes[nid] = node
            graph._dag.add_node(
                node_id=nid,
                node_type=node.node_type,
                payload=node.payload,
                status=node.status.value,
            )
            if node.invalidation_reason:
                graph._dag.get_node(nid).invalidation_reason = node.invalidation_reason

        # 2. Re-establish edges strictly in authoritative CausalDAG
        for nid, ndata in nodes_dict.items():
            for dep in ndata.get("dependencies", []):
                if dep in graph.nodes:
                    graph._dag.add_edge(dep, nid)

        history = data.get("invalidation_history", [])
        for rdata in history:
            graph.invalidation_history.append(InvalidationReceipt(**rdata))
        return graph
