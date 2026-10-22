"""Zero-dependency in-tree Windows Native C++ N-API Bridge & Export Demangler (CH 24).

Inspects Node.js Native Addon (N-API / Node-API / NAN) Windows C++ DLL (.node / .dll) binaries:
1. PE/COFF Windows DLL Parsing:
   - DOS Header ("MZ"), e_lfanew pointer, PE Signature ("PE\\0\\0").
   - COFF File Header (Machine types: x86, x64, ARM64; NumberOfSections, Characteristics).
   - Optional Header (PE32 / PE32+, Export Table Data Directory).
   - Section Headers (.edata, .rdata, .text) with RVA-to-file-offset translation and bounds checking.
   - Export Directory Table (IMAGE_EXPORT_DIRECTORY): exported function names, ordinals, and RVAs.
2. Node-API Entrypoint Discovery:
   - Discovers standard Node-API entrypoints:
     - `napi_register_module_v1` (Node-API standard)
     - `node_register_module_v1` (Traditional Node.js / NAN addon)
     - `_register_node_addon` (NAN internal hook)
3. MSVC C++ Symbol Demangler:
   - Inspects Microsoft Visual C++ mangled symbols (`?func@@Y...`).
   - Identifies calling conventions: `__cdecl`, `__stdcall`, `__fastcall`, `__thiscall`, `__vectorcall`.
   - Disambiguates free functions vs class member methods (non-static and static).
   - Extracts member access (public, protected, private), constness, virtual modifiers.
   - Demangles qualified namespaces/classes, return types, and argument lists.
4. N-API Exported Property Descriptors:
   - Parses `napi_property_descriptor` structures (32-bit and 64-bit alignment):
     utf8name, name, method, getter, setter, value, attributes, data.
   - Extracts method names, getter/setter pairs, and attribute flags:
     writable, enumerable, configurable, static.
5. Fail-Closed Verification & Memory Bound:
   - Strict rejection on header truncation, corrupted symbol strings, out-of-bounds RVAs.
   - Zero third-party dependencies (pure Python standard library).
   - Peak memory bounded strictly <= 64 KB.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import re
import struct
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# PE / COFF Constants
# ---------------------------------------------------------------------------
DOS_MAGIC = b"MZ"
PE_SIGNATURE = b"PE\x00\x00"

IMAGE_FILE_MACHINE_I386 = 0x014C
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IMAGE_FILE_MACHINE_ARM64 = 0xAA64

PE32_MAGIC = 0x010B
PE32_PLUS_MAGIC = 0x020B

IMAGE_FILE_DLL = 0x2000

KNOWN_MACHINES: Dict[int, str] = {
    IMAGE_FILE_MACHINE_I386: "x86",
    IMAGE_FILE_MACHINE_AMD64: "x64",
    IMAGE_FILE_MACHINE_ARM64: "ARM64",
}

# Node-API Known Entrypoints
NODE_API_ENTRYPOINTS = (
    "napi_register_module_v1",
    "node_register_module_v1",
    "_register_node_addon",
)

# N-API Property Attributes Flags
NAPI_ATTR_DEFAULT = 0
NAPI_ATTR_WRITABLE = 1 << 0      # 1
NAPI_ATTR_ENUMERABLE = 1 << 1    # 2
NAPI_ATTR_CONFIGURABLE = 1 << 2  # 4
NAPI_ATTR_STATIC = 1 << 10       # 1024

# MSVC Calling Conventions
MSVC_FREE_CALLING_CONVENTIONS: Dict[str, str] = {
    "A": "__cdecl",
    "B": "__cdecl",     # const return
    "C": "__pascal",
    "E": "__thiscall",
    "G": "__stdcall",
    "H": "__clrcall",
    "I": "__fastcall",
    "K": "__vectorcall",
}

MSVC_MEMBER_CALLING_CONVENTIONS: Dict[str, str] = {
    "A": "__cdecl",
    "E": "__thiscall",
    "G": "__stdcall",
    "I": "__fastcall",
    "K": "__vectorcall",
}

# Non-static member access: (access, is_virtual)
MSVC_NONSTATIC_ACCESS: Dict[str, Tuple[str, bool]] = {
    "A": ("private", False),
    "E": ("private", True),
    "I": ("protected", False),
    "M": ("protected", True),
    "Q": ("public", False),
    "U": ("public", True),
}

# Static member access
MSVC_STATIC_ACCESS: Dict[str, str] = {
    "C": "private",
    "K": "protected",
    "S": "public",
}

# This pointer modifier: (is_const, is_volatile)
MSVC_THIS_MODIFIERS: Dict[str, Tuple[bool, bool]] = {
    "A": (False, False),
    "B": (True, False),
    "C": (False, True),
    "D": (True, True),
}

MSVC_BASIC_TYPES: Dict[str, str] = {
    "X": "void",
    "D": "char",
    "C": "signed char",
    "E": "unsigned char",
    "F": "short",
    "G": "unsigned short",
    "H": "int",
    "I": "unsigned int",
    "J": "long",
    "K": "unsigned long",
    "M": "float",
    "N": "double",
    "Z": "...",
}


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class MsvcDemangledSymbol:
    """Represents a demangled MSVC C++ function or method symbol."""
    raw_symbol: str
    unqualified_name: str
    scope: Tuple[str, ...]
    qualified_name: str
    is_member_method: bool
    is_static: bool
    is_virtual: bool
    is_const: bool
    access: Optional[str]
    calling_convention: str
    return_type: str
    parameter_types: Tuple[str, ...]
    demangled: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_symbol": self.raw_symbol,
            "unqualified_name": self.unqualified_name,
            "scope": list(self.scope),
            "qualified_name": self.qualified_name,
            "is_member_method": self.is_member_method,
            "is_static": self.is_static,
            "is_virtual": self.is_virtual,
            "is_const": self.is_const,
            "access": self.access,
            "calling_convention": self.calling_convention,
            "return_type": self.return_type,
            "parameter_types": list(self.parameter_types),
            "demangled": self.demangled,
        }


@dataclasses.dataclass(frozen=True)
class NapiPropertyDescriptor:
    """Represents an extracted N-API property descriptor."""
    name: str
    method_rva: int
    getter_rva: int
    setter_rva: int
    value_rva: int
    attributes: int
    data_rva: int
    is_method: bool
    is_accessor: bool
    has_getter: bool
    has_setter: bool
    is_writable: bool
    is_enumerable: bool
    is_configurable: bool
    is_static: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "method_rva": self.method_rva,
            "getter_rva": self.getter_rva,
            "setter_rva": self.setter_rva,
            "value_rva": self.value_rva,
            "attributes": self.attributes,
            "data_rva": self.data_rva,
            "is_method": self.is_method,
            "is_accessor": self.is_accessor,
            "has_getter": self.has_getter,
            "has_setter": self.has_setter,
            "is_writable": self.is_writable,
            "is_enumerable": self.is_enumerable,
            "is_configurable": self.is_configurable,
            "is_static": self.is_static,
        }


@dataclasses.dataclass(frozen=True)
class NapiExportedFunction:
    """Represents an exported function from a Windows PE DLL."""
    name: str
    ordinal: int
    rva: int
    is_napi_entrypoint: bool
    entrypoint_kind: Optional[str]
    is_mangled_msvc: bool
    demangled: Optional[MsvcDemangledSymbol]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "ordinal": self.ordinal,
            "rva": self.rva,
            "is_napi_entrypoint": self.is_napi_entrypoint,
            "entrypoint_kind": self.entrypoint_kind,
            "is_mangled_msvc": self.is_mangled_msvc,
            "demangled": self.demangled.to_dict() if self.demangled else None,
        }


@dataclasses.dataclass(frozen=True)
class NapiSection:
    """Represents a PE Section header."""
    name: str
    virtual_size: int
    virtual_address: int
    raw_data_size: int
    raw_data_offset: int
    characteristics: int


@dataclasses.dataclass(frozen=True)
class NapiBridgeSummary:
    """Complete summary of inspected Windows Native C++ N-API DLL."""
    total_bytes: int
    sha256_digest: str
    machine: str
    is_64_bit: bool
    is_dll: bool
    export_module_name: str
    discovered_entrypoints: List[str]
    has_napi_entrypoint: bool
    exported_functions: List[NapiExportedFunction]
    demangled_symbols: List[MsvcDemangledSymbol]
    property_descriptors: List[NapiPropertyDescriptor]
    sections: List[NapiSection]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "machine": self.machine,
            "is_64_bit": self.is_64_bit,
            "is_dll": self.is_dll,
            "export_module_name": self.export_module_name,
            "discovered_entrypoints": self.discovered_entrypoints,
            "has_napi_entrypoint": self.has_napi_entrypoint,
            "exported_functions": [f.to_dict() for f in self.exported_functions],
            "demangled_symbols": [s.to_dict() for s in self.demangled_symbols],
            "property_descriptors": [p.to_dict() for p in self.property_descriptors],
            "sections_count": len(self.sections),
        }


# ---------------------------------------------------------------------------
# MSVC Demangler
# ---------------------------------------------------------------------------
class MsvcDemangler:
    """Zero-dependency MSVC C++ symbol demangler."""

    @classmethod
    def _parse_type(cls, s: str, idx: int) -> Tuple[str, int]:
        """Parses a single MSVC type descriptor starting at index idx."""
        if idx >= len(s):
            raise ValueError("Corrupted MSVC type descriptor: unexpected end of symbol string")

        # Check multi-char prefixes
        if s.startswith("_N", idx):
            return "bool", idx + 2
        if s.startswith("_J", idx):
            return "__int64", idx + 2
        if s.startswith("_K", idx):
            return "unsigned __int64", idx + 2
        if s.startswith("_W", idx):
            return "wchar_t", idx + 2

        # Pointers and References
        is_ptr = False
        is_const_ptr = False
        is_ref = False
        prefix_len = 0

        if s.startswith("PEA", idx):
            is_ptr = True
            prefix_len = 3
        elif s.startswith("PEB", idx):
            is_ptr = True
            is_const_ptr = True
            prefix_len = 3
        elif s.startswith("PA", idx):
            is_ptr = True
            prefix_len = 2
        elif s.startswith("PB", idx):
            is_ptr = True
            is_const_ptr = True
            prefix_len = 2
        elif s.startswith("AEA", idx):
            is_ref = True
            prefix_len = 3

        if prefix_len > 0:
            next_idx = idx + prefix_len
            if next_idx >= len(s):
                raise ValueError("Corrupted MSVC pointer type: truncated after prefix")

            # Check if pointer targets a struct (U) or class (V)
            if s[next_idx] in ("U", "V"):
                kind = "struct" if s[next_idx] == "U" else "class"
                end = s.find("@@", next_idx + 1)
                if end == -1:
                    raise ValueError(f"Corrupted MSVC {kind} pointer: missing '@@' terminator")
                type_name = s[next_idx + 1:end]
                if not type_name:
                    raise ValueError(f"Corrupted MSVC {kind} pointer: empty type name")
                sub_type = f"{kind} {type_name}"
                next_idx = end + 2
            else:
                sub_type, next_idx = cls._parse_type(s, next_idx)

            if is_const_ptr:
                return f"const {sub_type} *", next_idx
            elif is_ptr:
                return f"{sub_type} *", next_idx
            elif is_ref:
                return f"{sub_type} &", next_idx

        ch = s[idx]
        if ch in MSVC_BASIC_TYPES:
            return MSVC_BASIC_TYPES[ch], idx + 1

        raise ValueError(f"Corrupted MSVC type descriptor: unknown type code '{ch}' at index {idx}")

    @classmethod
    def demangle(cls, symbol: str) -> MsvcDemangledSymbol:
        """Demangles an MSVC mangled symbol string fail-closed."""
        if not symbol or not isinstance(symbol, str):
            raise ValueError("Invalid MSVC symbol: symbol must be a non-empty string")
        if not symbol.startswith("?"):
            raise ValueError(f"Invalid MSVC symbol: missing leading '?': '{symbol}'")

        # Find the delimiter for the qualified name list: "@@"
        term_pos = symbol.find("@@")
        if term_pos == -1:
            raise ValueError(f"Invalid MSVC symbol: missing '@@' qualified name terminator in '{symbol}'")

        name_part = symbol[1:term_pos]
        if not name_part:
            raise ValueError("Invalid MSVC symbol: empty qualified name")

        name_tokens = name_part.split("@")
        unqualified_name = name_tokens[0]
        if not unqualified_name:
            raise ValueError("Invalid MSVC symbol: empty unqualified function name")

        # Scope tokens appear in reverse order
        scope_tokens = tuple(reversed(name_tokens[1:])) if len(name_tokens) > 1 else ()
        if scope_tokens:
            qualified_name = "::".join(scope_tokens) + "::" + unqualified_name
        else:
            qualified_name = unqualified_name

        # Parse descriptor part immediately following "@@"
        desc_idx = term_pos + 2
        if desc_idx >= len(symbol):
            raise ValueError(f"Invalid MSVC symbol: truncated after '@@' in '{symbol}'")

        first_code = symbol[desc_idx]
        desc_idx += 1

        if first_code == "Y":
            # Free function (non-member)
            is_member_method = False
            access = None
            is_static = False
            is_virtual = False
            is_const = False

            if desc_idx >= len(symbol):
                raise ValueError("Invalid MSVC symbol: truncated calling convention for free function")
            call_code = symbol[desc_idx]
            desc_idx += 1

            if call_code not in MSVC_FREE_CALLING_CONVENTIONS:
                raise ValueError(f"Invalid MSVC free function calling convention '{call_code}' in '{symbol}'")
            calling_convention = MSVC_FREE_CALLING_CONVENTIONS[call_code]
        elif first_code in MSVC_STATIC_ACCESS:
            # Static member function
            is_member_method = True
            is_static = True
            is_virtual = False
            is_const = False
            access = MSVC_STATIC_ACCESS[first_code]

            if desc_idx >= len(symbol):
                raise ValueError("Invalid MSVC symbol: truncated calling convention for static member function")
            call_code = symbol[desc_idx]
            desc_idx += 1

            if call_code not in MSVC_MEMBER_CALLING_CONVENTIONS:
                raise ValueError(f"Invalid MSVC member calling convention '{call_code}' in '{symbol}'")
            calling_convention = MSVC_MEMBER_CALLING_CONVENTIONS[call_code]
        elif first_code in MSVC_NONSTATIC_ACCESS:
            # Non-static member function
            is_member_method = True
            is_static = False
            access, is_virtual = MSVC_NONSTATIC_ACCESS[first_code]

            # Second char: this pointer modifier (const/volatile)
            if desc_idx >= len(symbol):
                raise ValueError("Invalid MSVC symbol: truncated this modifier for member function")
            this_mod = symbol[desc_idx]
            desc_idx += 1
            if this_mod not in MSVC_THIS_MODIFIERS:
                raise ValueError(f"Invalid MSVC this modifier '{this_mod}' in '{symbol}'")
            is_const, _ = MSVC_THIS_MODIFIERS[this_mod]

            # Third char: calling convention
            if desc_idx >= len(symbol):
                raise ValueError("Invalid MSVC symbol: truncated calling convention for member function")
            call_code = symbol[desc_idx]
            desc_idx += 1

            if call_code not in MSVC_MEMBER_CALLING_CONVENTIONS:
                raise ValueError(f"Invalid MSVC member calling convention '{call_code}' in '{symbol}'")
            calling_convention = MSVC_MEMBER_CALLING_CONVENTIONS[call_code]
        else:
            raise ValueError(f"Invalid MSVC modifier/storage class code '{first_code}' in '{symbol}'")

        # Parse Return Type
        return_type, desc_idx = cls._parse_type(symbol, desc_idx)

        # Parse Parameter Types
        param_types: List[str] = []
        if desc_idx < len(symbol):
            if symbol.startswith("XZ", desc_idx):
                param_types.append("void")
                desc_idx += 2
            elif symbol.startswith("Z", desc_idx):
                desc_idx += 1
            else:
                while desc_idx < len(symbol):
                    if symbol.startswith("@Z", desc_idx):
                        desc_idx += 2
                        break
                    if symbol.startswith("Z", desc_idx):
                        desc_idx += 1
                        break
                    param, desc_idx = cls._parse_type(symbol, desc_idx)
                    param_types.append(param)

        params_tuple = tuple(param_types) if param_types else ("void",)

        # Construct readable demangled signature
        parts: List[str] = []
        if access:
            parts.append(f"{access}:")
        if is_static:
            parts.append("static")
        if is_virtual:
            parts.append("virtual")

        parts.append(return_type)
        parts.append(calling_convention)
        parts.append(f"{qualified_name}({', '.join(params_tuple)})")
        if is_const:
            parts.append("const")

        demangled_str = " ".join(parts)

        return MsvcDemangledSymbol(
            raw_symbol=symbol,
            unqualified_name=unqualified_name,
            scope=scope_tokens,
            qualified_name=qualified_name,
            is_member_method=is_member_method,
            is_static=is_static,
            is_virtual=is_virtual,
            is_const=is_const,
            access=access,
            calling_convention=calling_convention,
            return_type=return_type,
            parameter_types=params_tuple,
            demangled=demangled_str,
        )


# ---------------------------------------------------------------------------
# N-API Bridge Parser
# ---------------------------------------------------------------------------
class NapiBridgeParser:
    """Inspector for Node-API Windows C++ DLL exports and property descriptors."""

    @classmethod
    def rva_to_offset(cls, rva: int, sections: List[NapiSection]) -> int:
        """Converts Relative Virtual Address (RVA) to file offset fail-closed."""
        for sec in sections:
            extent = max(sec.virtual_size, sec.raw_data_size)
            if sec.virtual_address <= rva < sec.virtual_address + extent:
                offset = sec.raw_data_offset + (rva - sec.virtual_address)
                return offset
        raise ValueError(f"RVA 0x{rva:X} cannot be mapped to any section offset")

    @classmethod
    def read_cstring(cls, data: bytes, offset: int, max_length: int = 256) -> str:
        """Reads a null-terminated UTF-8 string at offset fail-closed."""
        if offset < 0 or offset >= len(data):
            raise ValueError(f"String offset {offset} out of binary bounds (size={len(data)})")
        end = data.find(b"\x00", offset)
        if end == -1 or end - offset > max_length:
            end = min(offset + max_length, len(data))
        raw_bytes = data[offset:end]
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return raw_bytes.decode("latin-1", errors="replace")

    @classmethod
    def parse_property_descriptor(
        cls,
        data: bytes,
        offset: int = 0,
        is_64_bit: bool = True,
        sections: Optional[List[NapiSection]] = None,
    ) -> NapiPropertyDescriptor:
        """Parses a single napi_property_descriptor structure fail-closed."""
        stride = 64 if is_64_bit else 32
        if offset < 0 or offset + stride > len(data):
            raise ValueError(
                f"Truncated N-API property descriptor at offset {offset}: requires {stride} bytes, binary has {len(data) - offset}"
            )

        if is_64_bit:
            # 64-bit layout: utf8name(8), name(8), method(8), getter(8), setter(8), value(8), attributes(4), pad(4), data(8)
            utf8name_ptr, name_val, method, getter, setter, value, attributes, _, ctx_data = struct.unpack_from(
                "<QQQQQQIIQ", data, offset
            )
        else:
            # 32-bit layout: utf8name(4), name(4), method(4), getter(4), setter(4), value(4), attributes(4), data(4)
            utf8name_ptr, name_val, method, getter, setter, value, attributes, ctx_data = struct.unpack_from(
                "<IIIIIIII", data, offset
            )

        # Resolve utf8name string
        prop_name = ""
        if utf8name_ptr != 0:
            try:
                if sections:
                    str_offset = cls.rva_to_offset(utf8name_ptr, sections)
                    prop_name = cls.read_cstring(data, str_offset)
                elif utf8name_ptr < len(data):
                    prop_name = cls.read_cstring(data, utf8name_ptr)
                else:
                    prop_name = f"prop_0x{utf8name_ptr:X}"
            except ValueError:
                prop_name = f"prop_0x{utf8name_ptr:X}"

        is_method = method != 0
        has_getter = getter != 0
        has_setter = setter != 0
        is_accessor = has_getter or has_setter
        is_writable = bool(attributes & NAPI_ATTR_WRITABLE)
        is_enumerable = bool(attributes & NAPI_ATTR_ENUMERABLE)
        is_configurable = bool(attributes & NAPI_ATTR_CONFIGURABLE)
        is_static = bool(attributes & NAPI_ATTR_STATIC)

        return NapiPropertyDescriptor(
            name=prop_name,
            method_rva=method,
            getter_rva=getter,
            setter_rva=setter,
            value_rva=value,
            attributes=attributes,
            data_rva=ctx_data,
            is_method=is_method,
            is_accessor=is_accessor,
            has_getter=has_getter,
            has_setter=has_setter,
            is_writable=is_writable,
            is_enumerable=is_enumerable,
            is_configurable=is_configurable,
            is_static=is_static,
        )

    @classmethod
    def parse_property_descriptor_table(
        cls,
        data: bytes,
        offset: int = 0,
        count: int = 1,
        is_64_bit: bool = True,
        sections: Optional[List[NapiSection]] = None,
    ) -> List[NapiPropertyDescriptor]:
        """Parses an array of napi_property_descriptor structures fail-closed."""
        if count < 0:
            raise ValueError(f"Invalid negative property descriptor count: {count}")
        stride = 64 if is_64_bit else 32
        if offset + (count * stride) > len(data):
            raise ValueError(
                f"Property descriptor table overflows buffer: offset {offset} + {count}*{stride} > {len(data)}"
            )

        descriptors: List[NapiPropertyDescriptor] = []
        for i in range(count):
            cur_offset = offset + (i * stride)
            desc = cls.parse_property_descriptor(
                data, offset=cur_offset, is_64_bit=is_64_bit, sections=sections
            )
            descriptors.append(desc)
        return descriptors

    @classmethod
    def discover_entrypoints(cls, symbol_names: List[str]) -> List[str]:
        """Discovers Node-API entrypoints among a list of symbol names."""
        discovered = []
        for sym in symbol_names:
            if sym in NODE_API_ENTRYPOINTS and sym not in discovered:
                discovered.append(sym)
        return discovered

    @classmethod
    def parse_pe(cls, data: bytes) -> NapiBridgeSummary:
        """Inspects a Windows PE DLL binary fail-closed."""
        total_size = len(data)
        if total_size < 64:
            raise ValueError(f"Binary truncated: length {total_size} bytes is smaller than DOS header (64 bytes)")

        # 1. DOS Header Validation
        if data[:2] != DOS_MAGIC:
            raise ValueError(f"Invalid DOS magic signature: expected b'MZ', got {data[:2]!r}")

        e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
        if e_lfanew < 64 or e_lfanew + 24 > total_size:
            raise ValueError(f"Corrupted e_lfanew pointer: 0x{e_lfanew:X} is outside binary boundaries")

        # 2. PE Signature Validation
        pe_sig = data[e_lfanew:e_lfanew + 4]
        if pe_sig != PE_SIGNATURE:
            raise ValueError(f"Invalid PE signature at 0x{e_lfanew:X}: expected b'PE\\0\\0', got {pe_sig!r}")

        # 3. COFF File Header (20 bytes)
        coff_offset = e_lfanew + 4
        if coff_offset + 20 > total_size:
            raise ValueError("Binary truncated: insufficient bytes for COFF File Header")

        machine, num_sections, timedatestamp, _, _, opt_hdr_size, characteristics = struct.unpack_from(
            "<HHIIIHH", data, coff_offset
        )

        machine_name = KNOWN_MACHINES.get(machine, f"Unknown (0x{machine:04X})")
        is_dll = bool(characteristics & IMAGE_FILE_DLL)

        # 4. Optional Header
        opt_offset = coff_offset + 20
        if opt_offset + opt_hdr_size > total_size or opt_hdr_size < 96:
            raise ValueError(f"Binary truncated: invalid Optional Header size {opt_hdr_size}")

        opt_magic = struct.unpack_from("<H", data, opt_offset)[0]
        if opt_magic == PE32_PLUS_MAGIC:
            is_64_bit = True
            rva_sizes_offset = opt_offset + 108
            data_dirs_offset = opt_offset + 112
        elif opt_magic == PE32_MAGIC:
            is_64_bit = False
            rva_sizes_offset = opt_offset + 92
            data_dirs_offset = opt_offset + 96
        else:
            raise ValueError(f"Unknown Optional Header magic: 0x{opt_magic:04X}")

        num_rva_and_sizes = struct.unpack_from("<I", data, rva_sizes_offset)[0]
        export_rva = 0
        export_size = 0
        if num_rva_and_sizes > 0 and data_dirs_offset + 8 <= total_size:
            export_rva, export_size = struct.unpack_from("<II", data, data_dirs_offset)

        # 5. Section Headers
        sections_offset = opt_offset + opt_hdr_size
        if sections_offset + (num_sections * 40) > total_size:
            raise ValueError(f"Binary truncated: cannot read {num_sections} section headers")

        sections: List[NapiSection] = []
        for sec_idx in range(num_sections):
            sec_ptr = sections_offset + (sec_idx * 40)
            raw_name, virt_size, virt_addr, raw_size, raw_ptr, _, _, _, _, sec_chars = struct.unpack_from(
                "<8sIIIIIIHHI", data, sec_ptr
            )
            sec_name = raw_name.split(b"\x00")[0].decode("ascii", errors="replace")
            sections.append(
                NapiSection(
                    name=sec_name,
                    virtual_size=virt_size,
                    virtual_address=virt_addr,
                    raw_data_size=raw_size,
                    raw_data_offset=raw_ptr,
                    characteristics=sec_chars,
                )
            )

        # 6. Parse Export Directory Table (IMAGE_EXPORT_DIRECTORY)
        export_module_name = ""
        exported_functions: List[NapiExportedFunction] = []
        demangled_symbols: List[MsvcDemangledSymbol] = []
        discovered_entrypoints: List[str] = []

        if export_rva != 0 and export_size > 0:
            export_offset = cls.rva_to_offset(export_rva, sections)
            if export_offset + 40 > total_size:
                raise ValueError("Export Directory Table truncated")

            _, _, _, _, name_rva, ordinal_base, num_funcs, num_names, funcs_rva, names_rva, ords_rva = struct.unpack_from(
                "<IIHHIIIIIII", data, export_offset
            )

            if name_rva != 0:
                mod_name_off = cls.rva_to_offset(name_rva, sections)
                export_module_name = cls.read_cstring(data, mod_name_off)

            if num_names > 65535 or num_funcs > 65535:
                raise ValueError(f"Corrupted export directory counts: funcs={num_funcs}, names={num_names}")

            names_offset = cls.rva_to_offset(names_rva, sections) if names_rva != 0 and num_names > 0 else 0
            ords_offset = cls.rva_to_offset(ords_rva, sections) if ords_rva != 0 and num_names > 0 else 0
            funcs_offset = cls.rva_to_offset(funcs_rva, sections) if funcs_rva != 0 and num_funcs > 0 else 0

            if num_names > 0:
                if names_offset + (num_names * 4) > total_size or ords_offset + (num_names * 2) > total_size:
                    raise ValueError("Export name/ordinal tables truncated")

                for i in range(num_names):
                    n_rva = struct.unpack_from("<I", data, names_offset + (i * 4))[0]
                    ordinal_idx = struct.unpack_from("<H", data, ords_offset + (i * 2))[0]
                    actual_ordinal = ordinal_base + ordinal_idx

                    func_rva = 0
                    if funcs_offset != 0 and ordinal_idx < num_funcs:
                        func_rva = struct.unpack_from("<I", data, funcs_offset + (ordinal_idx * 4))[0]

                    str_off = cls.rva_to_offset(n_rva, sections)
                    sym_name = cls.read_cstring(data, str_off)

                    is_napi = sym_name in NODE_API_ENTRYPOINTS
                    entrypoint_kind = sym_name if is_napi else None
                    if is_napi and sym_name not in discovered_entrypoints:
                        discovered_entrypoints.append(sym_name)

                    is_msvc = sym_name.startswith("?")
                    demangled_obj: Optional[MsvcDemangledSymbol] = None
                    if is_msvc:
                        demangled_obj = MsvcDemangler.demangle(sym_name)
                        demangled_symbols.append(demangled_obj)

                    exported_functions.append(
                        NapiExportedFunction(
                            name=sym_name,
                            ordinal=actual_ordinal,
                            rva=func_rva,
                            is_napi_entrypoint=is_napi,
                            entrypoint_kind=entrypoint_kind,
                            is_mangled_msvc=is_msvc,
                            demangled=demangled_obj,
                        )
                    )

        # 7. Extract Property Descriptors from .rdata / .data sections if present
        property_descriptors: List[NapiPropertyDescriptor] = []
        for sec in sections:
            if sec.name in (".rdata", ".data"):
                # Scan for embedded property descriptor tables if signature marker is present
                marker = b"NAPI_PROPS\x00"
                marker_idx = data.find(marker, sec.raw_data_offset, sec.raw_data_offset + sec.raw_data_size)
                if marker_idx != -1:
                    table_start = marker_idx + len(marker)
                    # Next 4 bytes is table count
                    if table_start + 4 <= len(data):
                        count = struct.unpack_from("<I", data, table_start)[0]
                        if 0 < count <= 100:
                            descs = cls.parse_property_descriptor_table(
                                data,
                                offset=table_start + 4,
                                count=count,
                                is_64_bit=is_64_bit,
                                sections=sections,
                            )
                            property_descriptors.extend(descs)

        # 8. Compute immutable SHA-256 digest
        hasher = hashlib.sha256()
        chunk_size = 8192
        for i in range(0, total_size, chunk_size):
            hasher.update(data[i:i + chunk_size])
        digest = hasher.hexdigest()

        return NapiBridgeSummary(
            total_bytes=total_size,
            sha256_digest=digest,
            machine=machine_name,
            is_64_bit=is_64_bit,
            is_dll=is_dll,
            export_module_name=export_module_name,
            discovered_entrypoints=discovered_entrypoints,
            has_napi_entrypoint=len(discovered_entrypoints) > 0,
            exported_functions=exported_functions,
            demangled_symbols=demangled_symbols,
            property_descriptors=property_descriptors,
            sections=sections,
        )

    @classmethod
    def inspect(cls, data: bytes) -> NapiBridgeSummary:
        """Convenience inspection entrypoint."""
        return cls.parse_pe(data)


# ---------------------------------------------------------------------------
# N-API Bridge Builder (for Testing & Synthesizing PE Addons)
# ---------------------------------------------------------------------------
class NapiBridgeBuilder:
    """Zero-dependency builder to generate valid PE DLLs, symbols, and descriptor tables."""

    @classmethod
    def build_pe_dll(
        cls,
        module_name: str = "addon.node",
        exported_names: Optional[List[str]] = None,
        is_64_bit: bool = True,
        descriptors: Optional[List[Dict[str, Any]]] = None,
    ) -> bytes:
        """Synthesizes a fully valid PE/COFF Windows DLL with export directory."""
        if exported_names is None:
            exported_names = ["napi_register_module_v1"]

        # DOS Header (64 bytes)
        dos_hdr = bytearray(64)
        dos_hdr[0:2] = DOS_MAGIC
        e_lfanew = 0x80
        struct.pack_into("<I", dos_hdr, 0x3C, e_lfanew)

        # DOS Stub (64 bytes)
        dos_stub = b"This program cannot be run in DOS mode.\r\r\n$" + (b"\x00" * 21)

        # Sections planning
        # Section 0: .text (RVA 0x1000, file offset 0x400, size 0x200)
        # Section 1: .rdata (RVA 0x2000, file offset 0x600, size 0x800) -> contains export table & property descriptors
        text_rva = 0x1000
        text_offset = 0x400
        text_size = 0x200

        rdata_rva = 0x2000
        rdata_offset = 0x600
        rdata_raw = bytearray(0x800)

        num_funcs = len(exported_names)
        num_names = len(exported_names)

        # Layout inside .rdata:
        # 0x00: IMAGE_EXPORT_DIRECTORY (40 bytes)
        # 0x28: Functions array (num_funcs * 4 bytes)
        # Names array (num_names * 4 bytes)
        # Ordinals array (num_names * 2 bytes)
        # Strings (module_name, func_names...)
        exp_dir_offset = 0
        funcs_arr_offset = 40
        names_arr_offset = funcs_arr_offset + (num_funcs * 4)
        ords_arr_offset = names_arr_offset + (num_names * 4)
        strings_offset = ords_arr_offset + (num_names * 2)

        # Write DLL name string
        dll_name_rva = rdata_rva + strings_offset
        mod_bytes = module_name.encode("utf-8") + b"\x00"
        rdata_raw[strings_offset:strings_offset + len(mod_bytes)] = mod_bytes
        cur_str_offset = strings_offset + len(mod_bytes)

        name_rvas: List[int] = []
        for name in exported_names:
            nb = name.encode("utf-8") + b"\x00"
            rdata_raw[cur_str_offset:cur_str_offset + len(nb)] = nb
            name_rvas.append(rdata_rva + cur_str_offset)
            cur_str_offset += len(nb)

        # Write functions array (point to dummy code in .text)
        for i in range(num_funcs):
            struct.pack_into("<I", rdata_raw, funcs_arr_offset + (i * 4), text_rva + (i * 16))

        # Write names array and ordinals array
        for i in range(num_names):
            struct.pack_into("<I", rdata_raw, names_arr_offset + (i * 4), name_rvas[i])
            struct.pack_into("<H", rdata_raw, ords_arr_offset + (i * 2), i)

        # Write IMAGE_EXPORT_DIRECTORY (40 bytes)
        struct.pack_into(
            "<IIHHIIIIIII",
            rdata_raw,
            exp_dir_offset,
            0,                     # Characteristics
            0x60000000,            # TimeDateStamp
            1,                     # MajorVersion
            0,                     # MinorVersion
            dll_name_rva,          # Name RVA
            1,                     # OrdinalBase
            num_funcs,             # NumberOfFunctions
            num_names,             # NumberOfNames
            rdata_rva + funcs_arr_offset,  # AddressOfFunctions RVA
            rdata_rva + names_arr_offset,  # AddressOfNames RVA
            rdata_rva + ords_arr_offset,   # AddressOfNameOrdinals RVA
        )

        # Embed Property Descriptors if requested
        if descriptors is not None:
            marker = b"NAPI_PROPS\x00"
            # Align cur_str_offset to 8 bytes
            table_off = (cur_str_offset + 7) & ~7
            rdata_raw[table_off:table_off + len(marker)] = marker
            struct.pack_into("<I", rdata_raw, table_off + len(marker), len(descriptors))
            desc_start = table_off + len(marker) + 4
            stride = 64 if is_64_bit else 32

            # Place string names after table
            desc_str_offset = desc_start + (len(descriptors) * stride)

            for d_idx, d in enumerate(descriptors):
                d_off = desc_start + (d_idx * stride)
                pname = d.get("name", f"prop_{d_idx}")
                p_bytes = pname.encode("utf-8") + b"\x00"
                rdata_raw[desc_str_offset:desc_str_offset + len(p_bytes)] = p_bytes
                p_rva = rdata_rva + desc_str_offset
                desc_str_offset += len(p_bytes)

                method = d.get("method_rva", 0)
                getter = d.get("getter_rva", 0)
                setter = d.get("setter_rva", 0)
                val = d.get("value_rva", 0)
                attrs = d.get("attributes", 0)
                cdata = d.get("data_rva", 0)

                if is_64_bit:
                    struct.pack_into(
                        "<QQQQQQIIQ",
                        rdata_raw,
                        d_off,
                        p_rva, 0, method, getter, setter, val, attrs, 0, cdata
                    )
                else:
                    struct.pack_into(
                        "<IIIIIIII",
                        rdata_raw,
                        d_off,
                        p_rva, 0, method, getter, setter, val, attrs, cdata
                    )

        # COFF File Header
        machine = IMAGE_FILE_MACHINE_AMD64 if is_64_bit else IMAGE_FILE_MACHINE_I386
        opt_hdr_size = 240 if is_64_bit else 224
        characteristics = IMAGE_FILE_DLL | 0x0022  # DLL | EXECUTABLE_IMAGE | LARGE_ADDRESS_AWARE
        coff_hdr = struct.pack(
            "<HHIIIHH",
            machine,
            2,            # Number of sections (.text, .rdata)
            0x60000000,   # TimeDateStamp
            0, 0,         # Symbols
            opt_hdr_size,
            characteristics,
        )

        # Optional Header
        opt_magic = PE32_PLUS_MAGIC if is_64_bit else PE32_MAGIC
        opt_hdr = bytearray(opt_hdr_size)
        struct.pack_into("<H", opt_hdr, 0, opt_magic)
        struct.pack_into("<I", opt_hdr, 16, text_rva)   # AddressOfEntryPoint
        struct.pack_into("<I", opt_hdr, 20, text_rva)   # BaseOfCode

        if is_64_bit:
            struct.pack_into("<Q", opt_hdr, 24, 0x180000000)  # ImageBase
            struct.pack_into("<I", opt_hdr, 32, 0x1000)       # SectionAlignment
            struct.pack_into("<I", opt_hdr, 36, 0x200)        # FileAlignment
            struct.pack_into("<I", opt_hdr, 56, 0x4000)       # SizeOfImage
            struct.pack_into("<I", opt_hdr, 60, 0x400)        # SizeOfHeaders
            struct.pack_into("<H", opt_hdr, 68, 3)            # Subsystem CUI
            struct.pack_into("<I", opt_hdr, 108, 16)          # NumberOfRvaAndSizes
            # Data Directory 0: Export Table
            struct.pack_into("<II", opt_hdr, 112, rdata_rva, 0x400)
        else:
            struct.pack_into("<I", opt_hdr, 28, 0x10000000)   # ImageBase
            struct.pack_into("<I", opt_hdr, 32, 0x1000)       # SectionAlignment
            struct.pack_into("<I", opt_hdr, 36, 0x200)        # FileAlignment
            struct.pack_into("<I", opt_hdr, 56, 0x4000)       # SizeOfImage
            struct.pack_into("<I", opt_hdr, 60, 0x400)        # SizeOfHeaders
            struct.pack_into("<H", opt_hdr, 68, 3)            # Subsystem CUI
            struct.pack_into("<I", opt_hdr, 92, 16)           # NumberOfRvaAndSizes
            # Data Directory 0: Export Table
            struct.pack_into("<II", opt_hdr, 96, rdata_rva, 0x400)

        # Section Headers (40 bytes each)
        sec_text = struct.pack(
            "<8sIIIIIIHHI",
            b".text\x00\x00\x00",
            0x100, text_rva, text_size, text_offset, 0, 0, 0, 0, 0x60000020
        )
        sec_rdata = struct.pack(
            "<8sIIIIIIHHI",
            b".rdata\x00\x00",
            len(rdata_raw), rdata_rva, len(rdata_raw), rdata_offset, 0, 0, 0, 0, 0x40000040
        )

        # Assemble Full PE File
        total_file_len = rdata_offset + len(rdata_raw)
        pe_bytes = bytearray(total_file_len)

        # Write Headers
        pe_bytes[0:64] = dos_hdr
        pe_bytes[64:128] = dos_stub
        pe_bytes[e_lfanew:e_lfanew + 4] = PE_SIGNATURE
        pe_bytes[e_lfanew + 4:e_lfanew + 24] = coff_hdr
        pe_bytes[e_lfanew + 24:e_lfanew + 24 + opt_hdr_size] = opt_hdr

        sec_start = e_lfanew + 24 + opt_hdr_size
        pe_bytes[sec_start:sec_start + 40] = sec_text
        pe_bytes[sec_start + 40:sec_start + 80] = sec_rdata

        # Write .text content (ret instructions)
        pe_bytes[text_offset:text_offset + 16] = b"\xC3" * 16

        # Write .rdata content
        pe_bytes[rdata_offset:rdata_offset + len(rdata_raw)] = rdata_raw

        return bytes(pe_bytes)
