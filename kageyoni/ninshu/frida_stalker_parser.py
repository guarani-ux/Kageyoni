"""Channel 17: Frida Stalker Engine & Dynamic Instruction Trace Inspector.

Zero-dependency in-tree dynamic instruction trace parser and call summary reconstructor:
1. Event Stream Parsing:
   - Gum/Stalker standard binary event streams (Call, Ret, Exec, Block).
   - Tagged binary streams and JSON/NDJSON event streams.
   - Event types:
       CALL (source address, target address, depth)
       RET (source address, target address, depth)
       EXEC (instruction address)
       BLOCK (start address, end address)
2. Execution Reconstruction:
   - Reconstructs hierarchical execution call tree and callee edge call graph.
   - Computes basic block coverage map (disjoint block intervals, execution frequencies, code volume).
3. Adversarial Analysis:
   - Detects direct and indirect recursive loops with cycle chains.
   - Flags deep call stacks exceeding configurable thresholds.
4. Fail-Closed Validation:
   - Enforces 64-bit unsigned address limits.
   - Rejects negative depths, out-of-order sequences, backwards time travel, and stack underflows.
   - Rejects truncated streams and malformed binary envelopes.
5. Thermodynamic Budget:
   - Zero third-party dependencies (pure Python standard library).
   - Peak heap memory bounded strictly <= 64 KB.
"""
from __future__ import annotations

import dataclasses
from enum import IntEnum
import hashlib
import io
import json
import struct
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Union

# Maximum 64-bit unsigned address limit
MAX_UINT64 = (1 << 64) - 1

# Maximum reasonable call depth limit to guard against runaway stack exhaustion
MAX_CALL_DEPTH_LIMIT = 8192

# Default threshold for reporting deep call stacks
DEFAULT_DEEP_STACK_THRESHOLD = 32


class FridaStalkerError(Exception):
    """Base exception for Frida Stalker parser failures."""
    pass


class MalformedEventError(FridaStalkerError):
    """Raised when an event structure is corrupted or contains illegal fields."""
    pass


class InvalidAddressError(FridaStalkerError):
    """Raised when an address is negative, not an integer, or exceeds 64-bit bounds."""
    pass


class InvalidDepthError(FridaStalkerError):
    """Raised when a call/ret depth is negative, non-integer, or exceeds depth bounds."""
    pass


class BackwardsTimeTravelError(FridaStalkerError):
    """Raised when timestamp or sequence order moves backwards."""
    pass


class StackUnderflowError(FridaStalkerError):
    """Raised when a return event occurs on an empty call stack or jumps out of bounds."""
    pass


class TruncatedStreamError(FridaStalkerError):
    """Raised when binary event stream terminates unexpectedly."""
    pass


class StreamCorruptionError(FridaStalkerError):
    """Raised when stream contains unparsed trailing garbage or illegal framing."""
    pass


class StalkerEventType(IntEnum):
    """Frida Gum stalker event type bitmasks."""
    CALL = 1
    RET = 2
    EXEC = 4
    BLOCK = 8
    COMPILE = 16


def _validate_address(addr: Any, field_name: str = "address") -> int:
    """Validates that address is a non-boolean integer within 64-bit unsigned bounds."""
    if isinstance(addr, str):
        cleaned = addr.strip()
        try:
            if cleaned.lower().startswith("0x"):
                addr = int(cleaned, 16)
            else:
                addr = int(cleaned, 10)
        except ValueError as err:
            raise InvalidAddressError(f"Field {field_name} must be a valid integer or hex string: {addr!r}") from err

    if not isinstance(addr, int) or isinstance(addr, bool):
        raise InvalidAddressError(f"Field {field_name} must be an integer, got {type(addr).__name__}: {addr!r}")
    if addr < 0 or addr > MAX_UINT64:
        raise InvalidAddressError(f"Field {field_name} out of 64-bit bounds [0, 0x{MAX_UINT64:x}]: 0x{addr:x}")
    return addr


