"""Ninshū SSL Active Session Mixing & Knob Shaper.

Provides the interactive engineering tactile surface:
- Flipping Switches (Mute, Solo, Phase Invert, EQ In, Insert Bypass)
- Turning Knobs (Preamp Gain, HPF Cutoff, 4-Band Parametric EQ, VCA Threshold/Ratio)
- Riding Faders (Channel volume & Bus Trim)
- Reading Meters (VU Levels, THD Saturation, Phase Correlation, Deficit Sockets)
All actively shaping the streaming liquid metal in real-time, aligned with Operator Intent.
"""
from __future__ import annotations

import copy
import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ageing import SSLBoardAgeingEngine
from .circuits import ChannelCircuit, WaveformMetric
from .patchbay import Patchbay
from .scars import ScarFeedbackMatrix


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


@dataclass
class ChannelMeterBridge:
    """Real-time LED / VU Meter readouts above the channel strip."""
    channel_number: int
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
        
        self.strips: Dict[int, ChannelPotentiometers] = {}
        self.circuits: Dict[int, ChannelCircuit] = {}
        self.meters: Dict[int, ChannelMeterBridge] = {}

        # Mount channel strips
        for ch in patch_channels:
            data = self.patchbay.get_channel(ch)
            name = data["name"] if data else f"Channel_{ch}"
            self.strips[ch] = ChannelPotentiometers(channel_number=ch, name=name)
            self.circuits[ch] = ChannelCircuit(channel_number=ch, name=name)
            self.meters[ch] = ChannelMeterBridge(channel_number=ch)

    # --- TACTILE KNOB TURNING & SWITCH FLIPPING ---

    def flip_switch(self, channel_number: int, switch_name: str, state: Optional[bool] = None) -> bool:
        """Flips a switch on the channel (mute, solo, phase_invert, eq_in, dynamics_in)."""
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
        """Turns an analog potentiometer (gain, eq, hpf, threshold, fader)."""
        strip = self.strips.get(channel_number)
        if not strip:
            raise ValueError(f"Channel {channel_number} not in active patch")
        if not hasattr(strip, knob_name):
            raise ValueError(f"Unknown knob: {knob_name}")
        setattr(strip, knob_name, float(value))
        return float(value)

    def ride_fader(self, channel_number: int, level_db: float) -> float:
        """Rides the physical VCA fader on a channel strip."""
        return self.turn_knob(channel_number, "fader_level_db", level_db)

    # --- SHAPING THE METAL THROUGH THE CONSOLE ---

    def sculpt_signal(
        self,
        channel_number: int,
        raw_signal: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Passes a packet of liquid metal through the active physical circuit:
        Preamp -> HPF/LPF -> 4-Band EQ -> VCA Compressor -> Noise Gate -> Scars -> THD Ageing -> Fader.
        """
        strip = self.strips[channel_number]
        circuit = self.circuits[channel_number]
        meter = self.meters[channel_number]

        if strip.mute:
            return {"_muted": True, "channel": channel_number}

        # 1. PREAMP STAGE
        raw_bytes = json.dumps(raw_signal).encode("utf-8")
        raw_len = len(raw_bytes)
        # Meter input VU
        input_vu = 20.0 * math.log10(max(1e-5, raw_len / 1024.0)) + strip.preamp_trim_db
        meter.vu_input_dbfs = min(0.0, input_vu)
        circuit.condition_cycle(raw_bytes, self.operator_intent)

        # 2. FREQUENCY CROSSOVER & EQ STAGE
        band = circuit.route_crossover(raw_signal)
        meter.dark_matter_deficits_lit = len(circuit.unplaced_deficits)

        shaped_signal = copy.deepcopy(raw_signal)
        if strip.eq_in:
            # Apply 4-Band gain adjustments to signal weight
            if band == "HIGH_TRANSIENT_TOKENS" and strip.hf_gain_db != 0:
                shaped_signal["_eq_hf_boost_db"] = strip.hf_gain_db
            elif band == "MID_RANGE_LOGIC" and strip.hmf_gain_db != 0:
                shaped_signal["_eq_mid_boost_db"] = strip.hmf_gain_db
            elif band == "SUB_BASS_SCHEMA" and strip.lf_gain_db != 0:
                shaped_signal["_eq_lf_boost_db"] = strip.lf_gain_db

        # 3. PHASE DISCRIMINATOR STAGE
        if "static_claim" in raw_signal and "dynamic_reality" in raw_signal:
            wf = circuit.discriminate_phase(raw_signal["static_claim"], raw_signal["dynamic_reality"])
            corr = -wf.phase_correlation if strip.phase_invert else wf.phase_correlation
            meter.phase_correlation = corr

        # 4. SCAR FEEDBACK MATRIX (Zenkai Shaping)
        shaped_signal, adaptations = self.scar_matrix.transform_signal(shaped_signal, self.operator_intent)

        # 5. AGED SSL HARMONIC DISTORTION & TAPE SATURATION
        shaped_signal, patina = self.ageing_engine.apply_harmonic_distortion(
            channel_number,
            shaped_signal,
            signal_level_db=strip.fader_level_db
        )
        meter.thd_percent = patina["total_harmonic_distortion_percent"]
        meter.vca_saturated = patina["vca_saturation_active"]

        # 6. VCA FADER OUTPUT
        meter.vu_output_dbfs = min(0.0, meter.vu_input_dbfs + strip.fader_level_db)

        return shaped_signal

    def read_meter_bridge(self) -> Dict[str, Any]:
        """Reads the full meter bridge across all active channels."""
        out = {}
        for ch, m in self.meters.items():
            strip = self.strips[ch]
            out[f"CH_{ch:02d}_{strip.name}"] = {
                "in_vu": f"{m.vu_input_dbfs:.1f} dBFS",
                "out_vu": f"{m.vu_output_dbfs:.1f} dBFS",
                "phase_corr": f"{m.phase_correlation:+.2f}",
                "thd": f"{m.thd_percent:.1f}%",
                "saturated": m.vca_saturated,
                "deficits": m.dark_matter_deficits_lit,
                "fader": f"{strip.fader_level_db:+.1f} dB"
            }
        return out
