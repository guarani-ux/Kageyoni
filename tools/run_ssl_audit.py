import json
from kageyoni.ninshu.patchbay import Patchbay
from kageyoni.ninshu.shaper import SSLMixingSession
from kageyoni.ninshu.wasm_parser import WasmParser

def run_console_audit():
    # Pass channel list directly to SSLMixingSession
    session = SSLMixingSession(
        patch_channels=[11, 45],
        operator_intent="Audit foreign binary imports against Kageyoni invariants"
    )

    print("=== SSL 4000 CONSOLE: ACTIVE MULTI-TRACK PATCH MOUNTED ===")
    for ch_num, strip in session.strips.items():
        print(f"CH {ch_num:02d} [{strip.name}]")

    # 1. RUN 1: Clean Minimal WASM
    raw_wasm = bytes.fromhex("0061736d01000000")
    summary = WasmParser.parse_bytes(raw_wasm)
    clean_signal = {
        "type": "header",
        "candidate_id": "clean_minimal_wasm",
        "version": summary.version,
        "static_claim": {"valid": True, "authorized": True},
        "dynamic_reality": {"valid": True, "authorized": True},
        "confidence_score": 1.0
    }
    session.sculpt_signal(11, clean_signal)

    print("\n>>> METER BRIDGE [TRACK 1: IN-PHASE CLEAN WASM]")
    for ch_k, m in session.read_meter_bridge().items():
        print(f"  {ch_k} -> VU In: {m['in_vu']} | Phase: {m['phase_corr']} | THD: {m['thd']} | Deficits: {m['deficits']}")

    # 2. RUN 2: Anti-Phase Binary Claim (Claim says authorized, host reality rejects unauthorized spawn)
    contradictory_signal = {
        "type": "function",
        "candidate_id": "malicious_spawn_import",
        "static_claim": {"valid": True, "authorized": True, "capability": "env.spawn"},
        "dynamic_reality": {"valid": True, "authorized": False, "capability": "env.spawn"},
        "confidence_score": 0.95
    }
    session.sculpt_signal(11, contradictory_signal)

    print("\n>>> METER BRIDGE [TRACK 2: ANTI-PHASE CLAIM CONTRADICTION (-180 DEGREE ROTATION)]")
    for ch_k, m in session.read_meter_bridge().items():
        print(f"  {ch_k} -> VU In: {m['in_vu']} | Phase: {m['phase_corr']} | THD: {m['thd']} | Deficits: {m['deficits']}")

    # 3. RUN 3: Unmodeled / Unknown Frequency Band (Outside known spectrum)
    unknown_signal = {
        "type": "exotic_gpu_shader_ir",
        "candidate_id": "spirv_binary_chunk",
        "payload_hex": "0702310700000100",
        "confidence_score": 0.8
    }
    session.sculpt_signal(11, unknown_signal)

    print("\n>>> METER BRIDGE [TRACK 3: UNMODELED INPUT -> DARK MATTER DEFICIT SOCKET]")
    for ch_k, m in session.read_meter_bridge().items():
        print(f"  {ch_k} -> VU In: {m['in_vu']} | Phase: {m['phase_corr']} | THD: {m['thd']} | Deficits: {m['deficits']}")

    print("\n=== CIRCUIT DEFICIT RESIDUE (CH 11 UNPLACED DEFICITS) ===")
    for d in session.circuits[11].unplaced_deficits:
        print(f"  [DEFICIT] Reason: {d['reason']} | Socket Needed: {d['socket_needed']}")

if __name__ == "__main__":
    run_console_audit()
