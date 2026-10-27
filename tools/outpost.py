"""Outpost Workflow & Tooling Engine for isolated WSL2 downstream systems."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

WSL_DISTRO = "Ubuntu"
WSL_BASE_DIR = "/home/flowe/outposts"
PRIMARY_UNC_BASE = Path(r"\\wsl$\Ubuntu\home\flowe\outposts")
FALLBACK_UNC_BASE = Path(r"\\wsl.localhost\Ubuntu\home\flowe\outposts")

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
OUTPOSTS_REGISTRY_PATH = WORKSPACE_ROOT / "OUTPOSTS.md"


def get_unc_base() -> Path:
    """Resolve the Windows UNC path to the WSL outposts base directory (or native path on non-Windows)."""
    if sys.platform != "win32":
        return Path(os.environ.get("KAGEYONI_OUTPOSTS_DIR", Path.home() / "outposts"))
    if PRIMARY_UNC_BASE.exists():
        return PRIMARY_UNC_BASE
    if FALLBACK_UNC_BASE.exists():
        return FALLBACK_UNC_BASE
    # Default to primary if neither is currently cached
    return PRIMARY_UNC_BASE


def get_outpost_unc_path(name: str) -> Path:
    """Return the Windows UNC path for an outpost."""
    return get_unc_base() / name


def get_outpost_wsl_path(name: str) -> str:
    """Return the POSIX WSL/native path for an outpost."""
    if sys.platform != "win32":
        return str(Path(os.environ.get("KAGEYONI_OUTPOSTS_DIR", Path.home() / "outposts")) / name) if "KAGEYONI_OUTPOSTS_DIR" in os.environ else f"{Path.home()}/outposts/{name}"
    return f"{WSL_BASE_DIR}/{name}"


def check_wsl_available() -> Tuple[bool, str]:
    """Verify that WSL2 and Ubuntu are available (or native POSIX on non-Windows)."""
    if sys.platform != "win32":
        if shutil.which("python3"):
            return True, "Native POSIX environment with python3 is available."
        return False, "python3 command not found in PATH."
    try:
        res = subprocess.run(
            ["wsl.exe", "-d", WSL_DISTRO, "-e", "bash", "-c", "echo WSL_READY"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if res.returncode == 0 and "WSL_READY" in res.stdout:
            return True, "WSL2 Ubuntu is available."
        return False, f"WSL returned code {res.returncode}: {res.stderr.strip()}"
    except Exception as exc:
        return False, f"Failed to execute wsl.exe: {exc}"


def run_wsl(
    cmd: str,
    cwd: Optional[str] = None,
    capture_output: bool = True,
    timeout: Optional[int] = 180,
) -> subprocess.CompletedProcess:
    """Execute a bash command inside WSL2 Ubuntu or native bash on POSIX."""
    full_cmd = f"cd {cwd} && {cmd}" if cwd else cmd
    if sys.platform != "win32":
        return subprocess.run(
            ["bash", "-c", full_cmd],
            capture_output=capture_output,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    args = ["wsl.exe", "-d", WSL_DISTRO, "-e", "bash", "-c", full_cmd]
    return subprocess.run(
        args,
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Outpost Templates Generator
# ---------------------------------------------------------------------------

def generate_charter_md(name: str, mandate: str, created_at: str) -> str:
    return f"""# Outpost Charter: {name}

> **Runtime Isolation Sandbox**: WSL2 Ubuntu (`/home/flowe/outposts/{name}`)  
> **Windows UNC Mirror**: `\\\\wsl$\\Ubuntu\\home\\flowe\\outposts\\{name}`  
> **Created At**: {created_at}  
> **Status**: ACTIVE  

---

## 1. System Contract & Mandate

### Primary Mandate
{mandate}

### Scope & Domain Fences
- **Self-Contained Execution**: All logic, tests, and dependencies reside strictly within this outpost directory.
- **Frozen Kageyōni Core Invariant**: This outpost does NOT modify, pollute, or import from the Kageyōni core repository (`c:\\Kageyoni`). It is a downstream consumer / experimental ground.
- **Virtual Environment Isolation**: All third-party packages must be installed strictly inside `.venv` in WSL. Zero global or workspace-level pip contamination.

---

## 2. Reversibility Tiers

This outpost adheres to the 3-Tier Reversibility Matrix:

