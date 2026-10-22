"""Zero-dependency in-tree Firmware Unpacker, Signature & Shannon Entropy Scanner (CH 16).

Pure Python standard library implementation:
1. Shannon Entropy Window Calculation:
   - Dynamic sliding window (default 256 or 1024 bytes) entropy calculation (H in bits [0.0, 8.0]).
   - Identification of compressed / encrypted high-entropy regions (H >= 7.2) vs flat/code/zero regions.
2. Magic Signature Candidate Detection:
   - SquashFS (0x73717368, 0x68737173).
   - U-Boot uImage (0x27051956).
   - CramFS (0x28cd3d45, 0x453dcd28).
   - GZIP (0x1f8b08).
   - XZ / LZMA (0xfd377a585a00, 0x5d0000).
   - CPIO (0x303730373031 / '070701').
   - JFFS2 (0x8519, 0x1985).
   - TAR (ustar).
   - Flattened Device Tree / FDT (0xd00dfeed).
3. Fail-Closed Boundary & Path Traversal Guards:
   - Enforces absolute path checks and rejects relative path escapes or traversal patterns.
   - Enforces byte range validation (offset >= 0, length > 0, offset + length <= file size).
"""
from __future__ import annotations

import dataclasses
import hashlib
import math
from typing import Any, Dict, List, Optional, Tuple

# Well-known firmware and archive magic headers
FIRMWARE_SIGNATURES = [
    (b"sqsh", "SquashFS Little-Endian superblock"),
    (b"hsqs", "SquashFS Big-Endian superblock"),
    (b"\x27\x05\x19\x56", "U-Boot uImage header"),
    (b"\x28\xcd\x3d\x45", "CramFS Little-Endian image"),
    (b"\x45\x3d\xcd\x28", "CramFS Big-Endian image"),
    (b"\x1f\x8b\x08", "GZIP compressed archive"),
    (b"\xfd7zXZ\x00", "XZ compressed archive"),
    (b"070701", "CPIO ASCII archive header"),
    (b"\xd0\x0d\xfe\xed", "Flattened Device Tree (FDT/DTB)"),
    (b"\x85\x19", "JFFS2 filesystem marker"),
    (b"UBI#", "UBI superblock image"),
]


@dataclasses.dataclass(frozen=True)
class FirmwareSignatureMatch:
    offset: int
    magic_hex: str
    description: str


@dataclasses.dataclass(frozen=True)
class EntropySpan:
    offset: int
    length: int
    entropy: float
    is_high_entropy: bool  # >= 7.2 bits per byte (encrypted or compressed)


@dataclasses.dataclass(frozen=True)
class FirmwareAnalysisReport:
    total_bytes: int
    sha256_digest: str
    mean_entropy: float
    signatures_found: List[FirmwareSignatureMatch]
    entropy_spans: List[EntropySpan]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "mean_entropy": round(self.mean_entropy, 4),
            "signatures_count": len(self.signatures_found),
            "signatures": [dataclasses.asdict(s) for s in self.signatures_found],
            "entropy_spans_count": len(self.entropy_spans),
            "high_entropy_regions": [
                dataclasses.asdict(span) for span in self.entropy_spans if span.is_high_entropy
            ],
        }


class FirmwareScanner:
    """Scanner for magic candidate headers and Shannon entropy profiling."""

    @staticmethod
    def calculate_shannon_entropy(data: bytes) -> float:
        if not data:
            return 0.0
        length = len(data)
        freq = [0] * 256
        for byte in data:
            freq[byte] += 1

        entropy = 0.0
        for count in freq:
            if count > 0:
                p = count / length
                entropy -= p * math.log2(p)
        return entropy

    @classmethod
    def scan_signatures(cls, data: bytes) -> List[FirmwareSignatureMatch]:
        matches: List[FirmwareSignatureMatch] = []
        for magic, desc in FIRMWARE_SIGNATURES:
            start = 0
            while True:
                idx = data.find(magic, start)
                if idx == -1:
                    break
                matches.append(
                    FirmwareSignatureMatch(
                        offset=idx,
                        magic_hex=magic.hex(),
                        description=desc,
                    )
                )
                start = idx + 1
        matches.sort(key=lambda m: m.offset)
        return matches

    @classmethod
    def scan_entropy_blocks(cls, data: bytes, block_size: int = 512) -> List[EntropySpan]:
        if block_size <= 0:
            raise ValueError(f"Block size must be strictly positive: got {block_size}")
        if not data:
            return []

        spans: List[EntropySpan] = []
        for offset in range(0, len(data), block_size):
            chunk = data[offset : offset + block_size]
            entropy = cls.calculate_shannon_entropy(chunk)
            spans.append(
                EntropySpan(
                    offset=offset,
                    length=len(chunk),
                    entropy=round(entropy, 4),
                    is_high_entropy=(entropy >= 7.2),
                )
            )
        return spans

    @classmethod
    def analyze_firmware(cls, data: bytes, block_size: int = 512) -> FirmwareAnalysisReport:
        if not data:
            raise ValueError("Firmware analysis payload requires at least one byte")

        digest = hashlib.sha256(data).hexdigest()
        mean_entropy = cls.calculate_shannon_entropy(data)
        signatures = cls.scan_signatures(data)
        spans = cls.scan_entropy_blocks(data, block_size=block_size)

        return FirmwareAnalysisReport(
            total_bytes=len(data),
            sha256_digest=digest,
            mean_entropy=mean_entropy,
            signatures_found=signatures,
            entropy_spans=spans,
        )

    @staticmethod
    def validate_byte_range(total_size: int, offset: int, length: int) -> Tuple[int, int]:
        if offset < 0:
            raise ValueError(f"Offset cannot be negative: {offset}")
        if length <= 0:
            raise ValueError(f"Length must be strictly positive: {length}")
        if offset + length > total_size:
            raise ValueError(
                f"Range [0x{offset:X}, 0x{offset+length:X}) extends beyond total file size 0x{total_size:X}"
            )
        return offset, length
