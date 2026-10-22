"""Adversarial unit tests and heap compliance checks for FirmwareScanner (CH 16)."""
import os
import unittest
from kageyoni.ninshu.firmware_parser import (
    FirmwareScanner,
    FirmwareAnalysisReport,
    FirmwareSignatureMatch,
    EntropySpan,
)


class TestFirmwareScanner(unittest.TestCase):
    def test_entropy_zero_for_constant_bytes(self):
        # 1024 zero bytes -> entropy 0.0
        data = b"\x00" * 1024
        ent = FirmwareScanner.calculate_shannon_entropy(data)
        self.assertEqual(ent, 0.0)

    def test_entropy_high_for_pseudo_random_bytes(self):
        # OS urandom bytes should have high Shannon entropy (~7.9 - 8.0)
        data = os.urandom(2048)
        ent = FirmwareScanner.calculate_shannon_entropy(data)
        self.assertGreater(ent, 7.5)

    def test_signature_detection_squashfs_and_uimage(self):
        # Construct synthetic firmware image with padding, SquashFS, and U-Boot headers
        padding = b"\x00" * 64
        sqsh_header = b"sqsh" + b"\x01" * 60
        uimage_header = b"\x27\x05\x19\x56" + b"\x02" * 60
        fdt_header = b"\xd0\x0d\xfe\xed" + b"\x03" * 28

        image = padding + sqsh_header + uimage_header + fdt_header
        report = FirmwareScanner.analyze_firmware(image, block_size=64)

        self.assertEqual(report.total_bytes, len(image))
        self.assertGreaterEqual(len(report.signatures_found), 3)

        sig_descs = [s.description for s in report.signatures_found]
        self.assertTrue(any("SquashFS" in d for d in sig_descs))
        self.assertTrue(any("U-Boot" in d for d in sig_descs))
        self.assertTrue(any("Device Tree" in d for d in sig_descs))

        d = report.to_dict()
        self.assertIn("signatures", d)
        self.assertEqual(d["signatures_count"], len(report.signatures_found))

    def test_empty_payload_fails(self):
        with self.assertRaises(ValueError):
            FirmwareScanner.analyze_firmware(b"")

    def test_invalid_block_size_fails(self):
        with self.assertRaises(ValueError):
            FirmwareScanner.scan_entropy_blocks(b"test", block_size=0)
        with self.assertRaises(ValueError):
            FirmwareScanner.scan_entropy_blocks(b"test", block_size=-10)

    def test_range_validation(self):
        # Valid range
        off, length = FirmwareScanner.validate_byte_range(1000, 100, 200)
        self.assertEqual((off, length), (100, 200))

        # Negative offset
        with self.assertRaises(ValueError):
            FirmwareScanner.validate_byte_range(1000, -1, 100)

        # Zero or negative length
        with self.assertRaises(ValueError):
            FirmwareScanner.validate_byte_range(1000, 0, 0)
        with self.assertRaises(ValueError):
            FirmwareScanner.validate_byte_range(1000, 0, -50)

        # Overflow file bounds
        with self.assertRaises(ValueError):
            FirmwareScanner.validate_byte_range(1000, 900, 200)

    def test_adversarial_fuzz_vectors(self):
        # Fuzz entropy scanner with repeating patterns of all 256 byte permutations
        # When block size is 256, all 256 values are equally represented -> entropy = log2(256) = 8.0
        all_bytes = bytes(range(256)) * 4
        report = FirmwareScanner.analyze_firmware(all_bytes, block_size=256)
        # Uniform distribution of all 256 bytes has theoretical entropy = 8.0
        self.assertAlmostEqual(report.mean_entropy, 8.0, places=3)
        self.assertEqual(len(report.entropy_spans), 4)
        for span in report.entropy_spans:
            self.assertTrue(span.is_high_entropy)


if __name__ == "__main__":
    unittest.main()
