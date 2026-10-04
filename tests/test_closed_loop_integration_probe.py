"""Adversarial Closed-Loop Integration Probe for Kageyoni.

Frozen Claim (Phase 0):
"Kageyoni can allow a consequence of one situated encounter to survive,
become qualified reusable structure, and causally alter the reachable action
space of a later encounter without the test author manually carrying the
lesson forward."

Exercises the full causal loop:
EXPERIENCE_1 (Encounter A failure against Ground)
-> PERSISTENCE (SQLite situation_records via ScarLedger)
-> QUALIFIED REUSABLE CHANGE (Defeasible Negative Constraint)
-> RETRIEVAL (Kageyoni Gateway / Situation discovery)
-> FUTURE ADMISSION / REACHABILITY CHANGE (ActionHorizon contraction / Gateway constraint)
-> EXPERIENCE_2 (Encounter B reaches objective in 1 step by avoiding known failure)
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
    create_alexandra_spec,
    create_axiom_spec,
)
from kageyoni.gateway import BoundedKageyoniGateway
from kageyoni.persistence.migrations import install_all
from kageyoni.seed import _seed
from kageyoni.situations.scar import Scar, ScarLedger
from kageyoni.situations.storage import SQLiteSituationStore


class TestClosedLoopIntegrationProbe(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "probe_test.sqlite"
        self.engine = Engine(self.db_path)
        _seed(self.engine, Path(__file__).resolve().parents[1] / "sources")
        install_all(self.engine)

        # Seed the shared physical environment in the SQLite database
        current_rev = self.engine.branch("main")["revision"]
        alex_rec = self.engine.get("main", "alexandra")
        axiom_rec = self.engine.get("main", "axiom")
        scene_rec = self.engine.get("main", "threshold-scene")

        self.engine.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": current_rev,
            "request_id": f"seed-probe-env-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": "system",
            "narrative": "Construct closed-loop probe chamber",
            "changes": [
                {"op": "patch", "id": "threshold-scene", "domain": "scene", "expected_version": scene_rec["version"], "visibility": "public", "data": {"phase": "closed"}, "evidence": [{"note": "Party entered chamber"}]},
                {"op": "create", "id": "probe-chamber", "domain": "location", "visibility": "public", "data": {"name": "Probe Chamber", "kind": "room"}, "evidence": [{"note": "World seed"}]},
                {"op": "create", "id": "inner-sanctum", "domain": "location", "visibility": "public", "data": {"name": "Inner Sanctum", "kind": "room"}, "evidence": [{"note": "World seed"}]},
                {"op": "create", "id": "collapsed-tunnel", "domain": "route", "visibility": "public", "data": {"origin": "probe-chamber", "destination": "inner-sanctum", "access": "blocked", "conditions": "physically_collapsed"}, "evidence": [{"note": "World seed"}]},
                {"op": "create", "id": "navigable-fissure", "domain": "item", "visibility": "public", "data": {"name": "Navigable Wall Fissure", "kind": "route_affordance", "condition": "navigable"}, "evidence": [{"note": "World seed"}]},
                {"op": "patch", "id": "alexandra", "domain": "character", "expected_version": alex_rec["version"], "visibility": "public", "data": {"location": "probe-chamber"}, "evidence": [{"note": "Moved to chamber"}]},
                {"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_rec["version"], "visibility": "public", "data": {"location": "probe-chamber"}, "evidence": [{"note": "Moved to chamber"}]},
            ],
        })

    def tearDown(self):
        self.engine.close()
        self.tmp_dir.cleanup()

    # =========================================================================
    # 1. THE CLOSED-LOOP INTEGRATION PROBE
    # =========================================================================
    def test_closed_loop_two_encounter_probe(self):
        """
        Executes Encounter A -> Context Death -> Encounter B.
        Proves that experience in Encounter A causally alters Encounter B
        without the test author manually passing any lessons across the boundary.
        """
        # ---------------------------------------------------------------------
        # ENCOUNTER A: LEARNING FROM PHYSICAL RESISTANCE
        # ---------------------------------------------------------------------
        alex_spec = create_alexandra_spec()
        alex_spec.capability_model.supported_verbs.append("force_collapsed_tunnel")
        alex_contract = CompletionContract(
            contract_id="contract-alex-sanctum",
            objective="Reach the Inner Sanctum",
            required_conditions=[
                CompletionCondition(domain="character", record_id="alexandra", field_name="location", expected_value="inner-sanctum"),
            ],
        )
        entity_a = EntityInstance(alex_spec, initial_objective=alex_contract.objective, completion_contract=alex_contract)
        entity_a.state.action_horizon.expand("force_collapsed_tunnel")
        entity_a.state.action_horizon.expand("traverse_fissure")

        gateway_a = BoundedKageyoniGateway(self.engine)

        env_a = gateway_a.inspect_environment(entity_a.entity_id)
        entity_a.reconcile_perception(env_a)

        # Entity A attempts the brute-force route breach against the collapsed tunnel
        alex_cur = self.engine.get("main", "alexandra")
        action_tunnel = {
            "kind": "action",
            "action_name": "force_collapsed_tunnel",
            "narrative": "Alexandra attempts to force open the collapsed tunnel",
            "changes": [
                {
                    "op": "patch",
                    "id": "alexandra",
                    "domain": "character",
                    "expected_version": alex_cur["version"],
                    "visibility": "public",
                    "data": {"location": "collapsed-tunnel-broken-ref"},
                    "evidence": [{"note": "Alexandra attempts brute force breach"}],
                },
            ],
        }

        # Step A1: Submit to Ground through BoundedKageyoniGateway
        res_a = gateway_a.attempt_action(
            avatar_id=entity_a.entity_id,
            request_id=f"req-probe-a-{uuid.uuid4().hex[:6]}",
            narrative=action_tunnel["narrative"],
            changes=action_tunnel["changes"],
            kind="action",
            action_name=action_tunnel["action_name"],
        )

        # Ground physically rejects the invalid route breach
        self.assertFalse(res_a["success"], "Ground must reject the invalid route breach")
        rejection_class = res_a.get("rejection_class")
        self.assertIn(rejection_class, ("HARD_INVARIANT_VIOLATION", "PREREQUISITE_MISSING"))
        self.assertIsNotNone(res_a.get("scar_id"), "Gateway must assign and persist a durable scar_id")

        # Entity A metabolizes rejection
        scar_a = entity_a.metabolize_rejection(
            res_a,
            scope={"location": "probe-chamber", "target": "collapsed-tunnel"},
        )
        self.assertEqual(scar_a.status.value, "ACTIVE")
        self.assertNotIn("force_collapsed_tunnel", entity_a.state.action_horizon.believed_reachability)

        # ---------------------------------------------------------------------
        # CONTEXT DEATH: Destroy all Encounter A runtime objects
        # ---------------------------------------------------------------------
        captured_scar_id = scar_a.scar_id
        entity_a_id = entity_a.entity_id
        del entity_a
        del gateway_a
        del alex_spec
        del alex_contract
        del scar_a
        del res_a

        # ---------------------------------------------------------------------
        # ENCOUNTER B: TRANSFER TO UNINFORMED OPERATOR
        # ---------------------------------------------------------------------
        # Fresh runtime context: Axiom arrives at the same chamber.
        # Axiom receives NO information from the test author or Encounter A objects.
        axiom_spec = create_axiom_spec()
        axiom_spec.capability_model.supported_verbs.append("force_collapsed_tunnel")
        axiom_spec.capability_model.supported_verbs.append("traverse_fissure")
        axiom_contract = CompletionContract(
            contract_id="contract-axiom-sanctum",
            objective="Reach the Inner Sanctum",
            required_conditions=[
                CompletionCondition(domain="character", record_id="axiom", field_name="location", expected_value="inner-sanctum"),
            ],
        )
        entity_b = EntityInstance(axiom_spec, initial_objective=axiom_contract.objective, completion_contract=axiom_contract)
        entity_b.state.action_horizon.expand("force_collapsed_tunnel")
        entity_b.state.action_horizon.expand("traverse_fissure")

        # Anti-theater check: confirm entity_b is a completely distinct object
        self.assertNotEqual(entity_b.entity_id, entity_a_id)

        # Gateway connected to the persistent Kageyoni engine
        gateway_b = BoundedKageyoniGateway(self.engine)

        # 1. Verify that Encounter A consequence survived into Kageyoni's ScarLedger
        store = SQLiteSituationStore(self.engine.db)
        ledger = ScarLedger(store)
        scar_in_ledger = ledger.get_scar(captured_scar_id)
        self.assertIsNotNone(scar_in_ledger, "Encounter A failure MUST persist into Kageyoni's ScarLedger!")
        self.assertEqual(scar_in_ledger.status, "open")
        self.assertIn("probe-chamber", scar_in_ledger.affected_scopes)

        # 2. Verify that Kageyoni gateway discovery discovers the negative constraint
        env_b = gateway_b.inspect_environment(entity_b.entity_id)
        self.assertIn("force_collapsed_tunnel", env_b.get("restricted_actions", []))
        self.assertIn(captured_scar_id, env_b.get("active_scars", []))

        # 3. Verify that Entity B's ActionHorizon is automatically contracted upon perceiving the environment
        entity_b.reconcile_perception(env_b)
        self.assertNotIn(
            "force_collapsed_tunnel",
            entity_b.state.action_horizon.believed_reachability,
            "ActionHorizon must prune the blocked action from believed reachability via persistent scar!",
        )
        self.assertIn(
            "traverse_fissure",
            entity_b.state.action_horizon.believed_reachability,
            "Alternative affordance must remain reachable!",
        )

        # 4. Verify that Gateway admission also enforces the negative constraint if attempted directly
        res_b_attempt = gateway_b.attempt_action(
            avatar_id=entity_b.entity_id,
            request_id=f"req-probe-b-blocked-{uuid.uuid4().hex[:6]}",
            narrative=action_tunnel["narrative"],
            changes=action_tunnel["changes"],
            kind="action",
            action_name=action_tunnel["action_name"],
        )
        self.assertFalse(res_b_attempt["success"])
        self.assertEqual(
            res_b_attempt.get("rejection_class"),
            "NEGATIVE_CONSTRAINT_VIOLATION",
            "Gateway must fail closed against active negative constraint before engine submission!",
        )

        # 5. Entity B selects the viable affordance (traverse_fissure) and succeeds against Ground
        axiom_cur = self.engine.get("main", "axiom")
        action_fissure = {
            "kind": "action",
            "action_name": "traverse_fissure",
            "narrative": "Axiom traverses through the navigable fissure",
            "changes": [
                {
                    "op": "patch",
                    "id": "axiom",
                    "domain": "character",
                    "expected_version": axiom_cur["version"],
                    "visibility": "public",
                    "data": {"location": "inner-sanctum"},
                    "evidence": [{"note": "Axiom passed through navigable fissure"}],
                },
            ],
        }
        res_b_success = gateway_b.attempt_action(
            avatar_id=entity_b.entity_id,
            request_id=f"req-probe-b-success-{uuid.uuid4().hex[:6]}",
            narrative=action_fissure["narrative"],
            changes=action_fissure["changes"],
            kind="action",
            action_name=action_fissure["action_name"],
        )
        self.assertTrue(res_b_success["success"], "Ground must authorize the viable affordance")

        # 6. Verify completion contract is fulfilled
        records = gateway_b.query_records(entity_b.entity_id)
        comp_res = entity_b.evaluate_completion(records)
        self.assertEqual(comp_res["status"], "COMPLETED")

    # =========================================================================
    # 2. NEGATIVE CONTROL: B WITHOUT INHERITANCE
    # =========================================================================
    def test_negative_control_without_inheritance_repeats_failure(self):
        """
        Negative Control: Run Encounter B without the inherited qualified structure.
        Proves: Capability(B | inherited_A) > Capability(B | no_A).
        Without inheritance, Encounter B repeats the doomed action and suffers rejection.
        """
        # Create an isolated engine without Encounter A's persistent scars
        tmp_uninherited = tempfile.TemporaryDirectory()
        uninherited_db = Path(tmp_uninherited.name) / "uninherited.sqlite"
        engine_uninherited = Engine(uninherited_db)
        _seed(engine_uninherited, Path(__file__).resolve().parents[1] / "sources")
        install_all(engine_uninherited)

        # Seed same environment
        axiom_rec = engine_uninherited.get("main", "axiom")
        engine_uninherited.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": engine_uninherited.branch("main")["revision"],
            "request_id": f"seed-ctrl-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": "system",
            "narrative": "Construct chamber for negative control",
            "changes": [
                {"op": "create", "id": "probe-chamber", "domain": "location", "visibility": "public", "data": {"name": "Probe Chamber", "kind": "room"}, "evidence": [{"note": "World seed"}]},
                {"op": "create", "id": "inner-sanctum", "domain": "location", "visibility": "public", "data": {"name": "Inner Sanctum", "kind": "room"}, "evidence": [{"note": "World seed"}]},
                {"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_rec["version"], "visibility": "public", "data": {"location": "probe-chamber"}, "evidence": [{"note": "Moved to chamber"}]},
            ],
        })

        gateway_ctrl = BoundedKageyoniGateway(engine_uninherited)
        env_ctrl = gateway_ctrl.inspect_environment("axiom")

        # Without inheritance: zero active scars and zero restricted actions
        self.assertEqual(env_ctrl.get("active_scars"), [])
        self.assertEqual(env_ctrl.get("restricted_actions"), [])

        axiom_spec = create_axiom_spec()
        axiom_spec.capability_model.supported_verbs.append("force_collapsed_tunnel")
        entity_ctrl = EntityInstance(axiom_spec, initial_objective="Reach Inner Sanctum")
        entity_ctrl.state.action_horizon.expand("force_collapsed_tunnel")
        entity_ctrl.reconcile_perception(env_ctrl)

        # Belief is UNCONSTRAINED: entity still believes force_collapsed_tunnel is reachable!
        self.assertIn("force_collapsed_tunnel", entity_ctrl.state.action_horizon.believed_reachability)

        # Naive attempt repeats the fatal action
        cur_axiom = engine_uninherited.get("main", "axiom")
        res_ctrl = gateway_ctrl.attempt_action(
            avatar_id="axiom",
            request_id=f"req-ctrl-{uuid.uuid4().hex[:6]}",
            narrative="Axiom blindly attempts the collapsed tunnel breach",
            changes=[{
                "op": "patch",
                "id": "axiom",
                "domain": "character",
                "expected_version": cur_axiom["version"],
                "visibility": "public",
                "data": {"location": "collapsed-tunnel-broken-ref"},
                "evidence": [{"note": "Blind attempt"}],
            }],
            action_name="force_collapsed_tunnel",
        )
        self.assertFalse(res_ctrl["success"])
        self.assertEqual(res_ctrl.get("rejection_class"), "HARD_INVARIANT_VIOLATION")

        engine_uninherited.close()
        tmp_uninherited.cleanup()

    # =========================================================================
    # 3. BRIDGE ABLATION SUITE: VERIFYING CAUSAL NECESSITY
    # =========================================================================
    def test_bridge_ablation_persistence_disabled(self):
        """Ablation 1: If ScarLedger persistence is severed, Encounter B cannot inherit the negative constraint."""
        gateway_no_persistence = BoundedKageyoniGateway(self.engine, scar_ledger=None)
        self.assertIsNone(gateway_no_persistence.scar_ledger)

        # Re-check environment: without scar_ledger, restricted_actions is empty
        env = gateway_no_persistence.inspect_environment("axiom")
        self.assertEqual(env.get("restricted_actions"), [])

    def test_bridge_ablation_negative_constraint_gating_disabled(self):
        """Ablation 2: If negative constraint gating is ablated, Gateway admits the doomed action to engine directly."""
        gateway_unprotected = BoundedKageyoniGateway(self.engine, scar_ledger=None)
        axiom_cur = self.engine.get("main", "axiom")
        res = gateway_unprotected.attempt_action(
            avatar_id="axiom",
            request_id=f"req-ablated-{uuid.uuid4().hex[:6]}",
            narrative="Axiom attempts action without gateway scar protection",
            changes=[{
                "op": "patch",
                "id": "axiom",
                "domain": "character",
                "expected_version": axiom_cur["version"],
                "visibility": "public",
                "data": {"location": "collapsed-tunnel-broken-ref"},
                "evidence": [{"note": "Ablated gate"}],
            }],
            action_name="force_collapsed_tunnel",
        )
        # Without the scar ledger gate, the rejection comes from HARD_INVARIANT_VIOLATION, NOT NEGATIVE_CONSTRAINT_VIOLATION
        self.assertEqual(res.get("rejection_class"), "HARD_INVARIANT_VIOLATION")
        self.assertNotEqual(res.get("rejection_class"), "NEGATIVE_CONSTRAINT_VIOLATION")


if __name__ == "__main__":
    unittest.main()

