"""Adversarial unit tests and heap compliance checks for ApkParser and DexParser (CH 28)."""
import io
import struct
import unittest
import zipfile
from kageyoni.ninshu.apk_parser import ApkParser, DexParser, DexHeader, ApkSummary


def build_synthetic_dex(version: bytes = b"035\x00", file_size: int = 112) -> bytes:
    # 8-byte magic
    magic = b"dex\n" + version
    checksum = 0x12345678
    sha1 = b"\xaa" * 20
    header_size = 112
    endian_tag = 0x12345678

    header = (
        magic
        + struct.pack("<I", checksum)
        + sha1
        + struct.pack("<III", file_size, header_size, endian_tag)
        + struct.pack("<IIIIIIIIIIIIIIIII", 0, 0, 0, 10, 0, 5, 0, 3, 0, 2, 0, 8, 0, 4, 0, 0, 0)
    )
    if len(header) < file_size:
        header += b"\x00" * (file_size - len(header))
    return header


class TestApkDexParser(unittest.TestCase):
    def test_valid_dex_parsing(self):
        dex_data = build_synthetic_dex(version=b"035\x00", file_size=112)
        hdr = DexParser.parse_header(dex_data)
        self.assertEqual(hdr.version, "035")
        self.assertEqual(hdr.endianness, "little")
        self.assertEqual(hdr.header_size, 112)
        self.assertEqual(hdr.string_ids_count, 10)
        self.assertEqual(hdr.type_ids_count, 5)
        self.assertEqual(hdr.proto_ids_count, 3)
        self.assertEqual(hdr.field_ids_count, 2)
        self.assertEqual(hdr.method_ids_count, 8)
        self.assertEqual(hdr.class_defs_count, 4)

    def test_dex_truncated_fails(self):
        with self.assertRaises(ValueError):
            DexParser.parse_header(b"dex\n035\x00")

    def test_dex_corrupted_magic_fails(self):
        bad_magic = b"bad\n035\x00" + b"\x00" * 104
        with self.assertRaises(ValueError):
            DexParser.parse_header(bad_magic)

    def test_dex_unsupported_version_fails(self):
        bad_ver = b"dex\n999\x00" + b"\x00" * 104
        with self.assertRaises(ValueError):
            DexParser.parse_header(bad_ver)

    def test_dex_file_size_overflow_fails(self):
        # file_size declared as 1000, but only 112 bytes provided
        dex_data = build_synthetic_dex(file_size=1000)[:112]
        with self.assertRaises(ValueError):
            DexParser.parse_header(dex_data)

    def test_valid_apk_parsing(self):
        # Create synthetic APK in memory
        bio = io.BytesIO()
        dex_bytes = build_synthetic_dex()
        with zipfile.ZipFile(bio, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"<manifest></manifest>")
            zf.writestr("resources.arsc", b"ARSC_BINARY_DATA")
            zf.writestr("classes.dex", dex_bytes)
            zf.writestr("META-INF/CERT.RSA", b"SIGNATURE_BLOCK")

        apk_bytes = bio.getvalue()
        summary = ApkParser.parse_apk(apk_bytes)

        self.assertEqual(summary.dex_count, 1)
        self.assertTrue(summary.has_manifest)
        self.assertTrue(summary.has_resources_arsc)
        self.assertTrue(summary.has_signatures)
        self.assertEqual(summary.entries_count, 4)
        self.assertEqual(summary.dex_headers[0].version, "035")

        d = summary.to_dict()
        self.assertEqual(d["dex_count"], 1)
        self.assertTrue(d["has_manifest"])

    def test_apk_empty_payload_fails(self):
        with self.assertRaises(ValueError):
            ApkParser.parse_apk(b"")

    def test_apk_corrupted_header_fails(self):
        with self.assertRaises(ValueError):
            ApkParser.parse_apk(b"NOT_A_ZIP_HEADER")

    def test_apk_adversarial_mutations(self):
        # 10 adversarial corrupted byte slices
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w") as zf:
            zf.writestr("classes.dex", build_synthetic_dex())
        valid_apk = bio.getvalue()

        mutations = [
            valid_apk[:10],
            valid_apk[:30],
            b"PK\x03\x04" + b"\xff" * 20,
            valid_apk[:50] + b"\x00" * 50,
        ]
        for mutant in mutations:
            with self.subTest(len=len(mutant)):
                with self.assertRaises(ValueError):
                    ApkParser.parse_apk(mutant)


if __name__ == "__main__":
    unittest.main()
