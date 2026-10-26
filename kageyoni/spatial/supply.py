"""Corridor Supply Engine & Attrition Logistics for Kageyōni.

Implements:
- Route integrity tracked on [0.0, 1.0] (0% to 100%).
- Contested decay: -0.15 integrity per turn when contested.
- Safe recovery: +0.25 integrity per turn when safe.
- Attrition: when integrity == 0.0, inflicts 0.05 (5%) garrison HP attrition per turn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CorridorState:
    """State of an individual military supply corridor."""
    corridor_id: str
    waypoints: List[Tuple[int, int]] = field(default_factory=list)
    integrity: float = 1.0
    is_contested: bool = False
    turns_contested: int = 0
    total_attrition_inflicted: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "corridor_id": self.corridor_id,
            "waypoints": self.waypoints,
            "integrity": self.integrity,
            "is_contested": self.is_contested,
            "turns_contested": self.turns_contested,
            "total_attrition_inflicted": self.total_attrition_inflicted,
        }


@dataclass
class CorridorTickResult:
    """Telemetry outcome of a single turn tick for a supply corridor."""
    corridor_id: str
    turn: int
    integrity: float
    integrity_delta: float
    is_contested: bool
    attrition_rate: float
    garrison_hp_loss: float
    garrison_hp_remaining: Optional[float] = None
    details: str = ""


class CorridorSupplyEngine:
    """Manages tactical supply route integrity, decay, recovery, and garrison attrition."""

    DECAY_RATE: float = 0.15
    RECOVERY_RATE: float = 0.25
    ATTRITION_RATE: float = 0.05

    def __init__(self) -> None:
        self.corridors: Dict[str, CorridorState] = {}
        self.current_turn: int = 1

    def register_corridor(
        self,
        corridor_id: str,
        waypoints: Optional[List[Tuple[int, int]]] = None,
        initial_integrity: float = 1.0,
    ) -> CorridorState:
        """Register a new military supply corridor."""
        state = CorridorState(
            corridor_id=corridor_id,
            waypoints=list(waypoints or []),
            integrity=max(0.0, min(1.0, float(initial_integrity))),
        )
        self.corridors[corridor_id] = state
        return state

    def get_integrity(self, corridor_id: str) -> float:
        """Retrieve current route integrity [0.0, 1.0]."""
        if corridor_id in self.corridors:
            return self.corridors[corridor_id].integrity
        return 0.0

    def set_contested(self, corridor_id: str, is_contested: bool) -> None:
        """Update contested status for a corridor."""
        if corridor_id in self.corridors:
            self.corridors[corridor_id].is_contested = is_contested

    def tick_turn(
        self,
        corridor_id: str,
        is_contested: Optional[bool] = None,
        garrison_hp: Optional[float] = None,
    ) -> CorridorTickResult:
        """Advance 1 turn for the corridor.

        - If contested: decays by 0.15 per turn.
        - If safe: recovers by 0.25 per turn.
        - If integrity reaches 0.0: inflicts 0.05 (5%) garrison HP attrition per turn.
        """
        if corridor_id not in self.corridors:
            self.register_corridor(corridor_id)

        corr = self.corridors[corridor_id]
        if is_contested is not None:
            corr.is_contested = is_contested

        old_integrity = corr.integrity
        integrity_delta = 0.0
        attrition_rate = 0.0
        hp_loss = 0.0
        hp_rem = garrison_hp

        if corr.is_contested:
            corr.turns_contested += 1
            corr.integrity = max(0.0, round(corr.integrity - self.DECAY_RATE, 4))
            integrity_delta = round(corr.integrity - old_integrity, 4)
            details = f"Corridor contested: integrity decayed by {self.DECAY_RATE} to {corr.integrity:.2f}."
        else:
            corr.turns_contested = 0
            corr.integrity = min(1.0, round(corr.integrity + self.RECOVERY_RATE, 4))
            integrity_delta = round(corr.integrity - old_integrity, 4)
            details = f"Corridor secure: integrity recovered by {self.RECOVERY_RATE} to {corr.integrity:.2f}."

        # Attrition check: strictly when integrity is 0.0
        if corr.integrity <= 0.0:
            attrition_rate = self.ATTRITION_RATE
            if garrison_hp is not None and garrison_hp > 0:
                hp_loss = round(garrison_hp * attrition_rate, 2)
                hp_rem = max(0.0, round(garrison_hp - hp_loss, 2))
                corr.total_attrition_inflicted += hp_loss
                details += f" Route collapsed (0.0 integrity)! Inflicted {hp_loss} garrison attrition (5%)."
            else:
                details += " Route collapsed (0.0 integrity)! Active 5% garrison attrition in effect."

        return CorridorTickResult(
            corridor_id=corridor_id,
            turn=self.current_turn,
            integrity=corr.integrity,
            integrity_delta=integrity_delta,
            is_contested=corr.is_contested,
            attrition_rate=attrition_rate,
            garrison_hp_loss=hp_loss,
            garrison_hp_remaining=hp_rem,
            details=details,
        )
