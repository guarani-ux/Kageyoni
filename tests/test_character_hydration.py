"""
Unit tests for Deterministic Character Hydration Substrate.
"""

from __future__ import annotations
import unittest
from pathlib import Path

from kageyoni.emergence.hydration import (
    hydrate_character_from_disk,
    hydrate_all_participants,
    HydratedCharacterPacket,
)


class TestCharacterHydration(unittest.TestCase):
    def test_hydrate_sciel_exact_state(self):
        packet = hydrate_character_from_disk("sciel")
        self.assertEqual(packet.character_id, "sciel")
        self.assertEqual(packet.name, "Sciel")
        self.assertEqual(packet.get_aspect(), "Twilight")
        self.assertEqual(packet.get_manifestation(), "Domain of the Painteress")
        self.assertEqual(packet.get_will_density(), "dense_primordial_core")

        # Verify raw dialogue turns exist without summarization
        turns = packet.dialogue_turns
        self.assertGreaterEqual(len(turns), 4)
        texts = [t["text"] for t in turns]
        self.assertTrue(any("stone remembers what was painted upon it" in txt for txt in texts))
        self.assertTrue(any("Domain of the Painteress" in txt for txt in texts))
        self.assertTrue(any("BasaltFixedMathRedoubt" in txt for txt in texts))

        # Verify cryptographic digest is non-empty and deterministic
        self.assertTrue(isinstance(packet.state_digest, str))
        self.assertEqual(len(packet.state_digest), 64)
        # Re-hydrating gives the same deterministic digest
        packet2 = hydrate_character_from_disk("sciel")
        self.assertEqual(packet.state_digest, packet2.state_digest)

    def test_hydrate_voss_and_maki(self):
        voss = hydrate_character_from_disk("voss")
        self.assertEqual(voss.character_id, "voss")
        self.assertIn("conduit", str(voss.shinobi_identity).lower())
        self.assertGreater(len(voss.dialogue_turns), 0)

        maki = hydrate_character_from_disk("maki")
        self.assertEqual(maki.character_id, "maki")
        self.assertIsNotNone(maki.shinobi_identity)

    def test_missing_character_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            hydrate_character_from_disk("non_existent_character_xyz")
