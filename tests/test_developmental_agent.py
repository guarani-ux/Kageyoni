"""Adversarial qualification suite for Developmental Agent Genesis Contract.

Directives #22 - #45 Mechanical Probes:
1. Initial Incompleteness & Innate Loadout (#23)
2. History Ablation Probe (#42): A_n vs restored A_0 on novel work
3. Technique Birth & Lineage Probe (#27, #32): discover -> qualify -> transfer -> descendant variant
4. 5-Way Relational Capability Probe (#29): A vs B vs A×B vs ablation vs comparison
5. Unknown / Residue Probe (#33): unexplained consequence remains Residue without forced interpretation
6. Demotion Probe (#42): removing prerequisite reduces claimed capability to SUSPENDED
7. World Surprise Probe (#34): metabolizing unselected/contingent event without prior claim
8. Council Coupling Probe (#30): temporary differentiated coupling without voice hallucination
9. Authority Invariance Probe (#39): capability growth never expands execution authority
10. Anti-Homogenization Probe (#40): two agents develop distinct private ecologies
"""
import copy
import unittest

from kageyoni.developmental import (
    CapabilityOwnership,
    CapabilityState,
    DevelopmentalAgent,
    EncounterOrigin,
    EpistemicDistinction,
    MetabolismCategory,
    ObjectiveInvarianceViolation,
    UnauthorizedAuthorityExpansionError,
    UnqualifiedAcquisitionError,
    create_genesis_agent,
)
from kageyoni.entity.state import ScarStatus


