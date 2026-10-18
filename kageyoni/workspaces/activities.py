"""Operational activity persistence; no handler execution or fictional authority.

The application supplies validated records. CAS and the enclosing UnitOfWork
keep operational receipts atomic with the existing Engine's domain receipts.
"""
import json
import hashlib
from ..engine import require, digest, encoded
from ..persistence.unit_of_work import UnitOfWork
from ..resources import schema_path


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
        return self.get(workspace_id, spec['activity_id'])

    def update(self, workspace_id, activity_id, expected_version, checkpoint, native):
        require(checkpoint['activity_version'] == expected_version + 1, 'activity version must advance once')
        with UnitOfWork(self.db):
            changed = self.db.execute('UPDATE activity_runs SET version=?,state=?,outcome=?,checkpoint_json=?,native_json=? WHERE workspace_id=? AND activity_id=? AND version=?',
                (checkpoint['activity_version'], checkpoint['state'], checkpoint['outcome'], encoded(checkpoint), encoded(native), workspace_id, activity_id, expected_version)).rowcount
            require(changed == 1, 'stale activity version')
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
    return {'installed': True, 'interface': '1', 'activities': engine.db.execute('SELECT count(*) FROM activity_runs').fetchone()[0]}
