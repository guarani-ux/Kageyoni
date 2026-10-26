"""Kageyoni Stateless Observation Frame Projection Driver.

Strictly satisfies Invariant Law 1 (Law of Stateless Epistemic Rendering):
Chat context is a read-only projection compiled from SQLite per turn;
zero state is derived from chat conversational history.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple


def ensure_schema(db_conn: sqlite3.Connection) -> None:
    """Ensure all required dual-runner tables exist in the database."""
    cursor = db_conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS encounters (
        encounter_id TEXT PRIMARY KEY,
        turn INTEGER NOT NULL DEFAULT 1,
        seed TEXT NOT NULL DEFAULT 'kageyoni-v11-seed',
        phase TEXT NOT NULL DEFAULT 'active',
        state_hash TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS encounter_participants (
        encounter_id TEXT NOT NULL,
        character_id TEXT NOT NULL,
        name TEXT NOT NULL,
        is_hero INTEGER NOT NULL DEFAULT 0,
        pos_x INTEGER NOT NULL DEFAULT 8,
        pos_y INTEGER NOT NULL DEFAULT 8,
        current_will INTEGER NOT NULL DEFAULT 10,
        max_will INTEGER NOT NULL DEFAULT 10,
        erosion INTEGER NOT NULL DEFAULT 0,
        emotional_state TEXT NOT NULL DEFAULT 'focused',
        calcified_armor TEXT NOT NULL DEFAULT 'None',
        PRIMARY KEY (encounter_id, character_id)
    );

    CREATE TABLE IF NOT EXISTS zenkai_scars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id TEXT NOT NULL,
        slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 3),
        anatomical_site TEXT NOT NULL,
        penalty TEXT NOT NULL,
        unlocked_art TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        UNIQUE(character_id, slot)
    );

    CREATE TABLE IF NOT EXISTS contact_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        encounter_id TEXT NOT NULL,
        turn INTEGER NOT NULL DEFAULT 1,
        attacker TEXT NOT NULL,
        defender TEXT NOT NULL,
        target_anatomy TEXT NOT NULL,
        damage INTEGER NOT NULL,
        crit INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS dialogue_options (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        encounter_id TEXT NOT NULL,
        character_id TEXT NOT NULL,
        tag TEXT NOT NULL,
        text TEXT NOT NULL,
        required_will INTEGER NOT NULL DEFAULT 0,
        max_erosion INTEGER DEFAULT NULL,
        required_capability TEXT DEFAULT NULL,
        affordance_type TEXT NOT NULL DEFAULT 'tactical',
        payload_json TEXT,
        available INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS equipped_katas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        character_id TEXT NOT NULL,
        slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 4),
        name TEXT NOT NULL,
        stamina_cost INTEGER NOT NULL DEFAULT 1,
        erosion_tick INTEGER NOT NULL DEFAULT 0,
        backlash_rating TEXT NOT NULL DEFAULT 'Low',
        description TEXT NOT NULL DEFAULT '',
        UNIQUE(character_id, slot)
    );

    CREATE TABLE IF NOT EXISTS private_action_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camp_id TEXT NOT NULL,
        companion_id TEXT NOT NULL,
        companion_name TEXT NOT NULL,
        topic TEXT NOT NULL,
        interaction_text TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tactical_tiles (
        encounter_id TEXT NOT NULL,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        terrain TEXT NOT NULL DEFAULT '.',
        PRIMARY KEY (encounter_id, x, y)
    );

    CREATE TABLE IF NOT EXISTS macro_tiles (
        sector_id TEXT NOT NULL DEFAULT 'main',
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        chunk_name TEXT NOT NULL DEFAULT 'Wilds',
        province TEXT NOT NULL DEFAULT 'Central',
        has_pass_gate INTEGER NOT NULL DEFAULT 0,
        squad_token TEXT,
        PRIMARY KEY (sector_id, x, y)
    );
    """)
    db_conn.commit()


def get_default_terrain_glyph(seed: str, x: int, y: int) -> str:
    """Deterministically generate terrain glyph based on seed and coordinates."""
    token = f"{seed}:{x}:{y}".encode("utf-8")
    h = int(hashlib.md5(token).hexdigest(), 16)
    val = h % 100
    if val < 8:
        return "#"  # mountain / barrier
    elif val < 16:
        return "~"  # water
    elif val < 30:
        return "T"  # forest
    else:
        return "."  # plains


