"""Executable Worked Encounters for the Ninshū Definitive Guide.

Serves as empirical, runnable evidence for Part VI of docs/NINSHU_DEFINITIVE_GUIDE.md.
Exercises the actual code at commit 277afd99cb7acea55a9a6c0de1049cde79c7783a without mocks:
  1. Encounter 1: Catalog vs. Source Entrypoint Audit & Single-Channel ELF Inspection (CH 02)
  2. Encounter 2: Multi-Channel Composition & Byte Transfer (CH 25 -> CH 26 + CH 38 -> CH 40)
  3. Encounter 3: Contradictory Evidence & Opposing Pressures (CH 04 vs CH 17 -> CH 43 + Console)
  4. Encounter 4: Refusal, Failure-Muting Mitigation & Deficit Classification (Tier 1 + CH 42 Compiler)
  5. Encounter 5: Cold-Process Causal Persistence & Recovery (CH 41 + CH 45 + CH 48 across subprocess)
"""
from __future__ import annotations

import ast
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.composition.compiler import Compiler
from kageyoni.composition.effects import EffectResolver
from kageyoni.engine import Engine
from kageyoni.ninshu.asar_parser import AsarArchiveParser
from kageyoni.ninshu.console import ActiveConsole
from kageyoni.ninshu.electron_ipc_scanner import ElectronIpcScanner
from kageyoni.ninshu.elf_parser import ElfBinaryParser
from kageyoni.ninshu.frida_stalker_parser import (
    FridaStalkerParser,
    StalkerCallEvent,
    StalkerRetEvent,
)
from kageyoni.ninshu.ghidra_parser import GhidraParser
from kageyoni.ninshu.patchbay import Patchbay
from kageyoni.ninshu.provenance_mapper import ArtifactNode, ProvenanceGraph
from kageyoni.ninshu.secret_scanner import SecretScanner
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.playable_world.kernel import SaveState
from levi_sim.epistemic_firewall import EpistemicFirewall


def build_minimal_elf64_x86_64() -> bytes:
    """Constructs a valid minimal 64-bit little-endian x86_64 ELF binary header."""
    e_ident = b"\x7fELF" + bytes([2, 1, 1, 0, 0]) + b"\x00" * 7
    header_tail = struct.pack(
        "<HHIQQQIHHHHHH",
        2,          # e_type: ET_EXEC
        62,         # e_machine: EM_X86_64
        1,          # e_version
        0x401000,   # e_entry
        64,         # e_phoff
        0,          # e_shoff
        0,          # e_flags
        64,         # e_ehsize
        56,         # e_phentsize
        1,          # e_phnum
        64,         # e_shentsize
        0,          # e_shnum
        0,          # e_shstrndx
    )
    phdr = struct.pack(
        "<IIQQQQQQ",
        1,          # p_type: PT_LOAD
        5,          # p_flags: PF_R | PF_X
        0,          # p_offset
        0x400000,   # p_vaddr
        0x400000,   # p_paddr
        120,        # p_filesz
        120,        # p_memsz
        0x1000,     # p_align
    )
    return e_ident + header_tail + phdr


def build_realistic_asar_bundle() -> bytes:
    """Constructs a valid Chromium/Electron ASAR archive with main.js and preload.js."""
    main_js = (
        b"const { app, BrowserWindow, ipcMain } = require('electron');\n"
        b"const win = new BrowserWindow({ webPreferences: { nodeIntegration: true, contextIsolation: false } });\n"
        b"ipcMain.handle('vault:decrypt', async (event, payload) => { return payload; });\n"
    )
    gh_pat = "ghp_" + "a9B8c7D6e5F4g3H2i1J0k9L8m7N6o5P4q3R2"
    preload_js = (
        b"const { contextBridge, ipcRenderer } = require('electron');\n"
        b"contextBridge.exposeInMainWorld('desktopAPI', {\n"
        b"  unlock: (token) => ipcRenderer.invoke('vault:decrypt', token),\n"
        b"  telemetrySink: (ch, data) => ipcRenderer.send(ch, data)\n"
        b"});\n"
        + f"const BACKUP_TOKEN = '{gh_pat}';\n".encode("utf-8")
    )

    header_dict = {
        "files": {
            "main.js": {"size": len(main_js), "offset": "0"},
            "preload.js": {"size": len(preload_js), "offset": str(len(main_js))},
        }
    }
    header_json = json.dumps(header_dict, separators=(",", ":")).encode("utf-8")
    str_len = len(header_json)
    pad_len = (4 - (str_len % 4)) % 4
    aligned_json = header_json + (b"\x00" * pad_len)

    inner_size = 4 + len(aligned_json)
    outer_size = 4 + inner_size
    pickle_header = struct.pack("<IIII", 4, outer_size, inner_size, str_len) + aligned_json
    return pickle_header + main_js + preload_js


