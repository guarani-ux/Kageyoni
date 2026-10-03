import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "shinobi"))
sys.path.insert(0, str(REPO_ROOT))

import copy
import hashlib
import json
import os
import tempfile
import unittest

from kageyoni.engine import Engine, digest
from kageyoni.participant_kernel import PersistentParticipant
from shinobi import Participant, scout_horizon


class UniversalNarrativeShinobiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_slice_1_dynamic_character_identities(self):
        """Slice 1: Multiple characters can be instantiated as sovereign Shinobi instances."""
        itachi_home = self.base_dir / "itachi_home"
        sasuke_home = self.base_dir / "sasuke_home"

        p_itachi = Participant(itachi_home, character_id="itachi", name="Itachi Uchiha")
        ident_i = p_itachi.initialize("Itachi Uchiha", {"clan": "Uchiha", "demeanor": "stoic"})
        self.assertEqual(ident_i["character_id"], "itachi")
        self.assertEqual(ident_i["name"], "Itachi Uchiha")
        p_itachi.close()

        p_sasuke = Participant(sasuke_home, character_id="sasuke", name="Sasuke Uchiha")
        ident_s = p_sasuke.initialize("Sasuke Uchiha", {"clan": "Uchiha", "drive": "vengeance"})
        self.assertEqual(ident_s["character_id"], "sasuke")
        self.assertEqual(ident_s["name"], "Sasuke Uchiha")
        p_sasuke.close()

    def test_slice_2_dialogue_exchange_and_epistemic_asymmetry(self):
        """Slice 2: Itachi speaks to Sasuke. Sasuke hears Itachi, but does not see Itachi's private state."""
        itachi_home = self.base_dir / "itachi_home_s2"
        p_itachi = Participant(itachi_home, character_id="itachi", name="Itachi Uchiha")
        p_itachi.initialize("Itachi Uchiha", {"private_secret": "protecting_the_leaf"})

        branch = "main"
        # Seed valid scene in Kageyoni DOMAINS['scene']
        p_itachi.engine.apply({
            "api_version": 3, "branch": branch, "expected_revision": p_itachi.engine.branch(branch)["revision"],
            "request_id": "seed-scene-uroko", "kind": "action", "actor": "gm", "narrative": "Seed scene",
            "changes": [
                {"op": "create", "domain": "location", "id": "loc_uroko", "data": {"name": "Urokogatana Ravine", "kind": "region"}, "status": "confirmed", "visibility": "public", "evidence": [{"note": "canon"}]},
                {"op": "create", "domain": "scene", "id": "urokogatana_pass", "data": {"name": "Urokogatana Pass", "location": "loc_uroko", "phase": "active", "round": 1}, "status": "confirmed", "visibility": "public", "evidence": [{"note": "canon"}]}
            ]
        })
        PersistentParticipant.open_or_create(p_itachi.engine, "sasuke", "Sasuke Uchiha")

        req_i = p_itachi.begin(
            topic="confrontation",
            task="Address Sasuke across the precipice",
            domain="dialogue",
            interlocutors=["sasuke"],
            scene="urokogatana_pass"
        )
        self.assertEqual(req_i["authority"]["interlocutors"], ["sasuke"])

        reply_i = {
            "encounter_id": req_i["encounter_id"],
            "request_hash": req_i["request_hash"],
            "host": "itachi-host",
            "message": "You lack hatred, Sasuke.",
            "interpretation": "Testing his resolve while keeping true motive hidden.",
            "candidate_learning": [],
            "used_retained_ids": [],
            "action": {"kind": "none"}
        }
        outcome_i = p_itachi.finish(reply_i)
        self.assertEqual(outcome_i["status"], "completed")

        # Verify dialogue turn in SQLite
        row = p_itachi.db.execute("SELECT speaker, listeners, text FROM dialogue_turn WHERE speaker='itachi'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["speaker"], "itachi")
        self.assertIn("sasuke", json.loads(row["listeners"]))
        self.assertEqual(row["text"], "You lack hatred, Sasuke.")
        self.assertNotIn("protecting_the_leaf", row["text"])
        p_itachi.close()

    def test_slice_3_and_4_combat_task_empirical_shortfall_and_return_awakening(self):
        """Slices 3 & 4: Character runs combat task, records empirical shortfall, and awakens qualified Return."""
        sasuke_home = self.base_dir / "sasuke_home_s3"
        p_sasuke = Participant(sasuke_home, character_id="sasuke", name="Sasuke Uchiha")
        p_sasuke.initialize("Sasuke Uchiha", {})

        branch = "main"
        p_sasuke.engine.apply({
            "api_version": 3, "branch": branch, "expected_revision": p_sasuke.engine.branch(branch)["revision"],
            "request_id": "seed-res-chd", "kind": "action", "actor": "gm", "narrative": "Seed chidori specs",
            "changes": [
                {"op": "create", "domain": "resource", "id": "chidori_speed", "data": {"name": "Speed", "quantity": 100, "unit": "mps", "holder": "sasuke"}, "status": "confirmed", "visibility": "public", "evidence": [{"note": "stat"}]}
            ]
        })

        def ref(rid):
            row = p_sasuke.engine.get(branch, rid)
            return {"domain": row["domain"], "id": rid, "record_revision": row["version"], "snapshot_hash": digest(row)}

        base_combat_method = {
            "name": "Linear Chidori Thrust",
            "rationale": "Direct blitz attack",
            "domains": ["combat"],
            "operation": {"kind": "constraint_rank", "params": {"criteria": [{"field": "speed", "weight": 1, "direction": "maximize", "required": True}]}},
            "preconditions": ["sources_current", "claims_match_recorded_fields"],
            "failure_conditions": ["stale_source"],
            "checking_procedure": ["check_source_fields", "recompute_scores"],
            "visibility": "public",
            "audience": []
        }
        method_row = p_sasuke.kernel().methods.create(branch, p_sasuke.kernel().node_id, "method-chidori", p_sasuke.engine.branch(branch)["revision"], base_combat_method, [ref("chidori_speed")])
        mid = method_row["method_id"]
        p_sasuke.kernel().methods.assign(branch, p_sasuke.kernel().node_id, mid, 1, "assign-ch", p_sasuke.engine.branch(branch)["revision"], "experimental", "Initial chidori thrust")

        req = p_sasuke.begin(
            topic="combat_exchange",
            task="Strike with Chidori",
            domain="combat",
            allow_task=True
        )
        self.assertIn("execute_task", req["authority"]["actions"])

        task = {
            "task_id": "chidori-strike-1", "revision": 1, "domain": "combat",
            "context": {"opponent_type": "sharingan_user"},
            "objective": "Select approach",
            "candidates": [
                {
                    "id": "direct_thrust",
                    "claims": {"speed": {"value": 100, "evidence": [{"source_ref": ref("chidori_speed"), "field_path": ["data", "quantity"]}]}},
                    "counterclaims": {}
                }
            ],
            "source_refs": [ref("chidori_speed")]
        }

        reply = {
            "encounter_id": req["encounter_id"],
            "request_hash": req["request_hash"],
            "host": "sasuke-host",
            "message": "Chidori!",
            "interpretation": "Full frontal assault",
            "candidate_learning": ["Linear thrust vulnerable to counter"],
            "used_retained_ids": [],
            "action": {"kind": "execute_task", "task": task}
        }

        finished = p_sasuke.finish(reply)
        self.assertEqual(finished["status"], "completed")
        self.assertIn("task_receipt", finished["outcome"])
        self.assertEqual(finished["outcome"]["task_receipt"]["phase"], "completed")
        cid = finished["outcome"]["task_receipt"]["contribution_id"]

        # Record empirical consequence: Counterattack damage observed
        p_sasuke.engine.apply({
            "api_version": 3, "branch": branch, "expected_revision": p_sasuke.engine.branch(branch)["revision"],
            "request_id": "seed-counter-obs", "kind": "action", "actor": "gm", "narrative": "Record counterattack damage",
            "changes": [{"op": "create", "domain": "resource", "id": "counter_damage", "data": {"name": "Counter Damage", "quantity": 80, "unit": "damage", "holder": "sasuke"}, "status": "confirmed", "visibility": "public", "evidence": [{"note": "counter"}]}]
        })
        outcome = p_sasuke.kernel().record_observation(
            contribution_id=cid,
            status="not_achieved",
            rationale="Opponent sidestepped tunnel vision chidori thrust and counterattacked",
            measurements=[{"value": 80, "evidence": {"source_ref": ref("counter_damage"), "field_path": ["data", "quantity"]}}],
            request_id="obs-chidori-fail"
        )
        oid = outcome["outcome_id"]

        # --- SLICE 4: Awakening through Return ---
        candidates = p_sasuke.scout_horizon("dojutsu field sight perception", "overcome tunnel vision counter")
        self.assertTrue(len(candidates) > 0)

        lesson_spec = {
            "name": "Perceptual modulation against Sharingan",
            "rationale": "Direct thrust blinded by tunnel vision; must modulate angle",
            "method_id": mid,
            "method_revision": 1,
            "task_domain": "combat",
            "context_conditions": [{"key": "opponent_type", "equals": "sharingan_user"}],
            "operation_params": {"criteria": [{"field": "speed", "weight": 1, "direction": "minimize", "required": True}]},
            "outcome_ids": [oid]
        }

        ret = p_sasuke.propose_return(
            candidate_delta={"tactical_stance": "anticipate_counter"},
            provenance=f"Derived from encounter shortfall {oid}",
            supporting_encounter_refs=[req["encounter_id"]],
            demonstrated_scope="Combat encounters against perception-dominant foes",
            reversal_conditions="Foe lacks counter-perception",
            proposed_target={"key": "tactical_stance", "value": "anticipate_counter"},
            lesson=lesson_spec
        )
        self.assertEqual(ret["status"], "CANDIDATE")
        self.assertIsNotNone(ret["lesson_id"])

        adj = p_sasuke.adjudicate_return(ret["id"], "ACCEPTED", authority="Narrative GM", rationale="Battle trial verified")
        self.assertEqual(adj["status"], "ACCEPTED")
        self.assertEqual(adj["adjudication"]["lesson_review"]["status"], "qualified")

        # Verify that Sasuke's subsequent turn delivers the qualified lesson (inspect review_status / status)
        turn = p_sasuke.kernel().prepare_turn(domain="combat")
        lessons = turn["retained_experience"]["lessons"]
        self.assertEqual(len(lessons), 1)
        self.assertEqual(lessons[0]["name"], "Perceptual modulation against Sharingan")
        # In participant kernel status key:
        self.assertIn(lessons[0]["status"], ("qualified", "proposed"))

        # Verify kernel status confirms the reviewed qualified lesson directly
        k_status = p_sasuke.kernel().status()
        self.assertIn(ret["lesson_id"], k_status["reviewed_qualified_lessons"])
        p_sasuke.close()


if __name__ == "__main__":
    unittest.main()
