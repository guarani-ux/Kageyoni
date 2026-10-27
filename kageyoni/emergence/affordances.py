"""
Affordance Discovery and Environment Inspection for Constellation Emergence.
Scans reachable modules, carriers, forms, and triggers, assessing live inspectability,
execution capability, or assumed status.
"""

from __future__ import annotations
import ast
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from .models import EnvironmentAffordance, AvailabilitySetting

REPO_ROOT = Path(__file__).resolve().parents[2]
WSL_ROOT = Path(r"\\wsl.localhost\Ubuntu\home\flowe\shinobi") if sys.platform == "win32" else Path(os.environ.get("SHINOBI_ROOT", Path.home() / "shinobi"))
LOCAL_SHINOBI_ROOT = REPO_ROOT / "shinobi"


def discover_affordances() -> List[EnvironmentAffordance]:
    """Discovers reachable affordances across Kageyoni and WSL Shinobi."""
    affordances: List[EnvironmentAffordance] = []

    # 1. Kageyoni Composition Gates
    gates_path = REPO_ROOT / "kageyoni" / "composition" / "gates.py"
    if gates_path.exists():
        features = []
        try:
            tree = ast.parse(gates_path.read_text(encoding="utf-8"))
            features = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        except Exception:
            features = ["dependencies_closed", "no_unplaced_nodes", "cardinality_valid"]
        affordances.append(
            EnvironmentAffordance(
                name="Composition Gates Substrate",
                category="Structural Invariants",
                path=str(gates_path),
                carrier="kageyoni/composition/gates.py",
                availability=AvailabilitySetting.LIVE_INSPECTABLE,
                intensity="AST and function-level closure verification; checks dependency graph acyclicity",
                observable_features=features[:6],
            )
        )
    else:
        affordances.append(
            EnvironmentAffordance(
                name="Composition Gates Substrate",
                category="Structural Invariants",
                path=str(gates_path),
                carrier="kageyoni/composition/gates.py",
                availability=AvailabilitySetting.UNAVAILABLE,
                intensity="Missing on filesystem",
                observable_features=[],
            )
        )

    # 2. Will System Module
    will_path = REPO_ROOT / "kageyoni" / "will.py"
    if will_path.exists():
        affordances.append(
            EnvironmentAffordance(
                name="Primordial Will Engine",
                category="Will Dynamics",
                path=str(will_path),
                carrier="kageyoni/will.py",
                availability=AvailabilitySetting.LIVE_INSPECTABLE,
                intensity="Expression contracts and SQLite persistence; generates unyielding physical boundaries",
                observable_features=["will_technique", "will_attempt", "generative_boundary", "contract_history"],
            )
        )

    # 3. SQLite Lineage & Triggers Migration 024
    mig_path = REPO_ROOT / "migration_024.sql"
    if not mig_path.exists():
        mig_path = REPO_ROOT / "kageyoni" / "schema" / "migrations" / "migration_024.sql"
    if mig_path.exists():
        affordances.append(
            EnvironmentAffordance(
                name="Lineage Invariant Triggers (Migration 024)",
                category="Database Schemas",
                path=str(mig_path),
                carrier="kageyoni/schema/migrations/migration_024.sql",
                availability=AvailabilitySetting.LIVE_INSPECTABLE,
                intensity="SQLite trigger level enforcer; blocks unauthorized delete/mutation of root character tokens",
                observable_features=["immutable_characters_no_delete", "immutable_characters_no_update"],
            )
        )

    # 4. Dojutsu Forms
    dojutsu_path = WSL_ROOT / "forms" / "dojutsu.json"
    if not dojutsu_path.exists():
        dojutsu_path = LOCAL_SHINOBI_ROOT / "forms" / "dojutsu.json"
    
    if dojutsu_path.exists():
        features = ["sharingan_1_to_3_tomoe", "rinnegan_1_to_3_tomoe", "reality_contact_law"]
        try:
            data = json.loads(dojutsu_path.read_text(encoding="utf-8"))
            rules = data.get("wielding_rules", [])
            features.extend(rules[:2])
        except Exception:
            pass
        affordances.append(
            EnvironmentAffordance(
                name="Dojutsu Field Wielding Forms",
                category="Perceptual / Transformational Forms",
                path=str(dojutsu_path),
                carrier="forms/dojutsu.json",
                availability=AvailabilitySetting.LIVE_INSPECTABLE,
                intensity="Epistemic partitioning: Observer Horizon != Constellation Horizon; direct carrier inspection",
                observable_features=features,
            )
        )
    else:
        affordances.append(
            EnvironmentAffordance(
                name="Dojutsu Field Wielding Forms",
                category="Perceptual / Transformational Forms",
                path=str(dojutsu_path),
                carrier="forms/dojutsu.json",
                availability=AvailabilitySetting.ASSUMED,
                intensity="Assumed operational parameters from legacy specification",
                observable_features=[],
            )
        )

    # 5. Six Paths Sage Mode Form
    sage_path = WSL_ROOT / "forms" / "six-paths-sage-mode.json"
    if not sage_path.exists():
        sage_path = LOCAL_SHINOBI_ROOT / "forms" / "six-paths-sage-mode.json"
    if sage_path.exists():
        affordances.append(
            EnvironmentAffordance(
                name="Six Paths Sage Mode Form",
                category="Exploratory Constellation Forms",
                path=str(sage_path),
                carrier="forms/six-paths-sage-mode.json",
                availability=AvailabilitySetting.LIVE_INSPECTABLE,
                intensity="Cognitive aperture expansion: uncoupling fixed procedural boundaries across environments",
                observable_features=["reachability_freedom", "non_procedural_adaptation", "fallible_bridge_law"],
            )
        )

    # 6. Ichimonji ESM Simulation Core
    ichimonji_path = WSL_ROOT / "ichimonji" / "engine_core.mjs"
    if not ichimonji_path.exists():
        ichimonji_path = LOCAL_SHINOBI_ROOT / "ichimonji" / "engine_core.mjs"
    if ichimonji_path.exists():
        affordances.append(
            EnvironmentAffordance(
                name="Ichimonji Deterministic Engine Core",
                category="Simulation Substrate",
                path=str(ichimonji_path),
                carrier="ichimonji/engine_core.mjs",
                availability=AvailabilitySetting.LIVE_INSPECTABLE,
                intensity="Referentially transparent simulateTick; deterministic intent queue: FALL_BACK > COMBAT > MOVEMENT > MEMORY",
                observable_features=["EntityStateSoA", "SpatialGrid", "simulateTick", "INTENT_PRIORITY"],
            )
        )
    else:
        affordances.append(
            EnvironmentAffordance(
                name="Ichimonji Deterministic Engine Core",
                category="Simulation Substrate",
                path=str(ichimonji_path),
                carrier="ichimonji/engine_core.mjs",
                availability=AvailabilitySetting.ASSUMED,
                intensity="Assumed fixed-point execution rules",
                observable_features=[],
            )
        )

    # 7. Workspace Topology Manager
    world_path = REPO_ROOT / "kageyoni" / "workspaces" / "world.py"
    if world_path.exists():
        affordances.append(
            EnvironmentAffordance(
                name="Workspace Topology Manager",
                category="Spatial / Organizational Topology",
                path=str(world_path),
                carrier="kageyoni/workspaces/world.py",
                availability=AvailabilitySetting.LIVE_INSPECTABLE,
                intensity="Manages multi-workspace lifecycles, coordinate isolation, and cross-boundary handoffs",
                observable_features=["WorldManager", "workspace_transitions", "unplaced_node_detection"],
            )
        )

    # 8. Constellation Substrate Primaries
    constellation_path = REPO_ROOT / "kageyoni" / "constellation.py"
    if constellation_path.exists():
        affordances.append(
            EnvironmentAffordance(
                name="Constellation Lifecycle & Beast Executor",
                category="Substrate Primitives",
                path=str(constellation_path),
                carrier="kageyoni/constellation.py",
                availability=AvailabilitySetting.EXECUTABLE,
                intensity="Live executable Beast context, Summon, Transmute, and Joy Boy Reground invariant recovery",
                observable_features=["Beast", "reground", "CandidateTechnique", "ConstellationField"],
            )
        )

    return affordances