| Tier | Classification | Scope inside Outpost | Confirmation Required |
|---|---|---|---|
| **Tier 0** | Autonomous Fast Loop | Local edits, running tests (`runner.py test`), running pipeline (`runner.py run`), reading `.state/` or `out/`. | Autonomous / No gate |
| **Tier 1** | Local Destructive Gate | Deleting `.state/` caches, deleting `out/` artifacts, recreating `.venv`, resetting configs. | Human / Operator checkpoint |
| **Tier 2** | Irreversible External Gate | Publishing packages, calling paid external APIs with production credentials, promoting code to Kageyōni core. | Explicit Sovereign Approval |

---

## 3. Directory Topology

```
/home/flowe/outposts/{name}/
├── .state/              # Local runtime state, checkpoints, databases
├── .venv/               # Isolated Linux Python virtual environment
├── config/              # Configuration files
│   └── settings.json    # Outpost runtime settings and parameters
├── out/                 # Generated deliverables, exports, and reports
│   └── .gitkeep
├── src/                 # Outpost source code
│   ├── __init__.py      # Package root and version metadata
│   ├── ingest.py        # Input data / telemetry ingestion
│   ├── filter.py        # Input validation, sanitization, filtering
│   ├── core.py          # Primary domain computation and logic
│   └── export.py        # Deliverable and report serialization
├── tests/               # Test suite
│   ├── __init__.py
│   └── test_smoke.py    # Day-0 verification smoke tests
├── CHARTER.md           # This system charter
├── pyproject.toml       # Linux Python project metadata
└── runner.py            # Single-gate entrypoint CLI
```

---

## 4. Operational Commands

From Windows (via Kageyōni Tool Runner):
```powershell
python -m tools.runner outpost test {name}
python -m tools.runner outpost run {name}
```

From WSL2 Ubuntu directly:
```bash
cd /home/flowe/outposts/{name}
.venv/bin/python runner.py test
.venv/bin/python runner.py run
.venv/bin/python runner.py status
```
"""


def generate_runner_py(name: str, mandate: str) -> str:
    return f"""#!/usr/bin/env python3
\"\"\"
runner.py - Single-gate entrypoint for {name} Outpost.

Provides unified commands:
  python runner.py test    - Execute test suite (Day-0 verification and regression)
  python runner.py run     - Execute primary pipeline (ingest -> filter -> core -> export)
  python runner.py status  - Display outpost health, settings, and output artifacts
\"\"\"

import argparse
import json
import os
from pathlib import Path
import sys
import unittest

OUTPOST_DIR = Path(__file__).resolve().parent
if str(OUTPOST_DIR) not in sys.path:
    sys.path.insert(0, str(OUTPOST_DIR))


