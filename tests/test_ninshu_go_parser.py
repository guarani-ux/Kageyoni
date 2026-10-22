"""Unit & Adversarial Verification Suite for Ninshū In-Tree Go Parser (CH 13).

Tests:
1. Extraction of Go buildinfo magic, go_version, module path, dependencies, and settings.
2. Binary format detection (ELF, PE, Mach-O, Raw).
3. Fail-closed rejection on empty payloads or truncated magic headers.
4. Thermodynamic profiling (heap ceiling <= 64 KB).
5. Adversarial mutant fuzzing.
"""
import unittest
from kageyoni.ninshu.go_parser import (
    GoBinaryParser,
    GO_BUILDINFO_MAGIC,
    GO_MODULE_START,
    GO_MODULE_END,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuGoParser(unittest.TestCase):
    def setUp(self):
        # Synthetic Go binary payload: ELF header + padding + Go buildinfo + module text + EOF
        module_text = (
            b"path github.com/example/daemon\n"
            b"mod github.com/example/daemon (devel)\n"
            b"dep github.com/pkg/errors v0.9.1 h1:qZACNdTQ...\n"
            b"build -compiler=gc\n"
            b"build CGO_ENABLED=0\n"
        )
        self.synthetic_go_binary = (
            b"\x7fELF\x02\x01\x01\x00" + (b"\x00" * 32) +
            b"go1.22.4" + b"\x00" +
            GO_BUILDINFO_MAGIC +
            b"\x08\x00" + # 64-bit little endian
            (b"\x00" * 16) +
            GO_MODULE_START +
            module_text +
            GO_MODULE_END +
            (b"\x00" * 16)
        )

    def test_go_build_info_extraction(self):
        """Verify extraction of go_version, module path, and build settings."""
        summary = GoBinaryParser.parse_bytes(self.synthetic_go_binary)
        self.assertTrue(summary.has_go_build_info)
        self.assertEqual(summary.format_detected, "elf")
        self.assertIsNotNone(summary.build_info)

        info = summary.build_info
        self.assertEqual(info.go_version, "go1.22.4")
        self.assertEqual(info.path, "github.com/example/daemon")
        self.assertIsNotNone(info.main_module)
        self.assertEqual(info.main_module.path, "github.com/example/daemon")
        self.assertEqual(len(info.dependencies), 1)
        self.assertEqual(info.dependencies[0].path, "github.com/pkg/errors")
        self.assertEqual(info.settings.get("-compiler"), "gc")
        self.assertEqual(info.settings.get("CGO_ENABLED"), "0")

    def test_non_go_binary_detection(self):
        """Verify that a standard ELF without Go magic reports has_go_build_info=False cleanly."""
        raw_elf = b"\x7fELF\x02\x01\x01\x00" + (b"\x00" * 64)
        summary = GoBinaryParser.parse_bytes(raw_elf)
        self.assertEqual(summary.format_detected, "elf")
        self.assertFalse(summary.has_go_build_info)
        self.assertIsNone(summary.build_info)

    def test_fail_closed_on_empty_and_truncated(self):
        """Verify fail-closed rejection on empty payloads or truncated magic."""
        with self.assertRaises(ValueError):
            GoBinaryParser.parse_bytes(b"")

        # Truncated buildinfo header (magic present but sliced before pointer bytes)
        truncated = GO_BUILDINFO_MAGIC + b"\x08"
        with self.assertRaises(ValueError):
            GoBinaryParser.parse_bytes(truncated)

    def test_thermodynamic_heap_ceiling(self):
        """Verify heap allocation stays strictly <= 64 KB."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            GoBinaryParser.parse_bytes,
            self.synthetic_go_binary,
            candidate_id="go_parser_ch13",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify that adversarial mutants either parse safely or fail cleanly with ValueError."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.synthetic_go_binary)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                summary = GoBinaryParser.parse_bytes(m.payload)
                self.assertIsInstance(summary.total_bytes, int)
            except ValueError:
                pass
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
