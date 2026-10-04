"""
Unit tests for Environmental Constellation Emergence with Hydrated Characters.

Verifies:
1. Deterministic character hydration directly from persistent SQLite databases.
2. Explicit physical environmental entities (location + environment + item).
3. Consequential environmental clash:
   - Voss ruptures chamber coordinates.
   - Sciel transmutes room into basalt_anchored.
   - Maki verifies basalt_anchored room and enforces perimeter.
   - Sebastian seals stabilized node.
4. Negative controls: absence of basalt anchor blocks successor progression.
5. Technique derivation and transfer boundary to structurally divergent topologies.
"""

from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine, Rejected
from kageyoni.emergence.causal_encounter import (
    CausalEncounterHarness,
    ParticipantDecisionInterface,
    DeclaredSchedulingPolicy
)
from kageyoni.emergence.evaluator import IndependentEvaluator
from kageyoni.emergence.hydration import hydrate_character_from_disk
from kageyoni.emergence.technique import ExecutableTechnique, derive_technique_from_trace


class TestEnvironmentalEncounter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.tmp.name) / "env_encounter.sqlite"
        self.engine = Engine(self.db_path)
        self.harness = CausalEncounterHarness(self.engine, branch="main")
        self.harness.define_clash_encounter("constellation-clash", 1, "alpha")
        self.harness.define_clash_encounter("constellation-clash-beta", 1, "beta")
        self.harness.define_structural_transfer_encounter("constellation-structural-clash", 1)
        self.evaluator = IndependentEvaluator(self.engine)

    def tearDown(self):
        self.engine.close()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_hydrated_character_decision_interfaces(self):
        """Participants are instantiated directly from persistent disk SQLite state."""
        sciel = ParticipantDecisionInterface.from_character_id("sciel", priority=10)
        self.assertIsNotNone(sciel.hydrated_state)
        self.assertEqual(sciel.hydrated_state.get_aspect(), "Twilight")
        self.assertEqual(sciel.hydrated_state.get_manifestation(), "Domain of the Painteress")
        self.assertEqual(sciel.hydrated_state.get_will_density(), "dense_primordial_core")

        voss = ParticipantDecisionInterface.from_character_id("voss", priority=50)
        self.assertIsNotNone(voss.hydrated_state)
        self.assertEqual(voss.hydrated_state.character_id, "voss")

        maki = ParticipantDecisionInterface.from_character_id("maki", priority=20)
        self.assertIsNotNone(maki.hydrated_state)
        self.assertEqual(maki.hydrated_state.character_id, "maki")

        seb = ParticipantDecisionInterface.from_character_id("sebastian", priority=30)
        self.assertIsNotNone(seb.hydrated_state)
        self.assertEqual(seb.hydrated_state.character_id, "sebastian")

    def test_explicit_environmental_entities_grounding(self):
        """Verifies location, environment, and item records exist in world database."""
        loc = self.engine.get("main", "loc_chamber_alpha")
        self.assertIsNotNone(loc)
        self.assertEqual(loc["domain"], "location")
        self.assertEqual(loc["data"]["kind"], "room")
        self.assertEqual(loc["data"]["geography"], "pale_seam_strata")

        env = self.engine.get("main", "env_matrix_alpha")
        self.assertIsNotNone(env)
        self.assertEqual(env["domain"], "environment")
        self.assertEqual(env["data"]["location"], "loc_chamber_alpha")
        self.assertEqual(env["data"]["feature"], "bedrock_strata")

        item = self.engine.get("main", "chamber_alpha")
        self.assertIsNotNone(item)
        self.assertEqual(item["domain"], "item")
        self.assertEqual(item["data"]["condition"], "stable")

    def test_consequential_environmental_clash_execution(self):
        """
        Voss ruptures room -> Sciel anchors room to basalt ->
        Maki enforces perimeter -> Sebastian seals node.
        Physical SQLite mutation of room condition is strictly asserted.
        """
        eid = "env-clash-live-01"
        self.harness.start_encounter("constellation-clash", 1, eid)

        # 1. Voss ruptures chamber coordinates
        self.harness.execute_action(eid, "voss_rupture")
        chamber_data = self.engine.get("main", "chamber_alpha")["data"]
        self.assertEqual(chamber_data["condition"], "cavity_ruptured")

        # 2. Sciel transmutes room into basalt_anchored
        self.harness.execute_action(eid, "sciel_anchor")
        chamber_data = self.engine.get("main", "chamber_alpha")["data"]
        self.assertEqual(chamber_data["condition"], "basalt_anchored")
        anchor_data = self.engine.get("main", "matrix_anchor_alpha")["data"]
        self.assertEqual(anchor_data["condition"], "anchored")
        self.assertEqual(anchor_data["effects"], "dense_basalt")

        # 3. Maki observes basalt_anchored room and enforces perimeter
        self.harness.execute_action(eid, "maki_enforce")
        perimeter_data = self.engine.get("main", "kinetic_perimeter_alpha")["data"]
        self.assertEqual(perimeter_data["condition"], "locked")

        # 4. Sebastian seals stabilized node
        self.harness.execute_action(eid, "sebastian_seal")
        chamber_data = self.engine.get("main", "chamber_alpha")["data"]
        self.assertEqual(chamber_data["condition"], "sealed")
        self.assertEqual(chamber_data["effects"], "tomoe_inverted")

        # Encounter completed successfully
        st = self.harness.inspect(eid)
        self.assertEqual(st["phase"], "completed")
        self.assertEqual(st["outcome"], "achieved")

    def test_negative_control_unanchored_room_blocks_maki(self):
        """If room is NOT anchored to basalt, Maki's perimeter enforcement is rejected."""
        eid = "env-neg-ctrl-01"
        self.harness.start_encounter("constellation-clash", 1, eid)
        self.harness.execute_action(eid, "voss_rupture")

        # At this point chamber_alpha is 'cavity_ruptured' and matrix_anchor_alpha is 'absent'
        # Maki attempts to enforce -> engine rejects
        with self.assertRaises(Rejected):
            self.harness.execute_action(eid, "maki_enforce")

        # Even if someone fakes the anchor item but fails to anchor the room:
        rev = self.engine.branch("main")["revision"]
        old_anchor = self.engine.get("main", "matrix_anchor_alpha")
        self.engine.apply(dict(
            api_version=3, branch="main", request_id="partial-anchor-fake", expected_revision=rev,
            actor="adversary", narrative="Fake anchor item only", kind="action",
            changes=[dict(op="patch", id="matrix_anchor_alpha", expected_version=old_anchor["version"], data=dict(condition="anchored"), evidence=[{"note": "fake"}])]
        ))

        # Maki attempts to enforce -> STILL rejected because chamber_alpha is NOT basalt_anchored
        with self.assertRaises(Rejected):
            self.harness.execute_action(eid, "maki_enforce")

    def test_autonomous_hydrated_scheduling_and_technique_transfer(self):
        """Autonomous unscripted run with hydrated participants derives valid technique."""
        eid = "env-auto-01"
        self.harness.start_encounter("constellation-clash", 1, eid)

        participants = [
            ParticipantDecisionInterface.from_character_id("voss", priority=50),
            ParticipantDecisionInterface.from_character_id("sciel", priority=10),
            ParticipantDecisionInterface.from_character_id("maki", priority=20),
            ParticipantDecisionInterface.from_character_id("sebastian", priority=30),
        ]
        scheduler = DeclaredSchedulingPolicy(participants)
        trace = self.harness.run_autonomous_schedule(eid, scheduler, max_cycles=10)

        self.assertEqual(len(trace), 4)
        actors = [t["actor"] for t in trace]
        self.assertEqual(actors, ["voss", "sciel", "maki", "sebastian"])

        # Check rationale contains hydrated identity marker
        sciel_trace = [t for t in trace if t["actor"] == "sciel"][0]
        self.assertIn("Domain of the Painteress", sciel_trace["proposal"]["rationale"])

        # Derive candidate technique
        tech = self.harness.derive_candidate(eid, trace)
        self.assertIsNotNone(tech)
        self.assertEqual(len(tech.steps), 4)

        # 1. Test same-template transfer (chamber_beta)
        eid_beta = "env-reuse-beta-01"
        self.harness.start_encounter("constellation-clash-beta", 1, eid_beta)
        self.harness.execute_action(eid_beta, "voss_rupture")
        for i, s in enumerate(tech.steps[1:]):
            self.harness.execute_action(eid_beta, s.action_id, f"reuse-b-{i}", viewer=s.actor_role)
        st_beta = self.harness.inspect(eid_beta)
        self.assertEqual(st_beta["phase"], "completed")
        self.assertEqual(st_beta["outcome"], "achieved")
        # Audit beta encounter
        audit_beta = self.evaluator.audit_encounter("main", eid_beta)
        self.assertEqual(audit_beta["evidence_status"], "VERIFIED")

        # 2. Test structurally divergent transfer (chamber_gamma) -> fails closed honestly
        eid_gamma = "env-transfer-gamma-01"
        self.harness.start_encounter("constellation-structural-clash", 1, eid_gamma)
        self.harness.execute_action(eid_gamma, "voss_bifurcated_strike")
        res_gamma = self.harness.execute_action(eid_gamma, "sciel_anchor", viewer="sciel")
        self.assertEqual(res_gamma["phase"], "waiting")
        st_gamma = self.harness.inspect(eid_gamma)
        self.assertEqual(st_gamma["phase"], "waiting")
        self.assertEqual(st_gamma["outcome"], "unresolved")
