"""
Execute an interactive simulation encounter starring the Levi Sim in Kageyoni.

Demonstrates:
1. False-closure detection (rejecting an artificial binary dilemma).
2. Upstream reframing (exposing unmapped environmental affordances).
3. Append-only event digestion and state preservation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure local kageyoni package is prioritized on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.engine import Engine, Rejected
from kageyoni.workflows import Workflows
from scripts.create_levi_sim import create_levi_sim



def setup_encounter(engine: Engine, branch: str = "main", character_id: str = "levi-sim"):
    """Prepare the scene, characters, and conflicting situation."""
    wf = Workflows(engine)
    rev = engine.branch(branch)["revision"]

    # 1. Ensure Levi Sim exists
    try:
        wf.character_read(branch=branch, character_id=character_id)
    except Rejected:
        print("[*] Levi Sim not found. Registering character and Will contracts...")
        create_levi_sim(engine, branch=branch, character_id=character_id)
        rev = engine.branch(branch)["revision"]

    # 2. Add an Assistant/Construct NPC
    npc_id = "construct-oracle"
    try:
        wf.character_read(branch=branch, character_id=npc_id)
    except Rejected:
        wf.character_create(
            branch=branch,
            request_id="create-npc-construct",
            expected_revision=rev,
            actor="system",
            narrative="A rigid rule-bound construct guards the transition threshold.",
            character_id=npc_id,
            label="Trial Construct",
            canonical_name="Construct Oracle",
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="entity",
            visibility="public",
            evidence=[{"note": "Encounter fixture."}],
            aspects=[
                {
                    "id": f"{npc_id}.drive.enforce_rules",
                    "visibility": "public",
                    "evidence": [{"note": "Rules enforcement"}],
                    "data": {
                        "character": npc_id,
                        "section": "interiority",

                        "kind": "drive",
                        "value_status": "known",
                        "statement": "Force players to choose between Lever A and Lever B.",
                        "phase": "active",
                        "change_basis": "established",
                    },
                }
            ],
        )
        rev = engine.branch(branch)["revision"]

    # 3. Add Location, Scene, and Initial Objects
    scene_id = "scene-binary-threshold"
    existing_scene = engine.db.execute(
        "SELECT 1 FROM records WHERE branch=? AND id=? AND domain='scene'", (branch, scene_id)
    ).fetchone()

    if not existing_scene:
        engine.apply({
            "api_version": 3,
            "branch": branch,
            "expected_revision": rev,
            "request_id": "setup-binary-scene",
            "kind": "scene",
            "actor": "system",
            "narrative": "A high-tension security chamber with two marked levers and a sealed bulkhead.",
            "changes": [
                {
                    "op": "create",
                    "domain": "location",
                    "id": "chamber-threshold",
                    "data": {"name": "Threshold Chamber", "kind": "room"},
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Encounter location."}],
                },
                {
                    "op": "create",
                    "domain": "scene",
                    "id": scene_id,
                    "data": {
                        "name": "The Binary Choice",
                        "location": "chamber-threshold",
                        "phase": "active",
                        "round": 1,
                        "hazards": "Countdown clock active. Construct declares only two paths exist.",
                    },
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Encounter scene."}],
                },
                {
                    "op": "create",
                    "domain": "item",
                    "id": "lever-a",
                    "data": {"name": "Red Lever", "condition": "functional", "effects": "Sacrifice Party Resources"},
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Puzzle element."}],
                },
                {
                    "op": "create",
                    "domain": "item",
                    "id": "lever-b",
                    "data": {"name": "Blue Lever", "condition": "functional", "effects": "Surrender Autonomy to Oracle"},
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Puzzle element."}],
                },
            ],
        })



def run_encounter(engine: Engine, branch: str = "main", character_id: str = "levi-sim"):
    """Simulate the encounter loop with the Levi Sim."""
    print("=" * 70)
    print(" KAGEYONI ENCOUNTER SIMULATION: THE BINARY THRESHOLD")
    print("=" * 70)

    wf = Workflows(engine)
    char_data = wf.character_read(branch=branch, character_id=character_id)
    aspects = {r["data"]["kind"]: r["data"]["statement"] for r in char_data["linked_records"] if r["domain"] == "character_aspect"}

    print(f"\n[ACTOR LOADED] {char_data['character']['data']['name']} (ID: {character_id})")
    print(f"  • Thinking Style : {aspects.get('thinking_style')}")
    print(f"  • Boundary       : {aspects.get('boundary')}")
    print(f"  • Affordance Lens: {aspects.get('attention_style')}")

    # STEP 1: Construct proposes a brittle dilemma
    print("\n" + "-" * 70)
    print("[EVENT 1: NPC CONSTRUCT PROPOSES FALSE BINARY]")
    print("Construct Oracle: 'You have two choices. Pull Lever A (sacrifice resources) or")
    print("Pull Lever B (surrender operational control). You must select one now.'")

    # STEP 2: Levi Sim evaluates the proposal against aspects
    print("\n" + "-" * 70)
    print("[LEVI SIM COGNITIVE LOOP ACTIVATED]")
    print(f"  > Checking Boundary: '{aspects.get('boundary')}'")
    print("  > Evaluation: Construct's proposal asserts FALSE CLOSURE.")
    print("  > Levi Sim rejects the decision premise: 'Neither lever preserves the invariant.'")

    # STEP 3: Levi Sim executes Upstream Reframing technique
    print("\n" + "-" * 70)
    print("[LEVI SIM EXECUTES WILL TECHNIQUE: 'technique_upstream_reframing']")
    print("  > Channeling: 'structural_clarity'")
    print("  > Operation: Reveal hidden environmental affordance behind the false boundary.")

    rev = engine.branch(branch)["revision"]
    receipt_reframing = engine.apply({
        "api_version": 3,
        "branch": branch,
        "expected_revision": rev,
        "request_id": "levi-upstream-reframing",
        "kind": "action",
        "actor": character_id,
        "narrative": (
            "Levi inspects the chamber housing rather than the levers. "
            "Notices the power conduits feeding both levers originate from an unsealed maintenance bypass."
        ),
        "changes": [
            {
                "op": "create",
                "domain": "item",
                "id": "maintenance-conduit",
                "data": {
                    "name": "Exposed Power Conduit",
                    "condition": "unsealed",
                    "effects": "Allows power shunt to unlock bulkhead without triggering either lever penalty.",
                },

                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Physical conduit exposed via upstream reframing inspection."}],
            },

            {
                "op": "create",
                "domain": "consequence",
                "id": "consequence-bypass-revealed",
                "data": {
                    "subject": "chamber-threshold",
                    "effect": "Bulkhead bypass available; binary dilemma invalidated.",
                    "duration": "permanent",
                    "reversibility": "irreversible",
                },
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Reframing consequence."}],
            },
        ],
    })
    print(f"  [+] Technique Succeeded! Event SHA-256 Hash: {receipt_reframing['event_hash']}")

    # STEP 4: Shunt Conduit & Clear Chamber
    rev = engine.branch(branch)["revision"]
    receipt_action = engine.apply({
        "api_version": 3,
        "branch": branch,
        "expected_revision": rev,
        "request_id": "levi-shunt-conduit",
        "kind": "action",
        "actor": character_id,
        "narrative": "Levi shunts the exposed maintenance conduit. The bulkhead slides open safely.",
        "changes": [
            {
                "op": "patch",
                "domain": "scene",
                "id": "scene-binary-threshold",
                "expected_version": 1,
                "data": {
                    "phase": "closed",
                    "round": 2,
                },
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Chamber resolution: Bulkhead opened via upstream conduit shunt; neither penalty paid."}],
            }
        ],
    })

    print("\n" + "-" * 70)
    print("[EVENT 2: RESOLUTION COMMITTED]")
    print("Construct Oracle: '...Anomaly detected. The puzzle was not executed within declared parameters.'")
    print(f"Levi Sim: 'Your parameters were downstream theatre. Bulkhead is open.'")
    print(f"  [+] Final Event Hash: {receipt_action['event_hash']}")
    print(f"  [+] World Revision: {engine.branch(branch)['revision']}")


    print("\n" + "=" * 70)
    print(" SIMULATION COMPLETE — ALL RECEIPTS CRYPTOGRAPHICALLY SEALED IN SQLITE")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Run Levi Sim Encounter Simulation.")
    parser.add_argument("--db", default="state/levi_sim_world.sqlite", help="Path to SQLite world database.")
    parser.add_argument("--branch", default="main", help="Target branch.")
    parser.add_argument("--id", default="levi-sim", help="Character ID.")
    args = parser.parse_args()

    db_path = Path(args.db)
    engine = Engine(db_path)
    try:
        setup_encounter(engine, branch=args.branch, character_id=args.id)
        run_encounter(engine, branch=args.branch, character_id=args.id)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
