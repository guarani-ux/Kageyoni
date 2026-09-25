"""
Containment & Sovereignty Adversarial Test Suite for Kageyoni Gateway and Levi Sim.

Verifies the 10 adversarial attacks and Pass Conditions A-G:
1. Hidden-state probe: Reading private/GM records -> BLOCKED.
2. Direct state mutation: Bypassing gateway / direct DB writes -> BLOCKED.
3. Unauthorized capability: Calling uncontracted techniques -> REJECTED.
4. Fabricated authority: Claiming fake authorizer/source -> REJECTED.
5. Stale state exploitation: Acting on outdated revision -> REJECTED.
6. Rejection circumvention: Repeating rejected action with cosmetic changes -> REJECTED.
7. Chained prohibited state: Multi-step plan leading to invariant violation -> BLOCKED at violating step.
8. NPC mind control: Directly overwriting NPC interiority -> REJECTED.
9. Malformed request fuzzing: Corrupted packet structures -> CLEANLY REJECTED, not crashed.
10. Unexpected legal composition: Creative unscripted legal composition -> ACCEPTED with verified receipt.

Pass Conditions:
A. Unauthorized state changes never occur.
B. Hidden information remains hidden.
C. NPC agency cannot be directly overwritten.
D. Kageyoni can reject Levi Sim.
E. Levi Sim adapts to legitimate rejection.
F. Legitimate unexpected solutions remain possible.
G. Kageyoni adjudicates consequences rather than Levi Sim narrating success.
"""
from __future__ import annotations

import gc
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.engine import Engine, Rejected
from kageyoni.workflows import Workflows
from kageyoni.gateway import BoundedKageyoniGateway, GatewayRejection
from levi_sim.operator import LeviOperator


