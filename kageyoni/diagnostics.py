"""
Atlas Diagnostic Umbilical & Architectural Trace Resolver.

Closes Void 4 of the Atlas Negative Space: The Diagnostic Umbilical
(Stack Traces Speak in Line Numbers, Not Domains).

Transforms raw, architectural-vacuum Python tracebacks
(e.g., File "kageyoni/engine.py", line 140, in apply)
into domain-aware, invariant-bound architectural diagnostic traces.

Atlas Sovereign Domains:
  - Domain 1: Core Kernel (Causal State Engine & Invariants)
  - Domain 2: Historical Narrative Continuity & Canonical Worlds (The Canon & Memory)
  - Domain 3: Tactical World Engine & Playable Simulation (The Playable RPG)
  - Domain 4: Systems & Binary Reverse Engineering (The REA Estate)
  - Domain 5: Cognitive Operating System & Media Production (The Agency Engine)
  - Domain 6: Autonomous Agents, Governance & Tooling (Runtime & Verification)
"""

from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DOMAINS: dict[int, dict[str, Any]] = {
    1: {
        "domain": 1,
        "domain_id": "01",
        "domain_name": "Core Kernel",
        "short_name": "Core Kernel",
        "name": "Core Kernel",
        "full_name": "Causal State Engine & Invariants (Core Kernel)",
        "tag": "[DOMAIN 01: Core Kernel]",
        "summary": "Core causal state engine, cryptographically hashed event store, revision tracking, SQLite migrations, and protected operations.",
        "invariants": [
            "Zero Direct SQLite Mutation: Never execute INSERT/UPDATE/DELETE on world tables outside of Engine.apply().",
            "Fail-Closed Compilation: Missing causal prerequisites, ontology gaps, or authority violations must reject explicitly.",
        ],
        "invariant_summary": "Zero Direct SQLite Mutation; Fail-Closed Compilation",
        "boundary_policy": "Core source code; strict reviews; all world state commits must flow through Engine.apply().",
        "primary_entrypoints": ["kageyoni/engine.py", "kageyoni/gateway.py"],
    },
    2: {
        "domain": 2,
        "domain_id": "02",
        "domain_name": "Historical Narrative & Continuity",
        "short_name": "Historical Narrative & Continuity",
        "name": "Historical Narrative & Continuity",
        "full_name": "Historical Narrative Continuity & Canonical Worlds (The Canon & Memory)",
        "tag": "[DOMAIN 02: Historical Narrative & Continuity]",
        "summary": "Authoritative historical grounding across canonical campaigns (Booderland, Gaia, Ichimonji, Voss Aftermath).",
        "invariants": [
            "Zero Silent Retcons: Alexandra is 25 years old. Xandra of Gaia is distinct from Xandra of Ichimonji.",
            "Historical Carrier Custody: Never delete or overwrite the .sqlite databases in recovery/ or fixtures/.",
        ],
        "invariant_summary": "Zero Silent Retcons; Historical Carrier Custody",
        "boundary_policy": "Absolute canon; read-only historical continuity.",
        "primary_entrypoints": ["sources/", "recovery/", "levi_sim/operator.py"],
    },
    3: {
        "domain": 3,
        "domain_id": "03",
        "domain_name": "Tactical World Engine & Playable Simulation",
        "short_name": "Tactical World Engine & Playable Simulation",
        "name": "Tactical World Engine & Playable Simulation",
        "full_name": "Tactical World Engine & Playable Simulation (The Playable RPG)",
        "tag": "[DOMAIN 03: Tactical World Engine & Playable Simulation]",
        "summary": "Discrete playable world execution: 100x100 spatial grid, 2RN combat math, DMW roulette, Gambits, Kata decks, and portable saves.",
        "invariants": [
            "No Detached Shadow Tables: The tactical layer must not create parallel un-audited tables that bypass the canonical Engine.apply event stream.",
            "Portable Saves: Saved states in data/SAVE.json must conform strictly to schema.",
        ],
        "invariant_summary": "No Detached Shadow Tables; Portable Saves Schema Conformity",
        "boundary_policy": "All game state must flow through Engine.apply; strict schema conformity for SAVE.json.",
        "primary_entrypoints": ["kageyoni/cli.py", "kageyoni/playable_world/", "kageyoni/combat/"],
    },
    4: {
        "domain": 4,
        "domain_id": "04",
        "domain_name": "Systems & Binary Reverse Engineering",
        "short_name": "Systems & Binary Reverse Engineering",
        "name": "Systems & Binary Reverse Engineering",
        "full_name": "Systems & Binary Reverse Engineering (The REA Estate)",
        "tag": "[DOMAIN 04: Systems & Binary Reverse Engineering]",
        "summary": "Binary reverse engineering, protocol reconstruction, and capability extraction (Universal Target Inspector & Ninshū 48-channel desk).",
        "invariants": [
            "Non-Invasive Inspection: Reverse engineering tools analyze binaries and emit structured artifacts/schemas; they never mutate the narrative database or alter game saves.",
            "No Duplicate Binary Readers: All new REA targets must be added as TargetProfile definitions in rea_forge/src/inspector/profiles/.",
        ],
        "invariant_summary": "Non-Invasive Inspection; No Duplicate Binary Readers",
        "boundary_policy": "Non-invasive analysis; no direct DB mutations; profiles registered in rea_forge.",
        "primary_entrypoints": ["rea_forge/", "kageyoni/ninshu/console.py", "tools/run_ssl_audit.py"],
    },
    5: {
        "domain": 5,
        "domain_id": "05",
        "domain_name": "Cognitive OS & Media Intelligence",
        "short_name": "Cognitive OS & Media Intelligence",
        "name": "Cognitive OS & Media Intelligence",
        "full_name": "Cognitive Operating System & Media Production (The Agency Engine)",
        "tag": "[DOMAIN 05: Cognitive OS & Media Intelligence]",
        "summary": "Multi-domain cognitive agency and production pipelines: mission runner, vault management, A/V scriptwriting, and research compiler.",
        "invariants": [
            "Epistemic Separation: Observation != Claim != Warrant. Information enters as evidence, never unearned canonical truth.",
            "Spoken-Ear & Visual Grounding: All script outputs must pass visual counterpoint and spoken-ear readability without robotic AI cadence.",
        ],
        "invariant_summary": "Epistemic Separation (Observation != Claim != Warrant); Spoken-Ear & Visual Grounding",
        "boundary_policy": "Epistemic separation via formal Warrants; visual-first script verification.",
        "primary_entrypoints": ["cognitive-os/scripts/cos_cli.py", "kageyoni/research_compiler/", "av-story-skills/"],
    },
    6: {
        "domain": 6,
        "domain_id": "06",
        "domain_name": "Autonomous Agents, Governance & Tooling",
        "short_name": "Autonomous Agents, Governance & Tooling",
        "name": "Autonomous Agents, Governance & Tooling",
        "full_name": "Autonomous Agents, Governance & Tooling (Runtime & Verification)",
        "tag": "[DOMAIN 06: Autonomous Agents, Governance & Tooling]",
        "summary": "Autonomous participant runtime, long-horizon evaluation benchmarks, and unified developer tooling/audit gates.",
        "invariants": [
            "No Synthetic Self-Certification: Benchmarks and qualification gates must execute real assertions and report raw exit codes (or declare VERIFIER_DEFICIT).",
        ],
        "invariant_summary": "No Synthetic Self-Certification (Real Assertions & Raw Exit Codes)",
        "boundary_policy": "Zero synthetic mock rigging; mechanical audit gates; append-only evidence custody.",
        "primary_entrypoints": ["shinobi/shinobi.py", "benchmarks/collapsing_city/", "tools/runner.py"],
    },
}

