"""Comprehensive test suite for Phase 3 Dual Runners.

Tests:
1. test_stateless_frame_compilation
2. test_stateless_hash_determinism
3. test_process_action_transaction
4. test_cli_rendering_macro_and_micro
5. test_cli_rhythm_bar_and_deck_display
6. test_cli_headless_step
"""
import os
from pathlib import Path
import re
import sqlite3
import sys
import unittest

# Ensure local repository root takes precedence in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path or sys.path[0] != str(ROOT):
    sys.path.insert(0, str(ROOT))

from kageyoni.chat_frame import (
    StatelessObservationFrame,
    ensure_schema,
)
from kageyoni.cli import KageyoniCLI



def seed_test_database(db: sqlite3.Connection) -> None:
    """Helper to populate canonical encounter fixture."""
    ensure_schema(db)
    cursor = db.cursor()
    with db:
        # Encounter
        cursor.execute(
            """INSERT OR REPLACE INTO encounters (encounter_id, turn, seed, phase)
               VALUES ('enc_comp_1', 1, 'seed-v11-comp', 'active')"""
        )
        # Hero participant
        cursor.execute(
            """INSERT OR REPLACE INTO encounter_participants
               (encounter_id, character_id, name, is_hero, pos_x, pos_y, current_will, max_will, erosion, emotional_state, calcified_armor)
               VALUES ('enc_comp_1', 'hero_1', 'Kage', 1, 8, 8, 10, 10, 1, 'resolute', 'Obsidian Carapace (+3 Armor)')"""
        )
        # Enemy participant
        cursor.execute(
            """INSERT OR REPLACE INTO encounter_participants
               (encounter_id, character_id, name, is_hero, pos_x, pos_y, current_will, max_will, erosion, emotional_state, calcified_armor)
               VALUES ('enc_comp_1', 'enemy_1', 'Ronin', 0, 10, 8, 8, 8, 0, 'frenzied', 'None')"""
        )
        # Zenkai Scars (2 active scars)
        cursor.execute(
            """INSERT OR REPLACE INTO zenkai_scars (character_id, slot, anatomical_site, penalty, unlocked_art, active)
               VALUES ('hero_1', 1, 'Left Clavicle', '-2 Reach', 'Severing Counter', 1)"""
        )
        cursor.execute(
            """INSERT OR REPLACE INTO zenkai_scars (character_id, slot, anatomical_site, penalty, unlocked_art, active)
               VALUES ('hero_1', 2, 'Right Eye', '-1 Reaction', 'Blind Fury', 1)"""
        )
        # Contact ledger strike
        cursor.execute(
            """INSERT OR REPLACE INTO contact_ledger (encounter_id, turn, attacker, defender, target_anatomy, damage, crit)
               VALUES ('enc_comp_1', 1, 'hero_1', 'enemy_1', 'throat', 14, 1)"""
        )
        # Dialogue & tactical affordances
        cursor.execute(
            """INSERT OR REPLACE INTO dialogue_options (encounter_id, character_id, tag, text, required_will, max_erosion, required_capability, affordance_type, available)
               VALUES ('enc_comp_1', 'hero_1', 'VAJRA READ', 'Anticipate incoming strike', 2, 5, NULL, 'tactical', 1)"""
        )
        cursor.execute(
            """INSERT OR REPLACE INTO dialogue_options (encounter_id, character_id, tag, text, required_will, max_erosion, required_capability, affordance_type, available)
               VALUES ('enc_comp_1', 'hero_1', 'FLIRT', 'Disarm with carnal banter', 0, 5, NULL, 'dialogue', 1)"""
        )
        cursor.execute(
            """INSERT OR REPLACE INTO dialogue_options (encounter_id, character_id, tag, text, required_will, max_erosion, required_capability, affordance_type, available)
               VALUES ('enc_comp_1', 'hero_1', 'ATTUNED KATA: Severing Wave', 'Release spatial arc', 3, 5, NULL, 'kata', 1)"""
        )


