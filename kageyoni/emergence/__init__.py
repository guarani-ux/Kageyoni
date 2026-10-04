"""
Constellation Emergence Architecture Package.
"""

from .models import (
    ParticipantConfig,
    EncounterConfig,
    EnvironmentAffordance,
    RunHorizon,
    EvidencePolicy,
    TestSpec,
    TestResult,
    TestStatus,
    RoundRecord,
    RoundStatus,
    CandidateDescendant,
    QualificationStatus,
    EvidenceDimension,
    ConstellationManipulationRecord,
    ManipulationType,
    SynthesisOutcome,
    HorizonMode,
    AvailabilitySetting,
)
from .affordances import discover_affordances
from .preview import generate_configuration_preview
from .engine import EmergenceEngine
from .store import EmergenceStore
from .dispatcher import CarrierTestDispatcher
from .cli import ConstellationEmergenceCLI, main

__all__ = [
    "ParticipantConfig",
    "EncounterConfig",
    "EnvironmentAffordance",
    "RunHorizon",
    "EvidencePolicy",
    "TestSpec",
    "TestResult",
    "TestStatus",
    "RoundRecord",
    "RoundStatus",
    "CandidateDescendant",
    "QualificationStatus",
    "EvidenceDimension",
    "ConstellationManipulationRecord",
    "ManipulationType",
    "SynthesisOutcome",
    "HorizonMode",
    "AvailabilitySetting",
    "discover_affordances",
    "generate_configuration_preview",
    "EmergenceEngine",
    "CarrierTestDispatcher",
    "EmergenceStore",
    "ConstellationEmergenceCLI",
    "main",
]
