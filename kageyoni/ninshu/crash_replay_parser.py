"""Zero-dependency in-tree Pwntools Exploit & Crash Replay Engine (CH 22).

Provides crash dump triage, cyclic De Bruijn pattern generation/offset finding,
security mitigation detection, and fail-closed crash classification:
1. De Bruijn Cyclic Pattern Generator & Offset Finder:
   - `cyclic(length, n=4, alphabet=...)` -> deterministic non-repeating pattern bytes.
   - `cyclic_find(sub, n=4, alphabet=...)` -> integer byte offset of overwrite.
   - Bounded memory generator strictly compliant with <= 64 KB heap ceiling.
2. Crash Trace & Register State Parsing:
   - Parses GDB/LLDB register dumps, Linux dmesg segfault lines, structured JSON,
     and raw binary crash structures.
   - Extracts architecture, instruction pointer (EIP/RIP), stack pointer (ESP/RSP),
     frame pointer (EBP/RBP), fault addresses, and signals (SIGSEGV, SIGBUS, SIGFPE, SIGILL, SIGABRT).
3. Security Mitigation Detection:
   - Inspects ELF binaries (NX via PT_GNU_STACK, PIE via e_type/DT_FLAGS, Canary via symbols,
     RELRO via PT_GNU_RELRO and BIND_NOW).
   - Inspects PE binaries (NX/DEP via DLLCharacteristics, ASLR/PIE via DynamicBase, Canary/Guard).
   - Structured dictionary and flags translation.
4. Crash Classification:
   - Control Flow Hijacking (EIP/RIP cyclic overwrite / controlled execution transfer).
   - Null Pointer Dereference (fault address in first page 0x0 - 0x1000).
   - Heap Corruption (malloc/free errors, double free, corrupted chunk pointers).
   - Stack Buffer Overflow (EBP/saved frame overwrite, canary destruction).
   - Divide by Zero (SIGFPE) and Illegal Instruction (SIGILL).
5. Strict Fail-Closed Invariants:
   - Rejects negative lengths and negative integer offsets.
   - Rejects corrupted or malformed crash traces.
   - Zero third-party dependencies (pure Python standard library).
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import re
import struct
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

DEFAULT_ALPHABET = b"abcdefghijklmnopqrstuvwxyz"
MAX_CYCLIC_LENGTH = 65536  # Strict 64 KB allocation ceiling

SUPPORTED_SIGNALS: Dict[str, int] = {
    "SIGSEGV": 11,
    "SIGBUS": 7,
    "SIGFPE": 8,
    "SIGILL": 4,
    "SIGABRT": 6,
}
SIGNAL_NUM_TO_NAME: Dict[int, str] = {v: k for k, v in SUPPORTED_SIGNALS.items()}

# Crash Classifications
CLASS_CONTROL_FLOW_HIJACK = "CONTROL_FLOW_HIJACK"
CLASS_NULL_POINTER_DEREFERENCE = "NULL_POINTER_DEREFERENCE"
CLASS_HEAP_CORRUPTION = "HEAP_CORRUPTION"
CLASS_STACK_BUFFER_OVERFLOW = "STACK_BUFFER_OVERFLOW"
CLASS_DIVIDE_BY_ZERO = "DIVIDE_BY_ZERO"
CLASS_ILLEGAL_INSTRUCTION = "ILLEGAL_INSTRUCTION"
CLASS_UNKNOWN = "UNKNOWN"

# Regular expressions for text crash parsing
RE_SIGNAL = re.compile(
    r"\b(SIGSEGV|SIGBUS|SIGFPE|SIGILL|SIGABRT)\b",
    re.IGNORECASE,
)
RE_FAULT_ADDR = re.compile(
    r"(?:fault\s+address|fault_addr|segfault\s+at|at\s+address|si_addr)[:=]?\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]{4,16})",
    re.IGNORECASE,
)
RE_REG_LINE = re.compile(
    r"\b([re]?[a-d]x|[re]?[si]p|[re]?[sb]p|[re]?[sd]i|r[8-9]|r1[0-5]|eflags|rflags)\s*[:=]?\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]{4,16})\b",
    re.IGNORECASE,
)
RE_DMESG_SEGFAULT = re.compile(
    r"segfault\s+at\s+([0-9a-fA-F]+)\s+ip\s+([0-9a-fA-F]+)\s+sp\s+([0-9a-fA-F]+)",
    re.IGNORECASE,
)

HEAP_ERROR_MARKERS = (
    "corrupted double-linked list",
    "double free",
    "free(): invalid pointer",
    "free(): invalid size",
    "malloc(): memory corruption",
    "malloc_consolidate",
    "corrupted size vs. prev_size",
    "heap-use-after-free",
    "heap-buffer-overflow",
)

STACK_ERROR_MARKERS = (
    "stack smashing detected",
    "*** stack smashing detected ***",
    "__stack_chk_fail",
)


# -------------------------------------------------------------------------
# 1. Cyclic De Bruijn Generator & Finder (Pure Python stdlib)
# -------------------------------------------------------------------------

def de_bruijn_sequence(alphabet: bytes = DEFAULT_ALPHABET, n: int = 4) -> Iterator[bytes]:
    """Generates an infinite or complete De Bruijn sequence stream using the FKM algorithm.

    Yields single-byte `bytes` objects one at a time. Peak memory usage is O(k * n)
    integers (< 1 KB) regardless of how many bytes are generated.
    """
    k = len(alphabet)
    a = [0] * (k * n)

    def db(t: int, p: int) -> Iterator[bytes]:
        if t > n:
            if n % p == 0:
                for i in range(1, p + 1):
                    yield alphabet[a[i] : a[i] + 1]
        else:
            a[t] = a[t - p]
            yield from db(t + 1, p)
            for j in range(a[t - p] + 1, k):
                a[t] = j
                yield from db(t + 1, t)

    yield from db(1, 1)


def cyclic(
    length: int,
    n: int = 4,
    alphabet: Union[str, bytes] = DEFAULT_ALPHABET,
) -> bytes:
    """Generates a De Bruijn cyclic pattern of `length` bytes.

    Args:
        length: Exact byte length of pattern to generate.
        n: Subsequence uniqueness stride (default 4 bytes).
        alphabet: Character or byte alphabet (default a-z).

    Returns:
        Pattern bytes of length `length`.

    Raises:
        ValueError: If length is negative or exceeds the 64 KB ceiling,
                    or if stride n <= 0 or alphabet is invalid.
    """
    if length < 0:
        raise ValueError(f"Negative cyclic length rejected: {length}")
    if length > MAX_CYCLIC_LENGTH:
        raise ValueError(
            f"Requested cyclic length {length} exceeds 64 KB memory limit ({MAX_CYCLIC_LENGTH} bytes)"
        )
    if n <= 0:
        raise ValueError(f"Pattern uniqueness stride n must be positive, got {n}")

    alpha_bytes = alphabet.encode("latin-1") if isinstance(alphabet, str) else bytes(alphabet)
    if len(alpha_bytes) == 0:
        raise ValueError("Alphabet cannot be empty")
    if len(set(alpha_bytes)) != len(alpha_bytes):
        raise ValueError("Alphabet contains duplicate characters; must be unique")

    if length == 0:
        return b""

    buf = bytearray()
    gen = de_bruijn_sequence(alpha_bytes, n)
    while len(buf) < length:
        try:
            buf.extend(next(gen))
        except StopIteration:
            # Re-seed generator if requested length exceeds De Bruijn cycle length
            gen = de_bruijn_sequence(alpha_bytes, n)
            buf.extend(next(gen))

    return bytes(buf[:length])


def cyclic_find(
    sub: Union[int, bytes, str],
    n: int = 4,
    alphabet: Union[str, bytes] = DEFAULT_ALPHABET,
    max_search: int = 456976,
) -> int:
    """Resolves the 0-indexed byte offset of `sub` in the De Bruijn pattern.

    Args:
        sub: Integer (e.g. 0x61616164), bytes (b"daaa"), or string ("daaa").
        n: Subsequence uniqueness stride (default 4).
        alphabet: Alphabet used for generation.
        max_search: Maximum bytes of sequence to evaluate before giving up.

    Returns:
        Integer byte offset (>= 0) or -1 if sub is not found.

    Raises:
        ValueError: If sub integer is negative or empty.
        TypeError: If sub is of an unsupported type.
    """
    if isinstance(sub, int):
        if sub < 0:
            raise ValueError(f"Negative sub-pattern value rejected: {sub}")
        if n == 4:
            if sub > 0xFFFFFFFF:
                sub_bytes = struct.pack("<Q", sub)
            else:
                sub_bytes = struct.pack("<I", sub)
        elif n == 8:
            sub_bytes = struct.pack("<Q", sub)
        else:
            sub_bytes = sub.to_bytes(n, "little")
    elif isinstance(sub, str):
        sub_bytes = sub.encode("latin-1")
    elif isinstance(sub, (bytes, bytearray)):
        sub_bytes = bytes(sub)
    else:
        raise TypeError(f"Unsupported sub-pattern type: {type(sub)}")

    if len(sub_bytes) == 0:
        raise ValueError("Sub-pattern cannot be empty")

    alpha_bytes = alphabet.encode("latin-1") if isinstance(alphabet, str) else bytes(alphabet)
    if len(alpha_bytes) == 0:
        raise ValueError("Alphabet cannot be empty")

    # Fast validation: if any byte in target is not in alphabet, it cannot be found
    for b in sub_bytes:
        if b not in alpha_bytes:
            return -1

    target_len = len(sub_bytes)
    window = bytearray()
    gen = de_bruijn_sequence(alpha_bytes, n)
    idx = 0

    while idx < max_search:
        try:
            nxt = next(gen)
        except StopIteration:
            break
        window.extend(nxt)
        if len(window) > target_len:
            window.pop(0)
        if len(window) == target_len and bytes(window) == sub_bytes:
            return idx - target_len + 1
        idx += 1

    return -1


# -------------------------------------------------------------------------
# 2. Data Models
# -------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class CrashSignal:
    """Represents a crash signal event."""
    name: str
    signum: int
    fault_address: Optional[int] = None
    description: str = ""


@dataclasses.dataclass(frozen=True)
class RegisterState:
    """Register dump snapshot at point of crash."""
    arch: str  # "x86", "x86_64", "arm", "unknown"
    ip: int
    sp: int
    bp: Optional[int]
    registers: Dict[str, int]
    flags: Optional[int] = None


@dataclasses.dataclass(frozen=True)
class SecurityMitigations:
    """Detected compiler and runtime security mitigations."""
    nx: bool
    pie: bool
    canary: bool
    relro: str  # "No", "Partial", "Full"
    fortify: bool = False
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class CrashTrace:
    """Parsed crash trace container."""
    signal: CrashSignal
    registers: Optional[RegisterState]
    raw_message: str
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class CrashAnalysis:
    """Comprehensive verdict produced by the replay engine."""
    classification: str
    signal: CrashSignal
    registers: Optional[RegisterState]
    control_flow_hijacked: bool
    cyclic_offset: Optional[int]
    cyclic_register: Optional[str]
    mitigations: Optional[SecurityMitigations]
    summary: str
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)


# -------------------------------------------------------------------------
# 3. Security Mitigation Detection (ELF & PE & Structured)
# -------------------------------------------------------------------------

class MitigationDetector:
    """Zero-dependency binary mitigation inspector for ELF, PE, and structured inputs."""

    @staticmethod
    def detect_from_elf(data: bytes) -> SecurityMitigations:
        """Inspects ELF header, program headers, and dynamic symbols for mitigations."""
        if len(data) < 52 or data[:4] != b"\x7fELF":
            raise ValueError("Data is not a valid ELF binary")

        ei_class = data[4]  # 1 = 32-bit, 2 = 64-bit
        ei_data = data[5]   # 1 = little-endian, 2 = big-endian
        endian = "<" if ei_data == 1 else ">"

        if ei_class == 1:
            # 32-bit ELF header (13 fields after 16-byte e_ident)
            (
                e_type,
                e_machine,
                e_version,
                e_entry,
                e_phoff,
                e_shoff,
                e_flags,
                e_ehsize,
                e_phentsize,
                e_phnum,
                e_shentsize,
                e_shnum,
                e_shstrndx,
            ) = struct.unpack_from(f"{endian}HHIIIIIHHHHHH", data, 16)
            p_header_size = 32
        elif ei_class == 2:
            # 64-bit ELF header (13 fields after 16-byte e_ident)
            (
                e_type,
                e_machine,
                e_version,
                e_entry,
                e_phoff,
                e_shoff,
                e_flags,
                e_ehsize,
                e_phentsize,
                e_phnum,
                e_shentsize,
                e_shnum,
                e_shstrndx,
            ) = struct.unpack_from(f"{endian}HHIQQQIHHHHHH", data, 16)
            p_header_size = 56
        else:
            raise ValueError(f"Invalid ELF class: {ei_class}")

        pie = (e_type == 3)  # ET_DYN is PIE if executable, ET_EXEC is No PIE
        nx = True  # Default to NX enabled in modern linkers unless PF_X found in PT_GNU_STACK
        has_gnu_stack = False
        has_relro = False
        bind_now = False

        PT_GNU_STACK = 0x6474E551
        PT_GNU_RELRO = 0x6474E552
        PT_DYNAMIC = 2

        # Parse program headers
        for i in range(min(e_phnum, 128)):
            offset = e_phoff + (i * p_header_size)
            if offset + p_header_size > len(data):
                break
            if ei_class == 1:
                p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack_from(
                    f"{endian}IIIIIIII", data, offset
                )
            else:
                p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = struct.unpack_from(
                    f"{endian}IIQQQQQQ", data, offset
                )

            if p_type == PT_GNU_STACK:
                has_gnu_stack = True
                # PF_X = 1
                if p_flags & 1:
                    nx = False
            elif p_type == PT_GNU_RELRO:
                has_relro = True

        if not has_gnu_stack:
            # Legacy binaries without PT_GNU_STACK usually execute stack
            nx = False

        # Scan for BIND_NOW or DT_BIND_NOW markers
        if b"\x18\x00\x00\x00" in data or b"BIND_NOW" in data:
            bind_now = True

        relro_status = "No"
        if has_relro:
            relro_status = "Full" if bind_now else "Partial"

        # Check for stack canary symbol
        canary = (b"__stack_chk_fail" in data or b"__intel_security_cookie" in data)

        return SecurityMitigations(
            nx=nx,
            pie=pie,
            canary=canary,
            relro=relro_status,
            fortify=(b"__printf_chk" in data or b"__sprintf_chk" in data),
            details={
                "elf_class": 32 if ei_class == 1 else 64,
                "has_gnu_stack": has_gnu_stack,
                "has_relro_segment": has_relro,
                "bind_now": bind_now,
            },
        )

    @staticmethod
    def detect_from_pe(data: bytes) -> SecurityMitigations:
        """Inspects PE headers for NX/DEP and ASLR/PIE flags."""
        if len(data) < 64 or data[:2] != b"MZ":
            raise ValueError("Data is not a valid PE binary")

        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\x00\x00":
            raise ValueError("Invalid PE signature")

        size_opt_header = struct.unpack_from("<H", data, pe_offset + 20)[0]
        if size_opt_header == 0:
            return SecurityMitigations(nx=False, pie=False, canary=False, relro="No")

        opt_offset = pe_offset + 24
        opt_magic = struct.unpack_from("<H", data, opt_offset)[0]
        dll_chars_offset = opt_offset + (70 if opt_magic == 0x10B else 70)  # offset of DllCharacteristics

        dll_chars = 0
        if dll_chars_offset + 2 <= len(data):
            dll_chars = struct.unpack_from("<H", data, dll_chars_offset)[0]

        nx = bool(dll_chars & 0x0100)       # IMAGE_DLLCHARACTERISTICS_NX_COMPAT
        pie = bool(dll_chars & 0x0040)      # IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE
        canary = (b"__security_cookie" in data or b"__security_check_cookie" in data)

        return SecurityMitigations(
            nx=nx,
            pie=pie,
            canary=canary,
            relro="No",  # Windows uses SafeSEH / CFG instead of RELRO
            fortify=False,
            details={"dll_characteristics": dll_chars},
        )

    @classmethod
    def detect(cls, target: Union[bytes, Dict[str, Any]]) -> SecurityMitigations:
        """Dispatches mitigation detection based on input format."""
        if isinstance(target, dict):
            nx_val = bool(target.get("nx", target.get("NX", True)))
            pie_val = bool(target.get("pie", target.get("PIE", True)))
            canary_val = bool(target.get("canary", target.get("Canary", False)))
            relro_val = str(target.get("relro", target.get("RELRO", "No"))).capitalize()
            fortify_val = bool(target.get("fortify", target.get("Fortify", False)))
            return SecurityMitigations(
                nx=nx_val,
                pie=pie_val,
                canary=canary_val,
                relro=relro_val,
                fortify=fortify_val,
                details=target,
            )

        if isinstance(target, (bytes, bytearray)):
            if target.startswith(b"\x7fELF"):
                return cls.detect_from_elf(bytes(target))
            if target.startswith(b"MZ"):
                return cls.detect_from_pe(bytes(target))

        raise ValueError("Unsupported mitigation input format; expected ELF, PE, or dict")


# -------------------------------------------------------------------------
# 4. Crash Trace Parser
# -------------------------------------------------------------------------

class CrashTraceParser:
    """Parses text, json, and binary crash traces into structured CrashTrace models."""

    @classmethod
    def parse(cls, raw: Union[str, bytes, Dict[str, Any]]) -> CrashTrace:
        """Parses raw crash trace data fail-closed."""
        if isinstance(raw, dict):
            return cls._parse_dict(raw)
        if isinstance(raw, str):
            return cls._parse_text(raw)
        if isinstance(raw, (bytes, bytearray)):
            # Try JSON string first
            try:
                decoded = raw.decode("utf-8")
                stripped = decoded.strip()
                if stripped.startswith("{") and stripped.endswith("}"):
                    return cls._parse_dict(json.loads(stripped))
                return cls._parse_text(decoded)
            except UnicodeDecodeError:
                return cls._parse_binary(bytes(raw))

        raise TypeError(f"Unsupported crash trace input type: {type(raw)}")

    @classmethod
    def _parse_dict(cls, data: Dict[str, Any]) -> CrashTrace:
        if not data:
            raise ValueError("Empty crash dictionary")

        sig_name = str(data.get("signal", "SIGSEGV")).upper()
        if sig_name not in SUPPORTED_SIGNALS and not any(sig_name == f"SIG{s}" for s in SUPPORTED_SIGNALS):
            raise ValueError(f"Unsupported crash signal: {sig_name}")

        signum = int(data.get("signum", SUPPORTED_SIGNALS.get(sig_name, 11)))
        fault_addr_raw = data.get("fault_address", data.get("fault_addr", data.get("si_addr")))
        fault_addr = None
        if fault_addr_raw is not None:
            if isinstance(fault_addr_raw, str):
                fault_addr = int(fault_addr_raw, 16 if fault_addr_raw.startswith("0x") else 10)
            else:
                fault_addr = int(fault_addr_raw)

        signal = CrashSignal(
            name=sig_name,
            signum=signum,
            fault_address=fault_addr,
            description=str(data.get("description", "")),
        )

        regs_dict = data.get("registers")
        reg_state = None
        if isinstance(regs_dict, dict) and regs_dict:
            cleaned_regs: Dict[str, int] = {}
            for k, v in regs_dict.items():
                k_lower = str(k).lower()
                if isinstance(v, str):
                    val = int(v, 16 if v.startswith("0x") else 10)
                else:
                    val = int(v)
                if val < 0:
                    raise ValueError(f"Negative register value for {k}: {val}")
                cleaned_regs[k_lower] = val

            arch = str(data.get("arch", "x86_64" if any(k.startswith("r") for k in cleaned_regs) else "x86"))
            ip = cleaned_regs.get("rip", cleaned_regs.get("eip", cleaned_regs.get("pc", 0)))
            sp = cleaned_regs.get("rsp", cleaned_regs.get("esp", cleaned_regs.get("sp", 0)))
            bp = cleaned_regs.get("rbp", cleaned_regs.get("ebp", cleaned_regs.get("fp")))

            reg_state = RegisterState(
                arch=arch,
                ip=ip,
                sp=sp,
                bp=bp,
                registers=cleaned_regs,
                flags=cleaned_regs.get("eflags", cleaned_regs.get("rflags")),
            )

        return CrashTrace(
            signal=signal,
            registers=reg_state,
            raw_message=str(data.get("raw_message", data.get("error_message", ""))),
            metadata=data,
        )

    @classmethod
    def _parse_text(cls, text: str) -> CrashTrace:
        if not text.strip():
            raise ValueError("Crash trace text cannot be empty")

        sig_match = RE_SIGNAL.search(text)
        sig_name = sig_match.group(1).upper() if sig_match else "SIGSEGV"
        signum = SUPPORTED_SIGNALS.get(sig_name, 11)

        # Parse fault address
        fault_addr = None
        f_match = RE_FAULT_ADDR.search(text)
        if f_match:
            raw_addr = f_match.group(1)
            fault_addr = int(raw_addr, 16 if raw_addr.startswith("0x") else 16)

        # Parse dmesg style
        dmesg_match = RE_DMESG_SEGFAULT.search(text)
        registers: Dict[str, int] = {}
        if dmesg_match:
            f_hex, ip_hex, sp_hex = dmesg_match.groups()
            fault_addr = int(f_hex, 16)
            registers["rip"] = int(ip_hex, 16)
            registers["rsp"] = int(sp_hex, 16)

        # Parse key-value registers
        for line in text.splitlines():
            for m in RE_REG_LINE.finditer(line):
                reg_name = m.group(1).lower()
                reg_val_str = m.group(2)
                reg_val = int(reg_val_str, 16 if reg_val_str.startswith("0x") else 16)
                registers[reg_name] = reg_val

        signal = CrashSignal(
            name=sig_name,
            signum=signum,
            fault_address=fault_addr,
            description="",
        )

        reg_state = None
        if registers:
            is_64 = any(k.startswith("r") for k in registers)
            arch = "x86_64" if is_64 else "x86"
            ip = registers.get("rip", registers.get("eip", registers.get("pc", 0)))
            sp = registers.get("rsp", registers.get("esp", registers.get("sp", 0)))
            bp = registers.get("rbp", registers.get("ebp"))

            reg_state = RegisterState(
                arch=arch,
                ip=ip,
                sp=sp,
                bp=bp,
                registers=registers,
                flags=registers.get("eflags", registers.get("rflags")),
            )

        return CrashTrace(
            signal=signal,
            registers=reg_state,
            raw_message=text,
            metadata={"parsed_regs_count": len(registers)},
        )

    @classmethod
    def _parse_binary(cls, data: bytes) -> CrashTrace:
        """Parses raw binary crash record (Magic: CRSH)."""
        if len(data) < 20 or data[:4] != b"CRSH":
            raise ValueError("Corrupted or unknown binary crash trace format")

        magic, version, signum, arch_id, fault_addr, reg_count = struct.unpack_from(
            "<4sIIIIQ", data, 0
        )
        sig_name = SIGNAL_NUM_TO_NAME.get(signum, "SIGSEGV")
        arch_map = {1: "x86", 2: "x86_64", 3: "arm"}
        arch = arch_map.get(arch_id, "unknown")

        registers: Dict[str, int] = {}
        offset = 24
        for _ in range(reg_count):
            if offset + 9 > len(data):
                break
            name_len = data[offset]
            offset += 1
            if offset + name_len + 8 > len(data):
                break
            reg_name = data[offset : offset + name_len].decode("ascii", errors="replace").lower()
            offset += name_len
            reg_val = struct.unpack_from("<Q", data, offset)[0]
            offset += 8
            registers[reg_name] = reg_val

        ip = registers.get("rip", registers.get("eip", registers.get("pc", 0)))
        sp = registers.get("rsp", registers.get("esp", registers.get("sp", 0)))
        bp = registers.get("rbp", registers.get("ebp"))

        return CrashTrace(
            signal=CrashSignal(name=sig_name, signum=signum, fault_address=fault_addr),
            registers=RegisterState(arch=arch, ip=ip, sp=sp, bp=bp, registers=registers),
            raw_message=f"Binary CRSH record v{version}",
            metadata={"version": version, "arch_id": arch_id},
        )


# -------------------------------------------------------------------------
# 5. Crash Classification & Exploit Replay Engine
# -------------------------------------------------------------------------

class CrashReplayEngine:
    """Triage and classification engine for crashes, registers, and memory violations."""

    @classmethod
    def analyze(
        cls,
        trace_input: Union[str, bytes, Dict[str, Any], CrashTrace],
        mitigations: Optional[Union[bytes, Dict[str, Any], SecurityMitigations]] = None,
        cyclic_stride: int = 4,
    ) -> CrashAnalysis:
        """Performs fail-closed crash triage and classification."""
        if isinstance(trace_input, CrashTrace):
            trace = trace_input
        else:
            trace = CrashTraceParser.parse(trace_input)

        sec_mitigations = None
        if mitigations is not None:
            if isinstance(mitigations, SecurityMitigations):
                sec_mitigations = mitigations
            else:
                sec_mitigations = MitigationDetector.detect(mitigations)

        sig = trace.signal
        regs = trace.registers
        raw_msg = trace.raw_message.lower()

        classification = CLASS_UNKNOWN
        control_flow_hijacked = False
        cyclic_offset = None
        cyclic_reg = None
        details: Dict[str, Any] = {}

        # 1. Evaluate Register State & De Bruijn Overwrite
        if regs is not None:
            # Check Instruction Pointer (EIP / RIP)
            if regs.ip != 0:
                # First check stride n, then fall back to 4 if 64-bit architecture
                offset = cyclic_find(regs.ip, n=cyclic_stride)
                if offset == -1 and cyclic_stride != 4 and regs.ip <= 0xFFFFFFFF:
                    offset = cyclic_find(regs.ip, n=4)

                if offset != -1:
                    classification = CLASS_CONTROL_FLOW_HIJACK
                    control_flow_hijacked = True
                    cyclic_offset = offset
                    cyclic_reg = "rip" if regs.arch == "x86_64" else "eip"
                    details["ip_overwrite_offset"] = offset

            # Check Base / Frame Pointer (EBP / RBP)
            if regs.bp is not None and regs.bp != 0:
                bp_offset = cyclic_find(regs.bp, n=cyclic_stride)
                if bp_offset == -1 and cyclic_stride != 4 and regs.bp <= 0xFFFFFFFF:
                    bp_offset = cyclic_find(regs.bp, n=4)

                if bp_offset != -1:
                    details["bp_overwrite_offset"] = bp_offset
                    if classification == CLASS_UNKNOWN:
                        classification = CLASS_STACK_BUFFER_OVERFLOW
                    details["stack_frame_corrupted"] = True

        # 2. Check for explicit Heap Corruption markers or signals
        is_heap_error = any(marker in raw_msg for marker in HEAP_ERROR_MARKERS)
        if is_heap_error:
            classification = CLASS_HEAP_CORRUPTION
            details["heap_corruption_detected"] = True

        # 3. Check for Stack Smashing markers
        is_stack_smash = any(marker in raw_msg for marker in STACK_ERROR_MARKERS)
        if is_stack_smash:
            classification = CLASS_STACK_BUFFER_OVERFLOW
            details["canary_destruction_detected"] = True

        # 4. Check Null Pointer Dereference
        if sig.fault_address is not None:
            details["fault_address_hex"] = hex(sig.fault_address)
            # Memory within first 4 KB page (0x0 - 0x0FFF)
            if 0 <= sig.fault_address < 0x1000 and sig.name in ("SIGSEGV", "SIGBUS"):
                if classification == CLASS_UNKNOWN:
                    classification = CLASS_NULL_POINTER_DEREFERENCE
                    details["null_dereference"] = True

        # 5. Arithmetic & Instruction faults
        if classification == CLASS_UNKNOWN:
            if sig.name == "SIGFPE":
                classification = CLASS_DIVIDE_BY_ZERO
            elif sig.name == "SIGILL":
                classification = CLASS_ILLEGAL_INSTRUCTION

        # 6. Reconcile Control Flow Hijack vs Stack Overflow
        if control_flow_hijacked:
            summary = f"Control flow hijacked via {cyclic_reg} overwrite at cyclic offset {cyclic_offset}."
        elif classification == CLASS_NULL_POINTER_DEREFERENCE:
            summary = f"Null pointer dereference fault at address {hex(sig.fault_address or 0)}."
        elif classification == CLASS_HEAP_CORRUPTION:
            summary = "Heap metadata corruption or double-free violation detected."
        elif classification == CLASS_STACK_BUFFER_OVERFLOW:
            summary = "Stack buffer overflow detected via frame corruption or canary check failure."
        elif classification == CLASS_DIVIDE_BY_ZERO:
            summary = "Divide by zero or floating point exception."
        elif classification == CLASS_ILLEGAL_INSTRUCTION:
            summary = "Execution of illegal or privileged CPU instruction."
        else:
            summary = f"Unclassified crash on signal {sig.name} ({sig.signum})."

        return CrashAnalysis(
            classification=classification,
            signal=sig,
            registers=regs,
            control_flow_hijacked=control_flow_hijacked,
            cyclic_offset=cyclic_offset,
            cyclic_register=cyclic_reg,
            mitigations=sec_mitigations,
            summary=summary,
            details=details,
        )


__all__ = [
    "DEFAULT_ALPHABET",
    "MAX_CYCLIC_LENGTH",
    "SUPPORTED_SIGNALS",
    "SIGNAL_NUM_TO_NAME",
    "CLASS_CONTROL_FLOW_HIJACK",
    "CLASS_NULL_POINTER_DEREFERENCE",
    "CLASS_HEAP_CORRUPTION",
    "CLASS_STACK_BUFFER_OVERFLOW",
    "CLASS_DIVIDE_BY_ZERO",
    "CLASS_ILLEGAL_INSTRUCTION",
    "CLASS_UNKNOWN",
    "CrashSignal",
    "RegisterState",
    "SecurityMitigations",
    "CrashTrace",
    "CrashAnalysis",
    "cyclic",
    "cyclic_find",
    "de_bruijn_sequence",
    "MitigationDetector",
    "CrashTraceParser",
    "CrashReplayEngine",
]
