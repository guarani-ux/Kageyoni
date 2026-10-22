"""Operational capability: Reverse Engineering & Binary Inspection (REA Engine).

Zero-dependency static inspection across PE/.NET assemblies, JavaScript/Electron
bundles, native binaries, and bridges to the REA toolkit (external_repos/rea).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple


class DotNetPEParser:
    """Zero-dependency parser for PE and .NET CLR metadata streams."""

    def __init__(self, data: bytes):
        self.data = data
        self.length = len(data)

    def is_pe(self) -> bool:
        if self.length < 0x40 or self.data[:2] != b"MZ":
            return False
        pe_offset = struct.unpack("<I", self.data[0x3C:0x40])[0]
        return self.length > pe_offset + 4 and self.data[pe_offset:pe_offset+4] == b"PE\x00\x00"

    def parse(self) -> Dict[str, Any]:
        if not self.is_pe():
            return {"error": "Not a valid PE binary"}

        pe_offset = struct.unpack("<I", self.data[0x3C:0x40])[0]
        machine, num_sections, timestamp, _, _, opt_size, characteristics = struct.unpack(
            "<HHIIIHH", self.data[pe_offset+4:pe_offset+24]
        )

        opt_offset = pe_offset + 24
        opt_magic = struct.unpack("<H", self.data[opt_offset:opt_offset+2])[0]
        is_pe32_plus = (opt_magic == 0x20B)

        machine_names = {0x014C: "x86 (i386)", 0x8664: "x64 (AMD64)", 0xAA64: "ARM64"}
        machine_str = machine_names.get(machine, f"Unknown (0x{machine:04x})")

        sections_offset = opt_offset + opt_size
        sections = []
        for i in range(num_sections):
            sec_ptr = sections_offset + i * 40
            sec_name = self.data[sec_ptr:sec_ptr+8].decode("latin1", errors="ignore").rstrip("\x00")
            v_size, v_addr, r_size, r_ptr = struct.unpack("<IIII", self.data[sec_ptr+8:sec_ptr+24])
            sections.append({
                "name": sec_name,
                "virtual_address": v_addr,
                "virtual_size": v_size,
                "raw_size": r_size,
                "raw_offset": r_ptr,
            })

        def rva_to_offset(rva: int) -> Optional[int]:
            for s in sections:
                v_addr = s["virtual_address"]
                v_span = max(s["virtual_size"], s["raw_size"])
                if v_addr <= rva < v_addr + v_span:
                    return s["raw_offset"] + (rva - v_addr)
            return None

        # Check CLR runtime header (DataDirectory[14])
        # DataDirectory starts at offset 96 (PE32) or 112 (PE32+) within OptionalHeader
        clr_dir_offset = opt_offset + (112 if is_pe32_plus else 96) + (14 * 8)
        has_clr = False
        clr_info: Dict[str, Any] = {}

        if opt_offset + opt_size >= clr_dir_offset + 8:
            clr_rva, clr_size = struct.unpack("<II", self.data[clr_dir_offset:clr_dir_offset+8])
            if clr_rva > 0 and clr_size >= 72:
                clr_file_off = rva_to_offset(clr_rva)
                if clr_file_off and clr_file_off + 72 <= self.length:
                    has_clr = True
                    cb, maj_r, min_r, meta_rva, meta_size, flags = struct.unpack(
                        "<IHHII I", self.data[clr_file_off:clr_file_off+20]
                    )
                    meta_file_off = rva_to_offset(meta_rva)
                    clr_info = {
                        "runtime_version": f"{maj_r}.{min_r}",
                        "flags": flags,
                        "metadata_rva": meta_rva,
                        "metadata_size": meta_size,
                    }

                    if meta_file_off and meta_file_off + 16 <= self.length:
                        magic = self.data[meta_file_off:meta_file_off+4]
                        if magic == b"BSJB":
                            vlen = struct.unpack("<I", self.data[meta_file_off+12:meta_file_off+16])[0]
                            vstr = self.data[meta_file_off+16:meta_file_off+16+vlen].decode("latin1", errors="ignore").rstrip("\x00")
                            clr_info["version_string"] = vstr

                            streams_ptr = meta_file_off + 16 + vlen
                            s_flags, stream_count = struct.unpack("<HH", self.data[streams_ptr:streams_ptr+4])
                            streams_ptr += 4
                            streams: Dict[str, Dict[str, int]] = {}
                            for _ in range(stream_count):
                                s_offset, s_size = struct.unpack("<II", self.data[streams_ptr:streams_ptr+8])
                                streams_ptr += 8
                                name_bytes = bytearray()
                                while streams_ptr < self.length and self.data[streams_ptr] != 0:
                                    name_bytes.append(self.data[streams_ptr])
                                    streams_ptr += 1
                                streams_ptr += 1
                                # 4-byte alignment
                                if (len(name_bytes) + 1) % 4 != 0:
                                    streams_ptr += 4 - ((len(name_bytes) + 1) % 4)
                                s_name = name_bytes.decode("ascii", errors="ignore")
                                streams[s_name] = {"offset": meta_file_off + s_offset, "size": s_size}

                            clr_info["streams"] = list(streams.keys())

                            # Extract metadata strings from #Strings
                            if "#Strings" in streams:
                                s_info = streams["#Strings"]
                                s_data = self.data[s_info["offset"]:s_info["offset"]+s_info["size"]]
                                raw_tokens = [t for t in s_data.decode("utf-8", errors="ignore").split("\x00") if len(t) >= 3]
                                clr_info["total_metadata_strings"] = len(raw_tokens)
                                clr_info["sample_types"] = [t for t in raw_tokens if re.match(r"^[A-Z][a-zA-Z0-9_]{3,}$", t)][:30]
                                clr_info["sample_methods"] = [t for t in raw_tokens if t.startswith(("get_", "set_")) or "Action" in t][:25]
                                clr_info["protobuf_tokens"] = [t for t in raw_tokens if "Message" in t or "Proto" in t][:20]

        return {
            "format": ".NET Assembly (PE/CLR)" if has_clr else "Native PE Binary",
            "machine": machine_str,
            "timestamp": timestamp,
            "is_64bit": is_pe32_plus,
            "sections": [s["name"] for s in sections],
            "clr_runtime": clr_info if has_clr else None,
        }


class JSApplicationParser:
    """Inspector for JavaScript / Node.js / Electron application directories."""

    def __init__(self, path: Path):
        self.path = path

    def parse(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "format": "JavaScript/Node/Electron Application",
            "root": str(self.path),
            "package_metadata": None,
            "electron_indicators": [],
            "api_surface": [],
        }

        pkg_json = self.path / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                result["package_metadata"] = {
                    "name": data.get("name"),
                    "version": data.get("version"),
                    "main": data.get("main"),
                    "dependencies": list((data.get("dependencies") or {}).keys()),
                    "devDependencies": list((data.get("devDependencies") or {}).keys()),
                    "scripts": list((data.get("scripts") or {}).keys()),
                }
                deps = set(result["package_metadata"]["dependencies"]) | set(result["package_metadata"]["devDependencies"])
                if "electron" in deps:
                    result["electron_indicators"].append("electron dependency declared")
            except Exception as e:
                result["package_metadata"] = {"error": str(e)}

        # Search for Electron entrypoints, preload scripts, and IPC calls
        main_entry = (self.path / "main.js") if (self.path / "main.js").is_file() else None
        preload = list(self.path.glob("*preload*.js")) + list(self.path.glob("src/*preload*.js"))

        if preload:
            result["electron_indicators"].append(f"Preload scripts: {[p.name for p in preload]}")

        # IPC scan in top scripts
        ipc_events = set()
        for f in list(self.path.glob("*.js")) + list(self.path.glob("src/*.js"))[:15]:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                matches = re.findall(r"ipc(?:Main|Renderer)\.(?:on|handle|send)\(['\"]([^'\"]+)['\"]", content)
                ipc_events.update(matches)
            except Exception:
                pass

        if ipc_events:
            result["electron_indicators"].append("Active IPC Channels detected")
            result["api_surface"] = sorted(list(ipc_events))

        return result


def extract_strings(data: bytes, min_length: int = 4, pattern: Optional[str] = None) -> List[str]:
    """Extract printable ASCII and UTF-8 strings with optional regex filter."""
    text = data.decode("latin1", errors="ignore")
    found = re.findall(rf"[a-zA-Z0-9_\-\./:]{{{min_length},}}", text)
    unique = sorted(list(set(found)))
    if pattern:
        rx = re.compile(pattern, re.IGNORECASE)
        unique = [s for s in unique if rx.search(s)]
    return unique


def get_rea_bridge_status() -> Dict[str, Any]:
    """Check readiness of REA (morluto/rea) repository and global CLI."""
    workspace_root = Path(__file__).resolve().parent.parent
    rea_dir = workspace_root / "external_repos" / "rea"
    dist_dir = rea_dir / "dist"

    has_source = (rea_dir / "package.json").is_file()
    has_compiled = (dist_dir / "main.js").is_file()

    # Check global CLI
    has_global_cli = False
    try:
        res = subprocess.run(["rea", "--version"], capture_output=True, text=True, timeout=3)
        has_global_cli = (res.returncode == 0)
    except Exception:
        has_global_cli = False

    return {
        "rea_source_present": has_source,
        "rea_source_path": str(rea_dir) if has_source else None,
        "rea_compiled_runtime": has_compiled,
        "global_cli_installed": has_global_cli,
        "status": "ready" if (has_compiled or has_global_cli) else "source_available_needs_build",
    }


def inspect_target(target_path: str) -> Dict[str, Any]:
    """Inspect any binary, application, or directory target."""
    path = Path(target_path).resolve()
    if not path.exists():
        return {"error": f"Path does not exist: {target_path}"}

    if path.is_dir():
        return JSApplicationParser(path).parse()

    data = path.read_bytes()
    if data[:2] == b"MZ":
        res = DotNetPEParser(data).parse()
        res["file_path"] = str(path)
        res["file_size_bytes"] = len(data)
        return res

    # Generic file identification
    magic_map = [
        (b"\x7fELF", "ELF Binary (Linux)"),
        (b"\xca\xfe\xba\xbe", "Mach-O / Java Class"),
        (b"\xcf\xfa\xed\xfe", "Mach-O 64-bit"),
        (b"PK\x03\x04", "ZIP / JAR Archive"),
    ]
    fmt = "Unknown Binary"
    for magic, name in magic_map:
        if data.startswith(magic):
            fmt = name
            break

    return {
        "format": fmt,
        "file_path": str(path),
        "file_size_bytes": len(data),
        "sample_strings": extract_strings(data, min_length=6)[:25],
    }


def main():
    parser = argparse.ArgumentParser(description="Reverse Engineering & Binary Inspection (REA Engine)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_cmd = subparsers.add_parser("inspect", help="Inspect a binary file or application directory")
    inspect_cmd.add_argument("path", help="Path to file or directory")
    inspect_cmd.add_argument("--json", action="store_true", help="Output pure JSON")

    scan_cmd = subparsers.add_parser("scan", help="Scan binary for strings matching a regex pattern")
    scan_cmd.add_argument("path", help="Path to binary file")
    scan_cmd.add_argument("--filter", required=True, help="Regex pattern to filter strings")
    scan_cmd.add_argument("--limit", type=int, default=50, help="Max strings to return")

    subparsers.add_parser("rea-status", help="Check REA toolkit compilation and bridge status")

    args = parser.parse_args()

    if args.command == "rea-status":
        status = get_rea_bridge_status()
        print(json.dumps(status, indent=2))
        return

    if args.command == "inspect":
        info = inspect_target(args.path)
        if args.json:
            print(json.dumps(info, indent=2))
        else:
            print(f"=== REA Static Inspection: {args.path} ===")
            print(json.dumps(info, indent=2))

    elif args.command == "scan":
        path = Path(args.path)
        if not path.is_file():
            print(f"Error: {args.path} is not a file", file=sys.stderr)
            sys.exit(1)
        strings = extract_strings(path.read_bytes(), pattern=args.filter)[:args.limit]
        print(f"Found {len(strings)} strings matching '{args.filter}':")
        for s in strings:
            print(f"  {s}")


if __name__ == "__main__":
    main()
