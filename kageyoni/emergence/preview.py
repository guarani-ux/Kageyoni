"""
Preflight Configuration Preview Generator.
Analyzes selected participants, encounter coordinates, and affordance availability
to produce evidence-based pre-launch recommendations and testability audits.
"""

from __future__ import annotations
from typing import Any, Dict, List
from .models import (
    ParticipantConfig,
    EncounterConfig,
    EnvironmentAffordance,
    RunHorizon,
    EvidencePolicy,
    AvailabilitySetting,
)


def generate_configuration_preview(
    participants: List[ParticipantConfig],
    encounter: EncounterConfig,
    affordances: List[EnvironmentAffordance],
    horizon: RunHorizon,
    policy: EvidencePolicy,
) -> Dict[str, Any]:
    """Generates the preflight analysis report before launch."""
    preview: Dict[str, Any] = {
        "promising_combinations": [],
        "constraints_and_conflicts": [],
        "round_testability": [],
        "unreachable_claims": [],
        "hypothesized_descendants": [],
    }

    # 1. Promising combinations & rationale
    part_names = {p.character_id: p for p in participants}
    afford_dict = {a.carrier: a for a in affordances}

    if "sebastian" in part_names and "forms/dojutsu.json" in afford_dict:
        preview["promising_combinations"].append({
            "actors": ["Sebastian Nelson", "Dojutsu Field Wielding"],
            "rationale": "High causal memory (92) pairs with 1st-3rd Tomoe rules to inspect carrier bytes and invert causal dependency graphs.",
        })

    if "sciel" in part_names and "ichimonji/engine_core.mjs" in afford_dict:
        preview["promising_combinations"].append({
            "actors": ["Sciel", "Ichimonji Engine Core"],
            "rationale": "Supreme Will Density (98) can bind directly to Int32Array fixed-point arrays, eliminating floating-point narrative drift and anchoring allies against void extraction.",
        })

    if "alexandra" in part_names and "forms/six-paths-sage-mode.json" in afford_dict:
        preview["promising_combinations"].append({
            "actors": ["Alexandra", "Six Paths Sage Mode"],
            "rationale": "Antigravity leverage (95) allows cross-environment IPC coordination, bridging Windows SQLite and Ubuntu WSL Shinobi memory buffers.",
        })

    if "voss" in part_names and "kageyoni/workspaces/world.py" in afford_dict:
        preview["promising_combinations"].append({
            "actors": ["Voss", "Workspace Topology Manager"],
            "rationale": "Specialist Prime authority enables rapid unplaced cavity projections to isolate enemy node bindings from table schemas.",
        })

    if "second_queen_bleaklands" in part_names and "kageyoni/will.py" in afford_dict:
        preview["promising_combinations"].append({
            "actors": ["Second Queen of Bleaklands", "Primordial Will Engine"],
            "rationale": "Supreme sovereign will (99) anchors basalt invariance, ensuring irreversible SQLite boundaries under causal extraction.",
        })

    if "elijah" in part_names and "kageyoni/constellation.py" in afford_dict:
        preview["promising_combinations"].append({
            "actors": ["Elijah", "Constellation Lifecycle & Beast Executor"],
            "rationale": "First Revision Seeker causal memory (96) pairs with Beast scar tracking to preserve unbroken lineage continuity across world reboots.",
        })

    if "arianne" in part_names and "kageyoni/workspaces/world.py" in afford_dict:
        preview["promising_combinations"].append({
            "actors": ["Arianne", "Workspace Topology Manager"],
            "rationale": "Antigravity leverage (93) and coordinate sentinel mastery re-routes unplaced nodes into isolated containment buffers before causal cascade.",
        })

    if "maki" in part_names and ("ichimonji/engine_core.mjs" in afford_dict or "kageyoni/composition/gates.py" in afford_dict):
        preview["promising_combinations"].append({
            "actors": ["Maki", "Ichimonji Deterministic Engine Core"],
            "rationale": "Kinetic Vanguard bandwidth (92) and Will density (94) enforce physical momentum conservation against unverified slot transitions.",
        })

    # 2. Constraints and conflicts
    for pt in participants:
        for c in pt.constraints:
            preview["constraints_and_conflicts"].append({
                "type": f"Participant Constraint ({pt.name})",
                "detail": c,
            })

    for enc_c in encounter.constraints:
        preview["constraints_and_conflicts"].append({
            "type": "Encounter Constraint",
            "detail": enc_c,
        })

    carriers_str = " ".join([a.carrier for a in affordances])
    if "migration_024.sql" in carriers_str or "gates.py" in carriers_str:
        preview["constraints_and_conflicts"].append({
            "type": "Substrate Invariant",
            "detail": "Composition gates enforce acyclic directed graph closure and database triggers block unplaced character severance.",
        })

    if any(a.availability in (AvailabilitySetting.ASSUMED, AvailabilitySetting.UNAVAILABLE) for a in affordances):
        assumed = [a.name for a in affordances if a.availability in (AvailabilitySetting.ASSUMED, AvailabilitySetting.UNAVAILABLE)]
        preview["constraints_and_conflicts"].append({
            "type": "Epistemic Gap",
            "detail": f"Affordances {assumed} are ASSUMED or UNAVAILABLE. Claims derived from them cannot achieve TESTED_IN_SCOPE without live execution.",
        })

    # 3. Round testability
    preview["round_testability"].append({
        "phase_range": "Rounds 1-3",
        "scope": "Perceptual & Carrier Telemetry: Verifies AST reading, transaction boundary detection, and isolation level checking.",
    })
    preview["round_testability"].append({
        "phase_range": "Rounds 4-6",
        "scope": "Resistance & Schema Invariance: Tests fixed-point substrate friction and database trigger deflection under simulated adversarial mutation.",
    })
    preview["round_testability"].append({
        "phase_range": "Rounds 7-9",
        "scope": "Confluence & Embodiment: Tests multi-workspace IPC synchronization and referentially transparent tick resolution under Priority 3 (COMBAT).",
    })
    preview["round_testability"].append({
        "phase_range": "Round 10",
        "scope": "Terminal Synthesis & Joy Boy Reground: Measures scar preservation, receipt immutability, and state reconstruction.",
    })

    # 4. Unreachable claims (lacking tests)
    preview["unreachable_claims"].append({
        "claim": "Instantaneous absolute annihilation of hostile entity",
        "reason": "Lacks reachable test; violated by Kageyoni conservation laws and referential transparency.",
    })
    preview["unreachable_claims"].append({
        "claim": "Autonomous qualification of candidate techniques without human or engine verification",
        "reason": "Wielding rule violation: Delta D, Delta T, Delta M !-> Delta Authority. Reality contact required.",
    })

    # 5. Hypothesized descendants to investigate
    preview["hypothesized_descendants"] = [
        {"name": "CarrierASTLens", "hypothesis": "Perceiving code AST directly reveals hostile execution graph depth."},
        {"name": "BasaltFixedMathRedoubt", "hypothesis": "Fixed-point integers prevent narrative topological displacement."},
        {"name": "ReflectiveInvariantBastion", "hypothesis": "SQLite schema triggers can deflect causal cascade vectors back onto caller."},
        {"name": "TriadConstellationBeast", "hypothesis": "Temporary multi-participant embodiment executes referentially transparent ticks."},
        {"name": "JoyBoyRegroundCommit", "hypothesis": "Regrounding releases prompt framing while preserving empirical receipts."},
        {"name": "DesolationBasaltBulwark", "hypothesis": "Second Queen absolute Will anchors substrate against narrative decay."},
        {"name": "FirstRevisionContinuityAnchor", "hypothesis": "Elijah causal memory stitches broken branches back to canonical roots."},
        {"name": "CoordinateSpatialWeave", "hypothesis": "Arianne coordinate boundary routing prevents workspace isolation leaks."},
        {"name": "KineticSubstrateMomentumGate", "hypothesis": "Maki physical mass enforcement defers non-physical narrative strikes."},
    ]

    return preview