class CapabilityAffordanceFilter:
    """Filters candidate dialogue and tactical affordances according to active constraints."""

    @staticmethod
    def filter_options(
        options: List[Dict[str, Any]],
        hero_will: int,
        hero_erosion: int,
        unlocked_arts: List[str],
        equipped_katas: List[str],
        emotional_state: str,
    ) -> List[Dict[str, Any]]:
        passed: List[Dict[str, Any]] = []
        known_capabilities = {art.lower() for art in unlocked_arts} | {kata.lower() for kata in equipped_katas}
        known_capabilities.add(emotional_state.lower())

        for opt in options:
            if not opt.get("available", 1):
                continue
            # Will constraint
            req_will = opt.get("required_will", 0)
            if hero_will < req_will:
                continue
            # Erosion constraint
            max_erosion = opt.get("max_erosion")
            if max_erosion is not None and hero_erosion > max_erosion:
                continue
            # Required capability / Art / Kata check
            req_cap = opt.get("required_capability")
            if req_cap and req_cap.lower() not in known_capabilities:
                continue
            passed.append(opt)
        return passed


class StatelessObservationFrame:
    """Stateless Observation Frame Projection Driver.
    
    Compiles a Markdown projection frame solely from SQLite state.
    Executes player actions transactionally against SQLite tables.
    """

    @classmethod
    def compile_frame(
        cls,
        db_conn: sqlite3.Connection,
        encounter_id: str,
        active_character_id: str,
    ) -> str:
        ensure_schema(db_conn)
        cursor = db_conn.cursor()

        # 1. Fetch encounter metadata
        enc_row = cursor.execute(
            "SELECT turn, seed, phase FROM encounters WHERE encounter_id = ?",
            (encounter_id,),
        ).fetchone()
        if not enc_row:
            turn = 1
            seed = "kageyoni-v11-seed"
            phase = "active"
        else:
            turn, seed, phase = enc_row

        # 2. Fetch active character data
        hero_row = cursor.execute(
            """SELECT name, is_hero, pos_x, pos_y, current_will, max_will, erosion,
                      emotional_state, calcified_armor
               FROM encounter_participants
               WHERE encounter_id = ? AND character_id = ?""",
            (encounter_id, active_character_id),
        ).fetchone()

        if not hero_row:
            # Fallback default participant
            name = active_character_id
            is_hero = 1
            pos_x, pos_y = 8, 8
            current_will, max_will = 10, 10
            erosion = 0
            emotional_state = "focused"
            calcified_armor = "None"
        else:
            (
                name,
                is_hero,
                pos_x,
                pos_y,
                current_will,
                max_will,
                erosion,
                emotional_state,
                calcified_armor,
            ) = hero_row

        # 3. Fetch all other participants in encounter
        part_rows = cursor.execute(
            """SELECT character_id, name, is_hero, pos_x, pos_y, current_will, max_will, erosion
               FROM encounter_participants
               WHERE encounter_id = ?
               ORDER BY character_id ASC""",
            (encounter_id,),
        ).fetchall()

        participants_dict = {}
        for prow in part_rows:
            participants_dict[(prow[3], prow[4])] = {
                "character_id": prow[0],
                "name": prow[1],
                "is_hero": prow[2],
                "current_will": prow[5],
                "max_will": prow[6],
                "erosion": prow[7],
            }

        # 4. Fetch Zenkai scars (1..3 slots)
        scar_rows = cursor.execute(
            """SELECT slot, anatomical_site, penalty, unlocked_art
               FROM zenkai_scars
               WHERE character_id = ? AND active = 1
               ORDER BY slot ASC""",
            (active_character_id,),
        ).fetchall()
        scars_by_slot: Dict[int, Tuple[str, str, str]] = {}
        unlocked_arts: List[str] = []
        for srow in scar_rows:
            slot, site, penalty, art = srow
            scars_by_slot[slot] = (site, penalty, art)
            unlocked_arts.append(art)

        # 5. Fetch equipped Katas
        kata_rows = cursor.execute(
            """SELECT slot, name, stamina_cost, erosion_tick, backlash_rating
               FROM equipped_katas
               WHERE character_id = ?
               ORDER BY slot ASC""",
            (active_character_id,),
        ).fetchall()
        equipped_katas = [krow[1] for krow in kata_rows]

        # 6. Fetch rolling 3-event contact ledger
        ledger_rows = cursor.execute(
            """SELECT attacker, defender, target_anatomy, damage, crit, turn
               FROM contact_ledger
               WHERE encounter_id = ?
               ORDER BY id DESC LIMIT 3""",
            (encounter_id,),
        ).fetchall()
        # Canonical order: last 3 strikes
        ledger_events = []
        for lrow in ledger_rows:
            ledger_events.append({
                "attacker": lrow[0],
                "defender": lrow[1],
                "target_anatomy": lrow[2],
                "damage": lrow[3],
                "crit": lrow[4],
                "turn": lrow[5],
            })

        # 7. Fetch custom terrain tiles in the 16x16 window
        # Window centered around (pos_x, pos_y): range [-7, 8]
        min_x = pos_x - 7
        max_x = pos_x + 8
        min_y = pos_y - 7
        max_y = pos_y + 8

        tile_rows = cursor.execute(
            """SELECT x, y, terrain FROM tactical_tiles
               WHERE encounter_id = ? AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?""",
            (encounter_id, min_x, max_x, min_y, max_y),
        ).fetchall()
        custom_tiles = {(trow[0], trow[1]): trow[2] for trow in tile_rows}

        # Build 16x16 grid lines
        grid_lines: List[str] = []
        grid_matrix: List[List[str]] = []
        for gy in range(min_y, max_y + 1):
            row_chars: List[str] = []
            for gx in range(min_x, max_x + 1):
                if gx == pos_x and gy == pos_y:
                    row_chars.append("@")
                elif (gx, gy) in participants_dict:
                    other = participants_dict[(gx, gy)]
                    if other["is_hero"]:
                        row_chars.append("@" if other["character_id"] == active_character_id else "H")
                    else:
                        row_chars.append("E")
                elif (gx, gy) in custom_tiles:
                    row_chars.append(custom_tiles[(gx, gy)])
                else:
                    row_chars.append(get_default_terrain_glyph(seed, gx, gy))
            line_str = "".join(row_chars)
            grid_lines.append(line_str)
            grid_matrix.append(row_chars)

        # 8. Fetch dialogue options and filter via CAF
        raw_options = cursor.execute(
            """SELECT id, tag, text, required_will, max_erosion, required_capability, affordance_type, payload_json, available
               FROM dialogue_options
               WHERE encounter_id = ? AND (character_id = ? OR character_id = 'all')
               ORDER BY id ASC""",
            (encounter_id, active_character_id),
        ).fetchall()

        parsed_options = []
        for opt in raw_options:
            parsed_options.append({
                "id": opt[0],
                "tag": opt[1],
                "text": opt[2],
                "required_will": opt[3],
                "max_erosion": opt[4],
                "required_capability": opt[5],
                "affordance_type": opt[6],
                "payload_json": opt[7],
                "available": opt[8],
            })

        affordances = CapabilityAffordanceFilter.filter_options(
            parsed_options,
            hero_will=current_will,
            hero_erosion=erosion,
            unlocked_arts=unlocked_arts,
            equipped_katas=equipped_katas,
            emotional_state=emotional_state,
        )

        # 9. Compute deterministic Merkle State Hash
        merkle_payload = {
            "encounter_id": encounter_id,
            "turn": turn,
            "seed": seed,
            "phase": phase,
            "active_character": {
                "id": active_character_id,
                "name": name,
                "pos": [pos_x, pos_y],
                "will": [current_will, max_will],
                "erosion": erosion,
                "emotional_state": emotional_state,
                "calcified_armor": calcified_armor,
            },
            "scars": [
                {"slot": slot, "site": scars_by_slot[slot][0], "penalty": scars_by_slot[slot][1], "art": scars_by_slot[slot][2]}
                for slot in sorted(scars_by_slot.keys())
            ],
            "katas": equipped_katas,
            "contact_ledger": ledger_events,
            "grid": grid_lines,
            "affordances": [f"[{a['tag']}] {a['text']}" for a in affordances],
        }
        merkle_json = json.dumps(merkle_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        merkle_hash = hashlib.sha256(merkle_json.encode("utf-8")).hexdigest()

        # Update encounters table with current state_hash
        cursor.execute(
            "UPDATE encounters SET state_hash = ? WHERE encounter_id = ?",
            (merkle_hash, encounter_id),
        )
        db_conn.commit()

        # 10. Format Markdown projection frame
        # Header
        merkle_header = (
            f"[STATE-V11: MERKLE_HASH={merkle_hash} | TURN={turn} | "
            f"POS=({pos_x},{pos_y}) | WILL={current_will}/{max_will} | "
            f"EROSION={erosion} | SEED={seed}]"
        )

        # Micro Tactical Lens
        tactical_lens = "### Micro 16x16 Tactical Lens\n```text\n" + "\n".join(grid_lines) + "\n```"

        # Active Constraint Capsule
        scars_lines = []
        for slot_idx in range(1, 4):
            if slot_idx in scars_by_slot:
                site, pen, art = scars_by_slot[slot_idx]
                scars_lines.append(
                    f"- Slot {slot_idx}: [{site}] Penalty: {pen} | Unlocked Compensatory Art: [{art}]"
                )
            else:
                scars_lines.append(f"- Slot {slot_idx}: [Empty]")

        constraint_capsule = (
            "### Active Constraint Capsule\n"
            f"- **Emotional State**: {emotional_state}\n"
            f"- **Calcified Armor**: {calcified_armor}\n"
            "- **Active Zenkai Scars**:\n  " + "\n  ".join(scars_lines)
        )

        # Rolling 3-Event Contact Ledger
        ledger_lines = []
        if ledger_events:
            for idx, event in enumerate(ledger_events):
                crit_badge = " (CRIT)" if event["crit"] else ""
                ledger_lines.append(
                    f"{idx + 1}. [Turn {event['turn']}] {event['attacker']} -> {event['defender']} "
                    f"on [{event['target_anatomy']}]: {event['damage']} DMG{crit_badge}"
                )
        else:
            ledger_lines.append("- [No contact strikes recorded in ledger]")
        ledger_section = "### Rolling 3-Event Contact Ledger\n" + "\n".join(ledger_lines)

        # Available Dialogue / Tactical Affordances
        affordance_lines = []
        if affordances:
            for idx, opt in enumerate(affordances):
                affordance_lines.append(f"{idx + 1}. [{opt['tag']}] {opt['text']}")
        else:
            affordance_lines.append("- [No available affordances for current Will/Erosion constraints]")
        affordance_section = "### Available Dialogue / Tactical Affordances\n" + "\n".join(affordance_lines)

        # Full frame assembly
        sections = [
            merkle_header,
            "",
            tactical_lens,
            "",
            constraint_capsule,
            "",
            ledger_section,
            "",
            affordance_section,
        ]
        return "\n".join(sections)

    @classmethod
    def process_action(
        cls,
        db_conn: sqlite3.Connection,
        encounter_id: str,
        character_id: str,
        action_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an action transactionally against SQLite tables.
        
        Mutates positions, spends will, applies damage, and enqueues strikes.
        Returns the updated state digest.
        """
        ensure_schema(db_conn)
        cursor = db_conn.cursor()

        with db_conn:
            # 1. Fetch encounter
            enc_row = cursor.execute(
                "SELECT turn, seed, phase FROM encounters WHERE encounter_id = ?",
                (encounter_id,),
            ).fetchone()
            if not enc_row:
                cursor.execute(
                    "INSERT INTO encounters (encounter_id, turn, seed, phase) VALUES (?, 1, 'kageyoni-v11-seed', 'active')",
                    (encounter_id,),
                )
                turn = 1
                seed = "kageyoni-v11-seed"
            else:
                turn, seed, _ = enc_row

            # 2. Fetch actor
            actor_row = cursor.execute(
                """SELECT pos_x, pos_y, current_will, max_will, erosion, name
                   FROM encounter_participants
                   WHERE encounter_id = ? AND character_id = ?""",
                (encounter_id, character_id),
            ).fetchone()

            if not actor_row:
                pos_x, pos_y = 8, 8
                curr_will, max_will = 10, 10
                erosion = 0
                actor_name = character_id
                cursor.execute(
                    """INSERT INTO encounter_participants
                       (encounter_id, character_id, name, is_hero, pos_x, pos_y, current_will, max_will, erosion)
                       VALUES (?, ?, ?, 1, 8, 8, 10, 10, 0)""",
                    (encounter_id, character_id, actor_name),
                )
            else:
                pos_x, pos_y, curr_will, max_will, erosion, actor_name = actor_row

            action_type = action_payload.get("type", "generic")

            # Movement mutation
            dx = action_payload.get("dx", 0)
            dy = action_payload.get("dy", 0)
            if "new_pos" in action_payload:
                new_x, new_y = action_payload["new_pos"]
            else:
                new_x = pos_x + dx
                new_y = pos_y + dy

            # Will & erosion mutation
            spend_will = action_payload.get("spend_will", 0)
            erosion_tick = action_payload.get("erosion_tick", 0)
            new_will = max(0, curr_will - spend_will)
            new_erosion = max(0, erosion + erosion_tick)

            # Update actor record
            cursor.execute(
                """UPDATE encounter_participants
                   SET pos_x = ?, pos_y = ?, current_will = ?, erosion = ?
                   WHERE encounter_id = ? AND character_id = ?""",
                (new_x, new_y, new_will, new_erosion, encounter_id, character_id),
            )

            # Strike / Combat event
            strike_data = action_payload.get("strike")
            if not strike_data and action_type == "strike":
                strike_data = {
                    "attacker": action_payload.get("attacker", actor_name),
                    "defender": action_payload.get("defender", "enemy"),
                    "target_anatomy": action_payload.get("target_anatomy", "torso"),
                    "damage": action_payload.get("damage", 10),
                    "crit": action_payload.get("crit", 0),
                }

            if strike_data:
                attacker = strike_data.get("attacker", actor_name)
                defender = strike_data.get("defender", "target")
                anatomy = strike_data.get("target_anatomy", "torso")
                damage = int(strike_data.get("damage", 0))
                crit = int(bool(strike_data.get("crit", 0)))

                cursor.execute(
                    """INSERT INTO contact_ledger
                       (encounter_id, turn, attacker, defender, target_anatomy, damage, crit)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (encounter_id, turn, attacker, defender, anatomy, damage, crit),
                )

                # If defender is in encounter participants, apply damage to will or record
                def_row = cursor.execute(
                    "SELECT current_will FROM encounter_participants WHERE encounter_id = ? AND (character_id = ? OR name = ?)",
                    (encounter_id, defender, defender),
                ).fetchone()
                if def_row:
                    def_new_will = max(0, def_row[0] - damage)
                    cursor.execute(
                        "UPDATE encounter_participants SET current_will = ? WHERE encounter_id = ? AND (character_id = ? OR name = ?)",
                        (def_new_will, encounter_id, defender, defender),
                    )

            # Advance turn unless explicitly asked not to
            advance_turn = action_payload.get("advance_turn", True)
            updated_turn = turn + 1 if advance_turn else turn
            cursor.execute(
                "UPDATE encounters SET turn = ? WHERE encounter_id = ?",
                (updated_turn, encounter_id),
            )

        # Compute updated Merkle state digest by compiling frame
        new_frame = cls.compile_frame(db_conn, encounter_id, character_id)
        # Extract new Merkle hash from header
        merkle_hash = ""
        for line in new_frame.splitlines():
            if line.startswith("[STATE-V11: MERKLE_HASH="):
                parts = line.split("|")
                for p in parts:
                    if "MERKLE_HASH=" in p:
                        merkle_hash = p.split("MERKLE_HASH=")[1].strip()
                        break
                break

        return {
            "status": "ok",
            "encounter_id": encounter_id,
            "character_id": character_id,
            "turn": updated_turn,
            "pos": (new_x, new_y),
            "will": (new_will, max_will),
            "erosion": new_erosion,
            "merkle_hash": merkle_hash,
            "frame": new_frame,
        }
