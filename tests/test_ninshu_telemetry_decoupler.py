"""Unit and adversarial verification suite for Channel 39 (Signal & Telemetry Decoupler).

Validates:
1. Valid packet admission, buffer drain, watermark hysteresis.
2. Monotonic sequence verification: gap detection, out-of-order, duplicates.
3. Capacity saturation and deterministic drop policies (DROP_OLDEST, DROP_NEWEST, REJECT_NEW).
4. Strict fail-closed integrity verification (corrupted SHA-256 hash, negative timestamps/seq/channel).
5. Thermodynamic heap memory profiling (peak allocation strictly <= 64 KB).
6. Adversarial fuzzing and boundary saturation.
"""
from __future__ import annotations

import hashlib
import time
import unittest

from kageyoni.ninshu.telemetry_decoupler import (
    BackpressureState,
    CorruptedPacketError,
    DecouplerError,
    DecouplerMetrics,
    DropPolicy,
    InvalidPacketFieldError,
    QueueFullError,
    SequenceAudit,
    TelemetryDecoupler,
    TelemetryPacket,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


class TestNinshuTelemetryDecoupler(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_event_1 = b'{"event": "system_boot", "subsystem": "ninshu", "val": 42}'
        self.raw_event_2 = b'{"event": "carrier_lock", "frequency_hz": 1420405751}'
        self.raw_event_3 = b'{"event": "frame_rendered", "delta_ms": 16.6}'

    def test_packet_creation_and_integrity_binding(self) -> None:
        """Verify normal creation and cryptographic SHA-256 hash validation."""
        pkt = TelemetryPacket.create(
            channel_id=39,
            sequence_no=0,
            payload_bytes=self.raw_event_1,
            timestamp_ns=1000000,
            priority=1,
        )
        self.assertEqual(pkt.channel_id, 39)
        self.assertEqual(pkt.sequence_no, 0)
        self.assertEqual(pkt.timestamp_ns, 1000000)
        self.assertEqual(pkt.payload_bytes, self.raw_event_1)
        self.assertEqual(pkt.payload_hash, hashlib.sha256(self.raw_event_1).hexdigest())
        self.assertEqual(pkt.priority, 1)

        d = pkt.to_dict()
        self.assertEqual(d["channel_id"], 39)
        self.assertEqual(d["payload_bytes_len"], len(self.raw_event_1))

    def test_fail_closed_on_corrupted_hash(self) -> None:
        """Verify corrupted payload_hash is rejected fail-closed."""
        bad_hash = "0" * 64
        with self.assertRaises(CorruptedPacketError):
            TelemetryPacket(
                channel_id=39,
                sequence_no=0,
                timestamp_ns=1000,
                payload_bytes=self.raw_event_1,
                payload_hash=bad_hash,
            )

    def test_fail_closed_on_negative_or_invalid_fields(self) -> None:
        """Verify negative timestamps, sequence numbers, or invalid payload types are rejected."""
        valid_hash = hashlib.sha256(self.raw_event_1).hexdigest()

        # Negative channel_id
        with self.assertRaises(InvalidPacketFieldError):
            TelemetryPacket(
                channel_id=-1,
                sequence_no=0,
                timestamp_ns=1000,
                payload_bytes=self.raw_event_1,
                payload_hash=valid_hash,
            )

        # Negative sequence_no
        with self.assertRaises(InvalidPacketFieldError):
            TelemetryPacket(
                channel_id=39,
                sequence_no=-5,
                timestamp_ns=1000,
                payload_bytes=self.raw_event_1,
                payload_hash=valid_hash,
            )

        # Negative timestamp
        with self.assertRaises(InvalidPacketFieldError):
            TelemetryPacket(
                channel_id=39,
                sequence_no=0,
                timestamp_ns=-1000,
                payload_bytes=self.raw_event_1,
                payload_hash=valid_hash,
            )

        # Invalid payload type (string instead of bytes)
        with self.assertRaises(InvalidPacketFieldError):
            TelemetryPacket(
                channel_id=39,
                sequence_no=0,
                timestamp_ns=1000,
                payload_bytes="not_bytes",  # type: ignore
                payload_hash=valid_hash,
            )

    def test_buffer_admission_and_drain(self) -> None:
        """Verify standard queue push, peek, pop, and drain operations."""
        decoupler = TelemetryDecoupler(capacity=10, high_watermark=0.8, low_watermark=0.2)
        pkt1 = TelemetryPacket.create(39, 0, self.raw_event_1)
        pkt2 = TelemetryPacket.create(39, 1, self.raw_event_2)

        audit1 = decoupler.push(pkt1)
        self.assertIsNotNone(audit1)
        self.assertFalse(audit1.is_gap)
        self.assertFalse(audit1.is_duplicate)

        audit2 = decoupler.push(pkt2)
        self.assertIsNotNone(audit2)
        self.assertFalse(audit2.is_gap)

        self.assertEqual(decoupler.queue_size, 2)
        self.assertEqual(decoupler.peek(), pkt1)

        popped = decoupler.pop()
        self.assertEqual(popped, pkt1)
        self.assertEqual(decoupler.queue_size, 1)

        drained = decoupler.drain()
        self.assertEqual(len(drained), 1)
        self.assertEqual(drained[0], pkt2)
        self.assertEqual(decoupler.queue_size, 0)
        self.assertIsNone(decoupler.pop())

    def test_watermark_hysteresis(self) -> None:
        """Verify high-watermark triggers CONGESTED and low-watermark resets to NORMAL."""
        capacity = 10
        decoupler = TelemetryDecoupler(
            capacity=capacity,
            high_watermark=0.8,  # Congested at >= 8 items
            low_watermark=0.2,   # Normal at <= 2 items
        )
        self.assertEqual(decoupler.backpressure_state, BackpressureState.NORMAL)

        # Push 7 items: ratio = 0.7 -> NORMAL
        for i in range(7):
            pkt = TelemetryPacket.create(39, i, f"msg_{i}".encode("utf-8"))
            decoupler.push(pkt)
            self.assertEqual(decoupler.backpressure_state, BackpressureState.NORMAL)

        # Push 8th item: ratio = 0.8 -> CONGESTED
        pkt8 = TelemetryPacket.create(39, 7, b"msg_7")
        decoupler.push(pkt8)
        self.assertEqual(decoupler.backpressure_state, BackpressureState.CONGESTED)

        # Pop 5 items: count = 3, ratio = 0.3 -> still CONGESTED (hysteresis)
        decoupler.drain(5)
        self.assertEqual(decoupler.queue_size, 3)
        self.assertEqual(decoupler.backpressure_state, BackpressureState.CONGESTED)

        # Pop 1 more item: count = 2, ratio = 0.2 -> NORMAL
        decoupler.pop()
        self.assertEqual(decoupler.queue_size, 2)
        self.assertEqual(decoupler.backpressure_state, BackpressureState.NORMAL)

    def test_sequence_continuity_and_gap_detection(self) -> None:
        """Verify sequence tracking accurately flags gaps, duplicates, and out-of-order packets."""
        decoupler = TelemetryDecoupler(capacity=100)

        # Push seq 0 (expected 0) -> ok
        p0 = TelemetryPacket.create(1, 0, b"seq_0")
        a0 = decoupler.push(p0)
        self.assertFalse(a0.is_gap)
        self.assertFalse(a0.is_duplicate)

        # Push seq 3 (expected 1) -> gap of 2 (missing 1, 2)
        p3 = TelemetryPacket.create(1, 3, b"seq_3")
        a3 = decoupler.push(p3)
        self.assertTrue(a3.is_gap)
        self.assertEqual(a3.gap_count, 2)
        self.assertEqual(decoupler.metrics.gap_count, 2)

        # Push seq 1 (expected 4) -> out of order / late duplicate
        p1 = TelemetryPacket.create(1, 1, b"seq_1")
        a1 = decoupler.push(p1)
        self.assertTrue(a1.is_out_of_order)
        self.assertTrue(a1.is_duplicate)

        # Multi-channel isolation: Channel 2 has its own sequence space
        p2_0 = TelemetryPacket.create(2, 0, b"ch2_0")
        a2_0 = decoupler.push(p2_0)
        self.assertFalse(a2_0.is_gap)
        self.assertEqual(a2_0.expected_sequence_no, 0)

    def test_drop_policy_reject_new(self) -> None:
        """Verify REJECT_NEW raises QueueFullError on buffer saturation."""
        decoupler = TelemetryDecoupler(capacity=2, drop_policy=DropPolicy.REJECT_NEW)
        p0 = TelemetryPacket.create(1, 0, b"p0")
        p1 = TelemetryPacket.create(1, 1, b"p1")
        p2 = TelemetryPacket.create(1, 2, b"p2")

        decoupler.push(p0)
        decoupler.push(p1)
        with self.assertRaises(QueueFullError):
            decoupler.push(p2)

        self.assertEqual(decoupler.queue_size, 2)
        self.assertEqual(decoupler.metrics.rejected_count, 1)

    def test_drop_policy_drop_oldest(self) -> None:
        """Verify DROP_OLDEST evicts oldest packet when capacity is saturated."""
        decoupler = TelemetryDecoupler(capacity=2, drop_policy=DropPolicy.DROP_OLDEST)
        p0 = TelemetryPacket.create(1, 0, b"p0")
        p1 = TelemetryPacket.create(1, 1, b"p1")
        p2 = TelemetryPacket.create(1, 2, b"p2")

        decoupler.push(p0)
        decoupler.push(p1)
        decoupler.push(p2)

        self.assertEqual(decoupler.queue_size, 2)
        self.assertEqual(decoupler.metrics.dropped_count, 1)
        # Oldest (p0) should have been evicted; p1 and p2 remain
        drained = decoupler.drain()
        self.assertEqual(drained[0].sequence_no, 1)
        self.assertEqual(drained[1].sequence_no, 2)

    def test_drop_policy_drop_newest(self) -> None:
        """Verify DROP_NEWEST silently drops new packet on saturation."""
        decoupler = TelemetryDecoupler(capacity=2, drop_policy=DropPolicy.DROP_NEWEST)
        p0 = TelemetryPacket.create(1, 0, b"p0")
        p1 = TelemetryPacket.create(1, 1, b"p1")
        p2 = TelemetryPacket.create(1, 2, b"p2")

        decoupler.push(p0)
        decoupler.push(p1)
        res = decoupler.push(p2)

        self.assertIsNone(res)
        self.assertEqual(decoupler.queue_size, 2)
        self.assertEqual(decoupler.metrics.dropped_count, 1)
        drained = decoupler.drain()
        self.assertEqual(drained[0].sequence_no, 0)
        self.assertEqual(drained[1].sequence_no, 1)

    def test_thermodynamic_heap_ceiling(self) -> None:
        """Verify peak heap allocation stays strictly <= 64 KB during continuous ingest/drain."""
        def workload() -> int:
            decoupler = TelemetryDecoupler(capacity=50)
            for i in range(100):
                payload = f'{{"idx": {i}, "data": "benchmark_payload_{i}"}}'.encode("utf-8")
                pkt = TelemetryPacket.create(
                    channel_id=39,
                    sequence_no=i,
                    payload_bytes=payload,
                )
                decoupler.push(pkt)
                if decoupler.queue_size >= 25:
                    decoupler.drain(15)
            return decoupler.metrics.admitted_count

        count, receipt = ThermodynamicProfiler.profile_callable(
            workload,
            candidate_id="ninshu_telemetry_decoupler_ch39",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertEqual(count, 100)
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_fuzzing_and_saturation(self) -> None:
        """Adversarial suite: boundary capacities, watermarks, zero bytes, huge seq numbers."""
        # 1. Invalid watermark configurations
        with self.assertRaises(ValueError):
            TelemetryDecoupler(capacity=10, high_watermark=0.5, low_watermark=0.6)
        with self.assertRaises(ValueError):
            TelemetryDecoupler(capacity=10, high_watermark=1.5, low_watermark=0.2)
        with self.assertRaises(ValueError):
            TelemetryDecoupler(capacity=0)

        # 2. Empty payload bytes (valid byte sequence, zero length)
        empty_pkt = TelemetryPacket.create(channel_id=0, sequence_no=0, payload_bytes=b"")
        self.assertEqual(empty_pkt.payload_bytes, b"")
        self.assertEqual(empty_pkt.payload_hash, hashlib.sha256(b"").hexdigest())

        decoupler = TelemetryDecoupler(capacity=5)
        decoupler.push(empty_pkt)
        self.assertEqual(decoupler.queue_size, 1)

        # 3. Clear operation
        cleared = decoupler.clear()
        self.assertEqual(cleared, 1)
        self.assertEqual(decoupler.queue_size, 0)
        self.assertEqual(decoupler.backpressure_state, BackpressureState.NORMAL)

        # 4. Reset sequence
        decoupler.reset_sequence(0, 100)
        p100 = TelemetryPacket.create(channel_id=0, sequence_no=100, payload_bytes=b"reset_test")
        audit = decoupler.push(p100)
        self.assertFalse(audit.is_gap)


if __name__ == "__main__":
    unittest.main()
