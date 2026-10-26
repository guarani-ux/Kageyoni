"""
Attuned Kata Deck Manager & Kata Forge for Kageyōni.

Enforces loadout constraints:
    - Exactly 3 to 4 compiled Katas
    - Exactly 1 Basic Strike
    - Exactly 1 Guard
    Total active skills = 5 or 6 (3-4 Katas + Basic Strike + Guard).

Equipping and unequipping are strictly restricted to the Camp phase (Kata Forge).
Calculates HUD preview metrics for equipped decks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from kageyoni.martial.compiler import (
    CompiledTechnique,
    MartialGrammar,
    TechniqueCompiler,
)


class DeckLoadoutError(Exception):
    """Raised when an attuned kata deck violates loadout constraints."""


class DeckModificationLockedError(DeckLoadoutError):
    """Raised when attempting to modify a deck outside the Camp phase."""


@dataclass
class DeckPreviewMetrics:
    """Summary metrics of an equipped Kata deck for HUD preview."""

    character_id: str
    total_techniques: int
    kata_count: int
    average_stamina_cost: float
    min_stamina_cost: float
    max_stamina_cost: float
    total_stamina_rotation: float
    average_recovery_frames: float
    min_recovery_frames: int
    max_recovery_frames: int
    total_erosion_risk: float
    max_backlash_risk: float
    reach_envelope: Tuple[float, float]
    stances_used: List[str]
    vectors_used: List[str]
    infusions_used: List[str]
    intents_used: List[str]

    def format_hud_display(self) -> str:
        """Renders an ASCII HUD dashboard preview for the equipped deck."""
        min_reach, max_reach = self.reach_envelope
        lines = [
            f"╔══ [ATTUNED KATA DECK HUD: {self.character_id}] ══════════════════════╗",
            f"║ Loadout: {self.kata_count} Katas + 1 Basic + 1 Guard ({self.total_techniques} Total Actions)",
            f"║ Stamina Cost : Avg {self.average_stamina_cost:>5.1f} | Min {self.min_stamina_cost:>4.1f} | Max {self.max_stamina_cost:>4.1f} | Full Rotation: {self.total_stamina_rotation:>5.1f}",
            f"║ Recovery Lag : Avg {self.average_recovery_frames:>5.1f}f | Min {self.min_recovery_frames:>2}f | Max {self.max_recovery_frames:>2}f",
            f"║ Reach Window : [{min_reach:.1f}m - {max_reach:.1f}m] | Max Backlash: {self.max_backlash_risk:>5.1f}",
            f"║ Erosion Risk : {self.total_erosion_risk:.3f} Cumulative Ticks",
            f"║ Stances In Deck : {', '.join(self.stances_used)}",
            f"║ Vectors In Deck : {', '.join(self.vectors_used)}",
            "╚══════════════════════════════════════════════════════════════════════╝",
        ]
        return "\n".join(lines)


class AttunedDeck:
    """
    Attuned Kata Deck for a character.
    Enforces the strict rule: 3 to 4 compiled Katas + 1 Basic Strike + 1 Guard.
    """

    MIN_KATAS = 3
    MAX_KATAS = 4

    def __init__(
        self,
        character_id: str,
        in_camp_phase: bool = True,
        katas: Optional[Dict[int, CompiledTechnique]] = None,
        basic_strike: Optional[CompiledTechnique] = None,
        guard: Optional[CompiledTechnique] = None,
    ) -> None:
        self.character_id = character_id
        self._in_camp_phase = in_camp_phase
        self._katas: Dict[int, CompiledTechnique] = {}
        self._basic_strike: Optional[CompiledTechnique] = basic_strike
        self._guard: Optional[CompiledTechnique] = guard

        if katas:
            for slot, tech in katas.items():
                if 1 <= slot <= self.MAX_KATAS:
                    self._katas[slot] = tech

    @property
    def in_camp_phase(self) -> bool:
        return self._in_camp_phase

    @property
    def katas(self) -> Dict[int, CompiledTechnique]:
        return dict(self._katas)

    @property
    def basic_strike(self) -> Optional[CompiledTechnique]:
        return self._basic_strike

    @property
    def guard(self) -> Optional[CompiledTechnique]:
        return self._guard

    def enter_camp_phase(self) -> None:
        """Enables Kata Forge modifications."""
        self._in_camp_phase = True

    def exit_camp_phase(self) -> None:
        """Locks deck loadout for combat encounter."""
        self.validate_loadout()
        self._in_camp_phase = False

    def equip_kata(self, slot_index: int, technique: CompiledTechnique) -> None:
        """Equip a compiled technique into one of the 4 Kata slots."""
        if not self._in_camp_phase:
            raise DeckModificationLockedError(
                f"Cannot equip Kata into slot {slot_index}: Deck modifications are locked outside Camp phase."
            )
        if slot_index < 1 or slot_index > self.MAX_KATAS:
            raise DeckLoadoutError(
                f"Invalid Kata slot index {slot_index}. Katas must be equipped into slots 1 through {self.MAX_KATAS}."
            )
        self._katas[slot_index] = technique

    def unequip_kata(self, slot_index: int) -> Optional[CompiledTechnique]:
        """Unequip a compiled technique from a Kata slot."""
        if not self._in_camp_phase:
            raise DeckModificationLockedError(
                f"Cannot unequip Kata from slot {slot_index}: Deck modifications are locked outside Camp phase."
            )
        return self._katas.pop(slot_index, None)

    def set_basic_strike(self, technique: CompiledTechnique) -> None:
        """Set the designated Basic Strike for the deck."""
        if not self._in_camp_phase:
            raise DeckModificationLockedError(
                "Cannot modify Basic Strike: Deck modifications are locked outside Camp phase."
            )
        self._basic_strike = technique

    def set_guard(self, technique: CompiledTechnique) -> None:
        """Set the designated Guard action for the deck."""
        if not self._in_camp_phase:
            raise DeckModificationLockedError(
                "Cannot modify Guard: Deck modifications are locked outside Camp phase."
            )
        self._guard = technique

    def get_all_active_techniques(self) -> List[CompiledTechnique]:
        """Returns the full list of active techniques in the deck."""
        actions: List[CompiledTechnique] = []
        # Katas in sorted slot order
        for slot in sorted(self._katas.keys()):
            actions.append(self._katas[slot])
        if self._basic_strike is not None:
            actions.append(self._basic_strike)
        if self._guard is not None:
            actions.append(self._guard)
        return actions

    def validate_loadout(self) -> Tuple[bool, List[str]]:
        """
        Validates deck against strict loadout constraints:
        - 3 to 4 compiled Katas
        - Exactly 1 Basic Strike
        - Exactly 1 Guard
        """
        errors: List[str] = []
        num_katas = len(self._katas)

        if num_katas < self.MIN_KATAS:
            errors.append(
                f"Attuned deck has {num_katas} Katas equipped; requires at least {self.MIN_KATAS} Katas."
            )
        elif num_katas > self.MAX_KATAS:
            errors.append(
                f"Attuned deck has {num_katas} Katas equipped; cannot exceed maximum {self.MAX_KATAS} Katas."
            )

        if self._basic_strike is None:
            errors.append("Attuned deck is missing a designated Basic Strike.")

        if self._guard is None:
            errors.append("Attuned deck is missing a designated Guard technique.")

        if errors:
            raise DeckLoadoutError(f"Deck loadout validation failed: {'; '.join(errors)}")

        return True, []

    def is_valid_loadout(self) -> bool:
        """Returns True if loadout passes all validation checks."""
        try:
            self.validate_loadout()
            return True
        except DeckLoadoutError:
            return False

    def calculate_preview_metrics(self, grammar: Optional[MartialGrammar] = None) -> DeckPreviewMetrics:
        """Calculates comprehensive HUD preview metrics across all equipped techniques."""
        all_techs = self.get_all_active_techniques()
        if not all_techs:
            return DeckPreviewMetrics(
                character_id=self.character_id,
                total_techniques=0,
                kata_count=len(self._katas),
                average_stamina_cost=0.0,
                min_stamina_cost=0.0,
                max_stamina_cost=0.0,
                total_stamina_rotation=0.0,
                average_recovery_frames=0.0,
                min_recovery_frames=0,
                max_recovery_frames=0,
                total_erosion_risk=0.0,
                max_backlash_risk=0.0,
                reach_envelope=(0.0, 0.0),
                stances_used=[],
                vectors_used=[],
                infusions_used=[],
                intents_used=[],
            )

        stamina_costs = [t.stamina_cost for t in all_techs]
        recovery_frames = [t.recovery_frames for t in all_techs]
        erosion_ticks = [t.erosion_ticks for t in all_techs]
        backlash_risks = [max(0.0, t.backlash_damage) for t in all_techs]

        # Reach calculation
        reach_values: List[float] = []
        stances: List[str] = []
        vectors: List[str] = []
        infusions: List[str] = []
        intents: List[str] = []

        g = grammar or MartialGrammar.load()
        for t in all_techs:
            try:
                v = g.get_vector(t.vector_id)
                reach_values.append(v.base_reach_meters)
            except Exception:
                reach_values.append(1.5)

            if t.stance_id not in stances:
                stances.append(t.stance_id)
            if t.vector_id not in vectors:
                vectors.append(t.vector_id)
            if t.infusion_id not in infusions:
                infusions.append(t.infusion_id)
            if t.intent_id not in intents:
                intents.append(t.intent_id)

        min_reach = min(reach_values) if reach_values else 0.0
        max_reach = max(reach_values) if reach_values else 0.0

        return DeckPreviewMetrics(
            character_id=self.character_id,
            total_techniques=len(all_techs),
            kata_count=len(self._katas),
            average_stamina_cost=round(sum(stamina_costs) / len(stamina_costs), 2),
            min_stamina_cost=round(min(stamina_costs), 2),
            max_stamina_cost=round(max(stamina_costs), 2),
            total_stamina_rotation=round(sum(stamina_costs), 2),
            average_recovery_frames=round(sum(recovery_frames) / len(recovery_frames), 2),
            min_recovery_frames=min(recovery_frames),
            max_recovery_frames=max(recovery_frames),
            total_erosion_risk=round(sum(erosion_ticks), 4),
            max_backlash_risk=round(max(backlash_risks), 2),
            reach_envelope=(round(min_reach, 2), round(max_reach, 2)),
            stances_used=stances,
            vectors_used=vectors,
            infusions_used=infusions,
            intents_used=intents,
        )

    def to_db_rows(self) -> List[Dict[str, Any]]:
        """Converts equipped Katas to SQLite martial_kata_decks rows."""
        rows: List[Dict[str, Any]] = []
        for slot, tech in self._katas.items():
            rows.append({
                "character_id": self.character_id,
                "slot_index": slot,
                "technique_id": tech.technique_id,
                "is_active": 1,
            })
        return rows


class KataForge:
    """
    Camp-Phase Kata Forge.
    Allows synthesizing, modifying, and equipping martial Katas into the character's deck.
    """

    def __init__(
        self,
        compiler: Optional[TechniqueCompiler] = None,
        grammar: Optional[MartialGrammar] = None,
    ) -> None:
        self.compiler = compiler or TechniqueCompiler(grammar)
        self.grammar = self.compiler.grammar

    def build_default_basic_strike(self, character_id: str) -> CompiledTechnique:
        """Synthesize canonical baseline basic strike."""
        return self.compiler.compile(
            stance="golden_lotus",
            vector="linear_cleave",
            infusion="structure_resonance",
            intent="reaction_inversion",
            character_id=character_id,
            custom_name="Basic Strike (Neutral Cleave)",
            practice_status="retained",
            discovery_engine="forge",
            base_cost=15.0,
        )

    def build_default_guard(self, character_id: str) -> CompiledTechnique:
        """Synthesize canonical baseline guard."""
        return self.compiler.compile(
            stance="mountain_root",
            vector="linear_cleave",
            infusion="structure_resonance",
            intent="unyielding_bastion",
            character_id=character_id,
            custom_name="Vajra Guard (Iron Stance)",
            practice_status="retained",
            discovery_engine="forge",
            base_cost=10.0,
        )

    def create_deck_with_defaults(self, character_id: str) -> AttunedDeck:
        """Creates a fresh camp-ready AttunedDeck pre-populated with standard Basic Strike and Guard."""
        deck = AttunedDeck(character_id=character_id, in_camp_phase=True)
        deck.set_basic_strike(self.build_default_basic_strike(character_id))
        deck.set_guard(self.build_default_guard(character_id))
        return deck
