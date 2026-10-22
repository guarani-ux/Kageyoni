"""Unit and adversarial verification suite for Channel 17 (Frida Stalker Engine).

Tests:
1. Valid event stream parsing (tagged binary, Gum64 binary, JSON list, NDJSON).
2. Call tree depth and call graph reconstruction across nested functions.
3. Basic block coverage map and instruction execution tracking.
4. Recursive loop detection (direct self-recursion and mutual cycle recursion).
5. Deep call stack alerting against configured depth threshold.
6. Fail-closed adversarial fuzzing:
   - Corrupted binary envelopes and unknown tags.
   - Truncated buffers at varying byte offsets.
   - Negative depths and out-of-bound call depths.
   - Backwards time travel (decreasing timestamps or out-of-order sequence numbers).
   - Stack underflows (orphan returns on empty call stack).
   - Inverted basic blocks (start address > end address).
   - Malformed addresses (negative, non-hex strings, booleans, > 64-bit uint).
7. Peak heap memory allocation <= 64 KB verified via ThermodynamicProfiler.
"""
from __future__ import annotations

import json
import struct
import unittest

from kageyoni.ninshu.frida_stalker_parser import (
    MAX_UINT64,
    BackwardsTimeTravelError,
    FridaStalkerParser,
    InvalidAddressError,
    InvalidDepthError,
    MalformedEventError,
    StackUnderflowError,
    StalkerBlockEvent,
    StalkerCallEvent,
    StalkerExecEvent,
    StalkerRetEvent,
    StalkerEventType,
    TruncatedStreamError,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


class TestNinshuFridaStalkerParser(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = FridaStalkerParser(deep_stack_threshold=4)

    def test_valid_tagged_binary_stream(self) -> None:
        """Verify parsing standard tagged binary stream with calls, blocks, and rets."""
        events = [
            StalkerCallEvent(source_address=0x1000, target_address=0x2000, depth=0),
            StalkerBlockEvent(start_address=0x2000, end_address=0x2050),
            StalkerExecEvent(instruction_address=0x2010),
            StalkerCallEvent(source_address=0x2020, target_address=0x3000, depth=1),
            StalkerBlockEvent(start_address=0x3000, end_address=0x3040),
            StalkerRetEvent(source_address=0x303F, target_address=0x2025, depth=1),
            StalkerRetEvent(source_address=0x204F, target_address=0x1005, depth=0),
        ]
        packed = FridaStalkerParser.pack_stream(events, format="tagged")
        self.assertGreater(len(packed), 0)

        summary = self.parser.inspect_trace(packed)
        self.assertEqual(summary.total_events, 7)
        self.assertEqual(summary.call_events_count, 2)
        self.assertEqual(summary.ret_events_count, 2)
        self.assertEqual(summary.block_events_count, 2)
        self.assertEqual(summary.exec_events_count, 1)
        self.assertEqual(summary.max_depth_observed, 1)
        self.assertEqual(len(summary.call_tree_roots), 1)

        root = summary.call_tree_roots[0]
        self.assertEqual(root.address, 0x2000)
        self.assertEqual(root.call_count, 1)
        self.assertIn(0x3000, root.children)
        self.assertEqual(root.children[0x3000].depth, 1)

        # Basic block coverage
        self.assertEqual(summary.coverage_map.total_blocks, 2)
        self.assertEqual(summary.coverage_map.total_bytes_covered, (0x2050 - 0x2000) + (0x3040 - 0x3000))
        self.assertEqual(summary.coverage_map.total_exec_instructions, 1)

        # Call graph edges
        self.assertEqual(summary.call_graph_edges[(0x1000, 0x2000)], 1)
        self.assertEqual(summary.call_graph_edges[(0x2020, 0x3000)], 1)

    def test_valid_gum64_binary_stream(self) -> None:
        """Verify parsing native 64-bit GumEvent binary streams."""
        events = [
            StalkerCallEvent(source_address=0x400000, target_address=0x401000, depth=0),
            StalkerBlockEvent(start_address=0x401000, end_address=0x401100),
            StalkerRetEvent(source_address=0x4010FE, target_address=0x400005, depth=0),
        ]
        packed = FridaStalkerParser.pack_stream(events, format="gum64")
        summary = self.parser.inspect_trace(packed)
        self.assertEqual(summary.total_events, 3)
        self.assertEqual(summary.call_events_count, 1)
        self.assertEqual(summary.block_events_count, 1)
        self.assertEqual(summary.ret_events_count, 1)
        self.assertEqual(summary.coverage_map.total_bytes_covered, 0x100)

    def test_json_and_dict_event_streams(self) -> None:
        """Verify parsing JSON array and Python dictionary formats."""
        json_data = json.dumps([
            {"type": "call", "location": "0x401000", "target": "0x402000", "depth": 0, "timestamp_ns": 1000},
            {"type": "block", "begin": "0x402000", "end": "0x402080", "timestamp_ns": 1050},
            {"type": "ret", "location": "0x40207f", "target": "0x401005", "depth": 0, "timestamp_ns": 1100},
        ])
        summary = self.parser.inspect_trace(json_data)
        self.assertEqual(summary.total_events, 3)
        self.assertEqual(summary.call_events_count, 1)
        self.assertEqual(summary.block_events_count, 1)
        self.assertEqual(summary.ret_events_count, 1)
        self.assertTrue(len(summary.sha256_digest) == 64)

    def test_ndjson_line_stream(self) -> None:
        """Verify parsing newline-delimited JSON streams."""
        ndjson = (
            '{"type": "call", "source": "0x5000", "target": "0x6000", "depth": 0}\n'
            '{"type": "exec", "address": "0x6004"}\n'
            '{"type": "ret", "source": "0x6004", "target": "0x5005", "depth": 0}\n'
        )
        summary = self.parser.inspect_trace(ndjson)
        self.assertEqual(summary.total_events, 3)
        self.assertEqual(summary.call_events_count, 1)
        self.assertEqual(summary.exec_events_count, 1)
        self.assertEqual(summary.ret_events_count, 1)

    def test_recursive_loop_detection(self) -> None:
        """Verify detection of direct self-recursion and mutual cycle recursion."""
        # Direct self recursion: A -> A
        events = [
            StalkerCallEvent(source_address=0x1000, target_address=0x2000, depth=0),
            StalkerCallEvent(source_address=0x2010, target_address=0x2000, depth=1),
            StalkerRetEvent(source_address=0x2020, target_address=0x2015, depth=1),
            StalkerRetEvent(source_address=0x2020, target_address=0x1005, depth=0),
        ]
        summary = self.parser.inspect_trace(events)
        self.assertEqual(len(summary.recursive_loops), 1)
        loop = summary.recursive_loops[0]
        self.assertEqual(loop.function_address, 0x2000)
        self.assertEqual(loop.cycle_chain, (0x2000, 0x2000))

        # Mutual cycle recursion: A -> B -> A
        mutual_events = [
            StalkerCallEvent(source_address=0x1000, target_address=0x2000, depth=0),
            StalkerCallEvent(source_address=0x2010, target_address=0x3000, depth=1),
            StalkerCallEvent(source_address=0x3010, target_address=0x2000, depth=2),
            StalkerRetEvent(source_address=0x2020, target_address=0x3015, depth=2),
            StalkerRetEvent(source_address=0x3020, target_address=0x2015, depth=1),
            StalkerRetEvent(source_address=0x2020, target_address=0x1005, depth=0),
        ]
        summary2 = self.parser.inspect_trace(mutual_events)
        self.assertEqual(len(summary2.recursive_loops), 1)
        loop2 = summary2.recursive_loops[0]
        self.assertEqual(loop2.function_address, 0x2000)
        self.assertEqual(loop2.cycle_chain, (0x2000, 0x3000, 0x2000))

    def test_deep_call_stack_detection(self) -> None:
        """Verify flagging when call stack exceeds deep_stack_threshold."""
        parser = FridaStalkerParser(deep_stack_threshold=3)
        events = [
            StalkerCallEvent(source_address=0x100, target_address=0x200, depth=0),
            StalkerCallEvent(source_address=0x200, target_address=0x300, depth=1),
            StalkerCallEvent(source_address=0x300, target_address=0x400, depth=2),
            StalkerCallEvent(source_address=0x400, target_address=0x500, depth=3),  # Exceeds threshold (len 4 > 3)
            StalkerRetEvent(source_address=0x500, target_address=0x405, depth=3),
            StalkerRetEvent(source_address=0x400, target_address=0x305, depth=2),
            StalkerRetEvent(source_address=0x300, target_address=0x205, depth=1),
            StalkerRetEvent(source_address=0x200, target_address=0x105, depth=0),
        ]
        summary = parser.inspect_trace(events)
        self.assertEqual(len(summary.deep_call_stacks), 1)
        self.assertEqual(summary.deep_call_stacks[0].depth, 4)
        self.assertEqual(summary.deep_call_stacks[0].target_address, 0x500)

    def test_adversarial_corrupted_binary_events(self) -> None:
        """Fail-closed on corrupted binary tags."""
        corrupt_data = b"\x99" + (b"\x00" * 30)
        with self.assertRaises(MalformedEventError):
            self.parser.inspect_trace(corrupt_data)

    def test_adversarial_truncated_binary_buffers(self) -> None:
        """Fail-closed on truncated event records."""
        # Tagged CALL expects 20 bytes payload, provide only 10
        truncated = bytes([StalkerEventType.CALL]) + (b"\x01" * 10)
        with self.assertRaises(TruncatedStreamError):
            self.parser.inspect_trace(truncated)

        # Single byte tag without payload
        with self.assertRaises(TruncatedStreamError):
            self.parser.inspect_trace(bytes([StalkerEventType.BLOCK]))

    def test_adversarial_negative_depth_rejection(self) -> None:
        """Fail-closed on negative call or return depths."""
        with self.assertRaises(InvalidDepthError):
            StalkerCallEvent(source_address=0x1000, target_address=0x2000, depth=-1)

        with self.assertRaises(InvalidDepthError):
            StalkerRetEvent(source_address=0x1000, target_address=0x2000, depth=-5)

        with self.assertRaises(InvalidDepthError):
            self.parser.inspect_trace([
                {"type": "call", "source": 0x1000, "target": 0x2000, "depth": -1}
            ])

    def test_adversarial_stack_underflow(self) -> None:
        """Fail-closed on orphan return event when stack is empty."""
        events = [
            StalkerRetEvent(source_address=0x2000, target_address=0x1000, depth=0),
        ]
        with self.assertRaises(StackUnderflowError):
            self.parser.inspect_trace(events)

    def test_adversarial_backwards_time_travel(self) -> None:
        """Fail-closed on backwards time travel or out-of-order sequence."""
        # Backwards timestamp
        events_time = [
            StalkerCallEvent(source_address=0x1000, target_address=0x2000, depth=0, timestamp_ns=5000),
            StalkerCallEvent(source_address=0x2000, target_address=0x3000, depth=1, timestamp_ns=4000),
        ]
        with self.assertRaises(BackwardsTimeTravelError):
            self.parser.inspect_trace(events_time)

        # Out-of-order sequence
        events_seq = [
            StalkerCallEvent(source_address=0x1000, target_address=0x2000, depth=0, sequence=10),
            StalkerCallEvent(source_address=0x2000, target_address=0x3000, depth=1, sequence=9),
        ]
        with self.assertRaises(BackwardsTimeTravelError):
            self.parser.inspect_trace(events_seq)

    def test_adversarial_inverted_block_addresses(self) -> None:
        """Fail-closed when basic block start address is greater than end address."""
        with self.assertRaises(MalformedEventError):
            StalkerBlockEvent(start_address=0x3000, end_address=0x2000)

        with self.assertRaises(MalformedEventError):
            self.parser.inspect_trace([
                {"type": "block", "start": 0x5000, "end": 0x4000}
            ])

    def test_adversarial_address_bounds(self) -> None:
        """Fail-closed on negative, oversized, or boolean addresses."""
        with self.assertRaises(InvalidAddressError):
            StalkerCallEvent(source_address=-1, target_address=0x2000, depth=0)

        with self.assertRaises(InvalidAddressError):
            StalkerCallEvent(source_address=MAX_UINT64 + 1, target_address=0x2000, depth=0)

        with self.assertRaises(InvalidAddressError):
            StalkerCallEvent(source_address=True, target_address=0x2000, depth=0)  # type: ignore

        with self.assertRaises(InvalidAddressError):
            self.parser.inspect_trace([
                {"type": "call", "source": "invalid_hex_addr", "target": 0x2000, "depth": 0}
            ])

    def test_thermodynamic_memory_ceiling(self) -> None:
        """Verify peak heap allocation stays strictly <= 64 KB under trace workloads."""
        raw_events = []
        for i in range(12):
            raw_events.append(StalkerCallEvent(source_address=0x1000 + i * 0x10, target_address=0x2000 + i * 0x10, depth=i))
            raw_events.append(StalkerBlockEvent(start_address=0x2000 + i * 0x10, end_address=0x2000 + i * 0x10 + 0x20))
            raw_events.append(StalkerExecEvent(instruction_address=0x2000 + i * 0x10 + 0x05))

        for i in reversed(range(12)):
            raw_events.append(StalkerRetEvent(source_address=0x2000 + i * 0x10 + 0x1F, target_address=0x1000 + i * 0x10 + 5, depth=i))

        packed_stream = FridaStalkerParser.pack_stream(raw_events, format="tagged")

        summary, receipt = ThermodynamicProfiler.profile_callable(
            self.parser.inspect_trace,
            packed_stream,
            candidate_id="frida_stalker_64kb_gate",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )

        self.assertTrue(receipt.passed)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)
        self.assertEqual(summary.total_events, len(raw_events))


if __name__ == "__main__":
    unittest.main()
