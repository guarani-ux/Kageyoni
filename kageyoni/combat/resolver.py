"""Fire Emblem 2RN True Hit probability resolution and Contact Split combat engine.

Implements:
- Fire Emblem 2RN (Two Random Numbers) hit system with piecewise quadratic distribution.
- Strict 1RN Critical strike evaluation (evaluated ONLY after hit connects).
- Contact Split: Somatic Contact vs Special Projective Will.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Tuple, Union
import random


def find_project_root() -> Path:
    """Locate project root directory containing data/ or kageyoni/."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "data" / "combat_rules.json").exists():
            return current
        if (current / "kageyoni").exists():
            return current
        current = current.parent
    return Path.cwd()


def load_combat_rules() -> dict[str, Any]:
    """Load combat rules from data/combat_rules.json with fallback defaults."""
    root = find_project_root()
    rules_path = root / "data" / "combat_rules.json"
    if rules_path.is_file():
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Built-in fallback reflecting data/combat_rules.json
    return {
        "two_rn_probability": {
            "enabled": True,
            "crit_uses_two_rn": False,
            "crit_multiplier": 2.5,
        },
        "contact_split": {
            "physical_somatic": {
                "base_durability_wear": 1,
                "critical_durability_wear": 3,
                "thorn_reflection_supported": True,
                "zenkai_scar_threshold_pct": 30,
            },
            "special_projective": {
                "durability_wear": 0,
                "triggers_thorns": False,
                "atmospheric_decay_lambda": 0.08,
                "elevation_advantage_pct": 15,
                "will_erosion_tick": 0.02,
            },
        },
    }


class AttackType(str, Enum):
    SOMATIC = "somatic"
    PROJECTIVE_WILL = "projective_will"


@dataclass
class Weapon:
    name: str = "Standard Katana"
    durability: int = 50
    max_durability: int = 50
    base_damage: float = 20.0

    def apply_wear(self, amount: int) -> int:
        actual_wear = min(self.durability, amount)
        self.durability = max(0, self.durability - amount)
        return actual_wear

    @property
    def is_broken(self) -> bool:
        return self.durability <= 0


@dataclass
class Combatant:
    id: str
    name: str
    hp: int = 100
    max_hp: int = 100
    stamina: int = 100
    max_stamina: int = 100
    weapon: Optional[Weapon] = None
    display_hit: int = 75
    crit_rate: int = 10
    dodge_rate: int = 5
    thorns_reflect_pct: float = 0.0
    trauma: float = 0.0
    elevation: int = 0
    will_erosion: float = 0.0
    agility: int = 10
    defense: float = 0.0

    @property
    def is_alive(self) -> bool:
        return self.hp > 0


@dataclass
class HitResult:
    hit: bool
    rolls: Tuple[int, int]
    effective_hit_rate: float
    true_hit_probability: float


@dataclass
class CombatResult:
    hit: bool
    critical: bool
    damage_dealt: float
    weapon_wear: int
    thorns_damage: float
    zenkai_triggered: bool
    will_erosion_delta: float
    hit_rolls: Tuple[int, int]
    crit_roll: Optional[int] = None
    attacker_hp_after: int = 100
    defender_hp_after: int = 100
    details: str = ""


