"""Unit & Adversarial Verification Suite for Ninshū Native Diagnostics & Objdump Parser (CH 08).

Tests:
1. Valid objdump text parsing for x86_64, ARM, and RISC-V outputs.
2. Section header table parsing (.text, .data, .rodata, .bss, flags, alignment, VMA, LMA).
3. Function boundary and instruction sequence reconstruction.
4. Thermodynamic profiling (heap ceiling <= 64 KB).
5. Adversarial fuzz vectors: truncated lines, corrupt hex, massive input buffers, negative offsets.
6. 100% fail-closed rejection on invalid mutants.
"""
from __future__ import annotations

import io
import tracemalloc
import unittest

from kageyoni.ninshu.objdump_parser import (
    MAX_INPUT_BYTES,
    ObjdumpFunction,
    ObjdumpInstruction,
    ObjdumpParsedReport,
    ObjdumpParser,
    ObjdumpSection,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler

X86_64_OBJDUMP_SAMPLE = """
test_binary:     file format elf64-x86-64
architecture: i386:x86-64, flags 0x00000112:
EXEC_P, HAS_SYMS, D_PAGED
start address 0x0000000000401000

Sections:
Idx Name          Size      VMA               LMA               File off  Algn
  0 .text         00000020  0000000000401000  0000000000401000  00001000  2**4
                  CONTENTS, ALLOC, LOAD, READONLY, CODE
  1 .data         00000008  0000000000402000  0000000000402000  00002000  2**3
                  CONTENTS, ALLOC, LOAD, DATA
  2 .bss          00000010  0000000000403000  0000000000403000  00003000  2**4
                  ALLOC

Disassembly of section .text:

0000000000401000 <main>:
  401000:	55                   	push   %rbp
  401001:	48 89 e5             	mov    %rsp,%rbp
  401004:	b8 00 00 00 00       	mov    $0x0,%eax
  401009:	e8 02 00 00 00       	call   401010 <helper>
  40100e:	5d                   	pop    %rbp
  40100f:	c3                   	retq   

0000000000401010 <helper>:
  401010:	55                   	push   %rbp
  401011:	48 89 e5             	mov    %rsp,%rbp
  401014:	90                   	nop
  401015:	5d                   	pop    %rbp
  401016:	c3                   	retq   
"""

ARM_OBJDUMP_SAMPLE = """
arm_test:     file format elf32-littlearm
architecture: arm, flags 0x00000500:

Sections:
Idx Name          Size      VMA               LMA               File off  Algn
  0 .text         00000018  0000000000008000  0000000000008000  00008000  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, CODE

Disassembly of section .text:

00008000 <_start>:
    8000:	e3a00000 	mov	r0, #0
    8004:	e3a01001 	mov	r1, #1
    8008:	e0802001 	add	r2, r0, r1
    800c:	eb000001 	bl	8018 <arm_func>
    8010:	e1a0f00e 	mov	pc, lr

00008018 <arm_func>:
    8018:	e12fff1e 	bx	lr
"""

RISCV_OBJDUMP_SAMPLE = """
rv_test:     file format elf64-littleriscv
architecture: riscv:rv64, flags 0x00000005:

Sections:
Idx Name          Size      VMA               LMA               File off  Algn
  0 .text         00000014  00000000000101b0  00000000000101b0  000001b0  2**2
                  CONTENTS, ALLOC, LOAD, READONLY, CODE

Disassembly of section .text:

00000000000101b0 <_start>:
   101b0:	00000513          	li	a0,0
   101b4:	00050593          	addi	a1,a0,0
   101b8:	00000097          	auipc	ra,0x0
   101bc:	000080e7          	jalr	ra # 101b8 <_start+0x8>
   101c0:	00008067          	ret
"""


class TestNinshuObjdumpParser(unittest.TestCase):
    """Unit and adversarial test suite for ObjdumpParser."""

    def test_x86_64_parsing(self):
        """Test complete extraction of x86_64 objdump report."""
        report = ObjdumpParser.parse(X86_64_OBJDUMP_SAMPLE)
        self.assertIsInstance(report, ObjdumpParsedReport)
        self.assertIn("x86-64", report.architecture)
        self.assertIn("elf64-x86-64", report.file_format)
        self.assertEqual(len(report.sections), 3)

        # Check section headers
        text_sec = report.sections[0]
        self.assertEqual(text_sec.name, ".text")
        self.assertEqual(text_sec.size, 0x20)
        self.assertEqual(text_sec.vma, 0x401000)
        self.assertEqual(text_sec.file_offset, 0x1000)
        self.assertEqual(text_sec.alignment, 16)
        self.assertIn("CODE", text_sec.flags)

        data_sec = report.sections[1]
        self.assertEqual(data_sec.name, ".data")
        self.assertEqual(data_sec.size, 0x08)
        self.assertEqual(data_sec.vma, 0x402000)
        self.assertIn("DATA", data_sec.flags)

        # Check function boundaries
        self.assertEqual(len(report.functions), 2)
        f_main = report.functions[0]
        self.assertEqual(f_main.name, "main")
        self.assertEqual(f_main.address, 0x401000)
        self.assertEqual(len(f_main.instructions), 6)

        # Verify instruction details
        insn0 = f_main.instructions[0]
        self.assertEqual(insn0.address, 0x401000)
        self.assertEqual(insn0.raw_bytes, b"\x55")
        self.assertEqual(insn0.mnemonic, "push")
        self.assertEqual(insn0.operands, "%rbp")

        insn1 = f_main.instructions[1]
        self.assertEqual(insn1.raw_bytes, b"\x48\x89\xe5")
        self.assertEqual(insn1.mnemonic, "mov")
        self.assertEqual(insn1.operands, "%rsp,%rbp")

        insn_call = f_main.instructions[3]
        self.assertEqual(insn_call.mnemonic, "call")
        self.assertEqual(insn_call.comment, "helper")

        f_helper = report.functions[1]
        self.assertEqual(f_helper.name, "helper")
        self.assertEqual(f_helper.address, 0x401010)
        self.assertEqual(len(f_helper.instructions), 5)

        self.assertEqual(report.total_instructions, 11)
        self.assertTrue(len(report.digest) == 64)

    def test_arm_parsing(self):
        """Test ARM 32-bit objdump disassembly parsing."""
        report = ObjdumpParser.parse(ARM_OBJDUMP_SAMPLE)
        self.assertIn("arm", report.architecture.lower())
        self.assertEqual(len(report.sections), 1)
        self.assertEqual(len(report.functions), 2)

        start_func = report.functions[0]
        self.assertEqual(start_func.name, "_start")
        self.assertEqual(start_func.address, 0x8000)
        self.assertEqual(len(start_func.instructions), 5)

        insn_add = start_func.instructions[2]
        self.assertEqual(insn_add.address, 0x8008)
        self.assertEqual(insn_add.mnemonic, "add")
        self.assertEqual(insn_add.operands, "r2, r0, r1")
        self.assertEqual(insn_add.raw_bytes, bytes.fromhex("e0802001"))

    def test_riscv_parsing(self):
        """Test RISC-V 64-bit objdump disassembly parsing."""
        report = ObjdumpParser.parse(RISCV_OBJDUMP_SAMPLE)
        self.assertIn("riscv", report.architecture.lower())
        self.assertEqual(len(report.functions), 1)

        f = report.functions[0]
        self.assertEqual(f.name, "_start")
        self.assertEqual(f.address, 0x101b0)
        self.assertEqual(len(f.instructions), 5)

        insn_jalr = f.instructions[3]
        self.assertEqual(insn_jalr.mnemonic, "jalr")
        self.assertEqual(insn_jalr.operands, "ra")
        self.assertEqual(insn_jalr.comment, "101b8 <_start+0x8>")

    def test_bytes_input_support(self):
        """Verify binary bytes inputs decode and parse properly."""
        report = ObjdumpParser.parse(X86_64_OBJDUMP_SAMPLE.encode("utf-8"))
        self.assertIsInstance(report, ObjdumpParsedReport)
        self.assertEqual(report.total_instructions, 11)

    def test_fail_closed_on_empty_and_invalid(self):
        """Ensure fail-closed rejection on invalid or empty inputs."""
        # Empty string / None
        with self.assertRaises(ValueError):
            ObjdumpParser.parse("")

        with self.assertRaises(ValueError):
            ObjdumpParser.parse(b"")

        with self.assertRaises(ValueError):
            ObjdumpParser.parse(None)  # type: ignore

        # No objdump structure
        with self.assertRaises(ValueError):
            ObjdumpParser.parse("Hello world\nThis is not objdump output.")

    def test_fail_closed_on_oversized_payload(self):
        """Ensure payload exceeding MAX_INPUT_BYTES is rejected."""
        oversized = "A" * (MAX_INPUT_BYTES + 10)
        with self.assertRaises(ValueError):
            ObjdumpParser.parse(oversized)

    def test_fail_closed_on_corrupt_hex_addresses(self):
        """Ensure corrupted addresses or hex values fail closed."""
        # Malformed hex in instruction line
        bad_insn = "  40100Z:\t55\tpush %rbp\n"
        with self.assertRaises(ValueError):
            ObjdumpParser.parse(bad_insn)

        # Malformed function header
        bad_func = "000000000040100Z <main>:\n  401000:\t55\tpush %rbp\n"
        with self.assertRaises(ValueError):
            ObjdumpParser.parse(bad_func)

        # Odd length opcode
        bad_opcode = "  401000:\t5\tpush %rbp\n"
        with self.assertRaises(ValueError):
            ObjdumpParser.parse(bad_opcode)

    def test_thermodynamic_heap_ceiling(self):
        """Ensure peak heap memory during parsing is strictly <= 64 KB."""
        sample_bytes = X86_64_OBJDUMP_SAMPLE.encode("utf-8")
        report, receipt = ThermodynamicProfiler.profile_callable(
            ObjdumpParser.parse,
            sample_bytes,
            candidate_id="objdump_parser_ch08",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify that adversarial mutants either parse safely or fail cleanly with ValueError."""
        from kageyoni.ninshu.adversary import AdversarialMutator
        raw = X86_64_OBJDUMP_SAMPLE.encode("utf-8")
        mutants = AdversarialMutator.generate_adversarial_suite(raw)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                rep = ObjdumpParser.parse(m.payload)
                self.assertIsInstance(rep, ObjdumpParsedReport)
            except ValueError:
                pass
            except Exception as e:
                self.fail(f"Unhandled non-ValueError exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
