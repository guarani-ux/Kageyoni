"""
tools/run_magnet_verification.py
MAGNET-AND-STATE VERIFICATION RUNNER

Enforces the 6 Gates of Magnet-and-State Verification in exact sequential order:
G1 — CONTRACT AND COVERAGE (Zero verification gaps, all behaviors mapped to observable state)
G2 — SEMANTIC PRESERVATION (Magnet families A, B, C, D)
G3 — EFFECT AND RECOVERY (Magnet family E, atomic commit, rollback, idempotency)
G4 — DOWNSTREAM INTEGRITY (Cascading retractions, memory boundaries, revocation)
G5 — VERIFIER SENSITIVITY (Mutation checks: mutants killed, clean controls pass)
G6 — WHOLE-SYSTEM QUALIFICATION (Exact candidate commit qualification, parity, clean install)

Rules:
- Uses Kageyoni's existing state, evidence, dependency and Scar mechanisms.
- Does not create a separate verification engine.
- Every gate physically executes live; NO skipping or caching.
- Failure at any gate blocks dependent advancement immediately.
"""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kageyoni.gate_runner import GateRunner, GateStatus, GateExecutionRecord

CONTRACT_PATH = ROOT / "docs" / "MAGNET-AND-STATE-CONTRACT.json"

MAGNET_GATES = {
    "G1": {
        "title": "Contract and Coverage",
        "description": "Verify read-only contract completeness; map every required behavior to state, transitions, and observable results.",
        "command": [sys.executable, "tools/verify_magnet_contract.py"],
        "input_files": ["docs/MAGNET-AND-STATE-CONTRACT.json"],
        "output_files": [],
    },
    "G2": {
        "title": "Semantic Preservation",
        "description": "Magnet families A, B, C, D: paraphrase equivalence, boundary reassessments, state dependence, and label stability.",
        "command": [
            sys.executable, "-m", "unittest",
            "tests/test_magnet_verification.py",
            "tests/test_g2_g3_semantic_integrity.py",
        ],
        "input_files": ["tests/test_magnet_verification.py", "kageyoni/research_compiler/semantic_casting.py"],
        "output_files": [],
    },
    "G3": {
        "title": "Effect and Recovery",
        "description": "Magnet family E: authorized effects, prohibited effects, partial execution resume, atomic commit rollback.",
        "command": [
            sys.executable, "-m", "unittest",
            "tests.test_magnet_verification.TestMagnetDeltaVerification.test_failure_and_recovery_decisive_cast",
            "tests.test_situation_runtime.RuntimeTests",
        ],
        "input_files": ["tests/test_magnet_verification.py", "kageyoni/situations/runtime.py"],
        "output_files": [],
    },
    "G4": {
        "title": "Downstream Integrity",
        "description": "Cascading invalidation across source -> claim -> decision -> memory -> retrieval; workspace isolation; method revocation.",
        "command": [
            sys.executable, "-m", "unittest",
            "tests/test_g5_invalidation_cascade.py",
            "tests/test_g6_situation_memory_transfer.py",
            "tests/test_g8_end_to_end_saturation.py",
        ],
        "input_files": ["kageyoni/research_compiler/invalidation_engine.py", "kageyoni/situations/memory.py"],
        "output_files": [],
    },
    "G5": {
        "title": "Verifier Sensitivity",
        "description": "Mutation testing: deliberately weaken safeguards in isolated copies; verify 100% mutants killed; valid control passes.",
        "command": [sys.executable, "tools/situation_mutation_check.py"],
        "input_files": ["tools/situation_mutation_check.py"],
        "output_files": [],
    },
    "G6": {
        "title": "Whole-System Qualification",
        "description": "R5 comparative trials against frozen fixtures and release qualification record derivation.",
        "command": [
            sys.executable, "tools/run_situation_comparative.py",
        ],
        "input_files": ["experiments/r5/fixtures/FIXTURE_MANIFEST.json", "tools/run_situation_comparative.py"],
        "output_files": ["evidence/audits/comparative_trial_report.json"],
    },
}


