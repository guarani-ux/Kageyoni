"""Zero-dependency in-tree Hopper Disassembler Bridge & Document Representation Reader (CH 05).

Pure Python standard library implementation:
1. Hopper Document & Script Export Reader:
   - Parses segments, sections, basic blocks, procedures, and local labels.
   - Reconstructs control flow graph (CFG) basic blocks, jump branches, and successors.
2. Pseudocode Decompiler AST Blocks & Comments:
   - Parses AST blocks (function, block, if, while, for, switch, case, return, call, assign, expr).
   - Extracts structured comments (inline, pre, post, decompiler) and user annotations.
3. Type Definitions & Structure Member Layout:
   - Extracts struct, union, enum, and typedef definitions.
   - Verifies struct member layout, non-overlapping members (for structs), alignment, and size.
4. Strict Fail-Closed Verification:
   - Empty input rejection.
   - Malformed / corrupted JSON rejection.
   - Negative procedure lengths, negative offsets, and memory bounds (0 <= addr <= 2^64 - 1).
   - Monotonic / out-of-order address validation within basic blocks and procedures.
   - Memory ceiling bounded <= 64 KB with RFC 8785 canonical SHA-256 digests.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

MAX_HOPPER_PAYLOAD_BYTES = 64 * 1024  # 64 KB memory ceiling
UINT64_MAX = 0xFFFF_FFFF_FFFF_FFFF

VALID_FORMATS = {"mach-o", "macho", "elf", "elf64", "elf32", "pe", "pe32", "pe64", "raw"}
VALID_ARCHITECTURES = {
    "x86", "x86_64", "x64", "arm", "arm64", "aarch64", "armv7", "armv7s",
    "mips", "riscv", "ppc", "ppc64", "unknown"
}
VALID_PERMISSIONS = re.compile(r"^[r\-][w\-][x\-]$")
VALID_COMMENT_TYPES = {"inline", "pre", "post", "decompiler", "user", "auto"}
VALID_TYPE_CATEGORIES = {"struct", "union", "enum", "typedef"}
VALID_AST_NODE_TYPES = {
    "function", "block", "if", "while", "for", "switch", "case",
    "return", "call", "assignment", "expr", "comment", "break", "continue"
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


def _parse_int(value: Any, field_name: str) -> int:
    """Parses and validates a signed integer."""
    if isinstance(value, bool):
        raise ValueError(f"Field '{field_name}' expected integer, received boolean: {value}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        val_str = value.strip()
        if not val_str:
            raise ValueError(f"Field '{field_name}' cannot be empty string")
        try:
            return int(val_str, 0)
        except (ValueError, TypeError) as err:
            raise ValueError(f"Field '{field_name}' invalid integer format '{value}': {err}") from err
    raise ValueError(f"Field '{field_name}' invalid type {type(value).__name__}: {value}")


def _parse_non_empty_str(value: Any, field_name: str) -> str:
    """Validates that a string field is non-empty and stripped."""
    if not isinstance(value, str):
        raise ValueError(f"Field '{field_name}' expected string, received {type(value).__name__}")
    s = value.strip()
    if not s:
        raise ValueError(f"Field '{field_name}' cannot be empty or blank")
    return s


def _parse_bool(value: Any, field_name: str) -> bool:
    """Parses and validates boolean flags."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    raise ValueError(f"Field '{field_name}' expected boolean, received {type(value).__name__}: {value}")


@dataclasses.dataclass(frozen=True)
class HopperSection:
    """Represents a section inside a Hopper segment."""
    name: str
    start_address: int
    length: int
    flags: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "start_address": self.start_address,
            "hex_start": f"0x{self.start_address:x}",
            "length": self.length,
            "flags": self.flags,
        }


@dataclasses.dataclass(frozen=True)
class HopperSegment:
    """Represents a binary memory segment in Hopper."""
    name: str
    start_address: int
    length: int
    permissions: str
    sections: List[HopperSection] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "start_address": self.start_address,
            "hex_start": f"0x{self.start_address:x}",
            "length": self.length,
            "permissions": self.permissions,
            "sections": [s.to_dict() for s in self.sections],
        }


@dataclasses.dataclass(frozen=True)
class HopperInstruction:
    """Represents a disassembled instruction in Hopper."""
    address: int
    mnemonic: str
    operands: str
    size: int
    opcode_bytes: bytes
    comment: Optional[str] = None
    instruction_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "hex_address": f"0x{self.address:x}",
            "mnemonic": self.mnemonic,
            "operands": self.operands,
            "size": self.size,
            "opcode_hex": self.opcode_bytes.hex(),
            "comment": self.comment,
            "instruction_type": self.instruction_type,
        }


