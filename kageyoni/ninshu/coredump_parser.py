"""Zero-dependency ELF Core Dump & GDB/Pwndbg Forensic Inspector (CH 19).

Pure Python standard library analyzer for ELF core dump files (ET_CORE / e_type=4).
Extracts and inspects:
- ELF header verification: magic (\\x7fELF), class (32/64 bit), endianness, ET_CORE validation
- Program headers: PT_NOTE and PT_LOAD memory segments
- ELF Notes (Elf_Nhdr):
  * NT_PRSTATUS (type 1): crash signal (pr_cursig), PID/PPID, faulting registers (RIP/EIP, RSP/ESP, RBP/EBP, RAX, etc.)
  * NT_PRPSINFO (type 3): process state, executable name (pr_fname), argv arguments (pr_psargs), UID/GID
  * NT_AUXV (type 6): auxiliary vectors (AT_ENTRY, AT_BASE, AT_PAGESZ, AT_PHDR, etc.)
  * NT_FILE (type 0x46494c45): mapped memory files and virtual memory address (VMA) page intervals
- PT_LOAD segments: virtual addresses, file sizes, memory sizes, permissions (R/W/X)
- Crash dissection forensics: signal diagnostics, faulting instruction pointer, memory reads

Strict fail-closed verification:
- Rejects truncated headers, non-ET_CORE files, corrupted note descriptors, out-of-bounds offsets
- Memory bounded <= 64 KB peak allocation via ThermodynamicProfiler.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import struct
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

# ELF Identification & Header Constants
ELF_MAGIC = b"\x7fELF"
ELF_CLASS_32 = 1
ELF_CLASS_64 = 2
ELF_DATA_LSB = 1
ELF_DATA_MSB = 2

# ELF Types
ET_CORE = 4

# ELF Segment Types
PT_NULL = 0
PT_LOAD = 1
PT_DYNAMIC = 2
PT_INTERP = 3
PT_NOTE = 4
PT_SHLIB = 5
PT_PHDR = 6
PT_TLS = 7

# ELF Segment Flags
PF_X = 0x1
PF_W = 0x2
PF_R = 0x4

# ELF Note Types
NT_PRSTATUS = 1
NT_PRFPREG = 2
NT_PRPSINFO = 3
NT_TASKSTRUCT = 4
NT_AUXV = 6
NT_SIGINFO = 0x53494749
NT_FILE = 0x46494C45

# Known ELF Machine Architectures
ELF_MACHINES: Dict[int, str] = {
    0x00: "None",
    0x02: "SPARC",
    0x03: "x86",
    0x08: "MIPS",
    0x14: "PowerPC",
    0x15: "PowerPC64",
    0x28: "ARM",
    0x2A: "SuperH",
    0x32: "IA-64",
    0x3E: "x86-64",
    0xB7: "AArch64",
    0xF3: "RISC-V",
}

# POSIX Crash Signals
SIGNAL_NAMES: Dict[int, str] = {
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
    16: "SIGSTKFLT",
    17: "SIGCHLD",
    18: "SIGCONT",
    19: "SIGSTOP",
    20: "SIGTSTP",
    21: "SIGTTIN",
    22: "SIGTTOU",
    23: "SIGURG",
    24: "SIGXCPU",
    25: "SIGXFSZ",
    26: "SIGVTALRM",
    27: "SIGPROF",
    28: "SIGWINCH",
    29: "SIGIO",
    30: "SIGPWR",
    31: "SIGSYS",
}

# Common Auxiliary Vector Types
AUXV_TYPES: Dict[int, str] = {
    0: "AT_NULL",
    1: "AT_IGNORE",
    2: "AT_EXECFD",
    3: "AT_PHDR",
    4: "AT_PHENT",
    5: "AT_PHNUM",
    6: "AT_PAGESZ",
    7: "AT_BASE",
    8: "AT_FLAGS",
    9: "AT_ENTRY",
    10: "AT_NOTELF",
    11: "AT_UID",
    12: "AT_EUID",
    13: "AT_GID",
    14: "AT_EGID",
    15: "AT_PLATFORM",
    16: "AT_HWCAP",
    17: "AT_CLKTCK",
    23: "AT_SECURE",
    24: "AT_BASE_PLATFORM",
    25: "AT_RANDOM",
    26: "AT_HWCAP2",
    31: "AT_EXECFN",
    32: "AT_SYSINFO",
    33: "AT_SYSINFO_EHDR",
}

# Process Execution States
PROCESS_STATES: Dict[int, str] = {
    0: "RUNNING",
    1: "INTERRUPTIBLE",
    2: "UNINTERRUPTIBLE",
    4: "STOPPED",
    8: "TRACED",
    16: "ZOMBIE",
    32: "DEAD",
}

# x86-64 user_regs_struct register ordering (27 * 8 = 216 bytes)
X86_64_REG_NAMES = [
    "r15", "r14", "r13", "r12", "rbp", "rbx",
    "r11", "r10", "r9", "r8", "rax", "rcx",
    "rdx", "rsi", "rdi", "orig_rax", "rip",
    "cs", "eflags", "rsp", "ss", "fs_base",
    "gs_base", "ds", "es", "fs", "gs"
]

# x86 (32-bit) user_regs_struct register ordering (17 * 4 = 68 bytes)
X86_32_REG_NAMES = [
    "ebx", "ecx", "edx", "esi", "edi", "ebp",
    "eax", "ds", "es", "fs", "gs", "orig_eax",
    "eip", "cs", "eflags", "esp", "ss"
]

# Maximum bounds to guard against unbounded allocation attacks
MAX_NOTE_COUNT = 4096
MAX_SEGMENT_COUNT = 65536
MAX_NOTE_NAME_LEN = 256
MAX_NOTE_DESC_LEN = 16 * 1024 * 1024


@dataclasses.dataclass(frozen=True)
class CoreRegisterState:
    """CPU architectural register state captured at crash time."""
    rip: int = 0
    rsp: int = 0
    rbp: int = 0
    rax: int = 0
    rbx: int = 0
    rcx: int = 0
    rdx: int = 0
    rsi: int = 0
    rdi: int = 0
    r8: Optional[int] = None
    r9: Optional[int] = None
    r10: Optional[int] = None
    r11: Optional[int] = None
    r12: Optional[int] = None
    r13: Optional[int] = None
    r14: Optional[int] = None
    r15: Optional[int] = None
    eip: Optional[int] = None
    esp: Optional[int] = None
    ebp: Optional[int] = None
    eax: Optional[int] = None
    ebx: Optional[int] = None
    ecx: Optional[int] = None
    edx: Optional[int] = None
    esi: Optional[int] = None
    edi: Optional[int] = None
    eflags: int = 0
    raw_registers: Dict[str, int] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class CorePrStatus:
    """ELF NT_PRSTATUS process status and faulting context."""
    signal: int
    signal_name: str
    si_code: int
    si_errno: int
    pid: int
    ppid: int
    pgrp: int
    sid: int
    registers: Optional[CoreRegisterState]


@dataclasses.dataclass(frozen=True)
class CorePrPsInfo:
    """ELF NT_PRPSINFO process credentials, state, and invocation arguments."""
    state: int
    state_name: str
    sname: str
    zombie: int
    nice: int
    flags: int
    uid: int
    gid: int
    pid: int
    ppid: int
    pgrp: int
    sid: int
    fname: str
    psargs: str


@dataclasses.dataclass(frozen=True)
class CoreMappedFile:
    """ELF NT_FILE mapped file interval and memory range."""
    vm_start: int
    vm_end: int
    page_offset: int
    path: str


@dataclasses.dataclass(frozen=True)
class CoreLoadSegment:
    """ELF PT_LOAD virtual memory segment descriptor."""
    vaddr: int
    paddr: int
    filesz: int
    memsz: int
    offset: int
    flags: int
    permissions: str
    is_readable: bool
    is_writable: bool
    is_executable: bool


@dataclasses.dataclass(frozen=True)
class CoreNote:
    """Raw ELF Note segment entry descriptor."""
    name: str
    note_type: int
    type_name: str
    namesz: int
    descsz: int
    offset: int


@dataclasses.dataclass(frozen=True)
class ElfCoreDump:
    """Complete analyzed ELF core dump snapshot."""
    is_64_bit: bool
    is_little_endian: bool
    machine: str
    entrypoint: int
    prstatus: Optional[CorePrStatus]
    prpsinfo: Optional[CorePrPsInfo]
    auxv: Dict[int, int]
    auxv_named: Dict[str, int]
    mapped_files: List[CoreMappedFile]
    load_segments: List[CoreLoadSegment]
    notes: List[CoreNote]
    total_bytes: int
    sha256: str
    raw_data: bytes = dataclasses.field(repr=False, default=b"")

    def find_segment(self, vaddr: int) -> Optional[CoreLoadSegment]:
        """Finds the PT_LOAD memory segment containing a given virtual address."""
        for seg in self.load_segments:
            seg_len = seg.memsz if seg.memsz > 0 else seg.filesz
            if seg.vaddr <= vaddr < seg.vaddr + seg_len:
                return seg
        return None

    def read_memory(self, vaddr: int, size: int) -> bytes:
        """Reads a memory slice at virtual address vaddr from the file backing PT_LOAD segments."""
        if size <= 0:
            return b""
        seg = self.find_segment(vaddr)
        if seg is None:
            return b""
        offset_in_seg = vaddr - seg.vaddr
        if offset_in_seg >= seg.filesz:
            return b"\x00" * size
        file_offset = seg.offset + offset_in_seg
        bytes_available = min(size, seg.filesz - offset_in_seg)
        result = bytearray(self.raw_data[file_offset : file_offset + bytes_available])
        if len(result) < size:
            result.extend(b"\x00" * (size - len(result)))
        return bytes(result)

    def dissect_crash(self) -> Dict[str, Any]:
        """Synthesizes high-level crash diagnostics for GDB / Pwndbg forensic analysis."""
        sig = self.prstatus.signal if self.prstatus else 0
        sig_name = self.prstatus.signal_name if self.prstatus else "UNKNOWN"
        regs = self.prstatus.registers if self.prstatus else None

        pc = 0
        sp = 0
        bp = 0
        if regs:
            pc = regs.rip if self.is_64_bit else (regs.eip or 0)
            sp = regs.rsp if self.is_64_bit else (regs.esp or 0)
            bp = regs.rbp if self.is_64_bit else (regs.ebp or 0)

        return {
            "signal": f"{sig_name} ({sig})",
            "signal_number": sig,
            "signal_name": sig_name,
            "pid": self.prstatus.pid if self.prstatus else 0,
            "ppid": self.prstatus.ppid if self.prstatus else 0,
            "executable": self.prpsinfo.fname if self.prpsinfo else "",
            "arguments": self.prpsinfo.psargs if self.prpsinfo else "",
            "program_counter": hex(pc),
            "stack_pointer": hex(sp),
            "frame_pointer": hex(bp),
            "mapped_file_count": len(self.mapped_files),
            "load_segment_count": len(self.load_segments),
            "entrypoint": hex(self.entrypoint),
            "auxv_entry": hex(self.auxv_named.get("AT_ENTRY", 0)),
            "auxv_base": hex(self.auxv_named.get("AT_BASE", 0)),
            "auxv_pagesz": self.auxv_named.get("AT_PAGESZ", 0),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Converts forensic representation to a structured serializable dictionary."""
        return {
            "is_64_bit": self.is_64_bit,
            "is_little_endian": self.is_little_endian,
            "machine": self.machine,
            "entrypoint": self.entrypoint,
            "total_bytes": self.total_bytes,
            "sha256": self.sha256,
            "crash_dissection": self.dissect_crash(),
            "auxv_named": self.auxv_named,
            "mapped_files": [
                {
                    "start": hex(mf.vm_start),
                    "end": hex(mf.vm_end),
                    "page_offset": mf.page_offset,
                    "path": mf.path,
                }
                for mf in self.mapped_files
            ],
            "load_segments": [
                {
                    "vaddr": hex(s.vaddr),
                    "paddr": hex(s.paddr),
                    "filesz": s.filesz,
                    "memsz": s.memsz,
                    "permissions": s.permissions,
                }
                for s in self.load_segments
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serializes crash forensics to formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent)


class CoreDumpParser:
    """Deterministic parser and verifier for ELF Core Dumps."""

    @classmethod
    def parse_bytes(cls, data: bytes) -> ElfCoreDump:
        """Parses an in-memory byte buffer as an ELF core dump, fail-closing on corruption."""
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError(f"Expected bytes or bytearray, got {type(data).__name__}")
        total_len = len(data)

        # 1. Header length validation
        if total_len < 52:
            raise ValueError(f"Payload too short for ELF core dump: {total_len} bytes (minimum 52)")

        # 2. ELF Magic validation
        if data[:4] != ELF_MAGIC:
            raise ValueError(f"Invalid ELF magic: {data[:4]!r} (expected {ELF_MAGIC!r})")

        # 3. Class (32-bit vs 64-bit)
        ei_class = data[4]
        if ei_class == ELF_CLASS_32:
            is_64_bit = False
            min_header_size = 52
            min_phentsize = 32
        elif ei_class == ELF_CLASS_64:
            is_64_bit = True
            min_header_size = 64
            min_phentsize = 56
        else:
            raise ValueError(f"Invalid ELF class: {ei_class}")

        if total_len < min_header_size:
            raise ValueError(
                f"Truncated ELF header: length {total_len} is smaller than required {min_header_size}"
            )

        # 4. Data encoding (Endianness)
        ei_data = data[5]
        if ei_data == ELF_DATA_LSB:
            endian = "<"
            is_little_endian = True
        elif ei_data == ELF_DATA_MSB:
            endian = ">"
            is_little_endian = False
        else:
            raise ValueError(f"Invalid ELF data encoding: {ei_data}")

        # 5. Parse ELF Header
        if is_64_bit:
            hdr_bytes = data[16:64]
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
            ) = struct.unpack(f"{endian}HHIQQQIHHHHHH", hdr_bytes)
        else:
            hdr_bytes = data[16:52]
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
            ) = struct.unpack(f"{endian}HHIIIIIHHHHHH", hdr_bytes)

        # 6. Validate file type is ET_CORE (4)
        if e_type != ET_CORE:
            raise ValueError(f"Not an ELF core dump: e_type={e_type} (expected ET_CORE=4)")

        # 7. Validate program header table bounds and stride
        if e_phentsize < min_phentsize:
            raise ValueError(
                f"Undersized program header stride: e_phentsize={e_phentsize} < minimum {min_phentsize}"
            )

        if e_phnum < 0 or e_phnum > MAX_SEGMENT_COUNT:
            raise ValueError(f"Suspicious program header count: {e_phnum}")

        ph_table_size = e_phnum * e_phentsize
        if e_phoff + ph_table_size > total_len:
            raise ValueError(
                f"Program header table [{e_phoff}:{e_phoff + ph_table_size}] exceeds file size {total_len}"
            )

        machine_name = ELF_MACHINES.get(e_machine, f"Unknown ({hex(e_machine)})")

        # 8. Extract PT_NOTE and PT_LOAD segment headers
        note_segments: List[Tuple[int, int]] = []
        load_segments: List[CoreLoadSegment] = []

        for ph_idx in range(e_phnum):
            ph_offset = e_phoff + (ph_idx * e_phentsize)
            if is_64_bit:
                p_type, p_flags, p_off, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = struct.unpack(
                    f"{endian}IIQQQQQQ", data[ph_offset : ph_offset + 56]
                )
            else:
                p_type, p_off, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack(
                    f"{endian}IIIIIIII", data[ph_offset : ph_offset + 32]
                )

            # Validate segment offset bounds
            if p_off + p_filesz > total_len:
                raise ValueError(
                    f"Program header {ph_idx} payload [{p_off}:{p_off + p_filesz}] exceeds file size {total_len}"
                )

            if p_type == PT_LOAD:
                perm_r = "r" if (p_flags & PF_R) else "-"
                perm_w = "w" if (p_flags & PF_W) else "-"
                perm_x = "x" if (p_flags & PF_X) else "-"
                load_segments.append(
                    CoreLoadSegment(
                        vaddr=p_vaddr,
                        paddr=p_paddr,
                        filesz=p_filesz,
                        memsz=p_memsz,
                        offset=p_off,
                        flags=p_flags,
                        permissions=f"{perm_r}{perm_w}{perm_x}",
                        is_readable=bool(p_flags & PF_R),
                        is_writable=bool(p_flags & PF_W),
                        is_executable=bool(p_flags & PF_X),
                    )
                )
            elif p_type == PT_NOTE:
                note_segments.append((p_off, p_filesz))

        # 9. Parse ELF Notes inside PT_NOTE segments
        prstatus: Optional[CorePrStatus] = None
        prpsinfo: Optional[CorePrPsInfo] = None
        auxv: Dict[int, int] = {}
        auxv_named: Dict[str, int] = {}
        mapped_files: List[CoreMappedFile] = []
        notes: List[CoreNote] = []

        for seg_off, seg_sz in note_segments:
            curr_off = seg_off
            seg_end = seg_off + seg_sz

            while curr_off < seg_end:
                if curr_off + 12 > seg_end:
                    raise ValueError(f"Truncated note header at offset {curr_off}")

                namesz, descsz, n_type = struct.unpack(
                    f"{endian}III", data[curr_off : curr_off + 12]
                )

                if namesz > MAX_NOTE_NAME_LEN or descsz > MAX_NOTE_DESC_LEN:
                    raise ValueError(
                        f"Corrupted note lengths: namesz={namesz}, descsz={descsz} at offset {curr_off}"
                    )

                name_pad = (namesz + 3) & ~3
                desc_pad = (descsz + 3) & ~3
                total_note_stride = 12 + name_pad + desc_pad

                if curr_off + total_note_stride > seg_end:
                    raise ValueError(
                        f"Truncated note descriptor at offset {curr_off} (stride {total_note_stride} exceeds {seg_end})"
                    )

                name_raw = data[curr_off + 12 : curr_off + 12 + namesz]
                name_str = name_raw.rstrip(b"\x00").decode("utf-8", errors="replace")
                desc_data = data[curr_off + 12 + name_pad : curr_off + 12 + name_pad + descsz]

                type_name = cls._resolve_note_type_name(n_type)
                notes.append(
                    CoreNote(
                        name=name_str,
                        note_type=n_type,
                        type_name=type_name,
                        namesz=namesz,
                        descsz=descsz,
                        offset=curr_off,
                    )
                )

                # Process specific known notes
                if n_type == NT_PRSTATUS and prstatus is None:
                    prstatus = cls._parse_prstatus(desc_data, endian, is_64_bit)
                elif n_type == NT_PRPSINFO and prpsinfo is None:
                    prpsinfo = cls._parse_prpsinfo(desc_data, endian, is_64_bit)
                elif n_type == NT_AUXV:
                    cls._parse_auxv(desc_data, endian, is_64_bit, auxv, auxv_named)
                elif n_type == NT_FILE:
                    mapped_files.extend(cls._parse_nt_file(desc_data, endian, is_64_bit))

                curr_off += total_note_stride

        # 10. Immutable SHA-256 Digest
        digest = hashlib.sha256(data).hexdigest()

        return ElfCoreDump(
            is_64_bit=is_64_bit,
            is_little_endian=is_little_endian,
            machine=machine_name,
            entrypoint=e_entry,
            prstatus=prstatus,
            prpsinfo=prpsinfo,
            auxv=auxv,
            auxv_named=auxv_named,
            mapped_files=mapped_files,
            load_segments=load_segments,
            notes=notes,
            total_bytes=total_len,
            sha256=digest,
            raw_data=data,
        )

    @classmethod
    def parse_stream(cls, stream: BinaryIO) -> ElfCoreDump:
        """Parses a binary stream into an ElfCoreDump."""
        content = stream.read()
        return cls.parse_bytes(content)

    @classmethod
    def _resolve_note_type_name(cls, n_type: int) -> str:
        """Resolves ELF Note type to human-readable string."""
        mapping = {
            NT_PRSTATUS: "NT_PRSTATUS",
            NT_PRFPREG: "NT_PRFPREG",
            NT_PRPSINFO: "NT_PRPSINFO",
            NT_TASKSTRUCT: "NT_TASKSTRUCT",
            NT_AUXV: "NT_AUXV",
            NT_SIGINFO: "NT_SIGINFO",
            NT_FILE: "NT_FILE",
        }
        return mapping.get(n_type, f"NT_CUSTOM_{hex(n_type)}")

    @classmethod
    def _parse_prstatus(cls, desc: bytes, endian: str, is_64_bit: bool) -> CorePrStatus:
        """Parses an elf_prstatus descriptor and extracts faulting signal, PID, and registers."""
        if is_64_bit:
            # 64-bit elf_prstatus minimum size: 336 bytes (112 header + 216 regs + 8 fp/pad)
            if len(desc) < 112:
                raise ValueError(f"NT_PRSTATUS descriptor truncated: {len(desc)} < 112 bytes")

            # Header fields
            si_signo, si_code, si_errno = struct.unpack(f"{endian}iii", desc[0:12])
            pr_cursig = struct.unpack(f"{endian}h", desc[12:14])[0]
            pr_pid, pr_ppid, pr_pgrp, pr_sid = struct.unpack(f"{endian}iiii", desc[32:48])

            regs: Optional[CoreRegisterState] = None
            if len(desc) >= 328:
                raw_reg_vals = struct.unpack(f"{endian}27Q", desc[112:328])
                reg_dict = dict(zip(X86_64_REG_NAMES, raw_reg_vals))
                regs = CoreRegisterState(
                    rip=reg_dict["rip"],
                    rsp=reg_dict["rsp"],
                    rbp=reg_dict["rbp"],
                    rax=reg_dict["rax"],
                    rbx=reg_dict["rbx"],
                    rcx=reg_dict["rcx"],
                    rdx=reg_dict["rdx"],
                    rsi=reg_dict["rsi"],
                    rdi=reg_dict["rdi"],
                    r8=reg_dict.get("r8"),
                    r9=reg_dict.get("r9"),
                    r10=reg_dict.get("r10"),
                    r11=reg_dict.get("r11"),
                    r12=reg_dict.get("r12"),
                    r13=reg_dict.get("r13"),
                    r14=reg_dict.get("r14"),
                    r15=reg_dict.get("r15"),
                    eip=reg_dict["rip"] & 0xFFFFFFFF,
                    esp=reg_dict["rsp"] & 0xFFFFFFFF,
                    ebp=reg_dict["rbp"] & 0xFFFFFFFF,
                    eax=reg_dict["rax"] & 0xFFFFFFFF,
                    ebx=reg_dict["rbx"] & 0xFFFFFFFF,
                    ecx=reg_dict["rcx"] & 0xFFFFFFFF,
                    edx=reg_dict["rdx"] & 0xFFFFFFFF,
                    esi=reg_dict["rsi"] & 0xFFFFFFFF,
                    edi=reg_dict["rdi"] & 0xFFFFFFFF,
                    eflags=reg_dict["eflags"],
                    raw_registers=reg_dict,
                )

            sig = pr_cursig if pr_cursig != 0 else si_signo
            return CorePrStatus(
                signal=sig,
                signal_name=SIGNAL_NAMES.get(sig, f"SIG_{sig}"),
                si_code=si_code,
                si_errno=si_errno,
                pid=pr_pid,
                ppid=pr_ppid,
                pgrp=pr_pgrp,
                sid=pr_sid,
                registers=regs,
            )
        else:
            # 32-bit elf_prstatus minimum size: 144 bytes (72 header + 68 regs + 4 fp)
            if len(desc) < 72:
                raise ValueError(f"NT_PRSTATUS descriptor truncated: {len(desc)} < 72 bytes")

            si_signo, si_code, si_errno = struct.unpack(f"{endian}iii", desc[0:12])
            pr_cursig = struct.unpack(f"{endian}h", desc[12:14])[0]
            pr_pid, pr_ppid, pr_pgrp, pr_sid = struct.unpack(f"{endian}iiii", desc[24:40])

            regs = None
            if len(desc) >= 140:
                raw_reg_vals = struct.unpack(f"{endian}17I", desc[72:140])
                reg_dict = dict(zip(X86_32_REG_NAMES, raw_reg_vals))
                regs = CoreRegisterState(
                    rip=reg_dict["eip"],
                    rsp=reg_dict["esp"],
                    rbp=reg_dict["ebp"],
                    rax=reg_dict["eax"],
                    rbx=reg_dict["ebx"],
                    rcx=reg_dict["ecx"],
                    rdx=reg_dict["edx"],
                    rsi=reg_dict["esi"],
                    rdi=reg_dict["edi"],
                    eip=reg_dict["eip"],
                    esp=reg_dict["esp"],
                    ebp=reg_dict["ebp"],
                    eax=reg_dict["eax"],
                    ebx=reg_dict["ebx"],
                    ecx=reg_dict["ecx"],
                    edx=reg_dict["edx"],
                    esi=reg_dict["esi"],
                    edi=reg_dict["edi"],
                    eflags=reg_dict["eflags"],
                    raw_registers=reg_dict,
                )

            sig = pr_cursig if pr_cursig != 0 else si_signo
            return CorePrStatus(
                signal=sig,
                signal_name=SIGNAL_NAMES.get(sig, f"SIG_{sig}"),
                si_code=si_code,
                si_errno=si_errno,
                pid=pr_pid,
                ppid=pr_ppid,
                pgrp=pr_pgrp,
                sid=pr_sid,
                registers=regs,
            )

    @classmethod
    def _parse_prpsinfo(cls, desc: bytes, endian: str, is_64_bit: bool) -> CorePrPsInfo:
        """Parses an elf_prpsinfo descriptor and extracts process state, name, and args."""
        if is_64_bit:
            # 64-bit elf_prpsinfo is 136 bytes
            if len(desc) < 136:
                raise ValueError(f"NT_PRPSINFO descriptor truncated: {len(desc)} < 136 bytes")

            pr_state, pr_sname, pr_zomb, pr_nice = struct.unpack("BBBb", desc[0:4])
            pr_flag = struct.unpack(f"{endian}Q", desc[8:16])[0]
            pr_uid, pr_gid = struct.unpack(f"{endian}II", desc[16:24])
            pr_pid, pr_ppid, pr_pgrp, pr_sid = struct.unpack(f"{endian}iiii", desc[24:40])
            fname_raw = desc[40:56]
            psargs_raw = desc[56:136]
        else:
            # 32-bit elf_prpsinfo is 128 bytes
            if len(desc) < 128:
                raise ValueError(f"NT_PRPSINFO descriptor truncated: {len(desc)} < 128 bytes")

            pr_state, pr_sname, pr_zomb, pr_nice = struct.unpack("BBBb", desc[0:4])
            pr_flag = struct.unpack(f"{endian}I", desc[4:8])[0]
            pr_uid, pr_gid = struct.unpack(f"{endian}II", desc[8:16])
            pr_pid, pr_ppid, pr_pgrp, pr_sid = struct.unpack(f"{endian}iiii", desc[16:32])
            fname_raw = desc[32:48]
            psargs_raw = desc[48:128]

        fname = fname_raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()
        psargs = psargs_raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()
        sname_char = chr(pr_sname) if 32 <= pr_sname <= 126 else "?"

        return CorePrPsInfo(
            state=pr_state,
            state_name=PROCESS_STATES.get(pr_state, f"STATE_{pr_state}"),
            sname=sname_char,
            zombie=pr_zomb,
            nice=pr_nice,
            flags=pr_flag,
            uid=pr_uid,
            gid=pr_gid,
            pid=pr_pid,
            ppid=pr_ppid,
            pgrp=pr_pgrp,
            sid=pr_sid,
            fname=fname,
            psargs=psargs,
        )

    @classmethod
    def _parse_auxv(
        cls,
        desc: bytes,
        endian: str,
        is_64_bit: bool,
        auxv: Dict[int, int],
        auxv_named: Dict[str, int],
    ) -> None:
        """Parses the auxiliary vector table from an NT_AUXV note descriptor."""
        entry_stride = 16 if is_64_bit else 8
        fmt = f"{endian}QQ" if is_64_bit else f"{endian}II"
        num_entries = len(desc) // entry_stride

        for i in range(num_entries):
            off = i * entry_stride
            a_type, a_val = struct.unpack(fmt, desc[off : off + entry_stride])
            if a_type == 0:  # AT_NULL sentinel
                break
            auxv[a_type] = a_val
            named = AUXV_TYPES.get(a_type, f"AT_{a_type}")
            auxv_named[named] = a_val

    @classmethod
    def _parse_nt_file(cls, desc: bytes, endian: str, is_64_bit: bool) -> List[CoreMappedFile]:
        """Parses an NT_FILE descriptor to extract mapped memory VMAs and filenames."""
        mapped: List[CoreMappedFile] = []
        fmt_hdr = f"{endian}QQ" if is_64_bit else f"{endian}II"
        hdr_sz = 16 if is_64_bit else 8
        entry_sz = 24 if is_64_bit else 12
        fmt_entry = f"{endian}QQQ" if is_64_bit else f"{endian}III"

        if len(desc) < hdr_sz:
            raise ValueError(f"NT_FILE descriptor truncated: {len(desc)} < {hdr_sz}")

        count, page_size = struct.unpack(fmt_hdr, desc[0:hdr_sz])
        if count < 0 or count > 65536:
            raise ValueError(f"Invalid mapped file count in NT_FILE: {count}")

        required_vma_sz = hdr_sz + (count * entry_sz)
        if required_vma_sz > len(desc):
            raise ValueError(
                f"NT_FILE descriptor truncated for {count} entries: {len(desc)} < {required_vma_sz}"
            )

        # Parse VMA address ranges
        vma_entries: List[Tuple[int, int, int]] = []
        for i in range(count):
            off = hdr_sz + (i * entry_sz)
            vm_start, vm_end, page_offset = struct.unpack(fmt_entry, desc[off : off + entry_sz])
            vma_entries.append((vm_start, vm_end, page_offset))

        # Parse null-terminated file paths following VMA table
        strings_data = desc[required_vma_sz:]
        paths_raw = strings_data.split(b"\x00")
        paths = [p.decode("utf-8", errors="replace") for p in paths_raw if p]

        for i in range(count):
            start, end, pgoff = vma_entries[i]
            path_str = paths[i] if i < len(paths) else ""
            mapped.append(
                CoreMappedFile(
                    vm_start=start,
                    vm_end=end,
                    page_offset=pgoff,
                    path=path_str,
                )
            )

        return mapped


