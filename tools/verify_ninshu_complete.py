"""Master Cold-Process End-to-End Qualification Runner for Ninshū.

Executes and verifies all 6 mandatory qualification gates in isolated child processes:
- Gate 1: `tools/audit_completion.py` in a fresh subprocess -> confirms 48/48 channels resolve and execute via `Patchbay.execute_channel()`.
- Gate 2: `tests.test_ninshu_patchbay_wiring` (8/8 tests including real WSL specimens in `\\wsl.localhost\\Ubuntu\\home\\flowe`).
- Gate 3: `tests.test_ssl_control_contract` (40/40 tests: expected-effect + absence-of-effect for all 20 SSL controls).
- Gate 4: `tests.test_ninshu_rea_parity` (19/19 tests: `js_ast_analyzer`, `adb_bridge`, `kuna_inspector`, `provider_bridge`, sequential x86/ARM64 `raw_binary_parser`, plus real WSL specimens).
- Gate 5: `tests.test_ninshu_molten_smelter` (8/8 tests: unknown specimen -> `MoltenSmelter` -> `MechanicalAuditorGate` -> SQLite hot-mount -> 8-knob `NinshuPowerSystem` modulation).
- Gate 6: Cold-process persistence verification: exports a signed `MasterTape` to `master_print.json`, then spawns a separate Python subprocess that opens `ninshu_codex.sqlite` and verifies the `MasterTape` / `master_print.json` SHA-256 cryptographic digest.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.ninshu.console import ActiveConsole
from kageyoni.ninshu.patchbay import Patchbay


_COLD_PERSISTENCE_VERIFIER_SCRIPT = r"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

db_path = Path(sys.argv[1]).resolve()
master_print_path = Path(sys.argv[2]).resolve()
expected_master_sha256 = sys.argv[3]

if not db_path.exists():
    raise FileNotFoundError(f"SQLite codex not found at {db_path}")
if not master_print_path.exists():
    raise FileNotFoundError(f"Master print file not found at {master_print_path}")

# 1. Fresh-process SQLite inspection
from kageyoni.ninshu.patchbay import compute_seeds_digest
conn = sqlite3.connect(str(db_path))
try:
    cur = conn.execute("SELECT COUNT(*) FROM channels WHERE channel_number BETWEEN 1 AND 48")
    channel_count = int(cur.fetchone()[0])
    cur_meta = conn.execute("SELECT value FROM schema_meta WHERE key = 'seeds_digest'")
    row = cur_meta.fetchone()
    stored_seeds_digest = row[0] if row else None
finally:
    conn.close()

expected_seeds_digest = compute_seeds_digest()
if channel_count != 48:
    raise AssertionError(f"Expected 48 base channels in SQLite, found {channel_count}")
if stored_seeds_digest != expected_seeds_digest:
    raise AssertionError(f"Seeds digest mismatch: {stored_seeds_digest} != {expected_seeds_digest}")

# 2. Fresh-process MasterTape / master_print.json cryptographic verification
raw_json = master_print_path.read_text(encoding="utf-8")
loaded = json.loads(raw_json)
recorded_sha256 = loaded.pop("master_sha256", None)

canonical_encoded = json.dumps(loaded, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
recomputed_sha256 = hashlib.sha256(canonical_encoded.encode("utf-8")).hexdigest()

if recorded_sha256 != expected_master_sha256 or recomputed_sha256 != expected_master_sha256:
    raise AssertionError(
        f"Master print SHA-256 mismatch: recorded={recorded_sha256}, "
        f"recomputed={recomputed_sha256}, expected={expected_master_sha256}"
    )
if loaded.get("verification_status") != "VERIFIED":
    raise AssertionError(f"Master print status not VERIFIED: {loaded.get('verification_status')}")

print(json.dumps({
    "cold_process_pid": os.getpid() if "os" in globals() else 0,
    "sqlite_path": str(db_path),
    "sqlite_channels_verified": channel_count,
    "seeds_digest": stored_seeds_digest,
    "master_print_sha256": recomputed_sha256,
    "verification_status": loaded.get("verification_status"),
    "passed": True,
}))
"""


