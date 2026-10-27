"""
tools/cartographer.py
AST Domain Boundary & Cartography Enforcement Gate for Kageyoni.

Closes Void 2 of the Atlas Negative Space: The Border Guard Gap.
Mechanically traces Python AST imports across the 6 Sovereign Domains
and physically fails the build if cross-domain boundary fences are breached.
"""

from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple

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

# Domain 1 Core Kernel paths (as defined in ATLAS.md)
DOMAIN_1_PREFIXES = (
    "kageyoni/composition",
    "kageyoni/database",
    "kageyoni/v11",
    "kageyoni/persistence",
    "kageyoni/execution",
    "kageyoni/entity",
    "kageyoni/processes",
    "kageyoni/engine.py",
    "kageyoni/gateway.py",
    "kageyoni/model.py",
    "kageyoni/operations.py",
    "kageyoni/migrate.py",
    "kageyoni/checkpoint.py",
    "kageyoni/decisions.py",
    "kageyoni/workflows.py",
    "kageyoni/ledger.py",
    "kageyoni/gate.py",
    "kageyoni/gate_runner.py",
    "kageyoni/graph.py",
    "kageyoni/magnet_delta.py",
    "kageyoni/resources.py",
    "kageyoni/seed.py",
)

# Domain 3 Tactical Simulation target modules (forbidden from Domain 1)
DOMAIN_3_FORBIDDEN_FROM_D1 = (
    "kageyoni.combat",
    "kageyoni.playable_world",
    "kageyoni.martial",
    "kageyoni.spatial",
    "kageyoni.chat_frame",
    "kageyoni.cli",
)


def is_domain_1_file(rel_posix: str) -> bool:
    return any(rel_posix == prefix or rel_posix.startswith(prefix) for prefix in DOMAIN_1_PREFIXES)


def resolve_import_module(file_path: Path, node: ast.ImportFrom, repo_root: Path) -> str:
    pkg_parts = list(file_path.relative_to(repo_root).with_suffix("").parts)[:-1]
    if node.level == 0:
        return node.module or ""
    up = node.level - 1
    base = list(pkg_parts) if up == 0 else list(pkg_parts[:-up]) if up <= len(pkg_parts) else []
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def check_domain_boundaries(workspace_root: Optional[Path] = None) -> Tuple[int, List[str]]:
    root = workspace_root or WORKSPACE_ROOT
    kageyoni_dir = root / "kageyoni"
    violations: List[str] = []
    checked_d1_files = 0

    for py_file in sorted(kageyoni_dir.rglob("*.py")):
        rel_posix = py_file.relative_to(root).as_posix()
        if not is_domain_1_file(rel_posix):
            continue

        checked_d1_files += 1
        try:
            content = py_file.read_text(encoding="utf-8-sig", errors="replace")
            tree = ast.parse(content, filename=py_file.name)
        except Exception as e:
            violations.append(f"{rel_posix}: Parse error: {e}")
            continue

        for node in ast.walk(tree):
            imported = ""
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    if any(imported == d3 or imported.startswith(d3 + ".") for d3 in DOMAIN_3_FORBIDDEN_FROM_D1):
                        violations.append(
                            f"{rel_posix}:{node.lineno} - Domain 1 Invariant Violation: "
                            f"Imports forbidden Domain 3 module '{imported}'."
                        )
            elif isinstance(node, ast.ImportFrom):
                resolved = resolve_import_module(py_file, node, root)
                if any(resolved == d3 or resolved.startswith(d3 + ".") for d3 in DOMAIN_3_FORBIDDEN_FROM_D1):
                    violations.append(
                        f"{rel_posix}:{node.lineno} - Domain 1 Invariant Violation: "
                        f"Imports from forbidden Domain 3 module '{resolved}'."
                    )

    return (len(violations), violations)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AST Domain Boundary & Cartography Enforcement Gate")
    parser.add_argument("--root", default=str(WORKSPACE_ROOT), help="Workspace root directory")
    args = parser.parse_args(argv)

    root = Path(args.root)
    count, violations = check_domain_boundaries(root)

    print("=" * 70)
    print("  KAGEYONI AST DOMAIN BOUNDARY & CARTOGRAPHY AUDIT")
    print("=" * 70)
    if count == 0:
        print("  [BOUNDARY CHECK PASSED] All Domain 1 files respect Domain 3 isolation.")
        print("  Zero illegal cross-domain imports detected.")
        print("=" * 70)
        return 0

    print(f"  [BOUNDARY CHECK FAILED] {count} cross-domain violation(s) detected:")
    for v in violations:
        print(f"    x {v}")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    sys.exit(main())
