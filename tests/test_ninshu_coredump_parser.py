"""Adversarial and Mechanical Verification Suite for ELF Core Dump Parser (CH 19).

Tests:
1. Complete ELF64 Little-Endian core dump: headers, PT_NOTE, PT_LOAD, NT_PRSTATUS, NT_PRPSINFO, NT_AUXV, NT_FILE.
2. Complete ELF32 Little-Endian core dump (x86 32-bit).
3. Faulting crash signal extraction, registers inspection (RIP/EIP, RSP/ESP, RBP/EBP, RAX, etc.).
4. Fail-closed rejection: invalid ELF magic, non-ET_CORE types, truncated headers, corrupted note sizes.
5. Fail-closed rejection on corrupted and truncated note descriptors (NT_PRSTATUS, NT_PRPSINFO, NT_FILE).
6. Thermodynamic memory ceiling evaluation (assert peak heap <= 64 KB via ThermodynamicProfiler).
7. Adversarial mutant fuzzing (bit flips, truncations, boundary overflows).
"""
from __future__ import annotations

import struct
import tracemalloc
import unittest

from kageyoni.ninshu.coredump_parser import (
    ELF_MAGIC,
    ET_CORE,
    CoreDumpBuilder,
    CoreDumpParser,
    ElfCoreDump,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuCoreDumpParser(unittest.TestCase):
    """Rigorous test suite for Channel 19 GDB / Pwndbg Core Dump Inspector."""

    def setUp(self) -> None:
        self.synthetic_elf64 = CoreDumpBuilder.build_elf64_core(
            signal=11,  # SIGSEGV
            pid=1337,
            ppid=1,
            fname="vulnerable_srv",
            psargs="./vulnerable_srv --port 8080",
            rip=0x401050,
            rsp=0x7FFFFFFFE000,
            rbp=0x7FFFFFFFE080,
            rax=0xDEADBEEF,
            rbx=0xCAFEBABE,
            rcx=0x100,
            rdx=0x200,
            rsi=0x300,
            rdi=0x400,
            auxv={
                3: 0x400040,       # AT_PHDR
                4: 56,             # AT_PHENT
                5: 4,              # AT_PHNUM
                6: 4096,           # AT_PAGESZ
                7: 0x7FFFF7DD5000, # AT_BASE
                9: 0x401050,       # AT_ENTRY
            },
            mapped_files=[
                (0x400000, 0x401000, 0, "/usr/bin/vulnerable_srv"),
                (0x7FFFF7DD5000, 0x7FFFF7DF5000, 0, "/lib/x86_64-linux-gnu/libc.so.6"),
            ],
            load_segments=[
                (0x400000, 0x400000, b"\x90\x90\x90\xcc" * 16, 5),  # R-X
                (0x7FFFFFFFE000, 0x7FFFFFFFE000, b"\x41" * 64, 6),   # RW-
            ],
        )

        self.synthetic_elf32 = CoreDumpBuilder.build_elf32_core(
            signal=6,  # SIGABRT
            pid=4242,
            ppid=1,
            fname="crash32",
            psargs="./crash32",
            eip=0x08048400,
            esp=0xBFFFF000,
            ebp=0xBFFFF040,
            eax=0x11111111,
            ebx=0x22222222,
            ecx=0x33333333,
            edx=0x44444444,
            esi=0x55555555,
            edi=0x66666666,
        )

    def test_elf64_core_dump_parsing(self) -> None:
        """Verify full structural parsing and register inspection for 64-bit ELF core dump."""
        core = CoreDumpParser.parse_bytes(self.synthetic_elf64)

        self.assertTrue(core.is_64_bit)
        self.assertTrue(core.is_little_endian)
        self.assertEqual(core.machine, "x86-64")
        self.assertEqual(core.entrypoint, 0x401050)
        self.assertGreater(core.total_bytes, 0)
        self.assertEqual(len(core.sha256), 64)

        # PRSTATUS inspection
        self.assertIsNotNone(core.prstatus)
        prstatus = core.prstatus
        self.assertEqual(prstatus.signal, 11)
        self.assertEqual(prstatus.signal_name, "SIGSEGV")
        self.assertEqual(prstatus.pid, 1337)
        self.assertEqual(prstatus.ppid, 1)

        # Registers extraction
        regs = prstatus.registers
        self.assertIsNotNone(regs)
        self.assertEqual(regs.rip, 0x401050)
        self.assertEqual(regs.eip, 0x401050)
        self.assertEqual(regs.rsp, 0x7FFFFFFFE000)
        self.assertEqual(regs.esp, 0xFFFFE000)
        self.assertEqual(regs.rbp, 0x7FFFFFFFE080)
        self.assertEqual(regs.rax, 0xDEADBEEF)
        self.assertEqual(regs.rbx, 0xCAFEBABE)
        self.assertEqual(regs.rcx, 0x100)
        self.assertEqual(regs.rdx, 0x200)
        self.assertEqual(regs.rsi, 0x300)
        self.assertEqual(regs.rdi, 0x400)

        # PRPSINFO inspection
        self.assertIsNotNone(core.prpsinfo)
        prpsinfo = core.prpsinfo
        self.assertEqual(prpsinfo.fname, "vulnerable_srv")
        self.assertEqual(prpsinfo.psargs, "./vulnerable_srv --port 8080")
        self.assertEqual(prpsinfo.state, 0)
        self.assertEqual(prpsinfo.state_name, "RUNNING")
        self.assertEqual(prpsinfo.uid, 1000)
        self.assertEqual(prpsinfo.gid, 1000)

        # AUXV inspection
        self.assertEqual(core.auxv_named.get("AT_ENTRY"), 0x401050)
        self.assertEqual(core.auxv_named.get("AT_PAGESZ"), 4096)
        self.assertEqual(core.auxv_named.get("AT_BASE"), 0x7FFFF7DD5000)
        self.assertEqual(core.auxv_named.get("AT_PHDR"), 0x400040)

        # Mapped files (NT_FILE)
        self.assertEqual(len(core.mapped_files), 2)
        self.assertEqual(core.mapped_files[0].path, "/usr/bin/vulnerable_srv")
        self.assertEqual(core.mapped_files[0].vm_start, 0x400000)
        self.assertEqual(core.mapped_files[0].vm_end, 0x401000)
        self.assertEqual(core.mapped_files[1].path, "/lib/x86_64-linux-gnu/libc.so.6")

        # Memory segments (PT_LOAD)
        self.assertEqual(len(core.load_segments), 2)
        code_seg = core.load_segments[0]
        self.assertEqual(code_seg.vaddr, 0x400000)
        self.assertTrue(code_seg.is_readable)
        self.assertFalse(code_seg.is_writable)
        self.assertTrue(code_seg.is_executable)
        self.assertEqual(code_seg.permissions, "r-x")

        # Memory read verification
        mem_bytes = core.read_memory(0x400000, 8)
        self.assertEqual(mem_bytes, b"\x90\x90\x90\xcc\x90\x90\x90\xcc")

        # Dissect crash diagnostics
        diagnostics = core.dissect_crash()
        self.assertEqual(diagnostics["signal_name"], "SIGSEGV")
        self.assertEqual(diagnostics["signal_number"], 11)
        self.assertEqual(diagnostics["pid"], 1337)
        self.assertEqual(diagnostics["program_counter"], "0x401050")
        self.assertEqual(diagnostics["executable"], "vulnerable_srv")

        # JSON serialization
        json_repr = core.to_json()
        self.assertIn("SIGSEGV", json_repr)
        self.assertIn("vulnerable_srv", json_repr)

    def test_elf32_core_dump_parsing(self) -> None:
        """Verify 32-bit ELF core dump parsing and register extraction."""
        core = CoreDumpParser.parse_bytes(self.synthetic_elf32)

        self.assertFalse(core.is_64_bit)
        self.assertTrue(core.is_little_endian)
        self.assertEqual(core.machine, "x86")
        self.assertEqual(core.entrypoint, 0x08048400)

        self.assertIsNotNone(core.prstatus)
        prstatus = core.prstatus
        self.assertEqual(prstatus.signal, 6)
        self.assertEqual(prstatus.signal_name, "SIGABRT")
        self.assertEqual(prstatus.pid, 4242)

        regs = prstatus.registers
        self.assertIsNotNone(regs)
        self.assertEqual(regs.eip, 0x08048400)
        self.assertEqual(regs.esp, 0xBFFFF000)
        self.assertEqual(regs.ebp, 0xBFFFF040)
        self.assertEqual(regs.eax, 0x11111111)
        self.assertEqual(regs.ebx, 0x22222222)
        self.assertEqual(regs.ecx, 0x33333333)

        self.assertIsNotNone(core.prpsinfo)
        self.assertEqual(core.prpsinfo.fname, "crash32")
        self.assertEqual(core.prpsinfo.pid, 4242)

    def test_fail_closed_on_corrupt_elf_magic(self) -> None:
        """Verify fail-closed rejection on invalid magic signature."""
        with self.assertRaises(ValueError):
            CoreDumpParser.parse_bytes(b"")

        with self.assertRaises(ValueError):
            CoreDumpParser.parse_bytes(b"MZ\x90\x00" + (b"\x00" * 60))

        with self.assertRaises(ValueError):
            CoreDumpParser.parse_bytes(b"\x00asm\x01\x00\x00\x00" + (b"\x00" * 56))

    def test_fail_closed_on_non_core_elf(self) -> None:
        """Verify rejection when ELF type is not ET_CORE (e_type != 4)."""
        # Change e_type from ET_CORE (4) to ET_EXEC (2) at offset 16
        corrupt = bytearray(self.synthetic_elf64)
        struct.pack_into("<H", corrupt, 16, 2)
        with self.assertRaises(ValueError) as ctx:
            CoreDumpParser.parse_bytes(bytes(corrupt))
        self.assertIn("Not an ELF core dump", str(ctx.exception))

    def test_fail_closed_on_truncated_header(self) -> None:
        """Verify rejection when ELF header is truncated."""
        for length in (0, 8, 16, 32, 51, 63):
            with self.assertRaises(ValueError):
                CoreDumpParser.parse_bytes(self.synthetic_elf64[:length])

    def test_fail_closed_on_corrupted_stride_and_offsets(self) -> None:
        """Verify rejection when program header stride is smaller than required struct."""
        corrupt = bytearray(self.synthetic_elf64)
        # e_phentsize is at offset 54 in ELF64
        struct.pack_into("<H", corrupt, 54, 20)  # requires 56
        with self.assertRaises(ValueError) as ctx:
            CoreDumpParser.parse_bytes(bytes(corrupt))
        self.assertIn("Undersized program header stride", str(ctx.exception))

        # Program header offset exceeding file bounds
        corrupt_phoff = bytearray(self.synthetic_elf64)
        struct.pack_into("<Q", corrupt_phoff, 32, 0x10000000)
        with self.assertRaises(ValueError) as ctx:
            CoreDumpParser.parse_bytes(bytes(corrupt_phoff))
        self.assertIn("exceeds file size", str(ctx.exception))

    def test_fail_closed_on_corrupted_notes(self) -> None:
        """Verify rejection on corrupted note descriptors and out-of-bounds lengths."""
        # Find PT_NOTE segment offset
        core = CoreDumpParser.parse_bytes(self.synthetic_elf64)
        note_off = core.notes[0].offset

        # Corrupted namesz to oversized value
        corrupt_namesz = bytearray(self.synthetic_elf64)
        struct.pack_into("<I", corrupt_namesz, note_off, 0x7FFFFFFF)
        with self.assertRaises(ValueError) as ctx:
            CoreDumpParser.parse_bytes(bytes(corrupt_namesz))
        self.assertIn("Corrupted note lengths", str(ctx.exception))

        # Corrupted descsz to oversized value
        corrupt_descsz = bytearray(self.synthetic_elf64)
        struct.pack_into("<I", corrupt_descsz, note_off + 4, 0x7FFFFFFF)
        with self.assertRaises(ValueError) as ctx:
            CoreDumpParser.parse_bytes(bytes(corrupt_descsz))
        self.assertIn("Corrupted note lengths", str(ctx.exception))

    def test_fail_closed_on_truncated_prstatus(self) -> None:
        """Verify rejection when NT_PRSTATUS descriptor is truncated."""
        # Synthesize core dump with truncated PRSTATUS (< 112 bytes)
        core_bytes = CoreDumpBuilder.build_elf64_core()
        # Locate NT_PRSTATUS note offset
        parsed = CoreDumpParser.parse_bytes(core_bytes)
        prstatus_note = next(n for n in parsed.notes if n.note_type == 1)

        corrupt = bytearray(core_bytes)
        # Change descsz of PRSTATUS from 336 to 40 bytes
        struct.pack_into("<I", corrupt, prstatus_note.offset + 4, 40)
        with self.assertRaises(ValueError) as ctx:
            CoreDumpParser.parse_bytes(bytes(corrupt))
        self.assertIn("NT_PRSTATUS descriptor truncated", str(ctx.exception))

    def test_thermodynamic_heap_ceiling(self) -> None:
        """Verify peak memory consumption is strictly within <= 64 KB ceiling."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            CoreDumpParser.parse_bytes,
            self.synthetic_elf64,
            candidate_id="coredump_parser_ch19",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

        # Tracemalloc secondary confirmation
        tracemalloc.start()
        try:
            parsed = CoreDumpParser.parse_bytes(self.synthetic_elf64)
            current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertIsNotNone(parsed.prstatus)
        self.assertLessEqual(peak, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self) -> None:
        """Verify fail-closed discrimination on deterministic adversarial mutants."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.synthetic_elf64)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                dump = CoreDumpParser.parse_bytes(m.payload)
                self.assertIsInstance(dump.total_bytes, int)
            except ValueError:
                continue
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