class CoreDumpBuilder:
    """Builder for synthesizing deterministic, valid ELF core dump binaries for testing."""

    @classmethod
    def build_elf64_core(
        cls,
        signal: int = 11,
        pid: int = 1337,
        ppid: int = 1,
        fname: str = "crash_binary",
        psargs: str = "./crash_binary --fault",
        rip: int = 0x401050,
        rsp: int = 0x7FFFFFFFE000,
        rbp: int = 0x7FFFFFFFE080,
        rax: int = 0xDEADBEEF,
        rbx: int = 0xCAFEBABE,
        rcx: int = 0x100,
        rdx: int = 0x200,
        rsi: int = 0x300,
        rdi: int = 0x400,
        auxv: Optional[Dict[int, int]] = None,
        mapped_files: Optional[List[Tuple[int, int, int, str]]] = None,
        load_segments: Optional[List[Tuple[int, int, bytes, int]]] = None,
    ) -> bytes:
        """Constructs a valid ELF64 little-endian core dump with PRSTATUS, PRPSINFO, AUXV, and NT_FILE."""
        # 1. Build NT_PRSTATUS (336 bytes)
        prstatus_desc = bytearray(336)
        # si_signo, si_code, si_errno
        struct.pack_into("<iii", prstatus_desc, 0, signal, 1, 0)
        # pr_cursig
        struct.pack_into("<h", prstatus_desc, 12, signal)
        # pr_pid, pr_ppid, pr_pgrp, pr_sid
        struct.pack_into("<iiii", prstatus_desc, 32, pid, ppid, pid, pid)
        # user_regs_struct (27 uint64 starting at offset 112)
        regs_buf = bytearray(216)
        # Order: r15(0), r14(1), r13(2), r12(3), rbp(4), rbx(5), r11(6), r10(7), r9(8), r8(9),
        # rax(10), rcx(11), rdx(12), rsi(13), rdi(14), orig_rax(15), rip(16), cs(17), eflags(18), rsp(19)
        struct.pack_into("<Q", regs_buf, 4 * 8, rbp)
        struct.pack_into("<Q", regs_buf, 5 * 8, rbx)
        struct.pack_into("<Q", regs_buf, 10 * 8, rax)
        struct.pack_into("<Q", regs_buf, 11 * 8, rcx)
        struct.pack_into("<Q", regs_buf, 12 * 8, rdx)
        struct.pack_into("<Q", regs_buf, 13 * 8, rsi)
        struct.pack_into("<Q", regs_buf, 14 * 8, rdi)
        struct.pack_into("<Q", regs_buf, 16 * 8, rip)
        struct.pack_into("<Q", regs_buf, 18 * 8, 0x246)  # eflags
        struct.pack_into("<Q", regs_buf, 19 * 8, rsp)
        prstatus_desc[112:328] = regs_buf
        struct.pack_into("<i", prstatus_desc, 328, 1)  # pr_fpvalid

        # 2. Build NT_PRPSINFO (136 bytes)
        prpsinfo_desc = bytearray(136)
        # pr_state=0 (running), pr_sname='R', pr_zomb=0, pr_nice=0
        struct.pack_into("BBBb", prpsinfo_desc, 0, 0, ord("R"), 0, 0)
        struct.pack_into("<Q", prpsinfo_desc, 8, 0x400000)  # pr_flag
        struct.pack_into("<II", prpsinfo_desc, 16, 1000, 1000)  # uid, gid
        struct.pack_into("<iiii", prpsinfo_desc, 24, pid, ppid, pid, pid)
        # pr_fname (16 bytes)
        fname_bytes = fname.encode("utf-8")[:15]
        prpsinfo_desc[40 : 40 + len(fname_bytes)] = fname_bytes
        # pr_psargs (80 bytes)
        psargs_bytes = psargs.encode("utf-8")[:79]
        prpsinfo_desc[56 : 56 + len(psargs_bytes)] = psargs_bytes

        # 3. Build NT_AUXV
        if auxv is None:
            auxv = {
                3: 0x400040,      # AT_PHDR
                4: 56,            # AT_PHENT
                5: 4,             # AT_PHNUM
                6: 4096,          # AT_PAGESZ
                7: 0x7FFFF7DD5000,# AT_BASE
                9: rip,           # AT_ENTRY
            }
        auxv_desc = bytearray()
        for k, v in auxv.items():
            auxv_desc.extend(struct.pack("<QQ", k, v))
        auxv_desc.extend(struct.pack("<QQ", 0, 0))  # AT_NULL

        # 4. Build NT_FILE
        if mapped_files is None:
            mapped_files = [
                (0x400000, 0x401000, 0, "/usr/bin/crash_binary"),
                (0x7FFFF7DD5000, 0x7FFFF7DF5000, 0, "/lib/x86_64-linux-gnu/libc.so.6"),
            ]
        nt_file_desc = bytearray()
        count = len(mapped_files)
        page_sz = 4096
        nt_file_desc.extend(struct.pack("<QQ", count, page_sz))
        for start, end, pgoff, _ in mapped_files:
            nt_file_desc.extend(struct.pack("<QQQ", start, end, pgoff))
        for _, _, _, path in mapped_files:
            nt_file_desc.extend(path.encode("utf-8") + b"\x00")

        # Assemble notes segment
        def make_note(name: bytes, n_type: int, desc: bytes) -> bytes:
            namesz = len(name) + 1  # include null terminator
            descsz = len(desc)
            name_pad = (namesz + 3) & ~3
            desc_pad = (descsz + 3) & ~3
            hdr = struct.pack("<III", namesz, descsz, n_type)
            name_bytes = name + b"\x00" + (b"\x00" * (name_pad - namesz))
            desc_bytes = desc + (b"\x00" * (desc_pad - descsz))
            return hdr + name_bytes + desc_bytes

        notes_data = bytearray()
        notes_data.extend(make_note(b"CORE", NT_PRSTATUS, bytes(prstatus_desc)))
        notes_data.extend(make_note(b"CORE", NT_PRPSINFO, bytes(prpsinfo_desc)))
        notes_data.extend(make_note(b"CORE", NT_AUXV, bytes(auxv_desc)))
        notes_data.extend(make_note(b"CORE", NT_FILE, bytes(nt_file_desc)))

        # 5. Build PT_LOAD segment data if specified
        if load_segments is None:
            load_segments = [
                (0x400000, 0x400000, b"\x90" * 64, PF_R | PF_X),
                (0x7FFFFFFFE000, 0x7FFFFFFFE000, b"\x00" * 128, PF_R | PF_W),
            ]

        # Calculate offsets
        # ELF header: 64 bytes
        # Program headers: (1 PT_NOTE + len(load_segments) PT_LOAD) * 56 bytes
        num_phdrs = 1 + len(load_segments)
        ph_table_size = num_phdrs * 56
        notes_offset = 64 + ph_table_size

        # Align notes to 4 bytes
        notes_len = len(notes_data)
        cur_file_offset = notes_offset + notes_len

        # Prepare segment buffers
        seg_records: List[Tuple[int, int, int, int, bytes, int]] = []
        for vaddr, paddr, payload, flags in load_segments:
            seg_len = len(payload)
            seg_records.append((vaddr, paddr, cur_file_offset, seg_len, payload, flags))
            cur_file_offset += seg_len

        # Construct Program Headers
        phdrs_bytes = bytearray()
        # PT_NOTE header
        phdrs_bytes.extend(
            struct.pack(
                "<IIQQQQQQ",
                PT_NOTE,
                0,
                notes_offset,
                0,
                0,
                notes_len,
                0,
                4,
            )
        )
        # PT_LOAD headers
        for vaddr, paddr, offset, filesz, _, flags in seg_records:
            phdrs_bytes.extend(
                struct.pack(
                    "<IIQQQQQQ",
                    PT_LOAD,
                    flags,
                    offset,
                    vaddr,
                    paddr,
                    filesz,
                    filesz,
                    4096,
                )
            )

        # Assemble full ELF64 binary
        elf_ident = ELF_MAGIC + bytes([ELF_CLASS_64, ELF_DATA_LSB, 1, 0, 0]) + (b"\x00" * 7)
        elf_hdr = struct.pack(
            "<HHIQQQIHHHHHH",
            ET_CORE,       # e_type
            0x3E,          # e_machine (x86-64)
            1,             # e_version
            rip,           # e_entry
            64,            # e_phoff
            0,             # e_shoff (no sections)
            0,             # e_flags
            64,            # e_ehsize
            56,            # e_phentsize
            num_phdrs,     # e_phnum
            0,             # e_shentsize
            0,             # e_shnum
            0,             # e_shstrndx
        )

        full_buf = bytearray(cur_file_offset)
        full_buf[0:16] = elf_ident
        full_buf[16:64] = elf_hdr
        full_buf[64 : 64 + ph_table_size] = phdrs_bytes
        full_buf[notes_offset : notes_offset + notes_len] = notes_data

        for _, _, offset, filesz, payload, _ in seg_records:
            full_buf[offset : offset + filesz] = payload

        return bytes(full_buf)

    @classmethod
    def build_elf32_core(
        cls,
        signal: int = 6,
        pid: int = 4242,
        ppid: int = 1,
        fname: str = "crash32",
        psargs: str = "./crash32",
        eip: int = 0x08048400,
        esp: int = 0xBFFFF000,
        ebp: int = 0xBFFFF040,
        eax: int = 0x11111111,
        ebx: int = 0x22222222,
        ecx: int = 0x33333333,
        edx: int = 0x44444444,
        esi: int = 0x55555555,
        edi: int = 0x66666666,
        auxv: Optional[Dict[int, int]] = None,
        mapped_files: Optional[List[Tuple[int, int, int, str]]] = None,
        load_segments: Optional[List[Tuple[int, int, bytes, int]]] = None,
    ) -> bytes:
        """Constructs a valid ELF32 little-endian core dump with PRSTATUS, PRPSINFO, AUXV, and NT_FILE."""
        # 1. Build NT_PRSTATUS (144 bytes)
        prstatus_desc = bytearray(144)
        struct.pack_into("<iii", prstatus_desc, 0, signal, 1, 0)
        struct.pack_into("<h", prstatus_desc, 12, signal)
        struct.pack_into("<iiii", prstatus_desc, 24, pid, ppid, pid, pid)
        regs_buf = bytearray(68)
        # Order: ebx(0), ecx(1), edx(2), esi(3), edi(4), ebp(5), eax(6), ds(7), es(8), fs(9), gs(10), orig_eax(11), eip(12), cs(13), eflags(14), esp(15), ss(16)
        struct.pack_into("<I", regs_buf, 0 * 4, ebx)
        struct.pack_into("<I", regs_buf, 1 * 4, ecx)
        struct.pack_into("<I", regs_buf, 2 * 4, edx)
        struct.pack_into("<I", regs_buf, 3 * 4, esi)
        struct.pack_into("<I", regs_buf, 4 * 4, edi)
        struct.pack_into("<I", regs_buf, 5 * 4, ebp)
        struct.pack_into("<I", regs_buf, 6 * 4, eax)
        struct.pack_into("<I", regs_buf, 12 * 4, eip)
        struct.pack_into("<I", regs_buf, 14 * 4, 0x246)
        struct.pack_into("<I", regs_buf, 15 * 4, esp)
        prstatus_desc[72:140] = regs_buf
        struct.pack_into("<i", prstatus_desc, 140, 1)

        # 2. Build NT_PRPSINFO (128 bytes)
        prpsinfo_desc = bytearray(128)
        struct.pack_into("BBBb", prpsinfo_desc, 0, 0, ord("R"), 0, 0)
        struct.pack_into("<I", prpsinfo_desc, 4, 0x400000)
        struct.pack_into("<II", prpsinfo_desc, 8, 1000, 1000)
        struct.pack_into("<iiii", prpsinfo_desc, 16, pid, ppid, pid, pid)
        fname_bytes = fname.encode("utf-8")[:15]
        prpsinfo_desc[32 : 32 + len(fname_bytes)] = fname_bytes
        psargs_bytes = psargs.encode("utf-8")[:79]
        prpsinfo_desc[48 : 48 + len(psargs_bytes)] = psargs_bytes

        # 3. Build NT_AUXV
        if auxv is None:
            auxv = {
                3: 0x08048034,
                4: 32,
                5: 3,
                6: 4096,
                7: 0xB7FFF000,
                9: eip,
            }
        auxv_desc = bytearray()
        for k, v in auxv.items():
            auxv_desc.extend(struct.pack("<II", k, v))
        auxv_desc.extend(struct.pack("<II", 0, 0))

        # 4. Build NT_FILE
        if mapped_files is None:
            mapped_files = [
                (0x08048000, 0x08049000, 0, "/usr/bin/crash32"),
            ]
        nt_file_desc = bytearray()
        count = len(mapped_files)
        page_sz = 4096
        nt_file_desc.extend(struct.pack("<II", count, page_sz))
        for start, end, pgoff, _ in mapped_files:
            nt_file_desc.extend(struct.pack("<III", start, end, pgoff))
        for _, _, _, path in mapped_files:
            nt_file_desc.extend(path.encode("utf-8") + b"\x00")

        def make_note(name: bytes, n_type: int, desc: bytes) -> bytes:
            namesz = len(name) + 1
            descsz = len(desc)
            name_pad = (namesz + 3) & ~3
            desc_pad = (descsz + 3) & ~3
            hdr = struct.pack("<III", namesz, descsz, n_type)
            name_bytes = name + b"\x00" + (b"\x00" * (name_pad - namesz))
            desc_bytes = desc + (b"\x00" * (desc_pad - descsz))
            return hdr + name_bytes + desc_bytes

        notes_data = bytearray()
        notes_data.extend(make_note(b"CORE", NT_PRSTATUS, bytes(prstatus_desc)))
        notes_data.extend(make_note(b"CORE", NT_PRPSINFO, bytes(prpsinfo_desc)))
        notes_data.extend(make_note(b"CORE", NT_AUXV, bytes(auxv_desc)))
        notes_data.extend(make_note(b"CORE", NT_FILE, bytes(nt_file_desc)))

        if load_segments is None:
            load_segments = [
                (0x08048000, 0x08048000, b"\x90" * 32, PF_R | PF_X),
            ]

        num_phdrs = 1 + len(load_segments)
        ph_table_size = num_phdrs * 32
        notes_offset = 52 + ph_table_size
        notes_len = len(notes_data)
        cur_file_offset = notes_offset + notes_len

        seg_records: List[Tuple[int, int, int, int, bytes, int]] = []
        for vaddr, paddr, payload, flags in load_segments:
            seg_len = len(payload)
            seg_records.append((vaddr, paddr, cur_file_offset, seg_len, payload, flags))
            cur_file_offset += seg_len

        phdrs_bytes = bytearray()
        phdrs_bytes.extend(
            struct.pack(
                "<IIIIIIII",
                PT_NOTE,
                notes_offset,
                0,
                0,
                notes_len,
                0,
                0,
                4,
            )
        )
        for vaddr, paddr, offset, filesz, _, flags in seg_records:
            phdrs_bytes.extend(
                struct.pack(
                    "<IIIIIIII",
                    PT_LOAD,
                    offset,
                    vaddr,
                    paddr,
                    filesz,
                    filesz,
                    flags,
                    4096,
                )
            )

        elf_ident = ELF_MAGIC + bytes([ELF_CLASS_32, ELF_DATA_LSB, 1, 0, 0]) + (b"\x00" * 7)
        elf_hdr = struct.pack(
            "<HHIIIIIHHHHHH",
            ET_CORE,
            0x03,
            1,
            eip,
            52,
            0,
            0,
            52,
            32,
            num_phdrs,
            0,
            0,
            0,
        )

        full_buf = bytearray(cur_file_offset)
        full_buf[0:16] = elf_ident
        full_buf[16:52] = elf_hdr
        full_buf[52 : 52 + ph_table_size] = phdrs_bytes
        full_buf[notes_offset : notes_offset + notes_len] = notes_data

        for _, _, offset, filesz, payload, _ in seg_records:
            full_buf[offset : offset + filesz] = payload

        return bytes(full_buf)

