"""Adversarial unit tests and heap compliance checks for DartSnapshotParser (CH 31)."""
import os
import tracemalloc
import unittest

from kageyoni.ninshu.dart_parser import (
    DART_SNAPSHOT_MAGIC_INT,
    DART_SNAPSHOT_MAGIC_LE,
    DART_SNAPSHOT_MAGIC_BE,
    KNOWN_DART_SYMBOLS,
    SNAPSHOT_KINDS,
    DartSnapshotBuilder,
    DartSnapshotHeader,
    DartSnapshotParser,
    DartSnapshotSummary,
)


class TestDartSnapshotParser(unittest.TestCase):
    """Rigorous verification suite for Dart snapshot parsing and adversarial discrimination."""

    def test_valid_64bit_full_aot_snapshot(self):
        commit_hash = "0123456789abcdef0123456789abcdef"
        flags = "--sound-null-safety --enable-asserts"
        payload = b"\x42" * 64

        data = DartSnapshotBuilder.build(
            kind="full_aot",
            snapshot_hash=commit_hash,
            isolate_flags=flags,
            payload=payload,
            arch_bits=64,
            endianness="little",
        )

        header = DartSnapshotParser.parse_header(data, offset=0)
        self.assertEqual(header.magic, DART_SNAPSHOT_MAGIC_INT)
        self.assertEqual(header.endianness, "little")
        self.assertEqual(header.arch_bits, 64)
        self.assertEqual(header.kind_id, 3)
        self.assertEqual(header.kind_name, "full_aot")
        self.assertEqual(header.snapshot_hash, commit_hash)
        self.assertIn("--sound-null-safety", header.isolate_flags)
        self.assertIn("--enable-asserts", header.isolate_flags)
        self.assertEqual(header.header_offset, 0)

        summary = DartSnapshotParser.inspect(data)
        self.assertTrue(summary.has_dart_snapshot)
        self.assertEqual(summary.snapshot_hash, commit_hash)
        self.assertEqual(summary.snapshot_hash_candidates, [commit_hash])
        self.assertEqual(summary.detected_kinds, ["full_aot"])

    def test_valid_32bit_big_endian_snapshot(self):
        commit_hash = "deadbeefcafebabe0123456789abcdef"
        data = DartSnapshotBuilder.build(
            kind=1,  # core
            snapshot_hash=commit_hash,
            isolate_flags="--target_os=android",
            payload=b"\x11" * 16,
            arch_bits=32,
            endianness="big",
        )

        header = DartSnapshotParser.parse_header(data, offset=0)
        self.assertEqual(header.magic, DART_SNAPSHOT_MAGIC_INT)
        self.assertEqual(header.endianness, "big")
        self.assertEqual(header.arch_bits, 32)
        self.assertEqual(header.kind_id, 1)
        self.assertEqual(header.kind_name, "core")
        self.assertEqual(header.snapshot_hash, commit_hash)
        self.assertEqual(header.isolate_flags, ["--target_os=android"])

    def test_all_snapshot_kinds(self):
        for kind_id, kind_name in SNAPSHOT_KINDS.items():
            commit_hash = f"{kind_id:02x}" * 16
            data = DartSnapshotBuilder.build(
                kind=kind_id,
                snapshot_hash=commit_hash,
                isolate_flags=f"--kind={kind_name}",
            )
            header = DartSnapshotParser.parse_header(data)
            self.assertEqual(header.kind_id, kind_id)
            self.assertEqual(header.kind_name, kind_name)
            self.assertEqual(header.snapshot_hash, commit_hash)

    def test_multi_section_consensus_and_conflicts(self):
        hash1 = "11111111111111111111111111111111"
        hash2 = "22222222222222222222222222222222"

        snap1 = DartSnapshotBuilder.build(kind="full_aot", snapshot_hash=hash1)
        snap2 = DartSnapshotBuilder.build(kind="core", snapshot_hash=hash1)

        # Composite payload with consensus
        composite_agree = snap1 + b"\x00\x00\x00\x00" + snap2
        summary_agree = DartSnapshotParser.inspect(composite_agree)
        self.assertEqual(len(summary_agree.snapshots_found), 2)
        self.assertEqual(summary_agree.snapshot_hash, hash1)
        self.assertEqual(summary_agree.snapshot_hash_candidates, [hash1])

        # Composite payload with conflicting hashes
        snap3 = DartSnapshotBuilder.build(kind="script", snapshot_hash=hash2)
        composite_conflict = snap1 + b"\x00" * 8 + snap3
        summary_conflict = DartSnapshotParser.inspect(composite_conflict)
        self.assertEqual(len(summary_conflict.snapshots_found), 2)
        self.assertIsNone(summary_conflict.snapshot_hash)
        self.assertEqual(summary_conflict.snapshot_hash_candidates, [hash1, hash2])

    def test_flutter_symbol_detection(self):
        snap = DartSnapshotBuilder.build(kind="full_aot", snapshot_hash="33333333333333333333333333333333")
        payload = (
            b"_kDartVmSnapshotData\x00"
            + snap
            + b"_kDartIsolateSnapshotData\x00"
        )
        summary = DartSnapshotParser.inspect(payload)
        self.assertIn("_kDartVmSnapshotData", summary.symbols_detected)
        self.assertIn("_kDartIsolateSnapshotData", summary.symbols_detected)
        self.assertTrue(summary.has_dart_snapshot)
        d = summary.to_dict()
        self.assertEqual(d["snapshots_count"], 1)

    def test_fail_closed_on_invalid_magic(self):
        corrupted = bytearray(DartSnapshotBuilder.build())
        corrupted[0] ^= 0xFF
        with self.assertRaises(ValueError) as ctx:
            DartSnapshotParser.parse_header(bytes(corrupted))
        self.assertIn("Invalid Dart snapshot magic", str(ctx.exception))

    def test_fail_closed_on_truncated_header(self):
        valid = DartSnapshotBuilder.build()
        # Truncate at various boundaries below minimum header
        for cut in range(0, 44):
            with self.subTest(cut=cut):
                with self.assertRaises(ValueError) as ctx:
                    DartSnapshotParser.parse_header(valid[:cut])
                self.assertIn("Truncated Dart snapshot header", str(ctx.exception))

    def test_fail_closed_on_length_overflow(self):
        # Override declared length to exceed buffer
        overflow_data = DartSnapshotBuilder.build(override_length=999999)
        with self.assertRaises(ValueError) as ctx:
            DartSnapshotParser.parse_header(overflow_data, strict_length=True)
        self.assertIn("length overflow", str(ctx.exception))

        # Huge length exceeding MAX_SNAPSHOT_SIZE (2 GB)
        huge_data = DartSnapshotBuilder.build(override_length=3 * 1024 * 1024 * 1024)
        with self.assertRaises(ValueError) as ctx:
            DartSnapshotParser.parse_header(huge_data, strict_length=False)
        self.assertIn("exceeds maximum ceiling", str(ctx.exception))

    def test_fail_closed_on_corrupted_hash(self):
        # Non-hex characters in hash
        bad_hash_bytes = DartSnapshotBuilder.build(snapshot_hash="not_a_valid_hex_hash_at_all!1234")
        with self.assertRaises(ValueError) as ctx:
            DartSnapshotParser.parse_header(bad_hash_bytes)
        self.assertIn("Invalid Dart snapshot hash", str(ctx.exception))

        # Binary/unprintable characters in hash
        corrupted = bytearray(DartSnapshotBuilder.build())
        corrupted[20] = 0x00  # Null byte inside hash
        with self.assertRaises(ValueError):
            DartSnapshotParser.parse_header(bytes(corrupted))

    def test_fail_closed_on_corrupted_kind(self):
        # Invalid kind ID 99
        data = DartSnapshotBuilder.build(kind=99)
        with self.assertRaises(ValueError) as ctx:
            DartSnapshotParser.parse_header(data)
        self.assertIn("Invalid Dart snapshot kind ID", str(ctx.exception))

    def test_adversarial_fuzzing_slices(self):
        valid = DartSnapshotBuilder.build(
            kind="full_aot",
            snapshot_hash="abcdef0123456789abcdef0123456789",
            isolate_flags="--test-flag",
        )
        # Fuzz every byte offset in valid header
        for i in range(len(valid)):
            mutated = bytearray(valid)
            mutated[i] ^= 0xFF
            # Should either parse cleanly with different values or raise ValueError fail-closed
            try:
                DartSnapshotParser.parse_header(bytes(mutated), strict_length=True)
            except ValueError:
                continue

    def test_memory_allocation_ceiling(self):
        """Ensures parser runs strictly within 64 KB peak memory allocation limit."""
        large_snap = DartSnapshotBuilder.build(
            kind="full_aot",
            snapshot_hash="abcdef0123456789abcdef0123456789",
            isolate_flags="--sound-null-safety --enable-asserts",
            payload=b"\x00" * 4096,
        )

        tracemalloc.start()
        try:
            summary = DartSnapshotParser.inspect(large_snap)
            current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertTrue(summary.has_dart_snapshot)
        # Peak memory must be well below 64 KB (65536 bytes)
        self.assertLessEqual(peak, 64 * 1024, f"Peak memory {peak} bytes exceeded 64 KB ceiling")


if __name__ == "__main__":
    unittest.main()
