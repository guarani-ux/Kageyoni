"""Tests for Ninshū Thermodynamic & Fresh-Process Reopening Verifier.

Verifies:
1. Cryptographic integrity and RFC 8785 canonical digest of ThermodynamicReceipt.
2. In-process ThermodynamicProfiler against WasmParser and BuildPlanCompiler.
3. Fail-closed threshold enforcement for memory ceilings and exit codes.
4. Clean-room fresh OS subprocess reopening against WasmParser and BuildPlanCompiler with zero shared heap.
5. Integration with the SSL 4000 Console and Master Print Tape.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from kageyoni.ninshu.console import ActiveConsole, ChannelStripConfig, MasterTape
from kageyoni.ninshu.planner import BuildPlanCompiler
from kageyoni.ninshu.thermodynamics import (
    DigestMismatchError,
    FreshProcessVerifier,
    MemoryCeilingExceededError,
    ProcessExitCodeError,
    ThermodynamicProfiler,
    ThermodynamicReceipt,
    ThermodynamicViolationError,
    canonical_digest,
)
from kageyoni.ninshu.wasm_parser import WasmParser


class TestNinshuThermodynamics(unittest.TestCase):
    def setUp(self):
        self.verifier = FreshProcessVerifier()
        self.plan = BuildPlanCompiler.compile_wasm_parser_plan()

    def test_thermodynamic_receipt_creation_and_integrity(self):
        """Verify ThermodynamicReceipt seals canonical SHA-256 digest and verifies integrity."""
        receipt = ThermodynamicReceipt.create(
            candidate_id="test_candidate",
            peak_memory_bytes=4096,
            current_memory_bytes=1024,
            wall_time_seconds=0.005,
            cpu_time_seconds=0.004,
            memory_ceiling_bytes=65536,
            passed=True,
            exit_code=0,
            artifact_sha256=hashlib.sha256(b"dummy_artifact").hexdigest(),
            verified_cross_process=False,
            details={"notes": "unit_test"},
        )

        self.assertEqual(len(receipt.receipt_digest), 64)
        self.assertTrue(receipt.verify_integrity())
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertEqual(receipt.peak_memory_bytes, 4096)

        # Verify that tampering invalidates the cryptographic check
        tampered = ThermodynamicReceipt(
            candidate_id="tampered_candidate",
            peak_memory_bytes=receipt.peak_memory_bytes,
            current_memory_bytes=receipt.current_memory_bytes,
            wall_time_seconds=receipt.wall_time_seconds,
            cpu_time_seconds=receipt.cpu_time_seconds,
            memory_ceiling_bytes=receipt.memory_ceiling_bytes,
            passed=receipt.passed,
            exit_code=receipt.exit_code,
            artifact_sha256=receipt.artifact_sha256,
            receipt_digest=receipt.receipt_digest,  # old digest
            verified_cross_process=receipt.verified_cross_process,
            timestamp=receipt.timestamp,
            details=receipt.details,
        )
        self.assertFalse(tampered.verify_integrity())

    def test_in_process_profiler_wasm_parser(self):
        """Profile WasmParser in-process and verify heap allocation stays <= 64 KB."""
        minimal_wasm = bytes.fromhex("0061736d01000000")
        expected_digest = hashlib.sha256(minimal_wasm).hexdigest()
        summary, receipt = ThermodynamicProfiler.profile_callable(
            WasmParser.parse_bytes,
            minimal_wasm,
            candidate_id="wasm_parser_in_process",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
            artifact_sha256=expected_digest,
        )

        self.assertEqual(summary.version, 1)
        self.assertEqual(summary.sections_count, 0)
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertFalse(receipt.verified_cross_process)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)
        self.assertEqual(receipt.artifact_sha256, expected_digest)
        self.assertTrue(receipt.verify_integrity())

    def test_in_process_profiler_build_plan_compiler(self):
        """Profile BuildPlanCompiler in-process and verify heap allocation stays <= 64 KB."""
        plan, receipt = ThermodynamicProfiler.profile_callable(
            BuildPlanCompiler.compile_wasm_parser_plan,
            candidate_id="build_plan_in_process",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )

        self.assertEqual(plan.plan_id, "BP-CH11-WASM-STDLIB")
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)
        self.assertEqual(receipt.artifact_sha256, plan.plan_digest)
        self.assertTrue(receipt.verify_integrity())

    def test_in_process_memory_ceiling_fail_closed(self):
        """Verify fail-closed enforcement when memory ceiling is exceeded in-process."""
        def allocate_big_buffer():
            return [x for x in range(50000)]

        # Fail-closed should raise MemoryCeilingExceededError
        with self.assertRaises(MemoryCeilingExceededError):
            ThermodynamicProfiler.profile_callable(
                allocate_big_buffer,
                candidate_id="buffer_allocator",
                memory_ceiling_bytes=1024,  # 1 KB ceiling (will be exceeded)
                fail_closed=True,
            )

        # Fail-open should not raise, but return passed=False
        res, receipt = ThermodynamicProfiler.profile_callable(
            allocate_big_buffer,
            candidate_id="buffer_allocator_non_fatal",
            memory_ceiling_bytes=1024,
            fail_closed=False,
        )
        self.assertFalse(receipt.passed)
        self.assertGreater(receipt.peak_memory_bytes, 1024)

    def test_fresh_process_wasm_parser_reopening_minimal(self):
        """Spawn a fresh OS subprocess to reopen and parse a minimal WASM binary from disk."""
        min_vector = next(v for v in self.plan.test_vectors if v.vector_id == "VEC-WASM-MIN-01")
        raw_bytes = bytes.fromhex(min_vector.input_bytes_hex)

        receipt = self.verifier.verify_wasm_bytes(
            raw_bytes,
            candidate_id="fresh_wasm_min",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )

        self.assertTrue(receipt.verified_cross_process)
        self.assertEqual(receipt.exit_code, 0)
        self.assertTrue(receipt.passed)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)
        self.assertEqual(receipt.details.get("version"), 1)
        self.assertEqual(receipt.details.get("sections_count"), 0)
        self.assertEqual(receipt.artifact_sha256, hashlib.sha256(raw_bytes).hexdigest())
        self.assertTrue(receipt.verify_integrity())

    def test_fresh_process_wasm_parser_reopening_sections(self):
        """Spawn a fresh OS subprocess to reopen and parse a WASM binary with sections from disk."""
        sec_vector = next(v for v in self.plan.test_vectors if v.vector_id == "VEC-WASM-SECTIONS-01")
        raw_bytes = bytes.fromhex(sec_vector.input_bytes_hex)

        receipt = self.verifier.verify_wasm_bytes(
            raw_bytes,
            candidate_id="fresh_wasm_sections",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )

        self.assertTrue(receipt.verified_cross_process)
        self.assertEqual(receipt.exit_code, 0)
        self.assertTrue(receipt.passed)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)
        self.assertEqual(receipt.details.get("sections_count"), 1)
        self.assertEqual(receipt.artifact_sha256, hashlib.sha256(raw_bytes).hexdigest())

    def test_fresh_process_wasm_parser_rejection_vectors(self):
        """Verify adversarial invalid vectors are cleanly rejected inside the fresh subprocess."""
        magic_vector = next(v for v in self.plan.test_vectors if v.vector_id == "VEC-WASM-ERR-MAGIC")
        raw_bytes = bytes.fromhex(magic_vector.input_bytes_hex)

        # When expected error substring is supplied, subprocess verifies that fail-closed exception occurred
        receipt = self.verifier.verify_wasm_bytes(
            raw_bytes,
            candidate_id="fresh_wasm_err_magic",
            memory_ceiling_bytes=64 * 1024,
            expected_error_substr="Invalid WASM magic header",
            fail_closed=True,
        )
        self.assertTrue(receipt.verified_cross_process)
        self.assertEqual(receipt.exit_code, 0)
        self.assertTrue(receipt.passed)
        self.assertIn("expected_rejection_verified", receipt.details)

        # When malformed payload is run without expected error under fail_closed, must raise ProcessExitCodeError
        with self.assertRaises(ProcessExitCodeError):
            self.verifier.verify_wasm_bytes(
                raw_bytes,
                candidate_id="fresh_wasm_err_unhandled",
                memory_ceiling_bytes=64 * 1024,
                expected_error_substr=None,
                fail_closed=True,
            )

    def test_fresh_process_build_plan_reopening(self):
        """Spawn fresh OS subprocess to reopen and verify BuildPlan JSON artifact from disk."""
        receipt = self.verifier.verify_build_plan_artifact(
            self.plan,
            candidate_id="fresh_build_plan",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )

        self.assertTrue(receipt.verified_cross_process)
        self.assertEqual(receipt.exit_code, 0)
        self.assertTrue(receipt.passed)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)
        self.assertEqual(receipt.details.get("plan_id"), "BP-CH11-WASM-STDLIB")
        self.assertEqual(receipt.details.get("target_channel_id"), 11)
        self.assertEqual(receipt.details.get("invariants_count"), 4)
        self.assertEqual(receipt.details.get("test_vectors_count"), 4)
        self.assertEqual(receipt.details.get("plan_digest"), self.plan.plan_digest)
        self.assertTrue(receipt.verify_integrity())

    def test_fresh_process_memory_ceiling_fail_closed(self):
        """Verify fail-closed enforcement when memory ceiling is exceeded in subprocess."""
        min_vector = next(v for v in self.plan.test_vectors if v.vector_id == "VEC-WASM-MIN-01")
        raw_bytes = bytes.fromhex(min_vector.input_bytes_hex)

        # Set an impossibly low ceiling of 50 bytes for cross-process reopening
        with self.assertRaises((MemoryCeilingExceededError, ProcessExitCodeError)):
            self.verifier.verify_wasm_bytes(
                raw_bytes,
                candidate_id="exceeded_cross_process",
                memory_ceiling_bytes=50,
                fail_closed=True,
            )

        # Non-fatal should return receipt with passed=False
        receipt = self.verifier.verify_wasm_bytes(
            raw_bytes,
            candidate_id="exceeded_cross_process_non_fatal",
            memory_ceiling_bytes=50,
            fail_closed=False,
        )
        self.assertFalse(receipt.passed)

    def test_fresh_process_artifact_digest_mismatch(self):
        """Verify DigestMismatchError when expected SHA-256 does not match disk bytes."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dat") as tmp:
            tmp.write(b"original_content")
            tmp_path = Path(tmp.name).resolve()

        try:
            wrong_digest = hashlib.sha256(b"different_content").hexdigest()
            with self.assertRaises(DigestMismatchError):
                self.verifier.verify_disk_artifact(
                    file_path=tmp_path,
                    mode="json",
                    candidate_id="tampered_artifact",
                    expected_sha256=wrong_digest,
                    fail_closed=True,
                )
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def test_ssl_console_thermodynamic_integration(self):
        """Verify ActiveConsole integration: channel audit, cross-process verification, and MasterTape seal."""
        patch_manifest = {
            "patch_id": "test_thermo_patch",
            "reversibility_tier": 0,
            "channel_strips": [
                {
                    "ch": 11,
                    "name": "WASM Module Inspector",
                    "carrier": "kageyoni/ninshu/wasm_parser.py",
                    "entrypoint": "WasmParser.parse_stream",
                    "tier": 0,
                }
            ],
        }
        console = ActiveConsole(patch_manifest)

        # 1. In-process channel thermodynamic audit
        receipt1 = console.audit_channel_thermodynamics(channel_number=11)
        self.assertTrue(receipt1.passed)
        self.assertIsNotNone(console.channels[11].thermodynamic_receipt)
        self.assertEqual(
            console.channels[11].thermodynamic_receipt["candidate_id"],
            "CH11_WASM Module Inspector",
        )

        # 2. Fresh OS subprocess channel artifact verification
        valid_wasm = bytes.fromhex("0061736d01000000")
        receipt2 = console.verify_channel_artifact_cross_process(
            channel_number=11,
            artifact_bytes=valid_wasm,
            mode="wasm",
        )
        self.assertTrue(receipt2.verified_cross_process)
        self.assertTrue(receipt2.passed)
        self.assertEqual(receipt2.details.get("version"), 1)

        # 3. Master Print Bus consolidation
        active_signals = [{"carrier": "liquid_metal_sample", "confidence_score": 1.0}]
        compiled_aspects = [{"aspect_id": "aspect_01", "intent": "inspect_wasm"}]
        master_tape = console.print_master(
            session_id="session_thermo_001",
            active_signals=active_signals,
            compiled_aspects=compiled_aspects,
            thermodynamic_receipts=[receipt1, receipt2],
        )

        # Verify MasterTape properties
        self.assertEqual(master_tape.session_id, "session_thermo_001")
        self.assertEqual(len(master_tape.thermodynamic_receipts), 2)
        self.assertEqual(len(master_tape.master_sha256), 64)

        # Verify thermodynamic evidence in evidence records
        thermo_evidence = [
            r for r in master_tape.verified_evidence_records
            if r.get("evidence_type") == "THERMODYNAMIC_RECEIPT"
        ]
        self.assertEqual(len(thermo_evidence), 2)
        self.assertTrue(any(e.get("cross_process") for e in thermo_evidence))


if __name__ == "__main__":
    unittest.main()
