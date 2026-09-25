"""Kageyoni Native Entity Substrate.

Provides the foundational architecture for Entities of Kageyoni:
- Modeling Models: CapabilityModel, ReasoningModel, UnderstandingModel, PersonalityModel.
- EntitySpecification: Declarative entity definition.
- PrivateEpistemicState (E_t): Private beliefs, unknowns, contradictions, and scars.
- ActionHorizon: Believed vs actual reachability gap.
- CompletionContract: Sovereign Non-Completion verification.
- EntityInstance: Persistent, model-decoupled situated entity.
- Canonical Specs: Alexandra, Levi, Xandra, Axiom.
"""
from .instance import EntityInstance
from .models import (
    CapabilityModel,
    EntitySpecification,
    PersonalityModel,
    ReasoningModel,
    UnderstandingModel,
)
from .specs import (
    create_alexandra_spec,
    create_axiom_spec,
    create_levi_spec,
    create_xandra_spec,
)
from .state import (
    ActionHorizon,
    CompletionCondition,
    CompletionContract,
    PrivateEpistemicState,
    Scar,
    UnverifiedCompletionError,
)

__all__ = [
    "CapabilityModel",
    "ReasoningModel",
    "UnderstandingModel",
    "PersonalityModel",
    "EntitySpecification",
    "ActionHorizon",
    "CompletionCondition",
    "CompletionContract",
    "UnverifiedCompletionError",
    "Scar",
    "PrivateEpistemicState",
    "EntityInstance",
    "create_alexandra_spec",
    "create_levi_spec",
    "create_xandra_spec",
    "create_axiom_spec",
]
