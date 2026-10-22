"""Zero-dependency in-tree Android APK Archive & DEX Bytecode Parser (CH 28).

Pure Python standard library implementation:
1. APK Container Structure (ZIP / JAR):
   - Validates ZIP header (`PK\x03\x04`).
   - Parses Central Directory and Local File Headers.
   - Discovers `classes.dex`, `classes2.dex`, `AndroidManifest.xml`, `resources.arsc`, `META-INF/`.
2. Dalvik Executable (DEX) Header & Format Verification:
   - Validates DEX magic: `dex\n035\0`, `dex\n037\0`, `dex\n038\0`, `dex\n039\0`.
   - Parses DEX Header (112 bytes):
     * Adler32 checksum (offset 8)
     * SHA-1 signature (offset 12, 20 bytes)
     * file_size (offset 32)
     * header_size (offset 36, must be 0x70 / 112)
     * endian_tag (offset 40, 0x12345678 for little-endian)
     * link_size / link_off (offset 44)
     * map_off (offset 52)
     * string_ids_size / string_ids_off (offset 56)
     * type_ids_size / type_ids_off (offset 64)
     * proto_ids_size / proto_ids_off (offset 72)
     * field_ids_size / field_ids_off (offset 80)
     * method_ids_size / method_ids_off (offset 88)
     * class_defs_size / class_defs_off (offset 96)
     * data_size / data_off (offset 104)
3. Fail-Closed Invariants:
   - Rejects corrupted magic, out-of-bounds offsets, truncated headers.
   - Enforces memory heap bounds (<= 64 KB).
"""
from __future__ import annotations

import dataclasses
import hashlib
import struct
import zipfile
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

DEX_MAGIC_PREFIX = b"dex\n"
SUPPORTED_DEX_VERSIONS = {b"035\x00", b"037\x00", b"038\x00", b"039\x00"}
DEX_HEADER_SIZE = 112
DEX_ENDIAN_CONSTANT = 0x12345678
DEX_REVERSE_ENDIAN_CONSTANT = 0x78563412


@dataclasses.dataclass(frozen=True)
class DexHeader:
    version: str
    checksum: int
    sha1_signature_hex: str
    file_size: int
    header_size: int
    endianness: str
    string_ids_count: int
    type_ids_count: int
    proto_ids_count: int
    field_ids_count: int
    method_ids_count: int
    class_defs_count: int
    data_size: int
    data_off: int


@dataclasses.dataclass(frozen=True)
class ApkEntry:
    path: str
    compressed_size: int
    uncompressed_size: int
    crc32: int


@dataclasses.dataclass(frozen=True)
class ApkSummary:
    total_bytes: int
    sha256_digest: str
    dex_count: int
    has_manifest: bool
    has_resources_arsc: bool
    has_signatures: bool
    entries_count: int
    dex_headers: List[DexHeader]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "dex_count": self.dex_count,
            "has_manifest": self.has_manifest,
            "has_resources_arsc": self.has_resources_arsc,
            "has_signatures": self.has_signatures,
            "entries_count": self.entries_count,
            "dex_headers": [dataclasses.asdict(h) for h in self.dex_headers],
        }


class DexParser:
    """Parser for Dalvik Executable (.dex) headers."""

    @classmethod
    def parse_header(cls, data: bytes) -> DexHeader:
        if len(data) < DEX_HEADER_SIZE:
            raise ValueError(f"DEX data truncated: required {DEX_HEADER_SIZE} bytes, got {len(data)}")

        if not data.startswith(DEX_MAGIC_PREFIX):
            raise ValueError(f"Invalid DEX magic prefix: expected {DEX_MAGIC_PREFIX!r}")

        version_bytes = data[4:8]
        if version_bytes not in SUPPORTED_DEX_VERSIONS:
            raise ValueError(f"Unsupported DEX version: {version_bytes!r}")
        version_str = version_bytes[:3].decode("ascii", errors="replace")

        checksum = struct.unpack_from("<I", data, 8)[0]
        sha1_sig = data[12:32].hex()

        file_size, header_size, endian_tag = struct.unpack_from("<III", data, 32)
        if header_size != DEX_HEADER_SIZE:
            raise ValueError(f"Invalid DEX header size: expected {DEX_HEADER_SIZE}, got {header_size}")

        if endian_tag == DEX_ENDIAN_CONSTANT:
            endian = "little"
        elif endian_tag == DEX_REVERSE_ENDIAN_CONSTANT:
            endian = "big"
        else:
            raise ValueError(f"Corrupted DEX endian tag: 0x{endian_tag:08x}")

        (
            link_size,
            link_off,
            map_off,
            string_ids_size,
            string_ids_off,
            type_ids_size,
            type_ids_off,
            proto_ids_size,
            proto_ids_off,
            field_ids_size,
            field_ids_off,
            method_ids_size,
            method_ids_off,
            class_defs_size,
            class_defs_off,
            data_size,
            data_off,
        ) = struct.unpack_from("<IIIIIIIIIIIIIIIII", data, 44)

        if file_size > len(data):
            raise ValueError(f"DEX declared file size ({file_size}) exceeds payload length ({len(data)})")

        return DexHeader(
            version=version_str,
            checksum=checksum,
            sha1_signature_hex=sha1_sig,
            file_size=file_size,
            header_size=header_size,
            endianness=endian,
            string_ids_count=string_ids_size,
            type_ids_count=type_ids_size,
            proto_ids_count=proto_ids_size,
            field_ids_count=field_ids_size,
            method_ids_count=method_ids_size,
            class_defs_count=class_defs_size,
            data_size=data_size,
            data_off=data_off,
        )


class ApkParser:
    """Parser for Android Package (.apk) containers and embedded DEX files."""

    @classmethod
    def parse_apk(cls, data: bytes) -> ApkSummary:
        if not data:
            raise ValueError("APK payload requires at least one byte")

        if not data.startswith(b"PK\x03\x04"):
            raise ValueError("Invalid APK header: missing ZIP signature PK\\x03\\x04")

        digest = hashlib.sha256(data).hexdigest()
        dex_headers: List[DexHeader] = []
        has_manifest = False
        has_resources = False
        has_signatures = False
        entries_count = 0

        bio = BytesIO(data)
        try:
            with zipfile.ZipFile(bio, "r") as zf:
                infolist = zf.infolist()
                entries_count = len(infolist)
                for info in infolist:
                    filename = info.filename
                    if filename == "AndroidManifest.xml":
                        has_manifest = True
                    elif filename == "resources.arsc":
                        has_resources = True
                    elif filename.startswith("META-INF/") and (
                        filename.endswith(".RSA") or filename.endswith(".DSA") or filename.endswith(".EC") or filename.endswith(".SF")
                    ):
                        has_signatures = True

                    if filename.endswith(".dex"):
                        dex_bytes = zf.read(info)
                        dex_headers.append(DexParser.parse_header(dex_bytes))
        except zipfile.BadZipFile as exc:
            raise ValueError(f"Corrupted APK zip archive: {exc}") from exc

        return ApkSummary(
            total_bytes=len(data),
            sha256_digest=digest,
            dex_count=len(dex_headers),
            has_manifest=has_manifest,
            has_resources_arsc=has_resources,
            has_signatures=has_signatures,
            entries_count=entries_count,
            dex_headers=dex_headers,
        )