def load_settings():
    settings_file = OUTPOST_DIR / "config" / "settings.json"
    if not settings_file.is_file():
        return {{"outpost_name": "{name}", "mandate": "{mandate}"}}
    with open(settings_file, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_test(verbose: bool = False) -> int:
    \"\"\"Run outpost test suite.\"\"\"
    print("=" * 60)
    print("  RUNNING TEST SUITE: {name}")
    print("=" * 60)
    test_dir = OUTPOST_DIR / "tests"
    if not test_dir.is_dir():
        print(f"Error: tests directory not found at {{test_dir}}", file=sys.stderr)
        return 1

    loader = unittest.defaultTestLoader
    suite = loader.discover(str(test_dir), pattern="test_*.py")
    verbosity = 2 if verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    if result.wasSuccessful():
        print(f"\\n✔ All {{result.testsRun}} test(s) passed successfully.")
        return 0
    else:
        print(
            f"\\n✖ Tests failed: {{len(result.failures)}} failure(s), {{len(result.errors)}} error(s).",
            file=sys.stderr,
        )
        return 1


def cmd_run(args) -> int:
    \"\"\"Run full execution pipeline: ingest -> filter -> core -> export.\"\"\"
    from src.ingest import run_ingest
    from src.filter import apply_filters
    from src.core import process_records
    from src.export import export_results

    settings = load_settings()
    print("=" * 60)
    print(f"  EXECUTING PIPELINE: {{settings.get('outpost_name', '{name}')}}")
    print(f"  Mandate: {{settings.get('mandate', '{mandate}')}}")
    print("=" * 60)

    try:
        # Step 1: Ingest
        print("[1/4] Ingesting source data...")
        raw_data = run_ingest(source=getattr(args, "input", None))
        print(f"      Ingested {{len(raw_data.get('records', []))}} record(s).")

        # Step 2: Filter
        print("[2/4] Applying filter rules and domain boundaries...")
        filtered_records = apply_filters(raw_data.get("records", []))
        print(f"      Retained {{len(filtered_records)}} valid record(s).")

        # Step 3: Core
        print("[3/4] Running core domain processing...")
        processed_data = process_records(filtered_records, settings)
        print(f"      Processed {{processed_data.get('metrics', {{}}).get('total_processed', 0)}} item(s).")

        # Step 4: Export
        print("[4/4] Generating deliverables and exports...")
        output_dir = OUTPOST_DIR / settings.get("paths", {{}}).get("output_dir", "out")
        exported = export_results(processed_data, output_dir=output_dir)
        print(f"      Generated {{len(exported)}} export artifact(s):")
        for p in exported:
            print(f"        - {{p}}")

        print("\\n✔ Pipeline execution completed successfully.")
        return 0
    except Exception as exc:
        print(f"\\n✖ Pipeline execution failed: {{exc}}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def cmd_status() -> int:
    \"\"\"Display outpost status, health, and artifacts.\"\"\"
    settings = load_settings()
    print("=" * 60)
    print(f"  OUTPOST STATUS: {{settings.get('outpost_name', '{name}')}}")
    print("=" * 60)
    print(f"  Name:        {{settings.get('outpost_name', '{name}')}}")
    print(f"  Version:     {{settings.get('version', '0.1.0')}}")
    print(f"  Mandate:     {{settings.get('mandate', '{mandate}')}}")
    print(f"  Directory:   {{OUTPOST_DIR}}")
    print(f"  Python:      {{sys.executable}} ({{sys.version.split()[0]}})")

    venv_dir = OUTPOST_DIR / ".venv"
    print(f"  Venv:        {{'Active/Found' if venv_dir.is_dir() else 'MISSING'}}")

    state_dir = OUTPOST_DIR / settings.get("paths", {{}}).get("state_dir", ".state")
    state_files = list(state_dir.glob("*")) if state_dir.is_dir() else []
    print(f"  State Files: {{len(state_files)}}")

    out_dir = OUTPOST_DIR / settings.get("paths", {{}}).get("output_dir", "out")
    out_files = [f for f in out_dir.glob("*") if f.name != ".gitkeep"] if out_dir.is_dir() else []
    print(f"  Deliverables ({{len(out_files)}}):")
    for f in out_files:
        print(f"    - {{f.name}} ({{f.stat().st_size}} bytes)")

    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=f"{name} Outpost Single-Gate Runner")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # test command
    test_p = subparsers.add_parser("test", help="Run test suite")
    test_p.add_argument("-v", "--verbose", action="store_true", help="Verbose test output")

    # run command
    run_p = subparsers.add_parser("run", help="Execute pipeline")
    run_p.add_argument("--input", "-i", type=str, default=None, help="Input data file")

    # status command
    subparsers.add_parser("status", help="Show outpost status and deliverables")

    args = parser.parse_args(argv)

    if args.command == "test":
        return cmd_test(verbose=args.verbose)
    elif args.command == "run":
        return cmd_run(args)
    elif args.command == "status":
        return cmd_status()
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
"""


def generate_pyproject_toml(name: str, mandate: str) -> str:
    return f"""[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "{name}"
version = "0.1.0"
description = "{mandate}"
readme = "CHARTER.md"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
"""


def generate_settings_json(name: str, mandate: str, created_at: str) -> str:
    data = {
        "outpost_name": name,
        "version": "0.1.0",
        "mandate": mandate,
        "created_at": created_at,
        "log_level": "INFO",
        "paths": {
            "state_dir": ".state",
            "output_dir": "out",
            "config_dir": "config",
        },
        "parameters": {},
    }
    return json.dumps(data, indent=2) + "\n"


def generate_src_init(name: str, mandate: str) -> str:
    return f"""\"\"\"
{name} Outpost Package.
Mandate: {mandate}
\"\"\"

__version__ = "0.1.0"
__mandate__ = "{mandate}"
"""


def generate_src_ingest() -> str:
    return """\"\"\"Data & Telemetry Ingestion Module.\"\"\"

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def run_ingest(source: Optional[str] = None) -> Dict[str, Any]:
    \"\"\"
    Ingest data from an external file or generate default mock records for Day-0 qualification.
    \"\"\"
    if source and Path(source).is_file():
        path = Path(source)
        try:
            with open(path, "r", encoding="utf-8") as f:
                if path.suffix.lower() == ".json":
                    data = json.load(f)
                    records = data if isinstance(data, list) else data.get("records", [data])
                else:
                    records = [
                        {"id": f"line_{i}", "content": line.strip()}
                        for i, line in enumerate(f)
                        if line.strip()
                    ]
                return {
                    "source": str(path),
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "records": records,
                }
        except Exception as exc:
            raise RuntimeError(f"Failed to read ingest source {source}: {exc}") from exc

    # Default Day-0 mock payload
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "source": "mock://internal/telemetry",
        "ingested_at": now_iso,
        "records": [
            {
                "id": "rec_001",
                "timestamp": now_iso,
                "type": "event",
                "status": "pending",
                "payload": {"metric": 42.0, "source": "node_alpha"},
            },
            {
                "id": "rec_002",
                "timestamp": now_iso,
                "type": "event",
                "status": "pending",
                "payload": {"metric": 99.5, "source": "node_beta"},
            },
            {
                "id": "rec_003_malformed",
                "timestamp": now_iso,
                "type": "corrupt",
                "status": "error",
                "payload": {},
            },
        ],
    }
"""


def generate_src_filter() -> str:
    return """\"\"\"Boundary Verification & Record Filtering Module.\"\"\"

from __future__ import annotations

from typing import Any, Dict, List, Optional


def apply_filters(
    records: List[Dict[str, Any]],
    rules: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    \"\"\"
    Filter raw records against domain boundary constraints, dropping malformed payloads.
    \"\"\"
    rules = rules or {}
    allowed_types = rules.get("allowed_types", {"event", "metric", "signal"})
    require_id = rules.get("require_id", True)

    filtered = []
    seen_ids = set()

    for rec in records:
        if not isinstance(rec, dict):
            continue
        rec_id = rec.get("id")
        if require_id and not rec_id:
            continue
        if rec_id in seen_ids:
            continue  # Deduplicate

        rec_type = rec.get("type", "unknown")
        if rec_type not in allowed_types:
            continue  # Drop unrecognized/corrupt types

        seen_ids.add(rec_id)
        filtered.append(rec)

    return filtered
"""


def generate_src_core(name: str) -> str:
    return f"""\"\"\"Primary Domain Computation & Business Logic for {name}.\"\"\"

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def process_records(
    records: List[Dict[str, Any]],
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    \"\"\"
    Execute core processing over validated records.
    \"\"\"
    settings = settings or {{}}
    outpost_name = settings.get("outpost_name", "{name}")

    processed_items = []
    total_metric = 0.0

    for rec in records:
        payload = rec.get("payload", {{}})
        metric = float(payload.get("metric", 0.0))
        total_metric += metric

        transformed = {{
            "record_id": rec.get("id"),
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "status": "verified",
            "score": round(metric * 1.15, 4),
            "origin": payload.get("source", "unknown"),
        }}
        processed_items.append(transformed)

    # Persist checkpoint to .state if state_dir exists
    state_dir = Path(settings.get("paths", {{}}).get("state_dir", ".state"))
    if state_dir.is_dir():
        checkpoint_file = state_dir / "last_run.json"
        try:
            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(
                    {{
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "count": len(processed_items),
                    }},
                    f,
                    indent=2,
                )
        except Exception:
            pass

    return {{
        "outpost": outpost_name,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": {{
            "total_processed": len(processed_items),
            "aggregate_metric": round(total_metric, 4),
            "average_metric": round(total_metric / max(len(processed_items), 1), 4),
        }},
        "items": processed_items,
    }}
"""


def generate_src_export(name: str) -> str:
    return f"""\"\"\"Deliverable & Report Exporter for {name}.\"\"\"

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def export_results(
    results: Dict[str, Any],
    output_dir: str | Path = "out",
    export_prefix: Optional[str] = None,
) -> List[str]:
    \"\"\"
    Serialize processed results into output deliverables inside out/.
    \"\"\"
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    prefix = export_prefix or "export"
    timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # 1. JSON deliverable
    json_filename = f"{{prefix}}_{{timestamp_slug}}.json"
    json_path = out_path / json_filename
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # 2. Markdown summary deliverable
    md_filename = f"{{prefix}}_summary.md"
    md_path = out_path / md_filename
    metrics = results.get("metrics", {{}})
    md_content = [
        f"# Outpost Deliverable Summary: {{results.get('outpost', '{name}')}}",
        f"**Timestamp**: {{results.get('execution_timestamp')}}",
        "",
        "## Performance Metrics",
        f"- **Total Processed**: {{metrics.get('total_processed', 0)}}",
        f"- **Aggregate Metric**: {{metrics.get('aggregate_metric', 0.0)}}",
        f"- **Average Metric**: {{metrics.get('average_metric', 0.0)}}",
        "",
        "## Verified Items",
        "| Record ID | Status | Origin | Score | Processed At |",
        "|---|---|---|---|---|",
    ]
    for item in results.get("items", []):
        md_content.append(
            f"| {{item.get('record_id')}} | {{item.get('status')}} | {{item.get('origin')}} | {{item.get('score')}} | {{item.get('processed_at')}} |"
        )
    md_content.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\\n".join(md_content) + "\\n")

    return [str(json_path), str(md_path)]
"""


def generate_tests_smoke(name: str) -> str:
    return """\"\"\"Day-0 Qualification Smoke Test.\"\"\"

import json
from pathlib import Path
import unittest

from src.ingest import run_ingest
from src.filter import apply_filters
from src.core import process_records
from src.export import export_results


class TestOutpostSmoke(unittest.TestCase):
    \"\"\"Day-0 verification smoke tests ensuring isolated outpost functions correctly.\"\"\"

    @classmethod
    def setUpClass(cls):
        cls.root_dir = Path(__file__).resolve().parent.parent

    def test_01_settings_validity(self):
        \"\"\"Verify config/settings.json exists and has mandatory schema keys.\"\"\"
        settings_file = self.root_dir / "config" / "settings.json"
        self.assertTrue(settings_file.is_file(), "config/settings.json must exist")
        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("outpost_name", data)
        self.assertIn("mandate", data)
        self.assertIn("paths", data)

    def test_02_pipeline_execution(self):
        \"\"\"Execute complete ingest -> filter -> core -> export pipeline.\"\"\"
        raw = run_ingest()
        self.assertIn("records", raw)
        self.assertGreater(len(raw["records"]), 0)

        filtered = apply_filters(raw["records"])
        self.assertTrue(len(filtered) > 0, "Filter should retain valid records")
        for rec in filtered:
            self.assertNotEqual(rec.get("type"), "corrupt")

        with open(self.root_dir / "config" / "settings.json", "r", encoding="utf-8") as f:
            settings = json.load(f)

        results = process_records(filtered, settings)
        self.assertIn("metrics", results)
        self.assertEqual(results["metrics"]["total_processed"], len(filtered))

        out_dir = self.root_dir / "out"
        exports = export_results(results, output_dir=out_dir, export_prefix="smoke_test")
        self.assertGreaterEqual(len(exports), 2)
        for ep in exports:
            self.assertTrue(Path(ep).is_file(), f"Export file {ep} must exist on disk")

    def test_03_isolation_boundary(self):
        \"\"\"Verify that runtime directory is self-contained.\"\"\"
        self.assertTrue((self.root_dir / "src").is_dir())
        self.assertTrue((self.root_dir / "tests").is_dir())
        self.assertTrue((self.root_dir / ".state").is_dir())
        self.assertTrue((self.root_dir / "out").is_dir())


if __name__ == "__main__":
    unittest.main()
"""


# ---------------------------------------------------------------------------
# Outposts Registry Management (OUTPOSTS.md)
# ---------------------------------------------------------------------------

REGISTRY_HEADER = """# Kageyōni Outpost Registry

The **Outpost Architecture** establishes WSL2 (`/home/flowe/outposts`) as an isolated runtime sandbox for new downstream systems, tool chains, and micro-applications. This guarantees that the Kageyōni core causal engine and repository remain pristine and frozen, while downstream development proceeds with native Linux tooling, dedicated `.venv` environments, and independent lifecycles.

## Invariant Fences
1. **Core Freeze**: Outposts are downstream consumers and experimental satellites. They never mutate or import core Kageyōni files without formal qualification.
2. **Runtime Isolation**: Each outpost maintains its own `.venv`, `.state/`, and `out/` directories inside `/home/flowe/outposts/<name>`.
3. **Single-Gate Entrypoint**: Every outpost implements `runner.py` with `test`, `run`, and `status` subcommands.
4. **Host Mirroring**: Windows host tools interact with outposts via the UNC path `\\\\wsl$\\Ubuntu\\home\\flowe\\outposts\\<name>` and `python -m tools.runner outpost <command>`.

## Outposts Table

| Outpost Name | Created At | Primary Mandate | Status | Tests | Path (WSL) | Path (Host) |
|---|---|---|---|---|---|---|
"""


def ensure_registry_exists() -> None:
    """Ensure OUTPOSTS.md exists with header and table format."""
    if not OUTPOSTS_REGISTRY_PATH.is_file():
        OUTPOSTS_REGISTRY_PATH.write_text(REGISTRY_HEADER, encoding="utf-8")


def update_registry(
    name: str,
    mandate: str,
    status: str,
    tests: str,
    created_at: Optional[str] = None,
) -> None:
    """Update or insert an outpost entry in OUTPOSTS.md."""
    ensure_registry_exists()
    content = OUTPOSTS_REGISTRY_PATH.read_text(encoding="utf-8")

    wsl_path = get_outpost_wsl_path(name)
    host_path = str(get_outpost_unc_path(name))
    created = created_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Table row pattern
    pattern = re.compile(rf"^\|\s*{re.escape(name)}\s*\|.*$", re.MULTILINE)
    new_row = f"| {name} | {created} | {mandate} | {status} | {tests} | `{wsl_path}` | `{host_path}` |"

    if pattern.search(content):
        updated_content = pattern.sub(lambda _: new_row, content)
    else:
        # Append row after table header if present
        table_marker = "| Outpost Name | Created At | Primary Mandate | Status | Tests | Path (WSL) | Path (Host) |\n|---|---|---|---|---|---|---|"
        if table_marker in content:
            updated_content = content.replace(
                table_marker,
                f"{table_marker}\n{new_row}",
            )
        else:
            updated_content = content.strip() + f"\n{new_row}\n"

    OUTPOSTS_REGISTRY_PATH.write_text(updated_content, encoding="utf-8")


def read_registry_table() -> List[Dict[str, str]]:
    """Parse outposts listed in OUTPOSTS.md."""
    if not OUTPOSTS_REGISTRY_PATH.is_file():
        return []
    lines = OUTPOSTS_REGISTRY_PATH.read_text(encoding="utf-8").splitlines()
    entries = []
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


# ---------------------------------------------------------------------------
# Outpost Commands: create, list, test, run, status
# ---------------------------------------------------------------------------

def cmd_create(name: str, mandate: str, skip_smoke: bool = False) -> int:
    """Create a new isolated downstream outpost in WSL2."""
    print("=" * 70)
    print("  KAGEYONI OUTPOST ENGINE: PROVISIONING NEW OUTPOST")
    print("=" * 70)

    # 1. Name validation
    if not re.match(r"^[a-zA-Z0-9_\-]+$", name):
        print(
            f"[ERROR] Invalid outpost name '{name}'. Names must be alphanumeric with dashes/underscores.",
            file=sys.stderr,
        )
        return 1

    # 2. Check WSL availability
    available, msg = check_wsl_available()
    if not available:
        print(f"[ERROR] WSL2 Ubuntu is not reachable: {msg}", file=sys.stderr)
        return 1

    unc_path = get_outpost_unc_path(name)
    wsl_path = get_outpost_wsl_path(name)

    print(f"Target Outpost: {name}")
    print(f"Primary Mandate: {mandate}")
    print(f"WSL Path:        {wsl_path}")
    print(f"Windows Path:    {unc_path}")

    # Ensure parent outposts directory exists in WSL or native
    if sys.platform != "win32":
        get_unc_base().mkdir(parents=True, exist_ok=True)
    else:
        run_wsl(f"mkdir -p {WSL_BASE_DIR}")

    if unc_path.exists():
        print(f"[ERROR] Outpost '{name}' already exists at {unc_path}.", file=sys.stderr)
        return 1

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 3. Create directory tree
    try:
        print("\n[Step 1/5] Creating directory topology...")
        for sub_dir in ["config", "src", "tests", ".state", "out"]:
            d = unc_path / sub_dir
            d.mkdir(parents=True, exist_ok=True)
            print(f"  ✔ Created {d.name}/")

        # 4. Write canonical templates with Unix line endings
        print("\n[Step 2/5] Writing canonical contract & source templates...")
        files_to_write = {
            unc_path / "CHARTER.md": generate_charter_md(name, mandate, created_at),
            unc_path / "runner.py": generate_runner_py(name, mandate),
            unc_path / "pyproject.toml": generate_pyproject_toml(name, mandate),
            unc_path / "config" / "settings.json": generate_settings_json(name, mandate, created_at),
            unc_path / "src" / "__init__.py": generate_src_init(name, mandate),
            unc_path / "src" / "ingest.py": generate_src_ingest(),
            unc_path / "src" / "filter.py": generate_src_filter(),
            unc_path / "src" / "core.py": generate_src_core(name),
            unc_path / "src" / "export.py": generate_src_export(name),
            unc_path / "tests" / "__init__.py": f'"""Tests for {name}."""\n',
            unc_path / "tests" / "test_smoke.py": generate_tests_smoke(name),
            unc_path / "out" / ".gitkeep": "",
        }

        for path, content in files_to_write.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            print(f"  ✔ Wrote {path.relative_to(unc_path)}")

        # Make runner.py executable in WSL
        run_wsl(f"chmod +x {wsl_path}/runner.py")

    except Exception as exc:
        print(f"[ERROR] Failed to write template files: {exc}", file=sys.stderr)
        return 1

    # 5. Provision isolated .venv inside WSL
    print("\n[Step 3/5] Provisioning isolated Linux Python virtual environment (.venv)...")
    res_venv = run_wsl(f"cd {wsl_path} && python3 -m venv .venv")
    if res_venv.returncode != 0:
        print(f"[ERROR] Failed to create .venv in WSL: {res_venv.stderr}", file=sys.stderr)
        return 1
    print("  ✔ .venv instantiated successfully in WSL.")

    # 6. Run Day-0 verification smoke test
    test_status = "PENDING"
    if not skip_smoke:
        print("\n[Step 4/5] Running Day-0 qualification smoke test in WSL...")
        res_test = run_wsl(f"cd {wsl_path} && .venv/bin/python runner.py test")
        if res_test.returncode == 0:
            print("  ✔ Day-0 smoke test passed 100%:")
            for line in res_test.stdout.strip().splitlines():
                print(f"    {line}")
            test_status = "PASSED (Day-0)"
        else:
            print(f"[WARN] Day-0 smoke test failed with code {res_test.returncode}:", file=sys.stderr)
            for line in res_test.stderr.strip().splitlines():
                print(f"    {line}", file=sys.stderr)
            test_status = "FAILED (Day-0)"
    else:
        print("\n[Step 4/5] Smoke test skipped by flag.")

    # 7. Register outpost in OUTPOSTS.md
    print("\n[Step 5/5] Registering outpost in OUTPOSTS.md...")
    update_registry(
        name=name,
        mandate=mandate,
        status="ACTIVE",
        tests=test_status,
        created_at=created_at,
    )
    print("  ✔ Registered in OUTPOSTS.md")

    print("\n" + "=" * 70)
    print(f"  ✔ OUTPOST '{name}' READY FOR ISOLATED DEVELOPMENT")
    print("=" * 70)
    print(f"  WSL Path:      {wsl_path}")
    print(f"  Host UNC:      {unc_path}")
    print(f"  Test Command:  python -m tools.runner outpost test {name}")
    print(f"  Run Command:   python -m tools.runner outpost run {name}")
    return 0


def cmd_list(as_json: bool = False) -> int:
    """List all registered and discovered outposts."""
    registry_entries = {e["name"]: e for e in read_registry_table()}

    # Discover on disk in WSL / UNC
    unc_base = get_unc_base()
    discovered_names = set(registry_entries.keys())
    if unc_base.is_dir():
        for d in unc_base.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                discovered_names.add(d.name)

    all_outposts = []
    for name in sorted(discovered_names):
        entry = registry_entries.get(name, {})
        charter_file = unc_base / name / "CHARTER.md"
        mandate = entry.get("mandate", "Downstream isolated subsystem")
        status = entry.get("status", "ACTIVE" if charter_file.exists() else "UNTRACKED")
        tests = entry.get("tests", "UNKNOWN")
        created_at = entry.get("created_at", "Unknown")

        all_outposts.append({
            "name": name,
            "created_at": created_at,
            "mandate": mandate,
            "status": status,
            "tests": tests,
            "wsl_path": get_outpost_wsl_path(name),
            "host_path": str(get_outpost_unc_path(name)),
        })

    if as_json:
        print(json.dumps(all_outposts, indent=2))
        return 0

    print("=" * 80)
    print("  KAGEYONI REGISTERED & DISCOVERED OUTPOSTS")
    print("=" * 80)
    if not all_outposts:
        print("  No outposts currently provisioned.")
        print("  Use 'python -m tools.runner outpost create <name>' to instantiate one.")
        return 0

    print(f"  {'NAME':<20} {'STATUS':<10} {'TESTS':<18} {'PRIMARY MANDATE':<30}")
    print("-" * 80)
    for op in all_outposts:
        print(f"  {op['name']:<20} {op['status']:<10} {op['tests']:<18} {op['mandate']:<30}")
    print("-" * 80)
    base_dir = str(get_unc_base()) if sys.platform != "win32" else WSL_BASE_DIR
    print(f"Total: {len(all_outposts)} outpost(s) in {base_dir}\n")
    return 0


def cmd_test(name: str, verbose: bool = False) -> int:
    """Run test suite for a specified outpost in WSL."""
    unc_path = get_outpost_unc_path(name)
    wsl_path = get_outpost_wsl_path(name)

    if not unc_path.is_dir():
        print(f"[ERROR] Outpost '{name}' does not exist at {unc_path}.", file=sys.stderr)
        return 1

    v_flag = " -v" if verbose else ""
    cmd = f"cd {wsl_path} && .venv/bin/python runner.py test{v_flag}"
    print(f"Running tests in WSL for '{name}'...")
    res = run_wsl(cmd)
    if res.stdout:
        print(res.stdout.rstrip())
    if res.stderr:
        print(res.stderr.rstrip(), file=sys.stderr)

    test_res_str = "PASSED" if res.returncode == 0 else "FAILED"
    update_registry(
        name=name,
        mandate="Downstream isolated subsystem",
        status="ACTIVE",
        tests=test_res_str,
    )
    return res.returncode


def cmd_run(name: str, extra_args: Optional[List[str]] = None) -> int:
    """Run the execution pipeline for a specified outpost in WSL."""
    unc_path = get_outpost_unc_path(name)
    wsl_path = get_outpost_wsl_path(name)

    if not unc_path.is_dir():
        print(f"[ERROR] Outpost '{name}' does not exist at {unc_path}.", file=sys.stderr)
        return 1

    args_str = " " + " ".join(extra_args) if extra_args else ""
    cmd = f"cd {wsl_path} && .venv/bin/python runner.py run{args_str}"
    print(f"Executing pipeline in WSL for '{name}'...")
    res = run_wsl(cmd)
    if res.stdout:
        print(res.stdout.rstrip())
    if res.stderr:
        print(res.stderr.rstrip(), file=sys.stderr)
    return res.returncode


def cmd_status(name: str) -> int:
    """Display status of a specified outpost in WSL."""
    unc_path = get_outpost_unc_path(name)
    wsl_path = get_outpost_wsl_path(name)

    if not unc_path.is_dir():
        print(f"[ERROR] Outpost '{name}' does not exist at {unc_path}.", file=sys.stderr)
        return 1

    cmd = f"cd {wsl_path} && .venv/bin/python runner.py status"
    res = run_wsl(cmd)
    if res.stdout:
        print(res.stdout.rstrip())
    if res.stderr:
        print(res.stderr.rstrip(), file=sys.stderr)
    return res.returncode


# ---------------------------------------------------------------------------
# Main CLI Router
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="outpost",
        description="Kageyoni Outpost Workflow & Tooling Engine (WSL2 sandbox manager)",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Outpost subcommand")

    # create
    create_p = subparsers.add_parser("create", help="Create a new isolated outpost in WSL")
    create_p.add_argument("name", help="Alphanumeric name for the outpost")
    create_p.add_argument(
        "--mandate",
        "-m",
        default="Downstream isolated subsystem",
        help="Primary mandate or contract description for the outpost",
    )
    create_p.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip immediate Day-0 smoke test execution",
    )

    # list
    list_p = subparsers.add_parser("list", help="List all registered and discovered outposts")
    list_p.add_argument("--json", action="store_true", help="Output in JSON format")

    # test
    test_p = subparsers.add_parser("test", help="Run test suite for an outpost in WSL")
    test_p.add_argument("name", help="Name of the outpost to test")
    test_p.add_argument("-v", "--verbose", action="store_true", help="Verbose test runner output")

    # run
    run_p = subparsers.add_parser("run", help="Execute the primary pipeline for an outpost in WSL")
    run_p.add_argument("name", help="Name of the outpost to run")
    run_p.add_argument("extra", nargs="*", help="Extra arguments passed to runner.py run")

    # status
    status_p = subparsers.add_parser("status", help="Show status and deliverables of an outpost")
    status_p.add_argument("name", help="Name of the outpost to inspect")

    args = parser.parse_args(argv)

    if args.subcommand == "create":
        return cmd_create(name=args.name, mandate=args.mandate, skip_smoke=args.skip_smoke)
    elif args.subcommand == "list":
        return cmd_list(as_json=args.json)
    elif args.subcommand == "test":
        return cmd_test(name=args.name, verbose=args.verbose)
    elif args.subcommand == "run":
        return cmd_run(name=args.name, extra_args=args.extra)
    elif args.subcommand == "status":
        return cmd_status(name=args.name)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
