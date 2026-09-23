"""
tests/test_g2_g3_semantic_integrity.py
Adversarial Verification for Gates G2 and G3:
- G2: Source-to-Claim Grounding & Separation
- G3: Preserving Meaning Through Transformations (Semantic Casting)
"""

from __future__ import annotations
import hashlib
import time
import unittest

from kageyoni.research_compiler.claims import (
    ClaimGraph,
    ClaimNode,
    EpistemicStatus,
    SourceRecord,
)
from kageyoni.research_compiler.semantic_casting import (
    SemanticCastingError,
    cast_claim_safely,
    infer_modality,
    infer_quantifier,
    validate_semantic_transition,
)
from contracts.epistemic_ledger import EPISTEMIC_STATUSES


class TestGateG2SourceClaimSupport(unittest.TestCase):

    def test_source_record_hash_and_literal_separation(self):
        """Verifies content hash calculation and literal assertion vs warranted claim."""
        excerpt = "Calgary Public Library offers free memberships to all residents."
        src = SourceRecord(
            source_id="src_cpl_01",
            title="CPL Membership Policy",
            provenance="https://calgarylibrary.ca/join",
            author_or_institution="Calgary Public Library",
            direct_excerpt=excerpt,
            date_recorded=time.time(),
        )
        expected_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        self.assertEqual(src.content_hash, expected_hash)
        self.assertEqual(src.source_says_statement, excerpt)

    def test_ungrounded_claim_rejected(self):
        """Rejects a claim declaring provenance sources that do not exist in the graph."""
        graph = ClaimGraph()
        claim = ClaimNode(
            claim_id="claim_01",
            statement="Libraries improve literacy.",
            epistemic_status=EpistemicStatus.SOURCE_SUPPLIED_FACT,
            provenance_sources=["nonexistent_source_id"],
        )
        with self.assertRaises(ValueError) as ctx:
            graph.add_claim(claim)
        self.assertIn("UNGROUNDED_CLAIM", str(ctx.exception))

    def test_epistemic_laundering_prevented_in_claim_graph(self):
        """Rejects SOURCE_SUPPLIED_FACT declared with zero provenance sources."""
        graph = ClaimGraph()
        claim = ClaimNode(
            claim_id="claim_02",
            statement="Plausible sounding fact without sources.",
            epistemic_status=EpistemicStatus.SOURCE_SUPPLIED_FACT,
            provenance_sources=[],
        )
        with self.assertRaises(ValueError) as ctx:
            graph.add_claim(claim)
        self.assertIn("EPISTEMIC_LAUNDERING", str(ctx.exception))

    def test_backward_lineage_preserves_hashes_and_literal_assertions(self):
        """Backward lineage walk returns source_says_statement and content_hash."""
        graph = ClaimGraph()
        excerpt = "Over 750,000 active cardholders in 2024."
        src = SourceRecord(
            source_id="src_annual_report",
            title="2024 Annual Report",
            provenance="annual_report_2024.pdf",
            author_or_institution="Calgary Public Library",
            direct_excerpt=excerpt,
            date_recorded=1700000000.0,
        )
        graph.add_source(src)

        parent_claim = ClaimNode(
            claim_id="c_parent",
            statement="CPL maintains 750k+ active accounts.",
            epistemic_status=EpistemicStatus.SOURCE_SUPPLIED_FACT,
            provenance_sources=["src_annual_report"],
            evidence_establishes_claim="Active member base verified at 750k+.",
        )
        graph.add_claim(parent_claim)

        child_claim = ClaimNode(
            claim_id="c_child",
            statement="High community reach across Calgary.",
            epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
            parent_claim_ids=["c_parent"],
            evidence_establishes_claim="Direct reach is extensive.",
        )
        graph.add_claim(child_claim)

        lineage = graph.trace_backward_lineage("c_child")
        self.assertEqual(lineage["claim_id"], "c_child")
        self.assertEqual(len(lineage["parent_lineages"]), 1)
        parent_lin = lineage["parent_lineages"][0]
        self.assertEqual(parent_lin["claim_id"], "c_parent")
        self.assertEqual(parent_lin["direct_sources"][0]["content_hash"], src.content_hash)
        self.assertEqual(parent_lin["direct_sources"][0]["source_says_statement"], excerpt)


