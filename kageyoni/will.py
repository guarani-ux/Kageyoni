"""Validation and reference helpers for the versioned Kageyoni Will system.

The uploaded Will schemas are the design contract.  This module implements the
engine-enforced subset that must hold before a contract can enter a branch:
identity/version binding, required structural fields, typed conditions,
versioned references, scopes/units, costs, and contribution uniqueness.  It is
deliberately conservative: semantic claims that still require GM judgment are
represented as ``mode='judgment'`` conditions and are never silently treated
as mechanics.
"""
from __future__ import annotations

import math
from typing import Any, Iterable


CONTRACT_VERSION = "will-contract/0.1"
DESIGN_STATUSES = {"proposed", "accepted"}
EVIDENCE_STATUSES = {"confirmed", "reported", "inferred", "contested", "unknown", "proposed"}
CONDITION_MODES = {"rule", "judgment"}
MISSING_POLICIES = {"block", "request_judgment"}

WILL_REQUIRED: dict[str, tuple[str, ...]] = {
    "will_definition": (
        "schema_version", "id", "version", "design_status", "evidence", "name",
        "classification", "nature", "ancestry", "generative_boundary", "inherent_limits", "invariants",
    ),
    "will_expression": (
        "schema_version", "id", "version", "design_status", "evidence", "definition", "bearer",
        "legacy_will_id", "interpretation", "channels", "stat_bindings", "learned_techniques",
        "conditions", "awakening_access", "awakening_mastery", "awakening_definition",
    ),
    "will_technique": (
        "schema_version", "id", "version", "design_status", "evidence", "expression", "name",
        "derivation", "practice_status", "activation", "trigger", "channels", "effects", "costs",
        "resolution_policy", "termination",
    ),
    "will_awakening": (
        "schema_version", "id", "version", "design_status", "evidence", "expression", "qualitative_change",
        "substrates", "eligibility", "activation_conditions", "transformed_techniques", "upkeep",
        "interruptions", "other_agency", "persistent_residue", "recovery_conditions",
    ),
    "will_development": (
        "schema_version", "id", "version", "design_status", "evidence", "expression", "dimension",
        "phase", "claim", "supporting_events", "limitations", "mechanical_unlocks",
    ),
    "will_effect": (
        "schema_version", "id", "version", "design_status", "evidence", "expression", "technique",
        "source_event", "targets", "phase", "anchor_records", "start_clock", "start_tick", "end_conditions",
        "process_ids", "consequence_ids", "residue_records",
    ),
}

WILL_TOP_LEVEL: dict[str, set[str]] = {
    domain: set(fields) for domain, fields in WILL_REQUIRED.items()
}

CLASSIFICATIONS = {"primordial", "derivative", "independent", "false", "unknown"}
PRACTICE_STATUSES = {"proposed", "experimental", "demonstrated", "retained", "unavailable"}
ACTIVATIONS = {"deliberate", "passive", "reactive", "sustained"}
AWAKENING_ACCESS = {"unknown", "unavailable", "latent", "accessed", "repeatable", "lost"}
AWAKENING_MASTERY = {"unknown", "unstable", "practiced", "stable"}
DEVELOPMENT_DIMENSIONS = {"perception", "intention", "understanding", "embodiment", "expression", "relationship", "integration", "presence"}
DEVELOPMENT_PHASES = {"proposed", "attempted", "demonstrated", "retained", "revised", "lost"}
EFFECT_PHASES = {"active", "suspended", "ended"}
EFFECT_OPERATIONS = {"create", "alter", "connect", "sever", "reveal", "preserve", "transfer", "suppress"}
AUTHORITIES = {"mechanical", "gm_judgment"}
STAGES = {"permission", "probability", "magnitude", "cost", "timing", "stability"}
ATTEMPT_OUTCOMES = {"success", "partial", "failure", "interrupted"}


class WillContractError(ValueError):
    """Raised for a contract that cannot be admitted to the engine."""


def _fail(message: str) -> None:
    raise WillContractError(message)


