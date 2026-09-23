"""
tests/test_g1_completion_checker.py
Adversarial Probes for Gate G1: Completion Checker Hardening.

Proves that tools/generate_qualification_record.py fails closed against:
1. Missing or uninitialized frontier database.
2. Unresolved open frontiers.
3. Unclosed or unverified Scars (missing repair_ref, reprobe_passed=False, positive_control_passed=False).
4. Survived mutation check.
5. Missing or stale candidate git_sha in package parity and clean wheel install audits.
6. Uncommitted working tree state.
"""

from __future__ import annotations
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.generate_qualification_record as gen_qual


class GateG1CompletionCheckerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_frontier_db_fails_closed(self):
        """Probe 1: A missing state/v11_completion_situation.sqlite must fail closed as BLOCKED, not empty."""
        fake_db = self.tmp_path / "nonexistent.sqlite"
        frontiers = gen_qual.check_frontiers(fake_db)
        self.assertGreater(len(frontiers), 0)
        self.assertEqual(frontiers[0]["state"], "BLOCKED")
        self.assertEqual(frontiers[0]["kind"], "DEFICIT")

    def test_open_frontier_blocks_release(self):
        """Probe 2: Unresolved frontiers in v11_frontiers must report as open frontiers."""
        fake_db = self.tmp_path / "frontier.sqlite"
        conn = sqlite3.connect(str(fake_db))
        conn.execute("CREATE TABLE v11_frontiers (frontier_id TEXT, state TEXT, kind TEXT, objective TEXT)")
        conn.execute("INSERT INTO v11_frontiers VALUES ('F-01', 'open', 'gap', 'resolve domain mediation')")
        conn.commit()
        conn.close()

        frontiers = gen_qual.check_frontiers(fake_db)
        self.assertEqual(len(frontiers), 1)
        self.assertEqual(frontiers[0]["frontier_id"], "F-01")
        self.assertEqual(frontiers[0]["state"], "open")

    def test_unclosed_scar_fails_closed(self):
        """Probe 3: Scars missing repair_ref, reprobe_passed, or positive_control_passed must report as open."""
        scar_manifest = {
            "scars": [
                {
                    "scar_id": "SCAR-BAD-01",
                    "class": "counterfeit",
                    "status": "closed",
                    "repair_ref": "",  # missing repair_ref
                    "reprobe_passed": True,
                    "positive_control_passed": True,
                },
                {
                    "scar_id": "SCAR-BAD-02",
                    "class": "authority",
                    "status": "closed",
                    "repair_ref": "patch:123",
                    "reprobe_passed": False,  # failed reprobe
                    "positive_control_passed": True,
                },
                {
                    "scar_id": "SCAR-GOOD-01",
                    "class": "schema",
                    "status": "closed",
                    "repair_ref": "patch:456",
                    "reprobe_passed": True,
                    "positive_control_passed": True,
                }
            ]
        }
        manifest_file = self.tmp_path / "scar_inventory.json"
        manifest_file.write_text(json.dumps(scar_manifest), encoding="utf-8")

        open_scars = gen_qual.check_scars(manifest_file)
        open_ids = [s["scar_id"] for s in open_scars]
        self.assertIn("SCAR-BAD-01", open_ids)
        self.assertIn("SCAR-BAD-02", open_ids)
        self.assertNotIn("SCAR-GOOD-01", open_ids)

    def test_missing_scar_manifest_fails_closed(self):
        """Probe 3b: Missing scar inventory manifest must produce VERIFIER_DEFICIT."""
        manifest_file = self.tmp_path / "nonexistent_scars.json"
        open_scars = gen_qual.check_scars(manifest_file)
        self.assertGreater(len(open_scars), 0)
        self.assertEqual(open_scars[0]["deficit"], "VERIFIER_DEFICIT")

    def test_mutation_check_evaluates_actual_execution(self):
        """Probe 4: Mutation check must fail if any mutant survives."""
        # Mutation failure case
        bad_mutation_output = {"killed": ["m1", "m2"], "inconclusive": [("m3", "mutant survived")]}
        self.assertFalse(gen_qual.evaluate_mutation_result(bad_mutation_output, expected_mutants=3))

        # Mutation success case
        good_mutation_output = {"killed": ["m1", "m2", "m3"], "inconclusive": []}
        self.assertTrue(gen_qual.evaluate_mutation_result(good_mutation_output, expected_mutants=3))

    def test_stale_candidate_sha_in_wheel_parity_fails_closed(self):
        """Probe 5: Mismatched or missing git_sha in parity audits must reject package parity."""
        pkg_audit = self.tmp_path / "package_parity_audit.json"
        clean_audit = self.tmp_path / "clean_wheel_install_audit.json"

        # Case A: Missing git_sha
        pkg_audit.write_text(json.dumps({"parity_audit_passed": True}), encoding="utf-8")
        clean_audit.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
        self.assertFalse(gen_qual.check_package_parity(pkg_audit, clean_audit, candidate_sha="sha_target"))

        # Case B: Mismatched git_sha
        pkg_audit.write_text(json.dumps({"parity_audit_passed": True, "git_sha": "sha_target"}), encoding="utf-8")
        clean_audit.write_text(json.dumps({"status": "PASS", "git_sha": "sha_stale"}), encoding="utf-8")
        self.assertFalse(gen_qual.check_package_parity(pkg_audit, clean_audit, candidate_sha="sha_target"))

        # Case C: Exact match
        pkg_audit.write_text(json.dumps({"parity_audit_passed": True, "git_sha": "sha_target"}), encoding="utf-8")
        clean_audit.write_text(json.dumps({"status": "PASS", "git_sha": "sha_target"}), encoding="utf-8")
        self.assertTrue(gen_qual.check_package_parity(pkg_audit, clean_audit, candidate_sha="sha_target"))

    def test_uncommitted_working_tree_disallows_release(self):
        """Probe 6: An uncommitted working tree cannot qualify for release."""
        eligibility = gen_qual.derive_release_eligibility(
            mechanical_pass=True,
            no_blocking_frontiers=True,
            no_open_scars=True,
            tests_passed=True,
            git_sha="UNCOMMITTED_WORKING_TREE"
        )
        self.assertFalse(eligibility)


if __name__ == "__main__":
    unittest.main()
