"""Comprehensive Verification Suite for Ninshū Patchbay Wiring & Execution Engine.

Validates:
1. Auto-seeding & cryptographic seeds digest tracking in SQLite (`ninshu_codex.sqlite`).
2. Complete resolution of ALL 48 channels via `resolve_callable()`.
3. Mechanical execution of golden sample payloads across ALL 48 channels under ThermodynamicProfiler (heap <= 64KB).
4. Serial and parallel multi-track patch execution via `execute_patch()`.
5. Strict fail-closed error handling on invalid channels, invalid inputs, and boundary violations.
6. ActiveConsole integration with channel configuration, noise gate, mute, and receipts.
7. Real-specimen verification using live WSL Ubuntu files (`journal.db`, `scouter_pulse.bin`, `bash`/`ls`).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from kageyoni.ninshu.patchbay import Patchbay, compute_seeds_digest
from kageyoni.ninshu.console import ActiveConsole
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
from tests.test_ninshu_tls_parser import build_client_hello_record


class TestNinshuPatchbayWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.patchbay = Patchbay()

        # Build golden test fixtures
        cls.pe_bytes = (
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
        cls.synthetic_elf64 = bytes(elf_buf)

        cls.macho_bytes = struct.pack("<IIIIIIII", 0xFEEDFACF, 0x01000007, 3, 2, 0, 0, 0, 0)

        frida_events = [
            StalkerCallEvent(source_address=0x1000, target_address=0x2000, depth=0),
            StalkerBlockEvent(start_address=0x2000, end_address=0x2050),
            StalkerExecEvent(instruction_address=0x2010),
            StalkerRetEvent(source_address=0x204F, target_address=0x1005, depth=0),
        ]
        cls.frida_packed = FridaStalkerParser.pack_stream(frida_events, format="tagged")

        cls.core_bytes = CoreDumpBuilder.build_elf64_core(
            signal=11,
            pid=1000,
            ppid=1,
            fname="app",
            psargs="./app",
            rip=0x401000,
            rsp=0x7FFFFFFFE000,
            rbp=0x7FFFFFFFE080,
            rax=0, rbx=0, rcx=0, rdx=0, rsi=0, rdi=0,
        )

        cls.rizin_session = {
            "registers": {
                "rax": 0, "rbx": 0, "rcx": 0, "rdx": 0, "rsi": 0, "rdi": 0,
                "rsp": 0x7FFFFFFFE000, "rbp": 0x7FFFFFFFE080, "rip": 0x401000, "rflags": 0x202,
            },
            "memory_maps": [{"addr": 0x400000, "addr_end": 0x401000, "perm": "r-x", "file": "app"}],
            "breakpoints": [],
            "backtrace": [],
        }

        asar_tree = {"files": {"main.js": {"size": 12, "offset": "0"}}}
        asar_json = json.dumps(asar_tree, separators=(",", ":")).encode("utf-8")
        cls.asar_bytes = (
            struct.pack("<IIII", 4, 8 + len(asar_json), 4 + len(asar_json), len(asar_json))
            + asar_json
            + b"console.log()"
        )

        cls.dex_bytes = (
            b"dex\n035\x00"
            + struct.pack("<I", 0x12345678)
            + (b"\xaa" * 20)
            + struct.pack("<III", 112, 112, 0x12345678)
            + struct.pack("<IIIIIIIIIIIIIIIII", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        )

        cls.dart_bytes = DartSnapshotBuilder.build(
            kind="full_aot",
            snapshot_hash="0123456789abcdef0123456789abcdef",
            isolate_flags="--sound-null-safety",
            payload=b"\x00" * 32,
            arch_bits=64,
            endianness="little",
        )

        cls.pcap_bytes = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
        cls.tls_bytes = build_client_hello_record(sni="example.com")

        mitm_flow = {
            "id": "flow-1",
            "type": "http",
            "request": {"method": "GET", "scheme": "https", "host": "example.com", "port": 443, "path": "/", "headers": [], "content": b"", "timestamp_start": 0.0, "timestamp_end": 0.1},
            "response": {"status_code": 200, "headers": [], "content": b"OK", "timestamp_start": 0.1, "timestamp_end": 0.2},
            "error": None,
        }
        cls.mitm_bytes = MsgPackSerializer.pack(mitm_flow)

        cls.napi_pe_dll = NapiBridgeBuilder.build_pe_dll(
            module_name="addon.node",
            exported_names=["napi_register_module_v1"],
            is_64_bit=True,
        )

        cls.golden_payloads = {
            1: cls.pe_bytes,
            2: cls.synthetic_elf64,
            3: cls.macho_bytes,
            4: {"name": "sample", "arch": "x86_64", "image_base": 0x400000, "functions": [{"name": "main", "entrypoint": 0x401000, "return_type": "int"}]},
            5: {"file_type": "mach-o", "segments": [{"name": "__TEXT", "address": 4096, "size": 4096}], "procedures": []},
            6: {
                "iIj": {"format": "elf64", "arch": "x86", "bits": 64, "endian": "little", "compiler": "gcc", "canary": True, "nx": True, "pic": True},
                "iSj": [{"name": ".text", "size": 4096, "vaddr": 0x401000, "paddr": 0x1000, "flags": "r-x"}],
                "aflj": [{"offset": 0x401000, "name": "main", "size": 16, "realsz": 16, "cc": 1, "nops": 0, "calltype": "cdecl", "type": "fcn"}],
                "pdfj": {"name": "main", "offset": 0x401000, "size": 16, "ops": [{"offset": 0x401000, "opcode": "nop", "size": 1, "type": "nop"}]},
            },
            7: {"database": "test.idb", "image_base": "0x400000", "functions": [], "segments": []},
            8: "test.o:     file format elf64-x86-64\nDisassembly of section .text:\n0000000000000000 <main>:\n   0:   48 83 ec 08             sub    $0x8,%rsp\n   4:   c3                      retq\n",
            9: cls.pe_bytes,
            10: cls.pe_bytes,
            11: b"\x00asm\x01\x00\x00\x00",
            12: b"\x60\x80\x60\x40\x52\x34\x80\x15\x60\x0f\x57\x60\x00\x80\xfd\x5b\x50",
            13: cls.synthetic_elf64,
            14: "_RNvCs1234_7my_crate3foo",
            15: b"\x90\x90\xc3",
            16: b"\x00" * 32,
            17: cls.frida_packed,
            18: {"regions": [{"base_address": "0x1000", "size": 4096, "permissions": "r-x", "segment_name": ".text"}]},
            19: cls.core_bytes,
            20: cls.rizin_session,
            21: "* thread #1, stop reason = breakpoint 1.1\n  frame #0: 0x0000000000401122 a.out`main at main.c:4:3",
            22: {"registers": {"rip": "0x41414141"}, "signal": "SIGSEGV"},
            23: {"pid": 1000, "parent_pid": 1, "lease_duration": 60.0, "max_budget": 300.0},
            24: cls.napi_pe_dll,
            25: cls.asar_bytes,
            26: 'contextBridge.exposeInMainWorld("api", { send: (c, d) => ipcRenderer.send(c, d) });',
            27: '{"method": "Network.requestWillBeSent", "params": {"requestId": "1", "request": {"url": "https://example.com"}}}',
            28: cls.dex_bytes,
            29: {"sources": [], "resources": []},
            30: "<manifest package='com.example'><application/></manifest>",
            31: cls.dart_bytes,
            32: {"engine": {"name": "JEB", "version": "5.0"}, "project_name": "sample", "units": []},
            33: cls.pcap_bytes,
            34: cls.tls_bytes,
            35: cls.mitm_bytes,
            36: b"\x08\x96\x01",
            37: "ghidra decompile",
            38: "export API_KEY=abcdef1234567890abcdef1234567890",
            39: {"channel_id": 1, "sequence_no": 1, "payload": b"ping"},
            40: {"nodes": {"n1": {"artifact_id": "n1", "sha256_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "byte_size": 0, "mime_type": "text/plain", "metadata": {}}}, "edges": []},
            41: {"api_version": 1, "branch": "main", "expected_revision": 0, "request_id": "req-001", "kind": "action", "actor": "system", "narrative": "init", "changes": [{"op": "create", "id": "char:1", "domain": "character", "expected_version": 0, "data": {"name": "Sciel", "entity_kind": "person", "identity": "scholar"}, "evidence": [{"note": "established"}]}]},
            42: {"frame": {"frame_id": "test", "slots": []}, "aspects": [], "bindings": {}},
            43: [],
            44: {"objective": "system_bootstrap", "requirement_version": "1.0", "scope": "kernel"},
            45: {"observation": "boundary verified", "source_record_id": "obs:001"},
            46: {"topic": "decompilation", "task": "parse elf", "search_roots": []},
            47: {"niche_id": "niche_alpha"},
            48: {"world_id": "w1", "branch": "main", "revision": 1, "settings": {}, "player": {}, "scene": {}},
        }

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "patchbay") and cls.patchbay:
            cls.patchbay.close()

    def test_seeds_digest_tracking_and_auto_reseed(self) -> None:
        """Verifies that Patchbay stores seeds digest and automatically re-seeds when out of sync."""
        expected_digest = compute_seeds_digest()
        stored_digest = self.patchbay._get_meta("seeds_digest")
        self.assertEqual(stored_digest, expected_digest)

        # Create temporary database to verify clean auto-seeding
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_db = Path(tmp_dir) / "fresh_codex.sqlite"
            fresh_pb = Patchbay(db_path=temp_db)
            self.assertEqual(fresh_pb._channel_count(), 48)
            self.assertEqual(fresh_pb._get_meta("seeds_digest"), expected_digest)

            # Corrupt digest in DB and verify re-seed
            fresh_pb._set_meta("seeds_digest", "stale_hash_value")
            self.assertEqual(fresh_pb._get_meta("seeds_digest"), "stale_hash_value")
            fresh_pb.close()

            re_seeded_pb = Patchbay(db_path=temp_db)
            self.assertEqual(re_seeded_pb._get_meta("seeds_digest"), expected_digest)
            self.assertEqual(re_seeded_pb._channel_count(), 48)
            re_seeded_pb.close()

    def test_resolve_callable_all_48_channels(self) -> None:
        """Verifies that ALL 48 channels dynamically resolve via resolve_callable()."""
        for ch in range(1, 49):
            fn = self.patchbay.resolve_callable(ch)
            self.assertTrue(callable(fn), f"Channel {ch} did not resolve to a callable: {fn}")

    def test_execute_channel_all_48_golden_payloads(self) -> None:
        """Executes valid golden sample payloads for all 48 channels and verifies thermodynamic compliance."""
        for ch in range(1, 49):
            payload = self.golden_payloads.get(ch)
            self.assertIsNotNone(payload, f"Golden payload missing for channel {ch}")

            res = self.patchbay.execute_channel(ch, payload)

            self.assertEqual(res["channel_number"], ch)
            self.assertEqual(res["status"], "success")
            self.assertTrue(res["thermodynamic_passed"], f"Channel {ch} failed thermodynamic verification")

            # Memory limit check
            self.assertLessEqual(
                res["peak_memory_bytes"],
                64 * 1024,
                f"Channel {ch} peak memory ({res['peak_memory_bytes']} bytes) exceeded 64 KB ceiling",
            )

            # Cryptographic hash verification
            self.assertEqual(len(res["input_sha256"]), 64)
            self.assertEqual(len(res["output_sha256"]), 64)
            self.assertGreaterEqual(res["latency_seconds"], 0.0)

            # Verification receipt inspection
            receipt = res["thermodynamic_receipt"]
            self.assertIsInstance(receipt, dict)
            self.assertTrue(receipt["passed"])
            self.assertEqual(receipt["exit_code"], 0)

    def test_execute_patch_serial_mode(self) -> None:
        """Tests cascading serial patch execution where channel output flows to subsequent channel."""
        # Channels [40, 45]: Provenance Graph generates manifest -> Epistemic Firewall records observation
        initial_manifest = {
            "nodes": {
                "artifact_1": {
                    "artifact_id": "artifact_1",
                    "sha256_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "byte_size": 0,
                    "mime_type": "application/octet-stream",
                    "metadata": {},
                }
            },
            "edges": [],
        }

        patch_res = self.patchbay.execute_patch([40, 45], initial_manifest, mode="serial")
        self.assertEqual(patch_res["mode"], "serial")
        self.assertEqual(patch_res["channel_count"], 2)
        self.assertTrue(patch_res["all_thermodynamic_passed"])
        self.assertEqual(len(patch_res["step_results"]), 2)

        # Final output is recorded observation from EpistemicFirewall
        final = patch_res["final_output"]
        self.assertIsInstance(final, dict)
        self.assertEqual(final["status"], "recorded")
        self.assertEqual(final["category"], "KAGEYONI_OBSERVATION")

    def test_execute_patch_parallel_mode(self) -> None:
        """Tests parallel patch execution where payload is broadcast across channels."""
        # Channels [1, 9]: PE Stripper and .NET PE Parser
        patch_res = self.patchbay.execute_patch([1, 9], self.pe_bytes, mode="parallel")
        self.assertEqual(patch_res["mode"], "parallel")
        self.assertEqual(patch_res["channel_count"], 2)
        self.assertTrue(patch_res["all_thermodynamic_passed"])
        self.assertIn(1, patch_res["final_output"])
        self.assertIn(9, patch_res["final_output"])

    def test_fail_closed_handling(self) -> None:
        """Verifies fail-closed behavior for invalid channel numbers, unsupported inputs, and illegal arguments."""
        # Invalid channel numbers
        for invalid_ch in [-1, 0, 49, 999]:
            with self.assertRaises(ValueError):
                self.patchbay.resolve_callable(invalid_ch)
            with self.assertRaises(ValueError):
                self.patchbay.execute_channel(invalid_ch, b"payload")

        # Invalid patch configurations
        with self.assertRaises(ValueError):
            self.patchbay.execute_patch([], b"payload", mode="serial")
        with self.assertRaises(ValueError):
            self.patchbay.execute_patch([1], b"payload", mode="unsupported_mode")

        # Invariant rejections by specific channel parsers
        with self.assertRaises(Exception):
            # CH 02 (ELF) rejects non-ELF magic
            self.patchbay.execute_channel(2, b"CORRUPTED_NOT_ELF_HEADER")

        with self.assertRaises(Exception):
            # CH 11 (WASM) rejects invalid magic
            self.patchbay.execute_channel(11, b"CORRUPTED_WASM")

        with self.assertRaises(Exception):
            # CH 33 (PCAP) rejects invalid magic
            self.patchbay.execute_channel(33, b"CORRUPTED_PCAP_MAGIC")

    def test_active_console_integration(self) -> None:
        """Verifies channel strip control (muting, custom thermal limits) via ActiveConsole."""
        manifest = self.patchbay.patch([1, 2], daimon_name="test_daimon")
        console = ActiveConsole(manifest)

        # Mute channel 1
        console.channels[1].mute = True
        res_muted = self.patchbay.execute_channel(1, self.pe_bytes, console=console)
        self.assertEqual(res_muted["status"], "muted")
        self.assertIsNone(res_muted["result"])
        self.assertTrue(res_muted["thermodynamic_passed"])

        # Unmute channel 1 and execute
        console.channels[1].mute = False
        res_active = self.patchbay.execute_channel(1, self.pe_bytes, console=console)
        self.assertEqual(res_active["status"], "success")
        self.assertIsNotNone(console.channels[1].thermodynamic_receipt)

    def test_real_wsl_specimens(self) -> None:
        r"""Verifies read-only inspection of real specimens in \\wsl.localhost\Ubuntu."""
        # 1. Specimen: scouter_pulse.bin (Raw binary inspection via CH 15)
        scouter_path = Path(r"\\wsl.localhost\Ubuntu\home\flowe\booder-kingdom\security\scouter_pulse.bin")
        if scouter_path.exists():
            data = scouter_path.read_bytes()
            res15 = self.patchbay.execute_channel(15, data)
            self.assertEqual(res15["status"], "success")
            self.assertTrue(res15["thermodynamic_passed"])
            self.assertLessEqual(res15["peak_memory_bytes"], 64 * 1024)

            # Fail-closed check: scouter_pulse.bin is NOT an ELF, so feeding to CH 02 must fail-closed
            with self.assertRaises(Exception):
                self.patchbay.execute_channel(2, data)

        # 2. Specimen: journal.db (SQLite binary firmware/storage inspection via CH 16)
        journal_path = Path(r"\\wsl.localhost\Ubuntu\home\flowe\booder-kingdom\journal.db")
        if journal_path.exists():
            data = journal_path.read_bytes()[:1024]
            res16 = self.patchbay.execute_channel(16, data)
            self.assertEqual(res16["status"], "success")
            self.assertTrue(res16["thermodynamic_passed"])
            self.assertLessEqual(res16["peak_memory_bytes"], 64 * 1024)

        # 3. Specimen: Real Linux ELF binary (/usr/bin/bash or cargo coreutils ls via CH 02)
        elf_candidates = [
            Path(r"\\wsl.localhost\Ubuntu\usr\bin\bash"),
            Path(r"\\wsl.localhost\Ubuntu\usr\lib\cargo\bin\coreutils\ls"),
        ]
        target_elf = next((p for p in elf_candidates if p.exists()), None)
        if target_elf is not None:
            data = target_elf.read_bytes()
            # Full 1.5MB executable inspection under ActiveConsole scaled ceiling
            console = ActiveConsole({
                "channel_strips": [{
                    "ch": 2,
                    "name": "ELF",
                    "carrier": "kageyoni/ninshu/elf_parser.py",
                    "entrypoint": "ElfBinaryParser.parse_bytes",
                    "tier": 0,
                }]
            })
            console.channels[2].max_memory_ceiling_bytes = 4 * 1024 * 1024  # 4 MB ceiling for full binary
            res02 = self.patchbay.execute_channel(2, data, console=console)
            self.assertEqual(res02["status"], "success")
            self.assertTrue(res02["thermodynamic_passed"])
            self.assertEqual(res02["result"].machine, "x86-64")
            self.assertTrue(res02["result"].is_64_bit)
            self.assertGreater(res02["result"].entrypoint, 0)


if __name__ == "__main__":
    unittest.main()
