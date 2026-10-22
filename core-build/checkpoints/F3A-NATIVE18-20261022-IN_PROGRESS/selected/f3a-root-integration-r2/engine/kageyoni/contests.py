"""Explicit synthetic exhibition terms, genuine consent and conserved awards.

Native records/events are authoritative. Projection tables add no request or
award ledger. This module does not install itself, choose actors, call a tool,
execute a fixture, supply a winner, or alter old no-award definitions.
Pure validation imports only stdlib; native APIs import their existing seams
when called. Root must bind DOMAINS/REQUIRED and the conditional verify hook.
"""
from copy import deepcopy
import hashlib
import json
import math
import re

INTERFACE = '1'
PREFIX = 'synthetic:f3a:'
DEFINITION_PREFIX = PREFIX + 'exhibition:'
BOUNDARY = 'Voluntary synthetic material award only; no compulsory subsistence, debt, injury or mastery.'
DOMAINS = {
    'contest_terms': {'contract': 'json', 'terms_digest': 'text', 'resource_preimages': 'json', 'defined_by': 'text'},
    'contest_consent': {'terms': 'ref:contest_terms', 'entrant': 'ref:character', 'choice': 'enum:accepted|declined|withdrawn', 'terms_digest': 'text'},
    'contest_settlement': {'terms': 'ref:contest_terms', 'terms_digest': 'text', 'beneficiary': 'ref:character', 'amount': 'integer', 'unit': 'text', 'pool': 'ref:resource', 'destination': 'ref:resource', 'terminal_event': 'text', 'proof': 'json'},
}
REQUIRED = {domain: list(fields) for domain, fields in DOMAINS.items()}
_TERMS_KEYS = {'version', 'contest_id', 'new_synthetic_exhibition', 'encounter', 'pool', 'destinations', 'amount', 'unit', 'eligible_actions', 'boundary'}
_ENCOUNTER_KEYS = {'id', 'definition_id', 'definition_version', 'definition_digest', 'participants'}
_RECORD_KEYS = {'branch', 'id', 'domain', 'version', 'status', 'visibility', 'audience', 'evidence', 'data', 'updated_event'}
_ALLOCATION_KEYS = {'branch', 'id', 'domain', 'version', 'data'}
TRANSFER_EVIDENCE = [{'note': 'Coupled conserved synthetic contest material transfer; no refund or mastery.'}]


class ContestValidationError(ValueError):
    """Pure schema rejection; native entry points translate to Engine.Rejected."""


def _ensure(ok, message):
    if not ok:
        raise ContestValidationError(message)


def _text(value, label='text', maximum=512):
    _ensure(type(value) is str and 0 < len(value.encode('utf-8')) <= maximum and value.strip() == value and bool(value), 'invalid ' + label)
    return value


def _integer(value, label='integer', minimum=0):
    _ensure(type(value) is int and minimum <= value <= 2**53 - 1, 'invalid ' + label)
    return value


def _quantity(value):
    # Native resource.quantity is REAL. Engine.get therefore returns 2.0 for
    # an originally integer 2. No bool, fractional, nonfinite or inexact-large
    # material is admitted. The public award amount remains strict int.
    _ensure(type(value) in (int, float) and 0 <= value <= 2**53 - 1 and math.isfinite(value) and int(value) == value, 'invalid integral resource quantity')
    return int(value)


def _shape(value, keys, label):
    _ensure(type(value) is dict and set(value) == set(keys), 'invalid ' + label + ' fields')


def canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ContestValidationError('invalid finite contest JSON') from exc


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _reference(value):
    _shape(value, {'id', 'version'}, 'resource reference')
    _text(value['id'], 'resource ID'); _integer(value['version'], 'resource version', 1)
    _ensure(value['id'].startswith(PREFIX), 'new synthetic resources required')


def validate_terms(value, definition=None):
    """One strict bounded data contract, optionally checked against actual spec.

    New operator-reviewed definition identity is mandatory. We do not infer a
    winner or a no-award exception from prose or old generic outcome labels.
    """
    _shape(value, _TERMS_KEYS, 'ContestTerms/1')
    _ensure(type(value['version']) is int and value['version'] == 1 and value['new_synthetic_exhibition'] is True, 'new version1 synthetic exhibition required')
    _text(value['contest_id'], 'contest ID', 400)
    _ensure(value['contest_id'].startswith(PREFIX), 'synthetic contest ID required')
    encounter = value['encounter']; _shape(encounter, _ENCOUNTER_KEYS, 'encounter pin')
    _text(encounter['id'], 'encounter ID')
    _ensure(encounter['id'].startswith(PREFIX), 'new synthetic encounter instance required')
    _text(encounter['definition_id'], 'definition ID')
    _ensure(encounter['definition_id'].startswith(DEFINITION_PREFIX), 'new explicit exhibition definition identity required')
    _integer(encounter['definition_version'], 'definition version', 1)
    _ensure(type(encounter['definition_digest']) is str and re.fullmatch('[0-9a-f]{64}', encounter['definition_digest']) is not None, 'invalid definition digest')
    participants = encounter['participants']
    _ensure(type(participants) is dict and len(participants) == 2, 'exactly two roles required')
    for role, entrant in participants.items():
        _text(role, 'role'); _text(entrant, 'entrant')
    _ensure(len(set(participants.values())) == 2, 'distinct entrants required')
    _reference(value['pool'])
    _ensure(type(value['destinations']) is dict and set(value['destinations']) == set(participants), 'one destination for each actual role required')
    for reference in value['destinations'].values():
        _reference(reference)
    ids = [value['pool']['id']] + [v['id'] for v in value['destinations'].values()]
    _ensure(len(set(ids)) == 3, 'pool and both destinations must be distinct')
    _integer(value['amount'], 'award amount', 1); _text(value['unit'], 'unit', 128)
    _ensure(value['boundary'] == BOUNDARY, 'explicit no-subsistence boundary required')
    eligible = value['eligible_actions']
    _ensure(type(eligible) is dict and 1 <= len(eligible) <= 16, 'eligible terminal mapping required')
    for action, role in eligible.items():
        _text(action, 'eligible action'); _ensure(type(role) is str and role in participants, 'beneficiary role absent')
    _ensure(len(canonical(value).encode()) <= 32768, 'terms exceed bound')
    if definition is not None:
        _ensure(digest(definition) == encounter['definition_digest'] and set(definition['roles']) == set(participants), 'actual definition pin mismatch')
        for action_id in eligible:
            action = definition['actions'].get(action_id)
            _ensure(action is not None and action['kind'] == 'event' and action.get('next_state') in definition['states'], 'eligible action is not authored event')
            state = definition['states'][action['next_state']]
            _ensure(state['phase'] == 'completed' and state['outcome'] == 'achieved', 'eligible terminal state must be completed/achieved')
            _ensure(bool(action['payload'].get('changes')), 'eligible terminal action needs actual world-effect changes')
    return deepcopy(value)


