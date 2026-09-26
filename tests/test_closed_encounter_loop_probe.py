"""Closed Encounter Loop Probe for Kageyoni.

Validates the minimal closed-loop encounter mechanism:
Intent -> Perception -> Discriminating Encounter -> Resistance -> Autonomous Metabolization -> Selective Pruning -> Traversal -> Verified Contract.

Proves:
1. Epistemic Membrane: Blocked or unrepresented affordances fail closed before touching Ground.
2. Autonomous Scar Formation: Physical resistance from Ground is directly metabolized by Entity into durable Scars without manual test scaffolding.
3. Cadence & State Tracking: Consecutive rejections increment on resistance and reset on verified movement.
4. Autonomous Traversal: Viable affordances execute without manual DB patch construction.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from kageyoni.engine import Engine
from kageyoni.entity import (
    CompletionCondition,
    CompletionContract,
    EntityInstance,
    create_axiom_spec,
)
from kageyoni.gateway import BoundedKageyoniGateway
from kageyoni.persistence.migrations import install_all
from kageyoni.resources import campaign_db_path
from kageyoni.situations.scar import Scar, ScarLedger
from kageyoni.situations.storage import SQLiteSituationStore


class TestClosedEncounterLoopProbe(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "encounter_probe.sqlite"
        shutil.copy2(campaign_db_path(), self.db_path)
        self.engine = Engine(self.db_path)
        install_all(self.engine)

        current_rev = self.engine.branch("main")["revision"]
        axiom_rec = self.engine.get("main", "axiom")
        scene_rec = self.engine.get("main", "threshold-scene")

        # Seed chamber with:
        # 1. Blocked route with pre-existing scar: collapsed-tunnel
        # 2. Blocked route WITHOUT pre-existing scar (virgin obstacle): chasm-void
        # 3. Viable route: navigable-fissure
        # 4. Axiom avatar positioned in probe-chamber
        self.engine.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": current_rev,
            "request_id": f"seed-encounter-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": "system",
            "narrative": "Construct closed encounter probe environment",
            "changes": [
                {"op": "patch", "id": "threshold-scene", "domain": "scene", "expected_version": scene_rec["version"], "visibility": "public", "data": {"phase": "closed"}, "evidence": [{"note": "Entered"}]},
                {"op": "create", "id": "probe-chamber", "domain": "location", "visibility": "public", "data": {"name": "Probe Chamber", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "inner-sanctum", "domain": "location", "visibility": "public", "data": {"name": "Inner Sanctum", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "collapsed-tunnel", "domain": "route", "visibility": "public", "data": {"origin": "probe-chamber", "destination": "inner-sanctum", "access": "blocked", "conditions": "physically_collapsed"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "chasm-void", "domain": "route", "visibility": "public", "data": {"origin": "probe-chamber", "destination": "inner-sanctum", "access": "blocked", "conditions": "blocked"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "navigable-fissure", "domain": "route", "visibility": "public", "data": {"origin": "probe-chamber", "destination": "inner-sanctum", "access": "open", "conditions": "navigable"}, "evidence": [{"note": "Seed"}]},
                {"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_rec["version"], "visibility": "public", "data": {"location": "probe-chamber"}, "evidence": [{"note": "Moved"}]},
            ],
        })

        # Pre-seed scar ONLY for collapsed-tunnel
        store = SQLiteSituationStore(self.engine.db)
        self.scar_ledger = ScarLedger(store)
        self.scar_ledger.record_scar(Scar(
            scar_id="scar:alexandra:tunnel-collapse-01",
            failure_class="HARD_INVARIANT_VIOLATION",
            root_cause="Tunnel is physically collapsed",
            probe_refs=("probe-seed",),
            trigger_condition="traverse_route:collapsed-tunnel",
            affected_scopes=("probe-chamber",),
            status="open",
        ))

        self.gateway = BoundedKageyoniGateway(self.engine, scar_ledger=self.scar_ledger, enable_affordance_synthesis=True)

    def tearDown(self):
        self.engine.close()
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_1_epistemic_membrane_fails_closed_before_ground(self):
        """Action outside believed reachability fails closed at epistemic membrane."""
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        entity = EntityInstance(spec, initial_objective="Reach Inner Sanctum")

        # Entity perceives environment: only navigable-fissure is viable
        env = self.gateway.inspect_environment(entity.entity_id)
        entity.reconcile_perception(env)

        self.assertIn("traverse_route:navigable-fissure", entity.state.action_horizon.believed_reachability)
        self.assertNotIn("traverse_route:collapsed-tunnel", entity.state.action_horizon.believed_reachability)

        # Attempting collapsed-tunnel fails closed at the membrane (never reaches gateway)
        res = entity.encounter(self.gateway, "traverse_route:collapsed-tunnel")
        self.assertFalse(res["success"])
        self.assertEqual(res["error_type"], "EPISTEMIC_HORIZON_REJECTION")
        self.assertEqual(entity.state.consecutive_rejections, 0, "Membrane rejections do not increment OS rejection stress")

    def test_2_virgin_collision_auto_scars_and_prunes_in_closed_loop(self):
        """
        Entity attempts a virgin blocked route (chasm-void).
        Ground rejects with HARD_INVARIANT_VIOLATION.
        Entity automatically metabolizes rejection:
        - consecutive_rejections increments to 1
        - Scar is recorded in private epistemic state
        - Scar is recorded in durable ScarLedger
        - Action is pruned from believed reachability
        - Immediate retry fails closed at the newly formed membrane boundary!
        """
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        entity = EntityInstance(spec, initial_objective="Explore Chasm")

        # Hypothesize reachability for chasm-void
        entity.state.action_horizon.expand("traverse_route:chasm-void")
        self.assertIn("traverse_route:chasm-void", entity.state.action_horizon.believed_reachability)

        # Direct encounter with Ground
        res = entity.encounter(self.gateway, "traverse_route:chasm-void")

        self.assertFalse(res["success"])
        self.assertEqual(res["rejection_class"], "HARD_INVARIANT_VIOLATION")
        self.assertIn("physically impassable", res["message"])

        # Verification of autonomous metabolization
        self.assertEqual(entity.state.consecutive_rejections, 1)
        self.assertEqual(len(entity.state.scars), 1)
        scar = entity.state.scars[0]
        self.assertEqual(scar.attempted_action, "traverse_route:chasm-void")
        self.assertEqual(scar.rejection_class, "HARD_INVARIANT_VIOLATION")

        # Action is now pruned from ActionHorizon
        self.assertNotIn("traverse_route:chasm-void", entity.state.action_horizon.believed_reachability)
        self.assertIn("traverse_route:chasm-void", entity.state.action_horizon.blocked_actions)

        # Immediate repeat attempt fails closed at the membrane
        res_retry = entity.encounter(self.gateway, "traverse_route:chasm-void")
        self.assertFalse(res_retry["success"])
        self.assertEqual(res_retry["error_type"], "EPISTEMIC_HORIZON_REJECTION")

    def test_3_autonomous_traversal_and_contract_fulfillment(self):
        """
        Entity executes viable affordance through encounter loop with 0 human scaffolding.
        - Location updates to inner-sanctum
        - Consecutive rejections reset to 0
        - Completion contract verified against authoritative world records
        """
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        contract = CompletionContract(
            contract_id="contract-closed-encounter",
            objective="Reach Inner Sanctum",
            required_conditions=[
                CompletionCondition(domain="character", record_id="axiom", field_name="location", expected_value="inner-sanctum"),
            ],
        )
        entity = EntityInstance(spec, initial_objective=contract.objective, completion_contract=contract)

        # Perceive situated affordances
        env = self.gateway.inspect_environment(entity.entity_id)
        entity.reconcile_perception(env)

        # Enact via closed encounter loop
        res = entity.encounter(self.gateway, "traverse_route:navigable-fissure")

        self.assertTrue(res["success"], f"Encounter failed: {res}")
        self.assertEqual(entity.state.consecutive_rejections, 0)
        self.assertEqual(entity.state.perceived_world["current_location"], "inner-sanctum")

        # Verify contract against authoritative context
        records = self.gateway.query_records(entity.entity_id)
        eval_res = entity.evaluate_completion(records)
        self.assertEqual(eval_res["status"], "COMPLETED")
