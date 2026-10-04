"""
Unit tests for kageyoni.ledger: Universal Cryptographic Evidence Ledger.
"""

import sys
import sqlite3
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.ledger import EvidenceLedger, EvidenceRecord, GENESIS_PREV_HASH


@pytest.fixture
def mem_db():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


def test_genesis_and_chaining(mem_db):
    ledger = EvidenceLedger(mem_db)
    
    # 1. Genesis record
    rec1 = ledger.record(
        kind="scar",
        actor_id="sciel",
        topic="combat_physics",
        payload={"injury": "blunt_trauma", "severity": 0.4},
    )
    assert rec1.sequence == 1
    assert rec1.prev_hash == GENESIS_PREV_HASH
    assert len(rec1.event_hash) == 64

    # 2. Second chained record
    rec2 = ledger.record(
        kind="learning",
        actor_id="sciel",
        topic="combat_physics",
        payload={"rule": "maintain_defensive_guard_under_stress"},
    )
    assert rec2.sequence == 2
    assert rec2.prev_hash == rec1.event_hash
    assert rec2.event_hash != rec1.event_hash

    # 3. Third chained record
    rec3 = ledger.record(
        kind="receipt",
        actor_id="kage",
        topic="adjudication",
        payload={"decision": "approved"},
    )
    assert rec3.sequence == 3
    assert rec3.prev_hash == rec2.event_hash

    valid, err = ledger.verify_integrity()
    assert valid is True
    assert err is None


def test_tamper_detection(mem_db):
    ledger = EvidenceLedger(mem_db)
    rec1 = ledger.record("scar", "sciel", "combat", {"loss": 10})
    rec2 = ledger.record("learning", "sciel", "combat", {"gain": 20})

    # Assert healthy ledger initially
    valid, err = ledger.verify_integrity()
    assert valid is True

    # Tamper payload in SQLite directly without updating hash
    cursor = mem_db.cursor()
    cursor.execute("UPDATE evidence_ledger SET payload_json = ? WHERE sequence = 1", ('{"loss": 9999}',))
    mem_db.commit()

    valid, err = ledger.verify_integrity()
    assert valid is False
    assert "Tampered record at sequence 1" in err


def test_cross_domain_actor_timeline(mem_db):
    ledger = EvidenceLedger(mem_db)
    
    # Interleaved events from multiple actors and multiple operational domains
    ledger.record("scar", "sciel", "chamber_heat", {"burn": True})
    ledger.record("dialogue", "orion", "diplomacy", {"message": "negotiating peace"})
    ledger.record("outcome", "sciel", "gate_run", {"success": True})
    ledger.record("assessment", "sciel", "fatigue", {"rating": "moderate"})

    # Query sciel timeline across domains
    sciel_events = ledger.query(actor_id="sciel")
    assert len(sciel_events) == 3
    assert [e.sequence for e in sciel_events] == [1, 3, 4]
    assert [e.kind for e in sciel_events] == ["scar", "outcome", "assessment"]

    # Reverse query
    sciel_events_rev = ledger.query(actor_id="sciel", reverse=True)
    assert [e.sequence for e in sciel_events_rev] == [4, 3, 1]


def test_kind_and_topic_filtering(mem_db):
    ledger = EvidenceLedger(mem_db)
    ledger.record("scar", "sciel", "combat", {"loss": 1})
    ledger.record("scar", "kage", "stealth", {"loss": 2})
    ledger.record("receipt", "sciel", "combat", {"status": "ok"})

    # Filter by kind
    scars = ledger.query(kind="scar")
    assert len(scars) == 2
    assert {s.actor_id for s in scars} == {"sciel", "kage"}

    # Filter by topic
    combat_events = ledger.query(topic="combat")
    assert len(combat_events) == 2
    assert {c.kind for c in combat_events} == {"scar", "receipt"}

    # Filter by kind + topic
    filtered = ledger.query(kind="scar", topic="combat")
    assert len(filtered) == 1
    assert filtered[0].actor_id == "sciel"


def test_connection_recovery(tmp_path):
    db_file = tmp_path / "persistent_ledger.db"
    
    # First connection writes 2 records
    conn1 = sqlite3.connect(db_file)
    ledger1 = EvidenceLedger(conn1)
    r1 = ledger1.record("event", "actor1", "recon", {"step": 1})
    r2 = ledger1.record("event", "actor2", "recon", {"step": 2})
    conn1.close()

    # Reopen in brand new connection & instance
    conn2 = sqlite3.connect(db_file)
    ledger2 = EvidenceLedger(conn2)
    
    # Verify existing integrity
    valid, err = ledger2.verify_integrity()
    assert valid is True

    # Append 3rd record
    r3 = ledger2.record("event", "actor3", "recon", {"step": 3})
    assert r3.sequence == 3
    assert r3.prev_hash == r2.event_hash

    # Final full integrity check
    valid, err = ledger2.verify_integrity()
    assert valid is True
    assert len(ledger2.query()) == 3
    conn2.close()
