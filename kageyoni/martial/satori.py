"""Satori Epiphany Engine (Crisis-Driven Technique Mutation).

Implements:
- Combat Danger Density formula:
  D_combat = [(P_danger * U_unresolved) / (R_stamina + 0.001)] * friction
- Satori threshold check (default Theta_satori = 1.5).
- Single-slot technique mutation (stance, vector, infusion, or intent).
- Strict rate-limiter: maximum 1 epiphany allowed per encounter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class SatoriResult:
    """Result of evaluating a potential Satori Epiphany during crisis."""
    triggered: bool
    danger_density: float
    threshold: float
    slot_mutated: Optional[str] = None
    original_primitive: Optional[str] = None
    mutated_primitive: Optional[str] = None
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triggered": self.triggered,
            "danger_density": self.danger_density,
            "threshold": self.threshold,
            "slot_mutated": self.slot_mutated,
            "original_primitive": self.original_primitive,
            "mutated_primitive": self.mutated_primitive,
            "details": self.details,
        }


class SatoriEpiphanyEngine:
    """Evaluates crisis states and triggers single-slot martial technique mutations."""

    DEFAULT_THRESHOLD: float = 1.5

    # Suggested progressive mutations for primitives
    MUTATION_UPGRADES: Dict[str, str] = {
        # Stances
        "stance.golden_lotus": "stance.flowing_willow",
        "stance.flowing_willow": "stance.void_stalker",
        "stance.mountain_root": "stance.adamantine_bastion",
        # Vectors
        "vector.linear_cleave": "vector.spiral_pierce",
        "vector.spiral_pierce": "vector.spatial_fold",
        "vector.sweeping_arc": "vector.falling_meteor",
        # Infusions
        "infusion.structure_resonance": "infusion.seismic_core",
        "infusion.seismic_core": "infusion.plasma_vent",
        "infusion.mist_veil": "infusion.void_silence",
        # Intents
        "intent.reaction_inversion": "intent.counter_reversal",
        "intent.unyielding_bastion": "intent.gaia_balance_recoil",
        "intent.executioner_verdict": "intent.memory_burn_ignition",
    }

    def __init__(self, threshold: float = DEFAULT_THRESHOLD) -> None:
        self.threshold: float = threshold
        self.has_triggered_this_encounter: bool = False

    def reset_encounter(self) -> None:
        """Reset the rate-limiter flag for a new combat encounter."""
        self.has_triggered_this_encounter = False

    @staticmethod
    def calculate_danger_density(
        danger: float,
        unresolved: float,
        stamina: float,
        friction: float = 1.0,
    ) -> float:
        """Compute D_combat = [(P_danger * U_unresolved) / (R_stamina + 0.001)] * friction."""
        p_danger = max(0.0, float(danger))
        u_unresolved = max(0.0, float(unresolved))
        r_stamina = max(0.0, float(stamina))
        f_friction = max(0.0, float(friction))

        raw_density = ((p_danger * u_unresolved) / (r_stamina + 0.001)) * f_friction
        return round(raw_density, 4)

    def evaluate_epiphany(
        self,
        danger: float,
        unresolved: float,
        stamina: float,
        friction: float = 1.0,
        current_stance: Optional[str] = None,
        current_vector: Optional[str] = None,
        current_infusion: Optional[str] = None,
        current_intent: Optional[str] = None,
        target_slot: Optional[str] = None,
    ) -> SatoriResult:
        """Evaluate if current crisis state triggers a Satori Epiphany mutation.

        Enforces strictly maximum 1 epiphany per encounter.
        """
        density = self.calculate_danger_density(danger, unresolved, stamina, friction)

        if self.has_triggered_this_encounter:
            return SatoriResult(
                triggered=False,
                danger_density=density,
                threshold=self.threshold,
                details="Epiphany rate-limit reached: Strictly maximum 1 Satori epiphany allowed per encounter.",
            )

        if density < self.threshold:
            return SatoriResult(
                triggered=False,
                danger_density=density,
                threshold=self.threshold,
                details=f"Danger density ({density:.4f}) did not meet Satori threshold ({self.threshold:.4f}).",
            )

        # Epiphany triggered!
        self.has_triggered_this_encounter = True

        # Determine which slot to mutate
        slots = {
            "stance": current_stance or "stance.golden_lotus",
            "vector": current_vector or "vector.linear_cleave",
            "infusion": current_infusion or "infusion.structure_resonance",
            "intent": current_intent or "intent.reaction_inversion",
        }

        chosen_slot = target_slot if target_slot in slots else "intent"
        original_primitive = slots[chosen_slot]
        mutated_primitive = self.MUTATION_UPGRADES.get(
            original_primitive,
            f"{original_primitive}_awakened"
        )

        return SatoriResult(
            triggered=True,
            danger_density=density,
            threshold=self.threshold,
            slot_mutated=chosen_slot,
            original_primitive=original_primitive,
            mutated_primitive=mutated_primitive,
            details=f"SATORI EPIPHANY! Danger density {density:.4f} >= {self.threshold:.4f}. Mutated slot '{chosen_slot}' from '{original_primitive}' to '{mutated_primitive}'.",
        )