class TrueHitResolver:
    """Fire Emblem 2RN True Hit and 1RN Critical resolver."""

    def __init__(self, rules: Optional[dict[str, Any]] = None):
        self.rules = rules or load_combat_rules()
        rn_cfg = self.rules.get("two_rn_probability", {})
        self.crit_multiplier: float = float(rn_cfg.get("crit_multiplier", 2.5))
        self.crit_uses_two_rn: bool = bool(rn_cfg.get("crit_uses_two_rn", False))
        self._lookup_table: dict[str, float] = rn_cfg.get("true_hit_lookup_table", {})

    def get_true_hit_rate(self, display_hit: Union[int, float]) -> float:
        """Returns the theoretical 2RN true hit rate for a display hit value 0..100.

        Formula:
          For H <= 50: (2 * H^2 + H) / 10000.0
          For H > 50:  1.0 - (2 * (100 - H)^2 + (100 - H)) / 10000.0
        Exact values:
          display_hit=50 -> 0.505 (50.5%)
          display_hit=25 -> 0.1275 (12.75%)
          display_hit=75 -> 0.8775 (87.75%)
        """
        if display_hit <= 0:
            return 0.0
        if display_hit >= 100:
            return 1.0

        int_key = str(round(display_hit))
        if int_key in self._lookup_table:
            return float(self._lookup_table[int_key])

        h = float(display_hit)
        if h <= 50.0:
            return (2.0 * h * h + h) / 10000.0
        else:
            diff = 100.0 - h
            return 1.0 - (2.0 * diff * diff + diff) / 10000.0

    def roll_hit(
        self,
        display_hit: Union[int, float],
        rng: Optional[random.Random] = None,
        rolls: Optional[Tuple[int, int]] = None,
    ) -> HitResult:
        """Roll 2RN to resolve whether an attack hits.

        Rolls 2 integers 0..99.
        Hit connects if (r1 + r2) / 2.0 < display_hit.
        """
        r = rng or random.Random()
        if rolls is not None:
            r1, r2 = rolls
        else:
            r1 = r.randint(0, 99)
            r2 = r.randint(0, 99)

        average_roll = (r1 + r2) / 2.0
        is_hit = (display_hit > 0) and (average_roll < display_hit)
        if display_hit >= 100:
            is_hit = True

        true_prob = self.get_true_hit_rate(display_hit)
        return HitResult(
            hit=is_hit,
            rolls=(r1, r2),
            effective_hit_rate=float(display_hit),
            true_hit_probability=true_prob,
        )

    def roll_critical(
        self,
        crit_rate: int,
        dodge_rate: int,
        hit_connected: bool,
        rng: Optional[random.Random] = None,
        crit_roll: Optional[int] = None,
    ) -> Tuple[bool, Optional[int]]:
        """Strict 1RN critical check: evaluated ONLY after hit connects.

        If hit fails, crit cannot trigger.
        Effective crit rate = max(0, crit_rate - dodge_rate).
        Rolls 1 integer 0..99. Critical triggers if roll < effective crit rate.
        """
        if not hit_connected:
            return False, None

        effective_crit = max(0, crit_rate - dodge_rate)
        if effective_crit <= 0:
            return False, None

        r = rng or random.Random()
        roll = crit_roll if crit_roll is not None else r.randint(0, 99)
        is_crit = roll < effective_crit
        return is_crit, roll

    def resolve_attack(
        self,
        attacker: Combatant,
        defender: Combatant,
        attack_type: AttackType = AttackType.SOMATIC,
        distance_tiles: int = 1,
        rng: Optional[random.Random] = None,
        hit_rolls: Optional[Tuple[int, int]] = None,
        crit_roll: Optional[int] = None,
    ) -> CombatResult:
        """Resolve full attack encounter with 2RN hit, 1RN crit, and contact split mechanics."""
        contact_cfg = self.rules.get("contact_split", {})
        somatic_cfg = contact_cfg.get("physical_somatic", {})
        proj_cfg = contact_cfg.get("special_projective", {})

        # Step 1: 2RN Hit Resolution
        hit_res = self.roll_hit(attacker.display_hit, rng=rng, rolls=hit_rolls)
        if not hit_res.hit:
            return CombatResult(
                hit=False,
                critical=False,
                damage_dealt=0.0,
                weapon_wear=0,
                thorns_damage=0.0,
                zenkai_triggered=False,
                will_erosion_delta=0.0,
                hit_rolls=hit_res.rolls,
                crit_roll=None,
                attacker_hp_after=attacker.hp,
                defender_hp_after=defender.hp,
                details="Attack missed (2RN average roll exceeded display hit).",
            )

        # Step 2: Strict 1RN Critical Evaluation
        is_crit, rolled_crit = self.roll_critical(
            attacker.crit_rate,
            defender.dodge_rate,
            hit_connected=True,
            rng=rng,
            crit_roll=crit_roll,
        )

        base_dmg = attacker.weapon.base_damage if attacker.weapon else 10.0
        crit_multiplier = self.crit_multiplier if is_crit else 1.0
        net_dmg = max(1.0, (base_dmg * crit_multiplier) - defender.defense)

        weapon_wear = 0
        thorns_damage = 0.0
        will_erosion_delta = 0.0

        # Step 3: Contact Split
        if attack_type == AttackType.SOMATIC:
            # Somatic Contact:
            # Weapon durability wear: base 1, crit 3
            base_wear = int(somatic_cfg.get("base_durability_wear", 1))
            crit_wear = int(somatic_cfg.get("critical_durability_wear", 3))
            wear_amount = crit_wear if is_crit else base_wear
            if attacker.weapon:
                weapon_wear = attacker.weapon.apply_wear(wear_amount)

            # Thorns reflection:
            if somatic_cfg.get("thorn_reflection_supported", True) and defender.thorns_reflect_pct > 0.0:
                thorns_damage = net_dmg * defender.thorns_reflect_pct
                attacker.hp = max(0, int(round(attacker.hp - thorns_damage)))

        elif attack_type == AttackType.PROJECTIVE_WILL:
            # Special projective Will:
            # Zero weapon wear
            weapon_wear = 0
            # Bypasses thorns completely
            thorns_damage = 0.0

            # Atmospheric decay: lambda (0.08) per tile of distance
            decay_lambda = float(proj_cfg.get("atmospheric_decay_lambda", 0.08))
            distance_decay = max(0.0, 1.0 - (decay_lambda * distance_tiles))
            net_dmg *= distance_decay

            # Elevation advantage (+15%)
            if attacker.elevation > defender.elevation:
                elevation_bonus = float(proj_cfg.get("elevation_advantage_pct", 15)) / 100.0
                net_dmg *= (1.0 + elevation_bonus)

            # Ticks Will erosion (+0.02)
            will_erosion_tick = float(proj_cfg.get("will_erosion_tick", 0.02))
            will_erosion_delta = will_erosion_tick
            attacker.will_erosion += will_erosion_delta

        # Step 4: Apply Damage to Defender
        damage_int = int(round(net_dmg))
        defender.hp = max(0, defender.hp - damage_int)

        # Step 5: Zenkai Scar Threshold Check
        # Triggered if damage > 75% of max HP OR trauma >= 30% (0.30)
        trauma_threshold = float(somatic_cfg.get("zenkai_scar_threshold_pct", 30)) / 100.0
        hp_damage_ratio = damage_int / max(1, defender.max_hp)
        zenkai_triggered = (hp_damage_ratio > 0.75) or (defender.trauma >= trauma_threshold)

        return CombatResult(
            hit=True,
            critical=is_crit,
            damage_dealt=net_dmg,
            weapon_wear=weapon_wear,
            thorns_damage=thorns_damage,
            zenkai_triggered=zenkai_triggered,
            will_erosion_delta=will_erosion_delta,
            hit_rolls=hit_res.rolls,
            crit_roll=rolled_crit,
            attacker_hp_after=attacker.hp,
            defender_hp_after=defender.hp,
            details=f"Attack connected (Crit={is_crit}, Dmg={damage_int}, Wear={weapon_wear}, Zenkai={zenkai_triggered}).",
        )


def calculate_true_hit(display_hit: Union[int, float]) -> float:
    """Convenience functional access to 2RN true hit rate."""
    resolver = TrueHitResolver()
    return resolver.get_true_hit_rate(display_hit)


def roll_2rn(
    display_hit: Union[int, float],
    rng: Optional[random.Random] = None,
    rolls: Optional[Tuple[int, int]] = None,
) -> HitResult:
    """Convenience functional roll for 2RN hit resolution."""
    resolver = TrueHitResolver()
    return resolver.roll_hit(display_hit, rng=rng, rolls=rolls)
