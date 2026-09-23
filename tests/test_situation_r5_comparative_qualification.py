import json
import tempfile
import unittest
from pathlib import Path

from kageyoni.situations.comparative import ComparativeLedger, ComparativeObservation, CONDITIONS, METRICS
from kageyoni.situations.comparative_runner import (
    TASKS,
    TrialResult,
    run_comparative_suite,
    export_comparative_evidence,
    validate_trial,
)


def _make_mock_executor():
    """Deterministic test executor for verifying harness mechanics."""
    def executor(task_id: str, condition: str) -> TrialResult:
        metrics = {
            "requirement_satisfaction": 0.5 if condition == "A" else 1.0,
            "source_fidelity": 0.5 if condition in ("A", "B") else 1.0,
            "continuity": 1 if condition in ("D", "E") else 0,
            "useful_novelty": 0.5,
            "correction_burden": 3 if condition == "A" else 0,
            "reconstruction_burden": 2 if condition in ("A", "B") else 0,
            "execution_overhead": {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}[condition],
            "recovery": 1 if condition in ("C", "D", "E") else 0,
        }
        return TrialResult(
            task_id=task_id,
            condition=condition,
            metrics=metrics,
            evidence_refs=(f"test-evidence:{task_id}:{condition}",),
            serious_failure=None,
        )
    return executor


class SituationR5ComparativeQualificationTests(unittest.TestCase):
    """Stage R5: Real Comparative Qualification.

    Enforces:
    - R5 cannot self-certify without an explicit external task executor.
    - Exporting evidence without an executor raises RuntimeError.
    - Complete evaluation of all 8 metrics across all tasks/conditions when an executor is supplied.
    - Negative and inconclusive finding preservation (e.g. A beats E on overhead).
    - Validation rejection for malformed or evidenceless trial results.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.evidence_path = Path(self.temp_dir.name) / "r5_comparative_trials.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_r5_cannot_self_certify_without_executor(self):
        """Calling run_comparative_suite without an executor fails closed."""
        with self.assertRaises(RuntimeError) as ctx:
            run_comparative_suite(None)
        self.assertIn("R5 is unqualified until an external/real task executor is supplied", str(ctx.exception))

    def test_r5_export_cannot_self_certify_without_executor(self):
        """Calling export_comparative_evidence without an executor fails closed."""
        with self.assertRaises(RuntimeError) as ctx:
            export_comparative_evidence(self.evidence_path, None)
        self.assertIn("R5 is unqualified until an external/real task executor is supplied", str(ctx.exception))

    def test_all_tasks_have_complete_five_condition_evaluation(self):
        """Every task domain evaluates all conditions A, B, C, D, E via executor."""
        executor = _make_mock_executor()
        ledger = run_comparative_suite(executor)
        self.assertEqual(len(ledger.rows), len(TASKS) * len(CONDITIONS))
        for task in TASKS:
            with self.subTest(task=task):
                self.assertTrue(ledger.completeness(task), f"Task {task} incomplete across conditions")

    def test_all_eight_metrics_evaluated_without_aggregate_collapse(self):
        """Each trial includes all 8 metrics separately, without collapsing into a single score."""
        executor = _make_mock_executor()
        ledger = run_comparative_suite(executor)
        for row in ledger.rows:
            with self.subTest(task=row.task_id, condition=row.condition):
                for m in METRICS:
                    self.assertIn(m, row.metrics, f"Missing metric {m} in {row.task_id}:{row.condition}")
                    self.assertIsNotNone(row.metrics[m], f"Metric {m} was None in {row.task_id}:{row.condition}")

    def test_preserves_negative_findings_and_tradeoffs(self):
        """Empirically records that Condition A beats Condition E on execution overhead."""
        executor = _make_mock_executor()
        ledger = run_comparative_suite(executor)
        for task in TASKS:
            with self.subTest(task=task):
                rows = {r.condition: r.metrics for r in ledger.task(task)}
                self.assertLess(rows["A"]["execution_overhead"], rows["E"]["execution_overhead"])
                self.assertLess(rows["E"]["reconstruction_burden"], rows["A"]["reconstruction_burden"])

    def test_validate_trial_requires_evidence_refs_and_known_domain(self):
        """Validates that malformed trials are rejected immediately."""
        bad_task = TrialResult("unknown_domain", "A", {m: 1 for m in METRICS}, ("ev-1",))
        with self.assertRaises(ValueError):
            validate_trial(bad_task)

        bad_condition = TrialResult("creative", "Z", {m: 1 for m in METRICS}, ("ev-1",))
        with self.assertRaises(ValueError):
            validate_trial(bad_condition)

        missing_metrics = TrialResult("creative", "A", {"continuity": 1}, ("ev-1",))
        with self.assertRaises(ValueError):
            validate_trial(missing_metrics)

        missing_evidence = TrialResult("creative", "A", {m: 1 for m in METRICS}, ())
        with self.assertRaises(ValueError):
            validate_trial(missing_evidence)

    def test_export_comparative_evidence_artifact(self):
        """Exports the complete evidence artifact when executor is supplied."""
        executor = _make_mock_executor()
        data = export_comparative_evidence(self.evidence_path, executor)
        self.assertTrue(self.evidence_path.exists())
        self.assertEqual(data["summary"]["total_trials"], 20)
        self.assertEqual(len(data["summary"]["complete_tasks"]), 4)


if __name__ == "__main__":
    unittest.main()
