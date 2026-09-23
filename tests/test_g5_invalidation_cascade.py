"""
tests/test_g5_invalidation_cascade.py
Adversarial Verification for Gate G5: Invalidation Engine, Cascading Retractions, and Cycle Detection.
"""

from __future__ import annotations
import sqlite3
import unittest

from kageyoni.research_compiler.claims import (
    ClaimGraph,
    ClaimNode,
    EpistemicStatus,
    SourceRecord,
)
from kageyoni.research_compiler.invalidation_engine import InvalidationEngine


class TestGateG5InvalidationCascade(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE agency_projects (
                project_id TEXT PRIMARY KEY,
                working_title TEXT NOT NULL,
                objective TEXT NOT NULL,
                target_audience TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                decision_owner TEXT NOT NULL,
                metadata_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
        """)
        self.conn.execute("""
            CREATE TABLE agency_research_packages (
                package_id TEXT PRIMARY KEY,
                project_id TEXT,
                subject_title TEXT NOT NULL,
                topic_model_json TEXT NOT NULL
            );
        """)
        self.conn.commit()
        self.engine = InvalidationEngine(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_recursive_cascade_to_child_claims(self):
        """Verifies that invalidating a root claim recursively invalidates all downstream children."""
        graph = ClaimGraph()
        src = SourceRecord("s1", "Title", "url", "auth", "Direct statement excerpt", 1.0)
        graph.add_source(src)

        c1 = ClaimNode("c1", "Root assertion", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["s1"])
        c2 = ClaimNode("c2", "Derived premise", EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM, parent_claim_ids=["c1"])
        c3 = ClaimNode("c3", "Creative treatment thesis", EpistemicStatus.CREATIVE_DECISION, parent_claim_ids=["c2"])
        c_unrelated = ClaimNode("c_other", "Independent claim", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["s1"])

        graph.add_claim(c1)
        graph.add_claim(c2)
        graph.add_claim(c3)
        graph.add_claim(c_unrelated)

        report = self.engine.invalidate_claim_with_cascade(graph, "c1", reason="Source data retracted by publisher")
        self.assertEqual(len(report.invalidated_child_claims), 3)
        self.assertIn("c1", report.invalidated_child_claims)
        self.assertIn("c2", report.invalidated_child_claims)
        self.assertIn("c3", report.invalidated_child_claims)
        self.assertNotIn("c_other", report.invalidated_child_claims)

        self.assertTrue(c1.is_invalidated)
        self.assertTrue(c2.is_invalidated)
        self.assertTrue(c3.is_invalidated)
        self.assertFalse(c_unrelated.is_invalidated)

    def test_cycle_detection_prevents_infinite_recursion(self):
        """Verifies that cyclical claims do not cause recursion errors and are flagged."""
        graph = ClaimGraph()
        src = SourceRecord("s1", "Title", "url", "auth", "Direct statement excerpt", 1.0)
        graph.add_source(src)

        cA = ClaimNode("cA", "Claim A", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["s1"])
        cB = ClaimNode("cB", "Claim B", EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM, parent_claim_ids=["cA"])
        graph.add_claim(cA)
        graph.add_claim(cB)

        # Artificially introduce cycle: cB -> cA
        cA.parent_claim_ids.append("cB")
        cB.child_claim_ids.append("cA")

        report = self.engine.invalidate_claim_with_cascade(graph, "cA", reason="Contradiction observed")
        self.assertTrue(report.cycle_detected)
        self.assertIn("cA", report.invalidated_child_claims)
        self.assertIn("cB", report.invalidated_child_claims)

    def test_durable_sqlite_cascade_updates_projects_and_logs_audit(self):
        """Verifies that affected database projects are marked REVISION_REQUIRED and retractions are logged."""
        # Insert a package containing c_target
        self.conn.execute(
            "INSERT INTO agency_research_packages VALUES (?, ?, ?, ?)",
            ("pkg_101", "proj_999", "Library Study", '{"topic": "study", "claims": ["c_target", "c_ok"]}')
        )
        # Insert a project referencing the affected claim
        self.conn.execute(
            """
            INSERT INTO agency_projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("proj_999", "Campaign Video", "Drive cards", "Teens", "PRODUCTION_SCRIPTING", "owner", '{"active_claim": "c_target"}', 100.0, 100.0)
        )
        self.conn.commit()

        graph = ClaimGraph()
        src = SourceRecord("s1", "Title", "url", "auth", "Excerpt", 1.0)
        graph.add_source(src)
        c_target = ClaimNode("c_target", "Flawed claim", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["s1"])
        graph.add_claim(c_target)

        report = self.engine.invalidate_claim_with_cascade(graph, "c_target", reason="Methodological error in source study")
        self.assertIn("pkg_101", report.impacted_packages)
        self.assertIn("proj_999", report.impacted_projects)

        # Verify project stage was updated to REVISION_REQUIRED
        cur = self.conn.cursor()
        cur.execute("SELECT current_stage FROM agency_projects WHERE project_id = 'proj_999'")
        updated_stage = cur.fetchone()[0]
        self.assertEqual(updated_stage, "REVISION_REQUIRED")

        # Verify retraction record was written to agency_claim_retractions
        cur.execute("SELECT root_claim_id, reason FROM agency_claim_retractions WHERE root_claim_id = 'c_target'")
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "c_target")
        self.assertEqual(row[1], "Methodological error in source study")


if __name__ == "__main__":
    unittest.main()
