"""Fixed pure native correspondence, never caller authentication or I/O.

The future producer and history collector share these exact operation shapes.
No Engine construction, token minting, insertion, replay or permission occurs.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math

from .source_authority_schema import (
    PROFILE, SourceAuthorityError, _identifier, _require, authority_id,
    validate_creation, validate_image, validate_transition,
)
from .source_authority_installation import strict_json, OP_PREFIX

EVIDENCE = [{'source_authority_profile': PROFILE}]
_OP_KEYS = {'profile', 'operation', 'request_id', 'expected_revision', 'creation'}
_ROW_KEYS = {'workspace_id', 'source_id', 'revision', 'request_id',
             'payload_hash', 'artifact_id', 'metadata_json'}
_METADATA_KEYS = {'identity', 'expected_identity', 'captured_at', 'expires_at',
                  'locator', 'acquisition', 'identity_limit'}
_RECORD_KEYS = {'branch', 'id', 'domain', 'version', 'status', 'visibility',
                'audience', 'evidence', 'data', 'updated_event'}
ACQUISITION = 'exact captured bytes'
IDENTITY_LIMIT = ('Identity attribution supplied by operator; equality does not '
                  'independently identify a business.')


def _primitive(value):
    kind = type(value)
    if kind is dict:
        _require(all(type(key) is str for key in value), 'exact JSON string keys required')
        for child in value.values():
            _primitive(child)
    elif kind is list:
        for child in value:
            _primitive(child)
    else:
        _require(kind in (str, int, float, bool, type(None)), 'exact JSON primitive dict/list shape required')
        _require(kind is not float or math.isfinite(value), 'finite JSON number required')


def canonical(value):
    try:
        _primitive(value)
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise SourceAuthorityError('finite source authority JSON required') from error


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def _keys(value, keys, label):
    _require(type(value) is dict and all(type(k) is str for k in value)
             and set(value) == keys, 'exact ' + label + ' fields required')


def _legacy_text(value, label, limit=20000):
    _require(type(value) is str and 0 < len(value.strip()) <= limit,
             label + ' required or too long')


def _timestamp(value):
    _legacy_text(value, 'capture timestamp', 100)
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        _require(parsed.tzinfo is not None, 'capture timestamp requires timezone')
        return parsed.astimezone(timezone.utc)
    except ValueError as error:
        raise SourceAuthorityError('invalid capture timestamp') from error


def validate_source_metadata(raw):
    _require(type(raw) is str, 'stored metadata JSON text required')
    value = strict_json(raw)
    _keys(value, _METADATA_KEYS, 'stored source metadata')
    for key in ('identity', 'expected_identity', 'locator'):
        _legacy_text(value[key], key)
    captured = _timestamp(value['captured_at'])
    _require(value['expires_at'] is None or _timestamp(value['expires_at']) >= captured,
             'source expiry precedes capture')
    _require(value['acquisition'] == ACQUISITION and value['identity_limit'] == IDENTITY_LIMIT,
             'stored source attribution constants differ')
    return deepcopy(value)


def source_metadata_hash(row):
    """Hash the real stored TEXT, never a normalized metadata presentation."""
    _keys(row, _ROW_KEYS, 'stored source row')
    _identifier(row['workspace_id'], 'workspace_id')
    _identifier(row['source_id'], 'source_id')
    _identifier(row['artifact_id'], 'artifact_id')
    _legacy_text(row['request_id'], 'source request ID')
    _require(type(row['revision']) is int and row['revision'] == 1,
             'controlled source requires exactly stored revision1')
    # Reuse strict digest rules through the profile leaf, without inventing pins.
    from .source_authority_schema import _hash
    _hash(row['payload_hash'], 'stored payload hash')
    validate_source_metadata(row['metadata_json'])
    return digest(dict(row, profile=PROFILE))


def validate_operation(value):
    _keys(value, _OP_KEYS, 'source authority operation')
    _require(type(value['profile']) is str and value['profile'] == PROFILE,
             'unsupported source authority operation profile')
    _require(type(value['operation']) is str and value['operation'] in ('capture', 'withdraw'),
             'invalid source authority operation')
    _identifier(value['request_id'], 'operation request ID')
    revision = value['expected_revision']
    _require(type(revision) is int and 0 <= revision <= 2**53 - 1,
             'strict bounded expected revision required')
    return dict(profile=PROFILE, operation=value['operation'], request_id=value['request_id'],
                expected_revision=revision, creation=validate_creation(value['creation']))


def operation_image(operation):
    operation = validate_operation(operation)
    creation = operation['creation']
    if operation['operation'] == 'capture':
        return creation
    withdrawal = dict(deepcopy(creation), phase='withdrawn', revision=2)
    return validate_transition(creation, withdrawal)


def command_for(operation):
    operation = validate_operation(operation)
    image = operation_image(operation)
    capture = operation['operation'] == 'capture'
    return {
        'api_version': 3, 'branch': image['branch'],
        'expected_revision': operation['expected_revision'],
        'request_id': OP_PREFIX + digest(operation),
        'actor': image['controller_principal'], 'kind': 'maintenance',
        'narrative': 'Source authority ' + operation['operation'] + '; current selected-world custody only.',
        'changes': [{
            'op': 'create' if capture else 'patch',
            'id': authority_id(image['workspace_id'], image['source_id']),
            'domain': 'source_authority', 'expected_version': 0 if capture else 1,
            'data': {'contract': image}, 'status': 'confirmed',
            'visibility': 'restricted' if capture else 'gm',
            'audience': [image['recipient']] if capture else [],
            'evidence': deepcopy(EVIDENCE),
        }],
        'causes': [], 'judgment': {'source_authority_operation': operation},
    }


def validate_command(command):
    _require(type(command) is dict and type(command.get('judgment')) is dict
             and set(command['judgment']) == {'source_authority_operation'},
             'fixed source authority judgment required')
    operation = validate_operation(command['judgment']['source_authority_operation'])
    _require(canonical(command) == canonical(command_for(operation)),
             'source authority command differs from fixed operation')
    return operation


def validate_record(record):
    canonical(record)  # exact primitive types across the entire wrapper
    _keys(record, _RECORD_KEYS, 'complete source authority record')
    _require(type(record['data']) is dict and set(record['data']) == {'contract'},
             'source authority data must contain only contract')
    image = validate_image(record['data']['contract'])
    _require(record['domain'] == 'source_authority'
             and record['branch'] == image['branch']
             and record['id'] == authority_id(image['workspace_id'], image['source_id'])
             and type(record['version']) is int and record['version'] == image['revision']
             and record['status'] == 'confirmed', 'source authority record identity mismatch')
    active = image['phase'] == 'active'
    _require(record['visibility'] == ('restricted' if active else 'gm')
             and canonical(record['audience']) == canonical([image['recipient']] if active else [])
             and canonical(record['evidence']) == canonical(EVIDENCE),
             'source authority wrapper visibility/evidence mismatch')
    _require(type(record['updated_event']) is str and bool(record['updated_event']),
             'actual updated event identity required')
    return deepcopy(record)
