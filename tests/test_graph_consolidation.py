"""
Verification suite for Topology Ownership Consolidation in Vantage and Research Compiler.
Validates:
1. Single authoritative topology owner (CausalDAG) with derived compatibility views.
2. Atomic rollback on rejected insertions (domain records and DAG topology unchanged).
3. Invalidation cascade and approval revocation.
4. Roundtrip serialization and exact restoration of saved validity.
"""

import pytest
from kageyoni.graph import CausalDAG, CycleDetectedError, NodeNotFoundError
from kageyoni.vantage.graph import EpistemicDependencyGraph, GraphNode, EpistemicNodeStatus, ApprovalStatus
from kageyoni.research_compiler.claims import ClaimGraph, ClaimNode, SourceRecord, EpistemicStatus


class TestVantageTopologyConsolidation:
    def test_derived_compatibility_views(self):
        graph = EpistemicDependencyGraph()
        n1 = graph.add_node("concept:01", "concept", "Core Concept")
        n2 = graph.add_node("script:01", "script", "Scene 1 Script", dependencies=["concept:01"])

        # Dependencies and dependents must derive from CausalDAG, not independent edge sets
        assert n1.dependents == {"script:01"}
        assert n2.dependencies == {"concept:01"}
        assert graph._dag.get_node("concept:01").dependents == {"script:01"}
        assert graph._dag.get_node("script:01").dependencies == {"concept:01"}

    def test_rejected_insertion_cycle_atomic_rollback(self):
        graph = EpistemicDependencyGraph()
        graph.add_node("A", "concept", "Node A")
        graph.add_node("B", "script", "Node B", dependencies=["A"])

        orig_dag_node_count = len(graph._dag.nodes)
        orig_nodes_count = len(graph.nodes)
        orig_a_dependents = set(graph.get_node("A").dependents)

        # Attempt to insert a new node C that creates a cycle: B -> C -> A (but A -> B exists)
        # Adding C with dependency B:
        graph.add_node("C", "storyboard", "Node C", dependencies=["B"])
        # Now try to update A to depend on C: A -> B -> C -> A
        with pytest.raises(CycleDetectedError):
            graph.add_node("A", "concept", "Updated Node A", dependencies=["C"])

        # Verify atomic rollback: domain records and DAG topology remain completely unchanged
        assert "C" not in graph.get_node("A").dependencies
        assert "A" not in graph.get_node("C").dependents
        assert graph.get_node("A").title == "Node A"  # domain record was not updated
        assert graph._dag.get_node("A").dependencies == set()
        assert graph._dag.get_node("C").dependents == set()

    def test_rejected_insertion_nonexistent_dependency_leaves_state_unchanged(self):
        graph = EpistemicDependencyGraph()
        graph.add_node("A", "concept", "Node A")

        with pytest.raises(KeyError):
            graph.add_node("B", "script", "Node B", dependencies=["NON_EXISTENT"])

        assert "B" not in graph.nodes
        assert "B" not in graph._dag
        assert len(graph.nodes) == 1
        assert len(graph._dag.nodes) == 1

    def test_restored_validity_matches_saved_validity(self):
        graph = EpistemicDependencyGraph()
        graph.add_node("A", "concept", "Node A")
        graph.add_node("B", "script", "Node B", dependencies=["A"])
        graph.grant_approval("B", approved_by="Director", current_hash="")

        # Invalidate A, which cascades to B and revokes approval
        graph.invalidate("A", reason="SME fact retracted", target_status=EpistemicNodeStatus.STALE)
        assert graph.get_node("A").status == EpistemicNodeStatus.STALE
        assert graph.get_node("B").status == EpistemicNodeStatus.STALE
        assert graph.get_node("B").approval_status == ApprovalStatus.STALE
        assert graph._dag.get_node("A").status == "STALE"
        assert graph._dag.get_node("B").status == "STALE"

        # Serialize and restore
        serialized = graph.to_dict()
        restored = EpistemicDependencyGraph.from_dict(serialized)

        # Restored domain records and CausalDAG nodes must match saved validity exactly
        assert restored.get_node("A").status == EpistemicNodeStatus.STALE
        assert restored.get_node("B").status == EpistemicNodeStatus.STALE
        assert restored.get_node("B").approval_status == ApprovalStatus.STALE
        assert restored._dag.get_node("A").status == "STALE"
        assert restored._dag.get_node("B").status == "STALE"
        assert restored.get_node("A").invalidation_reason == "SME fact retracted"
        assert restored._dag.get_node("A").invalidation_reason == "SME fact retracted"

        # Topology must match exactly
        assert restored.get_node("B").dependencies == {"A"}
        assert restored.get_node("A").dependents == {"B"}


