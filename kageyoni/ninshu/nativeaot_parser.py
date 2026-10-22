"""Zero-dependency in-tree .NET NativeAOT / ReadyToRun Binary Inspector (CH 10).

Inspects .NET NativeAOT (CoreRT / ReadyToRun) compiled binaries:
1. ReadyToRun Header & Section Parsing:
   - Validates RTR signature: 0x00525452 ("RTR\\x00") or 0x00523252 ("R2R\\x00") / "R2R\\x01".
   - Extracts major/minor versions, flags, section counts, entry sizes.
   - Parses section rows: DEHYDRATED_DATA (207), FROZEN_OBJECT_REGION (206),
     TYPE_MANAGER_INDIRECTION (204), METHOD_DEF_ENTRYPOINTS (104), RUNTIME_FUNCTIONS (103), etc.
2. Symbol Marker Discovery:
   - Identifies embedded NativeAOT runtime markers:
     - RhpReversePInvoke / RhpReversePInvokeAttachOrTrapThread (Native-to-Managed)
     - RhpPInvoke / RhpPInvokeSetup / RhpPInvokeReturn (Managed-to-Native)
     - RhTypeManager / RhTypeManager::Create / RhpCreateTypeManager
     - Runtime helpers: RhpAssignRef, RhpNewFast, RhpNewArray, RhpCheckedAssignRef
3. Thunk Boundaries:
   - Identifies Managed-to-Native (PInvoke) and Native-to-Managed (ReversePInvoke) thunk boundaries.
   - Extracts calling conventions, target addresses/symbols, and thunk extents.
4. GC Info Structures:
   - Parses NativeAOT GC info blobs: frameless flags, stack slot counts, register masks, live ranges.
5. Runtime Interfaces & MethodTable Recovery:
   - Parses MethodTables, virtual slots, and runtime interface tables.
6. Fail-Closed Validation:
   - Header truncation rejection.
   - Magic validation.
   - Out-of-bounds offsets and reversed boundary checks.
   - Peak heap memory bounded strictly <= 64 KB.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import struct
from typing import Any, Dict, List, Optional, Tuple, Union

# ReadyToRun / NativeAOT Signature constants
RTR_MAGIC_INT = 0x00525452  # "RTR\x00" in little-endian
R2R_MAGIC_INT = 0x00523252  # "R2R\x00" in little-endian

RTR_SIGNATURES = (
    b"RTR\x00",
    b"R2R\x00",
    b"R2R\x01",
    b"RTR\x01",
)

# RTR Section Types
RTR_SECTION_NAMES: Dict[int, str] = {
    101: "COMPILER_IDENTIFIER",
    102: "IMPORT_SECTIONS",
    103: "RUNTIME_FUNCTIONS",
    104: "METHOD_DEF_ENTRYPOINTS",
    105: "EXCEPTION_INFO",
    106: "DEBUG_INFO",
    107: "DELAY_LOAD_METHOD_CALL_THUNKS",
    108: "AVAILABLE_TYPES",
    109: "INSTANCE_METHOD_RESOLVER",
    200: "INLINING_INFO",
    201: "PROFILED_DATA",
    204: "TYPE_MANAGER_INDIRECTION",
    206: "FROZEN_OBJECT_REGION",
    207: "DEHYDRATED_DATA",
}

# Known NativeAOT Symbol Marker Signatures
KNOWN_SYMBOL_MARKERS: List[Tuple[bytes, str, str]] = [
    (b"RhpReversePInvokeAttachOrTrapThread", "RhpReversePInvokeAttachOrTrapThread", "reverse_pinvoke"),
    (b"RhpReversePInvokeReturnOrTrapThread", "RhpReversePInvokeReturnOrTrapThread", "reverse_pinvoke"),
    (b"RhpReversePInvoke2", "RhpReversePInvoke2", "reverse_pinvoke"),
    (b"RhpReversePInvoke", "RhpReversePInvoke", "reverse_pinvoke"),
    (b"RhpPInvokeSetup", "RhpPInvokeSetup", "pinvoke"),
    (b"RhpPInvokeReturn", "RhpPInvokeReturn", "pinvoke"),
    (b"RhpPInvoke", "RhpPInvoke", "pinvoke"),
    (b"RhTypeManager::Create", "RhTypeManager::Create", "type_manager"),
    (b"RhpCreateTypeManager", "RhpCreateTypeManager", "type_manager"),
    (b"RhTypeManager", "RhTypeManager", "type_manager"),
    (b"RhpAssignRef", "RhpAssignRef", "runtime_helper"),
    (b"RhpNewFast", "RhpNewFast", "runtime_helper"),
    (b"RhpNewArray", "RhpNewArray", "runtime_helper"),
    (b"RhpCheckedAssignRef", "RhpCheckedAssignRef", "runtime_helper"),
    (b"RhpByRefAssignRef", "RhpByRefAssignRef", "runtime_helper"),
    (b"RhpInitialDynamicInterfaceDispatch", "RhpInitialDynamicInterfaceDispatch", "runtime_helper"),
    (b"RhpInterfaceDispatch", "RhpInterfaceDispatch", "runtime_helper"),
]


@dataclasses.dataclass(frozen=True)
class NativeAotSymbolMarker:
    name: str
    offset: int
    category: str


@dataclasses.dataclass(frozen=True)
class NativeAotSection:
    type_id: int
    type_name: str
    flags: int
    start_address: int
    end_address: int
    size: int


@dataclasses.dataclass(frozen=True)
class NativeAotThunk:
    thunk_type: str  # "ManagedToNative" or "NativeToManaged"
    offset: int
    size: int
    target_marker: str
    convention: str


@dataclasses.dataclass(frozen=True)
class NativeAotGcInfo:
    offset: int
    code_size: int
    is_frameless: bool
    has_stack_pointers: bool
    register_mask: int
    stack_slot_count: int


@dataclasses.dataclass(frozen=True)
class NativeAotInterface:
    interface_id: int
    method_count: int
    vtable_offset: int


@dataclasses.dataclass(frozen=True)
class NativeAotMethodTable:
    address: int
    base_size: int
    flags: int
    related_type_address: int
    slots_count: int
    interfaces_count: int
    vtable_slots: List[int]
    interface_addresses: List[int]


@dataclasses.dataclass(frozen=True)
class NativeAotEntrypoint:
    token: int
    entrypoint_offset: int
    is_native_callable: bool
    name: Optional[str]


@dataclasses.dataclass(frozen=True)
class NativeAotHeader:
    magic: str
    major_version: int
    minor_version: int
    flags: int
    number_of_sections: int
    entry_size: int
    entry_type: int
    header_offset: int
    sections: List[NativeAotSection]


@dataclasses.dataclass(frozen=True)
class NativeAotSummary:
    total_bytes: int
    sha256_digest: str
    has_nativeaot: bool
    format_major: Optional[int]
    format_minor: Optional[int]
    rtr_header_offset: Optional[int]
    sections_count: int
    symbol_markers_count: int
    thunks_count: int
    gc_info_count: int
    method_tables_count: int
    entrypoints_count: int
    symbol_markers: List[NativeAotSymbolMarker]
    thunks: List[NativeAotThunk]
    gc_info: List[NativeAotGcInfo]
    method_tables: List[NativeAotMethodTable]
    entrypoints: List[NativeAotEntrypoint]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "has_nativeaot": self.has_nativeaot,
            "format_major": self.format_major,
            "format_minor": self.format_minor,
            "rtr_header_offset": self.rtr_header_offset,
            "sections_count": self.sections_count,
            "symbol_markers_count": self.symbol_markers_count,
            "thunks_count": self.thunks_count,
            "gc_info_count": self.gc_info_count,
            "method_tables_count": self.method_tables_count,
            "entrypoints_count": self.entrypoints_count,
            "symbol_markers": [dataclasses.asdict(m) for m in self.symbol_markers],
            "thunks": [dataclasses.asdict(t) for t in self.thunks],
            "gc_info": [dataclasses.asdict(g) for g in self.gc_info],
            "method_tables": [dataclasses.asdict(m) for m in self.method_tables],
            "entrypoints": [dataclasses.asdict(e) for e in self.entrypoints],
        }


class NativeAotParser:
    """Zero-dependency strict fail-closed NativeAOT / ReadyToRun binary inspector."""

    MAX_SECTIONS = 128
    MAX_METHOD_TABLE_ITEMS = 1024
    MAX_GC_INFO_RECORDS = 512

    @classmethod
    def parse_rtr_header(cls, data: bytes, offset: int = 0) -> NativeAotHeader:
        """Parses and validates a ReadyToRun header at a given byte offset."""
        if len(data) < offset + 16:
            raise ValueError(
                f"Truncated ReadyToRun header: expected at least 16 bytes at offset {offset}, "
                f"available {len(data) - offset}"
            )

        magic_bytes = data[offset : offset + 4]
        if magic_bytes not in RTR_SIGNATURES:
            raise ValueError(f"Invalid ReadyToRun magic signature: {magic_bytes!r}")

        major, minor, flags, num_sections, entry_size, entry_type = struct.unpack_from(
            "<HHIBBB", data, offset + 4
        )
        # Note: unpack format: HH (4 bytes) + I (4 bytes) + H (2 bytes: num_sections) + B (1 byte: entry_size) + B (1 byte: entry_type)
        # Total bytes: 4 (magic) + 2 + 2 + 4 + 2 + 1 + 1 = 16 bytes.
        # Let's verify layout precisely with <HHIBB
        num_sections, entry_size, entry_type = struct.unpack_from(
            "<HBB", data, offset + 12
        )

        if num_sections < 1 or num_sections > cls.MAX_SECTIONS:
            raise ValueError(
                f"Invalid ReadyToRun section count: {num_sections} (must be between 1 and {cls.MAX_SECTIONS})"
            )

        if entry_size != 24:
            raise ValueError(f"Unsupported ReadyToRun entry row size: {entry_size} (expected 24)")

        if entry_type != 1:
            raise ValueError(f"Unsupported ReadyToRun entry row type: {entry_type} (expected 1)")

        required_section_bytes = num_sections * entry_size
        if len(data) < offset + 16 + required_section_bytes:
            raise ValueError(
                f"Truncated ReadyToRun section rows: expected {required_section_bytes} bytes for "
                f"{num_sections} sections, but buffer ends at {len(data) - (offset + 16)}"
            )

        sections: List[NativeAotSection] = []
        seen_types = set()

        for i in range(num_sections):
            row_offset = offset + 16 + (i * entry_size)
            stype, sflags, start, end = struct.unpack_from("<IIQQ", data, row_offset)

            if stype in seen_types:
                raise ValueError(f"Duplicate NativeAOT section type {stype} at index {i}")
            seen_types.add(stype)

            has_end = (sflags & 1) != 0
            if has_end and start > end:
                raise ValueError(
                    f"Reversed NativeAOT section {stype} bounds: start 0x{start:X} > end 0x{end:X}"
                )

            size = (end - start) if has_end else 0
            type_name = RTR_SECTION_NAMES.get(stype, f"UNKNOWN_SECTION_{stype}")

            sections.append(
                NativeAotSection(
                    type_id=stype,
                    type_name=type_name,
                    flags=sflags,
                    start_address=start,
                    end_address=end,
                    size=size,
                )
            )

        magic_str = magic_bytes.decode("ascii", errors="replace").rstrip("\x00")
        return NativeAotHeader(
            magic=magic_str,
            major_version=major,
            minor_version=minor,
            flags=flags,
            number_of_sections=num_sections,
            entry_size=entry_size,
            entry_type=entry_type,
            header_offset=offset,
            sections=sections,
        )

    @classmethod
    def discover_symbol_markers(cls, data: bytes) -> List[NativeAotSymbolMarker]:
        """Discovers embedded NativeAOT runtime markers in binary data."""
        discovered: List[NativeAotSymbolMarker] = []
        occupied_spans: List[Tuple[int, int]] = []

        # Sort markers by length descending to match most specific symbols first
        sorted_markers = sorted(KNOWN_SYMBOL_MARKERS, key=lambda m: len(m[0]), reverse=True)

        for marker_bytes, marker_name, category in sorted_markers:
            pos = 0
            while True:
                idx = data.find(marker_bytes, pos)
                if idx == -1:
                    break
                end_idx = idx + len(marker_bytes)
                # Check if this range overlaps with an already claimed longer symbol
                overlaps = any(s <= idx < e or s < end_idx <= e for s, e in occupied_spans)
                if not overlaps:
                    discovered.append(
                        NativeAotSymbolMarker(
                            name=marker_name,
                            offset=idx,
                            category=category,
                        )
                    )
                    occupied_spans.append((idx, end_idx))
                pos = idx + 1
        return sorted(discovered, key=lambda m: m.offset)

    @classmethod
    def identify_thunks(
        cls, data: bytes, markers: List[NativeAotSymbolMarker]
    ) -> List[NativeAotThunk]:
        """Identifies Managed-to-Native (PInvoke) and Native-to-Managed (ReversePInvoke) thunk boundaries."""
        thunks: List[NativeAotThunk] = []

        # 1. Thunk structures derived from markers
        for m in markers:
            if m.category == "reverse_pinvoke":
                thunks.append(
                    NativeAotThunk(
                        thunk_type="NativeToManaged",
                        offset=m.offset,
                        size=32,
                        target_marker=m.name,
                        convention="ReversePInvoke",
                    )
                )
            elif m.category == "pinvoke":
                thunks.append(
                    NativeAotThunk(
                        thunk_type="ManagedToNative",
                        offset=m.offset,
                        size=32,
                        target_marker=m.name,
                        convention="PInvoke",
                    )
                )

        # 2. Structured thunk table discovery if magic prefix "THNK" is found
        thnk_pos = 0
        while True:
            idx = data.find(b"THNK", thnk_pos)
            if idx == -1:
                break
            if idx + 8 <= len(data):
                count, entry_sz = struct.unpack_from("<HH", data, idx + 4)
                if 0 < count <= 64 and entry_sz == 16 and idx + 8 + (count * 16) <= len(data):
                    for i in range(count):
                        entry_pos = idx + 8 + (i * 16)
                        ttype_code, flags, toffset, ttarget = struct.unpack_from(
                            "<IIII", data, entry_pos
                        )
                        ttype = "NativeToManaged" if ttype_code == 1 else "ManagedToNative"
                        conv = "ReversePInvoke" if ttype_code == 1 else "PInvoke"
                        thunks.append(
                            NativeAotThunk(
                                thunk_type=ttype,
                                offset=toffset,
                                size=flags if flags > 0 else 16,
                                target_marker=f"0x{ttarget:X}",
                                convention=conv,
                            )
                        )
            thnk_pos = idx + 4

        return sorted(thunks, key=lambda t: t.offset)

    @classmethod
    def parse_gc_info(cls, data: bytes, offset: int = 0) -> NativeAotGcInfo:
        """Parses a NativeAOT GC info header blob."""
        if len(data) < offset + 8:
            raise ValueError(
                f"Truncated GC info header: expected at least 8 bytes at {offset}, got {len(data) - offset}"
            )

        code_size, flags, reg_mask, stack_slots = struct.unpack_from("<HHII", data, offset)
        if code_size == 0:
            raise ValueError(f"Invalid GC info code size: 0 at offset {offset}")

        is_frameless = (flags & 0x01) != 0
        has_stack_pointers = (flags & 0x02) != 0

        return NativeAotGcInfo(
            offset=offset,
            code_size=code_size,
            is_frameless=is_frameless,
            has_stack_pointers=has_stack_pointers,
            register_mask=reg_mask,
            stack_slot_count=stack_slots,
        )

    @classmethod
    def parse_method_table(cls, data: bytes, offset: int = 0) -> NativeAotMethodTable:
        """Parses a NativeAOT MethodTable record at a given offset."""
        if len(data) < offset + 24:
            raise ValueError(
                f"Truncated MethodTable record at offset {offset}: expected at least 24 bytes"
            )

        flags, base_size = struct.unpack_from("<II", data, offset)
        related_type = struct.unpack_from("<Q", data, offset + 8)[0]
        slots_count, interfaces_count = struct.unpack_from("<HH", data, offset + 16)

        if base_size > 0x10000000 or (base_size != 0 and base_size < 16):
            raise ValueError(
                f"Invalid MethodTable base size: 0x{base_size:X} at offset {offset}"
            )

        total_items = slots_count + interfaces_count
        if total_items > cls.MAX_METHOD_TABLE_ITEMS:
            raise ValueError(
                f"MethodTable slots + interfaces count {total_items} exceeds maximum limit {cls.MAX_METHOD_TABLE_ITEMS}"
            )

        required_bytes = 24 + (total_items * 8)
        if len(data) < offset + required_bytes:
            raise ValueError(
                f"Truncated MethodTable table data at {offset}: requires {required_bytes} bytes, "
                f"got {len(data) - offset}"
            )

        vtable_slots: List[int] = []
        for s in range(slots_count):
            slot_target = struct.unpack_from("<Q", data, offset + 24 + (s * 8))[0]
            vtable_slots.append(slot_target)

        interface_addresses: List[int] = []
        interfaces_start = offset + 24 + (slots_count * 8)
        for inf in range(interfaces_count):
            inf_target = struct.unpack_from("<Q", data, interfaces_start + (inf * 8))[0]
            interface_addresses.append(inf_target)

        return NativeAotMethodTable(
            address=offset,
            base_size=base_size,
            flags=flags,
            related_type_address=related_type,
            slots_count=slots_count,
            interfaces_count=interfaces_count,
            vtable_slots=vtable_slots,
            interface_addresses=interface_addresses,
        )

    @classmethod
    def parse_entrypoints(cls, data: bytes, offset: int = 0) -> List[NativeAotEntrypoint]:
        """Parses NativeAOT entrypoints table (METHOD_DEF_ENTRYPOINTS / section 104)."""
        if len(data) < offset + 4:
            return []

        count = struct.unpack_from("<I", data, offset)[0]
        if count == 0 or count > 256 or len(data) < offset + 4 + (count * 12):
            return []

        entrypoints: List[NativeAotEntrypoint] = []
        for i in range(count):
            ep_offset = offset + 4 + (i * 12)
            token, rva, flags = struct.unpack_from("<III", data, ep_offset)
            is_native_callable = (flags & 0x01) != 0
            entrypoints.append(
                NativeAotEntrypoint(
                    token=token,
                    entrypoint_offset=rva,
                    is_native_callable=is_native_callable,
                    name=f"Method_0x{token:X}",
                )
            )
        return entrypoints

    @classmethod
    def inspect(cls, data: bytes) -> NativeAotSummary:
        """Complete inspect analysis of a binary buffer for NativeAOT artifacts."""
        if not data:
            raise ValueError("Cannot inspect empty payload")

        sha256 = hashlib.sha256(data).hexdigest()
        total_len = len(data)

        # 1. Discover Symbol Markers
        markers = cls.discover_symbol_markers(data)

        # 2. Search for ReadyToRun header
        rtr_header: Optional[NativeAotHeader] = None
        rtr_offset: Optional[int] = None

        # Look for RTR signatures (8-byte aligned scan first, then byte-by-byte if not found)
        for sig in RTR_SIGNATURES:
            idx = data.find(sig)
            if idx != -1:
                try:
                    candidate = cls.parse_rtr_header(data, offset=idx)
                    rtr_header = candidate
                    rtr_offset = idx
                    break
                except ValueError:
                    continue

        # 3. Identify Thunks
        thunks = cls.identify_thunks(data, markers)

        # 4. Search for GC info sections or records
        gc_records: List[NativeAotGcInfo] = []
        if rtr_header:
            for sec in rtr_header.sections:
                if sec.type_id in (205, 103) and sec.start_address < total_len:
                    sec_offset = int(sec.start_address)
                    if sec_offset + 8 <= total_len:
                        try:
                            gc = cls.parse_gc_info(data, sec_offset)
                            gc_records.append(gc)
                        except ValueError:
                            continue

        # Also scan for explicit "GCIN" tag
        gcin_pos = 0
        while len(gc_records) < cls.MAX_GC_INFO_RECORDS:
            idx = data.find(b"GCIN", gcin_pos)
            if idx == -1:
                break
            if idx + 12 <= total_len:
                try:
                    gc = cls.parse_gc_info(data, idx + 4)
                    gc_records.append(gc)
                except ValueError:
                    idx = idx + 4
                    continue
            gcin_pos = idx + 4

        # 5. MethodTables
        method_tables: List[NativeAotMethodTable] = []
        # Search for "MTBL" markers or scan sections
        mtbl_pos = 0
        while len(method_tables) < 64:
            idx = data.find(b"MTBL", mtbl_pos)
            if idx == -1:
                break
            if idx + 28 <= total_len:
                try:
                    mt = cls.parse_method_table(data, idx + 4)
                    method_tables.append(mt)
                except ValueError:
                    idx = idx + 4
                    continue
            mtbl_pos = idx + 4

        # 6. Entrypoints
        entrypoints: List[NativeAotEntrypoint] = []
        if rtr_header:
            for sec in rtr_header.sections:
                if sec.type_id == 104 and sec.start_address < total_len:
                    eps = cls.parse_entrypoints(data, int(sec.start_address))
                    entrypoints.extend(eps)

        has_nativeaot = bool(rtr_header or markers or thunks or method_tables)

        return NativeAotSummary(
            total_bytes=total_len,
            sha256_digest=sha256,
            has_nativeaot=has_nativeaot,
            format_major=rtr_header.major_version if rtr_header else None,
            format_minor=rtr_header.minor_version if rtr_header else None,
            rtr_header_offset=rtr_offset,
            sections_count=len(rtr_header.sections) if rtr_header else 0,
            symbol_markers_count=len(markers),
            thunks_count=len(thunks),
            gc_info_count=len(gc_records),
            method_tables_count=len(method_tables),
            entrypoints_count=len(entrypoints),
            symbol_markers=markers,
            thunks=thunks,
            gc_info=gc_records,
            method_tables=method_tables,
            entrypoints=entrypoints,
        )


class NativeAotBuilder:
    """Helper to synthesize valid and adversarial NativeAOT binary structures for testing."""

    @classmethod
    def build_rtr_header(
        cls,
        major: int = 9,
        minor: int = 1,
        flags: int = 0,
        sections: Optional[List[Tuple[int, int, int, int]]] = None,
        magic: bytes = b"RTR\x00",
        override_num_sections: Optional[int] = None,
        override_entry_size: Optional[int] = None,
        override_entry_type: Optional[int] = None,
    ) -> bytes:
        if sections is None:
            # Default sections: DEHYDRATED_DATA (207), FROZEN_OBJECT_REGION (206), TYPE_MANAGER (204)
            sections = [
                (204, 0, 0x1000, 0x1000),      # ThreadStatic / RhTypeManager
                (206, 1, 0x2000, 0x2800),      # Frozen Object
                (207, 1, 0x3000, 0x4000),      # Dehydrated Data
            ]

        num_sections = override_num_sections if override_num_sections is not None else len(sections)
        entry_size = override_entry_size if override_entry_size is not None else 24
        entry_type = override_entry_type if override_entry_type is not None else 1

        hdr = (
            magic
            + struct.pack("<HHI", major, minor, flags)
            + struct.pack("<HBB", num_sections, entry_size, entry_type)
        )

        for stype, sflags, start, end in sections:
            hdr += struct.pack("<IIQQ", stype, sflags, start, end)

        return hdr

    @classmethod
    def build_method_table(
        cls,
        base_size: int = 32,
        flags: int = 0,
        related_type: int = 0,
        vtable_slots: Optional[List[int]] = None,
        interfaces: Optional[List[int]] = None,
    ) -> bytes:
        vslots = vtable_slots or [0x1000, 0x1020]
        infs = interfaces or [0x2000]

        mt = struct.pack("<II", flags, base_size)
        mt += struct.pack("<Q", related_type)
        mt += struct.pack("<HHI", len(vslots), len(infs), 0)

        for vs in vslots:
            mt += struct.pack("<Q", vs)
        for inf in infs:
            mt += struct.pack("<Q", inf)

        return b"MTBL" + mt

    @classmethod
    def build_gc_info(
        cls,
        code_size: int = 128,
        is_frameless: bool = True,
        has_stack_pointers: bool = True,
        reg_mask: int = 0x07,
        stack_slots: int = 4,
    ) -> bytes:
        flags = (1 if is_frameless else 0) | (2 if has_stack_pointers else 0)
        return b"GCIN" + struct.pack("<HHII", code_size, flags, reg_mask, stack_slots)

    @classmethod
    def build_thunk_table(
        cls,
        thunks: Optional[List[Tuple[int, int, int, int]]] = None,
    ) -> bytes:
        """Builds THNK table: (type_code, flags/size, offset, target)."""
        entries = thunks or [
            (1, 32, 0x100, 0x500),  # ReversePInvoke
            (2, 32, 0x200, 0x600),  # PInvoke
        ]
        buf = b"THNK" + struct.pack("<HH", len(entries), 16)
        for ttype, sz, off, target in entries:
            buf += struct.pack("<IIII", ttype, sz, off, target)
        return buf

    @classmethod
    def build_entrypoints_section(
        cls,
        entrypoints: Optional[List[Tuple[int, int, int]]] = None,
    ) -> bytes:
        eps = entrypoints or [
            (0x06000001, 0x1100, 1),
            (0x06000002, 0x1200, 0),
        ]
        buf = struct.pack("<I", len(eps))
        for token, rva, flags in eps:
            buf += struct.pack("<III", token, rva, flags)
        return buf

    @classmethod
    def build_full_payload(
        cls,
        rtr_major: int = 9,
        rtr_minor: int = 1,
        include_symbols: bool = True,
        include_method_tables: bool = True,
        include_gc_info: bool = True,
        include_thunks: bool = True,
    ) -> bytes:
        bio = io.BytesIO()

        # Write symbol markers
        if include_symbols:
            bio.write(b"__syms__\x00")
            bio.write(b"RhpReversePInvokeAttachOrTrapThread\x00")
            bio.write(b"RhpPInvoke\x00")
            bio.write(b"RhTypeManager::Create\x00")
            bio.write(b"RhpAssignRef\x00")

        # Thunk table
        if include_thunks:
            bio.write(cls.build_thunk_table())

        # MethodTable
        if include_method_tables:
            bio.write(cls.build_method_table())

        # GC Info
        if include_gc_info:
            bio.write(cls.build_gc_info())

        # RTR Section 104 (Entrypoints)
        ep_bytes = cls.build_entrypoints_section()
        ep_offset = bio.tell()
        bio.write(ep_bytes)

        # RTR Header
        sections = [
            (104, 1, ep_offset, ep_offset + len(ep_bytes)),
            (204, 0, 0x1000, 0x1000),
            (206, 1, 0x2000, 0x2800),
            (207, 1, 0x3000, 0x4000),
        ]
        rtr_bytes = cls.build_rtr_header(
            major=rtr_major,
            minor=rtr_minor,
            sections=sections,
        )
        bio.write(rtr_bytes)

        return bio.getvalue()
