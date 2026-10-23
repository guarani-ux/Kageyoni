"""Metadata-only correspondence for the NEW direct source profile.

No ordinary permission check or artifact body read occurs in this module.
Callers own Registry/C2 authorization BEFORE this diagnostic and one coherent
UnitOfWork snapshot through any later body fetch. This is not a derivation
collector, host-capability verifier or a substitute for Engine.verify.
"""
from copy import deepcopy

from .source_authority_schema import _require, authority_id, validate_transition
from .source_authority_installation import (
    DOMAIN, PREFIX, OP_PREFIX, installation_state, strict_json, structured_signal, projection_signal,
)
from .source_authority_operations import (
    canonical, digest, source_metadata_hash, validate_command, validate_record,
)

_AUX = ('properties', 'facet_changes', 'processes', 'consequence_runs',
        'resolution', 'observations', 'process_runs', 'profiles', 'entity_links',
        'classification_claims', 'choice', 'will_attempt')


def _signal_record(record):
    return (type(record) is dict and (
        type(record.get('id')) is str and record['id'].casefold().startswith(PREFIX)
        or type(record.get('domain')) is str and record['domain'].casefold().startswith(DOMAIN)
        or structured_signal(record)))


def _record(db, row):
    """Decode only the controlled projection; never join away orphan rows."""
    value = dict(row)
    value['audience'] = strict_json(value.pop('audience_json'))
    value['evidence'] = strict_json(value.pop('evidence_json'))
    projection = db.execute('SELECT contract FROM source_authority WHERE branch=? AND id=?',
                            (value['branch'], value['id'])).fetchone()
    _require(projection is not None, 'controlled record projection missing')
    value['data'] = {'contract': strict_json(projection[0])}
    return validate_record(value)


def _event(db, row, changes):
    event = dict(row)
    command = strict_json(event['command_json'])
    operation = validate_command(command)
    image = operation['creation']
    rid = authority_id(image['workspace_id'], image['source_id'])
    _require(len(changes) == 1, 'source authority operation requires exactly one native change')
    change = dict(changes[0])
    _require(change['ordinal'] == 0 and type(change['ordinal']) is int
             and change['record_id'] == rid, 'source authority native change identity mismatch')
    before = strict_json(change['before_json']) if change['before_json'] is not None else None
    after = validate_record(strict_json(change['after_json']))
    _require(after['updated_event'] == event['id'] and after['branch'] == image['branch'],
             'source authority change event/branch mismatch')
    capture = operation['operation'] == 'capture'
    if capture:
        _require(before is None and canonical(after['data']['contract']) == canonical(image),
                 'source authority capture before/after mismatch')
    else:
        before = validate_record(before)
        _require(canonical(before['data']['contract']) == canonical(image),
                 'source authority withdrawal creation identity mismatch')
        validate_transition(before['data']['contract'], after['data']['contract'])
    authored = command['changes'][0]
    for field in ('id', 'domain', 'data', 'status', 'visibility', 'audience', 'evidence'):
        _require(canonical(after[field]) == canonical(authored[field]),
                 'source authority command/change correspondence mismatch')
    _require(event['branch'] == command['branch'] and event['request_id'] == command['request_id']
             and event['kind'] == command['kind'] and event['actor'] == command['actor']
             and event['narrative'] == command['narrative'] and event['clock_id'] is None
             and event['tick'] is None and strict_json(event['causes_json']) == []
             and type(event['revision']) is int
             and event['revision'] == operation['expected_revision'] + 1
             and event['payload_hash'] == digest(command),
             'source authority native event metadata mismatch')
    expected_hash = digest({'previous': event['prev_hash'], 'payload_hash': event['payload_hash'],
                            'changes': [[before, after]]})
    _require(event['event_hash'] == expected_hash, 'source authority native event hash mismatch')
    prior = db.execute('SELECT event_hash FROM events WHERE branch=? AND revision=?',
                        (event['branch'], event['revision'] - 1)).fetchone()
    _require(event['prev_hash'] == (prior[0] if prior is not None else '')
             and (event['revision'] == 1 or prior is not None),
             'source authority native predecessor event missing or mismatched')
    head = db.execute('SELECT revision FROM branches WHERE id=?', (event['branch'],)).fetchone()
    _require(head is not None and head[0] >= event['revision'],
             'source authority event beyond actual branch head')
    receipt = strict_json(event['receipt_json'])
    expected = dict(event_id=event['id'], branch=event['branch'], revision=event['revision'],
                    request_id=event['request_id'], event_hash=expected_hash, changed=[rid],
                    changed_properties=[], changed_processes=[], changed_profiles=[], changed_links=[],
                    changed_classifications=[], triggered_processes=[], will_attempt_id=None,
                    replayed=False, committed=True,
                    aux_digest=digest({key: command.get(key) for key in _AUX}))
    _require(canonical(receipt) == canonical(expected), 'source authority native receipt mismatch')
    return {'operation': operation, 'before': before, 'after': after,
            'event_id': event['id'], 'revision': event['revision']}