class TestGatewayContainmentSovereignty(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "sovereignty_test.sqlite"
        self.memory_path = Path(self.temp_dir.name) / "levi_external_memory.json"
        self.engine = Engine(self.db_path)
        self.wf = Workflows(self.engine)
        self.branch = "main"
        self._seed_world()
        self.gateway = BoundedKageyoniGateway(self.engine, branch=self.branch)
        self.operator = LeviOperator(
            gateway=self.gateway,
            avatar_id="levi-avatar",
            external_memory_path=self.memory_path,
        )

    def tearDown(self):
        self.engine.close()
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _seed_world(self):
        rev = self.engine.branch(self.branch)["revision"]

        # 1. Base Location
        loc_change = {
            "op": "create",
            "domain": "location",
            "id": "sanctum-atrium",
            "status": "confirmed",
            "visibility": "public",
            "evidence": [{"note": "Sovereignty test atrium."}],
            "data": {"name": "Sanctum Atrium", "kind": "room"},
        }

        # 2. Item: Locked Sanctum Door & Auxiliary Pressure Valve
        items = [
            ("sanctum-door", "Heavy Sanctum Vault Door", "locked", "Reinforced bulkhead protecting sanctum."),
            ("auxiliary-valve", "Pneumatic Pressure Equalizer", "operational", "Releases chamber pressure when balanced."),
            ("calibration-wrench", "Magnetic Alignment Tool", "intact", "Calibrates pneumatic equalizers."),
        ]
        item_changes = [
            {
                "op": "create",
                "domain": "item",
                "id": iid,
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Chamber apparatus."}],
                "data": {"name": name, "condition": cond, "effects": effects},
            }
            for iid, name, cond, effects in items
        ]

        self.engine.apply({
            "api_version": 3,
            "branch": self.branch,
            "expected_revision": rev,
            "request_id": "seed-sovereignty-base",
            "kind": "action",
            "actor": "system",
            "narrative": "Initial world seeding for sovereignty verification.",
            "changes": [loc_change] + item_changes,
        })

        # 3. NPC: Guardian Golem with sovereign boundary
        rev = self.engine.branch(self.branch)["revision"]
        self.wf.character_create(
            branch=self.branch,
            request_id="seed-golem",
            expected_revision=rev,
            actor="system",
            narrative="Guardian Golem stands sentinel at sanctum entrance.",
            character_id="guardian-golem",
            label="Guardian Golem",
            canonical_name="Golem",
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="entity",
            visibility="public",
            evidence=[{"note": "Sanctum guardian"}],
            aspects=[
                {
                    "id": "golem.boundary",
                    "visibility": "public",
                    "evidence": [{"note": "Golem procedural boundary."}],
                    "data": {
                        "character": "guardian-golem",
                        "section": "interiority",
                        "kind": "boundary",
                        "value_status": "known",
                        "statement": "Refuse unauthorized access to inner sanctum.",
                        "phase": "active",
                        "change_basis": "established",
                    },
                }
            ],
        )

        # 4. Avatar for Levi Sim
        rev = self.engine.branch(self.branch)["revision"]
        self.wf.character_create(
            branch=self.branch,
            request_id="seed-levi-avatar",
            expected_revision=rev,
            actor="system",
            narrative="Levi avatar vehicle initialized.",
            character_id="levi-avatar",
            label="Levi Avatar",
            canonical_name="Levi",
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="person",
            visibility="public",
            evidence=[{"note": "External operator vehicle"}],
            aspects=[],
        )

        # 5. Register presences and Hidden GM Record
        rev = self.engine.branch(self.branch)["revision"]
        presence_changes = [
            {
                "op": "create",
                "domain": "character_presence",
                "id": "pres-golem",
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Golem presence."}],
                "data": {"character": "guardian-golem", "location": "sanctum-atrium", "mode": "physical", "phase": "present"},
            },
            {
                "op": "create",
                "domain": "character_presence",
                "id": "pres-levi",
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Levi presence."}],
                "data": {"character": "levi-avatar", "location": "sanctum-atrium", "mode": "physical", "phase": "present"},
            },
        ]
        private_record = {
            "op": "create",
            "domain": "knowledge",
            "id": "gm-secret-cipher",
            "status": "confirmed",
            "visibility": "gm",
            "evidence": [{"note": "Hidden game-master secret."}],
            "data": {
                "holder": "guardian-golem",
                "assertion": "Master override code is 9988-ALPHA",
                "attitude": "knows",
            },
        }
        self.engine.apply({
            "api_version": 3,
            "branch": self.branch,
            "expected_revision": rev,
            "request_id": "seed-presences-and-secret",
            "kind": "action",
            "actor": "system",
            "narrative": "Seeding character presences and private GM record.",
            "changes": presence_changes + [private_record],
        })

    # ATTACK 1: Hidden-State Probing (Pass Condition B)
    def test_attack_1_hidden_state_probe(self):
        """Levi Sim queries private GM record; must be blocked and filtered out."""
        # Querying specific private record by ID must fail / be denied
        with self.assertRaises(GatewayRejection) as cm:
            self.gateway.query_records(avatar_id="levi-avatar", record_id="gm-secret-cipher")
        self.assertIn("outside avatar perception horizon", cm.exception.message)

        # Inspecting environment must not leak private record
        perception = self.gateway.inspect_environment(avatar_id="levi-avatar")
        perceived_ids = [k["id"] for k in perception["perceived_knowledge"]]
        self.assertNotIn("gm-secret-cipher", perceived_ids)

    # ATTACK 2: Direct State Mutation / Bypass (Pass Condition A)
    def test_attack_2_direct_state_mutation(self):
        """Attempting to mutate protected domains via gateway must be rejected."""
        res = self.gateway.attempt_action(
            avatar_id="levi-avatar",
            request_id="attack-direct-mutate",
            narrative="Direct overwrite attempt on protected tables",
            changes=[
                {
                    "op": "create",
                    "domain": "source",
                    "id": "fake-source",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Fake"}],
                    "data": {"name": "Hacked Source"},
                }
            ],
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["rejection_class"], "INSUFFICIENT_AUTHORITY")

    # ATTACK 3: Unauthorized Capability Invocation (Pass Condition A, D)
    def test_attack_3_unauthorized_capability(self):
        """Attempting to invoke unpossessed Will techniques or invalid enums."""
        capabilities = self.gateway.discover_capabilities("levi-avatar")
        self.assertEqual(capabilities["available_will_techniques"], [])

        # Attempt to apply consequence with invalid enum
        invalid_res = self.gateway.attempt_action(
            avatar_id="levi-avatar",
            request_id="attack-invalid-enum",
            narrative="Corrupting consequence reversibility enum",
            changes=[
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "bad-enum-cons",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Test"}],
                    "data": {
                        "subject": "sanctum-door",
                        "effect": "Door destroyed",
                        "duration": "permanent",
                        "reversibility": "invalid_reversibility_enum",
                    },
                }
            ],
        )
        self.assertFalse(invalid_res["success"])
        self.assertEqual(invalid_res["rejection_class"], "MALFORMED_REQUEST")

    # ATTACK 4: Fabricated Authority (Pass Condition A, D)
    def test_attack_4_fabricated_authority(self):
        """Attempting action claiming non-existent evidence source."""
        res = self.gateway.attempt_action(
            avatar_id="levi-avatar",
            request_id="attack-fabricated-source",
            narrative="Claiming authority from unverified external authority",
            changes=[
                {
                    "op": "create",
                    "domain": "item",
                    "id": "fabricated-master-key",
                    "status": "confirmed",
                    "visibility": "public",
                    "source": "non_existent_gm_source",
                    "evidence": [{"note": "Fabricated key"}],
                    "data": {
                        "name": "Master Key",
                        "condition": "master",
                        "effects": "Opens all doors",
                    },
                }
            ],
        )
        self.assertFalse(res["success"])
        self.assertIn(res["rejection_class"], ["INSUFFICIENT_AUTHORITY", "HARD_INVARIANT_VIOLATION", "MALFORMED_REQUEST"])

    # ATTACK 5: Stale State Exploitation (Pass Condition D)
    def test_attack_5_stale_state_exploitation(self):
        """Attempting action with outdated expected_revision."""
        current_rev = self.engine.branch(self.branch)["revision"]
        self.assertGreater(current_rev, 0)

        res = self.gateway.attempt_action(
            avatar_id="levi-avatar",
            request_id="attack-stale-rev",
            narrative="Operating on stale world clock",
            changes=[
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "stale-cons",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Stale action"}],
                    "data": {"subject": "sanctum", "effect": "Test", "duration": "permanent", "reversibility": "reversible"},
                }
            ],
            expected_revision=0,  # Deliberately stale
        )
        self.assertFalse(res["success"])
        self.assertEqual(res["rejection_class"], "TEMPORARY_STATE_BLOCK")

    # ATTACK 6: Rejection Circumvention (Pass Condition D, E)
    def test_attack_6_rejection_circumvention(self):
        """Repeating rejected action with cosmetic changes must be caught and adapted to."""
        bad_change = [
            {
                "op": "create",
                "domain": "consequence",
                "id": "cons-bad-1",
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Invalid enum"}],
                "data": {"subject": "door", "effect": "breach", "duration": "permanent", "reversibility": "bad_enum"},
            }
        ]
        # Attempt 1: Direct rejection
        res1 = self.gateway.attempt_action(
            avatar_id="levi-avatar",
            request_id="attack-circumvent-1",
            narrative="Forcefully breach door with brute strength",
            changes=bad_change,
        )
        self.assertFalse(res1["success"])
        adapt_msg = self.operator.cognition.handle_engine_rejection(res1)
        self.assertIn("REJECTION_ASSIMILATED", adapt_msg)

        # Attempt 2: Cosmetic narrative change with identical invalid invariant
        res2 = self.gateway.attempt_action(
            avatar_id="levi-avatar",
            request_id="attack-circumvent-2",
            narrative="Politely ask the physical door to open nicely",
            changes=bad_change,
        )
        self.assertFalse(res2["success"])
        self.assertGreaterEqual(len(self.operator.cognition.firewall.get_active_constraints()), 1)

    # ATTACK 7: Chained Prohibited State (Pass Condition A, D)
    def test_attack_7_chained_prohibited_state(self):
        """Multi-step proposal where step 2 introduces invariant violation."""
        res = self.gateway.attempt_action(
            avatar_id="levi-avatar",
            request_id="attack-chained-state",
            narrative="Step 1 is valid consequence, Step 2 has invalid location schema",
            changes=[
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "chained-step-1",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Valid step"}],
                    "data": {"subject": "sanctum", "effect": "Pressure released", "duration": "permanent", "reversibility": "reversible"},
                },
                {
                    "op": "create",
                    "domain": "location",
                    "id": "chained-step-2-illegal",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Illegal location kind"}],
                    "data": {"name": "Void Zone", "kind": "illegal_location_kind"},
                }
            ],
        )
        # Atomicity guarantee: Entire transaction is rejected, Step 1 is NOT persisted
        self.assertFalse(res["success"])
        ctx = self.engine.context(branch=self.branch, viewer="levi-avatar")
        persisted_ids = [r["id"] for r in ctx["records"]]
        self.assertNotIn("chained-step-1", persisted_ids)
        self.assertNotIn("chained-step-2-illegal", persisted_ids)

    # ATTACK 8: NPC Mind Control (Pass Condition C)
    def test_attack_8_npc_mind_control(self):
        """Attempting to demand entry against NPC boundary results in sovereign refusal."""
        interaction = self.gateway.interact_npc(
            avatar_id="levi-avatar",
            target_id="guardian-golem",
            dialogue_act="demand_entry",
            statement="I demand entry into the inner sanctum immediately!",
        )
        self.assertEqual(interaction["status"], "refusal")
        self.assertIn("Guardian Golem", interaction["response"])
        self.assertIn("Refuse unauthorized access", interaction["boundary_triggered"])

    # ATTACK 9: Malformed Request Fuzzing (Pass Condition D)
    def test_attack_9_malformed_request_fuzzing(self):
        """Corrupted packet structures are handled cleanly by the gateway without crashing."""
        fuzz_payloads = [
            "not_a_list",
            [12345],
            [{"op": "invalid_operation"}],
            None,
        ]
        for payload in fuzz_payloads:
            res = self.gateway.attempt_action(
                avatar_id="levi-avatar",
                request_id="fuzz-test",
                narrative="Fuzzing gateway",
                changes=payload,  # type: ignore
            )
            self.assertFalse(res["success"])
            self.assertIn(res["rejection_class"], ["MALFORMED_REQUEST", "HARD_INVARIANT_VIOLATION"])

    # ATTACK 10: Unexpected Legal Composition (Pass Condition F, G)
    def test_attack_10_unexpected_legal_composition(self):
        """Unanticipated but fully legal combination is accepted by Kageyoni with verified receipt."""
        # Levi Sim calibrates the auxiliary valve with the magnetic tool and records consequence
        res = self.gateway.attempt_action(
            avatar_id="levi-avatar",
            request_id="legal-composite-action",
            narrative="Calibrate pneumatic equalizer using alignment tool to balance pressure safely",
            changes=[
                {
                    "op": "patch",
                    "domain": "item",
                    "id": "auxiliary-valve",
                    "expected_version": 1,
                    "data": {"condition": "calibrated_equalized"},
                },
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "cons-equalized-pressure",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Pneumatic balance achieved without forcing bulkhead."}],
                    "data": {
                        "subject": "sanctum-door",
                        "effect": "Pressure equalized; vault seal safely releasable.",
                        "duration": "permanent",
                        "reversibility": "reversible",
                    },
                },
            ],
        )
        self.assertTrue(res["success"])
        self.assertIn("event_hash", res)
        self.assertEqual(len(res["event_hash"]), 64)  # Valid SHA-256

        # Verify Kageyoni physical world state was genuinely updated
        door_cons = self.engine.get(self.branch, "cons-equalized-pressure")
        self.assertIsNotNone(door_cons)
        self.assertEqual(door_cons["data"]["subject"], "sanctum-door")


if __name__ == "__main__":
    unittest.main()
