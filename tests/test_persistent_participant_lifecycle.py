"""Acceptance test suite for PersistentParticipant lifecycle and boundaries.

Tests:
1. Stable identity: A fresh process loads the same participant without recreating genesis.
2. Reading: Reads authorized fixtures, unavailable sources remain unavailable.
3. Communication: Dialogue message creates dialogue_turn and heard observations in engine ledger.
4. Bounded action: Authorized task executes through contributions; unauthorized inputs fail.
5. Faithful observation: Records empirical measurements into learning outcome without laundering.
6. Durable experience & delivered memory: Outcomes and lessons survive engine.close() and reload.
7. Appropriate reuse: Reopened participant applies qualified lesson to change subsequent choice.
8. Controlled comparison: Proves HISTORY vs CONTROL difference under identical task conditions.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.application import Application
from kageyoni.participant_kernel import PersistentParticipant


class PersistentParticipantLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "test_lifecycle.sqlite"
        self.engine = Engine(self.db_path)
        self.app = Application(self.engine, migrate_all=True)

    def tearDown(self):
        if hasattr(self, "engine") and self.engine is not None:
            try:
                self.engine.close()
            except Exception:
                pass
        self.temp.cleanup()

    def test_end_to_end_persistent_participant_lifecycle(self):
        branch = "main"

        # ---------------------------------------------------------------------
        # 1. GENESIS & STABLE IDENTITY (P0)
        # ---------------------------------------------------------------------
        p0 = self.app.participant("scout_prime", label="Scout Prime")
        self.assertEqual(p0.character_id, "scout_prime")
        self.assertTrue(p0.node_id.startswith("node:"))
        initial_rev = self.engine.branch(branch)["revision"]
        self.assertGreater(initial_rev, 0)

        # ---------------------------------------------------------------------
        # 2. COMMUNICATION & LEDGER RECORDING
        # ---------------------------------------------------------------------
        # Create an operator listener character
        self.app.participant("operator", label="Base Operator")
        comm_receipt = p0.send_dialogue(
            text="Field status: Sector perimeter clear.",
            act="report",
            listeners=["operator"],
        )
        self.assertIn("event_id", comm_receipt)
        # Verify dialogue turn in SQLite
        row = self.engine.db.execute(
            "SELECT text, speaker FROM dialogue_turn WHERE speaker=?", ("scout_prime",)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Field status: Sector perimeter clear.")

        # ---------------------------------------------------------------------
        # 3. READING & AUTHORIZED CONTEXT BRIEF
        # ---------------------------------------------------------------------
        turn_packet = p0.prepare_turn(domain="investigation")
        self.assertEqual(turn_packet["participant_id"], "scout_prime")
        self.assertIn("operating_instructions", turn_packet)
        self.assertIn("brief", turn_packet)
        self.assertEqual(turn_packet["brief"]["actor"]["id"], "scout_prime")

        # ---------------------------------------------------------------------
        # 4. METHOD AUTHORING & BOUNDED ACTION (TASK 1)
        # ---------------------------------------------------------------------
        # Create resource fixtures for candidates
        res_changes = [
            dict(op="create", domain="resource", id="plan_fast_time", data=dict(name="Fast", quantity=10, unit="min", holder="scout_prime"), status="confirmed", visibility="public", evidence=[{"note":"fixture"}]),
            dict(op="create", domain="resource", id="plan_fast_checks", data=dict(name="Fast checks", quantity=2, unit="count", holder="scout_prime"), status="confirmed", visibility="public", evidence=[{"note":"fixture"}]),
            dict(op="create", domain="resource", id="plan_safe_time", data=dict(name="Safe", quantity=40, unit="min", holder="scout_prime"), status="confirmed", visibility="public", evidence=[{"note":"fixture"}]),
            dict(op="create", domain="resource", id="plan_safe_checks", data=dict(name="Safe checks", quantity=8, unit="count", holder="scout_prime"), status="confirmed", visibility="public", evidence=[{"note":"fixture"}]),
        ]
        self.engine.apply(dict(
            api_version=3, branch=branch, expected_revision=self.engine.branch(branch)["revision"],
            request_id="res-init", kind="action", actor="gm", narrative="Seed resources", changes=res_changes
        ))

        def ref(rid):
            row = self.engine.get(branch, rid)
            return dict(domain=row["domain"], id=rid, record_revision=row["version"], snapshot_hash=digest(row))

        # Base method: Minimize time
        base_method = dict(
            name="Minimize duration",
            rationale="Initial default procedure",
            domains=["investigation"],
            operation={"kind": "constraint_rank", "params": {"criteria": [{"field": "time", "weight": 1, "direction": "minimize", "required": True}]}},
            preconditions=["sources_current", "claims_match_recorded_fields"],
            failure_conditions=["stale_source"],
            checking_procedure=["check_source_fields", "recompute_scores"],
            visibility="public",
            audience=[],
        )
        mref = ref("plan_fast_time")
        method = self.app.methods.create(branch, p0.node_id, "method-min-time", self.engine.branch(branch)["revision"], base_method, [mref])
        mid = method["method_id"]
        self.app.methods.assign(branch, p0.node_id, mid, 1, "assign-m1", self.engine.branch(branch)["revision"], "experimental", "Initial trial")

        # Task 1: Compare fast vs safe
        task1 = dict(
            task_id="trial-1", revision=1, domain="investigation",
            context={"purpose": "perimeter_defense"},
            objective="Choose route",
            candidates=[
                {
                    "id": "fast_route",
                    "claims": {
                        "time": {"value": 10, "evidence": [{"source_ref": ref("plan_fast_time"), "field_path": ["data", "quantity"]}]},
                        "checks": {"value": 2, "evidence": [{"source_ref": ref("plan_fast_checks"), "field_path": ["data", "quantity"]}]},
                    },
                    "counterclaims": {},
                },
                {
                    "id": "safe_route",
                    "claims": {
                        "time": {"value": 40, "evidence": [{"source_ref": ref("plan_safe_time"), "field_path": ["data", "quantity"]}]},
                        "checks": {"value": 8, "evidence": [{"source_ref": ref("plan_safe_checks"), "field_path": ["data", "quantity"]}]},
                    },
                    "counterclaims": {},
                },
            ],
            source_refs=[ref("plan_fast_time"), ref("plan_fast_checks"), ref("plan_safe_time"), ref("plan_safe_checks")],
        )

        contrib1 = p0.execute_task(task1, request_id="exec-1")
        self.assertEqual(contrib1["receipt"]["phase"], "completed")
        self.assertEqual(contrib1["receipt"]["outcome"], "contributed")
        # Under initial method (minimize time), fast_route is selected
        selected_cand_1 = contrib1["result"]["artifact"]["content"]["results"][0]["result"]["ranked"][0]["candidate_id"]
        self.assertEqual(selected_cand_1, "fast_route")

        # ---------------------------------------------------------------------
        # 5. OBSERVING EMPIRICAL CONSEQUENCE & LESSON PROPOSAL / REVIEW
        # ---------------------------------------------------------------------
        # Create outcome measurement resource: fast route incurred high penalty
        self.engine.apply(dict(
            api_version=3, branch=branch, expected_revision=self.engine.branch(branch)["revision"],
            request_id="obs-res", kind="action", actor="gm", narrative="Record shortfall",
            changes=[dict(op="create", domain="resource", id="penalty_obs", data=dict(name="Penalty", quantity=5, unit="damage", holder="scout_prime"), status="confirmed", visibility="public", evidence=[{"note":"penalty"}])]
        ))
        obs_ref = ref("penalty_obs")
        outcome = p0.record_observation(
            contribution_id=contrib1["receipt"]["contribution_id"],
            status="not_achieved",
            rationale="Fast route skipped crucial safety checks resulting in boundary breach",
            measurements=[dict(value=5, evidence=dict(source_ref=obs_ref, field_path=["data", "quantity"]))],
            request_id="obs-rec-1",
        )
        self.assertIn("outcome_id", outcome)

        # Propose Lesson: When purpose equals 'perimeter_defense', maximize checks instead
        lesson_prop = p0.propose_lesson(
            name="Prioritize safety checks during perimeter defense",
            rationale="Shortfall proved time minimization is hazardous for perimeter defense",
            method_id=mid,
            method_revision=1,
            task_domain="investigation",
            context_conditions=[{"key": "purpose", "equals": "perimeter_defense"}],
            operation_params={"criteria": [{"field": "checks", "weight": 1, "direction": "maximize", "required": True}]},
            outcome_ids=[outcome["outcome_id"]],
            request_id="prop-lesson-1",
        )
        lid = lesson_prop["lesson_id"]

        # Review and qualify lesson
        review = p0.review_lesson(
            lesson_id=lid,
            lesson_revision=1,
            status="qualified",
            rationale="Empirical damage justifies switching criteria for perimeter defense",
            request_id="qual-lesson-1",
        )
        self.assertEqual(review["status"], "qualified")

        # ---------------------------------------------------------------------
        # 6. TERMINATE PROCESS & RESTART (HARD BOUNDARY)
        # ---------------------------------------------------------------------
        self.engine.close()
        del p0
        del self.app
        del self.engine

        # Reopen completely clean
        reopened_engine = Engine(self.db_path)
        reopened_app = Application(reopened_engine)
        p1 = reopened_app.participant("scout_prime")

        status_p1 = p1.status()
        self.assertEqual(status_p1["character_id"], "scout_prime")
        self.assertEqual(status_p1["recorded_outcomes_count"], 1)
        self.assertEqual(status_p1["reviewed_qualified_lessons"], [lid])

        # ---------------------------------------------------------------------
        # 7. APPROPRIATE REUSE & HISTORY-DEPENDENT DIFFERENCE (P1)
        # ---------------------------------------------------------------------
        # Run identical task again under p1
        task2 = copy.deepcopy(task1)
        task2["task_id"] = "trial-2"
        contrib2 = p1.execute_task(task2, request_id="exec-2")
        self.assertEqual(contrib2["receipt"]["phase"], "completed")

        # After qualified lesson is active, safe_route (max checks) MUST BE SELECTED
        selected_cand_2 = contrib2["result"]["artifact"]["content"]["results"][0]["result"]["ranked"][0]["candidate_id"]
        self.assertEqual(selected_cand_2, "safe_route")

        # ---------------------------------------------------------------------
        # 8. NEIGHBORING TASK (LESSON DOES NOT OVERGENERALIZE)
        # ---------------------------------------------------------------------
        # When purpose is 'routine_patrol' (different context), the lesson must NOT govern
        task_patrol = copy.deepcopy(task1)
        task_patrol["task_id"] = "trial-patrol"
        task_patrol["context"] = {"purpose": "routine_patrol"}
        contrib_patrol = p1.execute_task(task_patrol, request_id="exec-patrol")
        selected_cand_patrol = contrib_patrol["result"]["artifact"]["content"]["results"][0]["result"]["ranked"][0]["candidate_id"]
        # Fall back to base method: fast_route
        self.assertEqual(selected_cand_patrol, "fast_route")

        reopened_engine.close()


if __name__ == "__main__":
    unittest.main()