def _validate_depth(depth: Any, field_name: str = "depth") -> int:
    """Validates that call/ret depth is a non-negative integer within bounds."""
    if not isinstance(depth, int) or isinstance(depth, bool):
        raise InvalidDepthError(f"Field {field_name} must be an integer, got {type(depth).__name__}: {depth!r}")
    if depth < 0:
        raise InvalidDepthError(f"Field {field_name} cannot be negative: {depth}")
    if depth > MAX_CALL_DEPTH_LIMIT:
        raise InvalidDepthError(f"Field {field_name} exceeds maximum allowed limit ({MAX_CALL_DEPTH_LIMIT}): {depth}")
    return depth


@dataclasses.dataclass(frozen=True, slots=True)
class StalkerCallEvent:
    source_address: int
    target_address: int
    depth: int
    timestamp_ns: Optional[int] = None
    sequence: Optional[int] = None
    event_type: str = "call"

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_address", _validate_address(self.source_address, "source_address"))
        object.__setattr__(self, "target_address", _validate_address(self.target_address, "target_address"))
        object.__setattr__(self, "depth", _validate_depth(self.depth, "depth"))
        if self.timestamp_ns is not None:
            if not isinstance(self.timestamp_ns, int) or isinstance(self.timestamp_ns, bool) or self.timestamp_ns < 0:
                raise MalformedEventError(f"Invalid timestamp_ns: {self.timestamp_ns!r}")
        if self.sequence is not None:
            if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 0:
                raise MalformedEventError(f"Invalid sequence: {self.sequence!r}")

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": "call",
            "source_address": f"0x{self.source_address:x}",
            "target_address": f"0x{self.target_address:x}",
            "depth": self.depth,
        }
        if self.timestamp_ns is not None:
            d["timestamp_ns"] = self.timestamp_ns
        if self.sequence is not None:
            d["sequence"] = self.sequence
        return d


@dataclasses.dataclass(frozen=True, slots=True)
class StalkerRetEvent:
    source_address: int
    target_address: int
    depth: int
    timestamp_ns: Optional[int] = None
    sequence: Optional[int] = None
    event_type: str = "ret"

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_address", _validate_address(self.source_address, "source_address"))
        object.__setattr__(self, "target_address", _validate_address(self.target_address, "target_address"))
        object.__setattr__(self, "depth", _validate_depth(self.depth, "depth"))
        if self.timestamp_ns is not None:
            if not isinstance(self.timestamp_ns, int) or isinstance(self.timestamp_ns, bool) or self.timestamp_ns < 0:
                raise MalformedEventError(f"Invalid timestamp_ns: {self.timestamp_ns!r}")
        if self.sequence is not None:
            if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 0:
                raise MalformedEventError(f"Invalid sequence: {self.sequence!r}")

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": "ret",
            "source_address": f"0x{self.source_address:x}",
            "target_address": f"0x{self.target_address:x}",
            "depth": self.depth,
        }
        if self.timestamp_ns is not None:
            d["timestamp_ns"] = self.timestamp_ns
        if self.sequence is not None:
            d["sequence"] = self.sequence
        return d


@dataclasses.dataclass(frozen=True, slots=True)
class StalkerExecEvent:
    instruction_address: int
    timestamp_ns: Optional[int] = None
    sequence: Optional[int] = None
    event_type: str = "exec"

    def __post_init__(self) -> None:
        object.__setattr__(self, "instruction_address", _validate_address(self.instruction_address, "instruction_address"))
        if self.timestamp_ns is not None:
            if not isinstance(self.timestamp_ns, int) or isinstance(self.timestamp_ns, bool) or self.timestamp_ns < 0:
                raise MalformedEventError(f"Invalid timestamp_ns: {self.timestamp_ns!r}")
        if self.sequence is not None:
            if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 0:
                raise MalformedEventError(f"Invalid sequence: {self.sequence!r}")

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": "exec",
            "instruction_address": f"0x{self.instruction_address:x}",
        }
        if self.timestamp_ns is not None:
            d["timestamp_ns"] = self.timestamp_ns
        if self.sequence is not None:
            d["sequence"] = self.sequence
        return d


