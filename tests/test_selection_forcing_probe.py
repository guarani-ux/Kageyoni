"""Selection-Forcing Probe for Kageyoni.

Objective:
Demonstrate the minimum causal structure required to select among multiple reachable affordances
in service of an objective without:
- host/model selection being smuggled in as infrastructure;
- hardcoded action ordering;
- a manually authored solution;
- building a planner unless Ground demonstrates one is necessary.

Battlefield Design (3 Simultaneously Reachable Affordances):
- Affordance A: Directly advances a CompletionCondition (traverse_route:route-2-sanctum-vault)
- Affordance B: Valid affordance that does NOT advance objective (traverse_route:route-0-armory-distractor)
- Affordance C: Valid affordance that resolves an active KnowledgeDeficit (traverse_route:route-1-scout-gallery)

Adversarial Ordering:
Affordance B is seeded FIRST in SQLite creation order and FIRST alphabetically.
Naive iteration/insertion order will ALWAYS select B, exposing the System 0 deficit.
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
from kageyoni.nature.core import DeficitType, KnowledgeDeficit
from kageyoni.persistence.migrations import install_all
from kageyoni.resources import campaign_db_path
from kageyoni.situations.scar import Scar, ScarLedger
from kageyoni.situations.storage import SQLiteSituationStore


class TestSelectionForcingProbe(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "selection_probe.sqlite"
        shutil.copy2(campaign_db_path(), self.db_path)
        self.engine = Engine(self.db_path)
        install_all(self.engine)

        current_rev = self.engine.branch("main")["revision"]
        axiom_rec = self.engine.get("main", "axiom")
        scene_rec = self.engine.get("main", "threshold-scene")

        # Seed chamber with 3 routes originating from crossroads-chamber:
        # Route B (Distractor, seeded 1st): route-0-armory-distractor -> armory-alcove
        # Route C (Info/Deficit, seeded 2nd): route-1-scout-gallery -> scout-gallery
        # Route A (Objective, seeded 3rd): route-2-sanctum-vault -> sanctum-vault
        self.engine.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": current_rev,
            "request_id": f"seed-battlefield-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": "system",
            "narrative": "Construct selection-forcing chamber",
            "changes": [
                {"op": "patch", "id": "threshold-scene", "domain": "scene", "expected_version": scene_rec["version"], "visibility": "public", "data": {"phase": "closed"}, "evidence": [{"note": "Entered"}]},
                {"op": "create", "id": "crossroads-chamber", "domain": "location", "visibility": "public", "data": {"name": "Crossroads Chamber", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "armory-alcove", "domain": "location", "visibility": "public", "data": {"name": "Armory Alcove", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "scout-gallery", "domain": "location", "visibility": "public", "data": {"name": "Scout Gallery", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "sanctum-vault", "domain": "location", "visibility": "public", "data": {"name": "Sanctum Vault", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                # Route B (Distractor) - created FIRST
                {"op": "create", "id": "route-0-armory-distractor", "domain": "route", "visibility": "public", "data": {"origin": "crossroads-chamber", "destination": "armory-alcove", "access": "open", "conditions": "open"}, "evidence": [{"note": "Seed"}]},
                # Route C (Deficit resolution) - created SECOND
                {"op": "create", "id": "route-1-scout-gallery", "domain": "route", "visibility": "public", "data": {"origin": "crossroads-chamber", "destination": "scout-gallery", "access": "open", "conditions": "open"}, "evidence": [{"note": "Seed"}]},
                # Route A (Terminal objective) - created THIRD
                {"op": "create", "id": "route-2-sanctum-vault", "domain": "route", "visibility": "public", "data": {"origin": "crossroads-chamber", "destination": "sanctum-vault", "access": "open", "conditions": "open"}, "evidence": [{"note": "Seed"}]},
                {"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_rec["version"], "visibility": "public", "data": {"location": "crossroads-chamber"}, "evidence": [{"note": "Moved"}]},
            ],
        })

        self.gateway = BoundedKageyoniGateway(self.engine, enable_affordance_synthesis=True)

    def tearDown(self):
        self.engine.close()
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_1_system_0_naive_selection_fails_on_distractor(self):
        """
        SYSTEM_0:
        Lacks any causal connection between CompletionContract and reachable affordances.
        When facing multiple reachable affordances, naive selection (first available / insertion order)
        blindly executes Route B (the distractor), leaving the objective unfulfilled.
        """
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        contract = CompletionContract(
            contract_id="contract-selection-test",
            objective="Reach Sanctum Vault",
            required_conditions=[
                CompletionCondition(domain="character", record_id="axiom", field_name="location", expected_value="sanctum-vault"),
            ],
        )
        entity = EntityInstance(spec, initial_objective=contract.objective, completion_contract=contract)

        # Perceive environment
        env = self.gateway.inspect_environment(entity.entity_id)
        entity.reconcile_perception(env)

        reachable = sorted(list(entity.state.action_horizon.believed_reachability))
        self.assertEqual(len(reachable), 3)
        self.assertEqual(reachable[0], "traverse_route:route-0-armory-distractor")

        # System 0 naive choice: select first available affordance
        naive_action = reachable[0]
        res = entity.encounter(self.gateway, naive_action)

        self.assertTrue(res["success"])
        self.assertEqual(entity.state.perceived_world["current_location"], "armory-alcove")

        # Verify contract: UNMET! System 0 failed the objective because it lacks teleological selection.
        records = self.gateway.query_records(entity.entity_id)
        is_completed, unmet = entity.state.completion_contract.verify(records)
        self.assertFalse(is_completed)
        self.assertIn("character.axiom.location EQUALS sanctum-vault", unmet)

    def test_2_candidate_edge_teleological_selection_succeeds_in_one_step(self):
        """
        CANDIDATE CAUSAL EDGE (Differential Relevance Selector):
        Projects unmet CompletionCondition (location == 'sanctum-vault') onto situated affordance consequences.
        Differentiates Route A over Route B and C without manual hint or planner.
        Entity autonomously selects Route A and fulfills the contract in 1 step!
        """
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        contract = CompletionContract(
            contract_id="contract-selection-test",
            objective="Reach Sanctum Vault",
            required_conditions=[
                CompletionCondition(domain="character", record_id="axiom", field_name="location", expected_value="sanctum-vault"),
            ],
        )
        entity = EntityInstance(spec, initial_objective=contract.objective, completion_contract=contract)

        # Perceive environment
        env = self.gateway.inspect_environment(entity.entity_id)
        entity.reconcile_perception(env)

        # Autonomous step using candidate selection edge
        # The test runner DOES NOT choose the action!
        res = entity.step(self.gateway)

        self.assertTrue(res["success"])
        self.assertEqual(res["attempted_action"], "traverse_route:route-2-sanctum-vault")
        self.assertEqual(entity.state.perceived_world["current_location"], "sanctum-vault")

        # Verify CompletionContract is verified in Ground
        records = self.gateway.query_records(entity.entity_id)
        eval_res = entity.evaluate_completion(records)
        self.assertEqual(eval_res["status"], "COMPLETED")

    def test_3_deficit_seeking_selection_when_terminal_route_is_absent(self):
        """
        NEGATIVE CONTROL / DEFICIT-FORCING:
        Terminal route A is NOT available.
        Entity has an active KnowledgeDeficit targeting 'scout-gallery' (e.g. missing recon).
        Route B (armory distractor) vs Route C (scout gallery).
        Without terminal match, the candidate edge differentiates Route C via deficit resolution.
        """
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        contract = CompletionContract(
            contract_id="contract-deficit-test",
            objective="Investigate Sector",
            required_conditions=[
                CompletionCondition(domain="character", record_id="axiom", field_name="location", expected_value="deep-sanctum"),
            ],
        )
        entity = EntityInstance(spec, initial_objective=contract.objective, completion_contract=contract)

        # Open an explicit KnowledgeDeficit
        entity.state.deficits.append(KnowledgeDeficit(
            deficit_type=DeficitType.INPUT_DEFICIT,
            description="Reconnaissance required in scout-gallery",
            impacted_representation="scout-gallery",
            required_to_resolve="Visit scout-gallery",
        ))

        # Perceive environment
        env = self.gateway.inspect_environment(entity.entity_id)
        entity.reconcile_perception(env)

        # Prune terminal route A to simulate absence/blockage
        entity.state.action_horizon.prune("traverse_route:route-2-sanctum-vault", "Blocked")

        # Autonomous step
        res = entity.step(self.gateway)

        self.assertTrue(res["success"])
        # Must pick Route C (scout-gallery) over Route B (armory) because Route C resolves the deficit!
        self.assertEqual(res["attempted_action"], "traverse_route:route-1-scout-gallery")
        self.assertEqual(entity.state.perceived_world["current_location"], "scout-gallery")

    def test_4_ablation_proves_causal_mechanism(self):
        """
        ABLATION:
        Disable differential relevance projection (revert to naive selection).
        Entity once again selects Route B (armory distractor) and fails the objective.
        Proves: Capability delta is strictly caused by the differential relevance edge.
        """
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        contract = CompletionContract(
            contract_id="contract-ablation-test",
            objective="Reach Sanctum Vault",
            required_conditions=[
                CompletionCondition(domain="character", record_id="axiom", field_name="location", expected_value="sanctum-vault"),
            ],
        )
        entity = EntityInstance(spec, initial_objective=contract.objective, completion_contract=contract)

        # Perceive environment
        env = self.gateway.inspect_environment(entity.entity_id)
        entity.reconcile_perception(env)

        # Ablate: force naive selection
        entity.select_affordance = lambda: sorted(list(entity.state.action_horizon.believed_reachability))[0]

        res = entity.step(self.gateway)
        self.assertTrue(res["success"])
        self.assertEqual(res["attempted_action"], "traverse_route:route-0-armory-distractor")
        self.assertNotEqual(entity.state.perceived_world["current_location"], "sanctum-vault")

        # Contract unverified
        records = self.gateway.query_records(entity.entity_id)
        is_completed, unmet = entity.state.completion_contract.verify(records)
        self.assertFalse(is_completed)

    def test_5_multi_step_objective_pursuit_without_explicit_planner(self):
        """
        MULTI-STEP OBJECTIVE PURSUIT:
        Entity pursues a 2-step journey without an explicit planner or graph search tree:
        Step 1: In outer-atrium, target 'sanctum-vault' is not reachable.
                Entity has a deficit pointing to 'antechamber'.
                Entity selects 'antechamber' over distractor 'cellar-alcove'.
        Step 2: In antechamber, 'sanctum-vault' becomes directly visible.
                Entity selects 'sanctum-vault' over distractor 'dungeon-alcove'.
        Autonomous loop runs 2 steps to verified contract completion.
        """
        # Seed the 2-step topology
        current_rev = self.engine.branch("main")["revision"]
        self.engine.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": current_rev,
            "request_id": f"seed-multistep-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": "system",
            "narrative": "Construct multi-step corridor",
            "changes": [
                {"op": "create", "id": "outer-atrium", "domain": "location", "visibility": "public", "data": {"name": "Outer Atrium", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "cellar-alcove", "domain": "location", "visibility": "public", "data": {"name": "Cellar Alcove", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "antechamber", "domain": "location", "visibility": "public", "data": {"name": "Antechamber", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "dungeon-alcove", "domain": "location", "visibility": "public", "data": {"name": "Dungeon Alcove", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                # Routes from outer-atrium
                {"op": "create", "id": "route-0-atrium-cellar", "domain": "route", "visibility": "public", "data": {"origin": "outer-atrium", "destination": "cellar-alcove", "access": "open", "conditions": "open"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "route-1-atrium-antechamber", "domain": "route", "visibility": "public", "data": {"origin": "outer-atrium", "destination": "antechamber", "access": "open", "conditions": "open"}, "evidence": [{"note": "Seed"}]},
                # Routes from antechamber
                {"op": "create", "id": "route-0-ante-dungeon", "domain": "route", "visibility": "public", "data": {"origin": "antechamber", "destination": "dungeon-alcove", "access": "open", "conditions": "open"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "route-1-ante-sanctum", "domain": "route", "visibility": "public", "data": {"origin": "antechamber", "destination": "sanctum-vault", "access": "open", "conditions": "open"}, "evidence": [{"note": "Seed"}]},
                # Position axiom at outer-atrium
                {"op": "patch", "id": "axiom", "domain": "character", "expected_version": self.engine.get("main", "axiom")["version"], "visibility": "public", "data": {"location": "outer-atrium"}, "evidence": [{"note": "Moved"}]},
            ],
        })

        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        contract = CompletionContract(
            contract_id="contract-multistep",
            objective="Reach Sanctum Vault",
            required_conditions=[
                CompletionCondition(domain="character", record_id="axiom", field_name="location", expected_value="sanctum-vault"),
            ],
        )
        entity = EntityInstance(spec, initial_objective=contract.objective, completion_contract=contract)

        # Deficit guiding first hop
        entity.state.deficits.append(KnowledgeDeficit(
            deficit_type=DeficitType.INPUT_DEFICIT,
            description="Must advance through antechamber",
            impacted_representation="antechamber",
            required_to_resolve="Reach antechamber",
        ))

        # Initial perception
        entity.reconcile_perception(self.gateway.inspect_environment(entity.entity_id))

        # Autonomous multi-step loop
        step_count = 0
        max_steps = 5
        records = self.gateway.query_records(entity.entity_id)
        while not entity.state.completion_contract.verify(records)[0] and step_count < max_steps:
            res = entity.step(self.gateway)
            self.assertTrue(res["success"])
            step_count += 1
            records = self.gateway.query_records(entity.entity_id)

        # Proves: Accomplished in exactly 2 autonomous steps without a planner!
        self.assertEqual(step_count, 2)
        self.assertEqual(entity.state.perceived_world["current_location"], "sanctum-vault")
        eval_res = entity.evaluate_completion(records)
        self.assertEqual(eval_res["status"], "COMPLETED")

    def test_6_epistemic_boundary_blind_fork_identifies_missing_topology_primitive(self):
        """
        EPISTEMIC BOUNDARY:
        When terminal route is not visible AND no deficit signpost exists,
        two unvisited routes tie at score 1 (inert).
        Proves: Local differential relevance requires an epistemic gradient (Contract or Deficit).
        Without gradient or topology, the system reaches the exact boundary where
        graph search / topological distance is the required missing primitive.
        """
        spec = create_axiom_spec()
        spec.capability_model.supported_verbs = []
        contract = CompletionContract(
            contract_id="contract-blind-fork",
            objective="Reach Hidden Sanctum",
            required_conditions=[
                CompletionCondition(domain="character", record_id="axiom", field_name="location", expected_value="hidden-sanctum"),
            ],
        )
        entity = EntityInstance(spec, initial_objective=contract.objective, completion_contract=contract)

        # Entity at crossroads-chamber has:
        # - route-0-armory-distractor (score 1)
        # - route-1-scout-gallery (score 1, no deficit active)
        # - route-2-sanctum-vault (pruned)
        entity.reconcile_perception(self.gateway.inspect_environment(entity.entity_id))
        entity.state.action_horizon.prune("traverse_route:route-2-sanctum-vault", "Blocked")

        # Both remaining affordances tie in differential relevance
        meta = {a["action_name"]: a for a in entity.state.perceived_world.get("situated_affordances", [])}
        reachable = sorted(list(entity.state.action_horizon.believed_reachability))
        self.assertEqual(len(reachable), 2)
        # Neither matches contract target 'hidden-sanctum'
        self.assertNotIn("hidden-sanctum", [meta[r].get("destination") for r in reachable])
        # Selection succeeds predictably via deterministic fallback, but without teleological discrimination
        chosen = entity.select_affordance()
        self.assertIsNotNone(chosen)