class TestGateG3SemanticCasting(unittest.TestCase):

    def test_vocabulary_unification_with_epistemic_ledger(self):
        """Verifies that all 9 canonical statuses from contracts/epistemic_ledger.py are supported."""
        for status_name in EPISTEMIC_STATUSES:
            # Must exist in EpistemicStatus enum
            self.assertTrue(hasattr(EpistemicStatus, status_name), f"Missing status: {status_name}")
            enum_val = getattr(EpistemicStatus, status_name).value
            self.assertEqual(enum_val, status_name)

    def test_modality_promotion_rejected(self):
        """Verifies that 'may' cannot be promoted to 'does' or 'proves'."""
        source_claim = ClaimNode(
            claim_id="c_mod_source",
            statement="Reading graphic novels may increase vocabulary retention in some readers.",
            epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
            modality="POSSIBLE",
            quantifier="SOME",
        )

        with self.assertRaises(SemanticCastingError) as ctx:
            cast_claim_safely(
                source_claim=source_claim,
                new_claim_id="c_mod_promoted",
                target_statement="Reading graphic novels proves that students will master reading.",
                target_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
                target_modality="CERTAIN",
            )
        self.assertIn("ILLEGAL_MODALITY_PROMOTION", str(ctx.exception))

    def test_quantifier_expansion_rejected(self):
        """Verifies that 'some' cannot expand to 'all'."""
        source_claim = ClaimNode(
            claim_id="c_quant_source",
            statement="Some library branches experience weekend parking congestion.",
            epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
            modality="CERTAIN",
            quantifier="SOME",
        )

        with self.assertRaises(SemanticCastingError) as ctx:
            cast_claim_safely(
                source_claim=source_claim,
                new_claim_id="c_quant_promoted",
                target_statement="All library branches suffer from severe parking deficits.",
                target_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
                target_quantifier="ALL",
            )
        self.assertIn("ILLEGAL_QUANTIFIER_EXPANSION", str(ctx.exception))

    def test_epistemic_status_laundering_rejected(self):
        """Verifies that an ASSUMPTION cannot be cast into a SOURCE_SUPPLIED_FACT."""
        source_claim = ClaimNode(
            claim_id="c_assump",
            statement="Assume youth prefer digital access.",
            epistemic_status=EpistemicStatus.ASSUMPTION,
        )

        with self.assertRaises(SemanticCastingError) as ctx:
            cast_claim_safely(
                source_claim=source_claim,
                new_claim_id="c_laundered",
                target_statement="Youth prefer digital access.",
                target_status=EpistemicStatus.SOURCE_SUPPLIED_FACT,
            )
        self.assertIn("EPISTEMIC_STATUS_LAUNDERING", str(ctx.exception))

    def test_valid_conservative_transformation_succeeds(self):
        """Verifies that conservative, modality-preserving transformation succeeds."""
        source_claim = ClaimNode(
            claim_id="c_valid_src",
            statement="Survey indicates that some patrons may visit weekly.",
            epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
            modality="POSSIBLE",
            quantifier="SOME",
        )

        child = cast_claim_safely(
            source_claim=source_claim,
            new_claim_id="c_valid_child",
            target_statement="Weekly visitation might occur among a subset of patrons.",
            target_status=EpistemicStatus.INFERENCE,
            target_modality="POSSIBLE",
            target_quantifier="SOME",
        )
        self.assertEqual(child.claim_id, "c_valid_child")
        self.assertEqual(child.modality, "POSSIBLE")
        self.assertEqual(child.quantifier, "SOME")
        self.assertIn("c_valid_src", child.parent_claim_ids)


if __name__ == "__main__":
    unittest.main()
