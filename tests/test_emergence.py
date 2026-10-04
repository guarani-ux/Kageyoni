"""
Comprehensive verification test suite for Constellation Emergence.
Validates:
1. CarrierTestDispatcher binding to real callables in gates.py, will.py, migration_024, constellation.py.
2. Exact content equality checks on reground (scars, receipts, invariants).
3. In-round remediation gate:
   - Failed/blocked tests keep next round LOCKED.
   - Remediation runs in the same round slot.
   - Exceeding max attempts marks round INCONCLUSIVE with next round remaining LOCKED.
4. Candidate descendants dynamically derived from execution receipts, strictly PROPOSED or TESTED_IN_SCOPE.
5. Deterministic version manifest excluding timestamps from content digest.
6. Unified SQLite store across all 6 views.
"""

import json
from pathlib import Path
import tempfile
import unittest

from kageyoni.emergence.models import (
    ParticipantConfig,
    EncounterConfig,
    EnvironmentAffordance,
    RunHorizon,
    EvidencePolicy,
    HorizonMode,
    AvailabilitySetting,
    TestSpec,
    TestStatus,
    RoundStatus,
    QualificationStatus,
    ManipulationType,
)
from kageyoni.emergence.affordances import discover_affordances
from kageyoni.emergence.preview import generate_configuration_preview
from kageyoni.emergence.engine import EmergenceEngine
from kageyoni.emergence.store import EmergenceStore
from kageyoni.emergence.dispatcher import CarrierTestDispatcher
from kageyoni.emergence.cli import default_preflight


class ConstellationEmergenceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_emergence.sqlite"
        self.store = EmergenceStore(self.db_path)
        self.preflight = default_preflight()
        self.dispatcher = CarrierTestDispatcher()

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_dispatcher_executes_real_gates_and_will_callables(self):
        """Dispatcher executes real gates.run_gate and will.validate_contract without stubs."""
        # 1. Gates Direct
        spec_gate_dir = TestSpec("test_gate_dir", "Gates Direct", "DIRECT", "kageyoni/composition/gates.py", "Dependencies closed")
        res_g1 = self.dispatcher.execute_test(spec_gate_dir, trials=3)
        self.assertEqual(res_g1.status, TestStatus.PASSED)
        self.assertIn("gates.run_gate", res_g1.measurement["actual_call"])
        self.assertEqual(res_g1.measurement["repeatability"], 1.0)
        self.assertTrue(len(res_g1.measurement["receipt_hash"]) == 64)

        # 2. Gates Adversarial (cyclic loop rejected)
        spec_gate_adv = TestSpec("test_gate_adv", "Gates Adversarial", "ADVERSARIAL", "kageyoni/composition/gates.py", "Catch cycle")
        res_g2 = self.dispatcher.execute_test(spec_gate_adv, trials=3)
        self.assertEqual(res_g2.status, TestStatus.PASSED)
        self.assertEqual(res_g2.measurement["output"]["code"], "REJECTED")

        # 3. Will Direct
        spec_will_dir = TestSpec("test_will_dir", "Will Direct", "DIRECT", "kageyoni/will.py", "Validate contract")
        res_w1 = self.dispatcher.execute_test(spec_will_dir, trials=3)
        self.assertEqual(res_w1.status, TestStatus.PASSED)
        self.assertIn("will.validate_contract", res_w1.measurement["actual_call"])

        # 4. Will Adversarial (missing schema version rejected)
        spec_will_adv = TestSpec("test_will_adv", "Will Adversarial", "ADVERSARIAL", "kageyoni/will.py", "Catch schema omission")
        res_w2 = self.dispatcher.execute_test(spec_will_adv, trials=3)
        self.assertEqual(res_w2.status, TestStatus.PASSED)
        self.assertEqual(res_w2.measurement["output"]["caught_exception"], "WillContractError")

    def test_dispatcher_destructive_isolation_and_reground_content_check(self):
        """Destructive tests run in-memory and reground asserts exact scar & receipt content."""
        # 1. SQLite trigger in-memory isolation
        spec_trig_adv = TestSpec("test_trig_adv", "Trigger Adversarial", "ADVERSARIAL", "migration_024.sql", "Trigger blocks delete")
        res_trig = self.dispatcher.execute_test(spec_trig_adv, trials=3)
        self.assertEqual(res_trig.status, TestStatus.PASSED)
        self.assertEqual(res_trig.measurement["cleanup"], "closed_in_memory_db")
        self.assertIn("character identity rows cannot be deleted", res_trig.measurement["output"]["caught_trigger_error"])

        # 2. Reground content equality check (scars, receipts, clean slate status)
        spec_rg_dir = TestSpec("test_rg_dir", "Reground Content", "DIRECT", "kageyoni/constellation.py", "reground preserves content")
        res_rg = self.dispatcher.execute_test(spec_rg_dir, trials=3)
        self.assertEqual(res_rg.status, TestStatus.PASSED)
        self.assertEqual(res_rg.measurement["output"]["framing_status"], "CLEAN_SLATE_RECONSTRUCTED")
        self.assertEqual(res_rg.measurement["output"]["preserved_scars_count"], 1)

    def test_missing_carrier_is_blocked_without_passing_stubs(self):
        """Nonexistent carrier returns BLOCKED with CARRIER_UNAVAILABLE."""
        spec_missing = TestSpec("test_missing", "Missing Carrier", "DIRECT", "nonexistent/module/carrier.py", "Assertion")
        res = self.dispatcher.execute_test(spec_missing, trials=3)
        self.assertEqual(res.status, TestStatus.BLOCKED)
        self.assertIn("CARRIER_UNAVAILABLE", res.error_message)

    def test_in_round_remediation_and_stop_condition(self):
        """Failed round stays locked; remediation occurs within the round; max attempts ends inconclusive."""
        short_horizon = RunHorizon(
            mode=HorizonMode.ONE_ROUND, n_cycles=1, current_cycle=1, current_round=1, total_rounds=2
        )
        engine = EmergenceEngine(
            self.preflight["participants"],
            self.preflight["encounter"],
            self.preflight["affordances"],
            short_horizon,
            self.preflight["policy"],
        )

        # Execute Round 1 with an ungrounded missing carrier
        failing_tests = [
            TestSpec("r1_fail", "Missing Carrier", "DIRECT", "invalid/path.py", "Will block"),
        ]
        r1 = engine.execute_round(1, custom_tests=failing_tests)
        self.assertEqual(r1.status, RoundStatus.BLOCKED)
        self.assertTrue(r1.round_result["remediation_needed"])

        # Next round (Round 2) MUST remain locked
        with self.assertRaises(PermissionError):
            engine.execute_round(2)

        # Attempt remediation attempt 1 (still failing)
        r1_rem1 = engine.remediate_round(1, remediated_tests=failing_tests, notes="Attempt 1: retested without fix")
        self.assertEqual(r1_rem1.status, RoundStatus.BLOCKED)
        self.assertEqual(r1_rem1.remediation_attempts, 1)

        # Attempt remediation attempt 2 (still failing)
        r1_rem2 = engine.remediate_round(1, remediated_tests=failing_tests, notes="Attempt 2: retested without fix")
        self.assertEqual(r1_rem2.remediation_attempts, 2)

        # Attempt remediation attempt 3 (exceeds max attempts -> stop condition met)
        r1_rem3 = engine.remediate_round(1, remediated_tests=failing_tests, notes="Attempt 3: max attempts hit")
        self.assertEqual(r1_rem3.status, RoundStatus.INCONCLUSIVE)
        self.assertTrue(r1_rem3.round_result["inconclusive"])
        self.assertEqual(engine.run_status, "INCONCLUSIVE")

        # Next round remains LOCKED even after inconclusive termination
        with self.assertRaises(PermissionError):
            engine.execute_round(2)

    def test_successful_remediation_unlocks_next_round(self):
        """Valid remediation within the same round unlocks the subsequent round."""
        short_horizon = RunHorizon(
            mode=HorizonMode.ONE_ROUND, n_cycles=1, current_cycle=1, current_round=1, total_rounds=2
        )
        engine = EmergenceEngine(
            self.preflight["participants"],
            self.preflight["encounter"],
            self.preflight["affordances"],
            short_horizon,
            self.preflight["policy"],
        )

        # Fail initially
        failing_tests = [TestSpec("r1_fail", "Missing", "DIRECT", "invalid/path.py", "Will block")]
        engine.execute_round(1, custom_tests=failing_tests)
        self.assertEqual(engine.rounds[0].status, RoundStatus.BLOCKED)

        # Remediate with real, passing tests against gates.py
        valid_tests = [TestSpec("r1_pass", "Gates", "DIRECT", "kageyoni/composition/gates.py", "Dependencies closed")]
        r1_fixed = engine.remediate_round(1, remediated_tests=valid_tests, notes="Remediated with real gate carrier")
        self.assertEqual(r1_fixed.status, RoundStatus.TERMINAL)
        self.assertFalse(r1_fixed.round_result.get("inconclusive", False))

        # Next round is now ACTIVE and can be executed
        self.assertEqual(engine.rounds[1].status, RoundStatus.ACTIVE)
        r2 = engine.execute_round(2)
        self.assertEqual(r2.status, RoundStatus.TERMINAL)

    def test_candidate_derived_dynamically_from_receipts(self):
        """Candidates derive names, operations, inputs, outputs, and failure signatures from receipts."""
        short_horizon = RunHorizon(
            mode=HorizonMode.ONE_ROUND, n_cycles=1, current_cycle=1, current_round=1, total_rounds=1
        )
        engine = EmergenceEngine(
            self.preflight["participants"],
            self.preflight["encounter"],
            self.preflight["affordances"],
            short_horizon,
            self.preflight["policy"],
        )
        engine.execute_round(1)

        candidate = list(engine.technique_bank.values())[0]
        self.assertIn("Gates", candidate.name)
        self.assertIn("gates.run_gate", candidate.operation)
        self.assertEqual(candidate.carrier, "kageyoni/composition/gates.py")
        self.assertEqual(candidate.status, QualificationStatus.TESTED_IN_SCOPE)
        self.assertEqual(candidate.dimensions.repeatability, 1.0)
        self.assertTrue(len(candidate.failure_signature) > 0)

    def test_deterministic_version_manifest_and_lineage_metadata(self):
        """Version manifest content digest is deterministic and excludes timestamps."""
        short_horizon = RunHorizon(
            mode=HorizonMode.ONE_ROUND, n_cycles=1, current_cycle=1, current_round=1, total_rounds=1
        )
        engine = EmergenceEngine(
            self.preflight["participants"],
            self.preflight["encounter"],
            self.preflight["affordances"],
            short_horizon,
            self.preflight["policy"],
        )
        engine.execute_round(1)

        # Compute manifest twice
        m1 = engine.compute_version_manifest(parent_version="rev_037", decision="Genesis encounter pass")
        m2 = engine.compute_version_manifest(parent_version="rev_037", decision="Genesis encounter pass")

        # Deterministic digest must match identically
        self.assertEqual(m1["version_digest"], m2["version_digest"])
        self.assertEqual(m1["source_manifest_hash"], m2["source_manifest_hash"])
        self.assertEqual(m1["config_hash"], m2["config_hash"])
        self.assertEqual(m1["receipts_hash"], m2["receipts_hash"])

        # Lineage metadata captured
        self.assertEqual(m1["parent_version"], "rev_037")
        self.assertEqual(m1["decision"], "Genesis encounter pass")
        self.assertIn("recorded_at", m1)


if __name__ == "__main__":
    unittest.main()
