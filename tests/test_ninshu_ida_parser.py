"""Adversarial Verification Suite for Ninshū IDA Pro Headless Telemetry & Protocol Parser (CH 07).

Verifications:
1. Address normalization across 64-bit/32-bit hex coordinates.
2. Function observations & spans.
3. Disassembly header validation (rejecting header contradictions).
4. XREF extraction & categorization.
5. Strict fail-closed rejections on corrupt inputs, negative sizes, out-of-bounds addresses.
6. Thermodynamic memory ceiling <= 64 KB via ThermodynamicProfiler.
7. Metamorphic mutation fuzzing via AdversarialMutator.
"""
from __future__ import annotations

import json
import unittest
from typing import Any, Dict

from kageyoni.ninshu.adversary import AdversarialMutator
from kageyoni.ninshu.ida_parser import (
    IdaDisassemblyBlock,
    IdaFunction,
    IdaHeadlessParser,
    IdaSessionSummary,
    IdaXref,
    normalize_ida_address,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


class TestNinshuIdaParser(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_payload_dict: Dict[str, Any] = {
            "functions": [
                {"address": "0x401000", "name": "main", "size": 0x50, "flags": 0},
                {"address": "401050", "name": "sub_401050", "size": "0x30", "flags": 1},
            ],
            "xrefs": [
                {"from": "0x401020", "to": "0x401050", "type": "call", "is_code": True},
                {"from": "0x401040", "to": "0x402000", "type": "data_read", "is_code": False},
            ],
        }
        self.valid_json_bytes = json.dumps(self.valid_payload_dict).encode("utf-8")

    def test_normalize_ida_address(self) -> None:
        self.assertEqual(normalize_ida_address(0x401000), "0x401000")
        self.assertEqual(normalize_ida_address("0x401000"), "0x401000")
        self.assertEqual(normalize_ida_address("401000"), "0x401000")
        self.assertEqual(normalize_ida_address("0XABC"), "0xabc")

        with self.assertRaises(ValueError):
            normalize_ida_address(-1)
        with self.assertRaises(ValueError):
            normalize_ida_address(0x10000000000000000)
        with self.assertRaises(ValueError):
            normalize_ida_address("not_hex")

    def test_parse_valid_session(self) -> None:
        summary = IdaHeadlessParser.parse_session(self.valid_json_bytes)
        self.assertIsInstance(summary, IdaSessionSummary)
        self.assertEqual(summary.functions_count, 2)
        self.assertEqual(summary.xrefs_count, 2)
        self.assertEqual(summary.functions[0].name, "main")
        self.assertEqual(summary.functions[0].address, "0x401000")
        self.assertEqual(summary.functions[0].size, 80)
        self.assertEqual(summary.xrefs[0].from_ea, "0x401020")
        self.assertEqual(summary.xrefs[0].to_ea, "0x401050")
        self.assertEqual(summary.xrefs[0].xref_type, "call")

    def test_parse_disassembly_with_header(self) -> None:
        disasm_data = {
            "name": "main",
            "start_ea": "0x401000",
            "lines": [
                "main (sub_401000 @ 0x401000):",
                "push rbp",
                "mov rbp, rsp",
                "ret",
            ],
        }
        block = IdaHeadlessParser.parse_disassembly(disasm_data)
        self.assertEqual(block.function_name, "main")
        self.assertEqual(block.start_ea, "0x401000")
        self.assertEqual(len(block.lines), 3)

    def test_parse_disassembly_header_contradiction(self) -> None:
        disasm_data = {
            "name": "main",
            "start_ea": "0x401000",
            "lines": [
                "other_func (other @ 0x402000):",
                "ret",
            ],
        }
        with self.assertRaises(ValueError):
            IdaHeadlessParser.parse_disassembly(disasm_data)

    def test_fail_closed_empty_and_corrupt(self) -> None:
        with self.assertRaises(ValueError):
            IdaHeadlessParser.parse_session("")
        with self.assertRaises(ValueError):
            IdaHeadlessParser.parse_session(b"")
        with self.assertRaises(ValueError):
            IdaHeadlessParser.parse_session({})

        corrupted = [
            b'{"functions": [{"name": "", "address": "0x1000"}]}',
            b'{"functions": [{"name": "f1", "address": "invalid_hex"}]}',
            b'{"functions": [{"name": "f1", "address": "0x1000", "size": -5}]}',
            b'{"xrefs": [{"from": "0x1000"}]}',  # missing to
        ]
        for bad in corrupted:
            with self.subTest(bad=bad[:30]):
                with self.assertRaises(ValueError):
                    IdaHeadlessParser.parse_session(bad)

    def test_thermodynamic_heap_ceiling(self) -> None:
        _, receipt = ThermodynamicProfiler.profile_callable(
            lambda: IdaHeadlessParser.parse_session(self.valid_json_bytes)
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutator_fuzzing(self) -> None:
        mutator = AdversarialMutator()
        mutants = mutator.generate_adversarial_suite(self.valid_json_bytes)
        for mutant in mutants:
            try:
                res = IdaHeadlessParser.parse_session(mutant)
                self.assertIsInstance(res, IdaSessionSummary)
            except (ValueError, TypeError, KeyError):
                pass


if __name__ == "__main__":
    unittest.main()
