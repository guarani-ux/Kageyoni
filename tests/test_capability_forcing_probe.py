"""Capability-Forcing Recomposition Probe for Kageyoni.

Objective:
Prove that an uninformed EntityInstance with ZERO pre-configured capability verbs
(supported_verbs = []) can dynamically acquire situated reachability from Ground,
avoid active negative constraints, and achieve an objective in 1 step without manual
prompt hints or hardcoded spec verbs.

Hypothesized Minimum Edge:
Existing A (Engine.context route records)
+ Existing B (ActionHorizon.actual_reachability & update_actual)
+ Minimum Edge (Gateway situated affordance synthesis & Entity perception binding)
-> Capability Delta: Dynamic situated agency without static verb pre-programming.

Pattern Verified:
1. SYSTEM_0 (Affordance synthesis ablated) -> FAILS (uninformed entity reachability is empty)
2. SYSTEM_0 + candidate change -> SUCCEEDS in 1 step (auto-reifies route affordances, prunes scars, reaches objective)
3. NEGATIVE CONTROL -> FAILS (chamber with only blocked routes has zero viable affordances, fails closed)
4. ABLATION -> FAILS AGAIN (removing affordance synthesis causes entity reachability to drop back to empty)
"""
import copy
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from kageyoni.engine import Engine, Rejected
from kageyoni.entity import (
    ActionHorizon,
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


class TestCapabilityForcingProbe(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "forcing_test.sqlite"
        shutil.copy2(campaign_db_path(), self.db_path)
        self.engine = Engine(self.db_path)
        install_all(self.engine)

        current_rev = self.engine.branch("main")["revision"]
        axiom_rec = self.engine.get("main", "axiom")
        scene_rec = self.engine.get("main", "threshold-scene")

        # Seed chamber with:
        # 1. Blocked route: collapsed-tunnel (probe-chamber -> inner-sanctum, access: blocked)
        # 2. Viable route: navigable-fissure (probe-chamber -> inner-sanctum, access: open)
        # 3. Axiom positioned in probe-chamber
        self.engine.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": current_rev,
            "request_id": f"seed-env-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": "system",
            "narrative": "Construct capability-forcing chamber",
            "changes": [
                {"op": "patch", "id": "threshold-scene", "domain": "scene", "expected_version": scene_rec["version"], "visibility": "public", "data": {"phase": "closed"}, "evidence": [{"note": "Entered"}]},
                {"op": "create", "id": "probe-chamber", "domain": "location", "visibility": "public", "data": {"name": "Probe Chamber", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "inner-sanctum", "domain": "location", "visibility": "public", "data": {"name": "Inner Sanctum", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "collapsed-tunnel", "domain": "route", "visibility": "public", "data": {"origin": "probe-chamber", "destination": "inner-sanctum", "access": "blocked", "conditions": "physically_collapsed"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "navigable-fissure", "domain": "route", "visibility": "public", "data": {"origin": "probe-chamber", "destination": "inner-sanctum", "access": "open", "conditions": "navigable"}, "evidence": [{"note": "Seed"}]},
                {"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_rec["version"], "visibility": "public", "data": {"location": "probe-chamber"}, "evidence": [{"note": "Moved"}]},
            ],
        })

        # Seed an active persistent Scar in ScarLedger barring the collapsed tunnel
        store = SQLiteSituationStore(self.engine.db)
        ledger = ScarLedger(store)
        ledger.record_scar(Scar(
            scar_id="scar:alexandra:tunnel-collapse-01",
            failure_class="HARD_INVARIANT_VIOLATION",
            root_cause="Tunnel is physically collapsed",
            probe_refs=("probe-seed",),
            trigger_condition="traverse_route:collapsed-tunnel",
            affected_scopes=("probe-chamber",),
            status="open",
        ))

    def tearDown(self):
        self.engine.close()
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_1_system_0_ablated_fails_without_affordance_synthesis(self):
        """
        SYSTEM_0 (Before Change / Ablated):
        Entity has ZERO pre-configured capability verbs (supported_verbs = []).
        Gateway affordance synthesis is disabled (enable_affordance_synthesis=False).
        Proves: Without affordance synthesis, an uninformed entity cannot discover reachable actions.
        """
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        spec.capability_model.active_capabilities = {}

        entity = EntityInstance(spec, initial_objective="Reach Inner Sanctum")
        gateway = BoundedKageyoniGateway(self.engine, enable_affordance_synthesis=False)
        env = gateway.inspect_environment(entity.entity_id)
        entity.reconcile_perception(env)

        # In System 0: available_affordances is empty, action horizon is empty
        self.assertEqual(env.get("available_affordances"), [])
        self.assertEqual(len(entity.state.action_horizon.believed_reachability), 0)
        self.assertNotIn("traverse_route:navigable-fissure", entity.state.action_horizon.believed_reachability)

    def test_2_system_0_plus_candidate_change_succeeds_in_one_step(self):
        """
        SYSTEM_0 + CANDIDATE CHANGE:
        Entity has ZERO pre-configured capability verbs (supported_verbs = []).
        Gateway synthesizes situated affordances directly from visible route records.
        Entity reconciles perception:
        - collapsed-tunnel is recognized as blocked and restricted by Scar -> NOT believed reachable.
        - navigable-fissure is recognized as open -> dynamically added to ActionHorizon.
        Entity executes traversal and fulfills completion contract in 1 step!
        """
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        spec.capability_model.active_capabilities = {}

        contract = CompletionContract(
            contract_id="contract-axiom-forcing",
            objective="Reach Inner Sanctum",
            required_conditions=[
                CompletionCondition(domain="character", record_id="axiom", field_name="location", expected_value="inner-sanctum"),
            ],
        )
        entity = EntityInstance(spec, initial_objective=contract.objective, completion_contract=contract)

        gateway = BoundedKageyoniGateway(self.engine, enable_affordance_synthesis=True)
        env = gateway.inspect_environment(entity.entity_id)

        # 1. Verify Gateway reified affordances
        situated = env.get("situated_affordances", [])
        self.assertEqual(len(situated), 2)
        available = env.get("available_affordances", [])
        self.assertEqual(available, ["traverse_route:navigable-fissure"])

        # 2. Reconcile perception into ActionHorizon
        entity.reconcile_perception(env)

        # 3. Verify Reachability: Only viable route is believed reachable; collapsed route is pruned!
        self.assertIn("traverse_route:navigable-fissure", entity.state.action_horizon.believed_reachability)
        self.assertNotIn("traverse_route:collapsed-tunnel", entity.state.action_horizon.believed_reachability)

        # 4. If entity were to try the blocked route, gateway fails closed with NEGATIVE_CONSTRAINT_VIOLATION
        axiom_cur = self.engine.get("main", "axiom")
        res_blocked = gateway.attempt_action(
            avatar_id=entity.entity_id,
            request_id=f"req-blocked-{uuid.uuid4().hex[:6]}",
            narrative="Axiom attempts to traverse collapsed tunnel",
            changes=[{"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_cur["version"], "visibility": "public", "data": {"location": "inner-sanctum"}}],
            action_name="traverse_route:collapsed-tunnel",
        )
        self.assertFalse(res_blocked["success"])
        self.assertEqual(res_blocked.get("rejection_class"), "NEGATIVE_CONSTRAINT_VIOLATION")

        # 5. Entity executes the dynamically discovered viable affordance (traverse_route:navigable-fissure)
        res_success = gateway.attempt_action(
            avatar_id=entity.entity_id,
            request_id=f"req-success-{uuid.uuid4().hex[:6]}",
            narrative="Axiom traverses navigable fissure to inner sanctum",
            changes=[{"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_cur["version"], "visibility": "public", "data": {"location": "inner-sanctum"}}],
            action_name="traverse_route:navigable-fissure",
        )
        self.assertTrue(res_success["success"], "Ground must authorize the viable affordance")

        # 6. Verify CompletionContract against authoritative world records
        records = gateway.query_records(entity.entity_id)
        comp_res = entity.evaluate_completion(records)
        self.assertEqual(comp_res["status"], "COMPLETED")

    def test_3_negative_control_fails_when_no_viable_affordance_exists(self):
        """
        NEGATIVE CONTROL:
        Chamber has NO open routes (all routes blocked/collapsed).
        Proves: Capability delta is strictly bounded by physical Ground affordances.
        When no physical affordances exist, ActionHorizon remains empty and entity fails closed.
        """
        tmp_ctrl = tempfile.TemporaryDirectory()
        ctrl_db = Path(tmp_ctrl.name) / "ctrl.sqlite"
        shutil.copy2(campaign_db_path(), ctrl_db)
        engine_ctrl = Engine(ctrl_db)
        install_all(engine_ctrl)

        axiom_rec = engine_ctrl.get("main", "axiom")
        engine_ctrl.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": engine_ctrl.branch("main")["revision"],
            "request_id": f"seed-ctrl-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": "system",
            "narrative": "Construct room with no open exits",
            "changes": [
                {"op": "create", "id": "dead-end-chamber", "domain": "location", "visibility": "public", "data": {"name": "Dead End", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "inner-sanctum", "domain": "location", "visibility": "public", "data": {"name": "Inner Sanctum", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "sealed-exit", "domain": "route", "visibility": "public", "data": {"origin": "dead-end-chamber", "destination": "inner-sanctum", "access": "blocked", "conditions": "magically_sealed"}, "evidence": [{"note": "Seed"}]},
                {"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_rec["version"], "visibility": "public", "data": {"location": "dead-end-chamber"}, "evidence": [{"note": "Moved"}]},
            ],
        })

        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        entity = EntityInstance(spec, initial_objective="Reach Inner Sanctum")

        gateway = BoundedKageyoniGateway(engine_ctrl, enable_affordance_synthesis=True)
        env = gateway.inspect_environment(entity.entity_id)
        entity.reconcile_perception(env)

        # All situated affordances are blocked; available_affordances is empty
        self.assertEqual(env.get("available_affordances"), [])
        self.assertEqual(len(entity.state.action_horizon.believed_reachability), 0)

        # Clean release of engine connection
        del gateway
        engine_ctrl.close()
        del engine_ctrl
        try:
            tmp_ctrl.cleanup()
        except Exception:
            pass

    def test_4_ablation_minus_causal_mechanism_fails_again(self):
        """
        ABLATION:
        SYSTEM_0 + Candidate Change − Causal Mechanism (enable_affordance_synthesis=False).
        Proves: If the affordance synthesis edge is ablated, the entity's reachability drops back to empty
        even though physical routes exist in Ground.
        """
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []

        entity = EntityInstance(spec, initial_objective="Reach Inner Sanctum")
        gateway_ablated = BoundedKageyoniGateway(self.engine, enable_affordance_synthesis=False)
        env = gateway_ablated.inspect_environment(entity.entity_id)
        entity.reconcile_perception(env)

        # Causal necessity verified: without the mechanism, capability vanishes
        self.assertNotIn("traverse_route:navigable-fissure", entity.state.action_horizon.believed_reachability)
        self.assertEqual(len(entity.state.action_horizon.believed_reachability), 0)


if __name__ == "__main__":
    unittest.main()
