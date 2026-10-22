"""Unit and adversarial verification suite for Channel 40 (Artifact Graph & Provenance Mapper).

Validates:
1. Valid DAG assembly, derivation edges, lineage queries, topological ordering.
2. Immediate cycle rejection (fail-closed on loops and self-referential cycles).
3. Missing parent / child node reference rejection.
4. Cryptographic digest preservation across transformation steps.
5. Strict memory ceiling (peak heap <= 64 KB during operations).
6. Adversarial vectors: disconnected components, deep chains, diamond DAGs, malformed manifests.
"""
from __future__ import annotations

import hashlib
import json
import tracemalloc
import unittest

from kageyoni.ninshu.provenance_mapper import (
    ArtifactNode,
    DerivationEdge,
    ProvenanceGraph,
)


class TestProvenanceMapper(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_a = b"RAW_SOURCE_CODE_DATA_FOR_ARTIFACT_A"
        self.raw_b = b"COMPILED_BYTECODE_OBJECT_B"
        self.raw_c = b"PACKAGED_CONTAINER_IMAGE_C"
        self.raw_d = b"ATTACHED_SIGNATURE_BLOB_D"

        self.node_a = ArtifactNode.from_bytes("art_a", self.raw_a, "text/plain", {"author": "kageyoni"})
        self.node_b = ArtifactNode.from_bytes("art_b", self.raw_b, "application/octet-stream")
        self.node_c = ArtifactNode.from_bytes("art_c", self.raw_c, "application/tar")
        self.node_d = ArtifactNode.from_bytes("art_d", self.raw_d, "application/pgp-signature")

    def test_node_validation_and_hashing(self) -> None:
        self.assertEqual(self.node_a.artifact_id, "art_a")
        self.assertEqual(self.node_a.sha256_digest, hashlib.sha256(self.raw_a).hexdigest())
        self.assertEqual(self.node_a.byte_size, len(self.raw_a))
        self.assertEqual(self.node_a.mime_type, "text/plain")
        self.assertEqual(self.node_a.metadata["author"], "kageyoni")

        # Invalid digest
        with self.assertRaises(ValueError):
            ArtifactNode("bad_node", "not_a_64_char_hex", 10, "text/plain")

        # Negative size
        with self.assertRaises(ValueError):
            ArtifactNode("bad_node", "a" * 64, -1, "text/plain")

        # Empty id
        with self.assertRaises(ValueError):
            ArtifactNode("", "a" * 64, 10, "text/plain")

    def test_valid_dag_assembly_and_topological_sort(self) -> None:
        graph = ProvenanceGraph()
        graph.add_node(self.node_a)
        graph.add_node(self.node_b)
        graph.add_node(self.node_c)

        # A -> B -> C
        edge1 = graph.add_derivation("art_a", "art_b", "compile", 100.0, {"flags": "-O2"})
        edge2 = graph.add_derivation("art_b", "art_c", "package", 200.0, {"format": "tar"})

        self.assertEqual(graph.node_count, 3)
        self.assertEqual(graph.edge_count, 2)
        self.assertEqual(edge1.transform_name, "compile")
        self.assertEqual(edge2.transform_name, "package")

        topo = graph.topological_sort()
        self.assertEqual(topo, ["art_a", "art_b", "art_c"])

        # Ancestors & descendants
        self.assertEqual(graph.get_ancestors("art_c"), ["art_a", "art_b"])
        self.assertEqual(graph.get_descendants("art_a"), ["art_b", "art_c"])
        self.assertEqual(graph.get_parents("art_b")[0].artifact_id, "art_a")
        self.assertEqual(graph.get_children("art_b")[0].artifact_id, "art_c")

    def test_diamond_dag_and_lineage(self) -> None:
        # A -> B -> D
        # A -> C -> D
        graph = ProvenanceGraph()
        graph.add_node(self.node_a)
        graph.add_node(self.node_b)
        graph.add_node(self.node_c)
        graph.add_node(self.node_d)

        graph.add_derivation("art_a", "art_b", "branch_left", 1.0)
        graph.add_derivation("art_a", "art_c", "branch_right", 2.0)
        graph.add_derivation("art_b", "art_d", "merge_left", 3.0)
        graph.add_derivation("art_c", "art_d", "merge_right", 4.0)

        topo = graph.topological_sort()
        self.assertEqual(topo[0], "art_a")
        self.assertEqual(topo[-1], "art_d")
        self.assertIn("art_b", topo[1:3])
        self.assertIn("art_c", topo[1:3])

        self.assertEqual(graph.get_ancestors("art_d"), ["art_a", "art_b", "art_c"])

    def test_cycle_rejection_fail_closed(self) -> None:
        graph = ProvenanceGraph()
        graph.add_node(self.node_a)
        graph.add_node(self.node_b)
        graph.add_node(self.node_c)

        graph.add_derivation("art_a", "art_b", "step_1", 10.0)
        graph.add_derivation("art_b", "art_c", "step_2", 20.0)

        # Attempting cycle: C -> A
        with self.assertRaises(ValueError) as ctx:
            graph.add_derivation("art_c", "art_a", "step_cycle", 30.0)
        self.assertIn("Circular dependency detected", str(ctx.exception))

        # Attempting 2-node cycle: B -> A
        with self.assertRaises(ValueError) as ctx2:
            graph.add_derivation("art_b", "art_a", "step_back", 40.0)
        self.assertIn("Circular dependency detected", str(ctx2.exception))

    def test_self_referential_edge_rejected(self) -> None:
        graph = ProvenanceGraph()
        graph.add_node(self.node_a)

        with self.assertRaises(ValueError) as ctx:
            graph.add_derivation("art_a", "art_a", "self_loop", 10.0)
        self.assertIn("Self-referential derivation edge detected", str(ctx.exception))

    def test_missing_node_references_rejected(self) -> None:
        graph = ProvenanceGraph()
        graph.add_node(self.node_a)

        # Target missing
        with self.assertRaises(ValueError) as ctx:
            graph.add_derivation("art_a", "art_nonexistent", "transform", 1.0)
        self.assertIn("Target artifact node 'art_nonexistent' does not exist", str(ctx.exception))

        # Source missing
        with self.assertRaises(ValueError) as ctx2:
            graph.add_derivation("art_nonexistent", "art_a", "transform", 1.0)
        self.assertIn("Source artifact node 'art_nonexistent' does not exist", str(ctx2.exception))

    def test_cryptographic_digest_preservation(self) -> None:
        graph = ProvenanceGraph()
        graph.add_node(self.node_a)
        graph.add_node(self.node_b)

        payload_map = {
            "art_a": self.raw_a,
            "art_b": self.raw_b,
        }
        self.assertTrue(graph.verify_digest_preservation(payload_map))

        # Corrupted payload
        corrupted_map = {
            "art_a": self.raw_a + b"MUTATED",
        }
        with self.assertRaises(ValueError) as ctx:
            graph.verify_digest_preservation(corrupted_map)
        self.assertIn("Cryptographic digest mismatch", str(ctx.exception))

    def test_manifest_export_and_import(self) -> None:
        graph = ProvenanceGraph()
        graph.add_node(self.node_a)
        graph.add_node(self.node_b)
        graph.add_derivation("art_a", "art_b", "compile", 100.0, {"opt": "fast"})

        manifest = graph.export_provenance_manifest()
        manifest_json = json.dumps(manifest)

        reloaded_manifest = json.loads(manifest_json)
        imported_graph = ProvenanceGraph.import_provenance_manifest(reloaded_manifest)

        self.assertEqual(imported_graph.node_count, 2)
        self.assertEqual(imported_graph.edge_count, 1)
        self.assertEqual(imported_graph.topological_sort(), ["art_a", "art_b"])

    def test_adversarial_deep_lineage_and_disconnected_graphs(self) -> None:
        graph = ProvenanceGraph(max_nodes=200)

        # 50 nodes chain: n0 -> n1 -> ... -> n49
        for i in range(50):
            node = ArtifactNode(
                artifact_id=f"node_{i}",
                sha256_digest=hashlib.sha256(f"content_{i}".encode()).hexdigest(),
                byte_size=10 + i,
                mime_type="application/octet-stream",
            )
            graph.add_node(node)
            if i > 0:
                graph.add_derivation(f"node_{i-1}", f"node_{i}", "chain_step", float(i))

        # 10 disconnected island nodes
        for j in range(10):
            island = ArtifactNode(
                artifact_id=f"island_{j}",
                sha256_digest=hashlib.sha256(f"island_{j}".encode()).hexdigest(),
                byte_size=5,
                mime_type="text/plain",
            )
            graph.add_node(island)

        self.assertEqual(graph.node_count, 60)
        topo = graph.topological_sort()
        self.assertEqual(len(topo), 60)

        # Verify ancestry on deep chain
        anc_49 = graph.get_ancestors("node_49")
        self.assertEqual(len(anc_49), 49)

        # Trying to close long cycle: node_49 -> node_0
        with self.assertRaises(ValueError) as ctx:
            graph.add_derivation("node_49", "node_0", "long_cycle", 999.0)
        self.assertIn("Circular dependency detected", str(ctx.exception))

    def test_memory_ceiling_64kb(self) -> None:
        tracemalloc.start()
        tracemalloc.reset_peak()

        graph = ProvenanceGraph(max_nodes=100)
        for i in range(40):
            node = ArtifactNode(
                artifact_id=f"bench_{i}",
                sha256_digest=hashlib.sha256(f"bench_payload_{i}".encode()).hexdigest(),
                byte_size=100,
                mime_type="application/octet-stream",
            )
            graph.add_node(node)
            if i > 0:
                graph.add_derivation(f"bench_{i-1}", f"bench_{i}", "step", float(i))

        _ = graph.topological_sort()
        _ = graph.export_provenance_manifest()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Enforce memory ceiling <= 64 KB (65536 bytes)
        self.assertLessEqual(peak, 65536, f"Peak memory {peak} bytes exceeded 64 KB ceiling")


if __name__ == "__main__":
    unittest.main()
