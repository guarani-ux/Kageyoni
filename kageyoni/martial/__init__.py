"""Kageyōni Martial Arts Subsystem (Phase 2 Core Mechanical Engine).

Synthesizes:
- Modular Martial Grammar & 4-part Compound Compiler (Stance + Vector + Infusion + Intent).
- Attuned Kata Deck & Camp Kata Forge (3-4 Katas + Basic Strike + Guard).
- Satori Epiphany Engine (Crisis-Driven Technique Mutation).
- Star Ocean style Secret Talent System & Friction Ledger.
"""

from .compiler import (
    TechniqueCompiler,
    MartialGrammar,
    CompiledTechnique,
    StancePrimitive,
    VectorPrimitive,
    InfusionPrimitive,
    IntentPrimitive,
    TalentPrimitive,
)
from .deck import (
    AttunedDeck,
    KataForge,
    DeckPreviewMetrics,
    DeckLoadoutError,
    DeckModificationLockedError,
)
from .satori import (
    SatoriEpiphanyEngine,
    SatoriResult,
)
from .talents import (
    TalentType,
    StarOceanTalentLedger,
    BreakthroughResult,
)

# Canonical Architectural Aliases
MartialCompoundCompiler = TechniqueCompiler
AttunedKataDeck = AttunedDeck

__all__ = [
    # Compiler & Grammar
    "MartialCompoundCompiler",
    "TechniqueCompiler",
    "MartialGrammar",
    "CompiledTechnique",
    "StancePrimitive",
    "VectorPrimitive",
    "InfusionPrimitive",
    "IntentPrimitive",
    "TalentPrimitive",
    # Deck & Forge
    "AttunedKataDeck",
    "AttunedDeck",
    "KataForge",
    "DeckPreviewMetrics",
    "DeckLoadoutError",
    "DeckModificationLockedError",
    # Satori
    "SatoriEpiphanyEngine",
    "SatoriResult",
    # Talents
    "TalentType",
    "StarOceanTalentLedger",
    "BreakthroughResult",
]
