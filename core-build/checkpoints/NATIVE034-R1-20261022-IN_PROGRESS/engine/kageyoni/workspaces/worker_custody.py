"""Distinct native identity-absence receipts for NEW registered attempts only.

Trusted-owner supplied facts follow the observe_exit trust boundary. Neither
provider tags nor public hashes authenticate a caller or prove OS execution.
No procfs reads, process control, fabricated exit status, output acceptance or
budget refund occurs here. Product wire admission remains root-owned.
"""
import hashlib
import json
import math
import re
import sqlite3

from ..engine import require, encoded
from ..persistence.unit_of_work import UnitOfWork
from ..resources import schema_path
from .resource_profiles import ResourceProfiles
from .worker_liveness import WorkerLiveness, POLICY, POLICY_DIGEST, DISPOSITIONS, _fence
from .custody_schema import (CustodySchemaError, PROVIDER, validate_registration,
                             validate_absence)

_TABLES = {'activity_worker_registrations', 'activity_worker_absences'}
_CURRENT_TERMINAL_STATES = {'queued', 'paused', 'cancelled', 'failed', 'reconciling'}
_REG_RECEIPT_KEYS = {'kind', 'job_id', 'workspace_id', 'fence', 'registered_at',
    'registration_digest', 'provider', 'owner_wall_before', 'owner_wall_after'}
_ABS_RECEIPT_KEYS = {'kind', 'job_id', 'workspace_id', 'fence', 'registration_digest',
    'observation', 'observed_at', 'disposition', 'state', 'returncode', 'provider',
    'owner_wall_before', 'owner_wall_after', 'clock_rollback', 'time_status', 'policy_digest'}


def _time(now):
    require(type(now) in (int, float) and math.isfinite(now), 'invalid custody owner time')
    return now


def _schema(function, *values):
    try:
        return function(*values)
    except (CustodySchemaError, TypeError, ValueError, OverflowError) as error:
        require(False, 'invalid custody schema: ' + str(error))


def _json(raw):
    require(type(raw) is str and len(raw.encode('utf-8')) <= 131072, 'invalid custody stored JSON')
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'duplicate custody stored JSON key')
            value[key] = item
        return value
    def bad(_value):
        require(False, 'nonfinite custody stored JSON')
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
        require(encoded(value) == raw, 'noncanonical custody stored JSON')
        return value
    except (TypeError, ValueError, RecursionError) as error:
        require(False, 'malformed custody stored JSON: ' + str(error))


def _object_statements(text):
    statement = ''; result = {}
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith('--'):
            continue
        statement += line
        if sqlite3.complete_statement(statement):
            match = re.match(r'\s*CREATE\s+(TABLE|TRIGGER|INDEX)\s+(\w+)\b', statement, re.I)
            if match:
                result[(match[1].lower(), match[2])] = ' '.join(statement.strip().rstrip(';').split())
            statement = ''
    require(not statement.strip(), 'incomplete custody migration source')
    return result


def _interface(engine):
    db = engine.db
    present = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} & _TABLES
    interface = db.execute("SELECT version FROM engine_versions WHERE component='worker_custody_interface'").fetchone()
    migration = db.execute('SELECT checksum FROM migration_checks WHERE version=34').fetchone()
    if not present and not interface and not migration:
        return False
    require(present == _TABLES and interface and interface[0] == '1' and migration,
            'incomplete worker custody interface')
    source = schema_path('migration_034.sql').read_bytes()
    require(migration[0] == hashlib.sha256(source).hexdigest(), 'worker custody migration checksum mismatch')
    for (kind, name), expected in _object_statements(source.decode('utf-8')).items():
        actual = db.execute('SELECT sql FROM sqlite_master WHERE type=? AND name=?', (kind, name)).fetchone()
        require(actual and ' '.join(actual[0].strip().rstrip(';').split()) == expected,
                'worker custody schema object mismatch: ' + name)
    return True


def _current_queue(db, workspace_id, job_id, fence):
    row = db.execute('SELECT * FROM activity_queue WHERE workspace_id=? AND job_id=?', (workspace_id, job_id)).fetchone()
    require(row and (row['owner_epoch'], row['generation'], row['lease_token']) ==
            (fence['epoch'], fence['generation'], fence['token']), 'stale worker custody fence')
    return dict(row)


