"""
Upstream Research-to-Creative Cognitive Compiler
Translates physical evidence, topic reality, and audience friction into
a script-ready intelligence package. Operates entirely upstream of scripting.
"""

from .claims import ClaimGraph, ClaimNode, SourceRecord, EpistemicStatus
from .topic_modeler import TopicModeler, TopicModel
from .adversarial import AdversarialAuditor, AdversarialAuditResult
from .treatment_generator import TreatmentGenerator, StoryArchetype, CompetingTreatment
from .package_compiler import ScriptReadyCompiler, ScriptReadyPackage

__all__ = [
    "ClaimGraph",
    "ClaimNode",
    "SourceRecord",
    "EpistemicStatus",
    "TopicModeler",
    "TopicModel",
    "AdversarialAuditor",
    "AdversarialAuditResult",
    "TreatmentGenerator",
    "StoryArchetype",
    "CompetingTreatment",
    "ScriptReadyCompiler",
    "ScriptReadyPackage",
]
