"""Star Ocean style Secret Talent System & Latent Friction Ledger.

Implements:
- TalentType enum: ORIGINALITY, SENSE_OF_DENSITY, RHYTHM_CADENCE, STRUCTURAL_SIGHT, SPATIAL_ACUITY.
- StarOceanTalentLedger:
  - Tracks accumulated martial friction Phi_friction per talent for each character.
  - On practice failure: accumulate_friction(character_id, talent_type, amount).
  - Breakthrough check: rolls 1d100 <= (Phi / base_threshold) * 100.
    If successful, marks talent permanently awakened.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union


class TalentType(str, Enum):
    ORIGINALITY = "ORIGINALITY"
    SENSE_OF_DENSITY = "SENSE_OF_DENSITY"
    RHYTHM_CADENCE = "RHYTHM_CADENCE"
    STRUCTURAL_SIGHT = "STRUCTURAL_SIGHT"
    SPATIAL_ACUITY = "SPATIAL_ACUITY"


@dataclass
class BreakthroughResult:
    """Result of a secret talent awakening breakthrough attempt."""
    character_id: str
    talent_type: TalentType
    awakened: bool
    already_unlocked: bool = False
    roll: float = 0.0
    target_chance: float = 0.0
    friction: float = 0.0
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "talent_type": self.talent_type.value,
            "awakened": self.awakened,
            "already_unlocked": self.already_unlocked,
            "roll": self.roll,
            "target_chance": self.target_chance,
            "friction": self.friction,
            "details": self.details,
        }


class StarOceanTalentLedger:
    """Tracks hidden martial friction and evaluates probabilistic talent breakthroughs."""

    DEFAULT_BASE_THRESHOLD: float = 100.0

    def __init__(self, base_threshold: float = DEFAULT_BASE_THRESHOLD) -> None:
        self.base_threshold = base_threshold
        self.friction_ledger: Dict[str, Dict[TalentType, float]] = {}
        self.awakened_talents: Dict[str, Set[TalentType]] = {}

    def _normalize_talent(self, talent_type: Union[TalentType, str]) -> TalentType:
        if isinstance(talent_type, TalentType):
            return talent_type
        clean = talent_type.strip().upper().replace("TALENT.", "")
        return TalentType(clean)

    def get_friction(self, character_id: str, talent_type: Union[TalentType, str]) -> float:
        """Get current accumulated friction for a character's talent."""
        tt = self._normalize_talent(talent_type)
        return self.friction_ledger.get(character_id, {}).get(tt, 0.0)

    def is_awakened(self, character_id: str, talent_type: Union[TalentType, str]) -> bool:
        """Check if character has permanently unlocked the specified talent."""
        tt = self._normalize_talent(talent_type)
        return tt in self.awakened_talents.get(character_id, set())

    def get_awakened_talents(self, character_id: str) -> Set[TalentType]:
        """Retrieve all awakened talents for a character."""
        return set(self.awakened_talents.get(character_id, set()))

    def accumulate_friction(
        self,
        character_id: str,
        talent_type: Union[TalentType, str],
        amount: float = 1.0,
    ) -> float:
        """Accumulate martial friction from practice or failure. Returns updated friction value."""
        tt = self._normalize_talent(talent_type)
        if character_id not in self.friction_ledger:
            self.friction_ledger[character_id] = {}
        current = self.friction_ledger[character_id].get(tt, 0.0)
        updated = round(current + max(0.0, float(amount)), 4)
        self.friction_ledger[character_id][tt] = updated
        return updated

    def check_breakthrough(
        self,
        character_id: str,
        talent_type: Union[TalentType, str],
        base_threshold: Optional[float] = None,
        rng_seed: Optional[int] = None,
    ) -> BreakthroughResult:
        """Evaluate breakthrough probability: roll 1d100 <= (Phi / threshold) * 100.

        If successful, marks talent permanently awakened.
        """
        tt = self._normalize_talent(talent_type)
        threshold = base_threshold if base_threshold is not None else self.base_threshold

        # If already awakened, no further check needed
        if self.is_awakened(character_id, tt):
            return BreakthroughResult(
                character_id=character_id,
                talent_type=tt,
                awakened=True,
                already_unlocked=True,
                roll=0.0,
                target_chance=100.0,
                friction=self.get_friction(character_id, tt),
                details=f"Talent '{tt.value}' is already permanently awakened for character '{character_id}'.",
            )

        friction = self.get_friction(character_id, tt)
        target_chance = min(100.0, max(0.0, (friction / max(0.001, threshold)) * 100.0))

        r = random.Random(rng_seed) if rng_seed is not None else random.Random()
        roll = r.uniform(1.0, 100.0)
        success = roll <= target_chance

        if success:
            if character_id not in self.awakened_talents:
                self.awakened_talents[character_id] = set()
            self.awakened_talents[character_id].add(tt)
            details = f"BREAKTHROUGH! Rolled {roll:.2f} <= {target_chance:.2f}%. Talent '{tt.value}' permanently awakened!"
        else:
            details = f"Breakthrough attempt failed: Rolled {roll:.2f} > {target_chance:.2f}% (Friction: {friction:.1f}/{threshold:.1f})."

        return BreakthroughResult(
            character_id=character_id,
            talent_type=tt,
            awakened=success,
            already_unlocked=False,
            roll=round(roll, 2),
            target_chance=round(target_chance, 2),
            friction=friction,
            details=details,
        )