EXTERNAL_DOMAIN: dict[str, Any] = {
    "domain": None,
    "domain_id": "00",
    "domain_name": "External / System",
    "short_name": "External",
    "name": "External / System",
    "full_name": "External Runtime Environment / Standard Library",
    "tag": "[EXTERNAL: System / Runtime]",
    "summary": "Unmonitored external runtime boundary outside Atlas Sovereign Domains.",
    "invariants": [],
    "invariant_summary": "External boundary; unmonitored invariants",
    "boundary_policy": "External caller boundary.",
    "primary_entrypoints": [],
}


def _normalize_path(file_path: Any) -> str:
    if file_path is None:
        return ""
    return str(file_path).replace("\\", "/")


def _extract_relative_display_path(file_path: str) -> str:
    p = _normalize_path(file_path)
    if not p:
        return "<unknown>"

    try:
        path_obj = Path(p)
        if path_obj.is_absolute():
            try:
                rel = path_obj.resolve().relative_to(Path.cwd().resolve())
                return str(rel).replace("\\", "/")
            except ValueError:
                pass
    except Exception:
        pass

    markers = [
        "kageyoni/", "sources/", "recovery/", "levi_sim/", "fixtures/",
        "cognitive-os/", "av-story-skills/", "contracts/", "rea_forge/",
        "shinobi/", "shinobi_agent/", "benchmarks/", "governance/", "tools/",
        "tests/", "data/", "schemas/", "external_repos/",
    ]
    p_lower = p.lower()
    for marker in markers:
        idx = p_lower.rfind(marker)
        if idx != -1:
            return p[idx:]

    return p


