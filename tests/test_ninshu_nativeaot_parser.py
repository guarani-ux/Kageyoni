"""Adversarial unit tests and heap compliance checks for NativeAotParser (CH 10)."""
from __future__ import annotations

import os
import tracemalloc
import unittest

from kageyoni.ninshu.nativeaot_parser import (
    RTR_SIGNATURES,
    NativeAotBuilder,
    NativeAotEntrypoint,
    NativeAotGcInfo,
    NativeAotHeader,
    NativeAotMethodTable,
    NativeAotParser,
    NativeAotSection,
    NativeAotSummary,
    NativeAotSymbolMarker,
    NativeAotThunk,
)


class TestNativeAotParser(unittest.TestCase):
    """Rigorous verification suite for NativeAOT parsing and adversarial discrimination."""

    def test_valid_rtr_header_parsing(self):
        sections = [
            (204, 0, 0x1000, 0x1000),  # TYPE_MANAGER_INDIRECTION
            (206, 1, 0x2000, 0x2800),  # FROZEN_OBJECT_REGION
            (207, 1, 0x3000, 0x4000),  # DEHYDRATED_DATA
        ]
        hdr_bytes = NativeAotBuilder.build_rtr_header(
            major=9,
            minor=1,
            flags=0x40,
            sections=sections,
            magic=b"RTR\x00",
        )

        header = NativeAotParser.parse_rtr_header(hdr_bytes, offset=0)
        self.assertEqual(header.magic, "RTR")
        self.assertEqual(header.major_version, 9)
        self.assertEqual(header.minor_version, 1)
        self.assertEqual(header.flags, 0x40)
        self.assertEqual(header.number_of_sections, 3)
        self.assertEqual(header.entry_size, 24)
        self.assertEqual(header.entry_type, 1)
        self.assertEqual(len(header.sections), 3)

        s0 = header.sections[0]
        self.assertEqual(s0.type_id, 204)
        self.assertEqual(s0.type_name, "TYPE_MANAGER_INDIRECTION")
        self.assertEqual(s0.flags, 0)
        self.assertEqual(s0.start_address, 0x1000)
        self.assertEqual(s0.end_address, 0x1000)
        self.assertEqual(s0.size, 0)

        s1 = header.sections[1]
        self.assertEqual(s1.type_id, 206)
        self.assertEqual(s1.type_name, "FROZEN_OBJECT_REGION")
        self.assertEqual(s1.flags, 1)
        self.assertEqual(s1.size, 0x800)

        s2 = header.sections[2]
        self.assertEqual(s2.type_id, 207)
        self.assertEqual(s2.type_name, "DEHYDRATED_DATA")
        self.assertEqual(s2.flags, 1)
        self.assertEqual(s2.size, 0x1000)

    def test_all_rtr_signatures(self):
        for sig in RTR_SIGNATURES:
            hdr_bytes = NativeAotBuilder.build_rtr_header(magic=sig)
            hdr = NativeAotParser.parse_rtr_header(hdr_bytes)
            expected_magic = sig.decode("ascii").rstrip("\x00")
            self.assertEqual(hdr.magic, expected_magic)

    def test_symbol_marker_discovery(self):
        payload = (
            b"padding_start\x00"
            b"RhpReversePInvokeAttachOrTrapThread\x00"
            b"middle_noise\x00"
            b"RhpPInvoke\x00"
            b"RhTypeManager::Create\x00"
            b"RhpAssignRef\x00"
            b"trailing_data"
        )
        markers = NativeAotParser.discover_symbol_markers(payload)
        self.assertEqual(len(markers), 4)

        names = [m.name for m in markers]
        self.assertIn("RhpReversePInvokeAttachOrTrapThread", names)
        self.assertIn("RhpPInvoke", names)
        self.assertIn("RhTypeManager::Create", names)
        self.assertIn("RhpAssignRef", names)

        categories = {m.name: m.category for m in markers}
        self.assertEqual(categories["RhpReversePInvokeAttachOrTrapThread"], "reverse_pinvoke")
        self.assertEqual(categories["RhpPInvoke"], "pinvoke")
        self.assertEqual(categories["RhTypeManager::Create"], "type_manager")
        self.assertEqual(categories["RhpAssignRef"], "runtime_helper")

    def test_thunk_identification_and_conventions(self):
        # 1. Derived from markers
        markers = [
            NativeAotSymbolMarker("RhpReversePInvokeAttachOrTrapThread", 0x100, "reverse_pinvoke"),
            NativeAotSymbolMarker("RhpPInvoke", 0x200, "pinvoke"),
        ]
        thunks = NativeAotParser.identify_thunks(b"", markers)
        self.assertEqual(len(thunks), 2)
        self.assertEqual(thunks[0].thunk_type, "NativeToManaged")
        self.assertEqual(thunks[0].convention, "ReversePInvoke")
        self.assertEqual(thunks[1].thunk_type, "ManagedToNative")
        self.assertEqual(thunks[1].convention, "PInvoke")

        # 2. Derived from structured THNK table
        thnk_table = NativeAotBuilder.build_thunk_table([
            (1, 48, 0x1000, 0x5000),  # ReversePInvoke
            (2, 64, 0x2000, 0x6000),  # PInvoke
        ])
        structured_thunks = NativeAotParser.identify_thunks(thnk_table, [])
        self.assertEqual(len(structured_thunks), 2)
        self.assertEqual(structured_thunks[0].thunk_type, "NativeToManaged")
        self.assertEqual(structured_thunks[0].size, 48)
        self.assertEqual(structured_thunks[0].target_marker, "0x5000")
        self.assertEqual(structured_thunks[1].thunk_type, "ManagedToNative")
        self.assertEqual(structured_thunks[1].size, 64)
        self.assertEqual(structured_thunks[1].target_marker, "0x6000")

    def test_gc_info_parsing(self):
        gc_bytes = NativeAotBuilder.build_gc_info(
            code_size=256,
            is_frameless=True,
            has_stack_pointers=True,
            reg_mask=0x0F,
            stack_slots=8,
        )
        # Offset 4 skips "GCIN" tag
        gc = NativeAotParser.parse_gc_info(gc_bytes, offset=4)
        self.assertEqual(gc.code_size, 256)
        self.assertTrue(gc.is_frameless)
        self.assertTrue(gc.has_stack_pointers)
        self.assertEqual(gc.register_mask, 0x0F)
        self.assertEqual(gc.stack_slot_count, 8)

    def test_method_table_parsing(self):
        slots = [0x1000, 0x1020, 0x1040]
        interfaces = [0x5000, 0x6000]
        mt_bytes = NativeAotBuilder.build_method_table(
            base_size=48,
            flags=0x80,
            related_type=0x2000,
            vtable_slots=slots,
            interfaces=interfaces,
        )
        # Offset 4 skips "MTBL" tag
        mt = NativeAotParser.parse_method_table(mt_bytes, offset=4)
        self.assertEqual(mt.base_size, 48)
        self.assertEqual(mt.flags, 0x80)
        self.assertEqual(mt.related_type_address, 0x2000)
        self.assertEqual(mt.slots_count, 3)
        self.assertEqual(mt.interfaces_count, 2)
        self.assertEqual(mt.vtable_slots, slots)
        self.assertEqual(mt.interface_addresses, interfaces)

    def test_entrypoints_parsing(self):
        ep_bytes = NativeAotBuilder.build_entrypoints_section([
            (0x06000001, 0x1100, 1),  # UnmanagedCallersOnly
            (0x06000002, 0x1200, 0),
        ])
        eps = NativeAotParser.parse_entrypoints(ep_bytes, offset=0)
        self.assertEqual(len(eps), 2)
        self.assertEqual(eps[0].token, 0x06000001)
        self.assertEqual(eps[0].entrypoint_offset, 0x1100)
        self.assertTrue(eps[0].is_native_callable)
        self.assertEqual(eps[1].token, 0x06000002)
        self.assertEqual(eps[1].entrypoint_offset, 0x1200)
        self.assertFalse(eps[1].is_native_callable)

    def test_full_synthetic_inspection(self):
        payload = NativeAotBuilder.build_full_payload()
        summary = NativeAotParser.inspect(payload)

        self.assertTrue(summary.has_nativeaot)
        self.assertEqual(summary.format_major, 9)
        self.assertEqual(summary.format_minor, 1)
        self.assertGreater(summary.sections_count, 0)
        self.assertGreater(summary.symbol_markers_count, 0)
        self.assertGreater(summary.thunks_count, 0)
        self.assertGreater(summary.gc_info_count, 0)
        self.assertGreater(summary.method_tables_count, 0)
        self.assertGreater(summary.entrypoints_count, 0)

        # Dictionary serialization check
        summary_dict = summary.to_dict()
        self.assertTrue(summary_dict["has_nativeaot"])
        self.assertEqual(summary_dict["format_major"], 9)
        self.assertEqual(summary_dict["format_minor"], 1)
        self.assertEqual(summary_dict["total_bytes"], len(payload))
        self.assertEqual(summary_dict["symbol_markers_count"], summary.symbol_markers_count)

    def test_fail_closed_on_empty_payload(self):
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.inspect(b"")
        self.assertIn("empty payload", str(ctx.exception).lower())

    def test_fail_closed_on_truncated_rtr_header(self):
        valid = NativeAotBuilder.build_rtr_header()
        for cut in range(0, 16):
            with self.subTest(cut=cut):
                with self.assertRaises(ValueError) as ctx:
                    NativeAotParser.parse_rtr_header(valid[:cut])
                self.assertIn("Truncated ReadyToRun header", str(ctx.exception))

    def test_fail_closed_on_invalid_magic(self):
        corrupted = b"XXXX" + NativeAotBuilder.build_rtr_header()[4:]
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_rtr_header(corrupted)
        self.assertIn("Invalid ReadyToRun magic", str(ctx.exception))

    def test_fail_closed_on_invalid_section_count(self):
        # Section count = 0
        bad_count_zero = NativeAotBuilder.build_rtr_header(override_num_sections=0)
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_rtr_header(bad_count_zero)
        self.assertIn("Invalid ReadyToRun section count", str(ctx.exception))

        # Section count > MAX_SECTIONS (128)
        bad_count_overflow = NativeAotBuilder.build_rtr_header(override_num_sections=200)
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_rtr_header(bad_count_overflow)
        self.assertIn("Invalid ReadyToRun section count", str(ctx.exception))

    def test_fail_closed_on_unsupported_entry_layout(self):
        # entry_size != 24
        bad_entry_size = NativeAotBuilder.build_rtr_header(override_entry_size=32)
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_rtr_header(bad_entry_size)
        self.assertIn("Unsupported ReadyToRun entry row size", str(ctx.exception))

        # entry_type != 1
        bad_entry_type = NativeAotBuilder.build_rtr_header(override_entry_type=2)
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_rtr_header(bad_entry_type)
        self.assertIn("Unsupported ReadyToRun entry row type", str(ctx.exception))

    def test_fail_closed_on_truncated_section_rows(self):
        valid = NativeAotBuilder.build_rtr_header(
            sections=[
                (204, 0, 0x1000, 0x1000),
                (206, 1, 0x2000, 0x2800),
            ]
        )
        # Header is 16 bytes + 2 * 24 = 64 bytes total. Truncate at 50 bytes.
        truncated = valid[:50]
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_rtr_header(truncated)
        self.assertIn("Truncated ReadyToRun section rows", str(ctx.exception))

    def test_fail_closed_on_reversed_section_bounds(self):
        reversed_sections = [
            (206, 1, 0x5000, 0x2000),  # start > end with flags=1
        ]
        bad_bounds = NativeAotBuilder.build_rtr_header(sections=reversed_sections)
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_rtr_header(bad_bounds)
        self.assertIn("Reversed NativeAOT section", str(ctx.exception))

    def test_fail_closed_on_duplicate_section_types(self):
        duplicate_sections = [
            (206, 1, 0x2000, 0x2800),
            (206, 1, 0x3000, 0x3800),
        ]
        bad_dup = NativeAotBuilder.build_rtr_header(sections=duplicate_sections)
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_rtr_header(bad_dup)
        self.assertIn("Duplicate NativeAOT section type", str(ctx.exception))

    def test_fail_closed_on_corrupted_method_table(self):
        # Truncated MT header (< 24 bytes)
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_method_table(b"\x00" * 16)
        self.assertIn("Truncated MethodTable", str(ctx.exception))

        # Invalid base size (< 16 and != 0)
        bad_base = NativeAotBuilder.build_method_table(base_size=8)
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_method_table(bad_base, offset=4)
        self.assertIn("Invalid MethodTable base size", str(ctx.exception))

        # Truncated slot data
        valid_mt = NativeAotBuilder.build_method_table(vtable_slots=[0x1000, 0x2000])
        truncated_mt = valid_mt[: len(valid_mt) - 4]
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_method_table(truncated_mt, offset=4)
        self.assertIn("Truncated MethodTable table data", str(ctx.exception))

    def test_fail_closed_on_corrupted_gc_info(self):
        # Truncated GC info (< 8 bytes)
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_gc_info(b"\x00" * 6)
        self.assertIn("Truncated GC info header", str(ctx.exception))

        # Code size == 0
        bad_code_size = NativeAotBuilder.build_gc_info(code_size=0)
        with self.assertRaises(ValueError) as ctx:
            NativeAotParser.parse_gc_info(bad_code_size, offset=4)
        self.assertIn("Invalid GC info code size", str(ctx.exception))

    def test_adversarial_fuzz_vectors(self):
        valid = NativeAotBuilder.build_rtr_header()
        # Mutate every byte offset in valid header
        for i in range(len(valid)):
            mutated = bytearray(valid)
            mutated[i] ^= 0xFF
            try:
                NativeAotParser.parse_rtr_header(bytes(mutated))
            except ValueError:
                continue

    def test_memory_allocation_ceiling(self):
        """Ensures NativeAotParser operates strictly within 64 KB peak memory allocation limit."""
        large_payload = NativeAotBuilder.build_full_payload() + (b"\x00" * 8192)

        tracemalloc.start()
        try:
            summary = NativeAotParser.inspect(large_payload)
            current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertTrue(summary.has_nativeaot)
        self.assertLessEqual(
            peak, 64 * 1024, f"Peak memory {peak} bytes exceeded 64 KB ceiling"
        )


if __name__ == "__main__":
    unittest.main()
