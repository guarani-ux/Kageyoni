"""
tests/test_slice5_bounded_adaptation.py
Adversarial Verification for Slice 5: Bounded Adaptive Action Without Daemon Theater.
"""

from __future__ import annotations
import shutil
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine
from kageyoni.resources import campaign_db_path
from kageyoni.persistence.migrations import install_all
from kageyoni.v11.adaptive import AdaptiveLoop, AdaptiveBudgetExceededError
from kageyoni.v11.runtime import ProtectedOperations


class Slice5BoundedAdaptationTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "db.sqlite"
        shutil.copy2(campaign_db_path(), self.db_path)
        self.engine = Engine(self.db_path)
        install_all(self.engine)
        self.loop = AdaptiveLoop(self.engine)
        self.ops = ProtectedOperations(self.engine)

    def tearDown(self):
        self.engine.close()
        self.temp_dir.cleanup()

    def test_bounded_pass_executes_and_emits_grounded_receipts(self):
        """Verifies bounded pass executes discrete steps and records verifiable execution receipts in SQLite."""
        op_info = self.loop.begin(
            objective="Adaptive calibration pass",
            requirement_version="calib-r1",
            scope="technical",
            basis={"branch": "main"},
            included=["config"],
        )
        oid = op_info["operation"]["operation_id"]

        steps = [
            lambda op: {"telemetry_probe": 42},
            lambda op: {"threshold_adjusted": 0.85},
        ]

        result = self.loop.execute_bounded_pass(oid, steps, max_steps=5, max_retries=2)
        self.assertEqual(result["steps_executed"], 2)
        self.assertEqual(len(result["receipts"]), 2)

        # Verify physical rows in v11_execution_receipts
        cur = self.engine.db.execute(
            "SELECT receipt_id, evidence_type, evidence_ref FROM v11_execution_receipts WHERE operation_id=?",
            (oid,)
        )
        rows = cur.fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1], "adaptive-step")
        self.assertEqual(rows[0][2], "adaptive:step:0")
        self.assertEqual(rows[1][1], "adaptive-step")
        self.assertEqual(rows[1][2], "adaptive:step:1")

    def test_step_budget_ceiling_enforced(self):
        """Verifies that exceeding max_steps ceiling raises AdaptiveBudgetExceededError without infinite loops."""
        op_info = self.loop.begin(
            objective="Infinite loop simulation",
            requirement_version="calib-r1",
            scope="technical",
            basis={"branch": "main"},
            included=["config"],
        )
        oid = op_info["operation"]["operation_id"]

        # 4 steps provided, but budget is 2
        steps = [lambda op: i for i in range(4)]

        with self.assertRaises(AdaptiveBudgetExceededError) as ctx:
            self.loop.execute_bounded_pass(oid, steps, max_steps=2)
        self.assertIn("Step budget ceiling of 2 reached", str(ctx.exception))

    def test_retry_budget_ceiling_enforced(self):
        """Verifies that repeatedly failing steps hit retry ceiling and fail fast."""
        op_info = self.loop.begin(
            objective="Failing step simulation",
            requirement_version="calib-r1",
            scope="technical",
            basis={"branch": "main"},
            included=["config"],
        )
        oid = op_info["operation"]["operation_id"]

        def failing_step(op):
            raise ValueError("Probe timeout")

        with self.assertRaises(AdaptiveBudgetExceededError) as ctx:
            self.loop.execute_bounded_pass(oid, [failing_step], max_retries=2)
        self.assertIn("Retry budget ceiling of 2 exceeded", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
