import json
import tempfile
import unittest
from pathlib import Path

from kageyoni.situations.comparative import ComparativeLedger, CONDITIONS, METRICS
from kageyoni.situations.comparative_runner import (
    TASKS,
    TRIAL_METRICS,
    LAYER_CONTRIBUTIONS,
    run_comparative_suite,
    export_comparative_evidence,
)


class SituationR5ComparativeQualificationTests(unittest.TestCase):
    """Stage R5: Real Comparative Qualification.

    Executes 5-condition comparison (A/B/C/D/E) across 4 representative task domains:
    - creative (source-constrained production brief)
    - research (evidence-grounded inquiry)
    - technical (repository repair)
    - living_world (consequential story encounter)

    Enforces:
    - Complete evaluation of all 8 metrics without collapsing into a single score.
    - Negative and inconclusive finding preservation (e.g. A beats E on overhead).
    - Clear layer-by-layer contribution evidence.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.evidence_path = Path(self.temp_dir.name) / "r5_comparative_trials.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_all_tasks_have_complete_five_condition_evaluation(self):
        """Every task domain evaluates all conditions A, B, C, D, E."""
        ledger = run_comparative_suite()
        self.assertEqual(len(ledger.rows), len(TASKS) * len(CONDITIONS))
        for task in TASKS:
            with self.subTest(task=task):
                self.assertTrue(ledger.completeness(task), f"Task {task} incomplete across conditions")

    def test_all_eight_metrics_evaluated_without_aggregate_collapse(self):
        """Each trial includes all 8 metrics separately, without collapsing into a single score."""
        ledger = run_comparative_suite()
        for row in ledger.rows:
            with self.subTest(task=row.task_id, condition=row.condition):
                for m in METRICS:
                    self.assertIn(m, row.metrics, f"Missing metric {m} in {row.task_id}:{row.condition}")
                    self.assertIsNotNone(row.metrics[m], f"Metric {m} was None in {row.task_id}:{row.condition}")

    def test_preserves_negative_findings_and_tradeoffs(self):
        """Empirically records that Condition A beats Condition E on execution overhead."""
        ledger = run_comparative_suite()
        for task in TASKS:
            with self.subTest(task=task):
                rows = {r.condition: r.metrics for r in ledger.task(task)}
                # Condition A has 0 overhead, whereas Condition E has 4
                self.assertLess(rows["A"]["execution_overhead"], rows["E"]["execution_overhead"])
                # Condition E has zero reconstruction burden, whereas A has high reconstruction burden
                self.assertLess(rows["E"]["reconstruction_burden"], rows["A"]["reconstruction_burden"])
                # Condition E provides complete recovery and continuity
                self.assertEqual(rows["E"]["continuity"], 1)
                self.assertEqual(rows["E"]["recovery"], 1)
                self.assertEqual(rows["A"]["continuity"], 0)
                self.assertEqual(rows["A"]["recovery"], 0)

    def test_layer_by_layer_contributions_demonstrated(self):
        """Verifies each layer transition (A->B->C->D->E) provides demonstrable value."""
        ledger = run_comparative_suite()
        for task in TASKS:
            with self.subTest(task=task):
                rows = {r.condition: r.metrics for r in ledger.task(task)}
                # A -> B improves requirement satisfaction
                self.assertGreater(rows["B"]["requirement_satisfaction"], rows["A"]["requirement_satisfaction"])
                # B -> C adds recovery
                self.assertGreater(rows["C"]["recovery"], rows["B"]["recovery"])
                # C -> D adds continuity and removes reconstruction burden
                self.assertGreater(rows["D"]["continuity"], rows["C"]["continuity"])
                self.assertLess(rows["D"]["reconstruction_burden"], rows["C"]["reconstruction_burden"])
                # D -> E maximizes source fidelity and requirement satisfaction
                self.assertGreaterEqual(rows["E"]["source_fidelity"], rows["D"]["source_fidelity"])
                self.assertEqual(rows["E"]["requirement_satisfaction"], 1.0)

    def test_export_comparative_evidence_artifact(self):
        """Exports the complete empirical evidence artifact for Stage R5 handoff."""
        repo_evidence_path = Path("evidence/r5_comparative_trials.json")
        data = export_comparative_evidence(repo_evidence_path)
        self.assertTrue(repo_evidence_path.exists())
        self.assertEqual(data["summary"]["total_trials"], 20)
        self.assertEqual(len(data["summary"]["complete_tasks"]), 4)
        self.assertIn("tradeoff_conclusion", data["summary"])


if __name__ == "__main__":
    unittest.main()
