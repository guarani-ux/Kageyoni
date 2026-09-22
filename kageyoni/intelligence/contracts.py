"""Version-one operational method contracts; descriptions confer no expertise."""
from copy import deepcopy
from ..engine import encoded, require

METHOD_INTERFACE = '1'
QUALIFICATIONS = ('proposed', 'experimental', 'revoked')
QUALIFICATION_LIMIT = 'Operator-approved bounded trial; not established mastery or world authority.'


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), label + ' required')
    require(len(value) <= 20000, label + ' too long')
    return value


def integer(value, label, minimum=1):
    require(type(value) is int and value >= minimum, label + ' invalid')
    return value


def strings(value, label, *, nonempty=False):
    require(isinstance(value, list) and len(value) <= 128, label + ' must be a bounded list')
    require(not nonempty or bool(value), label + ' required')
    for item in value:
        text(item, label + ' item')
    require(len(set(value)) == len(value), label + ' contains duplicates')
    return value


def method_definition(value):
    require(isinstance(value, dict), 'method must be an object')
    required = {'name', 'operation', 'rationale', 'domains', 'preconditions',
                'failure_conditions', 'checking_procedure'}
    allowed = required | {'roles', 'relationships', 'visibility', 'audience'}
    require(required <= set(value) <= allowed, 'method fields missing or unsupported')
    result = deepcopy(value)
    for field in ('name', 'rationale'):
        text(result[field], field)
    for field in ('domains', 'preconditions', 'failure_conditions', 'checking_procedure'):
        strings(result[field], field, nonempty=True)
    operation = result['operation']
    require(isinstance(operation, dict) and set(operation) == {'kind', 'params'}, 'operation requires kind and params')
    text(operation['kind'], 'operation kind')
    require(isinstance(operation['params'], dict), 'operation params must be an object')
    result.setdefault('roles', [])
    strings(result['roles'], 'roles')
    result.setdefault('relationships', [])
    require(isinstance(result['relationships'], list) and len(result['relationships']) <= 128,
            'relationships must be a bounded list')
    for edge in result['relationships']:
        require(isinstance(edge, dict) and set(edge) == {'source', 'relation', 'target'}, 'invalid directed relationship')
        text(edge['relation'], 'relationship relation')
        require(edge['source'] in result['roles'] and edge['target'] in result['roles'], 'relationship references unknown role')
    result.setdefault('visibility', 'gm')
    result.setdefault('audience', [])
    require(result['visibility'] in ('public', 'restricted', 'gm'), 'invalid method visibility')
    strings(result['audience'], 'audience')
    require(result['visibility'] == 'restricted' or not result['audience'], 'audience only applies to restricted methods')
    require(result['visibility'] != 'restricted' or bool(result['audience']), 'restricted method needs audience')
    try:
        serialized = encoded(result)
    except (TypeError, ValueError, OverflowError, RecursionError):
        require(False, 'method must contain finite JSON values')
    require(len(serialized) <= 200000, 'method too large')
    return result


def evidence_refs(value):
    require(isinstance(value, list) and 0 < len(value) <= 128, 'source refs required')
    result = []
    seen = set()
    for ref in value:
        require(isinstance(ref, dict) and {'domain', 'id', 'record_revision'} <= set(ref)
                <= {'domain', 'id', 'record_revision', 'snapshot_hash'}, 'invalid source ref')
        text(ref['domain'], 'source domain')
        text(ref['id'], 'source id')
        integer(ref['record_revision'], 'source record revision')
        if 'snapshot_hash' in ref:
            require(isinstance(ref['snapshot_hash'], str) and len(ref['snapshot_hash']) == 64
                    and all(c in '0123456789abcdef' for c in ref['snapshot_hash']), 'invalid source snapshot hash')
        require(ref['id'] not in seen, 'duplicate source ref')
        seen.add(ref['id'])
        result.append(deepcopy(ref))
    return sorted(result, key=lambda ref: ref['id'])