def validate_resource(record, unit, holder=None):
    _ensure(type(record) is dict and set(record) == _RECORD_KEYS and record['domain'] == 'resource', 'genuine complete native resource image required')
    _integer(record['version'], 'resource version', 1)
    _text(record['id'], 'resource ID'); _text(record['branch'], 'resource branch')
    data = record['data']; _ensure(type(data) is dict and data.get('unit') == unit, 'resource unit mismatch')
    _quantity(data.get('quantity'))
    _ensure(type(data.get('holder')) is str and (holder is None or data['holder'] == holder), 'resource holder mismatch')
    _ensure(record['id'].startswith(PREFIX), 'new synthetic resource image required')
    return deepcopy(record)


def validate_conservation(before, after, amount):
    """Full native preimages and explicit semantic after-allocation projections.

    Engine assigns the after event ID/evidence during apply. Exact complete
    native after-images live in immutable changes and are returned separately.
    """
    _integer(amount, 'award amount', 1)
    _shape(before, {'pool', 'destination'}, 'before images')
    _shape(after, {'pool', 'destination'}, 'after images')
    pool, dest = before['pool'], before['destination']
    _ensure(type(pool) is dict and type(pool.get('data')) is dict and type(dest) is dict, 'complete resource preimages required')
    validate_resource(pool, pool['data']['unit']); validate_resource(dest, pool['data']['unit'])
    _ensure(pool['id'] != dest['id'] and pool['branch'] == dest['branch'], 'distinct same-branch resources required')
    _ensure(pool['data']['quantity'] >= amount, 'insufficient pool')
    for key, delta in [('pool', -amount), ('destination', amount)]:
        old, new = before[key], after[key]
        _shape(new, _ALLOCATION_KEYS, 'after allocation projection')
        full = dict(deepcopy(old), **new)
        validate_resource(full, pool['data']['unit'], old['data']['holder'])
        _ensure(new['id'] == old['id'] and new['branch'] == old['branch'] and new['version'] == old['version'] + 1, 'resource identity/version mismatch')
        expected = deepcopy(old['data']); expected['quantity'] += delta
        _ensure(new['data'] == expected, 'unrelated resource field changed')
    pre = _quantity(pool['data']['quantity']) + _quantity(dest['data']['quantity'])
    post = _quantity(after['pool']['data']['quantity']) + _quantity(after['destination']['data']['quantity'])
    _ensure(pre == post, 'award material not conserved')
    return pre


def validate_record(record):
    """Pure hook for root's common native record validator."""
    domain, data = record.get('domain'), record.get('data')
    if domain not in DOMAINS:
        return
    _shape(record, _RECORD_KEYS, 'complete native contest record')
    _integer(record['version'], 'record version', 1)
    _ensure(record['status'] == 'reported' and record['visibility'] == 'restricted' and type(record['audience']) is list and len(record['audience']) == 2 and all(type(x) is str and x for x in record['audience']) and len(set(record['audience'])) == 2, 'contest requires two explicit participant viewers')
    _shape(data, DOMAINS[domain], domain)
    if domain == 'contest_terms':
        terms = validate_terms(data['contract'])
        _ensure(set(record['audience']) == set(terms['encounter']['participants'].values()), 'terms audience differs from entrants')
        _ensure(data['terms_digest'] == digest(terms), 'terms digest mismatch')
        _text(data['defined_by'], 'defining actor')
        _shape(data['resource_preimages'], {'pool', 'destinations'}, 'pinned resource preimages')
        validate_resource(data['resource_preimages']['pool'], terms['unit'])
        _ensure(all(data['resource_preimages']['pool'][key] == terms['pool'][key] for key in ('id', 'version')), 'pool preimage pin mismatch')
        _ensure(set(data['resource_preimages']['destinations']) == set(terms['destinations']), 'destination preimage roles mismatch')
        for role, image in data['resource_preimages']['destinations'].items():
            validate_resource(image, terms['unit'], terms['encounter']['participants'][role])
            _ensure(all(image[key] == terms['destinations'][role][key] for key in ('id', 'version')), 'destination preimage pin mismatch')
    elif domain == 'contest_consent':
        _ensure(data['choice'] in ('accepted', 'declined', 'withdrawn'), 'invalid consent choice')
        for key in ['terms', 'entrant', 'terms_digest']:
            _text(data[key], key)
        _ensure(data['entrant'] in record['audience'], 'consent audience must include actual entrant')
    else:
        _integer(data['amount'], 'settled amount', 1)
        for key in ['terms', 'terms_digest', 'beneficiary', 'unit', 'pool', 'destination', 'terminal_event']:
            _text(data[key], key)
        _shape(data['proof'], {'terminal', 'consents', 'before', 'after_allocations', 'total', 'operation'}, 'settlement proof')
        _ensure(type(data['proof']['total']) is int, 'strict material total required')
        _ensure(validate_conservation(data['proof']['before'], data['proof']['after_allocations'], data['amount']) == data['proof']['total'], 'settlement total mismatch')


def _native():
    from .engine import require
    from .persistence.unit_of_work import UnitOfWork
    return require, UnitOfWork


