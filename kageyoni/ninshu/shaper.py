"""Ninshū SSL Active Session Mixing & Knob Shaper.

Provides the interactive engineering tactile surface:
- Flipping Switches (Mute, Solo, Phase Invert, EQ In, Dynamics In, Insert Bypass)
- Turning Knobs (Preamp Gain/Trim, HPF/LPF Cutoff, 4-Band Parametric EQ, VCA Threshold/Ratio, Noise Gate)
- Riding Faders (Channel volume, Priority weight & Bus Trim)
- Reading Meters (Measured bytes, Latency, Peak heap, Failures, Contradictions; synthetic dB tagged illustrative)
- Comprehensive integration with all 20 SSL Controls
"""
from __future__ import annotations

import copy
import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ageing import SSLBoardAgeingEngine
from .circuits import (
    ChannelCircuit,
    IngressTrimExceededError,
    PhaseComparisonResult,
    WaveformMetric,
    apply_phase_invert,
    compare_phase,
)
from .modulator import SubstrateModulator
from .patchbay import Patchbay
from .scars import SCAR_REGISTRY, ScarFeedbackMatrix


@dataclass
class ChannelPotentiometers:
    """The physical knobs and switches on one SSL 4000 channel strip."""
    channel_number: int
    name: str

    # Switches
    eq_in: bool = True
    dynamics_in: bool = True
    phase_invert: bool = False
    mute: bool = False
    solo: bool = False
    insert_bypass: bool = False

    # Knobs (Potentiometers)
    preamp_trim_db: float = 0.0          # -20 to +20 dB
    hpf_freq_hz: float = 20.0            # 20 Hz to 500 Hz (High-Pass scope limiter)
    lpf_freq_khz: float = 20.0           # 3 kHz to 20 kHz (Low-Pass noise ceiling)

    # 4-Band Parametric EQ Knobs
    hf_gain_db: float = 0.0              # High Freq (Tokens, Secrets, Regex)
    hmf_gain_db: float = 0.0             # High-Mid (Functions, CFGs, AST logic)
    lmf_gain_db: float = 0.0             # Low-Mid (Wrappers, Dependencies, Schemas)
    lf_gain_db: float = 0.0              # Low Freq (OS, PE/ELF Headers, SQLite Foundation)

    # Dynamics Knobs
    vca_threshold_db: float = -6.0       # Compression trigger point
    vca_ratio: float = 4.0               # 2:1, 4:1, 10:1 (brickwall)
    noise_gate_threshold: float = 0.5    # Epistemic squelch threshold

    # Fader
    fader_level_db: float = 0.0          # Fader volume (-inf to +10 dB)

    # Additional SSL Control Configuration
    bus_assignment: str = "BUS_A"
    insert_chain: List[Callable[[Dict[str, Any]], Dict[str, Any]]] = field(default_factory=list)
    failures_recorded: List[Dict[str, Any]] = field(default_factory=list)
    safety_locked: bool = True


@dataclass
class ChannelMeterBridge:
    """Real-time LED / VU Meter and empirical telemetry readouts (Control 16)."""
    channel_number: int

    # Empirical measured metrics (strictly grounded)
    measured_bytes: int = 0
    latency_ms: float = 0.0
    peak_heap_bytes: int = 0
    failures_detected: int = 0
    contradictions_detected: int = 0

    # Synthetic / analogue visual metrics (explicitly flagged illustrative_only)
    vu_input_dbfs: float = -60.0
    vu_output_dbfs: float = -60.0
    gain_reduction_db: float = 0.0
    phase_correlation: float = 1.0       # +1 (pure coherence) to -1 (phase cancellation)
    thd_percent: float = 0.0             # Total Harmonic Distortion (patina/saturation)
    vca_saturated: bool = False
    dark_matter_deficits_lit: int = 0    # LED lights up when blind spots exist


class SSLMixingSession:
    """The interactive studio session where operator intent shapes the liquid metal."""

    def __init__(self, patch_channels: List[int], operator_intent: str):
        self.operator_intent = operator_intent
        self.patchbay = Patchbay()
        self.ageing_engine = SSLBoardAgeingEngine()
        self.scar_matrix = ScarFeedbackMatrix()
        self.modulator = SubstrateModulator()

        self.strips: Dict[int, ChannelPotentiometers] = {}
        self.circuits: Dict[int, ChannelCircuit] = {}
        self.meters: Dict[int, ChannelMeterBridge] = {}

        # Busses A-F routing graph (Control 2)
        self.busses: Dict[str, List[int]] = {
            "BUS_A": [],
            "BUS_B": [],
            "BUS_C": [],
            "BUS_D": [],
            "BUS_E": [],
            "BUS_F": [],
        }

        # Mount channel strips
        for ch in patch_channels:
            data = self.patchbay.get_channel(ch)
            name = data["name"] if data else f"Channel_{ch}"
            bus_id = data.get("bus_id", "BUS_A") if data else "BUS_A"
            self.strips[ch] = ChannelPotentiometers(channel_number=ch, name=name, bus_assignment=bus_id)
            self.circuits[ch] = ChannelCircuit(channel_number=ch, name=name)
            self.meters[ch] = ChannelMeterBridge(channel_number=ch)
            if bus_id in self.busses:
                self.busses[bus_id].append(ch)

        # Lifecycle token supervisor (Control 20)
        self.active_run_token: Any = None
        self.is_stopped: bool = False

    # --- TACTILE KNOB TURNING & SWITCH FLIPPING ---

    def flip_switch(self, channel_number: int, switch_name: str, state: Optional[bool] = None) -> bool:
        """Flips a switch on the channel (mute, solo, phase_invert, eq_in, dynamics_in, insert_bypass)."""
        strip = self.strips.get(channel_number)
        if not strip:
            raise ValueError(f"Channel {channel_number} not in active patch")
        if not hasattr(strip, switch_name):
            raise ValueError(f"Unknown switch: {switch_name}")
        curr = getattr(strip, switch_name)
        new_val = (not curr) if state is None else state
        setattr(strip, switch_name, new_val)
        return new_val

    def turn_knob(self, channel_number: int, knob_name: str, value: float) -> float:
        """Turns an analog potentiometer (gain, eq, hpf, threshold, fader, gate)."""
        strip = self.strips.get(channel_number)
        if not strip:
            raise ValueError(f"Channel {channel_number} not in active patch")
        if not hasattr(strip, knob_name):
            raise ValueError(f"Unknown knob: {knob_name}")
        setattr(strip, knob_name, float(value))
        return float(value)

    def ride_fader(self, channel_number: int, level_db: float) -> float:
        """Rides the physical VCA fader on a channel strip (Control 6)."""
        return self.turn_knob(channel_number, "fader_level_db", level_db)

    # --- CONTROL 1: DISCOVERY / ROUTE ---

    def resolve_route(
        self,
        query: Optional[str] = None,
        channel_number: Optional[int] = None,
        max_tier: int = 2
    ) -> Dict[str, Any]:
        """Resolves module path, callable symbol, input/output schema, and execution tier (Control 1)."""
        candidate_data = None
        if channel_number is not None:
            candidate_data = self.patchbay.get_channel(channel_number)
        elif query:
            matches = self.patchbay.search(query)
            if matches:
                candidate_data = matches[0]

        if not candidate_data:
            return {
                "status": "NO_MATCH",
                "is_executable": False,
                "reason": "No candidate found matching criteria",
                "universal_absence": False,
            }

        tier = candidate_data.get("reversibility_tier", 0)
        if tier > max_tier:
            return {
                "status": "INCOMPATIBLE",
                "is_executable": False,
                "channel_number": candidate_data["channel_number"],
                "name": candidate_data["name"],
                "execution_tier": tier,
                "max_permitted_tier": max_tier,
                "reason": f"Execution tier {tier} exceeds authorized max_tier {max_tier}",
                "universal_absence": False,
            }

        return {
            "status": "RESOLVED",
            "is_executable": True,
            "channel_number": candidate_data["channel_number"],
            "name": candidate_data["name"],
            "module_path": candidate_data["carrier_path"],
            "callable_symbol": candidate_data["entrypoint"],
            "input_schema": candidate_data.get("subject_formats", ["bytes"]),
            "output_schema": candidate_data.get("output_mold", "evidence_receipt"),
            "execution_tier": tier,
            "universal_absence": False,
        }

    # --- CONTROL 2: PATCH / BUS MEMBERSHIP ---

    def attach_to_bus(self, bus_id: str, channel_number: int) -> None:
        """Attaches channel strip to Bus A-F routing graph (Control 2)."""
        if bus_id not in self.busses:
            self.busses[bus_id] = []
        if channel_number not in self.busses[bus_id]:
            self.busses[bus_id].append(channel_number)
        if channel_number in self.strips:
            self.strips[channel_number].bus_assignment = bus_id

    def detach_from_bus(self, bus_id: str, channel_number: int) -> None:
        """Detaches channel strip from Bus A-F routing graph (Control 2)."""
        if bus_id in self.busses and channel_number in self.busses[bus_id]:
            self.busses[bus_id].remove(channel_number)

    def get_bus_channels(self, bus_id: str) -> List[int]:
        """Returns channels attached to bus."""
        return list(self.busses.get(bus_id, []))

    def route_bus_signal(self, bus_id: str, producer_output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Routes producer output to consumers attached to the specified bus (Control 2)."""
        attached = self.get_bus_channels(bus_id)
        routed = []
        for ch in attached:
            res = self.sculpt_signal(ch, producer_output)
            routed.append(res)
        return routed

    # --- CONTROL 6: FADER / PRIORITY SCHEDULING ---

    def schedule_execution(self, channels: List[int]) -> List[int]:
        """Governs scheduling weight and execution order under contention (Control 6)."""
        def fader_val(ch_num: int) -> float:
            strip = self.strips.get(ch_num)
            return strip.fader_level_db if strip else 0.0

        return sorted(channels, key=fader_val, reverse=True)

    # --- CONTROL 15: INSERT / BYPASS ---

    def add_insert_transform(
        self,
        channel_number: int,
        transform: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """Adds a callable transform to the channel's insert chain (Control 15)."""
        if channel_number in self.strips:
            self.strips[channel_number].insert_chain.append(transform)

    # --- CONTROL 20: LIFECYCLE SUPERVISOR (PAUSE / RESUME / STOP) ---

    def start_run(self, run_token: Any) -> None:
        """Binds ProcessSupervisor run token to session (Control 20)."""
        self.active_run_token = run_token
        self.is_stopped = False

    def pause_run(
        self,
        checkpoint_path: Optional[Path | str] = None,
        completed_strips: Optional[List[int]] = None,
        pending_strips: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Checkpoints session progress to disk/dict (Control 20)."""
        token_id = getattr(self.active_run_token, "token_id", "unbound_token")
        checkpoint = {
            "session_id": "ssl_session",
            "run_token_id": token_id,
            "state": "PAUSED",
            "timestamp": time.time(),
            "completed_strips": completed_strips or [],
            "pending_strips": pending_strips or [],
        }
        if checkpoint_path:
            p = Path(checkpoint_path)
            p.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
        return checkpoint

    def resume_run(
        self,
        checkpoint: Dict[str, Any],
        supervisor: Any,
        run_token: Any
    ) -> List[int]:
        """Resumes session execution, continuing only remaining strips (Control 20)."""
        if self.is_stopped:
            raise RuntimeError("Cannot resume a stopped session.")
        if supervisor and run_token:
            supervisor.validate_token(run_token)
        self.active_run_token = run_token
        return list(checkpoint.get("pending_strips", []))

    def stop_run(self, supervisor: Any, run_token: Any) -> Dict[str, Any]:
        """Cleanly aborts session execution and cancels run token (Control 20)."""
        self.is_stopped = True
        token_id = getattr(run_token, "token_id", None)
        if supervisor and token_id:
            supervisor.cancel_token(token_id)
        return {
            "status": "STOPPED",
            "cancelled_token_id": token_id,
            "timestamp": time.time(),
        }

    # --- SHAPING THE METAL THROUGH THE CONSOLE ---

    def sculpt_signal(
        self,
        channel_number: int,
        raw_signal: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Passes substrate packet through channel strip circuit.

        Applies:
        - Control 3: Preamp Ingress Trim
        - Control 7: Mute
        - Control 8: Solo
        - Control 10: Epistemic Noise Gate
        - Control 15: Insert Chain / Bypass
        - Control 18: Scar Feedback Matrix
        - Control 17: Board Ageing / Patina Isolation
        - Control 16: Meter Bridge Telemetry Recording
        """
        start_time = time.perf_counter()
        strip = self.strips[channel_number]
        circuit = self.circuits[channel_number]
        meter = self.meters[channel_number]

        # Control 7: Mute
        if strip.mute:
            if not raw_signal.get("outcome_passed", raw_signal.get("passed", True)):
                strip.failures_recorded.append(raw_signal)
            return {"_muted": True, "muted": True, "channel": channel_number}

        # Control 8: Solo
        any_solo = any(s.solo for s in self.strips.values())
        if any_solo and not strip.solo:
            return {"_solo_suppressed": True, "channel": channel_number}

        # Control 10: Noise Gate (Filters low-reliability chatter, preserves deterministic failures)
        reliability = raw_signal.get("reliability_score", raw_signal.get("confidence_score", 1.0))
        if reliability < strip.noise_gate_threshold:
            return {"_gated": True, "channel": channel_number}

        # Control 3: Preamp Ingress Trim
        circuit.ingress_trim.evaluate_payload(raw_signal)

        # 1. PREAMP STAGE
        raw_bytes = json.dumps(raw_signal, ensure_ascii=False).encode("utf-8")
        raw_len = len(raw_bytes)
        meter.measured_bytes += raw_len

        input_vu = 20.0 * math.log10(max(1e-5, raw_len / 1024.0)) + strip.preamp_trim_db
        meter.vu_input_dbfs = min(0.0, input_vu)
        circuit.condition_cycle(raw_bytes, self.operator_intent)

        # 2. FREQUENCY CROSSOVER & EQ STAGE (Control 5)
        band = circuit.route_crossover(raw_signal)
        meter.dark_matter_deficits_lit = len(circuit.unplaced_deficits)

        shaped_signal = copy.deepcopy(raw_signal)
        if strip.eq_in:
            if band == "HIGH_TRANSIENT_TOKENS" and strip.hf_gain_db != 0:
                shaped_signal["_eq_hf_boost_db"] = strip.hf_gain_db
            elif band == "MID_RANGE_LOGIC" and strip.hmf_gain_db != 0:
                shaped_signal["_eq_mid_boost_db"] = strip.hmf_gain_db
            elif band == "SUB_BASS_SCHEMA" and strip.lf_gain_db != 0:
                shaped_signal["_eq_lf_boost_db"] = strip.lf_gain_db

        # 3. PHASE DISCRIMINATOR STAGE (Control 11 & 12)
        if "static_claim" in raw_signal and "dynamic_reality" in raw_signal:
            res = compare_phase(raw_signal["static_claim"], raw_signal["dynamic_reality"])
            corr = -res.phase_correlation if strip.phase_invert else res.phase_correlation
            meter.phase_correlation = corr
            if res.status == "CONTRADICTION":
                meter.contradictions_detected += 1

        # Track failure evidence (never erased)
        if not raw_signal.get("outcome_passed", raw_signal.get("passed", True)):
            strip.failures_recorded.append(raw_signal)
            meter.failures_detected += 1

        # Control 15: Insert Chain & Bypass
        if not strip.insert_bypass:
            for transform in strip.insert_chain:
                shaped_signal = transform(shaped_signal)

        # Control 18: SCAR FEEDBACK MATRIX
        shaped_signal, adaptations = self.scar_matrix.transform_signal(shaped_signal, self.operator_intent)
        shaped_signal["safety_locked"] = True

        # Control 17: AGED SSL HARMONIC DISTORTION & TAPE SATURATION (Strictly isolated cosmetic patina)
        shaped_signal, patina = self.ageing_engine.apply_harmonic_distortion(
            channel_number,
            shaped_signal,
            signal_level_db=strip.fader_level_db,
            cosmetic_opt_in=True,
        )
        meter.thd_percent = patina.get("total_harmonic_distortion_percent", 0.0)
        meter.vca_saturated = patina.get("vca_saturation_active", False)

        # 6. VCA FADER OUTPUT
        meter.vu_output_dbfs = min(0.0, meter.vu_input_dbfs + strip.fader_level_db)
        meter.latency_ms = (time.perf_counter() - start_time) * 1000.0

        return shaped_signal

    def read_meter_bridge(self) -> Dict[str, Any]:
        """Reads full meter bridge across active channels, reporting measured metrics and synthetic flags (Control 16)."""
        out = {}
        for ch, m in self.meters.items():
            strip = self.strips[ch]
            out[f"CH_{ch:02d}_{strip.name}"] = {
                # Empirical measured metrics
                "measured_bytes": m.measured_bytes,
                "latency_ms": round(m.latency_ms, 3),
                "peak_heap_bytes": m.peak_heap_bytes,
                "failures_detected": m.failures_detected,
                "contradictions_detected": m.contradictions_detected,
                # Synthetic / analogue visual indicators (illustrative only)
                "in_vu": f"{m.vu_input_dbfs:.1f} dBFS",
                "out_vu": f"{m.vu_output_dbfs:.1f} dBFS",
                "phase_corr": f"{m.phase_correlation:+.2f}",
                "thd": f"{m.thd_percent:.1f}%",
                "saturated": m.vca_saturated,
                "deficits": m.dark_matter_deficits_lit,
                "fader": f"{strip.fader_level_db:+.1f} dB",
                "illustrative_only": True,
            }
        return out
