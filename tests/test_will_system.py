import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine, Rejected, digest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = [{"note": "Synthetic Will fixture; never canonical history."}]


def create(domain, record_id, **data):
    return {
        "op": "create", "domain": domain, "id": record_id, "data": data,
        "status": "proposed", "visibility": "public", "evidence": EVIDENCE,
    }


class WillFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "will.sqlite"
        self.e = Engine(self.path)
        self._event(
            "base", [
                create("character", "a", name="A", entity_kind="person"),
                create("character", "b", name="B", entity_kind="person"),
                create("location", "island", name="Island", kind="island"),
                create("ability", "ability", name="Ability", function="Fixture"),
                create("clock", "clock", name="Local", tick=0, unit="day"),
                create("will", "legacy", name="Legacy Will", bearer="a", principles="Choose"),
            ],
        )
        self.e.add_rule("will-allow", 1, "Fixture allow", [], [], True, {"kind": "contextual", "outcome": True})
        self.e.add_rule("will-deny", 1, "Fixture deny", [], [], True, {"kind": "contextual", "outcome": False})
        self.e.add_rule(
            "will-patch", 1, "Fixture patch", [], [], True,
            {"kind": "will_patch", "template": {"target_role": "target", "data": {"condition": "marked"}}},
        )

    def tearDown(self):
        self.e.close()
        self.temp.cleanup()

    def _event(self, request_id, changes, kind="action", actor="gm"):
        return self.e.apply({
            "api_version": 3, "branch": "main", "expected_revision": self.e.branch("main")["revision"],
            "request_id": request_id, "kind": kind, "actor": actor,
            "narrative": "Synthetic Will fixture only.", "changes": changes,
        })

    @staticmethod
    def _condition(rule_id="will-allow"):
        return {
            "id": f"condition-{rule_id}", "mode": "rule",
            "rule": {"id": rule_id, "version": 1},
            "statement": "Fixture rule", "missing_policy": "block",
        }

    @staticmethod
    def _definition(record_id="definition", version=1, ancestry=None, classification="independent"):
        return {
            "schema_version": "will-contract/0.1", "id": record_id, "version": version,
            "design_status": "accepted", "evidence": [{"source": "fixture", "assertion": "fixture", "status": "proposed"}],
            "name": "Fixture Will", "classification": classification, "nature": "chosen expression",
            "ancestry": ancestry or [], "generative_boundary": "bounded fixture",
            "inherent_limits": ["not canon"], "invariants": [],
        }

    def _expression(self, record_id="expression", definition="definition", bearer="a", techniques=None, awakening=None, version=1):
        return {
            "schema_version": "will-contract/0.1", "id": record_id, "version": version,
            "design_status": "accepted", "evidence": [{"source": "fixture", "assertion": "fixture", "status": "proposed"}],
            "definition": {"id": definition, "version": 1}, "bearer": bearer, "legacy_will_id": "legacy",
            "interpretation": "Fixture expression", "channels": ["voice"], "stat_bindings": [],
            "learned_techniques": techniques or [], "conditions": [], "awakening_access": "latent",
            "awakening_mastery": "unknown", "awakening_definition": awakening,
        }

    def _technique(self, record_id="technique", expression="expression", trigger=None, resolver=None, target_kinds=None, version=1, design_status="accepted", costs=None):
        trigger = trigger or self._condition()
        effect = {
            "operation": "alter", "target_role": "target", "mechanism": "fixture effect",
            "preconditions": [], "scope": {"target_kinds": target_kinds or ["person"], "range": None, "area": None, "duration": None, "unknowns": []},
            "inputs": [], "resolver": resolver, "authority": "mechanical" if resolver else "gm_judgment",
            "resistance": [], "postconditions": [],
        }
        return {
            "schema_version": "will-contract/0.1", "id": record_id, "version": version,
            "design_status": design_status, "evidence": [{"source": "fixture", "assertion": "fixture", "status": "proposed"}],
            "expression": {"id": expression, "version": 1}, "name": "Fixture Technique",
            "derivation": "fixture practice", "practice_status": "demonstrated", "activation": "deliberate",
            "trigger": trigger, "channels": [{"medium": "voice", "access": trigger, "break_conditions": []}],
            "effects": [effect], "costs": costs or [], "resolution_policy": {"id": "will-allow", "version": 1}, "termination": [],
        }

    def _install_basic_will(self, *, trigger=None, target_kinds=None, resolver=True, expression_bearer="a", technique_id="technique", design_status="accepted", costs=None):
        d = self._definition()
        e = self._expression(bearer=expression_bearer, techniques=[{"id": technique_id, "version": 1}])
        t = self._technique(record_id=technique_id, trigger=trigger, target_kinds=target_kinds, resolver={"id": "will-patch", "version": 1} if resolver else None, design_status=design_status, costs=costs)
        self._event("will-contracts", [
            create("will_definition", "definition", name="Fixture Will", classification="independent", contract=d),
            create("will_expression", "expression", definition="definition", bearer=expression_bearer, legacy_will="legacy", contract=e),
            create("will_technique", technique_id, expression="expression", ability="ability", name="Fixture Technique", contract=t),
        ])

    def _attempt(self, attempt_id="attempt", request_id=None, technique="technique", actor="a", target="b", **extra):
        spec = {
            "request_id": request_id or f"prepare-{attempt_id}", "attempt_id": attempt_id,
            "expected_revision": self.e.branch("main")["revision"], "actor": actor,
            "expression": {"id": "expression", "version": 1}, "technique": {"id": technique, "version": 1},
            "intent": "Use fixture Will", "targets": [target],
            "randomness": {"mode": "d20", "roll_id": f"roll-{attempt_id}", "difficulty": 1, "modifier": 0},
            "outcome_bindings": [
                {"outcome": "success", "effect_indexes": [0], "cost_ids": []},
                {"outcome": "failure", "effect_indexes": [], "cost_ids": []},
            ], "judgments": [],
        }
        spec.update(extra)
        return spec

    def test_two_bearers_cannot_borrow_technique(self):
        self._install_basic_will()
        self._event("second-expression", [
            create("will_expression", "expression-b", definition="definition", bearer="b", legacy_will=None, contract=self._expression("expression-b", bearer="b", techniques=[{"id": "technique-b", "version": 1}])),
            create("will_technique", "technique-b", expression="expression-b", ability="ability", name="B Technique", contract=self._technique("technique-b", expression="expression-b", resolver=None)),
        ])
        with self.assertRaisesRegex(Rejected, "not part"):
            self.e.prepare_will_attempt("main", self._attempt(technique="technique-b"))
        prepared = self.e.prepare_will_attempt("main", self._attempt())
        self.assertEqual(prepared["status"], "prepared")

    def test_false_precondition_blocks_before_randomness_or_cost(self):
        self._install_basic_will(trigger=self._condition("will-deny"), resolver=False)
        result = self.e.prepare_will_attempt("main", self._attempt())
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["judgment_required"] is False)
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM rolls").fetchone()[0], 0)
        self.assertEqual(self.e.branch("main")["revision"], 2)

    def test_stable_attempt_roll_and_stale_commit(self):
        self._install_basic_will()
        spec = self._attempt()
        first = self.e.prepare_will_attempt("main", spec)
        second = self.e.prepare_will_attempt("main", spec)
        self.assertTrue(second["replayed"])
        self.assertEqual(first["roll"]["result"], second["roll"]["result"])
        self._event("unrelated", [create("location", "elsewhere", name="Elsewhere", kind="island")])
        with self.assertRaisesRegex(Rejected, "stale branch revision"):
            self.e.apply_will_attempt("main", "attempt", "apply-stale", "a", "Use Will", expected_revision=2)

    def test_apply_rejects_caller_injected_delta(self):
        self._install_basic_will()
        spec = self._attempt()
        self.e.prepare_will_attempt("main", spec)
        row = self.e.db.execute("SELECT compiled_json FROM will_attempts WHERE attempt_id='attempt'").fetchone()
        compiled = json.loads(row[0])
        with self.assertRaisesRegex(Rejected, "caller-injected"):
            self.e.apply({
                "api_version": 3, "branch": "main", "expected_revision": 2,
                "request_id": "tampered", "kind": "will_attempt", "actor": "a", "narrative": "tampered",
                "changes": [{"op": "patch", "id": "a", "expected_version": 1, "data": {"condition": "omnipotent"}, "evidence": EVIDENCE}],
                "roll_ids": compiled["roll_ids"], "resolution": compiled["resolution"], "will_attempt": {"attempt_id": "attempt", "compiled_digest": digest(compiled)},
            })
        self.assertEqual(self.e.get("main", "a")["version"], 1)

    def test_scope_and_unit_validation(self):
        self._install_basic_will(target_kinds=["structure"])
        with self.assertRaisesRegex(Rejected, "outside effect scope"):
            self.e.prepare_will_attempt("main", self._attempt())
        bad = self._technique(record_id="bad", target_kinds=["person"], resolver=None)
        bad["effects"][0]["scope"]["range"] = {"value": 1}
        with self.assertRaisesRegex(Rejected, "value and unit"):
            self._event("bad-contract", [create("will_technique", "bad", expression="expression", ability="ability", name="Bad", contract=bad)])

    def test_history_version_and_branch_persistence(self):
        self._install_basic_will()
        old = self.e.get_will_contract("main", "will_technique", "technique", 1)
        revised = self._technique(version=2)
        self._event("revise-technique", [{"op": "patch", "id": "technique", "expected_version": 1, "data": {"contract": revised, "name": "Revised"}, "evidence": EVIDENCE}])
        self.assertEqual(self.e.get_will_contract("main", "will_technique", "technique", 1), old)
        self.assertEqual(self.e.get_will_contract("main", "will_technique", "technique")["version"], 2)
        self.e.fork("main", "branch", self.e.branch("main")["revision"])
        self.assertEqual(self.e.get("branch", "technique")["version"], 2)
        self.e.verify()

    def test_awakening_does_not_auto_activate_and_hidden_contract_is_redacted(self):
        self._install_basic_will()
        awakening = {
            "schema_version": "will-contract/0.1", "id": "awakening", "version": 1, "design_status": "accepted",
            "evidence": [{"source": "fixture", "assertion": "fixture", "status": "proposed"}], "expression": {"id": "expression", "version": 1},
            "qualitative_change": "new relation", "substrates": ["pressure"], "eligibility": [], "activation_conditions": [],
            "transformed_techniques": [], "upkeep": [], "interruptions": [], "other_agency": "judgment",
            "persistent_residue": ["scar"], "recovery_conditions": [],
        }
        self._event("awakening", [create("will_awakening", "awakening", expression="expression", contract=awakening)])
        self.assertEqual(self.e.get("main", "expression")["data"]["contract"]["awakening_access"], "latent")
        context = self.e.context("main", viewer="a")
        visible_expression = next(r for r in context["records"] if r["id"] == "expression")
        self.assertNotIn("redacted", visible_expression["data"]["contract"])


class WillUpgradeTests(unittest.TestCase):
    def test_real_predecessor_upgrade_and_recovery_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "upgrade.sqlite"
            shutil.copy2(ROOT / "build" / "kageyoni.sqlite.pre-v4.bak", path)
            e = Engine(path)
            self.assertEqual(e.db.execute("SELECT version FROM migration_checks WHERE version=4").fetchone()[0], 4)
            self.assertEqual(e.db.execute("SELECT version FROM engine_versions WHERE component='runtime_schema'").fetchone()[0], "4")
            self.assertIsNotNone(e.db.execute("SELECT 1 FROM sqlite_master WHERE name='will_attempts'").fetchone())
            self.assertTrue(Path(str(path) + ".pre-v4.bak").exists())
            e.verify()
            e.close()


if __name__ == "__main__":
    unittest.main()