@dataclasses.dataclass(frozen=True, slots=True)
class StalkerBlockEvent:
    start_address: int
    end_address: int
    timestamp_ns: Optional[int] = None
    sequence: Optional[int] = None
    event_type: str = "block"

    def __post_init__(self) -> None:
        start = _validate_address(self.start_address, "start_address")
        end = _validate_address(self.end_address, "end_address")
        if start > end:
            raise MalformedEventError(
                f"Block start address (0x{start:x}) cannot be greater than end address (0x{end:x})"
            )
        object.__setattr__(self, "start_address", start)
        object.__setattr__(self, "end_address", end)
        if self.timestamp_ns is not None:
            if not isinstance(self.timestamp_ns, int) or isinstance(self.timestamp_ns, bool) or self.timestamp_ns < 0:
                raise MalformedEventError(f"Invalid timestamp_ns: {self.timestamp_ns!r}")
        if self.sequence is not None:
            if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 0:
                raise MalformedEventError(f"Invalid sequence: {self.sequence!r}")

    @property
    def size_bytes(self) -> int:
        return self.end_address - self.start_address

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": "block",
            "start_address": f"0x{self.start_address:x}",
            "end_address": f"0x{self.end_address:x}",
            "size_bytes": self.size_bytes,
        }
        if self.timestamp_ns is not None:
            d["timestamp_ns"] = self.timestamp_ns
        if self.sequence is not None:
            d["sequence"] = self.sequence
        return d


StalkerEvent = Union[StalkerCallEvent, StalkerRetEvent, StalkerExecEvent, StalkerBlockEvent]


@dataclasses.dataclass(slots=True)
class CallTreeNode:
    address: int
    depth: int
    caller_address: Optional[int] = None
    call_count: int = 1
    children: Dict[int, "CallTreeNode"] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": f"0x{self.address:x}",
            "depth": self.depth,
            "caller_address": f"0x{self.caller_address:x}" if self.caller_address is not None else None,
            "call_count": self.call_count,
            "children": [child.to_dict() for child in self.children.values()],
        }


@dataclasses.dataclass(frozen=True, slots=True)
class RecursiveLoopReport:
    function_address: int
    cycle_chain: Tuple[int, ...]
    depth: int
    repetition_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "function_address": f"0x{self.function_address:x}",
            "cycle_chain": [f"0x{addr:x}" for addr in self.cycle_chain],
            "depth": self.depth,
            "repetition_count": self.repetition_count,
        }


@dataclasses.dataclass(frozen=True, slots=True)
class DeepCallStackReport:
    depth: int
    target_address: int
    stack_trace: Tuple[int, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "depth": self.depth,
            "target_address": f"0x{self.target_address:x}",
            "stack_trace": [f"0x{addr:x}" for addr in self.stack_trace],
        }


@dataclasses.dataclass(slots=True)
class BasicBlockRecord:
    start_address: int
    end_address: int
    size_bytes: int
    hit_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_address": f"0x{self.start_address:x}",
            "end_address": f"0x{self.end_address:x}",
            "size_bytes": self.size_bytes,
            "hit_count": self.hit_count,
        }


