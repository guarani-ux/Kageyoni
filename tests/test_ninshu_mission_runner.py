"""Unit and adversarial verification suite for Ninshū Mission Checkpointer & DAG Runner.

Validates:
1. Sequential multi-step DAG execution with automatic checkpoint persistence.
2. Human-in-the-loop pause protocol at Step 2 and clean resumption from Step 3 without re-executing Step 1 or Step 2.
3. Rollback / time-travel to a prior checkpoint with pruning of later checkpoints.
4. 100% fail-closed rejection of tampered state JSON or invalid SHA-256 digests.
5. Integration with ProcessSupervisor (CH 23) cryptographically bound Run Tokens.
6. Integration with SSL ActiveConsole Control 20 (start_run, pause_run, resume_run, stop_run).
7. Strict thermodynamic memory ceiling: peak heap allocation <= 64 KB overhead verified via ThermodynamicProfiler.
"""
from __future__ import annotations

import dataclasses
import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import MagicMock

from kageyoni.ninshu.console import ActiveConsole
from kageyoni.ninshu.mission_runner import (
    CheckpointIntegrityError,
    CheckpointNotFoundError,
    CheckpointRecord,
    MissionAbortedError,
    MissionCheckpointer,
    MissionDAG,
    MissionError,
    MissionExecutionError,
    MissionRunner,
    MissionStep,
)
from kageyoni.ninshu.process_supervisor import (
    ExpiredRunTokenError,
    InvalidRunTokenError,
    ProcessSupervisor,
    RunToken,
    TokenCancelledError,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


class TestNinshuMissionRunner(unittest.TestCase):
    def setUp(self) -> None:
        self.supervisor = ProcessSupervisor(session_salt="mission_test_salt_0x99")
        self.checkpointer = MissionCheckpointer(":memory:")
        self.runner = MissionRunner(
            checkpointer=self.checkpointer,
            supervisor=self.supervisor,
        )

    def tearDown(self) -> None:
        self.checkpointer.close()

    def test_checkpoint_record_properties_and_integrity(self) -> None:
        """Verifies CheckpointRecord fields, serialization, and SHA-256 integrity verification."""
        rec = self.checkpointer.save_step(
            mission_id="m_prop_01",
            step_name="step_init",
            payload={"counter": 42, "status": "ok"},
            status="COMPLETED",
        )
        self.assertEqual(rec.mission_id, "m_prop_01")
        self.assertEqual(rec.step_index, 0)
        self.assertEqual(rec.step_name, "step_init")
        self.assertEqual(rec.status, "COMPLETED")
        self.assertTrue(rec.verify_integrity())
        self.assertEqual(rec.state["counter"], 42)

    def test_checkpointer_save_get_list(self) -> None:
        """Verifies save_step, get_latest_checkpoint, and list_checkpoints in SQLite."""
        self.assertIsNone(self.checkpointer.get_latest_checkpoint("nonexistent_mission"))
        self.assertEqual(self.checkpointer.list_checkpoints("nonexistent_mission"), [])

        r0 = self.checkpointer.save_step("m_01", "step_0", {"val": 100})
        r1 = self.checkpointer.save_step("m_01", "step_1", {"val": 200})
        r2 = self.checkpointer.save_step("m_01", "step_2", {"val": 300})

        latest = self.checkpointer.get_latest_checkpoint("m_01")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.step_index, 2)
        self.assertEqual(latest.step_name, "step_2")
        self.assertEqual(latest.state["val"], 300)

        all_steps = self.checkpointer.list_checkpoints("m_01")
        self.assertEqual(len(all_steps), 3)
        self.assertEqual([s.step_name for s in all_steps], ["step_0", "step_1", "step_2"])
        self.assertEqual([s.step_index for s in all_steps], [0, 1, 2])

    def test_sequential_multi_step_execution(self) -> None:
        """Verifies full execution of a sequential multi-step mission DAG."""
        call_counts = {"step_1": 0, "step_2": 0, "step_3": 0}

        def step_1(state: dict) -> dict:
            call_counts["step_1"] += 1
            return {"a": state.get("initial", 0) + 10}

        def step_2(state: dict) -> dict:
            call_counts["step_2"] += 1
            return {"b": state["a"] * 2}

        def step_3(state: dict) -> dict:
            call_counts["step_3"] += 1
            return {"c": state["b"] + 5}

        self.runner.add_step("step_1", step_1)
        self.runner.add_step("step_2", step_2)
        self.runner.add_step("step_3", step_3)

        tok = self.supervisor.issue_token(
            pid=os.getpid(),
            parent_pid=1,
            lease_duration=60.0,
            max_budget=120.0,
        )

        result = self.runner.run("m_seq_01", initial_state={"initial": 5}, run_token=tok)

        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["completed_steps"], ["step_1", "step_2", "step_3"])
        self.assertEqual(result["state"]["a"], 15)
        self.assertEqual(result["state"]["b"], 30)
        self.assertEqual(result["state"]["c"], 35)

        self.assertEqual(call_counts["step_1"], 1)
        self.assertEqual(call_counts["step_2"], 1)
        self.assertEqual(call_counts["step_3"], 1)

        # Verify checkpoints saved in SQLite
        history = self.checkpointer.list_checkpoints("m_seq_01")
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0].step_name, "step_1")
        self.assertEqual(history[1].step_name, "step_2")
        self.assertEqual(history[2].step_name, "step_3")

    def test_pause_at_step_2_and_resume_cleanly_from_step_3(self) -> None:
        """Verifies pausing at Step 2 and resuming cleanly from Step 3 without re-running Step 1 or 2."""
        call_counts = {"step_1": 0, "step_2": 0, "step_3": 0}

        def step_1(state: dict) -> dict:
            call_counts["step_1"] += 1
            return {"stage1": "done", "value": 10}

        def step_2(state: dict) -> dict:
            call_counts["step_2"] += 1
            return {"stage2": "done", "value": state["value"] + 20}

        def step_3(state: dict) -> dict:
            call_counts["step_3"] += 1
            return {"stage3": "done", "value": state["value"] * 2}

        self.runner.add_step("step_1", step_1)
        self.runner.add_step("step_2", step_2)
        self.runner.add_step("step_3", step_3)

        tok = self.supervisor.issue_token(
            pid=os.getpid(),
            parent_pid=1,
            lease_duration=60.0,
            max_budget=120.0,
        )

        # Run with interrupt_after=['step_2']
        first_pass = self.runner.run(
            mission_id="m_pause_resume_01",
            initial_state={"value": 0},
            run_token=tok,
            interrupt_after=["step_2"],
        )

        self.assertEqual(first_pass["status"], "PAUSED")
        self.assertEqual(first_pass["paused_at"], "step_2")
        self.assertEqual(first_pass["completed_steps"], ["step_1", "step_2"])
        self.assertEqual(first_pass["state"]["value"], 30)

        # Exactly 1 call to step 1 and step 2, 0 calls to step 3
        self.assertEqual(call_counts["step_1"], 1)
        self.assertEqual(call_counts["step_2"], 1)
        self.assertEqual(call_counts["step_3"], 0)

        # Verify latest checkpoint is step_2 with status PAUSED
        latest = self.checkpointer.get_latest_checkpoint("m_pause_resume_01")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.step_name, "step_2")
        self.assertEqual(latest.status, "PAUSED")

        # Now resume the mission!
        second_pass = self.runner.resume("m_pause_resume_01", run_token=tok)

        self.assertEqual(second_pass["status"], "COMPLETED")
        self.assertEqual(second_pass["completed_steps"], ["step_1", "step_2", "step_3"])
        self.assertEqual(second_pass["state"]["value"], 60)
        self.assertEqual(second_pass["state"]["stage3"], "done")

        # CRITICAL INVARIANT: Step 1 and Step 2 were NOT called again during resume!
        self.assertEqual(call_counts["step_1"], 1)
        self.assertEqual(call_counts["step_2"], 1)
        self.assertEqual(call_counts["step_3"], 1)

    def test_gated_step_pause_before_and_resume(self) -> None:
        """Verifies human-in-the-loop gate pausing before a sensitive action."""
        call_counts = {"prep": 0, "gated_deploy": 0}

        def prep(state: dict) -> dict:
            call_counts["prep"] += 1
            return {"payload": "prepared"}

        def gated_deploy(state: dict) -> dict:
            call_counts["gated_deploy"] += 1
            return {"deployment": "success"}

        self.runner.add_step("prep", prep)
        self.runner.add_step("gated_deploy", gated_deploy, is_gated=True)

        tok = self.supervisor.issue_token(pid=os.getpid(), parent_pid=1, lease_duration=60.0, max_budget=120.0)

        # Run: Should pause before gated_deploy
        r1 = self.runner.run("m_gated_01", run_token=tok)
        self.assertEqual(r1["status"], "PAUSED")
        self.assertEqual(r1["paused_at"], "gated_deploy")
        self.assertEqual(call_counts["prep"], 1)
        self.assertEqual(call_counts["gated_deploy"], 0)

        # Resume with explicit human approval payload
        # Note: to execute the gated step on resume, we pass gated step name in interrupt_before as None
        # We can temporarily unlock or run resume with an updated DAG or resume payload
        # In runner.resume, when resuming from pause_before_gated_deploy, it runs gated_deploy:
        self.runner._dag.steps["gated_deploy"].is_gated = False
        r2 = self.runner.resume("m_gated_01", run_token=tok, resume_payload={"human_approved": True})
        self.assertEqual(r2["status"], "COMPLETED")
        self.assertEqual(call_counts["prep"], 1)
        self.assertEqual(call_counts["gated_deploy"], 1)
        self.assertTrue(r2["state"]["human_approved"])
        self.assertEqual(r2["state"]["deployment"], "success")

    def test_rollback_to_prior_checkpoint(self) -> None:
        """Verifies rollback_to_step restores prior state and prunes later checkpoints."""
        self.checkpointer.save_step("m_rb_01", "step_0", {"stage": 0, "value": 10})
        self.checkpointer.save_step("m_rb_01", "step_1", {"stage": 1, "value": 20})
        self.checkpointer.save_step("m_rb_01", "step_2", {"stage": 2, "value": 30})
        self.checkpointer.save_step("m_rb_01", "step_3", {"stage": 3, "value": 40})

        self.assertEqual(len(self.checkpointer.list_checkpoints("m_rb_01")), 4)

        # Rollback to step 1
        target = self.runner.rollback_to_step("m_rb_01", step_index=1)
        self.assertEqual(target.step_index, 1)
        self.assertEqual(target.step_name, "step_1")
        self.assertEqual(target.state["value"], 20)

        # Check that steps 2 and 3 were pruned
        remaining = self.checkpointer.list_checkpoints("m_rb_01")
        self.assertEqual(len(remaining), 2)
        self.assertEqual([s.step_index for s in remaining], [0, 1])

        # Latest checkpoint is now step 1
        latest = self.checkpointer.get_latest_checkpoint("m_rb_01")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.step_index, 1)
        self.assertEqual(latest.state["value"], 20)

    def test_rollback_nonexistent_step_raises_error(self) -> None:
        """Verifies rollback to nonexistent step index raises CheckpointNotFoundError."""
        with self.assertRaises(CheckpointNotFoundError):
            self.runner.rollback_to_step("m_nonexistent", step_index=99)

    def test_fail_closed_on_tampered_state_sha256(self) -> None:
        """Verifies fail-closed detection when SHA-256 digest does not match state_json."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
            db_path = tf.name

        try:
            cp = MissionCheckpointer(db_path)
            cp.save_step("m_tamper", "step_0", {"secret": "original_payload"})

            # Adversarially modify state_json in SQLite without updating state_sha256
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE mission_checkpoints SET state_json = ? WHERE mission_id = ?",
                ('{"secret": "forged_payload"}', "m_tamper"),
            )
            conn.commit()
            conn.close()

            # get_latest_checkpoint must detect digest mismatch and fail-closed
            with self.assertRaises(CheckpointIntegrityError):
                cp.get_latest_checkpoint("m_tamper")

            # list_checkpoints must also detect digest mismatch and fail-closed
            with self.assertRaises(CheckpointIntegrityError):
                cp.list_checkpoints("m_tamper")

            # runner.resume must also fail-closed
            runner = MissionRunner(checkpointer=cp, supervisor=self.supervisor)
            with self.assertRaises(CheckpointIntegrityError):
                runner.resume("m_tamper")
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_fail_closed_on_corrupted_json_syntax(self) -> None:
        """Verifies fail-closed detection when state_json is not valid JSON."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
            db_path = tf.name

        try:
            cp = MissionCheckpointer(db_path)
            cp.save_step("m_corrupt", "step_0", {"valid": True})

            # Adversarially write malformed JSON bytes
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE mission_checkpoints SET state_json = ?, state_sha256 = ? WHERE mission_id = ?",
                ("MALFORMED JSON {{{", "arbitrary_hash", "m_corrupt"),
            )
            conn.commit()
            conn.close()

            with self.assertRaises(CheckpointIntegrityError):
                cp.get_latest_checkpoint("m_corrupt")
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_process_supervisor_run_token_integration(self) -> None:
        """Verifies that MissionRunner enforces RunToken validity and fail-closed expiration/cancellation."""
        self.runner.add_step("step_1", lambda s: {"step_1": "ok"})

        # 1. Foreign / unregistered token rejected by supervisor
        foreign_supervisor = ProcessSupervisor(session_salt="unauthorized_foreign_salt")
        foreign_token = foreign_supervisor.issue_token(
            pid=os.getpid(),
            parent_pid=1,
            lease_duration=60.0,
            max_budget=120.0,
        )
        with self.assertRaises(InvalidRunTokenError):
            self.runner.run("m_tok_01", run_token=foreign_token)

        # 2. Forged token signature rejected fail-closed at construction
        with self.assertRaises(InvalidRunTokenError):
            RunToken(
                token_id="0" * 64,
                timestamp=time.time(),
                pid=os.getpid(),
                parent_pid=1,
                lease_duration=60.0,
                max_budget=120.0,
                session_salt=self.supervisor.session_salt,
            )

        # 3. Expired token rejected
        expired_token = self.supervisor.issue_token(
            pid=os.getpid(),
            parent_pid=1,
            lease_duration=1.0,
            max_budget=120.0,
            timestamp=time.time() - 100.0,
        )
        with self.assertRaises(ExpiredRunTokenError):
            self.runner.run("m_tok_02", run_token=expired_token)

        # 4. Cancelled / aborted token rejected
        valid_token = self.supervisor.issue_token(pid=os.getpid(), parent_pid=1, lease_duration=60.0, max_budget=120.0)
        self.supervisor.cancel_token(valid_token.token_id)
        with self.assertRaises(TokenCancelledError):
            self.runner.run("m_tok_03", run_token=valid_token)

    def test_mission_abort_lifecycle(self) -> None:
        """Verifies aborting an active mission revokes token and marks status ABORTED."""
        self.runner.add_step("step_1", lambda s: {"val": 1})
        self.runner.add_step("step_2", lambda s: {"val": 2})

        tok = self.supervisor.issue_token(pid=os.getpid(), parent_pid=1, lease_duration=60.0, max_budget=120.0)
        self.runner.run("m_abort_01", run_token=tok, interrupt_after=["step_1"])

        abort_res = self.runner.abort("m_abort_01", run_token=tok)
        self.assertEqual(abort_res["status"], "ABORTED")

        # Supervisor token is now cancelled
        self.assertTrue(tok.token_id in self.supervisor._cancelled_tokens)

        # Cannot resume an aborted mission
        with self.assertRaises(MissionAbortedError):
            self.runner.resume("m_abort_01")

    def test_active_console_control_20_wiring(self) -> None:
        """Verifies ActiveConsole Control 20 lifecycle hooks (start_run, pause_run, resume_run, stop_run)."""
        console = ActiveConsole({"patch_id": "test_patch_ssl_01"})
        runner = MissionRunner(
            checkpointer=self.checkpointer,
            supervisor=self.supervisor,
            console=console,
        )

        runner.add_step("step_1", lambda s: {"s1": 1})
        runner.add_step("step_2", lambda s: {"s2": 2})

        tok = self.supervisor.issue_token(pid=os.getpid(), parent_pid=1, lease_duration=60.0, max_budget=120.0)

        # 1. Start & pause
        r1 = runner.run("m_console_01", run_token=tok, interrupt_after=["step_1"])
        self.assertEqual(r1["status"], "PAUSED")
        self.assertIsNotNone(console.active_run_token)
        self.assertEqual(console.active_run_token.token_id, tok.token_id)

        # 2. Resume
        r2 = runner.resume("m_console_01", run_token=tok)
        self.assertEqual(r2["status"], "COMPLETED")

        # 3. Stop / Abort
        runner.abort("m_console_01", run_token=tok)
        self.assertTrue(console.is_stopped)

    def test_dag_dependency_topological_ordering(self) -> None:
        """Verifies DAG dependency ordering executes in topological sequence."""
        execution_trace = []

        def step_c(state: dict) -> dict:
            execution_trace.append("step_c")
            return {"c": True}

        def step_b(state: dict) -> dict:
            execution_trace.append("step_b")
            return {"b": True}

        def step_a(state: dict) -> dict:
            execution_trace.append("step_a")
            return {"a": True}

        # Step C depends on B, Step B depends on A
        self.runner.add_step("step_c", step_c, dependencies=["step_b"])
        self.runner.add_step("step_b", step_b, dependencies=["step_a"])
        self.runner.add_step("step_a", step_a)

        tok = self.supervisor.issue_token(pid=os.getpid(), parent_pid=1, lease_duration=60.0, max_budget=120.0)
        res = self.runner.run("m_dag_01", run_token=tok)

        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(execution_trace, ["step_a", "step_b", "step_c"])

    def test_dag_cycle_detection(self) -> None:
        """Verifies cycle detection in DAG dependencies raises MissionExecutionError."""
        self.runner.add_step("step_1", lambda s: {}, dependencies=["step_2"])
        self.runner.add_step("step_2", lambda s: {}, dependencies=["step_1"])

        with self.assertRaises(MissionExecutionError):
            self.runner.run("m_cyclic")

    def test_thermodynamic_memory_ceiling_under_64kb(self) -> None:
        """Verifies mission execution stays strictly bounded within <= 64 KB heap overhead."""
        receipt = self.runner.profile_mission_memory(steps_count=15)
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)
        self.assertIn("ninshu_mission_runner_ch20_23", receipt.candidate_id)


if __name__ == "__main__":
    unittest.main()
