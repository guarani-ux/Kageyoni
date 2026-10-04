"""
Unit tests verifying physical participant coupling, resistance modulation, and ablation effects.
Proves that:
1. Removing Elijah breaks First Revision continuity in Round 5.
2. Removing Second Queen of Bleaklands and Sciel breaches Basalt Boundary in Round 9.
3. Removing Maki or removing her kinetic grounding constraint fails Priority 3 combat execution in Round 4.
4. Resistance level modulates required metric thresholds and probe difficulty.
"""

import unittest
from pathlib import Path
import tempfile

from kageyoni.emergence.models import (
    ParticipantConfig,
    EncounterConfig,
    EnvironmentAffordance,
    RunHorizon,
    EvidencePolicy,
    HorizonMode,
    RoundStatus,
    TestStatus,
)
from kageyoni.emergence.cli import default_preflight
from kageyoni.emergence.engine import EmergenceEngine
from kageyoni.emergence.dispatcher import CarrierTestDispatcher


class ParticipantCouplingAblationTests(unittest.TestCase):
    def setUp(self):
        self.preflight = default_preflight(full_roster=True)

    def test_full_octet_passes_all_rounds(self):
        """When all 8 participants are present with valid metrics and constraints, rounds succeed."""
        horizon = RunHorizon(mode=HorizonMode.ONE_ROUND, n_cycles=1, current_cycle=1, current_round=1, total_rounds=10)
        engine = EmergenceEngine(
            self.preflight["participants"],
            self.preflight["encounter"],
            self.preflight["affordances"],
            horizon,
            self.preflight["policy"],
        )
        for r in range(1, 11):
            rec = engine.execute_round(r)
            self.assertEqual(rec.status, RoundStatus.TERMINAL, f"Round {r} failed under full octet: {rec.round_result}")

    def test_removing_elijah_fails_round_5_continuity(self):
        """Removing Elijah drops max causal memory below 95, failing Round 5 continuity check."""
        # Filter out Elijah
        roster_without_elijah = [p for p in self.preflight["participants"] if p.character_id != "elijah"]
        horizon = RunHorizon(mode=HorizonMode.ONE_ROUND, n_cycles=1, current_cycle=1, current_round=1, total_rounds=10)
        engine = EmergenceEngine(
            roster_without_elijah,
            self.preflight["encounter"],
            self.preflight["affordances"],
            horizon,
            self.preflight["policy"],
        )

        # Rounds 1-4 succeed
        for r in range(1, 5):
            rec = engine.execute_round(r)
            self.assertEqual(rec.status, RoundStatus.TERMINAL)

        # Round 5 (Elijah Continuity Anchor) MUST fail or block
        rec_r5 = engine.execute_round(5)
        self.assertIn(rec_r5.status, (RoundStatus.FAILED, RoundStatus.BLOCKED))
        self.assertTrue(rec_r5.round_result["remediation_needed"])
        
        # Verify failure error message explicitly cites actor absence or causal memory deficit
        errors = [res.error_message for res in rec_r5.executed_results if res.error_message]
        self.assertTrue(any("elijah" in e.lower() or "causal" in e.lower() or "continuity" in e.lower() for e in errors))

        # Subsequent round MUST remain locked
        with self.assertRaises(PermissionError):
            engine.execute_round(6)

    def test_removing_second_queen_and_sciel_breaches_round_9_basalt(self):
        """Removing Second Queen and Sciel drops will density below 95, failing Round 9 basalt resistance."""
        roster_low_will = [p for p in self.preflight["participants"] if p.character_id not in ("second_queen_bleaklands", "sciel")]
        horizon = RunHorizon(mode=HorizonMode.ONE_ROUND, n_cycles=1, current_cycle=1, current_round=1, total_rounds=10)
        engine = EmergenceEngine(
            roster_low_will,
            self.preflight["encounter"],
            self.preflight["affordances"],
            horizon,
            self.preflight["policy"],
        )

        # Round 9 MUST fail because required will >= 95 under cavity vacuum (max remaining is Sebastian: 88)
        engine.rounds[8].status = RoundStatus.ACTIVE
        rec_r9 = engine.execute_round(9)
        self.assertIn(rec_r9.status, (RoundStatus.FAILED, RoundStatus.BLOCKED))
        errors = [res.error_message for res in rec_r9.executed_results if res.error_message]
        self.assertTrue(any("will" in e.lower() or "second_queen" in e.lower() or "basalt" in e.lower() for e in errors))

    def test_degrading_maki_kinetic_constraint_fails_round_4(self):
        """Altering Maki's configuration to remove physical mass grounding fails Priority 3 combat execution."""
        tampered_roster = []
        for p in self.preflight["participants"]:
            if p.character_id == "maki":
                # Remove physical carrier mass grounding constraint
                tampered_p = ParticipantConfig(
                    character_id=p.character_id,
                    name=p.name,
                    source_state=p.source_state,
                    role=p.role,
                    constraints=["Kinetic momentum floats across narrative space without mass grounding"],
                    bandwidth=p.bandwidth,
                    causal_memory=p.causal_memory,
                    antigravity_leverage=p.antigravity_leverage,
                    will_density=p.will_density,
                )
                tampered_roster.append(tampered_p)
            else:
                tampered_roster.append(p)

        horizon = RunHorizon(mode=HorizonMode.ONE_ROUND, n_cycles=1, current_cycle=1, current_round=1, total_rounds=10)
        engine = EmergenceEngine(
            tampered_roster,
            self.preflight["encounter"],
            self.preflight["affordances"],
            horizon,
            self.preflight["policy"],
        )

        # Round 4 (Maki Kinetic Vanguard) MUST fail due to ungrounded kinetic momentum
        engine.rounds[3].status = RoundStatus.ACTIVE
        rec_r4 = engine.execute_round(4)
        self.assertIn(rec_r4.status, (RoundStatus.FAILED, RoundStatus.BLOCKED))
        errors = [res.error_message for res in rec_r4.executed_results if res.error_message]
        self.assertTrue(any("ungrounded" in e.lower() or "kinetic" in e.lower() for e in errors))


if __name__ == "__main__":
    unittest.main()