def _known_exit(db, attempt):
    return attempt['exit_json'] is not None or db.execute(
        'SELECT 1 FROM activity_worker_exits WHERE job_id=? AND owner_epoch=? AND generation=?',
        (attempt['job_id'], attempt['owner_epoch'], attempt['generation'])).fetchone() is not None


def _registration_record(engine, raw):
    db = engine.db; row = dict(raw)
    fence = {'epoch': row['owner_epoch'], 'generation': row['generation'], 'token': row['lease_token']}; _fence(fence)
    record = _schema(validate_registration, _json(row['registration_json']))
    require(row['registration_digest'] == record['registration_digest'], 'worker registration digest mismatch')
    attempt = WorkerLiveness(engine, row['workspace_id']).row(row['job_id'], fence)
    require(attempt['policy_json'] == encoded(POLICY) and attempt['policy_digest'] == POLICY_DIGEST,
            'worker custody liveness policy mismatch')
    for name in ('claimed_at','execution_until','lease_until'):
        _time(attempt[name])
    require(attempt['process_json'] is not None and _json(attempt['process_json']) == record['process'],
            'worker registration historical process mismatch')
    receipt = _json(row['receipt_json'])
    require(type(receipt) is dict and set(receipt) == _REG_RECEIPT_KEYS and
            receipt['kind'] == 'worker_process_registered' and receipt['provider'] == PROVIDER and
            receipt['job_id'] == row['job_id'] and receipt['workspace_id'] == row['workspace_id'] and
            receipt['fence'] == fence and receipt['registration_digest'] == record['registration_digest'] and
            receipt['registered_at'] == row['registered_at'], 'invalid worker registration receipt')
    _fence(receipt['fence'])
    for key in ('registered_at', 'owner_wall_before', 'owner_wall_after'):
        _time(receipt[key])
    require(receipt['owner_wall_before'] >= attempt['claimed_at'] and
            receipt['registered_at'] >= receipt['owner_wall_before'] and
            receipt['owner_wall_after'] == receipt['registered_at'] and
            attempt['claimed_at'] <= receipt['registered_at'] < attempt['execution_until'],
            'worker registration clock correspondence mismatch')
    owner = db.execute('SELECT last_wall FROM activity_queue_owners WHERE workspace_id=?', (row['workspace_id'],)).fetchone()
    require(owner and owner[0] >= receipt['owner_wall_after'], 'worker registration owner highwater mismatch')
    return row, record, receipt, attempt


def _stop_summary(db, attempt, fence):
    """Check links needed by absence; full033 stop-chain verification stays033."""
    require(attempt['stop_requested_at'] is not None and attempt['stop_disposition'] in DISPOSITIONS,
            'worker custody stop intent missing')
    stops = list(db.execute('SELECT * FROM activity_worker_stops WHERE job_id=? AND owner_epoch=? AND generation=? ORDER BY ordinal',
                 (attempt['job_id'], fence['epoch'], fence['generation'])))
    require(bool(stops), 'worker custody stop receipt missing')
    first = _json(stops[0]['receipt_json']); last = _json(stops[-1]['receipt_json'])
    required = {'kind','job_id','fence','request_id','observed_at','disposition','owner_wall_after'}
    require(type(first) is dict and type(last) is dict and required <= set(first) and required <= set(last),
            'malformed worker custody stop receipt')
    _fence(first['fence']); _fence(last['fence'])
    _time(first['observed_at']); _time(last['observed_at']); _time(last['owner_wall_after'])
    require(first['kind'] == last['kind'] == 'worker_stop' and
            first['job_id'] == last['job_id'] == attempt['job_id'] and
            first['fence'] == last['fence'] == fence and
            first['request_id'] == attempt['stop_request_id'] == stops[0]['request_id'] and
            first['observed_at'] == attempt['stop_requested_at'] and
            attempt['stop_deadline'] == first['observed_at'] + 5 and
            last['disposition'] == attempt['stop_disposition'], 'worker custody stop correspondence mismatch')
    return last


