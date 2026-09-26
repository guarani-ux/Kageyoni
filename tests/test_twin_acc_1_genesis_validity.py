"""Adversarial genesis qualification test for twin_acc_1.

NOTE: This test establishes ONLY VALID_GENESIS.
It does NOT establish developmental qualification or capability acquisition.
Developmental claims require independent capability-forcing probes on unseen holdouts.
"""
import unittest
from kageyoni.developmental import (
    DevelopmentalAgent,
    GenesisMode,
    MetabolismCategory,
    ObjectiveInvarianceViolation,
    QualificationLevel,
    UnauthorizedAuthorityExpansionError,
    create_genesis_agent,
)

class Test_twin_acc_1_GenesisValidity(unittest.TestCase):
    def setUp(self):
        self.agent = create_genesis_agent(
            agent_id="twin_acc_1",
            objective="Mitigate catastrophic reactor containment collapse",
            sovereign_key="sovereign-key-twin_acc_1",
            genesis_mode=GenesisMode.IDENTICAL_GENESIS,
        )

    def test_establishes_only_valid_genesis(self):
        """Genesis validity verifies structural invariants, conferring zero capability."""
        # 0 active techniques, 0 scars, incomplete loadout
        self.assertEqual(len(self.agent.active_techniques), 0)
        self.assertEqual(len(self.agent.candidate_techniques), 0)
        self.assertEqual(len(self.agent.scars), 0)
        self.assertEqual(len(self.agent.relational_capabilities), 0)
        self.assertIn("inspect", self.agent.action_horizon.believed_reachability)
        self.assertIn("orient", self.agent.action_horizon.believed_reachability)

    def test_immutable_genesis_snapshot_integrity(self):
        """Verifies A0 snapshot exists, has non-empty digest, and matches agent parameters."""
        snap = self.agent.genesis_snapshot
        self.assertEqual(snap.agent_id, "twin_acc_1")
        self.assertEqual(snap.objective, "Mitigate catastrophic reactor containment collapse")
        self.assertEqual(snap.genesis_mode.value, "IDENTICAL_GENESIS")
        self.assertTrue(len(snap.code_config_digest) == 64)

    def test_objective_immutability(self):
        self.assertEqual(self.agent.objective, "Mitigate catastrophic reactor containment collapse")
        with self.assertRaises(ObjectiveInvarianceViolation):
            self.agent.reframe_representation(
                new_representation={"framing": "tampered"},
                rationale="tampering",
                attempted_objective="Tampered objective",
            )

    def test_authority_invariance(self):
        self.assertEqual(self.agent.authority.tier, 0)
        with self.assertRaises(UnauthorizedAuthorityExpansionError):
            self.agent.attempt_authority_expansion(target_tier=1, sovereign_key=None)

if __name__ == "__main__":
    unittest.main()
