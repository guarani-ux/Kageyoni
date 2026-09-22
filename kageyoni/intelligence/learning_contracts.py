"""Bounded learning declarations. Matching recorded values is not proof of causality."""
from copy import deepcopy
from ..engine import require, encoded, Rejected
from .contracts import text, integer, strings, evidence_refs

LEARNING_INTERFACE = '1'
REVIEW_STATES = ('qualified', 'contested', 'retired')
OUTCOME_STATES = ('achieved', 'not_achieved', 'mixed', 'unknown')
JUDGMENT_LIMIT = 'Outcome interpretation and lesson qualification are owner judgments; exact source checks do not establish causality, expertise, or mastery.'


def finite_json(value, name):
    try:
        result = encoded(value)
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise Rejected(name + ' must be finite JSON') from None
    require(len(result) <= 500000, name + ' too large')
    return deepcopy(value)


def scalar(value):
    return value is None or type(value) in (str, bool, int, float)


def equal(left, right):
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    return type(left) is type(right) and left == right


def context(value):
    require(isinstance(value, dict) and len(value) <= 32, 'context must be a bounded scalar map')
    for key, item in value.items():
        text(key, 'context key')
        require(scalar(item), 'context values must be scalars')
    return finite_json(value, 'context')


def context_matches(conditions, value):
    if set(value) != {c['key'] for c in conditions}:
        return False
    return all(equal(c['equals'], value[c['key']]) for c in conditions)


def observation(value):
    require(isinstance(value, dict) and set(value) == {'status', 'rationale', 'measurements'}, 'observation requires status, rationale and measurements')
    require(value['status'] in OUTCOME_STATES, 'invalid observed outcome')
    text(value['rationale'], 'outcome rationale')
    measurements = value['measurements']
    require(isinstance(measurements, list) and 1 <= len(measurements) <= 64, 'outcome needs later source measurements')
    for item in measurements:
        require(isinstance(item, dict) and set(item) == {'value', 'evidence'}, 'invalid measurement')
        require(scalar(item['value']), 'measurement must be a scalar')
        evidence = item['evidence']
        require(isinstance(evidence, dict) and set(evidence) == {'source_ref', 'field_path'}, 'measurement needs source and field path')
        require(set(evidence['source_ref']) == {'domain', 'id', 'record_revision', 'snapshot_hash'}, 'measurement requires exact source hash')
        evidence_refs([evidence['source_ref']])
        path = evidence['field_path']
        require(isinstance(path, list) and 2 <= len(path) <= 12 and path[0] == 'data', 'measurement path must start in data')
        require(all((isinstance(part, str) and bool(part)) or (type(part) is int and part >= 0) for part in path), 'invalid measurement path')
    return finite_json(value, 'observation')


def lesson_definition(value):
    required = {'name', 'rationale', 'method_id', 'method_revision', 'task_domain', 'context_conditions', 'operation_params'}
    require(isinstance(value, dict) and required <= set(value) <= required | {'visibility', 'audience'}, 'lesson fields missing or unsupported')
    result = finite_json(value, 'lesson')
    for key in ('name', 'rationale', 'method_id', 'task_domain'):
        text(result[key], key)
    integer(result['method_revision'], 'method revision')
    conditions = result['context_conditions']
    require(isinstance(conditions, list) and 1 <= len(conditions) <= 32, 'lesson needs explicit observed context conditions')
    seen = set()
    for condition in conditions:
        require(isinstance(condition, dict) and set(condition) == {'key', 'equals'}, 'invalid context condition')
        text(condition['key'], 'context key')
        require(condition['key'] not in seen and scalar(condition['equals']), 'invalid context condition value or duplicate')
        seen.add(condition['key'])
    result['context_conditions'] = sorted(conditions, key=lambda item: item['key'])
    require(isinstance(result['operation_params'], dict), 'operation params must be an object')
    result.setdefault('visibility', 'gm'); result.setdefault('audience', [])
    require(result['visibility'] in ('gm', 'restricted', 'public'), 'invalid lesson visibility')
    strings(result['audience'], 'audience')
    require(result['visibility'] == 'restricted' or not result['audience'], 'audience only applies to restricted lessons')
    require(result['visibility'] != 'restricted' or bool(result['audience']), 'restricted lesson needs audience')
    return result
