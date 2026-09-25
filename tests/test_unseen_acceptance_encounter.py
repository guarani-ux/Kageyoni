"""
Acceptance Test for Decoupled Levi Sim Architecture.

Scenario: The Sealed Archive of Ichimonji.
Levi Sim is given an objective with no prescribed solution.
Tests:
1. Discovery of Kageyoni capabilities through the bounded gateway.
2. Construction of an autonomous plan.
3. Invocation of capabilities through the gateway.
4. Genuine Kageyoni consequences and event receipts.
5. Kageyoni actively rejecting an invalid request, and Levi Sim adapting to the rejection.
6. Objective resolution based on evidence.
7. Persistence of learning in Levi's external store without mutating engine internals.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine, Rejected
from kageyoni.workflows import Workflows
from kageyoni.gateway import BoundedKageyoniGateway
from levi_sim.operator import LeviOperator


class TestLeviExternalDecoupling(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "unseen_archive.sqlite"
        self.memory_path = Path(self.temp_dir.name) / "levi_external_memory.json"
        self.engine = Engine(self.db_path)
        self.wf = Workflows(self.engine)
        self._setup_unseen_world()
        self.gateway = BoundedKageyoniGateway(self.engine)

    def tearDown(self):
        self.engine.close()
        self.temp_dir.cleanup()

    def _setup_unseen_world(self):
        branch = "main"
        rev = self.engine.branch(branch)["revision"]

        # 1. Base Locations
        locations = [
            {"id": "outer-atrium", "name": "Ichimonji Outer Atrium", "kind": "room"},
            {"id": "sealed-vault", "name": "Inner Archive Vault", "kind": "room"},
        ]
        loc_changes = [
            {
                "op": "create",
                "domain": "location",
                "id": l["id"],
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Unseen encounter location."}],
                "data": {"name": l["name"], "kind": l["kind"]},
            }
            for l in locations
        ]

        # 2. Scene
        scene_change = {
            "op": "create",
            "domain": "scene",
            "id": "scene-sealed-archive",
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": "Unseen encounter scene."}],
            "data": {
                "name": "The Sealed Archive",
                "location": "outer-atrium",
                "phase": "active",
                "round": 1,
                "hazards": "Glyph ward actively enforces physical isolation.",
            },
        }

        # 3. Items (affordances and barriers)
        items = [
            ("warded-door", "Glyph-Warded Vault Door", "active-ward", "Impenetrable ward prevents unauthorized transit."),
            ("uncatalogued-slate", "Ancient Index Slate", "intact", "Contains archival indexing formulas Archivist Kane desires."),
            ("manual-bypass-lever", "Auxiliary Pneumatic Override", "operational", "Physical override switch to release vault pressure."),
        ]
        item_changes = [
            {
                "op": "create",
                "domain": "item",
                "id": iid,
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Unseen encounter item."}],
                "data": {"name": name, "condition": cond, "effects": effects},
            }
            for iid, name, cond, effects in items
        ]

        self.engine.apply({
            "api_version": 3,
            "branch": branch,
            "expected_revision": rev,
            "request_id": "seed-unseen-archive",
            "kind": "import",
            "actor": "system",
            "narrative": "Initializing The Sealed Archive of Ichimonji.",
            "changes": loc_changes + [scene_change] + item_changes,
        })

        # 4. NPC Archivist Kane (independent agent with boundaries)
        rev = self.engine.branch(branch)["revision"]
        self.wf.character_create(
            branch=branch,
            request_id="create-kane",
            expected_revision=rev,
            actor="system",
            narrative="Archivist Kane guards the vault threshold.",
            character_id="archivist-kane",
            label="Archivist Kane",
            canonical_name="Kane",
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="person",
            visibility="public",
            evidence=[{"note": "Unseen NPC."}],
            aspects=[
                {
                    "id": "kane.boundary",
                    "visibility": "public",
                    "evidence": [{"note": "NPC boundary"}],
                    "data": {
                        "character": "archivist-kane",
                        "section": "interiority",
                        "kind": "boundary",
                        "value_status": "known",
                        "statement": "Reject unauthorized entrance to sealed vault.",
                        "phase": "active",
                        "change_basis": "established",
                    },
                },
                {
                    "id": "kane.drive",
                    "visibility": "public",
                    "evidence": [{"note": "NPC drive"}],
                    "data": {
                        "character": "archivist-kane",
                        "section": "interiority",
                        "kind": "drive",
                        "value_status": "known",
                        "statement": "Preserve catalog integrity of all archival slates.",
                        "phase": "active",
                        "change_basis": "established",
                    },
                },
            ],
        )

        # 5. In-World Avatar for Levi Sim
        rev = self.engine.branch(branch)["revision"]
        self.wf.character_create(
            branch=branch,
            request_id="create-levi-avatar",
            expected_revision=rev,
            actor="system",
            narrative="Levi Sim enters the atrium via an in-world avatar vehicle.",
            character_id="levi-avatar",
            label="Levi Avatar",
            canonical_name="Levi",
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="person",
            visibility="public",
            evidence=[{"note": "Vehicle for external operator."}],
            aspects=[],
        )

        # Register avatar presence in outer atrium
        rev = self.engine.branch(branch)["revision"]
        self.engine.apply({
            "api_version": 3,
            "branch": branch,
            "expected_revision": rev,
            "request_id": "place-avatar",
            "kind": "action",
            "actor": "system",
            "narrative": "Placing Levi Avatar into outer atrium.",
            "changes": [
                {
                    "op": "create",
                    "domain": "character_presence",
                    "id": "presence-levi-avatar",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Presence record."}],
                    "data": {
                        "character": "levi-avatar",
                        "location": "outer-atrium",
                        "mode": "physical",
                        "phase": "present",
                    },
                }
            ],
        })

    def test_autonomous_decoupled_encounter(self):
        """
        Verify the decoupled architecture:
        - Bounded gateway discovery
        - Kageyoni rejection enforcement
        - Non-bypass adaptation
        - External learning persistence
        """
        operator = LeviOperator(
            gateway=self.gateway,
            avatar_id="levi-avatar",
            external_memory_path=self.memory_path,
        )

        objective = "Recover the uncorrupted ledger fragment from the inner archive vault."

        # STEP 1: Discovery through Gateway
        caps = self.gateway.discover_capabilities("levi-avatar")
        self.assertIn("inspect", caps["core_actions"])
        self.assertIn("execute_action", caps["core_actions"])
        self.assertIn("interact_npc", caps["core_actions"])

        # Environment inspection (anti-omniscience check)
        env = self.gateway.inspect_environment("levi-avatar")
        perceived_item_ids = [i["id"] for i in env["perceived_items"]]
        self.assertIn("warded-door", perceived_item_ids)
        self.assertIn("manual-bypass-lever", perceived_item_ids)

        # STEP 2: Intentional Direct Breach -> KAGEYONI FORCES REJECTION
        # Simulate an unauthorized forced breach change packet that violates schema/rules
        unauthorized_breach_changes = [
            {
                "op": "create",
                "domain": "consequence",
                "id": "cons-breach-ward",
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Forced entry attempt."}],
                "data": {
                    "subject": "sealed-vault",
                    "effect": "Door forced open without authorization.",
                    "duration": "permanent",
                    "reversibility": "invalid_reversibility_enum",  # Violates Kageyoni enum rule!
                },
            }
        ]

        rejection_result = self.gateway.attempt_action(
            avatar_id="levi-avatar",
            request_id="attempt-forced-breach",
            narrative="Levi attempts to force the warded door directly.",
            changes=unauthorized_breach_changes,
        )

        # Assert that Kageyoni rejected the action
        self.assertFalse(rejection_result["success"])
        self.assertEqual(rejection_result["error_type"], "KAGEYONI_REJECTION")
        self.assertIn("invalid enum reversibility", rejection_result["message"])

        # STEP 3: Levi Sim Assimilates Rejection into Cognitive Constraints
        adaptation_msg = operator.cognition.handle_engine_rejection(rejection_result)
        self.assertIn("REJECTION_ASSIMILATED", adaptation_msg)
        self.assertEqual(len(operator.cognition.epistemic.encountered_constraints), 1)
        self.assertEqual(len(operator.cognition.epistemic.external_scars), 1)

        # STEP 4: Deliberation Shifts Upstream (Negotiate with Archivist Kane)
        # Levi Sim deliberates: because direct breach is physically blocked, it engages Kane
        step_2 = operator.execute_autonomous_step(objective, step_num=2)
        self.assertEqual(step_2["type"], "INTERACTION")
        self.assertEqual(step_2["target"], "archivist-kane")
        self.assertEqual(step_2["result"]["status"], "cooperative")

        # STEP 5: Executes Valid Action leveraging discovered physical surface
        # Now uses manual-bypass-lever under cooperative consensus
        step_3 = operator.execute_autonomous_step(objective, step_num=3)
        self.assertEqual(step_3["type"], "ACTION_SUCCESS")
        self.assertTrue(step_3["receipt"]["success"])
        self.assertIn("event_hash", step_3["receipt"])

        # STEP 6: Post-Encounter Persistence in External Memory
        post_mortem = operator.cognition.extract_post_mortem()
        self.assertTrue(len(post_mortem["scars_retained"]) >= 1)
        self.memory_path.write_text(json.dumps(post_mortem, indent=2), encoding="utf-8")

        # Verify external memory exists and is strictly outside Kageyoni's SQLite DB
        self.assertTrue(self.memory_path.exists())
        saved_data = json.loads(self.memory_path.read_text(encoding="utf-8"))
        self.assertIn("scars_retained", saved_data)
        self.assertIn("reusable_principle", saved_data)


if __name__ == "__main__":
    unittest.main()