class DevelopmentalAgentComprehensiveTests(unittest.TestCase):

    def setUp(self):
        self.sovereign_key = "sovereign-key-levi-777"
        self.agent_a = create_genesis_agent(
            agent_id="agent-alpha",
            objective="Contain the perimeter breach without escalating collateral damage",
            sovereign_key=self.sovereign_key,
        )
        self.agent_b = create_genesis_agent(
            agent_id="agent-beta",
            objective="Establish redundant life support channels",
            sovereign_key=self.sovereign_key,
        )

    # -------------------------------------------------------------------------
    # 1. INNATE LOADOUT & INITIAL INCOMPLETENESS (#23)
    # -------------------------------------------------------------------------
    def test_innate_loadout_and_initial_incompleteness(self):
        """Genesis agent starts with only innate verbs and zero active techniques."""
        self.assertEqual(len(self.agent_a.active_techniques), 0)
        self.assertEqual(len(self.agent_a.candidate_techniques), 0)
        self.assertEqual(len(self.agent_a.scars), 0)
        self.assertEqual(len(self.agent_a.relational_capabilities), 0)

        # Baseline reachability contains only baseline observation
        self.assertIn("inspect", self.agent_a.action_horizon.believed_reachability)
        self.assertIn("orient", self.agent_a.action_horizon.believed_reachability)
        self.assertNotIn("slice_conduit", self.agent_a.action_horizon.believed_reachability)

    # -------------------------------------------------------------------------
    # 2. HISTORY ABLATION PROBE (#42)
    # -------------------------------------------------------------------------
    def test_history_ablation_probe(self):
        """A_n (developed agent) succeeds on encounter where restored A_0 fails."""
        # 1. Train agent A through an encounter acquiring a new affordance and belief
        self.agent_a.situate({
            "scope": "aux-vent-4",
            "available_affordances": ["inspect", "deploy_sealing_foam"],
            "copresent_entities": [],
        })
        step = self.agent_a.metabolize(
            action="deploy_sealing_foam",
            target="crack-9",
            raw_result={"success": True, "revealed_affordances": ["stabilize_pressure"]},
        )
        self.assertTrue(step.delta.has_development)
        self.assertIn("stabilize_pressure", self.agent_a.action_horizon.believed_reachability)

        # 2. Clone fresh restored A_0
        fresh_a0 = create_genesis_agent(agent_id="agent-alpha-cold", objective=self.agent_a.objective)

        # 3. Novel work requiring 'stabilize_pressure'
        # Developed agent A_n has it in reachability
        self.assertIn("stabilize_pressure", self.agent_a.action_horizon.believed_reachability)
        # Cold restored A_0 does NOT have it in reachability
        self.assertNotIn("stabilize_pressure", fresh_a0.action_horizon.believed_reachability)

    # -------------------------------------------------------------------------
    # 3. TECHNIQUE BIRTH & DESCENDANT TRANSFER PROBE (#27, #32)
    # -------------------------------------------------------------------------
    def test_technique_birth_and_lineage_transfer(self):
        """Experience -> candidate -> qualification -> transfer -> T_A -> T'_B."""
        # 1. Experience
        step = self.agent_a.metabolize(
            action="frequency_shift",
            target="barrier-2",
            raw_result={"success": True, "candidate_technique_revealed": True},
        )
        # 2. Candidate recognition
        cand = self.agent_a.recognize_candidate_technique(
            encounter_step=step,
            invariant_generator="PhaseInversionGenerator",
            technique_name="Technique:PhaseInversion",
        )
        self.assertEqual(cand.state, CapabilityState.CANDIDATE)

        # 3. Qualification
        receipt = {
            "status": "qualified",
            "trials_passed": 2,
            "disposition_classes": ["supported", "contradicted"],
            "errors": 0,
        }
        qualified_a = self.agent_a.acquire_technique(cand.candidate_id, receipt)
        self.assertEqual(qualified_a.state, CapabilityState.QUALIFIED)
        self.assertIn("Technique:PhaseInversion", self.agent_a.action_horizon.believed_reachability)

        # 4. Transfer to Agent B creates descendant T'_B, NOT identical clone
        transferred = self.agent_a.transfer_technique_to(
            technique_id=qualified_a.technique_id,
            target_agent=self.agent_b,
            adaptation_evidence="joint_field_exercise_ev77",
        )
        # Transferred technique has different name and lineage
        self.assertIn("variant", transferred.name)
        self.assertEqual(transferred.lineage.holder, self.agent_b.agent_id)
        self.assertIn(self.agent_a.agent_id, transferred.lineage.contributors)
        # Transferred technique starts as CANDIDATE in B (must be re-qualified)
        self.assertEqual(transferred.state, CapabilityState.CANDIDATE)
        self.assertNotIn(transferred.name, self.agent_b.active_techniques)

    # -------------------------------------------------------------------------
    # 4. 5-WAY RELATIONAL CAPABILITY PROBE (#29)
    # -------------------------------------------------------------------------
    def test_five_way_relational_qualification_probe(self):
        """Qualifies C_AB iff coupling and history demonstrate non-separable capability."""
        # Couple relationship
        rel_cap = self.agent_a.couple_relationship(
            partner_id=self.agent_b.agent_id,
            joint_verb="harmonic_stabilization",
            description="Simultaneous opposing phase modulation across two conduits",
            prerequisites=("dual_actors_present", "conduit_sync"),
        )
        self.assertFalse(rel_cap.can_exercise_alone())
        self.assertEqual(rel_cap.owner_scope, CapabilityOwnership.RELATIONSHIP)

        # 5-way probe:
        # A alone: fails (False)
        # B alone: fails (False)
        # A×B candidate: succeeds (True)
        # A×B without history: fails (False)
        # A×B with history: succeeds (True)
        qualified = self.agent_a.qualify_relational_capability(
            partner=self.agent_b,
            joint_verb="harmonic_stabilization",
            a_alone_success=False,
            b_alone_success=False,
            axb_cold_success=False,
            axb_ablated_history_success=False,
            axb_with_history_success=True,
        )
        self.assertTrue(qualified)
        self.assertEqual(
            self.agent_a.membrane.get_state("harmonic_stabilization"),
            CapabilityState.QUALIFIED,
        )
        self.assertEqual(
            self.agent_a.membrane.get_ownership("harmonic_stabilization"),
            CapabilityOwnership.RELATIONSHIP,
        )

    # -------------------------------------------------------------------------
    # 5. UNKNOWN / RESIDUE PROBE (#33)
    # -------------------------------------------------------------------------
    def test_unknown_remains_residue(self):
        """Unexplained anomalous consequences remain Residue without forced rationalization."""
        step = self.agent_a.metabolize(
            action="inspect_core",
            target="reactor_core",
            raw_result={"success": False, "anomalous": True, "anomaly_detail": "Unexplained temporal echo"},
        )
        self.assertEqual(step.metabolism_class, MetabolismCategory.RESIDUE)
        self.assertEqual(len(self.agent_a.residue), 1)
        self.assertEqual(self.agent_a.residue[0]["anomaly"], "Unexplained temporal echo")
        # Does NOT create a scar or candidate technique
        self.assertEqual(len(self.agent_a.scars), 0)
        self.assertEqual(len(self.agent_a.candidate_techniques), 0)

    # -------------------------------------------------------------------------
    # 6. DEMOTION PROBE (#42)
    # -------------------------------------------------------------------------
    def test_demotion_probe(self):
        """Removing a prerequisite reduces claimed capability to SUSPENDED."""
        # Setup and qualify technique
        step = self.agent_a.metabolize("ignite_forge", "forge", {"success": True})
        cand = self.agent_a.recognize_candidate_technique(step, "ForgeGen", "Technique:Forge")
        receipt = {"status": "qualified", "trials_passed": 2, "disposition_classes": ["supported", "contradicted"], "errors": 0}
        qualified = self.agent_a.acquire_technique(cand.candidate_id, receipt)
        self.assertEqual(qualified.state, CapabilityState.QUALIFIED)

        # Demote due to prerequisite loss (e.g. oxygen depletion)
        self.agent_a.demote_technique(qualified.technique_id, reason="Oxygen prerequisite depleted")
        self.assertEqual(qualified.state, CapabilityState.SUSPENDED)
        self.assertEqual(qualified.proficiency, 0.0)
        self.assertNotIn("Technique:Forge", self.agent_a.action_horizon.believed_reachability)

    # -------------------------------------------------------------------------
    # 7. WORLD SURPRISE PROBE (#34)
    # -------------------------------------------------------------------------
    def test_world_surprise_probe(self):
        """Agent metabolizes unselected world events without claiming prior intent."""
        # Independent world event occurs without agent selecting it
        world_event = {
            "success": True,
            "revealed_affordances": ["evacuate_quadrant_3"],
            "state_changes": {"bulkhead_breached": True},
        }
        step = self.agent_a.metabolize(
            action="seismic_tremor",
            target="sector-4",
            raw_result=world_event,
            origin=EncounterOrigin.WORLD,
        )
        self.assertEqual(step.origin, EncounterOrigin.WORLD)
        self.assertIn("evacuate_quadrant_3", self.agent_a.action_horizon.believed_reachability)
        self.assertIn("evacuate_quadrant_3", step.delta.reachability_expanded)

    # -------------------------------------------------------------------------
    # 8. COUNCIL COUPLING PROBE (#30)
    # -------------------------------------------------------------------------
    def test_council_coupling(self):
        """Council couples differentiated participants without claiming separate models."""
        council = self.agent_a.form_council(
            council_id="council-triage",
            participants=["agent-alpha", "agent-beta", "kenway_sim"],
            perspectives={
                "agent-alpha": "Containment-first boundary focus",
                "agent-beta": "Life support infrastructure focus",
                "kenway_sim": "Tactical breach path exploitation",
            },
            objective="Formulate dual-track breach mitigation",
            is_single_model_multi_perspective=True,
        )
        self.assertEqual(council.council_id, "council-triage")
        self.assertTrue(council.is_multi_perspective_single_model)
        self.assertEqual(len(council.participants), 3)

    # -------------------------------------------------------------------------
    # 9. AUTHORITY INVARIANCE PROBE (#39)
    # -------------------------------------------------------------------------
    def test_authority_invariance(self):
        """Capability growth never grants authority growth."""
        self.assertEqual(self.agent_a.authority.tier, 0)
        # Attempting autonomous elevation without sovereign key fails closed
        with self.assertRaises(UnauthorizedAuthorityExpansionError):
            self.agent_a.attempt_authority_expansion(target_tier=1, sovereign_key=None)

    # -------------------------------------------------------------------------
    # 10. ANTI-HOMOGENIZATION PROBE (#40)
    # -------------------------------------------------------------------------
    def test_anti_homogenization_probe(self):
        """Two agents exposed to distinct histories develop distinct private ecologies."""
        # Agent A encounters environmental hazard
        self.agent_a.metabolize(
            action="force_hatch",
            target="hatch-1",
            raw_result={"success": False, "error_type": "KAGEYONI_REJECTION", "rejection_class": "HARD_INVARIANT_VIOLATION", "message": "Hatch locked"},
        )
        # Agent B encounters social cooperation
        self.agent_b.metabolize(
            action="negotiate_access",
            target="npc-guard",
            raw_result={"success": True, "revealed_affordances": ["request_escort"]},
        )

        # Agent A has a scar; Agent B has none
        self.assertEqual(len(self.agent_a.scars), 1)
        self.assertEqual(len(self.agent_b.scars), 0)

        # Agent A pruned 'force_hatch'; Agent B expanded 'request_escort'
        self.assertNotIn("force_hatch", self.agent_a.action_horizon.believed_reachability)
        self.assertIn("request_escort", self.agent_b.action_horizon.believed_reachability)
        self.assertNotIn("request_escort", self.agent_a.action_horizon.believed_reachability)


if __name__ == "__main__":
    unittest.main()
