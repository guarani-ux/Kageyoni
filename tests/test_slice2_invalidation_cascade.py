"""
tests/test_slice2_invalidation_cascade.py
Adversarial Verification for Slice 2: Propagate and Invalidate Dependencies Truthfully.
"""

from __future__ import annotations
import json
import sqlite3
import unittest

from kageyoni.research_compiler.claims import (
    ClaimGraph,
    ClaimNode,
    EpistemicStatus,
    SourceRecord,
)
from kageyoni.research_compiler.invalidation_engine import (
    InvalidationEngine,
    InvalidationReport,
)


class Slice2InvalidationCascadeTests(unittest.TestCase):

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
                topic_model_json TEXT NOT NULL,
                is_falsified INTEGER DEFAULT 0
            );
        """)
        self.conn.execute("""
            CREATE TABLE agency_section_records (
                record_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                section_index INTEGER NOT NULL,
                timecode_in TEXT NOT NULL,
                timecode_out TEXT NOT NULL,
                structural_job TEXT NOT NULL,
                spoken_audio TEXT NOT NULL,
                visual_proof TEXT NOT NULL,
                retention_hazard TEXT
            );
        """)
        self.conn.execute("""
            CREATE TABLE situation_records (
                kind TEXT NOT NULL,
                record_key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (kind, record_key)
            );
        """)
        self.conn.commit()
        self.engine = InvalidationEngine(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_claim_graph_handles_cycles_without_infinite_loop(self):
        """Verifies ClaimGraph.invalidate_claim safely terminates when circular child dependencies exist."""
        graph = ClaimGraph()
        src = SourceRecord("src1", "T", "u", "a", "excerpt", 1.0)
        graph.add_source(src)

        c1 = ClaimNode("c1", "Node 1", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["src1"])
        c2 = ClaimNode("c2", "Node 2", EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM, parent_claim_ids=["c1"])
        c3 = ClaimNode("c3", "Node 3", EpistemicStatus.INFERENCE, parent_claim_ids=["c2"])
        graph.add_claim(c1)
        graph.add_claim(c2)
        graph.add_claim(c3)

        # Introduce circular dependency c3 -> c1
        with self.assertRaises(ValueError):
            c3.child_claim_ids.append("c1")

        # Must terminate cleanly and invalidate all 3
        invalidated = graph.invalidate_claim("c1", reason="Cycle test invalidation")
        self.assertEqual(len(invalidated), 3)
        self.assertIn("c1", invalidated)
        self.assertIn("c2", invalidated)
        self.assertIn("c3", invalidated)
        self.assertTrue(c1.is_invalidated)
        self.assertTrue(c2.is_invalidated)
        self.assertTrue(c3.is_invalidated)

    def test_consolidated_cascade_via_claim_graph(self):
        """Verifies graph.invalidate_claim_with_cascade propagates into DB and updates packages and projects."""
        # Insert package and project
        self.conn.execute(
            "INSERT INTO agency_research_packages VALUES (?, ?, ?, ?, ?)",
            ("pkg_alpha", "proj_alpha", "Title Alpha", '{"claims": ["c_root"]}', 0)
        )
        self.conn.execute(
            "INSERT INTO agency_projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("proj_alpha", "Title Alpha", "Obj", "Aud", "ACTIVE", "Owner", '{"active_claim": "c_root"}', 1.0, 1.0)
        )
        self.conn.commit()

        graph = ClaimGraph()
        src = SourceRecord("s_test", "T", "u", "a", "excerpt", 1.0)
        graph.add_source(src)
        c_root = ClaimNode("c_root", "Premise Root", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["s_test"])
        graph.add_claim(c_root)

        report = graph.invalidate_claim_with_cascade("c_root", "Empirical falsification", db=self.conn)
        self.assertIn("pkg_alpha", report.impacted_packages)
        self.assertIn("proj_alpha", report.impacted_projects)

        # Check DB states
        pkg_row = self.conn.execute("SELECT is_falsified FROM agency_research_packages WHERE package_id='pkg_alpha'").fetchone()
        self.assertEqual(pkg_row[0], 1)

        proj_row = self.conn.execute("SELECT current_stage FROM agency_projects WHERE project_id='proj_alpha'").fetchone()
        self.assertEqual(proj_row[0], "REVISION_REQUIRED")

    def test_cascade_invalidates_situations_and_sections(self):
        """Verifies that downstream situations and section records dependent on an invalidated claim are marked stale."""
        # Insert a project and a dependent section
        self.conn.execute(
            "INSERT INTO agency_projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("proj_beta", "Title Beta", "Obj", "Aud", "ACTIVE", "Owner", '{"primary_claim": "c_flawed"}', 1.0, 1.0)
        )
        self.conn.execute(
            "INSERT INTO agency_section_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("sec_01", "proj_beta", 1, "00:00", "00:30", "hook", "We discuss c_flawed here", "proof", None)
        )
        # Insert a situation referencing c_flawed in its payload
        sit_payload = {
            "situation_id": "sit_101",
            "template_id": "discovery_tmpl",
            "workspace": "ws_research",
            "objective": "Explore findings",
            "status": "active",
            "objects": {"claim_ref": "c_flawed"},
            "contradictions": {},
        }
        self.conn.execute(
            "INSERT INTO situation_records VALUES (?, ?, ?)",
            ("situation", "sit_101", json.dumps(sit_payload))
        )
        self.conn.commit()

        graph = ClaimGraph()
        src = SourceRecord("s_beta", "T", "u", "a", "excerpt", 1.0)
        graph.add_source(src)
        c_flawed = ClaimNode("c_flawed", "Flawed Premise", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["s_beta"])
        graph.add_claim(c_flawed)

        report = self.engine.invalidate_claim_with_cascade(graph, "c_flawed", "Source retraction")
        self.assertIn("sec_01", report.impacted_sections)
        self.assertIn("sit_101", report.impacted_situations)

        # Verify situation status is marked invalidated in SQLite
        sit_row = self.conn.execute("SELECT payload_json FROM situation_records WHERE kind='situation' AND record_key='sit_101'").fetchone()
        data = json.loads(sit_row[0])
        self.assertEqual(data["status"], "invalidated")
        self.assertIn("c_flawed", data["contradictions"])


if __name__ == "__main__":
    unittest.main()

