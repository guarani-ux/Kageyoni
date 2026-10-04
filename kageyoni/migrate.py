"""
kageyoni.migrate: Universal Database Migration Utility.

Migrates legacy unchained SQLite tables (scars, outcomes, dispatches, assessments)
into the SHA-256 hash-chained EvidenceLedger schema with deterministic sorting.
"""

from __future__ import annotations
import argparse
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kageyoni.ledger import EvidenceLedger


class DatabaseMigrator:
    """
    Deterministic ETL pipeline translating heterogeneous legacy tables
    into a unified cryptographic evidence ledger.
    """

    def __init__(self, target_ledger: EvidenceLedger):
        self.ledger = target_ledger

    def migrate_from_connection(self, source_conn: sqlite3.Connection) -> int:
        cursor = source_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in cursor.fetchall()]

        extracted_events: List[Dict[str, Any]] = []

        for tbl in tables:
            cursor.execute(f"PRAGMA table_info({tbl});")
            columns = [c[1] for c in cursor.fetchall()]
            
            # Query all rows with rowid for deterministic tie-breaking
            cursor.execute(f"SELECT rowid, * FROM {tbl};")
            rows = cursor.fetchall()

            for row in rows:
                rowid = row[0]
                col_data = dict(zip(columns, row[1:]))

                # Normalize kind, actor, topic, and timestamp
                kind = "event"
                actor_id = "unknown"
                topic = tbl
                ts = time.time()
                payload = dict(col_data)

                if "actor_id" in col_data and col_data["actor_id"]:
                    actor_id = str(col_data["actor_id"])
                elif "participant_id" in col_data and col_data["participant_id"]:
                    actor_id = str(col_data["participant_id"])

                if "scar_id" in col_data:
                    kind = "scar"
                elif "outcome_id" in col_data:
                    kind = "outcome"
                elif "dispatch_id" in col_data:
                    kind = "dispatch"
                elif "assessment_id" in col_data:
                    kind = "assessment"

                if "topic" in col_data and col_data["topic"]:
                    topic = str(col_data["topic"])
                elif "encounter_id" in col_data and col_data["encounter_id"]:
                    topic = str(col_data["encounter_id"])

                # Timestamp extraction
                for ts_col in ("created_at", "timestamp", "date_recorded", "time"):
                    if ts_col in col_data and col_data[ts_col]:
                        val = col_data[ts_col]
                        try:
                            if isinstance(val, (int, float)):
                                ts = float(val)
                            elif isinstance(val, str):
                                # ISO string or float string
                                try:
                                    ts = float(val)
                                except ValueError:
                                    ts = time.time()
                            break
                        except Exception:
                            pass

                extracted_events.append({
                    "rowid": rowid,
                    "created_at": ts,
                    "kind": kind,
                    "actor_id": actor_id,
                    "topic": topic,
                    "payload": payload,
                })

        # Deterministic sorting: timestamp ASC, tie-breaker rowid ASC
        extracted_events.sort(key=lambda x: (x["created_at"], x["rowid"]))

        migrated_count = 0
        for ev in extracted_events:
            self.ledger.record(
                kind=ev["kind"],
                actor_id=ev["actor_id"],
                topic=ev["topic"],
                payload=ev["payload"],
            )
            migrated_count += 1

        # Verify target ledger integrity post-migration
        valid, err = self.ledger.verify_integrity()
        if not valid:
            raise RuntimeError(f"Post-migration integrity verification failed: {err}")

        return migrated_count


def migrate_files(source_path: Path, target_path: Path) -> int:
    src_conn = sqlite3.connect(str(source_path))
    tgt_conn = sqlite3.connect(str(target_path))
    try:
        ledger = EvidenceLedger(tgt_conn)
        migrator = DatabaseMigrator(ledger)
        count = migrator.migrate_from_connection(src_conn)
        return count
    finally:
        src_conn.close()
        tgt_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate legacy SQLite tables to EvidenceLedger.")
    parser.add_argument("--source", required=True, type=Path, help="Path to legacy SQLite DB")
    parser.add_argument("--target", required=True, type=Path, help="Path to target EvidenceLedger DB")
    args = parser.parse_args()

    n = migrate_files(args.source, args.target)
    print(f"Successfully migrated {n} records to {args.target}")
