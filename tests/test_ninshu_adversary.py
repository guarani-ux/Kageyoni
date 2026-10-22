"""Unit tests for Ninshū Invariant Discriminator & Adversarial Scar Injector.

Verifies:
1. AdversarialMutator generates deterministic boundary, truncation, bit flip, and header mutants.
2. AdversarialDiscriminator exercises positive and negative vectors against WasmParser.
3. Strict fail-closed negative rejection on all adversarial mutants.
4. Active Scar binding into SCAR_REGISTRY on silent acceptance, unhandled crash, and false negative.
5. Integration with the SSL 4000 Console and ScarFeedbackMatrix.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict

from kageyoni.ninshu.adversary import (
    AdversarialDiscriminator,
    AdversarialMutant,
    AdversarialMutator,
    ConsoleAdversaryBridge,
    DiscriminationDisposition,
    GoldenVector,
    MutationType,
    ScarInjector,
)
from kageyoni.ninshu.console import ActiveConsole
from kageyoni.ninshu.planner import BuildPlanCompiler
from kageyoni.ninshu.scars import SCAR_REGISTRY, ScarFeedbackMatrix, ScarImpedanceTransformer
from kageyoni.ninshu.wasm_parser import WasmParser


class TestNinshuAdversary(unittest.TestCase):
    def setUp(self) -> None:
        self.wasm_min = b"\x00asm\x01\x00\x00\x00"
        self.wasm_sections = bytes.fromhex("0061736d01000000010401600000")

    def test_adversarial_mutator_generation(self) -> None:
        """Verify the mutator produces distinct, deterministic adversarial mutants."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.wasm_min, source_id="MIN")
        self.assertGreater(len(mutants), 10)

        types_found = {m.mutation_type for m in mutants}
        self.assertIn(MutationType.TRUNCATION, types_found)
        self.assertIn(MutationType.BIT_FLIP, types_found)
        self.assertIn(MutationType.BOUNDARY_OVERFLOW, types_found)
        self.assertIn(MutationType.MALFORMED_HEADER, types_found)

        # Check truncation includes empty bytes
        empty_mutants = [m for m in mutants if len(m.payload) == 0]
        self.assertEqual(len(empty_mutants), 1)

        # Check malformed headers include ELF and PE
        elf_mutants = [m for m in mutants if m.payload.startswith(b"\x7fELF")]
        self.assertEqual(len(elf_mutants), 1)
        pe_mutants = [m for m in mutants if m.payload.startswith(b"MZ")]
        self.assertEqual(len(pe_mutants), 1)

        # Check boundary overflow includes LEB128 overflows
        overflow_mutants = [m for m in mutants if b"\x80\x80\x80\x80\x80\x80\x01" in m.payload]
        self.assertEqual(len(overflow_mutants), 1)

    def test_wasm_parser_adversarial_discrimination(self) -> None:
        """Verify that WasmParser discriminates valid WASM and rejects all adversarial mutants fail-closed."""
        discriminator = AdversarialDiscriminator(
            target_callable=WasmParser.parse_bytes,
            target_name="WasmParser",
            expected_clean_exceptions=(ValueError,),
        )

        golden_vectors = [
            GoldenVector(
                vector_id="GOLDEN-WASM-MIN",
                payload=self.wasm_min,
                description="Minimal empty WASM header (8 bytes)",
                expected_attributes={"version": 1, "sections_count": 0},
            ),
            GoldenVector(
                vector_id="GOLDEN-WASM-SECTIONS",
                payload=self.wasm_sections,
                description="WASM module with valid Type section",
                expected_attributes={"version": 1, "sections_count": 1},
            ),
        ]

        report = discriminator.discriminate(golden_vectors)

        # All vectors and mutants must pass
        self.assertTrue(report.all_passed)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(report.positive_vectors_count, 2)
        self.assertGreater(report.negative_vectors_count, 15)
        self.assertEqual(len(report.scars_registered), 0)

        # Verify positive vectors are ACCEPTED
        pos_results = [r for r in report.results if r.is_positive]
        self.assertEqual(len(pos_results), 2)
        for r in pos_results:
            self.assertEqual(r.disposition, DiscriminationDisposition.ACCEPTED)
            self.assertTrue(r.passed)

        # Verify all adversarial mutants are CLEAN_REJECTION with ValueError
        neg_results = [r for r in report.results if not r.is_positive]
        for r in neg_results:
            self.assertEqual(r.disposition, DiscriminationDisposition.CLEAN_REJECTION)
            self.assertTrue(r.passed)
            self.assertEqual(r.exception_class, "ValueError")

    def test_scar_binding_on_silent_acceptance(self) -> None:
        """Verify that when a target silently accepts malformed input, an active Scar is registered."""
        # Flawed parser that accepts anything starting with 0x00 without validating magic or version
        def permissive_broken_parser(data: bytes) -> Dict[str, Any]:
            if not data:
                raise ValueError("Empty input")
            return {"parsed": True, "len": len(data)}

        initial_count = len(SCAR_REGISTRY)
        discriminator = AdversarialDiscriminator(
            target_callable=permissive_broken_parser,
            target_name="PermissiveBrokenParser",
            expected_clean_exceptions=(ValueError,),
        )

        golden_vectors = [GoldenVector("GOLDEN-01", self.wasm_min, "Valid WASM")]
        report = discriminator.discriminate(golden_vectors)

        self.assertFalse(report.all_passed)
        self.assertGreater(report.failed_count, 0)
        self.assertGreater(len(report.scars_registered), 0)
        self.assertGreater(len(SCAR_REGISTRY), initial_count)

        # Verify registered scar attributes
        scar_id = report.scars_registered[0]
        self.assertIn(scar_id, SCAR_REGISTRY)
        scar = SCAR_REGISTRY[scar_id]
        self.assertEqual(scar.failure_class, "SILENT_ACCEPTANCE_OF_MALFORMED_INPUT")
        self.assertEqual(scar.damping_factor, 1.0)
        self.assertEqual(scar.reversibility_barrier, 1)
        self.assertIn("PermissiveBrokenParser", scar.root_cause)

    def test_scar_binding_on_unhandled_crash(self) -> None:
        """Verify that when a target crashes with an unhandled exception, an active Scar is registered."""
        def crashing_parser(data: bytes) -> Any:
            # Unhandled IndexError if data is short
            return data[100]

        discriminator = AdversarialDiscriminator(
            target_callable=crashing_parser,
            target_name="CrashingParser",
            expected_clean_exceptions=(ValueError,),
        )

        golden_vectors = [GoldenVector("GOLDEN-CRASH", self.wasm_min, "Valid WASM")]
        report = discriminator.discriminate(golden_vectors)

        self.assertFalse(report.all_passed)
        # Should fail on golden vector (false negative / unhandled crash) and/or mutants
        crash_results = [r for r in report.results if r.disposition == DiscriminationDisposition.UNHANDLED_CRASH]
        self.assertGreater(len(crash_results), 0)

        # Check scar registered
        crashed_scars = [SCAR_REGISTRY[sid] for sid in report.scars_registered if sid in SCAR_REGISTRY]
        self.assertTrue(any(s.failure_class in ("UNHANDLED_CRASH", "FALSE_NEGATIVE_REJECTION") for s in crashed_scars))

    def test_scar_binding_on_false_negative(self) -> None:
        """Verify that when a target rejects a valid golden vector, a Scar is registered."""
        def always_rejecting_parser(data: bytes) -> Any:
            raise ValueError("Rejection of all inputs")

        discriminator = AdversarialDiscriminator(
            target_callable=always_rejecting_parser,
            target_name="RejectingParser",
            expected_clean_exceptions=(ValueError,),
        )

        golden_vectors = [GoldenVector("GOLDEN-01", self.wasm_min, "Valid WASM")]
        report = discriminator.discriminate(golden_vectors)

        self.assertFalse(report.all_passed)
        fn_results = [r for r in report.results if r.disposition == DiscriminationDisposition.FALSE_NEGATIVE_FAILURE]
        self.assertEqual(len(fn_results), 1)

        scar_id = fn_results[0].scar_id
        self.assertIsNotNone(scar_id)
        self.assertIn(scar_id, SCAR_REGISTRY)
        self.assertEqual(SCAR_REGISTRY[scar_id].failure_class, "FALSE_NEGATIVE_REJECTION")

    def test_planner_build_plan_discrimination(self) -> None:
        """Verify discrimination against test vectors defined in BuildPlanCompiler."""
        plan = BuildPlanCompiler.compile_wasm_parser_plan()
        discriminator = AdversarialDiscriminator(
            target_callable=WasmParser.parse_bytes,
            target_name="CH11_WasmParser",
            expected_clean_exceptions=(ValueError,),
        )

        # Pass plan.test_vectors directly into discriminator
        report = discriminator.discriminate(plan.test_vectors)

        self.assertTrue(report.all_passed)
        self.assertEqual(report.failed_count, 0)
        self.assertEqual(len(report.scars_registered), 0)

    def test_ssl_console_bridge_audit_and_feedback(self) -> None:
        """Verify that auditing an SSL channel streams telemetry and elevates thermal ceilings upon failure."""
        patch_manifest = {
            "patch_id": "test_adversary_session",
            "reversibility_tier": 0,
            "channel_strips": [
                {
                    "ch": 11,
                    "name": "WASM Disassembler & Module Inspector",
                    "carrier": "kageyoni/ninshu/wasm_parser.py",
                    "entrypoint": "WasmParser.parse_bytes",
                    "tier": 0,
                }
            ],
        }
        console = ActiveConsole(patch_manifest)
        strip = console.channels[11]
        self.assertEqual(strip.thermal_ceiling, 0)

        # 1. Audit passing component: WasmParser
        report_pass = console.audit_channel_adversarially(
            channel_number=11,
            target_callable=WasmParser.parse_bytes,
            golden_vectors=[self.wasm_min, self.wasm_sections],
        )
        self.assertTrue(report_pass.all_passed)
        self.assertEqual(strip.thermal_ceiling, 0)

        # 2. Audit failing component: defective parser that accepts ELF header
        def leaky_parser(data: bytes) -> Any:
            if data.startswith(b"\x7fELF"):
                return {"fake_elf": True}
            raise ValueError("Expected WASM")

        report_fail = ConsoleAdversaryBridge.audit_channel(
            console=console,
            channel_number=11,
            target_callable=leaky_parser,
            golden_vectors=[self.wasm_min],
            target_name="LeakyParser",
        )
        self.assertFalse(report_fail.all_passed)
        # Verify thermal ceiling was elevated to 1
        self.assertEqual(strip.thermal_ceiling, 1)

        # 3. Verify ScarFeedbackMatrix automatically picks up the registered scar
        matrix = ScarFeedbackMatrix()
        signal = {"target": "LeakyParser", "payload": "silent_acceptance"}
        conditioned, adaptations = matrix.transform_signal(signal, declared_intent="leakyparser audit")

        # Must have engaged the newly formed scar adaptation
        self.assertTrue(any("LEAKYPARSER" in ad or "ingress validation" in ad for ad in adaptations))


if __name__ == "__main__":
    unittest.main()
