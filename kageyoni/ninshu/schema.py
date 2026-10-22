"""Ninshū Codex & Patchbay Database Schema (SQLite).

Stores the 48-Channel SSL-style Capability Estate across 6 Master Busses,
indexed with FTS5 full-text search, 6-axis tensor coordinates,
and cryptographic RFC 8785 SHA-256 digests. Zero external dependencies.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS busses (
    bus_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    channel_range TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS channels (
    channel_number INTEGER PRIMARY KEY,
    bus_id TEXT NOT NULL REFERENCES busses(bus_id),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    carrier_path TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    
    -- 6-Axis Capability Tensor Coordinates
    subject_formats TEXT NOT NULL,      -- JSON array (e.g. ["pe", "dotnet"])
    lens_family TEXT NOT NULL,          -- e.g. "static_parser", "frida", "ghidra"
    effects_json TEXT NOT NULL,         -- 10-bit ToolEffects JSON
    reversibility_tier INTEGER NOT NULL,-- 0, 1, or 2
    epistemic_confidence TEXT NOT NULL, -- "observed", "derived", "inferred"
    coverage_status TEXT NOT NULL,      -- "complete", "partial", "unknown"
    output_mold TEXT NOT NULL,          -- "Aspect", "CandidateTechnique", "Evidence"
    
    -- Routing metadata & hash
    intent_keywords TEXT NOT NULL,
    digest_sha256 TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS channels_fts USING fts5(
    name,
    description,
    category,
    intent_keywords,
    content='channels',
    content_rowid='channel_number'
);

-- Triggers to keep FTS index synchronized
CREATE TRIGGER IF NOT EXISTS channels_ai AFTER INSERT ON channels BEGIN
    INSERT INTO channels_fts(rowid, name, description, category, intent_keywords)
    VALUES (new.channel_number, new.name, new.description, new.category, new.intent_keywords);
END;

CREATE TRIGGER IF NOT EXISTS channels_ad AFTER DELETE ON channels BEGIN
    INSERT INTO channels_fts(channels_fts, rowid, name, description, category, intent_keywords)
    VALUES ('delete', old.channel_number, old.name, old.description, old.category, old.intent_keywords);
END;

CREATE TRIGGER IF NOT EXISTS channels_au AFTER UPDATE ON channels BEGIN
    INSERT INTO channels_fts(channels_fts, rowid, name, description, category, intent_keywords)
    VALUES ('delete', old.channel_number, old.name, old.description, old.category, old.intent_keywords);
    INSERT INTO channels_fts(rowid, name, description, category, intent_keywords)
    VALUES (new.channel_number, new.name, new.description, new.category, new.intent_keywords);
END;
"""


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Initializes the database schema."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn
