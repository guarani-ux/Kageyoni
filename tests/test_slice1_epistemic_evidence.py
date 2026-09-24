"""
tests/test_slice1_epistemic_evidence.py
Adversarial Verification for Slice 1: Preserve Meaning & Consolidate Evidence Policy.
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
from kageyoni.research_compiler.semantic_casting import (
    cast_claim_safely,
    infer_modality,
    infer_quantifier,
)
from kageyoni.situations.integration import KageyoniSituationAdapter


class FakeEngineForEvidence:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE method_revisions(method_id TEXT)")
        self.db.execute("CREATE TABLE node_method_assignments(node_id TEXT, method_id TEXT, qualification TEXT)")
        self.db.execute("CREATE TABLE events(id TEXT PRIMARY KEY, actor TEXT)")
        self.db.execute("CREATE TABLE artifacts(artifact_id TEXT PRIMARY KEY)")
        self.db.execute("CREATE TABLE pipeline_runs(pipeline_id TEXT PRIMARY KEY, payload_json TEXT)")
        self.db.execute("CREATE TABLE v11_execution_receipts(receipt_id TEXT PRIMARY KEY)")
        self.db.execute("CREATE TABLE node_bindings(node_id TEXT, character_id TEXT)")


class Slice1EpistemicEvidenceTests(unittest.TestCase):

    def test_uncertainty_preservation_roundtrip(self):
        """Verifies that uncertainties are preserved in both directions between EpistemicStatement and ClaimNode."""
        statement = EpistemicStatement(
            statement_id="stmt:uncertain",
            proposition="Pre-adolescent reading latency increases under cognitive overload.",
            status="EVIDENCE_SUPPORTED_CLAIM",
            warrant_or_reasoning="Synthesized from cognitive testing literature.",
            uncertainties=("Sample size limited to 40 students", "Cross-lingual effects unverified"),
        )
        node = statement.to_claim_node()
        self.assertEqual(node.uncertainties, ["Sample size limited to 40 students", "Cross-lingual effects unverified"])

        # Re-convert back
        restored = EpistemicStatement.from_claim_node(node)
        self.assertEqual(restored.uncertainties, ("Sample size limited to 40 students", "Cross-lingual effects unverified"))

        # In ClaimNode.to_dict()
        node_dict = node.to_dict()
        self.assertIn("uncertainties", node_dict)
        self.assertEqual(node_dict["uncertainties"], ["Sample size limited to 40 students", "Cross-lingual effects unverified"])

    def test_unspecified_defaults_do_not_inflate(self):
        """Verifies that unspecified semantic fields default to UNSPECIFIED rather than inflating to CERTAIN/ALL/HIGH."""
        node = ClaimNode(
            claim_id="clm_unspecified",
            statement="Novel intervention introduced in pilot library branch.",
            epistemic_status=EpistemicStatus.ASSUMPTION,
        )
        self.assertEqual(node.confidence_level, "UNSPECIFIED")
        self.assertEqual(node.modality, "UNSPECIFIED")
        self.assertEqual(node.quantifier, "UNSPECIFIED")
        self.assertEqual(node.uncertainties, [])

        graph = ClaimGraph()
        graph.add_claim(node)

        # Unspecified claim must NOT appear in established facts
        established = graph.get_established_facts()
        self.assertNotIn(node, established)

        # Unspecified claim MUST be flagged in uncertain claims
        uncertain = graph.get_uncertain_claims()
        self.assertIn(node, uncertain)

    def test_uncertainties_propagate_through_semantic_casting(self):
        """Verifies that cast_claim_safely preserves uncertainties on derived child claims."""
        parent = ClaimNode(
            claim_id="clm_parent_with_uncertainty",
            statement="Intervention may increase attendance in some cohorts.",
            epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
            modality="POSSIBLE",
            quantifier="SOME",
            uncertainties=["Longitudinal retention unknown"],
        )
        child = cast_claim_safely(
            source_claim=parent,
            new_claim_id="clm_child_cast",
            target_statement="Intervention might slightly boost attendance in certain groups.",
            target_status=EpistemicStatus.INFERENCE,
            target_modality="POSSIBLE",
            target_quantifier="SOME",
        )
        self.assertEqual(child.uncertainties, ["Longitudinal retention unknown"])

    def test_auto_created_sources_marked_primary_unverified_with_empty_excerpt(self):
        """Verifies ledger adapter marks auto-created sources PRIMARY_UNVERIFIED without copying proposition as direct excerpt."""
        ledger = EpistemicLedger()
        statement = EpistemicStatement(
            statement_id="stmt:auto_src",
            proposition="Youth participation rose 15% in Q3.",
            status="SOURCE_SUPPLIED_FACT",
            provenance_source="src:external_doc_1",
        )
        ledger.record(statement)

        src = ledger.graph.sources["src:external_doc_1"]
        self.assertEqual(src.reliability_tier, "PRIMARY_UNVERIFIED")
        self.assertEqual(src.direct_excerpt, "")
        self.assertEqual(src.source_says_statement, "")

    def test_keyword_proof_heuristic_rejected_in_favor_of_warrant_and_provenance(self):
        """Verifies that keyword-based hacks (e.g. 'verified') fail if structural warrant or provenance is missing."""
        ledger = EpistemicLedger()
        unknown = EpistemicStatement(
            statement_id="stmt:unk",
            proposition="True drop-out rate of non-cardholders is unknown.",
            status="UNKNOWN",
        )
        ledger.record(unknown)

        # Keyword 'verified' present in reasoning, but missing substantive warrant length
        with self.assertRaises(EpistemicLaunderingError):
            ledger.transform(
                source_id="stmt:unk",
                target_id="stmt:laundered_by_keyword",
                new_proposition="Drop-out rate is 20%.",
                new_status="EVIDENCE_SUPPORTED_CLAIM",
                reasoning="verified",
            )

        # Keyword 'verified' with long text but no provenance sources cannot promote to EVIDENCE_SUPPORTED_CLAIM
        with self.assertRaises(EpistemicLaunderingError):
            ledger.transform(
                source_id="stmt:unk",
                target_id="stmt:laundered_no_prov",
                new_proposition="Drop-out rate is 20%.",
                new_status="EVIDENCE_SUPPORTED_CLAIM",
                reasoning="We verified this through informal conversation with staff.",
            )

    def test_situation_adapter_evidence_distinguishes_revocation_from_existence(self):
        """Verifies KageyoniSituationAdapter.evidence rejects revoked qualifications despite row existence."""
        engine = FakeEngineForEvidence()
        adapter = KageyoniSituationAdapter(engine)

        # 1. Non-existent method
        self.assertFalse(adapter.evidence("method:method_revoked"))

        # 2. Method exists in revisions, but assignment is revoked
        engine.db.execute("INSERT INTO method_revisions VALUES('method_revoked')")
        engine.db.execute("INSERT INTO node_method_assignments VALUES('node_1', 'method_revoked', 'revoked')")
        self.assertFalse(adapter.evidence("method:method_revoked"))

        # 3. Method exists with active/experimental assignment
        engine.db.execute("INSERT INTO method_revisions VALUES('method_valid')")
        engine.db.execute("INSERT INTO node_method_assignments VALUES('node_1', 'method_valid', 'experimental')")
        self.assertTrue(adapter.evidence("method:method_valid"))


if __name__ == "__main__":
    unittest.main()
