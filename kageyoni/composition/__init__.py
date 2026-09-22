"""Kageyoni v10 compositional simulation interface.

Frame/Slot/Aspect is a composition language over the existing causal engine.
It does not replace event sourcing, world records, Will contracts, learning,
or workspace execution.
"""
from .compiler import Compiler
from .adapter import EngineAspectAdapter
from .governor import ResolutionGovernor, ProposalError
from .registry import CompositionRegistry
from .service import CompositionService
from .effects import EffectResolver, ExpressionContract, ExpressionVerifier
from .knowledge import KnowledgeLedger

__all__ = ["Compiler", "EngineAspectAdapter", "ResolutionGovernor", "ProposalError", "CompositionRegistry", "CompositionService", "EffectResolver", "ExpressionContract", "KnowledgeLedger"]
