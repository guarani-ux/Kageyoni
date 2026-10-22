"""Zero-dependency in-tree Flutter Engine & Dart Snapshot Inspector (CH 31).

Inspects Dart VM snapshot headers, AOT payloads, and Flutter engine binaries:
1. Snapshot Magic & Header Structure:
   - Validates snapshot magic: 0xf5f5dcdc (little-endian: \\xdc\\xdc\\xf5\\xf5, big-endian: \\xf5\\xf5\\xdc\\xdc).
   - Parses declared snapshot length (uint64 or uint32).
   - Parses snapshot kind:
       0: Full
       1: Core
       2: App-JIT
       3: Full AOT
       4: Message
       5: Script
   - Extracts 32-character hexadecimal snapshot hash / commit digest.
   - Extracts isolate flags / runtime feature strings (e.g. --sound-null-safety).
2. Fail-Closed Validation:
   - Rejects truncated headers and partial buffers.
   - Rejects invalid or corrupted magic bytes.
   - Enforces length bounds to prevent integer and buffer overflows.
   - Validates snapshot hash against strict hex/alphanumeric invariants.
   - Validates kind ID within allowed enum range.
3. Multi-Section Scanning:
   - Locates embedded Dart snapshot sections (e.g. vm-snapshot-data, isolate-snapshot-data).
   - Tracks known Flutter ELF symbols: _kDartVmSnapshotData, _kDartIsolateSnapshotData, etc.
   - Computes consensus snapshot hash across sections.
4. Memory & Performance:
   - Zero third-party dependencies (pure Python standard library).
   - Strict bounded allocations keeping peak memory <= 64 KB.
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
import struct
from typing import Any, Dict, List, Optional, Tuple, Union

# Dart VM snapshot magic constant (0xf5f5dcdc)
DART_SNAPSHOT_MAGIC_INT = 0xF5F5DCDC
DART_SNAPSHOT_MAGIC_LE = b"\xdc\xdc\xf5\xf5"
DART_SNAPSHOT_MAGIC_BE = b"\xf5\xf5\xdc\xdc"

# Minimum header sizes:
# 64-bit: magic (4) + length (8) + kind (8) + hash (32) = 52 bytes
# 32-bit: magic (4) + length (4) + kind (4) + hash (32) = 44 bytes
MIN_HEADER_SIZE_64 = 52
MIN_HEADER_SIZE_32 = 44

# Maximum allowed snapshot payload size to guard against length overflow attacks (2 GB)
MAX_SNAPSHOT_SIZE = 2 * 1024 * 1024 * 1024

# Strict 32-character hexadecimal pattern for Dart snapshot commit / feature digest
SNAPSHOT_HASH_REGEX = re.compile(r"^[0-9a-fA-F]{32}$")

# Dart VM Snapshot::Kind enum mapping
SNAPSHOT_KINDS = {
    0: "full",
    1: "core",
    2: "app-jit",
    3: "full_aot",
    4: "message",
    5: "script",
}

KIND_NAME_TO_ID = {
    "full": 0,
    "core": 1,
    "app-jit": 2,
    "app_jit": 2,
    "full_aot": 3,
    "full aot": 3,
    "aot": 3,
    "message": 4,
    "script": 5,
}

# Flutter AOT symbol markers commonly embedded in libapp.so
KNOWN_DART_SYMBOLS = (
    b"_kDartVmSnapshotData",
    b"_kDartVmSnapshotInstructions",
    b"_kDartIsolateSnapshotData",
    b"_kDartIsolateSnapshotInstructions",
)


@dataclasses.dataclass(frozen=True)
class DartSnapshotHeader:
    """Parsed Dart VM snapshot header representation."""
    magic: int
    endianness: str
    arch_bits: int
    header_offset: int
    snapshot_length: int
    kind_id: int
    kind_name: str
    snapshot_hash: str
    isolate_flags: List[str]
    raw_flags: str
    header_size: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "magic": f"0x{self.magic:08x}",
            "endianness": self.endianness,
            "arch_bits": self.arch_bits,
            "header_offset": self.header_offset,
            "snapshot_length": self.snapshot_length,
            "kind_id": self.kind_id,
            "kind_name": self.kind_name,
            "snapshot_hash": self.snapshot_hash,
            "isolate_flags": self.isolate_flags,
            "raw_flags": self.raw_flags,
            "header_size": self.header_size,
        }


@dataclasses.dataclass(frozen=True)
class DartSnapshotSummary:
    """Comprehensive summary of Dart snapshots and Flutter symbols found."""
    total_bytes: int
    sha256_digest: str
    has_dart_snapshot: bool
    snapshots_found: List[DartSnapshotHeader]
    snapshot_hash: Optional[str]
    snapshot_hash_candidates: List[str]
    detected_kinds: List[str]
    symbols_detected: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "has_dart_snapshot": self.has_dart_snapshot,
            "snapshots_count": len(self.snapshots_found),
            "snapshots": [s.to_dict() for s in self.snapshots_found],
            "snapshot_hash": self.snapshot_hash,
            "snapshot_hash_candidates": self.snapshot_hash_candidates,
            "detected_kinds": self.detected_kinds,
            "symbols_detected": self.symbols_detected,
        }


class DartSnapshotParser:
    """Streaming and memory-bounded parser for Dart VM snapshot headers."""

    @classmethod
    def parse_header(
        cls,
        data: bytes,
        offset: int = 0,
        strict_length: bool = True,
    ) -> DartSnapshotHeader:
        """Parses a Dart snapshot header at the given offset with fail-closed validation.

        Args:
            data: Binary buffer containing the snapshot.
            offset: Byte offset where snapshot header starts.
            strict_length: If True, validates that declared length <= available buffer.

        Raises:
            ValueError: If header is truncated, magic is invalid, length overflows,
                        or hash / kind is corrupted.
        """
        if offset < 0:
            raise ValueError(f"Invalid negative offset: {offset}")

        avail = len(data) - offset
        if avail < MIN_HEADER_SIZE_32:
            raise ValueError(
                f"Truncated Dart snapshot header: minimum {MIN_HEADER_SIZE_32} bytes required, but got {avail}"
            )

        # Detect endianness and magic
        magic_le = struct.unpack_from("<I", data, offset)[0]
        magic_be = struct.unpack_from(">I", data, offset)[0]

        if magic_le == DART_SNAPSHOT_MAGIC_INT:
            endian = "<"
            endianness = "little"
        elif magic_be == DART_SNAPSHOT_MAGIC_INT:
            endian = ">"
            endianness = "big"
        else:
            raise ValueError(
                f"Invalid Dart snapshot magic: expected 0x{DART_SNAPSHOT_MAGIC_INT:08x}, "
                f"got 0x{magic_le:08x} (LE) / 0x{magic_be:08x} (BE)"
            )

        # Determine architecture (64-bit standard vs 32-bit legacy)
        arch_bits = 64
        parsed = None

        if avail >= MIN_HEADER_SIZE_64:
            # Try 64-bit layout: length (8 bytes), kind (8 bytes)
            length_64, kind_64 = struct.unpack_from(endian + "QQ", data, offset + 4)
            hash_bytes_64 = data[offset + 20 : offset + 52]
            try:
                candidate_hash_64 = hash_bytes_64.decode("ascii")
                if SNAPSHOT_HASH_REGEX.match(candidate_hash_64) and kind_64 in SNAPSHOT_KINDS:
                    parsed = (64, length_64, kind_64, candidate_hash_64, 52)
            except UnicodeDecodeError:
                parsed = None

        if parsed is None:
            # Fall back to 32-bit layout: length (4 bytes), kind (4 bytes)
            length_32, kind_32 = struct.unpack_from(endian + "II", data, offset + 4)
            hash_bytes_32 = data[offset + 12 : offset + 44]
            try:
                candidate_hash_32 = hash_bytes_32.decode("ascii")
                if SNAPSHOT_HASH_REGEX.match(candidate_hash_32) and kind_32 in SNAPSHOT_KINDS:
                    parsed = (32, length_32, kind_32, candidate_hash_32, 44)
            except UnicodeDecodeError:
                parsed = None

        if parsed is None:
            # Neither matched cleanly: diagnose failure fail-closed
            # If 64-bit was possible, diagnose on 64-bit fields
            if avail >= MIN_HEADER_SIZE_64:
                length_val, kind_val = struct.unpack_from(endian + "QQ", data, offset + 4)
                hash_bytes = data[offset + 20 : offset + 52]
            else:
                length_val, kind_val = struct.unpack_from(endian + "II", data, offset + 4)
                hash_bytes = data[offset + 12 : offset + 44]

            if kind_val not in SNAPSHOT_KINDS:
                raise ValueError(
                    f"Invalid Dart snapshot kind ID: {kind_val}. Allowed kinds: {sorted(SNAPSHOT_KINDS.keys())}"
                )

            try:
                decoded_hash = hash_bytes.decode("ascii")
            except UnicodeDecodeError as err:
                raise ValueError(f"Corrupted non-ASCII snapshot hash: {err}") from err

            if not SNAPSHOT_HASH_REGEX.match(decoded_hash):
                raise ValueError(
                    f"Invalid Dart snapshot hash: '{decoded_hash}', expected 32 hexadecimal characters"
                )
            raise ValueError("Malformed Dart snapshot header layout")

        arch_bits, length, kind_id, snapshot_hash, base_header_size = parsed

        # Validate snapshot length
        if length < 0:
            raise ValueError(f"Negative Dart snapshot length: {length}")
        if length > MAX_SNAPSHOT_SIZE:
            raise ValueError(
                f"Dart snapshot length overflow: declared {length} bytes exceeds maximum ceiling {MAX_SNAPSHOT_SIZE}"
            )

        # Dart VM snapshot length excludes the 4 magic bytes
        # Therefore total payload requirement is 4 + length
        if strict_length and (length + 4 > avail):
            raise ValueError(
                f"Dart snapshot length overflow: declared {length} bytes (total {length + 4}) "
                f"exceeds available buffer size {avail} bytes"
            )

        # Parse isolate flags / features string following the 32-byte hash
        flags_offset = offset + base_header_size
        flags_limit = min(offset + 4 + length, len(data)) if (4 + length <= avail) else len(data)
        flags_limit = min(flags_limit, flags_offset + 512)  # Bound flag reading to 512 bytes

        raw_flags_bytes = bytearray()
        for idx in range(flags_offset, flags_limit):
            b = data[idx]
            if b == 0:
                break
            raw_flags_bytes.append(b)

        raw_flags = raw_flags_bytes.decode("utf-8", errors="replace").strip()
        isolate_flags = [flag for flag in raw_flags.split() if flag]

        header_size = base_header_size + len(raw_flags_bytes) + (1 if (flags_offset + len(raw_flags_bytes) < len(data) and data[flags_offset + len(raw_flags_bytes)] == 0) else 0)

        return DartSnapshotHeader(
            magic=DART_SNAPSHOT_MAGIC_INT,
            endianness=endianness,
            arch_bits=arch_bits,
            header_offset=offset,
            snapshot_length=length,
            kind_id=kind_id,
            kind_name=SNAPSHOT_KINDS[kind_id],
            snapshot_hash=snapshot_hash,
            isolate_flags=isolate_flags,
            raw_flags=raw_flags,
            header_size=header_size,
        )

    @classmethod
    def scan_snapshots(
        cls,
        data: bytes,
        strict_length: bool = True,
    ) -> List[DartSnapshotHeader]:
        """Scans arbitrary binary buffer for Dart snapshot headers.

        Searches for both Little-Endian and Big-Endian magic patterns.
        """
        snapshots: List[DartSnapshotHeader] = []
        if len(data) < MIN_HEADER_SIZE_32:
            return snapshots

        # Find all occurrences of magic
        for magic_bytes in (DART_SNAPSHOT_MAGIC_LE, DART_SNAPSHOT_MAGIC_BE):
            start = 0
            while True:
                idx = data.find(magic_bytes, start)
                if idx == -1:
                    break
                try:
                    header = cls.parse_header(data, offset=idx, strict_length=strict_length)
                    snapshots.append(header)
                except ValueError:
                    # Not a valid snapshot header at this magic offset; proceed scanning
                    pass
                start = idx + 4

        snapshots.sort(key=lambda s: s.header_offset)
        return snapshots

    @classmethod
    def scan_symbols(cls, data: bytes) -> List[str]:
        """Detects known Flutter / Dart AOT symbol strings in binary."""
        found: List[str] = []
        for sym in KNOWN_DART_SYMBOLS:
            if sym in data:
                found.append(sym.decode("ascii"))
        return found

    @classmethod
    def inspect(cls, data: bytes, strict_length: bool = True) -> DartSnapshotSummary:
        """Inspects binary buffer or Dart snapshot payload and returns a comprehensive summary."""
        sha256_digest = hashlib.sha256(data).hexdigest()
        snapshots = cls.scan_snapshots(data, strict_length=strict_length)
        symbols = cls.scan_symbols(data)

        distinct_hashes: List[str] = []
        for s in snapshots:
            if s.snapshot_hash not in distinct_hashes:
                distinct_hashes.append(s.snapshot_hash)

        consensus_hash = distinct_hashes[0] if len(distinct_hashes) == 1 else None

        distinct_kinds: List[str] = []
        for s in snapshots:
            if s.kind_name not in distinct_kinds:
                distinct_kinds.append(s.kind_name)

        return DartSnapshotSummary(
            total_bytes=len(data),
            sha256_digest=sha256_digest,
            has_dart_snapshot=len(snapshots) > 0,
            snapshots_found=snapshots,
            snapshot_hash=consensus_hash,
            snapshot_hash_candidates=distinct_hashes,
            detected_kinds=distinct_kinds,
            symbols_detected=symbols,
        )


class DartSnapshotBuilder:
    """Synthetic builder for constructing valid and adversarial Dart snapshot buffers."""

    @staticmethod
    def build(
        kind: Union[int, str] = 3,
        snapshot_hash: str = "a1b2c3d4e5f60718293a4b5c6d7e8f90",
        isolate_flags: Union[str, List[str]] = "--sound-null-safety",
        payload: bytes = b"\x00" * 32,
        endianness: str = "little",
        arch_bits: int = 64,
        magic: int = DART_SNAPSHOT_MAGIC_INT,
        override_length: Optional[int] = None,
    ) -> bytes:
        """Constructs a binary Dart snapshot header and payload."""
        endian = "<" if endianness == "little" else ">"

        if isinstance(kind, str):
            clean_kind = kind.lower().strip()
            if clean_kind not in KIND_NAME_TO_ID:
                raise ValueError(f"Unknown kind string: {kind}")
            kind_id = KIND_NAME_TO_ID[clean_kind]
        else:
            kind_id = kind

        if isinstance(isolate_flags, list):
            flags_str = " ".join(isolate_flags)
        else:
            flags_str = isolate_flags

        flags_bytes = flags_str.encode("utf-8") + b"\x00"

        # Calculate base header size
        base_size = 52 if arch_bits == 64 else 44
        total_header_size = base_size + len(flags_bytes)

        # Snapshot length in Dart VM is payload size + (header size - 4)
        if override_length is not None:
            snapshot_len = override_length
        else:
            snapshot_len = (total_header_size - 4) + len(payload)

        hash_bytes = snapshot_hash.encode("ascii")
        if len(hash_bytes) != 32:
            raise ValueError(f"Snapshot hash must be exactly 32 ASCII characters, got {len(hash_bytes)}")

        buf = bytearray()
        buf.extend(struct.pack(endian + "I", magic))

        if arch_bits == 64:
            buf.extend(struct.pack(endian + "QQ", snapshot_len, kind_id))
        else:
            buf.extend(struct.pack(endian + "II", snapshot_len, kind_id))

        buf.extend(hash_bytes)
        buf.extend(flags_bytes)
        buf.extend(payload)

        return bytes(buf)
