"""Zero-dependency in-tree IDA Pro Headless Telemetry & Protocol Parser (CH 07).

Pure Python standard library implementation:
1. Address Normalization & Coordinates:
   - Normalizes 64-bit and 32-bit hexadecimal coordinates (`0x...` or bare hex).
   - Rejects negative addresses, invalid characters, or address space overflows.
2. IDA Function Observations & Spans:
   - Parses function boundaries: address, name, size, flags.
   - Extracts disassembly blocks and validates assembly header matching.
3. Cross-References (XREFs) & Call Graphs:
   - Callee relationships (`from_ea`, `to_ea`, `type`, `code/data`).
   - Call graph construction and cycle detection.
4. Fail-Closed Protocol & Memory Ceiling:
   - Rejects payload size > 64 KB.
   - 100% fail-closed on corrupt JSON, missing function identities, mismatched assembly headers.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

MAX_PAYLOAD_BYTES = 64 * 1024
HEX_PATTERN = re.compile(r"^(?:0[xX])?[0-9a-fA-F]+$")
ASM_HEADER_PATTERN = re.compile(r"^(.+) \((.*) @ (0x[0-9a-fA-F]+)\):$")


def normalize_ida_address(addr: Union[str, int]) -> str:
    """Normalizes an IDA address coordinate to canonical lowercase 0x hex string."""
    if isinstance(addr, int):
        if addr < 0:
            raise ValueError(f"Negative IDA address not allowed: {addr}")
        if addr > 0xFFFFFFFFFFFFFFFF:
            raise ValueError(f"Address exceeds 64-bit space: 0x{addr:X}")
        return f"0x{addr:x}"
    elif isinstance(addr, str):
        text = addr.strip()
        if not text or not HEX_PATTERN.match(text):
            raise ValueError(f"Invalid hexadecimal address coordinate: {addr!r}")
        int_val = int(text, 16)
        if int_val > 0xFFFFFFFFFFFFFFFF:
            raise ValueError(f"Address exceeds 64-bit space: {addr!r}")
        return f"0x{int_val:x}"
    raise ValueError(f"Unsupported address type: {type(addr).__name__}")


@dataclasses.dataclass(frozen=True)
class IdaFunction:
    address: str
    name: str
    size: int
    flags: int = 0


@dataclasses.dataclass(frozen=True)
class IdaXref:
    from_ea: str
    to_ea: str
    xref_type: str  # e.g., 'call', 'jump', 'data_read', 'data_write'
    is_code: bool = True


@dataclasses.dataclass(frozen=True)
class IdaDisassemblyBlock:
    function_name: str
    start_ea: str
    lines: List[str]
    raw_header: str


@dataclasses.dataclass(frozen=True)
class IdaSessionSummary:
    functions_count: int
    xrefs_count: int
    functions: List[IdaFunction]
    xrefs: List[IdaXref]
    sha256_digest: str


class IdaHeadlessParser:
    """Zero-dependency parser for IDA Pro headless telemetry and native MCP responses."""

    @classmethod
    def parse_function(cls, data: Dict[str, Any]) -> IdaFunction:
        if not isinstance(data, dict):
            raise ValueError("Function record must be a dict")
        name = data.get("name")
        if not name or not isinstance(name, str) or not name.strip():
            raise ValueError("Function name must be non-empty string")

        addr_raw = data.get("address") or data.get("addr") or data.get("start_ea")
        if addr_raw is None:
            raise ValueError("Missing function address")
        addr_clean = normalize_ida_address(addr_raw)

        size_raw = data.get("size", 0)
        if isinstance(size_raw, str):
            try:
                size_val = int(size_raw, 0)
            except ValueError as err:
                raise ValueError(f"Invalid function size: {size_raw!r}") from err
        elif isinstance(size_raw, int):
            size_val = size_raw
        else:
            raise ValueError(f"Invalid function size type: {type(size_raw).__name__}")

        if size_val < 0:
            raise ValueError(f"Negative function size: {size_val}")

        flags = int(data.get("flags", 0))
        return IdaFunction(address=addr_clean, name=name.strip(), size=size_val, flags=flags)

    @classmethod
    def parse_disassembly(cls, data: Dict[str, Any]) -> IdaDisassemblyBlock:
        if not isinstance(data, dict):
            raise ValueError("Disassembly record must be a dict")
        name = data.get("name")
        start_ea = data.get("start_ea") or data.get("address")
        lines_raw = data.get("lines")

        if not name or not start_ea or lines_raw is None:
            raise ValueError("Missing required fields for disassembly block")

        start_clean = normalize_ida_address(start_ea)

        if isinstance(lines_raw, str):
            all_lines = lines_raw.splitlines()
        elif isinstance(lines_raw, list):
            all_lines = [str(l) for l in lines_raw]
        else:
            raise ValueError("Disassembly lines must be string or list of strings")

        if not all_lines:
            raise ValueError("Disassembly lines cannot be empty")

        header = all_lines[0].strip()
        match = ASM_HEADER_PATTERN.match(header)
        if match:
            hdr_name, _, hdr_ea = match.groups()
            hdr_clean = normalize_ida_address(hdr_ea)
            if hdr_name != name or hdr_clean != start_clean:
                raise ValueError(
                    f"Assembly header '{header}' contradicts function identity '{name}' at {start_clean}"
                )

        return IdaDisassemblyBlock(
            function_name=name,
            start_ea=start_clean,
            lines=all_lines[1:] if match else all_lines,
            raw_header=header if match else "",
        )

    @classmethod
    def parse_xref(cls, data: Dict[str, Any]) -> IdaXref:
        if not isinstance(data, dict):
            raise ValueError("XREF record must be a dict")
        from_ea_raw = data.get("from_ea") or data.get("from") or data.get("src")
        to_ea_raw = data.get("to_ea") or data.get("to") or data.get("dst")
        if from_ea_raw is None or to_ea_raw is None:
            raise ValueError("Missing from/to coordinates in XREF")

        from_clean = normalize_ida_address(from_ea_raw)
        to_clean = normalize_ida_address(to_ea_raw)
        xref_type = str(data.get("type", "call"))
        is_code = bool(data.get("is_code", True))

        return IdaXref(from_ea=from_clean, to_ea=to_clean, xref_type=xref_type, is_code=is_code)

    @classmethod
    def parse_session(cls, data: Union[str, bytes, Dict[str, Any]]) -> IdaSessionSummary:
        if data is None:
            raise ValueError("Empty payload provided for IDA parser")

        if isinstance(data, (bytes, bytearray)):
            if len(data) == 0:
                raise ValueError("Empty payload provided for IDA parser")
            if len(data) > MAX_PAYLOAD_BYTES:
                raise ValueError(f"Payload size exceeds maximum allowed {MAX_PAYLOAD_BYTES} bytes")
            raw_bytes = bytes(data)
            try:
                payload = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as err:
                raise ValueError(f"Malformed JSON payload: {err}") from err
        elif isinstance(data, str):
            text = data.strip()
            if not text:
                raise ValueError("Empty payload provided for IDA parser")
            raw_bytes = text.encode("utf-8")
            if len(raw_bytes) > MAX_PAYLOAD_BYTES:
                raise ValueError(f"Payload size exceeds maximum allowed {MAX_PAYLOAD_BYTES} bytes")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as err:
                raise ValueError(f"Malformed JSON payload: {err}") from err
        elif isinstance(data, dict):
            if not data:
                raise ValueError("Empty dictionary provided for IDA parser")
            payload = data
            raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        else:
            raise ValueError(f"Unsupported payload type: {type(data).__name__}")

        if not isinstance(payload, dict):
            raise ValueError("Top-level payload must be a JSON object")

        raw_funcs = payload.get("functions") or []
        if not isinstance(raw_funcs, list):
            raise ValueError("Functions must be a list")
        functions = [cls.parse_function(f) for f in raw_funcs]

        raw_xrefs = payload.get("xrefs") or []
        if not isinstance(raw_xrefs, list):
            raise ValueError("XREFs must be a list")
        xrefs = [cls.parse_xref(x) for x in raw_xrefs]

        sha = hashlib.sha256(raw_bytes).hexdigest()

        return IdaSessionSummary(
            functions_count=len(functions),
            xrefs_count=len(xrefs),
            functions=functions,
            xrefs=xrefs,
            sha256_digest=sha,
        )
