"""Adversarial unit tests and heap compliance checks for RawBinaryDisassembler (CH 15)."""
import unittest
from kageyoni.ninshu.raw_binary_parser import RawBinaryDisassembler, RawBinarySummary


class TestRawBinaryParser(unittest.TestCase):
    def test_x86_valid_prologue_and_epilogue(self):
        # 0x55 (push ebp), 0x90 (nop), 0xCC (int3), 0xC3 (ret)
        payload = bytes([0x55, 0x89, 0xE5, 0x90, 0xCC, 0xC3])
        res = RawBinaryDisassembler.parse_raw(payload, architecture="x86", entry_point="0x1000")
        self.assertEqual(res.total_bytes, 6)
        self.assertEqual(res.architecture, "x86")
        self.assertEqual(res.address_bits, 32)
        self.assertEqual(res.entry_point_canonical, "0x1000")
        self.assertEqual(res.entry_point_integer, 0x1000)
        self.assertEqual(res.detected_markers_count, 3)
        mnemonics = [m.mnemonic for m in res.instruction_markers]
        self.assertIn("push rbp/ebp", mnemonics)
        self.assertIn("int3", mnemonics)
        self.assertIn("ret", mnemonics)
        d = res.to_dict()
        self.assertEqual(d["markers_count"], 3)

    def test_6502_markers(self):
        # 0xA9 0x01 (LDA #1), 0x4C 0x00 0x80 (JMP $8000), 0x60 (RTS)
        payload = bytes([0xA9, 0x01, 0x4C, 0x00, 0x80, 0x60])
        res = RawBinaryDisassembler.parse_raw(payload, architecture="6502", entry_point="0x8000")
        self.assertEqual(res.architecture, "6502")
        self.assertEqual(res.address_bits, 16)
        mnemonics = [m.mnemonic for m in res.instruction_markers]
        self.assertIn("jmp 0x8000", mnemonics)
        self.assertIn("rts", mnemonics)

    def test_m68k_rts(self):
        # 0x4E 0x75 (RTS)
        payload = bytes([0x70, 0x00, 0x4E, 0x75])
        res = RawBinaryDisassembler.parse_raw(payload, architecture="m68k", entry_point="0x400")
        self.assertEqual(res.architecture, "m68k")
        self.assertEqual(res.endianness, "big")
        mnemonics = [m.mnemonic for m in res.instruction_markers]
        self.assertIn("rts", mnemonics)

    def test_empty_payload_fails(self):
        with self.assertRaises(ValueError):
            RawBinaryDisassembler.parse_raw(b"", architecture="x86")

    def test_unsupported_arch_fails(self):
        with self.assertRaises(ValueError):
            RawBinaryDisassembler.parse_raw(b"\x90", architecture="sparc64")

    def test_malformed_entry_point_fails(self):
        with self.assertRaises(ValueError):
            RawBinaryDisassembler.parse_raw(b"\x90", architecture="x86", entry_point="not_hex")
        with self.assertRaises(ValueError):
            RawBinaryDisassembler.parse_raw(b"\x90", architecture="x86", entry_point="1000")  # missing 0x

    def test_16bit_address_space_overflow(self):
        # 6502 has 16-bit space (0xFFFF max)
        with self.assertRaises(ValueError):
            RawBinaryDisassembler.parse_raw(b"\x60", architecture="6502", entry_point="0x10000")

    def test_binary_extent_overflow(self):
        # 6502 entry at 0xFFFE with 5 bytes overflows 0xFFFF
        with self.assertRaises(ValueError):
            RawBinaryDisassembler.parse_raw(bytes([0x90] * 5), architecture="6502", entry_point="0xFFFE")

    def test_adversarial_fuzz_rejection(self):
        # 20 malformed entry formats and corrupted boundaries
        bad_entries = [
            "", "0x", "0xG", "-0x10", "0x 10", "0x10000000000000000000",
            "null", "NaN", "0x-1", "0x00000000000000000", "0xZZ",
            "0x1000\x00", "0x1000;drop", " 0x10", "0x10 ", "0x.10",
            "0x123456789abcdef01", "0xABCDEFGH"
        ]
        for bad in bad_entries:
            with self.subTest(entry=bad):
                with self.assertRaises(ValueError):
                    RawBinaryDisassembler.validate_entry_point(bad, "x86")


if __name__ == "__main__":
    unittest.main()