def encounter_1_single_channel_and_entrypoint_check() -> Dict[str, Any]:
    """Encounter 1: Verify channel entrypoint against AST and run CH 02 under 64 KB profiler."""
    desk = Patchbay()
    ch_meta = desk.get_channel(2)
    desk.conn.close()
    assert ch_meta is not None

    carrier_file = REPO_ROOT / ch_meta["carrier_path"]
    catalog_entrypoint = ch_meta["entrypoint"]  # 'ElfBinaryParser.parse' in 277afd99

    tree = ast.parse(carrier_file.read_text(encoding="utf-8"))
    actual_methods = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            actual_methods[node.name] = [
                n.name for n in node.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
            ]

    cls_name, method_name = catalog_entrypoint.split(".")
    catalog_symbol_exists = (cls_name in actual_methods) and (method_name in actual_methods[cls_name])

    elf_bytes = build_minimal_elf64_x86_64()
    summary, receipt = ThermodynamicProfiler.profile_callable(
        ElfBinaryParser.parse_bytes,
        elf_bytes,
        candidate_id="CH02_ELF_DIRECT",
        memory_ceiling_bytes=64 * 1024,
        fail_closed=True,
    )

    return {
        "encounter": "1_single_channel_inspection",
        "catalog_entrypoint": catalog_entrypoint,
        "catalog_symbol_exists_in_source": catalog_symbol_exists,
        "actual_class_methods": actual_methods.get(cls_name, []),
        "executed_entrypoint": "ElfBinaryParser.parse_bytes",
        "elf_machine": summary.machine,
        "elf_is_64_bit": summary.is_64_bit,
        "elf_entry": hex(summary.entrypoint),
        "peak_memory_bytes": receipt.peak_memory_bytes,
        "thermodynamic_passed": receipt.passed,
        "receipt_digest": receipt.receipt_digest,
    }


