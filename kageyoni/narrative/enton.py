"""Enton Rupture Engine & Glassing Fallout for Kageyōni.

Implements:
- Rupture Barrier Threshold check:
  (ambiguity^2 + pressure^2) >= 18 + 12 * prior_ruptures
- On breach:
  - Returns rupture_triggered = True
  - Inflicts 10-turn regional glassing lockout
  - Converts tile to RUIN_VOID (elevation 0, negative cover)
  - Applies +0.15 baseline erosion
  - Increments prior_ruptures count
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class EntonRuptureResult:
    """Telemetry report of an Enton Rupture evaluation."""
    rupture_triggered: bool
    stress_value: float
    barrier_threshold: float
    prior_ruptures: int
    glassing_lockout_turns: int = 0
    tile_converted: Optional[str] = None
    target_coord: Optional[Tuple[int, int]] = None
    erosion_delta: float = 0.0
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rupture_triggered": self.rupture_triggered,
            "stress_value": self.stress_value,
            "barrier_threshold": self.barrier_threshold,
            "prior_ruptures": self.prior_ruptures,
            "glassing_lockout_turns": self.glassing_lockout_turns,
            "tile_converted": self.tile_converted,
            "target_coord": self.target_coord,
            "erosion_delta": self.erosion_delta,
            "details": self.details,
        }


class EntonRuptureEngine:
    """Governs cataclysmic Enton Rupture barriers, regional glassing, and erosion fallout."""

    BASE_BARRIER: float = 18.0
    BARRIER_SCALE_PER_RUPTURE: float = 12.0
    GLASSING_LOCKOUT_TURNS: int = 10
    EROSION_INCREMENT: float = 0.15

    def __init__(self, initial_ruptures: int = 0) -> None:
        self.prior_ruptures: int = initial_ruptures
        self.active_glassing_lockouts: Dict[Tuple[int, int], int] = {}
        self.rupture_history: List[Dict[str, Any]] = []

    def calculate_barrier_threshold(self) -> float:
        """Compute current barrier: 18 + 12 * prior_ruptures."""
        return self.BASE_BARRIER + (self.BARRIER_SCALE_PER_RUPTURE * self.prior_ruptures)

    @staticmethod
    def calculate_stress(ambiguity: float, pressure: float) -> float:
        """Compute stress = ambiguity^2 + pressure^2."""
        return round((float(ambiguity) ** 2) + (float(pressure) ** 2), 4)

    def check_rupture_possible(self, ambiguity: float, pressure: float) -> Tuple[bool, float, float]:
        """Check if stress meets or exceeds barrier threshold without mutating state."""
        stress = self.calculate_stress(ambiguity, pressure)
        threshold = self.calculate_barrier_threshold()
        return (stress >= threshold), stress, threshold

    def evaluate_rupture(
        self,
        ambiguity: float,
        pressure: float,
        target_coord: Optional[Tuple[int, int]] = None,
        world_grid: Optional[Any] = None,
    ) -> EntonRuptureResult:
        """Evaluate Enton stress and trigger cataclysmic glassing rupture if breached."""
        stress = self.calculate_stress(ambiguity, pressure)
        threshold = self.calculate_barrier_threshold()

        if stress < threshold:
            return EntonRuptureResult(
                rupture_triggered=False,
                stress_value=stress,
                barrier_threshold=threshold,
                prior_ruptures=self.prior_ruptures,
                glassing_lockout_turns=0,
                tile_converted=None,
                target_coord=target_coord,
                erosion_delta=0.0,
                details=f"Enton stress ({stress:.2f}) remained contained below threshold ({threshold:.2f}).",
            )

        # Breach triggered!
        self.prior_ruptures += 1
        coord = target_coord or (50, 50)
        self.active_glassing_lockouts[coord] = self.GLASSING_LOCKOUT_TURNS

        # If WorldGrid instance provided, mutate tile to ruin_void
        tile_name = "RUIN_VOID"
        if world_grid is not None:
            try:
                world_grid.glass_tile(coord[0], coord[1])
                tile_name = "RUIN_VOID"
            except Exception:
                pass

        self.rupture_history.append({
            "coord": coord,
            "stress": stress,
            "threshold": threshold,
            "rupture_index": self.prior_ruptures,
        })

        return EntonRuptureResult(
            rupture_triggered=True,
            stress_value=stress,
            barrier_threshold=threshold,
            prior_ruptures=self.prior_ruptures,
            glassing_lockout_turns=self.GLASSING_LOCKOUT_TURNS,
            tile_converted=tile_name,
            target_coord=coord,
            erosion_delta=self.EROSION_INCREMENT,
            details=f"ENTON RUPTURE BREACHED! Stress {stress:.2f} >= Threshold {threshold:.2f}. Tile {coord} converted to {tile_name}, 10-turn lockout applied, +0.15 baseline erosion.",
        )

    def tick_turn(self) -> Dict[Tuple[int, int], int]:
        """Advance 1 turn for active regional glassing lockouts."""
        updated: Dict[Tuple[int, int], int] = {}
        for coord, remaining in self.active_glassing_lockouts.items():
            if remaining > 1:
                updated[coord] = remaining - 1
        self.active_glassing_lockouts = updated
        return dict(self.active_glassing_lockouts)
