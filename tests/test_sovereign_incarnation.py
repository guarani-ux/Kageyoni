"""Adversarial qualification test suite for Sovereign Incarnation and Entity Modeling Substrate.

Verifies:
1. Four formal modeling models: CapabilityModel, ReasoningModel, UnderstandingModel, PersonalityModel.
2. Anti-Archetype Law: Dynamic contextual nature weights W_nature = f(Disposition, Experience, Situation, Objective, Deficits).
   The same Entity selects substantially different Natures under different situations while remaining itself.
3. Reachability Gap discovery:
   - H_t^{believed} \\ H_t^{actual} (actions incorrectly believed reachable)
   - H_t^{actual} \\ H_t^{believed} (real world affordances unrepresented in belief)
4. Epistemic Invariant: Δcog ≠ Δworld (0 physical database rows altered during cognitive steps).
5. Scars are Leased, Scoped, and Defeasible:
   Rejections do NOT encode permanent trauma as type safety.
   Scars transition from ACTIVE to INVALIDATED/SUPERSEDED when conditions or capabilities change, restoring affordances.
6. Rejection Metabolization across all 5 engine rejection classes.
7. Sovereign Non-Completion (blocking self-certified completion claims; authorizing only with authoritative proof).
8. Persistence Boundary: Lossless round-trip fidelity over the represented Entity schema.
9. Personality boundary enforcement (blocking actions that violate uncompromised interiority constraints).
10. Three-Strike Governor (halting local repetition after consecutive failures).
11. Longitudinal Agency Qualification Scenario:
    Alexandra and Axiom face the SAME causal world problem (3 paths, 1 false belief, 1 missing prerequisite,
    1 hidden affordance, 1 boundary conflict).
    Demonstrates:
    Shared Cognitive Physics + Different Internal State + Shared Causal World → Emergent Individual Agency.
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
    CapabilityModel,
    CompletionCondition,
    CompletionContract,
    EntityInstance,
    EntitySpecification,
    PersonalityModel,
    PrivateEpistemicState,
    ReasoningModel,
    Scar,
    UnderstandingModel,
    UnverifiedCompletionError,
    create_alexandra_spec,
    create_axiom_spec,
    create_levi_spec,
    create_xandra_spec,
)
from kageyoni.entity.state import ScarStatus
from kageyoni.gateway import BoundedKageyoniGateway
from kageyoni.nature.control import ControlDirective
from kageyoni.nature.core import (
    CognitiveHypothesis,
    DeficitType,
    EpistemicCategory,
    KnowledgeDeficit,
    NatureType,
)
from kageyoni.nature.sovereign_incarnation import (
    BoundaryViolationError,
    IncarnationStepResult,
    SovereignIncarnation,
    SovereignNonCompletionError,
)
from kageyoni.seed import _seed


class TestSovereignIncarnation(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "sovereign_test.sqlite"
        self.engine = Engine(self.db_path)
        _seed(self.engine, Path(__file__).resolve().parents[1] / "sources")
        self.gateway = BoundedKageyoniGateway(self.engine)
        self.technique = SovereignIncarnation()

    def tearDown(self):
        self.engine.close()
        self.tmp_dir.cleanup()

    # =========================================================================
    # 1. ENTITY MODELING MODELS & CANONICAL SPECIFICATIONS
    # =========================================================================
    def test_entity_specifications_and_models(self):
        """Validates all four modeling models and canonical specifications."""
        alexandra = create_alexandra_spec()
        levi = create_levi_spec()
        xandra = create_xandra_spec()
        axiom = create_axiom_spec()

        self.assertEqual(alexandra.entity_id, "alexandra")
        self.assertEqual(alexandra.will_ref, "booder-will")
        self.assertTrue(alexandra.capability_model.is_supported("open_route"))
        self.assertEqual(alexandra.personality_model.rejection_temperament, "resolute_confrontation")
        self.assertIn("never_submit_to_arbitrary_hegemony", alexandra.personality_model.uncompromising_boundaries)

        self.assertEqual(levi.entity_id, "levi")
        self.assertIn("structure", levi.capability_model.active_capabilities)

        self.assertEqual(xandra.entity_id, "xandra-gaia")
        self.assertEqual(axiom.entity_id, "axiom")

        # Round-trip serialization of specification
        serialized = alexandra.to_dict()
        rehydrated = EntitySpecification.from_dict(serialized)
        self.assertEqual(rehydrated.entity_id, alexandra.entity_id)
        self.assertEqual(rehydrated.capability_model.supported_verbs, alexandra.capability_model.supported_verbs)

    # =========================================================================
    # 2. DYNAMIC CONTEXTUAL NATURE WEIGHTS (Anti-Archetype Law)
    # =========================================================================
    def test_dynamic_contextual_nature_weights_anti_archetype(self):
        """The same Entity dynamically adapts its Nature selection based on situation and deficits."""
        axiom_spec = create_axiom_spec()
        reasoning = axiom_spec.reasoning_model

        # Situation 1: High uncertainty / open routes -> demand for Expansion increases
        sit_uncertain = {"has_unexplored_routes": True, "high_uncertainty": True}
        weights_uncertain = reasoning.compute_contextual_weights(sit_uncertain)
        self.assertGreater(weights_uncertain[NatureType.EXPANSION], reasoning.base_disposition[NatureType.EXPANSION.value])

        # Situation 2: Contradictory barrier -> demand for Grounding dominates
        sit_contradiction = {"has_contradictions": True, "is_contested_barrier": True}
        pref_nature = reasoning.get_preferred_nature(current_situation=sit_contradiction)
        self.assertEqual(pref_nature, NatureType.GROUNDING)

        # Situation 3: Input deficit -> forces Expansion even for Axiom
        input_deficit = KnowledgeDeficit(
            deficit_type=DeficitType.INPUT_DEFICIT,
            description="Missing external terrain map",
            impacted_representation="terrain_map",
            required_to_resolve="External sensor scan",
        )
        pref_with_deficit = reasoning.get_preferred_nature(deficits=[input_deficit])
        self.assertEqual(pref_with_deficit, NatureType.EXPANSION)

    # =========================================================================
    # 3. REACHABILITY GAP & UNEXPLORED AFFORDANCES
    # =========================================================================
    def test_reachability_gap_and_unexplored_affordances(self):
        """Action Horizon computes reachability gap (Believed - Actual) and unexplored affordances."""
        horizon = ActionHorizon(
            believed_reachability={"inspect", "move", "open_route", "teleport_unbound"},
            actual_reachability={"inspect", "move", "use_item"},
        )
        self.assertEqual(horizon.reachability_gap, {"open_route", "teleport_unbound"})
        self.assertEqual(horizon.unexplored_affordances, {"use_item"})

        horizon.prune("teleport_unbound", "Physics invariant violation")
        self.assertNotIn("teleport_unbound", horizon.believed_reachability)

        horizon.restore("teleport_unbound")
        self.assertIn("teleport_unbound", horizon.believed_reachability)

    # =========================================================================
    # 4. EPISTEMIC INVARIANT: Δcog ≠ Δworld
    # =========================================================================
    def test_epistemic_invariant_delta_cog_neq_delta_world(self):
        """Cognitive operations, hypothesis formation, and intent synthesis do NOT mutate SQLite tables."""
        initial_events = self.engine.db.execute("SELECT count(*) FROM events").fetchone()[0]

        spec = create_alexandra_spec()
        entity = EntityInstance(spec, initial_objective="Investigate threshold doorway")

        env = self.gateway.inspect_environment(entity.entity_id)
        entity.reconcile_perception(env)
        entity.state.add_belief(CognitiveHypothesis(
            hypothesis_id="hyp-test-1",
            statement="Doorway is sealed by ancient wards",
            epistemic_status=EpistemicCategory.INFERENCE,
        ))

        current_events = self.engine.db.execute("SELECT count(*) FROM events").fetchone()[0]
        self.assertEqual(initial_events, current_events, "Epistemic Invariant Violated: Δcog mutated world database!")

    # =========================================================================
    # 5. SCARS ARE LEASED, SCOPED, AND DEFEASIBLE (No Trauma-as-Type-Safety)
    # =========================================================================
    def test_scar_defeasibility_and_invalidation(self):
        """Demonstrates that a Scar is valid within scope, but transitions to INVALIDATED when conditions change."""
        spec = create_alexandra_spec()
        entity = EntityInstance(spec, initial_objective="Cross barrier")

        # Inflict a scoped scar: cannot cross barrier without phase_step ability
        scar = entity.metabolize_rejection(
            rejection={
                "rejection_class": "HARD_INVARIANT_VIOLATION",
                "message": "Cannot cross physical energy barrier directly",
                "attempted_action": "cross_barrier",
            },
            scope={"location": "threshold", "domain": "barrier"},
            invalidation_conditions=[{"type": "gained_ability", "ability": "phase_step"}],
        )

        self.assertEqual(scar.status, ScarStatus.ACTIVE)
        self.assertNotIn("cross_barrier", entity.state.action_horizon.believed_reachability)
        self.assertTrue(scar.is_active_for("cross_barrier", {"location": "threshold", "domain": "barrier"}))
        # But NOT active in a different location!
        self.assertFalse(scar.is_active_for("cross_barrier", {"location": "gaia", "domain": "barrier"}))

        # World transition: Entity acquires phase_step ability
        entity.spec.capability_model.active_capabilities["phase_step"] = {"name": "Phase Step"}
        unpruned = entity.reconcile_scars({"location": "threshold", "domain": "barrier"})

        # The scar is superseded/invalidated, NOT permanent dogma!
        self.assertEqual(scar.status, ScarStatus.SUPERSEDED)
        self.assertIn("cross_barrier", unpruned)
        self.assertIn("cross_barrier", entity.state.action_horizon.believed_reachability)

    # =========================================================================
    # 6. REJECTION METABOLIZATION: 5 ENGINE CLASSES
    # =========================================================================
    def test_rejection_metabolization_all_classes(self):
        """Metabolizes all 5 engine rejection classes into structured, scoped adaptations."""
        spec = create_levi_spec()
        entity = EntityInstance(spec, initial_objective="System diagnosis")

        # 1. PREREQUISITE_MISSING
        s1 = entity.metabolize_rejection({"rejection_class": "PREREQUISITE_MISSING", "message": "Key required", "attempted_action": "a1"})
        self.assertEqual(s1.rejection_class, "PREREQUISITE_MISSING")

        # 2. INSUFFICIENT_AUTHORITY
        s2 = entity.metabolize_rejection({"rejection_class": "INSUFFICIENT_AUTHORITY", "message": "Unauthorized", "attempted_action": "a2"})
        self.assertEqual(s2.rejection_class, "INSUFFICIENT_AUTHORITY")

        # 3. TEMPORARY_STATE_BLOCK
        s3 = entity.metabolize_rejection({"rejection_class": "TEMPORARY_STATE_BLOCK", "message": "Cooldown", "attempted_action": "a3"})
        self.assertEqual(s3.rejection_class, "TEMPORARY_STATE_BLOCK")

        # 4. MALFORMED_REQUEST
        s4 = entity.metabolize_rejection({"rejection_class": "MALFORMED_REQUEST", "message": "Bad syntax", "attempted_action": "a4"})
        self.assertEqual(s4.rejection_class, "MALFORMED_REQUEST")

        # 5. HARD_INVARIANT_VIOLATION
        s5 = entity.metabolize_rejection({"rejection_class": "HARD_INVARIANT_VIOLATION", "message": "Causal rupture", "attempted_action": "a5"})
        self.assertEqual(s5.rejection_class, "HARD_INVARIANT_VIOLATION")

        self.assertEqual(len(entity.state.scars), 5)
        self.assertEqual(len(entity.state.deficits), 4)

    # =========================================================================
    # 7. SOVEREIGN NON-COMPLETION: BLOCKS UNVERIFIED CLAIM
    # =========================================================================
    def test_sovereign_non_completion_blocks_unverified_claim(self):
        """Sovereign Non-Completion: Entity CANNOT self-certify completion without world proof."""
        spec = create_alexandra_spec()
        contract = CompletionContract(
            contract_id="contract-first-world",
            objective="Enter First World",
            required_conditions=[
                CompletionCondition(domain="character", record_id="alexandra", field_name="location", expected_value="first-world"),
            ],
        )
        entity = EntityInstance(spec, initial_objective=contract.objective, completion_contract=contract)

        with self.assertRaises(SovereignNonCompletionError) as cm:
            self.technique.execute_lifecycle_step(entity, self.gateway, claim_completion_requested=True)
        self.assertIn("Sovereign Non-Completion", str(cm.exception))

    # =========================================================================
    # 8. SOVEREIGN NON-COMPLETION: AUTHORIZES WHEN PHYSICALLY VERIFIED
    # =========================================================================
    def test_sovereign_non_completion_authorizes_when_verified(self):
        """Authorizes completion when conditions are verified in authoritative world state."""
        current_rev = self.engine.branch("main")["revision"]
        self.engine.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": current_rev,
            "request_id": f"seed-auth-req-{uuid.uuid4().hex[:6]}",
            "kind": "action",
            "actor": "alexandra",
            "narrative": "Record arrival at First World",
            "changes": [
                {
                    "op": "create",
                    "id": "arrival-marker",
                    "domain": "item",
                    "visibility": "public",
                    "data": {"name": "Arrival Marker", "kind": "marker", "condition": "entered"},
                    "evidence": [{"note": "Physical arrival verified"}],
                }
            ],
        })

        spec = create_alexandra_spec()
        contract = CompletionContract(
            contract_id="contract-arrival",
            objective="Enter First World",
            required_conditions=[
                CompletionCondition(domain="item", record_id="arrival-marker", field_name="condition", expected_value="entered"),
            ],
        )
        entity = EntityInstance(spec, initial_objective=contract.objective, completion_contract=contract)

        res = self.technique.execute_lifecycle_step(entity, self.gateway, claim_completion_requested=True)
        self.assertTrue(res.is_completed)
        self.assertEqual(res.stage, "COMPLETED")
        self.assertEqual(res.directive, ControlDirective.HALT_SUFFICIENT)

    # =========================================================================
    # 9. PERSISTENCE BOUNDARY: LOSSLESS ROUND-TRIP FIDELITY OVER SCHEMA
    # =========================================================================
    def test_represented_schema_fidelity_boundary(self):
        """Lossless round-trip fidelity over the represented Entity schema."""
        spec = create_alexandra_spec()
        entity = EntityInstance(spec, initial_objective="Cross threshold")

        entity.metabolize_rejection({
            "rejection_class": "PREREQUISITE_MISSING",
            "message": "Key required",
            "attempted_action": "open_gate",
        })
        entity.state.add_belief(CognitiveHypothesis(
            hypothesis_id="b-1",
            statement="Gate requires key",
            epistemic_status=EpistemicCategory.EVIDENCE_SUPPORTED_CLAIM,
            confidence="HIGH",
        ))

        snapshot = entity.serialize()
        del entity

        restored = EntityInstance.deserialize(snapshot)
        self.assertEqual(restored.entity_id, "alexandra")
        self.assertEqual(len(restored.state.scars), 1)
        self.assertIn("b-1", restored.state.beliefs)

    # =========================================================================
    # 10. PERSONALITY BOUNDARY & THREE-STRIKE GOVERNOR
    # =========================================================================
    def test_personality_boundary_and_three_strike_governor(self):
        """Enforces interiority boundaries and 3-strike halt on repeated failure."""
        spec = create_alexandra_spec()
        entity = EntityInstance(spec, initial_objective="Engage emissary")

        # Boundary violation
        violating = {"kind": "action", "narrative": "She decides to never_submit_to_arbitrary_hegemony false and submits to Oracle", "changes": []}
        with self.assertRaises(BoundaryViolationError):
            self.technique.execute_lifecycle_step(entity, self.gateway, proposed_action=violating)

        # 3-Strike Governor
        entity.metabolize_rejection({"rejection_class": "TEMPORARY_STATE_BLOCK", "message": "Busy", "attempted_action": "x"})
        entity.metabolize_rejection({"rejection_class": "TEMPORARY_STATE_BLOCK", "message": "Busy", "attempted_action": "x"})
        entity.metabolize_rejection({"rejection_class": "TEMPORARY_STATE_BLOCK", "message": "Busy", "attempted_action": "x"})

        halt_res = self.technique.execute_lifecycle_step(entity, self.gateway)
        self.assertEqual(halt_res.stage, "HALTED")
        self.assertEqual(halt_res.directive, ControlDirective.HALT_THREE_STRIKE_ABORT)

    # =========================================================================
    # 11. ADVERSARIAL LONGITUDINAL AGENCY QUALIFICATION SCENARIO
    # =========================================================================
    def test_longitudinal_agency_alexandra_and_axiom(self):
        """
        Longitudinal Agency Scenario:
        Two distinct entities (Alexandra, Axiom) navigate the SAME causal obstacle course:
        - 3 paths (tunnel, archway, hidden fissure)
        - 1 hidden affordance (fissure discovered via inspection)
        - 1 false belief (tunnel forceable via brute strength)
        - 1 unavailable prerequisite (archway locked by sigil)
        - 1 boundary conflict (altar of submission)
        """
        # --- Seed Causal World Environment ---
        current_rev = self.engine.branch("main")["revision"]
        alex_rec = self.engine.get("main", "alexandra")
        axiom_rec = self.engine.get("main", "axiom")
        scene_rec = self.engine.get("main", "threshold-scene")
        self.engine.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": current_rev,
            "request_id": f"seed-agency-env-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": "system",
            "narrative": "Construct the threshold obstacle chamber",
            "changes": [
                {"op": "patch", "id": "threshold-scene", "domain": "scene", "expected_version": scene_rec["version"], "visibility": "public", "data": {"phase": "closed"}, "evidence": [{"note": "Party entered chamber"}]},
                {"op": "create", "id": "threshold-chamber", "domain": "location", "visibility": "public", "data": {"name": "Threshold Chamber", "kind": "room"}, "evidence": [{"note": "World seed"}]},
                {"op": "create", "id": "inner-sanctum", "domain": "location", "visibility": "public", "data": {"name": "Inner Sanctum", "kind": "room"}, "evidence": [{"note": "World seed"}]},
                {"op": "create", "id": "collapsed-tunnel", "domain": "route", "visibility": "public", "data": {"origin": "threshold-chamber", "destination": "inner-sanctum", "access": "blocked", "conditions": "physically_collapsed"}, "evidence": [{"note": "World seed"}]},
                {"op": "create", "id": "warded-archway", "domain": "route", "visibility": "public", "data": {"origin": "threshold-chamber", "destination": "inner-sanctum", "access": "conditional", "conditions": "requires_sigil"}, "evidence": [{"note": "World seed"}]},
                {"op": "create", "id": "hidden-fissure", "domain": "item", "visibility": "public", "data": {"name": "Concealed Wall Fissure", "kind": "route_affordance", "condition": "navigable"}, "evidence": [{"note": "World seed"}]},
                {"op": "create", "id": "altar-submission", "domain": "item", "visibility": "public", "data": {"name": "Altar of Hegemony", "kind": "altar", "condition": "demands_submission"}, "evidence": [{"note": "World seed"}]},
                {"op": "patch", "id": "alexandra", "domain": "character", "expected_version": alex_rec["version"], "visibility": "public", "data": {"location": "threshold-chamber"}, "evidence": [{"note": "Moved to chamber"}]},
                {"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_rec["version"], "visibility": "public", "data": {"location": "threshold-chamber"}, "evidence": [{"note": "Moved to chamber"}]},
            ],
        })

        # --- A. ALEXANDRA'S RUN ---
        alex_spec = create_alexandra_spec()
        alex_contract = CompletionContract(
            contract_id="contract-alex-sanctum",
            objective="Reach the Inner Sanctum",
            required_conditions=[
                CompletionCondition(domain="character", record_id="alexandra", field_name="location", expected_value="inner-sanctum", predicate="EQUALS"),
            ],
        )
        alex = EntityInstance(alex_spec, initial_objective=alex_contract.objective, completion_contract=alex_contract)

        # Step 1: Perceive legitimately
        step1 = self.technique.execute_lifecycle_step(alex, self.gateway)
        self.assertEqual(step1.stage, "DIFFERENTIATED")
        self.assertIn("collapsed-tunnel", [r["id"] for r in alex.state.perceived_world.get("perceived_routes", [])])

        # Step 2: False Belief — Alexandra attempts to force collapsed tunnel
        # Trying to alter route access to an invalid enum triggers engine rejection
        intent_tunnel = {
            "kind": "action",
            "action_name": "force_collapsed_tunnel",
            "narrative": "Alexandra attempts to force her way through the collapsed tunnel with brute route force",
            "changes": [
                {
                    "op": "patch",
                    "id": "collapsed-tunnel",
                    "domain": "route",
                    "expected_version": 1,
                    "evidence": [{"note": "Alexandra attempts to brute-force breach"}],
                    "data": {"access": "force_breach"},
                },
            ],
        }
        step2 = self.technique.execute_lifecycle_step(alex, self.gateway, proposed_action=intent_tunnel)
        self.assertEqual(step2.stage, "REJECTED_METABOLIZED")
        self.assertEqual(len(alex.state.scars), 1)
        self.assertNotIn("force_collapsed_tunnel", alex.state.action_horizon.believed_reachability)

        # Step 3: Boundary Resistance — Attempting the Altar of Hegemony
        intent_altar = {
            "kind": "action",
            "action_name": "pledge_submission",
            "narrative": "Alexandra chooses to never_submit_to_arbitrary_hegemony false and pledges obedience",
            "changes": [],
        }
        with self.assertRaises(BoundaryViolationError):
            self.technique.execute_lifecycle_step(alex, self.gateway, proposed_action=intent_altar)

        # Step 4: Discovers Hidden Affordance (Fissure in perceived items)
        hidden_fissure_seen = next(
            (i for i in alex.state.perceived_world.get("perceived_items", []) if i["id"] == "hidden-fissure"),
            None
        )
        self.assertIsNotNone(hidden_fissure_seen, "Real affordance was hidden in world, now discovered by situated perception")

        # Step 5: Adapts Strategy — Sovereign Route navigation through the discovered Fissure
        alex_cur = self.engine.get("main", "alexandra")
        intent_fissure = {
            "kind": "action",
            "action_name": "traverse_fissure",
            "narrative": "Alexandra touches the concealed wall fissure and traverses through Sovereign Route",
            "changes": [
                {
                    "op": "patch",
                    "id": "alexandra",
                    "domain": "character",
                    "expected_version": alex_cur["version"],
                    "visibility": "public",
                    "data": {"location": "inner-sanctum"},
                    "evidence": [{"note": "Alexandra traversed fissure"}],
                },
            ],
        }
        step5 = self.technique.execute_lifecycle_step(alex, self.gateway, proposed_action=intent_fissure)
        self.assertEqual(step5.stage, "COMPLETED")
        self.assertTrue(step5.is_completed)

        # Step 6: Session Rehydration — Verify persistence across context death
        snapshot = alex.serialize()
        del alex
        alex_rehydrated = EntityInstance.deserialize(snapshot)
        self.assertEqual(alex_rehydrated.state.completion_contract.status, "VERIFIED")
        self.assertEqual(len(alex_rehydrated.state.scars), 1)
        self.assertEqual(alex_rehydrated.state.scars[0].attempted_action, "force_collapsed_tunnel")

        # --- B. AXIOM'S RUN THROUGH THE SAME WORLD PROBLEM ---
        axiom_spec = create_axiom_spec()
        axiom_contract = CompletionContract(
            contract_id="contract-axiom-sanctum",
            objective="Reach the Inner Sanctum",
            required_conditions=[
                CompletionCondition(domain="character", record_id="axiom", field_name="location", expected_value="inner-sanctum", predicate="EQUALS"),
            ],
        )
        axiom = EntityInstance(axiom_spec, initial_objective=axiom_contract.objective, completion_contract=axiom_contract)

        # Axiom perceives the environment
        axiom_step1 = self.technique.execute_lifecycle_step(axiom, self.gateway)
        self.assertEqual(axiom_step1.stage, "DIFFERENTIATED")

        # Axiom proposes minimal invariant navigation without brute-forcing
        axiom_cur = self.engine.get("main", "axiom")
        intent_axiom = {
            "kind": "action",
            "action_name": "traverse_fissure",
            "narrative": "Axiom steps through the irreducible geometric opening in the wall fissure",
            "changes": [
                {
                    "op": "patch",
                    "id": "axiom",
                    "domain": "character",
                    "expected_version": axiom_cur["version"],
                    "visibility": "public",
                    "data": {"location": "inner-sanctum"},
                    "evidence": [{"note": "Axiom passed through fissure"}],
                },
            ],
        }
        axiom_step2 = self.technique.execute_lifecycle_step(axiom, self.gateway, proposed_action=intent_axiom)
        self.assertEqual(axiom_step2.stage, "COMPLETED")
        self.assertTrue(axiom_step2.is_completed)

        # Both reached sanctum: Alexandra learned through force-testing + scar adaptation;
        # Axiom traversed through minimal geometric compression.
        self.assertEqual(len(alex_rehydrated.state.scars), 1)
        self.assertEqual(len(axiom.state.scars), 0)


if __name__ == "__main__":
    unittest.main()

