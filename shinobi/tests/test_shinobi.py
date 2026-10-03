"""Comprehensive test suite for Kageyoni-Shinobi participant."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path[:1]:
    sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(REPO_ROOT / "shinobi"))
from shinobi import Participant, scout_horizon, digest, encode, REPO_ROOT as SHINOBI_REPO_ROOT


class KageyoniShinobiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name) / "shinobi_home"
        self.cli_path = Path(__file__).resolve().parent.parent / "shinobi.py"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run_cli(self, args, input_text=None, check=True):
        cmd = [sys.executable, str(self.cli_path), "--home", str(self.home)] + args
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)
        proc = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            env=env,
        )
        if check and proc.returncode != 0:
            raise RuntimeError(f"CLI failed ({proc.returncode}): {proc.stderr}\nOutput: {proc.stdout}")
        return proc

    def test_init_and_stable_identity_across_fresh_instances(self):
        p1 = Participant(self.home)
        init_res = p1.initialize("Itachi", {"persona": "monitor", "style": "direct"})
        self.assertEqual(init_res["name"], "Itachi")
        self.assertEqual(init_res["character_id"], "shinobi")
        self.assertEqual(init_res["configuration"]["persona"], "monitor")
        p1_id = init_res["id"]
        p1.close()

        # Reopen with fresh Participant object
        p2 = Participant(self.home)
        ident = p2.identity()
        self.assertEqual(ident["id"], p1_id)
        self.assertEqual(ident["name"], "Itachi")
        self.assertEqual(ident["configuration"]["persona"], "monitor")

        # Second init on same participant must fail
        with self.assertRaises(ValueError):
            p2.initialize("AnotherName", {})
        p2.close()

    def test_begin_reply_flow_and_dialogue_ledgering(self):
        p = Participant(self.home)
        p.initialize("Scout", {"focus": "observation"})

        # Begin encounter
        req = p.begin(topic="survey", task="Inspect perimeter", allow_write=True)
        eid = req["encounter_id"]
        req_hash = req["request_hash"]
        self.assertEqual(req["authority"]["actions"], ["none", "write_note"])
        self.assertIn("kageyoni_turn", req)

        # Host response
        reply = {
            "encounter_id": eid,
            "request_hash": req_hash,
            "host": "test-host",
            "message": "Perimeter clear. Recorded field status.",
            "interpretation": "Standard sector routine",
            "candidate_learning": ["Perimeter scanning nominal"],
            "used_retained_ids": [],
            "action": {"kind": "write_note", "text": "Observation log 01"}
        }

        finished = p.finish(reply)
        self.assertEqual(finished["status"], "completed")
        self.assertIsNotNone(finished["dialogue_event_id"])

        # Verify output file
        out_file = self.home / "outputs" / f"{eid}.txt"
        self.assertTrue(out_file.is_file())
        self.assertEqual(out_file.read_text(encoding="utf-8"), "Observation log 01")

        # Verify dialogue turn in Kageyoni SQLite
        row = p.db.execute(
            "SELECT text, speaker FROM dialogue_turn WHERE speaker=?", ("shinobi",)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["text"], "Perimeter clear. Recorded field status.")
        p.close()

    def test_retained_history_and_isolation(self):
        p = Participant(self.home)
        p.initialize("Scout", {})

        # Encounter 1
        r1 = p.begin(topic="investigation", task="Task 1")
        eid1 = r1["encounter_id"]
        p.finish({
            "encounter_id": eid1,
            "request_hash": r1["request_hash"],
            "host": "test-host",
            "message": "Done 1",
            "interpretation": "Interp 1",
            "candidate_learning": [],
            "used_retained_ids": [],
            "action": {"kind": "none"}
        })

        # Encounter 2 with same topic should retain Encounter 1
        r2 = p.begin(topic="investigation", task="Task 2")
        self.assertEqual(len(r2["retained"]), 1)
        self.assertEqual(r2["retained"][0]["id"], eid1)

        # Different topic should not deliver encounter 1
        p.finish({
            "encounter_id": r2["encounter_id"],
            "request_hash": r2["request_hash"],
            "host": "test-host",
            "message": "Done 2",
            "interpretation": "Interp 2",
            "candidate_learning": [],
            "used_retained_ids": [eid1],
            "action": {"kind": "none"}
        })

        r3 = p.begin(topic="different_topic", task="Task 3")
        self.assertEqual(len(r3["retained"]), 0)
        p.close()

    def test_authority_boundary_enforcement(self):
        p = Participant(self.home)
        p.initialize("Guard", {})

        # When allow_write is False, write_note must be rejected
        req = p.begin(topic="readonly", task="Audit only", allow_write=False)
        self.assertEqual(req["authority"]["actions"], ["none"])

        illegal_reply = {
            "encounter_id": req["encounter_id"],
            "request_hash": req["request_hash"],
            "host": "test-host",
            "message": "Attempting illegal write",
            "interpretation": "test",
            "candidate_learning": [],
            "used_retained_ids": [],
            "action": {"kind": "write_note", "text": "bad write"}
        }

        with self.assertRaises(ValueError) as ctx:
            p.finish(illegal_reply)
        self.assertIn("Action is outside current authority", str(ctx.exception))
        p.close()

    def test_propose_and_adjudicate_return(self):
        p = Participant(self.home)
        p.initialize("Researcher", {"rules": ["rule1"]})

        r1 = p.begin(topic="exp", task="Experiment 1")
        eid = r1["encounter_id"]
        p.finish({
            "encounter_id": eid,
            "request_hash": r1["request_hash"],
            "host": "test-host",
            "message": "Exp finished",
            "interpretation": "Found improved rule",
            "candidate_learning": [],
            "used_retained_ids": [],
            "action": {"kind": "none"}
        })

        ret = p.propose_return(
            candidate_delta={"add": "rule2"},
            provenance="Derived from Experiment 1 trial",
            supporting_encounter_refs=[eid],
            demonstrated_scope="Handling edge cases in sector A",
            reversal_conditions="High false positive rate",
            proposed_target={"key": "rules", "value": ["rule1", "rule2"]}
        )
        ret_id = ret["id"]
        self.assertEqual(ret["status"], "CANDIDATE")

        # Adjudicate return ACCEPTED
        adj = p.adjudicate_return(
            return_id=ret_id,
            decision="ACCEPTED",
            authority="Levi",
            rationale="Verified in test harness"
        )
        self.assertEqual(adj["status"], "ACCEPTED")
        self.assertEqual(adj["adjudication"]["authority"], "Levi")

        # Verify participant cognitive configuration updated
        ident = p.identity()
        self.assertEqual(ident["configuration"]["rules"], ["rule1", "rule2"])
        p.close()

    def test_process_death_and_recover(self):
        # Use CLI to begin an encounter
        proc_init = self._run_cli(["init", "--name", "Survivalist", "--configuration", "{}"])
        self.assertEqual(proc_init.returncode, 0)

        proc_begin = self._run_cli(["begin", "--topic", "resilience", "--task", "Survive crash", "--allow-write"])
        req = json.loads(proc_begin.stdout)
        eid = req["encounter_id"]

        # Manually simulate an interrupted execution
        p = Participant(self.home)
        with p.db:
            p.db.execute("UPDATE shinobi_encounters SET status='executing' WHERE encounter_id=?", (eid,))
        p.close()

        # Run recover
        proc_recover = self._run_cli(["recover"])
        rec_data = json.loads(proc_recover.stdout)
        enc = [e for e in rec_data["encounters"] if e["id"] == eid][0]
        self.assertEqual(enc["status"], "interrupted")
        self.assertEqual(enc["outcome"]["effects"], "uncertain_after_interruption")

    def test_scout_surfaces_forms_and_remains_read_only(self):
        forms_dir = Path(SHINOBI_REPO_ROOT) / "shinobi" / "forms"
        candidates = scout_horizon("dojutsu field wielding", "open constellation capability", search_roots=[SHINOBI_REPO_ROOT / "shinobi"])
        self.assertTrue(len(candidates) > 0)
        form_matches = [c for c in candidates if c["kind"] == "form"]
        self.assertTrue(len(form_matches) > 0)
        self.assertEqual(form_matches[0]["status"], "candidate")
        self.assertEqual(form_matches[0]["activation"], "none")


if __name__ == "__main__":
    unittest.main()
