"""Operational activity persistence; no handler execution or fictional authority.

The application supplies validated records. CAS and the enclosing UnitOfWork
keep operational receipts atomic with the existing Engine's domain receipts.
"""
import json
import hashlib
from ..engine import require, digest, encoded
from ..persistence.unit_of_work import UnitOfWork
from ..resources import schema_path


def _membership_installed(db):
    return bool(db.execute("SELECT 1 FROM engine_versions WHERE component='resource_admission_interface' AND version='1'").fetchone())


def _participants(spec):
    values = spec.get('participants')
    require(isinstance(values,list) and all(isinstance(value,str) and bool(value) for value in values)
            and len(values)==len(set(values)), 'invalid activity participants')
    return values


def verify_activity_membership(engine):
    db=engine.db
    if not _membership_installed(db):
        return
    expected=set()
    for row in db.execute('SELECT workspace_id,activity_id,spec_json FROM activity_runs'):
        expected.update((row['workspace_id'],character,row['activity_id'])
                        for character in _participants(json.loads(row['spec_json'])))
    actual={tuple(row) for row in db.execute('SELECT workspace_id,character_id,activity_id FROM activity_participants')}
    require(expected==actual,'activity participant membership mismatch')


class Activities:
    def __init__(self, engine):
        self.engine, self.db = engine, engine.db
        require(self.db.execute("SELECT 1 FROM engine_versions WHERE component='activity_interface' AND version='1'").fetchone(), 'activity interface not installed')

    def get(self, workspace_id, activity_id):
        row = self.db.execute('SELECT * FROM activity_runs WHERE workspace_id=? AND activity_id=?', (workspace_id, activity_id)).fetchone()
        require(row is not None, 'activity unavailable')
        value = dict(row)
        for name in ('spec', 'checkpoint', 'native'):
            value[name] = json.loads(value.pop(name + '_json'))
        require(digest(value['spec']) == value['spec_digest'], 'activity specification mismatch')
        return value

    def page(self, workspace_id, *, after=None, limit=20, character_id=None, root_activity_id=None):
        require(_membership_installed(self.db),'resource admission interface not installed')
        require(isinstance(workspace_id,str) and bool(workspace_id),'invalid workspace id')
        require(type(limit) is int and 1<=limit<=101,'invalid activity page limit')
        for value in (after,character_id,root_activity_id):
            require(value is None or (isinstance(value,str) and bool(value)),'invalid activity page id')
        require(root_activity_id is None or character_id is not None,'worker activity scope requires character')
        if character_id is None:
            scope='SELECT activity_id FROM activity_runs WHERE workspace_id=?'
            params=[workspace_id]
        else:
            scope='SELECT activity_id FROM activity_participants WHERE workspace_id=? AND character_id=?'
            params=[workspace_id,character_id]
        if root_activity_id is not None:
            scope+=''' AND activity_id IN (WITH RECURSIVE tree(activity_id,depth) AS (
                SELECT activity_id,1 FROM activity_runs WHERE workspace_id=? AND activity_id=?
                UNION ALL SELECT a.activity_id,t.depth+1 FROM activity_runs a JOIN tree t ON a.parent_id=t.activity_id
                WHERE a.workspace_id=? AND t.depth<5) SELECT activity_id FROM tree)'''
            params.extend([workspace_id,root_activity_id,workspace_id])
        if after is not None:
            require(self.db.execute('SELECT 1 FROM ('+scope+') WHERE activity_id=?',params+[after]).fetchone(),
                    'activity cursor unavailable')
        query='SELECT activity_id FROM ('+scope+')'
        if after is not None:
            query+=' WHERE activity_id>?'
            params.append(after)
        rows=self.db.execute(query+' ORDER BY activity_id LIMIT ?',params+[limit]).fetchall()
        result=[self.get(workspace_id,row['activity_id']) for row in rows]
        if character_id is not None:
            require(all(character_id in activity['spec']['participants'] for activity in result),'activity unavailable')
        return result

    def create(self, workspace_id, branch, spec, checkpoint, native):
        with UnitOfWork(self.db):
            if spec['parent_id']:
                parent = self.get(workspace_id, spec['parent_id'])
                require(parent['state'] not in ('finished', 'failed', 'cancelled'), 'parent is terminal')
                require(parent['branch'] == branch, 'parent branch mismatch')
                require(spec['parent_id'] != spec['activity_id'], 'activity cannot parent itself')
            self.db.execute('INSERT INTO activity_runs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (workspace_id, spec['activity_id'], branch, spec['parent_id'], encoded(spec), digest(spec), 1,
                 checkpoint['state'], checkpoint['outcome'], encoded(checkpoint), encoded(native)))
            if _membership_installed(self.db):
                self.db.executemany('INSERT INTO activity_participants VALUES(?,?,?)',
                                    [(workspace_id,character,spec['activity_id']) for character in _participants(spec)])
                from .resource_admission import _validate_configured_usage
                _validate_configured_usage(self.engine,workspace_id)
        return self.get(workspace_id, spec['activity_id'])

    def update(self, workspace_id, activity_id, expected_version, checkpoint, native):
        require(checkpoint['activity_version'] == expected_version + 1, 'activity version must advance once')
        with UnitOfWork(self.db):
            changed = self.db.execute('UPDATE activity_runs SET version=?,state=?,outcome=?,checkpoint_json=?,native_json=? WHERE workspace_id=? AND activity_id=? AND version=?',
                (checkpoint['activity_version'], checkpoint['state'], checkpoint['outcome'], encoded(checkpoint), encoded(native), workspace_id, activity_id, expected_version)).rowcount
            require(changed == 1, 'stale activity version')
            if _membership_installed(self.db) and checkpoint['state'] not in ('finished','failed','cancelled'):
                from .resource_admission import _validate_configured_usage
                _validate_configured_usage(self.engine,workspace_id)
        return self.get(workspace_id, activity_id)


