"""Persistent, scoped experience and reviewed changes to later method use.

Outcomes retain exact later observations. Their interpretation, relevance and
proposed intervention remain attributed owner judgments, never automatic skill.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import hashlib
import json
from pathlib import Path
from ..resources import schema_path
from uuid import uuid4

from ..engine import require, digest, encoded, Rejected
from ..persistence.unit_of_work import UnitOfWork
from ..persistence.contributions import _check_row
from ..execution import operations
from .contracts import text, integer, strings
from .methods import Methods, _source_origin
from .nodes import Nodes
from .learning_contracts import (LEARNING_INTERFACE, JUDGMENT_LIMIT, REVIEW_STATES,
                                 observation, lesson_definition, context, context_matches, equal, scalar)

_JSON = {'observation', 'source_refs', 'snapshots', 'origin_event_ids', 'definition',
         'outcome_ids', 'counter_outcome_ids'}


def _decode(row):
    result = dict(row)
    for key in list(result):
        if key.endswith('_json') and key[:-5] in _JSON:
            result[key[:-5]] = json.loads(result.pop(key))
    return result


def _content(row):
    return {k: v for k, v in row.items() if k not in ('digest', 'request_id')}


def _atomic(operation):
    @wraps(operation)
    def invoke(self, *args, **kwargs):
        with UnitOfWork(self.db):
            return operation(self, *args, **kwargs)
    return invoke


def _path(record, path):
    value = record
    for part in path:
        if isinstance(value, dict) and isinstance(part, str) and part in value:
            value = value[part]
        elif isinstance(value, list) and type(part) is int and 0 <= part < len(value):
            value = value[part]
        else:
            return False, None
    return True, value


class Learning:
    def __init__(self, engine):
        self.engine, self.db = engine, engine.db
        self.methods = Methods(engine)

    def _installed(self):
        require(self.db.execute("SELECT 1 FROM engine_versions WHERE component='learning_interface' AND version='1'").fetchone(),
                'learning interface not installed; run learning-init')

    def _owner(self, viewer, request_id, expected_world_revision, branch):
        self._installed()
        require(viewer is None, 'owner view required to record or qualify learning')
        text(request_id, 'request id'); integer(expected_world_revision, 'expected world revision', 0)
        self.engine.branch(branch)

    def _replay(self, request_id, payload):
        old = self.db.execute('SELECT payload_hash,receipt_json FROM learning_events WHERE request_id=?', (request_id,)).fetchone()
        if old:
            require(old['payload_hash'] == digest(payload), 'request key reused with different payload')
            return dict(json.loads(old['receipt_json']), replayed=True)
        return None

    def _event(self, kind, object_id, branch, payload, receipt):
        self.db.execute('INSERT INTO learning_events(request_id,kind,object_id,branch,payload_hash,payload_json,receipt_json) VALUES(?,?,?,?,?,?,?)',
                        (payload['request_id'], kind, object_id, branch, digest(payload), encoded(payload), encoded(receipt)))

    def _save(self, table, row):
        row['digest'] = digest(_content(row))
        columns = [(k + '_json' if k in _JSON else k) for k in row]
        values = [(encoded(v) if k in _JSON else v) for k, v in row.items()]
        self.db.execute('INSERT INTO ' + table + '(' + ','.join(columns) + ') VALUES(' + ','.join('?' for _ in columns) + ')', values)

    def _permitted(self, branch, viewer):
        return {r['id']: r for r in self.engine.context(branch, viewer=viewer, include_properties=False, include_processes=False)['records']}

    def _contribution(self, branch, contribution_id, viewer=None, _seen=None):
        # Historical evidence must not re-run Expression: doing so recurses
        # through learning and would rewrite the circumstances of an old trial.
        raw = self.db.execute('SELECT * FROM contributions WHERE branch=? AND contribution_id=?', (branch, contribution_id)).fetchone()
        require(raw is not None, 'contribution unavailable')
        _check_row(raw)
        request, result = json.loads(raw['request_json']), json.loads(raw['result_json'])
        Nodes(self.engine).read(branch, request['character_id'], viewer=viewer)
        if viewer is not None:
            seen = set(_seen or ())
            require(contribution_id not in seen and len(seen) < 128, 'learning ancestry is cyclic or exceeds inspection bound')
            seen.add(contribution_id)
            require(raw['viewer'] == viewer, 'contribution unavailable')
            permitted = self._permitted(branch, viewer)
            # The original reader was authorized at execution. Current hiding
            # still removes historical evidence; changing a value does not erase it.
            dependencies = result.get('binding', {}).get('sources', []) + result.get('binding', {}).get('historical_sources', [])
            require(all(ref['id'] in permitted and permitted[ref['id']]['domain'] == ref['domain']
                        for ref in dependencies), 'contribution unavailable')
            for ref in result.get('binding', {}).get('methods', []):
                self.methods.read(branch, ref['method_id'], ref['revision'], viewer=viewer, workspace_id=raw['workspace_id'])
            # Recheck the exact historical learning dependencies, including
            # measurement fields. Merely checking their source record IDs
            # would let a private ancestor continue influencing descendants.
            for ref in result.get('binding', {}).get('lessons', []):
                old_lesson = self._latest(branch, ref['lesson_id'], ref['revision'])
                require(old_lesson['digest'] == ref['digest']
                        and self.engine._visible(old_lesson['definition'], viewer), 'contribution learning ancestry unavailable')
                old_review = self.db.execute('SELECT * FROM lesson_reviews WHERE lesson_id=? AND lesson_revision=? AND review_revision=?',
                    (ref['lesson_id'], ref['revision'], ref['review_revision'])).fetchone()
                require(old_review is not None, 'contribution learning ancestry unavailable')
                old_review = _decode(old_review)
                require(old_review['digest'] == ref['review_digest'] and old_review['lesson_digest'] == old_lesson['digest']
                        and old_review['status'] == 'qualified', 'contribution learning ancestry mismatch')
                ids = sorted(set(old_lesson['outcome_ids']) | set(old_lesson['counter_outcome_ids'])
                             | set(old_review['counter_outcome_ids']))
                for oid in ids:
                    outcome = self.db.execute('SELECT * FROM learning_outcomes WHERE branch=? AND outcome_id=?', (branch, oid)).fetchone()
                    require(outcome is not None, 'contribution learning ancestry unavailable')
                    self._outcome_view(outcome, viewer, _seen=seen)
        return dict(raw=raw, request=request, result=result)

    def _historical_record(self, branch, record_id, revision):
        row = self.db.execute('''SELECT c.after_json FROM changes c JOIN events e ON e.id=c.event_id
            WHERE e.branch=? AND e.revision<=? AND c.record_id=? ORDER BY e.revision DESC LIMIT 1''',
            (branch, revision, record_id)).fetchone()
        if row:
            return json.loads(row[0])
        baseline = self.db.execute('SELECT state_json FROM snapshots WHERE id=?', ('fork:' + branch,)).fetchone()
        if baseline:
            value = json.loads(baseline[0]); records = value if isinstance(value, list) else value.get('records', [])
            return next((r for r in records if r['id'] == record_id), None)
        return None

    def _measurement_visible(self, row, item, snapshot, permitted, viewer):
        if viewer is None:
            return True
        path = item['evidence']['field_path']
        # A public record can contain a private relationship or nested contract.
        # Check the current projection when unchanged, and the captured field's
        # reference visibility at capture AND now for historical observations.
        full_now = self.engine.get(row['branch'], snapshot['id'])
        if digest(full_now) == item['evidence']['source_ref']['snapshot_hash']:
            found, value = _path(permitted[snapshot['id']], path)
            if not found or not equal(value, item['value']):
                return False
        def safe(value):
            if isinstance(value, dict):
                return all(safe(child) for child in value.values())
            if isinstance(value, list):
                return all(safe(child) for child in value)
            if isinstance(value, str):
                historic = self._historical_record(row['branch'], value, row['world_revision'])
                if historic is not None:
                    return value in permitted and self.engine._visible(historic, viewer)
            return True
        return safe(snapshot['data'].get(path[1]))

    def _capture(self, branch, contribution, declaration, world_revision):
        permitted = self._permitted(branch, None)
        refs, snapshots, events = {}, {}, set()
        for item in declaration['measurements']:
            citation = item['evidence']; ref = citation['source_ref']
            record = permitted.get(ref['id'])
            require(record and record['domain'] == ref['domain'], 'outcome source unavailable')
            full = self.engine.get(branch, ref['id'])
            require(full['version'] == ref['record_revision'] and digest(full) == ref['snapshot_hash'], 'outcome source unavailable or stale')
            _source_origin(self.engine, branch, world_revision, full)
            event = self.db.execute('SELECT branch,revision FROM events WHERE id=?', (full['updated_event'],)).fetchone()
            require(event['branch'] == branch and event['revision'] > contribution['result']['binding']['world_revision'],
                    'outcome measurement must be from a later event in this branch')
            found, actual = _path(record, citation['field_path'])
            require(found and scalar(actual) and equal(item['value'], actual), 'outcome measurement differs from recorded field')
            require(ref['id'] not in refs or refs[ref['id']] == ref, 'conflicting observation references')
            refs[ref['id']], snapshots[ref['id']] = ref, full
            events.add(full['updated_event'])
        if declaration['status'] != 'unknown':
            require(any(item['value'] is not None for item in declaration['measurements']), 'known outcome requires a non-null observation')
        return ([deepcopy(refs[k]) for k in sorted(refs)], [snapshots[k] for k in sorted(snapshots)], sorted(events))

    @_atomic
    def record_outcome(self, branch, contribution_id, request_id, expected_world_revision, observation, viewer=None):
        self._owner(viewer, request_id, expected_world_revision, branch)
        from .learning_contracts import observation as validate_observation
        declaration = validate_observation(observation)
        text(contribution_id, 'contribution id')
        payload = dict(branch=branch, contribution_id=contribution_id, request_id=request_id,
                       expected_world_revision=expected_world_revision, observation=declaration)
        replay = self._replay(request_id, payload)
        if replay is not None:
            return replay
        require(self.engine.branch(branch)['revision'] == expected_world_revision, 'stale branch revision')
        contribution = self._contribution(branch, contribution_id)
        refs, snapshots, events = self._capture(branch, contribution, declaration, expected_world_revision)
        raw = contribution['raw']
        row = dict(outcome_id='outcome:' + uuid4().hex, contribution_id=contribution_id,
                   branch=branch, node_id=raw['node_id'], workspace_id=raw['workspace_id'],
                   world_revision=expected_world_revision, contribution_digest=raw['result_hash'],
                   observation=declaration, source_refs=refs, snapshots=snapshots, origin_event_ids=events,
                   request_id=request_id)
        self._save('learning_outcomes', row)
        receipt = dict(learning_interface=LEARNING_INTERFACE, outcome_id=row['outcome_id'], digest=row['digest'],
                       contribution_id=contribution_id, branch=branch, node_id=row['node_id'],
                       status=declaration['status'], judgment_limit=JUDGMENT_LIMIT, replayed=False)
        self._event('outcome', row['outcome_id'], branch, payload, receipt)
        return receipt

    def _outcome_view(self, row, viewer, _seen=None):
        row = _decode(row)
        contribution = self._contribution(row['branch'], row['contribution_id'], viewer, _seen=_seen)
        require(contribution['raw']['result_hash'] == row['contribution_digest'], 'outcome contribution mismatch')
        permitted = self._permitted(row['branch'], viewer)
        fresh = True
        for ref, snapshot in zip(row['source_refs'], row['snapshots']):
            current = permitted.get(ref['id'])
            require(current and current['domain'] == ref['domain'] and self.engine._visible(snapshot, viewer), 'outcome unavailable')
            if current['version'] != ref['record_revision'] or digest(self.engine.get(row['branch'], ref['id'])) != ref['snapshot_hash']:
                fresh = False
        snapshots = {s['id']: s for s in row['snapshots']}
        for item in row['observation']['measurements']:
            snapshot = snapshots[item['evidence']['source_ref']['id']]
            require(self._measurement_visible(row, item, snapshot, permitted, viewer), 'outcome unavailable')
        row.pop('snapshots'); row.pop('request_id')
        if viewer is not None:
            # This explanation is owner provenance, unlike the lesson's
            # explicitly published rationale. It is not a public claim source.
            row['observation'].pop('rationale', None)
        row['source_fresh'] = fresh
        row['origin_contribution_ids'] = [row['contribution_id']]
        row['judgment_limit'] = JUDGMENT_LIMIT
        return row

    @_atomic
    def read_outcome(self, branch, outcome_id, viewer=None):
        self._installed(); text(outcome_id, 'outcome id')
        row = self.db.execute('SELECT * FROM learning_outcomes WHERE branch=? AND outcome_id=?', (branch, outcome_id)).fetchone()
        require(row is not None, 'outcome unavailable')
        return self._outcome_view(row, viewer)

    @_atomic
    def list_outcomes(self, branch, character_id, viewer=None):
        self._installed()
        node = Nodes(self.engine).read(branch, character_id, viewer=viewer)
        result = []
        for row in self.db.execute('SELECT * FROM learning_outcomes WHERE branch=? AND node_id=? ORDER BY outcome_id', (branch, node['node_id'])):
            try:
                result.append(self._outcome_view(row, viewer))
            except Rejected:
                continue
        return result

    def _latest(self, branch, lesson_id, lesson_revision=None):
        sql = 'SELECT * FROM lesson_revisions WHERE branch=? AND lesson_id=?'
        args = [branch, lesson_id]
        if lesson_revision is not None:
            integer(lesson_revision, 'lesson revision'); sql += ' AND revision=?'; args.append(lesson_revision)
        row = self.db.execute(sql + ' ORDER BY revision DESC LIMIT 1', args).fetchone()
        require(row is not None, 'lesson unavailable')
        return _decode(row)

    def _latest_review(self, lesson_id, lesson_revision):
        row = self.db.execute('SELECT * FROM lesson_reviews WHERE lesson_id=? AND lesson_revision=? ORDER BY review_revision DESC LIMIT 1',
                              (lesson_id, lesson_revision)).fetchone()
        return _decode(row) if row else None

    def _known_counters(self, lesson_id):
        result = set()
        for table in ('lesson_revisions', 'lesson_reviews'):
            for row in self.db.execute('SELECT counter_outcome_ids_json FROM ' + table + ' WHERE lesson_id=?', (lesson_id,)):
                result.update(json.loads(row[0]))
        return sorted(result)

    def _evidence(self, branch, node_id, workspace_id, definition, outcome_ids, counter_ids, viewer=None, require_fresh=False):
        supports, counters = [], []
        for ids, destination, supportive in ((outcome_ids, supports, True), (counter_ids, counters, False)):
            for oid in ids:
                outcome = self.read_outcome(branch, oid, viewer=viewer)
                require(outcome['node_id'] == node_id and outcome['workspace_id'] == workspace_id, 'outcome belongs to another node or workspace')
                contribution = self._contribution(branch, outcome['contribution_id'], viewer=viewer)
                used = contribution['result'].get('binding', {}).get('methods', [])
                require(contribution['result']['phase'] == 'completed'
                        and any(m['method_id'] == definition['method_id'] and m['revision'] == definition['method_revision'] for m in used),
                        'lesson needs a completed contribution using the pinned method')
                task = contribution['request']['task']
                require(task['domain'] == definition['task_domain'], 'outcome task domain mismatch')
                if supportive:
                    require(context_matches(definition['context_conditions'], context(task.get('context', {}))),
                            'lesson conditions exceed or differ from observed task context')
                    if require_fresh:
                        require(outcome['source_fresh'], 'lesson support observation requires revalidation')
                        require(outcome['observation']['status'] != 'unknown', 'unknown outcome cannot qualify a lesson')
                destination.append(outcome)
        return supports, counters

    def _evidence_digest(self, supports, counters):
        return digest({'supports': sorted((o['outcome_id'], o['digest']) for o in supports),
                       'counters': sorted((o['outcome_id'], o['digest']) for o in counters)})

    def propose(self, branch, node_id, request_id, expected_world_revision, lesson, outcome_ids, viewer=None, workspace_id=None):
        return self._write_lesson(branch, node_id, request_id, expected_world_revision, lesson, outcome_ids,
                                  viewer, workspace_id, None, None)

    def revise(self, branch, node_id, lesson_id, expected_lesson_revision, request_id, expected_world_revision,
               lesson, outcome_ids, viewer=None, workspace_id=None):
        text(lesson_id, 'lesson id'); integer(expected_lesson_revision, 'expected lesson revision')
        return self._write_lesson(branch, node_id, request_id, expected_world_revision, lesson, outcome_ids,
                                  viewer, workspace_id, lesson_id, expected_lesson_revision)

    @_atomic
    def _write_lesson(self, branch, node_id, request_id, expected_world_revision, lesson, outcome_ids,
                       viewer, workspace_id, lesson_id, expected_lesson_revision):
        self._owner(viewer, request_id, expected_world_revision, branch)
        text(node_id, 'node id'); definition = lesson_definition(lesson)
        strings(outcome_ids, 'outcome ids', nonempty=True); outcome_ids = sorted(outcome_ids)
        workspace_id = workspace_id or 'world:' + branch
        payload = dict(branch=branch, node_id=node_id, request_id=request_id, expected_world_revision=expected_world_revision,
                       lesson=definition, outcome_ids=outcome_ids, workspace_id=workspace_id,
                       lesson_id=lesson_id, expected_lesson_revision=expected_lesson_revision)
        replay = self._replay(request_id, payload)
        if replay is not None:
            return replay
        require(self.engine.branch(branch)['revision'] == expected_world_revision, 'stale branch revision')
        method = self.methods.read(branch, definition['method_id'], definition['method_revision'], workspace_id=workspace_id)
        require(method['node_id'] == node_id and definition['task_domain'] in method['definition']['domains'], 'lesson method scope mismatch')
        operation = dict(kind=method['definition']['operation']['kind'], params=definition['operation_params'])
        require(operation['kind'] in operations.SUPPORTED, 'lesson intervention must use a registered operation')
        operations.validate_operation(operation)
        require(definition['operation_params'] != method['definition']['operation']['params'], 'lesson intervention does not change the method operation')
        visible = self._permitted(branch, None)
        for actor in definition['audience']:
            require(actor in visible and visible[actor]['domain'] == 'character', 'lesson audience unavailable')
        prior, counters, revision = None, [], 1
        if lesson_id is not None:
            prior = self._latest(branch, lesson_id)
            require(prior['revision'] == expected_lesson_revision, 'stale lesson revision')
            require(prior['node_id'] == node_id and prior['workspace_id'] == workspace_id, 'lesson belongs to another node or workspace')
            # A lesson keeps its method lineage; changing the base belongs to a new lesson.
            require(all(prior['definition'][key] == definition[key] for key in ('method_id', 'method_revision', 'task_domain')), 'lesson base method or domain cannot change')
            revision = prior['revision'] + 1
            counters = self._known_counters(lesson_id)
        supports, counter_evidence = self._evidence(branch, node_id, workspace_id, definition, outcome_ids, counters)
        row = dict(lesson_id=lesson_id or 'lesson:' + uuid4().hex, revision=revision, node_id=node_id,
                   branch=branch, workspace_id=workspace_id, world_revision=expected_world_revision,
                   definition=definition, method_digest=method['digest'], outcome_ids=outcome_ids,
                   counter_outcome_ids=counters, evidence_digest=self._evidence_digest(supports, counter_evidence),
                   prior_digest=prior['digest'] if prior else None, request_id=request_id)
        self._save('lesson_revisions', row)
        receipt = dict(learning_interface=LEARNING_INTERFACE, lesson_id=row['lesson_id'], revision=revision,
                       digest=row['digest'], node_id=node_id, branch=branch, status='proposed', replayed=False)
        self._event('revised' if prior else 'proposed', row['lesson_id'], branch, payload, receipt)
        return receipt

    def _response_to_contest(self, lesson, supports):
        prior_contest = self.db.execute('''SELECT r.lesson_revision FROM lesson_reviews r
            WHERE r.lesson_id=? AND r.status='contested' AND r.lesson_revision<?
            ORDER BY r.lesson_revision DESC,r.review_revision DESC LIMIT 1''', (lesson['lesson_id'], lesson['revision'])).fetchone()
        if not prior_contest:
            return
        prior = self._latest(lesson['branch'], lesson['lesson_id'], prior_contest['lesson_revision'])
        changed = any(lesson['definition'][key] != prior['definition'][key] for key in ('operation_params', 'context_conditions'))
        if not changed:
            old_origins = {self.read_outcome(lesson['branch'], oid)['contribution_id']
                           for oid in prior['outcome_ids'] + self._known_counters(lesson['lesson_id'])}
            new_origins = {o['contribution_id'] for o in supports} - old_origins
            require(bool(new_origins), 'contested lesson needs a changed intervention or context, or a new completed trial origin')

    @_atomic
    def review(self, branch, lesson_id, lesson_revision, request_id, expected_world_revision, status, rationale,
               expected_review_revision=0, counter_outcome_ids=None, viewer=None):
        self._owner(viewer, request_id, expected_world_revision, branch)
        text(lesson_id, 'lesson id'); integer(lesson_revision, 'lesson revision')
        integer(expected_review_revision, 'expected review revision', 0); text(rationale, 'review rationale')
        require(status in REVIEW_STATES, 'invalid lesson review status')
        counters = [] if counter_outcome_ids is None else counter_outcome_ids
        strings(counters, 'counter outcome ids')
        counters = sorted(counters)
        require(not counters or status == 'contested', 'counterevidence must suspend influence')
        payload = dict(branch=branch, lesson_id=lesson_id, lesson_revision=lesson_revision, request_id=request_id,
                       expected_world_revision=expected_world_revision, status=status, rationale=rationale,
                       expected_review_revision=expected_review_revision, counter_outcome_ids=counters)
        replay = self._replay(request_id, payload)
        if replay is not None:
            return replay
        require(self.engine.branch(branch)['revision'] == expected_world_revision, 'stale branch revision')
        lesson = self._latest(branch, lesson_id)
        require(lesson['revision'] == lesson_revision, 'review requires current lesson revision')
        previous = self._latest_review(lesson_id, lesson_revision)
        require((previous['review_revision'] if previous else 0) == expected_review_revision, 'stale review revision')
        if status == 'qualified':
            require(not self.db.execute("SELECT 1 FROM lesson_reviews WHERE lesson_id=? AND lesson_revision=? AND status IN ('contested','retired')", (lesson_id, lesson_revision)).fetchone(),
                    'contested or retired lesson requires a new revision')
        combined_counters = sorted(set(lesson['counter_outcome_ids']) | set(counters) | set(previous['counter_outcome_ids'] if previous else []))
        definition = lesson['definition']
        supports, counter_evidence = self._evidence(branch, lesson['node_id'], lesson['workspace_id'], definition,
                                                    lesson['outcome_ids'], combined_counters, require_fresh=status == 'qualified')
        method = self.methods.read(branch, definition['method_id'], definition['method_revision'], workspace_id=lesson['workspace_id'])
        if status == 'qualified':
            require(method['source_fresh'] and method['qualification'] == 'experimental', 'lesson requires a current experimental method assignment')
            require(method['digest'] == lesson['method_digest'], 'lesson base method digest mismatch')
            self._response_to_contest(lesson, supports)
        row = dict(lesson_id=lesson_id, lesson_revision=lesson_revision, review_revision=expected_review_revision + 1,
                   status=status, rationale=rationale, world_revision=expected_world_revision, lesson_digest=lesson['digest'],
                   method_assignment_revision=method['assignment_revision'], method_assignment_digest=method['assignment_digest'],
                   counter_outcome_ids=combined_counters, evidence_digest=self._evidence_digest(supports, counter_evidence),
                   prior_digest=previous['digest'] if previous else None, request_id=request_id)
        self._save('lesson_reviews', row)
        receipt = dict(learning_interface=LEARNING_INTERFACE, lesson_id=lesson_id, revision=lesson_revision,
                       review_revision=row['review_revision'], review_digest=row['digest'], status=status,
                       branch=branch, judgment_limit=JUDGMENT_LIMIT, replayed=False)
        self._event('reviewed', lesson_id, branch, payload, receipt)
        return receipt

    def _lesson_view(self, lesson, viewer):
        definition = lesson['definition']
        require(self.engine._visible(definition, viewer), 'lesson unavailable')
        method = self.methods.read(lesson['branch'], definition['method_id'], definition['method_revision'],
                                   viewer=viewer, workspace_id=lesson['workspace_id'])
        review = self._latest_review(lesson['lesson_id'], lesson['revision'])
        counter_ids = sorted(set(lesson['counter_outcome_ids']) | set(review['counter_outcome_ids'] if review else []))
        supports, counters = self._evidence(lesson['branch'], lesson['node_id'], lesson['workspace_id'], definition,
                                            lesson['outcome_ids'], counter_ids, viewer=viewer)
        refs = {encoded(ref): ref for o in supports for ref in o['source_refs']}
        history = {encoded(ref): ref for o in counters for ref in o['source_refs']}
        result = {k: deepcopy(v) for k, v in lesson.items() if k not in ('prior_digest', 'request_id')}
        if viewer is not None:
            result['definition'].pop('audience', None)
        result.update(status=review['status'] if review else 'proposed', review_revision=review['review_revision'] if review else 0,
                      review_digest=review['digest'] if review else None,
                      method_assignment_revision=review['method_assignment_revision'] if review else None,
                      method_assignment_digest=review['method_assignment_digest'] if review else None,
                      source_refs=[refs[k] for k in sorted(refs)], historical_source_refs=[history[k] for k in sorted(history)],
                      counter_outcome_ids=counter_ids,
                      origin_contribution_ids=sorted({o['contribution_id'] for o in supports + counters}),
                      origin_event_ids=sorted({e for o in supports + counters for e in o['origin_event_ids']}),
                      source_fresh=method['source_fresh'] and all(o['source_fresh'] for o in supports),
                      assignment_current=bool(review and method['qualification'] == 'experimental'
                          and method['assignment_revision'] == review['method_assignment_revision']
                          and method['assignment_digest'] == review['method_assignment_digest']),
                      judgment_limit=JUDGMENT_LIMIT,
                      intervention=dict(method_id=definition['method_id'], method_revision=definition['method_revision'],
                                        operation_params=deepcopy(definition['operation_params'])))
        result['qualification'] = result['status']
        result['evidence_digest'] = review['evidence_digest'] if review else lesson['evidence_digest']
        return result

    @_atomic
    def read(self, branch, lesson_id, lesson_revision=None, viewer=None, workspace_id=None):
        self._installed(); text(lesson_id, 'lesson id')
        lesson = self._latest(branch, lesson_id, lesson_revision)
        require(workspace_id is None or workspace_id == lesson['workspace_id'], 'lesson unavailable')
        return self._lesson_view(lesson, viewer)

    @_atomic
    def list(self, branch, character_id, viewer=None, workspace_id=None):
        self._installed()
        node = Nodes(self.engine).read(branch, character_id, viewer=viewer)
        workspace_id = workspace_id or node['workspace_id']
        require(workspace_id == node['workspace_id'], 'workspace unavailable')
        result = []
        for raw in self.db.execute('''SELECT l.* FROM lesson_revisions l WHERE branch=? AND node_id=? AND workspace_id=?
            AND revision=(SELECT MAX(p.revision) FROM lesson_revisions p WHERE p.lesson_id=l.lesson_id) ORDER BY lesson_id''',
            (branch, node['node_id'], workspace_id)):
            try:
                result.append(self._lesson_view(_decode(raw), viewer))
            except Rejected:
                continue
        return result

    @_atomic
    def applicable(self, branch, character_id, task_domain, context, methods, viewer=None, workspace_id=None):
        from .learning_contracts import context as validate_context
        checked_context = validate_context(context)
        available = {(m['method_id'], m['revision']): m for m in methods}
        result = []
        for lesson in self.list(branch, character_id, viewer=viewer, workspace_id=workspace_id):
            definition = lesson['definition']
            method = available.get((definition['method_id'], definition['method_revision']))
            if (lesson['status'] == 'qualified' and lesson['source_fresh'] and lesson['assignment_current']
                    and definition['task_domain'] == task_domain and context_matches(definition['context_conditions'], checked_context)
                    and method and method['digest'] == lesson['method_digest']
                    and method['assignment_revision'] == lesson['method_assignment_revision']):
                result.append(lesson)
        return result


def verify_learning(engine):
    db = engine.db
    installed = db.execute("SELECT version FROM engine_versions WHERE component='learning_interface'").fetchone()
    if not installed:
        return {'installed': False}
    require(installed[0] == LEARNING_INTERFACE, 'unsupported learning interface')
    path = schema_path('migration_012.sql')
    check = db.execute('SELECT checksum FROM migration_checks WHERE version=12').fetchone()
    require(check and check[0] == hashlib.sha256(path.read_bytes()).hexdigest(), 'learning migration checksum mismatch')
    service, expected = Learning(engine), {}
    counts = {}
    previous_lessons, previous_reviews = {}, {}
    for table in ('learning_outcomes', 'lesson_revisions', 'lesson_reviews'):
        count = 0
        ordering = 'outcome_id' if table == 'learning_outcomes' else 'lesson_id,revision' if table == 'lesson_revisions' else 'lesson_id,lesson_revision,review_revision'
        for raw in db.execute('SELECT * FROM ' + table + ' ORDER BY ' + ordering):
            row = _decode(raw)
            require(digest(_content(row)) == row['digest'], 'learning content digest mismatch')
            require(row['request_id'] not in expected, 'duplicate learning request')
            if table == 'learning_outcomes':
                require(observation(row['observation']) == row['observation'], 'observation contract mismatch')
                contribution = service._contribution(row['branch'], row['contribution_id'])
                require(row['contribution_digest'] == contribution['raw']['result_hash']
                        and all(row[k] == contribution['raw'][k] for k in ('branch', 'node_id', 'workspace_id')), 'outcome contribution scope mismatch')
                require(len(row['source_refs']) == len(row['snapshots']), 'outcome snapshot count mismatch')
                sources = {}
                for ref, snapshot in zip(row['source_refs'], row['snapshots']):
                    require(snapshot['id'] == ref['id'] and snapshot['domain'] == ref['domain']
                            and snapshot['version'] == ref['record_revision'] and digest(snapshot) == ref['snapshot_hash'], 'outcome snapshot mismatch')
                    _source_origin(engine, row['branch'], row['world_revision'], snapshot)
                    event = db.execute('SELECT branch,revision FROM events WHERE id=?', (snapshot['updated_event'],)).fetchone()
                    require(event['branch'] == row['branch'] and event['revision'] > contribution['result']['binding']['world_revision'], 'outcome observation predates contribution')
                    sources[ref['id']] = snapshot
                require(sorted({s['updated_event'] for s in row['snapshots']}) == row['origin_event_ids'], 'outcome origin event mismatch')
                for item in row['observation']['measurements']:
                    ref = item['evidence']['source_ref']; snapshot = sources.get(ref['id'])
                    require(snapshot and digest(snapshot) == ref['snapshot_hash'], 'outcome measurement reference mismatch')
                    found, actual = _path(snapshot, item['evidence']['field_path'])
                    require(found and scalar(actual) and equal(actual, item['value']), 'outcome measurement value mismatch')
                object_id, kind, branch = row['outcome_id'], 'outcome', row['branch']
            elif table == 'lesson_revisions':
                require(lesson_definition(row['definition']) == row['definition'], 'lesson contract mismatch')
                prior = previous_lessons.get(row['lesson_id'])
                require(row['revision'] == (prior['revision'] + 1 if prior else 1)
                        and row['prior_digest'] == (prior['digest'] if prior else None), 'lesson revision chain mismatch')
                if prior:
                    require(all(row[k] == prior[k] for k in ('node_id', 'branch', 'workspace_id')), 'lesson scope changed')
                supports, counters = service._evidence(row['branch'], row['node_id'], row['workspace_id'], row['definition'], row['outcome_ids'], row['counter_outcome_ids'])
                require(service._evidence_digest(supports, counters) == row['evidence_digest'], 'lesson evidence digest mismatch')
                method = db.execute('SELECT digest FROM method_revisions WHERE method_id=? AND revision=?',
                                    (row['definition']['method_id'], row['definition']['method_revision'])).fetchone()
                require(method and method[0] == row['method_digest'], 'lesson method digest mismatch')
                previous_lessons[row['lesson_id']] = row
                object_id, kind, branch = row['lesson_id'], 'revised' if prior else 'proposed', row['branch']
            else:
                key = (row['lesson_id'], row['lesson_revision']); prior = previous_reviews.get(key)
                require(row['review_revision'] == (prior['review_revision'] + 1 if prior else 1)
                        and row['prior_digest'] == (prior['digest'] if prior else None), 'review revision chain mismatch')
                lesson = service._latest(service.db.execute('SELECT branch FROM lesson_revisions WHERE lesson_id=? AND revision=?', key).fetchone()[0], *key)
                require(row['lesson_digest'] == lesson['digest'], 'review lesson digest mismatch')
                supports, counters = service._evidence(lesson['branch'], lesson['node_id'], lesson['workspace_id'], lesson['definition'], lesson['outcome_ids'], row['counter_outcome_ids'])
                require(row['evidence_digest'] == service._evidence_digest(supports, counters), 'review evidence digest mismatch')
                if row['method_assignment_revision']:
                    assignment = db.execute('SELECT digest FROM node_method_assignments WHERE node_id=? AND method_id=? AND workspace_id=? AND assignment_revision=?',
                                            (lesson['node_id'], lesson['definition']['method_id'], lesson['workspace_id'], row['method_assignment_revision'])).fetchone()
                    require(assignment and assignment[0] == row['method_assignment_digest'], 'review method assignment mismatch')
                previous_reviews[key] = row
                object_id, kind, branch = row['lesson_id'], 'reviewed', lesson['branch']
            expected[row['request_id']] = (object_id, kind, branch, row)
            count += 1
        counts[table] = count
    events = list(db.execute('SELECT * FROM learning_events ORDER BY sequence'))
    require(len(events) == len(expected), 'learning event count mismatch')
    for event in events:
        require(event['request_id'] in expected, 'orphan learning event')
        object_id, kind, branch, row = expected[event['request_id']]
        payload, receipt = json.loads(event['payload_json']), json.loads(event['receipt_json'])
        require(digest(payload) == event['payload_hash'] and payload['request_id'] == event['request_id'], 'learning event payload mismatch')
        require(event['kind'] == kind and event['object_id'] == object_id and event['branch'] == branch == payload['branch'] == receipt['branch'], 'learning event identity mismatch')
        require(payload['expected_world_revision'] == row['world_revision'], 'learning event world revision mismatch')
        require(receipt['learning_interface'] == LEARNING_INTERFACE and receipt['replayed'] is False, 'learning event interface mismatch')
        if kind == 'outcome':
            require(receipt['outcome_id'] == object_id and receipt['digest'] == row['digest']
                    and payload['observation'] == row['observation'] and payload['contribution_id'] == row['contribution_id'], 'outcome event mismatch')
        elif kind == 'reviewed':
            require(receipt['lesson_id'] == object_id and receipt['review_digest'] == row['digest']
                    and receipt['review_revision'] == row['review_revision'] and payload['status'] == row['status']
                    and payload['rationale'] == row['rationale'], 'review event mismatch')
        else:
            require(receipt['lesson_id'] == object_id and receipt['digest'] == row['digest']
                    and receipt['revision'] == row['revision'] and payload['lesson'] == row['definition']
                    and payload['outcome_ids'] == row['outcome_ids'], 'lesson event mismatch')
    return dict(installed=True, interface=LEARNING_INTERFACE, **counts)
