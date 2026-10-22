"""Native attempt liveness CAS; the owner supplies observations, never OS IO.

This API does not authenticate or admit an arbitrary external worker. Transport,
actual heartbeat production, monotonic supervision and process observation are
separate trusted-owner responsibilities. No fictional clock or budget refund.
"""
import hashlib
import json
import math
from ..engine import require, digest, encoded
from ..persistence.unit_of_work import UnitOfWork
from ..resources import schema_path
from .resource_profiles import ResourceProfiles

POLICY = {'version': 1, 'lease_seconds': 30, 'heartbeat_seconds': 10, 'stop_grace_seconds': 5}
POLICY_DIGEST = digest(POLICY)
DISPOSITIONS = {'pause', 'cancel', 'shutdown', 'authority_revoked', 'lease_expired', 'execution_expired', 'protocol_error'}
METHODS = {'cooperative', 'forced', 'exited_before_stop', 'exited_after_stop'}


def _time(now):
    require(type(now) in (int, float) and math.isfinite(now), 'invalid owner time')
    return now


def _sequence(value):
    require(type(value) is int and value > 0, 'invalid heartbeat sequence')


def _fence(value):
    require(isinstance(value, dict) and set(value) == {'epoch', 'generation', 'token'}
            and type(value['epoch']) is int and value['epoch'] > 0
            and type(value['generation']) is int and value['generation'] > 0
            and isinstance(value['token'], str) and bool(value['token']), 'invalid worker fence')
    return value


def _process(value):
    require(isinstance(value, dict) and set(value) == {'pid', 'proc_pid', 'pid_namespace', 'start_ticks'}
            and type(value['pid']) is int and value['pid'] > 0
            and type(value['proc_pid']) is int and value['proc_pid'] > 0
            and isinstance(value['pid_namespace'], str) and bool(value['pid_namespace'])
            and isinstance(value['start_ticks'], str) and value['start_ticks'].isdigit(), 'invalid process identity')
    return value


def _observation(value):
    require(isinstance(value, dict) and set(value) == {'process', 'exited', 'returncode', 'method'}
            and value['exited'] is True and type(value['returncode']) is int
            and value['method'] in METHODS, 'invalid terminal process observation')
    _process(value['process'])
    return value


