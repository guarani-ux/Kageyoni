r"""Comprehensive mechanical verification of the Molten Metal Capability Smelter.

Verifies:
1. Probe raw binary protocol specimens (e.g., custom game packet) to discover structural grammar.
2. Cast pure-Python channel parser modules (CH 49) with fail-closed bounds checking and
   ThermodynamicProfiler peak heap <= 64KB, plus matching unittest suites.
3. Quench & mount via MechanicalAuditorGate, verifying clean ACCEPT verdict, hot-mounting
   into ninshu_codex.sqlite and registering into ActiveConsole.
4. Channel execution via Patchbay.execute_channel().
5. Board reconfiguration: substrate lens, 4-band EQ layer split, and insert chain.
6. 8-Knob modulation via NinshuPowerSystem and ActiveConsole streaming.
7. Fail-closed rejection of corrupted specimens and unsafe code templates.
8. Real-world specimen testing against \\wsl.localhost\Ubuntu\home\flowe (e.g. scouter_pulse.bin).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path
import struct
import unittest

from kageyoni.ninshu.console import ActiveConsole, ChannelStripConfig
from kageyoni.ninshu.patchbay import Patchbay
from kageyoni.ninshu.power_system import NinshuKnobVector, NinshuPowerSystem
from kageyoni.ninshu.smelter import CastArtifact, MoltenSmelter, StructuralBlueprint
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler

REPO_ROOT = Path(__file__).resolve().parent.parent
WSL_HOME = Path(r"\\wsl.localhost\Ubuntu\home\flowe")


class TestNinshuMoltenSmelter(unittest.TestCase):
    """Mechanical test suite for MoltenSmelter and Board Reconfiguration."""

    @classmethod
    def setUpClass(cls):
        cls.smelter = MoltenSmelter()
        cls.patchbay = Patchbay()
        cls.power_system = NinshuPowerSystem(cls.smelter)

        # Build custom binary protocol specimen samples (Game Packet format)
        # Header: Magic 4B ("GMPK"), Version 2B (1), PacketID 2B (0x0042), PayloadLen 4B, SeqID 4B = 16B
        cls.magic = b"GMPK"
        cls.endian = "<"
        cls.samples = []
        for i in range(3):
            payload = f"PAYLOAD_CH49_SEQUENCE_{i}".encode("utf-8")
            header = struct.pack(f"{cls.endian}4sHHII", cls.magic, 1, 0x0042 + i, len(payload), 1000 + i)
            cls.samples.append(header + payload)

        cls.created_files = []
        cls.mounted_channels = []

    @classmethod
    def tearDownClass(cls):
        # 1. Clean up database from test channels
        for ch_num in cls.mounted_channels:
            try:
                with cls.patchbay.conn:
                    cls.patchbay.conn.execute("DELETE FROM channels WHERE channel_number = ?", (ch_num,))
            except Exception:
                pass

        # 2. Clean up synthesized files from disk
        for file_path in cls.created_files:
            try:
                p = Path(file_path)
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    def test_01_probe_binary_specimen_grammar(self):
        """Probes specimen samples and verifies discovered structural invariants."""
        blueprint = self.smelter.probe_specimen(self.samples)

        self.assertIsInstance(blueprint, StructuralBlueprint)
        self.assertEqual(blueprint.specimen_format, "binary_packet")
        self.assertEqual(blueprint.magic_bytes, b"GMPK")
        self.assertEqual(blueprint.endianness, "<")
        self.assertEqual(blueprint.header_size, 16)
        self.assertEqual(blueprint.payload_length_field, "payload_length")
        self.assertTrue(blueprint.has_payload)
        self.assertIn("min_length >= 16", blueprint.invariants)
        self.assertIn("magic == 474d504b", blueprint.invariants)

        field_names = [f["name"] for f in blueprint.fields]
        self.assertEqual(field_names, ["magic", "version", "packet_id", "payload_length", "sequence_id"])

    def test_02_cast_quench_mount_and_execute_channel_49(self):
        """Casts CH 49, audits via MechanicalAuditorGate, mounts, and executes via Patchbay."""
        blueprint = self.smelter.probe_specimen(self.samples)
        artifact = self.smelter.cast_channel(
            blueprint=blueprint,
            channel_number=49,
            name="game_packet",
            bus="BUS_E",
        )

        self.created_files.append(artifact.impl_path)
        self.created_files.append(artifact.test_path)
        self.mounted_channels.append(49)

        # Verify synthesized files exist and pass AST parse
        self.assertTrue(artifact.impl_path.exists())
        self.assertTrue(artifact.test_path.exists())
        self.assertEqual(artifact.channel_number, 49)
        self.assertEqual(artifact.test_module, "tests.test_ninshu_smelted_game_packet")

        # Quench & mount through MechanicalAuditorGate
        mount_res = self.smelter.quench_and_mount(artifact, self.patchbay)
        self.assertEqual(mount_res["verdict"], "ACCEPT")
        self.assertEqual(mount_res["status"], "ACCEPTED")
        self.assertTrue(mount_res["mounted"])
        self.assertIn("audit_result", mount_res)

        # Verify mounted in SQLite codex
        ch_meta = self.patchbay.get_channel(49)
        self.assertIsNotNone(ch_meta)
        self.assertEqual(ch_meta["name"], "game_packet")
        self.assertEqual(ch_meta["bus_id"], "BUS_E")
        self.assertEqual(ch_meta["reversibility_tier"], 0)
        self.assertEqual(ch_meta["epistemic_confidence"], "verified")

        # Verify execution via Patchbay.execute_channel()
        parsed = self.patchbay.execute_channel(49, self.samples[0])
        self.assertEqual(parsed.channel_number, 49)
        self.assertEqual(parsed.fields["version"], 1)
        self.assertEqual(parsed.fields["packet_id"], 0x0042)
        self.assertEqual(parsed.fields["payload_length"], len(b"PAYLOAD_CH49_SEQUENCE_0"))
        self.assertEqual(parsed.payload_bytes, b"PAYLOAD_CH49_SEQUENCE_0")
        self.assertEqual(len(parsed.sha256_digest), 64)

        # Verify Thermodynamic Profiler peak heap <= 64KB during execution
        with ThermodynamicProfiler(
            candidate_id="ch49_execution_check",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        ) as profiler:
            for sample in self.samples:
                self.patchbay.execute_channel(49, sample)
        self.assertLessEqual(profiler.peak_memory_bytes, 64 * 1024)

    def test_03_reconfigure_channel_board_parameters(self):
        """Reconfigures channel substrate lens, 4-band EQ layer split, and insert chain on the fly."""
        ch_meta = self.patchbay.get_channel(49)
        self.assertIsNotNone(ch_meta)

        strip_config = ChannelStripConfig(
            channel_number=49,
            name="game_packet",
            carrier_path=ch_meta["carrier_path"],
            entrypoint=ch_meta["entrypoint"],
        )
        console = ActiveConsole({"patch_id": "test_reconfig", "channel_strips": [{"ch": 49, "name": "game_packet", "carrier": ch_meta["carrier_path"], "entrypoint": ch_meta["entrypoint"]}]})

        # Reconfigure with a custom 8-Knob Vector
        knobs = NinshuKnobVector(
            substrate="conduit_link",
            bandwidth_shape="spear",
            authority_gain=0.92,
            damping_density=0.88,
            thermal_tier=1,
            polarity="polyphonic",
            sidechain_from="ch_33_packet_sniffer",
            deficit_gain="wet",
        )

        reconfigured = self.smelter.reconfigure_channel(
            channel_number=49,
            knob_vector=knobs,
            strip_config=strip_config,
            console=console,
            patchbay=self.patchbay,
        )

        # Verify physical dials
        self.assertEqual(reconfigured.thermal_ceiling, 1)
        self.assertEqual(reconfigured.fader_gain_db, round((0.88 - 0.5) * 12.0, 2))
        self.assertEqual(reconfigured.noise_gate_threshold, 0.5)

        # Verify substrate lens
        self.assertEqual(getattr(reconfigured, "substrate_lens"), "substrate_lens:conduit_link")

        # Verify 4-band EQ layer split
        eq = getattr(reconfigured, "eq_layer_split")
        self.assertEqual(eq["LF"]["parameter"], "conduit_link")
        self.assertEqual(eq["LMF"]["shape"], "spear")
        self.assertEqual(eq["HMF"]["polarity"], "polyphonic")
        self.assertEqual(eq["HF"]["deficit"], "wet")

        # Verify insert chain
        insert_chain = getattr(reconfigured, "insert_chain")
        self.assertEqual(insert_chain[0]["type"], "sidechain_compressor")
        self.assertEqual(insert_chain[0]["source"], "ch_33_packet_sniffer")

        # Verify console reflection
        self.assertEqual(console.channels[49].fader_gain_db, reconfigured.fader_gain_db)

        # Verify patchbay reflection
        updated_row = self.patchbay.get_channel(49)
        self.assertEqual(updated_row["lens_family"], "smelted_lens_conduit_link")
        self.assertEqual(updated_row["reversibility_tier"], 1)

    def test_04_integrate_ninshu_power_system_8knob_modulation(self):
        """Tests NinshuPowerSystem shaping and modulating the newly smelted channel."""
        # 1. Shape channel strip into NinshuKnobVector
        derived_knobs = self.power_system.shape_channel_to_knobs(49, patchbay=self.patchbay)
        self.assertIsInstance(derived_knobs, NinshuKnobVector)
        self.assertEqual(derived_knobs.thermal_tier, 1)

        # 2. Modulate channel carrier through 8-Knob transformation
        mod_pkg, active_console = self.power_system.modulate_channel(
            channel=49,
            knobs=derived_knobs,
            patchbay=self.patchbay,
            effect_operation="reveal",
        )

        self.assertEqual(mod_pkg.carrier.carrier_id, "carrier_ch49_game_packet")
        self.assertEqual(mod_pkg.technique_id, "tech_ch49_game_packet")
        self.assertTrue(mod_pkg.will_definition_contract["id"].startswith("wdef_"))
        self.assertEqual(mod_pkg.composition_aspect["family"], "will_resonance")

        # 3. Stream track through ActiveConsole and freeze Master Tape
        signals = active_console.stream_track(
            49,
            [{"signal_type": "packet_burst", "bytes": len(self.samples[0]), "confidence_score": 1.0}],
        )
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["origin_channel"], 49)

        master_tape = active_console.print_master(
            session_id="smelted_master_print_test",
            active_signals=signals,
            compiled_aspects=[mod_pkg.composition_aspect],
        )
        self.assertEqual(len(master_tape.master_sha256), 64)
        self.assertIn(49, master_tape.channels_active)

    def test_05_fail_closed_on_corrupted_specimens(self):
        """Asserts 100% fail-closed rejection when corrupted inputs are fed to Patchbay."""
        # 1. Corrupted magic
        bad_magic = b"FAIL" + self.samples[0][4:]
        with self.assertRaises(ValueError) as ctx:
            self.patchbay.execute_channel(49, bad_magic)
        self.assertIn("Magic mismatch", str(ctx.exception))

        # 2. Truncated header (< 16 bytes)
        truncated_header = self.samples[0][:10]
        with self.assertRaises(ValueError) as ctx:
            self.patchbay.execute_channel(49, truncated_header)
        self.assertIn("truncated", str(ctx.exception).lower())

        # 3. Truncated payload
        truncated_payload = self.samples[0][:-5]
        with self.assertRaises(ValueError) as ctx:
            self.patchbay.execute_channel(49, truncated_payload)
        self.assertIn("mismatch", str(ctx.exception).lower())

        # 4. Trailing garbage
        trailing_garbage = self.samples[0] + b"EXTRANEOUS_UNVERIFIED_DATA"
        with self.assertRaises(ValueError) as ctx:
            self.patchbay.execute_channel(49, trailing_garbage)
        self.assertIn("mismatch", str(ctx.exception).lower())

        # 5. Empty specimen
        with self.assertRaises(ValueError):
            self.patchbay.execute_channel(49, b"")

        # 6. Invalid type
        with self.assertRaises(TypeError):
            self.patchbay.execute_channel(49, 99999)
        with self.assertRaises(TypeError):
            self.patchbay.execute_channel(49, "not_bytes")

    def test_06_fail_closed_on_unsafe_code_template(self):
        """Asserts MechanicalAuditorGate and quench_and_mount reject unsafe templates."""
        unsafe_impl_code = '''"""Unsafe channel implementation containing swallowed exceptions."""
class UnsafeParser:
    @classmethod
    def parse(cls, data):
        try:
            return {"parsed": True}
        except Exception:
            pass
'''
        unsafe_test_code = '''"""Unsafe channel test."""
import unittest
class TestUnsafe(unittest.TestCase):
    def test_dummy(self):
        pass
'''
        unsafe_impl = REPO_ROOT / "kageyoni" / "ninshu" / "smelted_unsafe_sample.py"
        unsafe_test = REPO_ROOT / "tests" / "test_ninshu_smelted_unsafe_sample.py"
        unsafe_impl.write_text(unsafe_impl_code, encoding="utf-8")
        unsafe_test.write_text(unsafe_test_code, encoding="utf-8")
        self.created_files.append(unsafe_impl)
        self.created_files.append(unsafe_test)

        unsafe_artifact = CastArtifact(
            channel_number=99,
            name="unsafe_sample",
            bus="BUS_F",
            blueprint=self.smelter.probe_specimen(self.samples),
            impl_path=unsafe_impl,
            test_path=unsafe_test,
            test_module="tests.test_ninshu_smelted_unsafe_sample",
            impl_code=unsafe_impl_code,
            test_code=unsafe_test_code,
            entrypoint="UnsafeParser.parse",
            sha256_digest="fake_digest",
        )

        res = self.smelter.quench_and_mount(unsafe_artifact, self.patchbay)
        self.assertEqual(res["verdict"], "REJECT")
        self.assertFalse(res["mounted"])
        self.assertTrue(len(res["anti_patterns"]) > 0 or len(res["reasons"]) > 0)

        # Verify not mounted in SQLite codex
        self.assertIsNone(self.patchbay.get_channel(99))

    def test_07_probe_json_specimen_grammar(self):
        """Tests probe_specimen on structured JSON schemas."""
        json_samples = [
            {"id": "packet_1", "count": 10, "active": True, "tags": ["alpha", "beta"]},
            {"id": "packet_2", "count": 20, "active": False, "tags": ["gamma"]},
        ]
        blueprint = self.smelter.probe_specimen(json_samples)
        self.assertEqual(blueprint.specimen_format, "json_schema")
        self.assertIsNotNone(blueprint.json_schema)
        self.assertTrue(blueprint.json_schema["id"]["required"])
        self.assertTrue(blueprint.json_schema["count"]["required"])

    def test_08_real_world_specimen_wsl_scouter_pulse(self):
        r"""Tests real-world specimen inspection against \\wsl.localhost\Ubuntu\home\flowe."""
        scouter_path = WSL_HOME / "booder-kingdom" / "security" / "scouter_pulse.bin"
        if not scouter_path.exists():
            self.skipTest(f"WSL specimen not available at {scouter_path}")

        raw_pulse = scouter_path.read_bytes()
        self.assertEqual(len(raw_pulse), 57)

        # Probe the real binary specimen
        blueprint = self.smelter.probe_specimen([raw_pulse])
        self.assertIsInstance(blueprint, StructuralBlueprint)
        self.assertEqual(blueprint.header_size, 16)
        self.assertTrue(blueprint.has_payload)

        # Cast channel 50 for the real specimen
        artifact = self.smelter.cast_channel(
            blueprint=blueprint,
            channel_number=50,
            name="scouter_pulse",
            bus="BUS_E",
        )
        self.created_files.append(artifact.impl_path)
        self.created_files.append(artifact.test_path)
        self.mounted_channels.append(50)

        # Quench and mount
        mount_res = self.smelter.quench_and_mount(artifact, self.patchbay)
        self.assertEqual(mount_res["verdict"], "ACCEPT")
        self.assertTrue(mount_res["mounted"])

        # Execute channel on the real raw specimen
        parsed = self.patchbay.execute_channel(50, raw_pulse)
        self.assertEqual(parsed.channel_number, 50)
        self.assertEqual(parsed.total_bytes, 57)
        self.assertEqual(len(parsed.sha256_digest), 64)

        # Modulate through NinshuPowerSystem
        derived_knobs = self.power_system.shape_channel_to_knobs(50, patchbay=self.patchbay)
        pkg, _ = self.power_system.modulate_channel(50, knobs=derived_knobs, patchbay=self.patchbay)
        self.assertEqual(pkg.carrier.carrier_id, "carrier_ch50_scouter_pulse")


if __name__ == "__main__":
    unittest.main()
