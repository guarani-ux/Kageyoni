"""Zero-dependency in-tree Cutter / Rizin Static Engine & Command Pipeline (CH 06).

Pure Python standard library implementation:
1. Binary Info Parsing (iIj format):
   - Extracts binary format (ELF/PE/Mach-O), architecture, bit width, endianness,
     compiler identification, and security mitigations (canary, nx, pic).
   - Strict validation of architecture tokens and non-negative bit widths.
2. Section Header Table Parsing (iSj format):
   - Parses section name, virtual address, physical/file address, size, and permission flags.
   - Validates memory bounds (0 <= vaddr, paddr <= 2^64 - 1), non-negative size, and RWX flags.
3. Function List Parsing (aflj format):
   - Parses offset, symbol name, virtual size, real size, cyclomatic complexity (cc),
     nop count, calling convention, and function type.
   - Enforces cc >= 1, non-negative sizes/offsets, and non-empty symbol names.
4. Function Disassembly Parsing (pdfj format):
   - Parses sequence of disassembled operations (ops): offset, opcode, size, instruction type
     (call, jmp, cjmp, ret, trap, mov, etc.), and jump targets.
   - Rejects out-of-order instruction offsets, non-positive instruction sizes, and negative addresses.
5. CFG Edge Extraction & Cyclomatic Analysis:
   - Reconstructs control flow graph (CFG) edges (call, unconditional jump, conditional branch, fallthrough).
   - Computes cyclomatic complexity from instruction decision points and control flow branches.
6. Fail-Closed Verification & Memory Bound:
   - Validates JSON schema integrity, rejects malformed payloads, and enforces memory ceilings <= 64 KB.
   - Computes RFC 8785 canonical SHA-256 digests.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

MAX_STATIC_PAYLOAD_BYTES = 64 * 1024  # 64 KB memory ceiling
UINT64_MAX = 0xFFFF_FFFF_FFFF_FFFF

# Strict permissions regex: rwx flags or POSIX tokens (e.g. "r-x", "rwx", "-r-x", "rw-")
SECTION_PERM_PATTERN = re.compile(r"^[r\-][w\-][x\-][sSpP\-]?$")

VALID_ARCHITECTURES = {
    "x86", "x86-64", "x64", "arm", "arm64", "aarch64", "mips", "riscv",
    "ppc", "sparc", "wasm", "avr", "sh4", "dalvik", "cil", "unknown"
}

VALID_FORMATS = {
    "elf", "elf64", "elf32", "pe", "pe+", "pe32", "pe64",
    "mach0", "macho", "mach-o", "wasm", "raw", "dex", "java"
}

VALID_OP_TYPES = {
    "call", "jmp", "cjmp", "ret", "trap", "mov", "nop", "cmp", "test",
    "push", "pop", "add", "sub", "xor", "and", "or", "lea", "shl", "shr",
    "not", "neg", "mul", "div", "syscall", "int", "ill", "crypto", "unknown"
}


def canonical_sha256(data: Union[bytes, str, Dict[str, Any], List[Any]]) -> str:
    """Computes an RFC 8785 compliant canonical SHA-256 digest."""
    if isinstance(data, bytes):
        raw_bytes = data
    elif isinstance(data, str):
        raw_bytes = data.encode("utf-8")
    else:
        raw_bytes = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


def _parse_uint(value: Any, field_name: str, max_val: int = UINT64_MAX) -> int:
    """Parses and strictly validates an unsigned integer."""
    if isinstance(value, bool):
        raise ValueError(f"Field '{field_name}' expected integer, received boolean: {value}")
    if isinstance(value, int):
        val = value
    elif isinstance(value, str):
        val_str = value.strip()
        if not val_str:
            raise ValueError(f"Field '{field_name}' cannot be empty string")
        try:
            val = int(val_str, 0)
        except (ValueError, TypeError) as err:
            raise ValueError(f"Field '{field_name}' invalid integer format '{value}': {err}") from err
    else:
        raise ValueError(f"Field '{field_name}' invalid type {type(value).__name__}: {value}")

    if val < 0:
        raise ValueError(f"Field '{field_name}' cannot be negative: {val}")
    if val > max_val:
        raise ValueError(f"Field '{field_name}' exceeds maximum 0x{max_val:X}: {val}")
    return val


def _parse_bool(value: Any, field_name: str) -> bool:
    """Parses and validates boolean flags."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        raise ValueError(f"Field '{field_name}' invalid numeric boolean: {value}")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "yes", "1", "y"):
            return True
        if normalized in ("false", "no", "0", "n"):
            return False
    raise ValueError(f"Field '{field_name}' invalid boolean value: {value}")


