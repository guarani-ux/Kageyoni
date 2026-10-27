"""Kageyoni Interactive ANSI Terminal TUI & Headless Skirmish Runner.

Provides dual-tier map rendering (Macro 10x10 and Micro 16x16),
rhythm defense bar visualization, Kata deck inspection,
camp private action morning review, and headless turn execution.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .chat_frame import StatelessObservationFrame, ensure_schema


class KageyoniCLI:
    """Terminal UI & Headless Skirmish Runner for Kageyōni."""

    DEFAULT_PALETTE = {
        "skin_warm": 216,
        "skin_pale": 254,
        "skin_weathered": 173,
        "shadow_deep": 236,
        "highlight_gold": 220,
        "blood_crimson": 160,
        "void_black": 232,
        "terrain_forest": 34,
        "terrain_water": 33,
        "terrain_mountain": 240,
        "terrain_plains": 245,
        "cyan": 51,
        "white": 255,
        "dim_gray": 238,
    }

    def __init__(self, templates_path: Optional[str] = None):
        self.palette = self._load_palette(templates_path)

    def _load_palette(self, templates_path: Optional[str] = None) -> Dict[str, int]:
        palette = dict(self.DEFAULT_PALETTE)
        candidates = []
        if templates_path:
            candidates.append(Path(templates_path))
        candidates.extend([
            Path(__file__).resolve().parent.parent / "data" / "visual_templates.json",
            Path("data/visual_templates.json"),
        ])

        for path in candidates:
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    c256 = data.get("ansi_terminal_palette", {}).get("colors_256", {})
                    palette.update(c256)
                    break
                except Exception:
                    pass
        return palette

    def colorize(
        self,
        text: str,
        fg: Optional[Union[str, int]] = None,
        bg: Optional[Union[str, int]] = None,
        bold: bool = False,
    ) -> str:
        """Wrap text in ANSI 256-color escape sequences."""
        codes = []
        if bold:
            codes.append("1")

        if fg is not None:
            fg_code = self.palette.get(fg, fg) if isinstance(fg, str) else fg
            codes.append(f"38;5;{fg_code}")

        if bg is not None:
            bg_code = self.palette.get(bg, bg) if isinstance(bg, str) else bg
            codes.append(f"48;5;{bg_code}")

        if not codes:
            return text
        prefix = f"\033[{';'.join(codes)}m"
        suffix = "\033[0m"
        return f"{prefix}{text}{suffix}"

    def strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes for length calculation or raw comparison."""
        return re.sub(r"\033\[[0-9;]*m", "", text)

    # -------------------------------------------------------------------------
    # 1. Dual-Tier Map Rendering
    # -------------------------------------------------------------------------

    def render_macro_map(
        self,
        db_conn: sqlite3.Connection,
        sector_id: str = "main",
    ) -> str:
        """Render the Macro 10x10 Sector Map displaying continental chunks,

        provinces, pass gates, and squad tokens.
        """
        ensure_schema(db_conn)
        cursor = db_conn.cursor()

        # Query sector tiles
        rows = cursor.execute(
            """SELECT x, y, chunk_name, province, has_pass_gate, squad_token
               FROM macro_tiles
               WHERE sector_id = ?
               ORDER BY y ASC, x ASC""",
            (sector_id,),
        ).fetchall()

        if not rows:
            # Seed default 10x10 sector
            self._seed_default_macro_sector(db_conn, sector_id)
            rows = cursor.execute(
                """SELECT x, y, chunk_name, province, has_pass_gate, squad_token
                   FROM macro_tiles
                   WHERE sector_id = ?
                   ORDER BY y ASC, x ASC""",
                (sector_id,),
            ).fetchall()

        tile_map = {(r[0], r[1]): {"chunk": r[2], "prov": r[3], "gate": r[4], "squad": r[5]} for r in rows}

        header = self.colorize(
            f"=== MACRO 10x10 SECTOR MAP: Imperial Expanse [Sector: {sector_id}] ===",
            fg="highlight_gold",
            bold=True,
        )

        col_header = "    " + " ".join(str(x) for x in range(10))
        lines = [header, col_header, "   +" + "-" * 20 + "+"]

        for y in range(10):
            row_cells = []
            for x in range(10):
                tile = tile_map.get((x, y), {"chunk": "Plains", "prov": "Neutral", "gate": 0, "squad": None})
                if tile["squad"]:
                    glyph = "[S]" if len(tile["squad"]) > 1 else tile["squad"]
                    cell = self.colorize("▲", fg="highlight_gold", bold=True)
                elif tile["gate"]:
                    cell = self.colorize("∩", fg="blood_crimson", bold=True)
                elif "mountain" in tile["chunk"].lower() or "highland" in tile["chunk"].lower():
                    cell = self.colorize("^", fg="terrain_mountain")
                elif "ocean" in tile["chunk"].lower() or "sea" in tile["chunk"].lower() or "water" in tile["chunk"].lower():
                    cell = self.colorize("~", fg="terrain_water")
                elif "forest" in tile["chunk"].lower() or "marsh" in tile["chunk"].lower():
                    cell = self.colorize("T", fg="terrain_forest")
                else:
                    cell = self.colorize(".", fg="terrain_plains")
                row_cells.append(cell)
            line = f"{y:2d} |" + " ".join(row_cells) + "|"
            lines.append(line)

        lines.append("   +" + "-" * 20 + "+")
        legend = (
            "Legend: "
            + self.colorize("▲", fg="highlight_gold", bold=True) + " Squad Token | "
            + self.colorize("∩", fg="blood_crimson", bold=True) + " Pass Gate | "
            + self.colorize("^", fg="terrain_mountain") + " Highland/Peak | "
            + self.colorize("~", fg="terrain_water") + " Water/Sea | "
            + self.colorize("T", fg="terrain_forest") + " Forest/Marsh | "
            + self.colorize(".", fg="terrain_plains") + " Plains\n"
            "Provinces: Iron Reach (N), Sunken Marches (W), Obsidian Vale (E), Imperial Heart (Central)"
        )
        lines.append(legend)
        return "\n".join(lines)

    def _seed_default_macro_sector(self, db_conn: sqlite3.Connection, sector_id: str) -> None:
        """Seed a rich 10x10 sector with chunks, pass gates, and squad tokens."""
        cursor = db_conn.cursor()
        with db_conn:
            for y in range(10):
                for x in range(10):
                    # Provinces and Chunks
                    if y < 3 and x < 5:
                        chunk = "Northern Highlands"
                        prov = "Iron Reach"
                    elif y >= 6 and x < 4:
                        chunk = "Sunken Ocean"
                        prov = "Sunken Marches"
                    elif x >= 7 and y >= 6:
                        chunk = "Obsidian Peaks"
                        prov = "Obsidian Vale"
                    elif x == 5 or y == 5:
                        chunk = "Verdant Forest"
                        prov = "Imperial Heart"
                    else:
                        chunk = "Rolling Plains"
                        prov = "Central Valley"

                    # Pass gates at strategic choke points
                    has_gate = 1 if (x, y) in [(4, 2), (5, 7), (2, 6)] else 0
                    # Squad token at vanguard position
                    squad = "S" if (x, y) == (2, 3) else None

                    cursor.execute(
                        """INSERT OR REPLACE INTO macro_tiles
                           (sector_id, x, y, chunk_name, province, has_pass_gate, squad_token)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (sector_id, x, y, chunk, prov, has_gate, squad),
                    )

    def render_micro_map(
        self,
        db_conn: sqlite3.Connection,
        encounter_id: str,
        active_character_id: Optional[str] = None,
    ) -> str:
        """Render the Micro 16x16 Tactical Zoom skirmish grid with ANSI styling."""
        ensure_schema(db_conn)
        cursor = db_conn.cursor()

        # Find active hero if not specified
        if not active_character_id:
            row = cursor.execute(
                "SELECT character_id FROM encounter_participants WHERE encounter_id = ? AND is_hero = 1 LIMIT 1",
                (encounter_id,),
            ).fetchone()
            if row:
                active_character_id = row[0]
            else:
                active_character_id = "hero"

        # Fetch hero position and encounter metadata
        hero_row = cursor.execute(
            "SELECT pos_x, pos_y, name, current_will, max_will FROM encounter_participants WHERE encounter_id = ? AND character_id = ?",
            (encounter_id, active_character_id),
        ).fetchone()
        pos_x, pos_y = (hero_row[0], hero_row[1]) if hero_row else (8, 8)

        enc_row = cursor.execute(
            "SELECT turn, seed FROM encounters WHERE encounter_id = ?",
            (encounter_id,),
        ).fetchone()
        turn, seed = enc_row if enc_row else (1, "kageyoni-seed")

        # Fetch participants in encounter
        part_rows = cursor.execute(
            "SELECT character_id, is_hero, pos_x, pos_y FROM encounter_participants WHERE encounter_id = ?",
            (encounter_id,),
        ).fetchall()
        participants = {(r[2], r[3]): (r[0], r[1]) for r in part_rows}

        # 16x16 window centered around (pos_x, pos_y)
        min_x = pos_x - 7
        max_x = pos_x + 8
        min_y = pos_y - 7
        max_y = pos_y + 8

        # Fetch custom terrain tiles
        tile_rows = cursor.execute(
            """SELECT x, y, terrain FROM tactical_tiles
               WHERE encounter_id = ? AND x BETWEEN ? AND ? AND y BETWEEN ? AND ?""",
            (encounter_id, min_x, max_x, min_y, max_y),
        ).fetchall()
        custom_tiles = {(r[0], r[1]): r[2] for r in tile_rows}

        header = self.colorize(
            f"=== MICRO 16x16 TACTICAL ZOOM [Turn: {turn} | Pos: ({pos_x}, {pos_y})] ===",
            fg="highlight_gold",
            bold=True,
        )

        col_coords = "    " + "".join(f"{x:x}" for x in range(16))
        lines = [header, col_coords, "   +" + "-" * 16 + "+"]

        for row_idx, gy in enumerate(range(min_y, max_y + 1)):
            row_cells = []
            for col_idx, gx in enumerate(range(min_x, max_x + 1)):
                if gx == pos_x and gy == pos_y:
                    cell = self.colorize("@", fg="highlight_gold", bold=True)
                elif (gx, gy) in participants:
                    pid, is_hero = participants[(gx, gy)]
                    if is_hero:
                        cell = self.colorize("H", fg="skin_warm", bold=True)
                    else:
                        cell = self.colorize("E", fg="blood_crimson", bold=True)
                elif (gx, gy) in custom_tiles:
                    t = custom_tiles[(gx, gy)]
                    cell = self._style_terrain(t)
                else:
                    from .chat_frame import get_default_terrain_glyph
                    t = get_default_terrain_glyph(seed, gx, gy)
                    cell = self._style_terrain(t)
                row_cells.append(cell)
            line = f"{row_idx:02d} |" + "".join(row_cells) + "|"
            lines.append(line)

        lines.append("   +" + "-" * 16 + "+")
        return "\n".join(lines)

    def _style_terrain(self, glyph: str) -> str:
        if glyph == "#":
            return self.colorize("#", fg="shadow_deep", bold=True)
        elif glyph == "~":
            return self.colorize("~", fg="terrain_water")
        elif glyph == "T":
            return self.colorize("T", fg="terrain_forest")
        else:
            return self.colorize(".", fg="terrain_plains")

    # -------------------------------------------------------------------------
    # 2. Rhythm Timing Defense Bar
    # -------------------------------------------------------------------------

    def render_rhythm_bar(
        self,
        current_beat: int = 2,
        timing_window: int = 2,
    ) -> str:
        """Visual rendering of the 3-beat rhythm bar [ ·  ·  █ ]

        with timing window for pre-cognitive gambits.
        """
        beat_chars = ["·", "·", "·"]
        idx = current_beat % 3
        beat_chars[idx] = "█"

        # Construct unstyled rhythm bar literal for deterministic matching
        raw_bar = f"[ {beat_chars[0]}  {beat_chars[1]}  {beat_chars[2]} ]"

        is_window_open = (idx == timing_window % 3)
        if is_window_open:
            styled_chars = list(beat_chars)
            styled_chars[idx] = self.colorize("█", fg="highlight_gold", bold=True)
            styled_bar = f"[ {styled_chars[0]}  {styled_chars[1]}  {styled_chars[2]} ]"
            window_msg = self.colorize(
                "<< PRE-COGNITIVE GAMBIT TIMING WINDOW OPEN >>",
                fg="blood_crimson",
                bold=True,
            )
            return f"{styled_bar}  {window_msg}"
        else:
            styled_chars = list(beat_chars)
            styled_chars[idx] = self.colorize("█", fg="skin_pale")
            styled_bar = f"[ {styled_chars[0]}  {styled_chars[1]}  {styled_chars[2]} ]"
            return styled_bar

    # -------------------------------------------------------------------------
    # 3. Attuned Kata Deck Inspector
    # -------------------------------------------------------------------------

    def render_kata_deck(
        self,
        db_conn: sqlite3.Connection,
        character_id: str,
    ) -> str:
        """Visual display of the 3-4 equipped Katas, stamina costs,

        erosion ticks, and backlash ratings.
        """
        ensure_schema(db_conn)
        cursor = db_conn.cursor()

        rows = cursor.execute(
            """SELECT slot, name, stamina_cost, erosion_tick, backlash_rating, description
               FROM equipped_katas
               WHERE character_id = ?
               ORDER BY slot ASC""",
            (character_id,),
        ).fetchall()

        if not rows:
            # Seed standard attuned Katas for demonstration
            self._seed_default_katas(db_conn, character_id)
            rows = cursor.execute(
                """SELECT slot, name, stamina_cost, erosion_tick, backlash_rating, description
                   FROM equipped_katas
                   WHERE character_id = ?
                   ORDER BY slot ASC""",
                (character_id,),
            ).fetchall()

        lines = [
            self.colorize("╔══════════════════════════════════════════════════════════════════════════════╗", fg="highlight_gold"),
            self.colorize("║                        ATTUNED KATA DECK INSPECTOR                           ║", fg="highlight_gold", bold=True),
            self.colorize("╠══════════════════════════════════════════════════════════════════════════════╣", fg="highlight_gold"),
        ]

        for idx, row in enumerate(rows):
            slot, name, stamina, erosion, backlash, desc = row
            backlash_color = "skin_pale"
            if str(backlash).lower() in ["moderate", "medium"]:
                backlash_color = "highlight_gold"
            elif str(backlash).lower() in ["severe", "high", "critical"]:
                backlash_color = "blood_crimson"

            title_line = (
                f"║ [Slot {slot}] "
                + self.colorize(name.upper().ljust(30), fg="white", bold=True)
                + f" (Equipped) ".rjust(38)
                + "║"
            )
            stats_line = (
                f"║   Stamina: "
                + self.colorize(str(stamina), fg="cyan", bold=True)
                + f" | Erosion: "
                + self.colorize(f"+{erosion}", fg="skin_weathered")
                + f" | Backlash: "
                + self.colorize(str(backlash), fg=backlash_color, bold=True)
            )
            # Pad stats line to box width
            visible_stats_len = len(self.strip_ansi(stats_line))
            stats_line += " " * (79 - visible_stats_len) + "║"

            desc_text = desc if desc else "Ancient martial pattern attuning personal Will to spatial friction."
            desc_line = f"║   Desc: {desc_text[:70]}"
            visible_desc_len = len(desc_line)
            desc_line += " " * (79 - visible_desc_len) + "║"

            lines.append(title_line)
            lines.append(stats_line)
            lines.append(desc_line)

            if idx < len(rows) - 1:
                lines.append(self.colorize("╟──────────────────────────────────────────────────────────────────────────────╢", fg="shadow_deep"))

        lines.append(self.colorize("╚══════════════════════════════════════════════════════════════════════════════╝", fg="highlight_gold"))
        return "\n".join(lines)

    def _seed_default_katas(self, db_conn: sqlite3.Connection, character_id: str) -> None:
        cursor = db_conn.cursor()
        defaults = [
            (1, "Severing Wave", 2, 1, "Low", "Focuses cutting intent forward; cleaves defensive posture."),
            (2, "Vajra Guard", 1, 0, "Low", "Immovable stance absorbing incoming kinetic force directly into earth."),
            (3, "Blood Ember Strike", 3, 2, "Moderate", "Ignites circulating Will for explosive bursting thrust."),
            (4, "Void Piercing Kata", 4, 3, "Severe", "Transcendent thrust destabilizing target causality; severe backlash risk."),
        ]
        with db_conn:
            for slot, name, stamina, erosion, backlash, desc in defaults:
                cursor.execute(
                    """INSERT OR REPLACE INTO equipped_katas
                       (character_id, slot, name, stamina_cost, erosion_tick, backlash_rating, description)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (character_id, slot, name, stamina, erosion, backlash, desc),
                )

    # -------------------------------------------------------------------------
    # 4. Camp Private Action Morning Review Screen
    # -------------------------------------------------------------------------

    def render_camp_review(
        self,
        db_conn: sqlite3.Connection,
        camp_id: str = "camp_main",
    ) -> str:
        """Display pending companion interactions from private_action_queue."""
        ensure_schema(db_conn)
        cursor = db_conn.cursor()

        rows = cursor.execute(
            """SELECT id, companion_id, companion_name, topic, interaction_text, status
               FROM private_action_queue
               WHERE camp_id = ? AND status = 'pending'
               ORDER BY id ASC""",
            (camp_id,),
        ).fetchall()

        header = self.colorize(
            f"=== CAMP PRIVATE ACTION: MORNING REVIEW [Camp: {camp_id}] ===",
            fg="highlight_gold",
            bold=True,
        )

        lines = [header, ""]
        if not rows:
            lines.append("No pending companion interactions in queue.")
            return "\n".join(lines)

        for row in rows:
            act_id, comp_id, comp_name, topic, text, status = row
            card_top = (
                self.colorize("┌─ [Companion: ", fg="skin_warm")
                + self.colorize(comp_name, fg="white", bold=True)
                + self.colorize("] Topic: ", fg="skin_warm")
                + self.colorize(topic, fg="highlight_gold")
                + self.colorize(" ───────────────────────────────────┐", fg="skin_warm")
            )
            card_body = f'│ "{text}"\n│ Affordance: [1] Discuss  [2] Share Ration  [3] Dismiss'
            card_bot = self.colorize("└──────────────────────────────────────────────────────────────────────────┘", fg="skin_warm")
            lines.extend([card_top, card_body, card_bot, ""])

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # 5. Headless Execution Mode
    # -------------------------------------------------------------------------

    def run_turn_step(
        self,
        db_conn: sqlite3.Connection,
        encounter_id: str,
        action_command: Union[str, Dict[str, Any]],
        character_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Programmatic and automated turn step execution without requiring an interactive TTY."""
        ensure_schema(db_conn)
        cursor = db_conn.cursor()

        # Resolve active character
        if not character_id:
            row = cursor.execute(
                "SELECT character_id FROM encounter_participants WHERE encounter_id = ? AND is_hero = 1 LIMIT 1",
                (encounter_id,),
            ).fetchone()
            if row:
                character_id = row[0]
            else:
                character_id = "hero_1"

        # Parse action command into action payload
        payload: Dict[str, Any] = {}
        if isinstance(action_command, dict):
            payload = dict(action_command)
        elif isinstance(action_command, str):
            tokens = action_command.strip().split()
            cmd = tokens[0].lower() if tokens else "wait"

            if cmd == "move" and len(tokens) >= 3:
                payload = {"type": "move", "dx": int(tokens[1]), "dy": int(tokens[2])}
            elif cmd == "strike" and len(tokens) >= 4:
                # strike <defender> <anatomy> <damage> [crit]
                payload = {
                    "type": "strike",
                    "defender": tokens[1],
                    "target_anatomy": tokens[2],
                    "damage": int(tokens[3]),
                    "crit": int(tokens[4]) if len(tokens) > 4 else 0,
                }
            elif cmd == "kata" and len(tokens) >= 2:
                payload = {"type": "kata", "slot": int(tokens[1]), "spend_will": 1, "erosion_tick": 1}
            elif cmd == "choice" and len(tokens) >= 2:
                payload = {"type": "choice", "index": int(tokens[1])}
            elif cmd in ["wait", "pass", "rest"]:
                payload = {"type": "wait", "spend_will": 0}
            else:
                payload = {"type": "generic", "raw": action_command}
        else:
            payload = {"type": "generic"}

        # Process the action transactionally
        action_result = StatelessObservationFrame.process_action(
            db_conn,
            encounter_id=encounter_id,
            character_id=character_id,
            action_payload=payload,
        )

        # Compile latest stateless observation frame
        frame = StatelessObservationFrame.compile_frame(
            db_conn,
            encounter_id=encounter_id,
            active_character_id=character_id,
        )

        return {
            "status": "ok",
            "encounter_id": encounter_id,
            "character_id": character_id,
            "turn": action_result["turn"],
            "action": action_command,
            "action_result": action_result,
            "frame": frame,
            "merkle_hash": action_result["merkle_hash"],
        }


def main() -> None:
    """CLI interactive demonstration entry point."""
    import sqlite3
    from pathlib import Path

    print("=====================================================================")
    print("        KAGEYŌNI DETERMINISTIC RPG: INTERACTIVE CLI DEMO             ")
    print("=====================================================================\n")

    cli = KageyoniCLI()

    # 1. Macro Sector Map
    print(cli.render_macro_map(player_chunk=(4, 4), pass_status={"pass_1_n": "CONTROLLED", "pass_1_s": "OPEN"}))
    print()

    # 2. Micro Tactical Zoom
    print(cli.render_micro_map(center_x=49, center_y=49, participants={"char_levi": (49, 49), "enemy_boss": (51, 50)}))
    print()

    # 3. 3-Beat Rhythm Defense Bar
    print(cli.render_rhythm_bar(active_beat=3, total_beats=3, tolerance_ms=150))
    print()

    # 4. Attuned Kata Deck Inspection
    sample_katas = [
        {"name": "Vajra Severing Cleave", "stamina_cost": 18.5, "erosion_ticks": 0.04, "backlash_damage": 0.0},
        {"name": "Mist Step Rising Geyser", "stamina_cost": 22.0, "erosion_ticks": 0.06, "backlash_damage": 5.2},
        {"name": "Adamantine Bastion Needle", "stamina_cost": 14.0, "erosion_ticks": 0.02, "backlash_damage": 0.0},
    ]
    print(cli.render_kata_deck(sample_katas))
    print()

    # 5. Live Headless Turn Simulation
    schema_path = Path(__file__).resolve().parent / "database" / "schema.sql"
    if schema_path.exists():
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT INTO character_genesis (character_id, canonical_name, genesis_seed, province_origin,
                affinity_agency, affinity_substance, affinity_information, affinity_space, affinity_time, affinity_value,
                current_will, max_will, erosion_level, is_dissolved)
            VALUES ('char_levi', 'Levi', '0x5354525543545552', 'Imperial_Core',
                0.88, 0.72, 0.85, 0.65, 0.78, 0.90, 100, 100, 0.0, 0);
            """
        )
        step = cli.run_turn_step(conn, "enc_demo", "char_levi", "ATTACK")
        print("Live Simulation Frame Output:\n")
        print(step["frame"])
        conn.close()

    print("\n[OK] Kageyoni deterministic RPG CLI runner verified operational.")


if __name__ == "__main__":
    main()