@dataclasses.dataclass(frozen=True)
class HopperBasicBlock:
    """Represents a basic block in a Hopper procedure CFG."""
    start_address: int
    length: int
    instructions: List[HopperInstruction] = dataclasses.field(default_factory=list)
    predecessors: List[int] = dataclasses.field(default_factory=list)
    successors: List[int] = dataclasses.field(default_factory=list)
    block_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_address": self.start_address,
            "hex_start": f"0x{self.start_address:x}",
            "length": self.length,
            "instructions": [inst.to_dict() for inst in self.instructions],
            "predecessors": [f"0x{p:x}" for p in self.predecessors],
            "successors": [f"0x{s:x}" for s in self.successors],
            "block_id": self.block_id,
        }


@dataclasses.dataclass(frozen=True)
class HopperLocalLabel:
    """Represents a local label inside a procedure."""
    address: int
    name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "hex_address": f"0x{self.address:x}",
            "name": self.name,
        }


@dataclasses.dataclass(frozen=True)
class HopperLocalVar:
    """Represents a local variable / frame member in a procedure."""
    name: str
    type_name: str
    stack_offset: int
    size: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type_name": self.type_name,
            "stack_offset": self.stack_offset,
            "size": self.size,
        }


@dataclasses.dataclass(frozen=True)
class HopperProcedure:
    """Represents a procedure/function defined in Hopper."""
    name: str
    entry_address: int
    length: int
    basic_blocks: List[HopperBasicBlock] = dataclasses.field(default_factory=list)
    local_labels: List[HopperLocalLabel] = dataclasses.field(default_factory=list)
    local_vars: List[HopperLocalVar] = dataclasses.field(default_factory=list)
    calling_convention: Optional[str] = None
    return_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entry_address": self.entry_address,
            "hex_entry": f"0x{self.entry_address:x}",
            "length": self.length,
            "basic_blocks": [bb.to_dict() for bb in self.basic_blocks],
            "local_labels": [ll.to_dict() for ll in self.local_labels],
            "local_vars": [lv.to_dict() for lv in self.local_vars],
            "calling_convention": self.calling_convention,
            "return_type": self.return_type,
        }


@dataclasses.dataclass(frozen=True)
class HopperComment:
    """Represents a comment extracted from Hopper."""
    address: int
    text: str
    comment_type: str = "inline"
    is_user_comment: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "hex_address": f"0x{self.address:x}",
            "text": self.text,
            "comment_type": self.comment_type,
            "is_user_comment": self.is_user_comment,
        }


@dataclasses.dataclass(frozen=True)
class HopperASTNode:
    """Represents an AST block or statement in Hopper pseudocode decompilation."""
    node_type: str
    address: Optional[int] = None
    condition: Optional[str] = None
    expression: Optional[str] = None
    body: List["HopperASTNode"] = dataclasses.field(default_factory=list)
    else_body: List["HopperASTNode"] = dataclasses.field(default_factory=list)
    indent_level: int = 0
    line_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "node_type": self.node_type,
            "address": self.address,
            "condition": self.condition,
            "expression": self.expression,
            "indent_level": self.indent_level,
            "line_number": self.line_number,
            "body": [b.to_dict() for b in self.body],
            "else_body": [eb.to_dict() for eb in self.else_body],
        }
        return res


@dataclasses.dataclass(frozen=True)
class HopperPseudocodeAST:
    """Represents complete pseudocode decompilation output for a procedure."""
    procedure_name: str
    entry_address: int
    raw_code: str
    ast_blocks: List[HopperASTNode] = dataclasses.field(default_factory=list)
    comments: List[HopperComment] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "procedure_name": self.procedure_name,
            "entry_address": self.entry_address,
            "hex_entry": f"0x{self.entry_address:x}",
            "raw_code": self.raw_code,
            "ast_blocks": [node.to_dict() for node in self.ast_blocks],
            "comments": [c.to_dict() for c in self.comments],
        }


@dataclasses.dataclass(frozen=True)
class HopperStructMember:
    """Represents a member field in a Hopper struct or union."""
    name: str
    type_name: str
    offset: int
    size: int
    comment: Optional[str] = None
    bitfield_size: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type_name": self.type_name,
            "offset": self.offset,
            "size": self.size,
            "comment": self.comment,
            "bitfield_size": self.bitfield_size,
        }


