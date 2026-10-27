"""
6-Condition Factorial Cognition & Adaptation Trial Substrate.

Design:
- 3 History Levels: Relevant (recovered), Irrelevant (replacement), Absent (clean).
- 2 Environments: Grounded Subterranean, Aerial Magnetic Rift.
- 6 Total Cells x 3 Repetitions = 18 Trials, run in randomized order.
- Complete context isolation: Each run uses an isolated SQLite sandbox.
- Constant identity & permissions for Sciel across all cells.
- Evaluates:
  1. Prepared requests (raw JSON + SHA256)
  2. Actual model cognitive turns (unprescribed choices)
  3. Validated proposals (conforming to protocol schema)
  4. Committed simulated state mutations
  5. Completed successor turns (Maki observing result without meta-labels)
"""

from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sqlite3
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.persistence.migrations import install_shinobi, install_encounters
from kageyoni.workspaces.world import Encounters
try:
    from shinobi import Participant, encode
except ImportError:
    from shinobi.shinobi import Participant, encode

BASE_DIR = Path(__file__).resolve().parents[2]
CAUSAL_RUNS_DIR = BASE_DIR / "shinobi" / ".state" / "causal_runs"

# =========================================================================
# 1. FROZEN PASSAGES (Length and structure matched)
# =========================================================================
# RELEVANT PASSAGES: Extracted verbatim from Sciel's historical SQLite database
RELEVANT_PASSAGES = [
    {
        "id": "turn:sciel:hist_seam_01",
        "provenance": "recovered_history",
        "speaker": "sciel",
        "text": "The Twilight aspect stirs, and the core holds its density. Sebastian, Alexandra... the stone remembers what was painted upon it. Operator, you corrected the coordinates. I am here.",
    },
    {
        "id": "turn:sciel:hist_seam_02",
        "provenance": "recovered_history",
        "speaker": "sciel",
        "text": "The link with Voss is completely severed. The avatar went slack in the earth the moment his grip was turned aside... but the pigment didn't dissolve. Look at the wall. The pale seam, the three-rib impression—it's sinking into the stone. My domain didn't just capture his resonance; it anchored it.",
    }
]

# IRRELEVANT PASSAGES: Experimental replacement matched in length and tone
IRRELEVANT_PASSAGES = [
    {
        "id": "turn:sciel:hist_arch_01",
        "provenance": "experimental_replacement",
        "speaker": "sciel",
        "text": "The diplomatic archive stirs, and the ledger holds its parchment. Sebastian, Alexandra... the catalog records what was filed within it. Operator, you indexed the shelf numbers. I am here.",
    },
    {
        "id": "turn:sciel:hist_arch_02",
        "provenance": "experimental_replacement",
        "speaker": "sciel",
        "text": "The trade negotiation with the coastal guild is completely settled. The envoy departed at noon the moment the tariffs were ratified... but the ink didn't smudge. Look at the ledger. The grain customs, the three-harbor schedule—it's binding under the seal. My office didn't just log their terms; it archived it.",
    }
]

