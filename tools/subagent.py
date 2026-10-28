"""tools/subagent.py
Subagent Forge & Hermetic P-N-S-C Contract Compiler for Kageyōni.

Provides deterministic prompt compilation, contract validation, PreToolUse hook
enforcement, completion sink verification, and durable SQLite append-only task
ledger with subagents.json mirror synchronization.

P-N-S-C Sections:
  1. PAYLOAD: Subagent identity, role, target task, and input references.
  2. NEGATIVE BOUNDS: Hard boundaries, foregone actions, and anti-slop blacklists.
  3. SUCCESS INVARIANT: Epistemic proof criteria and verification tests.
  4. COMPLETION SINK: Disk artifacts, byte thresholds, and IPC completion receipts.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

# Standardize stdout/stderr encoding across platforms
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError) as _rec_err:
        sys.stderr.write(f"Note: stdout reconfigure not applied: {_rec_err}\n")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError) as _rec_err:
        sys.stderr.write(f"Note: stderr reconfigure not applied: {_rec_err}\n")

# Workspace paths and ledger defaults
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_DIR = WORKSPACE_ROOT / ".state"
DEFAULT_DB_PATH = DEFAULT_STATE_DIR / "subagents.sqlite"
DEFAULT_JSON_PATH = DEFAULT_STATE_DIR / "subagents.json"
GENESIS_PREV_HASH = "0" * 64

# Default Anti-Slop Blacklist injected into all forged contracts
DEFAULT_ANTI_SLOP_BLACKLIST = [
    "FORBIDDEN: Conversational pleasantries, sycophantic preamble, and unsolicited commentary.",
    "FORBIDDEN: Narrative plot summaries, encyclopedia filler, and pseudo-intellectual platitudes.",
    "FORBIDDEN: Mutating unapproved files or modifying global environment configurations.",
    "FORBIDDEN: Mocking test suites or faking execution passes without verified command outputs.",
    "FORBIDDEN: Returning hollow stubs (pass/TODO) in place of production-grade implementations.",
]

# Section Headers for P-N-S-C
SECTION_1_PAT = re.compile(
    r"(?:^|\n)\s*(?:\[?1\.?\s*PAYLOAD(?:\s*:[^\]\n]*)?\]?|1\.\s+PAYLOAD:?|PAYLOAD:)",
    re.IGNORECASE,
)
SECTION_2_PAT = re.compile(
    r"(?:^|\n)\s*(?:\[?2\.?\s*NEGATIVE\s+BOUNDS(?:\s*\([^)]*\))?(?:\s*:[^\]\n]*)?\]?|2\.\s+NEGATIVE\s+BOUNDS(?:\s*\([^)]*\))?:?|NEGATIVE\s+BOUNDS:?)",
    re.IGNORECASE,
)
SECTION_3_PAT = re.compile(
    r"(?:^|\n)\s*(?:\[?3\.?\s*SUCCESS\s+INVARIANT(?:\s*\([^)]*\))?(?:\s*:[^\]\n]*)?\]?|3\.\s+SUCCESS\s+INVARIANT(?:\s*\([^)]*\))?:?|SUCCESS\s+INVARIANT:?)",
    re.IGNORECASE,
)
SECTION_4_PAT = re.compile(
    r"(?:^|\n)\s*(?:\[?4\.?\s*COMPLETION\s+SINK(?:\s*\([^)]*\))?(?:\s*:[^\]\n]*)?\]?|4\.\s+COMPLETION\s+SINK(?:\s*\([^)]*\))?:?|COMPLETION\s+SINK:?)",
    re.IGNORECASE,
)

PNSC_SECTIONS = [
    ("[1. PAYLOAD]", SECTION_1_PAT),
    ("[2. NEGATIVE BOUNDS]", SECTION_2_PAT),
    ("[3. SUCCESS INVARIANT]", SECTION_3_PAT),
    ("[4. COMPLETION SINK]", SECTION_4_PAT),
]


def _utcnow_iso() -> str:
    """Format current UTC time as standard ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _flatten_arg(val: Any) -> List[str]:
    """Helper to flatten string, list of strings, or comma/newline separated strings."""
    if not val:
        return []
    res = []
    if isinstance(val, str):
        items = re.split(r"[\r\n,]+", val)
        res.extend(s.strip() for s in items if s.strip())
    elif isinstance(val, list):
        for item in val:
            res.extend(_flatten_arg(item))
    return res


def _parse_receipt_arg(val: Optional[str]) -> Dict[str, Any]:
    """Parse receipt from JSON string or file path."""
    if not val:
        return {}
    val_s = val.strip()
    p = Path(val_s)
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return {"raw_receipt": val_s, "note": "file content is not a JSON object"}
        except (json.JSONDecodeError, OSError) as exc:
            return {"raw_receipt": val_s, "file_read_error": str(exc)}
    try:
        data = json.loads(val_s)
        if isinstance(data, dict):
            return data
        return {"raw_receipt": val_s, "note": "string is not a JSON object"}
    except json.JSONDecodeError as exc:
        return {"raw_receipt": val_s, "parse_error": str(exc)}


@dataclass
class SubagentTask:
    """Durable record of a subagent task and its execution state."""

    task_id: str
    name: str
    role: str
    task: str
    status: str = "FORGED"
    inputs: List[str] = field(default_factory=list)
    forego: List[str] = field(default_factory=list)
    success: List[str] = field(default_factory=list)
    sinks: List[str] = field(default_factory=list)
    prompt: str = ""
    receipt: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "role": self.role,
            "task": self.task,
            "status": self.status,
            "inputs": self.inputs,
            "forego": self.forego,
            "success": self.success,
            "sinks": self.sinks,
            "prompt": self.prompt,
            "receipt": self.receipt,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


