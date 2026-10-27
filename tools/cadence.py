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


def get_git_details(workspace_root: Path) -> Dict[str, Any]:
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

    return {
        "commit": commit_hash,
        "short_commit": commit_hash[:8] if commit_hash else "unknown",
        "subject": commit_subject or "unknown",
    }


def get_database_migration_count(workspace_root: Path) -> Dict[str, Any]:
    migrations_dir = workspace_root / "kageyoni" / "database" / "migrations"
    sql_files = sorted(migrations_dir.glob("migration_*.sql"))
    count = len(sql_files)
    latest = sql_files[-1].name if sql_files else "none"
    return {
        "count": count,
        "latest_file": latest,
        "directory": str(migrations_dir.relative_to(workspace_root)),
    }


def get_outposts_status(workspace_root: Path) -> Dict[str, Any]:
    outposts_md = workspace_root / "OUTPOSTS.md"
    outposts = []
    if outposts_md.is_file():
        text = outposts_md.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if (
                line.startswith("|")
                and not line.startswith("| Name")
                and not line.startswith("| Outpost")
                and not line.startswith("|:--")
                and not line.startswith("|--")
            ):
                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) >= 4 and cols[0] and cols[0] != "None":
                    status = cols[3] if len(cols) >= 4 else (cols[2] if len(cols) > 2 else "ACTIVE")
                    mandate = cols[2] if len(cols) >= 4 else (cols[1] if len(cols) > 1 else "")
                    outposts.append({
                        "name": cols[0].replace("`", ""),
                        "status": status,
                        "mandate": mandate,
                    })
    return {
        "registered_count": len(outposts),
        "outposts": outposts,
    }


def run_smoke_tests(workspace_root: Path, suite: str) -> Dict[str, Any]:
    start = time.perf_counter()
    cmd = [sys.executable, "-m", "pytest"] + suite.split()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        duration = time.perf_counter() - start
        passed = proc.returncode == 0
        return {
            "passed": passed,
            "returncode": proc.returncode,
            "duration_sec": round(duration, 3),
            "summary": "PASSED" if passed else "FAILED",
        }
    except Exception as e:
        return {
            "passed": False,
            "returncode": 1,
            "duration_sec": 0.0,
            "summary": f"ERROR: {e}",
        }


def collect_health_receipt(
    workspace_root: Optional[Path] = None,
    test_suite: str = "tests/test_diagnostics.py -q",
    skip_tests: bool = False,
) -> Dict[str, Any]:
    root = workspace_root or WORKSPACE_ROOT
    git_info = get_git_details(root)
    db_info = get_database_migration_count(root)
    outpost_info = get_outposts_status(root)

    test_info = {"passed": True, "summary": "SKIPPED", "duration_sec": 0.0} if skip_tests else run_smoke_tests(root, test_suite)
    overall_healthy = git_info["commit"] != "" and db_info["count"] > 0 and test_info["passed"]

    receipt = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_health": "HEALTHY" if overall_healthy else "DEGRADED",
        "git_commit": f"{git_info['short_commit']} ({git_info['subject']})",
        "core_status": test_info["summary"],
        "database_migrations": db_info["count"],
        "outposts_registered": outpost_info["registered_count"],
        "git_details": git_info,
        "database_details": db_info,
        "outposts_details": outpost_info,
        "test_details": test_info,
    }
    return receipt


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="System Cadence & Health Receipt Engine")
    parser.add_argument("--output", default=str(DEFAULT_RECEIPT_REL), help="Output receipt JSON path")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest execution")
    parser.add_argument("--suite", default="tests/test_diagnostics.py -q", help="Pytest suite args")
    parser.add_argument("--json-only", action="store_true", help="Output raw JSON")
    args = parser.parse_args(argv)

    receipt = collect_health_receipt(WORKSPACE_ROOT, test_suite=args.suite, skip_tests=args.skip_tests)

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = WORKSPACE_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    if args.json_only:
        print(json.dumps(receipt, indent=2))
        return 0 if receipt["overall_health"] == "HEALTHY" else 1

    print("=" * 70)
    print("  KAGEYONI SYSTEM CADENCE & HEALTH RECEIPT")
    print("=" * 70)
    print(f"  Status:      {receipt['overall_health']}")
    print(f"  Timestamp:   {receipt['timestamp']}")
    print(f"  Git HEAD:    {receipt['git_commit']}")
    print(f"  Core Tests:  {receipt['core_status']} ({receipt['test_details'].get('duration_sec', 0)}s)")
    print(f"  Migrations:  {receipt['database_migrations']} (latest: {receipt['database_details']['latest_file']})")
    print(f"  Outposts:    {receipt['outposts_registered']} registered in OUTPOSTS.md")
    print(f"  Receipt:     {out_path.relative_to(WORKSPACE_ROOT)}")
    print("=" * 70)

    return 0 if receipt["overall_health"] == "HEALTHY" else 1


if __name__ == "__main__":
    sys.exit(main())