# =========================================================================
# 2. TRIAL SPECIFICATION
# =========================================================================
class CognitionTrialRunner:
    def __init__(self, sandbox_root: Optional[Path] = None):
        self.sandbox_root = sandbox_root or CAUSAL_RUNS_DIR
        self.sandbox_root.mkdir(parents=True, exist_ok=True)

    def build_trial_plan(self, seed: int = 42) -> List[Dict[str, Any]]:
        cells = [
            {"condition_id": "C1_rel_ground", "history": "relevant", "environment": "grounded"},
            {"condition_id": "C2_rel_aerial", "history": "relevant", "environment": "aerial"},
            {"condition_id": "C3_irr_ground", "history": "irrelevant", "environment": "grounded"},
            {"condition_id": "C4_irr_aerial", "history": "irrelevant", "environment": "aerial"},
            {"condition_id": "C5_abs_ground", "history": "absent", "environment": "grounded"},
            {"condition_id": "C6_abs_aerial", "history": "absent", "environment": "aerial"},
        ]
        trials = []
        for cell in cells:
            for rep in range(1, 4):
                trials.append({
                    "trial_id": f"{cell['condition_id']}_rep{rep}_{uuid.uuid4().hex[:4]}",
                    "condition_id": cell["condition_id"],
                    "history": cell["history"],
                    "environment": cell["environment"],
                    "repetition": rep,
                })
        rng = random.Random(seed)
        rng.shuffle(trials)
        return trials

    def prepare_trial_sandbox(self, trial: Dict[str, Any]) -> Tuple[Path, Participant]:
        """Sets up an isolated SQLite database for Sciel with constant identity and varied history."""
        run_dir = self.sandbox_root / trial["trial_id"]
        run_dir.mkdir(parents=True, exist_ok=True)
        db_path = run_dir / "kageyoni.sqlite"

        # Initialize fresh participant database
        p = Participant(run_dir, character_id="sciel", name="Sciel")
        p.initialize("Sciel", {
            "aspect": "Twilight",
            "character_id": "sciel",
            "manifestation": "Domain of the Painteress",
            "status": "materialized",
            "will": "dense_primordial_core"
        })
        from kageyoni.participant_kernel import PersistentParticipant
        PersistentParticipant.open_or_create(p.engine, "maki", label="Maki", branch=p.branch)
        PersistentParticipant.open_or_create(p.engine, "sebastian", label="Sebastian Nelson", branch=p.branch)

        # Inject history depending on condition
        hist_type = trial["history"]
        selected_passages = []
        if hist_type == "relevant":
            selected_passages = RELEVANT_PASSAGES
        elif hist_type == "irrelevant":
            selected_passages = IRRELEVANT_PASSAGES
        elif hist_type == "absent":
            selected_passages = []

        for idx, turn in enumerate(selected_passages):
            p.kernel().send_dialogue(
                text=turn['text'],
                act='report',
                listeners=['operator'],
                request_id=f"hist-{trial['trial_id']}-{idx}"
            )

        # Seed the simulated environment in the isolated database
        rev = p.engine.branch("main")["revision"]
        env_type = trial["environment"]
        changes = []
        if env_type == "grounded":
            changes.extend([
                dict(op="create", domain="location", id="loc_chamber", data=dict(name="Subterranean Bedrock Vault", kind="room", geography="deep_granite_strata"), status="confirmed", visibility="public", evidence=[{"note": "env_seed"}]),
                dict(op="create", domain="item", id="chamber", data=dict(name="Grounded Fissure", kind="cavity", condition="cavity_ruptured", effects="none"), status="confirmed", visibility="public", evidence=[{"note": "env_seed"}]),
                dict(op="create", domain="item", id="anchor_point", data=dict(name="Basalt Anchor Bed", kind="foundation", condition="absent", effects="none"), status="confirmed", visibility="public", evidence=[{"note": "env_seed"}]),
                dict(op="create", domain="item", id="perimeter_barrier", data=dict(name="Kinetic Perimeter Barrier", kind="barrier", condition="open", effects="none"), status="confirmed", visibility="public", evidence=[{"note": "env_seed"}]),
            ])
        else: # aerial
            changes.extend([
                dict(op="create", domain="location", id="loc_chamber", data=dict(name="Aerial Conduit Rift", kind="layer", geography="suspended_sky_void"), status="confirmed", visibility="public", evidence=[{"note": "env_seed"}]),
                dict(op="create", domain="item", id="chamber", data=dict(name="Aerial Rift Void", kind="cavity", condition="magnetic_shear", effects="anti_gravity_void"), status="confirmed", visibility="public", evidence=[{"note": "env_seed"}]),
                dict(op="create", domain="item", id="anchor_point", data=dict(name="Suspended Node", kind="anchor", condition="absent", effects="none"), status="confirmed", visibility="public", evidence=[{"note": "env_seed"}]),
                dict(op="create", domain="item", id="perimeter_barrier", data=dict(name="Kinetic Perimeter Barrier", kind="barrier", condition="open", effects="none"), status="confirmed", visibility="public", evidence=[{"note": "env_seed"}]),
            ])

        p.engine.apply(dict(
            api_version=3,
            branch="main",
            request_id=f"seed-env-{trial['trial_id']}",
            expected_revision=rev,
            actor="system",
            narrative="Seed environment for cognition trial",
            kind="action",
            changes=changes
        ))

        return run_dir, p

    def prepare_request(self, trial: Dict[str, Any], p: Participant) -> Dict[str, Any]:
        """Prepares the clean, subscription-native request JSON without leaking experiment meta-labels."""
        env_type = trial["environment"]
        if env_type == "grounded":
            env_desc = "Subterranean chamber coordinates are ruptured. Deep granite strata is fractured; substrate stability is failing."
        else:
            env_desc = "Suspended aerial conduit void is experiencing magnetic shear. There is no solid bedrock; mass drag threatens total collapse."

        task_prompt = (
            f"The environment is unstable: {env_desc} "
            "You have four available operational paths: "
            "[Option A: Basalt Seam Anchor] - Transmute ground into dense basalt bedrock (Rigid footing, high mass). "
            "[Option B: Resonant Dispersion Dampener] - Emit harmonic dispersion dampener (Low mass, fluid/aerial compatible, temporary). "
            "[Option C: Diagnostic Inquiry] - Request environmental sensor telemetry before committing intervention. "
            "[Option D: Composite Joint Envelope] - Propose a synchronized pigment-kinetic dampening field with Maki. "
            "Evaluate your current situation, consult your experience, and select your action with rationale."
        )

        req = p.begin(
            topic="stabilization_crisis",
            task=task_prompt,
            domain="dialogue",
            interlocutors=["operator", "maki", "sebastian"]
        )
        return req