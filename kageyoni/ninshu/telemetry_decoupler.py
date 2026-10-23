"""Channel 39: Signal & Telemetry Decoupler for Kageyōni Ninshū.

Decouples synchronous or raw event streams into asynchronous, backpressured
telemetry frames with strict deterministic queue eviction, watermark hysteresis,
monotonic sequence tracking, and cryptographic integrity verification.

Zero external dependencies: uses only Python standard library.
Enforces fail-closed validation, explicit typed data structures, and deterministic state transitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple


class DropPolicy(Enum):
    """Deterministic queue eviction policy when capacity is saturated."""
    DROP_OLDEST = "DROP_OLDEST"  # Evicts the oldest packet in the queue
    DROP_NEWEST = "DROP_NEWEST"  # Evicts the newly incoming packet
    REJECT_NEW = "REJECT_NEW"    # Rejects incoming packet by raising QueueFullError


class BackpressureState(Enum):
    """Hysteresis state for buffer backpressure."""
    NORMAL = "NORMAL"          # Operating below high-watermark
    CONGESTED = "CONGESTED"    # Crossed high-watermark, backpressure active until below low-watermark


class DecouplerError(ValueError):
    """Base error for telemetry decoupler violations."""
    pass


class CorruptedPacketError(DecouplerError):
    """Raised when payload SHA-256 hash does not match payload_bytes."""
    pass


class InvalidPacketFieldError(DecouplerError):
    """Raised when packet fields contain illegal values (negative timestamp, negative sequence_no, etc.)."""
    pass


class QueueFullError(DecouplerError):
    """Raised when buffer is full and drop policy is REJECT_NEW."""
    pass


@dataclass(frozen=True)
class TelemetryPacket:
    """Immutable telemetry frame with cryptographic integrity binding."""
    channel_id: int
    sequence_no: int
    timestamp_ns: int
    payload_bytes: bytes
    payload_hash: str
    priority: int = 0  # Higher value indicates higher priority (e.g. 0=normal, 1=high, 2=critical)

    def __post_init__(self) -> None:
        if self.channel_id < 0:
            raise InvalidPacketFieldError(f"channel_id must be non-negative: {self.channel_id}")
        if self.sequence_no < 0:
            raise InvalidPacketFieldError(f"sequence_no must be non-negative: {self.sequence_no}")
        if self.timestamp_ns < 0:
            raise InvalidPacketFieldError(f"timestamp_ns must be non-negative: {self.timestamp_ns}")
        if not isinstance(self.payload_bytes, (bytes, bytearray)):
            raise InvalidPacketFieldError("payload_bytes must be bytes or bytearray")

        # Strict cryptographic verification
        expected_hash = hashlib.sha256(self.payload_bytes).hexdigest()
        if self.payload_hash.lower() != expected_hash.lower():
            raise CorruptedPacketError(
                f"Payload hash mismatch: provided={self.payload_hash}, computed={expected_hash}"
            )

    @classmethod
    def create(
        cls,
        channel_id: int,
        sequence_no: int,
        payload_bytes: bytes,
        timestamp_ns: Optional[int] = None,
        priority: int = 0,
    ) -> "TelemetryPacket":
        """Factory helper computing canonical payload_hash and current timestamp if omitted."""
        ts = timestamp_ns if timestamp_ns is not None else time.time_ns()
        digest = hashlib.sha256(payload_bytes).hexdigest()
        return cls(
            channel_id=channel_id,
            sequence_no=sequence_no,
            timestamp_ns=ts,
            payload_bytes=payload_bytes,
            payload_hash=digest,
            priority=priority,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes telemetry packet metadata (excluding raw payload bytes)."""
        return {
            "channel_id": self.channel_id,
            "sequence_no": self.sequence_no,
            "timestamp_ns": self.timestamp_ns,
            "payload_bytes_len": len(self.payload_bytes),
            "payload_hash": self.payload_hash,
            "priority": self.priority,
        }


@dataclass
class SequenceAudit:
    """Audit report for sequence continuity on a channel."""
    channel_id: int
    expected_sequence_no: int
    received_sequence_no: int
    is_duplicate: bool
    is_out_of_order: bool
    is_gap: bool
    gap_count: int