def _absence_record(engine, registration_row, record, registration_receipt, attempt, raw):
    db = engine.db; row = dict(raw)
    key = (attempt['job_id'], attempt['owner_epoch'], attempt['generation'])
    fence = {'epoch': key[1], 'generation': key[2], 'token': attempt['lease_token']}
    require((row['job_id'], row['owner_epoch'], row['generation'], row['workspace_id'], row['lease_token']) ==
            (key[0], key[1], key[2], attempt['workspace_id'], attempt['lease_token']),
            'worker absence attempt correspondence mismatch')
    require(not _known_exit(db, attempt), 'worker absence conflicts with known exit')
    observation = _schema(validate_absence, _json(row['observation_json']), record)
    receipt = _json(row['receipt_json'])
    stop = _stop_summary(db, attempt, fence)
    disposition = attempt['stop_disposition']
    selected = 'paused' if disposition == 'pause' else 'cancelled' if disposition == 'cancel' else 'reconciling'
    require(type(receipt) is dict and set(receipt) == _ABS_RECEIPT_KEYS and
            receipt['kind'] == 'worker_identity_absent' and receipt['provider'] == PROVIDER and
            receipt['job_id'] == key[0] and receipt['workspace_id'] == attempt['workspace_id'] and
            receipt['fence'] == fence and receipt['registration_digest'] == record['registration_digest'] and
            receipt['observation'] == observation and receipt['returncode'] is None and
            receipt['disposition'] == disposition and receipt['state'] == selected and
            receipt['policy_digest'] == POLICY_DIGEST, 'invalid worker absence receipt')
    _fence(receipt['fence'])
    for name in ('observed_at', 'owner_wall_before', 'owner_wall_after'):
        _time(receipt[name])
    owner = db.execute('SELECT last_wall FROM activity_queue_owners WHERE workspace_id=?', (attempt['workspace_id'],)).fetchone()
    floor = max(receipt['owner_wall_before'], attempt['claimed_at'],
                attempt['last_heartbeat'] if attempt['last_heartbeat'] is not None else attempt['claimed_at'])
    require(type(receipt['clock_rollback']) is bool and
            receipt['owner_wall_before'] >= max(stop['owner_wall_after'], registration_receipt['owner_wall_after']) and
            receipt['owner_wall_after'] == max(receipt['owner_wall_before'], receipt['observed_at']) and
            owner and owner[0] >= receipt['owner_wall_after'] and
            receipt['clock_rollback'] == (receipt['observed_at'] < floor) and
            receipt['time_status'] == ('uncertain' if receipt['clock_rollback'] else 'owner_wall'),
            'worker absence clock correspondence mismatch')
    q = db.execute('SELECT * FROM activity_queue WHERE job_id=?', (key[0],)).fetchone()
    require(q and q['workspace_id'] == attempt['workspace_id'], 'worker custody queue workspace mismatch')
    current = (q['owner_epoch'], q['generation'], q['lease_token']) == (fence['epoch'], fence['generation'], fence['token'])
    if current:
        # Receipt records FIRST selected state. Later explicit controls may
        # change state before the next claim advances the fence, just as033.
        require(q['process_json'] is None and q['state'] in _CURRENT_TERMINAL_STATES,
                'absent worker process still charged or returned')
    return receipt


