"""New 20261023 source-authority profile: pure images, never authentication.

This module performs no I/O or native activity. Callers must explicitly select
this controlled profile; legacy source identifiers must not be routed here.
"""
import hashlib
import json
import re
import unicodedata

PROFILE = 'samsara-source-authority/20261023-1'


class SourceAuthorityError(ValueError):
    """An image, transition or controlled identifier violates this profile."""


_IMAGE_KEYS = frozenset((
    'profile', 'branch', 'workspace_id', 'source_id', 'controller_principal',
    'recipient', 'source_payload_hash', 'source_metadata_hash', 'source_pin',
    'artifact_pin', 'phase', 'revision',
))
_PIN_KEYS = frozenset(('id', 'version', 'digest'))
_IDENTIFIERS = ('branch', 'workspace_id', 'source_id', 'controller_principal', 'recipient')
_HEX = re.compile(r'[0-9a-f]{64}')


def _require(condition, message):
    if not condition:
        raise SourceAuthorityError(message)


def _identifier(value, label):
    _require(type(value) is str and bool(value), label + ': controlled string required')
    _require(value == value.strip(), label + ': surrounding whitespace refused')
    _require(not any(unicodedata.category(c).startswith('C') for c in value),
             label + ': Unicode category C refused')
    _require(len(value.encode('utf-8')) <= 512, label + ': exceeds 512 UTF-8 bytes')
    return value


def _hash(value, label):
    _require(type(value) is str and _HEX.fullmatch(value) is not None,
             label + ': lowercase 64-hex digest required')
    return value


def _keys(value, expected, label):
    _require(type(value) is dict, label + ': exact dict required')
    _require(all(type(k) is str for k in value) and set(value) == expected,
             label + ': exact keys required')


def _pin(value, label):
    _keys(value, _PIN_KEYS, label)
    identifier = _identifier(value['id'], label + '.id')
    _require(type(value['version']) is int and value['version'] == 1,
             label + ': version must be exactly int1')
    return {'id': identifier, 'version': 1, 'digest': _hash(value['digest'], label + '.digest')}


def validate_image(value):
    """Return an independent valid image; no existence or authority is proven."""
    _keys(value, _IMAGE_KEYS, 'source authority image')
    _require(type(value['profile']) is str and value['profile'] == PROFILE,
             'unsupported source authority profile')
    result = {'profile': PROFILE}
    for field in _IDENTIFIERS:
        result[field] = _identifier(value[field], field)
    for field in ('source_payload_hash', 'source_metadata_hash'):
        result[field] = _hash(value[field], field)
    result['source_pin'] = _pin(value['source_pin'], 'source_pin')
    result['artifact_pin'] = _pin(value['artifact_pin'], 'artifact_pin')
    _require(result['source_pin']['id'] == result['source_id'], 'source pin family mismatch')
    _require(result['artifact_pin']['id'] != result['source_id'], 'distinct artifact identity required')
    _require(result['artifact_pin']['digest'] == result['source_pin']['digest'],
             'captured source/artifact body digest mismatch')
    phase = value['phase']
    _require(type(phase) is str and phase in ('active', 'withdrawn'), 'invalid authority phase')
    revision = value['revision']
    _require(type(revision) is int and revision == (1 if phase == 'active' else 2),
             'phase/revision pair must be active1 or withdrawn2')
    result['phase'] = phase
    result['revision'] = revision
    return result


def validate_creation(value):
    """Return an independent active1 image; this does not create a source."""
    result = validate_image(value)
    _require(result['phase'] == 'active', 'creation requires active1')
    return result


def validate_transition(old, new):
    """Return an independent withdrawn2 image for the sole allowed transition.

    Both full images are validated independently. No state is updated, no
    consent/controller is authenticated and no native history is inspected.
    """
    previous = validate_image(old)
    result = validate_image(new)
    _require(previous['phase'] == 'active' and result['phase'] == 'withdrawn',
             'only active1 to withdrawn2 is permitted')
    _require(all(previous[key] == result[key] for key in _IMAGE_KEYS - {'phase', 'revision'}),
             'authority identity, audience and capture fields are immutable')
    return result


def authority_id(workspace_id, source_id):
    """Return a deterministic routing name, never a permission or event proof."""
    _identifier(workspace_id, 'workspace_id')
    _identifier(source_id, 'source_id')
    body = json.dumps([PROFILE, workspace_id, source_id], ensure_ascii=False,
                      separators=(',', ':')).encode('utf-8')
    return 'source-authority:' + hashlib.sha256(body).hexdigest()