def resolve_domain(file_path: str) -> dict[str, Any]:
    raw_p = _normalize_path(file_path)
    p_lower = raw_p.lower()
    rel_p = _extract_relative_display_path(raw_p)

    target_domain: Optional[int] = None

    if any(m in p_lower for m in [
        "/rea_forge/", "rea_forge/",
        "/external_repos/rea", "external_repos/rea",
        "/kageyoni/ninshu/", "kageyoni/ninshu/", "ninshu/",
        "run_ssl_audit.py",
    ]):
        target_domain = 4

    elif any(m in p_lower for m in [
        "/cognitive-os/", "cognitive-os/",
        "/av-story-skills/", "av-story-skills/",
        "/contracts/", "contracts/",
        "/kageyoni/research_compiler/", "kageyoni/research_compiler/", "research_compiler/",
        "videostudio", "video-house",
    ]):
        target_domain = 5

    elif any(m in p_lower for m in [
        "/kageyoni/playable_world/", "kageyoni/playable_world/", "playable_world/",
        "/kageyoni/combat/", "kageyoni/combat/", "combat/",
        "/kageyoni/martial/", "kageyoni/martial/", "martial/",
        "/kageyoni/spatial/", "kageyoni/spatial/", "spatial/",
        "/kageyoni/chat_frame.py", "kageyoni/chat_frame.py", "chat_frame.py",
        "/kageyoni/cli.py", "kageyoni/cli.py", "cli.py",
        "/data/", "data/",
    ]):
        target_domain = 3

    elif any(m in p_lower for m in [
        "/sources/", "sources/",
        "/recovery/", "recovery/",
        "/levi_sim/", "levi_sim/",
        "/fixtures/historical", "fixtures/historical",
        "/fixtures/", "fixtures/",
    ]):
        target_domain = 2

    elif any(m in p_lower for m in [
        "/shinobi/", "shinobi/",
        "/shinobi_agent/", "shinobi_agent/",
        "/benchmarks/", "benchmarks/",
        "/governance/", "governance/",
        "/tools/", "tools/",
        "/.agents/", ".agents/",
        "/.github/", ".github/",
        "/evidence/", "evidence/",
        "/tests/", "tests/", "test_", "_test.py",
        "/kageyoni/situations/", "kageyoni/situations/", "situations/",
        "/kageyoni/vantage/", "kageyoni/vantage/", "vantage/",
        "/kageyoni/workspaces/", "kageyoni/workspaces/", "workspaces/",
        "participant_kernel.py",
    ]):
        target_domain = 6

    elif any(m in p_lower for m in [
        "/kageyoni/engine.py", "kageyoni/engine.py", "engine.py",
        "/kageyoni/gateway.py", "kageyoni/gateway.py", "gateway.py",
        "/kageyoni/model.py", "kageyoni/model.py", "model.py",
        "/kageyoni/composition/", "kageyoni/composition/", "composition/",
        "/kageyoni/v11/", "kageyoni/v11/", "v11/",
        "/kageyoni/database/", "kageyoni/database/", "database/",
        "/schemas/", "schemas/",
        "/build/", "build/",
        "/dist/", "dist/",
        "/kageyoni/", "kageyoni/",
    ]):
        target_domain = 1

    if target_domain is not None and target_domain in DOMAINS:
        info = dict(DOMAINS[target_domain])
    else:
        info = dict(EXTERNAL_DOMAIN)

    info["file_path"] = raw_p
    info["relative_path"] = rel_p
    return info


@dataclass
class FrameInfo:
    filename: str
    relative_path: str
    lineno: int
    name: str
    line: str
    domain_info: dict[str, Any]

    @property
    def domain(self) -> Optional[int]:
        return self.domain_info.get("domain")

    @property
    def tag(self) -> str:
        return self.domain_info.get("tag", "[DOMAIN ??]")


@dataclass
class BoundaryTransition:
    from_frame: FrameInfo
    to_frame: FrameInfo
    from_domain_info: dict[str, Any]
    to_domain_info: dict[str, Any]

    @property
    def transition_label(self) -> str:
        f_tag = self.from_domain_info.get("tag", "[DOMAIN ??]")
        t_tag = self.to_domain_info.get("tag", "[DOMAIN ??]")
        return f"{f_tag} -> {t_tag}"