class TestResearchCompilerTopologyConsolidation:
    def test_derived_compatibility_views(self):
        cg = ClaimGraph()
        src = SourceRecord("src_1", "Source Title", "https://example.com", "Author", "Direct excerpt", 100.0)
        cg.add_source(src)

        c1 = ClaimNode("c1", "Claim One", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["src_1"])
        c2 = ClaimNode("c2", "Claim Two", EpistemicStatus.INFERENCE, parent_claim_ids=["c1"])
        cg.add_claim(c1)
        cg.add_claim(c2)

        # Adjacency must derive dynamically from authoritative CausalDAG
        assert list(c1.child_claim_ids) == ["c2"]
        assert list(c2.parent_claim_ids) == ["c1"]
        assert cg._dag.get_node("c1").dependents == {"c2"}
        assert cg._dag.get_node("c2").dependencies == {"c1"}

    def test_rejected_insertion_cycle_atomic_rollback(self):
        cg = ClaimGraph()
        src = SourceRecord("src_1", "Source Title", "https://example.com", "Author", "Direct excerpt", 100.0)
        cg.add_source(src)

        c1 = ClaimNode("c1", "Claim One", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["src_1"])
        c2 = ClaimNode("c2", "Claim Two", EpistemicStatus.INFERENCE, parent_claim_ids=["c1"])
        cg.add_claim(c1)
        cg.add_claim(c2)

        orig_claims_count = len(cg.claims)
        orig_dag_nodes = len(cg._dag.nodes)

        # Attempt to insert c3 that depends on c2 and makes c1 depend on c3 -> cycle!
        c3 = ClaimNode("c3", "Claim Three", EpistemicStatus.INFERENCE, parent_claim_ids=["c2"])
        cg.add_claim(c3)

        # Now try to insert c_bad whose parents would close a cycle: c1 depends on c3
        c_bad = ClaimNode("c1", "Mutated Claim One", EpistemicStatus.INFERENCE, parent_claim_ids=["c3"])
        with pytest.raises(ValueError) as exc:
            cg.add_claim(c_bad)
        assert "CYCLE_DETECTED" in str(exc.value)

        # Assert atomic rollback: c_bad was NOT inserted, edge c3 -> c1 does NOT exist in DAG or claims
        assert "c3" not in cg.claims["c1"].parent_claim_ids
        assert "c1" not in cg.claims["c3"].child_claim_ids
        assert "c1" not in cg._dag.get_node("c3").dependents
        assert "c3" not in cg._dag.get_node("c1").dependencies
        assert cg.claims["c1"].statement == "Claim One"

    def test_rejected_insertion_ungrounded_claim_leaves_state_unchanged(self):
        cg = ClaimGraph()
        c = ClaimNode("c_orphan", "Orphan fact", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["missing_src"])
        with pytest.raises(ValueError) as exc:
            cg.add_claim(c)
        assert "UNGROUNDED_CLAIM" in str(exc.value)

        assert "c_orphan" not in cg.claims
        assert "c_orphan" not in cg._dag

    def test_invalidation_and_restored_validity(self):
        cg = ClaimGraph()
        src = SourceRecord("src_1", "Source Title", "https://example.com", "Author", "Direct excerpt", 100.0)
        cg.add_source(src)

        c1 = ClaimNode("c1", "Claim One", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["src_1"])
        c2 = ClaimNode("c2", "Claim Two", EpistemicStatus.INFERENCE, parent_claim_ids=["c1"])
        cg.add_claim(c1)
        cg.add_claim(c2)

        # Invalidate root claim c1
        invalidated = cg.invalidate_claim("c1", reason="Empirical disproof")
        assert set(invalidated) == {"c1", "c2"}

        # Invalidation must be reflected in both domain ClaimNode and CausalDAG
        assert cg.claims["c1"].is_invalidated is True
        assert cg.claims["c2"].is_invalidated is True
        assert cg._dag.get_node("c1").status == "INVALIDATED"
        assert cg._dag.get_node("c2").status == "INVALIDATED"