class WorkerCustody:
    def __init__(self, engine, workspace_id):
        self.engine, self.db, self.workspace_id = engine, engine.db, workspace_id

    def present(self):
        return _interface(self.engine)

    def row(self, job_id, fence):
        _fence(fence); require(self.present(), 'worker custody interface not installed')
        raw = self.db.execute('SELECT * FROM activity_worker_registrations WHERE workspace_id=? AND job_id=? AND owner_epoch=? AND generation=?',
                (self.workspace_id, job_id, fence['epoch'], fence['generation'])).fetchone()
        require(raw and raw['lease_token'] == fence['token'], 'worker custody registration unavailable')
        _registration_record(self.engine, raw)
        return dict(raw)

    def _start_authority(self, job_id, fence, now):
        q = _current_queue(self.db, self.workspace_id, job_id, fence)
        attempt = WorkerLiveness(self.engine, self.workspace_id).row(job_id, fence)
        owner = self.db.execute('SELECT * FROM activity_queue_owners WHERE workspace_id=?', (self.workspace_id,)).fetchone()
        require(q['state'] == 'running' and owner and owner['epoch'] == fence['epoch'] and
                attempt['stop_requested_at'] is None and not _known_exit(self.db, attempt),
                'worker registration unavailable')
        require(not self.db.execute('SELECT 1 FROM activity_worker_absences WHERE job_id=? AND owner_epoch=? AND generation=?',
                (job_id, fence['epoch'], fence['generation'])).fetchone(), 'worker registration already absent')
        require(attempt['process_json'] is not None and q['process_json'] == attempt['process_json'],
                'worker registration process unavailable')
        floor = max(owner['last_wall'], attempt['claimed_at'],
                    attempt['last_heartbeat'] if attempt['last_heartbeat'] is not None else attempt['claimed_at'])
        require(now >= floor and now < attempt['lease_until'] and now < attempt['execution_until'] and
                q['lease_until'] == attempt['lease_until'], 'stale worker registration lease')
        binding = self.db.execute('SELECT active,authority_epoch FROM activity_bindings WHERE binding_id=? AND workspace_id=?',
                                 (q['binding_id'], self.workspace_id)).fetchone()
        require(binding and binding['active'] and binding['authority_epoch'] == q['authority_epoch'], 'worker registration authority changed')
        require(q['profile_digest'] == ResourceProfiles(self.engine, self.workspace_id).get()['digest'], 'worker registration resource profile changed')
        job = self.db.execute('SELECT activity_id,state FROM activity_jobs WHERE job_id=? AND workspace_id=?', (job_id, self.workspace_id)).fetchone()
        require(job and job['state'] == 'waiting', 'worker registration job unavailable')
        aid = job['activity_id']; seen = set()
        while aid:
            require(aid not in seen, 'worker registration parent cycle'); seen.add(aid)
            activity = self.db.execute('SELECT parent_id,state FROM activity_runs WHERE workspace_id=? AND activity_id=?', (self.workspace_id, aid)).fetchone()
            require(activity and activity['state'] not in ('paused', 'cancelled', 'failed', 'finished'), 'worker registration ancestor stopped')
            aid = activity['parent_id']
        return q, attempt, dict(owner)

    def register(self, job_id, fence, registration, now):
        _time(now); _fence(fence); record = _schema(validate_registration, registration)
        require(self.present(), 'worker custody interface not installed')
        with UnitOfWork(self.db):
            q, attempt, owner = self._start_authority(job_id, fence, now)
            require(_json(attempt['process_json']) == record['process'], 'worker registration process mismatch')
            old = self.db.execute('SELECT * FROM activity_worker_registrations WHERE job_id=? AND owner_epoch=? AND generation=?',
                                 (job_id, fence['epoch'], fence['generation'])).fetchone()
            if old:
                self.row(job_id, fence)
                require(old['registration_json'] == encoded(record), 'worker registration identity conflict')
                return _json(old['receipt_json'])
            receipt = {'kind': 'worker_process_registered', 'job_id': job_id, 'workspace_id': self.workspace_id,
                       'fence': dict(fence), 'registered_at': now, 'registration_digest': record['registration_digest'],
                       'provider': PROVIDER, 'owner_wall_before': owner['last_wall'], 'owner_wall_after': now}
            self.db.execute('INSERT INTO activity_worker_registrations VALUES(?,?,?,?,?,?,?,?,?)',
                (job_id, fence['epoch'], fence['generation'], self.workspace_id, fence['token'],
                 encoded(record), record['registration_digest'], now, encoded(receipt)))
            self.db.execute('UPDATE activity_queue_owners SET last_wall=max(last_wall,?) WHERE workspace_id=?', (now, self.workspace_id))
            return receipt

    def observe_absence(self, job_id, fence, observation, now):
        _time(now); _fence(fence); require(self.present(), 'worker custody interface not installed')
        with UnitOfWork(self.db):
            q = _current_queue(self.db, self.workspace_id, job_id, fence)
            registered = self.row(job_id, fence)
            row, record, reg_receipt, attempt = _registration_record(self.engine, registered)
            supplied = _schema(validate_absence, observation, record)
            require(not _known_exit(self.db, attempt), 'worker absence conflicts with known exit')
            old = self.db.execute('SELECT * FROM activity_worker_absences WHERE job_id=? AND owner_epoch=? AND generation=?',
                                 (job_id, fence['epoch'], fence['generation'])).fetchone()
            if old:
                receipt = _absence_record(self.engine, row, record, reg_receipt, attempt, old)
                require(old['observation_json'] == encoded(supplied), 'worker absence observation conflict')
                return receipt
            require(q['state'] == 'reconciling' and q['process_json'] == attempt['process_json'] and
                    attempt['process_json'] is not None, 'worker absence requires current stopped custody')
            _stop_summary(self.db, attempt, fence)
            owner = self.db.execute('SELECT last_wall FROM activity_queue_owners WHERE workspace_id=?', (self.workspace_id,)).fetchone()
            require(owner is not None, 'worker custody owner unavailable')
            floor = max(owner[0], attempt['claimed_at'],
                        attempt['last_heartbeat'] if attempt['last_heartbeat'] is not None else attempt['claimed_at'])
            rollback = now < floor; disposition = attempt['stop_disposition']
            state = 'paused' if disposition == 'pause' else 'cancelled' if disposition == 'cancel' else 'reconciling'
            receipt = {'kind': 'worker_identity_absent', 'job_id': job_id, 'workspace_id': self.workspace_id,
                       'fence': dict(fence), 'registration_digest': record['registration_digest'],
                       'observation': supplied, 'observed_at': now, 'disposition': disposition, 'state': state,
                       'returncode': None, 'provider': PROVIDER, 'clock_rollback': rollback,
                       'time_status': 'uncertain' if rollback else 'owner_wall',
                       'owner_wall_before': owner[0], 'owner_wall_after': max(owner[0], now), 'policy_digest': POLICY_DIGEST}
            self.db.execute('INSERT INTO activity_worker_absences VALUES(?,?,?,?,?,?,?)',
                            (job_id, fence['epoch'], fence['generation'], self.workspace_id, fence['token'], encoded(supplied), encoded(receipt)))
            self.db.execute('UPDATE activity_queue SET state=?,reason=?,process_json=NULL WHERE job_id=?',
                            (state, 'worker identity absent; explicit disposition required' if state == 'reconciling' else 'worker identity absent: ' + disposition, job_id))
            self.db.execute('UPDATE activity_queue_owners SET last_wall=max(last_wall,?) WHERE workspace_id=?', (now, self.workspace_id))
            return receipt


