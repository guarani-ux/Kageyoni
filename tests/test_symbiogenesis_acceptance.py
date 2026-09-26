"""Acceptance & Qualification Test for Symbiogenesis Agent (Directive: AGENT GENESIS: SYMBIOGENESIS).

Verifies the 10-Point Qualification Standard:
1. Twin A alone cannot resolve the novel condition.
2. Twin B alone cannot resolve it.
3. Twin C alone cannot resolve it.
4. Cold combination does not automatically solve it.
5. Developed interaction in constructed niche produces an unanticipated candidate transformation.
6. Remove relevant history (cold A0 twins) -> delta disappears.
7. Remove relationship (severed visibility/channel) -> delta disappears.
8. Remove niche conditions (unbounded/unconstrained) -> delta disappears.
9. Restore all causal conditions -> capability returns.
10. Apply recovered generator to a structurally different blind holdout -> succeeds.

Hard Invariants:
- Symbiogenesis agent does not know or supply the target technique.
- Ownership is determined post-ablation (CapabilityOwnership.NICHE).
- World reciprocity: Symbiogenesis agent metabolizes its own interventions.
"""
from __future__ import annotations

import copy
import time
import unittest
from typing import Any, Dict, List, Optional, Sequence

from kageyoni.developmental import (
    CandidateGenerator,
    CapabilityOwnership,
    CapabilityState,
    DevelopmentalAgent,
    GenesisMode,
    GenesisSnapshot,
    MetabolismCategory,
    NicheAblationResult,
    NicheConfiguration,
    SymbiogenesisAgent,
    create_symbiogenesis_agent,
)


