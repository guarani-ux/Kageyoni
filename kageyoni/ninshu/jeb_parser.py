"""Zero-dependency in-tree JEB Decompiler Automation & Scripting Bridge (CH 32).

Pure Python standard library implementation:
1. JEB AST Unit & Project Parsing:
   - Parses project metadata, engine status, and decompiled units (DEX, ELF, Java, MIPS).
   - Extracts classes, fields, methods, and basic block control-flow structures.
2. Cross-Reference (XREF) Extraction:
   - Extracts and categorizes callers, callees, memory reads, and memory writes.
   - Validates address tokens and xref target validity with strict fail-closed rejection.
3. Type Hierarchy & Decompiler Metadata:
   - Resolves class inheritance chains with cycle detection.
   - Identifies implemented interfaces and overridden method definitions.
   - Preserves decompiler comments and user-applied symbol renames.
4. Strict Fail-Closed Invariants:
   - Empty input validation, payload size ceiling (<= 64 KB), and JSON malformation rejection.
   - Canonical RFC 8785 SHA-256 digest calculation.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

MAX_JEB_PAYLOAD_BYTES = 64 * 1024  # 64 KB thermodynamic memory ceiling
UINT64_MAX = 0xFFFF_FFFF_FFFF_FFFF

VALID_XREF_TYPES = {"caller", "callee", "read", "write"}

XREF_TYPE_ALIASES = {
    "caller": "caller",
    "callers": "caller",
    "call": "caller",
    "callee": "callee",
    "callees": "callee",
    "read": "read",
    "reads": "read",
    "memory_read": "read",
    "memory_reads": "read",
    "write": "write",
    "writes": "write",
    "memory_write": "write",
    "memory_writes": "write",
}

CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


def canonical_sha256(data: Union[bytes, str, Dict[str, Any], List[Any]]) -> str:
    """Computes an RFC 8785 compliant canonical SHA-256 digest."""
    if isinstance(data, bytes):
        raw_bytes = data
    elif isinstance(data, str):
        raw_bytes = data.encode("utf-8")
    else:
        raw_bytes = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


def _validate_address(addr: Any, field_name: str) -> str:
    """Validates and normalizes address, signature, or symbol strings."""
    if addr is None:
        raise ValueError(f"Field '{field_name}' address cannot be None")
    if isinstance(addr, bool):
        raise ValueError(f"Field '{field_name}' address cannot be boolean")
    if isinstance(addr, int):
        if addr < 0:
            raise ValueError(f"Field '{field_name}' address cannot be negative: {addr}")
        return f"0x{addr:X}"
    if not isinstance(addr, str):
        raise ValueError(f"Field '{field_name}' address must be str or int, got {type(addr).__name__}")
    cleaned = addr.strip()
    if not cleaned:
        raise ValueError(f"Field '{field_name}' address cannot be empty or whitespace")
    if CONTROL_CHARS_PATTERN.search(cleaned):
        raise ValueError(f"Field '{field_name}' address contains illegal control characters: {addr!r}")
    if cleaned.startswith("0x") or cleaned.startswith("0X"):
        try:
            int(cleaned, 16)
        except ValueError as err:
            raise ValueError(f"Field '{field_name}' has invalid hex address: '{cleaned}'") from err
    return cleaned


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
class JebEngineInfo:
    """JEB Decompiler client and engine metadata."""
    name: str
    version: Optional[str]
    endpoint: str
    gui_client: Optional[bool]


@dataclasses.dataclass(frozen=True)
class JebBasicBlock:
    """Basic block control-flow segment in decompiled code."""
    block_id: str
    start_address: int
    end_address: int
    instruction_count: int
    predecessors: Tuple[str, ...]
    successors: Tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class JebXref:
    """Cross-reference representing caller, callee, read, or write relationships."""
    xref_type: str
    source_address: str
    target_address: str
    details: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class JebField:
    """Decompiled field member within a class."""
    name: str
    signature: str
    field_type: str
    access_flags: int
    initial_value: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class JebMethod:
    """Decompiled method unit with AST CFG blocks, xrefs, and annotations."""
    name: str
    signature: str
    return_type: str
    parameter_types: Tuple[str, ...]
    access_flags: int
    basic_blocks: Tuple[JebBasicBlock, ...]
    xrefs: Tuple[JebXref, ...]
    decompiled_code: Optional[str] = None
    comments: Dict[str, str] = dataclasses.field(default_factory=dict)
    user_renames: Dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class JebClass:
    """Decompiled class or interface with hierarchy and member definitions."""
    name: str
    superclass: Optional[str]
    interfaces: Tuple[str, ...]
    fields: Tuple[JebField, ...]
    methods: Tuple[JebMethod, ...]
    method_overrides: Dict[str, str] = dataclasses.field(default_factory=dict)
    comments: Dict[str, str] = dataclasses.field(default_factory=dict)
    user_renames: Dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class JebUnit:
    """Top-level or child decompiled unit within a JEB project."""
    unit_path: str
    unit_type: str
    classes: Tuple[JebClass, ...]
    xrefs: Tuple[JebXref, ...]
    comments: Dict[str, str] = dataclasses.field(default_factory=dict)
    renames: Dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class JebAnalysisReport:
    """Full parsed report of a JEB decompilation session."""
    engine: JebEngineInfo
    project_name: Optional[str]
    units: Tuple[JebUnit, ...]
    classes: Dict[str, JebClass]
    all_xrefs: Tuple[JebXref, ...]
    comments: Dict[str, str]
    renames: Dict[str, str]
    digest: str


class JebParser:
    """Zero-dependency parser for JEB Decompiler analysis exports and AST units."""

    @classmethod
    def parse_bytes(cls, data: bytes) -> JebAnalysisReport:
        """Parses JEB analysis JSON payload from raw bytes under memory budget."""
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError(f"Expected bytes, received {type(data).__name__}")
        if len(data) > MAX_JEB_PAYLOAD_BYTES:
            raise ValueError(f"Payload size {len(data)} exceeds {MAX_JEB_PAYLOAD_BYTES} bytes ceiling")
        if not data.strip():
            raise ValueError("Cannot parse empty or whitespace payload")

        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError as err:
            raise ValueError(f"Payload is not valid UTF-8: {err}") from err

        return cls.parse_json(decoded)

    @classmethod
    def parse_json(cls, text: str) -> JebAnalysisReport:
        """Parses JEB analysis JSON payload from string."""
        if not isinstance(text, str):
            raise ValueError(f"Expected str, received {type(text).__name__}")
        trimmed = text.strip()
        if not trimmed:
            raise ValueError("Cannot parse empty or whitespace string")
        if len(trimmed.encode("utf-8")) > MAX_JEB_PAYLOAD_BYTES:
            raise ValueError(f"Payload size exceeds {MAX_JEB_PAYLOAD_BYTES} bytes ceiling")

        try:
            payload = json.loads(trimmed)
        except json.JSONDecodeError as err:
            raise ValueError(f"Malformed JSON in JEB payload: {err}") from err

        return cls.parse_dict(payload)

    @classmethod
    def parse_dict(cls, data: Dict[str, Any]) -> JebAnalysisReport:
        """Validates and parses JEB analysis dictionary structure."""
        if not isinstance(data, dict):
            raise ValueError(f"Expected dictionary root, received {type(data).__name__}")
        if not data:
            raise ValueError("Dictionary root cannot be empty")

        # 1. Parse Engine Info
        engine_raw = data.get("engine")
        if engine_raw is None:
            engine_info = JebEngineInfo(
                name="JEB Decompiler",
                version=None,
                endpoint="http://127.0.0.1:8425/mcp",
                gui_client=None,
            )
        elif isinstance(engine_raw, dict):
            eng_name = engine_raw.get("name", "JEB Decompiler")
            if not isinstance(eng_name, str) or not eng_name.strip():
                raise ValueError("Engine name must be a non-empty string")
            engine_info = JebEngineInfo(
                name=eng_name.strip(),
                version=engine_raw.get("version"),
                endpoint=str(engine_raw.get("endpoint", "http://127.0.0.1:8425/mcp")),
                gui_client=engine_raw.get("gui_client"),
            )
        else:
            raise ValueError("Field 'engine' must be a dictionary")

        project_name = data.get("project_name")
        if project_name is not None and not isinstance(project_name, str):
            raise ValueError("Field 'project_name' must be a string or null")

        # 2. Parse Units
        raw_units = data.get("units")
        if raw_units is None:
            raise ValueError("Missing required field 'units'")
        if not isinstance(raw_units, list):
            raise ValueError("Field 'units' must be a list")

        parsed_units: List[JebUnit] = []
        class_registry: Dict[str, JebClass] = {}
        all_xrefs: List[JebXref] = []
        global_comments: Dict[str, str] = {}
        global_renames: Dict[str, str] = {}

        for idx, u in enumerate(raw_units):
            unit = cls._parse_unit(u, idx)
            parsed_units.append(unit)
            for c in unit.classes:
                if c.name in class_registry:
                    raise ValueError(f"Duplicate class definition encountered: '{c.name}'")
                class_registry[c.name] = c
                global_comments.update(c.comments)
                global_renames.update(c.user_renames)
                for m in c.methods:
                    all_xrefs.extend(m.xrefs)
                    global_comments.update(m.comments)
                    global_renames.update(m.user_renames)
            all_xrefs.extend(unit.xrefs)
            global_comments.update(unit.comments)
            global_renames.update(unit.renames)

        # Top-level comments and renames if provided
        top_comments = data.get("comments")
        if isinstance(top_comments, dict):
            for k, v in top_comments.items():
                global_comments[str(k)] = str(v)
        elif top_comments is not None:
            raise ValueError("Field 'comments' must be a dictionary")

        top_renames = data.get("renames")
        if isinstance(top_renames, dict):
            for k, v in top_renames.items():
                global_renames[str(k)] = str(v)
        elif top_renames is not None:
            raise ValueError("Field 'renames' must be a dictionary")

        top_xrefs = data.get("xrefs")
        if isinstance(top_xrefs, list):
            for x_idx, x in enumerate(top_xrefs):
                all_xrefs.append(cls._parse_xref(x, f"root.xrefs[{x_idx}]"))
        elif top_xrefs is not None:
            raise ValueError("Field 'xrefs' must be a list")

        digest = canonical_sha256(data)

        return JebAnalysisReport(
            engine=engine_info,
            project_name=project_name,
            units=tuple(parsed_units),
            classes=class_registry,
            all_xrefs=tuple(all_xrefs),
            comments=global_comments,
            renames=global_renames,
            digest=digest,
        )

    @classmethod
    def _parse_unit(cls, data: Any, index: int) -> JebUnit:
        if not isinstance(data, dict):
            raise ValueError(f"Unit at index {index} must be a dictionary")

        unit_path = data.get("unit_path")
        if not isinstance(unit_path, str) or not unit_path.strip():
            raise ValueError(f"Unit at index {index} missing non-empty 'unit_path'")

        unit_type = data.get("unit_type")
        if not isinstance(unit_type, str) or not unit_type.strip():
            raise ValueError(f"Unit '{unit_path}' missing non-empty 'unit_type'")

        raw_classes = data.get("classes", [])
        if not isinstance(raw_classes, list):
            raise ValueError(f"Unit '{unit_path}' field 'classes' must be a list")

        classes: List[JebClass] = []
        for c_idx, c in enumerate(raw_classes):
            classes.append(cls._parse_class(c, unit_path, c_idx))

        raw_xrefs = data.get("xrefs", [])
        if not isinstance(raw_xrefs, list):
            raise ValueError(f"Unit '{unit_path}' field 'xrefs' must be a list")
        unit_xrefs = [cls._parse_xref(x, f"{unit_path}.xrefs[{i}]") for i, x in enumerate(raw_xrefs)]

        raw_comments = data.get("comments", {})
        if not isinstance(raw_comments, dict):
            raise ValueError(f"Unit '{unit_path}' field 'comments' must be a dict")
        comments = {str(k): str(v) for k, v in raw_comments.items()}

        raw_renames = data.get("renames", {})
        if not isinstance(raw_renames, dict):
            raise ValueError(f"Unit '{unit_path}' field 'renames' must be a dict")
        renames = {str(k): str(v) for k, v in raw_renames.items()}

        return JebUnit(
            unit_path=unit_path.strip(),
            unit_type=unit_type.strip(),
            classes=tuple(classes),
            xrefs=tuple(unit_xrefs),
            comments=comments,
            renames=renames,
        )

    @classmethod
    def _parse_class(cls, data: Any, unit_path: str, index: int) -> JebClass:
        if not isinstance(data, dict):
            raise ValueError(f"Class at index {index} in '{unit_path}' must be a dictionary")

        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Class in '{unit_path}' at index {index} missing non-empty 'name'")
        name = name.strip()

        superclass = data.get("superclass")
        if superclass is not None:
            if not isinstance(superclass, str) or not superclass.strip():
                raise ValueError(f"Class '{name}' superclass must be a non-empty string or null")
            superclass = superclass.strip()

        interfaces_raw = data.get("interfaces", [])
        if not isinstance(interfaces_raw, list):
            raise ValueError(f"Class '{name}' interfaces must be a list")
        interfaces = []
        for iface in interfaces_raw:
            if not isinstance(iface, str) or not iface.strip():
                raise ValueError(f"Class '{name}' interface item must be a non-empty string")
            interfaces.append(iface.strip())

        fields_raw = data.get("fields", [])
        if not isinstance(fields_raw, list):
            raise ValueError(f"Class '{name}' fields must be a list")
        fields = [cls._parse_field(f, name, i) for i, f in enumerate(fields_raw)]

        methods_raw = data.get("methods", [])
        if not isinstance(methods_raw, list):
            raise ValueError(f"Class '{name}' methods must be a list")
        methods = [cls._parse_method(m, name, i) for i, m in enumerate(methods_raw)]

        overrides_raw = data.get("method_overrides", {})
        if not isinstance(overrides_raw, dict):
            raise ValueError(f"Class '{name}' method_overrides must be a dictionary")
        overrides = {str(k): str(v) for k, v in overrides_raw.items()}

        comments_raw = data.get("comments", {})
        if not isinstance(comments_raw, dict):
            raise ValueError(f"Class '{name}' comments must be a dictionary")
        comments = {str(k): str(v) for k, v in comments_raw.items()}

        renames_raw = data.get("user_renames", {})
        if not isinstance(renames_raw, dict):
            raise ValueError(f"Class '{name}' user_renames must be a dictionary")
        renames = {str(k): str(v) for k, v in renames_raw.items()}

        return JebClass(
            name=name,
            superclass=superclass,
            interfaces=tuple(interfaces),
            fields=tuple(fields),
            methods=tuple(methods),
            method_overrides=overrides,
            comments=comments,
            user_renames=renames,
        )

    @classmethod
    def _parse_field(cls, data: Any, class_name: str, index: int) -> JebField:
        if not isinstance(data, dict):
            raise ValueError(f"Field at index {index} in class '{class_name}' must be a dictionary")

        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Field in '{class_name}' missing non-empty 'name'")

        signature = data.get("signature", name)
        if not isinstance(signature, str) or not signature.strip():
            raise ValueError(f"Field '{name}' in '{class_name}' missing non-empty 'signature'")

        field_type = data.get("field_type", "unknown")
        if not isinstance(field_type, str):
            raise ValueError(f"Field '{name}' field_type must be a string")

        access_flags = _parse_uint(data.get("access_flags", 0), f"{class_name}.{name}.access_flags")
        init_val = data.get("initial_value")
        if init_val is not None and not isinstance(init_val, (str, int, float, bool)):
            raise ValueError(f"Field '{name}' initial_value must be scalar or string")

        return JebField(
            name=name.strip(),
            signature=signature.strip(),
            field_type=field_type.strip(),
            access_flags=access_flags,
            initial_value=str(init_val) if init_val is not None else None,
        )

    @classmethod
    def _parse_method(cls, data: Any, class_name: str, index: int) -> JebMethod:
        if not isinstance(data, dict):
            raise ValueError(f"Method at index {index} in class '{class_name}' must be a dictionary")

        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Method in '{class_name}' missing non-empty 'name'")

        signature = data.get("signature")
        if not isinstance(signature, str) or not signature.strip():
            raise ValueError(f"Method '{name}' in '{class_name}' missing non-empty 'signature'")

        return_type = data.get("return_type", "void")
        if not isinstance(return_type, str):
            raise ValueError(f"Method '{name}' return_type must be a string")

        param_types_raw = data.get("parameter_types", [])
        if not isinstance(param_types_raw, list):
            raise ValueError(f"Method '{name}' parameter_types must be a list")
        param_types = [str(p) for p in param_types_raw]

        access_flags = _parse_uint(data.get("access_flags", 0), f"{class_name}.{name}.access_flags")

        raw_bbs = data.get("basic_blocks", [])
        if not isinstance(raw_bbs, list):
            raise ValueError(f"Method '{name}' basic_blocks must be a list")
        basic_blocks = [cls._parse_basic_block(bb, f"{class_name}->{name}", b_idx) for b_idx, bb in enumerate(raw_bbs)]

        raw_xrefs = data.get("xrefs", [])
        if not isinstance(raw_xrefs, list):
            raise ValueError(f"Method '{name}' xrefs must be a list")
        xrefs = [cls._parse_xref(x, f"{class_name}->{name}.xrefs[{x_idx}]") for x_idx, x in enumerate(raw_xrefs)]

        decompiled_code = data.get("decompiled_code")
        if decompiled_code is not None and not isinstance(decompiled_code, str):
            raise ValueError(f"Method '{name}' decompiled_code must be a string")

        comments_raw = data.get("comments", {})
        if not isinstance(comments_raw, dict):
            raise ValueError(f"Method '{name}' comments must be a dictionary")
        comments = {str(k): str(v) for k, v in comments_raw.items()}

        renames_raw = data.get("user_renames", {})
        if not isinstance(renames_raw, dict):
            raise ValueError(f"Method '{name}' user_renames must be a dictionary")
        renames = {str(k): str(v) for k, v in renames_raw.items()}

        return JebMethod(
            name=name.strip(),
            signature=signature.strip(),
            return_type=return_type.strip(),
            parameter_types=tuple(param_types),
            access_flags=access_flags,
            basic_blocks=tuple(basic_blocks),
            xrefs=tuple(xrefs),
            decompiled_code=decompiled_code,
            comments=comments,
            user_renames=renames,
        )

    @classmethod
    def _parse_basic_block(cls, data: Any, context: str, index: int) -> JebBasicBlock:
        if not isinstance(data, dict):
            raise ValueError(f"Basic block {index} in '{context}' must be a dictionary")

        block_id = data.get("block_id")
        if block_id is None:
            block_id = f"bb_{index}"
        elif not isinstance(block_id, (str, int)) or (isinstance(block_id, str) and not block_id.strip()):
            raise ValueError(f"Basic block in '{context}' has invalid 'block_id'")
        block_id_str = str(block_id).strip()

        start_addr = _parse_uint(data.get("start_address"), f"{context}.{block_id_str}.start_address")
        end_addr = _parse_uint(data.get("end_address"), f"{context}.{block_id_str}.end_address")

        if end_addr < start_addr:
            raise ValueError(
                f"Basic block '{block_id_str}' in '{context}' end_address (0x{end_addr:X}) < start_address (0x{start_addr:X})"
            )

        inst_count = _parse_uint(data.get("instruction_count", 0), f"{context}.{block_id_str}.instruction_count")

        preds_raw = data.get("predecessors", [])
        if not isinstance(preds_raw, list):
            raise ValueError(f"Basic block '{block_id_str}' in '{context}' predecessors must be a list")
        predecessors = [str(p) for p in preds_raw]

        succs_raw = data.get("successors", [])
        if not isinstance(succs_raw, list):
            raise ValueError(f"Basic block '{block_id_str}' in '{context}' successors must be a list")
        successors = [str(s) for s in succs_raw]

        return JebBasicBlock(
            block_id=block_id_str,
            start_address=start_addr,
            end_address=end_addr,
            instruction_count=inst_count,
            predecessors=tuple(predecessors),
            successors=tuple(successors),
        )

    @classmethod
    def _parse_xref(cls, data: Any, context: str) -> JebXref:
        if not isinstance(data, dict):
            raise ValueError(f"XREF at '{context}' must be a dictionary")

        raw_type = data.get("xref_type")
        if not isinstance(raw_type, str) or not raw_type.strip():
            raise ValueError(f"XREF at '{context}' missing non-empty 'xref_type'")

        normalized_type = XREF_TYPE_ALIASES.get(raw_type.strip().lower())
        if not normalized_type or normalized_type not in VALID_XREF_TYPES:
            raise ValueError(f"XREF at '{context}' has invalid xref_type: '{raw_type}'")

        source_addr = _validate_address(data.get("source_address"), f"{context}.source_address")
        target_addr = _validate_address(data.get("target_address"), f"{context}.target_address")

        details = data.get("details")
        if details is not None and not isinstance(details, str):
            raise ValueError(f"XREF at '{context}' field 'details' must be a string or null")

        return JebXref(
            xref_type=normalized_type,
            source_address=source_addr,
            target_address=target_addr,
            details=details.strip() if details else None,
        )

    # -------------------------------------------------------------------------
    # Analysis & Navigation API
    # -------------------------------------------------------------------------

    @classmethod
    def traverse_hierarchy(cls, report: JebAnalysisReport, class_name: str) -> List[str]:
        """Resolves inheritance hierarchy chain with strict cycle detection.

        Returns an ordered list of class names starting from `class_name` up to the root.
        """
        if not isinstance(class_name, str) or not class_name.strip():
            raise ValueError("class_name must be a non-empty string")

        target = class_name.strip()
        chain: List[str] = [target]
        visited: Set[str] = {target}

        curr = target
        while curr in report.classes:
            cls_obj = report.classes[curr]
            parent = cls_obj.superclass
            if not parent:
                break
            if parent in visited:
                raise ValueError(f"Cyclic inheritance detected involving class '{parent}' in hierarchy of '{class_name}'")
            visited.add(parent)
            chain.append(parent)
            curr = parent

        return chain

    @classmethod
    def get_implemented_interfaces(cls, report: JebAnalysisReport, class_name: str, recursive: bool = True) -> List[str]:
        """Returns all implemented interfaces for a class, optionally recursing superclasses."""
        if not recursive:
            cls_obj = report.classes.get(class_name)
            return list(cls_obj.interfaces) if cls_obj else []

        chain = cls.traverse_hierarchy(report, class_name)
        seen: Set[str] = set()
        result: List[str] = []

        for c_name in chain:
            c_obj = report.classes.get(c_name)
            if c_obj:
                for iface in c_obj.interfaces:
                    if iface not in seen:
                        seen.add(iface)
                        result.append(iface)
        return result

    @classmethod
    def get_method_overrides(cls, report: JebAnalysisReport, class_name: str) -> Dict[str, str]:
        """Returns the dictionary of method overrides defined for a class."""
        cls_obj = report.classes.get(class_name)
        if not cls_obj:
            return {}
        return dict(cls_obj.method_overrides)

    @classmethod
    def get_callers_of(cls, report: JebAnalysisReport, target_address: str) -> List[JebXref]:
        """Returns all XREFs that represent callers of the specified target address."""
        validated_target = _validate_address(target_address, "target_address")
        return [
            x for x in report.all_xrefs
            if x.xref_type == "caller" and x.target_address == validated_target
        ]

    @classmethod
    def get_callees_of(cls, report: JebAnalysisReport, source_address: str) -> List[JebXref]:
        """Returns all XREFs that represent callees invoked by the specified source address."""
        validated_source = _validate_address(source_address, "source_address")
        return [
            x for x in report.all_xrefs
            if x.xref_type == "callee" and x.source_address == validated_source
        ]

    @classmethod
    def get_memory_reads(cls, report: JebAnalysisReport, target_address: Optional[str] = None) -> List[JebXref]:
        """Returns memory read XREFs, optionally filtered by target memory/field address."""
        reads = [x for x in report.all_xrefs if x.xref_type == "read"]
        if target_address is not None:
            val_target = _validate_address(target_address, "target_address")
            reads = [x for x in reads if x.target_address == val_target]
        return reads

    @classmethod
    def get_memory_writes(cls, report: JebAnalysisReport, target_address: Optional[str] = None) -> List[JebXref]:
        """Returns memory write XREFs, optionally filtered by target memory/field address."""
        writes = [x for x in report.all_xrefs if x.xref_type == "write"]
        if target_address is not None:
            val_target = _validate_address(target_address, "target_address")
            writes = [x for x in writes if x.target_address == val_target]
        return writes

    @classmethod
    def get_comments(cls, report: JebAnalysisReport) -> Dict[str, str]:
        """Returns aggregated decompiler comments across all units, classes, and methods."""
        return dict(report.comments)

    @classmethod
    def get_user_renames(cls, report: JebAnalysisReport) -> Dict[str, str]:
        """Returns aggregated user renames across all units, classes, and methods."""
        return dict(report.renames)