def _validated(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except (ContestValidationError, KeyError, TypeError, ValueError) as exc:
        _native()[0](False, 'invalid contest contract: ' + str(exc))


def validate_engine_record(engine, record):
    """Public common-engine adapter; old domains remain an exact no-op.

    New domains require complete installation through the sole collector, then
    pure validation translates ContestValidationError into native Rejected.
    """
    if record.get('domain') not in DOMAINS:
        return
    _native()[0](_interface(engine), 'contest interface not installed')
    _validated(validate_record, record)


def _terms_id(contest_id): return contest_id + ':terms'
def _settlement_id(contest_id): return contest_id + ':settlement'
def _consent_id(contest_id, actor): return contest_id + ':consent:' + digest(actor)


def viewer_record_allows_context(viewer, record):
    """Pure privacy precheck; integrity errors obtaining record are not caught."""
    return viewer is None or record is not None and record['domain'] == 'character'


class Contests:
    def __init__(self, engine):
        self.engine, self.db = engine, engine.db

    def _check(self, ok, message): _native()[0](ok, message)

    def _installed(self):
        self._check(_interface(self.engine), 'contest interface not installed')

    def _visible(self, branch, contest_id, viewer):
        self._installed()
        if viewer is not None:
            _validated(_text, viewer, 'viewer')
            # Engine.get itself still exposes genuine corrupt-projection errors.
            # Only a genuinely absent/noncharacter viewer is normalized here.
            self._check(viewer_record_allows_context(viewer, self.engine.get(branch, viewer)), 'contest unavailable')
        visible = {r['id']: r for r in self.engine.context(branch, viewer=viewer)['records']}
        shown = visible.get(_terms_id(contest_id))
        self._check(shown is not None and shown['domain'] == 'contest_terms', 'contest unavailable')
        record = self.engine.get(branch, shown['id'])
        _validated(validate_record, record)
        return record

    def _caller(self, terms, actor, viewer):
        self._check(type(actor) is str and actor in terms['encounter']['participants'].values() and (viewer is None or viewer == actor), 'contest unavailable')

    def _payload(self, operation, branch, contest_id, actor, request_id, expected_revision, **extra):
        _validated(_text, branch, 'branch'); _validated(_text, contest_id, 'contest ID')
        _validated(_text, actor, 'actor'); _validated(_text, request_id, 'request ID')
        _validated(_integer, expected_revision, 'expected revision')
        return dict(operation=operation, branch=branch, contest_id=contest_id, actor=actor, request_id=request_id, expected_revision=expected_revision, **deepcopy(extra))

    def _event(self, branch, event_id):
        row = self.db.execute('SELECT * FROM events WHERE branch=? AND id=?', (branch, event_id)).fetchone()
        self._check(row is not None, 'contest historical event unavailable')
        command = json.loads(row['command_json']); receipt = json.loads(row['receipt_json'])
        self._check(digest(command) == row['payload_hash'] and receipt['event_id'] == event_id and receipt['committed'] is True and receipt['branch'] == row['branch'] == command['branch'] and receipt['revision'] == row['revision'] and receipt['request_id'] == row['request_id'] == command['request_id'] and receipt['event_hash'] == row['event_hash'], 'contest native event correspondence mismatch')
        return dict(row), command, receipt

    def _historical_record(self, event_id, record_id):
        row = self.db.execute('SELECT before_json,after_json FROM changes WHERE event_id=? AND record_id=?', (event_id, record_id)).fetchone()
        self._check(row is not None, 'contest native change missing')
        return (json.loads(row['before_json']) if row['before_json'] else None), json.loads(row['after_json'])

    def _operation(self, record, expected_kind):
        self._check(record['domain'] == {'define':'contest_terms','consent':'contest_consent','settle':'contest_settlement'}[expected_kind], 'contest operation domain mismatch')
        event, command, receipt = self._event(record['branch'], record['updated_event'])
        operation = command.get('judgment', {}).get('contest_operation')
        keys = {'operation','branch','contest_id','actor','request_id','expected_revision'} | ({'terms'} if expected_kind == 'define' else {'terms_digest','choice'} if expected_kind == 'consent' else {'terms_digest'})
        _validated(_shape, operation, keys, 'native contest operation')
        self._check(operation['operation'] == expected_kind and command['request_id'] == 'contest-operation:' + operation['request_id'] and command['actor'] == operation['actor'] and command['branch'] == operation['branch'] == record['branch'] and command['expected_revision'] == operation['expected_revision'] == event['revision'] - 1 and command['kind'] == 'action', 'contest operation event mismatch')
        rebuilt = self._payload(expected_kind, operation['branch'], operation['contest_id'], operation['actor'], operation['request_id'], operation['expected_revision'], **{key: operation[key] for key in keys - {'operation','branch','contest_id','actor','request_id','expected_revision'}})
        self._check(rebuilt == operation, 'contest operation fields mismatch')
        self._check(self._historical_record(event['id'], record['id'])[1] == record, 'contest projection differs from historical image')
        if expected_kind != 'settle':
            self._check(receipt['changed'] == [record['id']] and len(command['changes']) == 1, 'contest operation must create exactly one separate fact')
        return event, operation, receipt

    def _image_before(self, branch, record_id, revision):
        row = self.db.execute('SELECT c.after_json FROM changes c JOIN events e ON e.id=c.event_id WHERE e.branch=? AND c.record_id=? AND e.revision<=? ORDER BY e.revision DESC,c.ordinal DESC LIMIT 1', (branch, record_id, revision)).fetchone()
        self._check(row is not None, 'contest historical resource image missing')
        return json.loads(row[0])

    def _verify_terms(self, record):
        _validated(validate_record, record)
        event, operation, receipt = self._operation(record, 'define')
        terms = record['data']['contract']
        self._check(record['id'] == _terms_id(operation['contest_id']) and record['version'] == 1 and operation['terms'] == terms and operation['actor'] == record['data']['defined_by'] and self._historical_record(event['id'], record['id'])[0] is None and json.loads(event['causes_json']) == [], 'contest terms native definition mismatch')
        _, _, _, _ = self._pin(record['branch'], terms)
        start = self.db.execute('SELECT after_json FROM encounter_events WHERE branch=? AND encounter_id=? AND revision=1', (record['branch'], terms['encounter']['id'])).fetchone()
        initial = json.loads(start[0]); self._check(initial['world_revision'] <= operation['expected_revision'], 'contest defined before native encounter start')
        next_step = self.db.execute('SELECT payload_json FROM encounter_events WHERE branch=? AND encounter_id=? AND revision=2', (record['branch'], terms['encounter']['id'])).fetchone()
        if next_step:
            self._check(event['revision'] <= json.loads(next_step[0])['expected_revision'], 'contest terms not defined before competitive sequence')
        images = record['data']['resource_preimages']
        for image in [images['pool'], *images['destinations'].values()]:
            historical = self._image_before(record['branch'], image['id'], operation['expected_revision'])
            _validated(validate_resource, historical, terms['unit'])
            self._check(historical == image, 'contest preimage was not the actual resource at definition')
        self._check(images['pool']['data']['quantity'] >= terms['amount'], 'defined pool insufficient')
        return event, receipt

    def _reply(self, record, receipt, replayed=False):
        result = {'kind': record['domain'], 'record': deepcopy(record), 'reference': {'domain': record['domain'], 'id': record['id'], 'record_revision': record['version'], 'snapshot_hash': digest(record)}, 'native_receipt': deepcopy(receipt), 'replayed': replayed, 'scope': BOUNDARY}
        if record['domain'] == 'contest_settlement':
            result['historical_resources'] = {record['data'][key]: dict(zip(('before', 'after'), self._historical_record(record['updated_event'], record['data'][key]))) for key in ('pool', 'destination')}
        return result

    def _prior(self, payload):
        row = self.db.execute('SELECT * FROM events WHERE branch=? AND request_id=?', (payload['branch'], 'contest-operation:' + payload['request_id'])).fetchone()
        if row is None: return None
        command = json.loads(row['command_json'])
        self._check(command.get('judgment', {}).get('contest_operation') == payload and digest(command) == row['payload_hash'], 'contest request reused with changed operation')
        refs = [json.loads(x['after_json']) for x in self.db.execute('SELECT after_json FROM changes WHERE event_id=? ORDER BY ordinal', (row['id'],))]
        facts = [r for r in refs if r['domain'] in DOMAINS]
        self._check(len(facts) == 1, 'contest historical operation fact mismatch')
        _validated(validate_record, facts[0]); self._operation(facts[0], payload['operation'])
        return self._reply(facts[0], json.loads(row['receipt_json']), True)

    def _apply(self, payload, changes, causes=()):
        return self.engine.apply({'api_version': 3, 'branch': payload['branch'], 'request_id': 'contest-operation:' + payload['request_id'], 'expected_revision': payload['expected_revision'], 'actor': payload['actor'], 'kind': 'action', 'narrative': 'Explicit synthetic contest ' + payload['operation'] + '; ' + BOUNDARY, 'changes': changes, 'causes': list(causes), 'judgment': {'contest_operation': deepcopy(payload)}})

    def _create(self, rid, domain, data, participants):
        return {'op': 'create', 'id': rid, 'domain': domain, 'data': deepcopy(data), 'status': 'reported', 'visibility': 'restricted', 'audience': sorted(participants), 'evidence': [{'note': 'Explicit new synthetic contest operation, native provenance only; ' + BOUNDARY}]}

    def _pin(self, branch, terms, initial=False):
        from .workspaces.world import Encounters
        row, spec, participants, _ = Encounters(self.engine)._instance(branch, terms['encounter']['id'], None)
        _validated(validate_terms, terms, spec)
        self._check(row['definition_id'] == terms['encounter']['definition_id'] and row['definition_version'] == terms['encounter']['definition_version'] and participants == terms['encounter']['participants'], 'contest encounter pin differs from actual native start')
        state = json.loads(row['state_json'])
        if initial:
            self._check(row['revision'] == 1 and state['steps'] == 0 and state['current_state'] == spec['initial_state'] and state['phase'] == 'active' and state['pending'] is None, 'contest must still be at actual initial native step')
        return row, spec, participants, state

    def _resources(self, branch, terms):
        result = {'pool': self.engine.get(branch, terms['pool']['id']), 'destinations': {role: self.engine.get(branch, ref['id']) for role, ref in terms['destinations'].items()}}
        _validated(validate_resource, result['pool'], terms['unit'])
        self._check(result['pool']['version'] == terms['pool']['version'], 'stale pool resource')
        for role, record in result['destinations'].items():
            _validated(validate_resource, record, terms['unit'], terms['encounter']['participants'][role])
            self._check(record['version'] == terms['destinations'][role]['version'], 'stale destination resource')
        return result

    def define(self, branch, contest_id, terms, request_id, expected_revision, actor, viewer=None):
        self._check(viewer is None, 'owner view required to define contest')
        self._installed(); terms = _validated(validate_terms, terms)
        self._check(terms['contest_id'] == contest_id, 'contest identity differs from terms')
        payload = self._payload('define', branch, contest_id, actor, request_id, expected_revision, terms=terms)
        with _native()[1](self.db):
            prior = self._prior(payload)
            if prior: return prior
            self._pin(branch, terms, True)
            renamed = self.db.execute('SELECT 1 FROM encounter_definitions WHERE digest=? AND substr(definition_id,1,?)<>? LIMIT 1', (terms['encounter']['definition_digest'], len(DEFINITION_PREFIX), DEFINITION_PREFIX)).fetchone()
            self._check(renamed is None, 'an existing foreign/no-award definition cannot be admitted by renaming the same spec')
            resources = self._resources(branch, terms)
            self._check(resources['pool']['data']['quantity'] >= terms['amount'], 'insufficient declared pool')
            self._check(self.engine.get(branch, _terms_id(contest_id)) is None, 'contest terms already defined and immutable')
            for entrant in terms['encounter']['participants'].values():
                visible = {r['id'] for r in self.engine.context(branch, viewer=entrant)['records']}
                self._check(all(r['id'] in visible and r['data']['holder'] in visible for r in [resources['pool'], *resources['destinations'].values()]), 'contest resources or holders unavailable to entrant')
            data = {'contract': terms, 'terms_digest': digest(terms), 'resource_preimages': resources, 'defined_by': actor}
            receipt = self._apply(payload, [self._create(_terms_id(contest_id), 'contest_terms', data, terms['encounter']['participants'].values())])
            record = self.engine.get(branch, _terms_id(contest_id)); self._verify_terms(record)
            return self._reply(record, receipt)

    def consent(self, branch, contest_id, actor, choice, request_id, expected_revision, viewer=None):
        record = self._visible(branch, contest_id, viewer); terms = record['data']['contract']; self._caller(terms, actor, viewer)
        self._check(choice in ('accepted', 'declined', 'withdrawn'), 'invalid contest consent choice')
        payload = self._payload('consent', branch, contest_id, actor, request_id, expected_revision, choice=choice, terms_digest=record['data']['terms_digest'])
        with _native()[1](self.db):
            prior = self._prior(payload)
            if prior: return prior
            self._verify_terms(record)
            self._check(self.engine.get(branch, _settlement_id(contest_id)) is None, 'settled consent cannot change the historical award')
            if choice in ('accepted', 'declined'): self._pin(branch, terms, True)
            else: self._pin(branch, terms)
            rid = _consent_id(contest_id, actor); old = self.engine.get(branch, rid)
            self._check(old is None or old['data']['choice'] == 'accepted' and choice == 'withdrawn', 'consent is final except explicit withdrawal of accepted consent')
            data = {'terms': record['id'], 'entrant': actor, 'choice': choice, 'terms_digest': record['data']['terms_digest']}
            change = self._create(rid, 'contest_consent', data, terms['encounter']['participants'].values()) if old is None else {'op': 'patch', 'id': rid, 'expected_version': old['version'], 'data': data, 'evidence': [{'note': 'Actual entrant explicitly withdrew contest consent; no material refund.'}]}
            receipt = self._apply(payload, [change], [record['updated_event']])
            current = self.engine.get(branch, rid); self._verify_consent(current, record)
            return self._reply(current, receipt)

    def _verify_consent(self, consent, record):
        _validated(validate_record, consent)
        terms = record['data']['contract']; data = consent['data']
        event, operation, receipt = self._operation(consent, 'consent')
        self._caller(terms, operation['actor'], None)
        self._check(set(consent['audience']) == set(record['audience']), 'consent audience differs from actual entrants')
        self._check(data == {'terms': record['id'], 'entrant': operation['actor'], 'choice': operation['choice'], 'terms_digest': record['data']['terms_digest']} and operation['contest_id'] == terms['contest_id'] and operation['terms_digest'] == data['terms_digest'] and consent['id'] == _consent_id(terms['contest_id'], data['entrant']) and json.loads(event['causes_json']) == [record['updated_event']], 'contest consent terms/entrant provenance mismatch')
        defined, _, _ = self._event(record['branch'], record['updated_event'])
        self._check(event['revision'] > defined['revision'], 'consent must follow actual terms event')
        before, _ = self._historical_record(event['id'], consent['id'])
        if before is None:
            self._check(consent['version'] == 1, 'initial consent version mismatch')
        else:
            self._check(data['choice'] == 'withdrawn' and before['data']['choice'] == 'accepted' and consent['version'] == 2 and before['version'] == 1, 'only accepted consent can be withdrawn')
            self._verify_consent(before, record)
        if data['choice'] in ('accepted', 'declined'):
            next_step = self.db.execute('SELECT payload_json FROM encounter_events WHERE branch=? AND encounter_id=? AND revision=2', (record['branch'], terms['encounter']['id'])).fetchone()
            if next_step:
                self._check(event['revision'] <= json.loads(next_step[0])['expected_revision'], 'consent did not precede native sequence')
        return event, receipt

    def _terminal(self, branch, terms):
        row, spec, participants, state = self._pin(branch, terms)
        self._check(state['phase'] == 'completed' and state['outcome'] == 'achieved', 'contest has no eligible achieved native result')
        history = list(self.db.execute('SELECT * FROM encounter_events WHERE branch=? AND encounter_id=? ORDER BY revision', (branch, row['encounter_id'])))
        self._check(len(history) >= 2 and len(history) == row['revision'], 'contest native history missing')
        previous = None; first_world_revision = None
        for ordinal, entry in enumerate(history, 1):
            payload = json.loads(entry['payload_json']); after = json.loads(entry['after_json']); receipt = json.loads(entry['receipt_json'])
            before = json.loads(entry['before_json']) if entry['before_json'] else None
            self._check(entry['revision'] == ordinal and before == previous and digest(payload) == entry['payload_hash'] and payload['request_id'] == entry['request_id'] and receipt['state_digest'] == digest(after) and receipt['state_revision'] == ordinal, 'contest native history correspondence failed')
            self._check(payload['branch'] == branch and payload['encounter_id'] == row['encounter_id'] and receipt['definition_id'] == row['definition_id'] and receipt['definition_version'] == row['definition_version'] and receipt['encounter_id'] == row['encounter_id'] and receipt['branch'] == branch and receipt['phase'] == after['phase'] and receipt['outcome'] == after['outcome'] and receipt['state'] == after['current_state'] and receipt['world_revision'] == after['world_revision'], 'contest historical receipt pin mismatch')
            if ordinal == 1:
                self._check(payload['definition_id'] == row['definition_id'] and payload['definition_version'] == row['definition_version'] and payload['participants'] == participants and after['steps'] == 0, 'contest pinned start mismatch')
            else:
                action_id = payload.get('action_id'); action = spec['actions'].get(action_id)
                self._check(action is not None and payload.get('operation') is None and receipt.get('world_receipt') is not None, 'unknown/control/maintenance history cannot supply contest eligibility')
                event, command, actual = self._event(branch, receipt['world_receipt']['event_id'])
                self._check(action['kind'] == 'event' and action_id in spec['states'][before['current_state']]['actions'] and actual == receipt['world_receipt'] and command['request_id'] == 'encounter-action:' + entry['request_id'] and command['actor'] == participants[action['actor_role']] and command['kind'] == 'action' and event['revision'] == after['world_revision'] and event['revision'] == payload['expected_revision'] + 1 and after['steps'] == before['steps'] + 1 and not payload['fields'] and after['current_state'] == action['next_state'], 'contest native authored-event producer mismatch')
                self._check(before['phase'] == 'active' and before['pending'] is None, 'contest sequence contains unresolved/control history')
                first_world_revision = event['revision'] if first_world_revision is None else first_world_revision
            previous = after
        self._check(previous == state, 'contest final projection differs from native history')
        final = history[-1]; payload = json.loads(final['payload_json']); action_id = payload.get('action_id')
        self._check(action_id in terms['eligible_actions'], 'native terminal action is not award eligible')
        action = spec['actions'][action_id]; receipt = json.loads(final['receipt_json'])
        self._check(action['kind'] == 'event' and action.get('next_state') == state['current_state'] and bool(receipt['world_receipt']['changed']), 'terminal action lacks its actual world effect')
        terminal_event, command, _ = self._event(branch, receipt['world_receipt']['event_id'])
        from .workspaces.world import _expand
        authored = _expand(action['payload'], participants, row['encounter_id'])
        actual_changes = deepcopy(command['changes'])
        for change in actual_changes: change.pop('expected_version', None)
        expected_changes = deepcopy(authored['changes'])
        for change in expected_changes: change.pop('expected_version', None)
        self._check(actual_changes == expected_changes, 'terminal effect differs from pinned authored producer')
        return {'encounter_receipt': receipt, 'world_event': terminal_event['id'], 'world_revision': terminal_event['revision'], 'encounter_revision': final['revision'], 'action_id': action_id, 'beneficiary': participants[terms['eligible_actions'][action_id]], 'first_competitive_world_revision': first_world_revision}

    def _accepted_consents(self, branch, record, terminal):
        terms = record['data']['contract']; result = {}
        for role, entrant in terms['encounter']['participants'].items():
            consent = self.engine.get(branch, _consent_id(terms['contest_id'], entrant))
            self._check(consent is not None and consent['domain'] == 'contest_consent' and consent['data'] == {'terms': record['id'], 'entrant': entrant, 'choice': 'accepted', 'terms_digest': record['data']['terms_digest']}, 'both genuine current accepted consents required')
            event, receipt = self._verify_consent(consent, record)
            _, operation, _ = self._operation(consent, 'consent')
            self._check(operation['actor'] == entrant and operation['choice'] == 'accepted' and operation['contest_id'] == terms['contest_id'] and operation['terms_digest'] == record['data']['terms_digest'] and self._historical_record(event['id'], consent['id'])[0] is None and record['version'] == 1 and event['revision'] < terminal['first_competitive_world_revision'], 'consent was not separately accepted before competition')
            result[role] = {'record': consent, 'native_event': event['id'], 'native_receipt': receipt}
        self._check(len({x['native_event'] for x in result.values()}) == 2, 'two different genuine consent events required')
        return result

    def settle(self, branch, contest_id, actor, request_id, expected_revision, viewer=None):
        record = self._visible(branch, contest_id, viewer); terms = record['data']['contract']; self._caller(terms, actor, viewer)
        payload = self._payload('settle', branch, contest_id, actor, request_id, expected_revision, terms_digest=record['data']['terms_digest'])
        with _native()[1](self.db):
            prior = self._prior(payload)
            if prior:
                self._verify_settlement(prior['record']); return prior
            old = self.engine.get(branch, _settlement_id(contest_id))
            if old:
                receipt = self._verify_settlement(old)
                return self._reply(old, receipt, True)
            terminal = self._terminal(branch, terms); consents = self._accepted_consents(branch, record, terminal)
            resources = self._resources(branch, terms)
            self._check(resources == record['data']['resource_preimages'], 'contest resource preimages changed after definition')
            role = next(k for k, actor_id in terms['encounter']['participants'].items() if actor_id == terminal['beneficiary'])
            before = {'pool': resources['pool'], 'destination': resources['destinations'][role]}
            self._check(before['pool']['data']['quantity'] >= terms['amount'], 'insufficient contest pool')
            after = {key: {field: deepcopy(image[field]) for field in _ALLOCATION_KEYS} for key, image in before.items()}
            for key, delta in [('pool', -terms['amount']), ('destination', terms['amount'])]:
                after[key]['version'] += 1; after[key]['data']['quantity'] = _quantity(before[key]['data']['quantity']) + delta
            total = _validated(validate_conservation, before, after, terms['amount'])
            proof = {'terminal': terminal, 'consents': consents, 'before': before, 'after_allocations': after, 'total': total, 'operation': payload}
            data = {'terms': record['id'], 'terms_digest': record['data']['terms_digest'], 'beneficiary': terminal['beneficiary'], 'amount': terms['amount'], 'unit': terms['unit'], 'pool': before['pool']['id'], 'destination': before['destination']['id'], 'terminal_event': terminal['world_event'], 'proof': proof}
            changes = [{'op': 'patch', 'id': before[key]['id'], 'expected_version': before[key]['version'], 'data': {'quantity': after[key]['data']['quantity']}, 'evidence': deepcopy(TRANSFER_EVIDENCE)} for key in ['pool', 'destination']]
            changes.append(self._create(_settlement_id(contest_id), 'contest_settlement', data, terms['encounter']['participants'].values()))
            receipt = self._apply(payload, changes, [terminal['world_event'], *[x['native_event'] for x in consents.values()]])
            settled = self.engine.get(branch, _settlement_id(contest_id)); self._verify_settlement(settled)
            return self._reply(settled, receipt)

    def _verify_settlement(self, settled):
        _validated(validate_record, settled)
        event, operation, receipt = self._operation(settled, 'settle'); data = settled['data']; proof = data['proof']; branch = settled['branch']
        terms = self.engine.get(branch, data['terms']); self._check(terms is not None, 'settlement terms missing'); _validated(validate_record, terms)
        self._verify_terms(terms); self._caller(terms['data']['contract'], operation['actor'], None)
        self._check(set(settled['audience']) == set(terms['audience']), 'settlement audience differs from actual entrants')
        self._check(settled['id'] == _settlement_id(terms['data']['contract']['contest_id']) and data['terms_digest'] == terms['data']['terms_digest'] and operation == proof['operation'], 'settlement contest identity mismatch')
        terminal = self._terminal(branch, terms['data']['contract'])
        self._check(operation['contest_id'] == terms['data']['contract']['contest_id'] and operation['terms_digest'] == terms['data']['terms_digest'] and event['revision'] > terminal['world_revision'] and settled['version'] == 1 and self._historical_record(event['id'], settled['id'])[0] is None, 'settlement operation order/identity mismatch')
        self._check(terminal == proof['terminal'] and data['beneficiary'] == terminal['beneficiary'] and data['terminal_event'] == terminal['world_event'], 'settlement terminal provenance mismatch')
        self._check(self._accepted_consents(branch, terms, terminal) == proof['consents'], 'settlement genuine consent provenance mismatch')
        self._check(data['amount'] == terms['data']['contract']['amount'] and data['unit'] == terms['data']['contract']['unit'], 'settlement amount/unit differs from terms')
        self._check(set(proof['before']) == {'pool', 'destination'} and data['pool'] == proof['before']['pool']['id'] and data['destination'] == proof['before']['destination']['id'], 'settlement resource identity mismatch')
        role = next(k for k, entrant in terms['data']['contract']['encounter']['participants'].items() if entrant == data['beneficiary'])
        pins = terms['data']['resource_preimages']
        self._check(proof['before'] == {'pool': pins['pool'], 'destination': pins['destinations'][role]}, 'settlement before images differ from pinned native resources')
        for key in ['pool', 'destination']:
            before, actual_after = self._historical_record(event['id'], proof['before'][key]['id'])
            self._check(before == proof['before'][key], 'historical transfer before image mismatch')
            expected = dict(deepcopy(before), **deepcopy(proof['after_allocations'][key]))
            expected.update(updated_event=event['id'], evidence=deepcopy(TRANSFER_EVIDENCE))
            self._check(actual_after == expected, 'complete historical transfer postimage mismatch')
        changes = list(self.db.execute('SELECT record_id FROM changes WHERE event_id=?', (event['id'],)))
        self._check({r[0] for r in changes} == {data['pool'], data['destination'], settled['id']} and len(changes) == 3, 'settlement event has unrelated or missing changes')
        self._check(set(json.loads(event['causes_json'])) == {terminal['world_event'], *[x['native_event'] for x in proof['consents'].values()]}, 'settlement native causes mismatch')
        return receipt

    def inspect(self, branch, contest_id, viewer=None):
        record = self._visible(branch, contest_id, viewer); terms = record['data']['contract']
        self._check(viewer is None or viewer in terms['encounter']['participants'].values(), 'contest unavailable')
        settled = self.engine.get(branch, _settlement_id(contest_id))
        consents = {actor: self.engine.get(branch, _consent_id(contest_id, actor)) for actor in terms['encounter']['participants'].values()}
        state = 'settled' if settled else 'declined' if any(x is not None and x['data']['choice'] in ('declined', 'withdrawn') for x in consents.values()) else 'unresolved'
        self._verify_terms(record)
        references = {'terms': self._reply(record, self._event(branch, record['updated_event'])[2])['reference'], 'consents': {}}
        for actor, consent in consents.items():
            if consent:
                _, receipt = self._verify_consent(consent, record)
                references['consents'][actor] = self._reply(consent, receipt)['reference']
        result = {'kind': 'contest', 'state': state, 'terms': deepcopy(record), 'consents': deepcopy(consents), 'references': references, 'settlement': None, 'scope': BOUNDARY}
        if settled: result['settlement'] = self._reply(settled, self._verify_settlement(settled), True)
        return result


def schema_objects(source):
    """Parse this fixed migration's complete DDL without opening SQLite."""
    import sqlite3
    statement = ''; result = {}
    for line in source.splitlines(keepends=True):
        if line.lstrip().startswith('--'): continue
        statement += line
        if sqlite3.complete_statement(statement):
            match = re.match(r'\s*CREATE\s+(?:UNIQUE\s+)?(TABLE|TRIGGER|INDEX)\s+"?(\w+)"?\b', statement, re.I)
            _ensure(match is not None, 'contest migration must contain only explicit DDL')
            key = (match[1].lower(), match[2]); _ensure(key not in result, 'duplicate contest DDL object')
            result[key] = ' '.join(statement.strip().rstrip(';').split()); statement = ''
    _ensure(not statement.strip(), 'incomplete contest migration source')
    return result


def classify_optional_layout(objects, expected, *, nonempty=(), facts=False, history=False, marker=False, checksum=False, registry=False):
    """Pure authoritative optional layout model; no DB or installation effects.

    Auto-indexes implied by exact table DDL are validated/removed by the native
    collector. Everything else related to these domains must match exactly.
    """
    _ensure(type(objects) is dict and type(expected) is dict, 'invalid optional schema catalog')
    _ensure(all(type(value) is bool for value in (facts, history, marker, checksum, registry)), 'strict optional state flags required')
    if marker or checksum:
        _ensure(marker and checksum and registry and objects == expected, 'incomplete or mismatched installed contest interface')
        return 'installed'
    _ensure(not facts and not history and not registry, 'unmarked contest facts/history/registry cannot be adopted')
    _ensure(not nonempty, 'unmarked contest projections must be empty')
    if not objects:
        return 'absent'
    pristine = {key: value for key, value in expected.items() if key[0] == 'table'}
    _ensure({key[1] for key in pristine} == set(DOMAINS) and objects == pristine, 'partial/mismatched/extra unmarked contest schema')
    return 'pristine'


def _related_schema_objects(db):
    result = {}; implicit = set()
    related = re.compile(r'\b(?:' + '|'.join(re.escape(x) for x in (*DOMAINS, 'contest_interface', 'contest-operation')) + r')\b', re.IGNORECASE)
    for row in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master'):
        kind, name, table, sql = tuple(row)
        if kind == 'index' and sql is None and table in DOMAINS and name == 'sqlite_autoindex_' + table + '_1':
            implicit.add(table); continue
        if name.casefold().startswith('contest_') or table in DOMAINS or sql is not None and related.search(sql):
            result[(kind, name)] = ' '.join(sql.strip().rstrip(';').split()) if sql is not None else None
    tables = {name for kind, name in result if kind == 'table' and name in DOMAINS}
    _native()[0](implicit == tables, 'contest implicit primary-key index mismatch')
    return result


def _installation_state(engine):
    """One native collector/validator shared by global verify, APIs, installer."""
    from .resources import schema_path
    db = engine.db
    marker = db.execute("SELECT version FROM engine_versions WHERE component='contest_interface'").fetchone()
    checksum = db.execute('SELECT checksum,predecessor,script_name,engine_min FROM migration_checks WHERE version=35').fetchone()
    source = schema_path('migration_035.sql').read_bytes()
    expected = _validated(schema_objects, source.decode('utf-8'))
    objects = _related_schema_objects(db)
    present = {name for kind, name in objects if kind == 'table' and name in DOMAINS}
    nonempty = tuple(name for name in sorted(present) if db.execute('SELECT 1 FROM "' + name + '" LIMIT 1').fetchone())
    facts = bool(db.execute("SELECT 1 FROM records WHERE domain IN ('contest_terms','contest_consent','contest_settlement') LIMIT 1").fetchone())
    history = bool(db.execute("SELECT 1 FROM events WHERE request_id GLOB 'contest-operation:*' OR json_extract(command_json,'$.judgment.contest_operation') IS NOT NULL LIMIT 1").fetchone()
        or db.execute("SELECT 1 FROM changes WHERE json_extract(after_json,'$.domain') IN ('contest_terms','contest_consent','contest_settlement') OR json_extract(before_json,'$.domain') IN ('contest_terms','contest_consent','contest_settlement') LIMIT 1").fetchone()
        or db.execute("SELECT 1 FROM snapshots s,json_tree(s.state_json) j WHERE j.key='domain' AND j.value IN ('contest_terms','contest_consent','contest_settlement') LIMIT 1").fetchone())
    registry = bool(db.execute("SELECT 1 FROM registry_entries WHERE stable_id GLOB 'contest_*' OR stable_id='migration_035.sql' OR locator GLOB 'kageyoni/contests.py:*' OR json_extract(compatibility_json,'$.contest_interface') IS NOT NULL LIMIT 1").fetchone())
    state = _validated(classify_optional_layout, objects, expected, nonempty=nonempty, facts=facts, history=history, marker=bool(marker), checksum=bool(checksum), registry=registry)
    if state != 'installed': return state
    _native()[0](marker[0] == INTERFACE and checksum[0] == hashlib.sha256(source).hexdigest() and tuple(checksum)[1:] == (34, 'migration_035.sql', '4'), 'contest migration/interface metadata mismatch')
    from . import model
    _native()[0](all(model.DOMAINS.get(k) == v and model.REQUIRED.get(k) == REQUIRED[k] for k, v in DOMAINS.items()), 'root contest model binding missing')
    for domain in DOMAINS:
        entry = db.execute("SELECT status,locator,compatibility_json FROM registry_entries WHERE kind='domain' AND stable_id=? AND version='1'", (domain,)).fetchone()
        _native()[0](entry is not None and entry['status'] == 'verified' and entry['locator'] == 'kageyoni/contests.py:DOMAINS[' + repr(domain) + ']' and json.loads(entry['compatibility_json']) == {'contest_interface': INTERFACE}, 'contest registry binding mismatch')
    # Projection FKs prove record identity, not its declared domain. Validate
    # both directions before treating the installed interface as usable.
    for domain in DOMAINS:
        require = _native()[0]
        require(not db.execute('SELECT 1 FROM "' + domain + '" p LEFT JOIN records r ON r.branch=p.branch AND r.id=p.id WHERE r.domain IS NULL OR r.domain<>? LIMIT 1', (domain,)).fetchone(), 'contest projection record domain mismatch')
        require(not db.execute('SELECT 1 FROM records r LEFT JOIN "' + domain + '" p ON p.branch=r.branch AND p.id=r.id WHERE r.domain=? AND p.id IS NULL LIMIT 1', (domain,)).fetchone(), 'contest record projection missing')
    return state


def _interface(engine):
    # Strict APIs validate every optional state but never treat pristine as installed.
    return _installation_state(engine) == 'installed'


def _maintenance_token(engine):
    return (engine.db.total_changes, engine.db.execute('PRAGMA data_version').fetchone()[0],
            tuple(tuple(row) for row in engine.db.execute('SELECT id,revision,parent,fork_revision FROM branches ORDER BY id')),
            tuple(tuple(row) for row in engine.db.execute('SELECT version,checksum FROM migration_checks ORDER BY version')))


def _install_contests_atomic(engine, source, objects, initial_state, token):
    """Private DDL step, reached only after public checked maintenance preflight."""
    from .resources import schema_path
    require, UnitOfWork = _native()
    with UnitOfWork(engine.db):
        require(_maintenance_token(engine) == token, 'world changed during contest maintenance preflight/backup')
        require(schema_path('migration_035.sql').read_text() == source, 'contest migration source changed during maintenance')
        require(_installation_state(engine) == initial_state and initial_state in ('absent', 'pristine'), 'contest installation state changed during maintenance')
        for (kind, name), statement in objects.items():
            if kind == 'table' and initial_state == 'pristine': continue
            engine.db.execute(statement)
        engine.db.execute('INSERT INTO engine_versions(component,version) VALUES(?,?)', ('contest_interface', INTERFACE))
        engine.db.execute('INSERT INTO migration_checks(version,predecessor,script_name,checksum,engine_min) VALUES(?,?,?,?,?)', (35, 34, 'migration_035.sql', hashlib.sha256(source.encode()).hexdigest(), '4'))
        for domain in DOMAINS:
            engine.register_component('domain', domain, '1', 'kageyoni/contests.py:DOMAINS[' + repr(domain) + ']', status='verified', readers=['Contests.inspect', 'Engine.get'], writers=['Contests.define', 'Contests.consent', 'Contests.settle'], compatibility={'contest_interface': INTERFACE}, declared_by='explicit-contest-installer')
        result = verify_contests(engine)
        require(engine.validate_registry()['ok'], 'post-install contest direct registry validation failed')
        require(engine.verify()['ok'], 'post-install contest global verification failed')
        return result


def install_contests(engine):
    """Public safe owner maintenance: verify, unique checked backup, atomic035.

    Never called by open. The existing Engine.backup producer closes and twice
    reopens its separately staged copy read-only through actual Engine.verify.
    Backup exceptions propagate; its published predecessor is never cleaned up
    by this installer, including when the later atomic DDL step fails.
    """
    from pathlib import Path
    import stat
    from uuid import uuid4
    from . import model
    from .resources import schema_path
    require, _ = _native(); db = engine.db
    require(not db.in_transaction, 'finish transaction before contest installation')
    require(not db.execute('PRAGMA query_only').fetchone()[0], 'read-only contest installation refused')
    require(all(model.DOMAINS.get(k) == v and model.REQUIRED.get(k) == REQUIRED[k] for k, v in DOMAINS.items()), 'root must bind contest DOMAINS/REQUIRED before explicit install')
    state = _installation_state(engine)
    if state == 'installed':
        require(engine.verify()['ok'], 'installed contest global verification failed')
        require(engine.validate_registry()['ok'], 'installed contest registry verification failed')
        return verify_contests(engine)
    require(db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0] == 34, 'contest migration predecessor mismatch')
    token = _maintenance_token(engine)
    verification = engine.verify(); require(verification['ok'], 'pre-install contest global verification failed')
    registry = engine.validate_registry(); require(registry['ok'], 'pre-install contest direct registry validation failed')
    from .workspaces.worker_custody import verify_worker_custody
    require(verify_worker_custody(engine)['installed'], 'actual native034 predecessor required')
    require(_maintenance_token(engine) == token, 'world changed during contest verification')
    require(str(engine.path) != ':memory:', 'contest installation requires a file-backed predecessor for checked backup')
    destination = Path(engine.path).with_name(Path(engine.path).name + '.pre-v35-' + uuid4().hex + '.bak')
    try:
        backup = engine.backup(destination)
        require(Path(backup).resolve() == destination.resolve() and stat.S_ISREG(destination.lstat().st_mode), 'contest checked backup publication mismatch')
        backup_proof = {'path': str(destination), 'bytes': destination.stat().st_size, 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(), 'producer': 'Engine.backup -> checkpoint.checked_backup; two fresh read-only Engine.verify passes'}
        require(_maintenance_token(engine) == token, 'world changed during contest checked backup')
        source = schema_path('migration_035.sql').read_text(); objects = _validated(schema_objects, source)
        result = _install_contests_atomic(engine, source, objects, state, token)
    except Exception as error:
        error.add_note('Requested unique pre-v35 checked backup path: ' + str(destination) + '; this installer deletes no published backup. Backup failure prevents entry to the DDL step.')
        raise
    result['maintenance'] = {'checked_backup': backup_proof, 'preflight_verification': verification, 'preflight_registry': registry}
    return result


