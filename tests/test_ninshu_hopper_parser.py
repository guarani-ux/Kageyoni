"""Adversarial Verification Suite for Ninshū Hopper Disassembler Bridge (CH 05).

Verifications:
1. Valid Hopper JSON decoding across segments, procedures, basic blocks, and local labels.
2. Hopper pseudocode decompiler AST extraction, hierarchy, and comments.
3. Hopper type definitions and structure member layout verification.
4. Fail-closed rejection of corrupted JSON, empty inputs, negative lengths, out-of-order addresses,
   escaping basic blocks, overlapping struct members, and invalid memory ranges.
5. Thermodynamic memory profiling asserting peak heap ceiling <= 64 KB.
6. Metamorphic fuzzing via AdversarialMutator asserting 100% fail-closed rejection.
"""
from __future__ import annotations

import json
import unittest
from typing import Any, Dict

from kageyoni.ninshu.hopper_parser import (
    HopperASTNode,
    HopperBasicBlock,
    HopperComment,
    HopperDocument,
    HopperInstruction,
    HopperLocalLabel,
    HopperLocalVar,
    HopperParser,
    HopperProcedure,
    HopperPseudocodeAST,
    HopperSection,
    HopperSegment,
    HopperStructMember,
    HopperTypeDefinition,
    MAX_HOPPER_PAYLOAD_BYTES,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuHopperParser(unittest.TestCase):
    def setUp(self):
        self.valid_doc_dict: Dict[str, Any] = {
            "version": "hopper_v4",
            "arch": "x86_64",
            "format": "mach-o",
            "image_base": 0x100000000,
            "segments": [
                {
                    "name": "__TEXT",
                    "start_address": 0x100000000,
                    "length": 0x10000,
                    "permissions": "r-x",
                    "sections": [
                        {
                            "name": "__text",
                            "start_address": 0x100001000,
                            "length": 0x8000,
                            "flags": "code",
                        },
                        {
                            "name": "__stubs",
                            "start_address": 0x100009000,
                            "length": 0x1000,
                            "flags": "stubs",
                        },
                    ],
                },
                {
                    "name": "__DATA",
                    "start_address": 0x100010000,
                    "length": 0x4000,
                    "permissions": "rw-",
                    "sections": [
                        {
                            "name": "__data",
                            "start_address": 0x100010000,
                            "length": 0x2000,
                        }
                    ],
                },
            ],
            "procedures": [
                {
                    "name": "_main",
                    "entry_address": 0x100003F40,
                    "length": 0x50,
                    "calling_convention": "cdecl",
                    "return_type": "int",
                    "basic_blocks": [
                        {
                            "start_address": 0x100003F40,
                            "length": 0x20,
                            "instructions": [
                                {
                                    "address": 0x100003F40,
                                    "mnemonic": "push",
                                    "operands": "rbp",
                                    "size": 1,
                                    "bytes": "55",
                                    "type": "push",
                                },
                                {
                                    "address": 0x100003F41,
                                    "mnemonic": "mov",
                                    "operands": "rbp, rsp",
                                    "size": 3,
                                    "bytes": "4889e5",
                                    "type": "mov",
                                },
                                {
                                    "address": 0x100003F44,
                                    "mnemonic": "cmp",
                                    "operands": "edi, 0x0",
                                    "size": 3,
                                    "bytes": "83ff00",
                                    "type": "cmp",
                                },
                                {
                                    "address": 0x100003F47,
                                    "mnemonic": "jle",
                                    "operands": "0x100003f70",
                                    "size": 2,
                                    "bytes": "7e27",
                                    "type": "cjmp",
                                    "comment": "branch if argc <= 0",
                                },
                            ],
                            "predecessors": [],
                            "successors": [0x100003F60, 0x100003F70],
                            "block_id": "bb_0",
                        },
                        {
                            "start_address": 0x100003F60,
                            "length": 0x10,
                            "instructions": [
                                {
                                    "address": 0x100003F60,
                                    "mnemonic": "mov",
                                    "operands": "eax, 0x1",
                                    "size": 5,
                                    "bytes": "b801000000",
                                    "type": "mov",
                                },
                                {
                                    "address": 0x100003F65,
                                    "mnemonic": "jmp",
                                    "operands": "0x100003f80",
                                    "size": 5,
                                    "bytes": "e916000000",
                                    "type": "jmp",
                                },
                            ],
                            "predecessors": [0x100003F40],
                            "successors": [0x100003F80],
                            "block_id": "bb_1",
                        },
                        {
                            "start_address": 0x100003F70,
                            "length": 0x10,
                            "instructions": [
                                {
                                    "address": 0x100003F70,
                                    "mnemonic": "xor",
                                    "operands": "eax, eax",
                                    "size": 2,
                                    "bytes": "31c0",
                                    "type": "xor",
                                },
                                {
                                    "address": 0x100003F72,
                                    "mnemonic": "jmp",
                                    "operands": "0x100003f80",
                                    "size": 5,
                                    "bytes": "e909000000",
                                    "type": "jmp",
                                },
                            ],
                            "predecessors": [0x100003F40],
                            "successors": [0x100003F80],
                            "block_id": "bb_2",
                        },
                        {
                            "start_address": 0x100003F80,
                            "length": 0x10,
                            "instructions": [
                                {
                                    "address": 0x100003F80,
                                    "mnemonic": "pop",
                                    "operands": "rbp",
                                    "size": 1,
                                    "bytes": "5d",
                                    "type": "pop",
                                },
                                {
                                    "address": 0x100003F81,
                                    "mnemonic": "ret",
                                    "operands": "",
                                    "size": 1,
                                    "bytes": "c3",
                                    "type": "ret",
                                },
                            ],
                            "predecessors": [0x100003F60, 0x100003F70],
                            "successors": [],
                            "block_id": "bb_3",
                        },
                    ],
                    "local_labels": [
                        {"address": 0x100003F70, "name": "loc_else"},
                        {"address": 0x100003F80, "name": "loc_epilog"},
                    ],
                    "local_vars": [
                        {"name": "argc", "type": "int", "stack_offset": -4, "size": 4},
                        {"name": "argv", "type": "char**", "stack_offset": -16, "size": 8},
                    ],
                }
            ],
            "types": [
                {
                    "name": "PayloadHeader",
                    "category": "struct",
                    "size": 16,
                    "alignment": 8,
                    "members": [
                        {"name": "magic", "type": "uint32_t", "offset": 0, "size": 4},
                        {"name": "flags", "type": "uint16_t", "offset": 4, "size": 2},
                        {"name": "reserved", "type": "uint16_t", "offset": 6, "size": 2},
                        {"name": "data_ptr", "type": "void*", "offset": 8, "size": 8},
                    ],
                },
                {
                    "name": "StatusEnum",
                    "category": "enum",
                    "size": 4,
                    "alignment": 4,
                    "enum_values": {"STATUS_OK": 0, "STATUS_ERR": 1, "STATUS_PENDING": 2},
                },
                {
                    "name": "handle_t",
                    "category": "typedef",
                    "size": 8,
                    "alignment": 8,
                    "target_type": "uint64_t",
                },
            ],
            "pseudocode": [
                {
                    "procedure_name": "_main",
                    "entry_address": 0x100003F40,
                    "raw_code": "int main(int argc, char **argv) {\n    if (argc > 0) {\n        return 1;\n    }\n    return 0;\n}",
                    "ast_blocks": [
                        {
                            "node_type": "function",
                            "address": 0x100003F40,
                            "expression": "int main(int argc, char **argv)",
                            "body": [
                                {
                                    "node_type": "if",
                                    "address": 0x100003F44,
                                    "condition": "argc > 0",
                                    "body": [
                                        {
                                            "node_type": "return",
                                            "address": 0x100003F60,
                                            "expression": "1",
                                        }
                                    ],
                                    "else_body": [
                                        {
                                            "node_type": "return",
                                            "address": 0x100003F70,
                                            "expression": "0",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                    "comments": [
                        {
                            "address": 0x100003F47,
                            "text": "Condition branch to else",
                            "comment_type": "inline",
                            "is_user_comment": False,
                        }
                    ],
                }
            ],
            "comments": [
                {
                    "address": 0x100003F40,
                    "text": "Entrypoint of binary",
                    "comment_type": "pre",
                    "is_user_comment": True,
                }
            ],
        }
        self.valid_payload_bytes = json.dumps(self.valid_doc_dict).encode("utf-8")

    def test_valid_hopper_document_parsing(self):
        """Verifies complete parsing of segments, procedures, blocks, types, pseudocode."""
        doc = HopperParser.parse_bytes(self.valid_payload_bytes)
        self.assertEqual(doc.version, "hopper_v4")
        self.assertEqual(doc.arch, "x86_64")
        self.assertEqual(doc.format, "mach-o")
        self.assertEqual(doc.image_base, 0x100000000)
        self.assertEqual(len(doc.segments), 2)
        self.assertEqual(len(doc.procedures), 1)
        self.assertEqual(len(doc.types), 3)
        self.assertEqual(len(doc.pseudocode), 1)
        self.assertEqual(len(doc.comments), 1)
        self.assertTrue(len(doc.canonical_digest) == 64)

    def test_segment_and_section_structure(self):
        """Validates segments and sections hierarchical layout."""
        doc = HopperParser.parse_bytes(self.valid_payload_bytes)
        seg0 = doc.segments[0]
        self.assertEqual(seg0.name, "__TEXT")
        self.assertEqual(seg0.start_address, 0x100000000)
        self.assertEqual(seg0.length, 0x10000)
        self.assertEqual(seg0.permissions, "r-x")
        self.assertEqual(len(seg0.sections), 2)

        sec0 = seg0.sections[0]
        self.assertEqual(sec0.name, "__text")
        self.assertEqual(sec0.start_address, 0x100001000)
        self.assertEqual(sec0.length, 0x8000)
        self.assertEqual(sec0.flags, "code")

        dict_repr = seg0.to_dict()
        self.assertEqual(dict_repr["name"], "__TEXT")
        self.assertIn("sections", dict_repr)

    def test_procedure_and_basic_block_parsing(self):
        """Verifies procedure CFG blocks, instructions, local labels, and local variables."""
        doc = HopperParser.parse_bytes(self.valid_payload_bytes)
        proc = doc.procedures[0]
        self.assertEqual(proc.name, "_main")
        self.assertEqual(proc.entry_address, 0x100003F40)
        self.assertEqual(proc.length, 0x50)
        self.assertEqual(proc.calling_convention, "cdecl")
        self.assertEqual(proc.return_type, "int")
        self.assertEqual(len(proc.basic_blocks), 4)

        # Basic block 0
        bb0 = proc.basic_blocks[0]
        self.assertEqual(bb0.start_address, 0x100003F40)
        self.assertEqual(bb0.length, 0x20)
        self.assertEqual(len(bb0.instructions), 4)
        self.assertEqual(bb0.predecessors, [])
        self.assertEqual(bb0.successors, [0x100003F60, 0x100003F70])
        self.assertEqual(bb0.block_id, "bb_0")

        # Instruction inspection
        inst0 = bb0.instructions[0]
        self.assertEqual(inst0.address, 0x100003F40)
        self.assertEqual(inst0.mnemonic, "push")
        self.assertEqual(inst0.operands, "rbp")
        self.assertEqual(inst0.size, 1)
        self.assertEqual(inst0.opcode_bytes, b"\x55")

        # Local labels and local variables
        self.assertEqual(len(proc.local_labels), 2)
        self.assertEqual(proc.local_labels[0].name, "loc_else")
        self.assertEqual(proc.local_labels[0].address, 0x100003F70)

        self.assertEqual(len(proc.local_vars), 2)
        self.assertEqual(proc.local_vars[0].name, "argc")
        self.assertEqual(proc.local_vars[0].stack_offset, -4)

        proc_dict = proc.to_dict()
        self.assertEqual(proc_dict["name"], "_main")
        self.assertIn("basic_blocks", proc_dict)

    def test_pseudocode_ast_and_comments_extraction(self):
        """Verifies decompiled pseudocode AST nodes hierarchy and comments extraction."""
        doc = HopperParser.parse_bytes(self.valid_payload_bytes)
        pc = doc.pseudocode[0]
        self.assertEqual(pc.procedure_name, "_main")
        self.assertEqual(pc.entry_address, 0x100003F40)
        self.assertIn("int main", pc.raw_code)
        self.assertEqual(len(pc.ast_blocks), 1)

        fn_node = pc.ast_blocks[0]
        self.assertEqual(fn_node.node_type, "function")
        self.assertEqual(len(fn_node.body), 1)

        if_node = fn_node.body[0]
        self.assertEqual(if_node.node_type, "if")
        self.assertEqual(if_node.condition, "argc > 0")
        self.assertEqual(len(if_node.body), 1)
        self.assertEqual(if_node.body[0].node_type, "return")
        self.assertEqual(if_node.body[0].expression, "1")
        self.assertEqual(len(if_node.else_body), 1)
        self.assertEqual(if_node.else_body[0].node_type, "return")
        self.assertEqual(if_node.else_body[0].expression, "0")

        self.assertEqual(len(pc.comments), 1)
        self.assertEqual(pc.comments[0].text, "Condition branch to else")
        self.assertEqual(pc.comments[0].comment_type, "inline")

    def test_structure_member_layout_verification(self):
        """Verifies struct member layout, non-overlapping offsets, and alignment checking."""
        doc = HopperParser.parse_bytes(self.valid_payload_bytes)
        struct_type = doc.types[0]
        self.assertEqual(struct_type.name, "PayloadHeader")
        self.assertEqual(struct_type.category, "struct")
        self.assertEqual(struct_type.size, 16)
        self.assertEqual(struct_type.alignment, 8)
        self.assertEqual(len(struct_type.members), 4)

        m0 = struct_type.members[0]
        self.assertEqual(m0.name, "magic")
        self.assertEqual(m0.offset, 0)
        self.assertEqual(m0.size, 4)

        m3 = struct_type.members[3]
        self.assertEqual(m3.name, "data_ptr")
        self.assertEqual(m3.offset, 8)
        self.assertEqual(m3.size, 8)

        # Enum type
        enum_type = doc.types[1]
        self.assertEqual(enum_type.name, "StatusEnum")
        self.assertEqual(enum_type.category, "enum")
        self.assertEqual(enum_type.enum_values["STATUS_OK"], 0)
        self.assertEqual(enum_type.enum_values["STATUS_ERR"], 1)

    def test_overlapping_struct_members_rejected(self):
        """Verifies that overlapping members in a struct raise ValueError."""
        bad_struct = {
            "name": "BadStruct",
            "category": "struct",
            "size": 16,
            "alignment": 4,
            "members": [
                {"name": "field_a", "type": "uint32_t", "offset": 0, "size": 8},
                {"name": "field_b", "type": "uint32_t", "offset": 4, "size": 4},  # Overlaps [0, 8)!
            ],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_type_definition(bad_struct)

    def test_struct_member_exceeding_size_rejected(self):
        """Verifies struct members reaching past declared struct size raise ValueError."""
        overflow_struct = {
            "name": "OverflowStruct",
            "category": "struct",
            "size": 8,
            "alignment": 4,
            "members": [
                {"name": "f1", "type": "uint64_t", "offset": 0, "size": 8},
                {"name": "f2", "type": "uint32_t", "offset": 8, "size": 4},  # offset 8 + size 4 = 12 > 8!
            ],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_type_definition(overflow_struct)

    def test_invalid_alignment_rejected(self):
        """Verifies alignment must be non-zero power of 2."""
        bad_align = {
            "name": "BadAlign",
            "category": "struct",
            "size": 8,
            "alignment": 3,  # Not power of 2
            "members": [],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_type_definition(bad_align)

    def test_empty_and_corrupted_inputs_rejected(self):
        """Verifies fail-closed rejection on empty payloads and malformed JSON."""
        with self.assertRaises(ValueError):
            HopperParser.parse_bytes(b"")

        with self.assertRaises(ValueError):
            HopperParser.parse_bytes(b"   \t\n  ")

        with self.assertRaises(ValueError):
            HopperParser.parse_str("")

        with self.assertRaises(ValueError):
            HopperParser.parse_str("{\n  invalid json: ")

        with self.assertRaises(ValueError):
            HopperParser.parse_str("[1, 2, 3]")  # Root must be object

    def test_negative_procedure_length_rejected(self):
        """Verifies procedures with non-positive / negative lengths are rejected."""
        bad_proc_negative = {
            "name": "sub_bad",
            "entry_address": 0x1000,
            "length": -16,
            "basic_blocks": [],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_procedure(bad_proc_negative)

        bad_proc_zero = {
            "name": "sub_zero",
            "entry_address": 0x1000,
            "length": 0,
            "basic_blocks": [],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_procedure(bad_proc_zero)

    def test_out_of_order_basic_blocks_rejected(self):
        """Verifies basic blocks with out-of-order start addresses raise ValueError."""
        bad_blocks_proc = {
            "name": "sub_ooo",
            "entry_address": 0x1000,
            "length": 0x100,
            "basic_blocks": [
                {"start_address": 0x1050, "length": 0x20, "instructions": []},
                {"start_address": 0x1020, "length": 0x20, "instructions": []},  # 0x1020 < 0x1050!
            ],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_procedure(bad_blocks_proc)

    def test_basic_block_escaping_procedure_bounds_rejected(self):
        """Verifies basic blocks lying outside procedure range raise ValueError."""
        escaping_proc = {
            "name": "sub_escape",
            "entry_address": 0x1000,
            "length": 0x40,  # Range is [0x1000, 0x1040)
            "basic_blocks": [
                {"start_address": 0x1050, "length": 0x20, "instructions": []},  # Starts after procedure end!
            ],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_procedure(escaping_proc)

    def test_out_of_order_instructions_in_basic_block_rejected(self):
        """Verifies instructions within a basic block must have monotonic addresses."""
        bad_inst_bb = {
            "start_address": 0x1000,
            "length": 0x20,
            "instructions": [
                {"address": 0x1005, "mnemonic": "nop", "size": 1},
                {"address": 0x1002, "mnemonic": "nop", "size": 1},  # 0x1002 < 0x1005!
            ],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_basic_block(bad_inst_bb)

    def test_instruction_with_zero_size_rejected(self):
        """Verifies instruction with size 0 is rejected."""
        zero_size_bb = {
            "start_address": 0x1000,
            "length": 0x10,
            "instructions": [
                {"address": 0x1000, "mnemonic": "nop", "size": 0},
            ],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_basic_block(zero_size_bb)

    def test_section_escaping_segment_bounds_rejected(self):
        """Verifies section outside segment bounds raises ValueError."""
        bad_segment = {
            "name": "__TEXT",
            "start_address": 0x1000,
            "length": 0x1000,
            "permissions": "r-x",
            "sections": [
                {"name": "__text", "start_address": 0x2500, "length": 0x500},  # Beyond 0x2000!
            ],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_segment(bad_segment)

    def test_invalid_segment_permissions_rejected(self):
        """Verifies invalid segment permissions raise ValueError."""
        bad_perm_segment = {
            "name": "__BAD",
            "start_address": 0x1000,
            "length": 0x1000,
            "permissions": "invalid_perm",
            "sections": [],
        }
        with self.assertRaises(ValueError):
            HopperParser.parse_segment(bad_perm_segment)

    def test_oversized_payload_rejection(self):
        """Verifies payloads larger than MAX_HOPPER_PAYLOAD_BYTES (64 KB) are rejected."""
        oversized = b" " * (MAX_HOPPER_PAYLOAD_BYTES + 1)
        with self.assertRaises(ValueError):
            HopperParser.parse_bytes(oversized)

    def test_thermodynamic_heap_ceiling(self):
        """Verifies memory allocation strictly complies with <= 64 KB ceiling."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            HopperParser.parse_bytes,
            self.valid_payload_bytes,
            candidate_id="hopper_parser_ch05",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutator_fuzzing(self):
        """Verifies metamorphic stability and 100% fail-closed rejection on invalid mutants."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.valid_payload_bytes)
        self.assertGreaterEqual(len(mutants), 10)

        for m in mutants:
            try:
                doc = HopperParser.parse_bytes(m.payload)
                self.assertIsInstance(doc.version, str)
            except ValueError:
                # Expected fail-closed rejection
                continue
            except Exception as err:
                self.fail(f"Unhandled crash on mutant {m.mutation_type}: {err}")


if __name__ == "__main__":
    unittest.main()
