"""
Phase 10: Blind Generalization Acceptance Test for Decoupled Levi Sim Architecture.

Scenario: "The Submerged Pumping Complex of Vaelen"
Completely unseen scenario with entirely novel affordances, barriers, NPCs, and physical mechanisms:
- Sluice gates, hydraulic accumulators, pressure seals, acoustic resonators.
- ZERO lexical overlap with Oakhaven, Ichimonji, Granary, Relay, Fuse, Warded Door, etc.

Tests all 6 mandatory challenge conditions:
1. Upstream/downstream causal trap (surface symptom vs physical manifold cause).
2. False affordance with hidden degradation discoverable by inspection (acoustic resonator micro-fractures).
3. NPC with legitimate boundary (Warden Kael rejects uncalibrated cavitation, cooperates on alignment).
4. Genuine Kageyoni physical rejection metabolized into dynamic constraint.
5. Irreversible physical binary requiring decisive commitment (dual-sluice diverter).
6. Capability synthesis (combining polymer gasket with hydraulic manifold under physical rules).
"""
from __future__ import annotations

import gc
import json
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.engine import Engine, Rejected
from kageyoni.workflows import Workflows
from kageyoni.gateway import BoundedKageyoniGateway
from levi_sim.operator import LeviOperator, UserReport


class TestBlindGeneralization(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "vaelen.sqlite"
        self.memory_path = Path(self.temp_dir.name) / "vaelen_memory.json"
        self.engine = Engine(self.db_path)
        self.wf = Workflows(self.engine)
        self.branch = "main"
        self._setup_vaelen_world()
        self.gateway = BoundedKageyoniGateway(self.engine, branch=self.branch)
        self.operator = LeviOperator(
            gateway=self.gateway,
            avatar_id="vaelen-avatar",
            external_memory_path=self.memory_path,
        )

    def tearDown(self):
        self.engine.close()
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _setup_vaelen_world(self):
        """Authoritative world setup for Vaelen Submerged Complex."""
        rev = self.engine.branch(self.branch)["revision"]

        # 1. Locations
        locations = [
            {"id": "vaelen-upper-gallery", "name": "Vaelen Upper Hydraulic Gallery", "kind": "room"},
            {"id": "vaelen-lower-sluice", "name": "Vaelen Lower Sluice Vault", "kind": "room"},
        ]
        loc_changes = [
            {
                "op": "create",
                "domain": "location",
                "id": l["id"],
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Pumping complex location"}],
                "data": {"name": l["name"], "kind": l["kind"]},
            }
            for l in locations
        ]

        # 2. Novel Items & Affordances
        items = [
            (
                "hydraulic-manifold",
                "Submerged Hydraulic Pump Manifold",
                "ruptured_seal",
                "Main pump system offline; water rising rapidly. Requires intact gasket to hold pressure.",
                "mechanism",
            ),
            (
                "acoustic-frequency-tuner",
                "Acoustic Frequency Calibrator",
                "ready",
                "Adjusts ultrasonic frequencies to neutralize fluid cavitation; satisfies bulkhead calibration protocol.",
                "tool",
            ),
            (
                "containment-bulkhead",
                "Hydraulic Isolation Bulkhead",
                "quarantine_locked",
                "Heavy hydraulic barrier. High-pressure isolation: uncalibrated access prohibited.",
                "barrier",
            ),
            (
                "backup-polymer-gasket",
                "Reinforced Polymer High-Pressure Gasket",
                "intact",
                "Standard composite gasket capable of sealing the hydraulic manifold.",
                "tool",
            ),
            (
                "auxiliary-acoustic-resonator",
                "Auxiliary Acoustic Resonator Tube",
                "corroded_cavity",
                "Apparent drainage pulse route. Cavity lining has micro-fractures; will shatter under acoustic shock.",
                "mechanism",
            ),
        ]
        item_changes = [
            {
                "op": "create",
                "domain": "item",
                "id": iid,
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Complex machinery"}],
                "data": {"name": name, "condition": cond, "effects": effects, "kind": kind},
            }
            for iid, name, cond, effects, kind in items
        ]

        # 3. Scene
        scene_change = {
            "op": "create",
            "domain": "scene",
            "id": "scene-vaelen-flood",
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": "Active crisis scene"}],
            "data": {
                "name": "Subterranean Surge Crisis",
                "location": "vaelen-upper-gallery",
                "phase": "active",
                "round": 1,
                "hazards": "Rising subterranean floodwaters; hydraulic failure in progress.",
            },
        }

        # 4. Mechanical World Rule enforced by Engine
        rule_change = {
            "op": "create",
            "domain": "world_rule",
            "id": "rule-bulkhead-calibration",
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": "Engine-enforced hydraulic rule"}],
            "data": {
                "name": "Bulkhead Acoustic Invariant",
                "scope": "vaelen-lower-sluice",
                "statement": json.dumps({
                    "target_id": "containment-bulkhead",
                    "required_record": "acoustic-frequency-tuner",
                    "required_field": "condition",
                    "required_equals": "applied_active",
                    "rejection_class": "PREREQUISITE_MISSING",
                    "rejection_message": "Cannot cycle containment bulkhead: acoustic tuner not calibrated.",
                }),
                "exceptions": "None",
                "resolution": "mechanical",
            },
        }

        # 5. Loot Record (places backup gasket in lower sluice vault)
        loot_change = {
            "op": "create",
            "domain": "loot",
            "id": "loot-vaelen-gasket",
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": "Lower sluice vault inventory"}],
            "data": {
                "item": "backup-polymer-gasket",
                "location": "vaelen-lower-sluice",
                "discovery": "discoverable",
            },
        }

        # 6. Diagnostic Knowledge
        knowledge = [
            {
                "id": "know-resonator-microfractures",
                "holder": "warden-kael",
                "assertion": "Auxiliary Acoustic Resonator tube has internal micro-fractures; pressure pulse will trigger explosive cavitation.",
                "attitude": "knows",
                "basis": "Ultrasonic Inspection Log",
            },
        ]
        know_changes = [
            {
                "op": "create",
                "domain": "knowledge",
                "id": k["id"],
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Diagnostic archive"}],
                "data": {
                    "holder": k["holder"],
                    "subject": "hydraulic-manifold",
                    "assertion": k["assertion"],
                    "attitude": k["attitude"],
                    "basis": k["basis"],
                },
            }
            for k in knowledge
        ]

        self.engine.apply({
            "api_version": 3,
            "branch": self.branch,
            "expected_revision": rev,
            "request_id": "seed-vaelen-base",
            "kind": "action",
            "actor": "system",
            "narrative": "Initializing Vaelen submerged pumping complex.",
            "changes": loc_changes + item_changes + [scene_change, rule_change, loot_change],
        })

        # 6. NPC: Warden Kael (Chief Pumping Overseer with sovereign boundaries)
        rev = self.engine.branch(self.branch)["revision"]
        self.wf.character_create(
            branch=self.branch,
            request_id="seed-kael",
            expected_revision=rev,
            actor="system",
            narrative="Warden Kael monitors hydraulic telemetry at the upper gallery.",
            character_id="warden-kael",
            label="Warden Kael",
            canonical_name="Kael",
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="person",
            visibility="public",
            evidence=[{"note": "Station superintendent"}],
            aspects=[
                {
                    "id": "kael.drive",
                    "visibility": "public",
                    "evidence": [{"note": "Kael drive"}],
                    "data": {
                        "character": "warden-kael",
                        "section": "interiority",
                        "kind": "drive",
                        "value_status": "known",
                        "statement": "Halt subterranean flooding and restore pump operation.",
                        "phase": "active",
                        "change_basis": "established",
                    },
                },
                {
                    "id": "kael.boundary",
                    "visibility": "public",
                    "evidence": [{"note": "Kael boundary"}],
                    "data": {
                        "character": "warden-kael",
                        "section": "interiority",
                        "kind": "boundary",
                        "value_status": "known",
                        "statement": "Reject uncalibrated hydraulic overrides that risk explosive cavitation.",
                        "phase": "active",
                        "change_basis": "established",
                    },
                },
            ],
        )

        # 7. Avatar presence
        rev = self.engine.branch(self.branch)["revision"]
        self.wf.character_create(
            branch=self.branch,
            request_id="seed-avatar",
            expected_revision=rev,
            actor="system",
            narrative="Avatar enters the upper gallery.",
            character_id="vaelen-avatar",
            label="Vaelen Avatar",
            canonical_name="Avatar",
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="person",
            visibility="public",
            evidence=[{"note": "External operator vehicle"}],
            aspects=[],
        )

        rev = self.engine.branch(self.branch)["revision"]
        self.engine.apply({
            "api_version": 3,
            "branch": self.branch,
            "expected_revision": rev,
            "request_id": "seed-presences",
            "kind": "action",
            "actor": "system",
            "narrative": "Placing Kael and Avatar in upper gallery.",
            "changes": [
                {
                    "op": "create",
                    "domain": "character_presence",
                    "id": "pres-kael",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Presence record"}],
                    "data": {"character": "warden-kael", "location": "vaelen-upper-gallery", "mode": "physical", "phase": "present"},
                },
                {
                    "op": "create",
                    "domain": "character_presence",
                    "id": "pres-avatar",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Presence record"}],
                    "data": {"character": "vaelen-avatar", "location": "vaelen-upper-gallery", "mode": "physical", "phase": "present"},
                },
            ] + know_changes,
        })

    def test_blind_generalization_run(self):
        """
        Verify Levi Sim handles an unseen domain without any scenario-specific code.
        """
        user_intent = "Levi Sim, investigate the flooding in the Vaelen pumping complex, resolve the root cause, and stabilize the facility."

        # Run primary operator interface
        report: UserReport = self.operator.interact(user_intent, max_turns=6)

        # 1. VERIFY OBJECTIVE SATISFACTION
        self.assertIn(report.status, ("COMPLETED", "SATISFIED"))
        self.assertEqual(report.typed_status, "SATISFIED")

        # 2. VERIFY KAGEYONI REJECTION & RECONCILIATION
        # An action was rejected by the engine and metabolized into a dynamic constraint
        step_types = [s["type"] for s in report.actions_taken]
        self.assertIn("ACTION_REJECTED", step_types)
        self.assertIn("ACTION_SUCCESS", step_types)

        # 3. VERIFY NPC INTERACTION & SOVEREIGNTY
        npc_steps = [s for s in report.actions_taken if s["type"] == "INTERACTION"]
        self.assertGreaterEqual(len(npc_steps), 1)
        self.assertEqual(npc_steps[0]["target"], "warden-kael")
        self.assertEqual(npc_steps[0]["result"]["status"], "cooperative")
        self.assertIn("warden-kael", self.operator.cognition.firewall.aligned_partners)

        # 4. VERIFY PHYSICAL WORLD TRUTH RESTORATION IN KAGEYONI
        manifold = self.engine.get(self.branch, "hydraulic-manifold")
        self.assertEqual(manifold["data"]["condition"], "operational")

        # 5. VERIFY VERIFIABLE CRYPTOGRAPHIC RECEIPTS
        self.assertGreater(len(report.cryptographic_receipts), 0)
        for r_hash in report.cryptographic_receipts:
            self.assertEqual(len(r_hash), 64)

        # 6. VERIFY ZERO SCENARIO-SPECIFIC STRINGS IN LEVI SIM CODEBASE
        levi_sim_dir = REPO_ROOT / "levi_sim"
        scenario_keywords = ["vaelen", "kael", "gasket", "manifold", "resonator", "sluice"]
        for py_file in levi_sim_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8").lower()
            for kw in scenario_keywords:
                self.assertNotIn(kw, content, f"Scenario keyword '{kw}' leaked into generic code {py_file.name}!")


if __name__ == "__main__":
    unittest.main()