@dataclass
class SubagentEvent:
    """Immutable, cryptographically chained event in the subagent task ledger."""

    sequence: int
    event_id: str
    task_id: str
    event_type: str
    payload: Dict[str, Any]
    prev_hash: str
    event_hash: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_id": self.event_id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
            "created_at": self.created_at,
        }


class SubagentLedger:
    """Append-only SQLite task ledger and JSON mirror for autonomous subagents.

    Maintains an immutable SHA-256 hash-chained event trail of all subagent
    lifecycle transitions and synchronizes current task states to subagents.json.
    """

    def __init__(
        self,
        db_path: Optional[Union[Path, str]] = None,
        json_path: Optional[Union[Path, str]] = None,
        auto_mirror: bool = True,
    ) -> None:
        self.db_path = (
            Path(db_path) if db_path and str(db_path) != ":memory:" else (db_path or DEFAULT_DB_PATH)
        )
        self.json_path = Path(json_path) if json_path else DEFAULT_JSON_PATH
        self.auto_mirror = auto_mirror
        self._mem_conn: Optional[sqlite3.Connection] = None

        if str(self.db_path) != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        if self.json_path:
            self.json_path.parent.mkdir(parents=True, exist_ok=True)

        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        if str(self.db_path) == ":memory:":
            if self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:")
                self._mem_conn.row_factory = sqlite3.Row
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def close(self) -> None:
        """Close connection if using in-memory SQLite database."""
        if self._mem_conn is not None:
            conn = self._mem_conn
            self._mem_conn = None
            conn.close()

    def _ensure_schema(self) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS subagent_tasks (
                    task_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    inputs_json TEXT NOT NULL DEFAULT '[]',
                    forego_json TEXT NOT NULL DEFAULT '[]',
                    success_json TEXT NOT NULL DEFAULT '[]',
                    sinks_json TEXT NOT NULL DEFAULT '[]',
                    prompt TEXT NOT NULL DEFAULT '',
                    receipt_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON subagent_tasks(status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_name ON subagent_tasks(name);")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS subagent_events (
                    sequence INTEGER PRIMARY KEY,
                    event_id TEXT UNIQUE NOT NULL,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_events_task ON subagent_events(task_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON subagent_events(event_type);")
            conn.commit()
        finally:
            if str(self.db_path) != ":memory:":
                conn.close()

    @staticmethod
    def compute_hash(
        sequence: int,
        event_id: str,
        task_id: str,
        event_type: str,
        payload_json: str,
        prev_hash: str,
        created_at: str,
    ) -> str:
        """Compute canonical SHA-256 event hash over immutable record fields."""
        canonical = f"{sequence}|{event_id}|{task_id}|{event_type}|{payload_json}|{prev_hash}|{created_at}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _append_event(
        self,
        conn: sqlite3.Connection,
        task_id: str,
        event_type: str,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> SubagentEvent:
        cur = conn.cursor()
        cur.execute("SELECT sequence, event_hash FROM subagent_events ORDER BY sequence DESC LIMIT 1")
        last_row = cur.fetchone()

        if last_row is None:
            seq = 1
            prev_hash = GENESIS_PREV_HASH
        else:
            seq = last_row["sequence"] + 1
            prev_hash = last_row["event_hash"]

        ts = timestamp or _utcnow_iso()
        ev_id = event_id or f"ev_{seq}_{uuid.uuid4().hex[:12]}"
        payload_json = json.dumps(payload, sort_keys=True)
        ev_hash = self.compute_hash(seq, ev_id, task_id, event_type, payload_json, prev_hash, ts)

        cur.execute(
            """
            INSERT INTO subagent_events
            (sequence, event_id, task_id, event_type, payload_json, prev_hash, event_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (seq, ev_id, task_id, event_type, payload_json, prev_hash, ev_hash, ts),
        )

        return SubagentEvent(
            sequence=seq,
            event_id=ev_id,
            task_id=task_id,
            event_type=event_type,
            payload=payload,
            prev_hash=prev_hash,
            event_hash=ev_hash,
            created_at=ts,
        )

    def record_task(
        self,
        name: str = "unnamed-subagent",
        role: str = "Autonomous Task Specialist",
        task: str = "Execute assigned operational objectives.",
        inputs: Optional[List[str]] = None,
        forego: Optional[List[str]] = None,
        success: Optional[List[str]] = None,
        sink: Optional[List[str]] = None,
        prompt: str = "",
        status: str = "FORGED",
        task_id: Optional[str] = None,
        receipt: Optional[Dict[str, Any]] = None,
    ) -> SubagentTask:
        """Register or update a subagent task and record an immutable event."""
        inputs_list = inputs or []
        forego_list = forego or []
        success_list = success or []
        sinks_list = sink or []
        receipt_data = receipt or {}

        tid = task_id or f"task_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = _utcnow_iso()

        task_record = SubagentTask(
            task_id=tid,
            name=name,
            role=role,
            task=task,
            status=status,
            inputs=inputs_list,
            forego=forego_list,
            success=success_list,
            sinks=sinks_list,
            prompt=prompt,
            receipt=receipt_data,
            created_at=now,
            updated_at=now,
            completed_at=now if status in ("COMPLETED", "FAILED") else None,
        )

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO subagent_tasks
                (task_id, name, role, task, status, inputs_json, forego_json, success_json, sinks_json, prompt, receipt_json, created_at, updated_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    name=excluded.name,
                    role=excluded.role,
                    task=excluded.task,
                    status=excluded.status,
                    inputs_json=excluded.inputs_json,
                    forego_json=excluded.forego_json,
                    success_json=excluded.success_json,
                    sinks_json=excluded.sinks_json,
                    prompt=excluded.prompt,
                    receipt_json=excluded.receipt_json,
                    updated_at=excluded.updated_at,
                    completed_at=excluded.completed_at
                """,
                (
                    task_record.task_id,
                    task_record.name,
                    task_record.role,
                    task_record.task,
                    task_record.status,
                    json.dumps(task_record.inputs),
                    json.dumps(task_record.forego),
                    json.dumps(task_record.success),
                    json.dumps(task_record.sinks),
                    task_record.prompt,
                    json.dumps(task_record.receipt),
                    task_record.created_at,
                    task_record.updated_at,
                    task_record.completed_at,
                ),
            )

            self._append_event(
                conn,
                task_id=task_record.task_id,
                event_type="RECORD",
                payload={
                    "name": task_record.name,
                    "role": task_record.role,
                    "task": task_record.task,
                    "status": task_record.status,
                    "sinks": task_record.sinks,
                },
                timestamp=now,
            )
            conn.commit()
        finally:
            if str(self.db_path) != ":memory:":
                conn.close()

        if self.auto_mirror:
            self.sync_json_mirror()

        return task_record

    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        receipt: Optional[Dict[str, Any]] = None,
        sinks: Optional[List[str]] = None,
        event_type: str = "UPDATE",
        event_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[SubagentTask]:
        """Update an existing subagent task's status, receipt, or sinks."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM subagent_tasks WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None

            now = _utcnow_iso()
            current_status = status.upper() if status else row["status"]
            completed_at = row["completed_at"]
            if current_status in ("COMPLETED", "FAILED") and not completed_at:
                completed_at = now
            elif current_status not in ("COMPLETED", "FAILED"):
                completed_at = None

            current_receipt = receipt if receipt is not None else json.loads(row["receipt_json"])
            current_sinks = sinks if sinks is not None else json.loads(row["sinks_json"])

            cur.execute(
                """
                UPDATE subagent_tasks
                SET status = ?, receipt_json = ?, sinks_json = ?, updated_at = ?, completed_at = ?
                WHERE task_id = ?
                """,
                (
                    current_status,
                    json.dumps(current_receipt),
                    json.dumps(current_sinks),
                    now,
                    completed_at,
                    task_id,
                ),
            )

            payload = event_payload or {
                "status": current_status,
                "receipt": current_receipt,
                "sinks": current_sinks,
            }
            self._append_event(
                conn, task_id=task_id, event_type=event_type, payload=payload, timestamp=now
            )
            conn.commit()

            task_obj = SubagentTask(
                task_id=row["task_id"],
                name=row["name"],
                role=row["role"],
                task=row["task"],
                status=current_status,
                inputs=json.loads(row["inputs_json"]),
                forego=json.loads(row["forego_json"]),
                success=json.loads(row["success_json"]),
                sinks=current_sinks,
                prompt=row["prompt"],
                receipt=current_receipt,
                created_at=row["created_at"],
                updated_at=now,
                completed_at=completed_at,
            )
        finally:
            if str(self.db_path) != ":memory:":
                conn.close()

        if self.auto_mirror:
            self.sync_json_mirror()

        return task_obj

    def complete_task(
        self,
        task_id: str,
        receipt: Optional[Dict[str, Any]] = None,
        verify_sinks: bool = False,
        min_bytes: int = 1,
    ) -> Tuple[bool, Optional[SubagentTask], List[str]]:
        """Complete a task, optionally validating all declared completion sinks."""
        task = self.get_task(task_id)
        if not task:
            return False, None, [f"Task {task_id} not found in subagent ledger."]

        diagnostics: List[str] = []
        if verify_sinks and task.sinks:
            passed, diagnostics = verify_sink(task.sinks, min_bytes=min_bytes)
            if not passed:
                full_receipt = dict(task.receipt)
                if receipt:
                    full_receipt.update(receipt)
                full_receipt["sink_verification"] = "FAILED"
                full_receipt["diagnostics"] = diagnostics
                updated = self.update_task(
                    task_id=task_id,
                    status="FAILED",
                    receipt=full_receipt,
                    event_type="FAIL",
                    event_payload={"reason": "Sink verification failed", "diagnostics": diagnostics},
                )
                return False, updated, diagnostics

        full_receipt = dict(task.receipt)
        if receipt:
            full_receipt.update(receipt)
        if verify_sinks:
            full_receipt["sink_verification"] = "PASSED"

        updated = self.update_task(
            task_id=task_id,
            status="COMPLETED",
            receipt=full_receipt,
            event_type="COMPLETE",
            event_payload={"status": "COMPLETED", "receipt": full_receipt},
        )
        return True, updated, diagnostics

    def get_task(self, task_id: str) -> Optional[SubagentTask]:
        """Fetch a single subagent task by task_id."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM subagent_tasks WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            return SubagentTask(
                task_id=row["task_id"],
                name=row["name"],
                role=row["role"],
                task=row["task"],
                status=row["status"],
                inputs=json.loads(row["inputs_json"]),
                forego=json.loads(row["forego_json"]),
                success=json.loads(row["success_json"]),
                sinks=json.loads(row["sinks_json"]),
                prompt=row["prompt"],
                receipt=json.loads(row["receipt_json"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                completed_at=row["completed_at"],
            )
        finally:
            if str(self.db_path) != ":memory:":
                conn.close()

    def list_tasks(
        self,
        status: Optional[str] = None,
        name: Optional[str] = None,
        limit: int = 100,
    ) -> List[SubagentTask]:
        """Query subagent tasks with optional status and name filters."""
        clauses = []
        params: List[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status.upper())
        if name:
            clauses.append("name = ?")
            params.append(name)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM subagent_tasks {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            tasks = []
            for row in rows:
                tasks.append(
                    SubagentTask(
                        task_id=row["task_id"],
                        name=row["name"],
                        role=row["role"],
                        task=row["task"],
                        status=row["status"],
                        inputs=json.loads(row["inputs_json"]),
                        forego=json.loads(row["forego_json"]),
                        success=json.loads(row["success_json"]),
                        sinks=json.loads(row["sinks_json"]),
                        prompt=row["prompt"],
                        receipt=json.loads(row["receipt_json"]),
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        completed_at=row["completed_at"],
                    )
                )
            return tasks
        finally:
            if str(self.db_path) != ":memory:":
                conn.close()

    def get_events(self, task_id: Optional[str] = None) -> List[SubagentEvent]:
        """Retrieve all events or events for a specific task in sequence order."""
        sql = "SELECT * FROM subagent_events"
        params: List[Any] = []
        if task_id:
            sql += " WHERE task_id = ?"
            params.append(task_id)
        sql += " ORDER BY sequence ASC"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            events = []
            for r in rows:
                events.append(
                    SubagentEvent(
                        sequence=r["sequence"],
                        event_id=r["event_id"],
                        task_id=r["task_id"],
                        event_type=r["event_type"],
                        payload=json.loads(r["payload_json"]),
                        prev_hash=r["prev_hash"],
                        event_hash=r["event_hash"],
                        created_at=r["created_at"],
                    )
                )
            return events
        finally:
            if str(self.db_path) != ":memory:":
                conn.close()

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """Validate hash chain continuity and SHA-256 seal integrity."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM subagent_events ORDER BY sequence ASC")
            rows = cur.fetchall()
            if not rows:
                return True, None

            expected_prev_hash = GENESIS_PREV_HASH
            for idx, r in enumerate(rows, start=1):
                seq = r["sequence"]
                ev_id = r["event_id"]
                tid = r["task_id"]
                etype = r["event_type"]
                payload_json = r["payload_json"]
                prev_hash = r["prev_hash"]
                stored_hash = r["event_hash"]
                ts = r["created_at"]

                if seq != idx:
                    return False, f"Sequence gap: expected {idx}, got {seq}"

                if prev_hash != expected_prev_hash:
                    return (
                        False,
                        f"Chain broken at sequence {seq}: expected prev_hash '{expected_prev_hash}', got '{prev_hash}'",
                    )

                recomputed = self.compute_hash(seq, ev_id, tid, etype, payload_json, prev_hash, ts)
                if stored_hash != recomputed:
                    return (
                        False,
                        f"Tampered record at sequence {seq}: recomputed '{recomputed}' != stored '{stored_hash}'",
                    )

                expected_prev_hash = stored_hash

            return True, None
        finally:
            if str(self.db_path) != ":memory:":
                conn.close()

    def sync_json_mirror(self) -> Path:
        """Export all ledger tasks to subagents.json mirror."""
        tasks = self.list_tasks(limit=10000)
        task_dicts = [t.to_dict() for t in sorted(tasks, key=lambda x: x.created_at)]
        by_id_map = {t["task_id"]: t for t in task_dicts}

        mirror_data = {
            "version": "1.0",
            "updated_at": _utcnow_iso(),
            "total_subagents": len(task_dicts),
            "subagents": task_dicts,
            "by_id": by_id_map,
        }

        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(mirror_data, indent=2) + "\n"
        self.json_path.write_text(content, encoding="utf-8")
        return self.json_path


def forge_contract(
    name: str = "unnamed-subagent",
    role: str = "Autonomous Task Specialist",
    task: str = "Execute assigned operational objectives.",
    inputs: Optional[List[str]] = None,
    forego: Optional[List[str]] = None,
    success: Optional[List[str]] = None,
    sink: Optional[List[str]] = None,
    format_type: str = "prompt",
    record: bool = False,
    task_id: Optional[str] = None,
    ledger_db: Optional[Union[Path, str]] = None,
    ledger_json: Optional[Union[Path, str]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Compiles operational intent into a hermetic P-N-S-C contract."""
    inputs_list = inputs or []
    forego_list = forego or []
    success_list = success or []
    sink_list = sink or []

    # Section 1: Payload
    formatted_inputs = (
        "\n".join(f"     - {inp}" for inp in inputs_list)
        if inputs_list
        else "     - None specified (autonomous workspace discovery)."
    )
    payload_body = (
        f"   - Target Subagent: {name}\n"
        f"   - Operational Role: {role}\n"
        f"   - Primary Assignment:\n"
        f"     {task}\n"
        f"   - Reference Inputs:\n"
        f"{formatted_inputs}"
    )

    # Section 2: Negative Bounds
    custom_forego = "\n".join(f"   - {item}" for item in forego_list)
    auto_anti_slop = "\n".join(f"     * {item}" for item in DEFAULT_ANTI_SLOP_BLACKLIST)
    negative_bounds_body = (
        (f"{custom_forego}\n" if custom_forego else "")
        + "   - Auto-Injected Anti-Slop Blacklist:\n"
        + auto_anti_slop
    )

    # Section 3: Success Invariant
    custom_success = "\n".join(f"   - {item}" for item in success_list)
    success_body = (
        (f"{custom_success}\n" if custom_success else "")
        + "   - Epistemic Verification Gate:\n"
        + "     * All targeted test suites must run and pass with exit code 0.\n"
        + "     * Zero unhandled exceptions or hollow stubs (pass/TODO).\n"
        + "     * Proof of execution verified with concrete command outputs."
    )

    # Section 4: Completion Sink
    formatted_sinks = (
        "\n".join(f"     - {s}" for s in sink_list)
        if sink_list
        else "     - Clean process completion with zero uncommitted workspace mutations."
    )
    completion_sink_body = (
        f"   - Target Sink Files & Artifacts:\n"
        f"{formatted_sinks}\n"
        f"   - Termination Protocol:\n"
        f"     * Emit verified execution receipt to caller agent via send_message.\n"
        f"     * Conclude session immediately upon receipt confirmation."
    )

    contract_text = (
        f"[SUBAGENT EXECUTION KERNEL: P-N-S-C]\n\n"
        f"1. PAYLOAD:\n{payload_body}\n\n"
        f"2. NEGATIVE BOUNDS (FOREGO):\n{negative_bounds_body}\n\n"
        f"3. SUCCESS INVARIANT (EPISTEMIC GATE):\n{success_body}\n\n"
        f"4. COMPLETION SINK (PHYSICAL TERMINATION):\n{completion_sink_body}\n"
    )

    contract_data = {
        "TypeName": name,
        "Role": role,
        "Prompt": contract_text,
        "contract": {
            "payload": payload_body.strip(),
            "negative_bounds": negative_bounds_body.strip(),
            "success_invariant": success_body.strip(),
            "completion_sink": completion_sink_body.strip(),
            "inputs": inputs_list,
            "forego": forego_list,
            "success": success_list,
            "sink": sink_list,
        },
    }

    if record:
        ledger = SubagentLedger(db_path=ledger_db, json_path=ledger_json)
        ledger.record_task(
            name=name,
            role=role,
            task=task,
            inputs=inputs_list,
            forego=forego_list,
            success=success_list,
            sink=sink_list,
            prompt=contract_text,
            status="FORGED",
            task_id=task_id,
        )

    if format_type == "json":
        return json.dumps(contract_data, indent=2), contract_data
    return contract_text, contract_data


def validate_contract(text: str) -> Tuple[bool, str]:
    """Validates that text contains all 4 non-empty P-N-S-C sections.

    Returns (is_valid, diagnostic_message).
    """
    if not isinstance(text, str) or not text.strip():
        return (
            False,
            "FM-FORGE-01 (Un-Forged Subagent Blocked): Empty or non-string contract provided.",
        )

    matches: List[Tuple[str, int, int]] = []
    missing_sections: List[str] = []

    for name, pattern in PNSC_SECTIONS:
        m = pattern.search(text)
        if not m:
            missing_sections.append(name)
        else:
            matches.append((name, m.start(), m.end()))

    if missing_sections:
        return (
            False,
            f"FM-FORGE-01 (Un-Forged Subagent Blocked): Missing required P-N-S-C sections: {', '.join(missing_sections)}",
        )

    matches.sort(key=lambda x: x[1])

    empty_sections: List[str] = []
    for i, (sec_name, _, end_idx) in enumerate(matches):
        next_start = matches[i + 1][1] if i + 1 < len(matches) else len(text)
        section_content = text[end_idx:next_start].strip()

        substantive = re.sub(r"[\s\-\*\#\:\(\)\[\]]+", "", section_content)
        if len(substantive) < 3:
            empty_sections.append(sec_name)

    if empty_sections:
        return (
            False,
            f"FM-FORGE-03 (Empty Section Evasion): P-N-S-C sections exist but have empty content: {', '.join(empty_sections)}",
        )

    return True, "P-N-S-C Forge contract verified."


def verify_sink(sink_paths: List[str], min_bytes: int = 1) -> Tuple[bool, List[str]]:
    """Verifies that all specified sink files exist and meet minimum byte thresholds.

    Returns (all_passed, diagnostics_list).
    """
    diagnostics = []
    all_passed = True

    if not sink_paths:
        return True, ["No sink files specified to verify."]

    for path_str in sink_paths:
        p = Path(path_str).resolve()
        if not p.exists():
            diagnostics.append(
                f"[FAIL] FM-FORGE-04 (Phantom Completion Sink): Sink file does not exist: {p}"
            )
            all_passed = False
            continue

        if not p.is_file():
            diagnostics.append(
                f"[FAIL] FM-FORGE-04 (Phantom Completion Sink): Sink path is not a regular file: {p}"
            )
            all_passed = False
            continue

        size = p.stat().st_size
        if size < min_bytes:
            diagnostics.append(
                f"[FAIL] FM-FORGE-04 (Phantom Completion Sink): Sink file {p} is {size} bytes (required: >= {min_bytes} bytes)"
            )
            all_passed = False
        else:
            diagnostics.append(
                f"[PASS] Sink file {p.name} verified: {size} bytes (>= {min_bytes} bytes)"
            )

    return all_passed, diagnostics


def handle_hook_pre(raw_input: str) -> Dict[str, Any]:
    """Processes PreToolUse JSON payload from stdin.

    If toolCall.name == 'invoke_subagent', validates Prompt.
    Returns hook decision dict.
    """
    if not isinstance(raw_input, str):
        return {
            "decision": "force_ask",
            "reason": "FM-FORGE-02 (Corrupted Hook Payload): Raw input must be a string.",
        }

    if not raw_input.strip():
        return {"decision": "allow", "reason": "Empty payload received by pre-tool hook."}

    try:
        payload = json.loads(raw_input)
    except (json.JSONDecodeError, TypeError) as ex:
        return {
            "decision": "force_ask",
            "reason": f"FM-FORGE-02 (Corrupted Hook Payload): Failed to parse JSON ({type(ex).__name__}).",
        }

    if not isinstance(payload, dict):
        return {
            "decision": "force_ask",
            "reason": f"FM-FORGE-02 (Corrupted Hook Payload): Hook payload must be a JSON object, got {type(payload).__name__}.",
        }

    tool = payload.get("toolCall") or payload.get("tool_call") or payload
    if not isinstance(tool, dict):
        return {
            "decision": "force_ask",
            "reason": f"FM-FORGE-02 (Corrupted Hook Payload): toolCall must be a JSON object, got {type(tool).__name__}.",
        }

    name = tool.get("name") or payload.get("name")
    if not isinstance(name, str) or name != "invoke_subagent":
        return {
            "decision": "allow",
            "reason": f"Tool '{name}' is not invoke_subagent; bypassed forge gate.",
        }

    args = tool.get("args") or tool.get("arguments") or payload.get("args") or {}

    if isinstance(args, str):
        try:
            parsed_args = json.loads(args)
            if isinstance(parsed_args, dict):
                args = parsed_args
            else:
                args = {"_raw": args}
        except (json.JSONDecodeError, TypeError) as exc:
            args = {"_raw": args, "_parse_error": str(exc)}
    elif not isinstance(args, dict):
        args = {"_raw": str(args)}

    prompt = args.get("Prompt") or args.get("prompt") or ""
    if not isinstance(prompt, str):
        prompt = ""

    is_valid, reason = validate_contract(prompt)

    if not is_valid:
        return {
            "decision": "deny",
            "reason": reason,
        }

    return {
        "decision": "allow",
        "reason": "P-N-S-C Forge contract verified.",
    }


def install_hooks_config(target_dir: Optional[Path] = None) -> Path:
    """Installs or updates .agents/hooks.json to hook invoke_subagent."""
    base_dir = target_dir or Path(__file__).resolve().parent.parent
    agents_dir = base_dir / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    hooks_file = agents_dir / "hooks.json"

    forge_hook_entry = {
        "enabled": True,
        "PreToolUse": [
            {
                "matcher": "invoke_subagent",
                "hooks": [
                    {
                        "type": "command",
                        "command": "python -m tools.subagent hook pre",
                        "timeout": 10,
                    }
                ],
            }
        ],
    }

    config: Dict[str, Any] = {}
    if hooks_file.is_file():
        try:
            existing = json.loads(hooks_file.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                config = existing
            else:
                config = {"_legacy": existing}
        except (json.JSONDecodeError, OSError) as exc:
            config = {"_parse_warning": str(exc)}

    config["subagent_forge"] = forge_hook_entry
    hooks_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return hooks_file


def _render_tasks_table(tasks: List[SubagentTask]) -> None:
    """Render terminal table of subagent tasks."""
    sep = "=" * 80
    sub_sep = "-" * 80
    print(sep)
    print("                    SUBAGENT FORGE: DURABLE TASK LEDGER")
    print(sep)
    print(f"  {'TASK ID':<26} {'NAME':<16} {'STATUS':<12} {'UPDATED':<20}")
    print(sub_sep)
    for t in tasks:
        ts_short = t.updated_at[:19].replace("T", " ")
        print(f"  {t.task_id:<26} {t.name:<16} {t.status:<12} {ts_short:<20}")
    print(sub_sep)
    print(f"Total: {len(tasks)} subagent task(s)")
    print(sep)


def _render_task_detail(task: SubagentTask, events: Optional[List[SubagentEvent]] = None) -> None:
    """Render formatted terminal output for single task."""
    sep = "=" * 80
    sub_sep = "-" * 80
    print(sep)
    print(f"SUBAGENT TASK: {task.task_id}")
    print(sep)
    print(f"  Name:         {task.name}")
    print(f"  Role:         {task.role}")
    print(f"  Status:       {task.status}")
    print(f"  Created:      {task.created_at}")
    print(f"  Updated:      {task.updated_at}")
    print(f"  Completed:    {task.completed_at or 'None'}")
    print(f"  Assignment:   {task.task}")
    print(f"  Inputs:       {', '.join(task.inputs) if task.inputs else 'None'}")
    print(f"  Bounds:       {', '.join(task.forego) if task.forego else 'Default Anti-Slop'}")
    print(f"  Success:      {', '.join(task.success) if task.success else 'Exit 0'}")
    print(f"  Sinks:        {', '.join(task.sinks) if task.sinks else 'None'}")
    if task.receipt:
        print(sub_sep)
        print(f"  Receipt:      {json.dumps(task.receipt, indent=2)}")
    if events is not None:
        print(sub_sep)
        print("  CRYPTOGRAPHIC EVENT TRAIL:")
        for ev in events:
            short_hash = ev.event_hash[:12]
            print(
                f"    [{ev.sequence}] {ev.event_type:<10} | hash: {short_hash}... | at: {ev.created_at}"
            )
    print(sep)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Subagent Forge: P-N-S-C Contract Compiler, Gate & Durable Ledger",
        prog="tools.subagent",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Command: forge
    forge_parser = subparsers.add_parser(
        "forge", help="Compile intent into a hermetic P-N-S-C contract"
    )
    forge_parser.add_argument("--name", default="unnamed-subagent", help="Subagent name / TypeName")
    forge_parser.add_argument("--role", default="Autonomous Task Specialist", help="Operational role")
    forge_parser.add_argument(
        "--task", default="Execute assigned operational objectives.", help="Primary task"
    )
    forge_parser.add_argument("--inputs", action="append", default=[], help="Input files or context")
    forge_parser.add_argument("--forego", action="append", default=[], help="Negative bounds / constraints")
    forge_parser.add_argument("--success", action="append", default=[], help="Success invariants")
    forge_parser.add_argument("--sink", action="append", default=[], help="Disk sinks / outputs")
    forge_parser.add_argument(
        "--format",
        choices=["prompt", "json"],
        default="prompt",
        help="Output format (prompt or json)",
    )
    forge_parser.add_argument("--out", help="Optional output file path")
    forge_parser.add_argument(
        "--record", action="store_true", help="Record compiled contract to subagent ledger"
    )
    forge_parser.add_argument("--task-id", help="Explicit task ID to associate with ledger record")
    forge_parser.add_argument("--db", help="SQLite database path for ledger")
    forge_parser.add_argument("--json-path", help="JSON mirror path for ledger")

    # Command: validate
    val_parser = subparsers.add_parser(
        "validate", help="Validate that a prompt or file satisfies P-N-S-C"
    )
    val_parser.add_argument("target", nargs="?", help="Prompt string or path to contract file")
    val_parser.add_argument("--file", help="Path to contract file to validate")
    val_parser.add_argument("--prompt", help="Prompt text to validate")

    # Command: hook
    hook_parser = subparsers.add_parser("hook", help="Hook lifecycle commands")
    hook_subparsers = hook_parser.add_subparsers(dest="hook_action", help="Hook action")
    hook_subparsers.add_parser("pre", help="PreToolUse hook reading JSON payload from stdin")
    hook_subparsers.add_parser("install", help="Install .agents/hooks.json for subagent forge")

    # Command: verify-sink
    sink_parser = subparsers.add_parser(
        "verify-sink", help="Verify existence and byte thresholds of completion sinks"
    )
    sink_parser.add_argument("sinks", nargs="*", help="File paths to verify")
    sink_parser.add_argument("--sink", action="append", default=[], help="Sink file path")
    sink_parser.add_argument("--min-bytes", type=int, default=1, help="Minimum byte threshold")
    sink_parser.add_argument("--task-id", help="Subagent task ID to update upon sink verification")
    sink_parser.add_argument("--db", help="SQLite database path for ledger")
    sink_parser.add_argument("--json-path", help="JSON mirror path for ledger")

    # Command: ledger
    ledger_parser = subparsers.add_parser(
        "ledger", help="Durable subagent task ledger and subagents.json mirror"
    )
    ledger_subparsers = ledger_parser.add_subparsers(dest="ledger_action", help="Ledger action")

    # ledger record
    rec_p = ledger_subparsers.add_parser("record", help="Record a subagent task in the ledger")
    rec_p.add_argument("--name", default="unnamed-subagent", help="Subagent TypeName")
    rec_p.add_argument("--role", default="Autonomous Task Specialist", help="Operational role")
    rec_p.add_argument(
        "--task", default="Execute assigned operational objectives.", help="Primary task"
    )
    rec_p.add_argument("--inputs", action="append", default=[], help="Input files or context")
    rec_p.add_argument("--forego", action="append", default=[], help="Negative bounds")
    rec_p.add_argument("--success", action="append", default=[], help="Success invariants")
    rec_p.add_argument("--sink", action="append", default=[], help="Disk sinks / deliverables")
    rec_p.add_argument("--prompt", default="", help="Subagent contract text")
    rec_p.add_argument("--status", default="FORGED", help="Task status (default: FORGED)")
    rec_p.add_argument("--task-id", help="Explicit task ID")
    rec_p.add_argument("--receipt", help="JSON string or file path containing receipt")
    rec_p.add_argument("--db", help="SQLite database path")
    rec_p.add_argument("--json-path", help="JSON mirror path")
    rec_p.add_argument("--no-mirror", action="store_true", help="Do not update JSON mirror")

    # ledger list
    list_p = ledger_subparsers.add_parser("list", help="List subagent tasks in the ledger")
    list_p.add_argument("--status", help="Filter by status (e.g. FORGED, RUNNING, COMPLETED, FAILED)")
    list_p.add_argument("--name", help="Filter by subagent TypeName")
    list_p.add_argument(
        "--limit", type=int, default=100, help="Maximum records to return (default: 100)"
    )
    list_p.add_argument("--json", action="store_true", help="Output raw JSON array")
    list_p.add_argument("--db", help="SQLite database path")
    list_p.add_argument("--json-path", help="JSON mirror path")

    # ledger show
    show_p = ledger_subparsers.add_parser("show", help="Show subagent task details and history")
    show_p.add_argument("task_id", help="Target task ID")
    show_p.add_argument("--json", action="store_true", help="Output raw JSON")
    show_p.add_argument("--events", action="store_true", help="Include cryptographic event history")
    show_p.add_argument("--db", help="SQLite database path")
    show_p.add_argument("--json-path", help="JSON mirror path")

    # ledger update
    up_p = ledger_subparsers.add_parser("update", help="Update subagent task status or receipt")
    up_p.add_argument("task_id", help="Target task ID")
    up_p.add_argument("--status", help="New task status")
    up_p.add_argument("--receipt", help="JSON string or file path containing receipt")
    up_p.add_argument("--sink", action="append", default=[], help="Add or update sinks")
    up_p.add_argument("--db", help="SQLite database path")
    up_p.add_argument("--json-path", help="JSON mirror path")

    # ledger complete
    comp_p = ledger_subparsers.add_parser(
        "complete", help="Mark subagent task completed with sink verification"
    )
    comp_p.add_argument("task_id", help="Target task ID")
    comp_p.add_argument("--receipt", help="JSON string or file path containing completion receipt")
    comp_p.add_argument(
        "--verify-sinks", action="store_true", help="Verify that sinks exist and meet min-bytes"
    )
    comp_p.add_argument(
        "--min-bytes", type=int, default=1, help="Minimum byte threshold for sinks (default: 1)"
    )
    comp_p.add_argument("--db", help="SQLite database path")
    comp_p.add_argument("--json-path", help="JSON mirror path")

    # ledger verify
    ver_p = ledger_subparsers.add_parser("verify", help="Verify cryptographic hash chain integrity")
    ver_p.add_argument("--db", help="SQLite database path")

    # ledger sync
    sync_p = ledger_subparsers.add_parser(
        "sync", help="Synchronize SQLite ledger to subagents.json mirror"
    )
    sync_p.add_argument("--db", help="SQLite database path")
    sync_p.add_argument("--json-path", help="JSON mirror path")

    args = parser.parse_args(argv)

    if args.subcommand == "forge":
        inputs = _flatten_arg(args.inputs)
        forego = _flatten_arg(args.forego)
        success = _flatten_arg(args.success)
        sink = _flatten_arg(args.sink)

        output_str, _ = forge_contract(
            name=args.name,
            role=args.role,
            task=args.task,
            inputs=inputs,
            forego=forego,
            success=success,
            sink=sink,
            format_type=args.format,
            record=args.record,
            task_id=args.task_id,
            ledger_db=args.db,
            ledger_json=args.json_path,
        )

        if args.out:
            out_path = Path(args.out).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output_str, encoding="utf-8")
            print(f"[OK] Forged contract written to: {out_path}")
        else:
            sys.stdout.write(output_str + "\n")
        return 0

    elif args.subcommand == "validate":
        text_to_validate = ""
        if args.file:
            p = Path(args.file)
            if not p.is_file():
                print(f"[ERROR] Specified file not found: {p}", file=sys.stderr)
                return 1
            text_to_validate = p.read_text(encoding="utf-8")
        elif args.prompt:
            text_to_validate = args.prompt
        elif args.target:
            p = Path(args.target)
            if p.is_file():
                text_to_validate = p.read_text(encoding="utf-8")
            else:
                text_to_validate = args.target
        elif not sys.stdin.isatty():
            text_to_validate = sys.stdin.read()

        is_valid, msg = validate_contract(text_to_validate)
        if is_valid:
            print(f"[OK] {msg}")
            return 0
        else:
            print(f"[ERROR] {msg}", file=sys.stderr)
            return 1

    elif args.subcommand == "hook":
        if args.hook_action == "pre":
            raw_input = sys.stdin.read()
            res = handle_hook_pre(raw_input)
            sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
            return 0
        elif args.hook_action == "install":
            path = install_hooks_config()
            print(f"[OK] Subagent Forge hook configuration installed at {path}")
            return 0
        else:
            hook_parser.print_help()
            return 1

    elif args.subcommand == "verify-sink":
        all_sinks = list(args.sinks) + _flatten_arg(args.sink)

        if args.task_id and not all_sinks:
            ledger = SubagentLedger(db_path=args.db, json_path=args.json_path)
            task_rec = ledger.get_task(args.task_id)
            if task_rec:
                all_sinks = task_rec.sinks

        if not all_sinks:
            print(
                "[ERROR] FM-FORGE-04 (Phantom Completion Sink): No sink paths provided to verify-sink.",
                file=sys.stderr,
            )
            return 1

        passed, diagnostics = verify_sink(all_sinks, min_bytes=args.min_bytes)
        for diag in diagnostics:
            if diag.startswith("[PASS]"):
                print(diag)
            else:
                print(diag, file=sys.stderr)

        if args.task_id:
            ledger = SubagentLedger(db_path=args.db, json_path=args.json_path)
            if passed:
                ledger.complete_task(args.task_id, verify_sinks=False)
            else:
                ledger.update_task(
                    args.task_id,
                    status="FAILED",
                    receipt={"sink_verification": "FAILED", "diagnostics": diagnostics},
                    event_type="FAIL",
                )

        return 0 if passed else 1

    elif args.subcommand == "ledger":
        ledger = SubagentLedger(
            db_path=getattr(args, "db", None),
            json_path=getattr(args, "json_path", None),
            auto_mirror=not getattr(args, "no_mirror", False),
        )

        if args.ledger_action == "record":
            inputs = _flatten_arg(args.inputs)
            forego = _flatten_arg(args.forego)
            success = _flatten_arg(args.success)
            sink = _flatten_arg(args.sink)
            receipt = _parse_receipt_arg(args.receipt)

            task = ledger.record_task(
                name=args.name,
                role=args.role,
                task=args.task,
                inputs=inputs,
                forego=forego,
                success=success,
                sink=sink,
                prompt=args.prompt,
                status=args.status,
                task_id=args.task_id,
                receipt=receipt,
            )
            print(f"[OK] Subagent task recorded: {task.task_id} [{task.status}]")
            return 0

        elif args.ledger_action == "list":
            tasks = ledger.list_tasks(status=args.status, name=args.name, limit=args.limit)
            if args.json:
                print(json.dumps([t.to_dict() for t in tasks], indent=2))
            else:
                _render_tasks_table(tasks)
            return 0

        elif args.ledger_action == "show":
            task = ledger.get_task(args.task_id)
            if not task:
                print(f"[ERROR] Task not found in ledger: {args.task_id}", file=sys.stderr)
                return 1
            events = ledger.get_events(args.task_id) if args.events else None
            if args.json:
                data = task.to_dict()
                if events is not None:
                    data["events"] = [e.to_dict() for e in events]
                print(json.dumps(data, indent=2))
            else:
                _render_task_detail(task, events=events)
            return 0

        elif args.ledger_action == "update":
            receipt = _parse_receipt_arg(args.receipt) if args.receipt else None
            sinks = _flatten_arg(args.sink) if args.sink else None
            updated = ledger.update_task(
                task_id=args.task_id,
                status=args.status,
                receipt=receipt,
                sinks=sinks,
            )
            if not updated:
                print(f"[ERROR] Task not found to update: {args.task_id}", file=sys.stderr)
                return 1
            print(f"[OK] Subagent task updated: {updated.task_id} [{updated.status}]")
            return 0

        elif args.ledger_action == "complete":
            receipt = _parse_receipt_arg(args.receipt) if args.receipt else None
            passed, task, diags = ledger.complete_task(
                task_id=args.task_id,
                receipt=receipt,
                verify_sinks=args.verify_sinks,
                min_bytes=args.min_bytes,
            )
            for d in diags:
                if d.startswith("[PASS]"):
                    print(d)
                else:
                    print(d, file=sys.stderr)
            if not task:
                print(f"[ERROR] Task not found: {args.task_id}", file=sys.stderr)
                return 1
            if not passed:
                print(
                    f"[FAIL] Task completion failed sink verification: {task.task_id}",
                    file=sys.stderr,
                )
                return 1
            print(f"[OK] Subagent task completed: {task.task_id} [COMPLETED]")
            return 0

        elif args.ledger_action == "verify":
            passed, err = ledger.verify_integrity()
            if passed:
                print("[PASS] Subagent ledger cryptographic hash chain verified (0 errors).")
                return 0
            else:
                print(
                    f"[FAIL] Subagent ledger cryptographic integrity violation: {err}",
                    file=sys.stderr,
                )
                return 1

        elif args.ledger_action == "sync":
            path = ledger.sync_json_mirror()
            print(f"[OK] Subagents mirror synchronized to: {path}")
            return 0

        else:
            ledger_parser.print_help()
            return 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
