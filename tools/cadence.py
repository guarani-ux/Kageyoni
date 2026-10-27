"""
tools/cadence.py
Living System Cadence & Health Receipt Engine for Kageyoni.

Captures system cadence across git commit, database migrations, outpost fleet,
and core test suite smoke tests. Generates verifiable receipt at .state/system_health.json.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

# Ensure standard output can print Unicode characters across all platforms
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECEIPT_REL = Path(".state") / "system_health.json"
DEFAULT_TEST_SUITE = "tests/test_dual_runners.py tests/test_migration.py -q"


def get_git_details(workspace_root: Path) -> Dict[str, Any]:
    """Capture git commit hash and commit subject from HEAD."""
    commit_hash = ""
    commit_subject = ""

    try:
        res1 = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if res1.returncode == 0:
            commit_hash = res1.stdout.strip()
    except Exception:
        pass

    try:
        res2 = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if res2.returncode == 0:
            commit_subject = res2.stdout.strip()
    except Exception:
        pass

    resolved = bool(commit_hash and len(commit_hash) >= 7)
    summary = f"{commit_hash} {commit_subject}".strip() if resolved else "UNKNOWN"

    return {
        "summary": summary,
        "hash": commit_hash,
        "short_hash": commit_hash[:8] if commit_hash else "",
        "subject": commit_subject,
        "resolved": resolved,
    }


def get_migration_details(workspace_root: Path) -> Dict[str, Any]:
    """Capture database migration count and status from files and SQLite."""
    migrations_dir = workspace_root / "kageyoni" / "database" / "migrations"
    migration_files = sorted(migrations_dir.glob("migration_*.sql")) if migrations_dir.is_dir() else []
    file_count = len(migration_files)
    first_file = migration_files[0].name if migration_files else ""
    latest_file = migration_files[-1].name if migration_files else ""

    sqlite_path = workspace_root / "build" / "kageyoni.sqlite"
    db_present = sqlite_path.is_file()
    db_applied_count = 0
    db_latest_applied = ""

    if db_present:
        try:
            import sqlite3
            conn = sqlite3.connect(str(sqlite_path))
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}

            if "migration_checks" in tables:
                cur.execute("SELECT script_name FROM migration_checks ORDER BY version ASC")
                rows = cur.fetchall()
                db_applied_count = len(rows)
                if rows:
                    db_latest_applied = rows[-1][0]
            elif "migrations" in tables:
                cur.execute("SELECT count(*) FROM migrations")
                row = cur.fetchone()
                if row:
                    db_applied_count = row[0]
            conn.close()
        except Exception:
            pass

    status = "OK" if file_count > 0 else "MISSING"

    return {
        "file_count": file_count,
        "first_migration": first_file,
        "latest_migration": latest_file,
        "db_present": db_present,
        "db_path": str(sqlite_path.relative_to(workspace_root)) if db_present else "",
        "db_applied_count": db_applied_count,
        "db_latest_applied": db_latest_applied,
        "status": status,
    }


def parse_outposts_registry(workspace_root: Path) -> List[Dict[str, str]]:
    """Parse outposts listed in OUTPOSTS.md markdown table."""
    outposts_path = workspace_root / "OUTPOSTS.md"
    if not outposts_path.is_file():
        return []

    lines = outposts_path.read_text(encoding="utf-8", errors="replace").splitlines()
    entries: List[Dict[str, str]] = []
    in_table = False

    for line in lines:
        line_s = line.strip()
        if line_s.startswith("| Outpost Name"):
            in_table = True
            continue
        if in_table and line_s.startswith("|---"):
            continue
        if in_table and line_s.startswith("|"):
            parts = [p.strip() for p in line_s.split("|")[1:-1]]
            if len(parts) >= 5:
                entries.append({
                    "name": parts[0],
                    "created_at": parts[1],
                    "mandate": parts[2],
                    "status": parts[3],
                    "tests": parts[4],
                    "wsl_path": parts[5] if len(parts) > 5 else "",
                    "host_path": parts[6] if len(parts) > 6 else "",
                })
        elif in_table and not line_s.startswith("|"):
            in_table = False

    return entries


def run_core_tests(
    workspace_root: Path,
    suite: Optional[str] = None,
    skip_tests: bool = False,
) -> Dict[str, Any]:
    """Execute pytest smoke test suite and collect duration and counts."""
    if skip_tests:
        return {
            "summary": "SKIPPED (--skip-tests flag passed)",
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration_seconds": 0.0,
            "returncode": 0,
            "status": "SKIPPED",
            "command": "None",
        }

    suite_str = suite if suite else DEFAULT_TEST_SUITE
    cmd = [sys.executable, "-m", "pytest"] + suite_str.split()

    start_time = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        duration = time.perf_counter() - start_time
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        combined_output = f"{stdout}\n{stderr}".strip()

        passed = 0
        failed = 0
        skipped = 0

        m_passed = re.search(r"(\d+)\s+passed", combined_output)
        if m_passed:
            passed = int(m_passed.group(1))

        m_failed = re.search(r"(\d+)\s+failed", combined_output)
        if m_failed:
            failed = int(m_failed.group(1))

        m_skipped = re.search(r"(\d+)\s+skipped", combined_output)
        if m_skipped:
            skipped = int(m_skipped.group(1))

        m_time = re.search(r"in\s+([\d\.]+)s", combined_output)
        duration_reported = float(m_time.group(1)) if m_time else round(duration, 2)

        is_success = (proc.returncode == 0 and failed == 0)
        status_label = "PASSED" if is_success else "FAILED"
        summary = f"{status_label} ({passed} passed, {failed} failed in {duration_reported:.2f}s)"

        return {
            "summary": summary,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration_seconds": duration_reported,
            "returncode": proc.returncode,
            "status": status_label,
            "command": " ".join(cmd),
            "output_summary": combined_output.splitlines()[-1] if combined_output.splitlines() else "",
        }
    except Exception as exc:
        duration = time.perf_counter() - start_time
        return {
            "summary": f"ERROR ({exc})",
            "passed": 0,
            "failed": 1,
            "skipped": 0,
            "duration_seconds": round(duration, 2),
            "returncode": 1,
            "status": "ERROR",
            "command": " ".join(cmd),
            "output_summary": str(exc),
        }


def collect_system_cadence(
    workspace_root: Optional[Path] = None,
    suite: Optional[str] = None,
    skip_tests: bool = False,
) -> Dict[str, Any]:
    """Collect all cadence components and determine overall health."""
    root = workspace_root or WORKSPACE_ROOT
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    git_info = get_git_details(root)
    migration_info = get_migration_details(root)
    outposts = parse_outposts_registry(root)
    test_results = run_core_tests(root, suite=suite, skip_tests=skip_tests)

    # Health criteria:
    # 1. Tests pass (or skipped)
    # 2. Git hash resolved
    # 3. DB migrations count is positive
    # 4. Outposts count is positive
    tests_healthy = (test_results["returncode"] == 0 and test_results["failed"] == 0)
    git_healthy = git_info["resolved"]
    migrations_healthy = (migration_info["file_count"] > 0)
    outposts_healthy = (len(outposts) > 0)

    is_healthy = tests_healthy and git_healthy and migrations_healthy and outposts_healthy
    overall_health = "HEALTHY" if is_healthy else "DEGRADED"

    receipt = {
        "git_commit": git_info["summary"],
        "timestamp": timestamp,
        "core_status": test_results["summary"],
        "database_migrations": migration_info["file_count"],
        "outposts_registered": len(outposts),
        "overall_health": overall_health,
        "git_details": {
            "hash": git_info["hash"],
            "short_hash": git_info["short_hash"],
            "subject": git_info["subject"],
            "resolved": git_info["resolved"],
        },
        "core_status_details": test_results,
        "database_migrations_details": migration_info,
        "outposts": outposts,
    }

    return receipt


def collect_health_receipt(
    workspace_root: Optional[Path] = None,
    suite: Optional[str] = None,
    skip_tests: bool = False,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Collect system cadence and optionally persist health receipt JSON."""
    receipt = collect_system_cadence(
        workspace_root=workspace_root,
        suite=suite,
        skip_tests=skip_tests,
    )
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def render_terminal_table(receipt: Dict[str, Any], receipt_path: Path) -> None:
    """Render a clean, formatted ASCII/Unicode terminal table."""
    health = receipt["overall_health"]
    timestamp = receipt["timestamp"]
    git_commit = receipt["git_commit"]
    core_status = receipt["core_status"]
    db_count = receipt["database_migrations"]
    db_details = receipt.get("database_migrations_details", {})
    first_mig = db_details.get("first_migration", "N/A")
    latest_mig = db_details.get("latest_migration", "N/A")
    applied_in_db = db_details.get("db_applied_count", 0)
    outposts = receipt.get("outposts", [])

    health_symbol = "[+] HEALTHY" if health == "HEALTHY" else "[!] DEGRADED"

    sep_double = "=" * 80
    sep_single = "-" * 80

    print(sep_double)
    print("                      KAGEYONI LIVING SYSTEM CADENCE & HEALTH")
    print(sep_double)
    print(f"  Overall Health:     {health_symbol}")
    print(f"  Timestamp (UTC):    {timestamp}")
    print(f"  Git HEAD:           {git_commit}")
    print(f"  Core Test Suite:    {core_status}")
    print(
        f"  DB Migrations:      {db_count} files ({first_mig} -> {latest_mig}) "
        f"| build/kageyoni.sqlite: {applied_in_db} applied"
    )
    print(f"  Outposts Fleet:     {len(outposts)} registered active")
    print(sep_single)
    print("  OUTPOST FLEET ROSTER:")
    if outposts:
        for op in outposts:
            name = op.get("name", "unknown")
            status = op.get("status", "UNKNOWN")
            tests = op.get("tests", "UNKNOWN")
            mandate = op.get("mandate", "")
            wsl_path = op.get("wsl_path", "")
            print(f"    * {name:<16} [{status} | Tests: {tests}]")
            print(f"      Mandate:  {mandate}")
            print(f"      WSL Path: {wsl_path}")
    else:
        print("    (No outposts registered in OUTPOSTS.md)")
    print(sep_single)
    print(f"  Receipt Path:       {receipt_path}")
    print(sep_double)


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser for CLI interface."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.runner cadence",
        description="Generate living system cadence and health receipt (.state/system_health.json).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=str(DEFAULT_RECEIPT_REL),
        help="Path where system_health.json receipt will be written (default: .state/system_health.json).",
    )
    parser.add_argument(
        "--suite",
        type=str,
        default=None,
        help="Pytest test suite arguments (default: tests/test_dual_runners.py tests/test_migration.py -q).",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip executing the core pytest smoke test suite.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print raw JSON receipt output only, suppressing terminal table formatting.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main entrypoint for cadence tool execution."""
    parser = build_parser()
    args = parser.parse_args(argv)

    receipt = collect_system_cadence(
        workspace_root=WORKSPACE_ROOT,
        suite=args.suite,
        skip_tests=args.skip_tests,
    )

    # Resolve output path
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = WORKSPACE_ROOT / out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    if args.json_only:
        print(json.dumps(receipt, indent=2))
    else:
        render_terminal_table(receipt, out_path)

    return 0 if receipt["overall_health"] == "HEALTHY" else 1


if __name__ == "__main__":
    sys.exit(main())
