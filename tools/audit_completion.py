"""Live Executed 48-Channel Empirical Audit Probe for Ninshū Capability Estate.

Zero import-only shortcuts. Iterates through ALL 48 channels in `Patchbay().list_channels()`,
dynamically resolves and executes each channel via `Patchbay.execute_channel(channel_number, payload)`
using valid golden payloads, and verifies `thermodynamic_passed == True` for all 48/48 channels.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.ninshu.coredump_parser import CoreDumpBuilder
from kageyoni.ninshu.dart_parser import DartSnapshotBuilder
from kageyoni.ninshu.frida_stalker_parser import (
    FridaStalkerParser,
    StalkerBlockEvent,
    StalkerCallEvent,
    StalkerExecEvent,
    StalkerRetEvent,
)
from kageyoni.ninshu.mitmproxy_parser import MsgPackSerializer
from kageyoni.ninshu.napi_bridge_parser import NapiBridgeBuilder
from kageyoni.ninshu.patchbay import Patchbay
from tests.test_ninshu_tls_parser import build_client_hello_record


def build_golden_payloads() -> Dict[int, Any]:
    """Constructs deterministic golden input payloads for all 48 Ninshū channels."""
    pe_bytes = (
        struct.pack("<H", 0x5A4D)
        + b"\x00" * 58
        + struct.pack("<I", 0x40)
        + b"PE\x00\x00"
        + struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, 0, 0x0002)
        + struct.pack("<H", 0x20B)
        + b"\x00" * 200
    )

    elf_ident = b"\x7fELF" + bytes([2, 1, 1, 0, 0]) + (b"\x00" * 7)
    elf_hdr = struct.pack("<HHIQQQIHHHHHH", 2, 0x3E, 1, 0x401000, 64, 120, 0, 64, 56, 1, 64, 4, 1)
    prog_hdr = struct.pack("<IIQQQQQQ", 1, 5, 0, 0x400000, 0x400000, 0x400, 0x400, 0x1000)
    shstrtab = b"\x00.text\x00.shstrtab\x00.symtab\x00.strtab\x00"
    strtab = b"\x00main\x00"
    symtab = struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0) + struct.pack("<IBBHQQ", 1, 0x12, 0, 0, 0x401000, 16)
    sec0 = struct.pack("<IIQQQQIIQQ", 1, 1, 6, 0x401000, 700, 16, 0, 0, 16, 0)
    sec1 = struct.pack("<IIQQQQIIQQ", 7, 3, 0, 0, 400, len(shstrtab), 0, 0, 1, 0)
    sec2 = struct.pack("<IIQQQQIIQQ", 17, 2, 0, 0, 600, len(symtab), 3, 1, 8, 24)
    sec3 = struct.pack("<IIQQQQIIQQ", 25, 3, 0, 0, 500, len(strtab), 0, 0, 1, 0)
    sec_headers = sec0 + sec1 + sec2 + sec3
    elf_buf = bytearray(800)
    elf_buf[0:64] = elf_ident + elf_hdr
    elf_buf[64:120] = prog_hdr
    elf_buf[120:376] = sec_headers
    elf_buf[400 : 400 + len(shstrtab)] = shstrtab
    elf_buf[500 : 500 + len(strtab)] = strtab
    elf_buf[600 : 600 + len(symtab)] = symtab
    elf_buf[700:716] = b"\x90" * 16
    synthetic_elf64 = bytes(elf_buf)

    macho_bytes = struct.pack("<IIIIIIII", 0xFEEDFACF, 0x01000007, 3, 2, 0, 0, 0, 0)

    frida_events = [
        StalkerCallEvent(source_address=0x1000, target_address=0x2000, depth=0),
        StalkerBlockEvent(start_address=0x2000, end_address=0x2050),
        StalkerExecEvent(instruction_address=0x2010),
        StalkerRetEvent(source_address=0x204F, target_address=0x1005, depth=0),
    ]
    frida_packed = FridaStalkerParser.pack_stream(frida_events, format="tagged")

    core_bytes = CoreDumpBuilder.build_elf64_core(
        signal=11,
        pid=1000,
        ppid=1,
        fname="app",
        psargs="./app",
        rip=0x401000,
        rsp=0x7FFFFFFFE000,
        rbp=0x7FFFFFFFE080,
        rax=0,
        rbx=0,
        rcx=0,
        rdx=0,
        rsi=0,
        rdi=0,
    )

    rizin_session = {
        "registers": {
            "rax": 0,
            "rbx": 0,
            "rcx": 0,
            "rdx": 0,
            "rsi": 0,
            "rdi": 0,
            "rsp": 0x7FFFFFFFE000,
            "rbp": 0x7FFFFFFFE080,
            "rip": 0x401000,
            "rflags": 0x202,
        },
        "memory_maps": [{"addr": 0x400000, "addr_end": 0x401000, "perm": "r-x", "file": "app"}],
        "breakpoints": [],
        "backtrace": [],
    }

    asar_tree = {"files": {"main.js": {"size": 12, "offset": "0"}}}
    asar_json = json.dumps(asar_tree, separators=(",", ":")).encode("utf-8")
    asar_bytes = (
        struct.pack("<IIII", 4, 8 + len(asar_json), 4 + len(asar_json), len(asar_json))
        + asar_json
        + b"console.log()"
    )

    dex_bytes = (
        b"dex\n035\x00"
        + struct.pack("<I", 0x12345678)
        + (b"\xaa" * 20)
        + struct.pack("<III", 112, 112, 0x12345678)
        + struct.pack("<IIIIIIIIIIIIIIIII", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    )

    dart_bytes = DartSnapshotBuilder.build(
        kind="full_aot",
        snapshot_hash="0123456789abcdef0123456789abcdef",
        isolate_flags="--sound-null-safety",
        payload=b"\x00" * 32,
        arch_bits=64,
        endianness="little",
    )

    pcap_bytes = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    tls_bytes = build_client_hello_record(sni="example.com")

    mitm_flow = {
        "id": "flow-1",
        "type": "http",
        "request": {
            "method": "GET",
            "scheme": "https",
            "host": "example.com",
            "port": 443,
            "path": "/",
            "headers": [],
            "content": b"",
            "timestamp_start": 0.0,
            "timestamp_end": 0.1,
        },
        "response": {
            "status_code": 200,
            "headers": [],
            "content": b"OK",
            "timestamp_start": 0.1,
            "timestamp_end": 0.2,
        },
        "error": None,
    }
    mitm_bytes = MsgPackSerializer.pack(mitm_flow)

    napi_pe_dll = NapiBridgeBuilder.build_pe_dll(
        module_name="addon.node",
        exported_names=["napi_register_module_v1"],
        is_64_bit=True,
    )

    return {
        1: pe_bytes,
        2: synthetic_elf64,
        3: macho_bytes,
        4: {
            "name": "sample",
            "arch": "x86_64",
            "image_base": 0x400000,
            "functions": [{"name": "main", "entrypoint": 0x401000, "return_type": "int"}],
        },
        5: {
            "file_type": "mach-o",
            "segments": [{"name": "__TEXT", "address": 4096, "size": 4096}],
            "procedures": [],
        },
        6: {
            "iIj": {
                "format": "elf64",
                "arch": "x86",
                "bits": 64,
                "endian": "little",
                "compiler": "gcc",
                "canary": True,
                "nx": True,
                "pic": True,
            },
            "iSj": [{"name": ".text", "size": 4096, "vaddr": 0x401000, "paddr": 0x1000, "flags": "r-x"}],
            "aflj": [
                {
                    "offset": 0x401000,
                    "name": "main",
                    "size": 16,
                    "realsz": 16,
                    "cc": 1,
                    "nops": 0,
                    "calltype": "cdecl",
                    "type": "fcn",
                }
            ],
            "pdfj": {
                "name": "main",
                "offset": 0x401000,
                "size": 16,
                "ops": [{"offset": 0x401000, "opcode": "nop", "size": 1, "type": "nop"}],
            },
        },
        7: {"database": "test.idb", "image_base": "0x400000", "functions": [], "segments": []},
        8: (
            "test.o:     file format elf64-x86-64\n"
            "Disassembly of section .text:\n"
            "0000000000000000 <main>:\n"
            "   0:   48 83 ec 08             sub    $0x8,%rsp\n"
            "   4:   c3                      retq\n"
        ),
        9: pe_bytes,
        10: pe_bytes,
        11: b"\x00asm\x01\x00\x00\x00",
        12: b"\x60\x80\x60\x40\x52\x34\x80\x15\x60\x0f\x57\x60\x00\x80\xfd\x5b\x50",
        13: synthetic_elf64,
        14: "_RNvCs1234_7my_crate3foo",
        15: b"\x90\x90\xc3",
        16: b"\x00" * 32,
        17: frida_packed,
        18: {"regions": [{"base_address": "0x1000", "size": 4096, "permissions": "r-x", "segment_name": ".text"}]},
        19: core_bytes,
        20: rizin_session,
        21: "* thread #1, stop reason = breakpoint 1.1\n  frame #0: 0x0000000000401122 a.out`main at main.c:4:3",
        22: {"registers": {"rip": "0x41414141"}, "signal": "SIGSEGV"},
        23: {"pid": 1000, "parent_pid": 1, "lease_duration": 60.0, "max_budget": 300.0},
        24: napi_pe_dll,
        25: asar_bytes,
        26: 'contextBridge.exposeInMainWorld("api", { send: (c, d) => ipcRenderer.send(c, d) });',
        27: '{"method": "Network.requestWillBeSent", "params": {"requestId": "1", "request": {"url": "https://example.com"}}}',
        28: dex_bytes,
        29: {"sources": [], "resources": []},
        30: "<manifest package='com.example'><application/></manifest>",
        31: dart_bytes,
        32: {"engine": {"name": "JEB", "version": "5.0"}, "project_name": "sample", "units": []},
        33: pcap_bytes,
        34: tls_bytes,
        35: mitm_bytes,
        36: b"\x08\x96\x01",
        37: "ghidra decompile",
        38: "export API_KEY=abcdef1234567890abcdef1234567890",
        39: {"channel_id": 1, "sequence_no": 1, "payload": b"ping"},
        40: {
            "nodes": {
                "n1": {
                    "artifact_id": "n1",
                    "sha256_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "byte_size": 0,
                    "mime_type": "text/plain",
                    "metadata": {},
                }
            },
            "edges": [],
        },
        41: {
            "api_version": 1,
            "branch": "main",
            "expected_revision": 0,
            "request_id": "req-001",
            "kind": "action",
            "actor": "system",
            "narrative": "init",
            "changes": [
                {
                    "op": "create",
                    "id": "char:1",
                    "domain": "character",
                    "expected_version": 0,
                    "data": {"name": "Sciel", "entity_kind": "person", "identity": "scholar"},
                    "evidence": [{"note": "established"}],
                }
            ],
        },
        42: {"frame": {"frame_id": "test", "slots": []}, "aspects": [], "bindings": {}},
        43: [],
        44: {"objective": "system_bootstrap", "requirement_version": "1.0", "scope": "kernel"},
        45: {"observation": "boundary verified", "source_record_id": "obs:001"},
        46: {"topic": "decompilation", "task": "parse elf", "search_roots": []},
        47: {"niche_id": "niche_alpha"},
        48: {"world_id": "w1", "branch": "main", "revision": 1, "settings": {}, "player": {}, "scene": {}},
    }


def run_empirical_audit() -> Dict[str, Any]:
    """Iterates through all 48 channels in Patchbay, executes each with golden payloads, and verifies thermodynamic pass."""
    pb = Patchbay()
    try:
        channels = [ch for ch in pb.list_channels() if 1 <= int(ch["channel_number"]) <= 48]
        total = len(channels)
        golden_payloads = build_golden_payloads()

        passed_channels: List[Dict[str, Any]] = []
        failed_channels: List[Dict[str, Any]] = []

        print("================================================================================")
        print(" EMPIRICAL NINSHU AUDIT RECEIPT (48-CHANNEL LIVE PATCHBAY EXECUTION)")
        print("================================================================================")

        for ch_meta in channels:
            ch_num = int(ch_meta["channel_number"])
            ch_name = ch_meta["name"]
            payload = golden_payloads.get(ch_num)
            if payload is None:
                failed_channels.append(
                    {"channel_number": ch_num, "name": ch_name, "error": "Missing golden payload"}
                )
                print(f" [FAIL] CH {ch_num:02d} | {ch_name:<38} | Missing golden payload")
                continue

            try:
                exec_res = pb.execute_channel(ch_num, payload)
                status = exec_res.get("status")
                thermo_passed = bool(exec_res.get("thermodynamic_passed", False))
                peak_mem = int(exec_res.get("peak_memory_bytes", 0))
                out_sha = str(exec_res.get("output_sha256", ""))

                if status == "success" and thermo_passed and len(out_sha) == 64:
                    passed_channels.append(
                        {
                            "channel_number": ch_num,
                            "name": ch_name,
                            "peak_memory_bytes": peak_mem,
                            "thermodynamic_passed": thermo_passed,
                            "output_sha256": out_sha,
                        }
                    )
                    print(
                        f" [PASS] CH {ch_num:02d} | {ch_name:<38} | Peak: {peak_mem:>6} B | SHA256: {out_sha[:12]}..."
                    )
                else:
                    failed_channels.append(
                        {
                            "channel_number": ch_num,
                            "name": ch_name,
                            "error": f"status={status}, thermodynamic_passed={thermo_passed}",
                        }
                    )
                    print(
                        f" [FAIL] CH {ch_num:02d} | {ch_name:<38} | status={status}, thermo={thermo_passed}"
                    )
            except Exception as exc:
                failed_channels.append(
                    {"channel_number": ch_num, "name": ch_name, "error": str(exc)}
                )
                print(f" [FAIL] CH {ch_num:02d} | {ch_name:<38} | Exception: {exc}")

        verified_count = len(passed_channels)
        failed_count = total - verified_count
        pct = (verified_count / total * 100.0) if total > 0 else 0.0

        print("--------------------------------------------------------------------------------")
        print(f" Total Estate Channels:                {total}")
        print(f" Empirically Verified Grade A (Live):  {verified_count} / {total} ({pct:.1f}%)")
        print(f" Failed / Unverified Channels:         {failed_count} / {total}")
        print("--------------------------------------------------------------------------------")
        if verified_count == 48 and failed_count == 0:
            print(" STATUS: ALL 48/48 CHANNELS EMPIRICALLY EXECUTED AND THERMODYNAMICALLY VERIFIED.")
        else:
            print(f" STATUS: DEFICIT DETECTED ({failed_count} channels failed execution).")
        print("================================================================================\n")

        return {
            "total_channels": total,
            "verified_channels": verified_count,
            "failed_channels_count": failed_count,
            "all_passed": verified_count == 48 and failed_count == 0,
            "passed_channels": passed_channels,
            "failed_channels": failed_channels,
        }
    finally:
        pb.close()


if __name__ == "__main__":
    receipt = run_empirical_audit()
    sys.exit(0 if receipt["all_passed"] else 1)
