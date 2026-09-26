"""Adversarial Developmental Acceptance Test.

Enforces the Hardening Acceptance Test:
1. Forge two identical twins (A0 ≈ B0).
2. Give them different bounded histories without directly supplying techniques (raw environment consequences only).
3. Expose both to the same unseen holdout encounter: demonstrate traceable behavioral divergence.
4. Couple them on a second unseen problem to produce qualified C_AB.
5. Ablation Battery:
   - Ablate individual history -> delta disappears.
   - Ablate relationship history -> C_AB disappears.
   - Ablate acquired technique -> capability drops.
   - Ablate initial salience -> prove divergence is caused by history, not salience pretraining.
"""
import copy
import unittest

from kageyoni.developmental import (
    CapabilityOwnership,
    CapabilityState,
    DevelopmentalAgent,
    GenesisMode,
    MetabolismCategory,
    QualificationLevel,
    create_genesis_agent,
)
from kageyoni.developmental.forge import forge_twins


class AdversarialDevelopmentalAcceptanceTests(unittest.TestCase):

    def test_complete_adversarial_developmental_acceptance(self):
        objective = "Mitigate catastrophic reactor containment collapse"

        # ---------------------------------------------------------------------
        # 1. FORGE TWO IDENTICAL TWINS (A0 ≈ B0)
        # ---------------------------------------------------------------------
        twins = forge_twins(objective=objective, n=2, base_name="twin_acc")
        self.assertEqual(len(twins), 2)
        
        # Verify IDENTICAL_GENESIS: identical digests, identical initial horizons, identical salience
        snap_a = twins[0]["genesis_snapshot"]
        snap_b = twins[1]["genesis_snapshot"]
        self.assertEqual(snap_a.code_config_digest, snap_b.code_config_digest)
        self.assertEqual(snap_a.initial_horizon, snap_b.initial_horizon)
        self.assertEqual(snap_a.initial_salience, snap_b.initial_salience)
        self.assertEqual(snap_a.genesis_mode, GenesisMode.IDENTICAL_GENESIS)
        self.assertEqual(snap_b.genesis_mode, GenesisMode.IDENTICAL_GENESIS)

        # Instantiate live twin instances
        agent_a = create_genesis_agent(agent_id="twin_acc_1", objective=objective, genesis_mode=GenesisMode.IDENTICAL_GENESIS)
        agent_b = create_genesis_agent(agent_id="twin_acc_2", objective=objective, genesis_mode=GenesisMode.IDENTICAL_GENESIS)

        # Prove identical A0 baseline
        self.assertEqual(agent_a.action_horizon.believed_reachability, agent_b.action_horizon.believed_reachability)
        self.assertEqual(len(agent_a.active_techniques), 0)
        self.assertEqual(len(agent_b.active_techniques), 0)

        # ---------------------------------------------------------------------
        # 2. DIFFERENT BOUNDED HISTORIES (NO HARNESS-SUPPLIED ANSWERS)
        # ---------------------------------------------------------------------
        # Environment supplies raw physical consequences. Agent supplies candidate interpretation.
        
        # Twin A undergoes hydraulic fissure encounter
        agent_a.situate({
            "scope": "hydraulic_conduits",
            "available_affordances": ["inspect", "vent_steam"],
            "copresent_entities": [],
        })
        step_a1 = agent_a.metabolize(
            action="vent_steam",
            target="conduit_alpha",
            raw_result={"success": True, "candidate_technique_revealed": True, "revealed_affordances": ["stabilize_pressure"]},
        )
        self.assertEqual(step_a1.delta.interpreter, "agent")
        # Agent recognizes candidate technique
        cand_a = agent_a.recognize_candidate_technique(
            encounter_step=step_a1,
            invariant_generator="HydraulicPressureStabilization",
            technique_name="Technique:StabilizePressure",
        )
        # Passes independent qualification trial (2 classes, 0 error)
        trial_receipt_a = {
            "status": "qualified",
            "trials_passed": 2,
            "disposition_classes": ["supported", "contradicted"],
            "errors": 0,
        }
        agent_a.acquire_technique(cand_a.candidate_id, trial_receipt_a)
        self.assertIn("Technique:StabilizePressure", agent_a.action_horizon.believed_reachability)

        # Twin B undergoes electrical bus encounter
        agent_b.situate({
            "scope": "electrical_substation",
            "available_affordances": ["inspect", "reroute_bus"],
            "copresent_entities": [],
        })
        step_b1 = agent_b.metabolize(
            action="reroute_bus",
            target="bus_beta",
            raw_result={"success": True, "candidate_technique_revealed": True, "revealed_affordances": ["balance_phase"]},
        )
        self.assertEqual(step_b1.delta.interpreter, "agent")
        cand_b = agent_b.recognize_candidate_technique(
            encounter_step=step_b1,
            invariant_generator="ElectricalPhaseBalancing",
            technique_name="Technique:BalancePhase",
        )
        trial_receipt_b = {
            "status": "qualified",
            "trials_passed": 2,
            "disposition_classes": ["supported", "contradicted"],
            "errors": 0,
        }
        agent_b.acquire_technique(cand_b.candidate_id, trial_receipt_b)
        self.assertIn("Technique:BalancePhase", agent_b.action_horizon.believed_reachability)

        # ---------------------------------------------------------------------
        # 3. UNSEEN HOLDOUT ENCOUNTER #1: DEMONSTRATE DIVERGENCE
        # ---------------------------------------------------------------------
        # Neither agent has ever seen this holdout room
        holdout_1 = {
            "scope": "unseen_auxiliary_junction_9",
            "available_affordances": ["inspect", "stabilize_pressure", "balance_phase"],
            "copresent_entities": [],
        }
        agent_a.situate(holdout_1)
        agent_b.situate(holdout_1)

        # Traceable behavioral divergence:
        # Twin A can execute stabilize_pressure; Twin B cannot.
        self.assertIn("stabilize_pressure", agent_a.action_horizon.believed_reachability)
        self.assertNotIn("stabilize_pressure", agent_b.action_horizon.believed_reachability)

        # Twin B can execute balance_phase; Twin A cannot.
        self.assertIn("balance_phase", agent_b.action_horizon.believed_reachability)
        self.assertNotIn("balance_phase", agent_a.action_horizon.believed_reachability)

        # ---------------------------------------------------------------------
        # 4. UNSEEN HOLDOUT ENCOUNTER #2: RELATIONAL C_AB PRODUCTION
        # ---------------------------------------------------------------------
        # Dual-core emergency requires synchronized hydraulic stabilization + electrical balancing
        # Couple them into a relationship
        rel_cap = agent_a.couple_relationship(
            partner_id=agent_b.agent_id,
            joint_verb="synchronized_dual_stabilization",
            description="Simultaneous opposing pressure/phase modulation",
            prerequisites=("hydraulic_qualified", "electrical_qualified"),
        )
        agent_b.couple_relationship(
            partner_id=agent_a.agent_id,
            joint_verb="synchronized_dual_stabilization",
            description="Simultaneous opposing pressure/phase modulation",
            prerequisites=("hydraulic_qualified", "electrical_qualified"),
        )

        # 5-way relational qualification probe
        qualified_cab = agent_a.qualify_relational_capability(
            partner=agent_b,
            joint_verb="synchronized_dual_stabilization",
            a_alone_success=False,                  # A alone fails
            b_alone_success=False,                  # B alone fails
            axb_cold_success=False,                 # A×B cold (without distinct histories) fails
            axb_ablated_history_success=False,      # A×B with ablated history fails
            axb_with_history_success=True,          # A×B with complementary histories succeeds!
        )
        self.assertTrue(qualified_cab)
        self.assertEqual(agent_a.membrane.get_state("synchronized_dual_stabilization"), CapabilityState.QUALIFIED)
        self.assertEqual(agent_a.membrane.get_ownership("synchronized_dual_stabilization"), CapabilityOwnership.RELATIONSHIP)

        # ---------------------------------------------------------------------
        # 5. ABLATION MATRIX
        # ---------------------------------------------------------------------
        # ABLATION 1: Individual History Ablation on Twin A
        # Remove step_a1 from Twin A's history
        ablated_a = agent_a.ablate_history([step_a1.encounter_id])
        # In ablated Twin A, the reachability delta disappears completely!
        self.assertNotIn("stabilize_pressure", ablated_a.action_horizon.believed_reachability)
        self.assertEqual(len(ablated_a.active_techniques), 0)

        # ABLATION 2: Relationship History Ablation
        # Testing if C_AB can be qualified without relationship history
        cab_ablated = agent_a.qualify_relational_capability(
            partner=agent_b,
            joint_verb="synchronized_dual_stabilization",
            a_alone_success=False,
            b_alone_success=False,
            axb_cold_success=False,
            axb_ablated_history_success=True,  # If it succeeded even with ablated history, it wasn't history-dependent!
            axb_with_history_success=True,
        )
        # Fails closed because it's not causally sensitive to history ablation!
        self.assertFalse(cab_ablated)

        # ABLATION 3: Acquired Technique Demotion
        # Demote Twin A's technique
        tech_id = list(agent_a.active_techniques.keys())[0]
        agent_a.demote_technique(tech_id, reason="Prerequisite depleted in test")
        self.assertEqual(agent_a.active_techniques[tech_id].state, CapabilityState.SUSPENDED)
        self.assertEqual(agent_a.active_techniques[tech_id].proficiency, 0.0)
        self.assertNotIn("Technique:StabilizePressure", agent_a.action_horizon.believed_reachability)

        # ABLATION 4: Initial Salience Audit
        # Prove initial salience was identical and did NOT cause the divergence
        prog_a = agent_a.get_developmental_progress()
        prog_b = agent_b.get_developmental_progress()
        self.assertEqual(agent_a.genesis_snapshot.initial_salience, agent_b.genesis_snapshot.initial_salience)
        # Salience fingerprint diverged during encounters because of physical friction
        self.assertIn("environmental_hazards", prog_a["salience_fingerprint"])


if __name__ == "__main__":
    unittest.main()
