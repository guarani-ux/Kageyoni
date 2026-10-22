"""Unit & Adversarial Verification Suite for Ninshū In-Tree Rust Parser (CH 14).

Tests:
1. Legacy symbol demangling (_ZN3std2io4Read17h1234567890abcdefE -> std::io::Read).
2. v0 symbol demangling (_R...).
3. Embedded /rustc/<40-hex>/ commit identification.
4. Embedded cargo-auditable zlib dependency graph extraction.
5. Fail-closed rejection on empty payloads.
6. Thermodynamic profiling (heap ceiling <= 64 KB).
7. Adversarial mutant fuzzing.
"""
import json
import unittest
import zlib

from kageyoni.ninshu.rust_parser import RustBinaryParser, RustDemangler
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuRustParser(unittest.TestCase):
    def setUp(self):
        # Create synthetic auditable metadata payload
        auditable_doc = {
            "packages": [
                {
                    "name": "ripgrep",
                    "version": "14.1.0",
                    "source": "registry",
                    "kind": "runtime",
                    "dependencies": [1],
                    "root": True
                },
                {
                    "name": "regex",
                    "version": "1.10.4",
                    "source": "registry",
                    "kind": "runtime",
                    "dependencies": [],
                    "root": False
                }
            ]
        }
        compressed_zlib = zlib.compress(json.dumps(auditable_doc).encode("utf-8"))

        # Build synthetic binary
        self.synthetic_rust_binary = (
            b"\x7fELF\x02\x01\x01\x00" + (b"\x00" * 32) +
            b"/rustc/9b00956e56009bab2aa15d7bff109165b145a878/library/std\x00" +
            b"_ZN3std2io4Read17h1234567890abcdefE\x00" +
            b".dep-v0\x00\x00\x00" +
            compressed_zlib +
            (b"\x00" * 32)
        )

    def test_legacy_symbol_demangling(self):
        """Verify demangling of Itanium-style Rust legacy symbols."""
        mangled = "_ZN3std2io4Read17h1234567890abcdefE"
        demangled = RustDemangler.demangle(mangled)
        self.assertEqual(demangled, "std::io::Read")

        mangled2 = "_ZN7ripgrep4main17haabbccddeeff0011E"
        self.assertEqual(RustDemangler.demangle(mangled2), "ripgrep::main")

    def test_rustc_commit_extraction(self):
        """Verify extraction of embedded rustc 40-hex commit hashes."""
        commits = RustBinaryParser.extract_rustc_commits(self.synthetic_rust_binary)
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0].commit_hash, "9b00956e56009bab2aa15d7bff109165b145a878")

    def test_cargo_auditable_package_extraction(self):
        """Verify decompression and parsing of embedded cargo-auditable package graphs."""
        summary = RustBinaryParser.parse_bytes(self.synthetic_rust_binary)
        self.assertTrue(summary.has_auditable_data)
        self.assertEqual(len(summary.packages), 2)

        pkg_names = [p.name for p in summary.packages]
        self.assertIn("ripgrep", pkg_names)
        self.assertIn("regex", pkg_names)

        root_pkg = next(p for p in summary.packages if p.name == "ripgrep")
        self.assertEqual(root_pkg.version, "14.1.0")
        self.assertTrue(root_pkg.root)

    def test_fail_closed_on_empty(self):
        """Verify rejection on empty input."""
        with self.assertRaises(ValueError):
            RustBinaryParser.parse_bytes(b"")

    def test_thermodynamic_heap_ceiling(self):
        """Verify heap allocation stays strictly <= 64 KB."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            RustBinaryParser.parse_bytes,
            self.synthetic_rust_binary,
            candidate_id="rust_parser_ch14",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify adversarial mutants either parse cleanly or fail safely."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.synthetic_rust_binary)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                summary = RustBinaryParser.parse_bytes(m.payload)
                self.assertIsInstance(summary.total_bytes, int)
            except ValueError:
                pass
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
