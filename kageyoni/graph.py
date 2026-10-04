"""
kageyoni.graph: Unified Causal Directed Acyclic Graph (DAG) Substrate.

Consolidates epistemic dependency tracking, invalidation cascades,
claim/source lineage walking, and cycle-safe topological execution
into a single zero-dependency module.
"""

from __future__ import annotations
import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class CycleDetectedError(ValueError):
    """Raised when an edge insertion would introduce a cycle into the DAG."""
    pass


class NodeNotFoundError(KeyError):
    """Raised when an operation references a non-existent node in the DAG."""
    pass


@dataclass
class DAGNode:
    """A situated node within the causal graph."""
    node_id: str
    node_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "VALID"  # VALID, INVALIDATED, PENDING, ARCHIVED
    dependencies: Set[str] = field(default_factory=set)  # Upstream parent nodes
    dependents: Set[str] = field(default_factory=set)    # Downstream child nodes
    content_hash: str = ""
    invalidation_reason: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.content_hash and self.payload:
            canonical = json.dumps(self.payload, sort_keys=True, default=str)
            self.content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "payload": self.payload,
            "status": self.status,
            "dependencies": sorted(list(self.dependencies)),
            "dependents": sorted(list(self.dependents)),
            "content_hash": self.content_hash,
            "invalidation_reason": self.invalidation_reason,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DAGNode:
        d = dict(data)
        d["dependencies"] = set(d.get("dependencies", []))
        d["dependents"] = set(d.get("dependents", []))
        return cls(**d)


