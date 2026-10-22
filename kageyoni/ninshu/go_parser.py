"""Zero-dependency in-tree Go Binary Reconstructor & Build-Info Extractor (CH 13).

Recovers embedded Go build information, compiler version, modules, dependencies,
and compiler settings from native binaries (ELF, PE, Mach-O) using Go's buildinfo
magic pattern:
    MAGIC = \\xff Go buildinf: (ff 20 47 6f 20 62 75 69 6c 64 69 6e 66 3a)
    MODULE_START = 30 77 af 0c 92 74 08 02 41 e1 c1 07 e6 d6 18 e6
    MODULE_END   = f9 32 43 31 86 18 20 72 00 82 42 10 41 16 d8 f2

Adheres strictly to Go runtime/debug.BuildInfo and REA's inspect_go_binary specification.
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import struct
from typing import Any, Dict, List, Optional, Tuple

GO_BUILDINFO_MAGIC = bytes.fromhex("ff20476f206275696c64696e663a")
GO_MODULE_START = bytes.fromhex("3077af0c9274080241e1c107e6d618e6")
GO_MODULE_END = bytes.fromhex("f932433186182072008242104116d8f2")


@dataclasses.dataclass(frozen=True)
class GoModule:
    path: str
    version: str
    sum: Optional[str] = None
    replacement: Optional[Dict[str, Any]] = None


@dataclasses.dataclass(frozen=True)
class GoBuildInfo:
    header_offset: int
    go_version: Optional[str]
    path: Optional[str]
    main_module: Optional[GoModule]
    dependencies: List[GoModule]
    settings: Dict[str, str]
    raw_module_text: Optional[str]


@dataclasses.dataclass(frozen=True)
class GoBinarySummary:
    total_bytes: int
    sha256_digest: str
    has_go_build_info: bool
    build_info: Optional[GoBuildInfo]
    format_detected: str  # "elf", "pe", "macho", "raw"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "has_go_build_info": self.has_go_build_info,
            "build_info": dataclasses.asdict(self.build_info) if self.build_info else None,
            "format_detected": self.format_detected,
        }


def parse_go_varint_string(data: bytes, offset: int) -> Tuple[str, int]:
    """Reads a length-prefixed Go string where length is either 1 or 2 bytes."""
    if offset >= len(data):
        return "", offset
    length = data[offset]
    offset += 1
    if length >= 0x80:
        # Multibyte length
        if offset >= len(data):
            return "", offset
        length = (length & 0x7F) | (data[offset] << 7)
        offset += 1
    str_bytes = data[offset : offset + length]
    return str_bytes.decode("utf-8", errors="replace"), offset + length


class GoBinaryParser:
    """Zero-dependency streaming extractor for Go binaries."""

    @classmethod
    def detect_format(cls, data: bytes) -> str:
        if len(data) >= 4:
            if data[:4] == b"\x7fELF":
                return "elf"
            if data[:2] == b"MZ":
                return "pe"
            if data[:4] in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"):
                return "macho"
        return "raw"

    @classmethod
    def parse_module_text(cls, text: str) -> Tuple[Optional[str], Optional[GoModule], List[GoModule], Dict[str, str]]:
        """Parses Go runtime/debug module text lines (path, mod, dep, build settings)."""
        path = None
        main_module = None
        dependencies: List[GoModule] = []
        settings: Dict[str, str] = {}

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if not parts:
                continue
            verb = parts[0]
            if verb == "path" and len(parts) >= 2:
                path = parts[1]
            elif verb == "mod" and len(parts) >= 3:
                main_module = GoModule(path=parts[1], version=parts[2], sum=parts[3] if len(parts) > 3 else None)
            elif verb == "dep" and len(parts) >= 3:
                dependencies.append(GoModule(path=parts[1], version=parts[2], sum=parts[3] if len(parts) > 3 else None))
            elif verb == "build" and len(parts) >= 2:
                key_val = parts[1].split("=", 1)
                if len(key_val) == 2:
                    settings[key_val[0]] = key_val[1]

        return path, main_module, dependencies, settings

    @classmethod
    def parse_bytes(cls, data: bytes) -> GoBinarySummary:
        if not data:
            raise ValueError("Empty binary data supplied")

        total_bytes = len(data)
        digest = hashlib.sha256(data).hexdigest()
        fmt = cls.detect_format(data)

        # Scan for GO_BUILDINFO_MAGIC
        magic_idx = data.find(GO_BUILDINFO_MAGIC)
        if magic_idx == -1:
            return GoBinarySummary(
                total_bytes=total_bytes,
                sha256_digest=digest,
                has_go_build_info=False,
                build_info=None,
                format_detected=fmt,
            )

        # Found magic header: inspect payload immediately following magic (14 bytes)
        # Format: [14 bytes magic] [1 byte ptrsize] [1 byte endian]
        ptr_offset = magic_idx + len(GO_BUILDINFO_MAGIC)
        if ptr_offset + 2 > total_bytes:
            raise ValueError(f"Truncated Go buildinfo header at offset {magic_idx}")

        ptr_size = data[ptr_offset]
        is_big_endian = data[ptr_offset + 1] != 0

        # Scan forward for MODULE_START and MODULE_END
        mod_start = data.find(GO_MODULE_START, magic_idx)
        raw_module_text = None
        go_version = None
        path = None
        main_mod = None
        deps: List[GoModule] = []
        settings: Dict[str, str] = {}

        if mod_start != -1:
            mod_payload_start = mod_start + len(GO_MODULE_START)
            mod_end = data.find(GO_MODULE_END, mod_payload_start)
            if mod_end != -1:
                raw_bytes = data[mod_payload_start:mod_end]
                # Strip framing nulls or length prefixes
                try:
                    raw_module_text = raw_bytes.strip(b"\x00\n\r").decode("utf-8", errors="replace")
                    path, main_mod, deps, settings = cls.parse_module_text(raw_module_text)
                except Exception:
                    pass

        # Scan for go_version string (usually precedes or follows header in inline table)
        # Scan immediate vicinity (up to 256 bytes) for b"go1."
        vicinity = data[max(0, magic_idx - 64) : min(total_bytes, magic_idx + 512)]
        v_idx = vicinity.find(b"go1.")
        if v_idx != -1:
            # Read until null or whitespace
            v_end = v_idx
            while v_end < len(vicinity) and vicinity[v_end] not in (0, 0x0A, 0x20):
                v_end += 1
            go_version = vicinity[v_idx:v_end].decode("utf-8", errors="replace")

        build_info = GoBuildInfo(
            header_offset=magic_idx,
            go_version=go_version,
            path=path,
            main_module=main_mod,
            dependencies=deps,
            settings=settings,
            raw_module_text=raw_module_text,
        )

        return GoBinarySummary(
            total_bytes=total_bytes,
            sha256_digest=digest,
            has_go_build_info=True,
            build_info=build_info,
            format_detected=fmt,
        )