class WorkerLiveness:
    def __init__(self, engine, workspace_id):
        self.engine, self.db, self.workspace_id = engine, engine.db, workspace_id

    def present(self):
        return bool(self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='activity_worker_liveness'").fetchone())

    def row(self, job_id, fence):
        _fence(fence)
        row = self.db.execute('SELECT * FROM activity_worker_liveness WHERE workspace_id=? AND job_id=? AND owner_epoch=? AND generation=?',
                              (self.workspace_id, job_id, fence['epoch'], fence['generation'])).fetchone()
        require(row is not None and row['lease_token'] == fence['token'], 'worker liveness attempt unavailable')
        return dict(row)

    def _queue(self, job_id, fence):
        row = self.db.execute('SELECT * FROM activity_queue WHERE workspace_id=? AND job_id=?', (self.workspace_id, job_id)).fetchone()
        require(row is not None and (row['owner_epoch'], row['generation'], row['lease_token']) ==
                (fence['epoch'], fence['generation'], fence['token']), 'stale worker fence')
        return dict(row)

    def claim(self, row, now):
        """Called inside the queue claim UoW only for genuinely new033 claims."""
        require(self.db.in_transaction, 'liveness claim needs queue transaction')
        if not self.present():
            return
        _time(now)
        fence = {'epoch': row['owner_epoch'], 'generation': row['generation'], 'token': row['lease_token']}
        self._queue(row['job_id'], fence)
        ceiling = now + row['max_seconds']; lease = min(now + POLICY['lease_seconds'], ceiling)
        self.db.execute('''INSERT INTO activity_worker_liveness(job_id,owner_epoch,generation,workspace_id,lease_token,
            policy_json,policy_digest,claimed_at,execution_until,lease_until) VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (row['job_id'], fence['epoch'], fence['generation'], self.workspace_id, fence['token'],
             encoded(POLICY), POLICY_DIGEST, now, ceiling, lease))
        self.db.execute('UPDATE activity_queue SET lease_until=? WHERE job_id=?', (lease, row['job_id']))

    def _absence(self, job_id, fence):
        # Local import avoids a module-load/global-verifier cycle. The central
        # helper validates exact034 evidence; NULL process/exit is never proof.
        from .worker_custody import terminal_absence
        return terminal_absence(self.engine, self.workspace_id, job_id, fence)

    def process(self, job_id, fence, observation):
        if not self.present():
            return
        # Historical attempts without a033 row keep their original semantics.
        found = self.db.execute('SELECT 1 FROM activity_worker_liveness WHERE job_id=? AND owner_epoch=? AND generation=?',
                                (job_id, fence['epoch'], fence['generation'])).fetchone()
        if not found:
            return
        _process(observation)
        row = self.row(job_id, fence)
        require(self._absence(job_id, fence) is None, 'worker identity already absent')
        require(row['process_json'] is None or row['process_json'] == encoded(observation), 'worker process identity conflict')
        self.db.execute('UPDATE activity_worker_liveness SET process_json=? WHERE job_id=? AND owner_epoch=? AND generation=?',
                        (encoded(observation), job_id, fence['epoch'], fence['generation']))

    def heartbeat(self, job_id, fence, sequence, now):
        _time(now); _sequence(sequence); _fence(fence)
        rollback = False
        with UnitOfWork(self.db):
            attempt = self.row(job_id, fence); q = self._queue(job_id, fence)
            require(self._absence(job_id, fence) is None, 'worker identity already absent')
            owner = self.db.execute('SELECT * FROM activity_queue_owners WHERE workspace_id=?', (self.workspace_id,)).fetchone()
            require(q['state'] == 'running' and owner and owner['epoch'] == fence['epoch']
                    and attempt['stop_requested_at'] is None and attempt['exit_json'] is None, 'stale worker heartbeat')
            floor = max(owner['last_wall'], attempt['claimed_at'], attempt['last_heartbeat'] if attempt['last_heartbeat'] is not None else attempt['claimed_at'])
            if now < floor:
                self.db.execute("UPDATE activity_queue SET state='reconciling',reason='worker heartbeat wall clock rollback' WHERE job_id=?", (job_id,))
                rollback = True
            else:
                require(now < attempt['lease_until'] and now < attempt['execution_until'], 'expired worker heartbeat')
                require(q['lease_until'] == attempt['lease_until'], 'worker lease correspondence mismatch')
                binding = self.db.execute('SELECT active,authority_epoch FROM activity_bindings WHERE binding_id=?', (q['binding_id'],)).fetchone()
                require(binding and binding['active'] and binding['authority_epoch'] == q['authority_epoch'], 'worker authority changed')
                require(q.get('profile_digest') == ResourceProfiles(self.engine, self.workspace_id).get()['digest'], 'worker resource profile changed')
                job = self.db.execute('SELECT activity_id,state FROM activity_jobs WHERE job_id=? AND workspace_id=?', (job_id, self.workspace_id)).fetchone()
                require(job and job['state'] == 'waiting', 'worker job unavailable')
                aid = job['activity_id']; seen = set()
                while aid:
                    require(aid not in seen, 'worker activity parent cycle'); seen.add(aid)
                    activity = self.db.execute('SELECT parent_id,state FROM activity_runs WHERE workspace_id=? AND activity_id=?', (self.workspace_id, aid)).fetchone()
                    require(activity and activity['state'] not in ('paused', 'cancelled', 'failed', 'finished'), 'worker ancestor stopped')
                    aid = activity['parent_id']
                if sequence <= attempt['last_sequence']:
                    old = self.db.execute('SELECT receipt_json FROM activity_worker_heartbeats WHERE job_id=? AND owner_epoch=? AND generation=? AND sequence=?',
                                          (job_id, fence['epoch'], fence['generation'], sequence)).fetchone()
                    require(old is not None, 'reordered worker heartbeat')
                    return json.loads(old[0])
                require(sequence == attempt['last_sequence'] + 1, 'worker heartbeat sequence gap')
                lease = min(now + POLICY['lease_seconds'], attempt['execution_until'])
                receipt = {'kind': 'worker_heartbeat', 'job_id': job_id, 'fence': fence, 'sequence': sequence,
                           'observed_at': now, 'lease_until': lease, 'execution_until': attempt['execution_until'], 'policy_digest': POLICY_DIGEST}
                self.db.execute('INSERT INTO activity_worker_heartbeats VALUES(?,?,?,?,?)', (job_id, fence['epoch'], fence['generation'], sequence, encoded(receipt)))
                self.db.execute('UPDATE activity_worker_liveness SET last_sequence=?,last_heartbeat=?,lease_until=? WHERE job_id=? AND owner_epoch=? AND generation=?',
                                (sequence, now, lease, job_id, fence['epoch'], fence['generation']))
                self.db.execute('UPDATE activity_queue SET lease_until=? WHERE job_id=?', (lease, job_id))
                self.db.execute('UPDATE activity_queue_owners SET last_wall=? WHERE workspace_id=?', (now, self.workspace_id))
                return receipt
        require(not rollback, 'worker heartbeat wall clock rollback')

    def request_stop(self, job_id, fence, disposition, request_id, now):
        _time(now); _fence(fence)
        require(disposition in DISPOSITIONS and isinstance(request_id, str) and 0 < len(request_id) <= 128, 'invalid worker stop request')
        with UnitOfWork(self.db):
            attempt = self.row(job_id, fence); q = self._queue(job_id, fence)
            absence = self._absence(job_id, fence)
            old = self.db.execute('SELECT * FROM activity_worker_stops WHERE job_id=? AND owner_epoch=? AND generation=? AND request_id=?',
                                  (job_id, fence['epoch'], fence['generation'], request_id)).fetchone()
            if old:
                require(old['disposition'] == disposition, 'worker stop request conflict')
                return json.loads(old['receipt_json'])
            require(absence is None, 'worker identity already absent')
            require(attempt['exit_json'] is None and q['state'] in ('running', 'reconciling'), 'worker stop unavailable')
            owner = self.db.execute('SELECT last_wall FROM activity_queue_owners WHERE workspace_id=?', (self.workspace_id,)).fetchone()
            requested = now if attempt['stop_requested_at'] is None else attempt['stop_requested_at']
            deadline = now + POLICY['stop_grace_seconds'] if attempt['stop_deadline'] is None else attempt['stop_deadline']
            selected = attempt['stop_disposition'] or disposition
            if disposition == 'cancel': selected = 'cancel'
            rollback = now < max(owner[0], attempt['claimed_at'], attempt['last_heartbeat'] if attempt['last_heartbeat'] is not None else attempt['claimed_at'])
            receipt = {'kind': 'worker_stop', 'job_id': job_id, 'fence': fence, 'request_id': request_id,
                       'requested_disposition': disposition, 'disposition': selected, 'observed_at': now,
                       'stop_requested_at': requested, 'stop_deadline': deadline, 'clock_rollback': rollback,
                       'time_status': 'uncertain' if rollback else 'owner_wall',
                       'owner_wall_before': owner[0], 'owner_wall_after': max(owner[0], now), 'policy_digest': POLICY_DIGEST}
            self.db.execute('INSERT INTO activity_worker_stops(job_id,owner_epoch,generation,request_id,disposition,receipt_json) VALUES(?,?,?,?,?,?)',
                            (job_id, fence['epoch'], fence['generation'], request_id, disposition, encoded(receipt)))
            self.db.execute('UPDATE activity_worker_liveness SET stop_requested_at=?,stop_deadline=?,stop_disposition=?,stop_request_id=coalesce(stop_request_id,?) WHERE job_id=? AND owner_epoch=? AND generation=?',
                            (requested, deadline, selected, request_id, job_id, fence['epoch'], fence['generation']))
            self.db.execute("UPDATE activity_queue SET state='reconciling',reason=? WHERE job_id=?", ('worker stop: ' + selected, job_id))
            self.db.execute('UPDATE activity_queue_owners SET last_wall=max(last_wall,?) WHERE workspace_id=?', (now, self.workspace_id))
            return receipt

    def observe_exit(self, job_id, fence, observation, now):
        _time(now); _fence(fence); _observation(observation)
        with UnitOfWork(self.db):
            attempt = self.row(job_id, fence); q = self._queue(job_id, fence)
            absence = self._absence(job_id, fence)
            old = self.db.execute('SELECT receipt_json FROM activity_worker_exits WHERE job_id=? AND owner_epoch=? AND generation=?',
                                  (job_id, fence['epoch'], fence['generation'])).fetchone()
            if old:
                receipt = json.loads(old[0]); require(receipt['observation'] == observation, 'worker exit observation conflict'); return receipt
            require(absence is None, 'worker identity already absent')
            require(attempt['process_json'] is not None and q['process_json'] == attempt['process_json']
                    and json.loads(attempt['process_json']) == observation['process'], 'worker exit process identity mismatch')
            require(q['state'] in ('running', 'reconciling'), 'worker exit unavailable')
            if observation['method'] != 'exited_before_stop': require(attempt['stop_requested_at'] is not None, 'worker stop intent missing')
            disposition = attempt['stop_disposition']
            state = 'paused' if disposition == 'pause' else 'cancelled' if disposition == 'cancel' else 'reconciling'
            owner = self.db.execute('SELECT last_wall FROM activity_queue_owners WHERE workspace_id=?', (self.workspace_id,)).fetchone()
            floor = max(owner[0], attempt['claimed_at'], attempt['last_heartbeat'] if attempt['last_heartbeat'] is not None else attempt['claimed_at'])
            rollback = now < floor
            receipt = {'kind': 'worker_exit', 'job_id': job_id, 'fence': fence, 'observed_at': now,
                       'observation': observation, 'disposition': disposition, 'state': state,
                       'clock_rollback': rollback, 'time_status': 'uncertain' if rollback else 'owner_wall',
                       'owner_wall_before': owner[0], 'owner_wall_after': max(owner[0], now), 'policy_digest': POLICY_DIGEST}
            self.db.execute('INSERT INTO activity_worker_exits VALUES(?,?,?,?)', (job_id, fence['epoch'], fence['generation'], encoded(receipt)))
            self.db.execute('UPDATE activity_worker_liveness SET exit_json=? WHERE job_id=? AND owner_epoch=? AND generation=?',
                            (encoded(receipt), job_id, fence['epoch'], fence['generation']))
            self.db.execute('UPDATE activity_queue SET state=?,reason=?,process_json=NULL WHERE job_id=?', (state, 'worker exited; explicit disposition required' if state == 'reconciling' else 'worker exited: ' + disposition, job_id))
            self.db.execute('UPDATE activity_queue_owners SET last_wall=max(last_wall,?) WHERE workspace_id=?', (now, self.workspace_id))
            return receipt


def verify_worker_liveness(engine):
    """Direct conditional verifier; root owns the later Engine.verify hook."""
    db = engine.db
    tables = {'activity_worker_liveness', 'activity_worker_heartbeats', 'activity_worker_stops', 'activity_worker_exits'}
    present = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} & tables
    interface = db.execute("SELECT version FROM engine_versions WHERE component='worker_liveness_interface'").fetchone()
    migration = db.execute('SELECT checksum FROM migration_checks WHERE version=33').fetchone()
    if not present and not interface and not migration:
        return {'installed': False}
    require(present == tables and interface and interface[0] == '1' and migration, 'incomplete worker liveness interface')
    require(migration[0] == hashlib.sha256(schema_path('migration_033.sql').read_bytes()).hexdigest(), 'worker liveness migration checksum mismatch')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(), 'worker liveness foreign key failure')
    # Direct033 verification must not bless a partial/invalid034 companion
    # even when there are zero033 attempts.034 never calls this global verifier.
    from .worker_custody import verify_worker_custody
    verify_worker_custody(engine)
    count = 0
    for raw in db.execute('SELECT * FROM activity_worker_liveness'):
        a = dict(raw); count += 1
        key = (a['job_id'], a['owner_epoch'], a['generation'])
        fence = {'epoch': a['owner_epoch'], 'generation': a['generation'], 'token': a['lease_token']}; _fence(fence)
        require(a['policy_json'] == encoded(POLICY) and a['policy_digest'] == POLICY_DIGEST, 'worker liveness policy mismatch')
        _time(a['claimed_at']); _time(a['execution_until']); _time(a['lease_until'])
        q = db.execute('SELECT * FROM activity_queue WHERE job_id=?', (a['job_id'],)).fetchone()
        require(q and q['workspace_id'] == a['workspace_id'] and a['execution_until'] == a['claimed_at'] + q['max_seconds'], 'worker execution ceiling mismatch')
        lease = min(a['claimed_at'] + POLICY['lease_seconds'], a['execution_until']); last = a['claimed_at']; sequence = 0
        for raw_h in db.execute('SELECT * FROM activity_worker_heartbeats WHERE job_id=? AND owner_epoch=? AND generation=? ORDER BY sequence', key):
            h = json.loads(raw_h['receipt_json']); sequence += 1; _time(h['observed_at'])
            require(h == {'kind': 'worker_heartbeat', 'job_id': a['job_id'], 'fence': fence, 'sequence': sequence,
                    'observed_at': h['observed_at'], 'lease_until': min(h['observed_at'] + 30, a['execution_until']),
                    'execution_until': a['execution_until'], 'policy_digest': POLICY_DIGEST}
                    and raw_h['sequence'] == sequence and last <= h['observed_at'] < lease, 'invalid worker heartbeat receipt')
            last, lease = h['observed_at'], h['lease_until']
        require(a['last_sequence'] == sequence and a['lease_until'] == lease
                and a['last_heartbeat'] == (last if sequence else None), 'worker heartbeat correspondence mismatch')
        if a['process_json'] is not None: _process(json.loads(a['process_json']))
        stops = list(db.execute('SELECT * FROM activity_worker_stops WHERE job_id=? AND owner_epoch=? AND generation=? ORDER BY ordinal', key))
        first = None; disposition = None; stop_wall = a['claimed_at']
        owner = db.execute('SELECT last_wall FROM activity_queue_owners WHERE workspace_id=?', (a['workspace_id'],)).fetchone()
        require(owner and owner[0] >= last, 'worker owner clock high-water mismatch')
        for raw_s in stops:
            s = json.loads(raw_s['receipt_json']); _time(s['observed_at'])
            require(set(s) == {'kind','job_id','fence','request_id','requested_disposition','disposition','observed_at','stop_requested_at','stop_deadline','clock_rollback','time_status','owner_wall_before','owner_wall_after','policy_digest'}
                    and raw_s['disposition'] in DISPOSITIONS and s['requested_disposition'] == raw_s['disposition']
                    and s['request_id'] == raw_s['request_id'] and s['kind'] == 'worker_stop'
                    and s['job_id'] == a['job_id'] and s['fence'] == fence and s['policy_digest'] == POLICY_DIGEST
                    and type(s['clock_rollback']) is bool and s['time_status'] == ('uncertain' if s['clock_rollback'] else 'owner_wall'), 'invalid worker stop receipt')
            _time(s['owner_wall_before']); _time(s['owner_wall_after'])
            require(s['owner_wall_before'] >= stop_wall and s['owner_wall_after'] == max(s['owner_wall_before'], s['observed_at'])
                    and owner[0] >= s['owner_wall_after']
                    and s['clock_rollback'] == (s['observed_at'] < max(s['owner_wall_before'], a['claimed_at'], last)), 'worker stop clock correspondence mismatch')
            stop_wall = s['owner_wall_after']
            if first is None: first = s
            disposition = disposition or raw_s['disposition']
            if raw_s['disposition'] == 'cancel': disposition = 'cancel'
            require(s['stop_requested_at'] == first['observed_at'] and s['stop_deadline'] == first['observed_at'] + 5
                    and s['disposition'] == disposition, 'worker stop deadline/disposition mismatch')
        if first:
            require((a['stop_requested_at'], a['stop_deadline'], a['stop_disposition'], a['stop_request_id']) ==
                    (first['observed_at'], first['observed_at'] + 5, disposition, first['request_id']), 'worker stop correspondence mismatch')
        else:
            require(all(a[k] is None for k in ('stop_requested_at', 'stop_deadline', 'stop_disposition', 'stop_request_id')), 'worker stop receipt missing')
        x = db.execute('SELECT receipt_json FROM activity_worker_exits WHERE job_id=? AND owner_epoch=? AND generation=?', key).fetchone()
        require((x[0] if x else None) == a['exit_json'], 'worker exit receipt correspondence mismatch')
        if x:
            receipt = json.loads(x[0]); _observation(receipt['observation']); _time(receipt['observed_at'])
            require(set(receipt) == {'kind','job_id','fence','observed_at','observation','disposition','state','clock_rollback','time_status','owner_wall_before','owner_wall_after','policy_digest'}
                    and a['process_json'] is not None and receipt['observation']['process'] == json.loads(a['process_json'])
                    and receipt['kind'] == 'worker_exit' and receipt['job_id'] == a['job_id']
                    and receipt['fence'] == fence and receipt['policy_digest'] == POLICY_DIGEST
                    and receipt['disposition'] == disposition
                    and receipt['state'] == ('paused' if disposition == 'pause' else 'cancelled' if disposition == 'cancel' else 'reconciling'), 'invalid worker exit receipt')
            _time(receipt['owner_wall_before']); _time(receipt['owner_wall_after'])
            require(receipt['owner_wall_before'] >= stop_wall and receipt['owner_wall_after'] == max(receipt['owner_wall_before'], receipt['observed_at'])
                    and owner[0] >= receipt['owner_wall_after'] and type(receipt['clock_rollback']) is bool
                    and receipt['clock_rollback'] == (receipt['observed_at'] < max(receipt['owner_wall_before'], a['claimed_at'], last))
                    and receipt['time_status'] == ('uncertain' if receipt['clock_rollback'] else 'owner_wall'), 'worker exit clock correspondence mismatch')
            require(receipt['observation']['method'] == 'exited_before_stop' or first is not None, 'worker exit stop intent missing')
        # Older attempts remain immutable history; the queue corresponds only
        # to its current exact attempt. No backfill of pre033 history is inferred.
        from .worker_custody import terminal_absence
        absence = terminal_absence(engine, a['workspace_id'], a['job_id'], fence)
        current = (q['owner_epoch'], q['generation'], q['lease_token']) == (fence['epoch'], fence['generation'], fence['token'])
        if current:
            require(q['lease_until'] == a['lease_until'], 'current worker queue lease mismatch')
            if first:
                require(q['state'] not in ('running', 'returned'), 'stopped worker returned or revived')
                if a['process_json'] is None:
                    allowed = {'reconciling'}
                    if disposition == 'pause': allowed.add('paused')
                    if disposition == 'cancel': allowed.add('cancelled')
                    require(q['state'] in allowed and q['process_json'] is None, 'unregistered stopped worker state mismatch')
            if a['process_json'] is None:
                require(q['process_json'] is None, 'unregistered worker queue process correspondence mismatch')
            if q['state'] == 'returned':
                require(first is None and x is None and a['process_json'] is not None and q['process_json'] is None, 'invalid unobserved normal worker return')
            if x: require(q['process_json'] is None and q['state'] != 'running', 'exited worker process still charged')
            elif absence is not None:
                require(first is not None and q['process_json'] is None and q['state'] not in ('running', 'returned'),
                        'identity absent worker revived or returned')
            elif a['process_json'] is not None:
                normal_return = first is None and q['state'] == 'returned' and q['process_json'] is None
                require(normal_return or (q['state'] in ('running', 'reconciling') and q['process_json'] == a['process_json']), 'worker process cleared or slot released without observed exit')
            # No-stop normal _finish may retain its existing fenced acceptance
            # and actual product Popen observation without a new native exit API.
    return {'installed': True, 'interface': '1', 'attempts': count, 'policy_digest': POLICY_DIGEST}
