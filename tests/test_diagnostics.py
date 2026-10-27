"""Unit tests for Atlas Diagnostic Umbilical (Void 4 Resolver)."""

from __future__ import annotations

import sys
import pytest

from kageyoni.diagnostics import (
    DOMAINS,
    EXTERNAL_DOMAIN,
    ArchitecturalTrace,
    format_architectural_trace,
    inspect_exception,
    install_architectural_excepthook,
    resolve_domain,
)
from kageyoni.engine import Engine, Rejected, require


def test_resolve_domain_all_domains():
    # Domain 1: Core Kernel
    d1_a = resolve_domain("kageyoni/engine.py")
    assert d1_a["domain"] == 1
    assert d1_a["tag"] == "[DOMAIN 01: Core Kernel]"
    d1_b = resolve_domain("c:/repo/kageyoni/gateway.py")
    assert d1_b["domain"] == 1
    d1_c = resolve_domain("kageyoni/model.py")
    assert d1_c["domain"] == 1

    # Domain 2: Historical Narrative & Continuity
    d2_a = resolve_domain("sources/historical_events.md")
    assert d2_a["domain"] == 2
    assert d2_a["tag"] == "[DOMAIN 02: Historical Narrative & Continuity]"
    d2_b = resolve_domain("recovery/canonical_state.sqlite")
    assert d2_b["domain"] == 2
    d2_c = resolve_domain("fixtures/historical/booderland.sqlite")
    assert d2_c["domain"] == 2
    d2_d = resolve_domain("levi_sim/operator.py")
    assert d2_d["domain"] == 2

    # Domain 3: Tactical World Engine & Playable Simulation
    d3_a = resolve_domain("kageyoni/playable_world/grid.py")
    assert d3_a["domain"] == 3
    assert d3_a["tag"] == "[DOMAIN 03: Tactical World Engine & Playable Simulation]"
    d3_b = resolve_domain("kageyoni/combat/roulette.py")
    assert d3_b["domain"] == 3
    d3_c = resolve_domain("kageyoni/cli.py")
    assert d3_c["domain"] == 3
    d3_d = resolve_domain("data/SAVE.json")
    assert d3_d["domain"] == 3

    # Domain 4: Systems & Binary Reverse Engineering
    d4_a = resolve_domain("rea_forge/src/inspector/profiles/target.py")
    assert d4_a["domain"] == 4
    assert d4_a["tag"] == "[DOMAIN 04: Systems & Binary Reverse Engineering]"
    d4_b = resolve_domain("kageyoni/ninshu/console.py")
    assert d4_b["domain"] == 4
    d4_c = resolve_domain("tools/run_ssl_audit.py")
    assert d4_c["domain"] == 4

    # Domain 5: Cognitive OS & Media Intelligence
    d5_a = resolve_domain("cognitive-os/scripts/cos_cli.py")
    assert d5_a["domain"] == 5
    assert d5_a["tag"] == "[DOMAIN 05: Cognitive OS & Media Intelligence]"
    d5_b = resolve_domain("av-story-skills/av_script.py")
    assert d5_b["domain"] == 5
    d5_c = resolve_domain("contracts/agency_contract.json")
    assert d5_c["domain"] == 5
    d5_d = resolve_domain("kageyoni/research_compiler/compiler.py")
    assert d5_d["domain"] == 5

    # Domain 6: Autonomous Agents, Governance & Tooling
    d6_a = resolve_domain("shinobi/shinobi.py")
    assert d6_a["domain"] == 6
    assert d6_a["tag"] == "[DOMAIN 06: Autonomous Agents, Governance & Tooling]"
    d6_b = resolve_domain("benchmarks/collapsing_city/eval.py")
    assert d6_b["domain"] == 6
    d6_c = resolve_domain("tools/runner.py")
    assert d6_c["domain"] == 6
    d6_d = resolve_domain("tests/test_diagnostics.py")
    assert d6_d["domain"] == 6

    # External / System
    ext_a = resolve_domain("/usr/lib/python3.11/json/decoder.py")
    assert ext_a["domain"] is None
    assert ext_a["tag"] == "[EXTERNAL: System / Runtime]"
    ext_b = resolve_domain("C:/Python313/Lib/site-packages/pytest/__init__.py")
    assert ext_b["domain"] is None


def test_artificial_engine_exception_decoration():
    caught_exc = None
    try:
        require(
            False,
            "Causal invariant violation: unverified mutation",
            rejection_class="HARD_INVARIANT_VIOLATION",
        )
    except Rejected as exc:
        caught_exc = exc

    assert caught_exc is not None
    output = format_architectural_trace(caught_exc)

    assert "[DOMAIN 01: Core Kernel]" in output
    assert "kageyoni/engine.py" in output
    assert "Zero Direct SQLite Mutation" in output
    assert "Protected Operation Status:    VIOLATED" in output
    assert "HARD_INVARIANT_VIOLATION" in output
    assert "Cross-Domain Boundary" in output


def test_engine_apply_rejection_trace():
    engine = Engine(":memory:")
    caught_exc = None
    try:
        engine.apply({"invalid": "command"})
    except Rejected as exc:
        caught_exc = exc

    assert caught_exc is not None
    output = format_architectural_trace(caught_exc)

    assert "ATLAS ARCHITECTURAL DIAGNOSTIC UMBILICAL (VOID-4 RESOLVER)" in output
    assert "[DOMAIN 01: Core Kernel]" in output
    assert "unknown command field" in output
    assert "kageyoni/engine.py" in output


def test_inspect_exception_structured_output():
    caught_exc = None
    try:
        require(False, "Test structural verification error")
    except Rejected as exc:
        caught_exc = exc

    assert caught_exc is not None
    trace = inspect_exception(caught_exc)

    assert isinstance(trace, ArchitecturalTrace)
    assert trace.exception is caught_exc
    assert trace.exception_type == "Rejected"
    assert trace.failing_domain_info["domain"] == 1
    assert trace.protected_operation_violated is True
    assert len(trace.frames) >= 2
    assert trace.frames[-1].domain == 1
    assert "Core Kernel" in trace.failing_domain_info["domain_name"]
    assert trace.originating_outpost != ""


def test_exception_without_traceback():
    exc = Rejected("Synthetic pre-raise invariant violation", rejection_class="HARD_INVARIANT_VIOLATION")
    output = format_architectural_trace(exc)

    assert isinstance(output, str)
    assert "Synthetic pre-raise invariant violation" in output
    assert "[No physical traceback frames attached to exception; synthesized / pre-raise]" in output
    assert "[DOMAIN 01: Core Kernel]" in output

    ext_exc = ValueError("External system error without frames")
    ext_output = format_architectural_trace(ext_exc)
    assert "[EXTERNAL: System / Runtime]" in ext_output


def test_install_architectural_excepthook():
    orig_hook = sys.excepthook
    try:
        install_architectural_excepthook()
        assert sys.excepthook != orig_hook
    finally:
        sys.excepthook = orig_hook