@dataclasses.dataclass(frozen=True)
class HopperTypeDefinition:
    """Represents a struct, union, enum, or typedef in Hopper."""
    name: str
    category: str
    size: int
    alignment: int
    members: List[HopperStructMember] = dataclasses.field(default_factory=list)
    enum_values: Dict[str, int] = dataclasses.field(default_factory=dict)
    target_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "size": self.size,
            "alignment": self.alignment,
            "members": [m.to_dict() for m in self.members],
            "enum_values": dict(self.enum_values),
            "target_type": self.target_type,
        }


@dataclasses.dataclass(frozen=True)
class HopperDocument:
    """Root representation of an exported Hopper Disassembler document."""
    version: str
    arch: str
    format: str
    image_base: int
    segments: List[HopperSegment]
    procedures: List[HopperProcedure]
    types: List[HopperTypeDefinition]
    pseudocode: List[HopperPseudocodeAST]
    comments: List[HopperComment]
    canonical_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "arch": self.arch,
            "format": self.format,
            "image_base": self.image_base,
            "hex_image_base": f"0x{self.image_base:x}",
            "segments": [s.to_dict() for s in self.segments],
            "procedures": [p.to_dict() for p in self.procedures],
            "types": [t.to_dict() for t in self.types],
            "pseudocode": [pc.to_dict() for pc in self.pseudocode],
            "comments": [c.to_dict() for c in self.comments],
            "canonical_digest": self.canonical_digest,
        }