def _run_subprocess(cmd: List[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, env=env)


def _parse_unittest_counts(output: str) -> Dict[str, Any]:
    m = re.search(r"Ran (\d+) tests? in ([0-9.]+)s", output)
    tests_run = int(m.group(1)) if m else 0
    duration_s = float(m.group(2)) if m else 0.0
    ok = bool(re.search(r"^OK\b", output, re.MULTILINE))
    return {"tests_run": tests_run, "duration_seconds": duration_s, "ok": ok}


def run_gate_1_audit_completion() -> Dict[str, Any]:
    t0 = time.perf_counter()
    res = _run_subprocess([sys.executable, "tools/audit_completion.py"])
    elapsed = round(time.perf_counter() - t0, 4)
    combined = res.stdout + res.stderr
    m = re.search(r"Empirically Verified Grade A \(Live\):\s+(\d+)\s*/\s*(\d+)", combined)
    verified = int(m.group(1)) if m else 0
    total = int(m.group(2)) if m else 0
    passed = res.returncode == 0 and verified == 48 and total == 48
    return {
        "gate_id": "GATE_1_AUDIT_COMPLETION_48_CHANNELS",
        "command": f"{sys.executable} tools/audit_completion.py",
        "exit_code": res.returncode,
        "verified_channels": f"{verified}/{total}",
        "duration_seconds": elapsed,
        "passed": passed,
    }


def run_unittest_gate(gate_id: str, test_module: str, expected_min_tests: int) -> Dict[str, Any]:
    t0 = time.perf_counter()
    res = _run_subprocess([sys.executable, "-m", "unittest", "-v", test_module])
    elapsed = round(time.perf_counter() - t0, 4)
    combined = res.stdout + res.stderr
    stats = _parse_unittest_counts(combined)
    passed = (
        res.returncode == 0
        and stats["ok"]
        and stats["tests_run"] >= expected_min_tests
    )
    return {
        "gate_id": gate_id,
        "test_module": test_module,
        "command": f"{sys.executable} -m unittest -v {test_module}",
        "exit_code": res.returncode,
        "tests_run": stats["tests_run"],
        "expected_tests": expected_min_tests,
        "duration_seconds": elapsed,
        "passed": passed,
    }


def run_gate_6_cold_process_persistence() -> Dict[str, Any]:
    t0 = time.perf_counter()
    pb = Patchbay()
    try:
        db_path = pb.db_path
        manifest = pb.patch([1, 2, 15, 25, 34, 41], daimon_name="cold_process_qualification")
        console = ActiveConsole(manifest)

        # Execute channel 15 to record a live thermodynamic receipt on the console
        exec_res = pb.execute_channel(15, b"\x90\x90\xc3", console=console)
        signals = console.stream_track(
            15,
            [
                {
                    "signal_type": "disassembly_verified",
                    "input_sha256": exec_res["input_sha256"],
                    "output_sha256": exec_res["output_sha256"],
                    "confidence_score": 1.0,
                    "outcome_passed": True,
                }
            ],
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            master_print_path = Path(tmp_dir) / "master_print.json"
            master_tape = console.print_master(
                session_id="ninshu_cold_process_gate6",
                active_signals=signals,
                compiled_aspects=[],
                export_path=master_print_path,
            )

            res = _run_subprocess(
                [
                    sys.executable,
                    "-c",
                    _COLD_PERSISTENCE_VERIFIER_SCRIPT,
                    str(db_path),
                    str(master_print_path),
                    master_tape.master_sha256,
                ]
            )
            elapsed = round(time.perf_counter() - t0, 4)
            if res.returncode != 0:
                return {
                    "gate_id": "GATE_6_COLD_PROCESS_PERSISTENCE",
                    "exit_code": res.returncode,
                    "duration_seconds": elapsed,
                    "passed": False,
                    "error": (res.stderr or res.stdout).strip()[-400:],
                }

            lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            receipt = json.loads(lines[-1])
            return {
                "gate_id": "GATE_6_COLD_PROCESS_PERSISTENCE",
                "exit_code": 0,
                "duration_seconds": elapsed,
                "sqlite_channels_verified": receipt["sqlite_channels_verified"],
                "seeds_digest": receipt["seeds_digest"],
                "master_print_sha256": receipt["master_print_sha256"],
                "verification_status": receipt["verification_status"],
                "passed": bool(receipt.get("passed", False)),
            }
    finally:
        pb.close()


def run_complete_qualification() -> Dict[str, Any]:
    gates = [
        run_gate_1_audit_completion(),
        run_unittest_gate("GATE_2_PATCHBAY_WIRING_48_CHANNELS", "tests.test_ninshu_patchbay_wiring", 8),
        run_unittest_gate("GATE_3_SSL_20_CONTROL_CONTRACT", "tests.test_ssl_control_contract", 40),
        run_unittest_gate("GATE_4_REA_PARITY_AND_WSL_SPECIMENS", "tests.test_ninshu_rea_parity", 19),
        run_unittest_gate("GATE_5_MOLTEN_SMELTER_AND_8KNOB", "tests.test_ninshu_molten_smelter", 8),
        run_unittest_gate("GATE_5B_ZERO_TRUST_MUTATION_GATE", "tests.test_ninshu_zero_trust_gate", 6),
        run_gate_6_cold_process_persistence(),
    ]

    all_passed = all(g.get("passed", False) for g in gates)
    report = {
        "qualification_suite": "NINSHU_COMPLETE_COLD_PROCESS_QUALIFICATION",
        "overall_verdict": "QUALIFIED" if all_passed else "REJECTED",
        "gates_total": len(gates),
        "gates_passed": sum(1 for g in gates if g.get("passed", False)),
        "gates": gates,
    }

    print("\n" + "=" * 80)
    print(" NINSHU MASTER COLD-PROCESS END-TO-END QUALIFICATION REPORT")
    print("=" * 80)
    for g in gates:
        status_tag = "PASS" if g.get("passed") else "FAIL"
        detail = (
            f"tests={g['tests_run']}/{g['expected_tests']}"
            if "tests_run" in g
            else g.get("verified_channels") or f"sha256={str(g.get('master_print_sha256', ''))[:16]}..."
        )
        print(f" [{status_tag}] {g['gate_id']:<40} | {detail:<24} | {g['duration_seconds']:.2f}s")
    print("-" * 80)
    print(f" OVERALL VERDICT: {report['overall_verdict']} ({report['gates_passed']}/{report['gates_total']} Gates Passed)")
    print("=" * 80 + "\n")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    final_report = run_complete_qualification()
    sys.exit(0 if final_report["overall_verdict"] == "QUALIFIED" else 1)
