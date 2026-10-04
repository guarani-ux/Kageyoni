"""
kageyoni.ledger: Universal Cryptographic Evidence Ledger.

Consolidates all fragmented ledgers (scars, assessments, outcomes,
dialogue receipts, contributions) into a single append-only,
SHA-256 hash-chained cryptographic ledger backed by SQLite.
"""

from __future__ import annotations
import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


GENESIS_PREV_HASH = "0" * 64


@dataclass
class EvidenceRecord:
    """An immutable, cryptographically chained event record."""
    sequence: int
    event_id: str
    kind: str
    actor_id: str
    topic: str
    payload: Dict[str, Any]
    prev_hash: str
    event_hash: str
    created_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_id": self.event_id,
            "kind": self.kind,
            "actor_id": self.actor_id,
            "topic": self.topic,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
            "created_at": self.created_at,
        }


class EvidenceLedger:
    """
    Append-only cryptographic event ledger.
    Every event binds strictly to the hash of the preceding sequence.
    """

    def __init__(self, conn: sqlite3.Connection, table_name: str = "evidence_ledger"):
        self.conn = conn
        self.table_name = table_name
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                sequence INTEGER PRIMARY KEY,
                event_id TEXT UNIQUE NOT NULL,
                kind TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            );
        """)
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_actor ON {self.table_name}(actor_id);")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_kind ON {self.table_name}(kind);")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_topic ON {self.table_name}(topic);")
        self.conn.commit()

    @staticmethod
    def compute_hash(
        sequence: int,
        event_id: str,
        kind: str,
        actor_id: str,
        topic: str,
        payload_json: str,
        prev_hash: str,
    ) -> str:
        canonical_str = f"{sequence}|{event_id}|{kind}|{actor_id}|{topic}|{payload_json}|{prev_hash}"
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def record(
        self,
        kind: str,
        actor_id: str,
        topic: str,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
    ) -> EvidenceRecord:
        """
        Appends a new cryptographically chained event to the ledger.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT sequence, event_hash FROM {self.table_name} ORDER BY sequence DESC LIMIT 1"
        )
        last_row = cursor.fetchone()

        if last_row is None:
            seq = 1
            prev_hash = GENESIS_PREV_HASH
        else:
            seq = last_row[0] + 1
            prev_hash = last_row[1]

        if not event_id:
            event_id = f"ev_{seq}_{uuid.uuid4().hex[:12]}"

        now = time.time()
        payload_json = json.dumps(payload, sort_keys=True)
        event_hash = self.compute_hash(seq, event_id, kind, actor_id, topic, payload_json, prev_hash)

        cursor.execute(
            f"""
            INSERT INTO {self.table_name}
            (sequence, event_id, kind, actor_id, topic, payload_json, prev_hash, event_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (seq, event_id, kind, actor_id, topic, payload_json, prev_hash, event_hash, now),
        )
        self.conn.commit()

        return EvidenceRecord(
            sequence=seq,
            event_id=event_id,
            kind=kind,
            actor_id=actor_id,
            topic=topic,
            payload=payload,
            prev_hash=prev_hash,
            event_hash=event_hash,
            created_at=now,
        )

    def query(
        self,
        actor_id: Optional[str] = None,
        kind: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 100,
        reverse: bool = False,
    ) -> List[EvidenceRecord]:
        """
        Queries evidence records with optional filtering across actor, kind, and topic.
        """
        clauses = []
        params: List[Any] = []

        if actor_id is not None:
            clauses.append("actor_id = ?")
            params.append(actor_id)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if topic is not None:
            clauses.append("topic = ?")
            params.append(topic)

        where_stmt = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        order_dir = "DESC" if reverse else "ASC"
        sql = f"SELECT sequence, event_id, kind, actor_id, topic, payload_json, prev_hash, event_hash, created_at FROM {self.table_name} {where_stmt} ORDER BY sequence {order_dir} LIMIT ?"
        params.append(limit)

        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        records = []
        for r in rows:
            payload = json.loads(r[5])
            records.append(
                EvidenceRecord(
                    sequence=r[0],
                    event_id=r[1],
                    kind=r[2],
                    actor_id=r[3],
                    topic=r[4],
                    payload=payload,
                    prev_hash=r[6],
                    event_hash=r[7],
                    created_at=r[8],
                )
            )
        return records

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Validates hash chain integrity and sequence continuity.
        Fails closed on sequence gap, hash alteration, or chain break.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT sequence, event_id, kind, actor_id, topic, payload_json, prev_hash, event_hash FROM {self.table_name} ORDER BY sequence ASC"
        )
        rows = cursor.fetchall()
        if not rows:
            return True, None

        expected_prev_hash = GENESIS_PREV_HASH
        for idx, row in enumerate(rows, start=1):
            seq, ev_id, kind, actor, topic, payload_json, prev_hash, stored_hash = row

            if seq != idx:
                return False, f"Sequence gap: expected {idx}, got {seq}"

            if prev_hash != expected_prev_hash:
                return False, f"Chain broken at sequence {seq}: expected prev_hash '{expected_prev_hash}', got '{prev_hash}'"

            recomputed_hash = self.compute_hash(seq, ev_id, kind, actor, topic, payload_json, prev_hash)
            if stored_hash != recomputed_hash:
                return False, f"Tampered record at sequence {seq}: recomputed hash '{recomputed_hash}' != stored '{stored_hash}'"

            expected_prev_hash = stored_hash

        return True, None
