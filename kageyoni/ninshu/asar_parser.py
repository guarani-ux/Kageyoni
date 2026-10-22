"""Zero-dependency in-tree Electron ASAR Archive Unpacker & Reader (CH 25).

Parses Chromium/Electron ASAR (Atom Shell Archive) format:
- Chromium pickle header:
  - uint32: 4 (magic size)
  - uint32: header_size (bytes following)
  - uint32: header_object_size (header_size - 4)
  - uint32: json_length
  - JSON string representing directory file tree with offsets and sizes.
- Trailing binary payload containing raw concatenated files.

Adheres strictly to Electron's asar specification and REA's AsarHeader contract.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import struct
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union


@dataclasses.dataclass(frozen=True)
class AsarFileEntry:
    path: str
    size: int
    offset: int
    is_directory: bool
    unpacked: bool = False
    sha256_digest: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class AsarArchiveSummary:
    total_bytes: int
    header_size: int
    json_size: int
    sha256_digest: str
    files_count: int
    directories_count: int
    entries: List[AsarFileEntry]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "header_size": self.header_size,
            "json_size": self.json_size,
            "sha256_digest": self.sha256_digest,
            "files_count": self.files_count,
            "directories_count": self.directories_count,
            "entries": [dataclasses.asdict(e) for e in self.entries],
        }


class AsarArchiveParser:
    """Zero-dependency parser for Electron ASAR archives."""

    MAX_ASAR_HEADER_BYTES = 16 * 1024 * 1024  # 16 MB ceiling

    @classmethod
    def parse_bytes(cls, data: bytes) -> AsarArchiveSummary:
        return cls.parse_stream(io.BytesIO(data), total_size=len(data))

    @classmethod
    def parse_stream(cls, stream: BinaryIO, total_size: Optional[int] = None) -> AsarArchiveSummary:
        if total_size is None:
            stream.seek(0, io.SEEK_END)
            total_size = stream.tell()
            stream.seek(0, io.SEEK_SET)

        if total_size < 16:
            raise ValueError(f"Truncated ASAR container: file size is only {total_size} bytes (min 16)")

        prefix = stream.read(16)
        if len(prefix) < 16:
            raise ValueError("Truncated ASAR pickle prefix")

        magic, header_bytes, payload_bytes, json_bytes = struct.unpack("<IIII", prefix)

        if magic != 4:
            raise ValueError(f"Invalid ASAR pickle magic: expected 4, got {magic}")

        if header_bytes < 8 or header_bytes > total_size - 8:
            raise ValueError(f"Invalid ASAR header size: {header_bytes} exceeds container bounds")

        if payload_bytes != header_bytes - 4:
            raise ValueError(f"Invalid ASAR payload pickle: payload_bytes ({payload_bytes}) != header_bytes - 4 ({header_bytes - 4})")

        if json_bytes > payload_bytes - 4:
            raise ValueError(f"Invalid ASAR json pickle extent: json_bytes ({json_bytes}) > payload_bytes - 4")

        if header_bytes > cls.MAX_ASAR_HEADER_BYTES:
            raise ValueError(f"ASAR header {header_bytes} exceeds maximum budget {cls.MAX_ASAR_HEADER_BYTES}")

        json_raw = stream.read(json_bytes)
        if len(json_raw) < json_bytes:
            raise ValueError(f"Truncated ASAR JSON header: expected {json_bytes} bytes, got {len(json_raw)}")

        try:
            tree = json.loads(json_raw.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Malformed ASAR directory tree JSON: {e}")

        # Flatten directory tree
        entries: List[AsarFileEntry] = []
        files_count = 0
        dirs_count = 0

        # Base data offset is immediately after the header: 16 bytes prefix + (header_bytes - 8)
        base_data_offset = 16 + (header_bytes - 8)

        def walk_tree(node: Dict[str, Any], current_path: str):
            nonlocal files_count, dirs_count
            files_dict = node.get("files", {})
            for name, meta in files_dict.items():
                entry_path = f"{current_path}/{name}" if current_path else name
                if "files" in meta:
                    dirs_count += 1
                    entries.append(
                        AsarFileEntry(
                            path=entry_path,
                            size=0,
                            offset=0,
                            is_directory=True,
                        )
                    )
                    walk_tree(meta, entry_path)
                else:
                    files_count += 1
                    file_size = meta.get("size", 0)
                    # offset in JSON is string or int, relative to base_data_offset
                    raw_offset = int(meta.get("offset", 0))
                    unpacked = meta.get("unpacked", False)
                    entries.append(
                        AsarFileEntry(
                            path=entry_path,
                            size=file_size,
                            offset=base_data_offset + raw_offset if not unpacked else 0,
                            is_directory=False,
                            unpacked=unpacked,
                        )
                    )

        walk_tree(tree, "")

        # Compute SHA-256 over entire stream if possible
        stream.seek(0, io.SEEK_SET)
        hasher = hashlib.sha256()
        while chunk := stream.read(65536):
            hasher.update(chunk)
        digest = hasher.hexdigest()

        return AsarArchiveSummary(
            total_bytes=total_size,
            header_size=header_bytes,
            json_size=json_bytes,
            sha256_digest=digest,
            files_count=files_count,
            directories_count=dirs_count,
            entries=entries,
        )
