"""Ninshū SSL Board Ageing & Harmonic Distortion Engine (Analog Wear as Mechanical Law).

Emulates how a vintage SSL 4000 console physically transforms over decades of mixing:
1. Capacitor ageing & drift: Shifts transient response, softening brittle digital spikes.
2. VCA Non-Linear Saturation: Squeezes high-entropy payloads; compresses bloated signals.
3. Total Harmonic Distortion (THD):
   - 2nd Harmonic (Even / Asymmetric): Warms and glues related aspects together.
   - 3rd Harmonic (Odd / Symmetrical): Induces hard saturation when an operation is overdriven.
4. Channel Variance / Cross-Talk: Every channel strip ages uniquely, preventing monoculture
   blindspots and creating adversarial diversity across multi-track verification.
5. Board Wear Ledger: Stored in SQLite; every master print adds subtle patina to the copper.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BOARD_STATE_PATH = Path(__file__).resolve().parent / "ssl_patina.sqlite"

INIT_PATINA_SQL = """
CREATE TABLE IF NOT EXISTS console_patina (
    board_id TEXT PRIMARY KEY,
    total_master_prints INTEGER DEFAULT 0,
    total_hours_powered REAL DEFAULT 0.0,
    cumulative_thermal_cycles INTEGER DEFAULT 0,
    vca_drift_factor REAL DEFAULT 1.0,
    thd_floor_percent REAL DEFAULT 0.05,
    last_calibrated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channel_strip_wear (
    channel_number INTEGER PRIMARY KEY,
    heat_cycles INTEGER DEFAULT 0,
    saturation_fatigue REAL DEFAULT 0.0,
    capacitor_drift_ms REAL DEFAULT 0.0,
    even_harmonic_weight REAL DEFAULT 0.02,
    odd_harmonic_weight REAL DEFAULT 0.01,
    potentiometer_scratch_score REAL DEFAULT 0.0
);
"""


@dataclass
class ChannelPatina:
    """The unique analog wear profile of a specific channel strip."""
    channel_number: int
    heat_cycles: int = 0
    saturation_fatigue: float = 0.0       # Cumulative overdrive absorbed
    capacitor_drift_ms: float = 0.0       # Slew-rate slowdown (mellows digital jitter)
    even_harmonic_weight: float = 0.02    # Warmth / glue harmonic (2nd order)
    odd_harmonic_weight: float = 0.01     # Saturation / compression bite (3rd order)


class SSLBoardAgeingEngine:
    """The mechanical wear and harmonic distortion engine of the SSL 4000 console."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or BOARD_STATE_PATH
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.executescript(INIT_PATINA_SQL)
        # Ensure default board record exists
        row = self.conn.execute("SELECT 1 FROM console_patina WHERE board_id='SSL-4000-MAIN'").fetchone()
        if not row:
            self.conn.execute(
                "INSERT INTO console_patina (board_id, total_master_prints, total_hours_powered, cumulative_thermal_cycles, vca_drift_factor, thd_floor_percent) "
                "VALUES ('SSL-4000-MAIN', 1420, 87600.0, 3450, 1.042, 0.12)"
            )
            # Seed 48 unique channel wear variations (analog variance)
            for ch in range(1, 49):
                # Pseudo-random unique wear based on channel position
                drift = (math.sin(ch * 0.7) * 1.5) + 2.0
                even_w = 0.02 + (math.cos(ch * 0.5) * 0.01)
                odd_w = 0.01 + (math.sin(ch * 0.3) * 0.005)
                self.conn.execute(
                    "INSERT INTO channel_strip_wear (channel_number, heat_cycles, saturation_fatigue, capacitor_drift_ms, even_harmonic_weight, odd_harmonic_weight) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (ch, 250 + (ch * 12), ch * 0.45, drift, max(0.01, even_w), max(0.005, odd_w))
                )
            self.conn.commit()

    def get_channel_patina(self, channel_number: int) -> ChannelPatina:
        """Retrieves the physical aged component profile for a channel strip."""
        row = self.conn.execute(
            "SELECT * FROM channel_strip_wear WHERE channel_number=?", (channel_number,)
        ).fetchone()
        if not row:
            return ChannelPatina(channel_number=channel_number)
        return ChannelPatina(
            channel_number=row["channel_number"],
            heat_cycles=row["heat_cycles"],
            saturation_fatigue=row["saturation_fatigue"],
            capacitor_drift_ms=row["capacitor_drift_ms"],
            even_harmonic_weight=row["even_harmonic_weight"],
            odd_harmonic_weight=row["odd_harmonic_weight"]
        )

    def apply_harmonic_distortion(
        self,
        channel_number: int,
        signal: Dict[str, Any],
        signal_level_db: float = 0.0
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Mechanically enforces analog board wear:
        1. If signal is pushed too hot (drive > 0 dB), the 3rd harmonic kicks in,
           saturating and clamping verbose payload bloat.
        2. The 2nd harmonic glues metadata together, creating semantic warmth.
        3. Capacitor drift applies micro-damping to prevent digital edge clipping.
        """
        patina = self.get_channel_patina(channel_number)
        conditioned = copy.deepcopy(signal)

        # Calculate Drive / Saturation: how hard the channel is being hit
        input_mass = len(json.dumps(signal))
        # Normalize mass against reference baseline (1KB = 0dB drive)
        overdrive_ratio = max(0.1, input_mass / 1024.0)

        # 2nd Harmonic (Asymmetric Glue): Proportional to signal coherence
        even_distortion = patina.even_harmonic_weight * math.sqrt(overdrive_ratio)
        
        # 3rd Harmonic (Symmetric Saturation Bite): Penalizes bloat exponentially
        odd_distortion = patina.odd_harmonic_weight * (overdrive_ratio ** 1.5)

        total_thd = even_distortion + odd_distortion

        # Mechanical Enforcement via THD:
        # If odd harmonic distortion exceeds threshold (> 0.25), trigger soft-knee saturation
        saturated = False
        if odd_distortion > 0.15:
            saturated = True
            # Saturation compresses bloated string payloads into dense deterministic tokens
            if "raw_result" in conditioned and isinstance(conditioned["raw_result"], str) and len(conditioned["raw_result"]) > 500:
                truncated = conditioned["raw_result"][:400]
                conditioned["raw_result"] = f"{truncated}... [VCA_TAPE_SATURATION_CLAMPED]"

        conditioned["_analog_patina"] = {
            "channel": channel_number,
            "even_harmonic_glue": round(even_distortion, 4),
            "odd_harmonic_saturation": round(odd_distortion, 4),
            "total_harmonic_distortion_percent": round(total_thd * 100.0, 2),
            "vca_saturation_active": saturated,
            "capacitor_drift_ms": patina.capacitor_drift_ms
        }

        # Update wear on channel
        self.conn.execute(
            "UPDATE channel_strip_wear SET saturation_fatigue = saturation_fatigue + 0.01, "
            "heat_cycles = heat_cycles + 1 WHERE channel_number=?",
            (channel_number,)
        )
        self.conn.commit()

        return conditioned, conditioned["_analog_patina"]
