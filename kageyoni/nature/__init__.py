"""Kageyoni Core Nature Transformation Substrate.

Provides the five fundamental nature transformations:
1. EXPANSION (R → {R1, ... Rn} with Objective invariance)
2. COMPRESSION ({X1, ... Xn} → G with safety declarations)
3. GROUNDING (Hypothesis → Verifier → Evidence with anti-laundering)
4. CONTINUITY (S_t + Δ → S_(t+1) with 5-way categorization)
5. COUPLING (A + B + Rel → C with interface analysis and emergence mechanism)

Governed by Transformation Control.
Supports emerging Techniques, Compound Capabilities (ExtractTechnique),
and the self-improving Compounding Loop.

Invariant: Δcog ≠ Δworld and Cognitive Output ≠ Verified Fact.
"""
from .compression import (
    Compression,
    CompressionResult,
    DestructiveCompressionError,
    IncompatibleCasesError,
)
from .continuity import (
    Continuity,
    ContinuityDisposition,
    ContinuityItem,
    ContinuityResult,
)
from .control import (
    ControlDecision,
    ControlDirective,
    FailureModeGovernor,
    TransformationControl,
)
from .core import (
    CognitiveDelta,
    CognitiveHypothesis,
    CognitiveState,
    DeficitType,
    EpistemicCategory,
    EpistemicLaunderingError,
    KnowledgeDeficit,
    NatureType,
    ObjectiveDriftError,
)
from .coupling import (
    CandidateComposition,
    ComponentInterface,
    Coupling,
    CouplingResult,
    IncompatibleInterfaceError,
    SpuriousCouplingError,
)
from .expansion import (
    CandidateBranch,
    Expansion,
    ExpansionResult,
)
from .extraction import (
    CandidateTechnique,
    ExtractionResult,
    ExtractTechnique,
    StructuralType,
)
from .grounding import (
    Grounding,
    GroundingResult,
    VerificationProbe,
)
from .compounding import (
    CompoundingLoop,
    QualificationTrial,
    QualifiedTechniqueRecord,
    UnqualifiedTechniqueError,
)
from .techniques import (
    CarryForward,
    CausalAttribute,
    Falsify,
    LiftInvariant,
    Reframe,
    Technique,
    TechniqueComposition,
)
from .sovereign_incarnation import (
    BoundaryViolationError,
    IncarnationStepResult,
    SovereignIncarnation,
    SovereignNonCompletionError,
)

__all__ = [
    # Core
    "CognitiveState",
    "CognitiveDelta",
    "CognitiveHypothesis",
    "NatureType",
    "DeficitType",
    "KnowledgeDeficit",
    "EpistemicCategory",
    "EpistemicLaunderingError",
    "ObjectiveDriftError",
    # 5 Natures
    "Expansion",
    "ExpansionResult",
    "CandidateBranch",
    "Compression",
    "CompressionResult",
    "DestructiveCompressionError",
    "IncompatibleCasesError",
    "Grounding",
    "GroundingResult",
    "VerificationProbe",
    "Continuity",
    "ContinuityResult",
    "ContinuityItem",
    "ContinuityDisposition",
    "Coupling",
    "CouplingResult",
    "ComponentInterface",
    "CandidateComposition",
    "IncompatibleInterfaceError",
    "SpuriousCouplingError",
    # Control & Governance
    "TransformationControl",
    "FailureModeGovernor",
    "ControlDecision",
    "ControlDirective",
    # Techniques & Composition
    "Technique",
    "Reframe",
    "LiftInvariant",
    "Falsify",
    "CarryForward",
    "CausalAttribute",
    "TechniqueComposition",
    # Compound Capabilities
    "ExtractTechnique",
    "CandidateTechnique",
    "StructuralType",
    "ExtractionResult",
    "CompoundingLoop",
    "QualificationTrial",
    "QualifiedTechniqueRecord",
    "UnqualifiedTechniqueError",
    # Sovereign Incarnation
    "SovereignIncarnation",
    "IncarnationStepResult",
    "BoundaryViolationError",
    "SovereignNonCompletionError",
]
