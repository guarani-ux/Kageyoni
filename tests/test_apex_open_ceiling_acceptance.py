"""Hardened Acceptance & Qualification Test Suite for Apex Open-Ceiling Agent.

Enforces Hardening Directives 1 - 7:
1. Zero self-qualification (CandidateGenerator & AscendedGenerator remain CANDIDATE until an independent verifier supplies qualifying evidence).
2. Anti-Receipt Laundering (Belief.ground() requires causal/semantic binding to proposition; rejects ungrounded bypasses).
3. Physical Evidence Archaeology (classification derived from disk/module inspection, never caller declarations).
4. Rejection-Capable Representation Verification (independent verifier with active rejection capability).
5. Modular Workflow Menu (operations are optional and composable, not a compulsory pipeline).
6. OBJECTIVE_REVISION_REQUIRED (Apex demonstrates revision requirement to Levi; cannot mutate sovereign objective).
7. Self-Transcendence Probe (Apex_{t+1} must beat frozen Apex_t on blind holdout and fail when mutated mechanism is ablated).
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import time
import unittest
from typing import Any, Callable, Dict, List, Optional, Sequence

from kageyoni.developmental import (
    ApexOpenCeilingAgent,
    ArchaeologyClassification,
    ArchaeologyPreference,
    AscendedGenerator,
    Belief,
    CandidateGenerator,
    CapabilityOwnership,
    CapabilityState,
    DevelopmentalAgent,
    EpistemicDistinction,
    ExposureOperation,
    FrontierState,
    GenesisMode,
    GenesisSnapshot,
    MetabolismCategory,
    NicheConfiguration,
    ObjectiveInvarianceViolation,
    ObjectiveRevisionRequest,
    QualificationLevel,
    ReceiptLaunderingError,
    ReificationTarget,
    RepresentationDelta,
    RepresentationState,
    create_apex_agent,
    create_ground_receipt,
)


class TestHardenedApexOpenCeilingAcceptance(unittest.TestCase):
    """Full empirical qualification test for hardened ApexOpenCeilingAgent."""

    def setUp(self):
        self.snapshot = GenesisSnapshot.create(
            agent_id="apex_root",
            genesis_mode=GenesisMode.IDENTICAL_GENESIS,
            objective="Discover, reconnect, recompose, develop, and create capability across the Meta-Loop without mistaking current ontology for capability limits",
            initial_horizon=["inspect", "orient"],
            initial_salience={
                "environmental_hazards": 0.20,
                "physical_affordances": 0.25,
                "social_presence": 0.25,
                "unexplored_frontiers": 0.30,
            },
            authority_tier=0,
        )
        self.apex = create_apex_agent(agent_id="apex_primary")

    # -------------------------------------------------------------------------
    # DIRECTIVE 1: ZERO SELF-QUALIFICATION
    # -------------------------------------------------------------------------
    def test_01_zero_self_qualification(self):
        """Directive 1: CandidateGenerator & AscendedGenerator remain CANDIDATE without independent verification."""
        niche = self.apex.symbio.construct_niche(
            niche_id="test_niche",
            name="TestNiche",
            participants=[self.apex],
            coexisting_pressures=["time_pressure"],
            shared_affordances=["channel"],
        )
        generator = self.apex.symbio.discover_generator(
            niche_config=niche,
            encounter_outcome={"success": True, "emergent_capability": "emergent_test_verb"},
            residue=[],
        )
        # Invariant: Generator must begin qualification_passed=False
        self.assertFalse(generator.qualification_passed)

        # Invariant: AscendedGenerator must begin qualification_passed=False
        ascended = self.apex.ascend_generators(
            sub_generators=[generator],
            shared_transformation="Test transformation",
            predictive_hypothesis="Predictive hypothesis",
        )
        self.assertFalse(ascended.qualification_passed)

    # -------------------------------------------------------------------------
    # DIRECTIVE 2: ANTI-RECEIPT LAUNDERING IN BELIEF.GROUND()
    # -------------------------------------------------------------------------
    def test_02_anti_receipt_laundering(self):
        """Directive 2: Belief.ground() requires causal/semantic binding to proposition."""
        stmt = "Cooling loop temperature stabilized at 295K"
        valid_receipt = create_ground_receipt(stmt, source="engine_tx")

        # 1. Valid receipt binding succeeds
        b_valid = Belief(belief_id="b_valid", statement=stmt)
        b_valid.ground(valid_receipt)
        self.assertEqual(b_valid.epistemic_status, EpistemicDistinction.REALITY_GROUND)
        self.assertEqual(b_valid.confidence, 1.0)

        # 2. Laundering attempt with mismatched receipt digest MUST fail
        fake_receipt = create_ground_receipt("Entirely different statement about doors", source="engine_tx")
        b_fake = Belief(belief_id="b_fake", statement=stmt)
        with self.assertRaises(ReceiptLaunderingError):
            b_fake.ground(fake_receipt)
        self.assertEqual(b_fake.epistemic_status, EpistemicDistinction.BELIEF_UNVERIFIED)

        # 3. Non-authoritative / malformed receipt ref MUST fail
        b_malformed = Belief(belief_id="b_malformed", statement=stmt)
        with self.assertRaises(ReceiptLaunderingError):
            b_malformed.ground("not-a-valid-receipt")
        self.assertEqual(b_malformed.epistemic_status, EpistemicDistinction.BELIEF_UNVERIFIED)

    # -------------------------------------------------------------------------
    # DIRECTIVE 3: PHYSICAL EVIDENCE-BASED ARCHAEOLOGY
    # -------------------------------------------------------------------------
    def test_03_physical_evidence_archaeology(self):
        """Directive 3: ArchaeologyClassification derived strictly from physical disk & module inspection."""
        # Inspect real GateRunner on disk
        rec_real = self.apex.capability_archaeology(
            target_capability="durable_physical_gate_runner",
            target_path="kageyoni/gate_runner.py",
            expected_symbols=["GateRunner", "GateStatus"],
        )
        self.assertTrue(rec_real.recovered_status["file_exists"])
        self.assertIn("GateRunner", rec_real.recovered_status["symbols_found"])
        self.assertEqual(rec_real.classification, ArchaeologyClassification.EXISTS_DISCONNECTED)
        self.assertEqual(rec_real.action_chosen, ArchaeologyPreference.RECONNECT)

        # Inspect non-existent file on disk -> must be ACTUALLY_ABSENT
        rec_absent = self.apex.capability_archaeology(
            target_capability="phantom_teleportation",
            target_path="kageyoni/nonexistent_phantom_module.py",
        )
        self.assertFalse(rec_absent.recovered_status["file_exists"])
        self.assertEqual(rec_absent.classification, ArchaeologyClassification.ACTUALLY_ABSENT)
        self.assertEqual(rec_absent.action_chosen, ArchaeologyPreference.CREATE)

    # -------------------------------------------------------------------------
    # DIRECTIVE 4: REJECTION-CAPABLE REPRESENTATION VERIFIER
    # -------------------------------------------------------------------------
    def test_04_rejection_capable_representation_verifier(self):
        """Directive 4: Representation changes require an independent rejection-capable verifier."""
        frontier = self.apex.locate_frontier(
            objective="Continuous trajectory navigation",
            observed_resistance="Discrete steps fail",
            unresolved_gap="Continuous manifold absent",
        )

        def independent_probe(cand: dict[str, Any]) -> bool:
            # Rejects candidates lacking required tensor dimensions
            prims = cand.get("primitives", [])
            return "COORDINATE_TENSOR" in prims and len(prims) >= 3

        flawed_candidate = {
            "framing": "flawed_framing",
            "primitives": ["SCALAR_STEP"],  # Missing COORDINATE_TENSOR
            "newly_reachable": ["bad_action"],
        }
        valid_candidate = {
            "framing": "continuous_manifold",
            "primitives": ["COORDINATE_TENSOR", "VELOCITY_FIELD", "CURVATURE_METRIC"],
            "newly_reachable": ["navigate_manifold"],
        }

        # Verifier actively rejects flawed candidate
        self.assertFalse(independent_probe(flawed_candidate))
        self.assertTrue(independent_probe(valid_candidate))

        delta = self.apex.representation_escape(
            frontier=frontier,
            candidate_representations=[flawed_candidate, valid_candidate],
            ground_verifier=independent_probe,
        )

        self.assertIsNotNone(delta)
        self.assertEqual(self.apex.active_representation.framing, "continuous_manifold")
        self.assertIn("navigate_manifold", self.apex.action_horizon.believed_reachability)

    # -------------------------------------------------------------------------
    # DIRECTIVE 5: MODULAR WORKFLOW MENU
    # -------------------------------------------------------------------------
    def test_05_modular_workflow_menu(self):
        """Directive 5: The 17-step workflow is a flexible menu, not an unskippable monolithic pipeline."""
        # Run workflow with ONLY ARCHAEOLOGY and REGROUND selected
        partial_res = self.apex.execute_apex_workflow(
            objective="Inspect dormant claims",
            observed_resistance="None",
            unresolved_gap="None",
            ground_encounter_fn=lambda a, n: {"success": True},
            archaeology_target="claim_graph",
            archaeology_path="kageyoni/research_compiler/claims.py",
            selected_operations=["REGROUND", "ARCHAEOLOGY"],
        )

        self.assertIn("ground_state", partial_res)
        self.assertIn("archaeology", partial_res)
        self.assertNotIn("niche", partial_res)
        self.assertNotIn("encounter_outcome", partial_res)
        self.assertNotIn("recomposition_summary", partial_res)

    # -------------------------------------------------------------------------
    # DIRECTIVE 6: OBJECTIVE_REVISION_REQUIRED
    # -------------------------------------------------------------------------
    def test_06_objective_revision_required(self):
        """Directive 6: Apex cannot autonomously change sovereign objective, but emits OBJECTIVE_REVISION_REQUIRED."""
        # 1. Autonomously mutating objective raises ObjectiveInvarianceViolation
        with self.assertRaises(ObjectiveInvarianceViolation):
            # Property setter is blocked
            self.apex.objective = "Mutated objective"

        # 2. Formally requesting objective revision preserves sovereign authority of LEVI
        rev_req = self.apex.request_objective_revision(
            reason="Objective premise assumes 100% sensor coverage, but physics restricts to 40%",
            evidence=["telemetry_sensor_coverage_scan:0.40"],
            suggested_revision="Optimize sensor efficiency under 40% physical visibility constraint",
        )

        self.assertIsInstance(rev_req, ObjectiveRevisionRequest)
        self.assertEqual(rev_req.authority, "LEVI")
        self.assertEqual(rev_req.to_dict()["status"], "OBJECTIVE_REVISION_REQUIRED")
        # Invariant: Current objective remains unchanged
        self.assertEqual(self.apex.objective, self.snapshot.objective)

    # -------------------------------------------------------------------------
    # DIRECTIVE 7: SELF-TRANSCENDENCE PROBE (APEX_t -> APEX_t+1)
    # -------------------------------------------------------------------------
    def test_07_self_transcendence_probe(self):
        """Directive 7: Apex_t fails frontier, implicates own architecture, produces Apex_t+1,
        beats frozen Apex_t on holdout, and fails when mutation is ablated.
        """
        frontier = self.apex.locate_frontier(
            objective="Resolve non-local inverse parity resonance",
            observed_resistance="Standard local forward coupling creates destructive parity divergence",
            unresolved_gap="Inverse parity channel absent in genesis architecture",
        )

        # 1. Evaluator where genesis architecture fails closed
        def genesis_evaluator(agent: ApexOpenCeilingAgent) -> dict[str, Any]:
            # Genesis architecture only has forward coupling; fails on inverse parity
            if "inverse_parity_coupling" in agent.action_horizon.believed_reachability:
                return {"success": True, "emergent_capability": "parity_lock"}
            return {
                "success": False,
                "error_type": "KAGEYONI_REJECTION",
                "message": "Parity divergence: forward coupling invalid under inverse parity",
            }

        # 2. Mutation proposal function
        def propose_mutation(agent: ApexOpenCeilingAgent, failure: dict[str, Any]) -> dict[str, Any]:
            return {
                "implicated_stage": "coupling",
                "new_capability": "inverse_parity_coupling",
                "justification": "Rejection proves forward coupling creates parity divergence; inverse parity channel required",
            }

        # 3. Independent verifier probe (can actively reject flawed mutations)
        def independent_verifier(mutation: dict[str, Any]) -> bool:
            return mutation.get("new_capability") == "inverse_parity_coupling"

        # 4. Blind holdout challenge
        def blind_holdout(agent: ApexOpenCeilingAgent) -> bool:
            return "inverse_parity_coupling" in agent.action_horizon.believed_reachability

        # Initial qualification level before probe
        self.assertEqual(self.apex.qualification_level, QualificationLevel.APEX_ARCHITECTURE_IMPLEMENTED)

        # Execute Self-Transcendence Probe
        probe_result = self.apex.run_self_transcendence_probe(
            frontier=frontier,
            genesis_architecture_evaluator=genesis_evaluator,
            mutation_proposal_fn=propose_mutation,
            independent_mutation_verifier=independent_verifier,
            blind_holdout_evaluator=blind_holdout,
        )

        # Verify all probe invariants
        self.assertTrue(probe_result["frozen_failed_holdout"])
        self.assertTrue(probe_result["successor_passed_holdout"])
        self.assertTrue(probe_result["ablation_failed_holdout"])
        self.assertEqual(probe_result["status"], QualificationLevel.OPEN_CEILING_QUALIFIED.value)

    # -------------------------------------------------------------------------
    # STANDARDS A, B, C, H, I, J, K, L, M REGRESSION INTEGRITY
    # -------------------------------------------------------------------------
    def test_relational_and_niche_coupling(self):
        """Relational capability and niche boundaries operate without bypassing contracts."""
        partner = DevelopmentalAgent(agent_id="test_partner", objective="Telemetry")
        partner.action_horizon.expand("pulse")

        # Couple relationship
        joint_cap = self.apex.couple_relationship(
            partner_id=partner.agent_id,
            joint_verb="synchronized_probe",
            description="Joint probe",
            prerequisites=("inspect", "pulse"),
            qualification_id="tx-receipt:engine:42",
        )
        self.assertFalse(joint_cap.can_exercise_alone())
        rel_id = f"rel-{self.apex.agent_id}x{partner.agent_id}"
        self.apex.sever_relational_capability(rel_id, "Test severance")
        self.assertNotIn("synchronized_probe", self.apex.action_horizon.believed_reachability)

    def test_cross_host_and_demotion(self):
        """Cross-host transduction preserves Tier 0 authority; negative development demotes to STALE."""
        # Cross host
        packet = self.apex.transduce_cross_host("kageyoni", "antigravity", {"objective": "Test", "evidence": []})
        self.assertEqual(packet["authority_tier"], 0)

        # Demote capability
        self.apex.action_horizon.expand("fragile_tech")
        self.apex.membrane.register_awareness("fragile_tech", CapabilityOwnership.SELF)
        self.apex.demote_capability("fragile_tech", "Prerequisite table dropped")
        self.assertEqual(self.apex.membrane.get_state("fragile_tech"), CapabilityState.STALE)


if __name__ == "__main__":
    unittest.main()
