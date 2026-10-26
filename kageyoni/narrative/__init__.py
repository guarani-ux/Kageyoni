"""Kageyōni Narrative & Relational Subsystem (Phase 2 Core Mechanical Engine).

Synthesizes:
- Anti-Slop AST Gate & Austere Prose Verifier (Banned Stems, Adjective Density Ceiling, Physical Anchors).
- Baldur's Gate 3 Style Social Triad:
  - CapabilityAffordanceFilter (CAF)
  - SocialFrictionDCE (Base DCs, Leverage, 4-point Fail-Forward)
  - CausalConsequenceGraph (CCG)
- Enton Rupture Engine & Regional Glassing Fallout (10-turn lockout, Ruin Void).
- Tactical-to-Relational Bridge (Contact Ledger to Morning Camp Private Actions).
"""

from .anti_slop import (
    AntiSlopGate,
    AntiSlopResult,
    AntiSlopViolationError,
    inspect_prose,
    assert_prose_clean,
)
from .social import (
    CapabilityAffordanceFilter,
    SocialFrictionDCE,
    CausalConsequenceGraph,
    DialogueOption,
    CharacterSocialProfile,
    SocialCheckResult,
    SocialConsequence,
    ConsequenceExecutionResult,
    SocialDCTier,
)
from .enton import (
    EntonRuptureEngine,
    EntonRuptureResult,
)
from .pa_bridge import (
    TacticalRelationalBridge,
    ContactEvent,
    PrivateAction,
    CombatContactType,
)

# Canonical Architectural Aliases
AntiSlopInterceptor = AntiSlopGate

__all__ = [
    # Anti-Slop
    "AntiSlopInterceptor",
    "AntiSlopGate",
    "AntiSlopResult",
    "AntiSlopViolationError",
    "inspect_prose",
    "assert_prose_clean",
    # BG3 Social Triad
    "CapabilityAffordanceFilter",
    "SocialFrictionDCE",
    "CausalConsequenceGraph",
    "DialogueOption",
    "CharacterSocialProfile",
    "SocialCheckResult",
    "SocialConsequence",
    "ConsequenceExecutionResult",
    "SocialDCTier",
    # Enton Rupture
    "EntonRuptureEngine",
    "EntonRuptureResult",
    # Relational Bridge
    "TacticalRelationalBridge",
    "ContactEvent",
    "PrivateAction",
    "CombatContactType",
]
