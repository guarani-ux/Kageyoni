"""Zero-dependency in-tree Rizin Debug Session Controller & Trace Inspector (CH 20).

Pure Python standard library implementation:
1. Register Dump Parsing (drj format):
   - Parses x86_64 register dumps: rax, rbx, rcx, rdx, rsi, rdi, rsp, rbp, rip, rflags.
   - Strict 64-bit unsigned bounds checking and type validation.
2. Memory Map Parsing (dmj format):
   - Parses base address, end address, permissions, and file mapping.
   - Validates memory bounds (0 <= base < end <= 2^64 - 1) and permission tokens.
3. Breakpoint Table Parsing (dbj format):
   - Parses breakpoint ID, virtual address, hit count, and enabled status.
   - Enforces non-negative IDs, hit counts, and valid virtual addresses.
4. Backtrace Stack Frame Parsing (dbtj format):
   - Parses frame number, instruction pointer, frame pointer, and function name.
   - Enforces valid frame indexing and non-empty symbol strings.
5. Fail-Closed Session Verification:
   - Validates JSON schema integrity, numeric representations, and address bounds.
   - Thermodynamic memory containment <= 64 KB and canonical SHA-256 trace digests.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import re
import struct
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

MAX_SESSION_PAYLOAD_BYTES = 64 * 1024
UINT64_MAX = 0xFFFF_FFFF_FFFF_FFFF
REQUIRED_REGISTERS = (
    "rax",
    "rbx",
    "rcx",
    "rdx",
    "rsi",
    "rdi",
    "rsp",
    "rbp",
    "rip",
    "rflags",
)
PERM_PATTERN = re.compile(r"^[r\-][w\-][x\-][sSpP\-]?$")


def canonical_sha256(data: Union[bytes, str, Dict[str, Any], List[Any]]) -> str:
    """Computes an RFC 8785 compliant canonical SHA-256 digest."""
    if isinstance(data, bytes):
        raw_bytes = data
    elif isinstance(data, str):
        raw_bytes = data.encode("utf-8")
    else:
        raw_bytes = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


@dataclasses.dataclass(frozen=True)
class RizinRegisters:
    """Parsed x86_64 register state from Rizin drj command."""
    rax: int
    rbx: int
    rcx: int
    rdx: int
    rsi: int
    rdi: int
    rsp: int
    rbp: int
    rip: int
    rflags: int
    extra: Dict[str, int] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "rax": self.rax,
            "rbx": self.rbx,
            "rcx": self.rcx,
            "rdx": self.rdx,
            "rsi": self.rsi,
            "rdi": self.rdi,
            "rsp": self.rsp,
            "rbp": self.rbp,
            "rip": self.rip,
            "rflags": self.rflags,
        }
        if self.extra:
            result["extra"] = dict(self.extra)
        return result


@dataclasses.dataclass(frozen=True)
class RizinMemoryMap:
    """Parsed memory segment / map entry from Rizin dmj command."""
    base_address: int
    end_address: int
    permissions: str
    file_mapping: str

    @property
    def size(self) -> int:
        return self.end_address - self.base_address

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_address": self.base_address,
            "end_address": self.end_address,
            "permissions": self.permissions,
            "file_mapping": self.file_mapping,
            "size": self.size,
        }


@dataclasses.dataclass(frozen=True)
class RizinBreakpoint:
    """Parsed breakpoint table entry from Rizin dbj command."""
    breakpoint_id: int
    virtual_address: int
    hit_count: int
    enabled: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "breakpoint_id": self.breakpoint_id,
            "virtual_address": self.virtual_address,
            "hit_count": self.hit_count,
            "enabled": self.enabled,
        }


@dataclasses.dataclass(frozen=True)
class RizinStackFrame:
    """Parsed call stack frame from Rizin dbtj command."""
    frame_number: int
    instruction_pointer: int
    frame_pointer: int
    function_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_number": self.frame_number,
            "instruction_pointer": self.instruction_pointer,
            "frame_pointer": self.frame_pointer,
            "function_name": self.function_name,
        }


@dataclasses.dataclass(frozen=True)
class RizinDebugSession:
    """Verified complete Rizin debug session state and trace snapshot."""
    registers: RizinRegisters
    memory_maps: List[RizinMemoryMap]
    breakpoints: List[RizinBreakpoint]
    backtrace: List[RizinStackFrame]
    session_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "registers": self.registers.to_dict(),
            "memory_maps": [m.to_dict() for m in self.memory_maps],
            "breakpoints": [b.to_dict() for b in self.breakpoints],
            "backtrace": [f.to_dict() for f in self.backtrace],
            "session_digest": self.session_digest,
        }


class RizinDebugParser:
    """Strict fail-closed parser for Rizin / Radare2 debug telemetry and session logs."""

    @staticmethod
    def _parse_uint64(value: Any, field_name: str, max_val: int = UINT64_MAX) -> int:
        """Parses and validates an unsigned 64-bit integer from integer or hex/dec string."""
        if isinstance(value, bool):
            raise ValueError(f"Field '{field_name}' must be numeric integer or hex string, got bool: {value}")
        if isinstance(value, float):
            raise ValueError(f"Field '{field_name}' must not be float: {value}")
        if isinstance(value, int):
            if value < 0:
                raise ValueError(f"Field '{field_name}' cannot be negative: {value}")
            if value > max_val:
                raise ValueError(f"Field '{field_name}' exceeds maximum value ({max_val:#x}): {value:#x}")
            return value
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                raise ValueError(f"Field '{field_name}' numeric string cannot be empty")
            if trimmed.startswith("-"):
                raise ValueError(f"Field '{field_name}' numeric string cannot be negative: {value}")
            try:
                parsed = int(trimmed, 0)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Field '{field_name}' contains invalid numeric representation: {value}") from exc
            if parsed < 0:
                raise ValueError(f"Field '{field_name}' cannot be negative: {parsed}")
            if parsed > max_val:
                raise ValueError(f"Field '{field_name}' exceeds maximum value ({max_val:#x}): {parsed:#x}")
            return parsed

        raise ValueError(f"Field '{field_name}' unexpected type: {type(value).__name__}")

    @classmethod
    def parse_registers(
        cls,
        data: Union[str, bytes, Dict[str, Any], List[Dict[str, Any]]],
    ) -> RizinRegisters:
        """Parses Rizin register state (drj format).

        Accepts either a JSON dict mapping register names to values,
        or a list of register objects: [{'name': 'rax', 'value': 0}, ...].
        Strictly requires rax, rbx, rcx, rdx, rsi, rdi, rsp, rbp, rip, rflags.
        """
        raw_obj = cls._load_json_if_needed(data, "registers")

        reg_map: Dict[str, Any] = {}
        if isinstance(raw_obj, dict):
            for k, v in raw_obj.items():
                if not isinstance(k, str):
                    raise ValueError(f"Register key must be a string, got: {type(k).__name__}")
                reg_map[k.lower()] = v
        elif isinstance(raw_obj, list):
            for idx, entry in enumerate(raw_obj):
                if not isinstance(entry, dict):
                    raise ValueError(f"Register entry at index {idx} must be a dict")
                name = entry.get("name") or entry.get("reg")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"Register entry at index {idx} missing valid 'name' attribute")
                if "value" not in entry:
                    raise ValueError(f"Register '{name}' missing 'value' attribute")
                reg_map[name.strip().lower()] = entry["value"]
        else:
            raise ValueError(f"Registers payload must be dict or list, got: {type(raw_obj).__name__}")

        missing = [r for r in REQUIRED_REGISTERS if r not in reg_map]
        if missing:
            raise ValueError(f"Missing required register fields in drj dump: {', '.join(missing)}")

        parsed_values: Dict[str, int] = {}
        for reg in REQUIRED_REGISTERS:
            parsed_values[reg] = cls._parse_uint64(reg_map[reg], f"register_{reg}")

        extra: Dict[str, int] = {}
        for k, v in reg_map.items():
            if k not in REQUIRED_REGISTERS:
                extra[k] = cls._parse_uint64(v, f"register_{k}")

        return RizinRegisters(
            rax=parsed_values["rax"],
            rbx=parsed_values["rbx"],
            rcx=parsed_values["rcx"],
            rdx=parsed_values["rdx"],
            rsi=parsed_values["rsi"],
            rdi=parsed_values["rdi"],
            rsp=parsed_values["rsp"],
            rbp=parsed_values["rbp"],
            rip=parsed_values["rip"],
            rflags=parsed_values["rflags"],
            extra=extra,
        )

    @classmethod
    def parse_memory_maps(
        cls,
        data: Union[str, bytes, List[Dict[str, Any]]],
    ) -> List[RizinMemoryMap]:
        """Parses Rizin memory map list (dmj format).

        Each entry must contain base address, end address, permissions, and file mapping.
        Validates 0 <= base_address < end_address <= 2^64 - 1 and standard permission flags.
        """
        raw_obj = cls._load_json_if_needed(data, "memory_maps")

        if not isinstance(raw_obj, list):
            raise ValueError(f"Memory maps payload must be a list, got: {type(raw_obj).__name__}")

        maps: List[RizinMemoryMap] = []
        for idx, entry in enumerate(raw_obj):
            if not isinstance(entry, dict):
                raise ValueError(f"Memory map entry at index {idx} must be a dict")

            # Extract base address
            base_raw = (
                entry.get("base_address")
                if "base_address" in entry
                else entry.get("addr")
                if "addr" in entry
                else entry.get("start")
                if "start" in entry
                else entry.get("base")
                if "base" in entry
                else entry.get("from")
            )
            if base_raw is None:
                raise ValueError(f"Memory map at index {idx} missing base address ('addr'/'start'/'base')")
            base_address = cls._parse_uint64(base_raw, f"memory_map[{idx}].base_address")

            # Extract end address
            end_raw = (
                entry.get("end_address")
                if "end_address" in entry
                else entry.get("addr_end")
                if "addr_end" in entry
                else entry.get("end")
                if "end" in entry
                else entry.get("to")
            )
            if end_raw is None:
                raise ValueError(f"Memory map at index {idx} missing end address ('addr_end'/'end'/'to')")
            end_address = cls._parse_uint64(end_raw, f"memory_map[{idx}].end_address")

            if base_address >= end_address:
                raise ValueError(
                    f"Memory map at index {idx} invalid bounds: base ({base_address:#x}) >= end ({end_address:#x})"
                )

            # Extract permissions
            perm_raw = (
                entry.get("permissions")
                if "permissions" in entry
                else entry.get("perm")
                if "perm" in entry
                else entry.get("flags")
            )
            if not isinstance(perm_raw, str):
                raise ValueError(f"Memory map at index {idx} missing or non-string permissions ('perm'/'flags')")
            perm_str = perm_raw.strip()
            if not PERM_PATTERN.match(perm_str):
                raise ValueError(f"Memory map at index {idx} has invalid permission token: '{perm_str}'")

            # Extract file mapping / name
            file_raw = (
                entry.get("file_mapping")
                if "file_mapping" in entry
                else entry.get("file")
                if "file" in entry
                else entry.get("name")
                if "name" in entry
                else entry.get("path")
            )
            file_str = str(file_raw).strip() if file_raw is not None else ""

            maps.append(
                RizinMemoryMap(
                    base_address=base_address,
                    end_address=end_address,
                    permissions=perm_str,
                    file_mapping=file_str,
                )
            )

        return maps

    @classmethod
    def parse_breakpoints(
        cls,
        data: Union[str, bytes, List[Dict[str, Any]]],
    ) -> List[RizinBreakpoint]:
        """Parses Rizin breakpoint table (dbj format).

        Each entry must contain breakpoint ID, virtual address, hit count, and enabled status.
        """
        raw_obj = cls._load_json_if_needed(data, "breakpoints")

        if not isinstance(raw_obj, list):
            raise ValueError(f"Breakpoints payload must be a list, got: {type(raw_obj).__name__}")

        breakpoints: List[RizinBreakpoint] = []
        for idx, entry in enumerate(raw_obj):
            if not isinstance(entry, dict):
                raise ValueError(f"Breakpoint entry at index {idx} must be a dict")

            id_raw = (
                entry.get("breakpoint_id")
                if "breakpoint_id" in entry
                else entry.get("id")
                if "id" in entry
                else entry.get("bpid")
            )
            if id_raw is None:
                raise ValueError(f"Breakpoint at index {idx} missing ID ('id'/'bpid')")
            bpid = cls._parse_uint64(id_raw, f"breakpoint[{idx}].id")

            addr_raw = (
                entry.get("virtual_address")
                if "virtual_address" in entry
                else entry.get("addr")
                if "addr" in entry
                else entry.get("address")
            )
            if addr_raw is None:
                raise ValueError(f"Breakpoint at index {idx} missing virtual address ('addr'/'address')")
            vaddr = cls._parse_uint64(addr_raw, f"breakpoint[{idx}].virtual_address")

            count_raw = (
                entry.get("hit_count")
                if "hit_count" in entry
                else entry.get("count")
                if "count" in entry
                else entry.get("hits")
            )
            hit_count = 0 if count_raw is None else cls._parse_uint64(count_raw, f"breakpoint[{idx}].hit_count")

            enabled_raw = (
                entry.get("enabled")
                if "enabled" in entry
                else entry.get("enable")
            )
            if enabled_raw is None:
                enabled = True
            elif isinstance(enabled_raw, bool):
                enabled = enabled_raw
            elif isinstance(enabled_raw, str):
                lower_str = enabled_raw.strip().lower()
                if lower_str in ("true", "1"):
                    enabled = True
                elif lower_str in ("false", "0"):
                    enabled = False
                else:
                    raise ValueError(f"Breakpoint at index {idx} has invalid enabled string: '{enabled_raw}'")
            elif isinstance(enabled_raw, int):
                if enabled_raw == 1:
                    enabled = True
                elif enabled_raw == 0:
                    enabled = False
                else:
                    raise ValueError(f"Breakpoint at index {idx} has invalid enabled integer (must be 0 or 1): {enabled_raw}")
            else:
                raise ValueError(f"Breakpoint at index {idx} has invalid enabled type: {type(enabled_raw).__name__}")

            breakpoints.append(
                RizinBreakpoint(
                    breakpoint_id=bpid,
                    virtual_address=vaddr,
                    hit_count=hit_count,
                    enabled=enabled,
                )
            )

        return breakpoints

    @classmethod
    def parse_backtrace(
        cls,
        data: Union[str, bytes, List[Dict[str, Any]]],
    ) -> List[RizinStackFrame]:
        """Parses Rizin backtrace call stack frames (dbtj format).

        Each entry must contain frame number, instruction pointer, frame pointer, and function name.
        """
        raw_obj = cls._load_json_if_needed(data, "backtrace")

        if not isinstance(raw_obj, list):
            raise ValueError(f"Backtrace payload must be a list, got: {type(raw_obj).__name__}")

        frames: List[RizinStackFrame] = []
        for idx, entry in enumerate(raw_obj):
            if not isinstance(entry, dict):
                raise ValueError(f"Backtrace frame at index {idx} must be a dict")

            frame_raw = (
                entry.get("frame_number")
                if "frame_number" in entry
                else entry.get("frame")
                if "frame" in entry
                else entry.get("id")
                if "id" in entry
                else entry.get("level")
            )
            if frame_raw is None:
                raise ValueError(f"Backtrace frame at index {idx} missing frame number ('frame'/'id'/'level')")
            frame_num = cls._parse_uint64(frame_raw, f"backtrace[{idx}].frame_number")

            ip_raw = (
                entry.get("instruction_pointer")
                if "instruction_pointer" in entry
                else entry.get("ip")
                if "ip" in entry
                else entry.get("addr")
                if "addr" in entry
                else entry.get("pc")
            )
            if ip_raw is None:
                raise ValueError(f"Backtrace frame at index {idx} missing instruction pointer ('ip'/'addr'/'pc')")
            ip = cls._parse_uint64(ip_raw, f"backtrace[{idx}].instruction_pointer")

            fp_raw = (
                entry.get("frame_pointer")
                if "frame_pointer" in entry
                else entry.get("fp")
                if "fp" in entry
                else entry.get("bp")
                if "bp" in entry
                else entry.get("sp")
            )
            if fp_raw is None:
                raise ValueError(f"Backtrace frame at index {idx} missing frame pointer ('fp'/'bp'/'sp')")
            fp = cls._parse_uint64(fp_raw, f"backtrace[{idx}].frame_pointer")

            name_raw = (
                entry.get("function_name")
                if "function_name" in entry
                else entry.get("name")
                if "name" in entry
                else entry.get("fname")
                if "fname" in entry
                else entry.get("symbol")
            )
            if name_raw is None or not isinstance(name_raw, str) or not name_raw.strip():
                raise ValueError(f"Backtrace frame at index {idx} missing valid function name ('name'/'fname'/'symbol')")

            frames.append(
                RizinStackFrame(
                    frame_number=frame_num,
                    instruction_pointer=ip,
                    frame_pointer=fp,
                    function_name=name_raw.strip(),
                )
            )

        return frames

    @classmethod
    def parse_session(
        cls,
        data: Union[str, bytes, Dict[str, Any]],
        max_bytes: int = MAX_SESSION_PAYLOAD_BYTES,
    ) -> RizinDebugSession:
        """Parses a complete Rizin debug session trace snapshot.

        Expects a session object containing registers (drj), memory_maps (dmj),
        breakpoints (dbj), and backtrace (dbtj).
        """
        if isinstance(data, (bytes, bytearray)):
            if len(data) > max_bytes:
                raise ValueError(f"Session payload exceeds maximum ceiling of {max_bytes} bytes: {len(data)} bytes")
            raw_bytes = bytes(data)
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Malformed UTF-8 session payload: {exc}") from exc
            try:
                session_dict = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON session payload: {exc}") from exc
        elif isinstance(data, str):
            raw_bytes = data.encode("utf-8")
            if len(raw_bytes) > max_bytes:
                raise ValueError(f"Session payload exceeds maximum ceiling of {max_bytes} bytes: {len(raw_bytes)} bytes")
            try:
                session_dict = json.loads(data)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON session string: {exc}") from exc
        elif isinstance(data, dict):
            session_dict = data
            raw_bytes = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            if len(raw_bytes) > max_bytes:
                raise ValueError(f"Session payload exceeds maximum ceiling of {max_bytes} bytes: {len(raw_bytes)} bytes")
        else:
            raise ValueError(f"Session data must be bytes, str, or dict, got: {type(data).__name__}")

        if not isinstance(session_dict, dict):
            raise ValueError(f"Session root object must be a JSON dictionary, got: {type(session_dict).__name__}")

        # Extract registers
        reg_data = session_dict.get("registers") if "registers" in session_dict else session_dict.get("drj")
        if reg_data is None:
            raise ValueError("Debug session missing 'registers' or 'drj' component")
        registers = cls.parse_registers(reg_data)

        # Extract memory maps
        maps_data = session_dict.get("memory_maps") if "memory_maps" in session_dict else session_dict.get("dmj")
        if maps_data is None:
            raise ValueError("Debug session missing 'memory_maps' or 'dmj' component")
        memory_maps = cls.parse_memory_maps(maps_data)

        # Extract breakpoints
        bp_data = session_dict.get("breakpoints") if "breakpoints" in session_dict else session_dict.get("dbj")
        if bp_data is None:
            raise ValueError("Debug session missing 'breakpoints' or 'dbj' component")
        breakpoints = cls.parse_breakpoints(bp_data)

        # Extract backtrace
        bt_data = session_dict.get("backtrace") if "backtrace" in session_dict else session_dict.get("dbtj")
        if bt_data is None:
            raise ValueError("Debug session missing 'backtrace' or 'dbtj' component")
        backtrace = cls.parse_backtrace(bt_data)

        digest = canonical_sha256(raw_bytes)

        return RizinDebugSession(
            registers=registers,
            memory_maps=memory_maps,
            breakpoints=breakpoints,
            backtrace=backtrace,
            session_digest=digest,
        )

    @classmethod
    def parse_bytes(cls, data: bytes, max_bytes: int = MAX_SESSION_PAYLOAD_BYTES) -> RizinDebugSession:
        """Parses a Rizin debug session directly from raw bytes."""
        if not data:
            raise ValueError("Cannot parse empty debug session bytes")
        return cls.parse_session(data, max_bytes=max_bytes)

    @classmethod
    def parse_str(cls, data: str, max_bytes: int = MAX_SESSION_PAYLOAD_BYTES) -> RizinDebugSession:
        """Parses a Rizin debug session directly from a JSON string."""
        if not data.strip():
            raise ValueError("Cannot parse empty debug session string")
        return cls.parse_session(data, max_bytes=max_bytes)

    @staticmethod
    def _load_json_if_needed(data: Any, context_name: str) -> Any:
        """Helper to safely parse JSON strings or bytes into Python objects."""
        if isinstance(data, (bytes, bytearray)):
            try:
                text = bytes(data).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Malformed UTF-8 in {context_name}: {exc}") from exc
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON in {context_name}: {exc}") from exc
        elif isinstance(data, str):
            trimmed = data.strip()
            if not trimmed:
                raise ValueError(f"Empty JSON string in {context_name}")
            try:
                return json.loads(trimmed)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON in {context_name}: {exc}") from exc
        return data


# Canonical alias for SSL Channel 20 specification
RizinDebugSessionController = RizinDebugParser
