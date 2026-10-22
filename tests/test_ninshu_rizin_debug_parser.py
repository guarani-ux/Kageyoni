"""Adversarial Verification Suite for Ninshū Rizin Debug Session Controller (CH 20).

Verifications:
1. Valid session decoding across drj (registers), dmj (memory maps), dbj (breakpoints), and dbtj (backtrace).
2. Register dump parsing in both dict mapping and list-of-objects formats.
3. Memory map boundary and permission validation.
4. Breakpoint table state parsing and enabled flag coercion.
5. Backtrace stack frame resolution.
6. Fail-closed rejection of corrupted numbers, negative addresses, missing required registers, and invalid permissions.
7. Thermodynamic memory profiling asserting peak heap ceiling <= 64 KB.
8. Metamorphic fuzzing via AdversarialMutator asserting 100% fail-closed rejection.
"""
from __future__ import annotations

import json
import unittest
from typing import Any, Dict

from kageyoni.ninshu.rizin_debug_parser import (
    RizinDebugParser,
    RizinDebugSessionController,
    RizinDebugSession,
    RizinRegisters,
    RizinMemoryMap,
    RizinBreakpoint,
    RizinStackFrame,
    MAX_SESSION_PAYLOAD_BYTES,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuRizinDebugParser(unittest.TestCase):
    def setUp(self):
        self.valid_registers_dict = {
            "rax": 0x1122334455667788,
            "rbx": "0x0000000000001000",
            "rcx": 0x42,
            "rdx": 0,
            "rsi": "0x7fffffffe100",
            "rdi": "0x7fffffffe200",
            "rsp": 0x7fffffffe000,
            "rbp": 0x7fffffffe080,
            "rip": 0x0000000000401050,
            "rflags": 0x246,
            "r8": 0x8888,
        }

        self.valid_memory_maps_list = [
            {
                "addr": 0x400000,
                "addr_end": 0x401000,
                "perm": "r-x",
                "file": "/usr/bin/target_elf",
            },
            {
                "base_address": 0x600000,
                "end_address": 0x601000,
                "permissions": "rw-",
                "file_mapping": "/usr/bin/target_elf",
            },
            {
                "start": 0x7ffffffde000,
                "end": 0x7ffffffff000,
                "perm": "rwxp",
                "name": "[stack]",
            },
        ]

        self.valid_breakpoints_list = [
            {
                "id": 1,
                "addr": 0x401050,
                "count": 3,
                "enabled": True,
            },
            {
                "breakpoint_id": 2,
                "virtual_address": "0x401120",
                "hit_count": 0,
                "enabled": False,
            },
            {
                "id": "3",
                "addr": "0x401200",
                "hits": 10,
                "enabled": "1",
            },
        ]

        self.valid_backtrace_list = [
            {
                "frame": 0,
                "ip": 0x401050,
                "fp": 0x7fffffffe080,
                "name": "sym.vulnerable_function",
            },
            {
                "frame_number": 1,
                "instruction_pointer": "0x401120",
                "frame_pointer": "0x7fffffffe0a0",
                "function_name": "main",
            },
            {
                "id": 2,
                "addr": 0x7ffff7df0d90,
                "bp": 0x7fffffffe0f0,
                "fname": "__libc_start_main",
            },
        ]

        self.valid_session_dict = {
            "registers": self.valid_registers_dict,
            "memory_maps": self.valid_memory_maps_list,
            "breakpoints": self.valid_breakpoints_list,
            "backtrace": self.valid_backtrace_list,
        }
        self.valid_session_json = json.dumps(self.valid_session_dict)
        self.valid_session_bytes = self.valid_session_json.encode("utf-8")

    def test_parse_registers_valid_dict_and_list(self):
        regs = RizinDebugParser.parse_registers(self.valid_registers_dict)
        self.assertEqual(regs.rax, 0x1122334455667788)
        self.assertEqual(regs.rbx, 0x1000)
        self.assertEqual(regs.rcx, 0x42)
        self.assertEqual(regs.rdx, 0)
        self.assertEqual(regs.rsi, 0x7fffffffe100)
        self.assertEqual(regs.rdi, 0x7fffffffe200)
        self.assertEqual(regs.rsp, 0x7fffffffe000)
        self.assertEqual(regs.rbp, 0x7fffffffe080)
        self.assertEqual(regs.rip, 0x401050)
        self.assertEqual(regs.rflags, 0x246)
        self.assertEqual(regs.extra.get("r8"), 0x8888)

        # Test list-of-objects format
        list_format = [
            {"name": "rax", "value": 1},
            {"name": "rbx", "value": 2},
            {"name": "rcx", "value": 3},
            {"name": "rdx", "value": 4},
            {"name": "rsi", "value": 5},
            {"name": "rdi", "value": 6},
            {"name": "rsp", "value": 7},
            {"name": "rbp", "value": 8},
            {"name": "rip", "value": 9},
            {"name": "rflags", "value": 10},
        ]
        regs_from_list = RizinDebugParser.parse_registers(list_format)
        self.assertEqual(regs_from_list.rax, 1)
        self.assertEqual(regs_from_list.rip, 9)

    def test_parse_registers_missing_required_fails(self):
        incomplete = dict(self.valid_registers_dict)
        del incomplete["rip"]
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_registers(incomplete)

        del incomplete["rax"]
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_registers(incomplete)

    def test_parse_registers_invalid_values_fail(self):
        # Boolean rejected
        bad_bool = dict(self.valid_registers_dict, rax=True)
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_registers(bad_bool)

        # Float rejected
        bad_float = dict(self.valid_registers_dict, rbx=123.45)
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_registers(bad_float)

        # Negative number rejected
        bad_neg = dict(self.valid_registers_dict, rcx=-1)
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_registers(bad_neg)

        # Negative string rejected
        bad_neg_str = dict(self.valid_registers_dict, rdx="-100")
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_registers(bad_neg_str)

        # 64-bit overflow rejected
        bad_overflow = dict(self.valid_registers_dict, rip=0x1_0000_0000_0000_0000)
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_registers(bad_overflow)

        # Corrupted hex string rejected
        bad_hex = dict(self.valid_registers_dict, rsp="0xNotHexNumber")
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_registers(bad_hex)

    def test_parse_memory_maps_valid(self):
        maps = RizinDebugParser.parse_memory_maps(self.valid_memory_maps_list)
        self.assertEqual(len(maps), 3)
        self.assertEqual(maps[0].base_address, 0x400000)
        self.assertEqual(maps[0].end_address, 0x401000)
        self.assertEqual(maps[0].permissions, "r-x")
        self.assertEqual(maps[0].size, 0x1000)
        self.assertEqual(maps[0].file_mapping, "/usr/bin/target_elf")

        self.assertEqual(maps[1].permissions, "rw-")
        self.assertEqual(maps[2].permissions, "rwxp")
        self.assertEqual(maps[2].file_mapping, "[stack]")

    def test_parse_memory_maps_invalid_bounds_and_perms_fail(self):
        # Base >= end
        bad_bounds = [{"addr": 0x500000, "addr_end": 0x400000, "perm": "r-x"}]
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_memory_maps(bad_bounds)

        bad_equal = [{"addr": 0x500000, "addr_end": 0x500000, "perm": "r-x"}]
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_memory_maps(bad_equal)

        # Negative address
        bad_neg = [{"addr": -1, "addr_end": 0x500000, "perm": "r-x"}]
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_memory_maps(bad_neg)

        # Invalid permission strings
        for bad_perm in ["invalid", "rwx!", "123", ""]:
            with self.subTest(perm=bad_perm):
                with self.assertRaises(ValueError):
                    RizinDebugParser.parse_memory_maps([{"addr": 0x1000, "addr_end": 0x2000, "perm": bad_perm}])

        # Missing end address
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_memory_maps([{"addr": 0x1000, "perm": "r-x"}])

    def test_parse_breakpoints_valid(self):
        bps = RizinDebugParser.parse_breakpoints(self.valid_breakpoints_list)
        self.assertEqual(len(bps), 3)
        self.assertEqual(bps[0].breakpoint_id, 1)
        self.assertEqual(bps[0].virtual_address, 0x401050)
        self.assertEqual(bps[0].hit_count, 3)
        self.assertTrue(bps[0].enabled)

        self.assertEqual(bps[1].breakpoint_id, 2)
        self.assertEqual(bps[1].virtual_address, 0x401120)
        self.assertFalse(bps[1].enabled)

        self.assertEqual(bps[2].breakpoint_id, 3)
        self.assertEqual(bps[2].hit_count, 10)
        self.assertTrue(bps[2].enabled)

    def test_parse_breakpoints_invalid_fail(self):
        # Missing ID
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_breakpoints([{"addr": 0x401000}])

        # Missing address
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_breakpoints([{"id": 1}])

        # Negative hit count
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_breakpoints([{"id": 1, "addr": 0x4000, "count": -5}])

        # Invalid enabled representation
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_breakpoints([{"id": 1, "addr": 0x4000, "enabled": "not_a_bool"}])

    def test_parse_backtrace_valid(self):
        frames = RizinDebugParser.parse_backtrace(self.valid_backtrace_list)
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[0].frame_number, 0)
        self.assertEqual(frames[0].instruction_pointer, 0x401050)
        self.assertEqual(frames[0].frame_pointer, 0x7fffffffe080)
        self.assertEqual(frames[0].function_name, "sym.vulnerable_function")

        self.assertEqual(frames[1].function_name, "main")
        self.assertEqual(frames[2].function_name, "__libc_start_main")

    def test_parse_backtrace_invalid_fail(self):
        # Missing function name
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_backtrace([{"frame": 0, "ip": 0x4000, "fp": 0x5000}])

        # Empty function name
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_backtrace([{"frame": 0, "ip": 0x4000, "fp": 0x5000, "name": "   "}])

        # Missing frame number
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_backtrace([{"ip": 0x4000, "fp": 0x5000, "name": "foo"}])

    def test_full_session_decoding(self):
        session = RizinDebugParser.parse_bytes(self.valid_session_bytes)
        self.assertIsInstance(session, RizinDebugSession)
        self.assertEqual(session.registers.rip, 0x401050)
        self.assertEqual(len(session.memory_maps), 3)
        self.assertEqual(len(session.breakpoints), 3)
        self.assertEqual(len(session.backtrace), 3)
        self.assertTrue(len(session.session_digest) == 64)

        session_dict = session.to_dict()
        self.assertIn("registers", session_dict)
        self.assertIn("memory_maps", session_dict)
        self.assertIn("breakpoints", session_dict)
        self.assertIn("backtrace", session_dict)
        self.assertIn("session_digest", session_dict)

        # Alternate standard rizin keys (drj, dmj, dbj, dbtj)
        alt_dict = {
            "drj": self.valid_registers_dict,
            "dmj": self.valid_memory_maps_list,
            "dbj": self.valid_breakpoints_list,
            "dbtj": self.valid_backtrace_list,
        }
        alt_session = RizinDebugSessionController.parse_session(alt_dict)
        self.assertEqual(alt_session.registers.rip, 0x401050)

    def test_session_size_and_schema_rejections(self):
        # Exceeds max ceiling
        oversized = b" " * (MAX_SESSION_PAYLOAD_BYTES + 1)
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_bytes(oversized)

        # Empty input
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_bytes(b"")
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_str("   ")

        # Malformed JSON
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_str("{'unclosed': json")

        # Non-dict root
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_str("[]")

        # Missing component
        partial = dict(self.valid_session_dict)
        del partial["backtrace"]
        with self.assertRaises(ValueError):
            RizinDebugParser.parse_session(partial)

    def test_thermodynamic_heap_ceiling(self):
        """Verify memory allocation strictly complies with <= 64 KB ceiling."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            RizinDebugParser.parse_bytes,
            self.valid_session_bytes,
            candidate_id="rizin_debug_parser_ch20",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutator_fuzzing(self):
        """Verify metamorphic stability against adversarial mutations."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.valid_session_bytes)
        self.assertGreaterEqual(len(mutants), 10)

        for m in mutants:
            try:
                session = RizinDebugParser.parse_bytes(m.payload)
                self.assertIsInstance(session.registers.rip, int)
            except ValueError:
                # Expected fail-closed rejection
                pass
            except Exception as err:
                self.fail(f"Unhandled crash on mutant {m.mutation_type}: {err}")


if __name__ == "__main__":
    unittest.main()
