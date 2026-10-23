"""Ninshū SSL Circuit Architecture: Mechanical Waveform Enforcement.

Reconfigures the SSL channel strip into a physical signal conditioner
that mechanically governs the computational substrate (the liquid metal)
WHILE IT REMAINS LIQUID AND STREAMING:

1. Velocity / Hertz Governor (Rate limiter & Clock divider)
2. Frequency Crossover Network (Sub-bass, Mid logic, High tokens)
3. Epistemic Phase Discriminator (Vector cross-product: static claim vs dynamic trace)
4. Dynamic Amplitude Limiter (Zero-clipping token & memory ceiling)
5. Dark Matter Deficit Socket (First-class unknown resonator)
6. Preamp Ingress Trim (Byte, record, and recursion depth admission budget)
7. HPF / LPF Scope Filter (Confidence floor & depth/window ceilings)
8. Four-Band Parametric EQ (Layer budget allocator)
9. VCA Dynamics Compressor (Bounded queue with backpressure receipts)
10. Phase Comparison & Invert (Constructive lock vs contradiction & disconfirmation view)
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


class SignalClippingError(ValueError):
    """Raised when liquid metal amplitude exceeds the hard physical ceiling (0 dBFS)."""
    pass


class PhaseCancellationFault(ValueError):
    """Raised when an unhandled 180-degree phase contradiction is detected without Chord isolation."""
    pass


class IngressTrimExceededError(ValueError):
    """Raised when an ingress payload exceeds declared byte, record, or recursion bounds."""
    pass


@dataclass
class WaveformMetric:
    """Real-time physical measurement of streaming computational substrate."""
    frequency_hz: float          # Velocity of state transitions (cycles/sec)
    amplitude_dbfs: float        # Signal density / context saturation (-inf to 0.0 dBFS)
    phase_degrees: float         # 0.0 deg (in-phase truth) to 180.0 deg (anti-phase deception)
    spectrum_band: str           # "SUB_BASS_SCHEMA", "MID_RANGE_LOGIC", "HIGH_TRANSIENT_TOKENS"
    entropy_ratio: float         # 0.0 (quiescent constant) to 1.0 (pure random/encrypted)
    phase_correlation: float     # +1.0 (perfect coherence) to -1.0 (pure contradiction)


def _calculate_recursion_depth(obj: Any, current_depth: int = 1) -> int:
    """Calculates maximum recursion depth in nested dictionaries and lists."""
    if isinstance(obj, dict):
        if not obj:
            return current_depth
        return max(_calculate_recursion_depth(v, current_depth + 1) for v in obj.values())
    elif isinstance(obj, list):
        if not obj:
            return current_depth
        return max(_calculate_recursion_depth(item, current_depth + 1) for item in obj)
    return current_depth


@dataclass
class PreampIngressTrim:
    """Enforces byte, record, and recursion depth admission budgets (Control 3)."""
    max_input_bytes: int = 10 * 1024 * 1024  # 10 MB default
    max_records: int = 1000
    max_recursion_depth: int = 10
    trim_active: bool = True

    def evaluate_payload(self, payload: Any) -> Dict[str, Any]:
        """Evaluates payload against trim bounds; raises IngressTrimExceededError on violation if trim_active."""
        payload_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        records_count = len(payload) if isinstance(payload, list) else 1
        recursion_depth = _calculate_recursion_depth(payload)

        if self.trim_active:
            if payload_bytes > self.max_input_bytes:
                raise IngressTrimExceededError(
                    f"Payload size {payload_bytes} bytes exceeds max_input_bytes {self.max_input_bytes}"
                )
            if records_count > self.max_records:
                raise IngressTrimExceededError(
                    f"Payload records {records_count} exceeds max_records {self.max_records}"
                )
            if recursion_depth > self.max_recursion_depth:
                raise IngressTrimExceededError(
                    f"Payload recursion depth {recursion_depth} exceeds max_recursion_depth {self.max_recursion_depth}"
                )

        return {
            "admitted": True,
            "trim_active": self.trim_active,
            "bytes_admitted": payload_bytes,
            "records_admitted": records_count,
            "recursion_depth": recursion_depth,
            "timestamp": time.time(),
        }


@dataclass
class ScopeFilter:
    """HPF / LPF Scope Filter (Control 4).

    HPF enforces minimum confidence / severity floor.
    LPF enforces maximum depth / time-window ceiling.
    Logs omitted_by_scope_count.
    """
    min_confidence: float = 0.0            # HPF confidence floor
    min_severity: float = 0.0              # HPF severity floor
    max_depth: Optional[int] = None        # LPF depth ceiling
    max_time_window: Optional[float] = None # LPF timestamp ceiling
    filter_active: bool = True

    def filter_records(
        self,
        records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if not self.filter_active:
            return list(records), {
                "omitted_by_scope_count": 0,
                "retained_count": len(records),
                "omitted_records": [],
                "filter_active": False,
            }

        retained: List[Dict[str, Any]] = []
        omitted: List[Dict[str, Any]] = []

        for r in records:
            conf = r.get("confidence_score", r.get("reliability_score", 1.0))
            sev = r.get("severity", 1.0)
            depth = r.get("depth", 0)
            ts = r.get("timestamp", 0.0)

            # HPF checks (floor)
            if conf < self.min_confidence:
                omitted.append({"record": r, "reason": "HPF_CONFIDENCE_BELOW_FLOOR", "confidence": conf})
                continue
            if sev < self.min_severity:
                omitted.append({"record": r, "reason": "HPF_SEVERITY_BELOW_FLOOR", "severity": sev})
                continue

            # LPF checks (ceiling)
            if self.max_depth is not None and depth > self.max_depth:
                omitted.append({"record": r, "reason": "LPF_DEPTH_EXCEEDS_CEILING", "depth": depth})
                continue
            if self.max_time_window is not None and ts > self.max_time_window:
                omitted.append({"record": r, "reason": "LPF_TIMESTAMP_EXCEEDS_WINDOW", "timestamp": ts})
                continue

            retained.append(r)

        return retained, {
            "omitted_by_scope_count": len(omitted),
            "retained_count": len(retained),
            "omitted_records": omitted,
            "filter_active": True,
        }


@dataclass
class FourBandEQ:
    """Four-Band Parametric EQ Budget Allocator (Control 5).

    Allocates step/byte budget across:
    - LF: Low Freq (Headers, Substrate, SQLite schemas)
    - LMF: Low-Mid Freq (AST, CFG, Control flow)
    - HMF: High-Mid Freq (Runtime, Trace state)
    - HF: High Freq (Tokens, Secrets, Regex, Anomalies)
    """
    lf_budget_bytes: int = 1024 * 1024
    lmf_budget_bytes: int = 1024 * 1024
    hmf_budget_bytes: int = 1024 * 1024
    hf_budget_bytes: int = 1024 * 1024
    eq_in: bool = True

    def classify_band(self, record: Dict[str, Any]) -> str:
        rec_type = record.get("type", record.get("spectrum_band", ""))
        if rec_type in {"SUB_BASS_SCHEMA", "schema", "partition", "header", "sqlite_table", "LF"}:
            return "LF"
        elif rec_type in {"MID_RANGE_LOGIC", "function", "ast", "cfg", "method", "decompilation", "LMF"}:
            return "LMF"
        elif rec_type in {"HIGH_MID_TRACE", "trace", "runtime", "memory_offset", "register", "HMF"}:
            return "HMF"
        elif rec_type in {"HIGH_TRANSIENT_TOKENS", "token", "string", "key", "packet_sni", "regex", "secret", "HF"}:
            return "HF"
        return "LMF"

    def allocate(
        self,
        records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if not self.eq_in:
            return list(records), {
                "eq_in": False,
                "retained_count": len(records),
                "throttled_count": 0,
            }

        band_budgets = {
            "LF": self.lf_budget_bytes,
            "LMF": self.lmf_budget_bytes,
            "HMF": self.hmf_budget_bytes,
            "HF": self.hf_budget_bytes,
        }
        band_used = {"LF": 0, "LMF": 0, "HMF": 0, "HF": 0}
        retained = []
        throttled = []

        for r in records:
            band = self.classify_band(r)
            r_bytes = len(json.dumps(r, ensure_ascii=False).encode("utf-8"))
            if band_used[band] + r_bytes > band_budgets[band]:
                throttled_record = copy.deepcopy(r)
                throttled_record["_eq_throttled"] = True
                throttled_record["_eq_band"] = band
                throttled.append(throttled_record)
            else:
                band_used[band] += r_bytes
                r_copy = copy.deepcopy(r)
                r_copy["_eq_band"] = band
                retained.append(r_copy)

        return retained, {
            "eq_in": True,
            "band_used_bytes": band_used,
            "band_budget_bytes": band_budgets,
            "retained_count": len(retained),
            "throttled_count": len(throttled),
            "throttled_records": throttled,
        }


@dataclass
class VCADynamicsCompressor:
    """Dynamics & Backpressure Compressor (Control 9).

    Bounded queue (max_in_flight, batch_size) with overflow receipts.
    """
    max_in_flight: int = 10
    batch_size: int = 5
    dynamics_in: bool = True
    queue: List[Dict[str, Any]] = field(default_factory=list)
    overflow_receipts: List[Dict[str, Any]] = field(default_factory=list)

    def enqueue(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if not self.dynamics_in:
            self.queue.append(record)
            return {"status": "QUEUED_UNBOUNDED", "queue_depth": len(self.queue)}

        if len(self.queue) >= self.max_in_flight:
            rec_bytes = json.dumps(record, sort_keys=True).encode("utf-8")
            receipt = {
                "status": "OVERFLOW_BACKPRESSURE",
                "dropped": True,
                "queue_depth": len(self.queue),
                "max_in_flight": self.max_in_flight,
                "timestamp": time.time(),
                "receipt_digest": hashlib.sha256(rec_bytes).hexdigest(),
                "record": record,
            }
            self.overflow_receipts.append(receipt)
            return receipt

        self.queue.append(record)
        return {"status": "QUEUED", "queue_depth": len(self.queue)}

    def process_batch(self) -> List[Dict[str, Any]]:
        batch = self.queue[:self.batch_size]
        self.queue = self.queue[self.batch_size:]
        return batch


@dataclass
class PhaseComparisonResult:
    """Explicit typed comparison of claims and observations (Control 11)."""
    status: str                  # "CONSTRUCTIVE_LOCK", "CONTRADICTION", "DIFFERENT", "INCOMPARABLE", "UNKNOWN"
    phase_correlation: float     # +1.0 (lock), -1.0 (contradiction), 0.0 (orthogonal/different/incomparable)
    phase_degrees: float         # 0.0, 180.0, 90.0
    divergences: List[str] = field(default_factory=list)
    claim_a: Dict[str, Any] = field(default_factory=dict)
    claim_b: Dict[str, Any] = field(default_factory=dict)


def compare_phase(claim_a: Dict[str, Any], claim_b: Dict[str, Any]) -> PhaseComparisonResult:
    """Compares claims across two strips and computes exact constructive lock vs contradiction (Control 11)."""
    if not claim_a and not claim_b:
        return PhaseComparisonResult(
            status="UNKNOWN",
            phase_correlation=0.0,
            phase_degrees=90.0,
            divergences=["Both claims empty"],
            claim_a=claim_a,
            claim_b=claim_b,
        )

    # Identical claims -> Constructive lock
    if claim_a == claim_b:
        return PhaseComparisonResult(
            status="CONSTRUCTIVE_LOCK",
            phase_correlation=1.0,
            phase_degrees=0.0,
            divergences=[],
            claim_a=claim_a,
            claim_b=claim_b,
        )

    shared_keys = set(claim_a.keys()) & set(claim_b.keys())
    # Disjoint schemas / no shared context -> INCOMPARABLE (missing facts do not become false facts)
    if not shared_keys:
        return PhaseComparisonResult(
            status="INCOMPARABLE",
            phase_correlation=0.0,
            phase_degrees=90.0,
            divergences=["No overlapping keys between claims"],
            claim_a=claim_a,
            claim_b=claim_b,
        )

    divergences = []
    has_direct_contradiction = False

    for k in shared_keys:
        va = claim_a[k]
        vb = claim_b[k]
        if va != vb:
            divergences.append(f"Key '{k}': claim_a={va} != claim_b={vb}")
            # Check for direct logical/boolean contradiction or security refusal vs permission
            if isinstance(va, bool) and isinstance(vb, bool):
                has_direct_contradiction = True
            elif k in {"authorized", "valid", "permitted", "result", "outcome", "status"}:
                has_direct_contradiction = True

    if has_direct_contradiction:
        return PhaseComparisonResult(
            status="CONTRADICTION",
            phase_correlation=-1.0,
            phase_degrees=180.0,
            divergences=divergences,
            claim_a=claim_a,
            claim_b=claim_b,
        )

    return PhaseComparisonResult(
        status="DIFFERENT",
        phase_correlation=0.0,
        phase_degrees=90.0,
        divergences=divergences,
        claim_a=claim_a,
        claim_b=claim_b,
    )


def apply_phase_invert(
    items: List[Dict[str, Any]],
    phase_invert: bool = False
) -> List[Dict[str, Any]]:
    """Phase Invert ∅ (Control 12).

    Display-only view inverting polarity to adversarial disconfirmation mode:
    Surfaces only contradictions, anomalies, and boundary violations.
    Never turns a contradiction into truth or a refusal into permission.
    """
    if not phase_invert:
        return list(items)

    surfaced = []
    for item in items:
        # Check if item represents a contradiction, violation, or negative divergence
        status = item.get("status")
        corr = item.get("phase_correlation", 1.0)
        is_violation = item.get("is_violation", False) or item.get("boundary_violation", False)
        if status == "CONTRADICTION" or corr < 0 or is_violation:
            view_item = copy.deepcopy(item)
            view_item["_phase_inverted_view"] = True
            surfaced.append(view_item)
    return surfaced


@dataclass
class ChannelCircuit:
    """The internal physical circuit topology of an SSL 4000 channel strip."""
    channel_number: int
    name: str

    # 1. Clock Divider & Hertz Ceiling
    max_hertz_limit: float = 100.0        # Max permitted cycles per second before throttling
    last_cycle_timestamp: float = field(default_factory=time.time)

    # 2. 0 dBFS Hard Ceiling (Amplitude Limiter)
    max_byte_budget: int = 10 * 1024 * 1024  # 10 MB limit before hard clipping
    accumulated_bytes: int = 0

    # 3. 3-Way Crossover Filter (Band Splitter)
    crossover_active: bool = True

    # 4. Phase Discriminator Mode
    phase_mode: str = "CHORD_PRESERVE"    # "CHORD_PRESERVE" (polyphonic) vs "STRICT_IN_PHASE"

    # 5. Deficit Socket (Dark Matter Resonator)
    unplaced_deficits: List[Dict[str, Any]] = field(default_factory=list)
    anomalous_residue: List[Dict[str, Any]] = field(default_factory=list)

    # 6. Physical Controls Sub-Circuits
    ingress_trim: PreampIngressTrim = field(default_factory=PreampIngressTrim)
    scope_filter: ScopeFilter = field(default_factory=ScopeFilter)
    four_band_eq: FourBandEQ = field(default_factory=FourBandEQ)
    dynamics_compressor: VCADynamicsCompressor = field(default_factory=VCADynamicsCompressor)

    def condition_cycle(self, raw_input_bytes: bytes, declared_intent: str) -> None:
        """Mechanically enforces the Cycle & Hertz physics on incoming substrate."""
        now = time.time()
        elapsed = now - self.last_cycle_timestamp
        if elapsed > 0:
            current_hz = 1.0 / elapsed
            if current_hz > self.max_hertz_limit:
                required_sleep = (1.0 / self.max_hertz_limit) - elapsed
                time.sleep(max(0.0, required_sleep))
        self.last_cycle_timestamp = time.time()

        # Enforce Amplitude / Decibel Ceiling
        self.accumulated_bytes += len(raw_input_bytes)
        if self.accumulated_bytes > self.max_byte_budget:
            raise SignalClippingError(
                f"CH {self.channel_number:02d} clipped: {self.accumulated_bytes} bytes exceeds "
                f"0 dBFS limit ({self.max_byte_budget} bytes). Throttling required."
            )

    def discriminate_phase(
        self,
        static_claim: Dict[str, Any],
        dynamic_observation: Dict[str, Any]
    ) -> WaveformMetric:
        """Calculates the real-time Phase Angle (theta) between what the binary claims and what execution does."""
        claim_val = json.dumps(static_claim, sort_keys=True)
        obs_val = json.dumps(dynamic_observation, sort_keys=True)

        # Exact match = 0 degrees (Pure In-Phase)
        if claim_val == obs_val:
            return WaveformMetric(
                frequency_hz=1.0,
                amplitude_dbfs=-6.0,
                phase_degrees=0.0,
                spectrum_band="MID_RANGE_LOGIC",
                entropy_ratio=0.1,
                phase_correlation=1.0
            )

        is_anti_phase = (
            static_claim.get("authorized") != dynamic_observation.get("authorized") or
            static_claim.get("result") != dynamic_observation.get("result")
        )

        phase_angle = 180.0 if is_anti_phase else 90.0
        correlation = -1.0 if is_anti_phase else 0.0

        if phase_angle == 180.0 and self.phase_mode == "STRICT_IN_PHASE":
            raise PhaseCancellationFault(
                f"CH {self.channel_number:02d} Phase Cancellation Fault: "
                f"Static Claim {static_claim} directly contradicts Dynamic Reality {dynamic_observation}."
            )

        self.anomalous_residue.append({
            "channel": self.channel_number,
            "static_claim": static_claim,
            "dynamic_observation": dynamic_observation,
            "phase_degrees": phase_angle,
            "correlation": correlation,
            "timestamp": time.time()
        })

        return WaveformMetric(
            frequency_hz=1.0,
            amplitude_dbfs=-1.5,
            phase_degrees=phase_angle,
            spectrum_band="MID_RANGE_LOGIC",
            entropy_ratio=0.8,
            phase_correlation=correlation
        )

    def route_crossover(self, signal: Dict[str, Any]) -> str:
        """Mechanically sorts streaming signal into its proper frequency band."""
        sig_type = signal.get("type", "")
        if sig_type in {"schema", "partition", "header", "sqlite_table"}:
            return "SUB_BASS_SCHEMA"
        elif sig_type in {"function", "ast", "cfg", "method", "decompilation"}:
            return "MID_RANGE_LOGIC"
        elif sig_type in {"token", "string", "key", "packet_sni", "memory_offset"}:
            return "HIGH_TRANSIENT_TOKENS"
        else:
            self.unplaced_deficits.append({
                "signal": signal,
                "reason": "SIGNAL_OUTSIDE_KNOWN_SPECTRUM",
                "socket_needed": "FREQUENCY_TRANSDUCER_REQUIRED"
            })
            return "DARK_MATTER_DEFICIT"
