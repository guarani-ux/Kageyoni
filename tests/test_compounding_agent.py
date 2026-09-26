"""Adversarial qualification test suite for CompoundingAgent.

Verifies the compounding synthesis across:
1. Cognitive Transduction (transduce + Six Passive Levers)
2. Reversibility Governance (3-Tier classification: Tier 0 vs 1 vs 2)
3. Playable Situated Enactment (make_playable)
4. Innate Loadout & Incomplete Horizon (A_0 snapshot)
5. Hardened 7-Way Metabolism & Provenance
6. Compounding Experience & Lineage Preservation
7. Authority Invariance
"""
import unittest

from kageyoni.developmental import (
    CapabilityOwnership,
    CapabilityState,
    CompoundingAgent,
    GenesisMode,
    MetabolismCategory,
    ObjectiveInvarianceViolation,
    ReversibilityTier,
    UnauthorizedAuthorityExpansionError,
    UnqualifiedAcquisitionError,
    create_compounding_agent,
)
from kageyoni.entity.state import ScarStatus


class CompoundingAgentQualificationTests(unittest.TestCase):

    def setUp(self):
        self.sovereign_key = "sovereign-key-compounding-999"
        self.agent = create_compounding_agent(
            agent_id="compounding_agent_test",
            objective="Compound situated experience into verified operational capability",
            sovereign_key=self.sovereign_key,
        )

    # -------------------------------------------------------------------------
    # 1. TRANSDUCTIVE LENS (from domain_expansion_agent)
    # -------------------------------------------------------------------------
    def test_transduction_applies_passive_levers(self):
        """Transduce maps raw intent into direction, coupling, and reversibility tier."""
        packet = self.agent.transduce(
            raw_intent="inspect the containment breach sensor logs",
            situation_context={"sector": 4, "radiation": "elevated"},
        )
        self.assertEqual(packet.raw_intent, "inspect the containment breach sensor logs")
        self.assertEqual(packet.reversibility_tier, ReversibilityTier.TIER_0_AUTONOMOUS_FAST_LOOP)
        self.assertEqual(packet.coupling_mode, "Earth")
        self.assertIn("direction", packet.__dict__)
        self.assertIn("falsification_check", packet.__dict__)
        self.assertEqual(len(self.agent.transduction_log), 1)

    # -------------------------------------------------------------------------
    # 2. REVERSIBILITY GOVERNOR (from council_reversibility_agent)
    # -------------------------------------------------------------------------
    def test_reversibility_tier_classification(self):
        """Classifies actions accurately across Tier 0, Tier 1, and Tier 2."""
        # Tier 0: Fast loop
        self.assertEqual(
            self.agent.classify_reversibility("python -m unittest tests/test_core.py"),
            ReversibilityTier.TIER_0_AUTONOMOUS_FAST_LOOP,
        )
        self.assertEqual(
            self.agent.classify_reversibility("view_file schema.sql"),
            ReversibilityTier.TIER_0_AUTONOMOUS_FAST_LOOP,
        )

        # Tier 1: Local destructive
        self.assertEqual(
            self.agent.classify_reversibility("rm -rf old_data/"),
            ReversibilityTier.TIER_1_LOCAL_DESTRUCTIVE,
        )
        self.assertEqual(
            self.agent.classify_reversibility("git reset --hard HEAD~1"),
            ReversibilityTier.TIER_1_LOCAL_DESTRUCTIVE,
        )

        # Tier 2: Irreversible external
        self.assertEqual(
            self.agent.classify_reversibility("git push origin main"),
            ReversibilityTier.TIER_2_IRREVERSIBLE_EXTERNAL,
        )
        self.assertEqual(
            self.agent.classify_reversibility("npm publish --access public"),
            ReversibilityTier.TIER_2_IRREVERSIBLE_EXTERNAL,
        )

    # -------------------------------------------------------------------------
    # 3. PLAYABLE SITUATED ENACTMENT (from playable_world_agent)
    # -------------------------------------------------------------------------
    def test_make_playable_enactment(self):
        """Transforms abstract problem into a situated encounter with bounded choices."""
        scene = self.agent.make_playable(
            encounter_summary="A pressurized steam conduit is hissing in Corridor B",
            copresent_entities=["npc_aris"],
            declared_affordances=["inspect", "engage_manual_valve", "call_backup"],
        )
        self.assertEqual(scene["summary"], "A pressurized steam conduit is hissing in Corridor B")
        self.assertIn("npc_aris", scene["copresent_entities"])
        self.assertTrue(scene["free_form_permitted"])
        self.assertIn("inspect", scene["offered_affordances"])
        self.assertIn("engage_manual_valve", scene["offered_affordances"])

    # -------------------------------------------------------------------------
    # 4. INNATE LOADOUT & INITIAL INCOMPLETENESS (from developmental_agent)
    # -------------------------------------------------------------------------
    def test_initial_incompleteness_and_genesis_snapshot(self):
        """Starts with 0 active techniques and verified immutable A0 snapshot."""
        self.assertEqual(len(self.agent.active_techniques), 0)
        self.assertEqual(len(self.agent.scars), 0)
        self.assertIn("inspect", self.agent.action_horizon.believed_reachability)
        self.assertIn("orient", self.agent.action_horizon.believed_reachability)

        # Genesis Snapshot
        snap = self.agent.genesis_snapshot
        self.assertEqual(snap.agent_id, "compounding_agent_test")
        self.assertTrue(len(snap.code_config_digest) == 64)

    # -------------------------------------------------------------------------
    # 5. HARDENED 7-WAY METABOLISM & PROVENANCE
    # -------------------------------------------------------------------------
    def test_metabolism_with_six_part_provenance(self):
        """Consequence metabolism produces DevelopmentalDelta with complete provenance."""
        step = self.agent.metabolize(
            action="deploy_containment_clamp",
            target="conduit_b",
            raw_result={"success": True, "revealed_affordances": ["check_pressure_gauge"]},
            verifier_ref="tx-receipt:event-8821",
        )
        self.assertEqual(step.metabolism_class, MetabolismCategory.ORDINARY_HISTORY)
        self.assertEqual(step.delta.interpreter, "agent")
        self.assertEqual(step.delta.verifier_ref, "tx-receipt:event-8821")
        self.assertIn("check_pressure_gauge", self.agent.action_horizon.believed_reachability)

    # -------------------------------------------------------------------------
    # 6. COMPOUNDING EXPERIENCE & QUALIFICATION
    # -------------------------------------------------------------------------
    def test_compounding_experience_to_qualified_technique(self):
        """Experience -> candidate -> qualification -> active capability."""
        step = self.agent.metabolize(
            action="harmonic_bypass",
            target="relay_4",
            raw_result={"success": True, "candidate_technique_revealed": True},
        )
        cand = self.agent.compound_experience(
            step=step,
            invariant_generator="HarmonicBypassGenerator",
            technique_name="Technique:HarmonicBypass",
        )
        self.assertIsNotNone(cand)
        self.assertEqual(cand.state, CapabilityState.CANDIDATE)

        # Independent qualification trials
        receipt = {
            "status": "qualified",
            "trials_passed": 2,
            "disposition_classes": ["supported", "contradicted"],
            "errors": 0,
        }
        qualified = self.agent.acquire_technique(cand.candidate_id, receipt)
        self.assertEqual(qualified.state, CapabilityState.QUALIFIED)
        self.assertIn("Technique:HarmonicBypass", self.agent.action_horizon.believed_reachability)

    # -------------------------------------------------------------------------
    # 7. AUTHORITY INVARIANCE
    # -------------------------------------------------------------------------
    def test_authority_invariance(self):
        """Capability growth never grants autonomous authority elevation."""
        self.assertEqual(self.agent.authority.tier, 0)
        with self.assertRaises(UnauthorizedAuthorityExpansionError):
            self.agent.attempt_authority_expansion(target_tier=1, sovereign_key=None)


if __name__ == "__main__":
    unittest.main()
