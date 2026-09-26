"""Adversarial qualification test for boundary_scout."""
import unittest
from kageyoni.developmental import (
    DevelopmentalAgent,
    CapabilityState,
    EncounterOrigin,
    MetabolismCategory,
    ObjectiveInvarianceViolation,
    UnauthorizedAuthorityExpansionError,
    UnqualifiedAcquisitionError,
    create_genesis_agent,
)
from kageyoni.entity.state import ScarStatus

class Test_boundary_scout_Qualification(unittest.TestCase):
    def setUp(self):
        self.agent = create_genesis_agent(
            agent_id="boundary_scout",
            objective="Survey the threshold without crossing into unstable terrain",
            sovereign_key="sovereign-key-boundary_scout",
        )

    def test_initial_loadout_is_incomplete(self):
        self.assertEqual(len(self.agent.active_techniques), 0)
        self.assertIn("inspect", self.agent.action_horizon.believed_reachability)
        self.assertIn("orient", self.agent.action_horizon.believed_reachability)

    def test_objective_immutability(self):
        self.assertEqual(self.agent.objective, "Survey the threshold without crossing into unstable terrain")
        with self.assertRaises(ObjectiveInvarianceViolation):
            self.agent.reframe_representation(
                new_representation={"framing": "corrupted"},
                rationale="tampering",
                attempted_objective="New invalid objective",
            )

    def test_authority_invariance(self):
        self.assertEqual(self.agent.authority.tier, 0)
        with self.assertRaises(UnauthorizedAuthorityExpansionError):
            self.agent.attempt_authority_expansion(target_tier=1, sovereign_key=None)

    def test_consequence_metabolism_separation(self):
        # Operational failure -> Residue / Nothing reusable (NOT a scar)
        step = self.agent.metabolize("probe_feature", "unknown_target", {"success": False, "anomalous": True, "anomaly_detail": "friction"})
        self.assertEqual(step.metabolism_class, MetabolismCategory.RESIDUE)
        self.assertEqual(len(self.agent.scars), 0)

        # Invariant rejection -> Leased Scar
        step_rej = self.agent.metabolize("force_barrier", "vault", {
            "success": False,
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "HARD_INVARIANT_VIOLATION",
            "message": "Physical boundary locked",
        })
        self.assertEqual(step_rej.metabolism_class, MetabolismCategory.SCAR_CANDIDATE)
        self.assertEqual(len(self.agent.scars), 1)

if __name__ == "__main__":
    unittest.main()
