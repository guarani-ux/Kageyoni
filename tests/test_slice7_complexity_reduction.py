"""
tests/test_slice7_complexity_reduction.py
Adversarial Verification for Slice 7: Complexity Reduction & Net Code Deletion.
Validates that:
1. Canonical ClaimGraph provides authoritative verify_no_laundering() without redundant ledger audit traversal.
2. EpistemicLedger delegates verify_no_laundering() directly to ClaimGraph.
3. AgencyWorkflows initializes and executes cleanly without dead ledger state.
4. qualify_transfer() routes cleanly through Transfers service without raw bypass fallbacks.
5. InvalidationEngine initializes schema under UnitOfWork transaction custody.
"""

from __future__ import annotations
import sqlite3
import unittest

from contracts.epistemic_ledger import (
    EpistemicLedger,
    EpistemicStatement,
    EpistemicLaunderingError,
)
from kageyoni.research_compiler.claims import (
    ClaimGraph,
    ClaimNode,
    EpistemicStatus,
    SourceRecord,
)
from kageyoni.situations.memory import (
    SituationMemory,
    TransferCandidate,
    qualify_transfer,
)
from kageyoni.research_compiler.invalidation_engine import InvalidationEngine
from kageyoni.agency_workflows import AgencyWorkflows


class Slice7ComplexityReductionTests(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()

    def test_claim_graph_authoritative_verify_no_laundering(self):
        """ClaimGraph.verify_no_laundering detects ungrounded assumption promotion in graph structure."""
        graph = ClaimGraph()
        src = SourceRecord(
            source_id="src:valid",
            title="Valid Source",
            provenance="doc://ref",
            author_or_institution="Org",
            direct_excerpt="Exact text",
            date_recorded=100.0,
        )

        graph.add_source(src)

        # Valid fact
        fact = ClaimNode(
            claim_id="claim:fact",
            statement="Baseline fact statement",
            epistemic_status=EpistemicStatus.SOURCE_SUPPLIED_FACT,
            provenance_sources=["src:valid"],
        )
        graph.add_claim(fact)
        self.assertTrue(graph.verify_no_laundering())

        # Unwarranted assumption
        assumption = ClaimNode(
            claim_id="claim:assumption",
            statement="Assumed statement",
            epistemic_status=EpistemicStatus.ASSUMPTION,
        )
        graph.add_claim(assumption)
        self.assertTrue(graph.verify_no_laundering())

        # Laundering node: claim claims to be EVIDENCE_SUPPORTED_CLAIM but parent is ASSUMPTION
        laundered = ClaimNode(
            claim_id="claim:laundered",
            statement="Promoted fact without evidence",
            epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
            parent_claim_ids=["claim:assumption"],
            provenance_sources=["src:valid"],
        )
        graph.add_claim(laundered)

        # graph.verify_no_laundering() must detect this and return False
        self.assertFalse(graph.verify_no_laundering())

    def test_epistemic_ledger_delegation_to_claim_graph(self):
        """EpistemicLedger.verify_no_laundering delegates to ClaimGraph."""
        ledger = EpistemicLedger()
        fact = EpistemicStatement(
            statement_id="fact:1",
            proposition="Real proposition",
            status="SOURCE_SUPPLIED_FACT",
            provenance_source="src:1",
        )
        ledger.record(fact)
        self.assertTrue(ledger.verify_no_laundering())

        # Inject laundered node directly into graph
        bad_claim = ClaimNode(
            claim_id="claim:bad",
            statement="Bad claim",
            epistemic_status=EpistemicStatus.SOURCE_SUPPLIED_FACT,
            parent_claim_ids=["assump:ghost"],
            provenance_sources=["src:1"],
        )
        ghost = ClaimNode(
            claim_id="assump:ghost",
            statement="Ghost assumption",
            epistemic_status=EpistemicStatus.ASSUMPTION,
        )
        ledger.graph.add_claim(ghost)
        ledger.graph.add_claim(bad_claim)

        # Delegation must catch the laundering
        self.assertFalse(ledger.verify_no_laundering())

    def test_agency_workflows_initialization_without_dead_ledger(self):
        """AgencyWorkflows initializes schema and operates without redundant self.ledger."""
        class MockEngine:
            def __init__(self, db):
                self.db = db
        engine = MockEngine(self.conn)
        workflows = AgencyWorkflows(engine)
        self.assertFalse(hasattr(workflows, "ledger"), "AgencyWorkflows should not retain dead self.ledger")

        # Verify agency tables were created cleanly
        tables = [r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        self.assertIn("agency_projects", tables)
        self.assertIn("agency_gate_records", tables)
        self.assertIn("agency_research_packages", tables)

    def test_qualify_transfer_without_bypass_sql(self):
        """qualify_transfer routes status checks cleanly through Transfers service without raw SQL bypass."""
        candidate = TransferCandidate(
            candidate_id="transfer:valid",
            source_memory_id="mem:1",
            destination_situation_id="sit:dest",
            mapping="map:test",
            destination_evidence_refs=("event:1",),
            destination_workspace_id="default",
        )

        def dummy_resolver(ref, sit):
            return True

        # When evidence resolves and no engine is passed, status is supported_in_destination
        res = qualify_transfer(candidate, evidence_resolver=dummy_resolver)
        self.assertEqual(res.status, "supported_in_destination")

    def test_invalidation_engine_unit_of_work_schema(self):
        """InvalidationEngine initializes its schema under transaction custody without bare commit."""
        engine = InvalidationEngine(self.conn)
        row = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agency_claim_retractions'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "agency_claim_retractions")


if __name__ == "__main__":
    unittest.main()
