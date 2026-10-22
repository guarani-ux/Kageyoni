"""Strict, bounded wire records shared by every supported client."""
import hashlib
import json
from importlib.resources import files
from jsonschema import Draft202012Validator

PROTOCOL = 'samsara/5.1'
MAX_FRAME = 1048576
SCHEMA = json.loads(files('samsara').joinpath('data/contract.json').read_text())


def runtime_fingerprint():
    """Authoritative code/contract identity; renderer and prose may change."""
    names = ['application.py', 'handlers.py', 'content.py', 'owner.py', 'protocol.py', 'client.py', 'cli.py', 'intake.py',
             'data/contract.json', 'data/engine-lock.json', 'runner.py', 'process_custody.py', 'local_worker.py', 'properties.py', 'causality.py', 'extensions.py', 'situation.py', 'practice.py', 'practice_content.py', 'exploration.py', 'travel_content.py', 'sourcework.py', 'mediawork.py', 'compatibility.py', 'data/compatibility-policy.json','contentsets.py','atlas.py','equipment.py']
    return digest([[name, hashlib.sha256(files('samsara').joinpath(name).read_bytes()).hexdigest()] for name in names])


class Fault(Exception):
    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or code)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode('utf-8')).hexdigest()


def validate(value, definition):
    schema = {'$ref': '#/$defs/' + definition, '$defs': SCHEMA['$defs']}
    if not Draft202012Validator(schema).is_valid(value):
        raise Fault('INVALID')
    return value


def decode(data):
    if len(data) > MAX_FRAME:
        raise Fault('INVALID')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Fault('INVALID')
            result[key] = value
        return result
    def bad_number(_):
        raise Fault('INVALID')
    try:
        value = json.loads(data.decode('utf-8', errors='strict'), object_pairs_hook=pairs, parse_constant=bad_number)
        def depth(item, level=0):
            if level > 32:
                raise Fault('INVALID')
            if isinstance(item, dict):
                for key, child in item.items():
                    key.encode('utf-8', errors='strict'); depth(child, level + 1)
            elif isinstance(item, list):
                for child in item:
                    depth(child, level + 1)
            elif isinstance(item, str):
                item.encode('utf-8', errors='strict')
        depth(value)
        encoded(value).encode('utf-8', errors='strict')
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise Fault('INVALID') from None


def frame(value):
    data = encoded(value).encode('utf-8') + b'\n'
    if len(data) > MAX_FRAME:
        raise Fault('BUDGET')
    return data


def error(request_id, code):
    messages = {'INVALID': 'Invalid request.', 'UNAVAILABLE': 'Unavailable.',
        'STALE': 'Refresh the authorized view and prepare again.',
        'REQUEST_CONFLICT': 'Request identity conflicts with an earlier request.',
        'BUSY': 'Owner is busy; retain the input and retry later.',
        'BUDGET': 'The admitted resource budget is exhausted.',
        'DEPENDENCY': 'A required dependency is unavailable.',
        'RECONCILE_REQUIRED': 'Reconciliation is required before continuing.',
        'UNSUPPORTED': 'This operation is not installed.', 'INTERNAL': 'The operation failed; inspect the operator log.',
        'CONFLICT': 'Conflicting changes cannot be applied.'}
    return {'protocol': PROTOCOL, 'request_id': request_id, 'error': code,
        'message': messages[code], 'retryable': code in ('BUSY', 'STALE'),
        'next': {'actor': 'operator' if code == 'INTERNAL' else 'recipient',
                 'operation': 'inspect' if code == 'INTERNAL' else 'review', 'condition': messages[code]}}
