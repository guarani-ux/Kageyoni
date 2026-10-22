"""Zero-dependency in-tree WebAssembly (WASM) binary streaming parser.

Parsed according to WebAssembly Core Specification (Release 2.0 / 1.0).
Provides zero-copy header inspection, section enumeration, and LEB128 decoding.
"""
from __future__ import annotations

import io
import struct
from typing import BinaryIO, Dict, Generator, List, NamedTuple, Optional, Tuple, Union

WASM_MAGIC = b"\x00asm"
WASM_VERSION = 1

SECTION_NAMES = {
    0: "custom",
    1: "type",
    2: "import",
    3: "function",
    4: "table",
    5: "memory",
    6: "global",
    7: "export",
    8: "start",
    9: "element",
    10: "code",
    11: "data",
    12: "data_count",
}


class WasmSectionHeader(NamedTuple):
    section_id: int
    name: str
    offset: int
    size: int
    payload_offset: int


class WasmModuleSummary(NamedTuple):
    version: int
    total_bytes: int
    sections_count: int
    sections: List[WasmSectionHeader]
    custom_sections: List[str]
    has_code: bool
    has_exports: bool


def decode_u32_leb128(stream: BinaryIO) -> Tuple[int, int]:
    """Decodes an unsigned 32-bit integer in LEB128 format from stream.

    Returns (value, bytes_read).
    Raises ValueError on truncation or integer overflow (> 5 bytes).
    """
    result = 0
    shift = 0
    bytes_read = 0

    while True:
        byte_raw = stream.read(1)
        if not byte_raw:
            raise ValueError("Truncated LEB128 integer sequence")
        byte = byte_raw[0]
        bytes_read += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
        if shift >= 35:
            raise ValueError("Overflow parsing LEB128 integer (exceeded 5 bytes for u32)")

    return result, bytes_read


class WasmParser:
    """Streaming parser for WebAssembly binaries."""

    @classmethod
    def parse_bytes(cls, data: bytes) -> WasmModuleSummary:
        return cls.parse_stream(io.BytesIO(data))

    @classmethod
    def parse_stream(cls, stream: BinaryIO) -> WasmModuleSummary:
        header = stream.read(8)
        if len(header) < 8:
            raise ValueError(f"Truncated WASM header: expected 8 bytes, got {len(header)}")

        magic, version = struct.unpack("<4sI", header)
        if magic != WASM_MAGIC:
            raise ValueError(f"Invalid WASM magic header: expected {WASM_MAGIC!r}, got {magic!r}")
        if version != WASM_VERSION:
            raise ValueError(f"Unsupported WASM version: expected {WASM_VERSION}, got {version}")

        sections: List[WasmSectionHeader] = []
        custom_sections: List[str] = []
        has_code = False
        has_exports = False

        while True:
            id_byte = stream.read(1)
            if not id_byte:
                break
            sec_id = id_byte[0]
            sec_offset = stream.tell() - 1

            sec_size, _ = decode_u32_leb128(stream)
            payload_offset = stream.tell()

            sec_name = SECTION_NAMES.get(sec_id, f"unknown_{sec_id}")

            if stream.seekable():
                curr = stream.tell()
                stream.seek(0, io.SEEK_END)
                stream_end = stream.tell()
                stream.seek(curr, io.SEEK_SET)
                if payload_offset + sec_size > stream_end:
                    raise ValueError(
                        f"Truncated section payload for section {sec_id} ({sec_name}): "
                        f"expected {sec_size} bytes, got {stream_end - payload_offset}"
                    )

            if sec_id == 0:
                # Custom section names start with length-prefixed UTF-8 string
                try:
                    name_len, _ = decode_u32_leb128(stream)
                    c_name_bytes = stream.read(name_len)
                    c_name = c_name_bytes.decode("utf-8", errors="replace")
                    custom_sections.append(c_name)
                except Exception:
                    custom_sections.append(f"custom_{len(custom_sections)}")
                # Reset stream pointer to end of this section
                stream.seek(payload_offset + sec_size, io.SEEK_SET)
            else:
                if sec_id == 7:
                    has_exports = True
                elif sec_id == 10:
                    has_code = True
                stream.seek(payload_offset + sec_size, io.SEEK_SET)

            sections.append(
                WasmSectionHeader(
                    section_id=sec_id,
                    name=sec_name,
                    offset=sec_offset,
                    size=sec_size,
                    payload_offset=payload_offset,
                )
            )

        total_bytes = stream.tell()
        return WasmModuleSummary(
            version=version,
            total_bytes=total_bytes,
            sections_count=len(sections),
            sections=sections,
            custom_sections=custom_sections,
            has_code=has_code,
            has_exports=has_exports,
        )
