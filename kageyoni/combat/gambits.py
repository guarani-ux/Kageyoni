"""Pre-Cognitive Clash Gambits (Active Defense Engine).

Implements turn-based tactical reaction choices against incoming enemy vectors:
- VAJRA_READ: 0 stamina cost. Pure prediction read.
  - Success (predicted == incoming): 100% damage negation, 50% damage reflection, +150 rage.
  - Failure (predicted != incoming): incoming damage * 1.25, -10 stamina penalty.
- ROLL_AND_COUNTER: 15 stamina cost. Agility check (1d20 + agility >= 10).
  - Success: 100% damage negation, +20% critical counter bonus.
  - Failure: 50% damage reduction.
- BRACE_SHIELD: 30 stamina cost. Guaranteed 50% damage reduction.
  - If remaining stamina < 0: triggers exhaustion stun.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union


class GambitType(str, Enum):
    VAJRA_READ = "VAJRA_READ"
    ROLL_AND_COUNTER = "ROLL_AND_COUNTER"
    BRACE_SHIELD = "BRACE_SHIELD"


@dataclass
class GambitResult:
    """Outcome of resolving an active pre-cognitive clash gambit."""
    gambit_type: GambitType
    success: bool
    damage_taken: float
    damage_reflected: float
    rage_delta: int
    stamina_delta: int
    stamina_remaining: int
    exhaustion_stun: bool
    crit_counter_bonus: float
    d20_roll: Optional[int] = None
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "gambit_type": self.gambit_type.value,
            "success": self.success,
            "damage_taken": self.damage_taken,
            "damage_reflected": self.damage_reflected,
            "rage_delta": self.rage_delta,
            "stamina_delta": self.stamina_delta,
            "stamina_remaining": self.stamina_remaining,
            "exhaustion_stun": self.exhaustion_stun,
            "crit_counter_bonus": self.crit_counter_bonus,
            "d20_roll": self.d20_roll,
            "details": self.details,
        }


class PreCognitiveGambitEngine:
    """Resolves active defense reactions against incoming martial vectors."""

    @staticmethod
    def resolve_gambit(
        gambit_type: Union[GambitType, str],
        incoming_damage: float,
        incoming_vector: str,
        predicted_vector: str = "",
        user_agility: int = 10,
        user_stamina: int = 100,
        seed: Optional[int] = None,
    ) -> GambitResult:
        """Resolve an active defensive gambit against an incoming attack."""
        if isinstance(gambit_type, str):
            gambit_type = GambitType(gambit_type.upper())

        r = random.Random(seed) if seed is not None else random.Random()
        inc_dmg = float(incoming_damage)

        if gambit_type == GambitType.VAJRA_READ:
            # Stamina cost 0
            is_match = (
                predicted_vector.strip().lower() == incoming_vector.strip().lower()
                and bool(predicted_vector.strip())
            )
            if is_match:
                # 100% negate, 50% reflect, +150 rage gain
                return GambitResult(
                    gambit_type=gambit_type,
                    success=True,
                    damage_taken=0.0,
                    damage_reflected=round(inc_dmg * 0.5, 2),
                    rage_delta=150,
                    stamina_delta=0,
                    stamina_remaining=user_stamina,
                    exhaustion_stun=False,
                    crit_counter_bonus=0.0,
                    details=f"Vajra Read perfectly predicted '{incoming_vector}'! 100% negated, {round(inc_dmg * 0.5, 2)} reflected, +150 rage.",
                )
            else:
                # Failure: incoming damage * 1.25, -10 stamina penalty
                dmg_taken = round(inc_dmg * 1.25, 2)
                stamina_rem = user_stamina - 10
                return GambitResult(
                    gambit_type=gambit_type,
                    success=False,
                    damage_taken=dmg_taken,
                    damage_reflected=0.0,
                    rage_delta=0,
                    stamina_delta=-10,
                    stamina_remaining=stamina_rem,
                    exhaustion_stun=stamina_rem < 0,
                    crit_counter_bonus=0.0,
                    details=f"Vajra Read misread '{incoming_vector}' (predicted '{predicted_vector}'). Took amplified damage ({dmg_taken}) and -10 stamina.",
                )

        elif gambit_type == GambitType.ROLL_AND_COUNTER:
            # Stamina cost 15
            stamina_cost = 15
            stamina_rem = user_stamina - stamina_cost
            roll_d20 = r.randint(1, 20)
            total_check = roll_d20 + user_agility
            success = total_check >= 10

            if success:
                # 100% negate, +20% critical counter bonus
                return GambitResult(
                    gambit_type=gambit_type,
                    success=True,
                    damage_taken=0.0,
                    damage_reflected=0.0,
                    rage_delta=0,
                    stamina_delta=-stamina_cost,
                    stamina_remaining=stamina_rem,
                    exhaustion_stun=stamina_rem < 0,
                    crit_counter_bonus=0.20,
                    d20_roll=roll_d20,
                    details=f"Roll and Counter succeeded (1d20={roll_d20} + agi={user_agility} = {total_check} >= 10). Attack evaded with +20% crit counter bonus.",
                )
            else:
                # Failure: 50% damage reduction
                dmg_taken = round(inc_dmg * 0.5, 2)
                return GambitResult(
                    gambit_type=gambit_type,
                    success=False,
                    damage_taken=dmg_taken,
                    damage_reflected=0.0,
                    rage_delta=0,
                    stamina_delta=-stamina_cost,
                    stamina_remaining=stamina_rem,
                    exhaustion_stun=stamina_rem < 0,
                    crit_counter_bonus=0.0,
                    d20_roll=roll_d20,
                    details=f"Roll and Counter check failed (1d20={roll_d20} + agi={user_agility} = {total_check} < 10). Partial dodge reduced damage to {dmg_taken}.",
                )

        elif gambit_type == GambitType.BRACE_SHIELD:
            # Stamina cost 30. Guaranteed 50% reduction.
            stamina_cost = 30
            stamina_rem = user_stamina - stamina_cost
            exhaustion = stamina_rem < 0
            dmg_taken = round(inc_dmg * 0.5, 2)

            return GambitResult(
                gambit_type=gambit_type,
                success=True,
                damage_taken=dmg_taken,
                damage_reflected=0.0,
                rage_delta=0,
                stamina_delta=-stamina_cost,
                stamina_remaining=stamina_rem,
                exhaustion_stun=exhaustion,
                crit_counter_bonus=0.0,
                details=f"Brace Shield absorbed 50% damage (took {dmg_taken})."
                + (" Exhaustion stun triggered from depleted stamina!" if exhaustion else ""),
            )

        raise ValueError(f"Unknown GambitType: {gambit_type}")