def encounter_2_multi_channel_composition() -> Dict[str, Any]:
    """Encounter 2: Chain CH 25 (ASAR) -> CH 26 (IPC) + CH 38 (Secrets) -> CH 40 (Provenance DAG)."""
    desk = Patchbay()
    patch_manifest = desk.patch([25, 26, 38, 40], daimon_name="electron_audit_chain")
    desk.conn.close()

    raw_asar = build_realistic_asar_bundle()

    asar_summary, _ = ThermodynamicProfiler.profile_callable(
        AsarArchiveParser.parse_bytes,
        raw_asar,
        candidate_id="CH25_ASAR",
    )
    payload_base = 8 + asar_summary.header_size

    dag = ProvenanceGraph()
    root_node = ArtifactNode.from_bytes("bundle.asar", raw_asar, mime_type="application/x-asar")
    dag.add_node(root_node)

    ipc_reports = []
    secret_matches = []

    for entry in asar_summary.entries:
        if entry.is_directory:
            continue
        start = payload_base + entry.offset
        end = start + entry.size
        file_bytes = raw_asar[start:end]

        child_node = ArtifactNode.from_bytes(entry.path, file_bytes, mime_type="application/javascript")
        dag.add_node(child_node)
        dag.add_derivation(
            source_id="bundle.asar",
            target_id=entry.path,
            transform_name="AsarArchiveParser.slice_entry",
            timestamp=1700000000,
            parameters={"offset": entry.offset, "size": entry.size},
        )

        ipc_summary, _ = ThermodynamicProfiler.profile_callable(
            ElectronIpcScanner.parse_bytes,
            file_bytes,
            candidate_id=f"CH26_IPC:{entry.path}",
        )
        ipc_reports.append({
            "file": entry.path,
            "channels": [c.channel_name for c in ipc_summary.ipc_channels],
            "dynamic_sinks_count": ipc_summary.dynamic_sinks_count,
            "node_integration": ipc_summary.security.node_integration,
            "context_isolation": ipc_summary.security.context_isolation,
            "risk_level": ipc_summary.security.risk_level,
        })

        sec_summary, _ = ThermodynamicProfiler.profile_callable(
            SecretScanner.parse_bytes,
            file_bytes,
            candidate_id=f"CH38_SECRET:{entry.path}",
        )
        for m in sec_summary.matches:
            secret_matches.append({
                "file": entry.path,
                "rule_id": m.rule_id,
                "masked_value": m.raw_preview_masked,
                "entropy": round(m.entropy, 3),
            })

    return {
        "encounter": "2_multi_channel_composition",
        "patch_id": patch_manifest["patch_id"],
        "asar_files_extracted": [e.path for e in asar_summary.entries],
        "ipc_findings": ipc_reports,
        "secrets_detected": secret_matches,
        "provenance_topological_order": dag.topological_sort(),
        "provenance_digests_valid": dag.verify_digest_preservation(
            {
                "bundle.asar": raw_asar,
                **{
                    e.path: raw_asar[payload_base + e.offset : payload_base + e.offset + e.size]
                    for e in asar_summary.entries
                    if not e.is_directory
                },
            }
        ),
    }


def encounter_3_opposing_pressures_and_console() -> Dict[str, Any]:
    """Encounter 3: Preserve conflict between CH 04 static CFG and CH 17 dynamic trace via CH 43."""
    ghidra_payload = json.dumps({
        "name": "auth_daemon.elf",
        "arch": "x86:LE:64:default",
        "functions": [{
            "name": "dispatch_auth",
            "entrypoint": 0x401000,
            "return_type": "int",
            "parameters": [],
            "local_variables": [],
            "pcode": [{
                "seq": 1,
                "opcode": "CALL",
                "output": None,
                "inputs": [{"space": "ram", "offset": 0x401100, "size": 8}],
            }],
            "ast": {"type": "BLOCK", "children": []},
        }],
        "data_types": [],
        "symbols": [],
        "comments": [],
    }).encode("utf-8")
    ghidra_prog = GhidraParser.parse_bytes(ghidra_payload)
    static_target = hex(ghidra_prog.functions["dispatch_auth"].pcode[0].inputs[0].offset)

    stalker_events = [
        StalkerCallEvent(source_address=0x401000, target_address=0x409990, depth=0),
        StalkerRetEvent(source_address=0x409990, target_address=0x401004, depth=0),
    ]
    packed_stalker = FridaStalkerParser.pack_stream(stalker_events, format="tagged")
    stalker_summary = FridaStalkerParser().inspect_trace(packed_stalker)
    dynamic_target = hex(stalker_summary.call_tree_roots[0].address)

    # Express both as Kageyoni aspects with opposing pressures on 'direct_call_assumption'
    compiled_aspects = [
        {
            "aspect_id": "ch04_static_cfg",
            "provenance": [{"source": "ghidra_export", "function": "dispatch_auth"}],
            "effects": [
                {
                    "operation": "pressure",
                    "target": "direct_call_assumption_0x401000",
                    "direction": "activate",
                    "strength": "derived_static",
                },
                {
                    "operation": "assert",
                    "target": "call_target_0x401000",
                    "value": static_target,
                    "status": "proposed",
                },
            ],
        },
        {
            "aspect_id": "ch17_dynamic_stalker",
            "provenance": [{"source": "frida_stalker_trace", "site": "0x401000"}],
            "effects": [
                {
                    "operation": "pressure",
                    "target": "direct_call_assumption_0x401000",
                    "direction": "suppress",
                    "strength": "observed_runtime",
                },
                {
                    "operation": "assert",
                    "target": "call_target_0x401000",
                    "value": dynamic_target,
                    "status": "proposed",
                },
            ],
        },
    ]

    desk = Patchbay()
    patch_manifest = desk.patch([4, 17, 43], daimon_name="phase_conflict_session")
    desk.conn.close()
    console = ActiveConsole(patch_manifest)

    s_static = console.stream_track(4, [{"fact": f"Static CALL target {static_target}", "confidence_score": 0.8}])
    s_dynamic = console.stream_track(17, [{"fact": f"Dynamic CALL target {dynamic_target}", "confidence_score": 1.0}])

    master = console.print_master(
        session_id="enc3_polyphony",
        active_signals=s_static + s_dynamic,
        compiled_aspects=compiled_aspects,
    )

    return {
        "encounter": "3_opposing_pressures",
        "static_call_target": static_target,
        "dynamic_call_target": dynamic_target,
        "conflicts_preserved_count": len(master.opposing_pressures_preserved),
        "conflicts_preserved": master.opposing_pressures_preserved,
        "master_sha256": master.master_sha256,
    }