@dataclass
class ArchitecturalTrace:
    exception: Exception
    exception_type: str
    exception_message: str
    frames: list[FrameInfo] = field(default_factory=list)
    boundary_transitions: list[BoundaryTransition] = field(default_factory=list)
    failing_domain_info: dict[str, Any] = field(default_factory=dict)
    cross_domain_violated: bool = False
    cross_domain_reason: str = ""
    protected_operation_violated: bool = False
    protected_operation_details: str = ""
    gateway_mediated: bool = False
    originating_outpost: str = "Unknown"

    def format(self) -> str:
        lines: list[str] = []
        bar = "=" * 80
        thin_bar = "-" * 80

        lines.append(bar)
        lines.append("ATLAS ARCHITECTURAL DIAGNOSTIC UMBILICAL (VOID-4 RESOLVER)")
        lines.append("Domain-Aware Architectural Traceback & Invariant Verification")
        lines.append(bar)

        f_dom = self.failing_domain_info
        f_tag = f_dom.get("tag", "[DOMAIN ??]")
        f_inv_summary = f_dom.get("invariant_summary", "None")

        lines.append(f"Exception Type:    {self.exception_type}")
        lines.append(f"Exception Message: {self.exception_message}")
        lines.append(f"Failing Domain:    {f_tag}")
        lines.append(f"Domain Purpose:    {f_dom.get('full_name', f_dom.get('domain_name', 'Unknown'))}")
        lines.append(f"Active Invariant:  {f_inv_summary}")

        invariants = f_dom.get("invariants", [])
        if invariants:
            lines.append("Governing Invariants:")
            for inv in invariants:
                lines.append(f"  * {inv}")

        lines.append(thin_bar)
        lines.append("Architectural Stack Trace (Boundary-Decorated):")

        if not self.frames:
            lines.append("  [No physical traceback frames attached to exception; synthesized / pre-raise]")
        else:
            for idx, frame in enumerate(self.frames):
                matching_transitions = [
                    bt for bt in self.boundary_transitions if bt.to_frame is frame
                ]
                for bt in matching_transitions:
                    lines.append(f"  >>> CROSS-DOMAIN BOUNDARY: {bt.transition_label} <<<")

                frame_line = (
                    f"  {frame.tag} {frame.relative_path}:{frame.lineno} in {frame.name}()"
                )
                lines.append(frame_line)
                if frame.line:
                    lines.append(f"      --> {frame.line.strip()}")

        lines.append(thin_bar)
        lines.append("Boundary & Invariant Assessment:")

        c_status = "VIOLATION DETECTED" if self.cross_domain_violated else "INTRA-DOMAIN / COMPLIANT"
        lines.append(f"  * Cross-Domain Boundary Status:  {c_status}")
        if self.cross_domain_reason:
            lines.append(f"    - Boundary Analysis:           {self.cross_domain_reason}")

        p_status = "VIOLATED" if self.protected_operation_violated else "COMPLIANT / NONE"
        lines.append(f"  * Protected Operation Status:    {p_status}")
        if self.protected_operation_details:
            lines.append(f"    - Operation Details:           {self.protected_operation_details}")

        lines.append(f"  * Bounded Gateway Mediation:     {'YES (BoundedKageyoniGateway active)' if self.gateway_mediated else 'NO (Direct Engine Call)'}")
        lines.append(f"  * Originating Outpost/Caller:    {self.originating_outpost}")

        if self.boundary_transitions:
            lines.append(f"  * Boundary Transitions Count:    {len(self.boundary_transitions)}")
            for i, bt in enumerate(self.boundary_transitions, 1):
                f_loc = f"{bt.from_frame.relative_path}:{bt.from_frame.lineno}"
                t_loc = f"{bt.to_frame.relative_path}:{bt.to_frame.lineno}"
                lines.append(f"    {i}. {bt.from_domain_info.get('domain_name')} ({f_loc}) -> {bt.to_domain_info.get('domain_name')} ({t_loc})")

        lines.append(bar)
        return "\n".join(lines)


