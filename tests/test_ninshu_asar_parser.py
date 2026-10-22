"""Unit & Adversarial Verification Suite for Ninshū In-Tree ASAR Parser (CH 25).

Tests:
1. Parsing valid synthetic ASAR archives with nested directories and file payloads.
2. Pickle header validation (magic 4, extents, JSON sizes).
3. Fail-closed rejection on corrupt magic, truncated JSON, or out-of-bounds extents.
4. Thermodynamic profiling (heap ceiling <= 64 KB).
5. Adversarial mutant fuzzing.
"""
import io
import json
import struct
import unittest

from kageyoni.ninshu.asar_parser import AsarArchiveParser
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuAsarParser(unittest.TestCase):
    def setUp(self):
        # Create a synthetic ASAR archive:
        # File 1: "package.json", size: 14 bytes, offset: 0 -> b'{"name":"app"}'
        # File 2: "main.js", size: 18 bytes, offset: 14 -> b'console.log("hi");'
        file_tree = {
            "files": {
                "package.json": {"size": 14, "offset": "0"},
                "src": {
                    "files": {
                        "main.js": {"size": 18, "offset": "14"}
                    }
                }
            }
        }
        json_bytes = json.dumps(file_tree, separators=(",", ":")).encode("utf-8")
        json_len = len(json_bytes)

        # ASAR header layout:
        # magic (uint32 = 4)
        # header_bytes (uint32 = 4 + 4 + json_len)
        # payload_bytes (uint32 = header_bytes - 4 = 4 + json_len)
        # json_bytes (uint32 = json_len)
        header_bytes = 8 + json_len
        payload_bytes = header_bytes - 4

        header_prefix = struct.pack("<IIII", 4, header_bytes, payload_bytes, json_len)
        file_payloads = b'{"name":"app"}' + b'console.log("hi");'

        self.synthetic_asar = header_prefix + json_bytes + file_payloads

    def test_asar_extraction_and_file_tree(self):
        """Verify extraction of file entries, directory hierarchies, and byte offsets."""
        summary = AsarArchiveParser.parse_bytes(self.synthetic_asar)
        self.assertEqual(summary.total_bytes, len(self.synthetic_asar))
        self.assertEqual(summary.files_count, 2)
        self.assertEqual(summary.directories_count, 1)

        paths = [e.path for e in summary.entries]
        self.assertIn("package.json", paths)
        self.assertIn("src", paths)
        self.assertIn("src/main.js", paths)

        pkg_entry = next(e for e in summary.entries if e.path == "package.json")
        self.assertEqual(pkg_entry.size, 14)
        self.assertFalse(pkg_entry.is_directory)

    def test_fail_closed_on_corrupt_pickle(self):
        """Verify fail-closed rejection on invalid magic or truncated headers."""
        with self.assertRaises(ValueError):
            AsarArchiveParser.parse_bytes(b"")

        # Wrong magic (e.g. 5 instead of 4)
        corrupt_magic = struct.pack("<IIII", 5, 20, 16, 12) + (b"\x00" * 32)
        with self.assertRaises(ValueError):
            AsarArchiveParser.parse_bytes(corrupt_magic)

        # Truncated container (< 16 bytes)
        with self.assertRaises(ValueError):
            AsarArchiveParser.parse_bytes(b"\x04\x00\x00\x00\x10")

    def test_thermodynamic_heap_ceiling(self):
        """Verify heap allocation stays strictly <= 64 KB."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            AsarArchiveParser.parse_bytes,
            self.synthetic_asar,
            candidate_id="asar_parser_ch25",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify that adversarial mutants either parse safely or fail cleanly with ValueError."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.synthetic_asar)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                summary = AsarArchiveParser.parse_bytes(m.payload)
                self.assertIsInstance(summary.total_bytes, int)
            except ValueError:
                pass
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