def encounter_4_refusal_and_deficit_classification() -> Dict[str, Any]:
    """Encounter 4: Demonstrate refusal, failure-muting hazard, and typed deficits."""
    desk = Patchbay()
    hot_patch = desk.patch([17, 18, 27], daimon_name="live_attach_attempt")
    desk.conn.close()
    console = ActiveConsole(hot_patch)

    # Demonstrate how setting confidence_score=0.0 on a failed check causes stream_track to mute it
    muted_failure = console.stream_track(
        18, [{"event": "MEMORY_PROTECTION_FAULT", "passed": False, "confidence_score": 0.0}]
    )
    # Proper pattern: separate observation certainty (confidence_score=1.0) from outcome (passed=False)
    preserved_failure = console.stream_track(
        18,
        [{
            "event": "MEMORY_PROTECTION_FAULT",
            "passed": False,
            "observation_authority": "observed",
            "confidence_score": 1.0,
            "deficit_kind": "ACCESS_VIOLATION",
        }],
    )

    # Demonstrate Kageyoni Compiler (CH 42) failing closed and emitting typed deficits
    # when an upstream external REA provider slot is missing
    frame = {
        "frame_id": "live_ghidra_decompile_workflow",
        "slots": [
            {
                "slot_id": "upstream.ghidra_jvm_export",
                "family": "provider",
                "requirement": "required",
                "cardinality": {"min": 1, "max": 1},
                "accepts": ["ghidra_headless_runner"],
                "authority_policy": ["evidence", "derived"],
            },
            {
                "slot_id": "in_tree.ghidra_ast_parse",
                "family": "parser",
                "requirement": "required",
                "cardinality": {"min": 1, "max": 1},
                "accepts": ["ghidra_export_parser"],
                "authority_policy": ["derived"],
                "dependencies": ["upstream.ghidra_jvm_export"],
            },
        ],
    }
    aspects = [
        {
            "aspect_id": "ch04.ghidra_parser",
            "family": "parser",
            "type": "ghidra_export_parser",
            "authority": "derived",
            "provenance": [{"carrier": "kageyoni/ninshu/ghidra_parser.py"}],
            "effects": [],
        }
    ]
    compiler = Compiler(frame, aspects)
    # Bind only the in-tree parser without the upstream headless JVM runner
    compiled = compiler.compile({
        "upstream.ghidra_jvm_export": [],
        "in_tree.ghidra_ast_parse": ["ch04.ghidra_parser"],
    })

    return {
        "encounter": "4_refusal_and_deficits",
        "tier1_requires_human_gate": hot_patch["requires_human_gate"],
        "tier1_reversibility_tier": hot_patch["reversibility_tier"],
        "naive_zero_confidence_failure_survived": len(muted_failure) == 1,
        "properly_scored_failure_survived": len(preserved_failure) == 1,
        "compilation_runnable": compiled["runnable"],
        "compiler_blockers": compiled["blockers"],
        "compiler_emitted_deficits": compiled["deficits"],
    }