def inspect_exception(exc: Exception) -> ArchitecturalTrace:
    exc_type = type(exc).__name__
    exc_msg = str(exc)

    tb = exc.__traceback__
    if tb is None:
        _, _, sys_tb = sys.exc_info()
        tb = sys_tb

    extracted_frames: list[traceback.FrameSummary] = []
    if tb is not None:
        extracted_frames = traceback.extract_tb(tb)

    frames: list[FrameInfo] = []
    boundary_transitions: list[BoundaryTransition] = []

    prev_frame_info: Optional[FrameInfo] = None

    for fs in extracted_frames:
        d_info = resolve_domain(fs.filename)
        rel_path = _extract_relative_display_path(fs.filename)
        f_info = FrameInfo(
            filename=fs.filename,
            relative_path=rel_path,
            lineno=fs.lineno or 0,
            name=fs.name,
            line=fs.line or "",
            domain_info=d_info,
        )
        frames.append(f_info)

        if prev_frame_info is not None:
            prev_d = prev_frame_info.domain
            curr_d = f_info.domain
            if prev_d != curr_d and (prev_d is not None or curr_d is not None):
                transition = BoundaryTransition(
                    from_frame=prev_frame_info,
                    to_frame=f_info,
                    from_domain_info=prev_frame_info.domain_info,
                    to_domain_info=d_info,
                )
                boundary_transitions.append(transition)

        prev_frame_info = f_info

    if frames:
        failing_frame = frames[-1]
        failing_domain_info = failing_frame.domain_info
    else:
        exc_mod = getattr(type(exc), "__module__", "")
        if "kageyoni" in exc_mod or "Rejected" in exc_type:
            failing_domain_info = resolve_domain("kageyoni/engine.py")
        else:
            failing_domain_info = dict(EXTERNAL_DOMAIN)

    gateway_mediated = any("gateway.py" in f.relative_path.lower() for f in frames)

    originating_outpost = "External / Unknown"
    if frames:
        first_frame = frames[0]
        d_name = first_frame.domain_info.get("domain_name", "External")
        originating_outpost = f"{d_name} ({first_frame.relative_path})"

    protected_op_violated = False
    protected_details: list[str] = []

    rejection_class = getattr(exc, "rejection_class", None)
    rejection_details = getattr(exc, "details", None)
    rejection_type = getattr(exc, "rejection_type", None)

    if exc_type == "Rejected" or rejection_class is not None:
        protected_op_violated = True
        cls_str = rejection_class or "INVARIANT_REJECTION"
        protected_details.append(f"Engine Invariant Rejection [{cls_str}]: {exc_msg}")
        if rejection_details:
            protected_details.append(f"Rejection Details: {rejection_details}")

    elif exc_type == "GatewayRejection" or rejection_type is not None:
        protected_op_violated = True
        protected_details.append(f"Gateway Rejection [{rejection_type}/{rejection_class}]: {exc_msg}")

    else:
        keywords = [
            "invariant", "protected", "warrant", "authority", "prohibited",
            "fail-closed", "direct sqlite mutation", "shadow table",
            "unauthorized", "unverified", "qualification deficit",
        ]
        low_msg = exc_msg.lower()
        low_type = exc_type.lower()
        if any(k in low_msg or k in low_type for k in keywords):
            protected_op_violated = True
            protected_details.append(f"Identified invariant/protected violation keyword: {exc_msg}")

    cross_domain_violated = False
    cross_reasons: list[str] = []

    if boundary_transitions:
        cross_domain_violated = True
        for bt in boundary_transitions:
            from_name = bt.from_domain_info.get("domain_name")
            to_name = bt.to_domain_info.get("domain_name")
            to_dom = bt.to_domain_info.get("domain")

            if to_dom == 1 and not gateway_mediated and "test" not in bt.from_frame.relative_path.lower():
                cross_reasons.append(
                    f"Direct unmediated call from {from_name} ({bt.from_frame.relative_path}) "
                    f"into Domain 1 (Core Kernel) bypassing BoundedKageyoniGateway."
                )
            else:
                cross_reasons.append(
                    f"Cross-domain transition from {from_name} to {to_name} terminated with exception."
                )

    return ArchitecturalTrace(
        exception=exc,
        exception_type=exc_type,
        exception_message=exc_msg,
        frames=frames,
        boundary_transitions=boundary_transitions,
        failing_domain_info=failing_domain_info,
        cross_domain_violated=cross_domain_violated,
        cross_domain_reason="; ".join(cross_reasons) if cross_reasons else "",
        protected_operation_violated=protected_op_violated,
        protected_operation_details="; ".join(protected_details) if protected_details else "",
        gateway_mediated=gateway_mediated,
        originating_outpost=originating_outpost,
    )


def format_architectural_trace(exc: Exception) -> str:
    trace_obj = inspect_exception(exc)
    return trace_obj.format()


def install_architectural_excepthook() -> None:
    old_hook = sys.excepthook

    def _hook(exc_type, exc_val, exc_tb):
        if issubclass(exc_type, Exception) and exc_val is not None:
            sys.stderr.write(format_architectural_trace(exc_val) + "\n")
        else:
            old_hook(exc_type, exc_val, exc_tb)

    sys.excepthook = _hook