def verify_contests(engine, *, allow_pristine=False):
    """Root global hook uses allow_pristine=True; strict default never installs.

    Every absent/pristine/installed path uses the same authoritative collector.
    Partial, nonempty, advertised or extra optional schemas always refuse.
    """
    _native()[0](type(allow_pristine) is bool, 'strict allow_pristine flag required')
    state = _installation_state(engine)
    _native()[0](state != 'pristine' or allow_pristine, 'contest interface not installed')
    if state != 'installed': return {'installed': False, 'state': state}
    require, _ = _native()
    from .workspaces.world import verify_encounters
    verify_encounters(engine)
    require(not engine.db.execute('PRAGMA foreign_key_check').fetchall(), 'contest foreign key check failed')
    require(engine.validate_registry()['ok'], 'contest native registry validation failed')
    service = Contests(engine); counts = {domain: 0 for domain in DOMAINS}
    rows = list(engine.db.execute("SELECT branch,id FROM records WHERE domain IN ('contest_terms','contest_consent','contest_settlement') ORDER BY branch,id"))
    for row in rows:
        record = engine.get(row['branch'], row['id']); _validated(validate_record, record); counts[record['domain']] += 1
        if record['domain'] == 'contest_terms':
            service._verify_terms(record)
        elif record['domain'] == 'contest_consent':
            terms = engine.get(record['branch'], record['data']['terms']); require(terms is not None and terms['domain'] == 'contest_terms', 'contest consent terms missing')
            service._verify_terms(terms); service._verify_consent(record, terms)
        else:
            service._verify_settlement(record)
    return {'installed': True, 'interface': INTERFACE, 'counts': counts}
