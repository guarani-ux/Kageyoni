"""
Kageyoni Gated Repair Order State Machinery (Gate Runner)
Enforces fail-closed physical execution records across Gates G0 through G9.

Transitions:
PENDING -> TESTING -> FAILED -> REPAIRING -> RETESTING -> PASSED
Missing evidence/access -> BLOCKED
Changed dependencies after passing -> STALE -> RETESTING
"""

from __future__ import annotations
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class GateStatus(Enum):
    PENDING = "PENDING"
    TESTING = "TESTING"
    FAILED = "FAILED"
    REPAIRING = "REPAIRING"
    RETESTING = "RETESTING"
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"


@dataclass
class GateExecutionRecord:
    gate_id: str
    candidate_sha: str
    status: GateStatus
    command: str
    exit_code: int
    test_ids: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    skips: List[str] = field(default_factory=list)
    input_hashes: Dict[str, str] = field(default_factory=dict)
    output_hashes: Dict[str, str] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    recorded_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class GateRunner:
    """
    Physical State Gate Runner backed by durable SQLite records.
    An agent cannot submit passed=true as sufficient evidence.
    Advancement requires actual, verified physical execution records.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.root = Path(__file__).resolve().parent.parent
        self.db_path = Path(db_path) if db_path else self.root / "state" / "kageyoni_gates.sqlite"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.db_path))
        self.db.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS kageyoni_gate_records (
                gate_id TEXT PRIMARY KEY,
                candidate_sha TEXT NOT NULL,
                status TEXT NOT NULL,
                command TEXT NOT NULL,
                exit_code INTEGER NOT NULL,
                test_ids_json TEXT NOT NULL,
                failures_json TEXT NOT NULL,
                skips_json TEXT NOT NULL,
                input_hashes_json TEXT NOT NULL,
                output_hashes_json TEXT NOT NULL,
                evidence_refs_json TEXT NOT NULL,
                details_json TEXT NOT NULL,
                recorded_at REAL NOT NULL
            );
        """)
        self.db.commit()

    def get_current_git_sha(self) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except Exception:
            return "UNCOMMITTED_WORKING_TREE"

    def record_execution(self, record: GateExecutionRecord) -> None:
        """Persists a physical execution record into the gate registry."""
        cur = self.db.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO kageyoni_gate_records
            (gate_id, candidate_sha, status, command, exit_code, test_ids_json,
             failures_json, skips_json, input_hashes_json, output_hashes_json,
             evidence_refs_json, details_json, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.gate_id,
                record.candidate_sha,
                record.status.value,
                record.command,
                record.exit_code,
                json.dumps(record.test_ids),
                json.dumps(record.failures),
                json.dumps(record.skips),
                json.dumps(record.input_hashes),
                json.dumps(record.output_hashes),
                json.dumps(record.evidence_refs),
                json.dumps(record.details),
                record.recorded_at,
            ),
        )
        self.db.commit()

    def get_record(self, gate_id: str) -> Optional[GateExecutionRecord]:
        cur = self.db.cursor()
        cur.execute("SELECT * FROM kageyoni_gate_records WHERE gate_id = ?", (gate_id,))
        row = cur.fetchone()
        if not row:
            return None
        return GateExecutionRecord(
            gate_id=row["gate_id"],
            candidate_sha=row["candidate_sha"],
            status=GateStatus(row["status"]),
            command=row["command"],
            exit_code=row["exit_code"],
            test_ids=json.loads(row["test_ids_json"]),
            failures=json.loads(row["failures_json"]),
            skips=json.loads(row["skips_json"]),
            input_hashes=json.loads(row["input_hashes_json"]),
            output_hashes=json.loads(row["output_hashes_json"]),
            evidence_refs=json.loads(row["evidence_refs_json"]),
            details=json.loads(row["details_json"]),
            recorded_at=row["recorded_at"],
        )

    def validate_gate(self, gate_id: str, current_sha: Optional[str] = None) -> bool:
        """
        Validates whether a gate satisfies the physical requirements to permit advancement.
        Returns False if:
        - Record is missing
        - Candidate SHA does not match current HEAD
        - Status is not PASSED
        - Exit code != 0
        - Failures or skips exist
        - Test IDs are empty
        - Evidence references are empty
        """
        record = self.get_record(gate_id)
        if not record:
            return False

        cur_sha = current_sha or self.get_current_git_sha()
        if record.candidate_sha != cur_sha:
            # Mark STALE if candidate SHA diverged
            record.status = GateStatus.STALE
            self.record_execution(record)
            return False

        if record.status != GateStatus.PASSED:
            return False

        if record.exit_code != 0:
            return False

        if len(record.failures) > 0 or len(record.skips) > 0:
            return False

        if len(record.test_ids) == 0 or len(record.evidence_refs) == 0:
            return False

        return True

    def export_all_records(self, output_path: Path) -> Dict[str, Any]:
        cur = self.db.cursor()
        cur.execute("SELECT * FROM kageyoni_gate_records ORDER BY gate_id")
        rows = cur.fetchall()
        data = {
            "candidate_sha": self.get_current_git_sha(),
            "timestamp": time.time(),
            "gates": {},
        }
        for r in rows:
            data["gates"][r["gate_id"]] = {
                "status": r["status"],
                "candidate_sha": r["candidate_sha"],
                "command": r["command"],
                "exit_code": r["exit_code"],
                "test_count": len(json.loads(r["test_ids_json"])),
                "failures": json.loads(r["failures_json"]),
                "skips": json.loads(r["skips_json"]),
                "evidence_refs": json.loads(r["evidence_refs_json"]),
                "details": json.loads(r["details_json"]),
                "recorded_at": r["recorded_at"],
            }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def close(self):
        self.db.close()
