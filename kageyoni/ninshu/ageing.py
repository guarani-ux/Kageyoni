"""Ninshū SSL Board Ageing & Harmonic Distortion Engine (Control 17).

Enforces:
1. Historical reliability and drift tracker stored in SQLite (`channel_reliability_ledger`).
2. Cosmetic patina strictly isolated under `_cosmetic_patina` marked `illustrative_only: True`.
3. Canonical evidence is NEVER modified or corrupted by decorative wear simulations.
4. Optional simulation with explicit opt-in (`cosmetic_opt_in`).
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

CREATE TABLE IF NOT EXISTS channel_reliability_ledger (
    channel_number INTEGER PRIMARY KEY,
    total_runs INTEGER DEFAULT 0,
    success_runs INTEGER DEFAULT 0,
    failure_runs INTEGER DEFAULT 0,
    cumulative_drift_ms REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            # Seed 48 unique channel wear variations
            for ch in range(1, 49):
                drift = (math.sin(ch * 0.7) * 1.5) + 2.0
                even_w = 0.02 + (math.cos(ch * 0.5) * 0.01)
                odd_w = 0.01 + (math.sin(ch * 0.3) * 0.005)
                self.conn.execute(
                    "INSERT INTO channel_strip_wear (channel_number, heat_cycles, saturation_fatigue, capacitor_drift_ms, even_harmonic_weight, odd_harmonic_weight) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (ch, 250 + (ch * 12), ch * 0.45, drift, max(0.01, even_w), max(0.005, odd_w))
                )
            self.conn.commit()

    def record_run(
        self,
        channel_number: int,
        success: bool,
        latency_ms: float,
        drift_ms: float = 0.0
    ) -> Dict[str, Any]:
        """Records an actual empirical execution run into the SQLite reliability ledger (Control 17)."""
        succ_inc = 1 if success else 0
        fail_inc = 0 if success else 1
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO channel_reliability_ledger (channel_number, total_runs, success_runs, failure_runs, cumulative_drift_ms, last_updated)
                VALUES (?, 1, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(channel_number) DO UPDATE SET
                    total_runs = total_runs + 1,
                    success_runs = success_runs + excluded.success_runs,
                    failure_runs = failure_runs + excluded.failure_runs,
                    cumulative_drift_ms = cumulative_drift_ms + excluded.cumulative_drift_ms,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (channel_number, succ_inc, fail_inc, drift_ms)
            )
        return self.get_reliability_stats(channel_number)

    def get_reliability_stats(self, channel_number: int) -> Dict[str, Any]:
        """Retrieves verified empirical reliability statistics for a channel strip."""
        row = self.conn.execute(
            "SELECT * FROM channel_reliability_ledger WHERE channel_number=?",
            (channel_number,)
        ).fetchone()
        if not row:
            return {
                "channel_number": channel_number,
                "total_runs": 0,
                "success_runs": 0,
                "failure_runs": 0,
                "success_rate": 1.0,
                "cumulative_drift_ms": 0.0,
            }
        total = row["total_runs"]
        succ = row["success_runs"]
        fail = row["failure_runs"]
        rate = succ / total if total > 0 else 1.0
        return {
            "channel_number": channel_number,
            "total_runs": total,
            "success_runs": succ,
            "failure_runs": fail,
            "success_rate": round(rate, 4),
            "cumulative_drift_ms": round(row["cumulative_drift_ms"], 4),
        }

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
        signal_level_db: float = 0.0,
        cosmetic_opt_in: bool = True
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Applies optional analog patina simulation (Control 17).

        Invariants:
        1. If cosmetic_opt_in is False, returns signal completely untouched.
        2. If cosmetic_opt_in is True, cosmetic metadata is strictly isolated under `_cosmetic_patina`
           with `illustrative_only: True`.
        3. Canonical evidence fields (`raw_result`, digests, assertions) are NEVER modified or corrupted.
        """
        if not cosmetic_opt_in:
            return copy.deepcopy(signal), {
                "cosmetic_opt_in": False,
                "illustrative_only": True,
                "total_harmonic_distortion_percent": 0.0,
                "vca_saturation_active": False,
            }

        patina = self.get_channel_patina(channel_number)
        conditioned = copy.deepcopy(signal)

        # Calculate Drive / Saturation: how hard the channel is being hit
        input_mass = len(json.dumps(signal, ensure_ascii=False))
        overdrive_ratio = max(0.1, input_mass / 1024.0)

        even_distortion = patina.even_harmonic_weight * math.sqrt(overdrive_ratio)
        odd_distortion = patina.odd_harmonic_weight * (overdrive_ratio ** 1.5)
        total_thd = even_distortion + odd_distortion

        saturated = odd_distortion > 0.15

        # Strictly isolate cosmetic patina under non-canonical metadata tag
        cosmetic_meta = {
            "channel": channel_number,
            "illustrative_only": True,
            "even_harmonic_glue": round(even_distortion, 4),
            "odd_harmonic_saturation": round(odd_distortion, 4),
            "total_harmonic_distortion_percent": round(total_thd * 100.0, 2),
            "vca_saturation_active": saturated,
            "capacitor_drift_ms": patina.capacitor_drift_ms,
        }
        conditioned["_cosmetic_patina"] = cosmetic_meta

        # Update wear on channel
        with self.conn:
            self.conn.execute(
                "UPDATE channel_strip_wear SET saturation_fatigue = saturation_fatigue + 0.01, "
                "heat_cycles = heat_cycles + 1 WHERE channel_number=?",
                (channel_number,)
            )

        return conditioned, cosmetic_meta
