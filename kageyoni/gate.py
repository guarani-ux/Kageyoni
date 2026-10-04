"""
kageyoni.gate: Universal Declarative Gate Engine.

Provides unified rule evaluation across state transitions, encounter dispatches,
production pipelines, and causal graph dependencies with missing-field refusal and legacy Python comparison semantics.
World preconditions retain their separately typed equality and authorization.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class GateOperator(str, Enum):
    EQ = "=="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    IN = "in"
    NOT_IN = "not_in"
    NOT_NULL = "not_null"
    VALID_IN_DAG = "valid_in_dag"

    @classmethod
    def from_str(cls, val: Union[str, GateOperator]) -> GateOperator:
        if isinstance(val, GateOperator):
            return val
        for item in cls:
            if item.value == val or item.name.lower() == str(val).lower():
                return item
        raise ValueError(f"Unknown gate operator: {val}")


@dataclass
class GateRule:
    """A single declarative precondition rule."""
    field: str
    op: Union[str, GateOperator]
    expected: Any = None
    error_message: str = ""


@dataclass
class GateEvaluationResult:
    """Outcome of evaluating one or more GateRules against a target state."""
    passed: bool
    violations: List[str]
    evaluated_count: int

    def __bool__(self) -> bool:
        return self.passed


class GateEngine:
    """
    Evaluator for declarative gate rules against nested target dictionaries
    and optional CausalDAG epistemic graphs.
    """

    @staticmethod
    def extract_field(target: Dict[str, Any], path: str) -> Tuple[bool, Any]:
        """
        Traverses dot-separated keys through nested dictionaries.
        Returns (True, value) if found, (False, None) if any key is missing or non-dict.
        """
        if not path:
            return True, target
        parts = path.split(".")
        curr: Any = target
        for part in parts:
            if not isinstance(curr, dict) or part not in curr:
                return False, None
            curr = curr[part]
        return True, curr

    @classmethod
    def evaluate_rule(
        cls,
        target: Dict[str, Any],
        rule: GateRule,
        dag: Optional[Any] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates a single rule. Raises ValueError if operator is invalid.
        Returns (True, None) if passed, or (False, error_message) on violation.
        """
        op = GateOperator.from_str(rule.op)
        default_err = rule.error_message

        # Operator: VALID_IN_DAG
        if op == GateOperator.VALID_IN_DAG:
            found, val = cls.extract_field(target, rule.field)
            node_id = val if (found and val is not None) else rule.expected
            if not node_id:
                return False, default_err or f"No node_id provided for valid_in_dag rule on '{rule.field}'"
            if dag is None:
                return False, default_err or f"No CausalDAG provided for valid_in_dag check on '{node_id}'"
            if node_id not in dag:
                return False, default_err or f"Node '{node_id}' not found in CausalDAG"
            node = dag.get_node(node_id)
            if getattr(node, "status", None) != "VALID":
                return False, default_err or f"Node '{node_id}' status is '{getattr(node, 'status', None)}', expected 'VALID'"
            return True, None

        # Operator: NOT_NULL
        if op == GateOperator.NOT_NULL:
            found, val = cls.extract_field(target, rule.field)
            if not found or val is None:
                return False, default_err or f"Field '{rule.field}' must not be null"
            return True, None

        # Standard comparison and membership operators
        found, val = cls.extract_field(target, rule.field)
        if not found:
            return False, default_err or f"Field '{rule.field}' missing in target"

        try:
            passed = False
            if op == GateOperator.EQ:
                passed = (val == rule.expected)
            elif op == GateOperator.NE:
                passed = (val != rule.expected)
            elif op == GateOperator.GT:
                passed = (val > rule.expected)
            elif op == GateOperator.GTE:
                passed = (val >= rule.expected)
            elif op == GateOperator.LT:
                passed = (val < rule.expected)
            elif op == GateOperator.LTE:
                passed = (val <= rule.expected)
            elif op == GateOperator.IN:
                passed = (val in rule.expected)
            elif op == GateOperator.NOT_IN:
                passed = (val not in rule.expected)
            
            if passed:
                return True, None
            else:
                return False, default_err or f"Condition '{rule.field} {op.value} {rule.expected}' unsatisfied (got {val!r})"
        except Exception as exc:
            return False, default_err or f"Evaluation exception for '{rule.field}': {exc}"

    @classmethod
    def evaluate(
        cls,
        target: Dict[str, Any],
        rules: List[GateRule],
        dag: Optional[Any] = None,
    ) -> GateEvaluationResult:
        """
        Evaluates all rules against the target and optional CausalDAG.
        Fails closed on any violation or unknown operator.
        """
        violations: List[str] = []
        for r in rules:
            ok, err = cls.evaluate_rule(target, r, dag=dag)
            if not ok:
                violations.append(err or f"Gate rule failed for field '{r.field}'")

        return GateEvaluationResult(
            passed=len(violations) == 0,
            violations=violations,
            evaluated_count=len(rules),
        )

