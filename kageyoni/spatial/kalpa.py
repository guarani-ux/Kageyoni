"""Kalpa Revision Engine & Samsara Molt Lifecycle for Kageyōni.

Implements:
- Tracks conquered continental tiles out of 10,000 total ([0, 99] x [0, 99]).
- Unseal thresholds:
  - Pass 2 unseals at 5,000 tiles (50.0% continental conquest).
  - Pass 3 unseals at 8,000 tiles (80.0% continental conquest).
  - Kalpa Revision triggers at 10,000 tiles (100.0%), returning molt_triggered=True.
- Persistence across revisions:
  - Subterranean scars and memory ledgers strictly persist across Kalpa revisions,
    while surface tile conquest resets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class KalpaStatus:
    """Current status of continental conquest and milestone thresholds."""
    total_tiles: int
    conquered_count: int
    conquest_percentage: float
    pass_2_unsealed: bool
    pass_3_unsealed: bool
    molt_triggered: bool
    kalpa_cycle: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tiles": self.total_tiles,
            "conquered_count": self.conquered_count,
            "conquest_percentage": self.conquest_percentage,
            "pass_2_unsealed": self.pass_2_unsealed,
            "pass_3_unsealed": self.pass_3_unsealed,
            "molt_triggered": self.molt_triggered,
            "kalpa_cycle": self.kalpa_cycle,
        }


@dataclass
class KalpaRevisionReport:
    """Telemetry summary produced upon Kalpa Revision (molt cycle)."""
    cycle_completed: int
    new_cycle: int
    molt_triggered: bool
    scars_persisted: int
    memories_persisted: int
    details: str = ""


class KalpaRevisionEngine:
    """Governs macro continental progression, pass unsealing, and Kalpa revision molts."""

    TOTAL_TILES: int = 10000
    PASS_2_THRESHOLD: int = 5000   # 50%
    PASS_3_THRESHOLD: int = 8000   # 80%
    MOLT_THRESHOLD: int = 10000    # 100%

    def __init__(self, total_tiles: int = TOTAL_TILES) -> None:
        self.total_tiles = total_tiles
        self.conquered_tiles: Set[Tuple[int, int]] = set()
        self.kalpa_cycle: int = 1

        # Persistent across revisions
        self.subterranean_scars: List[Dict[str, Any]] = []
        self.memory_ledger: List[Dict[str, Any]] = []

    @property
    def conquered_count(self) -> int:
        return len(self.conquered_tiles)

    @property
    def conquest_percentage(self) -> float:
        if self.total_tiles <= 0:
            return 0.0
        return round((len(self.conquered_tiles) / self.total_tiles) * 100.0, 2)

    @property
    def is_pass_2_unsealed(self) -> bool:
        return self.conquered_count >= self.PASS_2_THRESHOLD

    @property
    def is_pass_3_unsealed(self) -> bool:
        return self.conquered_count >= self.PASS_3_THRESHOLD

    @property
    def is_molt_ready(self) -> bool:
        return self.conquered_count >= self.MOLT_THRESHOLD

    def conquer_tile(self, x: int, y: int) -> KalpaStatus:
        """Mark a single tile as conquered and evaluate thresholds."""
        if 0 <= x < 100 and 0 <= y < 100:
            self.conquered_tiles.add((x, y))
        return self.get_status()

    def conquer_n_tiles(self, count: int) -> KalpaStatus:
        """Batch conquer n arbitrary unmapped tiles for progression testing."""
        target = min(self.total_tiles, self.conquered_count + max(0, count))
        idx = 0
        while len(self.conquered_tiles) < target and idx < self.total_tiles:
            x = idx % 100
            y = idx // 100
            self.conquered_tiles.add((x, y))
            idx += 1
        return self.get_status()

    def record_subterranean_scar(self, scar_id: str, origin_tile: Tuple[int, int], details: str = "") -> None:
        """Record a permanent subterranean scar that persists across Kalpas."""
        self.subterranean_scars.append({
            "scar_id": scar_id,
            "origin_tile": origin_tile,
            "cycle_recorded": self.kalpa_cycle,
            "details": details,
        })

    def record_memory(self, memory_id: str, text: str, affinity: str = "neutral") -> None:
        """Record a persistent memory ledger entry that survives Kalpa revision."""
        self.memory_ledger.append({
            "memory_id": memory_id,
            "text": text,
            "affinity": affinity,
            "cycle_recorded": self.kalpa_cycle,
        })

    def get_status(self) -> KalpaStatus:
        """Retrieve current continental conquest status."""
        return KalpaStatus(
            total_tiles=self.total_tiles,
            conquered_count=self.conquered_count,
            conquest_percentage=self.conquest_percentage,
            pass_2_unsealed=self.is_pass_2_unsealed,
            pass_3_unsealed=self.is_pass_3_unsealed,
            molt_triggered=self.is_molt_ready,
            kalpa_cycle=self.kalpa_cycle,
        )

    def trigger_kalpa_revision(self) -> KalpaRevisionReport:
        """Trigger Samsara Molt Kalpa Revision.

        Resets surface conquest back to 0, increments kalpa cycle,
        while subterranean scars and memory ledgers persist untouched.
        """
        old_cycle = self.kalpa_cycle
        self.kalpa_cycle += 1
        self.conquered_tiles.clear()

        return KalpaRevisionReport(
            cycle_completed=old_cycle,
            new_cycle=self.kalpa_cycle,
            molt_triggered=True,
            scars_persisted=len(self.subterranean_scars),
            memories_persisted=len(self.memory_ledger),
            details=f"Kalpa Revision completed: Cycle {old_cycle} -> Cycle {self.kalpa_cycle}. Surface conquest cleared. {len(self.subterranean_scars)} scars and {len(self.memory_ledger)} memories preserved.",
        )
