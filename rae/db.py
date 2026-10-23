"""Knowledge DB access for RAE. Read-only on knowledge/sources; writes only to work_products."""
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "workspace" / "intel" / "vibe-knowledge.db"


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def get_element(ref):
    """Retrieve an element by id or title fragment. Returns dict with verification status."""
    db = get_db()
    try:
        if str(ref).isdigit():
            row = db.execute(
                "SELECT k.*, s.title AS source_title, s.url AS source_url FROM knowledge k "
                "LEFT JOIN sources s ON k.source_id = s.id WHERE k.id = ?", (int(ref),)
            ).fetchone()
        else:
            row = db.execute(
                "SELECT k.*, s.title AS source_title, s.url AS source_url FROM knowledge k "
                "LEFT JOIN sources s ON k.source_id = s.id WHERE k.title LIKE ? "
                "ORDER BY CASE k.status WHEN 'verified' THEN 0 WHEN 'candidate' THEN 1 ELSE 2 END LIMIT 1",
                (f"%{ref}%",),
            ).fetchone()
        if row is None:
            raise ValueError(f"No knowledge element matching {ref!r}")
        return dict(row)
    finally:
        db.close()


def register_work_product(title, file_path, knowledge_ids, summary="", kind="reified artifact"):
    """Register the reified artifact as a work product linked to its source element(s)."""
    import datetime
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO work_products (title, kind, date_created, path, summary) VALUES (?, ?, ?, ?, ?)",
            (title, kind, datetime.date.today().isoformat(), str(file_path), summary),
        )
        wp_id = cur.lastrowid
        for kid in knowledge_ids:
            db.execute(
                "INSERT OR IGNORE INTO knowledge_work_links (knowledge_id, work_id) VALUES (?, ?)",
                (kid, wp_id),
            )
        db.commit()
        return wp_id
    finally:
        db.close()
