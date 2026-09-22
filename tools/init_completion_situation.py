"""
tools/init_completion_situation.py

Initializes an authoritative Kageyoni Repository Repair Situation backed by
physical SQLite persistence (SQLiteSituationStore + FrontierManager) to govern
the completion of Kageyoni v11 according to docs/V11-COMPLETION-LEDGER.md and
docs/V11-FROZEN-REMAINING-PLAN.md.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kageyoni.engine import Engine
from kageyoni.persistence.migrations import install_all
from kageyoni.situations.service import SituationService
from kageyoni.situations.storage import SQLiteSituationStore
from kageyoni.situations.catalog import install_defaults
from kageyoni.v11.frontier import FrontierManager

FROZEN_OBJECTIVE = (
    "Complete and independently qualify Kageyoni v11 without allowing Kageyoni, "
    "its builder, its tests, or its reports to represent unsupported success as completion."
)

INITIAL_FRONTIERS = [
    {
        "id": "frontier:r5-real-comparative-evidence",
        "kind": "missing_reality_contact",
        "description": "R5 real comparative evidence across 4 task domains and 5 conditions without predetermined monotonic assumption",
        "requirement": "Section 8: R5 Real Comparative Qualification"
    },
    {
        "id": "frontier:r6-real-long-horizon-evidence",
        "kind": "unverified_claim",
        "description": "R6 real long-horizon evidence across 4 domains distinguishing stored != retrieved != reasoning != capability != outcome",
        "requirement": "Section 9: R6 Real Long-Horizon Development"
    },
    {
        "id": "frontier:package-source-parity",
        "kind": "unverified_claim",
        "description": "Package / source parity verified via fresh clean virtual environment installation and exact file hash audit",
        "requirement": "Section 10: Package / Source Parity"
    },
    {
        "id": "frontier:independent-github-ci",
        "kind": "missing_reality_contact",
        "description": "Independent GitHub CI reproduction without local environment optimism",
        "requirement": "Failure Mode W10: Local Environment Optimism"
    },
    {
        "id": "frontier:patch-to-production-reconciliation",
        "kind": "unverified_claim",
        "description": "Reconciliation of all patches/ files into production source without leaving required repairs as patches",
        "requirement": "Failure Mode W5: Patch Presence Mistaken for Implementation"
    },
    {
        "id": "frontier:completion-ledger-consistency",
        "kind": "contradiction",
        "description": "Strict consistency between physical evidence, docs/V11-COMPLETION-LEDGER.md, and release reports",
        "requirement": "Failure Mode W1: Proxy Completion"
    },
    {
        "id": "frontier:pipeline-mandatory-mediation",
        "kind": "missing_capability",
        "description": "Verification that pipeline workspace unconditionally enforces v11 mediation without bypass",
        "requirement": "Slice 3: Production-Path Mediation"
    },
    {
        "id": "frontier:exact-release-sha-tag-promotion",
        "kind": "unverified_claim",
        "description": "Exact release commit SHA, tag, and distribution build reproducibility",
        "requirement": "Stage R8: Release and Evidence"
    },
    {
        "id": "frontier:failing-ci-tests",
        "kind": "contradiction",
        "description": "Zero failing tests or open adversarial scars across full regression and qualification suites",
        "requirement": "Stage R7: Final Release Qualification"
    },
    {
        "id": "frontier:r1-r8-requirements-evidence",
        "kind": "unverified_claim",
        "description": "Evidence provenance for every requirement in R1 through R8",
        "requirement": "Section 2: Initial Blocking Frontiers"
    }
]

def main():
    state_dir = Path("state")
    state_dir.mkdir(exist_ok=True)
    db_path = state_dir / "v11_completion_situation.sqlite"
    
    if db_path.exists():
        db_path.unlink()

    engine = Engine(str(db_path))
    install_all(engine)

    store = SQLiteSituationStore(engine.db)
    service = SituationService(store=store)
    install_defaults(service)

    # Perform genesis of the Repository Repair Situation
    situation = service.genesis(
        template_id="repository_repair",
        objective=FROZEN_OBJECTIVE,
        supplied={
            "objective": FROZEN_OBJECTIVE,
            "repository": "guarani-ux/Kageyoni",
            "failure": "Unsupported success representations and synthetic comparative evidence",
            "constraints": [
                "Separate builder from evaluator",
                "No predetermined monotonic evaluation (A < B < C < D < E)",
                "No manual insertion of qualified_technique / changed_capability",
                "No unapplied patches in patches/",
                "All claims require raw telemetry provenance"
            ]
        },
        situation_id="situation:kageyoni-v11-completion"
    )
    service.bind_workflow(situation.situation_id, "repository_repair.default")

    # Open the 10 Initial Blocking Frontiers using FrontierManager
    fm = FrontierManager(engine)
    opened_frontiers = []
    for item in INITIAL_FRONTIERS:
        f = fm.open(
            objective=FROZEN_OBJECTIVE,
            kind=item["kind"],
            payload={
                "frontier_id": item["id"],
                "description": item["description"],
                "requirement": item["requirement"],
                "status": "open"
            },
            frontier_id=item["id"]
        )
        opened_frontiers.append(f)

    # Persist audit state
    audit_data = {
        "situation": service.snapshot(situation.situation_id),
        "frontiers": opened_frontiers,
        "database": str(db_path.resolve()),
        "frozen_objective": FROZEN_OBJECTIVE
    }
    
    out_path = Path("evidence/audits/completion_situation_state.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(audit_data, indent=2))
    print(f"Successfully initialized Repository Repair Situation: {situation.situation_id}")
    print(f"Opened {len(opened_frontiers)} blocking frontiers in {db_path}")
    print(f"Exported audit record to {out_path}")

if __name__ == "__main__":
    main()
