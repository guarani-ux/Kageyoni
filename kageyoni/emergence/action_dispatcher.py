"""Issued participant requests linked to existing encounter execution.

The caller is a trusted runtime/operator. Request issuance binds perspective,
branch, permitted actions, and revision; it is not operating-system isolation
or authentication of a model host. Domain effects remain owned by Encounters.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
import json

from kageyoni.engine import Engine, Rejected, digest, encoded, require
from kageyoni.workspaces.world import Encounters
from kageyoni.ledger import EvidenceLedger
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.persistence.migrations import install_action_dispatch

encode_json = encoded


@dataclass
class LinkedExecutionRecord:
    request_id: str
    request_digest: str
    reply_digest: str
    participant_id: str
    encounter_id: str
    proposed_action: Dict[str, Any]
    governing_ref: str
    validation_status: str
    rejection_reason: Optional[str] = None
    rejection_class: Optional[str] = None
    engine_receipt: Optional[Dict[str, Any]] = None
    revision_before: int = 0
    revision_after: int = 0
    created_at: str = ''
    branch: str = 'main'

    def to_dict(self):
        return asdict(self)


def ensure_dispatch_table(db):
    # Legacy audit format remains readable; issued requests own retry identity.
    with UnitOfWork(db):
        db.execute('''CREATE TABLE IF NOT EXISTS shinobi_action_dispatches (
            dispatch_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
            request_digest TEXT NOT NULL, reply_digest TEXT NOT NULL,
            participant_id TEXT NOT NULL, encounter_id TEXT NOT NULL,
            action_id TEXT, governing_ref TEXT NOT NULL, validation_status TEXT NOT NULL,
            rejection_reason TEXT, rejection_class TEXT, engine_receipt_json TEXT,
            revision_before INTEGER NOT NULL, revision_after INTEGER NOT NULL,
            created_at TEXT NOT NULL)''')


class EncounterActionDispatcher:
    def __init__(self, engine: Engine, encounters: Encounters):
        self.engine, self.encounters, self.db = engine, encounters, engine.db
        install_action_dispatch(engine)
        ensure_dispatch_table(self.db)
        self.ledger = EvidenceLedger(self.db)

    def prepare(self, branch, encounter_id, participant_id, request_id=None):
        """Issue a permitted observation; no host decision or world mutation."""
        request_id = request_id or 'turn:' + uuid4().hex
        require(isinstance(request_id, str) and request_id, 'request ID required')
        require(isinstance(participant_id, str) and participant_id, 'participant required')
        with UnitOfWork(self.db):
            prior = self.db.execute('SELECT request_json FROM shinobi_action_requests WHERE branch=? AND request_id=?', (branch, request_id)).fetchone()
            if prior:
                request = json.loads(prior[0])
                require(request['encounter_id'] == encounter_id and request['participant']['character_id'] == participant_id, 'request ID reused with changed binding')
                return request
            observation = self.encounters.inspect(branch, encounter_id, viewer=participant_id)
            request = dict(request_id=request_id, branch=branch, encounter_id=encounter_id,
                           participant={'character_id': participant_id},
                           expected_revision=self.engine.branch(branch)['revision'],
                           observation=observation,
                           authority={'actions': [a['action_id'] for a in observation['next_actions']]})
            request['request_hash'] = digest(request)
            self.db.execute('INSERT INTO shinobi_action_requests(branch,request_id,request_hash,request_json) VALUES(?,?,?,?)', (branch, request_id, request['request_hash'], encoded(request)))
            return request

    def dispatch(self, branch, encounter_id, request, reply, viewer=None,
                 expected_revision=None, dispatch_request_id=None):
        """Validate an issued request and commit effect plus required history."""
        require(isinstance(request, dict) and isinstance(reply, dict), 'request and reply must be objects')
        request_id = request.get('request_id')
        with UnitOfWork(self.db):
            row = self.db.execute('SELECT * FROM shinobi_action_requests WHERE branch=? AND request_id=?', (branch, request_id)).fetchone()
            require(row is not None, 'unknown issued request')
            issued = json.loads(row['request_json'])
            require(digest(request) == digest(issued), 'issued request was altered')
            actor = issued['participant']['character_id']
            require(issued['encounter_id'] == encounter_id, 'encounter binding mismatch')
            require(viewer is None or viewer == actor, 'participant binding mismatch')
            require(dispatch_request_id is None or dispatch_request_id == request_id, 'dispatch request ID differs from issued request')
            require(reply.get('request_hash') == issued['request_hash'] and reply.get('encounter_id') == encounter_id, 'reply does not acknowledge issued request')
            reply_hash = digest(reply)
            if row['result_json']:
                require(row['reply_digest'] == reply_hash, 'request ID reused with changed reply')
                record = LinkedExecutionRecord(**json.loads(row['result_json']))
                if record.validation_status in ('ACCEPTED', 'WAITING'):
                    record.validation_status = 'REPLAY_IDEMPOTENT'
                return record
            before = self.engine.branch(branch)['revision']
            action = reply.get('action', {})
            record = LinkedExecutionRecord(request_id, issued['request_hash'], reply_hash,
                actor, encounter_id, action, 'encounter:' + encounter_id, 'REJECTED',
                revision_before=before, revision_after=before,
                created_at=datetime.now(timezone.utc).isoformat(), branch=branch)
            try:
                require(isinstance(action, dict), 'action must be an object')
                kind = action.get('kind')
                require(kind in ('none', 'propose_action'), 'unsupported action kind')
                if kind == 'none':
                    require(set(action) == {'kind'}, 'invalid none action')
                    record.validation_status = 'SKIPPED_NONE'
                else:
                    require(set(action) <= {'kind','action_id','fields','payload','rationale'}, 'unknown action fields')
                    action_id = action.get('action_id')
                    require(action_id in issued['authority']['actions'], 'action unavailable in issued perspective')
                    require(not ('fields' in action and 'payload' in action), 'ambiguous action fields')
                    fields = action.get('fields', action.get('payload', {}))
                    require(isinstance(fields, dict), 'action fields must be an object')
                    require(expected_revision is None or expected_revision == issued['expected_revision'], 'stale branch revision: expected revision differs from issued request')
                    # A nested savepoint prevents partial effects on Rejected.
                    with UnitOfWork(self.db):
                        receipt = self.encounters.act(branch=branch, encounter_id=encounter_id,
                            action_id=action_id, request_id='dispatch:' + request_id,
                            expected_revision=issued['expected_revision'], fields=fields, viewer=actor)
                    record.engine_receipt = receipt
                    record.validation_status = 'WAITING' if receipt.get('phase') == 'waiting' else 'ACCEPTED'
                    record.revision_after = self.engine.branch(branch)['revision']
            except Rejected as error:
                record.rejection_reason = str(error)
                record.rejection_class = error.rejection_class
            self._persist_record(record)
            self.db.execute('UPDATE shinobi_action_requests SET reply_digest=?,result_json=? WHERE branch=? AND request_id=?', (reply_hash, encoded(record.to_dict()), branch, request_id))
            return record

    def _persist_record(self, record):
        self.db.execute('''INSERT INTO shinobi_action_dispatches VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            'disp:' + digest({'branch': record.branch, 'request_id': record.request_id}),
            record.request_id, record.request_digest, record.reply_digest,
            record.participant_id, record.encounter_id,
            record.proposed_action.get('action_id') if isinstance(record.proposed_action, dict) else None,
            record.governing_ref, record.validation_status,
            record.rejection_reason, record.rejection_class,
            encoded(record.engine_receipt) if record.engine_receipt else None,
            record.revision_before, record.revision_after, record.created_at))
        self.ledger.record(kind='dispatch', actor_id=record.participant_id,
                           topic=record.governing_ref, payload=record.to_dict(),
                           event_id='dispatch:' + digest({'branch': record.branch, 'request_id': record.request_id}))
