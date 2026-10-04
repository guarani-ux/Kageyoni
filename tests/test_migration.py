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



def test_export_repeat_unknown_time_and_readonly_source(tmp_path):
    import hashlib
    source=tmp_path/'source.sqlite';target=tmp_path/'target.sqlite'
    conn=sqlite3.connect(source)
    conn.execute('CREATE TABLE "quoted table" (id TEXT PRIMARY KEY, created_at TEXT, body BLOB) WITHOUT ROWID')
    conn.execute('INSERT INTO "quoted table" VALUES(?,?,?)',('one','2020-01-01T00:00:00Z',b'bytes'))
    conn.execute('INSERT INTO "quoted table" VALUES(?,?,?)',('two','unknown',b'other'))
    conn.commit();conn.close()
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    assert migrate_files(source,target)==2
    assert migrate_files(source,target)==0
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    conn=sqlite3.connect(target);records=EvidenceLedger(conn).query()
    assert records[0].payload['source_timestamp']==1577836800
    assert records[1].payload['source_timestamp'] is None
    assert records[1].payload['source_row']['created_at']=='unknown'
    assert records[0].payload['source_row']['body']=={'sqlite_blob_hex':b'bytes'.hex()}
    with pytest.raises(ValueError):migrate_files(source,source)
    conn.close()


def test_export_failure_is_atomic(tmp_path):
    from unittest.mock import patch
    source=sqlite3.connect(':memory:');source.execute('CREATE TABLE data(id INTEGER)')
    source.executemany('INSERT INTO data VALUES(?)',[(1,),(2,)]);source.commit()
    target=sqlite3.connect(tmp_path/'target.sqlite');ledger=EvidenceLedger(target)
    original=ledger.record;attempts=[]
    def injected(**kwargs):
        attempts.append(kwargs)
        if len(attempts)==2:raise RuntimeError('injected export interruption')
        return original(**kwargs)
    with patch.object(ledger,'record',side_effect=injected):
        with pytest.raises(RuntimeError):DatabaseMigrator(ledger).migrate_from_connection(source)
    assert ledger.query()==[]
    assert DatabaseMigrator(ledger).migrate_from_connection(source)==2
    source.close();target.close()