def _obj(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        _fail(f"{path} must be an object")
    return value


def _array(value: Any, path: str) -> list:
    if not isinstance(value, list):
        _fail(f"{path} must be an array")
    return value


def _nonempty(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{path} must be a non-empty string")
    return value


def ref(value: Any, path: str = "reference") -> dict:
    value = _obj(value, path)
    if set(value) != {"id", "version"}:
        _fail(f"{path} must contain only id and version")
    _nonempty(value["id"], f"{path}.id")
    if type(value["version"]) is not int or value["version"] < 1:
        _fail(f"{path}.version must be a positive integer")
    return value


def _evidence(value: Any, path: str = "evidence") -> None:
    rows = _array(value, path)
    if not rows:
        _fail(f"{path} must not be empty")
    for i, item in enumerate(rows):
        item = _obj(item, f"{path}[{i}]")
        if set(item) - {"source", "assertion", "status"}:
            _fail(f"{path}[{i}] has unknown fields")
        _nonempty(item.get("source"), f"{path}[{i}].source")
        _nonempty(item.get("assertion"), f"{path}[{i}].assertion")
        if item.get("status") not in EVIDENCE_STATUSES:
            _fail(f"{path}[{i}].status is invalid")


def condition(value: Any, path: str = "condition") -> dict:
    item = _obj(value, path)
    required = {"id", "mode", "rule", "statement", "missing_policy"}
    if set(item) != required:
        _fail(f"{path} must contain exactly {sorted(required)}")
    _nonempty(item["id"], f"{path}.id")
    if item["mode"] not in CONDITION_MODES:
        _fail(f"{path}.mode is invalid")
    _nonempty(item["statement"], f"{path}.statement")
    if item["missing_policy"] not in MISSING_POLICIES:
        _fail(f"{path}.missing_policy is invalid")
    if item["mode"] == "rule":
        if item["rule"] is None:
            _fail(f"{path}.rule is required for rule mode")
        ref(item["rule"], f"{path}.rule")
    elif item["rule"] is not None:
        _fail(f"{path}.rule must be null for judgment mode")
    return item


def _condition_list(value: Any, path: str) -> None:
    for i, item in enumerate(_array(value, path)):
        condition(item, f"{path}[{i}]")


def _common(domain: str, contract: Any, record_id: str | None, record_version: int | None) -> dict:
    contract = _obj(contract, f"{domain}.contract")
    required = set(WILL_REQUIRED[domain])
    missing = required - set(contract)
    if missing:
        _fail(f"{domain}.contract missing {sorted(missing)}")
    unknown = set(contract) - WILL_TOP_LEVEL[domain]
    if unknown:
        _fail(f"{domain}.contract has unknown fields {sorted(unknown)}")
    if contract.get("schema_version") != CONTRACT_VERSION:
        _fail(f"{domain}.contract schema_version must be {CONTRACT_VERSION}")
    _nonempty(contract.get("id"), f"{domain}.contract.id")
    if type(contract.get("version")) is not int or contract["version"] < 1:
        _fail(f"{domain}.contract.version must be a positive integer")
    if record_id is not None and contract["id"] != record_id:
        _fail(f"{domain}.contract.id must match record id")
    if record_version is not None and contract["version"] != record_version:
        _fail(f"{domain}.contract.version must match record version")
    if contract.get("design_status") not in DESIGN_STATUSES:
        _fail(f"{domain}.contract.design_status is invalid")
    _evidence(contract.get("evidence"), f"{domain}.contract.evidence")
    return contract


def _string_array(value: Any, path: str, nonempty: bool = False) -> None:
    for i, item in enumerate(_array(value, path)):
        _nonempty(item, f"{path}[{i}]")
    if nonempty and not value:
        _fail(f"{path} must not be empty")


def _ref_array(value: Any, path: str) -> None:
    for i, item in enumerate(_array(value, path)):
        ref(item, f"{path}[{i}]")


def _number_unit(value: Any, path: str, allow_null: bool = True) -> None:
    if value is None and allow_null:
        return
    item = _obj(value, path)
    if set(item) != {"value", "unit"}:
        _fail(f"{path} must contain value and unit")
    if type(item["value"]) not in (int, float) or isinstance(item["value"], bool) or not math.isfinite(item["value"]):
        _fail(f"{path}.value must be finite")
    _nonempty(item["unit"], f"{path}.unit")


def _validate_definition(contract: dict) -> None:
    _nonempty(contract["name"], "will_definition.name")
    _nonempty(contract["nature"], "will_definition.nature")
    if contract["classification"] not in CLASSIFICATIONS:
        _fail("will_definition.classification is invalid")
    for i, item in enumerate(_array(contract["ancestry"], "will_definition.ancestry")):
        item = _obj(item, f"will_definition.ancestry[{i}]")
        if set(item) != {"parent", "relation", "evidence"}:
            _fail(f"will_definition.ancestry[{i}] has invalid fields")
        ref(item["parent"], f"will_definition.ancestry[{i}].parent")
        if item["relation"] not in {"derived_from", "shares_principle", "claimed_descent"}:
            _fail("invalid Will ancestry relation")
        _evidence(item["evidence"], f"will_definition.ancestry[{i}].evidence")
    _nonempty(contract["generative_boundary"], "will_definition.generative_boundary")
    _string_array(contract["inherent_limits"], "will_definition.inherent_limits")
    for i, item in enumerate(_array(contract["invariants"], "will_definition.invariants")):
        condition(item, f"will_definition.invariants[{i}]")


def _validate_expression(contract: dict) -> None:
    ref(contract["definition"], "will_expression.definition")
    _nonempty(contract["bearer"], "will_expression.bearer")
    if contract["legacy_will_id"] is not None:
        _nonempty(contract["legacy_will_id"], "will_expression.legacy_will_id")
    _nonempty(contract["interpretation"], "will_expression.interpretation")
    _string_array(contract["channels"], "will_expression.channels")
    seen: set[str] = set()
    for i, binding in enumerate(_array(contract["stat_bindings"], "will_expression.stat_bindings")):
        binding = _obj(binding, f"will_expression.stat_bindings[{i}]")
        if set(binding) != {"property_id", "definition_version", "subject_role", "stage", "contribution_id"}:
            _fail("invalid Will stat binding fields")
        _nonempty(binding["property_id"], "stat binding property_id")
        if type(binding["definition_version"]) is not int or binding["definition_version"] < 1:
            _fail("invalid stat binding definition_version")
        _nonempty(binding["subject_role"], "stat binding subject_role")
        if binding["stage"] not in STAGES:
            _fail("invalid stat binding stage")
        _nonempty(binding["contribution_id"], "stat binding contribution_id")
        if binding["contribution_id"] in seen:
            _fail("duplicate Will contribution id")
        seen.add(binding["contribution_id"])
    _ref_array(contract["learned_techniques"], "will_expression.learned_techniques")
    _string_array(contract["conditions"], "will_expression.conditions")
    if contract["awakening_access"] not in AWAKENING_ACCESS:
        _fail("invalid awakening access")
    if contract["awakening_mastery"] not in AWAKENING_MASTERY:
        _fail("invalid awakening mastery")
    if contract["awakening_definition"] is not None:
        ref(contract["awakening_definition"], "will_expression.awakening_definition")


def _validate_technique(contract: dict) -> None:
    ref(contract["expression"], "will_technique.expression")
    _nonempty(contract["name"], "will_technique.name")
    _nonempty(contract["derivation"], "will_technique.derivation")
    if contract["practice_status"] not in PRACTICE_STATUSES:
        _fail("invalid technique practice_status")
    if contract["activation"] not in ACTIVATIONS:
        _fail("invalid technique activation")
    condition(contract["trigger"], "will_technique.trigger")
    for i, channel in enumerate(_array(contract["channels"], "will_technique.channels")):
        channel = _obj(channel, f"will_technique.channels[{i}]")
        if set(channel) != {"medium", "access", "break_conditions"}:
            _fail("invalid technique channel fields")
        _nonempty(channel["medium"], "technique channel medium")
        condition(channel["access"], "technique channel access")
        _condition_list(channel["break_conditions"], "technique channel break_conditions")
    for i, effect in enumerate(_array(contract["effects"], "will_technique.effects")):
        _validate_effect_spec(effect, f"will_technique.effects[{i}]")
    seen_costs: set[str] = set()
    for i, cost in enumerate(_array(contract["costs"], "will_technique.costs")):
        cost = _obj(cost, f"will_technique.costs[{i}]")
        if set(cost) != {"id", "resource", "amount", "when", "insufficient_policy"}:
            _fail("invalid technique cost fields")
        _nonempty(cost["id"], "technique cost id")
        if cost["id"] in seen_costs:
            _fail("duplicate technique cost id")
        seen_costs.add(cost["id"])
        resource = _obj(cost["resource"], "technique cost resource")
        required = {"property_id", "definition_version", "subject_role", "stage", "contribution_id"}
        if set(resource) != required:
            _fail("invalid technique cost resource")
        _nonempty(resource["property_id"], "technique cost property_id")
        if type(resource["definition_version"]) is not int or resource["definition_version"] < 1:
            _fail("invalid technique cost definition_version")
        _nonempty(resource["subject_role"], "technique cost subject_role")
        if resource["stage"] not in STAGES:
            _fail("invalid technique cost stage")
        _nonempty(resource["contribution_id"], "technique cost contribution_id")
        _number_unit(cost["amount"], "technique cost amount", allow_null=False)
        if cost["amount"]["value"] < 0:
            _fail("negative Will cost")
        if cost["when"] not in {"attempt", "success", "failure", "upkeep", "release"}:
            _fail("invalid technique cost timing")
        if cost["insufficient_policy"] not in {"block", "interrupt", "declared_overdraw"}:
            _fail("invalid insufficient cost policy")
    resolution = _obj(contract["resolution_policy"], "will_technique.resolution_policy")
    ref(resolution, "will_technique.resolution_policy")
    _condition_list(contract["termination"], "will_technique.termination")


def _validate_effect_spec(effect: Any, path: str) -> None:
    effect = _obj(effect, path)
    required = {"operation", "target_role", "mechanism", "preconditions", "scope", "inputs", "resolver", "authority", "resistance", "postconditions"}
    if set(effect) != required:
        _fail(f"{path} has invalid fields")
    if effect["operation"] not in EFFECT_OPERATIONS:
        _fail(f"{path}.operation is invalid")
    _nonempty(effect["target_role"], f"{path}.target_role")
    _nonempty(effect["mechanism"], f"{path}.mechanism")
    _condition_list(effect["preconditions"], f"{path}.preconditions")
    scope = _obj(effect["scope"], f"{path}.scope")
    if set(scope) != {"target_kinds", "range", "area", "duration", "unknowns"}:
        _fail(f"{path}.scope has invalid fields")
    _string_array(scope["target_kinds"], f"{path}.scope.target_kinds")
    _number_unit(scope["range"], f"{path}.scope.range")
    _number_unit(scope["area"], f"{path}.scope.area")
    _number_unit(scope["duration"], f"{path}.scope.duration")
    _string_array(scope["unknowns"], f"{path}.scope.unknowns")
    seen: set[str] = set()
    for i, binding in enumerate(_array(effect["inputs"], f"{path}.inputs")):
        binding = _obj(binding, f"{path}.inputs[{i}]")
        required_input = {"property_id", "definition_version", "subject_role", "stage", "contribution_id"}
        if set(binding) != required_input:
            _fail(f"{path}.inputs[{i}] has invalid fields")
        _nonempty(binding["property_id"], "effect input property_id")
        if type(binding["definition_version"]) is not int or binding["definition_version"] < 1:
            _fail("invalid effect input definition_version")
        _nonempty(binding["subject_role"], "effect input subject_role")
        if binding["stage"] not in STAGES:
            _fail("invalid effect input stage")
        _nonempty(binding["contribution_id"], "effect input contribution_id")
        if binding["contribution_id"] in seen:
            _fail("duplicate effect contribution id")
        seen.add(binding["contribution_id"])
    if effect["resolver"] is not None:
        ref(effect["resolver"], f"{path}.resolver")
    if effect["authority"] not in AUTHORITIES:
        _fail(f"{path}.authority is invalid")
    _condition_list(effect["resistance"], f"{path}.resistance")
    _condition_list(effect["postconditions"], f"{path}.postconditions")


def _validate_awakening(contract: dict) -> None:
    ref(contract["expression"], "will_awakening.expression")
    _nonempty(contract["qualitative_change"], "will_awakening.qualitative_change")
    _string_array(contract["substrates"], "will_awakening.substrates")
    _condition_list(contract["eligibility"], "will_awakening.eligibility")
    _condition_list(contract["activation_conditions"], "will_awakening.activation_conditions")
    _ref_array(contract["transformed_techniques"], "will_awakening.transformed_techniques")
    _condition_list(contract["interruptions"], "will_awakening.interruptions")
    _nonempty(contract["other_agency"], "will_awakening.other_agency")
    _string_array(contract["persistent_residue"], "will_awakening.persistent_residue")
    _condition_list(contract["recovery_conditions"], "will_awakening.recovery_conditions")
    for i, cost in enumerate(_array(contract["upkeep"], "will_awakening.upkeep")):
        _obj(cost, f"will_awakening.upkeep[{i}]")
        _number_unit(cost.get("amount"), f"will_awakening.upkeep[{i}].amount", allow_null=False)
        if cost["amount"]["value"] < 0:
            _fail("negative awakening upkeep")


def _validate_development(contract: dict) -> None:
    ref(contract["expression"], "will_development.expression")
    if contract["dimension"] not in DEVELOPMENT_DIMENSIONS:
        _fail("invalid Will development dimension")
    if contract["phase"] not in DEVELOPMENT_PHASES:
        _fail("invalid Will development phase")
    _nonempty(contract["claim"], "will_development.claim")
    _string_array(contract["supporting_events"], "will_development.supporting_events")
    _string_array(contract["limitations"], "will_development.limitations")
    _ref_array(contract["mechanical_unlocks"], "will_development.mechanical_unlocks")


def _validate_effect(contract: dict) -> None:
    ref(contract["expression"], "will_effect.expression")
    ref(contract["technique"], "will_effect.technique")
    _nonempty(contract["source_event"], "will_effect.source_event")
    _string_array(contract["targets"], "will_effect.targets")
    if contract["phase"] not in EFFECT_PHASES:
        _fail("invalid Will effect phase")
    _string_array(contract["anchor_records"], "will_effect.anchor_records")
    _nonempty(contract["start_clock"], "will_effect.start_clock")
    if type(contract["start_tick"]) not in (int, float) or isinstance(contract["start_tick"], bool) or not math.isfinite(contract["start_tick"]):
        _fail("invalid Will effect start_tick")
    _condition_list(contract["end_conditions"], "will_effect.end_conditions")
    _string_array(contract["process_ids"], "will_effect.process_ids")
    _string_array(contract["consequence_ids"], "will_effect.consequence_ids")
    _string_array(contract["residue_records"], "will_effect.residue_records")


def validate_contract(domain: str, contract: Any, record_id: str | None = None, record_version: int | None = None) -> dict:
    """Validate and return a Will contract, raising ``WillContractError``."""
    if domain not in WILL_REQUIRED:
        _fail(f"unsupported Will contract domain {domain}")
    contract = _common(domain, contract, record_id, record_version)
    if domain == "will_definition":
        _validate_definition(contract)
    elif domain == "will_expression":
        _validate_expression(contract)
    elif domain == "will_technique":
        _validate_technique(contract)
    elif domain == "will_awakening":
        _validate_awakening(contract)
    elif domain == "will_development":
        _validate_development(contract)
    elif domain == "will_effect":
        _validate_effect(contract)
    return contract


def condition_refs(contract: dict) -> Iterable[tuple[dict, str]]:
    """Yield every versioned rule reference and its semantic path."""
    def walk(value: Any, path: str) -> Iterable[tuple[dict, str]]:
        if isinstance(value, dict):
            if set(value) == {"id", "version"} and isinstance(value.get("id"), str):
                yield value, path
            else:
                for key, child in value.items():
                    yield from walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for i, child in enumerate(value):
                yield from walk(child, f"{path}[{i}]")
    yield from walk(contract, "contract")


def contract_refs(domain: str, contract: dict) -> list[tuple[str, dict, str]]:
    """Return record/rule references declared by a contract.

    The context (definition/expression/technique/etc.) determines record kind;
    nested ``rule`` objects are rule references.  This is used for dependency
    registry and exact version checks; arbitrary prose is intentionally not
    treated as discoverable dependency.
    """
    refs: list[tuple[str, dict, str]] = []
    mapping = {
        "will_expression": [("definition", "will_definition")],
        "will_technique": [("expression", "will_expression")],
        "will_awakening": [("expression", "will_expression")],
        "will_development": [("expression", "will_expression")],
        "will_effect": [("expression", "will_expression"), ("technique", "will_technique")],
    }
    for field, kind in mapping.get(domain, []):
        value = contract.get(field)
        if isinstance(value, dict):
            refs.append((kind, value, f"contract.{field}"))
        elif value is not None:
            refs.append((kind, {"id": value, "version": None}, f"contract.{field}"))
    if domain == "will_definition":
        for i, ancestry in enumerate(contract.get("ancestry", [])):
            refs.append(("will_definition", ancestry["parent"], f"contract.ancestry[{i}].parent"))
    if domain == "will_expression":
        for i, item in enumerate(contract.get("learned_techniques", [])):
            refs.append(("will_technique", item, f"contract.learned_techniques[{i}]"))
        if contract.get("awakening_definition"):
            refs.append(("will_awakening", contract["awakening_definition"], "contract.awakening_definition"))
    if domain == "will_technique":
        refs.append(("ability", contract.get("ability", {}), "record.ability")) if isinstance(contract.get("ability"), dict) else None
        for i, effect in enumerate(contract.get("effects", [])):
            if effect.get("resolver"):
                refs.append(("rule", effect["resolver"], f"contract.effects[{i}].resolver"))
        if isinstance(contract.get("resolution_policy"), dict):
            refs.append(("rule", contract["resolution_policy"], "contract.resolution_policy"))
    for ref_value, path in condition_refs(contract):
        # Only objects explicitly held under a ``rule`` key are rule refs;
        # ordinary record refs have already been emitted above.
        if ".rule" in path:
            refs.append(("rule", ref_value, path))
    return refs
