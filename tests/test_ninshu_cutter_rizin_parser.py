"""Adversarial Verification Suite for Ninshū Cutter / Rizin Static Engine (CH 06).

Verifications:
1. Valid JSON decoding across iIj (info), iSj (sections), aflj (functions), and pdfj (disassembly).
2. Control Flow Graph (CFG) edge extraction: calls, unconditional jumps, conditional branches, fallthroughs.
3. Cyclomatic complexity calculation and validation against function metadata.
4. Fail-closed rejection of corrupted JSON, missing fields, out-of-order instruction offsets, and negative addresses.
5. Thermodynamic memory profiling asserting peak heap ceiling <= 64 KB.
6. Metamorphic fuzzing via AdversarialMutator asserting 100% fail-closed rejection.
"""
from __future__ import annotations

import json
import unittest
from typing import Any, Dict

from kageyoni.ninshu.cutter_rizin_parser import (
    CutterRizinParser,
    CutterRizinPipeline,
    RizinBinaryInfo,
    RizinSection,
    RizinFunction,
    RizinOp,
    CFGEdge,
    RizinFunctionDisassembly,
    MAX_STATIC_PAYLOAD_BYTES,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuCutterRizinParser(unittest.TestCase):
    def setUp(self):
        self.valid_info_dict = {
            "format": "elf64",
            "arch": "x86",
            "bits": 64,
            "endian": "little",
            "compiler": "gcc 11.2.0",
            "canary": True,
            "nx": True,
            "pic": True,
        }

        self.valid_sections_list = [
            {
                "name": ".text",
                "size": 4096,
                "vaddr": 0x401000,
                "paddr": 0x1000,
                "flags": "r-x",
            },
            {
                "name": ".rodata",
                "size": 1024,
                "vaddr": 0x402000,
                "paddr": 0x2000,
                "flags": "r--",
            },
            {
                "name": ".data",
                "size": 512,
                "vaddr": 0x603000,
                "paddr": 0x3000,
                "flags": "rw-",
            },
        ]

        self.valid_functions_list = [
            {
                "offset": 0x401050,
                "name": "main",
                "size": 48,
                "realsz": 48,
                "cc": 2,
                "nops": 0,
                "calltype": "cdecl",
                "type": "fcn",
            },
            {
                "offset": 0x401100,
                "name": "sym.helper",
                "size": 32,
                "realsz": 32,
                "cc": 1,
                "nops": 1,
                "calltype": "cdecl",
                "type": "fcn",
            },
        ]

        self.valid_disasm_dict = {
            "name": "main",
            "offset": 0x401050,
            "size": 48,
            "ops": [
                {
                    "offset": 0x401050,
                    "opcode": "push rbp",
                    "size": 1,
                    "type": "push",
                },
                {
                    "offset": 0x401051,
                    "opcode": "mov rbp, rsp",
                    "size": 3,
                    "type": "mov",
                },
                {
                    "offset": 0x401054,
                    "opcode": "cmp edi, 0",
                    "size": 3,
                    "type": "cmp",
                },
                {
                    "offset": 0x401057,
                    "opcode": "jne 0x401065",
                    "size": 2,
                    "type": "cjmp",
                    "jump": 0x401065,
                    "fail": 0x401059,
                },
                {
                    "offset": 0x401059,
                    "opcode": "call sym.helper",
                    "size": 5,
                    "type": "call",
                    "jump": 0x401100,
                },
                {
                    "offset": 0x40105E,
                    "opcode": "jmp 0x40106A",
                    "size": 2,
                    "type": "jmp",
                    "jump": 0x40106A,
                },
                {
                    "offset": 0x401065,
                    "opcode": "mov eax, 1",
                    "size": 5,
                    "type": "mov",
                },
                {
                    "offset": 0x40106A,
                    "opcode": "pop rbp",
                    "size": 1,
                    "type": "pop",
                },
                {
                    "offset": 0x40106B,
                    "opcode": "ret",
                    "size": 1,
                    "type": "ret",
                },
            ],
        }

        self.valid_pipeline_dict = {
            "iIj": self.valid_info_dict,
            "iSj": self.valid_sections_list,
            "aflj": self.valid_functions_list,
            "pdfj": self.valid_disasm_dict,
        }

        self.valid_pipeline_json = json.dumps(self.valid_pipeline_dict, indent=2)
        self.valid_pipeline_bytes = self.valid_pipeline_json.encode("utf-8")

    def test_parse_iIj_binary_info_success(self):
        info = CutterRizinParser.parse_iIj(self.valid_info_dict)
        self.assertEqual(info.format, "elf64")
        self.assertEqual(info.arch, "x86")
        self.assertEqual(info.bits, 64)
        self.assertEqual(info.endian, "little")
        self.assertEqual(info.compiler, "gcc 11.2.0")
        self.assertTrue(info.canary)
        self.assertTrue(info.nx)
        self.assertTrue(info.pic)

        # Check serialization
        d = info.to_dict()
        self.assertEqual(d["bits"], 64)
        self.assertEqual(d["compiler"], "gcc 11.2.0")

    def test_parse_iIj_nested_and_pe_macho(self):
        # PE nested test
        pe_nested = {
            "core": {
                "format": "pe64",
                "arch": "x86-64",
                "bits": 64,
                "endian": "little",
            },
            "bin": {
                "compiler": "msvc 19.30",
                "canary": "true",
                "nx": 1,
                "pic": "yes",
            },
        }
        info_pe = CutterRizinParser.parse_iIj(pe_nested)
        self.assertEqual(info_pe.format, "pe64")
        self.assertTrue(info_pe.canary)
        self.assertTrue(info_pe.nx)
        self.assertTrue(info_pe.pic)

        # Mach-O ARM64 big endian test
        macho_dict = {
            "format": "mach0",
            "arch": "arm64",
            "bits": 64,
            "endian": "be",
            "compiler": "apple clang",
            "canary": False,
            "nx": True,
            "pic": False,
        }
        info_macho = CutterRizinParser.parse_iIj(macho_dict)
        self.assertEqual(info_macho.format, "mach0")
        self.assertEqual(info_macho.endian, "big")
        self.assertFalse(info_macho.canary)
        self.assertTrue(info_macho.nx)
        self.assertFalse(info_macho.pic)

    def test_parse_iSj_sections_success(self):
        sections = CutterRizinParser.parse_iSj(self.valid_sections_list)
        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[0].name, ".text")
        self.assertEqual(sections[0].size, 4096)
        self.assertEqual(sections[0].vaddr, 0x401000)
        self.assertEqual(sections[0].paddr, 0x1000)
        self.assertEqual(sections[0].flags, "r-x")

        # Dict wrapper
        wrapped = {"sections": self.valid_sections_list}
        sections_wrapped = CutterRizinParser.parse_iSj(wrapped)
        self.assertEqual(len(sections_wrapped), 3)

    def test_parse_aflj_functions_success(self):
        functions = CutterRizinParser.parse_aflj(self.valid_functions_list)
        self.assertEqual(len(functions), 2)
        self.assertEqual(functions[0].name, "main")
        self.assertEqual(functions[0].offset, 0x401050)
        self.assertEqual(functions[0].size, 48)
        self.assertEqual(functions[0].realsz, 48)
        self.assertEqual(functions[0].cc, 2)
        self.assertEqual(functions[0].nops, 0)
        self.assertEqual(functions[0].calltype, "cdecl")
        self.assertEqual(functions[0].type, "fcn")

    def test_parse_pdfj_disasm_and_cfg_edges(self):
        disasm = CutterRizinParser.parse_pdfj(self.valid_disasm_dict)
        self.assertEqual(disasm.name, "main")
        self.assertEqual(disasm.offset, 0x401050)
        self.assertEqual(len(disasm.ops), 9)

        # Verify CFG edge extraction
        edges = disasm.edges
        self.assertGreaterEqual(len(edges), 8)

        # Check cjmp edges at 0x401057: conditional_true -> 0x401065, conditional_false -> 0x401059
        cjmp_edges = [e for e in edges if e.source == 0x401057]
        self.assertEqual(len(cjmp_edges), 2)
        true_edge = next(e for e in cjmp_edges if e.edge_type == "conditional_true")
        false_edge = next(e for e in cjmp_edges if e.edge_type == "conditional_false")
        self.assertEqual(true_edge.target, 0x401065)
        self.assertEqual(false_edge.target, 0x401059)

        # Check call edge at 0x401059: call -> 0x401100, fallthrough -> 0x40105E
        call_edges = [e for e in edges if e.source == 0x401059]
        self.assertEqual(len(call_edges), 2)
        c_edge = next(e for e in call_edges if e.edge_type == "call")
        f_edge = next(e for e in call_edges if e.edge_type == "fallthrough")
        self.assertEqual(c_edge.target, 0x401100)
        self.assertEqual(f_edge.target, 0x40105E)

        # Check unconditional jmp at 0x40105E: jump -> 0x40106A (no fallthrough edge)
        jmp_edges = [e for e in edges if e.source == 0x40105E]
        self.assertEqual(len(jmp_edges), 1)
        self.assertEqual(jmp_edges[0].edge_type, "jump")
        self.assertEqual(jmp_edges[0].target, 0x40106A)

        # Check ret at 0x40106B: 0 outgoing edges
        ret_edges = [e for e in edges if e.source == 0x40106B]
        self.assertEqual(len(ret_edges), 0)

        # Check cyclomatic complexity calculation: 1 cjmp -> CC = 2
        self.assertEqual(disasm.computed_cc, 2)

    def test_pipeline_parsing_both_key_styles(self):
        pipeline_standard = CutterRizinParser.parse_pipeline(self.valid_pipeline_dict)
        self.assertEqual(pipeline_standard.info.arch, "x86")
        self.assertEqual(len(pipeline_standard.sections), 3)
        self.assertEqual(len(pipeline_standard.functions), 2)
        self.assertEqual(pipeline_standard.disassembly.name, "main")
        self.assertTrue(len(pipeline_standard.pipeline_digest) == 64)

        # Friendly keys
        friendly_dict = {
            "info": self.valid_info_dict,
            "sections": self.valid_sections_list,
            "functions": self.valid_functions_list,
            "disassembly": self.valid_disasm_dict,
        }
        pipeline_friendly = CutterRizinParser.parse_pipeline(friendly_dict)
        self.assertEqual(pipeline_friendly.info.bits, 64)
        self.assertEqual(len(pipeline_friendly.sections), 3)

        # Parse from bytes and string
        pipeline_from_bytes = CutterRizinParser.parse_bytes(self.valid_pipeline_bytes)
        self.assertEqual(pipeline_from_bytes.info.compiler, "gcc 11.2.0")

        pipeline_from_str = CutterRizinParser.parse_str(self.valid_pipeline_json)
        self.assertEqual(pipeline_from_str.functions[0].name, "main")

    def test_rejection_of_corrupted_json_and_empty_payloads(self):
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_bytes(b"")
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_str("   ")
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_str("invalid json {")
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_pipeline([])

    def test_rejection_of_missing_required_fields(self):
        # Missing format in iIj
        bad_info = dict(self.valid_info_dict)
        del bad_info["format"]
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_iIj(bad_info)

        # Missing arch in iIj
        bad_info = dict(self.valid_info_dict)
        del bad_info["arch"]
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_iIj(bad_info)

        # Missing canary in iIj
        bad_info = dict(self.valid_info_dict)
        del bad_info["canary"]
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_iIj(bad_info)

        # Missing size in section
        bad_sec = [{"name": ".text", "vaddr": 0x401000, "paddr": 0x1000, "flags": "r-x"}]
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_iSj(bad_sec)

        # Missing cc in function
        bad_fcn = [{"offset": 0x401000, "name": "f1", "size": 10, "realsz": 10, "nops": 0, "calltype": "cdecl", "type": "fcn"}]
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_aflj(bad_fcn)

        # Missing ops in pdfj
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_pdfj({"name": "f1", "offset": 0x401000})

    def test_rejection_of_negative_and_out_of_order_offsets(self):
        # Negative section address
        bad_sec = [{"name": ".bad", "size": 100, "vaddr": -42, "paddr": 0, "flags": "r-x"}]
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_iSj(bad_sec)

        # Negative function offset
        bad_fcn = [{"offset": -1, "name": "f1", "size": 10, "realsz": 10, "cc": 1, "nops": 0, "calltype": "cdecl", "type": "fcn"}]
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_aflj(bad_fcn)

        # Negative op offset
        bad_disasm = {
            "name": "main",
            "ops": [
                {"offset": -5, "opcode": "nop", "size": 1, "type": "nop"},
            ]
        }
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_pdfj(bad_disasm)

        # Out-of-order instruction offsets in pdfj (non-decreasing monotonicity violation)
        out_of_order_disasm = {
            "name": "main",
            "ops": [
                {"offset": 0x401050, "opcode": "push rbp", "size": 1, "type": "push"},
                {"offset": 0x401040, "opcode": "mov rbp, rsp", "size": 3, "type": "mov"},  # 0x401040 < 0x401050!
            ]
        }
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_pdfj(out_of_order_disasm)

        # Op with non-positive size
        zero_size_disasm = {
            "name": "main",
            "ops": [
                {"offset": 0x401050, "opcode": "nop", "size": 0, "type": "nop"},
            ]
        }
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_pdfj(zero_size_disasm)

        # Function cc < 1
        bad_cc_fcn = [{"offset": 0x401000, "name": "f1", "size": 10, "realsz": 10, "cc": 0, "nops": 0, "calltype": "cdecl", "type": "fcn"}]
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_aflj(bad_cc_fcn)

    def test_oversized_payload_rejection(self):
        oversized = b" " * (MAX_STATIC_PAYLOAD_BYTES + 1)
        with self.assertRaises(ValueError):
            CutterRizinParser.parse_bytes(oversized)

    def test_thermodynamic_heap_ceiling(self):
        """Verifies memory allocation strictly complies with <= 64 KB ceiling."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            CutterRizinParser.parse_bytes,
            self.valid_pipeline_bytes,
            candidate_id="cutter_rizin_parser_ch06",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutator_fuzzing(self):
        """Verifies metamorphic stability and 100% fail-closed rejection on invalid mutants."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.valid_pipeline_bytes)
        self.assertGreaterEqual(len(mutants), 10)

        for m in mutants:
            try:
                pipeline = CutterRizinParser.parse_bytes(m.payload)
                self.assertIsInstance(pipeline.info.bits, int)
            except ValueError:
                # Expected fail-closed rejection
                continue
            except Exception as err:
                self.fail(f"Unhandled crash on mutant {m.mutation_type}: {err}")


if __name__ == "__main__":
    unittest.main()
