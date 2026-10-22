"""Ninshū Patchbay & Query Engine.

Provides instant FTS5 / multi-axis routing over the 48-channel desk.
Used by situated Daimons to retrieve exact channel strips on-demand
without loading the whole estate into LLM context.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .schema import init_db
from .seeds import BUSSES, CHANNELS, digest_record

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "ninshu_codex.sqlite"


class Patchbay:
    """The SSL 4000 Patchbay for Kageyōni and REA."""

    def __init__(self, db_path: Optional[str | Path] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        is_new = not self.db_path.exists()
        self.conn = init_db(self.db_path)
        if is_new or self._channel_count() == 0:
            self.seed()

    def _channel_count(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM channels")
        return cur.fetchone()[0]

    def seed(self) -> None:
        """Seeds the database with the 6 Busses and 48 Channels."""
        with self.conn:
            # Seed Busses
            for b in BUSSES:
                self.conn.execute(
                    "INSERT OR REPLACE INTO busses (bus_id, name, description, channel_range) VALUES (?, ?, ?, ?)",
                    (b["bus_id"], b["name"], b["description"], b["channel_range"])
                )

            # Seed Channels
            for c in CHANNELS:
                digest = digest_record(c)
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO channels (
                        channel_number, bus_id, name, category, description,
                        carrier_path, entrypoint, subject_formats, lens_family,
                        effects_json, reversibility_tier, epistemic_confidence,
                        coverage_status, output_mold, intent_keywords, digest_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c["channel_number"],
                        c["bus_id"],
                        c["name"],
                        c["category"],
                        c["description"],
                        c["carrier_path"],
                        c["entrypoint"],
                        json.dumps(c["subject_formats"]),
                        c["lens_family"],
                        json.dumps(c["effects"]),
                        c["reversibility_tier"],
                        c["epistemic_confidence"],
                        c["coverage_status"],
                        c["output_mold"],
                        c["intent_keywords"],
                        digest
                    )
                )

    def get_busses(self) -> List[Dict[str, Any]]:
        """Returns all 6 Master Busses."""
        rows = self.conn.execute("SELECT * FROM busses ORDER BY bus_id").fetchall()
        return [dict(r) for r in rows]

    def get_channel(self, channel_number: int) -> Optional[Dict[str, Any]]:
        """Returns a single channel strip by channel number."""
        row = self.conn.execute("SELECT * FROM channels WHERE channel_number = ?", (channel_number,)).fetchone()
        if not row:
            return None
        res = dict(row)
        res["subject_formats"] = json.loads(res["subject_formats"])
        res["effects"] = json.loads(res["effects_json"])
        return res

    def list_channels(self, bus_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all channels, optionally filtered by bus."""
        query = "SELECT * FROM channels"
        params: list[Any] = []
        if bus_id:
            query += " WHERE bus_id = ?"
            params.append(bus_id)
        query += " ORDER BY channel_number"
        rows = self.conn.execute(query, params).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["subject_formats"] = json.loads(d["subject_formats"])
            d["effects"] = json.loads(d["effects_json"])
            res.append(d)
        return res

    def route(
        self,
        intent: str,
        subject: Optional[str] = None,
        max_tier: int = 2,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Routes a natural language intent or technical keyword to the optimal channel strips.
        Filters by subject format compatibility and reversibility tier.
        """
        # Clean intent tokens for FTS5
        clean_tokens = [w for w in intent.lower().replace(":", " ").replace("-", " ").split() if len(w) >= 2]
        if not clean_tokens:
            return []

        fts_query = " OR ".join(f'"{t}"' for t in clean_tokens)
        
        sql = """
        SELECT c.*, rank
        FROM channels c
        JOIN channels_fts fts ON c.channel_number = fts.rowid
        WHERE channels_fts MATCH ?
          AND c.reversibility_tier <= ?
        ORDER BY rank
        LIMIT ?
        """
        rows = self.conn.execute(sql, (fts_query, max_tier, limit * 2)).fetchall()
        
        matched: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["subject_formats"] = json.loads(d["subject_formats"])
            d["effects"] = json.loads(d["effects_json"])
            
            # Filter by subject if specified
            if subject and subject.lower() not in [s.lower() for s in d["subject_formats"]] and "file" not in d["subject_formats"]:
                continue
                
            matched.append(d)
            if len(matched) >= limit:
                break
                
        return matched

    def patch(
        self,
        channel_numbers: List[int],
        daimon_name: str = "ad_hoc_submix"
    ) -> Dict[str, Any]:
        """
        Builds a multi-track Ninshū Sub-Mix Patch from a list of channel numbers.
        Returns the runnable wiring manifest without code duplication.
        """
        strips = []
        for ch in channel_numbers:
            strip = self.get_channel(ch)
            if strip:
                strips.append(strip)

        max_tier = max((s["reversibility_tier"] for s in strips), default=0)
        
        return {
            "patch_id": f"patch:{daimon_name}",
            "channel_count": len(strips),
            "reversibility_tier": max_tier,
            "requires_human_gate": max_tier > 0,
            "channel_strips": [
                {
                    "ch": s["channel_number"],
                    "name": s["name"],
                    "bus": s["bus_id"],
                    "carrier": s["carrier_path"],
                    "entrypoint": s["entrypoint"],
                    "authority": s["epistemic_confidence"],
                    "tier": s["reversibility_tier"]
                }
                for s in strips
            ]
        }
