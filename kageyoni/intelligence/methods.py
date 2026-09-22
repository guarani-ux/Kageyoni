"""Source-bound operational methods. No story, capability or mastery is inferred.

Versions and assignments are append-only; owner approval permits bounded trials.
The prose rationale is an attributable judgment, not semantic verification.
"""
from __future__ import annotations

import hashlib
import json
from functools import wraps
from pathlib import Path
from ..resources import schema_path
from uuid import uuid4

from ..engine import digest, encoded, require
from ..persistence.unit_of_work import UnitOfWork
from .contracts import (METHOD_INTERFACE, QUALIFICATIONS, QUALIFICATION_LIMIT,
                        evidence_refs, integer, method_definition, text)


def _method_content(row):
    return {key: row[key] for key in ('method_id', 'revision', 'node_id', 'branch',
            'workspace_id', 'world_revision', 'definition', 'source_refs', 'snapshots',
            'source_digest', 'prior_digest')}


def _assignment_content(row):
    return {key: row[key] for key in ('node_id', 'method_id', 'method_revision', 'branch',
            'workspace_id', 'assignment_revision', 'qualification', 'rationale',
            'world_revision', 'method_digest', 'prior_digest')}


def _decode(row):
    result = dict(row)
    for field in ('definition', 'source_refs', 'snapshots'):
        result[field] = json.loads(result.pop(field + '_json'))
    return result


def _consistent_read(operation):
    """Keep permission projection and source/assignment checks in one snapshot."""
    @wraps(operation)
    def read(self, *args, **kwargs):
        with UnitOfWork(self.db):
            return operation(self, *args, **kwargs)
    return read


def _source_origin(engine, branch, world_revision, snapshot):
    """Bind a saved record to its actual ledger after-image and branch ancestry."""
    event = engine.db.execute('SELECT branch,revision FROM events WHERE id=?',
                              (snapshot.get('updated_event'),)).fetchone()
    require(event is not None, 'method source event unavailable')
    permitted = {}
    current, limit = branch, world_revision
    while current is not None:
        permitted[current] = limit
        meta = engine.branch(current)
        current, limit = meta['parent'], meta['fork_revision']
    require(event['branch'] in permitted and event['revision'] <= permitted[event['branch']],
            'method source is outside captured lineage')
    change = engine.db.execute('SELECT after_json FROM changes WHERE event_id=? AND record_id=?',
                               (snapshot['updated_event'], snapshot['id'])).fetchone()
    require(change is not None, 'method source after-image unavailable')
    original = json.loads(change[0])
    original['branch'] = branch
    require(original == snapshot, 'method source differs from ledger')


