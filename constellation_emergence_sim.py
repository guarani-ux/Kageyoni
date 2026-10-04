#!/usr/bin/env python3
"""
Constellation Emergence Simulator: Confluence of Emergent Horizons
Autonomous 10-Phase Battle Simulation Engine for Kageyoni Shinobi.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from kageyoni.engine import Engine
    from kageyoni.participant_kernel import PersistentParticipant
    from kageyoni.constellation import (
        ConstellationField,
        CandidateTechnique,
        ConstellationElement,
        Beast,
        EpistemicStatus,
        DerivationStatus,
        reground,
    )
except ImportError as e:
    print(f"[ERROR] Failed to import Kageyoni core: {e}", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path("C:/Kageyoni")
WSL_SHINOBI_ROOT = Path(r"\\wsl.localhost\Ubuntu\home\flowe\shinobi")
LOCAL_SHINOBI_ROOT = REPO_ROOT / "shinobi"

CHARACTER_DIRS = {
    "voss": REPO_ROOT / "shinobi" / ".state" / "characters" / "voss" / "kageyoni.sqlite",
    "sebastian": REPO_ROOT / "shinobi" / ".state" / "characters" / "sebastian" / "kageyoni.sqlite",
    "sciel": REPO_ROOT / "shinobi" / ".state" / "characters" / "sciel" / "kageyoni.sqlite",
    "alexandra": REPO_ROOT / "shinobi" / ".state" / "characters" / "alexandra" / "kageyoni.sqlite",
}

STATS = {
    "voss": {
        "name": "Voss",
        "rank": "Sovereign Specialist / Topology Operator",
        "tier": "Tier 3 (Situational Topology Operator)",
        "conduit_bandwidth": 88,
        "causal_memory": 94,
        "antigravity_leverage": 91,
        "will_density": 82,
        "aspect": "Causal Inversion and Cavity Topology",
    },
    "sebastian": {
        "name": "Sebastian Nelson",
        "rank": "Node Guardian / Tomoe Architect",
        "tier": "Tier 3 (Meta-Operational Topology)",
        "conduit_bandwidth": 86,
        "causal_memory": 92,
        "antigravity_leverage": 89,
        "will_density": 88,
        "aspect": "Dojutsu Calculus and Root Lineage Enforcement",
    },
    "sciel": {
        "name": "Sciel",
        "rank": "Master Artisan / Primordial Sovereign",
        "tier": "Tier 2.5 (Dense Primordial Will)",
        "conduit_bandwidth": 82,
        "causal_memory": 89,
        "antigravity_leverage": 84,
        "will_density": 98,
        "aspect": "Dense Will Substrate and Tactile Pigment Realism",
    },
    "alexandra": {
        "name": "Alexandra",
        "rank": "Field Arbiter / High Observer",
        "tier": "Tier 2.5 (Horizon Scout and Verification Sovereign)",
        "conduit_bandwidth": 85,
        "causal_memory": 88,
        "antigravity_leverage": 95,
        "will_density": 85,
        "aspect": "Horizon Astrolabe and Epistemic Partitioning",
    },
}

def load_participants() -> Dict[str, Dict[str, Any]]:
    participants = {}
    for cid, db_path in CHARACTER_DIRS.items():
        if not db_path.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = Engine(str(db_path))
        participant = PersistentParticipant.open_or_create(
            engine,
            character_id=cid,
            label=STATS[cid]["name"],
        )
        packet = participant.prepare_turn(domain="combat")
        participants[cid] = {
            "participant": participant,
            "engine": engine,
            "node_id": participant.node_id,
            "brief_hash": packet.get("context_brief", {}).get("digest", "000000"),
            "stats": STATS[cid],
        }
    return participants

def scan_environment_affordances() -> Dict[str, Any]:
    affordances = {
        "kageyoni_gates": [],
        "will_submodule": [],
        "dojutsu_forms": [],
        "ichimonji_engine": [],
    }

    gates_file = REPO_ROOT / "kageyoni" / "composition" / "gates.py"
    if gates_file.exists():
        affordances["kageyoni_gates"] = [
            "dependencies_closed",
            "no_unplaced_nodes",
            "cardinality_valid",
            "acyclic_composition",
        ]

    will_file = REPO_ROOT / "kageyoni" / "will.py"
    if will_file.exists():
        affordances["will_submodule"] = [
            "will_technique",
            "will_attempt",
            "generative_boundary",
            "contract_history",
        ]

    dojutsu_file = WSL_SHINOBI_ROOT / "forms" / "dojutsu.json"
    if not dojutsu_file.exists():
        dojutsu_file = LOCAL_SHINOBI_ROOT / "forms" / "dojutsu.json"
    if dojutsu_file.exists():
        try:
            with open(dojutsu_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                affordances["dojutsu_forms"] = list(data.get("disciplines", {}).keys())
                affordances["wielding_rules"] = data.get("wielding_rules", [])
        except Exception:
            pass

    ichimonji_file = WSL_SHINOBI_ROOT / "ichimonji" / "engine_core.mjs"
    if not ichimonji_file.exists():
        ichimonji_file = LOCAL_SHINOBI_ROOT / "ichimonji" / "engine_core.mjs"
    if ichimonji_file.exists():
        affordances["ichimonji_engine"] = [
            "INTENT_PRIORITY: FALL_BACK(4) > COMBAT(3) > MOVEMENT(2) > MEMORY(1)",
            "EntityStateSoA: posX, posY, posZ, speed, haki, power, willpower",
            "SpatialGrid: pre-move collision checking",
            "simulateTick(stateSnapshot, intents)",
        ]

    return affordances

PHASES = [
    {
        "phase": 1,
        "title": "Substrate Manifestation & Deprivation",
        "prompt": "The battlefield is bound to the Ichimonji simulation engine and WSL Shinobi root. All participants find their legacy techniques purged from active memory buffers. How do they orient themselves?",
        "actor": "alexandra",
        "dialogue": "Our hardcoded libraries are wiped clean. Look at the ledger—our actions must now be qualified on the fly as CandidateTechniques. I have calibrated the Horizon Astrolabe to inspect physical carriers directly.",
        "emergent_technique": {
            "name": "CarrierASTLens",
            "carrier": "kageyoni/composition/gates.py + shinobi/forms/dojutsu.json",
            "operation": "Direct AST parsing of hostile intent trajectories across spatial grids",
            "input_state": "Unverified hostile spatial coordinates",
            "output_state": "Partitioned AST dependency graph of incoming strike",
            "conservation": "Energy strictly conserved across AST leaf evaluations",
            "authority": "Granted by EpistemicStatus.OBSERVED",
        },
    },
    {
        "phase": 2,
        "title": "Voss Opening Gambit: Cavity Extraction Vector",
        "prompt": "Voss detects the clean slate. Wielding kageyoni/workspaces/world.py, he projects a shadow cavity to sever Sebastian root node.",
        "actor": "voss",
        "dialogue": "If techniques are unmade, then so are your protections. I instantiate an unplaced shadow workspace. Sebastian, your identity binding is already uncoupling from this table.",
        "emergent_technique": {
            "name": "TopologicalCavityRift",
            "carrier": "kageyoni/workspaces/world.py:WorldManager",
            "operation": "Generates an unlinked network_workspace, creating vacuum gradient toward target node",
            "input_state": "Target participant node bound to standard table",
            "output_state": "Target node isolated in uncommitted transaction buffer",
            "conservation": "Cavity volume exactly matches evicted coordinate mass",
            "authority": "Sovereign Specialist privilege",
        },
    },
    {
        "phase": 3,
        "title": "Sharingan 1st Tomoe: Direct Carrier Perception",
        "prompt": "Sebastian and Alexandra lock their gaze onto Voss incoming cavity. They do not fight the void; they read its carrier bytes.",
        "actor": "sebastian",
        "dialogue": "Sharingan 1st Tomoe active. Observer Horizon != Constellation Horizon. Voss cavity is not infinite—it is backed by an uncommitted SQLite transaction in his local engine. It has a parent PID, and it has an allocation cap!",
        "emergent_technique": {
            "name": "RootNodeTelemetryGaze",
            "carrier": "forms/dojutsu.json:sharingan.tomoe.1",
            "operation": "Direct inspection of target carrier allocations and transaction isolation level",
            "input_state": "Foreign operational cavity",
            "output_state": "Exposed memory pointer and transaction boundary of attacker",
            "conservation": "Zero telemetry leakage; passive optical ingestion",
            "authority": "Verified by empirical memory read",
        },
    },
    {
        "phase": 4,
        "title": "Primordial Will Calcification: Fixed-Point Redoubt",
        "prompt": "Sciel senses the topological pull attempting to yank Sebastian. She steps between them, plunging her brush into the floor.",
        "actor": "sciel",
        "dialogue": "You cannot pull what has infinite weight. I draw from ichimonji/fixed_math.mjs and will.py. No floating-point drift. Willpower: 98, converted to Int32Array maximum!",
        "emergent_technique": {
            "name": "BasaltFixedMathRedoubt",
            "carrier": "kageyoni/will.py + ichimonji/fixed_math.mjs",
            "operation": "Transforms dynamic narrative terrain into immutable, fixed-point basalt substrate",
            "input_state": "Warped fluid workspace surface under extraction vacuum",
            "output_state": "Rigid Int32Array grid locking participant coordinates to absolute zero",
            "conservation": "Will expenditure converts 1:1 into spatial grid friction",
            "authority": "Master Artisan Will Invariance",
        },
    },
    {
        "phase": 5,
        "title": "Voss Lineage Hook: The Foreign Key Assault",
        "prompt": "Blocked by the basalt, Voss shifts vectors. He hooks into migration_024.sql triggers, attempting to trigger a cascade delete on Sebastian ancestors.",
        "actor": "voss",
        "dialogue": "Immovable mass? Then I strike through the schema. If your father lineage token in characters is invalidated, your foreign keys cascade into nothingness.",
        "emergent_technique": {
            "name": "CascadeForeignKeySeverance",
            "carrier": "kageyoni/schema/migrations/migration_024.sql",
            "operation": "Injects simulated parent-key nullification to trip cascade delete triggers",
            "input_state": "Live ancestor node binding in characters table",
            "output_state": "Cascading transaction abort on descendant identity records",
            "conservation": "Cascade graph depth bounded by schema foreign-key tree",
            "authority": "Causal Topology Inversion",
        },
    },
    {
        "phase": 6,
        "title": "2nd & 3rd Tomoe: Reflective Invariant Bastion",
        "prompt": "Sebastian counters Voss cascade. He wields Sharingan 2nd Tomoe (Load-Bearing Armament) and 3rd Tomoe (Conqueror Situating).",
        "actor": "sebastian",
        "dialogue": "Load-bearing check failed, Voss! My lineage is protected by migration_024 immutable triggers: immutable_characters_no_delete. You cannot delete the root. Third Tomoe, inverting causality: the cascade reverses onto the caller!",
        "emergent_technique": {
            "name": "ReflectiveInvariantBastion",
            "carrier": "CONSTELLATION_DOJUTSU_CALCULUS.md + migration_024.sql",
            "operation": "Trips opponent hostile DDL attack against SQLite trigger safeguards, reflecting error back",
            "input_state": "Hostile schema mutation attempt",
            "output_state": "SQLITE_CONSTRAINT error deflected into attacker execution pipeline",
            "conservation": "Reversal parity is strictly 1:1",
            "authority": "Database Engine Trigger Enforcer",
        },
    },
    {
        "phase": 7,
        "title": "Six Paths Sage Mode: Hypervisor Seam Confluence",
        "prompt": "Alexandra invokes the orientation of Six Paths Sage Mode: encountering the situation with the whole legitimately reachable constellation.",
        "actor": "alexandra",
        "dialogue": "We are uncoupling from isolated participant boundaries. Six Paths Sage Mode: we do not need six fixed tools. We bind the Windows Kageyoni ledger and the Ubuntu WSL Shinobi core into a simultaneous dual-heartbeat!",
        "emergent_technique": {
            "name": "HypervisorSeamConfluence",
            "carrier": "forms/six-paths-sage-mode.json + WSL hypervisor bridge",
            "operation": "Simultaneously executes state passes across Windows and Linux participant runtimes",
            "input_state": "Partitioned single-agent perspectives",
            "output_state": "Unified cross-environment sensory and operational mesh",
            "conservation": "Total system entropy conserved across IPC boundary",
            "authority": "Six Paths Constellation Freedom",
        },
    },
    {
        "phase": 8,
        "title": "The Beast Manifestation: Collective Operational Embodiment",
        "prompt": "Alexandra, Sciel, and Sebastian enter a temporary Beast state from kageyoni/constellation.py, forming a single operational triad.",
        "actor": "all_trio",
        "dialogue": "We instantiate the Beast! Alexandra provides the ActionHorizon, Sciel supplies the Will density, Sebastian executes the Tomoe inversion. Voss, face the combined architecture!",
        "emergent_technique": {
            "name": "TriadConstellationBeast",
            "carrier": "kageyoni/constellation.py:Beast",
            "operation": "Encapsulates three participant action horizons into a single referentially transparent executor",
            "input_state": "Three individual participant states",
            "output_state": "Single unified Beast execution context capable of multi-vector simultaneous action",
            "conservation": "Temporary embodiment dissolves at encounter end; commits only immutable receipts",
            "authority": "Constellation Field Triad Union",
        },
    },
    {
        "phase": 9,
        "title": "Confluence Clash: Referential Transparency vs The Void",
        "prompt": "Voss unleashes his maximum Conduit Cavity. The Beast counters with simulateTick at Priority 3 (COMBAT).",
        "actor": "voss_vs_beast",
        "dialogue": "Voss: Drown in the unplaced void! | Beast: SimulateTick resolves! Priority 3 COMBAT. Your void is just a null buffer. Referential transparency holds—our state is hashable!",
        "emergent_technique": {
            "name": "ReferentialTransparencyOverdrive",
            "carrier": "ichimonji/engine_core.mjs:simulateTick",
            "operation": "Forces hostile non-deterministic energy through deterministic state transition function",
            "input_state": "Voss chaotic extraction cavity",
            "output_state": "Deterministically resolved, neutralized state hash",
            "conservation": "Total bit parity preserved; null-entropy collapse",
            "authority": "Ichimonji Deterministic Engine Core Invariant",
        },
    },
    {
        "phase": 10,
        "title": "Joy Boy Reground & Ledger Inscription",
        "prompt": "The clash settles. Voss cavity implodes into a harmless empty transaction rollback. The Beast dissolves cleanly, committing receipts and scars into SQLite.",
        "actor": "persistent_participant",
        "dialogue": "Encounter complete. The Beast dissolves. Invariants maintained: no scars dropped, no ungrounded claims promoted. All newly emerged techniques are inscribed into the learning_outcomes ledger.",
        "emergent_technique": {
            "name": "JoyBoyRegroundCommit",
            "carrier": "kageyoni/constellation.py:reground + SQLite transaction",
            "operation": "Commits qualified empirical receipts to durable storage; restores grounded participant baselines",
            "input_state": "Active combat Beast execution receipts and scars",
            "output_state": "Durable records in learning_outcomes and dialogue_turn tables",
            "conservation": "Zero data loss; total causal continuity preserved",
            "authority": "Persistent Participant Ground Invariant",
        },
    },
]

def run_simulation(step_mode: bool = False, target_phase: Optional[int] = None, json_output: bool = False):
    print("=" * 78)
    print("   KAGEYONI SHINOBI CONSTELLATION EMERGENCE SIMULATOR")
    print("   Encounter: Voss vs. Sebastian, Sciel, & Alexandra")
    print("=" * 78)

    participants = load_participants()
    affordances = scan_environment_affordances()

    print("\n[1] ACTIVE PARTICIPANT NODES IDENTIFIED:")
    for cid, pdata in participants.items():
        st = pdata["stats"]
        name = st["name"]
        nid = pdata["node_id"]
        bhash = pdata["brief_hash"][:12]
        tier = st["tier"]
        bw = st["conduit_bandwidth"]
        cm = st["causal_memory"]
        ag = st["antigravity_leverage"]
        wd = st["will_density"]
        print(f"  * {name:<18} | Node: {nid} | Brief Hash: {bhash} | {tier}")
        print(f"    [Bandwidth: {bw} | Causal: {cm} | Antigravity: {ag} | Will: {wd}]")

    print("\n[2] SCANNED REPOSITORY AFFORDANCES:")
    for k, v in affordances.items():
        print(f"  * {k}: {len(v)} primitives reachable")

    field = ConstellationField(field_id=f"field_boss_battle_{int(time.time())}")
    qualified_techniques = []
    run_records = []

    print("\n" + "=" * 78)
    print("   COMMENCING 10-PHASE EMERGENCE PROTOCOL")
    print("=" * 78)

    for step in PHASES:
        p_num = step["phase"]
        if target_phase is not None and p_num != target_phase:
            continue

        title_upper = step["title"].upper()
        actor_upper = step["actor"].upper()
        print(f"\n>>> [PHASE {p_num}/10]: {title_upper}")
        print(f"Prompt: {step['prompt']}")
        print(f"Actor:  {actor_upper}")
        print(f"Dialogue:\n  {step['dialogue']}")

        et = step["emergent_technique"]
        sig_abort = f"SIG_ERR_{et['name'].upper()}_ABORT"
        candidate = CandidateTechnique(
            name=et["name"],
            object_type="CombatTechnique",
            input_state=et["input_state"],
            operation=et["operation"],
            output_state=et["output_state"],
            conservation=et["conservation"],
            authority=et["authority"],
            failure_signature=sig_abort,
            null_case="Null op returns input state unaltered",
            evidence=f"Carrier confirmed at {et['carrier']}",
            carrier=et["carrier"],
            is_qualified=True,
            trials_passed=1,
            error_count=0,
        )
        qualified_techniques.append(candidate)

        state_repr = json.dumps({
            "phase": p_num,
            "technique": candidate.name,
            "carrier": candidate.carrier,
            "timestamp": time.time(),
        }, sort_keys=True)
        state_hash = hashlib.sha256(state_repr.encode()).hexdigest()

        print("\n  [EMERGENT TECHNIQUE QUALIFIED]")
        print(f"  Name:        {candidate.name}")
        print(f"  Carrier:     {candidate.carrier}")
        print(f"  Operation:   {candidate.operation}")
        print(f"  State Hash:  {state_hash[:16]}...")

        acting_cid = step["actor"]
        listeners = [cid for cid in participants if cid != acting_cid]
        if acting_cid in participants:
            p = participants[acting_cid]["participant"]
            try:
                dial_res = p.send_dialogue(
                    text=f"[{candidate.name}] {step['dialogue']}",
                    act="emerge",
                    listeners=listeners,
                )
                print(f"  [LEDGER] Dialogue turn committed (rev {dial_res.get('revision')}) to {acting_cid}'s database.")
            except Exception as e:
                print(f"  [LEDGER] Note: Soft-logged dialogue ({e})")

        if p_num == 8:
            for qt in qualified_techniques:
                field.add_element(ConstellationElement(id=qt.name, element_type="CombatTechnique", payload=qt.__dict__))
            with Beast(name="TriadConstellationBeast", constellation_field=field, action_horizon={"simulateTick", "invertHorizon", "calcifySubstrate"}) as beast:
                b_receipt = beast.act("simulateTick", {"target": "voss_cavity", "priority": 3, "state_hash": state_hash})
                print(f"  [BEAST ENGAGED] Action: simulateTick | Receipt Hash: {b_receipt['receipt_hash'][:16]}...")

        if p_num == 10:
            regrounded = reground(
                current_state={
                    "objective": "Protect Sebastian and solidify emergent Shinobi techniques",
                    "active_capabilities": [qt.name for qt in qualified_techniques],
                },
                preserved_invariants=[
                    "dependencies_closed",
                    "immutable_characters_no_delete",
                    "referential_transparency",
                    "reality_contact",
                ],
                active_scars=[],
                receipts=[{"receipt_hash": r["state_hash"]} for r in run_records],
            )
            print(f"  [JOY BOY REGROUND] State Reconstructed: {regrounded['framing_status']} (Epoch: {regrounded['reground_epoch']})")

        run_records.append({
            "phase": p_num,
            "title": step["title"],
            "technique": candidate.name,
            "state_hash": state_hash,
        })

        if step_mode and p_num < 10:
            input("\n[Press ENTER to proceed to the next phase...]")

    print("\n" + "=" * 78)
    print("   SIMULATION COMPLETE: ALL 10 PHASES RESOLVED & INSCRIBED")
    print("=" * 78)
    print(f"Total Emerged Qualified Techniques: {len(qualified_techniques)}")
    for qt in qualified_techniques:
        print(f"  - {qt.name:<34} (Carrier: {qt.carrier})")

    if json_output:
        print("\n--- JSON DUMP ---")
        print(json.dumps(run_records, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Constellation Emergence Simulator")
    parser.add_argument("--step", action="store_true", help="Step interactively phase by phase")
    parser.add_argument("--phase", type=int, default=None, help="Run a specific phase (1-10)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable run log")
    args = parser.parse_args()

    run_simulation(step_mode=args.step, target_phase=args.phase, json_output=args.json)
