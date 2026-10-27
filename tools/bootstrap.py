"""
tools/bootstrap.py
Automated host platform detection, environment provisioning, and health verification for Kageyoni.

Detects host platform (macOS/Darwin vs Windows vs Linux), CPU architecture (Apple Silicon vs Intel/AMD),
provisions local runtime directories (.state/, build/) and outpost sandboxes, audits domain boundaries,
collects system cadence, and outputs the platform readiness receipt banner.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

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


def detect_platform() -> Dict[str, Any]:
    """Detect operating system, architecture, and normalize naming."""
    os_name = sys.platform  # 'darwin', 'win32', 'linux'
    raw_machine = platform.machine()
    machine_lower = raw_machine.lower()

    if os_name == "darwin":
        os_display = "macOS / Darwin"
        if machine_lower in ("arm64", "aarch64"):
            arch_display = "arm64 (Apple Silicon)"
        elif machine_lower in ("x86_64", "amd64", "intel64"):
            arch_display = "x86_64 (Intel)"
        else:
            arch_display = raw_machine
    elif os_name == "win32":
        os_display = "Windows"
        if machine_lower in ("x86_64", "amd64"):
            arch_display = "x86_64 Intel/AMD"
        elif machine_lower in ("arm64", "aarch64"):
            arch_display = "arm64"
        else:
            arch_display = raw_machine
    elif os_name.startswith("linux"):
        os_display = "Linux"
        if machine_lower in ("x86_64", "amd64"):
            arch_display = "x86_64"
        elif machine_lower in ("arm64", "aarch64"):
            arch_display = "arm64"
        else:
            arch_display = raw_machine
    else:
        os_display = os_name
        arch_display = raw_machine

    return {
        "os_key": os_name,
        "os_display": os_display,
        "machine": raw_machine,
        "arch_display": arch_display,
        "platform_str": f"{os_display} ({arch_display})",
    }


def verify_python_version() -> Tuple[bool, str, str]:
    """Verify that Python version meets >= 3.10 requirement."""
    ver = sys.version_info
    ver_str = f"{ver.major}.{ver.minor}.{ver.micro}"
    exe = sys.executable
    is_valid = (ver.major, ver.minor) >= (3, 10)
    summary = f"{ver_str} ({exe})"
    return is_valid, ver_str, summary


def verify_terminal_utf8() -> Tuple[bool, str]:
    """Verify terminal stdout UTF-8 encoding capability."""
    enc = getattr(sys.stdout, "encoding", "") or ""
    is_utf8 = "utf" in enc.lower()
    return is_utf8, enc or "unknown"


def ensure_local_state_dirs(workspace_root: Path) -> List[Path]:
    """Ensure local .state/ and build/ directories exist in repository root."""
    verified = []
    for d_name in [".state", "build"]:
        p = workspace_root / d_name
        p.mkdir(parents=True, exist_ok=True)
        verified.append(p)
    return verified


def setup_platform_sandbox(workspace_root: Path, os_key: str) -> Dict[str, Any]:
    """Provision and inspect platform-specific outpost sandboxes and state paths."""
    details: Dict[str, Any] = {
        "sandbox_label": "",
        "outpost_dir": None,
        "wsl_available": False,
        "wsl_message": "",
        "unc_mirror": None,
        "shinobi_present": False,
        "shinobi_path": None,
    }

    if os_key == "darwin":
        # macOS: native POSIX isolation in ~/outposts or KAGEYONI_OUTPOSTS_DIR
        outpost_dir = Path(os.environ.get("KAGEYONI_OUTPOSTS_DIR", Path.home() / "outposts"))
        outpost_dir.mkdir(parents=True, exist_ok=True)
        details["outpost_dir"] = outpost_dir
        details["sandbox_label"] = "Native Darwin POSIX"

        # Check Shinobi state
        shinobi_candidates = [
            Path(os.environ.get("SHINOBI_ROOT", "")) if "SHINOBI_ROOT" in os.environ else None,
            Path.home() / "shinobi",
            workspace_root / "shinobi" / ".state",
            workspace_root / "shinobi",
        ]
        for candidate in shinobi_candidates:
            if candidate and candidate.exists():
                details["shinobi_present"] = True
                details["shinobi_path"] = candidate
                break

    elif os_key == "win32":
        # Windows: WSL2 Ubuntu with UNC mirror
        try:
            from tools.outpost import check_wsl_available, get_unc_base
            wsl_ok, wsl_msg = check_wsl_available()
            details["wsl_available"] = wsl_ok
            details["wsl_message"] = wsl_msg
            unc_base = get_unc_base()
            details["unc_mirror"] = unc_base
        except Exception as exc:
            details["wsl_available"] = False
            details["wsl_message"] = str(exc)

        details["sandbox_label"] = "WSL2 Ubuntu"

        # Check Shinobi state in repo or local directory
        local_shinobi = workspace_root / "shinobi" / ".state"
        if local_shinobi.exists() or (workspace_root / "shinobi").exists():
            details["shinobi_present"] = True
            details["shinobi_path"] = workspace_root / "shinobi"

    else:
        # Linux or generic POSIX
        outpost_dir = Path(os.environ.get("KAGEYONI_OUTPOSTS_DIR", Path.home() / "outposts"))
        outpost_dir.mkdir(parents=True, exist_ok=True)
        details["outpost_dir"] = outpost_dir
        details["sandbox_label"] = "Native Linux POSIX"

    return details


def run_boundary_check(workspace_root: Path, verbose: bool = False) -> Tuple[bool, int, List[Any]]:
    """Execute Domain Boundary Cartography inspection."""
    try:
        from tools.cartographer import audit_domain_boundaries
        count, violations, _, _ = audit_domain_boundaries(workspace_root)
        return (count == 0), count, violations
    except Exception as exc:
        return False, 1, [str(exc)]


def run_cadence_check(workspace_root: Path, skip_tests: bool = False) -> Dict[str, Any]:
    """Execute living system cadence and generate health receipt."""
    try:
        from tools.cadence import collect_health_receipt
        receipt_path = workspace_root / ".state" / "system_health.json"
        receipt = collect_health_receipt(
            workspace_root=workspace_root,
            skip_tests=skip_tests,
            output_path=receipt_path,
        )
        return receipt
    except Exception as exc:
        return {
            "overall_health": "DEGRADED",
            "git_commit": "UNKNOWN",
            "git_details": {"short_hash": "unknown"},
            "core_status": f"ERROR: {exc}",
            "database_migrations": 0,
            "outposts": [],
        }


def discover_outposts(workspace_root: Path) -> List[Dict[str, str]]:
    """Parse outposts roster from OUTPOSTS.md."""
    try:
        from tools.cadence import parse_outposts_registry
        return parse_outposts_registry(workspace_root)
    except Exception:
        return []


def render_banner(
    platform_str: str,
    python_summary: str,
    sandbox_label: str,
    health_status: str,
    commit_short: str,
    ready: bool,
) -> None:
    """Output the clear, formatted terminal banner mandated by Kageyoni invariants."""
    banner_sep = "=" * 70
    status_str = "READY TO OPERATE" if ready else "DEGRADED (ATTENTION REQUIRED)"
    health_line = f"{health_status} ({commit_short})" if commit_short else health_status

    print(banner_sep)
    print("  KAGEYONI SYSTEM PLATFORM BOOTSTRAP & RUNTIME DETECTION")
    print(banner_sep)
    print(f"Platform: {platform_str}")
    print(f"Python:   {python_summary}")
    print(f"Sandbox:  {sandbox_label}")
    print(f"Health:   {health_line}")
    print(f"Status:   {status_str}")
    print(banner_sep)


def bootstrap(
    workspace_root: Optional[Path] = None,
    skip_tests: bool = False,
    verbose: bool = False,
    quiet: bool = False,
) -> int:
    """
    Main orchestration routine for Kageyoni platform bootstrap.
    Returns 0 when system is healthy and ready to operate, 1 otherwise.
    """
    root = (workspace_root or WORKSPACE_ROOT).resolve()

    # 1. Platform & architecture detection
    plat_info = detect_platform()
    os_key = plat_info["os_key"]
    platform_str = plat_info["platform_str"]

    # 2. Python version & UTF-8 capability
    python_ok, python_ver, python_summary = verify_python_version()
    utf8_ok, utf8_encoding = verify_terminal_utf8()

    # 3. Ensure local state directories exist in repo root
    ensure_local_state_dirs(root)

    # 4. Provision & inspect platform sandboxes
    sandbox_info = setup_platform_sandbox(root, os_key)
    sandbox_label = sandbox_info["sandbox_label"]

    # 5. Execute Sovereign Domain Boundary Cartography audit
    boundaries_ok, violation_count, violations = run_boundary_check(root, verbose=verbose)

    # 6. Execute system cadence & health receipt generation
    cadence_data = run_cadence_check(root, skip_tests=skip_tests)
    overall_health = cadence_data.get("overall_health", "DEGRADED")
    git_short = cadence_data.get("git_details", {}).get("short_hash", "")

    # 7. Outpost discovery
    outposts = cadence_data.get("outposts") or discover_outposts(root)

    # 8. Readiness evaluation
    is_ready = bool(
        python_ok
        and boundaries_ok
        and overall_health == "HEALTHY"
    )

    # 9. Render canonical terminal banner
    render_banner(
        platform_str=platform_str,
        python_summary=python_summary,
        sandbox_label=sandbox_label,
        health_status=overall_health,
        commit_short=git_short,
        ready=is_ready,
    )

    # 10. Checklist breakdown (unless quiet mode requested)
    if not quiet:
        utf8_label = f"UTF-8 ({utf8_encoding})" if utf8_ok else f"Non-UTF8 ({utf8_encoding})"
        py_status = f"Python {python_ver} >= 3.10" if python_ok else f"Python {python_ver} < 3.10 UNSUPPORTED"
        print(f"  ✔ Platform:        {platform_str} [{py_status}, {utf8_label}]")

        if os_key == "win32":
            wsl_desc = "WSL2 Ubuntu Available" if sandbox_info["wsl_available"] else f"WSL2 Warning ({sandbox_info['wsl_message']})"
            unc_desc = f" (UNC Mirror: {sandbox_info['unc_mirror']})" if sandbox_info.get("unc_mirror") else ""
            print(f"  ✔ Sandboxes:       {wsl_desc}{unc_desc}")
        elif os_key == "darwin":
            outpost_desc = f" ({sandbox_info['outpost_dir']})" if sandbox_info.get("outpost_dir") else " (~/outposts)"
            shinobi_desc = " [Shinobi reachable]" if sandbox_info.get("shinobi_present") else ""
            print(f"  ✔ Sandboxes:       Native Darwin POSIX{outpost_desc}{shinobi_desc}")
        else:
            print(f"  ✔ Sandboxes:       Native Linux POSIX ({sandbox_info.get('outpost_dir', '~/outposts')})")

        print("  ✔ Local Dirs:      .state/ and build/ verified")

        if boundaries_ok:
            print("  ✔ Boundaries:      Passed (Domain 1 / Domain 3 AST isolation clean)")
        else:
            print(f"  ✖ Boundaries:      FAILED ({violation_count} cross-domain violation(s) detected)")
            if verbose:
                for v in violations:
                    print(f"       - {v}")

        core_status = cadence_data.get("core_status", "UNKNOWN")
        if overall_health == "HEALTHY":
            print(f"  ✔ Cadence:         Generated .state/system_health.json ({core_status})")
        else:
            print(f"  ✖ Cadence:         {overall_health} ({core_status})")

        outpost_count = len(outposts)
        outpost_names = ", ".join(o.get("name", "") for o in outposts) if outposts else "none"
        print(f"  ✔ Outposts Fleet:  {outpost_count} registered active ({outpost_names})")
        print("=" * 70)

    return 0 if is_ready else 1


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for tools/bootstrap.py."""
    parser = argparse.ArgumentParser(
        description="Automated host platform detection, environment provisioning, and health verification for Kageyoni."
    )
    parser.add_argument(
        "--root",
        default=str(WORKSPACE_ROOT),
        help="Workspace root directory (default: repository root).",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip test suite execution during cadence health collection.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Display detailed diagnostic output for boundary and health checks.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress detail checklist, rendering only the canonical banner.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    return bootstrap(
        workspace_root=root,
        skip_tests=args.skip_tests,
        verbose=args.verbose,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    sys.exit(main())
