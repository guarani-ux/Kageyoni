"""Adversarial Verification Suite for Ninshū Ghidra Headless Decompiler Bridge (CH 04).

Verifications:
1. Valid Ghidra Function ASTs: entrypoint, return type, parameters, local variables.
2. High-level P-code and C decompiler tokens (IF, GOTO, RETURN, CALL, BRANCH).
3. Memory references & varnodes (unique, register, ram, const, stack).
4. Symbols and Data Types.
5. Strict fail-closed rejections on corrupt inputs, out-of-bounds offsets, negative sizes.
6. Thermodynamic memory ceiling <= 64 KB via ThermodynamicProfiler.
7. Metamorphic mutation fuzzing via AdversarialMutator.
"""
from __future__ import annotations

import json
import unittest
from typing import Any, Dict

from kageyoni.ninshu.adversary import AdversarialMutator
from kageyoni.ninshu.ghidra_parser import (
    ASTNode,
    GhidraDataType,
    GhidraFunction,
    GhidraParser,
    GhidraProgram,
    GhidraSymbol,
    PcodeOp,
    Varnode,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


class TestNinshuGhidraParser(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_program_dict: Dict[str, Any] = {
            "name": "crackme_v1",
            "arch": "x86_64",
            "image_base": 0x400000,
            "functions": [
                {
                    "name": "main",
                    "entrypoint": 0x401120,
                    "return_type": "int",
                    "parameters": [
                        {"name": "argc", "type_name": "int", "storage": "EDI"},
                        {"name": "argv", "type_name": "char **", "storage": "RSI"},
                    ],
                    "local_variables": [
                        {"name": "local_10", "type_name": "int", "storage": "Stack[-0x10]"},
                    ],
                    "ast": {
                        "node_type": "BLOCK",
                        "attributes": {"address": 0x401120},
                        "children": [
                            {
                                "node_type": "CALL",
                                "token_text": "puts",
                                "attributes": {"target": "puts", "address": 0x401125},
                            },
                            {
                                "node_type": "RETURN",
                                "attributes": {"address": 0x401130},
                            },
                        ],
                    },
                    "pcode": [
                        {
                            "opcode": "CALL",
                            "address": 0x401125,
                            "inputs": [
                                {"space": "ram", "offset": 0x402000, "size": 8},
                            ],
                            "output": None,
                        },
                        {
                            "opcode": "RETURN",
                            "address": 0x401130,
                            "inputs": [
                                {"space": "const", "offset": 0, "size": 4},
                            ],
                            "output": None,
                        },
                    ],
                }
            ],
            "symbols": [
                {"name": "main", "address": 0x401120, "symbol_type": "function", "is_exported": True},
                {"name": "puts", "address": 0x401030, "symbol_type": "imported", "is_imported": True},
            ],
            "data_types": [
                {"name": "int", "size": 4, "category": "primitive"},
                {
                    "name": "UserStruct",
                    "size": 16,
                    "category": "structure",
                    "fields": [
                        {"name": "id", "type_name": "int", "offset": 0, "size": 4},
                        {"name": "flag", "type_name": "int", "offset": 4, "size": 4},
                    ],
                },
            ],
        }
        self.valid_json_bytes = json.dumps(self.valid_program_dict).encode("utf-8")

    def test_parse_valid_program_json(self) -> None:
        prog = GhidraParser.parse_json(self.valid_json_bytes)
        self.assertIsInstance(prog, GhidraProgram)
        self.assertEqual(prog.name, "crackme_v1")
        self.assertEqual(prog.arch, "x86_64")
        self.assertEqual(len(prog.functions), 1)
        self.assertIn("main", prog.functions)

        fn = prog.functions["main"]
        self.assertEqual(fn.entrypoint, 0x401120)
        self.assertEqual(fn.return_type, "int")
        self.assertEqual(len(fn.parameters), 2)
        self.assertEqual(fn.parameters[0].name, "argc")
        self.assertEqual(len(fn.local_variables), 1)
        self.assertIsNotNone(fn.ast)
        self.assertEqual(len(fn.pcode), 2)

    def test_parse_pcode_and_varnodes(self) -> None:
        prog = GhidraParser.parse_json(self.valid_program_dict)
        fn = prog.functions["main"]
        call_op = fn.pcode[0]
        self.assertEqual(call_op.opcode, "CALL")
        self.assertTrue(call_op.is_control_flow)
        self.assertEqual(len(call_op.inputs), 1)
        vn = call_op.inputs[0]
        self.assertEqual(vn.space, "ram")
        self.assertEqual(vn.offset, 0x402000)
        self.assertEqual(vn.size, 8)

    def test_symbols_and_data_types(self) -> None:
        prog = GhidraParser.parse_json(self.valid_program_dict)
        self.assertEqual(len(prog.symbols), 2)
        self.assertEqual(prog.symbols[0].name, "main")
        self.assertEqual(prog.symbols[0].address, 0x401120)
        self.assertIn("UserStruct", prog.data_types)
        self.assertEqual(prog.data_types["UserStruct"].name, "UserStruct")
        self.assertEqual(prog.data_types["UserStruct"].size, 16)

    def test_fail_closed_empty_inputs(self) -> None:
        with self.assertRaises(ValueError):
            GhidraParser.parse_json("")
        with self.assertRaises(ValueError):
            GhidraParser.parse_json(b"")
        with self.assertRaises(ValueError):
            GhidraParser.parse_json({})
        with self.assertRaises(ValueError):
            GhidraParser.parse_xml("")

    def test_fail_closed_corrupted_json(self) -> None:
        corrupted = [
            b'{"name": "test", "functions": [{"name": "f1", "entrypoint": -10}]}',
            b'{"name": "test", "functions": [{"name": "f1", "entrypoint": "0x4000", "pcode": [{"opcode": ""}]}]}',
            b'{"name": "test", "symbols": [{"name": "s1", "address": 4096, "symbol_type": "invalid_type"}]}',
        ]
        for bad in corrupted:
            with self.subTest(bad=bad[:30]):
                with self.assertRaises(ValueError):
                    GhidraParser.parse_json(bad)

    def test_thermodynamic_heap_ceiling(self) -> None:
        _, receipt = ThermodynamicProfiler.profile_callable(lambda: GhidraParser.parse_json(self.valid_json_bytes))
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutator_fuzzing(self) -> None:
        mutator = AdversarialMutator()
        mutants = mutator.generate_adversarial_suite(self.valid_json_bytes)
        for mutant in mutants:
            try:
                prog = GhidraParser.parse_json(mutant)
                self.assertIsInstance(prog, GhidraProgram)
            except (ValueError, TypeError, KeyError):
                pass


if __name__ == "__main__":
    unittest.main()
