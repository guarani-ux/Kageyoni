import unittest
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from contracts.epistemic_ledger import EpistemicLedger, EpistemicStatement, EpistemicLaunderingError

class EpistemicLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = EpistemicLedger()

    def test_record_valid_source_fact(self):
        stmt = EpistemicStatement(
            statement_id="fact:1",
            proposition="CPL reached 26,600 students across 12 programs.",
            status="SOURCE_SUPPLIED_FACT",
            provenance_source="CPL 2023-2026 Strategic Plan & Video Inventory"
        )
        saved = self.ledger.record(stmt)
        self.assertEqual(saved.statement_id, "fact:1")
        self.assertTrue(saved.digest())

    def test_reject_unattributed_source_fact(self):
        with self.assertRaises(EpistemicLaunderingError):
            EpistemicStatement(
                statement_id="fact:bad",
                proposition="Unattributed statement",
                status="SOURCE_SUPPLIED_FACT",
                provenance_source=None
            )

    def test_prevent_assumption_laundering_into_fact(self):
        assumption = EpistemicStatement(
            statement_id="assump:1",
            proposition="Target audience checks YouTube before school.",
            status="ASSUMPTION"
        )
        self.ledger.record(assumption)

        with self.assertRaises(EpistemicLaunderingError):
            self.ledger.transform(
                source_id="assump:1",
                target_id="claim:laundered",
                new_proposition="Audience always watches before school.",
                new_status="EVIDENCE_SUPPORTED_CLAIM",
                reasoning="Plausible summary compression"
            )

    def test_prevent_creative_decision_laundering_into_empirical_fact(self):
        creative = EpistemicStatement(
            statement_id="art:1",
            proposition="The protagonist must wear a deep blue hood.",
            status="CREATIVE_DECISION"
        )
        self.ledger.record(creative)

        with self.assertRaises(EpistemicLaunderingError):
            self.ledger.transform(
                source_id="art:1",
                target_id="claim:bad",
                new_proposition="Blue hoods statistically increase conversion.",
                new_status="EVIDENCE_SUPPORTED_CLAIM",
                reasoning="Creative choice framed as evidence"
            )

if __name__ == "__main__":
    unittest.main()
