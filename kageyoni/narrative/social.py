"""Baldur's Gate 3 Style Narrative Social Triad for Kageyōni.

Implements:
1. CapabilityAffordanceFilter (CAF):
   Filters dialogue options based on stats, active scars, and tactical roles.
   Tags include: [VAJRA INSIGHT], [FLIRT], [CRUEL], [BRIBE], [PATRONIZE].
2. SocialFrictionDCE:
   - Base DC tiers: trivial (8), standard (12), strained (15), severe (18), apex (22).
   - Leverage modifiers: physical receipt (+3), high ground (+2), scar resonance (+3),
     ideological hostility (-4), slop violation (-5).
   - 4-point Fail-Forward: if roll fails by <= 4 points, returns branch="complication"
     (partial success with systemic cost).
3. CausalConsequenceGraph (CCG):
   Applies companion approval deltas, faction disposition shifts, and spatial grid displacements.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class DialogueOption:
    """Represents an actionable dialogue choice."""
    option_id: str
    text: str
    tag: Optional[str] = None  # e.g. "[VAJRA INSIGHT]", "[FLIRT]", "[CRUEL]", "[BRIBE]", "[PATRONIZE]"
    required_stat: Optional[str] = None
    min_stat_value: int = 0
    required_scar: Optional[str] = None
    required_role: Optional[str] = None
    consequence_id: Optional[str] = None


@dataclass
class CharacterSocialProfile:
    """Actor attributes evaluated by the Capability Affordance Filter."""
    character_id: str
    stats: Dict[str, int] = field(default_factory=dict)       # e.g. {"insight": 14, "charisma": 12, "will": 16}
    active_scars: Set[str] = field(default_factory=set)        # e.g. {"zenkai_eye", "void_brand"}
    roles: Set[str] = field(default_factory=set)               # e.g. {"commander", "monk", "infiltrator"}
    gold: int = 100


class CapabilityAffordanceFilter:
    """Filters available dialogue affordances based on character capabilities and scars."""

    @staticmethod
    def is_option_available(option: DialogueOption, profile: CharacterSocialProfile) -> bool:
        # Check stat requirements
        if option.required_stat:
            val = profile.stats.get(option.required_stat.lower(), 0)
            if val < option.min_stat_value:
                return False

        # Check scar requirements (e.g. [VAJRA INSIGHT] requires zenkai or insight scar)
        if option.required_scar:
            if option.required_scar not in profile.active_scars:
                return False

        # Tag-based heuristic checks
        if option.tag == "[VAJRA INSIGHT]":
            has_insight = profile.stats.get("insight", 0) >= 14 or "zenkai_eye" in profile.active_scars
            if not has_insight:
                return False

        if option.tag == "[BRIBE]":
            if profile.gold < 50:
                return False

        # Check role requirements
        if option.required_role:
            if option.required_role.lower() not in {r.lower() for r in profile.roles}:
                return False

        return True

    @classmethod
    def filter_options(
        cls,
        options: List[DialogueOption],
        profile: CharacterSocialProfile,
    ) -> List[DialogueOption]:
        """Filter dialogue choices down to those permitted by current capabilities."""
        return [opt for opt in options if cls.is_option_available(opt, profile)]


class SocialDCTier(int, Enum):
    TRIVIAL = 8
    STANDARD = 12
    STRAINED = 15
    SEVERE = 18
    APEX = 22


@dataclass
class SocialCheckResult:
    """Detailed outcome of resolving a social dialogue check with fail-forward dynamics."""
    branch: str  # "success", "complication", "failure"
    target_dc: int
    raw_roll: int
    net_modifier: int
    effective_total: int
    margin: int
    modifiers_applied: Dict[str, int]
    details: str = ""


class SocialFrictionDCE:
    """Resolves social friction rolls with systematic leverage and 4-point fail-forward."""

    TIER_MAP: Dict[str, int] = {
        "trivial": 8,
        "standard": 12,
        "strained": 15,
        "severe": 18,
        "apex": 22,
    }

    LEVERAGE_MODS: Dict[str, int] = {
        "physical_receipt": 3,
        "high_ground": 2,
        "scar_resonance": 3,
        "ideological_hostility": -4,
        "slop_violation": -5,
    }

    @classmethod
    def resolve_check(
        cls,
        base_dc: int | str,
        d20_roll: int,
        active_leverages: Optional[Dict[str, bool]] = None,
        character_bonus: int = 0,
    ) -> SocialCheckResult:
        """Resolve a social friction check.

        4-point Fail-Forward rule:
        - If effective_total >= target_dc: branch="success"
        - If roll fails by <= 4 points (target_dc - effective_total <= 4): branch="complication"
        - If roll fails by > 4 points: branch="failure"
        """
        if isinstance(base_dc, str):
            target = cls.TIER_MAP.get(base_dc.lower(), 12)
        else:
            target = int(base_dc)

        modifiers_applied: Dict[str, int] = {}
        net_mod = character_bonus
        if character_bonus != 0:
            modifiers_applied["character_bonus"] = character_bonus

        leverages = active_leverages or {}
        for mod_key, is_active in leverages.items():
            if is_active and mod_key in cls.LEVERAGE_MODS:
                val = cls.LEVERAGE_MODS[mod_key]
                net_mod += val
                modifiers_applied[mod_key] = val

        effective_total = d20_roll + net_mod
        margin = effective_total - target

        if margin >= 0:
            branch = "success"
            details = f"Check succeeded cleanly (Total {effective_total} >= DC {target}, margin +{margin})."
        elif margin >= -4:
            # 4-point Fail-Forward window
            branch = "complication"
            details = f"FAIL-FORWARD COMPLICATION: Total {effective_total} failed DC {target} by {abs(margin)} (<= 4). Partial success with systemic cost."
        else:
            branch = "failure"
            details = f"Check failed decisively (Total {effective_total} < DC {target}, margin {margin})."

        return SocialCheckResult(
            branch=branch,
            target_dc=target,
            raw_roll=d20_roll,
            net_modifier=net_mod,
            effective_total=effective_total,
            margin=margin,
            modifiers_applied=modifiers_applied,
            details=details,
        )


@dataclass
class SocialConsequence:
    """Consequence bundle triggered by dialogue outcomes."""
    consequence_id: str
    approval_deltas: Dict[str, int] = field(default_factory=dict)       # e.g. {"Astarion": +5, "Gale": -3}
    disposition_deltas: Dict[str, int] = field(default_factory=dict)    # e.g. {"Frostfall": -10, "Citadel": +15}
    spatial_displacements: List[Tuple[int, int, str]] = field(default_factory=list) # (x, y, faction/state)


@dataclass
class ConsequenceExecutionResult:
    consequence_id: str
    approval_applied: Dict[str, int]
    disposition_applied: Dict[str, int]
    displacements_applied: List[Tuple[int, int, str]]
    details: str = ""


class CausalConsequenceGraph:
    """Applies social consequences to game world state, companion approval, and spatial grid."""

    def __init__(self) -> None:
        self.companion_approval: Dict[str, int] = {}
        self.faction_disposition: Dict[str, int] = {}
        self.displacement_history: List[Tuple[int, int, str]] = []

    def apply_consequence(
        self,
        consequence: SocialConsequence,
        world_grid: Optional[Any] = None,
    ) -> ConsequenceExecutionResult:
        """Mutate approval, disposition, and world grid based on consequence payload."""
        # 1. Companion Approval
        applied_approval: Dict[str, int] = {}
        for comp, delta in consequence.approval_deltas.items():
            self.companion_approval[comp] = self.companion_approval.get(comp, 0) + delta
            applied_approval[comp] = self.companion_approval[comp]

        # 2. Faction Disposition
        applied_disposition: Dict[str, int] = {}
        for fac, delta in consequence.disposition_deltas.items():
            self.faction_disposition[fac] = self.faction_disposition.get(fac, 0) + delta
            applied_disposition[fac] = self.faction_disposition[fac]

        # 3. Spatial Grid Displacements
        applied_displacements: List[Tuple[int, int, str]] = []
        for x, y, faction_or_event in consequence.spatial_displacements:
            self.displacement_history.append((x, y, faction_or_event))
            applied_displacements.append((x, y, faction_or_event))
            if world_grid is not None:
                try:
                    world_grid.set_tile_faction(x, y, faction_or_event)
                except Exception:
                    pass

        return ConsequenceExecutionResult(
            consequence_id=consequence.consequence_id,
            approval_applied=applied_approval,
            disposition_applied=applied_disposition,
            displacements_applied=applied_displacements,
            details=f"Consequence '{consequence.consequence_id}' executed: {len(applied_approval)} approval shifts, {len(applied_disposition)} disposition shifts, {len(applied_displacements)} spatial mutations.",
        )
