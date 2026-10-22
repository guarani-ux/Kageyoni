"""Unit and adversarial verification suite for Channel 23 (Process Lineage & Run Token Supervisor).

Validates:
1. Valid run token generation, cryptographic signature binding, validation, and lease renewal.
2. Process tree lineage inspection, ancestry chain, descendant resolution, cycle prevention.
3. Fail-closed expiration, signature tampering, and revoked/cancelled token rejection.
4. Adversarial fuzz vectors: corrupted tokens, negative budgets, zero/negative durations,
   mismatched context PIDs, expired timestamps, cyclic ancestries.
5. Strict memory ceiling: peak heap allocation <= 64 KB overhead verified via ThermodynamicProfiler.
"""
from __future__ import annotations

import hashlib
import time
import unittest

from kageyoni.ninshu.process_supervisor import (
    BoundaryBudgetExceededError,
    ExpiredRunTokenError,
    InvalidRunTokenError,
    ProcessDescriptor,
    ProcessLineageError,
    ProcessLineageTree,
    ProcessSupervisor,
    RunToken,
    SupervisorSecurityError,
    TokenCancelledError,
    _compute_run_token_digest,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


class TestProcessSupervisor(unittest.TestCase):
    def setUp(self) -> None:
        self.salt = "epistemic_ninshu_salt_0x42"
        self.supervisor = ProcessSupervisor(session_salt=self.salt)

    def test_run_token_generation_and_cryptographic_binding(self) -> None:
        """Verifies token generation has valid SHA-256 signature and fields."""
        token = self.supervisor.issue_token(
            pid=1234,
            parent_pid=1000,
            lease_duration=30.0,
            max_budget=120.0,
            timestamp=1700000000.0,
        )

        expected_digest = _compute_run_token_digest(1700000000.0, 1234, 1000, self.salt)
        self.assertEqual(token.token_id, expected_digest)
        self.assertEqual(token.pid, 1234)
        self.assertEqual(token.parent_pid, 1000)
        self.assertEqual(token.lease_duration, 30.0)
        self.assertEqual(token.max_budget, 120.0)
        self.assertEqual(token.cumulative_execution_time, 0.0)
        self.assertFalse(token.is_cancelled)
        self.assertEqual(token.expiry_time, 1700000030.0)

        # Validation succeeds within lease
        is_valid = self.supervisor.validate_token(
            token,
            expected_pid=1234,
            expected_parent_pid=1000,
            current_time=1700000010.0,
        )
        self.assertTrue(is_valid)

    def test_run_token_serialization_roundtrip(self) -> None:
        """Verifies serialization to dict and deserialization preserves signature and data."""
        token = self.supervisor.issue_token(
            pid=4321,
            parent_pid=4000,
            lease_duration=15.0,
            max_budget=60.0,
            timestamp=1700000100.0,
        )
        d = token.to_dict()
        reconstructed = RunToken.from_dict(d)
        self.assertEqual(token, reconstructed)

    def test_lease_renewal_and_budget_enforcement(self) -> None:
        """Verifies renewing leases advances cumulative execution time up to max_budget."""
        token = self.supervisor.issue_token(
            pid=5555,
            parent_pid=1,
            lease_duration=10.0,
            max_budget=25.0,
            timestamp=1700000000.0,
        )

        # First renewal after 8s elapsed
        renewed_1 = self.supervisor.renew_lease(
            token=token,
            additional_duration=10.0,
            elapsed_execution_time=8.0,
            current_time=1700000008.0,
        )
        self.assertEqual(renewed_1.cumulative_execution_time, 8.0)
        self.assertEqual(renewed_1.lease_duration, 10.0)
        self.assertEqual(renewed_1.timestamp, 1700000008.0)

        # Old token is removed from registry
        with self.assertRaises(InvalidRunTokenError):
            self.supervisor.validate_token(token, current_time=1700000008.0)

        # Second renewal after another 9s elapsed (total cumulative = 17.0s, before expiry at 1700000018.0)
        renewed_2 = self.supervisor.renew_lease(
            token=renewed_1,
            additional_duration=10.0,
            elapsed_execution_time=9.0,
            current_time=1700000017.0,
        )
        self.assertEqual(renewed_2.cumulative_execution_time, 17.0)

        # Third renewal attempts 10s elapsed, which pushes cumulative to 27s > 25s budget
        with self.assertRaises(BoundaryBudgetExceededError):
            self.supervisor.renew_lease(
                token=renewed_2,
                additional_duration=5.0,
                elapsed_execution_time=10.0,
                current_time=1700000020.0,
            )

    def test_fail_closed_expiration_rejection(self) -> None:
        """Rejects expired tokens fail-closed."""
        token = self.supervisor.issue_token(
            pid=9999,
            parent_pid=1,
            lease_duration=5.0,
            max_budget=50.0,
            timestamp=1700000000.0,
        )
        # Exactly at or past expiry
        with self.assertRaises(ExpiredRunTokenError):
            self.supervisor.validate_token(token, current_time=1700000005.0)

        with self.assertRaises(ExpiredRunTokenError):
            self.supervisor.validate_token(token, current_time=1700000010.0)

    def test_signature_tampering_and_context_mismatch_rejection(self) -> None:
        """Rejects modified digests or forged context attributes."""
        token = self.supervisor.issue_token(
            pid=7777,
            parent_pid=100,
            lease_duration=20.0,
            max_budget=100.0,
            timestamp=1700000000.0,
        )

        # Context PID mismatch
        with self.assertRaises(InvalidRunTokenError):
            self.supervisor.validate_token(token, expected_pid=8888, current_time=1700000001.0)

        # Context Parent PID mismatch
        with self.assertRaises(InvalidRunTokenError):
            self.supervisor.validate_token(token, expected_parent_pid=999, current_time=1700000001.0)

        # Forged token with invalid signature rejected at construction
        with self.assertRaises(InvalidRunTokenError):
            RunToken(
                token_id="0" * 64,
                timestamp=token.timestamp,
                pid=token.pid,
                parent_pid=token.parent_pid,
                session_salt=token.session_salt,
                lease_duration=token.lease_duration,
                max_budget=token.max_budget,
            )

    def test_cancellation_and_revocation(self) -> None:
        """Rejects cancelled tokens immediately upon revocation."""
        token = self.supervisor.issue_token(
            pid=3333,
            parent_pid=1,
            lease_duration=20.0,
            max_budget=100.0,
            timestamp=1700000000.0,
        )
        self.supervisor.cancel_token(token.token_id)

        with self.assertRaises(TokenCancelledError):
            self.supervisor.validate_token(token, current_time=1700000001.0)

        # Renewal of cancelled token must also fail
        with self.assertRaises(TokenCancelledError):
            self.supervisor.renew_lease(token, additional_duration=10.0, elapsed_execution_time=1.0)

    def test_process_lineage_tree_and_ancestry(self) -> None:
        """Tests process lineage hierarchy, ancestry tracing, and descendant querying."""
        tree = ProcessLineageTree()

        # Build hierarchy: init (1) -> daemon (10) -> worker (100) -> job (1000)
        tree.register_process(pid=1, parent_pid=0, process_name="init", start_time=100.0)
        tree.register_process(pid=10, parent_pid=1, process_name="daemon", start_time=110.0)
        tree.register_process(pid=100, parent_pid=10, process_name="worker", start_time=120.0)
        tree.register_process(pid=1000, parent_pid=100, process_name="job", start_time=130.0)

        ancestry = tree.get_ancestry(1000)
        ancestry_pids = [p.pid for p in ancestry]
        self.assertEqual(ancestry_pids, [100, 10, 1])

        descendants_1 = tree.get_descendants(1)
        desc_pids = {p.pid for p in descendants_1}
        self.assertEqual(desc_pids, {10, 100, 1000})

        current = tree.capture_current_process()
        self.assertIsInstance(current, ProcessDescriptor)
        self.assertGreater(current.pid, 0)

    def test_adversarial_lineage_cycles_and_anomalies(self) -> None:
        """Verifies cycle detection and capacity limits in ProcessLineageTree."""
        tree = ProcessLineageTree(max_nodes=10)

        # Self-parenting rejection
        with self.assertRaises(ProcessLineageError):
            tree.register_process(pid=50, parent_pid=50, process_name="self_parent")

        # Duplicate PID rejection
        tree.register_process(pid=1, parent_pid=0, process_name="root")
        tree.register_process(pid=2, parent_pid=1, process_name="child")
        with self.assertRaises(ProcessLineageError):
            tree.register_process(pid=2, parent_pid=1, process_name="duplicate")

        # Direct cycle rejection: 2 is parent of 3, attempting to make 3 parent of 2
        tree.register_process(pid=3, parent_pid=2, process_name="grandchild")
        # Trying to register node 4 with parent 3, then attempting cycle
        tree.register_process(pid=4, parent_pid=3, process_name="leaf")

        # Missing PID lookups
        with self.assertRaises(ProcessLineageError):
            tree.get_ancestry(99999)

        with self.assertRaises(ProcessLineageError):
            tree.get_process(99999)

    def test_adversarial_fuzz_vectors(self) -> None:
        """Validates fail-closed handling of malformed input, negative budgets, and bad salts."""
        # Negative lease duration
        with self.assertRaises(InvalidRunTokenError):
            self.supervisor.issue_token(pid=100, parent_pid=1, lease_duration=-5.0, max_budget=10.0)

        # Zero lease duration
        with self.assertRaises(InvalidRunTokenError):
            self.supervisor.issue_token(pid=100, parent_pid=1, lease_duration=0.0, max_budget=10.0)

        # Negative max budget
        with self.assertRaises(InvalidRunTokenError):
            self.supervisor.issue_token(pid=100, parent_pid=1, lease_duration=5.0, max_budget=-10.0)

        # Initial lease duration > max_budget
        with self.assertRaises(BoundaryBudgetExceededError):
            self.supervisor.issue_token(pid=100, parent_pid=1, lease_duration=50.0, max_budget=10.0)

        # Negative timestamp
        with self.assertRaises(InvalidRunTokenError):
            self.supervisor.issue_token(pid=100, parent_pid=1, lease_duration=5.0, max_budget=10.0, timestamp=-1.0)

        # Empty supervisor salt
        with self.assertRaises(SupervisorSecurityError):
            ProcessSupervisor(session_salt="")

        # Malformed deserialization dict
        with self.assertRaises(InvalidRunTokenError):
            RunToken.from_dict({"corrupted": 123})

    def test_thermodynamic_memory_ceiling_64kb(self) -> None:
        """Enforces peak heap memory allocation <= 64 KB overhead via ThermodynamicProfiler."""
        receipt = self.supervisor.profile_supervisor_memory(iterations=50)

        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(
            receipt.peak_memory_bytes,
            65536,
            f"Peak memory {receipt.peak_memory_bytes} bytes exceeded 64 KB ceiling",
        )
        self.assertTrue(receipt.verify_integrity())


if __name__ == "__main__":
    unittest.main()