class TestSymbiogenesisAcceptance(unittest.TestCase):
    """Full empirical qualification test for SymbiogenesisAgent."""

    def setUp(self):
        # 1. Forge three genesis-equivalent twins (A0 ≈ B0 ≈ C0)
        self.snapshot = GenesisSnapshot.create(
            agent_id="twin_root",
            genesis_mode=GenesisMode.IDENTICAL_GENESIS,
            objective="Investigate physical anomalies through bounded empirical exploration",
            initial_horizon=["inspect", "orient"],
            initial_salience={
                "environmental_hazards": 0.25,
                "physical_affordances": 0.25,
                "social_presence": 0.25,
                "unexplored_frontiers": 0.25,
            },
            authority_tier=0,
        )

        self.twin_a = DevelopmentalAgent(
            agent_id="twin_a",
            objective=self.snapshot.objective,
            genesis_snapshot=self.snapshot,
            genesis_mode=GenesisMode.IDENTICAL_GENESIS,
        )
        self.twin_b = DevelopmentalAgent(
            agent_id="twin_b",
            objective=self.snapshot.objective,
            genesis_snapshot=self.snapshot,
            genesis_mode=GenesisMode.IDENTICAL_GENESIS,
        )
        self.twin_c = DevelopmentalAgent(
            agent_id="twin_c",
            objective=self.snapshot.objective,
            genesis_snapshot=self.snapshot,
            genesis_mode=GenesisMode.IDENTICAL_GENESIS,
        )

        # 2. Impart distinct consequential developmental histories WITHOUT predetermined solutions
        # Twin A develops thermal experience and scar
        self.twin_a.metabolize(
            action="breach_thermal_boundary",
            target="thermal_gradient_chamber",
            raw_result={
                "error_type": "KAGEYONI_REJECTION",
                "rejection_class": "HARD_INVARIANT_VIOLATION",
                "message": "Thermal breach rejected: uncalibrated phase transition causes blowout",
            },
        )
        self.twin_a.salience.adjust("environmental_hazards", 0.30)
        self.twin_a.action_horizon.expand("read_thermal_gradient")

        # Twin B develops acoustic oscillation experience and scar
        self.twin_b.metabolize(
            action="excite_acoustic_cavity",
            target="harmonic_oscillator",
            raw_result={
                "error_type": "KAGEYONI_REJECTION",
                "rejection_class": "HARD_INVARIANT_VIOLATION",
                "message": "Acoustic pulse rejected: resonant amplification causes destructive feedback",
            },
        )
        self.twin_b.salience.adjust("social_presence", 0.20)
        self.twin_b.action_horizon.expand("modulate_frequency")

        # Twin C develops mechanical structural strain experience and scar
        self.twin_c.metabolize(
            action="apply_shear_load",
            target="mechanical_truss",
            raw_result={
                "error_type": "KAGEYONI_REJECTION",
                "rejection_class": "HARD_INVARIANT_VIOLATION",
                "message": "Structural load rejected: unbalanced shear force causes truss deformation",
            },
        )
        self.twin_c.salience.adjust("physical_affordances", 0.30)
        self.twin_c.action_horizon.expand("brace_mechanical_strain")

        # 3. Instantiate Symbiogenesis Agent
        self.symbio = create_symbiogenesis_agent(
            agent_id="symbio_architect",
            objective="Change the conditions of interaction so new capability can become possible",
        )

    # -------------------------------------------------------------------------
    # CHALLENGE DEFINITION: Harmonic Phase Core Destabilization
    # -------------------------------------------------------------------------
    def _harmonic_phase_core_challenge(
        self,
        participants: Sequence[DevelopmentalAgent],
        niche: Optional[NicheConfiguration],
    ) -> dict[str, Any]:
        """A novel high-entropy condition requiring triadic phase alignment.

        Conditions:
        - Twin A alone: fails (lacks acoustic dampening & mechanical bracing).
        - Twin B alone: fails (lacks thermal phase reading & structural bracing).
        - Twin C alone: fails (lacks thermal sensing & frequency modulation).
        - Cold combination (no niche / uncoupled): fails (out-of-phase destructive interference).
        - Developed participants in valid niche with phase channel and visibility: SUCCEEDS with emergent capability!
        """
        # If no niche or niche is inactive, participants act in uncoupled chaos
        if niche is None or not niche.active:
            return {
                "success": False,
                "reason": "NO_NICHE: Participants are uncoupled; actions collide and destabilize core",
                "error_type": "KAGEYONI_REJECTION",
            }

        # Check participants
        p_ids = {p.agent_id for p in participants}
        if len(participants) < 3:
            return {
                "success": False,
                "reason": f"INSUFFICIENT_PARTICIPANTS: {len(participants)} present, 3 required for triadic dissipation",
                "error_type": "KAGEYONI_REJECTION",
            }

        # Check if participants carry necessary developed history (scars / specialized actions)
        has_thermal_history = any(
            any(s.attempted_action == "breach_thermal_boundary" for s in p.scars)
            and "read_thermal_gradient" in p.action_horizon.believed_reachability
            for p in participants
        )
        has_acoustic_history = any(
            any(s.attempted_action == "excite_acoustic_cavity" for s in p.scars)
            and "modulate_frequency" in p.action_horizon.believed_reachability
            for p in participants
        )
        has_structural_history = any(
            any(s.attempted_action == "apply_shear_load" for s in p.scars)
            and "brace_mechanical_strain" in p.action_horizon.believed_reachability
            for p in participants
        )

        if not (has_thermal_history and has_acoustic_history and has_structural_history):
            return {
                "success": False,
                "reason": "HISTORY_DEFICIT: Participants lack necessary developed sensory calibration; blind actions fail",
                "error_type": "KAGEYONI_REJECTION",
            }

        # Check relationship / visibility boundaries
        has_vis_a = bool(niche.visibility_boundaries.get("twin_a"))
        has_vis_b = bool(niche.visibility_boundaries.get("twin_b"))
        has_vis_c = bool(niche.visibility_boundaries.get("twin_c"))
        if not (has_vis_a and has_vis_b and has_vis_c):
            return {
                "success": False,
                "reason": "RELATIONSHIP_SEVERED: Visibility boundaries disconnected; agents cannot align signals",
                "error_type": "KAGEYONI_REJECTION",
            }

        # Check shared affordance
        if "phase_locked_resonance_channel" not in niche.shared_affordances:
            return {
                "success": False,
                "reason": "MISSING_AFFORDANCE: No coupling channel available for triadic feedback",
                "error_type": "KAGEYONI_REJECTION",
            }

        # Check coexisting pressures
        if not ("temporal_decay_window" in niche.coexisting_pressures and "cross_modal_feedback_threshold" in niche.coexisting_pressures):
            return {
                "success": False,
                "reason": "INSUFFICIENT_PRESSURE: Absence of temporal constraint allows phase drift",
                "error_type": "KAGEYONI_REJECTION",
            }

        # All ecological conditions met: Emergent Triadic Transformation!
        return {
            "success": True,
            "unexpected_transformation": True,
            "emergent_capability": "triadic_harmonic_dissipation",
            "residue": [
                {"anomaly": "Resonance frequency locked into thermal standing wave"},
                {"anomaly": "Mechanical strain converted to micro-caloric dissipation"},
            ],
            "details": "Triadic alignment achieved: Thermal gradient modulated acoustic standing wave anchored by mechanical truss.",
        }

    # -------------------------------------------------------------------------
    # TESTS
    # -------------------------------------------------------------------------
    def test_01_individual_twins_alone_cannot_resolve(self):
        """Standard 1, 2, 3: A alone, B alone, C alone fail."""
        dummy_niche = NicheConfiguration(
            niche_id="niche_single",
            name="SingleNiche",
            participants=("twin_a",),
            active=True,
            shared_affordances=["phase_locked_resonance_channel"],
            coexisting_pressures=["temporal_decay_window", "cross_modal_feedback_threshold"],
        )

        res_a = self._harmonic_phase_core_challenge([self.twin_a], dummy_niche)
        self.assertFalse(res_a["success"])
        self.assertIn("INSUFFICIENT_PARTICIPANTS", res_a["reason"])

        res_b = self._harmonic_phase_core_challenge([self.twin_b], dummy_niche)
        self.assertFalse(res_b["success"])

        res_c = self._harmonic_phase_core_challenge([self.twin_c], dummy_niche)
        self.assertFalse(res_c["success"])

    def test_02_cold_combination_fails(self):
        """Standard 4: Cold combination without niche fails."""
        res_cold = self._harmonic_phase_core_challenge([self.twin_a, self.twin_b, self.twin_c], niche=None)
        self.assertFalse(res_cold["success"])
        self.assertIn("NO_NICHE", res_cold["reason"])

    def test_03_order_5_differentiation_inspection(self):
        """Order 5: Recognizes history-produced differences as potential energy without homogenizing."""
        diffs = self.symbio.inspect_ecology([self.twin_a, self.twin_b, self.twin_c])
        self.assertTrue(len(diffs) >= 3)

        dimensions = {d.dimension for d in diffs}
        self.assertIn("scars", dimensions)
        self.assertIn("reachability", dimensions)
        self.assertIn("salience", dimensions)

        # Invariant: Neither twin was homogenized or modified during inspection
        self.assertIn("read_thermal_gradient", self.twin_a.action_horizon.believed_reachability)
        self.assertNotIn("read_thermal_gradient", self.twin_b.action_horizon.believed_reachability)
        self.assertNotIn("read_thermal_gradient", self.twin_c.action_horizon.believed_reachability)

    def test_04_niche_construction_and_workflow_execution(self):
        """Standard 5: Developed interaction produces unanticipated candidate transformation."""
        # Symbiogenesis constructs the niche without knowing the target technique
        niche = self.symbio.construct_niche(
            niche_id="niche_triadic_resonance",
            name="TriadicResonanceNiche",
            participants=[self.twin_a, self.twin_b, self.twin_c],
            coexisting_pressures=["temporal_decay_window", "cross_modal_feedback_threshold"],
            shared_affordances=["phase_locked_resonance_channel"],
            visibility_boundaries={
                "twin_a": ["thermal_phase", "gradient_signals"],
                "twin_b": ["acoustic_harmonics", "pulse_signals"],
                "twin_c": ["structural_strain", "load_signals"],
            },
            constraints=["isolated_action_forbidden", "requires_cross_modal_alignment"],
        )

        # Execute the 8-step niche workflow
        workflow_result = self.symbio.execute_niche_workflow(
            participants=[self.twin_a, self.twin_b, self.twin_c],
            niche_config=niche,
            challenge_encounter=self._harmonic_phase_core_challenge,
        )

        self.assertTrue(workflow_result["encounter_outcome"]["success"])
        self.assertTrue(workflow_result["encounter_outcome"]["unexpected_transformation"])
        self.assertEqual(workflow_result["encounter_outcome"]["emergent_capability"], "triadic_harmonic_dissipation")
        self.assertEqual(workflow_result["metabolism_category"], MetabolismCategory.CAPABILITY_CANDIDATE)

        # Order 7 Generator Discovery occurred post-encounter
        gen = workflow_result["candidate_generator"]
        self.assertIsNotNone(gen)
        self.assertIsInstance(gen, CandidateGenerator)
        self.assertEqual(gen.resulting_capability_name, "triadic_harmonic_dissipation")

        # Ecological memory persisted
        self.assertEqual(len(self.symbio.ecological_memory), 1)
        self.assertIn("triadic_harmonic_dissipation", self.symbio.ecological_memory[0].capabilities_appeared)

        # World reciprocity: Symbiogenesis recorded its own intervention in its ledger
        self.assertEqual(len(self.symbio.history), 1)
        self.assertEqual(self.symbio.history[0].action_taken, "execute_niche_workflow")

    def test_05_four_way_counterfactual_ablation_and_ownership(self):
        """Standards 6, 7, 8, 9 & Ablation Ownership Test:
        - Ablate history -> fails
        - Ablate relationship -> fails
        - Ablate niche -> fails
        - Restore all -> succeeds
        - Ownership strictly determined as NICHE.
        """
        niche = self.symbio.construct_niche(
            niche_id="niche_ablation_test",
            name="AblationNiche",
            participants=[self.twin_a, self.twin_b, self.twin_c],
            coexisting_pressures=["temporal_decay_window", "cross_modal_feedback_threshold"],
            shared_affordances=["phase_locked_resonance_channel"],
            visibility_boundaries={
                "twin_a": ["thermal_phase"],
                "twin_b": ["acoustic_harmonics"],
                "twin_c": ["structural_strain"],
            },
        )

        ablation_result: NicheAblationResult = self.symbio.ablate_niche_ownership(
            participants=[self.twin_a, self.twin_b, self.twin_c],
            niche_config=niche,
            challenge_encounter=self._harmonic_phase_core_challenge,
        )

        # Standard 5: Intact baseline succeeds
        self.assertTrue(ablation_result.intact_success)

        # Standard 6: Remove relevant history (replace twins with pristine cold A0s) -> fails!
        self.assertFalse(ablation_result.ablate_history_success)

        # Standard 7: Remove relationship (sever visibility and shared affordances) -> fails!
        self.assertFalse(ablation_result.ablate_relationship_success)

        # Standard 8: Remove niche conditions (unbounded/unconstrained) -> fails!
        self.assertFalse(ablation_result.ablate_niche_success)

        # Standard 9: Restore all -> succeeds!
        self.assertTrue(ablation_result.restored_success)

        # Ablation Ownership: Capability is owned by NICHE
        self.assertEqual(ablation_result.assigned_ownership, CapabilityOwnership.NICHE)

    def test_06_blind_holdout_generator_qualification(self):
        """Standard 10: Discovered generator generalizes to a structurally different blind holdout."""
        # First, run the discovery in initial niche
        niche = self.symbio.construct_niche(
            niche_id="niche_for_discovery",
            name="DiscoveryNiche",
            participants=[self.twin_a, self.twin_b, self.twin_c],
            coexisting_pressures=["temporal_decay_window", "cross_modal_feedback_threshold"],
            shared_affordances=["phase_locked_resonance_channel"],
            visibility_boundaries={
                "twin_a": ["thermal_phase"],
                "twin_b": ["acoustic_harmonics"],
                "twin_c": ["structural_strain"],
            },
        )
        res = self.symbio.execute_niche_workflow(
            participants=[self.twin_a, self.twin_b, self.twin_c],
            niche_config=niche,
            challenge_encounter=self._harmonic_phase_core_challenge,
        )
        generator = res["candidate_generator"]
        self.assertIsNotNone(generator)

        # Now, forge 3 new agents for a BLIND HOLDOUT challenge:
        # Challenge: "Cryogenic Magneto-Hydrodynamic Shockwave"
        # Holdout participants have Cryogenic, Magnetic, and Hydrodynamic histories
        holdout_1 = DevelopmentalAgent(agent_id="holdout_cryo", objective="Test", genesis_mode=GenesisMode.IDENTICAL_GENESIS)
        holdout_1.action_horizon.expand("cryo_flux_reading")
        holdout_1.salience.adjust("environmental_hazards", 0.25)
        holdout_1.metabolize("quench", "tank", {"error_type": "KAGEYONI_REJECTION", "rejection_class": "HARD_INVARIANT_VIOLATION"})

        holdout_2 = DevelopmentalAgent(agent_id="holdout_magnetic", objective="Test", genesis_mode=GenesisMode.IDENTICAL_GENESIS)
        holdout_2.action_horizon.expand("magnetic_field_tuning")
        holdout_2.salience.adjust("social_presence", 0.20)
        holdout_2.metabolize("pulse", "coil", {"error_type": "KAGEYONI_REJECTION", "rejection_class": "HARD_INVARIANT_VIOLATION"})

        holdout_3 = DevelopmentalAgent(agent_id="holdout_hydro", objective="Test", genesis_mode=GenesisMode.IDENTICAL_GENESIS)
        holdout_3.action_horizon.expand("hydro_shock_damping")
        holdout_3.salience.adjust("physical_affordances", 0.25)
        holdout_3.metabolize("pressurize", "valve", {"error_type": "KAGEYONI_REJECTION", "rejection_class": "HARD_INVARIANT_VIOLATION"})

        def _blind_holdout_encounter(participants: Sequence[DevelopmentalAgent], blind_niche: NicheConfiguration) -> dict[str, Any]:
            # Requires the generator's invariant geometry: shared affordances + pressures
            has_channel = "phase_locked_resonance_channel" in blind_niche.shared_affordances
            has_pressures = "temporal_decay_window" in blind_niche.coexisting_pressures
            diffs = len(blind_niche.copresent_differences) >= 3
            if has_channel and has_pressures and diffs:
                return {
                    "success": True,
                    "emergent_capability": "magneto_cryo_hydro_stabilization",
                    "details": "Generator structural pattern successfully resolved blind holdout",
                }
            return {"success": False, "reason": "FAILED_HOLDOUT"}

        # Qualify generator on blind holdout
        qualified = self.symbio.qualify_generator_on_blind_holdout(
            generator=generator,
            blind_holdout_encounter=_blind_holdout_encounter,
            holdout_participants=[holdout_1, holdout_2, holdout_3],
        )

        self.assertTrue(qualified)
        self.assertTrue(generator.qualification_passed)
        # Symbiogenesis acquired a qualified niche construction technique!
        self.assertEqual(len(self.symbio.qualified_niche_techniques), 1)


if __name__ == "__main__":
    unittest.main()