@dataclass
class DecouplerMetrics:
    """Operational metrics for the telemetry decoupler."""
    admitted_count: int = 0
    drained_count: int = 0
    dropped_count: int = 0
    rejected_count: int = 0
    gap_count: int = 0
    duplicate_count: int = 0
    out_of_order_count: int = 0


class TelemetryDecoupler:
    """Decouples synchronous event production from asynchronous consumption.

    Features:
    - Bounded queue with capacity limits.
    - Watermark hysteresis: triggers CONGESTED state at high_watermark and clears at low_watermark.
    - Deterministic drop policy: DROP_OLDEST, DROP_NEWEST, REJECT_NEW.
    - Per-channel monotonic sequence number tracking (detecting gaps, duplicates, out-of-order).
    - Fail-closed cryptographic integrity validation.
    """

    def __init__(
        self,
        capacity: int = 1000,
        high_watermark: float = 0.8,
        low_watermark: float = 0.2,
        drop_policy: DropPolicy = DropPolicy.DROP_OLDEST,
    ) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be positive: {capacity}")
        if not (0.0 < low_watermark < high_watermark <= 1.0):
            raise ValueError(
                f"Watermarks must satisfy 0.0 < low ({low_watermark}) < high ({high_watermark}) <= 1.0"
            )

        self.capacity: int = capacity
        self.high_watermark: float = high_watermark
        self.low_watermark: float = low_watermark
        self.drop_policy: DropPolicy = drop_policy

        self._queue: List[TelemetryPacket] = []
        self._backpressure_state: BackpressureState = BackpressureState.NORMAL
        self._next_expected_seq: Dict[int, int] = {}  # channel_id -> next expected seq
        self.metrics: DecouplerMetrics = DecouplerMetrics()

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def backpressure_state(self) -> BackpressureState:
        return self._backpressure_state

    @property
    def fill_ratio(self) -> float:
        return len(self._queue) / self.capacity

    def _update_watermark_state(self) -> None:
        ratio = self.fill_ratio
        if self._backpressure_state == BackpressureState.NORMAL:
            if ratio >= self.high_watermark:
                self._backpressure_state = BackpressureState.CONGESTED
        elif self._backpressure_state == BackpressureState.CONGESTED:
            if ratio <= self.low_watermark:
                self._backpressure_state = BackpressureState.NORMAL

    def check_sequence(self, packet: TelemetryPacket) -> SequenceAudit:
        """Audits packet sequence continuity without modifying tracker state."""
        ch = packet.channel_id
        seq = packet.sequence_no
        expected = self._next_expected_seq.get(ch, 0)

        is_dup = seq < expected
        is_ooo = seq < expected
        is_gap = seq > expected
        gap_cnt = (seq - expected) if is_gap else 0

        return SequenceAudit(
            channel_id=ch,
            expected_sequence_no=expected,
            received_sequence_no=seq,
            is_duplicate=is_dup,
            is_out_of_order=is_ooo,
            is_gap=is_gap,
            gap_count=gap_cnt,
        )

    def push(self, packet: TelemetryPacket) -> Optional[SequenceAudit]:
        """Ingests a packet into the buffer adhering to drop policy, watermarks, and sequence tracking.

        Returns:
            SequenceAudit report for the ingested packet, or None if packet was dropped.
        """
        if not isinstance(packet, TelemetryPacket):
            raise InvalidPacketFieldError(f"Expected TelemetryPacket, got {type(packet)}")

        # 1. Capacity and Backpressure check
        if len(self._queue) >= self.capacity:
            if self.drop_policy == DropPolicy.REJECT_NEW:
                self.metrics.rejected_count += 1
                raise QueueFullError(
                    f"Buffer capacity {self.capacity} exceeded and policy is REJECT_NEW"
                )
            elif self.drop_policy == DropPolicy.DROP_NEWEST:
                self.metrics.dropped_count += 1
                self._update_watermark_state()
                return None
            elif self.drop_policy == DropPolicy.DROP_OLDEST:
                evicted = self._queue.pop(0)
                self.metrics.dropped_count += 1
            else:
                raise DecouplerError(f"Unsupported drop policy: {self.drop_policy}")

        # 2. Sequence verification & audit
        audit = self.check_sequence(packet)
        if audit.is_duplicate:
            self.metrics.duplicate_count += 1
        elif audit.is_out_of_order:
            self.metrics.out_of_order_count += 1
        elif audit.is_gap:
            self.metrics.gap_count += audit.gap_count

        # Advance expected sequence number to packet.sequence_no + 1 if forward progress
        ch = packet.channel_id
        if packet.sequence_no >= self._next_expected_seq.get(ch, 0):
            self._next_expected_seq[ch] = packet.sequence_no + 1

        # 3. Admission to queue
        self._queue.append(packet)
        self.metrics.admitted_count += 1

        # 4. Hysteresis update
        self._update_watermark_state()

        return audit

    def pop(self) -> Optional[TelemetryPacket]:
        """Pops and returns the next telemetry packet from the queue in FIFO order."""
        if not self._queue:
            return None

        packet = self._queue.pop(0)
        self.metrics.drained_count += 1
        self._update_watermark_state()
        return packet

    def drain(self, max_items: Optional[int] = None) -> List[TelemetryPacket]:
        """Drains up to max_items (or all if None) from the queue."""
        if max_items is not None and max_items < 0:
            raise ValueError(f"max_items must be non-negative: {max_items}")

        limit = len(self._queue) if max_items is None else min(len(self._queue), max_items)
        drained: List[TelemetryPacket] = []
        for _ in range(limit):
            pkt = self.pop()
            if pkt is not None:
                drained.append(pkt)

        return drained

    def peek(self) -> Optional[TelemetryPacket]:
        """Peeks at the next packet without dequeuing."""
        return self._queue[0] if self._queue else None

    def clear(self) -> int:
        """Clears all buffered packets and resets watermark state. Returns number of cleared packets."""
        count = len(self._queue)
        self._queue.clear()
        self._backpressure_state = BackpressureState.NORMAL
        return count

    def reset_sequence(self, channel_id: int, expected_seq: int = 0) -> None:
        """Explicitly resets or sets the next expected sequence number for a channel."""
        if expected_seq < 0:
            raise InvalidPacketFieldError(f"expected_seq must be non-negative: {expected_seq}")
        self._next_expected_seq[channel_id] = expected_seq

    def inspect_frame(self, frame: Union[TelemetryPacket, Dict[str, Any], bytes, str]) -> Dict[str, Any]:
        """Inspects, admits, and audits a telemetry frame, returning structured verification metrics."""
        if isinstance(frame, bytes):
            try:
                frame = json.loads(frame.decode("utf-8"))
            except Exception:
                frame = {"channel_id": 1, "sequence_no": self._next_expected_seq.get(1, 0), "payload": frame}
        elif isinstance(frame, str):
            try:
                frame = json.loads(frame)
            except Exception:
                frame = {"channel_id": 1, "sequence_no": self._next_expected_seq.get(1, 0), "payload": frame.encode("utf-8")}

        if isinstance(frame, dict):
            raw_payload = frame.get("payload", b"")
            if isinstance(raw_payload, str):
                p_bytes = raw_payload.encode("utf-8")
            elif isinstance(raw_payload, bytes):
                p_bytes = raw_payload
            else:
                p_bytes = json.dumps(raw_payload).encode("utf-8")
            
            ch_id = frame.get("channel_id", 1)
            seq_no = frame.get("sequence_no", self._next_expected_seq.get(ch_id, 0))
            ts = frame.get("timestamp_ns", int(time.time() * 1e9))
            packet = TelemetryPacket.create(
                channel_id=ch_id,
                sequence_no=seq_no,
                payload_bytes=p_bytes,
                timestamp_ns=ts,
            )
        elif isinstance(frame, TelemetryPacket):
            packet = frame
        else:
            raise DecouplerError(f"Unsupported frame type: {type(frame)}")

        audit = self.push(packet)
        return {
            "channel_id": packet.channel_id,
            "sequence_no": packet.sequence_no,
            "payload_hash": packet.payload_hash,
            "timestamp_ns": packet.timestamp_ns,
            "backpressure_state": self.backpressure_state.value,
            "queue_size": self.queue_size,
            "audit": {
                "is_duplicate": audit.is_duplicate if audit else False,
                "is_out_of_order": audit.is_out_of_order if audit else False,
                "is_gap": audit.is_gap if audit else False,
                "gap_count": audit.gap_count if audit else 0,
            } if audit else None,
        }
