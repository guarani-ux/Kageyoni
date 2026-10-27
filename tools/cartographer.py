"""
tools/cartographer.py
Mechanical AST Sovereign Domain Cartographer & Boundary Guard for Kageyoni.

Enforces the 6 Sovereign Domains defined in ATLAS.md and verifies domain boundary invariants:
- Domain 1: Causal State Engine & Invariants
- Domain 2: Historical Narrative Continuity & Canonical Worlds
- Domain 3: Tactical World Engine & Playable Simulation
- Domain 4: Systems & Binary Reverse Engineering (REA Estate)
- Domain 5: Cognitive OS & Media Production
- Domain 6: Autonomous Agents, Governance & Tooling

Strict Boundary Invariant:
Domain 1 cannot directly import Domain 3 (kageyoni.combat, kageyoni.playable_world,
kageyoni.martial, kageyoni.spatial, kageyoni.chat_frame, kageyoni.cli).
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple, Union

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


@dataclass(frozen=True)
class DomainDefinition:
    """Metadata specification for a Sovereign Architectural Domain."""
    number: int
    name: str
    description: str
    path_prefixes: Tuple[str, ...]
    module_prefixes: Tuple[str, ...]


# ---------------------------------------------------------------------------
# The 6 Sovereign Domains (Canonically defined in ATLAS.md)
# ---------------------------------------------------------------------------
SOVEREIGN_DOMAINS: Dict[int, DomainDefinition] = {
    1: DomainDefinition(
        number=1,
        name="Causal State Engine & Invariants",
        description="Immutable heartbeat, transactional event store, revisions, qualitative composition compiler, V11 protected operations.",
        path_prefixes=(
            "kageyoni/engine.py",
            "kageyoni/gateway.py",
            "kageyoni/model.py",
            "kageyoni/coliseum.py",
            "kageyoni/composition",
            "kageyoni/database",
            "kageyoni/v11",
            "kageyoni/persistence",
            "kageyoni/execution",
            "kageyoni/entity",
            "kageyoni/processes",
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
            "kageyoni/application.py",
            "kageyoni/diagnostics.py",
            "schemas",
            "build",
            "dist",
            "examples",
        ),
        module_prefixes=(
            "kageyoni.engine",
            "kageyoni.gateway",
            "kageyoni.model",
            "kageyoni.coliseum",
            "kageyoni.composition",
            "kageyoni.database",
            "kageyoni.v11",
            "kageyoni.persistence",
            "kageyoni.execution",
            "kageyoni.entity",
            "kageyoni.processes",
            "kageyoni.operations",
            "kageyoni.migrate",
            "kageyoni.checkpoint",
            "kageyoni.decisions",
            "kageyoni.workflows",
            "kageyoni.ledger",
            "kageyoni.gate",
            "kageyoni.gate_runner",
            "kageyoni.graph",
            "kageyoni.magnet_delta",
            "kageyoni.resources",
            "kageyoni.seed",
            "kageyoni.application",
            "kageyoni.diagnostics",
        ),
    ),
    2: DomainDefinition(
        number=2,
        name="Historical Narrative Continuity & Canonical Worlds",
        description="Historical continuity across 4 canonical campaigns, Levi balance simulation, immutable SQLite archives.",
        path_prefixes=(
            "sources",
            "recovery",
            "levi_sim",
            "fixtures",
            "kageyoni/nature",
            "kageyoni/characters.py",
            "kageyoni/will.py",
            "kageyoni/personality.py",
        ),
        module_prefixes=(
            "sources",
            "recovery",
            "levi_sim",
            "fixtures",
            "kageyoni.nature",
            "kageyoni.characters",
            "kageyoni.will",
            "kageyoni.personality",
        ),
    ),
    3: DomainDefinition(
        number=3,
        name="Tactical World Engine & Playable Simulation",
        description="Discrete playable world execution, 100x100 spatial grid, 2RN combat math, DMW roulette, Kata decks, CLI RPG.",
        path_prefixes=(
            "kageyoni/playable_world",
            "kageyoni/combat",
            "kageyoni/martial",
            "kageyoni/spatial",
            "kageyoni/chat_frame.py",
            "kageyoni/cli.py",
            "data",
        ),
        module_prefixes=(
            "kageyoni.playable_world",
            "kageyoni.combat",
            "kageyoni.martial",
            "kageyoni.spatial",
            "kageyoni.chat_frame",
            "kageyoni.cli",
        ),
    ),
    4: DomainDefinition(
        number=4,
        name="Systems & Binary Reverse Engineering (REA Estate)",
        description="Binary reverse engineering, target inspection (ASAR, PE, ELF, Mach-O), 48-channel SSL mixing console, capability smelting.",
        path_prefixes=(
            "rea_forge",
            "kageyoni/ninshu",
            "external_repos/rea",
        ),
        module_prefixes=(
            "rea_forge",
            "kageyoni.ninshu",
        ),
    ),
    5: DomainDefinition(
        number=5,
        name="Cognitive OS & Media Production",
        description="Multi-domain cognitive operating system, missions, vault management, A/V documentary scriptwriting craft, research compiler.",
        path_prefixes=(
            "cognitive-os",
            "av-story-skills",
            "contracts",
            "kageyoni/research_compiler",
            "kageyoni/writing.py",
            "external_repos/Video-House",
            "external_repos/VoiceStudio",
        ),
        module_prefixes=(
            "cognitive-os",
            "av-story-skills",
            "contracts",
            "kageyoni.research_compiler",
            "kageyoni.writing",
        ),
    ),
    6: DomainDefinition(
        number=6,
        name="Autonomous Agents, Governance & Tooling",
        description="Autonomous agent runtimes (Shinobi), long-horizon benchmarks, council governance, developer tooling and audit gates.",
        path_prefixes=(
            "shinobi",
            "shinobi_agent",
            "benchmarks",
            "governance",
            "tools",
            "scripts",
            "skills",
            ".agents",
            ".github",
            "evidence",
            "state",
            "kageyoni/developmental",
            "kageyoni/emergence",
            "kageyoni/intelligence",
            "kageyoni/narrative",
            "kageyoni/participant_kernel.py",
            "kageyoni/situations",
            "kageyoni/vantage",
            "kageyoni/workspaces",
            "kageyoni/agency_workflows.py",
            "kageyoni/celestial.py",
            "kageyoni/console.py",
            "kageyoni/constellation.py",
            "kageyoni/scout.py",
            "temp_agent_governing_files",
        ),
        module_prefixes=(
            "shinobi",
            "shinobi_agent",
            "benchmarks",
            "governance",
            "tools",
            "scripts",
            "kageyoni.developmental",
            "kageyoni.emergence",
            "kageyoni.intelligence",
            "kageyoni.narrative",
            "kageyoni.participant_kernel",
            "kageyoni.situations",
            "kageyoni.vantage",
            "kageyoni.workspaces",
            "kageyoni.agency_workflows",
            "kageyoni.celestial",
            "kageyoni.console",
            "kageyoni.constellation",
            "kageyoni.scout",
        ),
    ),
}

# Explicit forbidden targets from Domain 1 (Domain 3 modules)
DOMAIN_3_FORBIDDEN_FROM_D1: Tuple[str, ...] = (
    "kageyoni.combat",
    "kageyoni.playable_world",
    "kageyoni.martial",
    "kageyoni.spatial",
    "kageyoni.chat_frame",
    "kageyoni.cli",
)


@dataclass
class BoundaryViolation:
    """Represents a mechanical cross-domain import invariant violation."""
    source_file: str
    line_number: int
    source_domain: int
    target_domain: int
    imported_module: str
    imported_names: List[str]
    message: str

    def __str__(self) -> str:
        names_str = f" ({', '.join(self.imported_names)})" if self.imported_names else ""
        return (
            f"{self.source_file}:{self.line_number} - Domain {self.source_domain} Invariant Breach: "
            f"imports Domain {self.target_domain} module '{self.imported_module}'{names_str}."
        )


def map_file_to_domain(file_path: Path, repo_root: Path) -> Optional[int]:
    """
    Map a file path to its Sovereign Domain (1-6) based on ATLAS.md topology.
    Returns domain integer 1..6, or None if unmapped / cross-cutting.
    """
    try:
        rel = file_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        try:
            rel = file_path.relative_to(repo_root).as_posix()
        except ValueError:
            rel = file_path.as_posix()

    # Normalise leading slashes
    rel = rel.lstrip("/")

    # Check domains in order
    for domain_num, domain_def in SOVEREIGN_DOMAINS.items():
        for prefix in domain_def.path_prefixes:
            if rel == prefix or rel.startswith(prefix + "/") or rel.startswith(prefix):
                return domain_num

    return None


def map_module_to_domain(module_name: str) -> Optional[int]:
    """
    Map an import module name to its Sovereign Domain (1-6).
    Returns domain integer 1..6, or None if external / unmapped.
    """
    mod = module_name.strip()
    if not mod:
        return None

    for domain_num, domain_def in SOVEREIGN_DOMAINS.items():
        for prefix in domain_def.module_prefixes:
            if mod == prefix or mod.startswith(prefix + "."):
                return domain_num

    return None


def resolve_import_module(
    file_path: Path,
    node: ast.ImportFrom,
    repo_root: Path,
) -> Tuple[str, List[str]]:
    """
    Resolve an ast.ImportFrom node to its absolute module path and list of imported names.

    Handles absolute imports (node.level == 0) and relative imports (node.level > 0).
    """
    try:
        rel_path = file_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        rel_path = file_path.relative_to(repo_root)

    pkg_parts = list(rel_path.with_suffix("").parts)[:-1]
    imported_names = [alias.name for alias in node.names]

    if node.level == 0:
        return node.module or "", imported_names

    up = node.level - 1
    if up == 0:
        base = list(pkg_parts)
    elif up <= len(pkg_parts):
        base = list(pkg_parts[:-up])
    else:
        base = []

    if node.module:
        base.extend(node.module.split("."))

    resolved_module = ".".join(base)
    return resolved_module, imported_names


def audit_domain_boundaries(
    workspace_root: Optional[Path] = None,
    scan_dir: Optional[str] = "kageyoni",
) -> Tuple[int, List[BoundaryViolation], Dict[int, int], int]:
    """
    Perform AST inspection of Python files to enforce Sovereign Domain boundary fences.

    Specifically verifies that Domain 1 files do not import Domain 3 modules.
    Returns:
      (violation_count, violations_list, domain_file_counts, total_files_scanned)
    """
    root = (workspace_root or WORKSPACE_ROOT).resolve()
    target_dir = (root / scan_dir) if scan_dir else root

    violations: List[BoundaryViolation] = []
    domain_counts: Dict[int, int] = {i: 0 for i in range(1, 7)}
    total_scanned = 0

    if not target_dir.exists():
        return 0, violations, domain_counts, 0

    for py_file in sorted(target_dir.rglob("*.py")):
        # Skip pycache or hidden directories
        if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
            continue

        domain = map_file_to_domain(py_file, root)
        if domain is not None:
            domain_counts[domain] += 1
        total_scanned += 1

        # Currently enforced boundary invariant: Domain 1 cannot import Domain 3
        if domain != 1:
            continue

        rel_posix = py_file.relative_to(root).as_posix()

        try:
            content = py_file.read_text(encoding="utf-8-sig", errors="replace")
            tree = ast.parse(content, filename=py_file.name)
        except Exception as e:
            violations.append(
                BoundaryViolation(
                    source_file=rel_posix,
                    line_number=1,
                    source_domain=1,
                    target_domain=0,
                    imported_module="",
                    imported_names=[],
                    message=f"AST parse failure: {e}",
                )
            )
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    target_dom = map_module_to_domain(imported)
                    is_d3 = target_dom == 3 or any(
                        imported == d3 or imported.startswith(d3 + ".")
                        for d3 in DOMAIN_3_FORBIDDEN_FROM_D1
                    )
                    if is_d3:
                        violations.append(
                            BoundaryViolation(
                                source_file=rel_posix,
                                line_number=node.lineno,
                                source_domain=1,
                                target_domain=3,
                                imported_module=imported,
                                imported_names=[alias.asname or alias.name],
                                message=f"Direct import of forbidden Domain 3 module '{imported}'",
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                resolved_mod, names = resolve_import_module(py_file, node, root)
                target_dom = map_module_to_domain(resolved_mod)
                is_d3 = target_dom == 3 or any(
                    resolved_mod == d3 or resolved_mod.startswith(d3 + ".")
                    for d3 in DOMAIN_3_FORBIDDEN_FROM_D1
                )
                if is_d3:
                    violations.append(
                        BoundaryViolation(
                            source_file=rel_posix,
                            line_number=node.lineno,
                            source_domain=1,
                            target_domain=3,
                            imported_module=resolved_mod,
                            imported_names=names,
                            message=f"From-import of forbidden Domain 3 module '{resolved_mod}'",
                        )
                    )
                else:
                    # Check individual imported names if resolved_mod is package prefix
                    for name in names:
                        full_mod = f"{resolved_mod}.{name}" if resolved_mod else name
                        full_dom = map_module_to_domain(full_mod)
                        if full_dom == 3 or any(
                            full_mod == d3 or full_mod.startswith(d3 + ".")
                            for d3 in DOMAIN_3_FORBIDDEN_FROM_D1
                        ):
                            violations.append(
                                BoundaryViolation(
                                    source_file=rel_posix,
                                    line_number=node.lineno,
                                    source_domain=1,
                                    target_domain=3,
                                    imported_module=full_mod,
                                    imported_names=[name],
                                    message=f"From-import of forbidden Domain 3 member '{full_mod}'",
                                )
                            )

    return len(violations), violations, domain_counts, total_scanned


def check_domain_boundaries(
    workspace_root: Optional[Union[Path, str, List[str]]] = None,
    verbose: bool = False,
    *args,
    **kwargs,
) -> int:
    """
    Clean CLI entrypoint to verify Sovereign Domain boundaries.
    Returns 0 if all boundaries are respected, 1 if violations are found.
    """
    if isinstance(workspace_root, (list, tuple)):
        return main(list(workspace_root))

    if isinstance(workspace_root, str):
        root = Path(workspace_root)
    else:
        root = workspace_root or WORKSPACE_ROOT

    count, violations, domain_counts, total_files = audit_domain_boundaries(root)

    print("=" * 72)
    print("  KAGEYONI MECHANICAL AST SOVEREIGN DOMAIN CARTOGRAPHY AUDIT")
    print("=" * 72)

    if verbose:
        print("\n  [SOVEREIGN DOMAIN CARTOGRAPHY BREAKDOWN]")
        for d_num in range(1, 7):
            info = SOVEREIGN_DOMAINS[d_num]
            print(f"    Domain {d_num}: {info.name:<48} [{domain_counts.get(d_num, 0):>3} files]")
        print(f"    Total Scanned Python Files: {total_files:>3}")
        print()

    if count == 0:
        print("  [BOUNDARY CHECK PASSED] All Domain 1 files respect Domain 3 isolation.")
        print(f"  Verified {domain_counts.get(1, 0)} Domain 1 files ({total_files} total files scanned).")
        print("  Zero illegal cross-domain imports detected.")
        print("=" * 72)
        return 0

    print(f"  [BOUNDARY CHECK FAILED] {count} cross-domain violation(s) detected:\n")
    for v in violations:
        print(f"    x {v}")
    print("=" * 72)
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Mechanical AST Sovereign Domain Cartographer & Boundary Guard."
    )
    parser.add_argument(
        "--root",
        default=str(WORKSPACE_ROOT),
        help="Workspace root directory (default: repo root).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable detailed cartography summary and domain file counts.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    return check_domain_boundaries(workspace_root=root, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
