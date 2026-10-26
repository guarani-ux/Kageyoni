"""Kageyōni Combat Subsystem (Phase 2 Core Mechanical Engine).

Synthesizes:
- Fire Emblem GBA 2RN True Hit probability resolution & 1RN Critical checks.
- Rise of Kingdoms Dual-Commanders modulated by relational affection.
- Crisis Core spendable DMW resonance tokens.
- Pre-Cognitive Clash Gambits (Turn-based active defense).
- Pokémon Diamond Physical/Special contact split with durability & Zenkai scars.
- Samsara 3-tier casualty economics with Stagnant Convalescence.
"""

from .resolver import (
    TrueHitResolver,
    AttackType,
    Weapon,
    Combatant,
    HitResult,
    CombatResult,
    calculate_true_hit,
    roll_2rn,
)
from .commanders import (
    DualCommanderTeam,
    Commander,
    AffectionTier,
    get_affection_tier,
    QueuedSkill,
    SkillExecutionResult,
)
from .casualty import (
    CasualtyLedger,
    Hospital,
    ConvalescencePatient,
    CasualtyBreakdown,
    AdmissionResult,
    DailyTickResult,
)
from .dmw import (
    DMWTokenType,
    DMWTokenPool,
    DMWSpinResult,
)
from .gambits import (
    GambitType,
    PreCognitiveGambitEngine,
    GambitResult,
)

# Compatibility Aliases
CombatResolver = TrueHitResolver
TrueHitCalculator = TrueHitResolver
ContactSplitType = AttackType
DualCommanderSquad = DualCommanderTeam
StagnantConvalescenceRoster = Hospital

__all__ = [
    # Resolver
    "TrueHitResolver",
    "CombatResolver",
    "TrueHitCalculator",
    "AttackType",
    "ContactSplitType",
    "Weapon",
    "Combatant",
    "HitResult",
    "CombatResult",
    "calculate_true_hit",
    "roll_2rn",
    # Commanders
    "DualCommanderTeam",
    "DualCommanderSquad",
    "Commander",
    "AffectionTier",
    "get_affection_tier",
    "QueuedSkill",
    "SkillExecutionResult",
    # Casualty
    "CasualtyLedger",
    "Hospital",
    "StagnantConvalescenceRoster",
    "ConvalescencePatient",
    "CasualtyBreakdown",
    "AdmissionResult",
    "DailyTickResult",
    # DMW
    "DMWTokenType",
    "DMWTokenPool",
    "DMWSpinResult",
    # Gambits
    "GambitType",
    "PreCognitiveGambitEngine",
    "GambitResult",
]