class Methods:
    def __init__(self, engine):
        self.engine, self.db = engine, engine.db

    def _installed(self):
        row = self.db.execute("SELECT version FROM engine_versions WHERE component='method_interface'").fetchone()
        require(row and row[0] == METHOD_INTERFACE, 'method interface not installed; run methods-init')

    def _scope(self, branch, workspace_id):
        self._installed()
        self.engine.branch(branch)
        workspace_id = workspace_id or 'world:' + branch
        row = self.db.execute('SELECT branch FROM network_workspaces WHERE workspace_id=?', (workspace_id,)).fetchone()
        require(row and row[0] == branch, 'method workspace unavailable')
        return workspace_id

    def _context(self, branch, viewer):
        return {r['id']: r for r in self.engine.context(branch, viewer=viewer)['records']}

    def _binding(self, branch, workspace_id, node_id, visible):
        row = self.db.execute('SELECT * FROM node_bindings WHERE branch=? AND workspace_id=? AND node_id=?',
                              (branch, workspace_id, node_id)).fetchone()
        require(row and row['character_id'] in visible and visible[row['character_id']]['domain'] == 'character',
                'node unavailable in workspace')
        return row

    def _capture(self, branch, world_revision, refs, visible):
        snapshots, captured = [], []
        for ref in refs:
            record = visible.get(ref['id'])
            require(record and record['domain'] == ref['domain'], 'method source unavailable')
            require(record['version'] == ref['record_revision'], 'stale method source revision')
            # Only after the reference was resolved in the permitted context.
            snapshot = self.engine.get(branch, ref['id'])
            source_hash = digest(snapshot)
            require('snapshot_hash' not in ref or ref['snapshot_hash'] == source_hash, 'stale method source digest')
            _source_origin(self.engine, branch, world_revision, snapshot)
            snapshots.append(snapshot)
            captured.append(dict(domain=ref['domain'], id=ref['id'],
                                 record_revision=ref['record_revision'], snapshot_hash=source_hash))
        return captured, snapshots

    def _replay(self, request_id, payload):
        old = self.db.execute('SELECT payload_hash,receipt_json FROM method_events WHERE request_id=?', (request_id,)).fetchone()
        if old:
            require(old['payload_hash'] == digest(payload), 'request key reused with different payload')
            return dict(json.loads(old['receipt_json']), replayed=True)
        return None

    def _event(self, kind, row, payload, receipt):
        self.db.execute('INSERT INTO method_events(request_id,kind,method_id,node_id,branch,workspace_id,payload_hash,payload_json,receipt_json) VALUES(?,?,?,?,?,?,?,?,?)',
                        (payload['request_id'], kind, row['method_id'], row['node_id'], row['branch'],
                         row['workspace_id'], digest(payload), encoded(payload), encoded(receipt)))

    def create(self, branch, node_id, request_id, expected_world_revision, method, source_refs,
               workspace_id=None, viewer=None):
        return self._write(branch, node_id, request_id, expected_world_revision, method, source_refs,
                           workspace_id, viewer, None, None)

    def revise(self, branch, node_id, method_id, expected_method_revision, request_id,
               expected_world_revision, method, source_refs, workspace_id=None, viewer=None):
        text(method_id, 'method id')
        integer(expected_method_revision, 'expected method revision')
        return self._write(branch, node_id, request_id, expected_world_revision, method, source_refs,
                           workspace_id, viewer, method_id, expected_method_revision)

    def _write(self, branch, node_id, request_id, expected_world_revision, method, source_refs,
               workspace_id, viewer, method_id, expected_method_revision):
        require(viewer is None, 'owner view required to record methods')
        text(request_id, 'request id'); text(node_id, 'node id')
        integer(expected_world_revision, 'expected world revision', 0)
        definition, refs = method_definition(method), evidence_refs(source_refs)
        workspace_id = self._scope(branch, workspace_id)
        payload = dict(branch=branch, node_id=node_id, request_id=request_id,
                       expected_world_revision=expected_world_revision, method=definition,
                       source_refs=refs, workspace_id=workspace_id, method_id=method_id,
                       expected_method_revision=expected_method_revision)
        with UnitOfWork(self.db):
            previous = self._replay(request_id, payload)
            if previous is not None:
                return previous
            require(self.engine.branch(branch)['revision'] == expected_world_revision, 'stale branch revision')
            visible = self._context(branch, viewer)
            self._binding(branch, workspace_id, node_id, visible)
            for actor in definition['audience']:
                require(actor in visible and visible[actor]['domain'] == 'character', 'method audience unavailable')
            prior, revision = None, 1
            if method_id is not None:
                prior = self.db.execute('SELECT * FROM method_revisions WHERE method_id=? AND node_id=? AND branch=? AND workspace_id=? ORDER BY revision DESC LIMIT 1',
                                        (method_id, node_id, branch, workspace_id)).fetchone()
                require(prior is not None, 'method unavailable')
                require(prior['revision'] == expected_method_revision, 'stale method revision')
                revision = prior['revision'] + 1
            captured, snapshots = self._capture(branch, expected_world_revision, refs, visible)
            row = dict(method_id=method_id or 'method:' + uuid4().hex, revision=revision,
                       node_id=node_id, branch=branch, workspace_id=workspace_id,
                       world_revision=expected_world_revision, definition=definition,
                       source_refs=captured, snapshots=snapshots, source_digest=digest(captured),
                       prior_digest=prior['digest'] if prior else None)
            row['digest'] = digest(_method_content(row))
            self.db.execute('INSERT INTO method_revisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                            (row['method_id'], revision, node_id, branch, workspace_id, expected_world_revision,
                             encoded(definition), encoded(captured), encoded(snapshots), row['source_digest'],
                             row['prior_digest'], row['digest'], request_id))
            receipt = dict(method_interface=METHOD_INTERFACE, method_id=row['method_id'], revision=revision,
                           digest=row['digest'], source_digest=row['source_digest'], node_id=node_id,
                           branch=branch, workspace_id=workspace_id, replayed=False)
            self._event('revised' if prior else 'created', row, payload, receipt)
            return receipt

    def assign(self, branch, node_id, method_id, method_revision, request_id, expected_world_revision,
               qualification, rationale, expected_assignment_revision=0, workspace_id=None, viewer=None):
        require(viewer is None, 'owner view required to assign methods')
        text(request_id, 'request id'); text(rationale, 'assignment rationale'); text(node_id, 'node id')
        text(method_id, 'method id'); integer(method_revision, 'method revision')
        integer(expected_world_revision, 'expected world revision', 0)
        integer(expected_assignment_revision, 'expected assignment revision', 0)
        require(qualification in QUALIFICATIONS, 'unsupported method qualification')
        workspace_id = self._scope(branch, workspace_id)
        payload = dict(branch=branch, node_id=node_id, method_id=method_id, method_revision=method_revision,
                       request_id=request_id, expected_world_revision=expected_world_revision,
                       qualification=qualification, rationale=rationale,
                       expected_assignment_revision=expected_assignment_revision, workspace_id=workspace_id)
        with UnitOfWork(self.db):
            old_receipt = self._replay(request_id, payload)
            if old_receipt is not None:
                return old_receipt
            require(self.engine.branch(branch)['revision'] == expected_world_revision, 'stale branch revision')
            visible = self._context(branch, viewer)
            self._binding(branch, workspace_id, node_id, visible)
            method = self.read(branch, method_id, method_revision, viewer=viewer, workspace_id=workspace_id)
            require(method['node_id'] == node_id, 'method belongs to another node')
            require(qualification != 'experimental' or method['source_fresh'], 'method source requires revalidation')
            old = self._assignment(branch, workspace_id, node_id, method_id)
            require((old['assignment_revision'] if old else 0) == expected_assignment_revision, 'stale assignment revision')
            row = dict(node_id=node_id, method_id=method_id, method_revision=method_revision, branch=branch,
                       workspace_id=workspace_id, assignment_revision=expected_assignment_revision + 1,
                       qualification=qualification, rationale=rationale, world_revision=expected_world_revision,
                       method_digest=method['digest'], prior_digest=old['digest'] if old else None)
            row['digest'] = digest(_assignment_content(row))
            self.db.execute('INSERT INTO node_method_assignments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                            tuple(row[k] for k in ('node_id', 'method_id', 'method_revision', 'branch', 'workspace_id',
                                  'assignment_revision', 'qualification', 'rationale', 'world_revision',
                                  'method_digest', 'prior_digest', 'digest')) + (request_id,))
            receipt = dict(method_interface=METHOD_INTERFACE, method_id=method_id, revision=method_revision,
                           digest=method['digest'], node_id=node_id, branch=branch, workspace_id=workspace_id,
                           assignment_revision=row['assignment_revision'], assignment_digest=row['digest'],
                           qualification=qualification, qualification_limit=QUALIFICATION_LIMIT, replayed=False)
            self._event('assigned', row, payload, receipt)
            return receipt

    def _assignment(self, branch, workspace_id, node_id, method_id):
        return self.db.execute('SELECT * FROM node_method_assignments WHERE branch=? AND workspace_id=? AND node_id=? AND method_id=? ORDER BY assignment_revision DESC LIMIT 1',
                                (branch, workspace_id, node_id, method_id)).fetchone()

    def _view(self, row, visible, viewer):
        row = _decode(row)
        binding = self.db.execute('SELECT character_id FROM node_bindings WHERE node_id=? AND workspace_id=? AND branch=?',
                                  (row['node_id'], row['workspace_id'], row['branch'])).fetchone()
        if not binding or binding[0] not in visible or not self.engine._visible(row['definition'], viewer):
            return None
        fresh = True
        for ref, snapshot in zip(row['source_refs'], row['snapshots']):
            current = visible.get(ref['id'])
            if not current or current['domain'] != ref['domain'] or not self.engine._visible(snapshot, viewer):
                return None
            if current['version'] != ref['record_revision'] or digest(self.engine.get(row['branch'], ref['id'])) != ref['snapshot_hash']:
                fresh = False
        # Never expose private after-images, origin evidence metadata or owner rationale.
        row.pop('snapshots'); row.pop('request_id'); row.pop('prior_digest')
        if viewer is not None:
            row['definition'].pop('audience', None)
        row['source_fresh'] = fresh
        assignment = self._assignment(row['branch'], row['workspace_id'], row['node_id'], row['method_id'])
        row.update(qualification=None, assignment_revision=0, assignment_digest=None, assigned_method_revision=None,
                   qualification_limit=QUALIFICATION_LIMIT)
        if assignment:
            row.update(assignment_revision=assignment['assignment_revision'], assignment_digest=assignment['digest'],
                       assigned_method_revision=assignment['method_revision'])
            if assignment['method_revision'] == row['revision']:
                row['qualification'] = assignment['qualification']
            if viewer is None:
                row['assignment_rationale'] = assignment['rationale']
        return row

    @_consistent_read
    def read(self, branch, method_id, method_revision=None, viewer=None, workspace_id=None):
        text(method_id, 'method id')
        if method_revision is not None:
            integer(method_revision, 'method revision')
        workspace_id = self._scope(branch, workspace_id)
        visible = self._context(branch, viewer)
        sql = 'SELECT * FROM method_revisions WHERE branch=? AND workspace_id=? AND method_id=?'
        args = [branch, workspace_id, method_id]
        if method_revision is not None:
            sql += ' AND revision=?'; args.append(method_revision)
        row = self.db.execute(sql + ' ORDER BY revision DESC LIMIT 1', args).fetchone()
        result = self._view(row, visible, viewer) if row else None
        require(result is not None, 'method unavailable')
        return result

    @_consistent_read
    def list(self, branch, character_id, task_domain=None, viewer=None, workspace_id=None):
        workspace_id = self._scope(branch, workspace_id)
        visible = self._context(branch, viewer)
        require(character_id in visible and visible[character_id]['domain'] == 'character', 'character unavailable')
        binding = self.db.execute('SELECT node_id FROM node_bindings WHERE branch=? AND workspace_id=? AND character_id=?',
                                  (branch, workspace_id, character_id)).fetchone()
        require(binding is not None, 'character has no node in this workspace')
        if task_domain is not None:
            text(task_domain, 'task domain')
        rows = self.db.execute('SELECT m.* FROM method_revisions m WHERE branch=? AND workspace_id=? AND node_id=? AND revision=(SELECT MAX(n.revision) FROM method_revisions n WHERE n.method_id=m.method_id) ORDER BY method_id',
                               (branch, workspace_id, binding['node_id'])).fetchall()
        views = [self._view(row, visible, viewer) for row in rows]
        return [v for v in views if v and (task_domain is None or task_domain in v['definition']['domains'])]

    @_consistent_read
    def eligible(self, branch, character_id, task_domain, viewer=None, workspace_id=None):
        text(task_domain, 'task domain')
        workspace_id = self._scope(branch, workspace_id)
        visible = self._context(branch, viewer)
        require(character_id in visible and visible[character_id]['domain'] == 'character', 'character unavailable')
        binding = self.db.execute('SELECT node_id FROM node_bindings WHERE branch=? AND workspace_id=? AND character_id=?',
                                  (branch, workspace_id, character_id)).fetchone()
        require(binding is not None, 'character has no node in this workspace')
        # Retrieval reads persisted definitions; there is no process-local motif cache.
        result = []
        rows = self.db.execute('''SELECT m.* FROM node_method_assignments a
            JOIN method_revisions m ON m.method_id=a.method_id AND m.revision=a.method_revision
            WHERE a.branch=? AND a.workspace_id=? AND a.node_id=? AND a.qualification='experimental'
            AND a.assignment_revision=(SELECT MAX(b.assignment_revision) FROM node_method_assignments b
                 WHERE b.node_id=a.node_id AND b.method_id=a.method_id AND b.workspace_id=a.workspace_id)
            ORDER BY a.method_id''', (branch, workspace_id, binding['node_id'])).fetchall()
        for row in rows:
            # A private, unassigned draft cannot suppress a currently assigned public revision.
            selected = self._view(row, visible, viewer)
            if selected and selected['source_fresh'] and task_domain in selected['definition']['domains']:
                result.append(selected)
        return result


