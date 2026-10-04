"""
Unit tests for kageyoni.graph: Unified Causal Directed Acyclic Graph.

Verifies:
1. Node creation, payload hashing, and status.
2. Bidirectional edge binding.
3. Cycle detection (self-loop, direct, and indirect).
4. Forward Invalidation Cascade (targeted retraction, leaves independent branches intact).
5. Backward Lineage Walking (traces conclusions back to empirical roots).
6. Topological Sorting (Kahn's algorithm).
7. SQLite ACID persistence and recovery.
8. Edge and node removal.
"""

from __future__ import annotations
import sqlite3
import unittest
from pathlib import Path
import sys

# Ensure local kageyoni is prioritized
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path[:1]:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.graph import CausalDAG, DAGNode, CycleDetectedError, NodeNotFoundError


class TestCausalDAG(unittest.TestCase):

    def setUp(self):
        self.dag = CausalDAG()

    def test_node_creation_and_payload_hashing(self):
        node = self.dag.add_node("n1", "source", payload={"title": "Field Report Alpha", "author": "Sciel"})
        self.assertEqual(node.node_id, "n1")
        self.assertEqual(node.node_type, "source")
        self.assertEqual(node.status, "VALID")
        self.assertTrue(len(node.content_hash) > 0)
        self.assertIn("n1", self.dag)
        self.assertEqual(len(self.dag), 1)

    def test_bidirectional_edge_binding(self):
        self.dag.add_node("parent", "premise")
        self.dag.add_node("child", "deduction", dependencies=["parent"])

        parent = self.dag.get_node("parent")
        child = self.dag.get_node("child")

        self.assertIn("child", parent.dependents)
        self.assertIn("parent", child.dependencies)

    def test_cycle_detection_self_loop(self):
        self.dag.add_node("loop", "concept")
        with self.assertRaises(CycleDetectedError):
            self.dag.add_edge("loop", "loop")

    def test_cycle_detection_indirect(self):
        # A -> B -> C
        self.dag.add_node("A", "root")
        self.dag.add_node("B", "middle", dependencies=["A"])
        self.dag.add_node("C", "leaf", dependencies=["B"])

        # Attempting C -> A must be blocked
        with self.assertRaises(CycleDetectedError):
            self.dag.add_edge("C", "A")

        # Attempting C -> B must also be blocked
        with self.assertRaises(CycleDetectedError):
            self.dag.add_edge("C", "B")

    def test_forward_invalidation_cascade(self):
        # Branch 1: Source A -> Claim B -> Conclusion C
        self.dag.add_node("src_A", "source")
        self.dag.add_node("claim_B", "claim", dependencies=["src_A"])
        self.dag.add_node("conclusion_C", "decision", dependencies=["claim_B"])

        # Branch 2 (Independent): Source X -> Claim Y
        self.dag.add_node("src_X", "source")
        self.dag.add_node("claim_Y", "claim", dependencies=["src_X"])

        # Invalidate root of Branch 1
        affected = self.dag.invalidate("src_A", "Source data corrupted upon re-test")

        # Verify Branch 1 is entirely invalidated
        self.assertIn("src_A", affected)
        self.assertIn("claim_B", affected)
        self.assertIn("conclusion_C", affected)

        self.assertEqual(self.dag.get_node("src_A").status, "INVALIDATED")
        self.assertEqual(self.dag.get_node("claim_B").status, "INVALIDATED")
        self.assertEqual(self.dag.get_node("conclusion_C").status, "INVALIDATED")
        self.assertIn("corrupted", self.dag.get_node("conclusion_C").invalidation_reason)

        # Verify Branch 2 remains completely VALID (no collateral damage)
        self.assertEqual(self.dag.get_node("src_X").status, "VALID")
        self.assertEqual(self.dag.get_node("claim_Y").status, "VALID")
        self.assertNotIn("src_X", affected)
        self.assertNotIn("claim_Y", affected)

    def test_backward_lineage_trace(self):
        # Multiple roots feed one conclusion:
        # (Src1, Src2) -> StepA -> (StepA, Src3) -> FinalResult
        self.dag.add_node("src1", "source")
        self.dag.add_node("src2", "source")
        self.dag.add_node("src3", "source")
        self.dag.add_node("stepA", "intermediate", dependencies=["src1", "src2"])
        self.dag.add_node("final", "output", dependencies=["stepA", "src3"])

        roots = self.dag.trace_lineage("final")
        self.assertEqual(roots, ["src1", "src2", "src3"])

        # Roots of stepA alone
        roots_a = self.dag.trace_lineage("stepA")
        self.assertEqual(roots_a, ["src1", "src2"])

    def test_topological_sort(self):
        # Task 1 -> Task 2 -> Task 3
        # Task 4 -> Task 3
        self.dag.add_node("t1", "task")
        self.dag.add_node("t4", "task")
        self.dag.add_node("t2", "task", dependencies=["t1"])
        self.dag.add_node("t3", "task", dependencies=["t2", "t4"])

        order = self.dag.topological_sort()
        
        # Verify ordering constraints
        self.assertTrue(order.index("t1") < order.index("t2"))
        self.assertTrue(order.index("t2") < order.index("t3"))
        self.assertTrue(order.index("t4") < order.index("t3"))

    def test_sqlite_persistence_roundtrip(self):
        conn = sqlite3.connect(":memory:")
        self.dag.add_node("doc1", "brief", payload={"title": "Mission Spec"})
        self.dag.add_node("gate1", "gate", payload={"threshold": 0.95}, dependencies=["doc1"])
        self.dag.invalidate("doc1", "Spec revised by operator")

        # Save to SQLite
        self.dag.to_sqlite(conn)

        # Reload into a completely fresh CausalDAG
        loaded = CausalDAG.from_sqlite(conn)
        conn.close()

        self.assertEqual(len(loaded), 2)
        self.assertIn("doc1", loaded)
        self.assertIn("gate1", loaded)

        doc1 = loaded.get_node("doc1")
        gate1 = loaded.get_node("gate1")

        self.assertEqual(doc1.status, "INVALIDATED")
        self.assertEqual(doc1.payload["title"], "Mission Spec")
        self.assertIn("gate1", doc1.dependents)
        self.assertIn("doc1", gate1.dependencies)

    def test_edge_and_node_removal(self):
        self.dag.add_node("A", "node")
        self.dag.add_node("B", "node", dependencies=["A"])

        self.assertIn("B", self.dag.get_node("A").dependents)
        self.dag.remove_edge("A", "B")
        self.assertNotIn("B", self.dag.get_node("A").dependents)
        self.assertNotIn("A", self.dag.get_node("B").dependencies)

        # Remove node
        self.dag.remove_node("A")
        self.assertNotIn("A", self.dag)
        self.assertIn("B", self.dag)


if __name__ == "__main__":
    unittest.main()
