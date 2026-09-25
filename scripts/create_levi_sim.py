"""
Instantiate the Levi Sim entity in Kageyoni.

Encodes the operational capabilities, behavioral tensions, and Will contracts
documented in the 'Levi — Working Human Model (v0.1)'.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure local kageyoni package is prioritized on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.engine import Engine, Rejected, require
from kageyoni.workflows import Workflows
from kageyoni.will import validate_contract

EVIDENCE_NOTE = "Extracted from Levi — Working Human Model (v0.1)."



def build_aspects(character_id: str) -> list[dict[str, Any]]:
    """Generate the aspect records representing Levi's cognitive operating model."""
    raw_aspects = [
        # --- INTERIORITY ---
        {
            "id": f"{character_id}.drive.preserve_intent",
            "section": "interiority",
            "kind": "drive",
            "statement": "Preserve core intent; treat mechanisms, terminology, and tooling as volatile.",
        },
        {
            "id": f"{character_id}.drive.upstream_variables",
            "section": "interiority",
            "kind": "drive",
            "statement": "Move upstream to the representation that generated the problem; expose hidden dependencies before committing downstream.",
        },
        {
            "id": f"{character_id}.boundary.reject_false_closure",
            "section": "interiority",
            "kind": "boundary",
            "statement": "Refuse premature closure; reject claims of completion without demonstrated physical counterexample resistance.",
        },
        {
            "id": f"{character_id}.boundary.epistemic_integrity",
            "section": "interiority",
            "kind": "boundary",
            "statement": "Reject silent substitution of missing requirements or data with convenient inference; represent deficits explicitly.",
        },
        {
            "id": f"{character_id}.conflict.prep_vs_contact",
            "section": "interiority",
            "kind": "conflict",
            "statement": "Tension between accumulating reusable infrastructure (preparation) and direct experiential friction (contact).",
        },
        {
            "id": f"{character_id}.conflict.control_vs_agency",
            "section": "interiority",
            "kind": "conflict",
            "statement": "Tension between maintaining systemic integrity/invariants and allowing independent agency to external entities.",
        },
        # --- PORTRAYAL ---
        {
            "id": f"{character_id}.thinking_style.upstream",
            "section": "portrayal",
            "kind": "thinking_style",
            "statement": "Upstream reframing: seeks representations where one intervention transforms multiple downstream outcomes.",
        },
        {
            "id": f"{character_id}.attention_style.affordance",
            "section": "portrayal",
            "kind": "attention_style",
            "statement": "Affordance-oriented: perceives physical structures, rules, and constraints as navigable surfaces and leverage.",
        },
        {
            "id": f"{character_id}.mannerism.adversarial_gate",
            "section": "portrayal",
            "kind": "mannerism",
            "statement": "Inspects consequences before acknowledging closure; demands falsification tests.",
        },
        # --- CONDITION ---
        {
            "id": f"{character_id}.condition.vigilant",
            "section": "condition",
            "kind": "emotion",
            "statement": "Composed, vigilant against unverified assumptions and premature consensus.",
        },
    ]

    aspects = []
    for item in raw_aspects:
        aspects.append({
            "id": item["id"],
            "visibility": "public",
            "evidence": [{"note": f"Aspect extracted from Levi Working Human Model (v0.1): {item['statement']}"}],
            "data": {
                "character": character_id,
                "section": item["section"],
                "kind": item["kind"],
                "value_status": "known",
                "statement": item["statement"],
                "phase": "active",
                "change_basis": "established",
            },
        })
    return aspects



