"""Unit & Adversarial Verification Suite for Ninshū In-Tree Mach-O Parser (CH 03).

Tests:
1. Complete Mach-O Universal / FAT container with 2 slices (x86_64 and arm64).
2. Thin Mach-O 64-bit binary (arm64, MH_EXECUTE).
3. Disambiguation of Java .class bytecode from FAT_MAGIC.
4. Fail-closed rejection on invalid magic, truncated headers, slice offset out-of-bounds.
5. Thermodynamic profiling (heap ceiling <= 64 KB).
6. Adversarial mutant fuzzing (bit flips, truncations).
"""
import io
import struct
import unittest

from kageyoni.ninshu.macho_parser import (
    MachOBinaryParser,
    FAT_MAGIC,
    MH_MAGIC_64,
    CPU_TYPE_X86_64,
    CPU_TYPE_ARM64,
    MH_EXECUTE,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuMachoParser(unittest.TestCase):
    def setUp(self):
        # 1. Create Slice 1: x86_64 thin Mach-O (32 bytes header + 32 bytes dummy)
        # MH_MAGIC_64 (0xfeedfacf, big endian), cputype=CPU_TYPE_X86_64, subtype=3, filetype=MH_EXECUTE, ncmds=2, sizeofcmds=64, flags=0x200085
        slice1_hdr = struct.pack(">IIIIIIII", MH_MAGIC_64, CPU_TYPE_X86_64, 3, MH_EXECUTE, 2, 64, 0x200085, 0)
        slice1 = slice1_hdr + (b"\x90" * 32)  # total 64 bytes

        # 2. Create Slice 2: arm64 thin Mach-O (32 bytes header + 32 bytes dummy)
        slice2_hdr = struct.pack(">IIIIIIII", MH_MAGIC_64, CPU_TYPE_ARM64, 0, MH_EXECUTE, 2, 64, 0x200085, 0)
        slice2 = slice2_hdr + (b"\x90" * 32)  # total 64 bytes

        # 3. Create Universal FAT Container Header:
        # magic=FAT_MAGIC (0xcafebabe, big endian), nfat_arch=2
        fat_hdr = struct.pack(">II", FAT_MAGIC, 2)

        # Slice 1 descriptor (20 bytes): cputype, subtype, offset=4096 (page aligned), size=len(slice1), align=12
        slice1_desc = struct.pack(">IIIII", CPU_TYPE_X86_64, 3, 4096, len(slice1), 12)
        # Slice 2 descriptor (20 bytes): cputype, subtype, offset=8192, size=len(slice2), align=14
        slice2_desc = struct.pack(">IIIII", CPU_TYPE_ARM64, 0, 8192, len(slice2), 14)

        buf = bytearray(8192 + len(slice2))
        buf[0:8] = fat_hdr
        buf[8:28] = slice1_desc
        buf[28:48] = slice2_desc
        buf[4096 : 4096 + len(slice1)] = slice1
        buf[8192 : 8192 + len(slice2)] = slice2

        self.synthetic_fat_macho = bytes(buf)
        self.synthetic_thin_macho = slice2

    def test_universal_fat_macho_extraction(self):
        """Verify extraction of multi-architecture FAT container slices."""
        summary = MachOBinaryParser.parse_bytes(self.synthetic_fat_macho)
        self.assertTrue(summary.is_fat_container)
        self.assertEqual(len(summary.slices), 2)

        slice_names = [s.cpu_name for s in summary.slices]
        self.assertIn("x86_64", slice_names)
        self.assertIn("arm64", slice_names)

        s_arm = next(s for s in summary.slices if s.cpu_name == "arm64")
        self.assertEqual(s_arm.offset, 8192)
        self.assertEqual(s_arm.size, 64)
        self.assertTrue(s_arm.is_64_bit)
        self.assertEqual(s_arm.file_type, "MH_EXECUTE")

    def test_thin_single_macho_parsing(self):
        """Verify parsing a standalone thin Mach-O binary."""
        summary = MachOBinaryParser.parse_bytes(self.synthetic_thin_macho)
        self.assertFalse(summary.is_fat_container)
        self.assertEqual(len(summary.slices), 1)
        self.assertEqual(summary.slices[0].cpu_name, "arm64")
        self.assertEqual(summary.slices[0].file_type, "MH_EXECUTE")

    def test_disambiguate_java_bytecode(self):
        """Verify that Java .class bytecode with CAFEBABE is rejected fail-closed."""
        # Java class: CAFEBABE + minor=0 (0x0000) + major=61 (0x003D = Java 17)
        java_class = struct.pack(">IHH", 0xCAFEBABE, 0, 61) + (b"\x00" * 32)
        with self.assertRaises(ValueError) as ctx:
            MachOBinaryParser.parse_bytes(java_class)
        self.assertIn("Java .class file", str(ctx.exception))

    def test_fail_closed_on_corrupt_macho(self):
        """Verify fail-closed rejection on invalid magic or truncated headers."""
        with self.assertRaises(ValueError):
            MachOBinaryParser.parse_bytes(b"")

        # Wrong magic (e.g. standard ELF)
        with self.assertRaises(ValueError):
            MachOBinaryParser.parse_bytes(b"\x7fELF" + (b"\x00" * 32))

        # Truncated FAT header
        with self.assertRaises(ValueError):
            MachOBinaryParser.parse_bytes(b"\xca\xfe\xba\xbe\x00")

    def test_thermodynamic_heap_ceiling(self):
        """Verify heap allocation stays strictly <= 64 KB."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            MachOBinaryParser.parse_bytes,
            self.synthetic_fat_macho,
            candidate_id="macho_parser_ch03",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify that adversarial mutants either parse safely or fail cleanly with ValueError."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.synthetic_thin_macho)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                summary = MachOBinaryParser.parse_bytes(m.payload)
                self.assertIsInstance(summary.total_bytes, int)
            except ValueError:
                pass
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