def verify_methods(engine):
    """Check append-only provenance without treating a rationale as proof of skill."""
    db = engine.db
    installed = db.execute("SELECT version FROM engine_versions WHERE component='method_interface'").fetchone()
    if not installed:
        return {'installed': False}
    require(installed[0] == METHOD_INTERFACE, 'unsupported method interface')
    migration = schema_path('migration_010.sql')
    check = db.execute('SELECT checksum FROM migration_checks WHERE version=10').fetchone()
    require(check and check[0] == hashlib.sha256(migration.read_bytes()).hexdigest(), 'method migration checksum mismatch')
    seen, expected_events = {}, {}
    for raw in db.execute('SELECT * FROM method_revisions ORDER BY method_id,revision'):
        row = _decode(raw)
        require(method_definition(row['definition']) == row['definition'], 'method definition mismatch')
        refs = evidence_refs(row['source_refs'])
        require(refs == row['source_refs'] and len(refs) == len(row['snapshots']), 'method source count mismatch')
        require(digest(refs) == row['source_digest'], 'method source digest mismatch')
        for ref, snapshot in zip(refs, row['snapshots']):
            require(snapshot['branch'] == row['branch'] and snapshot['id'] == ref['id']
                    and snapshot['domain'] == ref['domain'] and snapshot['version'] == ref['record_revision']
                    and digest(snapshot) == ref['snapshot_hash'], 'method source snapshot mismatch')
            _source_origin(engine, row['branch'], row['world_revision'], snapshot)
        prior = seen.get(row['method_id'])
        require(row['revision'] == (prior['revision'] + 1 if prior else 1), 'method revision chain gap')
        require(row['prior_digest'] == (prior['digest'] if prior else None), 'method prior digest mismatch')
        if prior:
            require(all(row[k] == prior[k] for k in ('node_id', 'branch', 'workspace_id')), 'method scope changed')
        binding = db.execute('SELECT branch FROM node_bindings WHERE node_id=? AND workspace_id=?',
                              (row['node_id'], row['workspace_id'])).fetchone()
        require(binding and binding[0] == row['branch'], 'method binding scope mismatch')
        require(row['world_revision'] <= engine.branch(row['branch'])['revision'], 'method world revision is in the future')
        require(digest(_method_content(row)) == row['digest'], 'method digest mismatch')
        seen[row['method_id']] = row
        expected_events[row['request_id']] = ('revised' if prior else 'created', row)
    assignments = {}
    for raw in db.execute('SELECT * FROM node_method_assignments ORDER BY node_id,method_id,workspace_id,assignment_revision'):
        row = dict(raw)
        key = (row['node_id'], row['method_id'], row['workspace_id'])
        prior = assignments.get(key)
        require(row['assignment_revision'] == (prior['assignment_revision'] + 1 if prior else 1), 'assignment revision chain gap')
        require(row['prior_digest'] == (prior['digest'] if prior else None), 'assignment prior digest mismatch')
        require(digest(_assignment_content(row)) == row['digest'], 'assignment digest mismatch')
        method = db.execute('SELECT * FROM method_revisions WHERE method_id=? AND revision=?',
                            (row['method_id'], row['method_revision'])).fetchone()
        require(method and all(row[k] == method[k] for k in ('node_id', 'branch', 'workspace_id'))
                and row['method_digest'] == method['digest'], 'assignment method mismatch')
        require(method['world_revision'] <= row['world_revision'] <= engine.branch(row['branch'])['revision'], 'assignment world revision mismatch')
        assignments[key] = row
        require(row['request_id'] not in expected_events, 'duplicate method request')
        expected_events[row['request_id']] = ('assigned', row)
    count = 0
    for event in db.execute('SELECT * FROM method_events ORDER BY sequence'):
        require(event['request_id'] in expected_events, 'orphan method event')
        kind, row = expected_events[event['request_id']]
        payload, receipt = json.loads(event['payload_json']), json.loads(event['receipt_json'])
        require(event['kind'] == kind and digest(payload) == event['payload_hash'], 'method event hash or kind mismatch')
        require(payload['request_id'] == event['request_id'], 'method event request mismatch')
        require(all(event[k] == row[k] == receipt[k] == payload[k] for k in ('node_id', 'branch', 'workspace_id')), 'method event scope mismatch')
        require(event['method_id'] == row['method_id'] == receipt['method_id'], 'method event identity mismatch')
        require(receipt['method_interface'] == METHOD_INTERFACE and receipt['replayed'] is False, 'method receipt interface mismatch')
        if kind == 'assigned':
            require(receipt['revision'] == row['method_revision'] and receipt['assignment_revision'] == row['assignment_revision']
                    and receipt['digest'] == row['method_digest'] and receipt['assignment_digest'] == row['digest']
                    and receipt['qualification'] == row['qualification'], 'assignment receipt mismatch')
            require(payload['method_id'] == row['method_id'] and payload['method_revision'] == row['method_revision']
                    and payload['qualification'] == row['qualification'] and payload['rationale'] == row['rationale']
                    and payload['expected_assignment_revision'] + 1 == row['assignment_revision'], 'assignment payload mismatch')
        else:
            require(receipt['revision'] == row['revision'] and receipt['digest'] == row['digest']
                    and receipt['source_digest'] == row['source_digest'], 'method receipt mismatch')
            require(payload['method'] == row['definition'] and evidence_refs(payload['source_refs']) == payload['source_refs'], 'method event definition mismatch')
            require(len(payload['source_refs']) == len(row['source_refs']), 'method event source count mismatch')
            require((payload['method_id'] is None and payload['expected_method_revision'] is None and row['revision'] == 1)
                    if kind == 'created' else (payload['method_id'] == row['method_id']
                    and payload['expected_method_revision'] + 1 == row['revision']), 'method event revision mismatch')
            for proposed, captured in zip(payload['source_refs'], row['source_refs']):
                require(all(captured[k] == v for k, v in proposed.items()), 'method event source mismatch')
        require(payload['expected_world_revision'] == row['world_revision'], 'method event world revision mismatch')
        count += 1
    require(count == len(expected_events), 'method event history incomplete')
    return {'installed': True, 'interface': METHOD_INTERFACE, 'methods': len(seen),
            'revisions': sum(1 for v in expected_events.values() if v[0] != 'assigned'),
            'assignments': sum(1 for v in expected_events.values() if v[0] == 'assigned')}