class HopperParser:
    """Zero-dependency parser for Hopper Disassembler JSON exports."""

    @classmethod
    def parse_bytes(cls, payload: bytes) -> HopperDocument:
        """Parses raw UTF-8 JSON bytes representing a Hopper document."""
        if not isinstance(payload, bytes):
            raise ValueError(f"Expected bytes payload, received {type(payload).__name__}")
        if len(payload) == 0:
            raise ValueError("Empty Hopper input payload")
        if len(payload) > MAX_HOPPER_PAYLOAD_BYTES:
            raise ValueError(
                f"Payload size {len(payload)} bytes exceeds maximum {MAX_HOPPER_PAYLOAD_BYTES} bytes"
            )

        stripped = payload.strip()
        if not stripped:
            raise ValueError("Empty or whitespace-only Hopper input payload")

        try:
            text = stripped.decode("utf-8")
        except UnicodeDecodeError as err:
            raise ValueError(f"Corrupted UTF-8 Hopper payload: {err}") from err

        return cls.parse_str(text)

    @classmethod
    def parse_str(cls, text: str) -> HopperDocument:
        """Parses a JSON string representing a Hopper document."""
        if not isinstance(text, str):
            raise ValueError(f"Expected string input, received {type(text).__name__}")
        s = text.strip()
        if not s:
            raise ValueError("Empty Hopper input string")

        try:
            data = json.loads(s)
        except json.JSONDecodeError as err:
            raise ValueError(f"Malformed Hopper JSON: {err}") from err

        if not isinstance(data, dict):
            raise ValueError(f"Root Hopper JSON must be an object, received {type(data).__name__}")

        return cls.parse_dict(data)

    @classmethod
    def parse_dict(cls, data: Dict[str, Any]) -> HopperDocument:
        """Parses a validated dictionary representing a Hopper document."""
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, received {type(data).__name__}")

        version = _parse_non_empty_str(data.get("version", "hopper_v4"), "version")
        arch = _parse_non_empty_str(data.get("arch", "x86_64"), "arch").lower()
        if arch not in VALID_ARCHITECTURES:
            raise ValueError(f"Unsupported architecture '{arch}'. Valid: {sorted(VALID_ARCHITECTURES)}")

        fmt = _parse_non_empty_str(data.get("format", "mach-o"), "format").lower()
        if fmt not in VALID_FORMATS:
            raise ValueError(f"Unsupported binary format '{fmt}'. Valid: {sorted(VALID_FORMATS)}")

        image_base = _parse_uint(data.get("image_base", 0), "image_base")

        # Parse segments
        raw_segments = data.get("segments", [])
        if not isinstance(raw_segments, list):
            raise ValueError(f"Field 'segments' must be a list, received {type(raw_segments).__name__}")
        segments = [cls.parse_segment(s) for s in raw_segments]

        # Parse procedures
        raw_procedures = data.get("procedures", [])
        if not isinstance(raw_procedures, list):
            raise ValueError(f"Field 'procedures' must be a list, received {type(raw_procedures).__name__}")
        procedures = [cls.parse_procedure(p) for p in raw_procedures]

        # Parse types
        raw_types = data.get("types", [])
        if not isinstance(raw_types, list):
            raise ValueError(f"Field 'types' must be a list, received {type(raw_types).__name__}")
        types = [cls.parse_type_definition(t) for t in raw_types]

        # Parse pseudocode
        raw_pseudocode = data.get("pseudocode", [])
        if isinstance(raw_pseudocode, dict):
            raw_pseudocode = [raw_pseudocode]
        elif not isinstance(raw_pseudocode, list):
            raise ValueError(f"Field 'pseudocode' must be a list or object, received {type(raw_pseudocode).__name__}")
        pseudocode = [cls.parse_pseudocode(pc) for pc in raw_pseudocode]

        # Parse document-level comments
        raw_comments = data.get("comments", [])
        if not isinstance(raw_comments, list):
            raise ValueError(f"Field 'comments' must be a list, received {type(raw_comments).__name__}")
        comments = [cls.parse_comment(c) for c in raw_comments]

        digest = canonical_sha256(data)

        return HopperDocument(
            version=version,
            arch=arch,
            format=fmt,
            image_base=image_base,
            segments=segments,
            procedures=procedures,
            types=types,
            pseudocode=pseudocode,
            comments=comments,
            canonical_digest=digest,
        )

    @classmethod
    def parse_section(cls, data: Dict[str, Any]) -> HopperSection:
        """Parses a Hopper section record."""
        if not isinstance(data, dict):
            raise ValueError(f"Section must be an object, received {type(data).__name__}")

        name = _parse_non_empty_str(data.get("name"), "section.name")
        start_address = _parse_uint(data.get("start_address", data.get("address", 0)), "section.start_address")
        length = _parse_uint(data.get("length", data.get("size", 0)), "section.length")

        if start_address + length > UINT64_MAX:
            raise ValueError(f"Section '{name}' range 0x{start_address:x}+0x{length:x} exceeds 64-bit address space")

        flags = data.get("flags")
        if flags is not None and not isinstance(flags, str):
            raise ValueError(f"Section flags must be string or None, received {type(flags).__name__}")

        return HopperSection(
            name=name,
            start_address=start_address,
            length=length,
            flags=flags,
        )

    @classmethod
    def parse_segment(cls, data: Dict[str, Any]) -> HopperSegment:
        """Parses a Hopper segment record."""
        if not isinstance(data, dict):
            raise ValueError(f"Segment must be an object, received {type(data).__name__}")

        name = _parse_non_empty_str(data.get("name"), "segment.name")
        start_address = _parse_uint(data.get("start_address", data.get("address", 0)), "segment.start_address")
        length = _parse_uint(data.get("length", data.get("size", 0)), "segment.length")

        if start_address + length > UINT64_MAX:
            raise ValueError(f"Segment '{name}' range 0x{start_address:x}+0x{length:x} exceeds 64-bit address space")

        perms = _parse_non_empty_str(data.get("permissions", data.get("flags", "r-x")), "segment.permissions")
        if not VALID_PERMISSIONS.match(perms):
            raise ValueError(f"Invalid segment permission string '{perms}'. Must match rwx pattern (e.g. 'r-x', 'rwx')")

        raw_sections = data.get("sections", [])
        if not isinstance(raw_sections, list):
            raise ValueError(f"Segment sections must be a list, received {type(raw_sections).__name__}")
        sections = [cls.parse_section(s) for s in raw_sections]

        # Verify sections are within segment bounds
        for sec in sections:
            if sec.start_address < start_address or (sec.start_address + sec.length) > (start_address + length):
                raise ValueError(
                    f"Section '{sec.name}' [0x{sec.start_address:x}, 0x{sec.start_address + sec.length:x}] "
                    f"lies outside segment '{name}' [0x{start_address:x}, 0x{start_address + length:x}]"
                )

        return HopperSegment(
            name=name,
            start_address=start_address,
            length=length,
            permissions=perms,
            sections=sections,
        )

    @classmethod
    def parse_instruction(cls, data: Dict[str, Any]) -> HopperInstruction:
        """Parses a disassembled instruction."""
        if not isinstance(data, dict):
            raise ValueError(f"Instruction must be an object, received {type(data).__name__}")

        address = _parse_uint(data.get("address", data.get("offset", 0)), "instruction.address")
        mnemonic = _parse_non_empty_str(data.get("mnemonic", data.get("opcode", "nop")), "instruction.mnemonic")

        operands_raw = data.get("operands", "")
        if isinstance(operands_raw, list):
            operands = ", ".join(str(op) for op in operands_raw)
        elif isinstance(operands_raw, str):
            operands = operands_raw.strip()
        else:
            raise ValueError(f"Instruction operands must be str or list, received {type(operands_raw).__name__}")

        size = _parse_uint(data.get("size", 1), "instruction.size")
        if size == 0:
            raise ValueError(f"Instruction at 0x{address:x} has non-positive size 0")

        bytes_raw = data.get("bytes", data.get("opcode_bytes", data.get("opcode_hex", "")))
        if isinstance(bytes_raw, bytes):
            opcode_bytes = bytes_raw
        elif isinstance(bytes_raw, str):
            clean_hex = re.sub(r"\s+", "", bytes_raw)
            try:
                opcode_bytes = bytes.fromhex(clean_hex) if clean_hex else b""
            except ValueError as err:
                raise ValueError(f"Invalid opcode hex '{bytes_raw}' at 0x{address:x}: {err}") from err
        else:
            raise ValueError(f"Instruction bytes must be hex string or bytes, received {type(bytes_raw).__name__}")

        comment = data.get("comment")
        if comment is not None and not isinstance(comment, str):
            raise ValueError(f"Instruction comment must be string or None, received {type(comment).__name__}")

        inst_type = data.get("type", data.get("instruction_type"))
        if inst_type is not None and not isinstance(inst_type, str):
            raise ValueError(f"Instruction type must be string or None, received {type(inst_type).__name__}")

        return HopperInstruction(
            address=address,
            mnemonic=mnemonic,
            operands=operands,
            size=size,
            opcode_bytes=opcode_bytes,
            comment=comment.strip() if comment else None,
            instruction_type=inst_type.strip() if inst_type else None,
        )

    @classmethod
    def parse_basic_block(
        cls,
        data: Dict[str, Any],
        proc_bounds: Optional[Tuple[int, int]] = None,
    ) -> HopperBasicBlock:
        """Parses a basic block and validates internal instruction order and bounds."""
        if not isinstance(data, dict):
            raise ValueError(f"Basic block must be an object, received {type(data).__name__}")

        start_address = _parse_uint(data.get("start_address", data.get("address", 0)), "basic_block.start_address")
        length = _parse_uint(data.get("length", data.get("size", 0)), "basic_block.length")

        if start_address + length > UINT64_MAX:
            raise ValueError(f"Basic block range 0x{start_address:x}+0x{length:x} exceeds 64-bit address space")

        if proc_bounds is not None:
            proc_start, proc_len = proc_bounds
            if start_address < proc_start or (start_address + length) > (proc_start + proc_len):
                raise ValueError(
                    f"Basic block [0x{start_address:x}, 0x{start_address + length:x}] "
                    f"escapes procedure boundaries [0x{proc_start:x}, 0x{proc_start + proc_len:x}]"
                )

        raw_instructions = data.get("instructions", data.get("ops", []))
        if not isinstance(raw_instructions, list):
            raise ValueError(f"Basic block instructions must be a list, received {type(raw_instructions).__name__}")

        instructions: List[HopperInstruction] = []
        last_addr: Optional[int] = None
        for inst_data in raw_instructions:
            inst = cls.parse_instruction(inst_data)
            if last_addr is not None and inst.address < last_addr:
                raise ValueError(
                    f"Out of order instruction address: 0x{inst.address:x} < preceding 0x{last_addr:x} "
                    f"in basic block starting at 0x{start_address:x}"
                )
            if inst.address < start_address or (length > 0 and inst.address >= start_address + length):
                raise ValueError(
                    f"Instruction at 0x{inst.address:x} outside basic block range "
                    f"[0x{start_address:x}, 0x{start_address + length:x}]"
                )
            last_addr = inst.address
            instructions.append(inst)

        # Parse CFG edges (predecessors / successors)
        raw_preds = data.get("predecessors", [])
        if not isinstance(raw_preds, list):
            raise ValueError(f"Basic block predecessors must be list, received {type(raw_preds).__name__}")
        predecessors = [_parse_uint(p, "basic_block.predecessors") for p in raw_preds]

        raw_succs = data.get("successors", [])
        if not isinstance(raw_succs, list):
            raise ValueError(f"Basic block successors must be list, received {type(raw_succs).__name__}")
        successors = [_parse_uint(s, "basic_block.successors") for s in raw_succs]

        block_id = data.get("block_id", data.get("id"))
        if block_id is not None and not isinstance(block_id, str):
            block_id = str(block_id)

        return HopperBasicBlock(
            start_address=start_address,
            length=length,
            instructions=instructions,
            predecessors=predecessors,
            successors=successors,
            block_id=block_id,
        )

    @classmethod
    def parse_procedure(cls, data: Dict[str, Any]) -> HopperProcedure:
        """Parses a procedure record and enforces monotonic basic blocks and valid length."""
        if not isinstance(data, dict):
            raise ValueError(f"Procedure must be an object, received {type(data).__name__}")

        name = _parse_non_empty_str(data.get("name"), "procedure.name")
        entry_address = _parse_uint(data.get("entry_address", data.get("address", 0)), "procedure.entry_address")

        length_raw = data.get("length", data.get("size"))
        if length_raw is None:
            raise ValueError(f"Procedure '{name}' missing required field 'length' or 'size'")

        length = _parse_int(length_raw, "procedure.length")
        if length <= 0:
            raise ValueError(f"Procedure '{name}' has non-positive or negative length: {length}")

        if entry_address + length > UINT64_MAX:
            raise ValueError(f"Procedure '{name}' range 0x{entry_address:x}+0x{length:x} exceeds 64-bit address space")

        # Parse basic blocks
        raw_bbs = data.get("basic_blocks", data.get("blocks", []))
        if not isinstance(raw_bbs, list):
            raise ValueError(f"Procedure basic_blocks must be list, received {type(raw_bbs).__name__}")

        bbs: List[HopperBasicBlock] = []
        last_bb_start: Optional[int] = None
        for bb_dict in raw_bbs:
            bb = cls.parse_basic_block(bb_dict, proc_bounds=(entry_address, length))
            if last_bb_start is not None and bb.start_address < last_bb_start:
                raise ValueError(
                    f"Out of order basic block address: 0x{bb.start_address:x} < preceding 0x{last_bb_start:x} "
                    f"in procedure '{name}'"
                )
            last_bb_start = bb.start_address
            bbs.append(bb)

        # Parse local labels
        raw_labels = data.get("local_labels", data.get("labels", []))
        local_labels: List[HopperLocalLabel] = []
        if isinstance(raw_labels, dict):
            for k, v in raw_labels.items():
                lbl_addr = _parse_uint(k, "local_label.address")
                lbl_name = _parse_non_empty_str(v, "local_label.name")
                local_labels.append(HopperLocalLabel(address=lbl_addr, name=lbl_name))
        elif isinstance(raw_labels, list):
            for item in raw_labels:
                if not isinstance(item, dict):
                    raise ValueError(f"Local label item must be object, received {type(item).__name__}")
                lbl_addr = _parse_uint(item.get("address", item.get("offset", 0)), "local_label.address")
                lbl_name = _parse_non_empty_str(item.get("name"), "local_label.name")
                local_labels.append(HopperLocalLabel(address=lbl_addr, name=lbl_name))
        else:
            raise ValueError(f"Local labels must be dict or list, received {type(raw_labels).__name__}")

        # Parse local variables
        raw_vars = data.get("local_vars", data.get("variables", []))
        if not isinstance(raw_vars, list):
            raise ValueError(f"Local variables must be list, received {type(raw_vars).__name__}")
        local_vars: List[HopperLocalVar] = []
        for var_item in raw_vars:
            if not isinstance(var_item, dict):
                raise ValueError(f"Local variable item must be object, received {type(var_item).__name__}")
            var_name = _parse_non_empty_str(var_item.get("name"), "local_var.name")
            var_type = _parse_non_empty_str(var_item.get("type", "void*"), "local_var.type")
            stack_offset = _parse_int(var_item.get("stack_offset", var_item.get("offset", 0)), "local_var.stack_offset")
            var_size = _parse_uint(var_item.get("size", 4), "local_var.size")
            local_vars.append(
                HopperLocalVar(
                    name=var_name,
                    type_name=var_type,
                    stack_offset=stack_offset,
                    size=var_size,
                )
            )

        calling_conv = data.get("calling_convention", data.get("calltype"))
        return_type = data.get("return_type")

        return HopperProcedure(
            name=name,
            entry_address=entry_address,
            length=length,
            basic_blocks=bbs,
            local_labels=local_labels,
            local_vars=local_vars,
            calling_convention=calling_conv.strip() if isinstance(calling_conv, str) else None,
            return_type=return_type.strip() if isinstance(return_type, str) else None,
        )

    @classmethod
    def parse_comment(cls, data: Dict[str, Any]) -> HopperComment:
        """Parses a comment object."""
        if not isinstance(data, dict):
            raise ValueError(f"Comment must be an object, received {type(data).__name__}")

        address = _parse_uint(data.get("address", data.get("offset", 0)), "comment.address")
        text = _parse_non_empty_str(data.get("text", data.get("comment", "")), "comment.text")

        c_type = _parse_non_empty_str(data.get("comment_type", data.get("type", "inline")), "comment.type").lower()
        if c_type not in VALID_COMMENT_TYPES:
            raise ValueError(f"Unsupported comment type '{c_type}'. Valid: {sorted(VALID_COMMENT_TYPES)}")

        is_user = _parse_bool(data.get("is_user_comment", data.get("user", False)), "comment.is_user_comment")

        return HopperComment(
            address=address,
            text=text,
            comment_type=c_type,
            is_user_comment=is_user,
        )

    @classmethod
    def parse_ast_node(cls, data: Dict[str, Any]) -> HopperASTNode:
        """Recursively parses an AST node in decompiled pseudocode."""
        if not isinstance(data, dict):
            raise ValueError(f"AST node must be an object, received {type(data).__name__}")

        node_type = _parse_non_empty_str(data.get("node_type", data.get("type", "expr")), "ast_node.type").lower()
        if node_type not in VALID_AST_NODE_TYPES:
            raise ValueError(f"Unsupported AST node type '{node_type}'. Valid: {sorted(VALID_AST_NODE_TYPES)}")

        address: Optional[int] = None
        if "address" in data and data["address"] is not None:
            address = _parse_uint(data["address"], "ast_node.address")

        condition: Optional[str] = None
        if "condition" in data and data["condition"] is not None:
            condition = str(data["condition"]).strip()

        expression: Optional[str] = None
        if "expression" in data and data["expression"] is not None:
            expression = str(data["expression"]).strip()
        elif "expr" in data and data["expr"] is not None:
            expression = str(data["expr"]).strip()

        indent_level = _parse_uint(data.get("indent_level", data.get("indent", 0)), "ast_node.indent_level", max_val=128)

        line_number: Optional[int] = None
        if "line_number" in data and data["line_number"] is not None:
            line_number = _parse_uint(data["line_number"], "ast_node.line_number")

        raw_body = data.get("body", [])
        if not isinstance(raw_body, list):
            raise ValueError(f"AST node body must be list, received {type(raw_body).__name__}")
        body = [cls.parse_ast_node(child) for child in raw_body]

        raw_else = data.get("else_body", [])
        if not isinstance(raw_else, list):
            raise ValueError(f"AST node else_body must be list, received {type(raw_else).__name__}")
        else_body = [cls.parse_ast_node(child) for child in raw_else]

        return HopperASTNode(
            node_type=node_type,
            address=address,
            condition=condition,
            expression=expression,
            body=body,
            else_body=else_body,
            indent_level=indent_level,
            line_number=line_number,
        )

    @classmethod
    def parse_pseudocode(cls, data: Dict[str, Any]) -> HopperPseudocodeAST:
        """Parses decompiled pseudocode and associated AST blocks."""
        if not isinstance(data, dict):
            raise ValueError(f"Pseudocode must be an object, received {type(data).__name__}")

        proc_name = _parse_non_empty_str(data.get("procedure_name", data.get("name", "unknown")), "pseudocode.procedure_name")
        entry_addr = _parse_uint(data.get("entry_address", data.get("address", 0)), "pseudocode.entry_address")

        raw_code = data.get("raw_code", data.get("code", ""))
        if not isinstance(raw_code, str):
            raise ValueError(f"Pseudocode raw_code must be string, received {type(raw_code).__name__}")

        raw_blocks = data.get("ast_blocks", data.get("ast", []))
        if not isinstance(raw_blocks, list):
            raise ValueError(f"Pseudocode ast_blocks must be list, received {type(raw_blocks).__name__}")
        ast_blocks = [cls.parse_ast_node(b) for b in raw_blocks]

        raw_comments = data.get("comments", [])
        if not isinstance(raw_comments, list):
            raise ValueError(f"Pseudocode comments must be list, received {type(raw_comments).__name__}")
        comments = [cls.parse_comment(c) for c in raw_comments]

        return HopperPseudocodeAST(
            procedure_name=proc_name,
            entry_address=entry_addr,
            raw_code=raw_code,
            ast_blocks=ast_blocks,
            comments=comments,
        )

    @classmethod
    def parse_struct_member(cls, data: Dict[str, Any]) -> HopperStructMember:
        """Parses a struct or union member field."""
        if not isinstance(data, dict):
            raise ValueError(f"Struct member must be an object, received {type(data).__name__}")

        name = _parse_non_empty_str(data.get("name"), "struct_member.name")
        type_name = _parse_non_empty_str(data.get("type", data.get("type_name", "uint32_t")), "struct_member.type")
        offset = _parse_uint(data.get("offset", 0), "struct_member.offset")
        size = _parse_uint(data.get("size", 1), "struct_member.size")
        if size == 0:
            raise ValueError(f"Struct member '{name}' cannot have size 0")

        comment = data.get("comment")
        bitfield_size: Optional[int] = None
        if "bitfield_size" in data and data["bitfield_size"] is not None:
            bitfield_size = _parse_uint(data["bitfield_size"], "struct_member.bitfield_size", max_val=64)

        return HopperStructMember(
            name=name,
            type_name=type_name,
            offset=offset,
            size=size,
            comment=comment.strip() if isinstance(comment, str) else None,
            bitfield_size=bitfield_size,
        )

    @classmethod
    def parse_type_definition(cls, data: Dict[str, Any]) -> HopperTypeDefinition:
        """Parses a type definition (struct, union, enum, typedef) and validates member layout."""
        if not isinstance(data, dict):
            raise ValueError(f"Type definition must be an object, received {type(data).__name__}")

        name = _parse_non_empty_str(data.get("name"), "type_definition.name")
        category = _parse_non_empty_str(data.get("category", "struct"), "type_definition.category").lower()
        if category not in VALID_TYPE_CATEGORIES:
            raise ValueError(f"Unsupported type category '{category}'. Valid: {sorted(VALID_TYPE_CATEGORIES)}")

        size = _parse_uint(data.get("size", 0), "type_definition.size")
        alignment = _parse_uint(data.get("alignment", 1), "type_definition.alignment", max_val=4096)
        if alignment == 0 or (alignment & (alignment - 1)) != 0:
            raise ValueError(f"Type '{name}' alignment {alignment} must be a non-zero power of 2 (1, 2, 4, 8, etc.)")

        raw_members = data.get("members", [])
        if not isinstance(raw_members, list):
            raise ValueError(f"Type members must be list, received {type(raw_members).__name__}")
        members = [cls.parse_struct_member(m) for m in raw_members]

        # Layout validation for structs
        if category == "struct" and members:
            # Sort members by offset for layout checking
            sorted_members = sorted(members, key=lambda m: m.offset)
            for i in range(len(sorted_members) - 1):
                cur = sorted_members[i]
                nxt = sorted_members[i + 1]
                # If neither is a bitfield with shared offset, check overlap
                if cur.bitfield_size is None and nxt.bitfield_size is None:
                    if cur.offset + cur.size > nxt.offset:
                        raise ValueError(
                            f"Overlapping struct members in '{name}': '{cur.name}' "
                            f"[0x{cur.offset:x}, 0x{cur.offset + cur.size:x}] overlaps with "
                            f"'{nxt.name}' at 0x{nxt.offset:x}"
                        )

            # Check if members exceed declared struct size
            if size > 0:
                max_reach = max(m.offset + m.size for m in members)
                if max_reach > size:
                    raise ValueError(
                        f"Struct '{name}' members reach offset 0x{max_reach:x}, "
                        f"exceeding declared struct size 0x{size:x}"
                    )

        # Parse enum values
        raw_enum = data.get("enum_values", {})
        enum_values: Dict[str, int] = {}
        if isinstance(raw_enum, dict):
            for k, v in raw_enum.items():
                k_name = _parse_non_empty_str(k, "enum_values.key")
                v_int = _parse_int(v, f"enum_values.{k}")
                enum_values[k_name] = v_int
        elif isinstance(raw_enum, list):
            for idx, item in enumerate(raw_enum):
                if isinstance(item, dict):
                    k_name = _parse_non_empty_str(item.get("name"), "enum_values.name")
                    v_int = _parse_int(item.get("value", idx), f"enum_values.{k_name}")
                    enum_values[k_name] = v_int
                elif isinstance(item, str):
                    enum_values[item.strip()] = idx
                else:
                    raise ValueError(f"Invalid enum value item: {item}")

        target_type: Optional[str] = None
        if "target_type" in data and data["target_type"] is not None:
            target_type = _parse_non_empty_str(data["target_type"], "type_definition.target_type")

        return HopperTypeDefinition(
            name=name,
            category=category,
            size=size,
            alignment=alignment,
            members=members,
            enum_values=enum_values,
            target_type=target_type,
        )
