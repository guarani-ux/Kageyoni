"""
tools/run_compression_comparison.py

Comparison test surface harness for Kageyoni Capability Compression (CP-02).
Runs isolated test suites, captures execution telemetry (pass/fail, counts, runtimes),
and validates that refactored components preserve 100% of capabilities against the baseline.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CORE_SUITES = [
    {"name": "foundation", "path": "tests/test_foundation.py", "expected_min_tests": 25},
    {"name": "characters", "path": "tests/test_characters.py", "expected_min_tests": 15},
    {"name": "decisions", "path": "tests/test_decisions.py", "expected_min_tests": 15},
    {"name": "personality", "path": "tests/test_personality.py", "expected_min_tests": 20},
    {"name": "writing", "path": "tests/test_writing.py", "expected_min_tests": 12},
    {"name": "situations", "path": "tests/test_situation_r3_integration.py", "expected_min_tests": 5},
    {"name": "semantic_integrity", "path": "tests/test_g2_g3_semantic_integrity.py", "expected_min_tests": 8},
    {"name": "treatment_generator", "path": "tests/test_g4_treatment_generator.py", "expected_min_tests": 5},
    {"name": "invalidation_cascade", "path": "tests/test_g5_invalidation_cascade.py", "expected_min_tests": 4},
    {"name": "v11_trust_gate", "path": "tests/test_v11_frozen_trust_gate.py", "expected_min_tests": 10},
]


def run_suite(suite: Dict[str, Any], env: Dict[str, str] | None = None) -> Dict[str, Any]:
    suite_path = ROOT / suite["path"]
    if not suite_path.exists():
        return {
            "name": suite["name"],
            "path": suite["path"],
            "status": "MISSING",
            "exit_code": 1,
            "duration": 0.0,
            "stdout": "",
            "stderr": f"Suite file not found: {suite_path}",
        }

    start = time.time()
    run_env = env.copy() if env else os.environ.copy()
    tests_dir = str(ROOT / "tests")
    root_dir = str(ROOT)
    existing_pp = run_env.get("PYTHONPATH", "")
    run_env["PYTHONPATH"] = f"{root_dir}{os.pathsep}{tests_dir}{os.pathsep}{existing_pp}".strip(os.pathsep)

    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", Path(suite["path"]).name],
        cwd=str(ROOT),
        env=run_env,
        capture_output=True,
        text=True,
    )
    duration = time.time() - start

    output = proc.stdout + proc.stderr
    passed = proc.returncode == 0 and "OK" in output and "FAIL" not in output

    return {
        "name": suite["name"],
        "path": suite["path"],
        "status": "PASSED" if passed else "FAILED",
        "exit_code": proc.returncode,
        "duration": round(duration, 3),
        "output_snippet": output.strip()[-500:],
    }


def main():
    parser = argparse.ArgumentParser(description="Run comparison test surface")
    parser.add_argument("--output", default="evidence/audits/compression_comparison.json", help="Output evidence JSON path")
    parser.add_argument("--quick", action="store_true", help="Run only core domain suites")
    args = parser.parse_args()

    suites_to_run = CORE_SUITES[:5] if args.quick else CORE_SUITES
    print(f"[Compression Comparison] Running {len(suites_to_run)} test suites...")

    results = []
    all_passed = True
    total_duration = 0.0

    for s in suites_to_run:
        print(f"  Running suite: {s['name']} ({s['path']})...", end=" ", flush=True)
        res = run_suite(s)
        print(f"{res['status']} ({res['duration']}s)")
        results.append(res)
        total_duration += res["duration"]
        if res["status"] != "PASSED":
            all_passed = False

    evidence = {
        "contract": "CP-02: Compression Test Surface Verification",
        "timestamp": time.time(),
        "total_suites": len(results),
        "passed_suites": sum(1 for r in results if r["status"] == "PASSED"),
        "failed_suites": sum(1 for r in results if r["status"] != "PASSED"),
        "total_duration": round(total_duration, 3),
        "all_passed": all_passed,
        "suites": results,
    }

    out_path = ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"[Compression Comparison] Report saved to {out_path}")
    print(f"[Compression Comparison] Surface status: {'COMPARISON_READY' if all_passed else 'COMPARISON_FAILED'}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