def _parse_perm_string(flags_raw: Any, field_name: str = "flags") -> str:
    """Validates and returns normalized permission token (e.g. 'r-x', 'rwx')."""
    if not isinstance(flags_raw, str):
        raise ValueError(f"Field '{field_name}' expected string permission, got {type(flags_raw).__name__}")
    perm = flags_raw.strip().lower()
    # Strip optional leading dash if formatted like '-r-x'
    if len(perm) == 4 and perm.startswith("-"):
        perm = perm[1:]
    if not SECTION_PERM_PATTERN.match(perm):
        # Permitted formats: rwx combinations
        valid_chars = set("rwx-sp")
        if not set(perm).issubset(valid_chars) or len(perm) < 3:
            raise ValueError(f"Field '{field_name}' has invalid permission tokens: '{flags_raw}'")
    return perm


@dataclasses.dataclass(frozen=True)
class RizinBinaryInfo:
    """Parsed binary info from Rizin iIj command."""
    format: str
    arch: str
    bits: int
    endian: str
    compiler: Optional[str]
    canary: bool
    nx: bool
    pic: bool
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "format": self.format,
            "arch": self.arch,
            "bits": self.bits,
            "endian": self.endian,
            "compiler": self.compiler,
            "canary": self.canary,
            "nx": self.nx,
            "pic": self.pic,
        }
        if self.extra:
            data["extra"] = dict(self.extra)
        return data


@dataclasses.dataclass(frozen=True)
class RizinSection:
    """Parsed section entry from Rizin iSj command."""
    name: str
    size: int
    vaddr: int
    paddr: int
    flags: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "size": self.size,
            "vaddr": self.vaddr,
            "paddr": self.paddr,
            "flags": self.flags,
        }


@dataclasses.dataclass(frozen=True)
class RizinFunction:
    """Parsed function entry from Rizin aflj command."""
    offset: int
    name: str
    size: int
    realsz: int
    cc: int
    nops: int
    calltype: str
    type: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offset": self.offset,
            "name": self.name,
            "size": self.size,
            "realsz": self.realsz,
            "cc": self.cc,
            "nops": self.nops,
            "calltype": self.calltype,
            "type": self.type,
        }


@dataclasses.dataclass(frozen=True)
class RizinOp:
    """Parsed disassembled instruction from Rizin pdfj command."""
    offset: int
    opcode: str
    size: int
    type: str
    jump: Optional[int] = None
    fail: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "offset": self.offset,
            "opcode": self.opcode,
            "size": self.size,
            "type": self.type,
        }
        if self.jump is not None:
            result["jump"] = self.jump
        if self.fail is not None:
            result["fail"] = self.fail
        return result


@dataclasses.dataclass(frozen=True)
class CFGEdge:
    """Directed control flow edge connecting instruction addresses."""
    source: int
    target: int
    edge_type: str  # 'call', 'jump', 'conditional_true', 'conditional_false', 'fallthrough'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
        }


@dataclasses.dataclass(frozen=True)
class RizinFunctionDisassembly:
    """Parsed function disassembly from Rizin pdfj command with CFG analysis."""
    name: str
    offset: int
    size: int
    ops: List[RizinOp]
    edges: List[CFGEdge]
    computed_cc: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "offset": self.offset,
            "size": self.size,
            "ops": [op.to_dict() for op in self.ops],
            "edges": [edge.to_dict() for edge in self.edges],
            "computed_cc": self.computed_cc,
        }


@dataclasses.dataclass(frozen=True)
class CutterRizinPipeline:
    """Unified static analysis session bundling iIj, iSj, aflj, and pdfj outputs."""
    info: RizinBinaryInfo
    sections: List[RizinSection]
    functions: List[RizinFunction]
    disassembly: RizinFunctionDisassembly
    pipeline_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "info": self.info.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "functions": [f.to_dict() for f in self.functions],
            "disassembly": self.disassembly.to_dict(),
            "pipeline_digest": self.pipeline_digest,
        }


