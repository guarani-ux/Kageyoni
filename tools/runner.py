"""
tools/runner.py
Unified Tool Runner for the Kageyoni capability & tools estate.

Eliminates prefix-multiplied run_*.py scripts and establishes a single execution mechanism:
  python -m tools.runner <command> [args...]
  python -m tools.runner --list
  python -m tools.runner check-hygiene
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import importlib.util
import inspect
import os
from dataclasses import dataclass, field
from pathlib import Path
import runpy
import sys
import traceback
from typing import Dict, List, Optional, Set

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

# ---------------------------------------------------------------------------
# Registered legacy run_*.py scripts
# Any new run_*.py script created in tools/ without being in this legacy registry
# will fail check-hygiene.
# ---------------------------------------------------------------------------
REGISTERED_LEGACY_RUN_SCRIPTS: Set[str] = {
    "run_agency_tribunal.py",
    "run_competitive_analysis.py",
    "run_compression_comparison.py",
    "run_gate_g0_baseline.py",
    "run_gated_repairs.py",
    "run_magnet_verification.py",
    "run_peer_competitive_compiler.py",
    "run_research_compiler.py",
    "run_situation_comparative.py",
    "run_ssl_audit.py",
}

# ---------------------------------------------------------------------------
# Known entrypoint function names if direct functional invocation is used
# ---------------------------------------------------------------------------
ENTRYPOINTS: Dict[str, str] = {
    "audit_completion.py": "run_empirical_audit",
    "audit_gate.py": "main",
    "autonomous_builder_daemon.py": "main",
    "categorize_channels.py": "categorize_channels",
    "continuous_builder.py": "main",
    "generate_qualification_record.py": "main",
    "hash_r5_fixtures.py": "main",
    "init_completion_situation.py": "main",
    "init_compression_situation.py": "main",
    "mechanical_audit_gate.py": "main",
    "monitor_progress.py": "print_dashboard",
    "ninshu_worked_encounters.py": "encounter_1_single_channel_and_entrypoint_check",
    "package_personality.py": "build",
    "package_writing.py": "build",
    "resident_daimon.py": "main",
    "resolve_completion_frontiers.py": "main",
    "reverse_engineer.py": "main",
    "run_agency_tribunal.py": "main",
    "run_competitive_analysis.py": "main",
    "run_compression_comparison.py": "main",
    "run_gate_g0_baseline.py": "run_g0",
    "run_gated_repairs.py": "main",
    "run_magnet_verification.py": "main",
    "run_peer_competitive_compiler.py": "main",
    "run_research_compiler.py": "main",
    "run_situation_comparative.py": "main",
    "run_ssl_audit.py": "run_console_audit",
    "situation_mutation_check.py": "main",
    "test_clean_wheel_install.py": "main",
    "transition_compression_frontier.py": "main",
    "verify_magnet_contract.py": "main",
    "verify_ninshu_complete.py": "run_gate_1_audit_completion",
    "verify_package_source_parity.py": "main",
}

# ---------------------------------------------------------------------------
# Canonical aliases mapping user-friendly names to script stems
# ---------------------------------------------------------------------------
ALIASES: Dict[str, str] = {
    "verify-package-parity": "verify_package_source_parity",
    "verify_package_parity": "verify_package_source_parity",
    "package-parity": "verify_package_source_parity",
    "package_parity": "verify_package_source_parity",
    "clean-wheel-install": "test_clean_wheel_install",
    "clean_wheel_install": "test_clean_wheel_install",
    "agency-tribunal": "run_agency_tribunal",
    "tribunal": "run_agency_tribunal",
    "ssl-audit": "run_ssl_audit",
    "competitive-analysis": "run_competitive_analysis",
    "compression-comparison": "run_compression_comparison",
    "gate-g0-baseline": "run_gate_g0_baseline",
    "gate-g0": "run_gate_g0_baseline",
    "gated-repairs": "run_gated_repairs",
    "magnet-verification": "run_magnet_verification",
    "peer-competitive-compiler": "run_peer_competitive_compiler",
    "research-compiler": "run_research_compiler",
    "situation-comparative": "run_situation_comparative",
    "ninshu-complete": "verify_ninshu_complete",
    "magnet-contract": "verify_magnet_contract",
}

# ---------------------------------------------------------------------------
# Curated summaries for tools where AST docstring is absent or terse
# ---------------------------------------------------------------------------
TOOL_SUMMARIES: Dict[str, str] = {
    "audit_completion": "Run empirical completion audit across golden payloads.",
    "audit_gate": "Antigravity CLI (agy) Dual-Agent Adversarial Verification Gate.",
    "autonomous_builder_daemon": "Autonomous Dual-Agent Builder & Qualification Daemon.",
    "categorize_channels": "Categorize Ninshu SSL channels by implementation grade (Grade A, B, C).",
    "continuous_builder": "Autonomous Continuous Smelter & Capability Builder for the SSL Estate.",
    "generate_qualification_record": "Physical Release Qualification Authority (Gate G1 Hardened).",
    "hash_r5_fixtures": "Compute SHA-256 hashes for all R5 fixtures and rubrics.",
    "init_completion_situation": "Initialize Kageyoni Repository Repair Situation backed by SQLite.",
    "init_compression_situation": "Initialize Kageyoni Compression Situation backed by SQLite.",
    "mechanical_audit_gate": "Deterministic Mechanical Zero-Trust Code Auditor.",
    "monitor_progress": "Display real-time build and qualification progress dashboard.",
    "ninshu_worked_encounters": "Execute Ninshu worked encounter integration scenarios.",
    "package_personality": "Package verified development copy including campaign and recovery.",
    "package_writing": "Package verified development copy for writing.",
    "resident_daimon": "Autonomous SSL Resident Daimon (Continuous Build, Test & Verify Loop).",
    "resolve_completion_frontiers": "Transition the 10 Initial Blocking Frontiers in engine-held situation.",
    "reverse_engineer": "Operational capability: Reverse Engineering & Binary Inspection (REA Engine).",
    "run_agency_tribunal": "Production Reasoning Protocol: /tribunal Executor.",
    "run_competitive_analysis": "Competitive Media Strategy Analysis Runner (Sovereign Media Engine).",
    "run_compression_comparison": "Comparison test surface harness for Kageyoni Capability Compression.",
    "run_gate_g0_baseline": "Gate G0: Establish Real Baseline against Git SHA and Scars.",
    "run_gated_repairs": "Kageyoni Gated Repair Order Master Orchestrator (Gates G0 through G9).",
    "run_magnet_verification": "Magnet and state verification runner across gates.",
    "run_peer_competitive_compiler": "Peer Public Library Competitive Media Strategy Compiler.",
    "run_research_compiler": "Upstream Research-to-Creative Compiler CLI Runner.",
    "run_situation_comparative": "R5 Comparative Trials Runner (Gate G7 Hardened).",
    "run_ssl_audit": "Audit foreign binary imports against Kageyoni invariants using SSL mixing session.",
    "situation_mutation_check": "Check situation mutations and state transitions against baseline.",
    "test_clean_wheel_install": "Test clean installation of built wheel package in isolated environment.",
    "transition_compression_frontier": "Transition a Frontier in compression situation through states.",
    "verify_magnet_contract": "Gate G1 Verification: Read-Only Contract and Observable State Mapping.",
    "verify_ninshu_complete": "Master Cold-Process End-to-End Qualification Runner for Ninshu.",
    "verify_package_source_parity": "Verify package/source parity and generate qualification evidence dossier.",
}

# ---------------------------------------------------------------------------
# Workspace hygiene rules
# Patterns for throwaway files that are strictly forbidden in workspace root
# ---------------------------------------------------------------------------
THROWAWAY_PATTERNS: List[str] = [
    "temp_*",
    "tmp_*",
    "scratch_*",
    "test_*.py",
    "*.tmp",
    "*.bak",
    "*.swp",
    "*~",
    "dump_*",
    "ag_qualification_*.txt",
    "ag_shell_inside_*.txt",
    "temp.*",
    "tmp.*",
    "scratch.*",
    "test.*",
    "*.dump",
    "output.txt",
    "debug.log",
]


@dataclass
class ToolInfo:
    canonical_name: str
    module_name: str
    path: Path
    summary: str
    aliases: List[str] = field(default_factory=list)


def extract_docstring_summary(file_path: Path) -> str:
    """Extract a 1-line summary from module docstring or fallback dictionary."""
    stem = file_path.stem
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=file_path.name)
        doc = ast.get_docstring(tree)
        if doc:
            lines = [
                line.strip()
                for line in doc.strip().splitlines()
                if line.strip() and not line.strip().startswith("tools/")
            ]
            if lines:
                first = lines[0]
                # Filter out pure headings/agent labels
                if first.startswith("AGENT ") and len(lines) > 1:
                    first = lines[1]
                if len(first) > 80:
                    first = first[:77] + "..."
                return first
    except Exception:
        pass

    return TOOL_SUMMARIES.get(stem, "Executable tool module.")


def discover_tools(tools_dir: Optional[Path] = None) -> Dict[str, ToolInfo]:
    """Dynamically discover all runnable tools in tools/."""
    if tools_dir is None:
        tools_dir = Path(__file__).resolve().parent

    tools: Dict[str, ToolInfo] = {}

    for file_path in sorted(tools_dir.glob("*.py")):
        if file_path.name in ("__init__.py", "runner.py"):
            continue

        stem = file_path.stem
        # Canonical CLI name: hyphenated
        canonical = stem.replace("_", "-")
        summary = extract_docstring_summary(file_path)

        # Collect applicable aliases
        tool_aliases = [stem]
        if stem.startswith("run_"):
            tool_aliases.append(stem[4:].replace("_", "-"))
            tool_aliases.append(stem[4:])
        for alias, target in ALIASES.items():
            if target == stem and alias != canonical:
                tool_aliases.append(alias)

        tools[canonical] = ToolInfo(
            canonical_name=canonical,
            module_name=stem,
            path=file_path,
            summary=summary,
            aliases=sorted(set(tool_aliases)),
        )

    return tools


def resolve_tool(command_name: str, tools_dir: Optional[Path] = None) -> Optional[Path]:
    """Resolve a command name or alias to a tool script Path."""
    if tools_dir is None:
        tools_dir = Path(__file__).resolve().parent

    cmd_normalized = command_name.strip()

    # Check explicit alias dictionary
    if cmd_normalized in ALIASES:
        target_stem = ALIASES[cmd_normalized]
        p = tools_dir / f"{target_stem}.py"
        if p.is_file():
            return p

    # Direct filename match
    as_underscores = cmd_normalized.replace("-", "_")
    p1 = tools_dir / f"{as_underscores}.py"
    if p1.is_file():
        return p1

    # Try prepending 'run_'
    if not as_underscores.startswith("run_"):
        p2 = tools_dir / f"run_{as_underscores}.py"
        if p2.is_file():
            return p2

    # Try removing 'run_'
    if as_underscores.startswith("run_"):
        p3 = tools_dir / f"{as_underscores[4:]}.py"
        if p3.is_file():
            return p3

    # Dynamic lookup across discovered tools
    all_tools = discover_tools(tools_dir)
    for info in all_tools.values():
        if cmd_normalized in (info.canonical_name, info.module_name) or cmd_normalized in info.aliases:
            return info.path

    return None


def execute_tool(
    script_path: Path,
    args: Optional[List[str]] = None,
    mode: str = "runpy",
) -> int:
    """
    Execute a tool script with provided arguments.

    Sets sys.argv, ensures workspace root in sys.path, and dispatches via runpy or entrypoint.
    """
    args = args or []
    workspace_root = script_path.parent.parent.resolve()

    original_argv = list(sys.argv)
    original_cwd = Path.cwd()

    sys.argv = [str(script_path)] + args

    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    try:
        if mode == "entrypoint":
            spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[script_path.stem] = mod
                spec.loader.exec_module(mod)
                entry_name = ENTRYPOINTS.get(script_path.name, "main")
                entry_fn = getattr(mod, entry_name, None) or getattr(mod, "main", None)
                if callable(entry_fn):
                    sig = inspect.signature(entry_fn)
                    if len(sig.parameters) > 0:
                        res = entry_fn(args)
                    else:
                        res = entry_fn()
                    return int(res) if isinstance(res, int) else 0
                else:
                    print(
                        f"[RUNNER ERROR] Script {script_path.name} does not expose entrypoint '{entry_name}'.",
                        file=sys.stderr,
                    )
                    return 1

        # Default standard execution: runpy module runner under __main__
        runpy.run_path(str(script_path), run_name="__main__")
        return 0
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return int(code) if isinstance(code, int) else 1
    except Exception as exc:
        print(f"[RUNNER ERROR] Execution failed for {script_path.name}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1
    finally:
        sys.argv = original_argv
        try:
            os.chdir(original_cwd)
        except Exception:
            pass


def check_hygiene(
    tools_dir: Optional[Path] = None,
    root_dir: Optional[Path] = None,
) -> int:
    """
    Built-in lint/hygiene check command.

    Fails if:
    1. Any new run_*.py script is added to tools/ without registration.
    2. Throwaway or temporary files are detected in the workspace root.
    """
    if tools_dir is None:
        tools_dir = Path(__file__).resolve().parent
    if root_dir is None:
        root_dir = tools_dir.parent

    violations: List[str] = []

    # Check 1: Unregistered run_*.py scripts in tools/
    for script in sorted(tools_dir.glob("run_*.py")):
        if script.name not in REGISTERED_LEGACY_RUN_SCRIPTS:
            violations.append(
                f"Unregistered run_*.py script: tools/{script.name}. "
                "New tools must not create prefix-multiplied run_*.py scripts. "
                "Register new tools as standard modules and execute via 'python -m tools.runner <command>'."
            )

    # Check 2: Throwaway files in workspace root
    for item in root_dir.iterdir():
        if item.is_file():
            for pattern in THROWAWAY_PATTERNS:
                if fnmatch.fnmatch(item.name, pattern):
                    violations.append(
                        f"Throwaway file detected in workspace root: '{item.name}'. "
                        "Workspace hygiene invariant: Temporary files, test dumps, and scratch scripts "
                        "must be stored strictly in brain/<conversation-id>/scratch/ or dedicated directories, "
                        "never in the workspace root."
                    )
                    break

    # Report results
    print("=" * 70)
    print("  KAGEYONI TOOL RUNNER: WORKSPACE HYGIENE AUDIT")
    print("=" * 70)

    if violations:
        print(f"\n[HYGIENE FAILED] Found {len(violations)} hygiene violation(s):\n")
        for i, v in enumerate(violations, 1):
            print(f"  {i}. [VIOLATION] {v}\n")
        return 1

    print("\n[HYGIENE PASSED] All tools and workspace root conform to hygiene standards:")
    print(f"  ✔ Checked tools/: All {len(REGISTERED_LEGACY_RUN_SCRIPTS)} legacy run_*.py scripts are registered.")
    print("  ✔ Checked workspace root: Zero throwaway or temporary files detected.")
    return 0


def print_tool_list(tools_dir: Optional[Path] = None) -> None:
    """Display dynamically discovered tools with docstrings and aliases."""
    tools = discover_tools(tools_dir)

    print("=" * 78)
    print("  KAGEYONI UNIFIED TOOL RUNNER (tools/runner.py)")
    print("=" * 78)
    print("Usage: python -m tools.runner <command> [args...]")
    print("       python -m tools.runner --list")
    print("       python -m tools.runner check-hygiene\n")

    print("Built-in Runner Commands:")
    print(f"  {'check-hygiene':<32} Lint/hygiene check for run_*.py scripts & workspace root")
    print(f"  {'--list, -l':<32} Dynamically discover and display all runnable tools\n")

    print(f"Available Tools ({len(tools)} registered in tools/):")
    print("-" * 78)
    print(f"  {'COMMAND':<32} {'DESCRIPTION':<44}")
    print("-" * 78)

    for canonical, info in sorted(tools.items()):
        summary = info.summary
        print(f"  {canonical:<32} {summary}")
        # Print key aliases if present
        extra_aliases = [a for a in info.aliases if a != canonical and a != info.module_name]
        if extra_aliases:
            alias_str = ", ".join(extra_aliases)
            print(f"    {' ' * 30} [alias: {alias_str}]")

    print("-" * 78)


def dispatch(command: str, args: Optional[List[str]] = None, mode: str = "runpy") -> int:
    """Main dispatcher for tool execution."""
    args = args or []

    # Built-in hygiene check
    if command in ("check-hygiene", "check_hygiene", "hygiene"):
        return check_hygiene()

    target_path = resolve_tool(command)
    if not target_path:
        print(
            f"[RUNNER ERROR] Unknown tool or command: '{command}'.\n"
            f"Run 'python -m tools.runner --list' to see available tools.",
            file=sys.stderr,
        )
        return 1

    return execute_tool(target_path, args, mode=mode)


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser for CLI interface."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.runner",
        description="Unified Tool Runner for Kageyoni tools estate.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="Dynamically discover and display all runnable tools in tools/ with summaries.",
    )
    parser.add_argument(
        "--mode",
        choices=["runpy", "entrypoint"],
        default="runpy",
        help="Execution mode: 'runpy' (default, runs module as __main__) or 'entrypoint' (invokes main func).",
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Tool command or alias to execute (e.g. categorize-channels, verify-package-parity, check-hygiene).",
    )
    parser.add_argument(
        "tool_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded directly to the tool.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main entrypoint for CLI invocation."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        print_tool_list()
        return 0

    if not args.command:
        parser.print_help()
        print("\nTip: Use 'python -m tools.runner --list' to see all available tools.")
        return 0

    return dispatch(args.command, args=args.tool_args, mode=args.mode)


if __name__ == "__main__":
    sys.exit(main())
