"""
Unit tests for kageyoni.gate: Declarative Gate Engine.
"""

import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.gate import GateEngine, GateRule, GateOperator, GateEvaluationResult
from kageyoni.graph import CausalDAG


def test_equality_and_inequality():
    target = {"status": "ACTIVE", "code": 200, "flag": True}
    
    # Passing rules
    rules = [
        GateRule(field="status", op="==", expected="ACTIVE"),
        GateRule(field="code", op=GateOperator.EQ, expected=200),
        GateRule(field="status", op="!=", expected="DISABLED"),
    ]
    res = GateEngine.evaluate(target, rules)
    assert res.passed is True
    assert res.violations == []
    assert res.evaluated_count == 3
    assert bool(res) is True

    # Failing rules
    fail_rules = [
        GateRule(field="status", op="==", expected="INACTIVE", error_message="Status not inactive"),
        GateRule(field="code", op="!=", expected=200, error_message="Code must not be 200"),
    ]
    res_fail = GateEngine.evaluate(target, fail_rules)
    assert res_fail.passed is False
    assert len(res_fail.violations) == 2
    assert "Status not inactive" in res_fail.violations
    assert "Code must not be 200" in res_fail.violations


def test_numeric_comparisons():
    target = {"score": 85, "threshold": 50, "latency": 12.5}
    
    rules = [
        GateRule(field="score", op=">", expected=80),
        GateRule(field="score", op=">=", expected=85),
        GateRule(field="threshold", op="<", expected=60),
        GateRule(field="latency", op="<=", expected=12.5),
    ]
    res = GateEngine.evaluate(target, rules)
    assert res.passed is True

    fail_rules = [
        GateRule(field="score", op=">", expected=90, error_message="Score below minimum"),
        GateRule(field="latency", op="<", expected=10.0, error_message="Latency too high"),
    ]
    res_fail = GateEngine.evaluate(target, fail_rules)
    assert res_fail.passed is False
    assert len(res_fail.violations) == 2


def test_membership_operators():
    target = {"role": "operative", "tier": "gold", "tags": ["stealth", "combat"]}
    
    rules = [
        GateRule(field="role", op="in", expected=["scout", "operative", "leader"]),
        GateRule(field="tier", op="not_in", expected=["banned", "suspended"]),
    ]
    res = GateEngine.evaluate(target, rules)
    assert res.passed is True

    fail_rules = [
        GateRule(field="role", op="not_in", expected=["operative"], error_message="Role excluded"),
        GateRule(field="tier", op="in", expected=["silver", "bronze"], error_message="Tier missing"),
    ]
    res_fail = GateEngine.evaluate(target, fail_rules)
    assert res_fail.passed is False
    assert len(res_fail.violations) == 2


def test_not_null_check():
    target = {"ready": True, "token": "xyz", "empty_val": None}
    
    rules = [
        GateRule(field="ready", op="not_null"),
        GateRule(field="token", op=GateOperator.NOT_NULL),
    ]
    res = GateEngine.evaluate(target, rules)
    assert res.passed is True

    fail_rules = [
        GateRule(field="empty_val", op="not_null", error_message="Empty val is null"),
        GateRule(field="missing_key", op="not_null", error_message="Missing key is absent"),
    ]
    res_fail = GateEngine.evaluate(target, fail_rules)
    assert res_fail.passed is False
    assert len(res_fail.violations) == 2
    assert "Empty val is null" in res_fail.violations
    assert "Missing key is absent" in res_fail.violations


def test_nested_field_traversal():
    target = {
        "chamber": {
            "data": {
                "condition": "STABLE",
                "heat": 42
            }
        },
        "metadata": {
            "active": True
        }
    }
    
    rules = [
        GateRule(field="chamber.data.condition", op="==", expected="STABLE"),
        GateRule(field="chamber.data.heat", op="<", expected=50),
        GateRule(field="metadata.active", op="==", expected=True),
    ]
    res = GateEngine.evaluate(target, rules)
    assert res.passed is True

    fail_rules = [
        GateRule(field="chamber.data.condition", op="==", expected="CRITICAL"),
        GateRule(field="chamber.nonexistent.key", op="==", expected=1),
    ]
    res_fail = GateEngine.evaluate(target, fail_rules)
    assert res_fail.passed is False
    assert len(res_fail.violations) == 2


def test_causal_dag_integration():
    dag = CausalDAG()
    dag.add_node("claim_001", "claim", {"text": "A is true"})
    dag.add_node("claim_002", "claim", {"text": "B follows A"}, dependencies=["claim_001"])
    dag.add_node("broken_claim", "claim", {"text": "Unverified assertion"})
    dag.invalidate("broken_claim", reason="Contradicted by physics")

    target = {
        "action": "execute_strike",
        "prereq_claim": "claim_002",
        "bad_prereq": "broken_claim",
        "missing_prereq": "non_existent_claim",
    }

    # Valid DAG reference passes
    valid_rules = [
        GateRule(field="prereq_claim", op="valid_in_dag", error_message="Prereq must be valid in DAG"),
    ]
    res = GateEngine.evaluate(target, valid_rules, dag=dag)
    assert res.passed is True

    # Invalidated node fails closed
    invalid_rules = [
        GateRule(field="bad_prereq", op="valid_in_dag", error_message="Bad prereq is invalidated"),
    ]
    res_inv = GateEngine.evaluate(target, invalid_rules, dag=dag)
    assert res_inv.passed is False
    assert "Bad prereq is invalidated" in res_inv.violations

    # Missing node in DAG fails closed
    missing_rules = [
        GateRule(field="missing_prereq", op="valid_in_dag", error_message="Prereq node missing in graph"),
    ]
    res_missing = GateEngine.evaluate(target, missing_rules, dag=dag)
    assert res_missing.passed is False
    assert "Prereq node missing in graph" in res_missing.violations

    # Calling valid_in_dag without providing a DAG fails closed with diagnostic
    rule_no_dag = GateRule(field="prereq_claim", op="valid_in_dag")
    res_no_dag = GateEngine.evaluate(target, [rule_no_dag], dag=None)
    assert res_no_dag.passed is False
    assert "No CausalDAG provided" in res_no_dag.violations[0]


def test_fail_closed_unknown_operator():
    target = {"val": 10}
    bad_rule = GateRule(field="val", op="unsupported_op", expected=10)
    
    with pytest.raises(ValueError, match="Unknown gate operator"):
        GateEngine.evaluate(target, [bad_rule])


def test_multiple_rule_aggregation():
    target = {"a": 1, "b": "bad", "c": None}
    rules = [
        GateRule(field="a", op="==", expected=99, error_message="Violation A"),
        GateRule(field="b", op="==", expected="good", error_message="Violation B"),
        GateRule(field="c", op="not_null", error_message="Violation C"),
    ]
    res = GateEngine.evaluate(target, rules)
    assert res.passed is False
    assert res.evaluated_count == 3
    assert len(res.violations) == 3
    assert res.violations == ["Violation A", "Violation B", "Violation C"]