class CausalDAG:
    """
    Universal Causal Directed Acyclic Graph.
    
    Provides:
    - Cycle-safe node and edge insertion.
    - Forward Invalidation Cascades: downstream invalidation propagation when an upstream node breaks.
    - Backward Lineage Walking: tracing from any conclusion back to its empirical root sources.
    - Topological Sorting: discovering valid linear execution orders.
    - SQLite ACID Persistence: durable storage and recovery without data loss.
    """

    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}

    def __contains__(self, node_id: str) -> bool:
        return node_id in self.nodes

    def __len__(self) -> int:
        return len(self.nodes)

    def get_node(self, node_id: str) -> DAGNode:
        if node_id not in self.nodes:
            raise NodeNotFoundError(f"Node '{node_id}' does not exist in graph.")
        return self.nodes[node_id]

    def add_node(
        self,
        node_id: str,
        node_type: str,
        payload: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        status: str = "VALID",
        content_hash: str = "",
    ) -> DAGNode:
        """Adds a node to the DAG. Binds dependencies with strict cycle detection."""
        if not node_id or not isinstance(node_id, str):
            raise ValueError("node_id must be a non-empty string.")

        deps = list(dependencies or [])
        # Verify that all referenced dependencies exist
        for dep_id in deps:
            if dep_id not in self.nodes:
                raise NodeNotFoundError(f"Dependency '{dep_id}' does not exist in graph.")

        # Create or update node
        payload_dict = payload or {}
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.node_type = node_type
            node.payload = payload_dict
            node.status = status
            node.last_updated = time.time()
            if content_hash:
                node.content_hash = content_hash
        else:
            node = DAGNode(
                node_id=node_id,
                node_type=node_type,
                payload=payload_dict,
                status=status,
                content_hash=content_hash,
            )
            self.nodes[node_id] = node

        # Bind edges with cycle checking
        for dep_id in deps:
            self.add_edge(dep_id, node_id)

        return node

    def add_edge(self, parent_id: str, child_id: str) -> None:
        """Binds a directed causal edge: parent -> child. Enforces acyclicity."""
        if parent_id not in self.nodes:
            raise NodeNotFoundError(f"Parent node '{parent_id}' does not exist.")
        if child_id not in self.nodes:
            raise NodeNotFoundError(f"Child node '{child_id}' does not exist.")
        if parent_id == child_id:
            raise CycleDetectedError(f"Self-loop detected: '{parent_id}' cannot depend on itself.")

        # Check if adding parent -> child would create a cycle.
        # A cycle would occur if parent is already reachable downstream from child.
        if self._is_reachable(from_id=child_id, to_id=parent_id):
            raise CycleDetectedError(
                f"Cycle detected: adding edge '{parent_id}' -> '{child_id}' would create a circular dependency."
            )

        parent = self.nodes[parent_id]
        child = self.nodes[child_id]

        parent.dependents.add(child_id)
        child.dependencies.add(parent_id)
        child.last_updated = time.time()

    def remove_edge(self, parent_id: str, child_id: str) -> None:
        """Removes a directed edge: parent -> child."""
        if parent_id in self.nodes:
            self.nodes[parent_id].dependents.discard(child_id)
        if child_id in self.nodes:
            self.nodes[child_id].dependencies.discard(parent_id)
            self.nodes[child_id].last_updated = time.time()

    def remove_node(self, node_id: str) -> None:
        """Removes a node and unbinds all incident edges."""
        if node_id not in self.nodes:
            return
        node = self.nodes.pop(node_id)
        for dep_id in node.dependencies:
            if dep_id in self.nodes:
                self.nodes[dep_id].dependents.discard(node_id)
        for child_id in node.dependents:
            if child_id in self.nodes:
                self.nodes[child_id].dependencies.discard(node_id)

    def _is_reachable(self, from_id: str, to_id: str) -> bool:
        """DFS traversal checking if to_id can be reached downstream from from_id."""
        visited: Set[str] = set()
        stack = [from_id]
        while stack:
            curr = stack.pop()
            if curr == to_id:
                return True
            if curr not in visited:
                visited.add(curr)
                if curr in self.nodes:
                    stack.extend(self.nodes[curr].dependents - visited)
        return False

    def invalidate(self, node_id: str, reason: str) -> List[str]:
        """
        Forward Invalidation Cascade:
        Recursively marks the target node and all downstream dependent nodes as INVALIDATED.
        Guarantees termination via visited set. Returns ordered list of all affected node IDs.
        """
        if node_id not in self.nodes:
            raise NodeNotFoundError(f"Node '{node_id}' does not exist.")

        invalidated: List[str] = []
        visited: Set[str] = set()
        stack = [(node_id, reason)]

        while stack:
            curr_id, curr_reason = stack.pop()
            if curr_id in visited:
                continue
            visited.add(curr_id)

            if curr_id in self.nodes:
                node = self.nodes[curr_id]
                node.status = "INVALIDATED"
                node.invalidation_reason = curr_reason
                node.last_updated = time.time()
                invalidated.append(curr_id)

                for child_id in sorted(list(node.dependents)):
                    if child_id not in visited:
                        stack.append((child_id, f"Upstream dependency '{curr_id}' invalidated: {curr_reason}"))

        return invalidated

    def trace_lineage(self, node_id: str) -> List[str]:
        """
        Backward Lineage Walk:
        Traverses upstream parents to return root sources/origins (nodes with no dependencies).
        """
        if node_id not in self.nodes:
            raise NodeNotFoundError(f"Node '{node_id}' does not exist.")

        roots: Set[str] = set()
        visited: Set[str] = set()
        stack = [node_id]

        while stack:
            curr_id = stack.pop()
            if curr_id in visited:
                continue
            visited.add(curr_id)

            if curr_id in self.nodes:
                node = self.nodes[curr_id]
                if not node.dependencies:
                    roots.add(curr_id)
                else:
                    stack.extend(node.dependencies - visited)

        return sorted(list(roots))

    def topological_sort(self) -> List[str]:
        """
        Computes a topological ordering of all nodes using Kahn's algorithm.
        Returns a list of node IDs where dependencies precede dependents.
        """
        in_degree = {nid: len(n.dependencies) for nid, n in self.nodes.items()}
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        ordered: List[str] = []

        while queue:
            queue.sort()  # Deterministic tie-breaking
            curr = queue.pop(0)
            ordered.append(curr)

            for child in self.nodes[curr].dependents:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(ordered) != len(self.nodes):
            raise CycleDetectedError("Graph contains a cycle; topological sort impossible.")

        return ordered

    def to_sqlite(self, conn: sqlite3.Connection, table_prefix: str = "causal_dag") -> None:
        """Persists entire DAG to SQLite within an ACID transaction."""
        node_tbl = f"{table_prefix}_nodes"
        edge_tbl = f"{table_prefix}_edges"

        with conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {node_tbl} (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    content_hash TEXT,
                    invalidation_reason TEXT,
                    created_at REAL NOT NULL,
                    last_updated REAL NOT NULL
                );
            """)
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {edge_tbl} (
                    parent_id TEXT NOT NULL,
                    child_id TEXT NOT NULL,
                    PRIMARY KEY (parent_id, child_id)
                );
            """)

            # Clear old records for clean snapshot
            conn.execute(f"DELETE FROM {edge_tbl}")
            conn.execute(f"DELETE FROM {node_tbl}")

            for n in self.nodes.values():
                conn.execute(
                    f"INSERT INTO {node_tbl} VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        n.node_id,
                        n.node_type,
                        json.dumps(n.payload),
                        n.status,
                        n.content_hash,
                        n.invalidation_reason,
                        n.created_at,
                        n.last_updated,
                    ),
                )
                for child_id in n.dependents:
                    conn.execute(
                        f"INSERT INTO {edge_tbl} VALUES (?, ?)",
                        (n.node_id, child_id),
                    )

    @classmethod
    def from_sqlite(cls, conn: sqlite3.Connection, table_prefix: str = "causal_dag") -> CausalDAG:
        """Loads a DAG snapshot from SQLite."""
        node_tbl = f"{table_prefix}_nodes"
        edge_tbl = f"{table_prefix}_edges"

        dag = cls()
        rows = conn.execute(f"SELECT * FROM {node_tbl}").fetchall()
        for r in rows:
            # Handle tuple or dict row
            nid, ntype, payload_str, status, chash, inv_reason, cat, lup = r[:8]
            payload = json.loads(payload_str)
            dag.nodes[nid] = DAGNode(
                node_id=nid,
                node_type=ntype,
                payload=payload,
                status=status,
                content_hash=chash,
                invalidation_reason=inv_reason,
                created_at=cat,
                last_updated=lup,
            )

        edge_rows = conn.execute(f"SELECT parent_id, child_id FROM {edge_tbl}").fetchall()
        for pid, cid in edge_rows:
            if pid in dag.nodes and cid in dag.nodes:
                dag.nodes[pid].dependents.add(cid)
                dag.nodes[cid].dependencies.add(pid)

        return dag

    def to_dict(self) -> Dict[str, Any]:
        return {nid: n.to_dict() for nid, n in self.nodes.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CausalDAG:
        dag = cls()
        for nid, ndata in data.items():
            dag.nodes[nid] = DAGNode.from_dict(ndata)
        return dag
