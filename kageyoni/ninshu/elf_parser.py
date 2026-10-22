"""Zero-dependency in-tree ELF Multi-Architecture Transducer (CH 02).

Parses 32-bit and 64-bit Executable and Linkable Format (ELF) binaries across
Little-Endian and Big-Endian architectures (x86, x86-64, ARM, AArch64, RISC-V, MIPS).
Extracts:
- e_ident, file class (32 vs 64 bit), data encoding (LE vs BE), OS ABI, ABI version
- e_type (relocatable, executable, shared, core)
- e_machine (architecture mapping)
- Program headers (segments, flags, virtual addresses) with strict stride seeking
- Section headers (names from .shstrtab, types, flags, addresses, sizes)
- Symbol table (.symtab / .dynsym) with verified entry bounds and string table mapping

Adheres strictly to the System V ABI ELF specification and REA's binaryTargetTypes.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import struct
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

ELF_MAGIC = b"\x7fELF"

# Strict memory and iteration limits to prevent OOM/DoS attacks
MAX_STRTAB_BYTES = 16 * 1024 * 1024  # 16 MB string table ceiling
MAX_TABLE_ENTRIES = 65536             # 64k entries maximum

ELF_MACHINES = {
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
    0xF7: "BPF",
}

ELF_TYPES = {
    0x00: "ET_NONE",
    0x01: "ET_REL",
    0x02: "ET_EXEC",
    0x03: "ET_DYN",
    0x04: "ET_CORE",
}

SHT_TYPES = {
    0: "SHT_NULL",
    1: "SHT_PROGBITS",
    2: "SHT_SYMTAB",
    3: "SHT_STRTAB",
    4: "SHT_RELA",
    5: "SHT_HASH",
    6: "SHT_DYNAMIC",
    7: "SHT_NOTE",
    8: "SHT_NOBITS",
    9: "SHT_REL",
    10: "SHT_SHLIB",
    11: "SHT_DYNSYM",
}


@dataclasses.dataclass(frozen=True)
class ElfSection:
    name: str
    section_type: str
    flags: int
    addr: int
    offset: int
    size: int
    link: int
    info: int
    addralign: int
    entsize: int


@dataclasses.dataclass(frozen=True)
class ElfSegment:
    segment_type: int
    flags: int
    offset: int
    vaddr: int
    paddr: int
    filesz: int
    memsz: int
    align: int


@dataclasses.dataclass(frozen=True)
class ElfSymbol:
    name: str
    value: int
    size: int
    info: int
    other: int
    shndx: int


@dataclasses.dataclass(frozen=True)
class ElfBinarySummary:
    total_bytes: int
    sha256_digest: str
    is_64_bit: bool
    is_little_endian: bool
    os_abi: int
    abi_version: int
    elf_type: str
    machine: str
    entrypoint: int
    sections: List[ElfSection]
    segments: List[ElfSegment]
    symbols: List[ElfSymbol]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "is_64_bit": self.is_64_bit,
            "is_little_endian": self.is_little_endian,
            "os_abi": self.os_abi,
            "abi_version": self.abi_version,
            "elf_type": self.elf_type,
            "machine": self.machine,
            "entrypoint": self.entrypoint,
            "sections_count": len(self.sections),
            "segments_count": len(self.segments),
            "symbols_count": len(self.symbols),
            "sections": [dataclasses.asdict(s) for s in self.sections],
            "symbols": [dataclasses.asdict(s) for s in self.symbols],
        }


class ElfBinaryParser:
    """Zero-dependency streaming parser for ELF binaries."""

    @classmethod
    def parse_bytes(cls, data: bytes) -> ElfBinarySummary:
        return cls.parse_stream(io.BytesIO(data), total_size=len(data))

    @classmethod
    def parse_stream(cls, stream: BinaryIO, total_size: Optional[int] = None) -> ElfBinarySummary:
        if total_size is None:
            stream.seek(0, io.SEEK_END)
            total_size = stream.tell()
            stream.seek(0, io.SEEK_SET)

        if total_size < 52:
            raise ValueError(f"Truncated ELF header: expected at least 52 bytes, got {total_size}")

        ident = stream.read(16)
        if len(ident) < 16 or ident[:4] != ELF_MAGIC:
            raise ValueError(f"Invalid ELF magic: expected {ELF_MAGIC!r}, got {ident[:4]!r}")

        ei_class = ident[4]
        ei_data = ident[5]
        ei_osabi = ident[7]
        ei_abiversion = ident[8]

        if ei_class not in (1, 2):
            raise ValueError(f"Unsupported ELF class: {ei_class}")
        if ei_data not in (1, 2):
            raise ValueError(f"Unsupported ELF data encoding: {ei_data}")

        is_64_bit = (ei_class == 2)
        is_little_endian = (ei_data == 1)
        endian_char = "<" if is_little_endian else ">"

        if is_64_bit:
            if total_size < 64:
                raise ValueError(f"Truncated ELF64 header: expected 64 bytes, got {total_size}")
            hdr_bytes = stream.read(48)
            e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags, e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx = struct.unpack(
                f"{endian_char}HHIQQQIHHHHHH", hdr_bytes
            )
            min_phentsize = 56
            min_shentsize = 64
        else:
            hdr_bytes = stream.read(36)
            e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags, e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx = struct.unpack(
                f"{endian_char}HHIIIIIHHHHHH", hdr_bytes
            )
            min_phentsize = 32
            min_shentsize = 40

        elf_type_name = ELF_TYPES.get(e_type, f"ET_UNKNOWN_{e_type}")
        machine_name = ELF_MACHINES.get(e_machine, f"EM_UNKNOWN_{e_machine}")

        # 1. PARSE PROGRAM HEADERS (SEGMENTS) WITH STRIDE SEEKING
        segments: List[ElfSegment] = []
        if e_phoff > 0 and e_phnum > 0:
            if e_phentsize < min_phentsize:
                raise ValueError(f"e_phentsize {e_phentsize} is smaller than required struct size {min_phentsize}")
            if e_phnum > MAX_TABLE_ENTRIES:
                raise ValueError(f"e_phnum {e_phnum} exceeds safety threshold {MAX_TABLE_ENTRIES}")
            if e_phoff + (e_phnum * e_phentsize) > total_size:
                raise ValueError("Program header table extends past end of file")

            for i in range(e_phnum):
                entry_offset = e_phoff + (i * e_phentsize)
                stream.seek(entry_offset, io.SEEK_SET)
                if is_64_bit:
                    p_data = stream.read(56)
                    p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = struct.unpack(
                        f"{endian_char}IIQQQQQQ", p_data
                    )
                else:
                    p_data = stream.read(32)
                    p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack(
                        f"{endian_char}IIIIIIII", p_data
                    )
                segments.append(
                    ElfSegment(
                        segment_type=p_type,
                        flags=p_flags,
                        offset=p_offset,
                        vaddr=p_vaddr,
                        paddr=p_paddr,
                        filesz=p_filesz,
                        memsz=p_memsz,
                        align=p_align,
                    )
                )

        # 2. PARSE SECTION HEADERS WITH STRIDE SEEKING
        raw_sections = []
        if e_shoff > 0 and e_shnum > 0:
            if e_shentsize < min_shentsize:
                raise ValueError(f"e_shentsize {e_shentsize} is smaller than required struct size {min_shentsize}")
            if e_shnum > MAX_TABLE_ENTRIES:
                raise ValueError(f"e_shnum {e_shnum} exceeds safety threshold {MAX_TABLE_ENTRIES}")
            if e_shoff + (e_shnum * e_shentsize) > total_size:
                raise ValueError("Section header table extends past end of file")

            for i in range(e_shnum):
                entry_offset = e_shoff + (i * e_shentsize)
                stream.seek(entry_offset, io.SEEK_SET)
                if is_64_bit:
                    s_data = stream.read(64)
                    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link, sh_info, sh_addralign, sh_entsize = struct.unpack(
                        f"{endian_char}IIQQQQIIQQ", s_data
                    )
                else:
                    s_data = stream.read(40)
                    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link, sh_info, sh_addralign, sh_entsize = struct.unpack(
                        f"{endian_char}IIIIIIIIII", s_data
                    )
                raw_sections.append({
                    "name_idx": sh_name,
                    "type": sh_type,
                    "flags": sh_flags,
                    "addr": sh_addr,
                    "offset": sh_offset,
                    "size": sh_size,
                    "link": sh_link,
                    "info": sh_info,
                    "addralign": sh_addralign,
                    "entsize": sh_entsize,
                })

        # 3. BOUNDED STRING TABLE EXTRACTION
        shstrtab = b""
        if 0 <= e_shstrndx < len(raw_sections):
            sh_meta = raw_sections[e_shstrndx]
            if sh_meta["size"] > MAX_STRTAB_BYTES:
                raise ValueError(f".shstrtab size {sh_meta['size']} exceeds ceiling {MAX_STRTAB_BYTES}")
            if sh_meta["offset"] + sh_meta["size"] > total_size:
                raise ValueError(".shstrtab section extends past end of file")
            stream.seek(sh_meta["offset"], io.SEEK_SET)
            shstrtab = stream.read(sh_meta["size"])

        def get_string_from_table(table: bytes, offset: int) -> str:
            if offset >= len(table):
                return ""
            end = table.find(b"\x00", offset)
            if end == -1:
                end = len(table)
            return table[offset:end].decode("utf-8", errors="replace")

        sections: List[ElfSection] = []
        for s in raw_sections:
            sec_name = get_string_from_table(shstrtab, s["name_idx"]) if shstrtab else f"sec_{s['name_idx']}"
            type_str = SHT_TYPES.get(s["type"], f"SHT_UNKNOWN_{s['type']}")
            sections.append(
                ElfSection(
                    name=sec_name,
                    section_type=type_str,
                    flags=s["flags"],
                    addr=s["addr"],
                    offset=s["offset"],
                    size=s["size"],
                    link=s["link"],
                    info=s["info"],
                    addralign=s["addralign"],
                    entsize=s["entsize"],
                )
            )

        # 4. BOUNDED SYMBOL TABLE PARSING
        symbols: List[ElfSymbol] = []
        min_sym_size = 24 if is_64_bit else 16

        for s in raw_sections:
            if s["type"] in (2, 11):  # SHT_SYMTAB, SHT_DYNSYM
                if s["entsize"] < min_sym_size:
                    raise ValueError(f"Symbol entsize {s['entsize']} is smaller than required struct size {min_sym_size}")
                
                sym_count = s["size"] // s["entsize"]
                if sym_count > MAX_TABLE_ENTRIES:
                    raise ValueError(f"Symbol count {sym_count} exceeds maximum safety threshold {MAX_TABLE_ENTRIES}")
                if s["offset"] + s["size"] > total_size:
                    raise ValueError("Symbol table extends past end of file")

                # Resolve linked string table
                strtab_idx = s["link"]
                strtab_data = b""
                if 0 <= strtab_idx < len(raw_sections):
                    st_meta = raw_sections[strtab_idx]
                    if st_meta["size"] <= MAX_STRTAB_BYTES and st_meta["offset"] + st_meta["size"] <= total_size:
                        stream.seek(st_meta["offset"], io.SEEK_SET)
                        strtab_data = stream.read(st_meta["size"])

                for sym_idx in range(sym_count):
                    sym_offset = s["offset"] + (sym_idx * s["entsize"])
                    stream.seek(sym_offset, io.SEEK_SET)
                    if is_64_bit:
                        sym_bytes = stream.read(24)
                        st_name, st_info, st_other, st_shndx, st_value, st_size = struct.unpack(
                            f"{endian_char}IBBHQQ", sym_bytes
                        )
                    else:
                        sym_bytes = stream.read(16)
                        st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack(
                            f"{endian_char}IIIBBH", sym_bytes
                        )
                    sym_name = get_string_from_table(strtab_data, st_name) if strtab_data else f"sym_{st_name}"
                    symbols.append(
                        ElfSymbol(
                            name=sym_name,
                            value=st_value,
                            size=st_size,
                            info=st_info,
                            other=st_other,
                            shndx=st_shndx,
                        )
                    )

        # 5. IMMUTABLE SHA-256 DIGEST
        stream.seek(0, io.SEEK_SET)
        hasher = hashlib.sha256()
        while chunk := stream.read(65536):
            hasher.update(chunk)
        digest = hasher.hexdigest()

        return ElfBinarySummary(
            total_bytes=total_size,
            sha256_digest=digest,
            is_64_bit=is_64_bit,
            is_little_endian=is_little_endian,
            os_abi=ei_osabi,
            abi_version=ei_abiversion,
            elf_type=elf_type_name,
            machine=machine_name,
            entrypoint=e_entry,
            sections=sections,
            segments=segments,
            symbols=symbols,
        )