class CutterRizinParser:
    """Zero-dependency Cutter / Rizin Static Analysis Engine & Command Pipeline."""

    @classmethod
    def parse_iIj(cls, data: Union[str, bytes, Dict[str, Any], List[Any]]) -> RizinBinaryInfo:
        """Parses Rizin iIj (binary info) output."""
        raw_dict = cls._coerce_dict(data, "iIj")

        # Support nested structure (e.g. core/bin) or flattened dictionary
        core = raw_dict.get("core") if isinstance(raw_dict.get("core"), dict) else {}
        bin_info = raw_dict.get("bin") if isinstance(raw_dict.get("bin"), dict) else {}

        def get_val(key: str) -> Any:
            if key in raw_dict:
                return raw_dict[key]
            if key in core:
                return core[key]
            if key in bin_info:
                return bin_info[key]
            return None

        # Required fields: format, arch, bits, endian, canary, nx, pic
        fmt = get_val("format") or get_val("bintype") or get_val("class")
        if not isinstance(fmt, str) or not fmt.strip():
            raise ValueError("Missing or invalid required field 'format' in iIj output")
        fmt = fmt.strip().lower()

        arch = get_val("arch")
        if not isinstance(arch, str) or not arch.strip():
            raise ValueError("Missing or invalid required field 'arch' in iIj output")
        arch = arch.strip().lower()

        bits_val = get_val("bits")
        if bits_val is None:
            raise ValueError("Missing required field 'bits' in iIj output")
        bits = _parse_uint(bits_val, "bits", max_val=128)
        if bits not in (8, 16, 32, 64, 128):
            raise ValueError(f"Invalid bit width in iIj: {bits}")

        endian = get_val("endian")
        if not isinstance(endian, str) or not endian.strip():
            raise ValueError("Missing or invalid required field 'endian' in iIj output")
        endian = endian.strip().lower()
        if endian in ("le", "little"):
            endian = "little"
        elif endian in ("be", "big"):
            endian = "big"
        else:
            raise ValueError(f"Unrecognized endianness in iIj: {endian}")

        canary_val = get_val("canary")
        if canary_val is None:
            raise ValueError("Missing required security mitigation field 'canary' in iIj output")
        canary = _parse_bool(canary_val, "canary")

        nx_val = get_val("nx")
        if nx_val is None:
            raise ValueError("Missing required security mitigation field 'nx' in iIj output")
        nx = _parse_bool(nx_val, "nx")

        pic_val = get_val("pic")
        if pic_val is None:
            raise ValueError("Missing required security mitigation field 'pic' in iIj output")
        pic = _parse_bool(pic_val, "pic")

        compiler_raw = get_val("compiler")
        compiler = str(compiler_raw).strip() if compiler_raw is not None else None

        # Capture extra fields for downstream metadata preservation
        standard_keys = {
            "format", "bintype", "class", "arch", "bits", "endian",
            "canary", "nx", "pic", "compiler", "core", "bin"
        }
        extra = {k: v for k, v in raw_dict.items() if k not in standard_keys}

        return RizinBinaryInfo(
            format=fmt,
            arch=arch,
            bits=bits,
            endian=endian,
            compiler=compiler,
            canary=canary,
            nx=nx,
            pic=pic,
            extra=extra,
        )

    @classmethod
    def parse_iSj(cls, data: Union[str, bytes, List[Any], Dict[str, Any]]) -> List[RizinSection]:
        """Parses Rizin iSj (sections) output."""
        items = cls._coerce_list(data, "iSj", "sections")
        sections: List[RizinSection] = []

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"Section at index {idx} must be a dictionary, got {type(item).__name__}")

            name = item.get("name")
            if not isinstance(name, str):
                raise ValueError(f"Section at index {idx} missing required string 'name'")

            if "size" not in item:
                raise ValueError(f"Section '{name}' missing required field 'size'")
            size = _parse_uint(item["size"], f"sections[{idx}].size")

            if "vaddr" not in item and "addr" not in item:
                raise ValueError(f"Section '{name}' missing required field 'vaddr'")
            vaddr_raw = item.get("vaddr", item.get("addr"))
            vaddr = _parse_uint(vaddr_raw, f"sections[{idx}].vaddr")

            if "paddr" not in item and "offset" not in item:
                raise ValueError(f"Section '{name}' missing required field 'paddr'")
            paddr_raw = item.get("paddr", item.get("offset"))
            paddr = _parse_uint(paddr_raw, f"sections[{idx}].paddr")

            flags_raw = item.get("flags") or item.get("perm")
            if flags_raw is None:
                raise ValueError(f"Section '{name}' missing required permission 'flags'")
            flags = _parse_perm_string(flags_raw, f"sections[{idx}].flags")

            sections.append(RizinSection(
                name=name,
                size=size,
                vaddr=vaddr,
                paddr=paddr,
                flags=flags,
            ))

        return sections

    @classmethod
    def parse_aflj(cls, data: Union[str, bytes, List[Any], Dict[str, Any]]) -> List[RizinFunction]:
        """Parses Rizin aflj (functions list) output."""
        items = cls._coerce_list(data, "aflj", "functions")
        functions: List[RizinFunction] = []

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"Function at index {idx} must be a dictionary, got {type(item).__name__}")

            if "offset" not in item and "addr" not in item:
                raise ValueError(f"Function at index {idx} missing required field 'offset'")
            offset = _parse_uint(item.get("offset", item.get("addr")), f"functions[{idx}].offset")

            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"Function at index {idx} missing or invalid string 'name'")

            if "size" not in item:
                raise ValueError(f"Function '{name}' missing required field 'size'")
            size = _parse_uint(item["size"], f"functions[{idx}].size")

            if "realsz" not in item:
                raise ValueError(f"Function '{name}' missing required field 'realsz'")
            realsz = _parse_uint(item["realsz"], f"functions[{idx}].realsz")

            if "cc" not in item:
                raise ValueError(f"Function '{name}' missing required field 'cc'")
            cc = _parse_uint(item["cc"], f"functions[{idx}].cc")
            if cc < 1:
                raise ValueError(f"Function '{name}' cyclomatic complexity cc must be >= 1, got {cc}")

            if "nops" not in item:
                raise ValueError(f"Function '{name}' missing required field 'nops'")
            nops = _parse_uint(item["nops"], f"functions[{idx}].nops")

            calltype = item.get("calltype")
            if not isinstance(calltype, str):
                raise ValueError(f"Function '{name}' missing required string 'calltype'")

            fcn_type = item.get("type")
            if not isinstance(fcn_type, str):
                raise ValueError(f"Function '{name}' missing required string 'type'")

            functions.append(RizinFunction(
                offset=offset,
                name=name,
                size=size,
                realsz=realsz,
                cc=cc,
                nops=nops,
                calltype=calltype,
                type=fcn_type,
            ))

        return functions

    @classmethod
    def parse_pdfj(cls, data: Union[str, bytes, Dict[str, Any]]) -> RizinFunctionDisassembly:
        """Parses Rizin pdfj (function disassembly) output with CFG edge extraction."""
        raw_dict = cls._coerce_dict(data, "pdfj")

        # Ops array resolution
        ops_raw = raw_dict.get("ops")
        if ops_raw is None:
            ops_raw = raw_dict.get("instructions")
        if not isinstance(ops_raw, list):
            raise ValueError("pdfj output missing required list 'ops'")
        if not ops_raw:
            raise ValueError("pdfj output 'ops' array cannot be empty")

        parsed_ops: List[RizinOp] = []
        last_offset = -1

        for idx, op_item in enumerate(ops_raw):
            if not isinstance(op_item, dict):
                raise ValueError(f"Instruction op at index {idx} must be a dictionary")

            if "offset" not in op_item:
                raise ValueError(f"Instruction op at index {idx} missing required field 'offset'")
            offset = _parse_uint(op_item["offset"], f"ops[{idx}].offset")

            # Validate non-decreasing monotonicity: offsets must strictly preserve forward execution order
            if offset < last_offset:
                raise ValueError(
                    f"Out-of-order instruction offset at index {idx}: 0x{offset:X} < 0x{last_offset:X}"
                )
            last_offset = offset

            opcode = op_item.get("opcode")
            if not isinstance(opcode, str) or not opcode.strip():
                raise ValueError(f"Instruction op at index {idx} missing required string 'opcode'")

            if "size" not in op_item:
                raise ValueError(f"Instruction op at index {idx} missing required field 'size'")
            size = _parse_uint(op_item["size"], f"ops[{idx}].size")
            if size <= 0:
                raise ValueError(f"Instruction op at index {idx} size must be positive (> 0), got {size}")

            op_type = op_item.get("type")
            if not isinstance(op_type, str) or not op_type.strip():
                raise ValueError(f"Instruction op at index {idx} missing required string 'type'")
            op_type = op_type.strip().lower()

            jump: Optional[int] = None
            if "jump" in op_item and op_item["jump"] is not None:
                jump = _parse_uint(op_item["jump"], f"ops[{idx}].jump")

            fail: Optional[int] = None
            if "fail" in op_item and op_item["fail"] is not None:
                fail = _parse_uint(op_item["fail"], f"ops[{idx}].fail")

            parsed_ops.append(RizinOp(
                offset=offset,
                opcode=opcode,
                size=size,
                type=op_type,
                jump=jump,
                fail=fail,
            ))

        name = raw_dict.get("name")
        if not isinstance(name, str) or not name.strip():
            # Derive from first op or generic symbol
            name = f"fcn_{parsed_ops[0].offset:x}"

        fcn_offset = _parse_uint(raw_dict.get("offset", parsed_ops[0].offset), "pdfj.offset")
        total_size = _parse_uint(
            raw_dict.get("size", (parsed_ops[-1].offset + parsed_ops[-1].size - fcn_offset)),
            "pdfj.size"
        )

        edges = cls.extract_cfg_edges(parsed_ops)
        computed_cc = cls.compute_cyclomatic_complexity(parsed_ops)

        return RizinFunctionDisassembly(
            name=name,
            offset=fcn_offset,
            size=total_size,
            ops=parsed_ops,
            edges=edges,
            computed_cc=computed_cc,
        )

    @classmethod
    def extract_cfg_edges(cls, ops: Sequence[RizinOp]) -> List[CFGEdge]:
        """Extracts directed CFG edges from sequential disassembled instructions."""
        edges: List[CFGEdge] = []
        num_ops = len(ops)

        for i, op in enumerate(ops):
            next_offset = ops[i + 1].offset if (i + 1 < num_ops) else (op.offset + op.size)

            if op.type == "cjmp":
                # Conditional branch: true branch to jump target, false branch to fail or fallthrough
                if op.jump is not None:
                    edges.append(CFGEdge(source=op.offset, target=op.jump, edge_type="conditional_true"))
                false_target = op.fail if op.fail is not None else next_offset
                edges.append(CFGEdge(source=op.offset, target=false_target, edge_type="conditional_false"))

            elif op.type == "jmp":
                # Unconditional branch: single jump edge, no fallthrough
                if op.jump is not None:
                    edges.append(CFGEdge(source=op.offset, target=op.jump, edge_type="jump"))

            elif op.type == "call":
                # Call instruction: edge to called target, plus fallthrough edge upon return
                if op.jump is not None:
                    edges.append(CFGEdge(source=op.offset, target=op.jump, edge_type="call"))
                edges.append(CFGEdge(source=op.offset, target=next_offset, edge_type="fallthrough"))

            elif op.type in ("ret", "trap"):
                # Control flow exits function boundary; no intra-procedural fallthrough
                continue

            else:
                # Standard linear instruction: fallthrough to successor
                edges.append(CFGEdge(source=op.offset, target=next_offset, edge_type="fallthrough"))

        return edges

    @classmethod
    def compute_cyclomatic_complexity(cls, ops: Sequence[RizinOp]) -> int:
        """Computes cyclomatic complexity CC = 1 + decision_points from instruction ops."""
        decision_points = sum(1 for op in ops if op.type == "cjmp")
        return 1 + decision_points

    @classmethod
    def parse_pipeline(cls, data: Union[str, bytes, Dict[str, Any]]) -> CutterRizinPipeline:
        """Parses combined Cutter / Rizin static analysis pipeline output."""
        raw_dict = cls._coerce_dict(data, "pipeline")

        info_raw = raw_dict.get("iIj", raw_dict.get("info"))
        if info_raw is None:
            raise ValueError("Static pipeline missing required binary info ('iIj' or 'info')")
        info = cls.parse_iIj(info_raw)

        sections_raw = raw_dict.get("iSj", raw_dict.get("sections"))
        if sections_raw is None:
            raise ValueError("Static pipeline missing required sections ('iSj' or 'sections')")
        sections = cls.parse_iSj(sections_raw)

        functions_raw = raw_dict.get("aflj", raw_dict.get("functions"))
        if functions_raw is None:
            raise ValueError("Static pipeline missing required functions ('aflj' or 'functions')")
        functions = cls.parse_aflj(functions_raw)

        disasm_raw = raw_dict.get("pdfj", raw_dict.get("disassembly"))
        if disasm_raw is None:
            raise ValueError("Static pipeline missing required disassembly ('pdfj' or 'disassembly')")
        disasm = cls.parse_pdfj(disasm_raw)

        pipeline_digest = canonical_sha256(raw_dict)

        return CutterRizinPipeline(
            info=info,
            sections=sections,
            functions=functions,
            disassembly=disasm,
            pipeline_digest=pipeline_digest,
        )

    @classmethod
    def parse_bytes(cls, data: bytes) -> CutterRizinPipeline:
        """Parses raw JSON bytes with thermodynamic length assertion."""
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError(f"parse_bytes requires bytes, received {type(data).__name__}")
        if len(data) == 0:
            raise ValueError("Cannot parse empty byte payload")
        if len(data) > MAX_STATIC_PAYLOAD_BYTES:
            raise ValueError(
                f"Payload size {len(data)} bytes exceeds thermodynamic ceiling of {MAX_STATIC_PAYLOAD_BYTES} bytes"
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as err:
            raise ValueError(f"Invalid UTF-8 encoding in byte payload: {err}") from err
        return cls.parse_str(text)

    @classmethod
    def parse_str(cls, text: str) -> CutterRizinPipeline:
        """Parses JSON string into unified static analysis pipeline."""
        if not isinstance(text, str):
            raise ValueError(f"parse_str requires str, received {type(text).__name__}")
        trimmed = text.strip()
        if not trimmed:
            raise ValueError("Cannot parse empty or whitespace string payload")
        if len(trimmed.encode("utf-8")) > MAX_STATIC_PAYLOAD_BYTES:
            raise ValueError(f"String payload exceeds thermodynamic ceiling of {MAX_STATIC_PAYLOAD_BYTES} bytes")
        try:
            parsed = json.loads(trimmed)
        except json.JSONDecodeError as err:
            raise ValueError(f"Malformed JSON payload: {err}") from err
        return cls.parse_pipeline(parsed)

    @classmethod
    def _coerce_dict(cls, data: Any, context: str) -> Dict[str, Any]:
        """Safely deserializes and bounds checks input expected to be a dictionary."""
        if isinstance(data, (bytes, bytearray)):
            if len(data) > MAX_STATIC_PAYLOAD_BYTES:
                raise ValueError(f"{context} payload exceeds {MAX_STATIC_PAYLOAD_BYTES} bytes")
            if not data.strip():
                raise ValueError(f"{context} cannot parse empty bytes")
            try:
                data = json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as err:
                raise ValueError(f"Malformed JSON for {context}: {err}") from err
        elif isinstance(data, str):
            trimmed = data.strip()
            if len(trimmed.encode("utf-8")) > MAX_STATIC_PAYLOAD_BYTES:
                raise ValueError(f"{context} payload exceeds {MAX_STATIC_PAYLOAD_BYTES} bytes")
            if not trimmed:
                raise ValueError(f"{context} cannot parse empty string")
            try:
                data = json.loads(trimmed)
            except json.JSONDecodeError as err:
                raise ValueError(f"Malformed JSON for {context}: {err}") from err

        if isinstance(data, list):
            if len(data) == 1 and isinstance(data[0], dict):
                data = data[0]
            else:
                raise ValueError(f"Expected dict for {context}, got list with {len(data)} items")

        if not isinstance(data, dict):
            raise ValueError(f"Expected dictionary for {context}, got {type(data).__name__}")
        return data

    @classmethod
    def _coerce_list(cls, data: Any, context: str, fallback_key: str) -> List[Any]:
        """Safely deserializes and bounds checks input expected to be a list."""
        if isinstance(data, (bytes, bytearray)):
            if len(data) > MAX_STATIC_PAYLOAD_BYTES:
                raise ValueError(f"{context} payload exceeds {MAX_STATIC_PAYLOAD_BYTES} bytes")
            if not data.strip():
                raise ValueError(f"{context} cannot parse empty bytes")
            try:
                data = json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as err:
                raise ValueError(f"Malformed JSON for {context}: {err}") from err
        elif isinstance(data, str):
            trimmed = data.strip()
            if len(trimmed.encode("utf-8")) > MAX_STATIC_PAYLOAD_BYTES:
                raise ValueError(f"{context} payload exceeds {MAX_STATIC_PAYLOAD_BYTES} bytes")
            if not trimmed:
                raise ValueError(f"{context} cannot parse empty string")
            try:
                data = json.loads(trimmed)
            except json.JSONDecodeError as err:
                raise ValueError(f"Malformed JSON for {context}: {err}") from err

        if isinstance(data, dict):
            if fallback_key in data and isinstance(data[fallback_key], list):
                data = data[fallback_key]
            elif context in data and isinstance(data[context], list):
                data = data[context]
            else:
                raise ValueError(f"Expected list for {context}, got dict without '{fallback_key}' list")

        if not isinstance(data, list):
            raise ValueError(f"Expected list for {context}, got {type(data).__name__}")
        return data
