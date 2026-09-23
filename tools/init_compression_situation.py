"""
tools/init_compression_situation.py

Initializes an authoritative Kageyoni Repository Repair Situation backed by
physical SQLite persistence (SQLiteSituationStore + FrontierManager) to govern
the execution of the Kageyoni Capability-Preserving Compression Build Plan.
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
    "Reduce duplicated rules, competing sources of truth, unnecessary interfaces, "
    "and the number of places an AI must understand or edit to make one correct change, "
    "while preserving Kageyoni's demonstrated capabilities, meaningful distinctions, "
    "world continuity, public entry points, recovery behavior, and evidence history."
)

INITIAL_FRONTIERS = [
    {
        "id": "frontier:cp00-baseline-reproducibility",
        "kind": "missing_reality_contact",
        "description": "Clean-checkout inherited and relevant mechanical tests reproduce on CI without developer-local files.",
        "requirement": "CP-00: Recover and make the baseline reproducible",
    },
    {
        "id": "frontier:cp01-responsibility-mapping",
        "kind": "unverified_claim",
        "description": "Map capabilities to public entry points, surviving owners, tests, and retirement conditions.",
        "requirement": "CP-01: Map responsibilities and choose survivors",
    },
    {
        "id": "frontier:cp02-compression-test-surface",
        "kind": "missing_capability",
        "description": "Comparison surface auditing gate runners, test discovery, and paired old/new isolated runs.",
        "requirement": "CP-02: Establish the compression test surface",
    },
    {
        "id": "frontier:cp03-epistemic-claim-consolidation",
        "kind": "contradiction",
        "description": "Consolidate EpistemicLedger and ClaimGraph policy ownership and validation.",
        "requirement": "CP-03: Consolidate claim representation and policy",
    },
    {
        "id": "frontier:cp04-transaction-persistence-consolidation",
        "kind": "missing_capability",
        "description": "Consolidate transaction and persistence ownership using UnitOfWork without new storage framework.",
        "requirement": "CP-04: Consolidate transaction and persistence ownership",
    },
    {
        "id": "frontier:cp05-evidence-validation-unification",
        "kind": "contradiction",
        "description": "Unify repeated identity, scope, revision, receipt and result checks while preserving distinct lifecycles.",
        "requirement": "CP-05: Share evidence validation, preserve distinct lifecycles",
    },
    {
        "id": "frontier:cp06-dependency-traversal-unification",
        "kind": "contradiction",
        "description": "Replace serialized text matching with exact typed dependency references and unified cycle handling.",
        "requirement": "CP-06: Consolidate dependency traversal and invalidation",
    },
    {
        "id": "frontier:cp07-memory-learning-transfer-unification",
        "kind": "contradiction",
        "description": "Route applicability, learning, and transfer through authoritative services instead of caller booleans.",
        "requirement": "CP-07: Unify applicability, learning and transfer access",
    },
    {
        "id": "frontier:cp08-caller-interface-simplification",
        "kind": "missing_capability",
        "description": "Simplify caller operations across all 6 Situation families with fewer independent rules.",
        "requirement": "CP-08: Simplify domain compositions and caller interfaces",
    },
    {
        "id": "frontier:cp09-duplicate-retirement",
        "kind": "unverified_claim",
        "description": "Retire superseded implementations with verified retirement ledger and backward-compatibility adapters.",
        "requirement": "CP-09: Retire duplicates and compress instructions",
    },
    {
        "id": "frontier:cp10-qualification-and-integration",
        "kind": "unverified_claim",
        "description": "Final compression qualification across all suites, targeted mutations, and clean package installation.",
        "requirement": "CP-10: Qualify compression and integrate",
    },
]

INITIAL_SCARS = [
    {
        "id": "scar:ci-missing-fixture-35923033946",
        "description": "GitHub Actions run 35923033946 failed during inherited regression due to missing build/personality-fixture.sqlite in clean checkout.",
        "target": "tests/test_foundation.py",
    },
    {
        "id": "scar:epistemic-policy-duplication",
        "description": "EpistemicLedger and ClaimGraph maintain separate transition rules and keyword-based validation.",
        "target": "contracts/epistemic_ledger.py",
    },
    {
        "id": "scar:gate-runner-key-overwrite",
        "description": "GateRunner creates separate SQLite connection/schema and overwrites records keyed only by gate ID without execution attempt history.",
        "target": "kageyoni/gate_runner.py",
    },
    {
        "id": "scar:invalidation-text-matching",
        "description": "Invalidation traverses claims separately, searches serialized text for IDs, and suppresses database exceptions.",
        "target": "kageyoni/research_compiler/invalidation_engine.py",
    },
    {
        "id": "scar:memory-transfer-caller-enforcement",
        "description": "Situation memory and transfer rely on caller-supplied booleans and caller-maintained revocation sets.",
        "target": "kageyoni/situations/memory.py",
    },
]


def main():
    root = Path(__file__).resolve().parent.parent
    state_dir = root / "state"
    state_dir.mkdir(exist_ok=True)
    db_path = state_dir / "compression_situation.sqlite"

    if db_path.exists():
        db_path.unlink()

    print(f"[Init Compression Situation] Creating isolated database: {db_path}")
    engine = Engine(db_path)
    install_all(engine)

    # Initialize Situation store and install defaults
    store = SQLiteSituationStore(engine.db)
    service = SituationService(store)
    install_defaults(service)

    # Create the Repository Repair Situation
    situation_id = "situation:kageyoni-capability-compression"
    print(f"[Init Compression Situation] Creating Situation: {situation_id}")
    sit = service.genesis(
        template_id="repository_repair",
        objective=FROZEN_OBJECTIVE,
        supplied={
            "objective": FROZEN_OBJECTIVE,
            "repository": "guarani-ux/Kageyoni",
            "branch": "refactor/capability-compression",
            "baseline_sha": "24e16c5b3321681022ff9bfcc42932f50f48fde1",
        },
        situation_id=situation_id,
    )
    service.bind_workflow(sit.situation_id, "repository_repair.default")

    # Initialize FrontierManager
    fm = FrontierManager(engine)
    print(f"[Init Compression Situation] Registering {len(INITIAL_FRONTIERS)} Frontiers...")
    for f in INITIAL_FRONTIERS:
        fm.open(
            objective=f["description"],
            kind=f["kind"],
            payload={
                "frontier_id": f["id"],
                "description": f["description"],
                "requirement": f["requirement"],
                "status": "open",
            },
            frontier_id=f["id"],
        )

    # Record initial Scars in the Situation store
    print(f"[Init Compression Situation] Registering {len(INITIAL_SCARS)} Scars...")
    for scar in INITIAL_SCARS:
        store.put(
            "scar",
            scar["id"],
            {
                "scar_id": scar["id"],
                "description": scar["description"],
                "target": scar["target"],
                "status": "reproduced_or_identified",
                "evidence_refs": [scar["target"]],
            },
        )

    engine.close()
    print("[Init Compression Situation] Repository Repair Situation successfully initialized.")


if __name__ == "__main__":
    main()
