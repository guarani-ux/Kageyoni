"""Rise of Kingdoms (RoK) style Dual-Commander state machine.

Implements:
- Primary and Secondary commander tracking.
- Rage meter (0..1000 base with bounded carryover up to +200, max 1200).
- Turn T+1 execution offset for secondary skill.
- Affection tiers (Harmonic, Cooperative, Neutral, Distrust, Sovereign Veto).
- Troop count exponential scaling ((troops / 10000) ^ 0.5).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Tuple

from .resolver import load_combat_rules


class AffectionTier(str, Enum):
    HARMONIC = "harmonic"
    COOPERATIVE = "cooperative"
    NEUTRAL = "neutral"
    DISTRUST = "distrust"
    SOVEREIGN_VETO = "sovereign_veto"


def get_affection_tier(affection: int | float) -> AffectionTier:
    """Categorize an affection score into its corresponding tier."""
    if affection >= 75:
        return AffectionTier.HARMONIC
    elif affection >= 50:
        return AffectionTier.COOPERATIVE
    elif affection >= 25:
        return AffectionTier.NEUTRAL
    elif affection >= 0:
        return AffectionTier.DISTRUST
    else:
        return AffectionTier.SOVEREIGN_VETO


@dataclass
class Commander:
    name: str
    skill_name: str = "Active Tactical Art"
    base_skill_damage: float = 100.0
    affection: int = 50
    is_primary: bool = False
    troop_count: int = 10000


@dataclass
class QueuedSkill:
    commander_name: str
    skill_name: str
    base_damage: float
    scheduled_turn: int
    damage_multiplier: float
    friendly_fire_chance: float = 0.0
    friendly_fire_recoil_pct: float = 0.0


@dataclass
class SkillExecutionResult:
    caster: str
    skill_name: str
    turn_executed: int
    damage_dealt: float
    friendly_fire: bool = False
    recoil_damage: float = 0.0
    mutiny: bool = False
    details: str = ""


class DualCommanderTeam:
    """State machine governing dual-commander tactical pairing."""

    def __init__(
        self,
        primary: Commander,
        secondary: Commander,
        troop_count: int = 10000,
        rules: Optional[dict[str, Any]] = None,
    ):
        self.primary = primary
        self.primary.is_primary = True
        self.secondary = secondary
        self.secondary.is_primary = False
        self.troop_count = troop_count
        self.rules = rules or load_combat_rules()

        rok_cfg = self.rules.get("dual_commanders", {})
        self.max_rage_base: int = int(rok_cfg.get("max_rage", 1000))
        self.max_rage_carryover: int = int(rok_cfg.get("max_rage_carryover", 200))
        self.max_rage_total: int = self.max_rage_base + self.max_rage_carryover
        self.base_rage_per_turn: int = int(rok_cfg.get("base_rage_per_turn", 100))
        self.secondary_turn_offset: int = int(rok_cfg.get("secondary_turn_offset", 1))

        self.affection_configs: dict[str, Any] = rok_cfg.get("affection_tiers", {})
        self.troop_scaling_cfg: dict[str, Any] = rok_cfg.get(
            "troop_count_scaling", {"baseline_battalion": 10000, "exponent": 0.5}
        )

        self.rage: int = 0
        self.current_turn: int = 1
        self.queued_skills: List[QueuedSkill] = []

    @property
    def affection_tier(self) -> AffectionTier:
        return get_affection_tier(self.secondary.affection)

    @property
    def tier_config(self) -> dict[str, Any]:
        tier_key = self.affection_tier.value
        return self.affection_configs.get(tier_key, {})

    @property
    def is_formation_allowed(self) -> bool:
        return bool(self.tier_config.get("allowed_in_formation", True))

    @property
    def defense_bonus_pct(self) -> float:
        return float(self.tier_config.get("defense_bonus_pct", 0.0))

    def get_troop_scaling_factor(self, count: Optional[int] = None) -> float:
        troops = count if count is not None else self.troop_count
        baseline = float(self.troop_scaling_cfg.get("baseline_battalion", 10000))
        exponent = float(self.troop_scaling_cfg.get("exponent", 0.5))
        if troops <= 0 or baseline <= 0:
            return 0.0
        return math.pow(troops / baseline, exponent)

    def add_rage(self, amount: int) -> int:
        """Add rage, applying affection tier multipliers and enforcing bounded carryover (max 1200)."""
        cfg = self.tier_config
        mult = float(cfg.get("rage_generation_multiplier", 1.0))
        effective_add = int(amount * mult)

        old_rage = self.rage
        self.rage = min(self.max_rage_total, self.rage + effective_add)
        return self.rage - old_rage

    def can_cast_primary(self) -> bool:
        """Check if primary commander skill can be unleashed."""
        if not self.is_formation_allowed:
            return False
        return self.rage >= self.max_rage_base

    def cast_primary_skill(
        self,
        rng: Optional[random.Random] = None,
        override_mutiny: Optional[bool] = None,
    ) -> SkillExecutionResult:
        """Cast primary commander active skill.

        Consumes 1000 rage. Bounded overflow carryover (up to 200) is preserved.
        Harmonic tier awards a 150 rage refund.
        Schedules secondary skill for turn T + 1 + latency.
        """
        r = rng or random.Random()
        cfg = self.tier_config

        if not self.is_formation_allowed:
            return SkillExecutionResult(
                caster=self.primary.name,
                skill_name=self.primary.skill_name,
                turn_executed=self.current_turn,
                damage_dealt=0.0,
                mutiny=True,
                details="Barred from formation under Sovereign Veto.",
            )

        if self.rage < self.max_rage_base:
            raise ValueError(
                f"Insufficient rage: {self.rage}/{self.max_rage_base} required."
            )

        # Mutiny Check under Sovereign Veto (50% chance)
        mutiny_chance = float(cfg.get("mutiny_chance", 0.0))
        mutinied = False
        if mutiny_chance > 0.0:
            mutinied = (
                override_mutiny
                if override_mutiny is not None
                else (r.random() < mutiny_chance)
            )

        if mutinied:
            # Mutiny zeroes rage and aborts skill
            self.rage = 0
            return SkillExecutionResult(
                caster=self.primary.name,
                skill_name=self.primary.skill_name,
                turn_executed=self.current_turn,
                damage_dealt=0.0,
                mutiny=True,
                details="Mutiny triggered! Skill cancelled and rage drained.",
            )

        # Rage carryover calculation:
        # e.g., if rage is 1150, overflow is 150. Max carryover is 200.
        overflow_carryover = min(
            self.max_rage_carryover, max(0, self.rage - self.max_rage_base)
        )
        self.rage = overflow_carryover

        # Harmonic Rage Refund (+150)
        rage_refund = int(cfg.get("rage_refund", 0))
        if rage_refund > 0:
            self.rage = min(self.max_rage_total, self.rage + rage_refund)

        # Damage calculation for primary
        dmg_multiplier = float(cfg.get("damage_multiplier", 1.0))
        scaling = self.get_troop_scaling_factor()
        primary_damage = self.primary.base_skill_damage * dmg_multiplier * scaling

        # Schedule Secondary Commander Skill
        # T + 1 (secondary_turn_offset) + recovery_latency_turns
        latency = int(cfg.get("recovery_latency_turns", 0))
        target_turn = self.current_turn + self.secondary_turn_offset + latency

        friendly_fire_chance = float(cfg.get("friendly_fire_chance", 0.0))
        friendly_fire_recoil = float(cfg.get("friendly_fire_recoil_pct", 0.0))

        queued = QueuedSkill(
            commander_name=self.secondary.name,
            skill_name=self.secondary.skill_name,
            base_damage=self.secondary.base_skill_damage,
            scheduled_turn=target_turn,
            damage_multiplier=dmg_multiplier,
            friendly_fire_chance=friendly_fire_chance,
            friendly_fire_recoil_pct=friendly_fire_recoil,
        )
        self.queued_skills.append(queued)

        return SkillExecutionResult(
            caster=self.primary.name,
            skill_name=self.primary.skill_name,
            turn_executed=self.current_turn,
            damage_dealt=primary_damage,
            mutiny=False,
            details=f"Primary skill executed! Secondary queued for Turn {target_turn}. Remaining rage: {self.rage}.",
        )

    def tick_turn(
        self,
        rng: Optional[random.Random] = None,
        override_friendly_fire: Optional[bool] = None,
    ) -> List[SkillExecutionResult]:
        """Advance turn by 1, generate passive rage, and fire any scheduled secondary skills."""
        self.current_turn += 1
        r = rng or random.Random()

        # Passive turn rage generation
        self.add_rage(self.base_rage_per_turn)

        executed_results: List[SkillExecutionResult] = []
        still_queued: List[QueuedSkill] = []

        for q in self.queued_skills:
            if q.scheduled_turn <= self.current_turn:
                # Trigger secondary skill
                scaling = self.get_troop_scaling_factor()
                raw_dmg = q.base_damage * q.damage_multiplier * scaling

                # Friendly fire evaluation under Distrust
                ff_triggered = False
                recoil_dmg = 0.0
                if q.friendly_fire_chance > 0.0:
                    ff_triggered = (
                        override_friendly_fire
                        if override_friendly_fire is not None
                        else (r.random() < q.friendly_fire_chance)
                    )

                if ff_triggered:
                    recoil_dmg = raw_dmg * (q.friendly_fire_recoil_pct / 100.0)
                    raw_dmg *= 0.5  # reduced damage to enemy due to internal chaos
                    details = f"Secondary skill {q.skill_name} triggered friendly fire ({recoil_dmg:.1f} recoil damage)!"
                else:
                    details = f"Secondary skill {q.skill_name} executed smoothly at Turn {self.current_turn}."

                executed_results.append(
                    SkillExecutionResult(
                        caster=q.commander_name,
                        skill_name=q.skill_name,
                        turn_executed=self.current_turn,
                        damage_dealt=raw_dmg,
                        friendly_fire=ff_triggered,
                        recoil_damage=recoil_dmg,
                        mutiny=False,
                        details=details,
                    )
                )
            else:
                still_queued.append(q)

        self.queued_skills = still_queued
        return executed_results