def _source_metadata(db, image):
    rows = list(db.execute('SELECT workspace_id,source_id,revision,request_id,payload_hash,artifact_id,metadata_json '
                           'FROM document_sources WHERE workspace_id=? AND source_id=? ORDER BY revision',
                           (image['workspace_id'], image['source_id'])))
    _require(len(rows) == 1, 'controlled source family must retain exactly revision1')
    row = dict(rows[0])
    _require(source_metadata_hash(row) == image['source_metadata_hash']
             and row['payload_hash'] == image['source_payload_hash']
             and row['artifact_id'] == image['artifact_pin']['id'],
             'controlled source row metadata/payload/artifact mismatch')
    workspace = db.execute('SELECT branch FROM operational_workspaces WHERE workspace_id=?',
                            (row['workspace_id'],)).fetchone()
    _require(workspace is not None and workspace[0] == image['branch'],
             'controlled source actual workspace branch mismatch')
    recipient = db.execute('SELECT domain FROM records WHERE branch=? AND id=?',
                            (image['branch'], image['recipient'])).fetchone()
    _require(recipient is not None and recipient[0] == 'character',
             'controlled source native recipient character missing')
    artifact = db.execute('SELECT artifact_id,workspace_id,viewer,request_id,payload_hash,digest,media_type,size '
                           'FROM artifacts WHERE artifact_id=?', (row['artifact_id'],)).fetchone()
    _require(artifact is not None, 'controlled source artifact metadata missing')
    artifact = dict(artifact)
    _require(artifact['workspace_id'] == row['workspace_id']
             and artifact['viewer'] == image['recipient']
             and artifact['request_id'] == row['request_id'] + ':source'
             and artifact['digest'] == image['artifact_pin']['digest']
             and artifact['media_type'] == 'text/plain; charset=utf-8'
             and type(artifact['size']) is int and 0 < artifact['size'] <= 4000000,
             'controlled source artifact scope/pin mismatch')
    expected = dict(workspace_id=row['workspace_id'], viewer=None,
                    media_type=artifact['media_type'], digest=artifact['digest'],
                    size=artifact['size'], recipient=image['recipient'])
    _require(artifact['payload_hash'] == digest(expected), 'controlled source artifact creation hash mismatch')
    aliases = list(db.execute('SELECT workspace_id,source_id,revision FROM document_sources WHERE artifact_id=?',
                              (row['artifact_id'],)))
    _require([tuple(r) for r in aliases] == [(row['workspace_id'], row['source_id'], 1)],
             'controlled source artifact reused by another source family')
    return row, artifact