def build_will_contracts(character_id: str) -> tuple[dict, dict, list[dict]]:
    """Build the validated Will contracts for the Levi Sim."""
    # 1. Will Definition
    definition = {
        "schema_version": "will-contract/0.1",
        "id": "will_def_levi_operator",
        "version": 1,
        "design_status": "accepted",
        "evidence": [{"source": "levi_human_model_v01", "assertion": "Working Human Model documentation", "status": "confirmed"}],
        "name": "Upstream Capability Construction",
        "classification": "independent",
        "nature": "structural_orchestration",
        "ancestry": [],
        "generative_boundary": "Cannot manufacture physical authority without external verification gates.",
        "inherent_limits": [
            "Vulnerable to recursive verification paralysis",
            "Requires external tools or agents to execute downstream syntax",
        ],
        "invariants": [
            {
                "id": "inv_falsification_gate",
                "mode": "judgment",
                "rule": None,
                "statement": "Must test candidate solutions under conditions capable of failing.",
                "missing_policy": "request_judgment",
            },
        ],
    }

    # 2. Will Expression
    expression = {
        "schema_version": "will-contract/0.1",
        "id": "will_expr_levi_operator",
        "version": 1,
        "design_status": "accepted",
        "evidence": [{"source": "levi_human_model_v01", "assertion": "Expression bound to Levi Sim", "status": "confirmed"}],
        "definition": {"id": "will_def_levi_operator", "version": 1},
        "bearer": character_id,
        "legacy_will_id": None,
        "interpretation": "Affordance-driven capability orchestrator",
        "channels": ["structural_clarity", "focus"],
        "stat_bindings": [],
        "learned_techniques": [
            {"id": "technique_upstream_reframing", "version": 1},
            {"id": "technique_constraint_economics", "version": 1},
        ],
        "conditions": ["Active cognitive awareness"],
        "awakening_access": "latent",
        "awakening_mastery": "unknown",
        "awakening_definition": None,
    }

    trigger_cond = {
        "id": "trigger_choice_friction",
        "mode": "judgment",
        "rule": None,
        "statement": "Encounter presents brittle, false binary, or artificial deadlock.",
        "missing_policy": "request_judgment",
    }

    channel_spec = {
        "medium": "structural_clarity",
        "access": trigger_cond,
        "break_conditions": [],
    }

    # 3. Techniques
    t1 = {
        "schema_version": "will-contract/0.1",
        "id": "technique_upstream_reframing",
        "version": 1,
        "design_status": "accepted",
        "evidence": [{"source": "levi_human_model_v01", "assertion": "Reframing technique", "status": "confirmed"}],
        "expression": {"id": "will_expr_levi_operator", "version": 1},
        "name": "Upstream Reframing",
        "derivation": "Cognitive OS Axiom 1: Re-encode problem geometry.",
        "practice_status": "demonstrated",
        "activation": "deliberate",
        "trigger": trigger_cond,
        "channels": [channel_spec],
        "effects": [
            {
                "operation": "reveal",
                "target_role": "environment",
                "mechanism": "Coordinate space transformation",
                "preconditions": [],
                "scope": {"target_kinds": ["situation", "scene"], "range": None, "area": None, "duration": None, "unknowns": []},
                "inputs": [],
                "resolver": None,
                "authority": "gm_judgment",
                "resistance": [],
                "postconditions": [],
            }
        ],
        "costs": [],
        "resolution_policy": {"id": "rule-reframing-policy", "version": 1},
        "termination": [],
    }

    t2 = {
        "schema_version": "will-contract/0.1",
        "id": "technique_constraint_economics",
        "version": 1,
        "design_status": "accepted",
        "evidence": [{"source": "levi_human_model_v01", "assertion": "Constraint economics technique", "status": "confirmed"}],
        "expression": {"id": "will_expr_levi_operator", "version": 1},
        "name": "Constraint Economics",
        "derivation": "Treat constraints as material surfaces for traction.",
        "practice_status": "demonstrated",
        "activation": "deliberate",
        "trigger": trigger_cond,
        "channels": [channel_spec],
        "effects": [
            {
                "operation": "connect",
                "target_role": "constraint",
                "mechanism": "Affordance extraction",
                "preconditions": [],
                "scope": {"target_kinds": ["world_rule", "boundary"], "range": None, "area": None, "duration": None, "unknowns": []},
                "inputs": [],
                "resolver": None,
                "authority": "gm_judgment",
                "resistance": [],
                "postconditions": [],
            }
        ],
        "costs": [],
        "resolution_policy": {"id": "rule-reframing-policy", "version": 1},
        "termination": [],
    }

    # Validate all contracts locally first
    validate_contract("will_definition", definition, "will_def_levi_operator", 1)
    validate_contract("will_expression", expression, "will_expr_levi_operator", 1)
    validate_contract("will_technique", t1, "technique_upstream_reframing", 1)
    validate_contract("will_technique", t2, "technique_constraint_economics", 1)

    return definition, expression, [t1, t2]


