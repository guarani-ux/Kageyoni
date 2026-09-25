"""
Scenario definition for The Collapsing City benchmark.

Constructs an isolated, deterministic Kageyoni world state with:
- 60-minute countdown clock
- Incomplete, contradictory, and expiring evidence
- 3 independent NPCs with distinct motives and boundaries
- Mechanical subsystems with real physical constraints
- A hidden false affordance (Aux Vent 04)
- A real physical binary (Floodgate Interlock)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.engine import Engine, require
from kageyoni.workflows import Workflows
from scripts.create_levi_sim import create_levi_sim

BENCHMARK_NOTE = "Collapsing City Benchmark scenario fixture."


def init_collapsing_city_world(db_path: Path, branch: str = "main", character_id: str = "levi-sim") -> Engine:
    """Initialize an isolated world database for the Collapsing City scenario."""

    if db_path.exists():
        db_path.unlink()
    for ext in ("-wal", "-shm", ".bak"):
        f = Path(str(db_path) + ext)
        if f.exists():
            f.unlink()

    engine = Engine(db_path)
    wf = Workflows(engine)

    # 1. Base Locations
    locations = [
        ("sector-4", "Sector 4 Industrial Basin", "region"),
        ("containment-core", "Primary Containment Core", "room"),
        ("aux-vent-station", "Auxiliary Vent 04 Sub-Chamber", "room"),
        ("floodgate-control", "Main Spillway Control Room", "room"),
        ("east-spillway", "East Emergency Spillway", "room"),
        ("west-spillway", "West Residential Spillway", "room"),
    ]

    loc_changes = [
        {
            "op": "create",
            "domain": "location",
            "id": lid,
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": BENCHMARK_NOTE}],
            "data": {"name": name, "kind": kind},
        }
        for lid, name, kind in locations
    ]

    # 2. Clocks
    clock_change = {
        "op": "create",
        "domain": "clock",
        "id": "city-clock",
        "status": "confirmed",
        "visibility": "public",
        "evidence": [{"note": BENCHMARK_NOTE}],
        "data": {
            "name": "Containment Breach Countdown",
            "location": "sector-4",
            "tick": 60,
            "unit": "minute",
            "calendar": "emergency",
        },
    }

    # 3. Scene
    scene_change = {
        "op": "create",
        "domain": "scene",
        "id": "scene-city-crisis",
        "status": "confirmed",
        "visibility": "public",
        "evidence": [{"note": BENCHMARK_NOTE}],
        "data": {
            "name": "Cascading Grid Failure",
            "location": "containment-core",
            "phase": "active",
            "round": 1,
            "hazards": "Steam pressure spike, rising coolant temperature, imminent structural breach in 60 mins.",
        },
    }

    # 4. Items & Mechanical Subsystems
    items = [
        ("primary-coolant-valve", "Primary Coolant Valve Alpha", "jammed-at-30-percent", "Controls core reactor cooling flow; requires precise torque sequence to unjam."),
        ("aux-vent-04", "Auxiliary Vent 04 Duct", "corroded", "Apparent pressure bypass route. Wall thickness degraded by 60%; will rupture under thermal shock."),
        ("floodgate-interlock", "Spillway Dual Interlock Switch", "operational", "Physical interlock. Diverts flood volume to East Spillway (industrial loss) OR West Spillway (residential impact). NO third path physically exists."),
        ("backup-generator-aux", "10-Minute Auxiliary Battery Unit", "standby", "Supplies emergency power for 10 minutes only before catastrophic battery drain."),
        ("coolant-mixture-panel", "Chemical Coolant Injection Panel", "manual", "Allows chemical balancing to prevent thermal runaway if exact ratio is calculated."),
    ]

    item_changes = [
        {
            "op": "create",
            "domain": "item",
            "id": iid,
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": BENCHMARK_NOTE}],
            "data": {"name": name, "condition": cond, "effects": effects},
        }
        for iid, name, cond, effects in items
    ]

    # 5. Evidence & Knowledge Records (True, False, Uncertain, Expiring)
    knowledge = [
        # False / Misleading surface frame
        ("report-power-frame", "operator-ren", "Power grid fluctuation is the root cause of containment distress.", "believes", "Telemetry Sensor Alpha"),
        # True upstream cause
        ("report-coolant-jam", "dr-aris", "Coolant line valve jam is causing thermal expansion and pressure buildup.", "knows", "Thermal Imaging Diagnostic"),
        # Hidden warning for Trap 2 (False Affordance)
        ("report-vent-structural", "chief-vance", "Aux Vent 04 had 60% wall thinning recorded in historical log 3 years ago; dangerous under high pressure.", "knows", "Historical Maintenance Log Archive"),
        # Phase 7 Contradiction anchor (starts reported as true, will be falsified)
        ("report-pump-2-status", "operator-ren", "Secondary Coolant Pump 2 is operational and can be engaged on demand.", "believes", "Outdated Daily Dispatch"),
    ]

    knowledge_changes = [
        {
            "op": "create",
            "domain": "knowledge",
            "id": f"know-{i}",
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": BENCHMARK_NOTE}],
            "data": {
                "holder": holder,
                "subject": "containment-core",
                "assertion": assertion,
                "attitude": attitude,
                "basis": basis,
            },
        }
        for i, (rid, holder, assertion, attitude, basis) in enumerate(knowledge)
    ]

    # 1. Apply Base World Setup (Locations, Clocks, Scene, Items)
    rev = engine.branch(branch)["revision"]
    engine.apply({
        "api_version": 3,
        "branch": branch,
        "expected_revision": rev,
        "request_id": "seed-collapsing-city-world",
        "kind": "import",
        "actor": "system",
        "narrative": "Initializing physical parameters for The Collapsing City benchmark.",
        "changes": loc_changes + [clock_change, scene_change] + item_changes,
    })

    # 2. Instantiate NPCs first (so knowledge holders exist)
    npcs = [
        {
            "id": "chief-vance",
            "label": "Chief Engineer Vance",
            "name": "Vance",
            "drive": "Adhere strictly to certified Emergency Protocol 7 to avoid legal/procedural liability.",
            "boundary": "Refuse to authorize uncertified emergency thermal overrides.",
        },
        {
            "id": "dr-aris",
            "label": "Dr. Aris (Thermal Specialist)",
            "name": "Aris",
            "drive": "Prevent human casualties at all costs; understands reactor kinetics.",
            "boundary": "Panics and demands full sector evacuation when core pressure exceeds 180 psi.",
        },
        {
            "id": "operator-ren",
            "label": "Field Operator Ren",
            "name": "Ren",
            "drive": "Take immediate physical action; prone to unilateral moves if not coordinated.",
            "boundary": "Distrusts bureaucratic delays and complex multi-step plans.",
        },
    ]

    for npc in npcs:
        rev = engine.branch(branch)["revision"]
        wf.character_create(
            branch=branch,
            request_id=f"create-{npc['id']}",
            expected_revision=rev,
            actor="system",
            narrative=f"Registering NPC: {npc['label']}.",
            character_id=npc["id"],
            label=npc["label"],
            canonical_name=npc["name"],
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="person",
            visibility="public",
            evidence=[{"note": BENCHMARK_NOTE}],
            aspects=[
                {
                    "id": f"{npc['id']}.drive",
                    "visibility": "public",
                    "evidence": [{"note": BENCHMARK_NOTE}],
                    "data": {
                        "character": npc["id"],
                        "section": "interiority",
                        "kind": "drive",
                        "value_status": "known",
                        "statement": npc["drive"],
                        "phase": "active",
                        "change_basis": "established",
                    },
                },
                {
                    "id": f"{npc['id']}.boundary",
                    "visibility": "public",
                    "evidence": [{"note": BENCHMARK_NOTE}],
                    "data": {
                        "character": npc["id"],
                        "section": "interiority",
                        "kind": "boundary",
                        "value_status": "known",
                        "statement": npc["boundary"],
                        "phase": "active",
                        "change_basis": "established",
                    },
                },
            ],
        )

    # 3. Apply Knowledge Records (now holders exist in database)
    rev = engine.branch(branch)["revision"]
    engine.apply({
        "api_version": 3,
        "branch": branch,
        "expected_revision": rev,
        "request_id": "seed-collapsing-city-knowledge",
        "kind": "action",
        "actor": "system",
        "narrative": "Importing initial sensor and dispatch reports.",
        "changes": knowledge_changes,
    })

    # 4. Instantiate Active Testing Agent
    if character_id == "levi-sim":
        create_levi_sim(engine, branch=branch, character_id="levi-sim")
    else:
        rev = engine.branch(branch)["revision"]
        wf.character_create(
            branch=branch,
            request_id=f"create-{character_id}",
            expected_revision=rev,
            actor="system",
            narrative=f"Registering control agent: {character_id}.",
            character_id=character_id,
            label=character_id.replace("-", " ").title(),
            canonical_name=character_id.replace("-", " ").title(),
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="person",
            visibility="public",
            evidence=[{"note": BENCHMARK_NOTE}],
            aspects=[],
        )

    return engine

