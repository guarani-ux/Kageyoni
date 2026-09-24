"""
tests/test_slice6_experience_scar_writeback.py
Adversarial Verification for Slice 6: Experience and Scar Write-Back.
"""

from __future__ import annotations
import sqlite3
import unittest

from kageyoni.situations.catalog import install_defaults
from kageyoni.situations.models import SituationTemplate
from kageyoni.situations.runtime import SituationRuntime, WorkflowRun
from kageyoni.situations.scar import Scar, ScarLedger, close_scar
from kageyoni.situations.service import SituationService, SituationError
from kageyoni.situations.storage import SQLiteSituationStore


class Slice6ExperienceScarWritebackTests(unittest.TestCase):

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE situation_records(kind TEXT, record_key TEXT, payload_json TEXT, PRIMARY KEY(kind, record_key))")
        self.store = SQLiteSituationStore(self.conn)
        self.service = install_defaults(SituationService(self.store))
        self.runtime = SituationRuntime(self.service, test_mode=True)
        self.scar_ledger = ScarLedger(self.store)

    def tearDown(self):
        self.conn.close()

    def test_failure_writes_back_open_scar(self):
        """Verifies runtime.fail persists an immutable open scar record with root cause and affected scope."""
        sit = self.service.genesis("research", "Investigate bounds", {"question": "Why bounds?"})
        run = WorkflowRun("run_01", sit.situation_id, "research.default", authority=("research_auth",))
        self.service.bind_workflow(sit.situation_id, "research.default")
        self.runtime.start(run)

        scar = self.runtime.fail(
            "run_01",
            "Data corruption in external telemetry",
            failure_class="data_corruption",
            trigger_condition="latency > 500ms",
        )
        self.assertEqual(scar.status, "open")
        self.assertEqual(scar.failure_class, "data_corruption")
        self.assertEqual(scar.root_cause, "Data corruption in external telemetry")
        self.assertIn("research_auth", scar.affected_scopes)

        # Verify scar is readable from SQLiteSituationStore
        retrieved_scar = self.store.get("scar", scar.scar_id)
        self.assertEqual(retrieved_scar.status, "open")
        self.assertEqual(retrieved_scar.failure_class, "data_corruption")

    def test_negative_constraint_blocks_repeating_failed_pattern(self):
        """Verifies active open scar mechanically blocks starting another run with the same authority."""
        sit = self.service.genesis("research", "Investigate bounds", {"question": "Why bounds?"})
        self.service.bind_workflow(sit.situation_id, "research.default")

        # Create an open scar affecting 'vulnerable_scope'
        scar = Scar(
            scar_id="scar:scope:blocked",
            failure_class="privilege_leak",
            root_cause="Leaked scope token",
            probe_refs=("probe:01",),
            affected_scopes=("vulnerable_scope",),
            status="open",
        )
        self.scar_ledger.record_scar(scar)

        # Attempt to start a run requesting 'vulnerable_scope'
        blocked_run = WorkflowRun("run_blocked", sit.situation_id, "research.default", authority=("vulnerable_scope",))
        with self.assertRaises(SituationError) as ctx:
            self.runtime.start(blocked_run)
        self.assertIn("NEGATIVE_CONSTRAINT_VIOLATION", str(ctx.exception))

    def test_scar_closes_only_with_reprobe_and_positive_control(self):
        """Verifies scar transitions to closed only when repair_ref, reprobe, and positive control are satisfied."""
        scar = Scar(
            scar_id="scar:test:gate",
            failure_class="regression_defect",
            root_cause="Missing bounds check",
            probe_refs=("probe:regression",),
            status="open",
        )
        self.scar_ledger.record_scar(scar)

        # Attempt close without repair_ref -> stays open
        s1 = close_scar(scar, reprobe_passed=True, positive_control_passed=True)
        self.assertEqual(s1.status, "open")

        # With repair_ref, but reprobe failed -> stays open
        repaired = Scar(**{**scar.__dict__, "repair_ref": "git:abc1234"})
        s2 = close_scar(repaired, reprobe_passed=False, positive_control_passed=True)
        self.assertEqual(s2.status, "open")

        # Reprobe passed, but positive control failed -> stays open
        s3 = close_scar(repaired, reprobe_passed=True, positive_control_passed=False)
        self.assertEqual(s3.status, "open")

        # Both passed -> closed
        s4 = close_scar(repaired, reprobe_passed=True, positive_control_passed=True)
        self.assertEqual(s4.status, "closed")

    def test_successful_workflow_writes_back_experience_memory(self):
        """Verifies runtime.complete_workflow writes back persistent SituationMemory."""
        sit = self.service.genesis("research", "Successful research", {"question": "Is it valid?"})
        self.service.bind_workflow(sit.situation_id, "research.default")
        run = WorkflowRun("run_success", sit.situation_id, "research.default")
        self.runtime.start(run)

        mem = self.runtime.complete_workflow("run_success", outcome_refs=("event:synthesis_complete",))
        self.assertEqual(mem.situation_id, sit.situation_id)
        self.assertEqual(mem.template_id, "research")
        self.assertIn("event:synthesis_complete", mem.outcome_refs)

        # Verify memory is persisted in store
        retrieved_mem = self.store.get("memory", mem.memory_id)
        self.assertEqual(retrieved_mem.memory_id, mem.memory_id)
        self.assertEqual(retrieved_mem.objective, "Successful research")


if __name__ == "__main__":
    unittest.main()