def compute_file_hash(rel_path: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return "ABSENT"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute_gate(gate_id: str, runner: GateRunner) -> bool:
    spec = MAGNET_GATES[gate_id]
    current_sha = runner.get_current_git_sha()
    print(f"\n{'='*80}")
    print(f"MAGNET GATE {gate_id}: {spec['title'].upper()}")
    print(f"Description: {spec['description']}")
    print(f"Candidate SHA: {current_sha}")
    print(f"{'='*80}")

    input_hashes = {f: compute_file_hash(f) for f in spec.get("input_files", [])}

    start = time.time()
    res = subprocess.run(spec["command"], cwd=ROOT, capture_output=True, text=True)
    duration = time.time() - start

    output_hashes = {f: compute_file_hash(f) for f in spec.get("output_files", [])}

    if res.returncode != 0:
        print(f"\n[MAGNET GATE {gate_id} FAILED] Exit code: {res.returncode}")
        if res.stderr:
            print(f"Stderr:\n{res.stderr.strip()}")
        if res.stdout:
            print(f"Stdout:\n{res.stdout.strip()}")

        record = GateExecutionRecord(
            gate_id=f"MAGNET_{gate_id}",
            candidate_sha=current_sha,
            status=GateStatus.FAILED,
            command=" ".join(spec["command"]) if isinstance(spec["command"], list) else str(spec["command"]),
            exit_code=res.returncode,
            test_ids=[f"MAGNET_{gate_id}"],
            failures=[res.stderr.strip() or "Nonzero exit code"],
            skips=[],
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            evidence_refs=[str(ROOT / f) for f in spec.get("output_files", [])],
            details={"duration": duration, "stderr": res.stderr, "stdout": res.stdout},
        )
        runner.record_execution(record)
        return False

    if res.stdout.strip():
        print(res.stdout.strip())
    print(f"\n[MAGNET GATE {gate_id} PASSED] (Elapsed: {round(duration, 3)}s)")

    record = GateExecutionRecord(
        gate_id=f"MAGNET_{gate_id}",
        candidate_sha=current_sha,
        status=GateStatus.PASSED,
        command=" ".join(spec["command"]) if isinstance(spec["command"], list) else str(spec["command"]),
        exit_code=0,
        test_ids=[f"MAGNET_{gate_id}"],
        failures=[],
        skips=[],
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        evidence_refs=[str(ROOT / f) for f in spec.get("output_files", [])],
        details={"duration": duration},
    )
    runner.record_execution(record)
    return True


def show_magnet_status(runner: GateRunner):
    current_sha = runner.get_current_git_sha()
    print(f"\nMAGNET-AND-STATE VERIFICATION STATUS")
    print(f"Contract: docs/MAGNET-AND-STATE-CONTRACT.json")
    print(f"Current Git SHA: {current_sha}\n")
    print(f"{'Gate':<6} | {'Title':<35} | {'Status':<10} | {'Exit':<5} | {'SHA Match'}")
    print("-" * 75)
    for gid, spec in MAGNET_GATES.items():
        rec = runner.get_record(f"MAGNET_{gid}")
        if not rec:
            print(f"{gid:<6} | {spec['title']:<35} | {'UNTESTED':<10} | {'-':<5} | -")
        else:
            sha_match = "MATCH" if rec.candidate_sha == current_sha else f"DIVERGED ({rec.candidate_sha[:7]})"
            print(f"{gid:<6} | {spec['title']:<35} | {rec.status.value:<10} | {rec.exit_code:<5} | {sha_match}")
    print("")


def main():
    parser = argparse.ArgumentParser(description="Magnet-and-State Verification Runner")
    parser.add_argument("--gate", type=str, help="Execute specific Magnet Gate (G1 - G6)")
    parser.add_argument("--all", action="store_true", help="Execute all Magnet Gates sequentially")
    parser.add_argument("--status", action="store_true", help="Display current status across all Magnet Gates")
    args = parser.parse_args()

    runner = GateRunner()

    if args.status:
        show_magnet_status(runner)
        runner.close()
        return 0

    if args.gate:
        gid = args.gate.upper()
        if gid not in MAGNET_GATES:
            print(f"Invalid gate '{gid}'. Valid gates: {list(MAGNET_GATES.keys())}")
            runner.close()
            return 1
        success = execute_gate(gid, runner)
        runner.close()
        return 0 if success else 1

    if args.all:
        print("\nStarting Sequential Execution of MAGNET-AND-STATE VERIFICATION (G1 through G6)...")
        for gid in MAGNET_GATES.keys():
            success = execute_gate(gid, runner)
            if not success:
                print(f"\nExecution HALTED at Gate {gid} (Fail-Closed Rule). Dependent advancement blocked.")
                show_magnet_status(runner)
                runner.close()
                return 1
        print(f"\nALL MAGNET GATES G1 THROUGH G6 PASSED.")
        show_magnet_status(runner)
        runner.close()
        return 0

    show_magnet_status(runner)
    runner.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