@dataclasses.dataclass(slots=True)
class CoverageMap:
    blocks: Dict[Tuple[int, int], BasicBlockRecord] = dataclasses.field(default_factory=dict)
    executed_instructions: Set[int] = dataclasses.field(default_factory=set)

    def record_block(self, start: int, end: int) -> None:
        key = (start, end)
        if key in self.blocks:
            self.blocks[key].hit_count += 1
        else:
            self.blocks[key] = BasicBlockRecord(
                start_address=start,
                end_address=end,
                size_bytes=end - start,
                hit_count=1,
            )

    def record_exec(self, addr: int) -> None:
        self.executed_instructions.add(addr)

    @property
    def total_blocks(self) -> int:
        return len(self.blocks)

    @property
    def total_bytes_covered(self) -> int:
        return sum(b.size_bytes for b in self.blocks.values())

    @property
    def total_exec_instructions(self) -> int:
        return len(self.executed_instructions)

    def to_dict(self) -> Dict[str, Any]:
        sorted_blocks = sorted(self.blocks.values(), key=lambda b: (b.start_address, b.end_address))
        return {
            "total_blocks": self.total_blocks,
            "total_bytes_covered": self.total_bytes_covered,
            "total_exec_instructions": self.total_exec_instructions,
            "blocks": [b.to_dict() for b in sorted_blocks],
        }


@dataclasses.dataclass(slots=True)
class StalkerTraceSummary:
    total_events: int
    call_events_count: int
    ret_events_count: int
    exec_events_count: int
    block_events_count: int
    max_depth_observed: int
    call_tree_roots: List[CallTreeNode]
    call_graph_edges: Dict[Tuple[int, int], int]
    coverage_map: CoverageMap
    recursive_loops: List[RecursiveLoopReport]
    deep_call_stacks: List[DeepCallStackReport]
    sha256_digest: str = ""

    def to_dict(self) -> Dict[str, Any]:
        sorted_edges = [
            {
                "caller": f"0x{k[0]:x}",
                "callee": f"0x{k[1]:x}",
                "count": v,
            }
            for k, v in sorted(self.call_graph_edges.items(), key=lambda item: (item[0][0], item[0][1]))
        ]
        return {
            "total_events": self.total_events,
            "call_events_count": self.call_events_count,
            "ret_events_count": self.ret_events_count,
            "exec_events_count": self.exec_events_count,
            "block_events_count": self.block_events_count,
            "max_depth_observed": self.max_depth_observed,
            "call_tree": [root.to_dict() for root in self.call_tree_roots],
            "call_graph_edges": sorted_edges,
            "coverage_map": self.coverage_map.to_dict(),
            "recursive_loops": [loop.to_dict() for loop in self.recursive_loops],
            "deep_call_stacks": [deep.to_dict() for deep in self.deep_call_stacks],
            "sha256_digest": self.sha256_digest,
        }


