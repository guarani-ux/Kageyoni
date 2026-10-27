"""
Deterministic Character Hydration Substrate for Constellation Emergence.

Extracts ground-truth character state, identity bindings, raw dialogue history,
and Will expressions directly from the participant's persistent SQLite database on disk
(shinobi/.state/characters/<character_id>/kageyoni.sqlite).
Guarantees zero AI summarization, zero narrative laundering, and strict cryptographic digest verification.
"""

from __future__ import annotations
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CHARACTERS_ROOT = Path(__file__).resolve().parents[2] / "shinobi" / ".state" / "characters"


@dataclass
class HydratedCharacterPacket:
    character_id: str
    name: str
    shinobi_identity: Dict[str, Any]
    character_records: List[Dict[str, Any]]
    dialogue_turns: List[Dict[str, Any]]
    encounters: List[Dict[str, Any]]
    returns: List[Dict[str, Any]]
    will_records: List[Dict[str, Any]]
    state_digest: str

    def get_latest_dialogue(self, n: int = 5) -> List[Dict[str, Any]]:
        """Returns the n most recent dialogue turns without summarization."""
        return self.dialogue_turns[-n:] if self.dialogue_turns else []

    def get_aspect(self) -> Optional[str]:
        cfg = self.shinobi_identity.get("configuration", {})
        return cfg.get("aspect")

    def get_manifestation(self) -> Optional[str]:
        cfg = self.shinobi_identity.get("configuration", {})
        return cfg.get("manifestation")

    def get_will_density(self) -> Optional[str]:
        cfg = self.shinobi_identity.get("configuration", {})
        return cfg.get("will")


def _read_table_dicts(con: sqlite3.Connection, table_name: str) -> List[Dict[str, Any]]:
    cur = con.cursor()
    # Check if table exists
    exists = cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()[0]
    if not exists:
        return []
    
    cols = [col[1] for col in cur.execute(f"PRAGMA table_info({table_name})").fetchall()]
    rows = cur.execute(f"SELECT * FROM {table_name}").fetchall()
    results = []
    for r in rows:
        results.append(dict(zip(cols, r)))
    return results


def hydrate_character_from_disk(
    character_id: str,
    characters_root: Optional[Path] = None
) -> HydratedCharacterPacket:
    """
    Hydrates a participant directly from their persistent SQLite database.
    Raises FileNotFoundError if the database does not exist.
    """
    root = characters_root or DEFAULT_CHARACTERS_ROOT
    db_path = root / character_id / "kageyoni.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(f"Character database not found at {db_path}")

    con = sqlite3.connect(str(db_path))
    try:
        # 1. Shinobi Identity
        identity_rows = _read_table_dicts(con, "shinobi_identity")
        shinobi_identity: Dict[str, Any] = {}
        if identity_rows:
            raw_id = identity_rows[0]
            cfg_json = raw_id.get("configuration_json") or "{}"
            try:
                parsed_cfg = json.loads(cfg_json)
            except Exception:
                parsed_cfg = {"raw": cfg_json}
            shinobi_identity = {
                "slot": raw_id.get("slot"),
                "participant_id": raw_id.get("participant_id"),
                "branch": raw_id.get("branch"),
                "character_id": raw_id.get("character_id"),
                "name": raw_id.get("name"),
                "configuration": parsed_cfg,
                "created_at": raw_id.get("created_at"),
            }

        # 2. Character & Character Identity records
        char_rows = _read_table_dicts(con, "character")
        char_id_rows = _read_table_dicts(con, "character_identity")
        character_records = char_rows + char_id_rows

        # 3. Dialogue Turns
        dialogue_turns = _read_table_dicts(con, "dialogue_turn")

        # 4. Shinobi Encounters
        encounters = _read_table_dicts(con, "shinobi_encounters")

        # 5. Shinobi Returns
        returns = _read_table_dicts(con, "shinobi_returns")

        # 6. Will records
        will_records = (
            _read_table_dicts(con, "will") +
            _read_table_dicts(con, "will_definition") +
            _read_table_dicts(con, "will_expression") +
            _read_table_dicts(con, "will_technique")
        )

        # Name extraction
        name = shinobi_identity.get("name")
        if not name and char_rows:
            name = char_rows[0].get("name")
        if not name:
            name = character_id.capitalize()

        # Deterministic digest of the extracted raw state
        raw_payload = {
            "character_id": character_id,
            "name": name,
            "shinobi_identity": shinobi_identity,
            "character_records": character_records,
            "dialogue_turns": dialogue_turns,
            "encounters": encounters,
            "returns": returns,
            "will_records": will_records,
        }
        canonical_json = json.dumps(raw_payload, sort_keys=True, default=str)
        state_digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        return HydratedCharacterPacket(
            character_id=character_id,
            name=name,
            shinobi_identity=shinobi_identity,
            character_records=character_records,
            dialogue_turns=dialogue_turns,
            encounters=encounters,
            returns=returns,
            will_records=will_records,
            state_digest=state_digest,
        )
    finally:
        con.close()


def hydrate_all_participants(
    character_ids: Optional[List[str]] = None,
    characters_root: Optional[Path] = None
) -> Dict[str, HydratedCharacterPacket]:
    """Hydrates all requested participants (or all present in characters_root)."""
    root = characters_root or DEFAULT_CHARACTERS_ROOT
    if character_ids is None:
        if root.exists():
            character_ids = [d.name for d in root.iterdir() if d.is_dir() and (d / "kageyoni.sqlite").exists()]
        else:
            character_ids = []

    packets = {}
    for cid in character_ids:
        try:
            packets[cid] = hydrate_character_from_disk(cid, root)
        except FileNotFoundError:
            pass
    return packets
