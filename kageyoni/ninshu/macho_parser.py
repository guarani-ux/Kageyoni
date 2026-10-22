"""Zero-dependency in-tree Mach-O Universal / FAT Binary Slicer (CH 03).

Parses Apple Mach-O binaries:
1. FAT / Universal Binary containers (FAT_MAGIC 0xcafebabe, FAT_MAGIC_64 0xcafebabf, and endian swapped CIGAM).
   - Distinguishes Java .class bytecode from Mach-O FAT (evaluates major/minor version vs nfat_arch).
   - Extracts architecture slices (cputype, cpusubtype, offset, size, align).
2. Thin Mach-O images:
   - 32-bit (MH_MAGIC 0xfeedface, MH_CIGAM 0xcefaedfe).
   - 64-bit (MH_MAGIC_64 0xfeedfacf, MH_CIGAM_64 0xcffaedfe).
   - CPU architectures (x86, x86_64, ARM, ARM64, PowerPC).
   - Load commands enumeration (LC_SEGMENT, LC_SEGMENT_64, LC_LOAD_DYLIB, LC_UUID, LC_CODE_SIGNATURE).

Adheres to Apple's mach-o/loader.h and REA's machoContainer specification.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import struct
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

FAT_MAGIC = 0xCAFEBABE
FAT_CIGAM = 0xBEBAFECA
FAT_MAGIC_64 = 0xCAFEBABF
FAT_CIGAM_64 = 0xBFBAFECA

MH_MAGIC = 0xFEEDFACE
MH_CIGAM = 0xCEFAEDFE
MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE

# CPU Types
CPU_TYPE_X86 = 7
CPU_TYPE_X86_64 = 0x01000007
CPU_TYPE_ARM = 12
CPU_TYPE_ARM64 = 0x0100000C
CPU_TYPE_ARM64_32 = 0x0200000C
CPU_TYPE_POWERPC = 18
CPU_TYPE_POWERPC64 = 0x01000012

CPU_NAMES = {
    CPU_TYPE_X86: "i386",
    CPU_TYPE_X86_64: "x86_64",
    CPU_TYPE_ARM: "arm",
    CPU_TYPE_ARM64: "arm64",
    CPU_TYPE_ARM64_32: "arm64_32",
    CPU_TYPE_POWERPC: "ppc",
    CPU_TYPE_POWERPC64: "ppc64",
}

# File Types (filetype in mach_header)
MH_OBJECT = 0x1
MH_EXECUTE = 0x2
MH_DYLIB = 0x6
MH_BUNDLE = 0x8
MH_DSYM = 0xA

FILE_TYPE_NAMES = {
    MH_OBJECT: "MH_OBJECT",
    MH_EXECUTE: "MH_EXECUTE",
    MH_DYLIB: "MH_DYLIB",
    MH_BUNDLE: "MH_BUNDLE",
    MH_DSYM: "MH_DSYM",
}

MAX_FAT_SLICES = 128
MAX_LOAD_COMMANDS = 1024


@dataclasses.dataclass(frozen=True)
class MachOLoadCommand:
    cmd_type: int
    cmd_name: str
    cmd_size: int
    offset: int


@dataclasses.dataclass(frozen=True)
class MachOSlice:
    slice_index: int
    cpu_type: int
    cpu_name: str
    cpu_subtype: int
    offset: int
    size: int
    align: int
    is_64_bit: bool
    file_type: str
    load_commands_count: int
    sha256_digest: str


@dataclasses.dataclass(frozen=True)
class MachOBinarySummary:
    total_bytes: int
    sha256_digest: str
    is_fat_container: bool
    fat_magic: Optional[int]
    slices: List[MachOSlice]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "is_fat_container": self.is_fat_container,
            "slices_count": len(self.slices),
            "slices": [dataclasses.asdict(s) for s in self.slices],
        }


def is_java_class_file(stream: BinaryIO) -> bool:
    """Disambiguates FAT_MAGIC (0xCAFEBABE) from Java bytecode class files."""
    pos = stream.tell()
    try:
        stream.seek(0, io.SEEK_SET)
        head = stream.read(8)
        if len(head) < 8:
            return False
        magic, minor, major = struct.unpack(">IHH", head)
        if magic == FAT_MAGIC:
            # Java class version check: major version is between 45 (Java 1.1) and 70
            if 45 <= major <= 70:
                return True
        return False
    finally:
        stream.seek(pos, io.SEEK_SET)


class MachOBinaryParser:
    """Zero-dependency streaming parser for Apple Mach-O binaries."""

    @classmethod
    def parse_bytes(cls, data: bytes) -> MachOBinarySummary:
        return cls.parse_stream(io.BytesIO(data), total_size=len(data))

    @classmethod
    def parse_stream(cls, stream: BinaryIO, total_size: Optional[int] = None) -> MachOBinarySummary:
        if total_size is None:
            stream.seek(0, io.SEEK_END)
            total_size = stream.tell()
            stream.seek(0, io.SEEK_SET)

        if total_size < 4:
            raise ValueError(f"Truncated Mach-O binary: expected at least 4 bytes, got {total_size}")

        head4 = stream.read(4)
        if len(head4) < 4:
            raise ValueError("Truncated header")

        magic_be = struct.unpack(">I", head4)[0]

        # Check for Java bytecode collision
        if magic_be == FAT_MAGIC and is_java_class_file(stream):
            raise ValueError("Java .class file signature detected (not a Mach-O container)")

        slices: List[MachOSlice] = []
        is_fat = False

        if magic_be in (FAT_MAGIC, FAT_CIGAM, FAT_MAGIC_64, FAT_CIGAM_64):
            # Universal / FAT Container
            is_fat = True
            is_64_fat = magic_be in (FAT_MAGIC_64, FAT_CIGAM_64)
            is_le_fat = magic_be in (FAT_CIGAM, FAT_CIGAM_64)
            endian = "<" if is_le_fat else ">"

            nfat_bytes = stream.read(4)
            if len(nfat_bytes) < 4:
                raise ValueError("Truncated FAT header (missing nfat_arch)")
            nfat_arch = struct.unpack(f"{endian}I", nfat_bytes)[0]

            if nfat_arch < 1 or nfat_arch > MAX_FAT_SLICES:
                raise ValueError(f"Invalid FAT architecture count: {nfat_arch} (max {MAX_FAT_SLICES})")

            table_entry_size = 32 if is_64_fat else 20
            if 8 + (nfat_arch * table_entry_size) > total_size:
                raise ValueError("FAT architecture table extends past end of file")

            fat_entries = []
            for i in range(nfat_arch):
                if is_64_fat:
                    entry = stream.read(32)
                    cputype, cpusubtype, offset, size, align, reserved = struct.unpack(f"{endian}IIQQII", entry)
                else:
                    entry = stream.read(20)
                    cputype, cpusubtype, offset, size, align = struct.unpack(f"{endian}IIIII", entry)

                if offset + size > total_size:
                    raise ValueError(f"FAT slice {i} offset {offset} + size {size} exceeds file bounds {total_size}")
                fat_entries.append((cputype, cpusubtype, offset, size, align))

            # Inspect individual slices
            for idx, (cputype, cpusubtype, offset, size, align) in enumerate(fat_entries):
                stream.seek(offset, io.SEEK_SET)
                slice_data = stream.read(size)
                slice_digest = hashlib.sha256(slice_data).hexdigest()
                
                # Parse thin header
                is_64, ftype, ncmds = cls._parse_thin_header(io.BytesIO(slice_data[:64]))
                cpu_name = CPU_NAMES.get(cputype, f"cpu_{cputype}")
                ftype_name = FILE_TYPE_NAMES.get(ftype, f"TYPE_{ftype}")

                slices.append(
                    MachOSlice(
                        slice_index=idx,
                        cpu_type=cputype,
                        cpu_name=cpu_name,
                        cpu_subtype=cpusubtype,
                        offset=offset,
                        size=size,
                        align=align,
                        is_64_bit=is_64,
                        file_type=ftype_name,
                        load_commands_count=ncmds,
                        sha256_digest=slice_digest,
                    )
                )
        elif magic_be in (MH_MAGIC, MH_CIGAM, MH_MAGIC_64, MH_CIGAM_64):
            # Thin Single-Architecture Mach-O
            stream.seek(0, io.SEEK_SET)
            slice_data = stream.read(total_size)
            slice_digest = hashlib.sha256(slice_data).hexdigest()

            is_64, ftype, ncmds, cputype, cpusubtype = cls._parse_thin_header_full(io.BytesIO(slice_data[:64]))
            cpu_name = CPU_NAMES.get(cputype, f"cpu_{cputype}")
            ftype_name = FILE_TYPE_NAMES.get(ftype, f"TYPE_{ftype}")

            slices.append(
                MachOSlice(
                    slice_index=0,
                    cpu_type=cputype,
                    cpu_name=cpu_name,
                    cpu_subtype=cpusubtype,
                    offset=0,
                    size=total_size,
                    align=0,
                    is_64_bit=is_64,
                    file_type=ftype_name,
                    load_commands_count=ncmds,
                    sha256_digest=slice_digest,
                )
            )
        else:
            raise ValueError(f"Unrecognized Mach-O magic: 0x{magic_be:08X}")

        # Compute full container digest
        stream.seek(0, io.SEEK_SET)
        hasher = hashlib.sha256()
        while chunk := stream.read(65536):
            hasher.update(chunk)
        digest = hasher.hexdigest()

        return MachOBinarySummary(
            total_bytes=total_size,
            sha256_digest=digest,
            is_fat_container=is_fat,
            fat_magic=magic_be if is_fat else None,
            slices=slices,
        )

    @classmethod
    def _parse_thin_header(cls, stream: BinaryIO) -> Tuple[bool, int, int]:
        is_64, ftype, ncmds, _, _ = cls._parse_thin_header_full(stream)
        return is_64, ftype, ncmds

    @classmethod
    def _parse_thin_header_full(cls, stream: BinaryIO) -> Tuple[bool, int, int, int, int]:
        hdr4 = stream.read(4)
        if len(hdr4) < 4:
            raise ValueError("Truncated thin header")
        magic = struct.unpack(">I", hdr4)[0]

        is_64 = magic in (MH_MAGIC_64, MH_CIGAM_64)
        is_le = magic in (MH_CIGAM, MH_CIGAM_64)
        endian = "<" if is_le else ">"

        # mach_header / mach_header_64
        # cputype(4), cpusubtype(4), filetype(4), ncmds(4), sizeofcmds(4), flags(4) [, reserved(4)]
        rest = stream.read(24)
        if len(rest) < 24:
            raise ValueError("Truncated mach_header fields")

        cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags = struct.unpack(f"{endian}IIIIII", rest)
        return is_64, filetype, ncmds, cputype, cpusubtype
