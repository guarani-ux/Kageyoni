import json
import tempfile
import unittest
from pathlib import Path

from kageyoni.situations.memory import SituationMemory, SituationMemoryStore
from kageyoni.situations.long_horizon import (
    run_horizon_trial,
    run_multi_turn_trajectory,
    export_long_horizon_evidence,
)


class SituationR6LongHorizonQualificationTests(unittest.TestCase):
    """Stage R6: Long-Horizon Development Trials Qualification.

    Validates repeated trajectories across:
    1. Living World / Story
    2. Research / Planning
    3. Creative / Production
    4. Repository / Technical

    Enforces the invariant:
    stored history != retrieved history != changed reasoning != changed capability != changed outcome
    """

    def setUp(self):
        self.store = SituationMemoryStore()

    def test_four_repeated_developmental_trajectories_distinguish_levels(self):
        """All 4 domains distinguish stored history, retrieved history, reasoning, capability, and outcome."""
        trajectories = [
            ("story", "living_world", "living_world", "relationship:promise"),
            ("research", "research", "research", "claim:source-gap"),
            ("production", "creative", "production_brief", "audience:ambiguity"),
            ("technical", "repository", "repository_repair", "failure:replay"),
        ]
        for t_id, domain, tmpl, key in trajectories:
            with self.subTest(trajectory=t_id):
                ledger = run_multi_turn_trajectory(self.store, t_id, domain, tmpl, key)
                self.assertEqual(len(ledger.encounters), 3)

                # Encounter 1: Empty prior retrieval, baseline decision
                e1 = ledger.encounters[0]
                self.assertEqual(len(e1.retrieved_memory_ids), 0)
                self.assertEqual(e1.decision, "baseline_approach")
                self.assertIsNone(e1.capability_exercised)

                # Encounter 2: Retrieved E1 memory, changed reasoning, but NO new capability
                e2 = ledger.encounters[1]
                self.assertGreater(len(e2.retrieved_memory_ids), 0)
                self.assertNotEqual(e2.decision, e1.decision)
                self.assertIsNone(e2.capability_exercised)

                # Encounter 3: Exercised verified engine capability, resulting in changed outcome
                e3 = ledger.encounters[2]
                self.assertIsNotNone(e3.capability_exercised)
                self.assertEqual(e3.outcome_observed, "verified_changed_outcome")

                # Verify all distinctions are explicitly captured
                d = ledger.distinctions
                self.assertTrue(d["stored_history"])
                self.assertTrue(d["retrieved_history"])
                self.assertTrue(d["changed_reasoning"])
                self.assertTrue(d["changed_capability"])
                self.assertTrue(d["changed_outcome"])

                # Verify unqualified claims are preserved
                self.assertGreaterEqual(len(ledger.unqualified_claims), 2)

    def test_storage_alone_does_not_claim_development(self):
        """Storing memories without retrieval or execution does not alter capability or outcome."""
        obs = run_horizon_trial(self.store, "control", "research", "topic:unrelated")
        self.assertTrue(obs.stored_history)
        self.assertFalse(obs.changed_capability)
        self.assertFalse(obs.changed_outcome)

    def test_export_long_horizon_evidence_package(self):
        """Exports the complete empirical evidence artifact for Stage R6 handoff."""
        repo_evidence_path = Path("evidence/r6_long_horizon_trials.json")
        data = export_long_horizon_evidence(repo_evidence_path)
        self.assertTrue(repo_evidence_path.exists())
        self.assertEqual(data["summary"]["total_trajectories"], 4)
        self.assertEqual(data["summary"]["total_encounters_analyzed"], 12)
        self.assertTrue(data["summary"]["verified_development"])


if __name__ == "__main__":
    unittest.main()