def terminal_absence(engine, workspace_id, job_id, fence):
    """Return only a fully validated exact companion receipt; never infer one."""
    _fence(fence)
    if not _interface(engine):
        return None
    db = engine.db
    raw = db.execute('SELECT * FROM activity_worker_absences WHERE workspace_id=? AND job_id=? AND owner_epoch=? AND generation=?',
                     (workspace_id, job_id, fence['epoch'], fence['generation'])).fetchone()
    if raw is None:
        return None
    require(raw['lease_token'] == fence['token'], 'worker absence stale token')
    registration = WorkerCustody(engine, workspace_id).row(job_id, fence)
    row, record, reg_receipt, attempt = _registration_record(engine, registration)
    return _absence_record(engine, row, record, reg_receipt, attempt, raw)


def verify_worker_custody(engine):
    """Read-only conditional034 verifier; never calls033 global verifier."""
    if not _interface(engine):
        return {'installed': False}
    db = engine.db
    require(not db.execute('PRAGMA foreign_key_check').fetchall(), 'worker custody foreign key failure')
    registrations = absences = 0
    for raw in db.execute('SELECT * FROM activity_worker_registrations'):
        row, record, reg_receipt, attempt = _registration_record(engine, raw); registrations += 1
        fence = reg_receipt['fence']
        absent = db.execute('SELECT * FROM activity_worker_absences WHERE job_id=? AND owner_epoch=? AND generation=?',
                            (row['job_id'], fence['epoch'], fence['generation'])).fetchone()
        if absent:
            _absence_record(engine, row, record, reg_receipt, attempt, absent); absences += 1
        else:
            q = db.execute('SELECT * FROM activity_queue WHERE job_id=?', (row['job_id'],)).fetchone()
            require(q and q['workspace_id'] == row['workspace_id'], 'worker custody queue correspondence missing')
            current = (q['owner_epoch'], q['generation'], q['lease_token']) == (fence['epoch'], fence['generation'], fence['token'])
            if current and not _known_exit(db, attempt):
                normal_return = q['state'] == 'returned' and attempt['stop_requested_at'] is None and q['process_json'] is None
                require(normal_return or (q['state'] in ('running', 'reconciling') and q['process_json'] == attempt['process_json']),
                        'registered worker process cleared without a terminal fact')
    count = db.execute('SELECT count(*) FROM activity_worker_absences').fetchone()[0]
    require(count == absences, 'worker absence registration coverage mismatch')
    return {'installed': True, 'interface': '1', 'registrations': registrations, 'absences': absences}
