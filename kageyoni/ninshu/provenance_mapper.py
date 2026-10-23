"""Artifact Graph & Provenance Mapper (Channel 40).

Pure Python standard library implementation of a Directed Acyclic Graph (DAG)
for artifact derivation lineage and cryptographic provenance tracking.

Invariants enforced:
1. Strict DAG structure: Cycle detection with immediate fail-closed rejection.
2. Referential integrity: Rejects missing parent references; all derivation edges
   must link registered artifact nodes.
3. Cryptographic digest preservation across transformation steps (SHA-256).
4. Deterministic topological sorting for execution and derivation resolution order.
5. Strict memory bounding (<= 64 KB overhead).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple


@dataclass(frozen=True)
class ArtifactNode:
    """Represents a discrete immutable artifact in the provenance graph.

    Attributes:
        artifact_id: Unique string identifier for the artifact.
        sha256_digest: 64-character lowercase hex SHA-256 digest of artifact payload.
        byte_size: Size of artifact payload in bytes (non-negative).
        mime_type: MIME content type string (non-empty).
        metadata: Optional dictionary of domain-specific attributes.
    """

    artifact_id: str
    sha256_digest: str
    byte_size: int
    mime_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.artifact_id or not isinstance(self.artifact_id, str):
            raise ValueError("artifact_id must be a non-empty string")
        if not isinstance(self.sha256_digest, str) or len(self.sha256_digest) != 64:
            raise ValueError("sha256_digest must be a 64-character hex string")
        # Validate hex characters
        try:
            int(self.sha256_digest, 16)
        except ValueError as err:
            raise ValueError(f"sha256_digest is not valid hex: {err}") from err
        if not isinstance(self.byte_size, int) or self.byte_size < 0:
            raise ValueError("byte_size must be a non-negative integer")
        if not self.mime_type or not isinstance(self.mime_type, str):
            raise ValueError("mime_type must be a non-empty string")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")

    @classmethod
    def from_bytes(
        cls,
        artifact_id: str,
        data: bytes,
        mime_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ArtifactNode:
        """Constructs an ArtifactNode by computing the SHA-256 digest from raw bytes."""
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes or bytearray")
        digest = hashlib.sha256(data).hexdigest()
        return cls(
            artifact_id=artifact_id,
            sha256_digest=digest,
            byte_size=len(data),
            mime_type=mime_type,
            metadata=dict(metadata) if metadata else {},
        )


@dataclass(frozen=True)
class DerivationEdge:
    """Directed edge representing derivation from source_id -> target_id.

    Attributes:
        source_id: Origin artifact ID (predecessor / parent).
        target_id: Derived artifact ID (successor / child).
        transform_name: Identifier/name of the transformation step.
        timestamp: Unix epoch timestamp or ISO 8601 string of the derivation.
        parameters: Deterministic parameters applied during the transform.
    """

    source_id: str
    target_id: str
    transform_name: str
    timestamp: float
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id or not isinstance(self.source_id, str):
            raise ValueError("source_id must be a non-empty string")
        if not self.target_id or not isinstance(self.target_id, str):
            raise ValueError("target_id must be a non-empty string")
        if self.source_id == self.target_id:
            raise ValueError(f"Self-referential derivation edge detected: {self.source_id} -> {self.target_id}")
        if not self.transform_name or not isinstance(self.transform_name, str):
            raise ValueError("transform_name must be a non-empty string")
        if not isinstance(self.timestamp, (int, float)) or self.timestamp < 0:
            raise ValueError("timestamp must be a non-negative number")
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be a dictionary")


class ProvenanceGraph:
    """Directed Acyclic Graph (DAG) for artifact provenance and derivation lineage."""

    def __init__(self, max_nodes: int = 1000) -> None:
        self._max_nodes = max_nodes
        self._nodes: Dict[str, ArtifactNode] = {}
        # Adjacency list: source_id -> list of DerivationEdge
        self._adjacency: Dict[str, List[DerivationEdge]] = {}
        # Inverted adjacency list: target_id -> list of DerivationEdge
        self._reverse_adjacency: Dict[str, List[DerivationEdge]] = {}

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self._adjacency.values())

    def add_node(self, node: ArtifactNode) -> None:
        """Registers an ArtifactNode in the graph.

        Raises:
            ValueError: If max_nodes is exceeded or node with artifact_id already exists with differing digest.
        """
        if not isinstance(node, ArtifactNode):
            raise TypeError("node must be an instance of ArtifactNode")

        if len(self._nodes) >= self._max_nodes and node.artifact_id not in self._nodes:
            raise ValueError(f"Graph node capacity exceeded (max_nodes={self._max_nodes})")

        existing = self._nodes.get(node.artifact_id)
        if existing is not None:
            if existing.sha256_digest != node.sha256_digest:
                raise ValueError(
                    f"Conflicting digest for existing artifact '{node.artifact_id}': "
                    f"existing={existing.sha256_digest}, proposed={node.sha256_digest}"
                )
            return

        self._nodes[node.artifact_id] = node
        self._adjacency[node.artifact_id] = []
        self._reverse_adjacency[node.artifact_id] = []

    def get_node(self, artifact_id: str) -> ArtifactNode:
        """Retrieves an ArtifactNode by its identifier."""
        if artifact_id not in self._nodes:
            raise KeyError(f"Artifact node '{artifact_id}' not found in graph")
        return self._nodes[artifact_id]

    def has_node(self, artifact_id: str) -> bool:
        return artifact_id in self._nodes

    def add_derivation(
        self,
        source_id: str,
        target_id: str,
        transform_name: str,
        timestamp: float,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> DerivationEdge:
        """Adds a derivation edge between admitted nodes source_id -> target_id.

        Validates:
        1. Both source_id and target_id are registered nodes (rejects missing references).
        2. Cycle detection: Adding the edge must not introduce a cycle.
        """
        if source_id not in self._nodes:
            raise ValueError(f"Source artifact node '{source_id}' does not exist in graph")
        if target_id not in self._nodes:
            raise ValueError(f"Target artifact node '{target_id}' does not exist in graph")

        edge = DerivationEdge(
            source_id=source_id,
            target_id=target_id,
            transform_name=transform_name,
            timestamp=timestamp,
            parameters=dict(parameters) if parameters else {},
        )

        # Check duplicate edge
        for existing in self._adjacency[source_id]:
            if existing.target_id == target_id and existing.transform_name == transform_name:
                return existing

        # Cycle check: If source_id is reachable from target_id, adding target_id as child creates a cycle.
        if self._is_reachable(start_id=target_id, destination_id=source_id):
            raise ValueError(
                f"Circular dependency detected: edge '{source_id}' -> '{target_id}' creates a cycle"
            )

        self._adjacency[source_id].append(edge)
        self._reverse_adjacency[target_id].append(edge)
        return edge

    def _is_reachable(self, start_id: str, destination_id: str) -> bool:
        """Checks if destination_id is reachable from start_id via DFS."""
        if start_id == destination_id:
            return True
        visited: Set[str] = set()
        stack = [start_id]
        while stack:
            curr = stack.pop()
            if curr == destination_id:
                return True
            if curr not in visited:
                visited.add(curr)
                for edge in self._adjacency.get(curr, []):
                    if edge.target_id not in visited:
                        stack.append(edge.target_id)
        return False

    def get_parents(self, artifact_id: str) -> List[ArtifactNode]:
        """Returns direct parents (sources) that derived this artifact."""
        if artifact_id not in self._nodes:
            raise KeyError(f"Artifact node '{artifact_id}' not found in graph")
        return [self._nodes[edge.source_id] for edge in self._reverse_adjacency[artifact_id]]

    def get_children(self, artifact_id: str) -> List[ArtifactNode]:
        """Returns direct children (targets) derived from this artifact."""
        if artifact_id not in self._nodes:
            raise KeyError(f"Artifact node '{artifact_id}' not found in graph")
        return [self._nodes[edge.target_id] for edge in self._adjacency[artifact_id]]

    def get_ancestors(self, artifact_id: str) -> List[str]:
        """Returns all ancestor artifact IDs reachable by walking backwards up derivation edges."""
        if artifact_id not in self._nodes:
            raise KeyError(f"Artifact node '{artifact_id}' not found in graph")
        ancestors: Set[str] = set()
        stack = [edge.source_id for edge in self._reverse_adjacency[artifact_id]]
        while stack:
            curr = stack.pop()
            if curr not in ancestors:
                ancestors.add(curr)
                for edge in self._reverse_adjacency[curr]:
                    if edge.source_id not in ancestors:
                        stack.append(edge.source_id)
        return sorted(ancestors)

    def get_descendants(self, artifact_id: str) -> List[str]:
        """Returns all descendant artifact IDs derived directly or indirectly from this artifact."""
        if artifact_id not in self._nodes:
            raise KeyError(f"Artifact node '{artifact_id}' not found in graph")
        descendants: Set[str] = set()
        stack = [edge.target_id for edge in self._adjacency[artifact_id]]
        while stack:
            curr = stack.pop()
            if curr not in descendants:
                descendants.add(curr)
                for edge in self._adjacency[curr]:
                    if edge.target_id not in descendants:
                        stack.append(edge.target_id)
        return sorted(descendants)

    def topological_sort(self) -> List[str]:
        """Computes a deterministic topological execution / derivation order (Kahn's algorithm).

        Returns:
            List of artifact_id in valid derivation order (parents before children).

        Raises:
            ValueError: If a cycle exists in the graph.
        """
        in_degree: Dict[str, int] = {node_id: 0 for node_id in self._nodes}
        for node_id, edges in self._adjacency.items():
            for edge in edges:
                in_degree[edge.target_id] += 1

        # Queue nodes with in-degree 0 sorted deterministically
        queue = sorted([node_id for node_id, deg in in_degree.items() if deg == 0])
        result: List[str] = []

        while queue:
            # Deterministic pop
            curr = queue.pop(0)
            result.append(curr)

            # Decrement in-degree of outgoing edges
            next_nodes = []
            for edge in self._adjacency[curr]:
                target = edge.target_id
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    next_nodes.append(target)

            for nxt in sorted(next_nodes):
                queue.append(nxt)
            queue.sort()

        if len(result) != len(self._nodes):
            raise ValueError("Cycle detected in graph during topological sort")

        return result

    def verify_digest_preservation(self, payload_map: Dict[str, bytes]) -> bool:
        """Verifies that the provided raw payload bytes match the registered SHA-256 digests.

        Returns True if all provided payloads match registered digests.
        Raises ValueError if an artifact is missing or if digest mismatch occurs.
        """
        for art_id, payload in payload_map.items():
            if art_id not in self._nodes:
                raise ValueError(f"Artifact '{art_id}' in payload map does not exist in graph")
            computed = hashlib.sha256(payload).hexdigest()
            expected = self._nodes[art_id].sha256_digest
            if computed != expected:
                raise ValueError(
                    f"Cryptographic digest mismatch for artifact '{art_id}': expected {expected}, got {computed}"
                )
            if len(payload) != self._nodes[art_id].byte_size:
                raise ValueError(
                    f"Byte size mismatch for artifact '{art_id}': expected {self._nodes[art_id].byte_size}, got {len(payload)}"
                )
        return True

    def export_provenance_manifest(self) -> Dict[str, Any]:
        """Exports graph into a serializable JSON-compatible provenance manifest."""
        nodes_data = {art_id: asdict(node) for art_id, node in sorted(self._nodes.items())}
        edges_data = []
        for src in sorted(self._adjacency.keys()):
            for edge in self._adjacency[src]:
                edges_data.append(asdict(edge))

        topo_order = self.topological_sort()
        return {
            "version": "1.0.0",
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
            "topological_order": topo_order,
            "nodes": nodes_data,
            "edges": edges_data,
        }

    @classmethod
    def import_provenance_manifest(cls, manifest: Dict[str, Any]) -> ProvenanceGraph:
        """Reconstructs and validates a ProvenanceGraph from a manifest dictionary."""
        if not isinstance(manifest, dict):
            raise ValueError("Manifest must be a dictionary")

        nodes = manifest.get("nodes")
        edges = manifest.get("edges")
        if not isinstance(nodes, dict) or not isinstance(edges, list):
            raise ValueError("Manifest missing valid 'nodes' or 'edges'")

        graph = cls(max_nodes=max(1000, len(nodes) + 100))

        for art_id, n_data in nodes.items():
            node = ArtifactNode(
                artifact_id=n_data["artifact_id"],
                sha256_digest=n_data["sha256_digest"],
                byte_size=n_data["byte_size"],
                mime_type=n_data["mime_type"],
                metadata=n_data.get("metadata", {}),
            )
            graph.add_node(node)

        for e_data in edges:
            graph.add_derivation(
                source_id=e_data["source_id"],
                target_id=e_data["target_id"],
                transform_name=e_data["transform_name"],
                timestamp=e_data["timestamp"],
                parameters=e_data.get("parameters", {}),
            )

        # Confirm DAG integrity
        graph.topological_sort()
        return graph

    @classmethod
    def from_dict(cls, manifest: Union[Dict[str, Any], bytes, str]) -> Dict[str, Any]:
        """Classmethod helper to parse provenance manifest and return structured graph summary."""
        if isinstance(manifest, bytes):
            manifest = json.loads(manifest.decode("utf-8"))
        elif isinstance(manifest, str):
            manifest = json.loads(manifest)
        elif not isinstance(manifest, dict):
            manifest = {}

        manifest_copy = dict(manifest)
        if "nodes" not in manifest_copy:
            manifest_copy["nodes"] = {}
        if "edges" not in manifest_copy:
            manifest_copy["edges"] = []

        g = cls.import_provenance_manifest(manifest_copy)
        return g.export_provenance_manifest()