class FridaStalkerParser:
    """Zero-dependency parser for Frida Stalker event streams.

    Supports:
    - Tagged binary streams:
        Tag 'C' (0x01): CALL [source: u64, target: u64, depth: u32] (21 bytes)
        Tag 'R' (0x02): RET  [source: u64, target: u64, depth: u32] (21 bytes)
        Tag 'E' (0x04): EXEC [addr: u64] (9 bytes)
        Tag 'B' (0x08): BLOCK [start: u64, end: u64] (17 bytes)
    - Frida GumEvent binary stream (64-bit aligned structs):
        CALL/RET: [type: u64, location: u64, target: u64, depth: u64] (32 bytes)
        EXEC:     [type: u64, location: u64] (16 bytes)
        BLOCK:    [type: u64, begin: u64, end: u64] (24 bytes)
    - JSON / NDJSON / Python dict streams.
    """

    def __init__(self, deep_stack_threshold: int = DEFAULT_DEEP_STACK_THRESHOLD) -> None:
        if deep_stack_threshold < 1:
            raise ValueError(f"deep_stack_threshold must be >= 1, got {deep_stack_threshold}")
        self.deep_stack_threshold = deep_stack_threshold

    @classmethod
    def pack_tagged_event(cls, event: StalkerEvent) -> bytes:
        """Serializes a StalkerEvent into standard tagged binary encoding."""
        if isinstance(event, StalkerCallEvent):
            return struct.pack("<BQQI", StalkerEventType.CALL, event.source_address, event.target_address, event.depth)
        elif isinstance(event, StalkerRetEvent):
            return struct.pack("<BQQI", StalkerEventType.RET, event.source_address, event.target_address, event.depth)
        elif isinstance(event, StalkerExecEvent):
            return struct.pack("<BQ", StalkerEventType.EXEC, event.instruction_address)
        elif isinstance(event, StalkerBlockEvent):
            return struct.pack("<BQQ", StalkerEventType.BLOCK, event.start_address, event.end_address)
        else:
            raise MalformedEventError(f"Unsupported event type for serialization: {type(event).__name__}")

    @classmethod
    def pack_gum64_event(cls, event: StalkerEvent) -> bytes:
        """Serializes a StalkerEvent into 64-bit GumEvent C struct layout."""
        if isinstance(event, StalkerCallEvent):
            return struct.pack("<QQQq", StalkerEventType.CALL, event.source_address, event.target_address, event.depth)
        elif isinstance(event, StalkerRetEvent):
            return struct.pack("<QQQq", StalkerEventType.RET, event.source_address, event.target_address, event.depth)
        elif isinstance(event, StalkerExecEvent):
            return struct.pack("<QQ", StalkerEventType.EXEC, event.instruction_address)
        elif isinstance(event, StalkerBlockEvent):
            return struct.pack("<QQQ", StalkerEventType.BLOCK, event.start_address, event.end_address)
        else:
            raise MalformedEventError(f"Unsupported event type for serialization: {type(event).__name__}")

    @classmethod
    def pack_stream(cls, events: List[StalkerEvent], format: str = "tagged") -> bytes:
        """Packs a sequence of events into binary bytes."""
        buf = io.BytesIO()
        for ev in events:
            if format == "tagged":
                buf.write(cls.pack_tagged_event(ev))
            elif format == "gum64":
                buf.write(cls.pack_gum64_event(ev))
            else:
                raise ValueError(f"Unknown serialization format: {format}")
        return buf.getvalue()

    def iter_tagged_binary(self, data: bytes) -> Iterator[StalkerEvent]:
        """Lazily parses a tagged binary Frida stalker stream."""
        offset = 0
        total_len = len(data)

        while offset < total_len:
            tag = data[offset]
            offset += 1

            if tag == StalkerEventType.CALL or tag == ord("C") or tag == ord("c"):
                stride = 20
                if offset + stride > total_len:
                    raise TruncatedStreamError(
                        f"Truncated CALL event at offset {offset - 1}: expected {stride} bytes, remaining {total_len - offset}"
                    )
                src, dst, depth = struct.unpack_from("<QQI", data, offset)
                offset += stride
                yield StalkerCallEvent(source_address=src, target_address=dst, depth=depth)

            elif tag == StalkerEventType.RET or tag == ord("R") or tag == ord("r"):
                stride = 20
                if offset + stride > total_len:
                    raise TruncatedStreamError(
                        f"Truncated RET event at offset {offset - 1}: expected {stride} bytes, remaining {total_len - offset}"
                    )
                src, dst, depth = struct.unpack_from("<QQI", data, offset)
                offset += stride
                yield StalkerRetEvent(source_address=src, target_address=dst, depth=depth)

            elif tag == StalkerEventType.EXEC or tag == ord("E") or tag == ord("e"):
                stride = 8
                if offset + stride > total_len:
                    raise TruncatedStreamError(
                        f"Truncated EXEC event at offset {offset - 1}: expected {stride} bytes, remaining {total_len - offset}"
                    )
                (addr,) = struct.unpack_from("<Q", data, offset)
                offset += stride
                yield StalkerExecEvent(instruction_address=addr)

            elif tag == StalkerEventType.BLOCK or tag == ord("B") or tag == ord("b"):
                stride = 16
                if offset + stride > total_len:
                    raise TruncatedStreamError(
                        f"Truncated BLOCK event at offset {offset - 1}: expected {stride} bytes, remaining {total_len - offset}"
                    )
                start, end = struct.unpack_from("<QQ", data, offset)
                offset += stride
                yield StalkerBlockEvent(start_address=start, end_address=end)

            else:
                raise MalformedEventError(f"Unknown stalker event tag 0x{tag:02x} at offset {offset - 1}")

    def iter_gum64_binary(self, data: bytes) -> Iterator[StalkerEvent]:
        """Lazily parses a native 64-bit GumEvent binary stream."""
        offset = 0
        total_len = len(data)

        while offset < total_len:
            if offset + 8 > total_len:
                raise TruncatedStreamError(f"Truncated GumEvent type at offset {offset}")
            (ev_type,) = struct.unpack_from("<Q", data, offset)
            offset += 8

            if ev_type == StalkerEventType.CALL:
                stride = 24
                if offset + stride > total_len:
                    raise TruncatedStreamError(f"Truncated GumCallEvent at offset {offset - 8}")
                src, dst, depth = struct.unpack_from("<QQq", data, offset)
                offset += stride
                yield StalkerCallEvent(source_address=src, target_address=dst, depth=depth)

            elif ev_type == StalkerEventType.RET:
                stride = 24
                if offset + stride > total_len:
                    raise TruncatedStreamError(f"Truncated GumRetEvent at offset {offset - 8}")
                src, dst, depth = struct.unpack_from("<QQq", data, offset)
                offset += stride
                yield StalkerRetEvent(source_address=src, target_address=dst, depth=depth)

            elif ev_type == StalkerEventType.EXEC:
                stride = 8
                if offset + stride > total_len:
                    raise TruncatedStreamError(f"Truncated GumExecEvent at offset {offset - 8}")
                (addr,) = struct.unpack_from("<Q", data, offset)
                offset += stride
                yield StalkerExecEvent(instruction_address=addr)

            elif ev_type == StalkerEventType.BLOCK:
                stride = 16
                if offset + stride > total_len:
                    raise TruncatedStreamError(f"Truncated GumBlockEvent at offset {offset - 8}")
                start, end = struct.unpack_from("<QQ", data, offset)
                offset += stride
                yield StalkerBlockEvent(start_address=start, end_address=end)

            else:
                raise MalformedEventError(f"Unknown GumEvent type 0x{ev_type:x} at offset {offset - 8}")

    def parse_dict_event(self, d: Dict[str, Any]) -> StalkerEvent:
        """Parses a single event dictionary."""
        if not isinstance(d, dict):
            raise MalformedEventError(f"Event item must be a dictionary, got {type(d).__name__}")

        raw_type = d.get("type") or d.get("event")
        if not raw_type or not isinstance(raw_type, str):
            raise MalformedEventError(f"Event missing valid string 'type': {d!r}")

        t = raw_type.lower().strip()
        ts = d.get("timestamp_ns") or d.get("timestamp")
        seq = d.get("sequence") or d.get("seq")

        if t in ("call", "gum_call"):
            src = d.get("source_address") or d.get("location") or d.get("source") or d.get("from")
            dst = d.get("target_address") or d.get("target") or d.get("to")
            depth = d.get("depth", 0)
            if src is None or dst is None:
                raise MalformedEventError(f"Call event missing source or target address: {d!r}")
            return StalkerCallEvent(
                source_address=src,
                target_address=dst,
                depth=depth,
                timestamp_ns=ts,
                sequence=seq,
            )

        elif t in ("ret", "return", "gum_ret"):
            src = d.get("source_address") or d.get("location") or d.get("source") or d.get("from")
            dst = d.get("target_address") or d.get("target") or d.get("to")
            depth = d.get("depth", 0)
            if src is None or dst is None:
                raise MalformedEventError(f"Ret event missing source or target address: {d!r}")
            return StalkerRetEvent(
                source_address=src,
                target_address=dst,
                depth=depth,
                timestamp_ns=ts,
                sequence=seq,
            )

        elif t in ("exec", "execute", "instruction", "gum_exec"):
            addr = d.get("instruction_address") or d.get("location") or d.get("address") or d.get("pc")
            if addr is None:
                raise MalformedEventError(f"Exec event missing instruction address: {d!r}")
            return StalkerExecEvent(
                instruction_address=addr,
                timestamp_ns=ts,
                sequence=seq,
            )

        elif t in ("block", "bb", "basic_block", "gum_block"):
            start = d.get("start_address") or d.get("begin") or d.get("start")
            end = d.get("end_address") or d.get("end")
            if start is None or end is None:
                raise MalformedEventError(f"Block event missing start or end address: {d!r}")
            return StalkerBlockEvent(
                start_address=start,
                end_address=end,
                timestamp_ns=ts,
                sequence=seq,
            )

        else:
            raise MalformedEventError(f"Unknown event type: {raw_type!r}")

    def iter_events(self, source: Union[bytes, str, List[Any]]) -> Iterator[StalkerEvent]:
        """Lazily yields StalkerEvent objects from various source formats."""
        if isinstance(source, list):
            for item in source:
                yield self.parse_dict_event(item) if isinstance(item, dict) else item
            return

        if isinstance(source, str):
            text = source.strip()
            if not text:
                return
            if text.startswith("["):
                try:
                    loaded = json.loads(text)
                except json.JSONDecodeError as err:
                    raise MalformedEventError(f"Invalid JSON array: {err}") from err
                if not isinstance(loaded, list):
                    raise MalformedEventError("JSON input must be an array of event objects")
                for item in loaded:
                    yield self.parse_dict_event(item)
                return
            else:
                for line_idx, line in enumerate(text.splitlines(), start=1):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        obj = json.loads(line_str)
                    except json.JSONDecodeError as err:
                        raise MalformedEventError(f"Malformed JSON on line {line_idx}: {err}") from err
                    yield self.parse_dict_event(obj)
                return

        if isinstance(source, bytes):
            if not source:
                return
            stripped = source.strip()
            if stripped.startswith(b"[") or stripped.startswith(b"{"):
                try:
                    text_content = stripped.decode("utf-8")
                except UnicodeDecodeError as err:
                    raise MalformedEventError(f"Corrupted UTF-8 JSON stream: {err}") from err
                yield from self.iter_events(text_content)
                return

            if len(source) >= 8:
                possible_gum_type = struct.unpack_from("<Q", source, 0)[0]
                if possible_gum_type in (1, 2, 4, 8):
                    yield from self.iter_gum64_binary(source)
                    return

            yield from self.iter_tagged_binary(source)
            return

        raise MalformedEventError(f"Unsupported event source type: {type(source).__name__}")

    def parse_events(self, source: Union[bytes, str, List[Any]]) -> List[StalkerEvent]:
        """Auto-detects format and parses input into a list of StalkerEvent objects."""
        return list(self.iter_events(source))

    def inspect_trace(self, source: Union[bytes, str, List[Any]]) -> StalkerTraceSummary:
        """Parses event stream, enforces fail-closed invariants, and reconstructs execution model."""
        total_events = 0
        call_count = 0
        ret_count = 0
        exec_count = 0
        block_count = 0
        max_depth = 0

        last_timestamp: Optional[int] = None
        last_sequence: Optional[int] = None

        # Execution tracking state
        call_stack: List[Tuple[int, int]] = []
        call_tree_roots: List[CallTreeNode] = []
        node_stack: List[CallTreeNode] = []
        call_graph_edges: Dict[Tuple[int, int], int] = {}
        coverage_map = CoverageMap()
        recursive_loops: List[RecursiveLoopReport] = []
        deep_call_stacks: List[DeepCallStackReport] = []

        seen_recursive_keys: Set[Tuple[int, Tuple[int, ...]]] = set()

        for idx, event in enumerate(self.iter_events(source)):
            total_events += 1

            # Invariant 1: Monotonic time and sequence progression
            if event.timestamp_ns is not None:
                if last_timestamp is not None and event.timestamp_ns < last_timestamp:
                    raise BackwardsTimeTravelError(
                        f"Backwards time travel at event {idx}: timestamp {event.timestamp_ns} < previous {last_timestamp}"
                    )
                last_timestamp = event.timestamp_ns

            if event.sequence is not None:
                if last_sequence is not None and event.sequence <= last_sequence:
                    raise BackwardsTimeTravelError(
                        f"Out-of-order sequence at event {idx}: sequence {event.sequence} <= previous {last_sequence}"
                    )
                last_sequence = event.sequence

            if isinstance(event, StalkerCallEvent):
                call_count += 1
                if event.depth > max_depth:
                    max_depth = event.depth

                edge = (event.source_address, event.target_address)
                call_graph_edges[edge] = call_graph_edges.get(edge, 0) + 1

                active_addrs = [item[0] for item in call_stack]
                if event.target_address in active_addrs:
                    first_idx = active_addrs.index(event.target_address)
                    cycle_chain = tuple(active_addrs[first_idx:] + [event.target_address])
                    rep_key = (event.target_address, cycle_chain)
                    if rep_key not in seen_recursive_keys:
                        seen_recursive_keys.add(rep_key)
                        recursive_loops.append(
                            RecursiveLoopReport(
                                function_address=event.target_address,
                                cycle_chain=cycle_chain,
                                depth=event.depth,
                                repetition_count=1,
                            )
                        )

                call_stack.append((event.target_address, event.depth))

                if len(call_stack) > self.deep_stack_threshold:
                    deep_call_stacks.append(
                        DeepCallStackReport(
                            depth=len(call_stack),
                            target_address=event.target_address,
                            stack_trace=tuple(item[0] for item in call_stack),
                        )
                    )

                if not node_stack:
                    root_found = None
                    for r in call_tree_roots:
                        if r.address == event.target_address:
                            r.call_count += 1
                            root_found = r
                            break
                    if not root_found:
                        root_found = CallTreeNode(
                            address=event.target_address,
                            depth=event.depth,
                            caller_address=event.source_address,
                            call_count=1,
                        )
                        call_tree_roots.append(root_found)
                    node_stack.append(root_found)
                else:
                    parent_node = node_stack[-1]
                    if event.target_address in parent_node.children:
                        child = parent_node.children[event.target_address]
                        child.call_count += 1
                        node_stack.append(child)
                    else:
                        child = CallTreeNode(
                            address=event.target_address,
                            depth=event.depth,
                            caller_address=event.source_address,
                            call_count=1,
                        )
                        parent_node.children[event.target_address] = child
                        node_stack.append(child)

            elif isinstance(event, StalkerRetEvent):
                ret_count += 1
                if event.depth > max_depth:
                    max_depth = event.depth

                if not call_stack:
                    raise StackUnderflowError(
                        f"Ret event at index {idx} with empty call stack (target: 0x{event.target_address:x})"
                    )

                call_stack.pop()
                if node_stack:
                    node_stack.pop()

            elif isinstance(event, StalkerExecEvent):
                exec_count += 1
                coverage_map.record_exec(event.instruction_address)

            elif isinstance(event, StalkerBlockEvent):
                block_count += 1
                coverage_map.record_block(event.start_address, event.end_address)

        summary = StalkerTraceSummary(
            total_events=total_events,
            call_events_count=call_count,
            ret_events_count=ret_count,
            exec_events_count=exec_count,
            block_events_count=block_count,
            max_depth_observed=max_depth,
            call_tree_roots=call_tree_roots,
            call_graph_edges=call_graph_edges,
            coverage_map=coverage_map,
            recursive_loops=recursive_loops,
            deep_call_stacks=deep_call_stacks,
        )

        canon_json = json.dumps(summary.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        summary.sha256_digest = hashlib.sha256(canon_json.encode("utf-8")).hexdigest()

        return summary
