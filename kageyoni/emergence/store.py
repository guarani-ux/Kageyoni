"""
Unified Evidence and Lineage Store for Constellation Emergence.
Persists runs, round evidence, technique candidates, lineage trees, and receipts
into a shared SQLite store, powering all 6 views over a single model.
"""

from __future__ import annotations
from contextlib import contextmanager
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    CandidateDescendant,
    ConstellationManipulationRecord,
    RoundRecord,
    SynthesisOutcome,
    EvidenceDimension,
    QualificationStatus,
    ManipulationType,
)

DB_PATH = Path(__file__).resolve().parents[2] / "shinobi" / ".state" / "emergence_store.sqlite"


class EmergenceStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _get_connection(self):
        return self._connection()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp REAL,
                    config_json TEXT,
                    status TEXT,
                    synthesis_hash TEXT
                );

                CREATE TABLE IF NOT EXISTS round_evidence (
                    round_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    round_num INTEGER,
                    cycle_num INTEGER,
                    hypothesis TEXT,
                    procedure TEXT,
                    tests_json TEXT,
                    results_json TEXT,
                    evidence_digest TEXT,
                    status TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS technique_bank (
                    descendant_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    name TEXT,
                    ancestor TEXT,
                    carrier TEXT,
                    operation TEXT,
                    status TEXT,
                    dimensions_json TEXT,
                    evidence_ref TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS lineage_map (
                    link_id TEXT PRIMARY KEY,
                    descendant_id TEXT,
                    parent_id TEXT,
                    relation TEXT,
                    attribution TEXT,
                    FOREIGN KEY (descendant_id) REFERENCES technique_bank(descendant_id)
                );

                CREATE TABLE IF NOT EXISTS manipulations (
                    manipulation_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    type TEXT,
                    target TEXT,
                    observed_change TEXT,
                    gain TEXT,
                    loss TEXT,
                    new_reachability TEXT,
                    closed_reachability TEXT,
                    residue TEXT,
                    uncertainty TEXT,
                    attribution TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
            """)

    def save_run(
        self,
        run_id: str,
        config: Dict[str, Any],
        rounds: List[RoundRecord],
        bank: Optional[Dict[str, CandidateDescendant]] = None,
        synthesis: Optional[SynthesisOutcome] = None,
        technique_bank: Optional[Dict[str, CandidateDescendant]] = None,
    ) -> None:
        bank = bank if bank is not None else (technique_bank or {})
        """Persists an entire emergence run into the unified ledger."""
        with self._get_connection() as conn:
            # 1. Run entry
            conn.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?)",
                (
                    run_id,
                    time.time(),
                    json.dumps(config),
                    "COMPLETED" if synthesis else "IN_PROGRESS",
                    synthesis.synthesis_hash if synthesis else "",
                ),
            )

            # 2. Round Evidence
            for r in rounds:
                rid = f"{run_id}_r{r.round_num}"
                conn.execute(
                    "INSERT OR REPLACE INTO round_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rid,
                        run_id,
                        r.round_num,
                        r.cycle_num,
                        r.hypothesis,
                        r.procedure,
                        json.dumps([t.__dict__ for t in r.planned_tests + r.adversarial_tests]),
                        json.dumps([res.__dict__ for res in r.executed_results]),
                        r.round_result.get("evidence_digest", ""),
                        r.status.value,
                    ),
                )

            # 3. Technique Bank
            for desc in bank.values():
                conn.execute(
                    "INSERT OR REPLACE INTO technique_bank VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        desc.descendant_id,
                        run_id,
                        desc.name,
                        desc.ancestor_technique,
                        desc.carrier,
                        desc.operation,
                        desc.status.value,
                        json.dumps(desc.dimensions.to_dict() if desc.dimensions else {}),
                        desc.evidence_ref,
                    ),
                )
                # Add lineage link
                lid = f"link_{desc.descendant_id}_parent"
                conn.execute(
                    "INSERT OR REPLACE INTO lineage_map VALUES (?, ?, ?, ?, ?)",
                    (
                        lid,
                        desc.descendant_id,
                        desc.ancestor_technique,
                        "EMERGED_DESCENDANT",
                        desc.authority,
                    ),
                )

            # 4. Manipulations
            if synthesis:
                for idx, m in enumerate(synthesis.manipulations):
                    mid = f"{run_id}_man_{idx}"
                    conn.execute(
                        "INSERT OR REPLACE INTO manipulations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            mid,
                            run_id,
                            m.manipulation_type.value,
                            m.target,
                            m.observed_change,
                            m.gain,
                            m.loss,
                            m.new_reachability,
                            m.closed_reachability,
                            m.residue,
                            m.uncertainty,
                            m.attribution,
                        ),
                    )

    def get_technique_bank(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """View 2: Technique Bank — browse descendants and candidate applications."""
        with self._get_connection() as conn:
            if run_id:
                rows = conn.execute("SELECT * FROM technique_bank WHERE run_id=? ORDER BY rowid ASC", (run_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM technique_bank ORDER BY rowid DESC").fetchall()
            return [dict(r) for r in rows]

    def get_lineage_map(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """View 3: Lineage Map — inspect parentage, revisions and evidence paths."""
        with self._get_connection() as conn:
            if run_id:
                rows = conn.execute("""
                    SELECT l.*, t.name, t.status, t.carrier, t.evidence_ref
                    FROM lineage_map l
                    JOIN technique_bank t ON l.descendant_id = t.descendant_id
                    WHERE t.run_id = ?
                """, (run_id,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT l.*, t.name, t.status, t.carrier, t.evidence_ref
                    FROM lineage_map l
                    JOIN technique_bank t ON l.descendant_id = t.descendant_id
                """).fetchall()
            return [dict(r) for r in rows]

    def get_compare_and_test(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """View 4: Compare and Test — compare candidates against shared tests."""
        with self._get_connection() as conn:
            if run_id:
                rows = conn.execute("SELECT * FROM technique_bank WHERE run_id=?", (run_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM technique_bank").fetchall()
            candidates = []
            for r in rows:
                c = dict(r)
                dims = json.loads(c["dimensions_json"]) if c["dimensions_json"] else {}
                c["dimensions"] = dims
                candidates.append(c)
            return candidates

    def get_constellation_map(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """View 5: Constellation Map — inspect active points, relations and transformations."""
        with self._get_connection() as conn:
            if run_id:
                points = conn.execute("SELECT descendant_id, name, status, carrier FROM technique_bank WHERE run_id=?", (run_id,)).fetchall()
                manips = conn.execute("SELECT * FROM manipulations WHERE run_id=?", (run_id,)).fetchall()
            else:
                points = conn.execute("SELECT descendant_id, name, status, carrier FROM technique_bank").fetchall()
                manips = conn.execute("SELECT * FROM manipulations").fetchall()
            return {
                "active_points": [dict(p) for p in points],
                "transformations": [dict(m) for m in manips],
            }

    def get_runs_and_receipts(self) -> List[Dict[str, Any]]:
        """View 6: Runs and Receipts — review configurations, round evidence and outcomes."""
        with self._get_connection() as conn:
            runs = conn.execute("SELECT * FROM runs ORDER BY timestamp DESC").fetchall()
            results = []
            for r in runs:
                run_dict = dict(r)
                run_id = run_dict["run_id"]
                rounds = conn.execute("SELECT * FROM round_evidence WHERE run_id=?", (run_id,)).fetchall()
                run_dict["rounds"] = [dict(rd) for rd in rounds]
                results.append(run_dict)
            return results

    record_run = save_run