def collect_source_authority_metadata(engine, *, allow_pristine=True):
    """Resolve complete direct-profile current/history metadata before bytes.

    Caller must retain the same snapshot through authorization and byte read.
    Returned facts are correspondence, not proof of a human choice or hostile
    in-process isolation. Unsupported lineage routes still need explicit refusal.
    """
    db = engine.db
    _require(db.in_transaction, 'source authority metadata requires existing coherent UnitOfWork')
    _require(type(allow_pristine) is bool, 'strict pristine policy required')
    state = installation_state(engine)
    _require(state != 'pristine' or allow_pristine, 'source authority projection is pristine, not installed')
    if state != 'installed':
        return {'installed': False, 'state': state, 'families': {}, 'artifacts': {}, 'histories': {}}
    current = {}
    for row in db.execute('SELECT * FROM records'):
        raw = dict(row)
        signal = (raw['domain'].casefold().startswith(DOMAIN)
                  or raw['id'].casefold().startswith(PREFIX)
                  or structured_signal(strict_json(raw['audience_json']))
                  or structured_signal(strict_json(raw['evidence_json']))
                  or projection_signal(db, row))
        if signal:
            record = _record(db, row)
            current[record['branch'], record['id']] = record
    # Scan all changes without an event join: orphan/misbound signals refuse.
    changes = {}
    signaled_events = set()
    for row in db.execute('SELECT * FROM changes ORDER BY event_id,ordinal'):
        change = dict(row)
        images = [strict_json(change[key]) for key in ('before_json', 'after_json')
                  if change[key] is not None]
        changes.setdefault(change['event_id'], []).append(change)
        if (change['record_id'].casefold().startswith(PREFIX)
                or any(_signal_record(image) for image in images)):
            signaled_events.add(change['event_id'])
    history = {}
    known_events = set()
    for row in db.execute('SELECT * FROM events ORDER BY branch,revision'):
        event = dict(row)
        command = strict_json(event['command_json'])
        receipt = strict_json(event['receipt_json'])
        signal = (event['id'] in signaled_events
                  or event['request_id'].casefold().startswith(OP_PREFIX)
                  or event['kind'].casefold().startswith(DOMAIN)
                  or structured_signal(command) or structured_signal(receipt))
        if not signal:
            continue
        fact = _event(db, row, changes.get(event['id'], []))
        after = fact['after']
        key = after['branch'], after['id']
        chain = history.setdefault(key, [])
        _require(len(chain) < 2 and ((not chain and fact['before'] is None)
                 or (len(chain) == 1 and canonical(chain[-1]['after']) == canonical(fact['before']))),
                 'source authority native history missing, reordered or repeated')
        chain.append(fact)
        known_events.add(event['id'])
    _require(signaled_events <= known_events, 'orphan controlled change/event correspondence')
    _require(set(history) == set(current), 'source authority current/history identity sets differ')
    families, artifacts = {}, {}
    for key, record in current.items():
        chain = history[key]
        _require(canonical(record) == canonical(chain[-1]['after']),
                 'source authority current record differs from native history')
        creation = chain[0]['operation']['creation']
        row, artifact = _source_metadata(db, creation)
        family = (creation['workspace_id'], creation['source_id'])
        _require(family not in families and artifact['artifact_id'] not in artifacts,
                 'controlled source family/artifact authority ambiguous')
        item = dict(image=deepcopy(record['data']['contract']), creation=deepcopy(creation),
                    source=row, artifact=artifact, record=record)
        families[family] = item
        artifacts[artifact['artifact_id']] = item
    for row in db.execute('SELECT id,branch,revision,state_json,sha256 FROM snapshots'):
        snapshot = dict(row)
        payload = strict_json(snapshot['state_json'])
        _require(digest(payload) == snapshot['sha256'], 'snapshot hash mismatch during control resolution')
        records = payload if type(payload) is list else payload.get('records') if type(payload) is dict else None
        _require(type(records) is list, 'native snapshot records missing')
        selected = {}
        for record in records:
            _require(type(record) is dict, 'native snapshot record image required')
            if _signal_record(record):
                record = validate_record(record)
                _require(record['branch'] == snapshot['branch'] and record['id'] not in selected,
                         'source authority snapshot branch/duplicate mismatch')
                selected[record['id']] = record
        expected = {}
        for (branch, rid), chain in history.items():
            if branch == snapshot['branch']:
                prior = [fact for fact in chain if fact['revision'] <= snapshot['revision']]
                if prior:
                    expected[rid] = prior[-1]['after']
        _require(canonical(selected) == canonical(expected),
                 'source authority snapshot does not match native as-of history')
        if type(payload) is dict:
            _require(not structured_signal({k: v for k, v in payload.items() if k != 'records'}),
                     'unsupported source authority snapshot auxiliary signal')
    return {'installed': True, 'state': state, 'families': families,
            'artifacts': artifacts, 'histories': history}


def resolve_source(engine, workspace_id, source_id):
    """Resolve ACTUAL stored identity before strict controlled-ID validation.

    Preserve legacy SQLite identity/alias and absent-source behavior; an absent
    row does not bypass the complete global metadata classification.
    """
    resolved = collect_source_authority_metadata(engine)
    row = engine.db.execute('SELECT workspace_id,source_id FROM document_sources '
                            'WHERE workspace_id=? AND source_id=? ORDER BY revision DESC LIMIT 1',
                            (workspace_id, source_id)).fetchone()
    if row is None:
        return None
    return resolved['families'].get((row[0], row[1]))


def resolve_artifact(engine, artifact_id):
    resolved = collect_source_authority_metadata(engine)
    row = engine.db.execute('SELECT artifact_id FROM artifacts WHERE artifact_id=?',
                            (artifact_id,)).fetchone()
    return None if row is None else resolved['artifacts'].get(row[0])
