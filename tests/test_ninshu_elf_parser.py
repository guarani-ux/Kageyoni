"""Unit & Adversarial Verification Suite for Ninshū In-Tree ELF Parser (CH 02).

Tests:
1. Complete ELF64 Little-Endian binary header, segments, sections, and symbols (.symtab).
2. Complete ELF32 Big-Endian binary header (ARM/MIPS).
3. Section header string table name resolution (.text, .symtab, .strtab, .shstrtab).
4. Symbol resolution mapping names from .strtab via .symtab.
5. Fail-closed rejection on invalid magic, truncated headers, out-of-bounds offsets, and stride undersize.
6. Thermodynamic profiling (heap ceiling <= 64 KB).
7. Adversarial mutant fuzzing (bit flips, truncations).
"""
import io
import struct
import unittest

from kageyoni.ninshu.elf_parser import ElfBinaryParser, ELF_MAGIC
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuElfParser(unittest.TestCase):
    def setUp(self):
        # Construct synthetic valid ELF64 Little-Endian binary with .text, .shstrtab, .strtab, and .symtab
        ident = ELF_MAGIC + bytes([2, 1, 1, 0, 0]) + (b"\x00" * 7)

        # ELF64 Header (64 bytes total):
        # ehsize=64, phentsize=56, phnum=1, shentsize=64, shnum=4, shstrndx=1
        elf_hdr = struct.pack(
            "<HHIQQQIHHHHHH",
            2, 0x3E, 1, 0x401000, 64, 120, 0, 64, 56, 1, 64, 4, 1
        )

        # Program Header (56 bytes at offset 64):
        prog_hdr = struct.pack(
            "<IIQQQQQQ",
            1, 5, 0, 0x400000, 0x400000, 0x400, 0x400, 0x1000
        )

        # Section Header String Table (.shstrtab)
        # offset 0="", 1=".text", 7=".shstrtab", 17=".symtab", 25=".strtab"
        shstrtab = b"\x00.text\x00.shstrtab\x00.symtab\x00.strtab\x00"
        shstrtab_offset = 400

        # Symbol String Table (.strtab)
        # offset 0="", 1="main", 6="helper_func"
        strtab = b"\x00main\x00helper_func\x00"
        strtab_offset = 500

        # Symbol Table (.symtab, 2 entries of 24 bytes each = 48 bytes)
        # Symbol 0: null symbol
        sym0 = struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0)
        # Symbol 1: "main" (st_name=1, st_info=0x12 (FUNC/GLOBAL), st_other=0, st_shndx=0, st_value=0x401000, st_size=16)
        sym1 = struct.pack("<IBBHQQ", 1, 0x12, 0, 0, 0x401000, 16)
        symtab = sym0 + sym1
        symtab_offset = 600

        # Section 0: .text (sh_name=1, type=1 SHT_PROGBITS, flags=6 AX, addr=0x401000, offset=700, size=16)
        sec0 = struct.pack("<IIQQQQIIQQ", 1, 1, 6, 0x401000, 700, 16, 0, 0, 16, 0)

        # Section 1: .shstrtab (sh_name=7, type=3 SHT_STRTAB, flags=0, addr=0, offset=shstrtab_offset, size=len(shstrtab), link=0)
        sec1 = struct.pack("<IIQQQQIIQQ", 7, 3, 0, 0, shstrtab_offset, len(shstrtab), 0, 0, 1, 0)

        # Section 2: .symtab (sh_name=17, type=2 SHT_SYMTAB, flags=0, addr=0, offset=symtab_offset, size=len(symtab), link=3 (.strtab index), entsize=24)
        sec2 = struct.pack("<IIQQQQIIQQ", 17, 2, 0, 0, symtab_offset, len(symtab), 3, 1, 8, 24)

        # Section 3: .strtab (sh_name=25, type=3 SHT_STRTAB, flags=0, addr=0, offset=strtab_offset, size=len(strtab), link=0)
        sec3 = struct.pack("<IIQQQQIIQQ", 25, 3, 0, 0, strtab_offset, len(strtab), 0, 0, 1, 0)

        section_headers = sec0 + sec1 + sec2 + sec3  # 4 * 64 = 256 bytes (starts at 120, ends at 376)

        # Assemble full binary stream with paddings to offsets
        buf = bytearray(800)
        buf[0:64] = ident + elf_hdr
        buf[64:120] = prog_hdr
        buf[120:376] = section_headers
        buf[shstrtab_offset : shstrtab_offset + len(shstrtab)] = shstrtab
        buf[strtab_offset : strtab_offset + len(strtab)] = strtab
        buf[symtab_offset : symtab_offset + len(symtab)] = symtab
        buf[700:716] = b"\x90" * 16  # .text NOPs

        self.synthetic_elf64 = bytes(buf)

    def test_elf64_parsing_and_symbol_resolution(self):
        """Verify extraction of architecture, entrypoint, sections, and symbols."""
        summary = ElfBinaryParser.parse_bytes(self.synthetic_elf64)
        self.assertTrue(summary.is_64_bit)
        self.assertTrue(summary.is_little_endian)
        self.assertEqual(summary.machine, "x86-64")
        self.assertEqual(summary.elf_type, "ET_EXEC")
        self.assertEqual(summary.entrypoint, 0x401000)
        self.assertEqual(len(summary.segments), 1)
        self.assertEqual(len(summary.sections), 4)

        sec_names = [s.name for s in summary.sections]
        self.assertIn(".text", sec_names)
        self.assertIn(".shstrtab", sec_names)
        self.assertIn(".symtab", sec_names)
        self.assertIn(".strtab", sec_names)

        # Verify Symbol Table extraction & name resolution
        self.assertEqual(len(summary.symbols), 2)
        sym_names = [sym.name for sym in summary.symbols]
        self.assertIn("main", sym_names)
        main_sym = next(s for s in summary.symbols if s.name == "main")
        self.assertEqual(main_sym.value, 0x401000)
        self.assertEqual(main_sym.size, 16)

    def test_elf32_big_endian_header(self):
        """Verify parsing 32-bit Big-Endian ELF header (e.g. MIPS / PowerPC)."""
        ident32 = ELF_MAGIC + bytes([1, 2, 1, 0, 0]) + (b"\x00" * 7)
        hdr32 = struct.pack(
            ">HHIIIIIHHHHHH",
            2, 0x08, 1, 0x80000000, 0, 0, 0, 52, 32, 0, 40, 0, 0
        )
        data = ident32 + hdr32
        summary = ElfBinaryParser.parse_bytes(data)
        self.assertFalse(summary.is_64_bit)
        self.assertFalse(summary.is_little_endian)
        self.assertEqual(summary.machine, "MIPS")
        self.assertEqual(summary.entrypoint, 0x80000000)

    def test_fail_closed_on_corrupt_elf(self):
        """Verify fail-closed rejection on invalid magic or truncated headers."""
        with self.assertRaises(ValueError):
            ElfBinaryParser.parse_bytes(b"")

        # Wrong magic (e.g. MZ instead of \x7fELF)
        corrupt_magic = b"MZ\x00\x00" + (b"\x00" * 60)
        with self.assertRaises(ValueError):
            ElfBinaryParser.parse_bytes(corrupt_magic)

        # Truncated ELF header (< 52 bytes)
        with self.assertRaises(ValueError):
            ElfBinaryParser.parse_bytes(ELF_MAGIC + b"\x02\x01\x01\x00")

    def test_fail_closed_on_undersized_stride(self):
        """Verify rejection when e_phentsize or e_shentsize is smaller than required struct size."""
        # Corrupt e_shentsize to 10 (needs 64 for 64-bit)
        corrupt = bytearray(self.synthetic_elf64)
        # e_shentsize is at offset 58 in ELF64
        corrupt[58:60] = struct.pack("<H", 10)
        with self.assertRaises(ValueError):
            ElfBinaryParser.parse_bytes(bytes(corrupt))

    def test_thermodynamic_heap_ceiling(self):
        """Verify heap allocation stays strictly <= 64 KB."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            ElfBinaryParser.parse_bytes,
            self.synthetic_elf64,
            candidate_id="elf_parser_ch02",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify that adversarial mutants either parse safely or fail cleanly with ValueError."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.synthetic_elf64)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                summary = ElfBinaryParser.parse_bytes(m.payload)
                self.assertIsInstance(summary.total_bytes, int)
            except ValueError:
                pass
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
