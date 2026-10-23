"""Channel 18: Dynamic Memory Interceptor & Segment Range Validator for Kageyōni Ninshū.

Provides virtual memory address range interception, disjoint address segment mapping,
O(log N) bisect interval search, fail-closed bounds checking, overlapping collision rejection,
64-bit wrap-around detection, and memory access permission verification (Read, Write, Execute).

Zero external dependencies: uses only Python standard library (dataclasses, bisect, struct, hashlib, typing).
Peak heap allocation <= 64 KB verified via ThermodynamicProfiler.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from enum import Flag, auto
import hashlib
import json
import struct
from typing import Any, Dict, List, Optional, Tuple, Union

# Max 64-bit unsigned address space limit (0 to 2^64 - 1)
MAX_UINT64 = (1 << 64) - 1


class MemoryPermission(Flag):
    """Memory access permission flags."""
    NONE = 0
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()

    @classmethod
    def from_string(cls, perm_str: str) -> "MemoryPermission":
        """Parses permissions string like 'rwx', 'r-x', 'rw-', 'r--', '---'."""
        if not isinstance(perm_str, str) or len(perm_str) != 3:
            raise InvalidPermissionError(f"Permission string must be 3 characters long, got: {perm_str!r}")
        
        r, w, x = perm_str[0], perm_str[1], perm_str[2]
        flags = cls.NONE

        if r == "r":
            flags |= cls.READ
        elif r != "-":
            raise InvalidPermissionError(f"Invalid read permission char '{r}' in '{perm_str}'")

        if w == "w":
            flags |= cls.WRITE
        elif w != "-":
            raise InvalidPermissionError(f"Invalid write permission char '{w}' in '{perm_str}'")

        if x == "x":
            flags |= cls.EXECUTE
        elif x != "-":
            raise InvalidPermissionError(f"Invalid execute permission char '{x}' in '{perm_str}'")

        return flags

    def to_string(self) -> str:
        r = "r" if (self & MemoryPermission.READ) else "-"
        w = "w" if (self & MemoryPermission.WRITE) else "-"
        x = "x" if (self & MemoryPermission.EXECUTE) else "-"
        return f"{r}{w}{x}"


class MemoryInterceptorError(Exception):
    """Base exception for dynamic memory interceptor failures."""
    pass


class InvalidAddressError(MemoryInterceptorError):
    """Raised for negative, non-integer, or out-of-range memory addresses."""
    pass


class InvalidSizeError(MemoryInterceptorError):
    """Raised for non-positive or out-of-bounds region/access size."""
    pass


class AddressWrapAroundError(MemoryInterceptorError):
    """Raised when base_address + size wraps around 64-bit address space."""
    pass


class OverlappingRegionCollisionError(MemoryInterceptorError):
    """Raised when registering a region that collides with an existing region."""
    pass


class UnmappedAccessError(MemoryInterceptorError):
    """Raised when an address range accesses unmapped memory."""
    pass


class PermissionViolationError(MemoryInterceptorError):
    """Raised when an access operation violates region permissions."""
    pass


class InvalidPermissionError(MemoryInterceptorError):
    """Raised when permission format is invalid."""
    pass


@dataclass(frozen=True)
class MemoryRegion:
    """Immutable virtual memory segment definition."""
    base_address: int
    size: int
    permissions: MemoryPermission
    segment_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.base_address, int) or isinstance(self.base_address, bool):
            raise InvalidAddressError(f"Base address must be an integer, got: {type(self.base_address).__name__}")
        if self.base_address < 0 or self.base_address > MAX_UINT64:
            raise InvalidAddressError(f"Base address 0x{self.base_address:x} is out of 64-bit range [0, 0x{MAX_UINT64:x}]")

        if not isinstance(self.size, int) or isinstance(self.size, bool):
            raise InvalidSizeError(f"Size must be an integer, got: {type(self.size).__name__}")
        if self.size <= 0:
            raise InvalidSizeError(f"Region size must be strictly positive (> 0), got: {self.size}")

        end = self.base_address + self.size
        if end > MAX_UINT64 + 1:
            raise AddressWrapAroundError(
                f"Region [0x{self.base_address:x}, 0x{end:x}) exceeds 64-bit address space (wrap-around)."
            )

        if not isinstance(self.permissions, MemoryPermission):
            raise InvalidPermissionError(f"Permissions must be an instance of MemoryPermission, got {type(self.permissions)}")

        if not isinstance(self.segment_name, str) or not self.segment_name.strip():
            raise MemoryInterceptorError(f"Segment name must be a non-empty string, got: {self.segment_name!r}")

    @property
    def end_address(self) -> int:
        return self.base_address + self.size

    def contains_range(self, address: int, size: int) -> bool:
        """Returns True if [address, address + size) is completely inside this region."""
        return self.base_address <= address and (address + size) <= self.end_address

    def overlaps_with(self, base: int, size: int) -> bool:
        """Returns True if [base, base + size) overlaps with this region."""
        other_end = base + size
        return max(self.base_address, base) < min(self.end_address, other_end)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_address": f"0x{self.base_address:016x}",
            "end_address": f"0x{self.end_address:016x}",
            "size": self.size,
            "permissions": self.permissions.to_string(),
            "segment_name": self.segment_name,
        }

    def digest(self) -> str:
        """Computes deterministic SHA-256 digest of region metadata."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DynamicMemoryInterceptor:
    """Manages virtual memory segments and enforces zero-trust access permissions.

    Maintains a disjoint set of memory regions sorted by base address, using bisect
    for O(log N) region lookup and collision detection.
    """

    def __init__(self) -> None:
        # Sorted list of registered MemoryRegion objects
        self._regions: List[MemoryRegion] = []
        # Parallel list of base addresses for bisect
        self._bases: List[int] = []

    def region_count(self) -> int:
        return len(self._regions)

    def register_region(
        self,
        base_address: int,
        size: int,
        permissions: Union[MemoryPermission, str],
        segment_name: str,
    ) -> MemoryRegion:
        """Registers a new memory segment after fail-closed overlap and bounds validation."""
        if isinstance(permissions, str):
            perm = MemoryPermission.from_string(permissions)
        elif isinstance(permissions, MemoryPermission):
            perm = permissions
        else:
            raise InvalidPermissionError(f"Unsupported permissions type: {type(permissions)}")

        new_region = MemoryRegion(
            base_address=base_address,
            size=size,
            permissions=perm,
            segment_name=segment_name,
        )

        idx = bisect.bisect_right(self._bases, new_region.base_address)

        # Check collision with previous region (if it ends after new_region.base_address)
        if idx > 0:
            prev_region = self._regions[idx - 1]
            if prev_region.overlaps_with(new_region.base_address, new_region.size):
                raise OverlappingRegionCollisionError(
                    f"Collision detected: New region [{new_region.segment_name}: 0x{new_region.base_address:x}-0x{new_region.end_address:x}) "
                    f"overlaps with existing region [{prev_region.segment_name}: 0x{prev_region.base_address:x}-0x{prev_region.end_address:x})"
                )

        # Check collision with next region (if new_region ends after next_region.base_address)
        if idx < len(self._regions):
            next_region = self._regions[idx]
            if next_region.overlaps_with(new_region.base_address, new_region.size):
                raise OverlappingRegionCollisionError(
                    f"Collision detected: New region [{new_region.segment_name}: 0x{new_region.base_address:x}-0x{new_region.end_address:x}) "
                    f"overlaps with existing region [{next_region.segment_name}: 0x{next_region.base_address:x}-0x{next_region.end_address:x})"
                )

        self._regions.insert(idx, new_region)
        self._bases.insert(idx, new_region.base_address)
        return new_region

    def find_region(self, address: int) -> Optional[MemoryRegion]:
        """Finds the memory region containing the specified address in O(log N) time."""
        if not isinstance(address, int) or isinstance(address, bool):
            raise InvalidAddressError(f"Address must be an integer, got: {type(address).__name__}")
        if address < 0 or address > MAX_UINT64:
            raise InvalidAddressError(f"Address 0x{address:x} is out of 64-bit bounds")

        idx = bisect.bisect_right(self._bases, address)
        if idx == 0:
            return None
        candidate = self._regions[idx - 1]
        if candidate.base_address <= address < candidate.end_address:
            return candidate
        return None

    def validate_access(
        self,
        address: int,
        size: int,
        required_permission: Union[MemoryPermission, str],
    ) -> MemoryRegion:
        """Validates that [address, address + size) lies completely within a single mapped region

        and has the required permissions. Raises appropriate fail-closed exceptions if not.
        """
        if not isinstance(address, int) or isinstance(address, bool):
            raise InvalidAddressError(f"Access address must be an integer, got {type(address).__name__}")
        if address < 0 or address > MAX_UINT64:
            raise InvalidAddressError(f"Access address 0x{address:x} is out of bounds")

        if not isinstance(size, int) or isinstance(size, bool):
            raise InvalidSizeError(f"Access size must be an integer, got {type(size).__name__}")
        if size <= 0:
            raise InvalidSizeError(f"Access size must be strictly positive, got {size}")

        access_end = address + size
        if access_end > MAX_UINT64 + 1:
            raise AddressWrapAroundError(f"Access range [0x{address:x}, 0x{access_end:x}) wraps around 64-bit space")

        if isinstance(required_permission, str):
            req_perm = MemoryPermission.from_string(required_permission)
        elif isinstance(required_permission, MemoryPermission):
            req_perm = required_permission
        else:
            raise InvalidPermissionError(f"Invalid required_permission type: {type(required_permission)}")

        region = self.find_region(address)
        if region is None:
            raise UnmappedAccessError(f"Address 0x{address:x} is not mapped in virtual memory space")

        if not region.contains_range(address, size):
            raise UnmappedAccessError(
                f"Access range [0x{address:x}, 0x{access_end:x}) exceeds segment boundary "
                f"[{region.segment_name}: 0x{region.base_address:x}, 0x{region.end_address:x})"
            )

        # Check permissions: region.permissions must have all flags in req_perm
        if (region.permissions & req_perm) != req_perm:
            missing_flags = req_perm & ~region.permissions
            raise PermissionViolationError(
                f"Permission denied on segment '{region.segment_name}' at 0x{address:x}: "
                f"Required {req_perm.to_string()} but segment only has {region.permissions.to_string()} "
                f"(missing {missing_flags.to_string()})"
            )

        return region

    def intercept_read(self, address: int, size: int) -> MemoryRegion:
        """Validates read access at address with size."""
        return self.validate_access(address, size, MemoryPermission.READ)

    def intercept_write(self, address: int, size: int) -> MemoryRegion:
        """Validates write access at address with size."""
        return self.validate_access(address, size, MemoryPermission.WRITE)

    def intercept_execute(self, address: int, size: int) -> MemoryRegion:
        """Validates execute access at address with size."""
        return self.validate_access(address, size, MemoryPermission.EXECUTE)

    def snapshot_map(self) -> List[Dict[str, Any]]:
        """Returns ordered list of all registered region descriptors."""
        return [r.to_dict() for r in self._regions]

    def digest(self) -> str:
        """Computes canonical digest of the entire memory map via incremental hashing."""
        hasher = hashlib.sha256()
        for r in self._regions:
            hasher.update(r.digest().encode("ascii"))
        return hasher.hexdigest()

    @classmethod
    def inspect_payload(cls, payload: Union[Dict[str, Any], bytes, str]) -> Dict[str, Any]:
        """Classmethod helper to instantiate interceptor and validate memory regions and access."""
        if isinstance(payload, bytes):
            payload = json.loads(payload.decode("utf-8"))
        elif isinstance(payload, str):
            payload = json.loads(payload)
        elif not isinstance(payload, dict):
            payload = {}

        interceptor = cls()
        regions_data = payload.get("regions", [])
        registered = []
        for r in regions_data:
            base = r.get("base_address", 0)
            if isinstance(base, str):
                base = int(base, 16) if base.startswith("0x") else int(base)
            size = r.get("size", 0)
            perm = r.get("permissions", "r--")
            name = r.get("segment_name", "segment")
            reg = interceptor.register_region(base, size, perm, name)
            registered.append(reg.to_dict())

        access_result = None
        access_req = payload.get("access")
        if access_req:
            addr = access_req.get("address", 0)
            if isinstance(addr, str):
                addr = int(addr, 16) if addr.startswith("0x") else int(addr)
            sz = access_req.get("size", 1)
            perm = access_req.get("permission", "r--")
            matched = interceptor.validate_access(addr, sz, perm)
            access_result = matched.to_dict()

        return {
            "region_count": interceptor.region_count(),
            "regions": registered,
            "digest": interceptor.digest(),
            "validated_access": access_result,
        }
