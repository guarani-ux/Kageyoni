"""Unit and adversarial verification suite for Channel 18 (Dynamic Memory Interceptor).

Validates:
1. Valid memory map population and range queries (O(log N) bisect interval search).
2. Overlap collision rejection (left, right, enclosed, encompassing).
3. Permission violation enforcement (read, write, execute, missing flags).
4. Adversarial fuzz vectors: 64-bit boundary overflows, wrap-arounds, negative sizes/addresses, corrupt flags.
5. Peak heap allocation <= 64 KB verified via ThermodynamicProfiler.
"""
from __future__ import annotations

import unittest

from kageyoni.ninshu.memory_interceptor import (
    MAX_UINT64,
    AddressWrapAroundError,
    DynamicMemoryInterceptor,
    InvalidAddressError,
    InvalidPermissionError,
    InvalidSizeError,
    MemoryInterceptorError,
    MemoryPermission,
    MemoryRegion,
    OverlappingRegionCollisionError,
    PermissionViolationError,
    UnmappedAccessError,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


class TestNinshuMemoryInterceptor(unittest.TestCase):
    def setUp(self) -> None:
        self.interceptor = DynamicMemoryInterceptor()

    def test_permission_parsing_and_formatting(self) -> None:
        """Verify strict MemoryPermission string parsing and serialization."""
        p_rwx = MemoryPermission.from_string("rwx")
        self.assertEqual(p_rwx.to_string(), "rwx")
        self.assertTrue(p_rwx & MemoryPermission.READ)
        self.assertTrue(p_rwx & MemoryPermission.WRITE)
        self.assertTrue(p_rwx & MemoryPermission.EXECUTE)

        p_rx = MemoryPermission.from_string("r-x")
        self.assertEqual(p_rx.to_string(), "r-x")
        self.assertTrue(p_rx & MemoryPermission.READ)
        self.assertFalse(bool(p_rx & MemoryPermission.WRITE))
        self.assertTrue(p_rx & MemoryPermission.EXECUTE)

        p_none = MemoryPermission.from_string("---")
        self.assertEqual(p_none.to_string(), "---")

        with self.assertRaises(InvalidPermissionError):
            MemoryPermission.from_string("rw")
        with self.assertRaises(InvalidPermissionError):
            MemoryPermission.from_string("rwx-")
        with self.assertRaises(InvalidPermissionError):
            MemoryPermission.from_string("axc")

    def test_valid_memory_map_population_and_query(self) -> None:
        """Verify registering disjoint memory segments and looking up addresses."""
        # .text segment (code: r-x)
        text_reg = self.interceptor.register_region(
            base_address=0x00400000,
            size=0x10000,  # 64 KB
            permissions="r-x",
            segment_name=".text",
        )
        # .data segment (data: rw-)
        data_reg = self.interceptor.register_region(
            base_address=0x00600000,
            size=0x20000,  # 128 KB
            permissions="rw-",
            segment_name=".data",
        )
        # .rodata segment (read-only: r--)
        rodata_reg = self.interceptor.register_region(
            base_address=0x00500000,
            size=0x8000,   # 32 KB
            permissions="r--",
            segment_name=".rodata",
        )

        self.assertEqual(self.interceptor.region_count(), 3)

        # Lookup exact base
        found = self.interceptor.find_region(0x00400000)
        self.assertIsNotNone(found)
        self.assertEqual(found.segment_name, ".text")

        # Lookup middle
        found = self.interceptor.find_region(0x00501000)
        self.assertIsNotNone(found)
        self.assertEqual(found.segment_name, ".rodata")

        # Lookup last byte of region
        found = self.interceptor.find_region(0x0061FFFF)
        self.assertIsNotNone(found)
        self.assertEqual(found.segment_name, ".data")

        # Lookup unmapped space
        self.assertIsNone(self.interceptor.find_region(0x00100000))
        self.assertIsNone(self.interceptor.find_region(0x00410000))  # Exactly end of .text

    def test_overlapping_collision_rejections(self) -> None:
        """Verify fail-closed rejection of overlapping segment registrations."""
        self.interceptor.register_region(0x1000, 0x1000, "r-x", "code")  # [0x1000, 0x2000)

        # 1. Exact collision
        with self.assertRaises(OverlappingRegionCollisionError):
            self.interceptor.register_region(0x1000, 0x1000, "rw-", "collision_exact")

        # 2. Overlap left boundary
        with self.assertRaises(OverlappingRegionCollisionError):
            self.interceptor.register_region(0x800, 0x1000, "rw-", "overlap_left")

        # 3. Overlap right boundary
        with self.assertRaises(OverlappingRegionCollisionError):
            self.interceptor.register_region(0x1800, 0x1000, "rw-", "overlap_right")

        # 4. Enclosed within existing
        with self.assertRaises(OverlappingRegionCollisionError):
            self.interceptor.register_region(0x1200, 0x100, "rw-", "enclosed")

        # 5. Encompassing existing
        with self.assertRaises(OverlappingRegionCollisionError):
            self.interceptor.register_region(0x500, 0x3000, "rw-", "encompassing")

        # Valid non-overlapping adjacent regions
        left_adj = self.interceptor.register_region(0x0000, 0x1000, "r--", "left_adjacent")
        right_adj = self.interceptor.register_region(0x2000, 0x1000, "rw-", "right_adjacent")
        self.assertEqual(self.interceptor.region_count(), 3)

    def test_permission_violations(self) -> None:
        """Verify enforcement of read, write, and execute permissions."""
        self.interceptor.register_region(0x1000, 0x1000, "r-x", ".text")
        self.interceptor.register_region(0x2000, 0x1000, "rw-", ".data")
        self.interceptor.register_region(0x3000, 0x1000, "r--", ".rodata")

        # .text: Read and Execute allowed, Write denied
        self.interceptor.intercept_read(0x1000, 64)
        self.interceptor.intercept_execute(0x1000, 64)
        with self.assertRaises(PermissionViolationError):
            self.interceptor.intercept_write(0x1000, 64)

        # .data: Read and Write allowed, Execute denied
        self.interceptor.intercept_read(0x2000, 64)
        self.interceptor.intercept_write(0x2000, 64)
        with self.assertRaises(PermissionViolationError):
            self.interceptor.intercept_execute(0x2000, 64)

        # .rodata: Read allowed, Write and Execute denied
        self.interceptor.intercept_read(0x3000, 64)
        with self.assertRaises(PermissionViolationError):
            self.interceptor.intercept_write(0x3000, 64)
        with self.assertRaises(PermissionViolationError):
            self.interceptor.intercept_execute(0x3000, 64)

    def test_boundary_and_unmapped_access_rejections(self) -> None:
        """Verify fail-closed rejection on accessing unmapped or straddling memory ranges."""
        self.interceptor.register_region(0x1000, 0x1000, "rw-", ".data")  # [0x1000, 0x2000)

        # Access before segment
        with self.assertRaises(UnmappedAccessError):
            self.interceptor.intercept_read(0x0FFF, 1)

        # Access past end
        with self.assertRaises(UnmappedAccessError):
            self.interceptor.intercept_read(0x2000, 1)

        # Straddling access (starts inside, ends outside)
        with self.assertRaises(UnmappedAccessError):
            self.interceptor.intercept_read(0x1FFE, 4)

    def test_adversarial_fuzz_vectors(self) -> None:
        """Verify rejection of 64-bit wrap-arounds, negative sizes, corrupt flags, and types."""
        # 1. Negative addresses
        with self.assertRaises(InvalidAddressError):
            MemoryRegion(base_address=-1, size=1024, permissions=MemoryPermission.READ, segment_name="neg")
        with self.assertRaises(InvalidAddressError):
            self.interceptor.find_region(-1)
        with self.assertRaises(InvalidAddressError):
            self.interceptor.intercept_read(-1, 10)

        # 2. Negative or zero size
        with self.assertRaises(InvalidSizeError):
            MemoryRegion(base_address=0x1000, size=0, permissions=MemoryPermission.READ, segment_name="zero")
        with self.assertRaises(InvalidSizeError):
            MemoryRegion(base_address=0x1000, size=-100, permissions=MemoryPermission.READ, segment_name="neg_sz")
        with self.assertRaises(InvalidSizeError):
            self.interceptor.intercept_read(0x1000, 0)
        with self.assertRaises(InvalidSizeError):
            self.interceptor.intercept_read(0x1000, -50)

        # 3. 64-bit Address Wrap-Around
        with self.assertRaises(AddressWrapAroundError):
            # Base + size wraps around 2^64
            MemoryRegion(base_address=MAX_UINT64, size=2, permissions=MemoryPermission.READ, segment_name="wrap")

        # 4. Access wrap-around
        with self.assertRaises(AddressWrapAroundError):
            self.interceptor.validate_access(MAX_UINT64 - 10, 20, MemoryPermission.READ)

        # 5. Out of bounds > MAX_UINT64
        with self.assertRaises(InvalidAddressError):
            self.interceptor.find_region(MAX_UINT64 + 1)

        # 6. Invalid non-integer types (e.g. bool, str)
        with self.assertRaises(InvalidAddressError):
            self.interceptor.find_region(True)  # type: ignore
        with self.assertRaises(InvalidAddressError):
            self.interceptor.find_region("0x1000")  # type: ignore

        # 7. Corrupt permission string / types
        with self.assertRaises(InvalidPermissionError):
            self.interceptor.register_region(0x1000, 0x1000, 1234, "corrupt_perm")  # type: ignore

        # 8. Empty segment name
        with self.assertRaises(MemoryInterceptorError):
            self.interceptor.register_region(0x1000, 0x1000, "rwx", "   ")

    def test_digest_and_snapshot_integrity(self) -> None:
        """Verify snapshot_map and deterministic SHA-256 digests."""
        self.interceptor.register_region(0x1000, 0x1000, "r-x", "sec1")
        self.interceptor.register_region(0x2000, 0x1000, "rw-", "sec2")

        snapshot = self.interceptor.snapshot_map()
        self.assertEqual(len(snapshot), 2)
        self.assertEqual(snapshot[0]["segment_name"], "sec1")
        self.assertEqual(snapshot[1]["segment_name"], "sec2")

        d1 = self.interceptor.digest()
        d2 = self.interceptor.digest()
        self.assertEqual(d1, d2)
        self.assertEqual(len(d1), 64)

    def test_thermodynamic_memory_ceiling(self) -> None:
        """Verify peak heap memory allocation strictly <= 64 KB during intense map operations."""
        with ThermodynamicProfiler(candidate_id="memory_interceptor_64kb_gate", memory_ceiling_bytes=64 * 1024) as profiler:
            interceptor = DynamicMemoryInterceptor()
            # Register 100 disjoint segments across 64-bit address space
            base = 0x10000000
            for i in range(100):
                interceptor.register_region(
                    base_address=base + (i * 0x2000),
                    size=0x1000,
                    permissions="r-x" if i % 2 == 0 else "rw-",
                    segment_name=f"seg_{i}",
                )

            # Perform 500 lookups and interceptions
            for i in range(100):
                reg = interceptor.find_region(base + (i * 0x2000) + 0x500)
                assert reg is not None
                if i % 2 == 0:
                    interceptor.intercept_read(base + (i * 0x2000), 256)
                    interceptor.intercept_execute(base + (i * 0x2000), 256)
                else:
                    interceptor.intercept_write(base + (i * 0x2000), 256)

            digest = interceptor.digest()
            receipt = profiler.get_receipt(artifact_sha256=digest)

        self.assertTrue(receipt.passed)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)


if __name__ == "__main__":
    unittest.main()
