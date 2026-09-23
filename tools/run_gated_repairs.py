"""
tools/run_gated_repairs.py
Kageyoni Gated Repair Order Master Orchestrator (Gates G0 through G9).

Executes gates with physical verification invariants:
PENDING -> TESTING -> FAILED -> REPAIRING -> RETESTING -> PASSED
Missing evidence/access -> BLOCKED
Changed dependencies after passing -> STALE -> RETESTING

Usage:
  python tools/run_gated_repairs.py --all
  python tools/run_gated_repairs.py --gate G1
  python tools/run_gated_repairs.py --status
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


GATES_DEFINITION = {
    "G0": {
        "title": "Establish the Real Baseline",
        "command": [sys.executable, "tools/run_gate_g0_baseline.py"],
        "description": "Multi-branch inventory, 13 historical Scars mapping, full suite baseline discovery.",
        "input_files": ["docs/V11-FROZEN-REMAINING-PLAN.md", "docs/V11-COMPLETION-LEDGER.md"],
        "output_files": ["evidence/audits/g0_baseline_inventory.json", "evidence/audits/scar_inventory.json"],
    },
    "G1": {
        "title": "Repair the Completion Checker First",
        "command": [sys.executable, "-m", "unittest", "tests/test_g1_completion_checker.py"],
        "description": "Fail closed on missing frontiers, unclosed scars, unexecuted mutations, and stale audit SHAs.",
        "input_files": ["tools/generate_qualification_record.py", "tests/test_g1_completion_checker.py"],
        "output_files": ["evidence/audits/scar_inventory.json"],
    },
    "G2": {
        "title": "Verify Source-to-Claim Support",
        "command": [sys.executable, "-m", "unittest", "tests/test_g2_g3_semantic_integrity.py"],
        "description": "Literal source assertions vs warranted claims, content hash, dates, and excerpt bounds.",
        "input_files": ["kageyoni/research_compiler/claims.py"],
        "output_files": [],
    },
    "G3": {
        "title": "Preserve Meaning Through Transformations",
        "command": [sys.executable, "-m", "unittest", "tests/test_g2_g3_semantic_integrity.py"],
        "description": "Semantic casting rejecting modality promotion ('may' -> 'does') and quantifier expansion ('some' -> 'all').",
        "input_files": ["kageyoni/research_compiler/semantic_casting.py", "contracts/epistemic_ledger.py"],
        "output_files": [],
    },
    "G4": {
        "title": "Bind Claims to Decisions and Real Effects",
        "command": [sys.executable, "-m", "unittest", "tests/test_g4_treatment_generator.py"],
        "description": "Dynamic archetype scoring against TopicModel/AudienceModel with explicit heuristic markers.",
        "input_files": ["kageyoni/research_compiler/treatment_generator.py"],
        "output_files": [],
    },
    "G5": {
        "title": "Propagate Corrections and Preserve History",
        "command": [sys.executable, "-m", "unittest", "tests/test_g5_invalidation_cascade.py"],
        "description": "Retraction engine cascading to packages, projects, section records, and warrants with cycle detection.",
        "input_files": ["kageyoni/research_compiler/invalidation_engine.py"],
        "output_files": [],
    },
    "G6": {
        "title": "Control Retrieval, Learning and Transfer",
        "command": [sys.executable, "-m", "unittest", "tests/test_g6_situation_memory_transfer.py"],
        "description": "Workspace isolation and method revocation checking in situation memory.",
        "input_files": ["kageyoni/situations/memory.py"],
        "output_files": [],
    },
    "G7": {
        "title": "Run Real Comparative and Developmental Trials",
        "command": [sys.executable, "tools/run_situation_comparative.py"],
        "description": "Real task executions across conditions A-E against cryptographically frozen fixtures.",
        "input_files": ["experiments/r5/fixtures/FIXTURE_MANIFEST.json"],
        "output_files": ["evidence/audits/comparative_trial_report.json"],
    },
    "G8": {
        "title": "Saturate and Measure Cost",
        "command": [sys.executable, "-m", "unittest", "tests/test_g8_end_to_end_saturation.py"],
        "description": "Full end-to-end transformation chain probe (source -> claim -> decision -> effect -> memory -> retrieval).",
        "input_files": ["tests/test_g8_end_to_end_saturation.py"],
        "output_files": [],
    },
    "G9": {
        "title": "Qualify and Release the Exact Build",
        "command": [sys.executable, "tools/generate_qualification_record.py"],
        "description": "Authoritative qualification record generation and mechanical verification.",
        "input_files": ["tools/generate_qualification_record.py"],
        "output_files": ["evidence/qualification/qualification.json"],
    },
}


def compute_file_hash(rel_path: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return "ABSENT"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_single_gate(gate_id: str, runner: GateRunner) -> bool:
    if gate_id not in GATES_DEFINITION:
        print(f"Unknown gate: {gate_id}")
        return False

    spec = GATES_DEFINITION[gate_id]
    current_sha = runner.get_current_git_sha()
    print(f"\n================================================================================")
    print(f"EXECUTING GATE {gate_id}: {spec['title']}")
    print(f"Description: {spec['description']}")
    print(f"Candidate SHA: {current_sha}")
    print(f"Command: {' '.join(spec['command'])}")
    print(f"================================================================================")

    # Calculate input hashes
    input_hashes = {f: compute_file_hash(f) for f in spec.get("input_files", [])}

    # Execute physical command
    start = time.time()
    res = subprocess.run(spec["command"], cwd=ROOT, capture_output=True, text=True)
    duration = time.time() - start

    output_hashes = {f: compute_file_hash(f) for f in spec.get("output_files", [])}

    if res.returncode != 0:
        print(f"[GATE {gate_id} FAILED] Exit code: {res.returncode}")
        print(f"Stderr:\n{res.stderr}")
        print(f"Stdout:\n{res.stdout}")
        record = GateExecutionRecord(
            gate_id=gate_id,
            candidate_sha=current_sha,
            status=GateStatus.FAILED,
            command=" ".join(spec["command"]),
            exit_code=res.returncode,
            test_ids=[gate_id],
            failures=[res.stderr.strip() or "Nonzero exit code"],
            skips=[],
            input_hashes=input_hashes,
            output_hashes=output_hashes,
            evidence_refs=[str(ROOT / f) for f in spec.get("output_files", [])],
            details={"duration": duration, "stderr": res.stderr, "stdout": res.stdout},
        )
        runner.record_execution(record)
        return False

    print(res.stdout.strip())
    print(f"[GATE {gate_id} PASSED] (Elapsed: {round(duration, 3)}s)")

    record = GateExecutionRecord(
        gate_id=gate_id,
        candidate_sha=current_sha,
        status=GateStatus.PASSED,
        command=" ".join(spec["command"]),
        exit_code=0,
        test_ids=[gate_id],
        failures=[],
        skips=[],
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        evidence_refs=[str(ROOT / f) for f in spec.get("output_files", [])],
        details={"duration": duration},
    )
    runner.record_execution(record)
    return True


def show_status(runner: GateRunner):
    current_sha = runner.get_current_git_sha()
    print(f"\nKageyoni Gated Repair Order Registry Status")
    print(f"Current Git SHA: {current_sha}\n")
    print(f"{'Gate':<6} | {'Title':<42} | {'Status':<10} | {'Exit':<5} | {'SHA Match'}")
    print("-" * 80)
    for gid, spec in GATES_DEFINITION.items():
        rec = runner.get_record(gid)
        if not rec:
            print(f"{gid:<6} | {spec['title']:<42} | {'PENDING':<10} | {'-':<5} | -")
        else:
            sha_match = "MATCH" if rec.candidate_sha == current_sha else f"DIVERGED ({rec.candidate_sha[:7]})"
            print(f"{gid:<6} | {spec['title']:<42} | {rec.status.value:<10} | {rec.exit_code:<5} | {sha_match}")
    print("")


def main():
    parser = argparse.ArgumentParser(description="Kageyoni Gated Repair Order Master Orchestrator")
    parser.add_argument("--gate", type=str, help="Execute specific gate (G0 - G9)")
    parser.add_argument("--all", action="store_true", help="Execute all gates sequentially")
    parser.add_argument("--status", action="store_true", help="Display current status across all gates")
    args = parser.parse_args()

    runner = GateRunner()

    if args.status:
        show_status(runner)
        runner.close()
        return 0

    if args.gate:
        success = run_single_gate(args.gate.upper(), runner)
        runner.close()
        return 0 if success else 1

    if args.all:
        for gid in GATES_DEFINITION.keys():
            success = run_single_gate(gid, runner)
            if not success:
                print(f"\nExecution HALTED at Gate {gid} (Fail-Closed Gate Rule).")
                show_status(runner)
                runner.close()
                return 1
        print(f"\nALL GATES G0 THROUGH G9 PASSED.")
        show_status(runner)
        runner.close()
        return 0

    show_status(runner)
    runner.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