class TestDualRunners(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        seed_test_database(self.db)
        self.cli = KageyoniCLI()

    def tearDown(self):
        self.db.close()

    def test_stateless_frame_compilation(self):
        """1. Assert presence of Merkle header, 16x16 tactical grid, scars capsule, and affordances."""
        frame = StatelessObservationFrame.compile_frame(
            self.db,
            encounter_id="enc_comp_1",
            active_character_id="hero_1",
        )

        # 1. Merkle State Header
        self.assertIn("[STATE-V11: MERKLE_HASH=", frame)
        self.assertIn("TURN=1", frame)
        self.assertIn("POS=(8,8)", frame)
        self.assertIn("WILL=10/10", frame)
        self.assertIn("EROSION=1", frame)
        self.assertIn("SEED=seed-v11-comp", frame)

        # 2. Micro 16x16 Tactical Lens
        self.assertIn("### Micro 16x16 Tactical Lens", frame)
        grid_match = re.search(r"```text\n(.*?)\n```", frame, re.DOTALL)
        self.assertIsNotNone(grid_match, "Tactical grid must be enclosed in ```text code block")
        grid_text = grid_match.group(1)
        grid_lines = grid_text.strip().splitlines()
        self.assertEqual(len(grid_lines), 16, f"Expected 16 rows in tactical grid, got {len(grid_lines)}")
        for r_idx, line in enumerate(grid_lines):
            self.assertEqual(len(line), 16, f"Row {r_idx} must have 16 columns, got {len(line)}")

        # Verify active hero '@' and enemy 'E' tokens are present on the grid
        self.assertIn("@", grid_text, "Active hero token @ must be on tactical grid")
        self.assertIn("E", grid_text, "Enemy token E must be on tactical grid")

        # 3. Active Constraint Capsule
        self.assertIn("### Active Constraint Capsule", frame)
        self.assertIn("resolute", frame)
        self.assertIn("Obsidian Carapace (+3 Armor)", frame)
        self.assertIn("Left Clavicle", frame)
        self.assertIn("Severing Counter", frame)
        self.assertIn("Right Eye", frame)
        self.assertIn("Blind Fury", frame)

        # 4. Rolling 3-Event Contact Ledger
        self.assertIn("### Rolling 3-Event Contact Ledger", frame)
        self.assertIn("throat", frame)
        self.assertIn("14 DMG", frame)
        self.assertIn("(CRIT)", frame)

        # 5. Available Dialogue / Tactical Affordances
        self.assertIn("### Available Dialogue / Tactical Affordances", frame)
        self.assertIn("[VAJRA READ] Anticipate incoming strike", frame)
        self.assertIn("[FLIRT] Disarm with carnal banter", frame)
        self.assertIn("[ATTUNED KATA: Severing Wave]", frame)

    def test_stateless_hash_determinism(self):
        """2. Assert querying same SQLite state twice produces identical Merkle hashes and frame outputs."""
        frame1 = StatelessObservationFrame.compile_frame(self.db, "enc_comp_1", "hero_1")
        frame2 = StatelessObservationFrame.compile_frame(self.db, "enc_comp_1", "hero_1")

        self.assertEqual(frame1, frame2, "Stateless frames from same DB must be identical")

        # Extract hash
        match1 = re.search(r"MERKLE_HASH=([0-9a-f]{64})", frame1)
        match2 = re.search(r"MERKLE_HASH=([0-9a-f]{64})", frame2)
        self.assertIsNotNone(match1)
        self.assertIsNotNone(match2)
        self.assertEqual(match1.group(1), match2.group(1))

        # Test across independent SQLite connection with identical state
        db2 = sqlite3.connect(":memory:")
        try:
            seed_test_database(db2)
            frame3 = StatelessObservationFrame.compile_frame(db2, "enc_comp_1", "hero_1")
            self.assertEqual(frame1, frame3, "Deterministic reproduction across fresh connection failed")
        finally:
            db2.close()

    def test_process_action_transaction(self):
        """3. Assert submitting action updates SQLite and mutates the next compiled frame."""
        frame_before = StatelessObservationFrame.compile_frame(self.db, "enc_comp_1", "hero_1")
        hash_before = re.search(r"MERKLE_HASH=([0-9a-f]{64})", frame_before).group(1)

        # Execute move and will-spending action
        action_payload = {
            "type": "move",
            "dx": 1,
            "dy": 0,
            "spend_will": 2,
        }
        digest = StatelessObservationFrame.process_action(
            self.db,
            encounter_id="enc_comp_1",
            character_id="hero_1",
            action_payload=action_payload,
        )

        self.assertEqual(digest["status"], "ok")
        self.assertEqual(digest["turn"], 2)
        self.assertEqual(digest["pos"], (9, 8))
        self.assertEqual(digest["will"], (8, 10))

        # Compile frame after action
        frame_after = StatelessObservationFrame.compile_frame(self.db, "enc_comp_1", "hero_1")
        hash_after = re.search(r"MERKLE_HASH=([0-9a-f]{64})", frame_after).group(1)

        self.assertNotEqual(hash_before, hash_after, "Merkle hash must mutate after state change")
        self.assertIn("TURN=2", frame_after)
        self.assertIn("POS=(9,8)", frame_after)
        self.assertIn("WILL=8/10", frame_after)

        # Verify direct SQLite state mutation
        cursor = self.db.cursor()
        row = cursor.execute(
            "SELECT pos_x, pos_y, current_will FROM encounter_participants WHERE character_id = 'hero_1'"
        ).fetchone()
        self.assertEqual(row, (9, 8, 8))

        # Execute strike action
        strike_payload = {
            "type": "strike",
            "attacker": "hero_1",
            "defender": "enemy_1",
            "target_anatomy": "ribs",
            "damage": 12,
            "crit": 0,
        }
        StatelessObservationFrame.process_action(
            self.db,
            encounter_id="enc_comp_1",
            character_id="hero_1",
            action_payload=strike_payload,
        )
        frame_strike = StatelessObservationFrame.compile_frame(self.db, "enc_comp_1", "hero_1")
        self.assertIn("ribs", frame_strike)
        self.assertIn("12 DMG", frame_strike)

    def test_cli_rendering_macro_and_micro(self):
        """4. Assert CLI macro sector map and micro tactical grid generation."""
        # 1. Macro 10x10 Sector Map
        macro_map = self.cli.render_macro_map(self.db, sector_id="main")
        macro_plain = self.cli.strip_ansi(macro_map)

        self.assertIn("MACRO 10x10 SECTOR MAP", macro_plain)
        # Verify 10 coordinate rows: 0 to 9
        for y in range(10):
            self.assertIn(f"{y:2d} |", macro_plain)
        self.assertIn("Pass Gate", macro_plain)
        self.assertIn("Squad Token", macro_plain)

        # 2. Micro 16x16 Tactical Zoom
        micro_map = self.cli.render_micro_map(self.db, encounter_id="enc_comp_1", active_character_id="hero_1")
        micro_plain = self.cli.strip_ansi(micro_map)

        self.assertIn("MICRO 16x16 TACTICAL ZOOM", micro_plain)
        self.assertIn("@", micro_plain, "Active hero token must be present in micro zoom")
        self.assertIn("E", micro_plain, "Enemy token must be present in micro zoom")
        # Check all 16 rows: 00 to 15
        for row_idx in range(16):
            self.assertIn(f"{row_idx:02d} |", micro_plain)

    def test_cli_rhythm_bar_and_deck_display(self):
        """5. Assert rhythm bar formatting and Kata deck inspection display."""
        # Test Rhythm Bar at beat 0, 1, 2
        bar0 = self.cli.render_rhythm_bar(current_beat=0, timing_window=2)
        self.assertIn("[ █  ·  · ]", self.cli.strip_ansi(bar0))

        bar1 = self.cli.render_rhythm_bar(current_beat=1, timing_window=2)
        self.assertIn("[ ·  █  · ]", self.cli.strip_ansi(bar1))

        bar2 = self.cli.render_rhythm_bar(current_beat=2, timing_window=2)
        plain_bar2 = self.cli.strip_ansi(bar2)
        self.assertIn("[ ·  ·  █ ]", plain_bar2)
        self.assertIn("PRE-COGNITIVE GAMBIT TIMING WINDOW OPEN", plain_bar2)

        # Test Attuned Kata Deck Inspector
        deck_output = self.cli.render_kata_deck(self.db, character_id="hero_1")
        deck_plain = self.cli.strip_ansi(deck_output)

        self.assertIn("ATTUNED KATA DECK INSPECTOR", deck_plain)
        self.assertIn("SEVERING WAVE", deck_plain)
        self.assertIn("VAJRA GUARD", deck_plain)
        self.assertIn("BLOOD EMBER STRIKE", deck_plain)
        self.assertIn("VOID PIERCING KATA", deck_plain)
        self.assertIn("Stamina:", deck_plain)
        self.assertIn("Erosion:", deck_plain)
        self.assertIn("Backlash:", deck_plain)

    def test_cli_headless_step(self):
        """6. Assert running headless turn steps through the CLI engine."""
        # 1. Run headless movement step
        res1 = self.cli.run_turn_step(self.db, "enc_comp_1", "move 0 1", character_id="hero_1")
        self.assertEqual(res1["status"], "ok")
        self.assertEqual(res1["turn"], 2)
        self.assertIn("frame", res1)
        self.assertIn("POS=(8,9)", res1["frame"])

        # 2. Run headless strike step
        res2 = self.cli.run_turn_step(
            self.db,
            "enc_comp_1",
            {"type": "strike", "attacker": "hero_1", "defender": "enemy_1", "target_anatomy": "solar_plexus", "damage": 18, "crit": 1},
            character_id="hero_1",
        )
        self.assertEqual(res2["status"], "ok")
        self.assertEqual(res2["turn"], 3)
        self.assertIn("solar_plexus", res2["frame"])
        self.assertIn("18 DMG", res2["frame"])
        self.assertNotEqual(res1["merkle_hash"], res2["merkle_hash"])

        # 3. Test Camp Private Action morning review screen
        cursor = self.db.cursor()
        cursor.execute(
            """INSERT INTO private_action_queue
               (camp_id, companion_id, companion_name, topic, interaction_text, status)
               VALUES ('camp_alpha', 'comp_ren', 'Scribe Ren', 'Deciphering the Stele', 'The inscriptions refer to an ancient pass gate.', 'pending')"""
        )
        self.db.commit()

        camp_review = self.cli.render_camp_review(self.db, camp_id="camp_alpha")
        camp_plain = self.cli.strip_ansi(camp_review)

        self.assertIn("CAMP PRIVATE ACTION: MORNING REVIEW", camp_plain)
        self.assertIn("Scribe Ren", camp_plain)
        self.assertIn("Deciphering the Stele", camp_plain)
        self.assertIn("ancient pass gate", camp_plain)


if __name__ == "__main__":
    unittest.main()
