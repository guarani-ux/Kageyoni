"""Zero-dependency in-tree LLDB Native Tracer Bridge & Stop Reason Analyzer (CH 21).

Pure Python standard library implementation for interpreting LLDB thread states,
stop reasons, and thread frame backtraces.

Supports:
1. Stop Reason Decoding:
   - eStopReasonBreakpoint (hit breakpoint index / ID)
   - eStopReasonWatchpoint (watchpoint address)
   - eStopReasonSignal (Unix signal number & description, e.g. SIGTRAP, SIGSEGV)
   - eStopReasonException (Mach exception or Windows exception code e.g. STATUS_ACCESS_VIOLATION / 0xC0000005)
   - eStopReasonExec (process exec replacement)
   - eStopReasonPlanComplete (step over/in completed)
   - eStopReasonTrace (single step trace)
   - eStopReasonNone / eStopReasonInvalid
2. Thread Frame Stack Parser:
   - Frame index, PC (program counter), SP (stack pointer), FP (frame pointer),
     function / symbol name, source location (file:line), offset / module.
3. Fail-Closed Verification & Robust Invariants:
   - Rejects unknown negative thread IDs, corrupted hex addresses, negative frame indices.
   - Enforces strict input validation and payload bounds (<= 64 KB).
   - Zero third-party dependencies (strictly struct, io, hashlib, dataclasses, json, re).
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import re
import struct
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# Bounded payload size for memory ceiling
MAX_PAYLOAD_SIZE = 65536  # 64 KB

# Canonical LLDB Stop Reason Enums
STOP_REASON_INVALID = "eStopReasonInvalid"
STOP_REASON_NONE = "eStopReasonNone"
STOP_REASON_TRACE = "eStopReasonTrace"
STOP_REASON_BREAKPOINT = "eStopReasonBreakpoint"
STOP_REASON_WATCHPOINT = "eStopReasonWatchpoint"
STOP_REASON_SIGNAL = "eStopReasonSignal"
STOP_REASON_EXCEPTION = "eStopReasonException"
STOP_REASON_EXEC = "eStopReasonExec"
STOP_REASON_PLAN_COMPLETE = "eStopReasonPlanComplete"
STOP_REASON_THREAD_EXITING = "eStopReasonThreadExiting"
STOP_REASON_INSTRUMENTATION = "eStopReasonInstrumentation"
STOP_REASON_PROCESSOR_TRACE = "eStopReasonProcessorTrace"

KNOWN_STOP_REASONS = {
    STOP_REASON_INVALID,
    STOP_REASON_NONE,
    STOP_REASON_TRACE,
    STOP_REASON_BREAKPOINT,
    STOP_REASON_WATCHPOINT,
    STOP_REASON_SIGNAL,
    STOP_REASON_EXCEPTION,
    STOP_REASON_EXEC,
    STOP_REASON_PLAN_COMPLETE,
    STOP_REASON_THREAD_EXITING,
    STOP_REASON_INSTRUMENTATION,
    STOP_REASON_PROCESSOR_TRACE,
}

# Common Unix signals mapping
UNIX_SIGNALS: Dict[int, str] = {
    1: "SIGHUP",
    2: "SIGINT",
    3: "SIGQUIT",
    4: "SIGILL",
    5: "SIGTRAP",
    6: "SIGABRT",
    7: "SIGBUS",
    8: "SIGFPE",
    9: "SIGKILL",
    10: "SIGUSR1",
    11: "SIGSEGV",
    12: "SIGUSR2",
    13: "SIGPIPE",
    14: "SIGALRM",
    15: "SIGTERM",
}

# Common Windows NTSTATUS exception codes
WINDOWS_EXCEPTIONS: Dict[int, str] = {
    0xC0000005: "STATUS_ACCESS_VIOLATION",
    0x80000002: "STATUS_DATATYPE_MISALIGNMENT",
    0x80000003: "STATUS_BREAKPOINT",
    0x80000004: "STATUS_SINGLE_STEP",
    0xC000001D: "STATUS_ILLEGAL_INSTRUCTION",
    0xC000008C: "STATUS_ARRAY_BOUNDS_EXCEEDED",
    0xC000008D: "STATUS_FLOAT_DENORMAL_OPERAND",
    0xC000008E: "STATUS_FLOAT_DIVIDE_BY_ZERO",
    0xC000008F: "STATUS_FLOAT_INEXACT_RESULT",
    0xC0000090: "STATUS_FLOAT_INVALID_OPERATION",
    0xC0000091: "STATUS_FLOAT_OVERFLOW",
    0xC0000092: "STATUS_FLOAT_STACK_CHECK",
    0xC0000093: "STATUS_FLOAT_UNDERFLOW",
    0xC0000094: "STATUS_INTEGER_DIVIDE_BY_ZERO",
    0xC0000095: "STATUS_INTEGER_OVERFLOW",
    0xC00000FD: "STATUS_STACK_OVERFLOW",
    0xC0000025: "STATUS_NONCONTINUABLE_EXCEPTION",
}

# Mach Exception codes
MACH_EXCEPTIONS: Dict[int, str] = {
    1: "EXC_BAD_ACCESS",
    2: "EXC_BAD_INSTRUCTION",
    3: "EXC_ARITHMETIC",
    4: "EXC_EMULATION",
    5: "EXC_SOFTWARE",
    6: "EXC_BREAKPOINT",
    7: "EXC_SYSCALL",
    8: "EXC_MACH_SYSCALL",
    9: "EXC_RPC_ALERT",
    10: "EXC_CRASH",
}


@dataclasses.dataclass(frozen=True)
class StopReasonDetails:
    """Detailed metadata for a decoded stop reason."""
    reason: str
    raw_description: str
    breakpoint_id: Optional[int] = None
    breakpoint_hit_count: Optional[int] = None
    watchpoint_address: Optional[int] = None
    signal_number: Optional[int] = None
    signal_name: Optional[str] = None
    exception_code: Optional[int] = None
    exception_name: Optional[str] = None
    plan_complete: bool = False
    exec_replaced: bool = False
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class StackFrame:
    """Parsed single thread frame in LLDB backtrace."""
    index: int
    pc: int
    sp: Optional[int] = None
    fp: Optional[int] = None
    symbol_name: str = ""
    module_name: str = ""
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    source_column: Optional[int] = None
    symbol_offset: Optional[int] = None


@dataclasses.dataclass(frozen=True)
class ThreadState:
    """LLDB Thread state representation."""
    thread_id: int
    thread_index: int
    name: str
    queue: str
    stop_reason: StopReasonDetails
    frames: List[StackFrame]
    is_stopped: bool = True


@dataclasses.dataclass(frozen=True)
class LLDBTraceReport:
    """Complete parsed LLDB state report across threads."""
    process_id: Optional[int]
    selected_thread_id: Optional[int]
    threads: List[ThreadState]
    raw_digest: str
    total_frames: int

    @property
    def selected_thread(self) -> Optional[ThreadState]:
        if self.selected_thread_id is not None:
            for t in self.threads:
                if t.thread_id == self.selected_thread_id:
                    return t
        if self.threads:
            return self.threads[0]
        return None


def parse_address_token(token: Any) -> int:
    """Strictly parses a memory address string or integer into non-negative int.

    Rejects negative numbers, invalid hex characters, and out-of-range addresses.
    """
    if isinstance(token, int):
        if token < 0:
            raise ValueError(f"Negative memory address rejected: {token}")
        if token > 0xFFFFFFFFFFFFFFFF:
            raise ValueError(f"Address exceeds 64-bit address space: {token:#x}")
        return token

    if isinstance(token, str):
        tok = token.strip()
        if not tok:
            raise ValueError("Empty address token")
        if tok.startswith("-"):
            raise ValueError(f"Negative memory address rejected: {tok}")

        base = 16 if (tok.startswith("0x") or tok.startswith("0X") or any(c in "abcdefABCDEF" for c in tok)) else 10
        try:
            val = int(tok, base)
        except ValueError as exc:
            if base == 10:
                try:
                    val = int(tok, 16)
                except ValueError:
                    raise ValueError(f"Corrupted hex address token: {tok}") from exc
            else:
                raise ValueError(f"Corrupted hex address token: {tok}") from exc

        if val < 0:
            raise ValueError(f"Negative memory address rejected: {val}")
        if val > 0xFFFFFFFFFFFFFFFF:
            raise ValueError(f"Address exceeds 64-bit address space: {val:#x}")
        return val

    raise TypeError(f"Unsupported address token type: {type(token).__name__}")


def decode_stop_reason(reason_str: str, description: str = "") -> StopReasonDetails:
    """Decodes LLDB stop reason enum and descriptive text into structured StopReasonDetails.

    Fails closed if reason is unknown or corrupted.
    """
    if not isinstance(reason_str, str):
        raise TypeError(f"Stop reason must be str, got {type(reason_str).__name__}")

    raw_reason = reason_str.strip()
    norm_reason = raw_reason

    # Handle short names like 'breakpoint', 'signal', etc.
    if not norm_reason.startswith("eStopReason"):
        capitalized = norm_reason.capitalize()
        candidate = f"eStopReason{capitalized}"
        if candidate in KNOWN_STOP_REASONS:
            norm_reason = candidate
        elif norm_reason.lower() == "plancomplete" or norm_reason.lower() == "plan_complete":
            norm_reason = STOP_REASON_PLAN_COMPLETE
        elif norm_reason.lower() == "threadexiting" or norm_reason.lower() == "thread_exiting":
            norm_reason = STOP_REASON_THREAD_EXITING

    if norm_reason not in KNOWN_STOP_REASONS:
        raise ValueError(f"Unknown or invalid stop reason: {raw_reason}")

    desc = description.strip()
    bp_id: Optional[int] = None
    bp_hit: Optional[int] = None
    wp_addr: Optional[int] = None
    sig_num: Optional[int] = None
    sig_name: Optional[str] = None
    exc_code: Optional[int] = None
    exc_name: Optional[str] = None
    plan_comp = (norm_reason == STOP_REASON_PLAN_COMPLETE)
    exec_rep = (norm_reason == STOP_REASON_EXEC)
    extra: Dict[str, Any] = {}

    # 1. Breakpoint decoding
    if norm_reason == STOP_REASON_BREAKPOINT:
        m = re.search(r"breakpoint\s+(?:hit\s+id\s*=\s*)?(\d+)(?:\.(\d+))?", desc, re.IGNORECASE)
        if m:
            bp_id = int(m.group(1))
            if m.group(2):
                extra["breakpoint_sub_id"] = int(m.group(2))
        m_hit = re.search(r"hit\s+count\s*=\s*(\d+)", desc, re.IGNORECASE)
        if m_hit:
            bp_hit = int(m_hit.group(1))

    # 2. Watchpoint decoding
    elif norm_reason == STOP_REASON_WATCHPOINT:
        m_wp = re.search(r"watchpoint\s+(\d+)", desc, re.IGNORECASE)
        if m_wp:
            extra["watchpoint_id"] = int(m_wp.group(1))
        m_addr = re.search(r"(?:address|addr)\s*[:=]\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]{4,16})", desc, re.IGNORECASE)
        if m_addr:
            wp_addr = parse_address_token(m_addr.group(1))

    # 3. Signal decoding
    elif norm_reason == STOP_REASON_SIGNAL:
        m_sig = re.search(r"\b(SIG[A-Z0-9]+)\b", desc)
        if m_sig:
            sig_name = m_sig.group(1).upper()
            for n, name in UNIX_SIGNALS.items():
                if name == sig_name:
                    sig_num = n
                    break
        m_num = re.search(r"signal(?:\s*=\s*|\s+)(\d+)", desc, re.IGNORECASE)
        if m_num:
            n_val = int(m_num.group(1))
            sig_num = n_val
            if not sig_name and n_val in UNIX_SIGNALS:
                sig_name = UNIX_SIGNALS[n_val]

    # 4. Exception decoding
    elif norm_reason == STOP_REASON_EXCEPTION:
        m_hex = re.search(r"(0x[0-9a-fA-F]{8})", desc)
        if m_hex:
            exc_code = int(m_hex.group(1), 16)
            if exc_code in WINDOWS_EXCEPTIONS:
                exc_name = WINDOWS_EXCEPTIONS[exc_code]
        m_win = re.search(r"\b(STATUS_[A-Z0-9_]+)\b", desc)
        if m_win:
            exc_name = m_win.group(1)
            for c, name in WINDOWS_EXCEPTIONS.items():
                if name == exc_name:
                    exc_code = c
                    break
        m_mach = re.search(r"\b(EXC_[A-Z0-9_]+)\b", desc)
        if m_mach:
            exc_name = m_mach.group(1)
            for c, name in MACH_EXCEPTIONS.items():
                if name == exc_name:
                    exc_code = c
                    break

    return StopReasonDetails(
        reason=norm_reason,
        raw_description=desc,
        breakpoint_id=bp_id,
        breakpoint_hit_count=bp_hit,
        watchpoint_address=wp_addr,
        signal_number=sig_num,
        signal_name=sig_name,
        exception_code=exc_code,
        exception_name=exc_name,
        plan_complete=plan_comp,
        exec_replaced=exec_rep,
        extra=extra,
    )


class LLDBTracerParser:
    """Parser and state reconciler for native LLDB trace output and JSON envelopes."""

    RE_THREAD_HEADER = re.compile(
        r"^\*?\s*thread\s+#(\d+)(?::\s*tid\s*=\s*(0x[0-9a-fA-F]+|\d+))?(?:,\s*name\s*=\s*'([^']*)')?(?:,\s*queue\s*=\s*'([^']*)')?(?:,\s*stop\s+reason\s*=\s*(.*))?$",
        re.IGNORECASE,
    )

    RE_FRAME_LINE = re.compile(
        r"^\s*(?:frame\s+#|\*)?(\d+):\s*(0x[0-9a-fA-F]+)\s+(?:`?([^`]+)`?)?(?:`([^+]+))?(?:\s*\+\s*(\d+|0x[0-9a-fA-F]+))?(?:\s+at\s+([^:]+):(\d+)(?::(\d+))?)?",
        re.IGNORECASE,
    )

    @classmethod
    def parse_frame_line(cls, line: str) -> Optional[StackFrame]:
        """Parses a single LLDB backtrace frame line.

        Example formats:
        - "frame #0: 0x0000000100000f50 a.out`main(argc=1, argv=0x7fff5fbff8b0) at main.c:10:5"
        - "    frame #1: 0x00007fff8d2d55ad libsystem_c.dylib`start + 1"
        - "* frame #0: 0x00007ff712341000 ntdll.dll`RtlUserThreadStart"
        """
        line_clean = line.strip()
        if not line_clean:
            return None

        # Quick pre-filter for frame indicators
        if not (line_clean.startswith("frame") or line_clean.startswith("* frame") or re.match(r"^\*?\s*#?\d+:", line_clean)):
            return None

        m_idx = re.search(r"^\*?\s*(?:frame\s+)?#?(\d+):", line_clean)
        if not m_idx:
            return None

        frame_idx = int(m_idx.group(1))
        if frame_idx < 0:
            raise ValueError(f"Negative frame index rejected: {frame_idx}")

        remainder = line_clean[m_idx.end():].strip()
        m_pc = re.search(r"^(0x[0-9a-fA-F]+|\d+)", remainder)
        if not m_pc:
            raise ValueError(f"Missing or corrupted PC address in frame: {line_clean}")

        pc_val = parse_address_token(m_pc.group(1))
        remainder = remainder[m_pc.end():].strip()

        module_name = ""
        symbol_name = ""
        symbol_offset: Optional[int] = None
        source_file: Optional[str] = None
        source_line: Optional[int] = None
        source_col: Optional[int] = None

        m_at = re.search(r"\bat\s+([^:\s]+):(\d+)(?::(\d+))?", remainder)
        if m_at:
            source_file = m_at.group(1)
            source_line = int(m_at.group(2))
            if source_line < 0:
                raise ValueError(f"Negative source line rejected: {source_line}")
            if m_at.group(3):
                source_col = int(m_at.group(3))
                if source_col < 0:
                    raise ValueError(f"Negative source column rejected: {source_col}")
            remainder = remainder[:m_at.start()].strip()

        m_off = re.search(r"\+\s*(0x[0-9a-fA-F]+|\d+)\s*$", remainder)
        if m_off:
            symbol_offset = parse_address_token(m_off.group(1))
            remainder = remainder[:m_off.start()].strip()

        if "`" in remainder:
            parts = remainder.split("`", 1)
            module_name = parts[0].strip()
            symbol_name = parts[1].strip()
        else:
            symbol_name = remainder.strip()

        return StackFrame(
            index=frame_idx,
            pc=pc_val,
            sp=None,
            fp=None,
            symbol_name=symbol_name,
            module_name=module_name,
            source_file=source_file,
            source_line=source_line,
            source_column=source_col,
            symbol_offset=symbol_offset,
        )

    @classmethod
    def parse_text_dump(cls, text: str) -> LLDBTraceReport:
        """Parses raw text dump of LLDB thread backtrace / stop state."""
        if not isinstance(text, str):
            raise TypeError("Text dump must be a string")
        if len(text.encode("utf-8")) > MAX_PAYLOAD_SIZE:
            raise ValueError(f"Payload exceeds strict 64 KB ceiling: {len(text.encode('utf-8'))} bytes")
        if not text.strip():
            raise ValueError("Empty LLDB text dump rejected")

        lines = text.splitlines()
        threads: List[ThreadState] = []
        cur_thread_id: Optional[int] = None
        cur_thread_index: int = 1
        cur_name: str = ""
        cur_queue: str = ""
        cur_stop_reason: StopReasonDetails = StopReasonDetails(STOP_REASON_NONE, "")
        cur_frames: List[StackFrame] = []
        selected_thread_id: Optional[int] = None

        def flush_thread():
            nonlocal cur_thread_id, cur_thread_index, cur_name, cur_queue, cur_stop_reason, cur_frames
            if cur_thread_id is not None or cur_frames:
                tid = cur_thread_id if cur_thread_id is not None else cur_thread_index
                if tid < 0:
                    raise ValueError(f"Negative thread ID rejected: {tid}")
                threads.append(
                    ThreadState(
                        thread_id=tid,
                        thread_index=cur_thread_index,
                        name=cur_name,
                        queue=cur_queue,
                        stop_reason=cur_stop_reason,
                        frames=list(cur_frames),
                        is_stopped=True,
                    )
                )
                cur_thread_id = None
                cur_name = ""
                cur_queue = ""
                cur_stop_reason = StopReasonDetails(STOP_REASON_NONE, "")
                cur_frames = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            if line_str.startswith("* thread #") or line_str.startswith("thread #"):
                flush_thread()
                is_selected = line_str.startswith("*")

                m_num = re.search(r"thread\s+#(\d+)", line_str, re.IGNORECASE)
                if not m_num:
                    raise ValueError(f"Corrupted thread index in line: {line_str}")
                cur_thread_index = int(m_num.group(1))
                if cur_thread_index < 0:
                    raise ValueError(f"Negative thread index: {cur_thread_index}")

                m_tid = re.search(r"tid\s*=\s*(0x[0-9a-fA-F]+|\d+)", line_str, re.IGNORECASE)
                if m_tid:
                    cur_thread_id = parse_address_token(m_tid.group(1))
                else:
                    cur_thread_id = cur_thread_index

                if is_selected:
                    selected_thread_id = cur_thread_id

                m_name = re.search(r"name\s*=\s*'([^']*)'", line_str)
                if m_name:
                    cur_name = m_name.group(1)

                m_queue = re.search(r"queue\s*=\s*'([^']*)'", line_str)
                if m_queue:
                    cur_queue = m_queue.group(1)

                m_reason = re.search(r"stop\s+reason\s*=\s*(.*)$", line_str, re.IGNORECASE)
                if m_reason:
                    raw_r = m_reason.group(1).strip()
                    r_tok = raw_r.split()[0] if raw_r else STOP_REASON_NONE
                    try:
                        cur_stop_reason = decode_stop_reason(r_tok, raw_r)
                    except ValueError:
                        cur_stop_reason = decode_stop_reason(raw_r, raw_r)
                continue

            frame = cls.parse_frame_line(line_str)
            if frame is not None:
                cur_frames.append(frame)

        flush_thread()

        if not threads:
            raise ValueError("No valid thread states or frames parsed from text dump")

        raw_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        total_frames = sum(len(t.frames) for t in threads)

        return LLDBTraceReport(
            process_id=None,
            selected_thread_id=selected_thread_id,
            threads=threads,
            raw_digest=raw_digest,
            total_frames=total_frames,
        )

    @classmethod
    def parse_json(cls, payload: Union[str, bytes, Dict[str, Any]]) -> LLDBTraceReport:
        """Parses a structured JSON representation of LLDB process/thread telemetry."""
        raw_bytes: bytes
        if isinstance(payload, bytes):
            raw_bytes = payload
            if len(raw_bytes) > MAX_PAYLOAD_SIZE:
                raise ValueError(f"Payload exceeds strict 64 KB ceiling: {len(raw_bytes)} bytes")
            if not raw_bytes.strip():
                raise ValueError("Empty JSON payload rejected")
            data = json.loads(raw_bytes.decode("utf-8"))
        elif isinstance(payload, str):
            raw_bytes = payload.encode("utf-8")
            if len(raw_bytes) > MAX_PAYLOAD_SIZE:
                raise ValueError(f"Payload exceeds strict 64 KB ceiling: {len(raw_bytes)} bytes")
            if not payload.strip():
                raise ValueError("Empty JSON payload rejected")
            data = json.loads(payload)
        elif isinstance(payload, dict):
            raw_bytes = json.dumps(payload).encode("utf-8")
            if len(raw_bytes) > MAX_PAYLOAD_SIZE:
                raise ValueError(f"Payload exceeds strict 64 KB ceiling: {len(raw_bytes)} bytes")
            data = payload
        else:
            raise TypeError(f"Expected str, bytes, or dict, got {type(payload).__name__}")

        if not isinstance(data, dict):
            raise ValueError("Root JSON object must be an object/dict")

        process_id: Optional[int] = None
        if "process_id" in data and data["process_id"] is not None:
            pid = data["process_id"]
            if not isinstance(pid, int) or pid < 0:
                raise ValueError(f"Invalid process_id: {pid}")
            process_id = pid

        selected_thread_id: Optional[int] = None
        if "selected_thread_id" in data and data["selected_thread_id"] is not None:
            selected_thread_id = parse_address_token(data["selected_thread_id"])

        threads_data = data.get("threads")
        if threads_data is None or not isinstance(threads_data, list):
            raise ValueError("Missing or invalid 'threads' array in JSON")

        threads: List[ThreadState] = []
        for t_idx, t_item in enumerate(threads_data):
            if not isinstance(t_item, dict):
                raise ValueError(f"Thread entry at index {t_idx} is not a dictionary")

            raw_tid = t_item.get("thread_id", t_item.get("tid", t_idx))
            thread_id = parse_address_token(raw_tid)
            thread_index = t_item.get("thread_index", t_item.get("index", t_idx))
            if not isinstance(thread_index, int) or thread_index < 0:
                raise ValueError(f"Invalid thread index: {thread_index}")

            name = str(t_item.get("name", ""))
            queue = str(t_item.get("queue", ""))

            stop_reason_obj = t_item.get("stop_reason")
            if isinstance(stop_reason_obj, dict):
                reason_name = stop_reason_obj.get("reason", STOP_REASON_NONE)
                desc = stop_reason_obj.get("description", "")
                stop_details = decode_stop_reason(reason_name, desc)
                if "breakpoint_id" in stop_reason_obj and stop_reason_obj["breakpoint_id"] is not None:
                    bp_id = int(stop_reason_obj["breakpoint_id"])
                    if bp_id < 0:
                        raise ValueError("Negative breakpoint_id rejected")
                    stop_details = dataclasses.replace(stop_details, breakpoint_id=bp_id)
                if "watchpoint_address" in stop_reason_obj and stop_reason_obj["watchpoint_address"] is not None:
                    wp_addr = parse_address_token(stop_reason_obj["watchpoint_address"])
                    stop_details = dataclasses.replace(stop_details, watchpoint_address=wp_addr)
                if "signal_number" in stop_reason_obj and stop_reason_obj["signal_number"] is not None:
                    sig_n = int(stop_reason_obj["signal_number"])
                    if sig_n < 0:
                        raise ValueError("Negative signal_number rejected")
                    sig_nm = stop_reason_obj.get("signal_name", UNIX_SIGNALS.get(sig_n))
                    stop_details = dataclasses.replace(stop_details, signal_number=sig_n, signal_name=sig_nm)
                if "exception_code" in stop_reason_obj and stop_reason_obj["exception_code"] is not None:
                    exc_c = parse_address_token(stop_reason_obj["exception_code"])
                    exc_nm = stop_reason_obj.get("exception_name", WINDOWS_EXCEPTIONS.get(exc_c, MACH_EXCEPTIONS.get(exc_c)))
                    stop_details = dataclasses.replace(stop_details, exception_code=exc_c, exception_name=exc_nm)
            elif isinstance(stop_reason_obj, str):
                stop_details = decode_stop_reason(stop_reason_obj, stop_reason_obj)
            else:
                stop_details = StopReasonDetails(STOP_REASON_NONE, "")

            raw_frames = t_item.get("frames", [])
            if not isinstance(raw_frames, list):
                raise ValueError("Thread 'frames' must be a list")

            frames: List[StackFrame] = []
            for f_idx, f_item in enumerate(raw_frames):
                if not isinstance(f_item, dict):
                    raise ValueError(f"Frame at index {f_idx} must be a dictionary")

                frame_i = f_item.get("index", f_idx)
                if not isinstance(frame_i, int) or frame_i < 0:
                    raise ValueError(f"Invalid frame index: {frame_i}")

                if "pc" not in f_item:
                    raise ValueError(f"Frame {frame_i} missing required 'pc' address")
                pc = parse_address_token(f_item["pc"])

                sp = parse_address_token(f_item["sp"]) if "sp" in f_item and f_item["sp"] is not None else None
                fp = parse_address_token(f_item["fp"]) if "fp" in f_item and f_item["fp"] is not None else None

                sym_name = str(f_item.get("symbol_name", f_item.get("symbol", "")))
                mod_name = str(f_item.get("module_name", f_item.get("module", "")))
                src_file = str(f_item["source_file"]) if "source_file" in f_item and f_item["source_file"] is not None else None
                src_line = int(f_item["source_line"]) if "source_line" in f_item and f_item["source_line"] is not None else None
                if src_line is not None and src_line < 0:
                    raise ValueError(f"Negative source_line rejected: {src_line}")
                src_col = int(f_item["source_column"]) if "source_column" in f_item and f_item["source_column"] is not None else None
                if src_col is not None and src_col < 0:
                    raise ValueError(f"Negative source_column rejected: {src_col}")

                sym_off = parse_address_token(f_item["symbol_offset"]) if "symbol_offset" in f_item and f_item["symbol_offset"] is not None else None

                frames.append(
                    StackFrame(
                        index=frame_i,
                        pc=pc,
                        sp=sp,
                        fp=fp,
                        symbol_name=sym_name,
                        module_name=mod_name,
                        source_file=src_file,
                        source_line=src_line,
                        source_column=src_col,
                        symbol_offset=sym_off,
                    )
                )

            threads.append(
                ThreadState(
                    thread_id=thread_id,
                    thread_index=thread_index,
                    name=name,
                    queue=queue,
                    stop_reason=stop_details,
                    frames=frames,
                    is_stopped=t_item.get("is_stopped", True),
                )
            )

        raw_digest = hashlib.sha256(raw_bytes).hexdigest()
        total_frames = sum(len(t.frames) for t in threads)

        return LLDBTraceReport(
            process_id=process_id,
            selected_thread_id=selected_thread_id,
            threads=threads,
            raw_digest=raw_digest,
            total_frames=total_frames,
        )

    @classmethod
    def parse(cls, input_data: Union[str, bytes, Dict[str, Any]]) -> LLDBTraceReport:
        """Unified entrypoint: auto-detects JSON or text dump format."""
        if isinstance(input_data, dict):
            return cls.parse_json(input_data)

        if isinstance(input_data, bytes):
            if len(input_data) > MAX_PAYLOAD_SIZE:
                raise ValueError(f"Payload exceeds strict 64 KB ceiling: {len(input_data)} bytes")
            if not input_data.strip():
                raise ValueError("Empty binary input rejected")
            text = input_data.decode("utf-8")
        elif isinstance(input_data, str):
            if len(input_data.encode("utf-8")) > MAX_PAYLOAD_SIZE:
                raise ValueError(f"Payload exceeds strict 64 KB ceiling: {len(input_data.encode('utf-8'))} bytes")
            if not input_data.strip():
                raise ValueError("Empty string input rejected")
            text = input_data
        else:
            raise TypeError(f"Unsupported input type: {type(input_data).__name__}")

        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return cls.parse_json(stripped)

        return cls.parse_text_dump(text)
