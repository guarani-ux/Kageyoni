"""
Unit tests for kageyoni.migrate: Universal Database Migration Utility.
"""

import sys
import sqlite3
import time
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.ledger import EvidenceLedger
from kageyoni.migrate import DatabaseMigrator, migrate_files


def test_legacy_multi_table_migration(tmp_path):
    src_db = tmp_path / "legacy.db"
    tgt_db = tmp_path / "migrated.db"

    # Create dummy legacy tables
    conn = sqlite3.connect(src_db)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE scars (
            scar_id TEXT PRIMARY KEY,
            actor_id TEXT,
            severity REAL,
            created_at REAL
        );
    """)
    cursor.execute("""
        CREATE TABLE outcomes (
            outcome_id TEXT PRIMARY KEY,
            actor_id TEXT,
            topic TEXT,
            success INTEGER,
            timestamp REAL
        );
    """)
    cursor.execute("""
        CREATE TABLE shinobi_action_dispatches (
            dispatch_id TEXT PRIMARY KEY,
            participant_id TEXT,
            encounter_id TEXT,
            validation_status TEXT,
            created_at REAL
        );
    """)

    # Insert interleaved timestamps
    now = time.time()
    cursor.execute("INSERT INTO scars VALUES ('s1', 'sciel', 0.5, ?)", (now + 10,))
    cursor.execute("INSERT INTO outcomes VALUES ('o1', 'kage', 'stealth', 1, ?)", (now + 20,))
    cursor.execute("INSERT INTO shinobi_action_dispatches VALUES ('d1', 'sciel', 'enc_1', 'ACCEPTED', ?)", (now + 5,))
    # Identical timestamp for tie-breaker check
    cursor.execute("INSERT INTO scars VALUES ('s2', 'sciel', 0.2, ?)", (now + 10,))
    conn.commit()
    conn.close()

    # Run migration
    count = migrate_files(src_db, tgt_db)
    assert count == 4

    # Verify target ledger
    tgt_conn = sqlite3.connect(tgt_db)
    ledger = EvidenceLedger(tgt_conn)
    
    valid, err = ledger.verify_integrity()
    assert valid is True
    assert err is None

    records = ledger.query()
    assert len(records) == 4
    # First chronologically must be d1 (now + 5)
    assert records[0].kind == "dispatch"
    assert records[0].actor_id == "sciel"

    tgt_conn.close()
