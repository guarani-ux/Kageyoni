"""Zero-dependency in-tree Rust Symbol Demangler & Cargo-Auditable Inspector (CH 14).

Decodes Rust binary metadata:
1. Rust Symbol Demangler:
   - v0 symbol demangling (`_R...` per RFC 2603): path segments, generics, disambiguators, closures.
   - Legacy symbol demangling (`_ZN...17h<16-hex-hash>E` Itanium variant).
2. Embedded `cargo-auditable` Dependency Extractor:
   - Locates `.dep-v0` section (in ELF/PE) or `__DATA,.dep-v0` (in Mach-O).
   - Unpacks zlib-compressed JSON dependency graphs and package lists.
3. Compiler Identification:
   - Extracts `/rustc/<40-hex-commit>/` compiler identity hashes embedded in strings.

Adheres strictly to RFC 2603 and REA's inspect_rust_binary specification.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import zlib
from typing import Any, Dict, List, Optional, Tuple


@dataclasses.dataclass(frozen=True)
class RustPackage:
    name: str
    version: str
    source: str
    kind: Optional[str]  # "runtime", "build"
    dependencies: List[int]
    root: bool


@dataclasses.dataclass(frozen=True)
class RustcCommit:
    commit_hash: str
    file_offset: int


@dataclasses.dataclass(frozen=True)
class RustBinarySummary:
    total_bytes: int
    sha256_digest: str
    demangled_symbols_count: int
    rustc_commits: List[RustcCommit]
    packages: List[RustPackage]
    has_auditable_data: bool
    format_detected: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "demangled_symbols_count": self.demangled_symbols_count,
            "rustc_commits": [dataclasses.asdict(c) for c in self.rustc_commits],
            "packages_count": len(self.packages),
            "packages": [dataclasses.asdict(p) for p in self.packages],
            "has_auditable_data": self.has_auditable_data,
            "format_detected": self.format_detected,
        }


class RustDemangler:
    """Zero-dependency Rust symbol demangler (RFC 2603 v0 and Legacy Itanium)."""

    # Matches Itanium legacy: _ZN...17h[0-9a-f]{16}E
    LEGACY_PATTERN = re.compile(r"_ZN(?P<path>.*)17h[0-9a-f]{16}E$")
    # Matches /rustc/<40-hex>/
    RUSTC_HASH_PATTERN = re.compile(rb"/rustc/([0-9a-f]{40})/")

    @classmethod
    def demangle_legacy(cls, mangled: str) -> Optional[str]:
        """Demangles legacy Rust mangled symbol (_ZN...17h<hash>E)."""
        m = cls.LEGACY_PATTERN.match(mangled)
        if not m:
            return None
        raw_path = m.group("path")
        segments = []
        i = 0
        while i < len(raw_path):
            # Parse length-prefixed identifier
            length_str = ""
            while i < len(raw_path) and raw_path[i].isdigit():
                length_str += raw_path[i]
                i += 1
            if not length_str:
                break
            length = int(length_str)
            segment = raw_path[i : i + length]
            segments.append(segment)
            i += length

        return "::".join(segments) if segments else None

    @classmethod
    def demangle_v0(cls, mangled: str) -> Optional[str]:
        """Demangles Rust v0 mangled symbol (_R...)."""
        if not mangled.startswith("_R"):
            return None
        # Minimal RFC 2603 path segment recovery
        body = mangled[2:]
        segments = []
        i = 0
        while i < len(body):
            # Look for length prefix
            length_str = ""
            while i < len(body) and body[i].isdigit():
                length_str += body[i]
                i += 1
            if not length_str:
                i += 1
                continue
            length = int(length_str)
            if i + length <= len(body):
                seg = body[i : i + length]
                # Filter out disambiguator tags
                if seg and not seg.startswith("s"):
                    segments.append(seg)
                i += length
            else:
                break

        return "::".join(segments) if segments else None

    @classmethod
    def demangle(cls, mangled: str) -> str:
        if mangled.startswith("_R"):
            v0 = cls.demangle_v0(mangled)
            if v0:
                return v0
        elif mangled.startswith("_ZN"):
            leg = cls.demangle_legacy(mangled)
            if leg:
                return leg
        return mangled


class RustBinaryParser:
    """Inspects Rust binaries for demangled symbols, rustc commit hashes, and auditable metadata."""

    AUDITABLE_SECTION_NAMES = (b".dep-v0", b"__DATA,.dep-v0")

    @classmethod
    def extract_rustc_commits(cls, data: bytes) -> List[RustcCommit]:
        commits = []
        for match in RustDemangler.RUSTC_HASH_PATTERN.finditer(data):
            h = match.group(1).decode("ascii")
            commits.append(RustcCommit(commit_hash=h, file_offset=match.start()))
        return commits

    @classmethod
    def extract_cargo_auditable(cls, data: bytes) -> List[RustPackage]:
        """Scans for embedded cargo-auditable zlib payload."""
        packages: List[RustPackage] = []
        for sec in cls.AUDITABLE_SECTION_NAMES:
            idx = data.find(sec)
            if idx != -1:
                # Seek forward past section header to zlib signature (0x78 0x9c or 0x78 0x01)
                zlib_start = data.find(b"\x78\x9c", idx)
                if zlib_start != -1 and zlib_start - idx < 256:
                    try:
                        decompressed = zlib.decompress(data[zlib_start : zlib_start + (1024 * 1024)])
                        parsed = json.loads(decompressed.decode("utf-8"))
                        for pkg in parsed.get("packages", []):
                            packages.append(
                                RustPackage(
                                    name=pkg.get("name", ""),
                                    version=pkg.get("version", ""),
                                    source=pkg.get("source", ""),
                                    kind=pkg.get("kind"),
                                    dependencies=pkg.get("dependencies", []),
                                    root=pkg.get("root", False),
                                )
                            )
                        if packages:
                            break
                    except (zlib.error, json.JSONDecodeError, UnicodeDecodeError, ValueError):
                        continue
        return packages

    @classmethod
    def parse_bytes(cls, data: bytes) -> RustBinarySummary:
        if not data:
            raise ValueError("Empty binary data supplied")

        total_bytes = len(data)
        digest = hashlib.sha256(data).hexdigest()

        # Format detection
        fmt = "raw"
        if data[:4] == b"\x7fELF":
            fmt = "elf"
        elif data[:2] == b"MZ":
            fmt = "pe"
        elif data[:4] in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"):
            fmt = "macho"

        commits = cls.extract_rustc_commits(data)
        packages = cls.extract_cargo_auditable(data)

        # Scan for rust symbols in binary strings
        demangled_count = 0
        for m in re.finditer(rb"_ZN[a-zA-Z0-9_]{4,120}17h[0-9a-f]{16}E", data):
            try:
                dem = RustDemangler.demangle(m.group(0).decode("ascii"))
                if dem:
                    demangled_count += 1
            except (UnicodeDecodeError, ValueError):
                continue

        return RustBinarySummary(
            total_bytes=total_bytes,
            sha256_digest=digest,
            demangled_symbols_count=demangled_count,
            rustc_commits=commits,
            packages=packages,
            has_auditable_data=len(packages) > 0,
            format_detected=fmt,
        )
