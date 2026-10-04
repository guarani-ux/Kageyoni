"""
Generic Action Dispatcher for Constellation Emergence.

Binds cognitive participant replies to authoritative engine operations via Encounters.act().
Enforces:
1. Participant proposals do NOT grant authority; engine verifies permissions, visibility, prerequisites, and revisions at execution time.
2. Persists a single, durable LinkedExecutionRecord uniting:
   - request ID & digest
   - reply digest & participant binding
   - proposed action & governing authorization reference
   - validation status (ACCEPTED, REJECTED, WAITING, SKIPPED)
   - engine receipt & revision deltas
3. Cryptographically chains all dispatches into kageyoni.ledger.EvidenceLedger.
4. Idempotent retries and distinct outcomes for dialogue vs action execution.
"""

from __future__ import annotations
from dataclasses import asdict, dataclass
import datetime
import hashlib
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.workspaces.world import Encounters
from kageyoni.ledger import EvidenceLedger, EvidenceRecord


def encode_json(val: Any) -> str:
    return json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass
class LinkedExecutionRecord:
    request_id: str
    request_digest: str
    reply_digest: str
    participant_id: str
    encounter_id: str
    proposed_action: Dict[str, Any]
    governing_ref: str
    validation_status: str  # ACCEPTED | REJECTED | WAITING | SKIPPED_NONE | REPLAY_IDEMPOTENT
    rejection_reason: Optional[str] = None
    rejection_class: Optional[str] = None
    engine_receipt: Optional[Dict[str, Any]] = None
    revision_before: int = 0
    revision_after: int = 0
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def ensure_dispatch_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS shinobi_action_dispatches (
            dispatch_id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL,
            request_digest TEXT NOT NULL,
            reply_digest TEXT NOT NULL,
            participant_id TEXT NOT NULL,
            encounter_id TEXT NOT NULL,
            action_id TEXT,
            governing_ref TEXT NOT NULL,
            validation_status TEXT NOT NULL,
            rejection_reason TEXT,
            rejection_class TEXT,
            engine_receipt_json TEXT,
            revision_before INTEGER NOT NULL,
            revision_after INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    db.commit()


class EncounterActionDispatcher:
    def __init__(self, engine: Engine, encounters: Encounters):
        self.engine = engine
        self.encounters = encounters
        self.db = engine.db
        ensure_dispatch_table(self.db)
        self.ledger = EvidenceLedger(self.db)

    def dispatch(
        self,
        branch: str,
        encounter_id: str,
        request: Dict[str, Any],
        reply: Dict[str, Any],
        viewer: Optional[str] = None,
        expected_revision: Optional[int] = None,
        dispatch_request_id: Optional[str] = None
    ) -> LinkedExecutionRecord:
        """
        Dispatches a participant's reply through the authoritative Encounters.act() boundary.
        Checks current actor binding, visibility, prerequisites, and revisions at execution time.
        """
        req_id = request.get("encounter_id", encounter_id)
        req_hash = request.get("request_hash", digest(request))
        rep_hash = digest(reply)
        actor = viewer or request.get("participant", {}).get("character_id") or "unknown"
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        rev_before = self.engine.branch(branch)["revision"]
        exp_rev = expected_revision if expected_revision is not None else rev_before

        action_payload = reply.get("action", {})
        action_kind = action_payload.get("kind", "none")
        governing_ref = f"encounter:{encounter_id}"

        # 1. Dialogue-only turn (action.kind == 'none')
        if action_kind == "none":
            record = LinkedExecutionRecord(
                request_id=req_id,
                request_digest=req_hash,
                reply_digest=rep_hash,
                participant_id=actor,
                encounter_id=encounter_id,
                proposed_action=action_payload,
                governing_ref=governing_ref,
                validation_status="SKIPPED_NONE",
                revision_before=rev_before,
                revision_after=rev_before,
                created_at=created_at
            )
            self._persist_record(record)
            return record

        # 2. Action proposal
        action_id = action_payload.get("action_id")
        action_fields = action_payload.get("fields", {})

        # Determine dispatch request ID for idempotence
        act_req_id = dispatch_request_id or f"dispatch:{encounter_id}:{actor}:{action_id}"

        # If this exact request was previously dispatched, match the original expected revision for idempotent replay
        old_disp = self.db.execute("SELECT revision_before FROM shinobi_action_dispatches WHERE request_id=?", (act_req_id,)).fetchone()
        if old_disp and expected_revision is None:
            exp_rev = old_disp[0]

        try:
            receipt = self.encounters.act(
                branch=branch,
                encounter_id=encounter_id,
                action_id=action_id,
                request_id=act_req_id,
                expected_revision=exp_rev,
                fields=action_fields,
                viewer=actor
            )
            rev_after = self.engine.branch(branch)["revision"]
            
            # Check if this was an inquiry transition (waiting)
            phase = receipt.get("phase")
            if phase == "waiting":
                status = "WAITING"
            elif receipt.get("replayed"):
                status = "REPLAY_IDEMPOTENT"
            else:
                status = "ACCEPTED"

            record = LinkedExecutionRecord(
                request_id=act_req_id,
                request_digest=req_hash,
                reply_digest=rep_hash,
                participant_id=actor,
                encounter_id=encounter_id,
                proposed_action=action_payload,
                governing_ref=governing_ref,
                validation_status=status,
                engine_receipt=receipt,
                revision_before=rev_before,
                revision_after=rev_after,
                created_at=created_at
            )
            self._persist_record(record)
            return record

        except Rejected as rej:
            rev_after = self.engine.branch(branch)["revision"]
            record = LinkedExecutionRecord(
                request_id=act_req_id,
                request_digest=req_hash,
                reply_digest=rep_hash,
                participant_id=actor,
                encounter_id=encounter_id,
                proposed_action=action_payload,
                governing_ref=governing_ref,
                validation_status="REJECTED",
                rejection_reason=str(rej),
                rejection_class=getattr(rej, "rejection_class", "REJECTED"),
                revision_before=rev_before,
                revision_after=rev_after,
                created_at=created_at
            )
            self._persist_record(record)
            return record

    def _persist_record(self, record: LinkedExecutionRecord) -> None:
        rec_id = f"disp:{uuid4().hex[:12]}"
        self.db.execute("""
            INSERT OR REPLACE INTO shinobi_action_dispatches (
                dispatch_id, request_id, request_digest, reply_digest, participant_id,
                encounter_id, action_id, governing_ref, validation_status,
                rejection_reason, rejection_class, engine_receipt_json,
                revision_before, revision_after, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rec_id,
            record.request_id,
            record.request_digest,
            record.reply_digest,
            record.participant_id,
            record.encounter_id,
            record.proposed_action.get("action_id"),
            record.governing_ref,
            record.validation_status,
            record.rejection_reason,
            record.rejection_class,
            encode_json(record.engine_receipt) if record.engine_receipt else None,
            record.revision_before,
            record.revision_after,
            record.created_at
        ))
        self.db.commit()

        # Cryptographically chain into EvidenceLedger
        self.ledger.record(
            kind="dispatch",
            actor_id=record.participant_id or "unknown",
            topic=record.governing_ref,
            payload=record.to_dict(),
        )
