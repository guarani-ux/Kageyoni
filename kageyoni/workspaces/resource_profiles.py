"""Explicit trusted-host operational capacity; never fictional/model authority.

Absent opt-in storage retains the exact legacy profile. Configure before any
activity/queue admission; historical request identities and issued pins persist.
"""
import hashlib
import json

from ..engine import digest, encoded, require
from ..persistence.unit_of_work import UnitOfWork
from ..resources import schema_path


def legacy_profile():
    value = dict(profile_id='legacy', version=1, active_jobs=2, heavy_jobs=1,
                 active_activity_limit=32, inactive_activity_limit=32,
                 total_nonterminal_limit=32, queue_backlog=32)
    return dict(value, digest=digest(value))


def _selected(profile):
    require(isinstance(profile, dict) and set(profile) == {'profile_id', 'active_jobs'}, 'invalid resource profile')
    require(profile['profile_id'] == 'calibration-1000' and type(profile['active_jobs']) is int
            and profile['active_jobs'] in (1, 2), 'invalid resource profile')
    value = dict(profile_id='calibration-1000', version=1, active_jobs=profile['active_jobs'],
                 heavy_jobs=1, active_activity_limit=32, inactive_activity_limit=1000,
                 total_nonterminal_limit=1032, queue_backlog=32)
    return dict(value, digest=digest(value))


def _payload(profile, request_id, expected_digest):
    _selected(profile)
    require(isinstance(request_id, str) and request_id.strip() and len(request_id) <= 128, 'invalid profile request id')
    require(isinstance(expected_digest, str) and len(expected_digest) == 64
            and all(c in '0123456789abcdef' for c in expected_digest), 'invalid expected profile digest')
    return dict(profile=profile, request_id=request_id, expected_digest=expected_digest)


class ResourceProfiles:
    def __init__(self, engine, workspace_id):
        self.engine, self.db, self.workspace_id = engine, engine.db, workspace_id

    def _present(self):
        return bool(self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='activity_resource_profiles'").fetchone())

    def get(self):
        require(self.db.execute('SELECT 1 FROM operational_workspaces WHERE workspace_id=?',
                                (self.workspace_id,)).fetchone(), 'workspace unavailable')
        if not self._present():
            return legacy_profile()
        row = self.db.execute('SELECT * FROM activity_resource_profiles WHERE workspace_id=?',
                              (self.workspace_id,)).fetchone()
        if not row:
            return legacy_profile()
        value = json.loads(row['profile_json'])
        require(isinstance(value, dict) and set(value) == set(legacy_profile()) - {'digest'}, 'invalid stored resource profile')
        expected = _selected({key: value[key] for key in ('profile_id', 'active_jobs')})
        require(digest(value) == row['profile_digest'] == expected['digest'], 'resource profile digest mismatch')
        return expected

    def configure(self, profile, request_id, expected_digest):
        payload = _payload(profile, request_id, expected_digest)
        selected = _selected(profile)
        require(self._present() and self.db.execute(
            "SELECT 1 FROM engine_versions WHERE component='resource_profile_interface' AND version='1'"
        ).fetchone(), 'resource profile interface not installed')
        with UnitOfWork(self.db):
            old = self.db.execute('SELECT * FROM activity_resource_profile_receipts WHERE workspace_id=? AND request_id=?',
                                  (self.workspace_id, request_id)).fetchone()
            if old:
                require(old['payload_hash'] == digest(payload) and old['payload_json'] == encoded(payload), 'profile request identity conflict')
                require(old['receipt_json'] == encoded(selected), 'resource profile receipt mismatch')
                return json.loads(old['receipt_json'])
            current = self.get()
            require(current['digest'] == expected_digest, 'stale resource profile')
            if current != selected:
                require(not self.db.execute('SELECT 1 FROM activity_runs WHERE workspace_id=? LIMIT 1',
                                            (self.workspace_id,)).fetchone()
                        and not self.db.execute('SELECT 1 FROM activity_queue WHERE workspace_id=? LIMIT 1',
                                                (self.workspace_id,)).fetchone(), 'configure resource profile before issued work')
            self.db.execute('INSERT INTO activity_resource_profile_receipts(workspace_id,request_id,payload_json,payload_hash,receipt_json) VALUES(?,?,?,?,?)',
                            (self.workspace_id, request_id, encoded(payload), digest(payload), encoded(selected)))
            if current != selected:
                body = {key: value for key, value in selected.items() if key != 'digest'}
                self.db.execute('INSERT INTO activity_resource_profiles VALUES(?,?,?,?) ON CONFLICT(workspace_id) DO UPDATE SET profile_json=excluded.profile_json,profile_digest=excluded.profile_digest,selected_request_id=excluded.selected_request_id',
                                (self.workspace_id, encoded(body), selected['digest'], request_id))
            return selected


def verify_resource_profiles(engine):
    db = engine.db
    present = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='activity_resource_profiles'").fetchone()
    interface = db.execute("SELECT version FROM engine_versions WHERE component='resource_profile_interface'").fetchone()
    if not present and not interface:
        return {'installed': False}
    require(present and interface and interface[0] == '1', 'unsupported resource profile interface')
    checksum = db.execute('SELECT checksum FROM migration_checks WHERE version=31').fetchone()
    require(checksum and checksum[0] == hashlib.sha256(schema_path('migration_031.sql').read_bytes()).hexdigest(), 'resource profile migration checksum mismatch')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(), 'resource profile foreign key failure')
    by_workspace = {}
    last_requests = {}
    for row in db.execute('SELECT * FROM activity_resource_profile_receipts ORDER BY sequence'):
        payload = json.loads(row['payload_json'])
        require(isinstance(payload, dict) and set(payload) == {'profile', 'request_id', 'expected_digest'}, 'invalid resource profile receipt payload')
        _payload(payload['profile'], payload['request_id'], payload['expected_digest'])
        require(payload['request_id'] == row['request_id'] and row['payload_hash'] == digest(payload)
                and row['payload_json'] == encoded(payload), 'resource profile receipt identity mismatch')
        prior = by_workspace.get(row['workspace_id'], legacy_profile())
        require(payload['expected_digest'] == prior['digest'], 'resource profile receipt CAS mismatch')
        receipt = _selected(payload['profile'])
        require(row['receipt_json'] == encoded(receipt), 'resource profile receipt mismatch')
        by_workspace[row['workspace_id']] = receipt
        if receipt != prior:
            last_requests[row['workspace_id']] = row['request_id']
    rows = list(db.execute('SELECT * FROM activity_resource_profiles'))
    require({row['workspace_id'] for row in rows} == set(by_workspace), 'resource profile receipt coverage mismatch')
    for row in rows:
        require(ResourceProfiles(engine, row['workspace_id']).get() == by_workspace[row['workspace_id']]
                and row['selected_request_id'] == last_requests[row['workspace_id']], 'resource profile selected receipt mismatch')
    for row in db.execute('SELECT workspace_id,profile_digest FROM activity_queue'):
        require(row['profile_digest'] == ResourceProfiles(engine, row['workspace_id']).get()['digest'], 'queue resource profile binding mismatch')
    return {'installed': True, 'interface': '1', 'profiles': len(rows)}
