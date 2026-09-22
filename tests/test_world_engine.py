import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine, Rejected
from kageyoni.workflows import Workflows


EVIDENCE = [{"note": "Noncanonical acceptance fixture; never import into canon."}]


def create(domain, rid, **data):
    return {
        "op": "create", "domain": domain, "id": rid, "data": data,
        "status": "proposed", "visibility": "public", "evidence": EVIDENCE,
    }


def patch(rid, version, **data):
    return {
        "op": "patch", "id": rid, "expected_version": version,
        "data": data, "evidence": EVIDENCE,
    }


class IntegratedFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.e = Engine(Path(self.temp.name) / "fixture.sqlite")
        changes = [
            create("location", "near-bank", name="Near bank", kind="region"),
            create("location", "far-bank", name="Far bank", kind="region"),
            create("character", "specialist", name="Bridge specialist", entity_kind="person", location="near-bank", condition="ready"),
            create("character", "generalist", name="Generally powerful traveler", entity_kind="person", location="near-bank", condition="ready"),
            create("character", "mother", name="Mother", entity_kind="person", location="near-bank"),
            create("character", "child", name="Child", entity_kind="person", location="near-bank"),
            create("faction", "family", name="Crossing family", purpose="Reach the far bank"),
            create("affiliation", "mother-family", character="mother", faction="family", allegiance="member", role="parent", consent="yes"),
            create("affiliation", "child-family", character="child", faction="family", allegiance="member", role="child", consent="no"),
            create("relationship", "mother-child", subject="mother", object="child", kind="family", feeling="protective", tension="child refuses the crossing"),
            create("environment", "bridge", location="near-bank", feature="Damaged bridge", kind="infrastructure", rule="load capacity is uncertain", duration="until repaired", ending_condition="repair"),
            create("environment", "water", location="near-bank", feature="Rising water", kind="hazard", rule="conceals footing while increasing crossing risk", duration="until recedes", ending_condition="recession"),
            create("route", "crossing", origin="near-bank", destination="far-bank", access="open", conditions="Bridge or alternate crossing", duration="one hour"),
            create("ability", "bridgecraft", name="Bridgecraft", function="Read load paths and choose safer footing", conditions="Near damaged structures", limits="Does not guarantee a safe crossing"),
            create("capability", "specialist-bridgecraft", character="specialist", ability="bridgecraft", mastery="specialist", condition="ready", demonstrated_use="fixture only"),
            create("clock", "clock", name="Fixture clock", tick=0, unit="hour"),
            create("scene", "crossing-scene", name="Bridge crossing", location="near-bank", clock="clock", phase="active", round=0),
            create("participation", "specialist-present", scene="crossing-scene", character="specialist"),
            create("participation", "family-present", scene="crossing-scene", character="mother"),
            create("participation", "child-present", scene="crossing-scene", character="child"),
        ]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": 0,
            "request_id": "fixture-seed", "kind": "import", "actor": "fixture",
            "narrative": "Noncanonical crossing fixture.", "changes": changes,
        })
        self.e.define_property("person.bridgecraft", 1, "Bridgecraft", "Contextual skill at damaged bridges", "integer", ["person"], {"min": 0, "max": 10}, "active", unit="rank")
        self.e.define_property("person.fatigue", 1, "Fatigue", "Accumulated exertion", "number", ["person"], {"min": 0}, "active", unit="hours")
        self.e.define_property("environment.water_level", 1, "Water level", "Rising water state", "number", ["environment"], {"min": 0}, "active", unit="metres")
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "fixture-properties", "kind": "property_assignment", "actor": "fixture",
            "narrative": "Assign fixture properties.", "changes": [],
            "properties": [
                {"entity_id": "specialist", "property_id": "person.bridgecraft", "definition_version": 1, "state": "known", "value": 8, "unit": "rank", "epistemic_status": "confirmed", "visibility": "public"},
                {"entity_id": "specialist", "property_id": "person.fatigue", "definition_version": 1, "state": "known", "value": 0, "unit": "hours", "epistemic_status": "confirmed", "visibility": "public"},
                {"entity_id": "generalist", "property_id": "person.fatigue", "definition_version": 1, "state": "known", "value": 0, "unit": "hours", "epistemic_status": "confirmed", "visibility": "public"},
                {"entity_id": "water", "property_id": "environment.water_level", "definition_version": 1, "state": "known", "value": 1, "unit": "metres", "epistemic_status": "confirmed", "visibility": "public"},
            ],
        })

    def tearDown(self):
        self.e.close()
        self.temp.cleanup()

    def test_property_assignment_is_event_state_and_replayable(self):
        row = self.e.property_value("main", "specialist", "person.bridgecraft", 1)
        self.assertEqual(row["value"], 8)
        self.assertIsNotNone(row["valid_from_event"])
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM property_changes").fetchone()[0], 4)
        replay = self.e.replay("main")
        self.assertTrue(replay["complete"])
        self.assertTrue(any("person.bridgecraft" in key for key, _ in replay["auxiliary"]))
        self.e.verify()

    def test_applicability_units_constraints_and_unknowns(self):
        rev = self.e.branch("main")["revision"]
        def command(assignment, key):
            return {
                "api_version": 2, "branch": "main", "expected_revision": rev,
                "request_id": key, "kind": "property_assignment", "actor": "fixture",
                "narrative": "invalid fixture assignment", "changes": [], "properties": [assignment],
            }
        wrong_unit = {"entity_id": "specialist", "property_id": "person.bridgecraft", "definition_version": 1, "state": "known", "value": 3, "unit": "metres"}
        with self.assertRaises(Rejected):
            self.e.apply(command(wrong_unit, "wrong-unit"))
        wrong_entity = dict(wrong_unit, unit="rank", entity_id="water")
        with self.assertRaises(Rejected):
            self.e.apply(command(wrong_entity, "wrong-entity"))
        unknown = dict(wrong_unit, entity_id="specialist", unit="rank", state="unknown", value=None)
        self.e.apply(command(unknown, "unknown-state"))
        self.assertEqual(self.e.property_value("main", "specialist", "person.bridgecraft", 1)["state"], "unknown")
        self.e.define_property("structure.load", 1, "Load capacity", "Bridge load capacity", "number", ["damaged_structure"], {"min": 0}, "active", unit="tonnes")
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "bridge-facet", "kind": "action", "actor": "fixture",
            "narrative": "The bridge receives an explicit composable facet.", "changes": [],
            "facet_changes": [{"entity_id": "bridge", "facet": "damaged_structure", "op": "add"}],
        })
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "bridge-load", "kind": "property_assignment", "actor": "fixture",
            "narrative": "Assign bridge load capacity in the fixture.", "changes": [],
            "properties": [{"entity_id": "bridge", "property_id": "structure.load", "definition_version": 1,
                            "state": "known", "value": 2.5, "unit": "tonnes", "visibility": "public"}],
        })
        self.assertEqual(self.e.property_value("main", "bridge", "structure.load", 1)["value"], 2.5)
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM entity_facet_changes").fetchone()[0], 1)

    def test_mixed_action_resolves_stages_once_and_keeps_uncertainty(self):
        action = self.e.resolve_action("main", {
            "actor": "specialist", "difficulty": 16, "requires_roll": True,
            "roll_id": "crossing-attempt-1", "reason": "Bridge crossing",
            "modifier": 0,
            "contributions": [
                {"id": "bridgecraft", "stage": "probability", "value": 4, "source": "person.bridgecraft"},
                {"id": "water-risk", "stage": "cost", "value": {"kind": "exposure", "amount": "high"}},
                {"id": "concealment", "stage": "magnitude", "value": 1},
            ],
            "cost": [{"kind": "fatigue", "amount": 1, "unit": "hours"}],
        })
        self.assertIn(action["probability"]["success"], (True, False))
        self.assertEqual(action["probability"]["difficulty"], 16)
        rev = self.e.branch("main")["revision"]
        crossing_command = {
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "crossing-event", "kind": "action", "actor": "specialist",
            "narrative": "The specialist studies the damaged bridge.", "changes": [],
            "roll_ids": ["crossing-attempt-1"], "resolution": action,
            "choice": {
                "id": "choice-cross", "actor_id": "specialist", "intent": "cross with the family",
                "method": "bridgecraft", "agency_state": "available",
                "options": [{"id": "cross"}, {"id": "wait"}],
                "selected": {"id": "cross"}, "knowledge": {"known": ["damaged bridge"], "hidden": ["unstable footing"]},
            },
            "consequences": [{
                "id": "bridge-consequence", "subject_id": "bridge",
                "effect": {"changes": [patch("crossing", 1, access="conditional", conditions="Water is rising; specialist route required")]},
                "trigger": {"kind": "immediate"}, "apply_once": 1,
            }],
        }
        receipt = self.e.apply(crossing_command)
        self.assertEqual(receipt["changed"], [])
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM roll_uses").fetchone()[0], 1)
        self.assertTrue(self.e.apply(crossing_command)["replayed"])
        rev = self.e.branch("main")["revision"]
        result = self.e.apply_consequences("main", "apply-bridge-consequence", "engine", "Apply immediate crossing consequence", rev)
        self.assertEqual(self.e.get("main", "crossing")["data"]["access"], "conditional")
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM consequence_runs WHERE status='applied'").fetchone()[0], 1)
        self.e.verify()

    def test_contextual_specialist_advantage_does_not_guarantee_success(self):
        specialist = self.e.resolve_action("main", {"actor": "specialist", "difficulty": 15, "requires_roll": False, "modifier": 4, "contributions": [{"id": "context", "stage": "probability", "value": 4}]})
        generalist = self.e.resolve_action("main", {"actor": "generalist", "difficulty": 15, "requires_roll": False, "modifier": 0, "contributions": []})
        self.assertGreater(specialist["probability"]["modifier"], generalist["probability"]["modifier"])
        self.assertFalse(specialist["probability"]["success"])
        self.assertFalse(generalist["probability"]["success"])

    def test_opportunities_keep_open_action_and_environment_constraints(self):
        options = self.e.opportunities("main", "specialist", viewer="specialist", scene="crossing-scene")
        self.assertTrue(options["open_action_supported"])
        self.assertTrue(any(option["kind"] == "route" for option in options["opportunities"]))
        self.assertTrue(any(item["kind"] == "environment" for item in options["constraints"]))

    def test_collective_members_keep_disagreement(self):
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "family-decisions", "kind": "decision", "actor": "family",
            "narrative": "The family considers the crossing.", "changes": [
                create("decision", "mother-choice", actor="mother", choice="cross", alternatives=["wait"], rationale="protect child", commitment="proposed"),
                create("decision", "child-choice", actor="child", choice="wait", alternatives=["cross"], rationale="bridge looks unsafe", commitment="refusal"),
            ],
        })
        self.assertEqual(self.e.get("main", "mother-choice")["data"]["choice"], "cross")
        self.assertEqual(self.e.get("main", "child-choice")["data"]["choice"], "wait")

    def test_entity_profile_composition_and_classification_are_separate(self):
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "entity-facets", "kind": "action", "actor": "fixture",
            "narrative": "Describe the family and bridge without collapsing them.", "changes": [],
            "profiles": [{"entity_id": "family", "identity_label": "Crossing family", "nature": "collective", "composition": {"members": ["mother", "child"]}, "agency_mode": "collective", "control_mode": "npc", "classification": ["family"], "visibility": "public"}],
            "entity_links": [{"id": "family-mother", "whole_id": "family", "part_id": "mother", "relation": "contains"}],
            "classification_claims": [{"id": "bridge-claim", "subject_id": "bridge", "claimant_id": "specialist", "classification": "unsafe structure", "mechanism": "bridgecraft assessment", "force": "none", "status": "contested"}],
        })
        profile = self.e.entity_profiles("main")[0]
        self.assertEqual(profile["agency_mode"], "collective")
        self.assertEqual(profile["composition"]["members"], ["mother", "child"])
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM classification_claims").fetchone()[0], 1)

    def test_hidden_fact_affects_gm_resolution_without_context_leak(self):
        rev = self.e.branch("main")["revision"]
        secret = create("knowledge", "hidden-footing", holder="specialist", assertion="A submerged gap will collapse under heavy load", attitude="knows", basis="scouting")
        secret["visibility"] = "restricted"; secret["audience"] = ["specialist"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "hidden-fact", "kind": "observation", "actor": "specialist",
            "narrative": "A hidden scouting fact enters the world state.", "changes": [secret],
        })
        self.assertNotIn("submerged gap", str(self.e.context("main", viewer="mother")))
        self.assertIn("submerged gap", str(self.e.context("main", viewer="specialist")))
        resolution = self.e.resolve_action("main", {"actor": "specialist", "difficulty": 18, "requires_roll": False, "modifier": 2, "inputs": ["hidden-footing"]})
        self.assertEqual(resolution["inputs"], ["hidden-footing"])

    def test_background_process_advances_once_and_is_step_invariant(self):
        self.e.set_property("main", "generalist", "person.fatigue", 1, "known", 0, unit="hours")
        self.e.create_process("main", {
            "id": "fatigue-process", "process_kind": "fatigue", "state": "active",
            "subjects": ["generalist"], "next_tick": 1, "interval_value": 1,
            "granularity": "exact", "metadata": {"effect": {
                "kind": "property_delta", "entity_id": "generalist",
                "property_id": "person.fatigue", "definition_version": 1,
                "delta_per_unit": 1,
            }},
        }, "process-start", "engine", "Start fixture fatigue")
        self.e.fork("main", "stepped", self.e.branch("main")["revision"])
        self.e.advance_simulation("main", "clock", 3, "advance-3", "engine", "Three hours pass")
        self.assertEqual(self.e.property_value("main", "generalist", "person.fatigue", 1)["value"], 3)
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM process_runs WHERE process_id='fatigue-process'").fetchone()[0], 1)
        self.e.advance_simulation("stepped", "clock", 1, "advance-1", "engine", "One hour passes")
        self.e.advance_simulation("stepped", "clock", 3, "advance-1-to-3", "engine", "Two more hours pass")
        self.assertEqual(self.e.property_value("stepped", "generalist", "person.fatigue", 1)["value"], 3)
        self.e.verify()

    def test_integrated_journey_coordinates_backgrounds_and_later_scene(self):
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "journey-schedule", "kind": "scene", "actor": "fixture",
            "narrative": "Noncanonical journey fixture establishes a deadline.", "changes": [
                create("schedule", "expiring-opportunity", clock="clock", due=2, trigger="ferry window closes",
                       proposed_effect="The alternate ferry window expires", phase="pending"),
            ],
        })
        self.e.create_process("main", {
            "id": "patrol-process", "process_kind": "patrol", "state": "active", "subjects": ["family"],
            "scope": {"location": "far-bank"}, "subscriptions": ["action"], "next_tick": 1,
            "interval_value": 1, "interval_unit": "hour", "granularity": "judgment", "visibility": "gm",
            "metadata": {"effect": {"kind": "judgment", "reason": "GM must decide what the offscreen patrol witnessed"}},
        }, "journey-patrol", "engine", "Start patrol process")
        self.e.create_process("main", {
            "id": "faction-project", "process_kind": "faction_project", "state": "active", "subjects": ["family"],
            "scope": {"location": "far-bank"}, "subscriptions": ["decision"], "next_tick": 2,
            "interval_value": 2, "interval_unit": "hour", "granularity": "exact", "visibility": "gm",
            "metadata": {"effect": {"kind": "record_patch", "record_id": "crossing",
                                      "data": {"access": "blocked", "conditions": "Offscreen faction patrol now enforces closure"}}},
        }, "journey-faction", "engine", "Start offscreen faction project")
        self.e.create_process("main", {
            "id": "journey-fatigue", "process_kind": "fatigue", "state": "active", "subjects": ["specialist"],
            "scope": {"location": "near-bank"}, "next_tick": 1, "interval_value": 1,
            "interval_unit": "hour", "granularity": "exact", "visibility": "public",
            "metadata": {"effect": {"kind": "property_delta", "entity_id": "specialist",
                                      "property_id": "person.fatigue", "definition_version": 1, "delta_per_unit": 1}},
        }, "journey-fatigue-start", "engine", "Start travel fatigue")
        fork_revision = self.e.branch("main")["revision"]
        self.e.fork("main", "without-prior-change", fork_revision)
        resolution = self.e.resolve_action("main", {
            "actor": "specialist", "difficulty": 15, "requires_roll": True,
            "roll_id": "journey-crossing-attempt", "reason": "Navigate the damaged bridge while water rises",
            "contributions": [{"id": "bridgecraft", "stage": "probability", "value": 4},
                              {"id": "water-exposure", "stage": "cost", "value": {"kind": "exposure", "amount": "high"}}],
            "cost": [{"kind": "fatigue", "amount": 1, "unit": "hours"}],
        })
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "journey-crossing", "kind": "action", "actor": "specialist",
            "narrative": "The specialist chooses a safer line across the damaged bridge; the family disagrees.",
            "changes": [
                patch("crossing", 1, access="conditional", conditions="Specialist route selected; rising water conceals footing"),
                create("decision", "journey-mother-choice", actor="mother", choice="cross", alternatives=["wait"], rationale="protect child", commitment="proposed"),
                create("decision", "journey-child-choice", actor="child", choice="wait", alternatives=["cross"], rationale="refuses the bridge", commitment="refusal"),
            ], "roll_ids": ["journey-crossing-attempt"], "resolution": resolution,
            "choice": {"id": "journey-choice", "actor_id": "specialist", "intent": "help the family cross",
                       "method": "bridgecraft", "agency_state": "available", "options": [{"id": "cross"}, {"id": "wait"}],
                       "selected": {"id": "cross"}, "knowledge": {"known": ["rising water"], "hidden": ["patrol"]}},
        })
        self.assertEqual(self.e.get("main", "crossing")["data"]["access"], "conditional")
        self.assertEqual(self.e.get("without-prior-change", "crossing")["data"]["access"], "open")
        self.assertEqual(next(p for p in self.e.list_processes("main") if p["id"] == "patrol-process")["state"], "due")
        self.e.advance_simulation("main", "clock", 2, "journey-advance", "engine", "Two hours pass")
        self.assertEqual(self.e.get("main", "crossing")["data"]["access"], "blocked")
        self.assertEqual(self.e.get("main", "expiring-opportunity")["data"]["phase"], "due")
        self.assertEqual(self.e.property_value("main", "specialist", "person.fatigue", 1)["value"], 2)
        patrol = next(p for p in self.e.list_processes("main") if p["id"] == "patrol-process")
        self.assertEqual(patrol["state"], "blocked")
        self.assertNotIn("faction-project", [p["id"] for p in self.e.list_processes("main", viewer="specialist")])
        self.e.verify()

    def test_relevance_is_presentation_only(self):
        self.e.create_process("main", {"id": "urgent", "process_kind": "deadline", "state": "due", "metadata": {"relevance": {"causal_connection": 0, "urgency": 5}}}, "p-urgent", "engine", "Urgent process")
        ranked = self.e.rank_relevance("main", "specialist")
        self.assertGreaterEqual(ranked[0]["relevance"]["score"], 100)
        self.assertFalse(ranked[0]["relevance"]["affects_mechanics"])

    def test_property_evolution_dependency_and_old_event(self):
        self.e.define_property("person.focus", 1, "Focus", "attention", "integer", ["person"], {"min": 0}, "active", unit="points")
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "focus-assignment", "kind": "property_assignment", "actor": "engine",
            "narrative": "Assign focus.", "changes": [], "properties": [{
                "entity_id": "specialist", "property_id": "person.focus", "definition_version": 1,
                "state": "known", "value": 4, "unit": "points", "visibility": "public",
            }],
        })
        self.e.add_rule("focus-rule", 1, "Focus threshold", ["person.focus"], ["person.focus.result"], True, {"kind": "threshold", "property": "person.focus", "threshold": 3}, [("person.focus", 1, "reads")])
        resolution = self.e.resolve_action("main", {"actor": "specialist", "difficulty": 10, "requires_roll": False, "rules": [{"id": "focus-rule", "version": 1}]})
        self.assertEqual(resolution["rule_results"][0]["output"]["value"], True)
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "focus-rule-event", "kind": "action", "actor": "specialist",
            "narrative": "The focus rule is used in a fixture action.", "changes": [],
            "dependencies": [{"kind": "rule", "ref_id": "focus-rule", "version": "1", "usage": "reads"}],
            "resolution": resolution,
        })
        with self.assertRaises(Rejected):
            self.e.retire_property("person.focus", 1, "cannot retire while rule reads it")
        self.e.revise_property("person.focus", 1, 2, label="Focus", meaning="attention revised", value_type="integer", applicability=["person"], constraints={"min": 0}, lifecycle="active", unit="points")
        self.e.retire_property("person.focus", 1, "replaced by v2", replacement=("person.focus", 2))
        self.assertEqual(self.e.property_value("main", "specialist", "person.focus", 1)["value"], 4)
        self.assertTrue(self.e.replay("main")["complete"])
        self.e.verify()

    def test_rule_dependency_cycle_is_rejected(self):
        self.e.define_property("person.a", 1, "A", "A", "integer", ["person"], {}, "active")
        self.e.define_property("person.b", 1, "B", "B", "integer", ["person"], {}, "active")
        self.e.add_rule("rule-a", 1, "A", ["person.b"], ["person.a"], True, {"kind": "sum"}, [("person.b", 1, "reads")])
        with self.assertRaises(Rejected):
            self.e.add_rule("rule-b", 1, "B", ["person.a"], ["person.b"], True, {"kind": "sum"}, [("person.a", 1, "reads")])

    def test_branch_copies_auxiliary_state_and_isolates_changes(self):
        self.e.fork("main", "alternate", self.e.branch("main")["revision"])
        self.assertEqual(self.e.property_value("alternate", "specialist", "person.bridgecraft", 1)["value"], 8)
        rev = self.e.branch("alternate")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "alternate", "expected_revision": rev,
            "request_id": "alt-property", "kind": "property_assignment", "actor": "fixture",
            "narrative": "Alternate branch lowers bridgecraft.", "changes": [],
            "properties": [{"entity_id":"specialist","property_id":"person.bridgecraft","definition_version":1,"state":"known","value":1,"unit":"rank","visibility":"public"}],
        })
        self.assertEqual(self.e.property_value("main", "specialist", "person.bridgecraft", 1)["value"], 8)
        self.assertEqual(self.e.property_value("alternate", "specialist", "person.bridgecraft", 1)["value"], 1)
        self.e.verify()

    def test_branch_preserves_global_auxiliary_rows_without_collisions(self):
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "auxiliary-event", "kind": "action", "actor": "specialist",
            "narrative": "Noncanonical branch fixture records an observation and a choice.",
            "changes": [],
            "choice": {"id": "fixture-choice", "actor_id": "specialist", "intent": "cross",
                       "options": [{"id": "cross"}, {"id": "wait"}], "selected": {"id": "wait"},
                       "knowledge": {"known": ["water"]}, "agency_state": "available"},
            "observations": [{"id": "fixture-observation", "observer_id": "specialist", "subject_id": "bridge",
                              "assertion": "A support is cracked", "certainty": "observed",
                              "visibility": "restricted", "audience": ["specialist"]}],
            "consequences": [{"id": "fixture-consequence", "subject_id": "bridge", "effect": {"changes": []},
                              "trigger": {"kind": "manual"}}],
        })
        self.e.fork("main", "auxiliary-branch", self.e.branch("main")["revision"])
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM choices WHERE branch='auxiliary-branch'").fetchone()[0], 1)
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM observations WHERE branch='auxiliary-branch'").fetchone()[0], 1)
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM consequences WHERE branch='auxiliary-branch'").fetchone()[0], 1)
        self.assertTrue(self.e.replay("auxiliary-branch")["complete"])
        self.e.verify()

    def test_branch_preserves_spent_random_attempts(self):
        roll = self.e.roll("main", "pre-fork-roll", 20, 12, 2, "Noncanonical pre-fork attempt")
        rev = self.e.branch("main")["revision"]
        self.e.apply({
            "api_version": 2, "branch": "main", "expected_revision": rev,
            "request_id": "pre-fork-roll-event", "kind": "failed_action", "actor": "specialist",
            "narrative": "The fixture spends a roll before branching.", "changes": [],
            "roll_ids": [roll["id"]],
        })
        self.e.fork("main", "roll-branch", self.e.branch("main")["revision"])
        with self.assertRaises(Rejected):
            self.e.apply({
                "api_version": 2, "branch": "roll-branch", "expected_revision": 0,
                "request_id": "reuse-spent-roll", "kind": "failed_action", "actor": "specialist",
                "narrative": "The child cannot spend the same logical attempt twice.", "changes": [],
                "roll_ids": [roll["id"]],
            })
        self.e.verify()

    def test_duplicate_process_request_and_recovery(self):
        proc = {"id":"patrol","process_kind":"patrol","state":"active","next_tick":2,"interval_value":2,"metadata":{"effect":{"kind":"judgment","reason":"GM must decide what the patrol saw"}}}
        first = self.e.create_process("main", proc, "patrol-start", "engine", "Start patrol")
        second = self.e.apply({
            "api_version": 2, "branch":"main", "expected_revision":first["revision"] - 1,
            "request_id":"patrol-start", "kind":"process", "actor":"engine", "narrative":"Start patrol",
            "changes":[], "processes":[dict(proc, op="create")], "causes": [],
        })
        self.assertTrue(second["replayed"])
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM processes WHERE id='patrol'").fetchone()[0], 1)

    def test_interface_mismatch_and_atomic_failure_do_not_mutate_story(self):
        rev = self.e.branch("main")["revision"]
        with self.assertRaises(Rejected):
            self.e.apply({
                "api_version": 2, "branch": "main", "expected_revision": rev,
                "request_id": "bad-module-version", "kind": "action", "actor": "specialist",
                "narrative": "The fixture deliberately uses an incompatible module.", "changes": [],
                "dependencies": [{"kind": "module", "ref_id": "kageyoni.travel", "version": "999", "usage": "reads"}],
            })
        self.assertEqual(self.e.branch("main")["revision"], rev)
        with self.assertRaises(Rejected):
            self.e.apply({
                "api_version": 2, "branch": "main", "expected_revision": rev,
                "request_id": "atomic-invalid-property", "kind": "property_assignment", "actor": "fixture",
                "narrative": "The second assignment is invalid; the first must not persist.", "changes": [],
                "properties": [
                    {"entity_id": "specialist", "property_id": "person.fatigue", "definition_version": 1,
                     "state": "known", "value": 2, "unit": "hours", "visibility": "public"},
                    {"entity_id": "water", "property_id": "person.fatigue", "definition_version": 1,
                     "state": "known", "value": 4, "unit": "hours", "visibility": "public"},
                ],
            })
        self.assertEqual(self.e.branch("main")["revision"], rev)
        self.assertEqual(self.e.property_value("main", "specialist", "person.fatigue", 1)["value"], 0)


if __name__ == "__main__":
    unittest.main()