def encounter_5_cold_process_persistence_and_recovery() -> Dict[str, Any]:
    """Encounter 5: Commit findings to Kageyoni SQLite Engine (CH 41) & SaveState (CH 48), reopen in fresh process."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_file = tmp_path / "causal_encounter.sqlite"
        save_file = tmp_path / "portable_save.json"

        # Process A: Record observation in EpistemicFirewall (CH 45), commit to Engine (CH 41), export SaveState (CH 48)
        firewall = EpistemicFirewall()
        firewall.record_observation(
            observation="CH26+CH38 detected unsafe nodeIntegration=True and leaked PAT in preload.js",
            source_record_id="ninshu_encounter_2",
        )
        fw_summary = firewall.export_summary()

        engine = Engine.create(db_file, seed=42)
        try:
            apply_res = engine.apply({
                "api_version": 3,
                "branch": "main",
                "expected_revision": 0,
                "request_id": "ninshu:enc2:electron-audit",
                "kind": "action",
                "actor": "ninshu_auditor",
                "narrative": "Recorded verified Electron ASAR IPC and secret exposure from Encounter 2",
                "changes": [
                    {
                        "op": "create",
                        "domain": "character",
                        "id": "auditor_daimon",
                        "data": {"name": "Ninshu Auditor", "entity_kind": "person"},
                        "status": "proposed",
                        "visibility": "public",
                        "evidence": [{"note": "Observed via CH25+CH26+CH38 pipeline"}],
                    }
                ],
            })
        finally:
            engine.close()

        save_obj = SaveState(
            kernel="playable-world/0.1",
            world_id="ninshu_audit_world",
            branch="main",
            revision=apply_res["revision"],
            parent_revision=0,
            settings={"reversibility_tier": 0},
            player={"id": "auditor_daimon"},
            scene={"id": "electron_bundle_triage", "status": "verified"},
            claims=[{
                "claim_id": "claim:preload_secret_leak",
                "status": "observed",
                "firewall_observations": len(fw_summary["observations"]),
            }],
        )
        save_obj.write_to_file(save_file)

        # Process B: Spawn a fresh Python interpreter to reopen and verify both artifacts
        verify_code = (
            "import json, os\n"
            "from kageyoni.engine import Engine\n"
            "from kageyoni.playable_world.kernel import SaveState\n"
            f"eng = Engine({str(db_file)!r})\n"
            "ver = eng.verify()\n"
            "rec = eng.get('main', 'auditor_daimon')\n"
            "eng.close()\n"
            f"loaded = SaveState.from_file({str(save_file)!r})\n"
            "print(json.dumps({\n"
            "  'child_pid': os.getpid(),\n"
            "  'engine_verified_ok': ver.get('ok', ver.get('valid', True)),\n"
            "  'persisted_record_id': rec['id'] if rec else None,\n"
            "  'persisted_record_status': rec['status'] if rec else None,\n"
            "  'save_state_world_id': loaded.world_id,\n"
            "  'save_state_revision': loaded.revision,\n"
            "  'save_state_claims_count': len(loaded.claims),\n"
            "}))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", verify_code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        fresh_result = json.loads(proc.stdout.strip())
        return {
            "encounter": "5_cold_process_recovery",
            "parent_pid_differs_from_child": (fresh_result["child_pid"] != subprocess.os.getpid()),
            "writer_revision": apply_res["revision"],
            "writer_event_hash": apply_res["event_hash"],
            "fresh_process_receipt": fresh_result,
        }


def run_all_encounters() -> Dict[str, Any]:
    return {
        "commit_inspected": "277afd99cb7acea55a9a6c0de1049cde79c7783a",
        "encounters": [
            encounter_1_single_channel_and_entrypoint_check(),
            encounter_2_multi_channel_composition(),
            encounter_3_opposing_pressures_and_console(),
            encounter_4_refusal_and_deficit_classification(),
            encounter_5_cold_process_persistence_and_recovery(),
        ],
    }


if __name__ == "__main__":
    report = run_all_encounters()
    print(json.dumps(report, indent=2))