def verify_activities(engine):
    row = engine.db.execute("SELECT version FROM engine_versions WHERE component='activity_interface'").fetchone()
    if not row:
        return {'installed': False}
    require(row[0] == '1', 'unsupported activity interface')
    check = engine.db.execute('SELECT checksum FROM migration_checks WHERE version=26').fetchone()
    require(check and check[0] == hashlib.sha256(schema_path('migration_026.sql').read_bytes()).hexdigest(), 'activity migration checksum mismatch')
    require(not engine.db.execute('PRAGMA foreign_key_check').fetchall(), 'activity foreign key failure')
    for row in engine.db.execute('SELECT * FROM activity_runs'):
        spec, checkpoint = json.loads(row['spec_json']), json.loads(row['checkpoint_json'])
        require(digest(spec) == row['spec_digest'] and spec['activity_id'] == row['activity_id'] and spec['parent_id'] == row['parent_id'], 'activity specification mismatch')
        require(checkpoint['activity_id'] == row['activity_id'] and checkpoint['activity_version'] == row['version'] and checkpoint['state'] == row['state'] and checkpoint['outcome'] == row['outcome'], 'activity checkpoint mismatch')
    for row in engine.db.execute('SELECT * FROM activity_jobs'):
        prepared = json.loads(row['prepared_json'])
        require(digest(prepared) == row['prepared_digest'] and prepared['job_id'] == row['job_id'] and prepared['attempt_generation'] == row['generation'], 'activity prepared binding mismatch')
    for row in engine.db.execute('SELECT * FROM activity_artifact_grants'):
        artifact = engine.db.execute('SELECT workspace_id,digest FROM artifacts WHERE artifact_id=?', (row['artifact_id'],)).fetchone()
        require(artifact and artifact['workspace_id'] == row['workspace_id'] and artifact['digest'] == row['digest'], 'activity artifact grant mismatch')
    for row in engine.db.execute('SELECT * FROM activity_staging'):
        content = bytes(row['content'])
        require(len(content) == row['size'] and hashlib.sha256(content).hexdigest() == row['digest'], 'activity staging mismatch')
    verify_activity_membership(engine)
    return {'installed': True, 'interface': '1', 'activities': engine.db.execute('SELECT count(*) FROM activity_runs').fetchone()[0]}
