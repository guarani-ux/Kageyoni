"""Zero-dependency in-tree Ghidra Headless Decompiler Bridge & AST Parser (CH 04).

Pure Python standard library implementation:
1. Ghidra Headless Decompilation Output & XML/JSON Export Reader:
   - Parses Ghidra Function ASTs: function name, entrypoint, return type, parameters, local variables.
   - Parses Ghidra high-level P-code and C decompiler tokens:
     * Control flow nodes (IF, GOTO, RETURN, CALL, BRANCH, CBRANCH).
     * Memory references & varnodes (unique, register, ram, const, stack).
   - Extracts Ghidra Data Types & Program Symbols (functions, labels, comments).
2. Fail-Closed Verification & Memory Bound:
   - Empty input validation.
   - Rejects corrupted XML/JSON or out-of-bounds varnode offsets.
   - Detects and rejects cyclic data type definitions.
   - Enforces memory ceilings <= 64 KB and computes RFC 8785 canonical SHA-256 digests.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

MAX_PAYLOAD_BYTES = 64 * 1024  # 64 KB memory ceiling
UINT64_MAX = 0xFFFF_FFFF_FFFF_FFFF
UINT32_MAX = 0xFFFF_FFFF

VALID_SPACES = {"ram", "register", "unique", "const", "stack", "join"}
CONTROL_FLOW_OPCODES = {"IF", "BRANCH", "CBRANCH", "BRANCHIND", "CALL", "CALLIND", "RETURN", "GOTO"}

VALID_SYMBOL_TYPES = {"function", "label", "parameter", "local", "global", "imported"}
VALID_COMMENT_TYPES = {"plate", "pre", "eol", "post", "repeatable"}
VALID_DATA_TYPE_KINDS = {"builtin", "struct", "typedef", "pointer", "enum", "union", "array"}


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


@dataclasses.dataclass(frozen=True)
class Varnode:
    """Ghidra decompiler varnode representing a value storage location."""
    space: str
    offset: int
    size: int
    name: Optional[str] = None

    def __post_init__(self):
        if not self.space or not isinstance(self.space, str):
            raise ValueError("Varnode space must be a non-empty string")
        norm_space = self.space.strip().lower()
        if norm_space not in VALID_SPACES and not re.match(r"^[a-zA-Z0-9_]+$", norm_space):
            raise ValueError(f"Invalid varnode address space: '{self.space}'")
        if self.offset < 0 or self.offset > UINT64_MAX:
            raise ValueError(f"Out-of-bounds varnode offset: {self.offset}")
        if self.size <= 0 or self.size > 65536:
            raise ValueError(f"Invalid varnode size: {self.size}")

    def is_ram(self) -> bool:
        return self.space.lower() == "ram"

    def is_register(self) -> bool:
        return self.space.lower() == "register"

    def is_unique(self) -> bool:
        return self.space.lower() == "unique"

    def is_const(self) -> bool:
        return self.space.lower() == "const"

    def is_stack(self) -> bool:
        return self.space.lower() == "stack"

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "space": self.space,
            "offset": self.offset,
            "size": self.size,
        }
        if self.name is not None:
            res["name"] = self.name
        return res


@dataclasses.dataclass(frozen=True)
class PcodeOp:
    """Ghidra high-level P-code instruction node."""
    opcode: str
    seq: int
    inputs: List[Varnode] = dataclasses.field(default_factory=list)
    output: Optional[Varnode] = None
    target: Optional[int] = None
    is_control_flow: bool = False

    def __post_init__(self):
        if not self.opcode or not isinstance(self.opcode, str):
            raise ValueError("Pcode opcode must be a non-empty string")
        if self.seq < 0:
            raise ValueError(f"Pcode sequence number cannot be negative: {self.seq}")
        norm_op = self.opcode.strip().upper()
        cf = norm_op in CONTROL_FLOW_OPCODES
        object.__setattr__(self, "opcode", norm_op)
        object.__setattr__(self, "is_control_flow", cf)

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "opcode": self.opcode,
            "seq": self.seq,
            "inputs": [inp.to_dict() for inp in self.inputs],
            "is_control_flow": self.is_control_flow,
        }
        if self.output is not None:
            res["output"] = self.output.to_dict()
        if self.target is not None:
            res["target"] = self.target
        return res


@dataclasses.dataclass(frozen=True)
class CFGEdge:
    """Directed control flow edge connecting instruction sequence addresses."""
    source: int
    target: int
    edge_type: str  # 'call', 'branch', 'goto', 'conditional_true', 'conditional_false', 'return', 'fallthrough'

    def __post_init__(self):
        if self.source < 0 or self.source > UINT64_MAX:
            raise ValueError(f"Invalid CFGEdge source address: {self.source}")
        if self.target < 0 or self.target > UINT64_MAX:
            raise ValueError(f"Invalid CFGEdge target address: {self.target}")
        valid_edge_types = {"call", "branch", "goto", "conditional_true", "conditional_false", "return", "fallthrough"}
        if self.edge_type.lower() not in valid_edge_types:
            raise ValueError(f"Invalid CFGEdge type: '{self.edge_type}'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type,
        }


@dataclasses.dataclass(frozen=True)
class Parameter:
    """Function formal parameter extracted from AST / decompilation."""
    name: str
    type_name: str
    storage: str
    size: int
    offset: Optional[int] = None
    register: Optional[str] = None

    def __post_init__(self):
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Parameter name must be a non-empty string")
        if not self.type_name or not isinstance(self.type_name, str):
            raise ValueError("Parameter type_name must be a non-empty string")
        if self.size <= 0:
            raise ValueError(f"Parameter size must be positive: {self.size}")
        if self.offset is not None and (self.offset < 0 or self.offset > UINT64_MAX):
            raise ValueError(f"Invalid parameter offset: {self.offset}")

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "name": self.name,
            "type_name": self.type_name,
            "storage": self.storage,
            "size": self.size,
        }
        if self.offset is not None:
            res["offset"] = self.offset
        if self.register is not None:
            res["register"] = self.register
        return res


@dataclasses.dataclass(frozen=True)
class LocalVariable:
    """Function local variable extracted from decompiler scope."""
    name: str
    type_name: str
    storage: str
    size: int
    offset: Optional[int] = None
    register: Optional[str] = None

    def __post_init__(self):
        if not self.name or not isinstance(self.name, str):
            raise ValueError("LocalVariable name must be a non-empty string")
        if not self.type_name or not isinstance(self.type_name, str):
            raise ValueError("LocalVariable type_name must be a non-empty string")
        if self.size <= 0:
            raise ValueError(f"LocalVariable size must be positive: {self.size}")
        if self.offset is not None and (self.offset < 0 or self.offset > UINT64_MAX):
            raise ValueError(f"Invalid local variable offset: {self.offset}")

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "name": self.name,
            "type_name": self.type_name,
            "storage": self.storage,
            "size": self.size,
        }
        if self.offset is not None:
            res["offset"] = self.offset
        if self.register is not None:
            res["register"] = self.register
        return res


@dataclasses.dataclass(frozen=True)
class ASTNode:
    """Generic AST Node representing decompiled control flow and expressions."""
    node_type: str
    label: Optional[str] = None
    attributes: Dict[str, Any] = dataclasses.field(default_factory=dict)
    children: List[ASTNode] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        if not self.node_type or not isinstance(self.node_type, str):
            raise ValueError("ASTNode node_type must be a non-empty string")

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {"node_type": self.node_type}
        if self.label is not None:
            res["label"] = self.label
        if self.attributes:
            res["attributes"] = dict(self.attributes)
        if self.children:
            res["children"] = [c.to_dict() for c in self.children]
        return res


@dataclasses.dataclass(frozen=True)
class DecompilerToken:
    """Individual syntactic token emitted by Ghidra C decompiler."""
    token_type: str  # 'keyword', 'type', 'identifier', 'operator', 'literal', 'comment', 'syntax'
    text: str
    line: int
    column: int

    def __post_init__(self):
        if not self.token_type or not isinstance(self.token_type, str):
            raise ValueError("DecompilerToken token_type must be a non-empty string")
        if self.line <= 0:
            raise ValueError(f"DecompilerToken line number must be positive: {self.line}")
        if self.column <= 0:
            raise ValueError(f"DecompilerToken column number must be positive: {self.column}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_type": self.token_type,
            "text": self.text,
            "line": self.line,
            "column": self.column,
        }


@dataclasses.dataclass(frozen=True)
class GhidraDataTypeField:
    """Field definition within a Ghidra composite data type (struct or union)."""
    name: str
    type_name: str
    offset: int
    size: int

    def __post_init__(self):
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Data type field name must be a non-empty string")
        if self.offset < 0 or self.offset > UINT64_MAX:
            raise ValueError(f"Invalid field offset: {self.offset}")
        if self.size < 0:
            raise ValueError(f"Invalid field size: {self.size}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type_name": self.type_name,
            "offset": self.offset,
            "size": self.size,
        }


@dataclasses.dataclass(frozen=True)
class GhidraDataType:
    """Data type definition from Ghidra Data Type Manager."""
    name: str
    size: int
    kind: str  # 'builtin', 'struct', 'typedef', 'pointer', 'enum', 'union', 'array'
    fields: List[GhidraDataTypeField] = dataclasses.field(default_factory=list)
    base_type: Optional[str] = None
    enum_values: Dict[str, int] = dataclasses.field(default_factory=dict)

    def __post_init__(self):
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Data type name must be a non-empty string")
        if self.size < 0:
            raise ValueError(f"Data type size cannot be negative: {self.size}")
        if self.kind.lower() not in VALID_DATA_TYPE_KINDS:
            raise ValueError(f"Invalid data type kind: '{self.kind}'")

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "name": self.name,
            "size": self.size,
            "kind": self.kind,
        }
        if self.fields:
            res["fields"] = [f.to_dict() for f in self.fields]
        if self.base_type is not None:
            res["base_type"] = self.base_type
        if self.enum_values:
            res["enum_values"] = dict(self.enum_values)
        return res


@dataclasses.dataclass(frozen=True)
class GhidraSymbol:
    """Program symbol entry (function, label, variable)."""
    name: str
    address: int
    symbol_type: str  # 'function', 'label', 'parameter', 'local', 'global', 'imported'
    namespace: Optional[str] = None

    def __post_init__(self):
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Symbol name must be a non-empty string")
        if self.address < 0 or self.address > UINT64_MAX:
            raise ValueError(f"Invalid symbol address: {self.address}")
        if self.symbol_type.lower() not in VALID_SYMBOL_TYPES:
            raise ValueError(f"Invalid symbol type: '{self.symbol_type}'")

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "name": self.name,
            "address": self.address,
            "symbol_type": self.symbol_type,
        }
        if self.namespace is not None:
            res["namespace"] = self.namespace
        return res


@dataclasses.dataclass(frozen=True)
class GhidraComment:
    """Annotated comment extracted from Ghidra disassembly or decompiler."""
    address: int
    comment_type: str  # 'plate', 'pre', 'eol', 'post', 'repeatable'
    text: str

    def __post_init__(self):
        if self.address < 0 or self.address > UINT64_MAX:
            raise ValueError(f"Invalid comment address: {self.address}")
        if self.comment_type.lower() not in VALID_COMMENT_TYPES:
            raise ValueError(f"Invalid comment type: '{self.comment_type}'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "comment_type": self.comment_type,
            "text": self.text,
        }


@dataclasses.dataclass(frozen=True)
class GhidraFunction:
    """Complete decompiled function representation with AST, P-code, and CFG."""
    name: str
    entrypoint: int
    return_type: str
    size: int
    parameters: List[Parameter] = dataclasses.field(default_factory=list)
    local_variables: List[LocalVariable] = dataclasses.field(default_factory=list)
    pcode: List[PcodeOp] = dataclasses.field(default_factory=list)
    ast: Optional[ASTNode] = None
    c_code: Optional[str] = None
    c_tokens: List[DecompilerToken] = dataclasses.field(default_factory=list)
    cfg_edges: List[CFGEdge] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Function name must be a non-empty string")
        if self.entrypoint < 0 or self.entrypoint > UINT64_MAX:
            raise ValueError(f"Invalid function entrypoint: {self.entrypoint}")
        if self.size < 0 or self.size > UINT64_MAX:
            raise ValueError(f"Invalid function size: {self.size}")
        if not self.return_type or not isinstance(self.return_type, str):
            raise ValueError("Function return_type must be a non-empty string")

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "name": self.name,
            "entrypoint": self.entrypoint,
            "return_type": self.return_type,
            "size": self.size,
            "parameters": [p.to_dict() for p in self.parameters],
            "local_variables": [lv.to_dict() for lv in self.local_variables],
            "pcode": [op.to_dict() for op in self.pcode],
            "cfg_edges": [e.to_dict() for e in self.cfg_edges],
        }
        if self.ast is not None:
            res["ast"] = self.ast.to_dict()
        if self.c_code is not None:
            res["c_code"] = self.c_code
        if self.c_tokens:
            res["c_tokens"] = [t.to_dict() for t in self.c_tokens]
        return res


@dataclasses.dataclass(frozen=True)
class GhidraProgram:
    """Unified Ghidra Program dump containing symbols, datatypes, comments, and functions."""
    name: str
    arch: str
    data_types: Dict[str, GhidraDataType] = dataclasses.field(default_factory=dict)
    symbols: List[GhidraSymbol] = dataclasses.field(default_factory=list)
    comments: List[GhidraComment] = dataclasses.field(default_factory=list)
    functions: Dict[str, GhidraFunction] = dataclasses.field(default_factory=dict)
    program_digest: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "arch": self.arch,
            "data_types": {k: v.to_dict() for k, v in self.data_types.items()},
            "symbols": [s.to_dict() for s in self.symbols],
            "comments": [c.to_dict() for c in self.comments],
            "functions": {k: v.to_dict() for k, v in self.functions.items()},
            "program_digest": self.program_digest,
        }


# Control Flow Graph Builder
def extract_cfg_edges(pcode: Sequence[PcodeOp]) -> List[CFGEdge]:
    """Reconstructs CFG edges from sequential high-level P-code operations."""
    edges: List[CFGEdge] = []
    n = len(pcode)
    for i, op in enumerate(pcode):
        src = op.seq
        next_seq = pcode[i + 1].seq if i + 1 < n else None

        if op.opcode in ("BRANCH", "GOTO"):
            if op.target is not None:
                edges.append(CFGEdge(source=src, target=op.target, edge_type="branch"))
        elif op.opcode in ("IF", "CBRANCH"):
            if op.target is not None:
                edges.append(CFGEdge(source=src, target=op.target, edge_type="conditional_true"))
            if next_seq is not None:
                edges.append(CFGEdge(source=src, target=next_seq, edge_type="conditional_false"))
        elif op.opcode in ("CALL", "CALLIND"):
            if op.target is not None:
                edges.append(CFGEdge(source=src, target=op.target, edge_type="call"))
            if next_seq is not None:
                edges.append(CFGEdge(source=src, target=next_seq, edge_type="fallthrough"))
        elif op.opcode == "RETURN":
            target_addr = op.target if op.target is not None else 0
            edges.append(CFGEdge(source=src, target=target_addr, edge_type="return"))
        else:
            if next_seq is not None:
                edges.append(CFGEdge(source=src, target=next_seq, edge_type="fallthrough"))
    return edges


# Cycle Detector for Ghidra Data Types
def check_cyclic_data_types(data_types: Dict[str, GhidraDataType]) -> None:
    """Verifies no cyclic value definitions or cyclic typedef chains exist.
    
    A cycle occurs if:
    1. A typedef refers directly or indirectly to itself (e.g. A -> B -> A).
    2. A struct/union embeds another struct/union by value in a circular dependency.
    Pointer indirection (e.g. Struct A has field of type Struct A*) does NOT create a cyclic value cycle.
    """
    graph: Dict[str, List[str]] = {}
    for name, dt in data_types.items():
        refs: List[str] = []
        if dt.kind == "typedef" and dt.base_type:
            target = dt.base_type.strip()
            if target in data_types:
                refs.append(target)
        elif dt.kind in ("struct", "union"):
            for f in dt.fields:
                t = f.type_name.strip()
                if t.endswith("*") or "*" in t or t.startswith("pointer_to_"):
                    continue
                base_t = re.sub(r"\[\d*\]", "", t).strip()
                if base_t in data_types:
                    refs.append(base_t)
        graph[name] = refs

    visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited

    def dfs(node: str, path: List[str]) -> None:
        visited[node] = 1
        path.append(node)
        for neighbor in graph.get(node, []):
            if visited.get(neighbor, 0) == 0:
                dfs(neighbor, path)
            elif visited.get(neighbor) == 1:
                cycle_start_idx = path.index(neighbor)
                cycle_path = path[cycle_start_idx:] + [neighbor]
                raise ValueError(f"Cyclic data type definition detected: {' -> '.join(cycle_path)}")
        path.pop()
        visited[node] = 2

    for node in graph:
        if visited.get(node, 0) == 0:
            dfs(node, [])


# Lexical C Tokenizer
C_KEYWORDS = {
    "if", "else", "while", "for", "do", "return", "goto", "switch", "case",
    "default", "break", "continue", "struct", "union", "typedef", "enum", "sizeof"
}

C_TYPES = {
    "void", "char", "short", "int", "long", "float", "double", "signed", "unsigned",
    "bool", "size_t", "uint8_t", "uint16_t", "uint32_t", "uint64_t",
    "int8_t", "int16_t", "int32_t", "int64_t", "undefined", "undefined1",
    "undefined2", "undefined4", "undefined8", "code", "pointer"
}

TOKEN_SPECIFICATION = [
    ("COMMENT_BLOCK", r"/\*[\s\S]*?\*/"),
    ("COMMENT_LINE", r"//[^\n]*"),
    ("STRING", r'"[^"\\]*(?:\\.[^"\\]*)*"'),
    ("CHAR", r"'[^'\\]*(?:\\.[^'\\]*)*'"),
    ("HEX_LITERAL", r"0[xX][0-9a-fA-F]+"),
    ("DEC_LITERAL", r"\b\d+\b"),
    ("ARROW", r"->"),
    ("EQ_OP", r"==|!=|<=|>="),
    ("LOGICAL", r"&&|\|\|"),
    ("SHIFT", r"<<|>>"),
    ("ASSIGN_OP", r"\+=|-=|\*=|/=|%=|&=|\|=|\^="),
    ("IDENTIFIER", r"[a-zA-Z_][a-zA-Z0-9_]*"),
    ("OPERATOR", r"[+\-*/%=!&|^~<>?:*]"),
    ("SYNTAX", r"[{}()\[\],;]"),
    ("NEWLINE", r"\n"),
    ("SKIP", r"[ \t\r]+"),
    ("MISMATCH", r"."),
]

TOKEN_REGEX = re.compile("|".join(f"(?P<{pair[0]}>{pair[1]})" for pair in TOKEN_SPECIFICATION))


def tokenize_c_code(c_source: str) -> List[DecompilerToken]:
    """Tokenizes Ghidra decompiled C source code into typed decompiler tokens."""
    tokens: List[DecompilerToken] = []
    line_num = 1
    line_start = 0

    for mo in TOKEN_REGEX.finditer(c_source):
        kind = mo.lastgroup
        value = mo.group()
        column = mo.start() - line_start + 1

        if kind == "NEWLINE":
            line_start = mo.end()
            line_num += 1
            continue
        elif kind == "SKIP":
            continue
        elif kind == "MISMATCH":
            raise ValueError(f"Malformed C token at line {line_num}, column {column}: {value!r}")
        elif kind in ("COMMENT_BLOCK", "COMMENT_LINE"):
            tokens.append(DecompilerToken(token_type="comment", text=value, line=line_num, column=column))
            if kind == "COMMENT_BLOCK":
                line_num += value.count("\n")
        elif kind in ("STRING", "CHAR", "HEX_LITERAL", "DEC_LITERAL"):
            tokens.append(DecompilerToken(token_type="literal", text=value, line=line_num, column=column))
        elif kind == "IDENTIFIER":
            if value in C_KEYWORDS:
                token_type = "keyword"
            elif value in C_TYPES:
                token_type = "type"
            else:
                token_type = "identifier"
            tokens.append(DecompilerToken(token_type=token_type, text=value, line=line_num, column=column))
        elif kind in ("ARROW", "EQ_OP", "LOGICAL", "SHIFT", "ASSIGN_OP", "OPERATOR"):
            tokens.append(DecompilerToken(token_type="operator", text=value, line=line_num, column=column))
        elif kind == "SYNTAX":
            tokens.append(DecompilerToken(token_type="syntax", text=value, line=line_num, column=column))

    return tokens


class GhidraParser:
    """Zero-dependency Ghidra Headless Decompiler Bridge & Parser."""

    @classmethod
    def parse_varnode(cls, data: Union[Dict[str, Any], ET.Element]) -> Varnode:
        """Parses and validates a single Varnode from dict or XML element."""
        if isinstance(data, dict):
            space = data.get("space")
            if not space or not isinstance(space, str):
                raise ValueError("Missing or invalid 'space' in varnode")
            offset_val = data.get("offset")
            if offset_val is None:
                raise ValueError("Missing 'offset' in varnode")
            offset = _parse_uint(offset_val, "offset", max_val=UINT64_MAX)
            size_val = data.get("size")
            if size_val is None:
                raise ValueError("Missing 'size' in varnode")
            size = _parse_uint(size_val, "size", max_val=65536)
            name = data.get("name") or data.get("register")
            if name is not None:
                name = str(name).strip()
            return Varnode(space=space.strip(), offset=offset, size=size, name=name)

        if isinstance(data, ET.Element):
            space = data.attrib.get("space")
            if not space:
                raise ValueError("Missing 'space' attribute in varnode XML element")
            offset_str = data.attrib.get("offset")
            if offset_str is None:
                raise ValueError("Missing 'offset' attribute in varnode XML element")
            offset = _parse_uint(offset_str, "offset", max_val=UINT64_MAX)
            size_str = data.attrib.get("size")
            if size_str is None:
                raise ValueError("Missing 'size' attribute in varnode XML element")
            size = _parse_uint(size_str, "size", max_val=65536)
            name = data.attrib.get("name") or data.attrib.get("register")
            if name:
                name = name.strip()
            return Varnode(space=space.strip(), offset=offset, size=size, name=name)

        raise ValueError(f"Unsupported varnode input type: {type(data).__name__}")

    @classmethod
    def parse_pcode_op(cls, data: Union[Dict[str, Any], ET.Element]) -> PcodeOp:
        """Parses and validates a high-level PcodeOp from dict or XML element."""
        if isinstance(data, dict):
            opcode = data.get("opcode") or data.get("code") or data.get("op")
            if not opcode or not isinstance(opcode, str):
                raise ValueError("Missing or invalid 'opcode' in pcode op")
            seq_val = data.get("seq", 0)
            seq = _parse_uint(seq_val, "seq", max_val=UINT32_MAX)

            inputs: List[Varnode] = []
            raw_inputs = data.get("inputs") or data.get("varnodes") or []
            if not isinstance(raw_inputs, list):
                raise ValueError(f"Expected list for 'inputs', got {type(raw_inputs).__name__}")
            for inp in raw_inputs:
                inputs.append(cls.parse_varnode(inp))

            output: Optional[Varnode] = None
            raw_output = data.get("output")
            if raw_output is not None:
                output = cls.parse_varnode(raw_output)

            target: Optional[int] = None
            if "target" in data and data["target"] is not None:
                target_val = data["target"]
                if isinstance(target_val, dict):
                    target_vn = cls.parse_varnode(target_val)
                    target = target_vn.offset
                else:
                    target = _parse_uint(target_val, "target", max_val=UINT64_MAX)

            return PcodeOp(opcode=opcode.strip(), seq=seq, inputs=inputs, output=output, target=target)

        if isinstance(data, ET.Element):
            opcode = data.attrib.get("code") or data.attrib.get("opcode") or data.attrib.get("op")
            if not opcode:
                raise ValueError("Missing 'code' attribute in pcode op XML element")
            seq_str = data.attrib.get("seq", "0")
            seq = _parse_uint(seq_str, "seq", max_val=UINT32_MAX)

            target: Optional[int] = None
            if "target" in data.attrib:
                target = _parse_uint(data.attrib["target"], "target", max_val=UINT64_MAX)

            inputs = []
            output = None

            for child in data:
                tag_lower = child.tag.lower()
                if tag_lower in ("varnode", "input"):
                    inputs.append(cls.parse_varnode(child))
                elif tag_lower == "output":
                    output = cls.parse_varnode(child)
                elif tag_lower == "target":
                    if "offset" in child.attrib:
                        target = _parse_uint(child.attrib["offset"], "target offset", max_val=UINT64_MAX)

            return PcodeOp(opcode=opcode.strip(), seq=seq, inputs=inputs, output=output, target=target)

        raise ValueError(f"Unsupported pcode op input type: {type(data).__name__}")

    @classmethod
    def parse_ast_node(cls, data: Union[Dict[str, Any], ET.Element]) -> ASTNode:
        """Parses an ASTNode recursively from dict or XML element."""
        if isinstance(data, dict):
            node_type = data.get("node_type") or data.get("type")
            if not node_type or not isinstance(node_type, str):
                raise ValueError("Missing or invalid 'node_type' in AST node")
            label = data.get("label") or data.get("name")
            if label is not None:
                label = str(label).strip()
            attributes = data.get("attributes") or {}
            if not isinstance(attributes, dict):
                raise ValueError(f"AST node 'attributes' must be a dict, got {type(attributes).__name__}")

            children: List[ASTNode] = []
            raw_children = data.get("children") or []
            if not isinstance(raw_children, list):
                raise ValueError(f"AST node 'children' must be a list, got {type(raw_children).__name__}")
            for child in raw_children:
                children.append(cls.parse_ast_node(child))

            return ASTNode(node_type=node_type.strip(), label=label, attributes=attributes, children=children)

        if isinstance(data, ET.Element):
            node_type = data.attrib.get("type") or data.attrib.get("node_type") or data.tag
            label = data.attrib.get("label") or data.attrib.get("name")
            if label:
                label = label.strip()

            attrs = {k: v for k, v in data.attrib.items() if k not in ("type", "node_type", "label", "name")}
            children = []
            for child in data:
                children.append(cls.parse_ast_node(child))

            return ASTNode(node_type=node_type.strip(), label=label, attributes=attrs, children=children)

        raise ValueError(f"Unsupported AST node input type: {type(data).__name__}")

    @classmethod
    def parse_function(cls, data: Union[Dict[str, Any], ET.Element]) -> GhidraFunction:
        """Parses a GhidraFunction from dictionary or XML element."""
        if isinstance(data, dict):
            name = data.get("name")
            if not name or not isinstance(name, str):
                raise ValueError("Missing or invalid function 'name'")

            entrypoint_val = data.get("entrypoint") or data.get("entry") or data.get("address")
            if entrypoint_val is None:
                raise ValueError("Missing function 'entrypoint'")
            entrypoint = _parse_uint(entrypoint_val, "entrypoint", max_val=UINT64_MAX)

            return_type = data.get("return_type") or data.get("return") or "void"
            if not isinstance(return_type, str):
                raise ValueError(f"Invalid return_type: {return_type}")

            size_val = data.get("size", 0)
            size = _parse_uint(size_val, "size", max_val=UINT64_MAX)

            # Parameters
            params: List[Parameter] = []
            raw_params = data.get("parameters") or []
            if not isinstance(raw_params, list):
                raise ValueError(f"Parameters must be a list, got {type(raw_params).__name__}")
            for p in raw_params:
                p_name = p.get("name")
                p_type = p.get("type") or p.get("type_name") or "undefined"
                p_storage = p.get("storage") or "register"
                p_size = _parse_uint(p.get("size", 4), "parameter size", max_val=UINT32_MAX)
                p_offset = _parse_uint(p["offset"], "parameter offset", max_val=UINT64_MAX) if "offset" in p else None
                p_reg = p.get("register")
                params.append(Parameter(name=p_name, type_name=p_type, storage=p_storage, size=p_size, offset=p_offset, register=p_reg))

            # Local variables
            locals_list: List[LocalVariable] = []
            raw_locals = data.get("local_variables") or data.get("locals") or []
            if not isinstance(raw_locals, list):
                raise ValueError(f"Local variables must be a list, got {type(raw_locals).__name__}")
            for lv in raw_locals:
                lv_name = lv.get("name")
                lv_type = lv.get("type") or lv.get("type_name") or "undefined"
                lv_storage = lv.get("storage") or "stack"
                lv_size = _parse_uint(lv.get("size", 4), "local variable size", max_val=UINT32_MAX)
                lv_offset = _parse_uint(lv["offset"], "local variable offset", max_val=UINT64_MAX) if "offset" in lv else None
                lv_reg = lv.get("register")
                locals_list.append(LocalVariable(name=lv_name, type_name=lv_type, storage=lv_storage, size=lv_size, offset=lv_offset, register=lv_reg))

            # P-code
            pcode: List[PcodeOp] = []
            raw_pcode = data.get("pcode") or []
            if not isinstance(raw_pcode, list):
                raise ValueError(f"P-code must be a list, got {type(raw_pcode).__name__}")
            for op in raw_pcode:
                pcode.append(cls.parse_pcode_op(op))

            # AST
            ast_node: Optional[ASTNode] = None
            if "ast" in data and data["ast"]:
                ast_node = cls.parse_ast_node(data["ast"])

            # C Code & Tokens
            c_code = data.get("c_code") or data.get("decompilation")
            c_tokens: List[DecompilerToken] = []
            if c_code:
                if not isinstance(c_code, str):
                    raise ValueError("Field 'c_code' must be a string")
                c_tokens = tokenize_c_code(c_code)

            # CFG edges
            cfg_edges = extract_cfg_edges(pcode)

            return GhidraFunction(
                name=name.strip(),
                entrypoint=entrypoint,
                return_type=return_type.strip(),
                size=size,
                parameters=params,
                local_variables=locals_list,
                pcode=pcode,
                ast=ast_node,
                c_code=c_code,
                c_tokens=c_tokens,
                cfg_edges=cfg_edges,
            )

        if isinstance(data, ET.Element):
            name = data.attrib.get("name")
            if not name:
                raise ValueError("Missing 'name' attribute in function XML element")

            entrypoint_str = data.attrib.get("entry") or data.attrib.get("entrypoint") or data.attrib.get("address")
            if entrypoint_str is None:
                raise ValueError("Missing 'entry' attribute in function XML element")
            entrypoint = _parse_uint(entrypoint_str, "entrypoint", max_val=UINT64_MAX)

            return_type = data.attrib.get("return_type") or data.attrib.get("return") or "void"
            size_str = data.attrib.get("size", "0")
            size = _parse_uint(size_str, "size", max_val=UINT64_MAX)

            params = []
            locals_list = []
            pcode = []
            ast_node = None
            c_code = None

            for child in data:
                tag_lower = child.tag.lower()
                if tag_lower in ("parameters", "params"):
                    for p_elem in child:
                        p_name = p_elem.attrib.get("name")
                        p_type = p_elem.attrib.get("type") or p_elem.attrib.get("type_name") or "undefined"
                        p_storage = p_elem.attrib.get("storage") or "register"
                        p_size = _parse_uint(p_elem.attrib.get("size", "4"), "param size", max_val=UINT32_MAX)
                        p_offset = _parse_uint(p_elem.attrib["offset"], "param offset", max_val=UINT64_MAX) if "offset" in p_elem.attrib else None
                        p_reg = p_elem.attrib.get("register")
                        params.append(Parameter(name=p_name, type_name=p_type, storage=p_storage, size=p_size, offset=p_offset, register=p_reg))
                elif tag_lower == "param" or tag_lower == "parameter":
                    p_name = child.attrib.get("name")
                    p_type = child.attrib.get("type") or child.attrib.get("type_name") or "undefined"
                    p_storage = child.attrib.get("storage") or "register"
                    p_size = _parse_uint(child.attrib.get("size", "4"), "param size", max_val=UINT32_MAX)
                    p_offset = _parse_uint(child.attrib["offset"], "param offset", max_val=UINT64_MAX) if "offset" in child.attrib else None
                    p_reg = child.attrib.get("register")
                    params.append(Parameter(name=p_name, type_name=p_type, storage=p_storage, size=p_size, offset=p_offset, register=p_reg))
                elif tag_lower in ("local_variables", "locals"):
                    for lv_elem in child:
                        lv_name = lv_elem.attrib.get("name")
                        lv_type = lv_elem.attrib.get("type") or lv_elem.attrib.get("type_name") or "undefined"
                        lv_storage = lv_elem.attrib.get("storage") or "stack"
                        lv_size = _parse_uint(lv_elem.attrib.get("size", "4"), "local var size", max_val=UINT32_MAX)
                        lv_offset = _parse_uint(lv_elem.attrib["offset"], "local var offset", max_val=UINT64_MAX) if "offset" in lv_elem.attrib else None
                        lv_reg = lv_elem.attrib.get("register")
                        locals_list.append(LocalVariable(name=lv_name, type_name=lv_type, storage=lv_storage, size=lv_size, offset=lv_offset, register=lv_reg))
                elif tag_lower in ("pcode", "pcode_ops"):
                    for op_elem in child:
                        pcode.append(cls.parse_pcode_op(op_elem))
                elif tag_lower == "ast":
                    for ast_child in child:
                        ast_node = cls.parse_ast_node(ast_child)
                        break
                elif tag_lower in ("c_code", "decompilation"):
                    c_code = child.text

            c_tokens: List[DecompilerToken] = []
            if c_code:
                c_tokens = tokenize_c_code(c_code)

            cfg_edges = extract_cfg_edges(pcode)

            return GhidraFunction(
                name=name.strip(),
                entrypoint=entrypoint,
                return_type=return_type.strip(),
                size=size,
                parameters=params,
                local_variables=locals_list,
                pcode=pcode,
                ast=ast_node,
                c_code=c_code,
                c_tokens=c_tokens,
                cfg_edges=cfg_edges,
            )

        raise ValueError(f"Unsupported function input type: {type(data).__name__}")

    @classmethod
    def parse_data_type(cls, data: Union[Dict[str, Any], ET.Element]) -> GhidraDataType:
        """Parses a GhidraDataType from dict or XML element."""
        if isinstance(data, dict):
            name = data.get("name")
            if not name or not isinstance(name, str):
                raise ValueError("Missing or invalid 'name' in data type")
            size_val = data.get("size", 0)
            size = _parse_uint(size_val, "data type size", max_val=UINT32_MAX)
            kind = data.get("kind") or "builtin"
            base_type = data.get("base_type")
            if base_type is not None:
                base_type = str(base_type).strip()

            fields: List[GhidraDataTypeField] = []
            raw_fields = data.get("fields") or []
            if not isinstance(raw_fields, list):
                raise ValueError("Data type 'fields' must be a list")
            for f in raw_fields:
                f_name = f.get("name")
                f_type = f.get("type") or f.get("type_name") or "undefined"
                f_offset = _parse_uint(f.get("offset", 0), "field offset", max_val=UINT64_MAX)
                f_size = _parse_uint(f.get("size", 0), "field size", max_val=UINT32_MAX)
                fields.append(GhidraDataTypeField(name=f_name, type_name=f_type, offset=f_offset, size=f_size))

            enum_vals = {}
            if "enum_values" in data and isinstance(data["enum_values"], dict):
                for k, v in data["enum_values"].items():
                    enum_vals[str(k)] = _parse_uint(v, f"enum {k}", max_val=UINT64_MAX)

            return GhidraDataType(name=name.strip(), size=size, kind=kind.strip(), fields=fields, base_type=base_type, enum_values=enum_vals)

        if isinstance(data, ET.Element):
            name = data.attrib.get("name")
            if not name:
                raise ValueError("Missing 'name' attribute in data type XML element")
            size_str = data.attrib.get("size", "0")
            size = _parse_uint(size_str, "data type size", max_val=UINT32_MAX)
            kind = data.attrib.get("kind") or "builtin"
            base_type = data.attrib.get("base_type")
            if base_type:
                base_type = base_type.strip()

            fields = []
            enum_vals = {}
            for child in data:
                tag_lower = child.tag.lower()
                if tag_lower in ("field", "member"):
                    f_name = child.attrib.get("name")
                    f_type = child.attrib.get("type") or child.attrib.get("type_name") or "undefined"
                    f_offset = _parse_uint(child.attrib.get("offset", "0"), "field offset", max_val=UINT64_MAX)
                    f_size = _parse_uint(child.attrib.get("size", "0"), "field size", max_val=UINT32_MAX)
                    fields.append(GhidraDataTypeField(name=f_name, type_name=f_type, offset=f_offset, size=f_size))
                elif tag_lower in ("enum_value", "entry"):
                    ev_name = child.attrib.get("name")
                    ev_val = _parse_uint(child.attrib.get("value", "0"), "enum value", max_val=UINT64_MAX)
                    enum_vals[ev_name] = ev_val

            return GhidraDataType(name=name.strip(), size=size, kind=kind.strip(), fields=fields, base_type=base_type, enum_values=enum_vals)

        raise ValueError(f"Unsupported data type input type: {type(data).__name__}")

    @classmethod
    def parse_symbol(cls, data: Union[Dict[str, Any], ET.Element]) -> GhidraSymbol:
        """Parses a GhidraSymbol from dict or XML element."""
        if isinstance(data, dict):
            name = data.get("name")
            if not name or not isinstance(name, str):
                raise ValueError("Missing or invalid 'name' in symbol")
            addr_val = data.get("address") or data.get("addr")
            if addr_val is None:
                raise ValueError("Missing 'address' in symbol")
            address = _parse_uint(addr_val, "symbol address", max_val=UINT64_MAX)
            sym_type = data.get("type") or data.get("symbol_type") or "label"
            namespace = data.get("namespace")
            if namespace is not None:
                namespace = str(namespace).strip()
            return GhidraSymbol(name=name.strip(), address=address, symbol_type=sym_type.strip(), namespace=namespace)

        if isinstance(data, ET.Element):
            name = data.attrib.get("name")
            if not name:
                raise ValueError("Missing 'name' attribute in symbol XML element")
            addr_str = data.attrib.get("address") or data.attrib.get("addr")
            if addr_str is None:
                raise ValueError("Missing 'address' attribute in symbol XML element")
            address = _parse_uint(addr_str, "symbol address", max_val=UINT64_MAX)
            sym_type = data.attrib.get("type") or data.attrib.get("symbol_type") or "label"
            namespace = data.attrib.get("namespace")
            if namespace:
                namespace = namespace.strip()
            return GhidraSymbol(name=name.strip(), address=address, symbol_type=sym_type.strip(), namespace=namespace)

        raise ValueError(f"Unsupported symbol input type: {type(data).__name__}")

    @classmethod
    def parse_comment(cls, data: Union[Dict[str, Any], ET.Element]) -> GhidraComment:
        """Parses a GhidraComment from dict or XML element."""
        if isinstance(data, dict):
            addr_val = data.get("address") or data.get("addr")
            if addr_val is None:
                raise ValueError("Missing 'address' in comment")
            address = _parse_uint(addr_val, "comment address", max_val=UINT64_MAX)
            comment_type = data.get("type") or data.get("comment_type") or "eol"
            text = data.get("text") or data.get("comment") or ""
            return GhidraComment(address=address, comment_type=comment_type.strip(), text=str(text).strip())

        if isinstance(data, ET.Element):
            addr_str = data.attrib.get("address") or data.attrib.get("addr")
            if addr_str is None:
                raise ValueError("Missing 'address' attribute in comment XML element")
            address = _parse_uint(addr_str, "comment address", max_val=UINT64_MAX)
            comment_type = data.attrib.get("type") or data.attrib.get("comment_type") or "eol"
            text = (data.text or "").strip()
            return GhidraComment(address=address, comment_type=comment_type.strip(), text=text)

        raise ValueError(f"Unsupported comment input type: {type(data).__name__}")

    @classmethod
    def parse_json(cls, data: Union[str, bytes, Dict[str, Any], List[Any]]) -> GhidraProgram:
        """Parses full Ghidra Program or function JSON export."""
        if data is None:
            raise ValueError("Empty payload provided for Ghidra JSON parser")

        if isinstance(data, (bytes, bytearray)):
            if len(data) == 0:
                raise ValueError("Empty payload provided for Ghidra JSON parser")
            if len(data) > MAX_PAYLOAD_BYTES:
                raise ValueError(f"Payload size {len(data)} exceeds maximum allowed {MAX_PAYLOAD_BYTES} bytes")
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as err:
                raise ValueError(f"Invalid UTF-8 encoding in JSON payload: {err}") from err
            try:
                raw_json = json.loads(text)
            except json.JSONDecodeError as err:
                raise ValueError(f"Corrupted or invalid JSON payload: {err}") from err
        elif isinstance(data, str):
            text = data.strip()
            if not text:
                raise ValueError("Empty payload provided for Ghidra JSON parser")
            if len(data.encode("utf-8")) > MAX_PAYLOAD_BYTES:
                raise ValueError(f"Payload size exceeds maximum allowed {MAX_PAYLOAD_BYTES} bytes")
            try:
                raw_json = json.loads(text)
            except json.JSONDecodeError as err:
                raise ValueError(f"Corrupted or invalid JSON payload: {err}") from err
        elif isinstance(data, (dict, list)):
            raw_json = data
        else:
            raise ValueError(f"Unsupported data type for Ghidra JSON parser: {type(data).__name__}")

        # Coerce root: if single function dict or list of functions
        if isinstance(raw_json, list):
            # List of functions
            functions_dict: Dict[str, GhidraFunction] = {}
            for item in raw_json:
                f = cls.parse_function(item)
                functions_dict[f.name] = f
            prog = GhidraProgram(name="ExportedFunctions", arch="unknown", functions=functions_dict)
            object.__setattr__(prog, "program_digest", canonical_sha256(prog.to_dict()))
            return prog

        if not isinstance(raw_json, dict):
            raise ValueError(f"Top-level JSON payload must be an object or array, got {type(raw_json).__name__}")

        if not raw_json:
            raise ValueError("Empty JSON object provided for Ghidra parser")

        # Check if single function payload
        if "functions" not in raw_json and ("entrypoint" in raw_json or "entry" in raw_json) and "name" in raw_json:
            f = cls.parse_function(raw_json)
            prog = GhidraProgram(name=f.name, arch="unknown", functions={f.name: f})
            object.__setattr__(prog, "program_digest", canonical_sha256(prog.to_dict()))
            return prog

        prog_name = raw_json.get("name") or raw_json.get("program") or "GhidraExport"
        arch = raw_json.get("arch") or raw_json.get("architecture") or "unknown"

        # Data types
        data_types: Dict[str, GhidraDataType] = {}
        raw_dts = raw_json.get("data_types") or raw_json.get("datatypes") or []
        if isinstance(raw_dts, list):
            for dt_item in raw_dts:
                dt = cls.parse_data_type(dt_item)
                data_types[dt.name] = dt
        elif isinstance(raw_dts, dict):
            for dt_k, dt_v in raw_dts.items():
                if isinstance(dt_v, dict) and "name" not in dt_v:
                    dt_v = dict(dt_v)
                    dt_v["name"] = dt_k
                dt = cls.parse_data_type(dt_v)
                data_types[dt.name] = dt
        else:
            raise ValueError(f"Field 'data_types' must be list or dict, got {type(raw_dts).__name__}")

        # Validate no cyclic data types
        check_cyclic_data_types(data_types)

        # Symbols
        symbols: List[GhidraSymbol] = []
        raw_symbols = raw_json.get("symbols") or raw_json.get("symbol_table") or []
        if isinstance(raw_symbols, list):
            for sym_item in raw_symbols:
                symbols.append(cls.parse_symbol(sym_item))
        elif isinstance(raw_symbols, dict):
            for sym_k, sym_v in raw_symbols.items():
                if isinstance(sym_v, dict) and "name" not in sym_v:
                    sym_v = dict(sym_v)
                    sym_v["name"] = sym_k
                symbols.append(cls.parse_symbol(sym_v))
        else:
            raise ValueError(f"Field 'symbols' must be list or dict, got {type(raw_symbols).__name__}")

        # Comments
        comments: List[GhidraComment] = []
        raw_comments = raw_json.get("comments") or []
        if isinstance(raw_comments, list):
            for c_item in raw_comments:
                comments.append(cls.parse_comment(c_item))
        else:
            raise ValueError(f"Field 'comments' must be list, got {type(raw_comments).__name__}")

        # Functions
        functions: Dict[str, GhidraFunction] = {}
        raw_functions = raw_json.get("functions") or []
        if isinstance(raw_functions, list):
            for f_item in raw_functions:
                f = cls.parse_function(f_item)
                functions[f.name] = f
        elif isinstance(raw_functions, dict):
            for f_k, f_v in raw_functions.items():
                if isinstance(f_v, dict) and "name" not in f_v:
                    f_v = dict(f_v)
                    f_v["name"] = f_k
                f = cls.parse_function(f_v)
                functions[f.name] = f
        else:
            raise ValueError(f"Field 'functions' must be list or dict, got {type(raw_functions).__name__}")

        prog = GhidraProgram(
            name=str(prog_name).strip(),
            arch=str(arch).strip(),
            data_types=data_types,
            symbols=symbols,
            comments=comments,
            functions=functions,
        )
        object.__setattr__(prog, "program_digest", canonical_sha256(prog.to_dict()))
        return prog

    @classmethod
    def parse_xml(cls, data: Union[str, bytes]) -> GhidraProgram:
        """Parses full Ghidra Program or function XML export."""
        if data is None:
            raise ValueError("Empty payload provided for Ghidra XML parser")

        if isinstance(data, (bytes, bytearray)):
            if len(data) == 0:
                raise ValueError("Empty payload provided for Ghidra XML parser")
            if len(data) > MAX_PAYLOAD_BYTES:
                raise ValueError(f"Payload size {len(data)} exceeds maximum allowed {MAX_PAYLOAD_BYTES} bytes")
            try:
                root = ET.fromstring(data)
            except ET.ParseError as err:
                raise ValueError(f"Corrupted or invalid XML payload: {err}") from err
        elif isinstance(data, str):
            text = data.strip()
            if not text:
                raise ValueError("Empty payload provided for Ghidra XML parser")
            if len(data.encode("utf-8")) > MAX_PAYLOAD_BYTES:
                raise ValueError(f"Payload size exceeds maximum allowed {MAX_PAYLOAD_BYTES} bytes")
            try:
                root = ET.fromstring(text)
            except ET.ParseError as err:
                raise ValueError(f"Corrupted or invalid XML payload: {err}") from err
        else:
            raise ValueError(f"Unsupported data type for Ghidra XML parser: {type(data).__name__}")

        root_tag = root.tag.upper()

        # Case 1: Single function XML
        if root_tag in ("FUNCTION", "DECOMPILED_FUNCTION"):
            f = cls.parse_function(root)
            prog = GhidraProgram(name=f.name, arch="unknown", functions={f.name: f})
            object.__setattr__(prog, "program_digest", canonical_sha256(prog.to_dict()))
            return prog

        # Case 2: List of functions `<FUNCTIONS>`
        if root_tag == "FUNCTIONS":
            functions_dict: Dict[str, GhidraFunction] = {}
            for child in root:
                if child.tag.upper() in ("FUNCTION", "DECOMPILED_FUNCTION"):
                    f = cls.parse_function(child)
                    functions_dict[f.name] = f
            prog = GhidraProgram(name="ExportedFunctions", arch="unknown", functions=functions_dict)
            object.__setattr__(prog, "program_digest", canonical_sha256(prog.to_dict()))
            return prog

        # Case 3: Complete Program XML
        prog_name = root.attrib.get("NAME") or root.attrib.get("name") or "GhidraExport"
        arch = root.attrib.get("ARCH") or root.attrib.get("arch") or "unknown"

        data_types: Dict[str, GhidraDataType] = {}
        symbols: List[GhidraSymbol] = []
        comments: List[GhidraComment] = []
        functions: Dict[str, GhidraFunction] = {}

        for child in root:
            child_tag = child.tag.upper()
            if child_tag in ("DATATYPES", "DATA_TYPES"):
                for dt_elem in child:
                    dt = cls.parse_data_type(dt_elem)
                    data_types[dt.name] = dt
            elif child_tag in ("SYMBOL_TABLE", "SYMBOLS"):
                for sym_elem in child:
                    symbols.append(cls.parse_symbol(sym_elem))
            elif child_tag in ("COMMENTS", "COMMENT_TABLE"):
                for c_elem in child:
                    comments.append(cls.parse_comment(c_elem))
            elif child_tag in ("FUNCTIONS", "FUNCTION_TABLE"):
                for f_elem in child:
                    if f_elem.tag.upper() in ("FUNCTION", "DECOMPILED_FUNCTION"):
                        f = cls.parse_function(f_elem)
                        functions[f.name] = f

        # Validate no cyclic data types
        check_cyclic_data_types(data_types)

        prog = GhidraProgram(
            name=str(prog_name).strip(),
            arch=str(arch).strip(),
            data_types=data_types,
            symbols=symbols,
            comments=comments,
            functions=functions,
        )
        object.__setattr__(prog, "program_digest", canonical_sha256(prog.to_dict()))
        return prog

    @classmethod
    def parse_bytes(cls, data: bytes) -> GhidraProgram:
        """Auto-detects XML vs JSON format from raw bytes and parses GhidraProgram."""
        if not data or len(data) == 0:
            raise ValueError("Empty payload provided for Ghidra parser")
        if len(data) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"Payload size {len(data)} exceeds maximum allowed {MAX_PAYLOAD_BYTES} bytes")

        # Strip leading whitespace
        stripped = data.lstrip()
        if not stripped:
            raise ValueError("Empty payload provided for Ghidra parser")

        if stripped.startswith(b"<"):
            return cls.parse_xml(data)
        elif stripped.startswith(b"{") or stripped.startswith(b"["):
            return cls.parse_json(data)
        else:
            raise ValueError(f"Unrecognized payload header for Ghidra parser: {stripped[:16]!r}")

    @classmethod
    def parse_str(cls, text: str) -> GhidraProgram:
        """Auto-detects XML vs JSON format from string and parses GhidraProgram."""
        if not text or not text.strip():
            raise ValueError("Empty payload provided for Ghidra parser")
        return cls.parse_bytes(text.encode("utf-8"))