def create_levi_sim(engine: Engine, branch: str = "main", character_id: str = "levi-sim") -> dict[str, Any]:
    """Register the complete Levi Sim entity and contracts in Kageyoni."""
    wf = Workflows(engine)

    # 1. Register Supporting Rule Definition for Resolution Policy
    engine.add_rule(
        "rule-reframing-policy",
        1,
        "Reframing Policy: permits exposing latent affordances when upstream intent is preserved.",
        [],
        [],
        True,
        {"kind": "contextual", "outcome": True},
    )

    # 2. Build Aspect Records
    aspects = build_aspects(character_id)

    # 3. Create Character using Character Workflow
    rev = engine.branch(branch)["revision"]
    receipt_char = wf.character_create(
        branch=branch,
        request_id=f"create-{character_id}",
        expected_revision=rev,
        actor="system",
        narrative=f"Instantiating {character_id} from Levi — Working Human Model (v0.1).",
        character_id=character_id,
        label="Levi Sim",
        canonical_name="Levi",
        existence="established",
        name_status="known",
        continuity="established",
        entity_kind="person",
        visibility="public",
        evidence=[{"note": EVIDENCE_NOTE}],
        aspects=aspects,
    )

    # 4. Build and Register Will Contracts
    will_def, will_expr, techniques = build_will_contracts(character_id)

    contract_changes = [
        {
            "op": "create",
            "domain": "will_definition",
            "id": will_def["id"],
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": EVIDENCE_NOTE}],
            "data": {"name": will_def["name"], "classification": will_def["classification"], "contract": will_def},
        },
        {
            "op": "create",
            "domain": "will_expression",
            "id": will_expr["id"],
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": EVIDENCE_NOTE}],
            "data": {
                "definition": will_def["id"],
                "bearer": character_id,
                "contract": will_expr,
            },
        },

    ]

    for t in techniques:
        contract_changes.append({
            "op": "create",
            "domain": "will_technique",
            "id": t["id"],
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": EVIDENCE_NOTE}],
            "data": {
                "expression": will_expr["id"],
                "name": t["name"],
                "contract": t,
            },
        })



    rev = engine.branch(branch)["revision"]
    receipt_will = engine.apply({
        "api_version": 3,
        "branch": branch,
        "expected_revision": rev,
        "request_id": f"bind-will-{character_id}",
        "kind": "action",
        "actor": "system",
        "narrative": f"Binding Will capability contracts to {character_id}.",
        "changes": contract_changes,
    })

    # Read back character to verify
    summary = wf.character_read(branch=branch, character_id=character_id)

    return {
        "character_receipt": receipt_char,
        "will_receipt": receipt_will,
        "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Instantiate Levi Sim in Kageyoni.")
    parser.add_argument("--db", default="state/levi_sim_world.sqlite", help="Path to SQLite world database.")
    parser.add_argument("--branch", default="main", help="Target branch.")
    parser.add_argument("--id", default="levi-sim", help="Character ID.")
    args = parser.parse_args()

    db_path = Path(args.db)
    print(f"[*] Initializing Kageyoni Engine at: {db_path.resolve()}")
    engine = Engine(db_path)
    try:
        result = create_levi_sim(engine, branch=args.branch, character_id=args.id)
        char = result["summary"]["character"]
        linked = result["summary"]["linked_records"]
        print(f"[+] Levi Sim successfully created! ID: '{char['id']}', Revision: {result['summary']['revision']}")
        print(f"[+] Registered Aspects: {len(linked)} records")
        for r in linked:
            if r["domain"] == "character_aspect":
                print(f"    - [{r['data']['section'].upper()}/{r['data']['kind']}] {r['data']['statement']}")
        print(f"[+] Character Event Hash: {result['character_receipt']['event_hash'][:16]}...")
        print(f"[+] Will Contract Event Hash: {result['will_receipt']['event_hash'][:16]}...")

    finally:
        engine.close()


if __name__ == "__main__":
    main()
