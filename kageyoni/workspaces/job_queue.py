"""Engine-owned durable admission, fair selection and fenced lease state.

The sole application owner supplies process observations. No process, model or
file IO runs inside these transactions. Charged starts/ceilings are never
refunded by nesting, cancellation, a crash, or manual reconciliation.
"""
import hashlib
import json
from uuid import uuid4
from ..engine import require, encoded
from ..persistence.unit_of_work import UnitOfWork
from ..resources import schema_path
from .resource_profiles import ResourceProfiles


class JobQueue:
    def __init__(self, engine, workspace_id):
        self.engine, self.db, self.workspace_id = engine, engine.db, workspace_id
        require(self.db.execute("SELECT 1 FROM engine_versions WHERE component='activity_queue_interface' AND version='1'").fetchone(), 'queue not installed')

    def boot(self, now):
        with UnitOfWork(self.db):
            from .worker_liveness import WorkerLiveness
            clock = 'max(activity_queue_owners.last_wall,excluded.last_wall)' if WorkerLiveness(self.engine,self.workspace_id).present() else 'excluded.last_wall'
            self.db.execute('''INSERT INTO activity_queue_owners VALUES(?,1,?)
                ON CONFLICT(workspace_id) DO UPDATE SET epoch=epoch+1,last_wall=''' + clock, (self.workspace_id, now))
            self.db.execute("UPDATE activity_queue SET state='reconciling',reason='owner restarted; observe process before disposition' WHERE workspace_id=? AND state='running'", (self.workspace_id,))
        return self.owner()['epoch']

    def owner(self):
        return dict(self.db.execute('SELECT * FROM activity_queue_owners WHERE workspace_id=?', (self.workspace_id,)).fetchone())

    def row(self, job_id):
        row = self.db.execute('SELECT * FROM activity_queue WHERE workspace_id=? AND job_id=?', (self.workspace_id, job_id)).fetchone()
        return dict(row) if row else None

    def rows(self, live_only=False):
        where = " AND state IN ('queued','running','reconciling')" if live_only else ''
        return [dict(r) for r in self.db.execute('SELECT * FROM activity_queue WHERE workspace_id=?'+where+' ORDER BY sequence', (self.workspace_id,))]

    def root(self, activity_id):
        seen = set()
        while True:
            require(activity_id not in seen, 'activity parent cycle')
            seen.add(activity_id)
            row = self.db.execute('SELECT parent_id FROM activity_runs WHERE workspace_id=? AND activity_id=?', (self.workspace_id, activity_id)).fetchone()
            require(row is not None, 'activity unavailable')
            if not row[0]: return activity_id
            activity_id = row[0]

    def manual_starts(self, root_id):
        return self.db.execute('''WITH RECURSIVE tree(activity_id) AS (
            SELECT activity_id FROM activity_runs WHERE workspace_id=? AND activity_id=?
            UNION ALL SELECT a.activity_id FROM activity_runs a JOIN tree t ON a.parent_id=t.activity_id WHERE a.workspace_id=?)
            SELECT count(*) FROM activity_jobs j JOIN tree t ON j.activity_id=t.activity_id
            LEFT JOIN activity_queue q ON q.job_id=j.job_id
            WHERE j.workspace_id=? AND j.result_json IS NOT NULL AND j.returned_by='worker' AND q.job_id IS NULL''',
            (self.workspace_id,root_id,self.workspace_id,self.workspace_id)).fetchone()[0]

    def enqueue(self, job_id, binding_id, authority_epoch, recipe, parameters, max_seconds):
        require(0 < max_seconds <= 120, 'invalid work ceiling')
        with UnitOfWork(self.db):
            old = self.row(job_id)
            if old:
                require((old['binding_id'],old['authority_epoch'],old['recipe'],old['parameters_json'],old['max_seconds']) ==
                    (binding_id,authority_epoch,recipe,encoded(parameters),max_seconds), 'queue identity conflict')
                return old
            job = self.db.execute('SELECT activity_id,state FROM activity_jobs WHERE workspace_id=? AND job_id=?', (self.workspace_id,job_id)).fetchone()
            require(job and job['state']=='waiting', 'job unavailable')
            profile = ResourceProfiles(self.engine, self.workspace_id).get()
            require(self.db.execute("SELECT count(*) FROM activity_queue WHERE workspace_id=? AND state IN ('queued','running','paused','reconciling')", (self.workspace_id,)).fetchone()[0] < profile['queue_backlog'], 'queue full')
            root = self.root(job['activity_id'])
            tail = self.db.execute('SELECT coalesce(max(last_dispatch),0) FROM activity_queue_roots WHERE workspace_id=?', (self.workspace_id,)).fetchone()[0]
            self.db.execute('INSERT OR IGNORE INTO activity_queue_roots(workspace_id,root_id,last_dispatch) VALUES(?,?,?)', (self.workspace_id,root,tail))
            columns = {r['name'] for r in self.db.execute('PRAGMA table_info(activity_queue)')}
            if 'profile_digest' in columns:
                self.db.execute('''INSERT INTO activity_queue(job_id,workspace_id,root_id,binding_id,authority_epoch,recipe,parameters_json,state,max_seconds,profile_digest)
                    VALUES(?,?,?,?,?,?,?,'queued',?,?)''', (job_id,self.workspace_id,root,binding_id,authority_epoch,recipe,encoded(parameters),max_seconds,profile['digest']))
            else:
                self.db.execute('''INSERT INTO activity_queue(job_id,workspace_id,root_id,binding_id,authority_epoch,recipe,parameters_json,state,max_seconds)
                    VALUES(?,?,?,?,?,?,?,'queued',?)''', (job_id,self.workspace_id,root,binding_id,authority_epoch,recipe,encoded(parameters),max_seconds))
        return self.row(job_id)

    def claim(self, now):
        with UnitOfWork(self.db):
            owner = self.owner()
            if now < owner['last_wall']:
                self.db.execute("UPDATE activity_queue SET state='reconciling',reason='wall clock rollback' WHERE workspace_id=? AND state IN ('running','queued')", (self.workspace_id,))
                return None
            self.db.execute('UPDATE activity_queue_owners SET last_wall=? WHERE workspace_id=?', (now,self.workspace_id))
            # Reconciling processes retain their slot until observed stopped.
            active = self.db.execute("SELECT count(*) FROM activity_queue WHERE workspace_id=? AND (state='running' OR (state='reconciling' AND process_json IS NOT NULL))", (self.workspace_id,)).fetchone()[0]
            profile = ResourceProfiles(self.engine, self.workspace_id).get()
            if active >= profile['active_jobs']: return None
            heavy = any(json.loads(r['parameters_json']).get('cpu_iterations',0)>0 for r in
                self.db.execute("SELECT parameters_json FROM activity_queue WHERE workspace_id=? AND (state='running' OR (state='reconciling' AND process_json IS NOT NULL))", (self.workspace_id,)))
            rows = self.db.execute('''SELECT q.* FROM activity_queue q JOIN activity_queue_roots r
                ON q.workspace_id=r.workspace_id AND q.root_id=r.root_id
                WHERE q.workspace_id=? AND q.state='queued' ORDER BY r.last_dispatch,q.sequence''', (self.workspace_id,)).fetchall()
            for raw in rows:
                row = dict(raw)
                if 'profile_digest' in row:
                    require(row['profile_digest'] == profile['digest'], 'queue resource profile binding mismatch')
                if heavy and json.loads(row['parameters_json']).get('cpu_iterations',0)>0:
                    continue
                binding = self.db.execute('SELECT active,authority_epoch FROM activity_bindings WHERE binding_id=?', (row['binding_id'],)).fetchone()
                if not binding or not binding['active'] or binding['authority_epoch'] != row['authority_epoch']:
                    self.db.execute("UPDATE activity_queue SET state='paused',reason='authority changed' WHERE job_id=?", (row['job_id'],)); continue
                job = self.db.execute('SELECT activity_id,state FROM activity_jobs WHERE job_id=?', (row['job_id'],)).fetchone()
                aid = job['activity_id']; blocked = job['state']!='waiting'
                while aid:
                    a = self.db.execute('SELECT state,parent_id FROM activity_runs WHERE workspace_id=? AND activity_id=?', (self.workspace_id,aid)).fetchone()
                    if a['state'] in ('paused','cancelled','failed','finished'): blocked=True
                    aid=a['parent_id']
                if blocked: continue
                budget = self.db.execute('SELECT * FROM activity_queue_roots WHERE workspace_id=? AND root_id=?', (self.workspace_id,row['root_id'])).fetchone()
                if budget['starts']+self.manual_starts(row['root_id']) >= 4 or budget['reserved_seconds']+row['max_seconds']>900:
                    self.db.execute("UPDATE activity_queue SET state='paused',reason='parent budget exhausted' WHERE job_id=?", (row['job_id'],));continue
                serial = self.db.execute('SELECT coalesce(max(last_dispatch),0)+1 FROM activity_queue_roots WHERE workspace_id=?', (self.workspace_id,)).fetchone()[0]
                self.db.execute('UPDATE activity_queue_roots SET starts=starts+1,reserved_seconds=reserved_seconds+?,last_dispatch=? WHERE workspace_id=? AND root_id=?',
                    (row['max_seconds'],serial,self.workspace_id,row['root_id']))
                self.db.execute("UPDATE activity_queue SET state='running',generation=generation+1,owner_epoch=?,lease_token=?,lease_until=?,reason='' WHERE job_id=? AND state='queued'",
                    (owner['epoch'],uuid4().hex,now+row['max_seconds'],row['job_id']))
                from .worker_liveness import WorkerLiveness
                WorkerLiveness(self.engine,self.workspace_id).claim(self.row(row['job_id']),now)
                return self.row(row['job_id'])
        return None

    def assert_lease(self, job_id, fence, now):
        row=self.row(job_id)
        require(row and row['state']=='running' and row['owner_epoch']==self.owner()['epoch'] and
            fence=={'epoch':row['owner_epoch'],'generation':row['generation'],'token':row['lease_token']} and
            now>=self.owner()['last_wall'] and now<row['lease_until'], 'stale queue lease')
        return row

    @staticmethod
    def fence(row):
        return {'epoch':row['owner_epoch'],'generation':row['generation'],'token':row['lease_token']}

    def process(self, job_id, fence, observation, now):
        with UnitOfWork(self.db):
            self.assert_lease(job_id,fence,now)
            from .worker_liveness import WorkerLiveness
            WorkerLiveness(self.engine,self.workspace_id).process(job_id,fence,observation)
            self.db.execute('UPDATE activity_queue SET process_json=? WHERE job_id=?', (encoded(observation),job_id))

    def transition(self, job_id, state, reason='', output_ref=None, clear_process=False):
        require(state in ('queued','paused','reconciling','returned','cancelled','failed'), 'invalid queue transition')
        with UnitOfWork(self.db):
            row=self.row(job_id)
            require(row, 'queue job unavailable')
            from .worker_liveness import WorkerLiveness
            live=WorkerLiveness(self.engine,self.workspace_id)
            if live.present():
                attempt=self.db.execute('SELECT stop_requested_at,stop_disposition,process_json,exit_json FROM activity_worker_liveness WHERE job_id=? AND owner_epoch=? AND generation=?', (job_id,row['owner_epoch'],row['generation'])).fetchone()
                if attempt:
                    normal_return = row['state'] == 'running' and attempt['stop_requested_at'] is None and state == 'returned' and clear_process and attempt['process_json'] is not None and row['process_json'] == attempt['process_json']
                    if attempt['exit_json'] is None and attempt['process_json'] is not None:
                        require(normal_return or (not clear_process and state == 'reconciling' and row['process_json'] == attempt['process_json']), 'observe stopped worker exit before clearing process or releasing slot')
                    elif attempt['stop_requested_at'] is not None and attempt['process_json'] is None:
                        allowed = {'reconciling'}
                        if attempt['stop_disposition'] == 'pause': allowed.add('paused')
                        if attempt['stop_disposition'] == 'cancel': allowed.add('cancelled')
                        require(state in allowed, 'unregistered stopped worker cannot revive or return')
                    require(state != 'returned' or normal_return, 'stopped worker cannot return')
            self.db.execute('''UPDATE activity_queue SET state=?,reason=?,output_ref_json=coalesce(?,output_ref_json),
                process_json=CASE WHEN ? THEN NULL ELSE process_json END WHERE job_id=?''',
                (state,reason,encoded(output_ref) if output_ref else None,clear_process,job_id))


    def heartbeat(self, job_id, fence, sequence, now):
        from .worker_liveness import WorkerLiveness
        return WorkerLiveness(self.engine,self.workspace_id).heartbeat(job_id,fence,sequence,now)

    def request_stop(self, job_id, fence, disposition, request_id, now):
        from .worker_liveness import WorkerLiveness
        return WorkerLiveness(self.engine,self.workspace_id).request_stop(job_id,fence,disposition,request_id,now)

    def observe_exit(self, job_id, fence, observation, now):
        from .worker_liveness import WorkerLiveness
        return WorkerLiveness(self.engine,self.workspace_id).observe_exit(job_id,fence,observation,now)


def verify_queue(engine):
    db=engine.db
    check=db.execute('SELECT checksum FROM migration_checks WHERE version=27').fetchone()
    require(check and check[0]==hashlib.sha256(schema_path('migration_027.sql').read_bytes()).hexdigest(), 'queue migration checksum mismatch')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(), 'queue foreign key failure')
    for row in db.execute("SELECT workspace_id,count(*) AS active FROM activity_queue WHERE state='running' OR (state='reconciling' AND process_json IS NOT NULL) GROUP BY workspace_id"):
        require(row['active'] <= ResourceProfiles(engine,row['workspace_id']).get()['active_jobs'], 'queue capacity exceeded')
    for row in db.execute("SELECT * FROM activity_queue WHERE state='running'"):
        owner=db.execute('SELECT epoch FROM activity_queue_owners WHERE workspace_id=?',(row['workspace_id'],)).fetchone()
        require(owner and row['owner_epoch']==owner[0] and row['lease_token'] and row['lease_until'] is not None,'invalid live lease')
    return {'installed':True,'interface':'1'}
