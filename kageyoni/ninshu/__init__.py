"""Ninshū Module Package Initialization."""
from .patchbay import Patchbay
from .console import ActiveConsole, ChannelStripConfig, MasterTape
from .circuits import ChannelCircuit, WaveformMetric, SignalClippingError, PhaseCancellationFault
from .scars import ScarFeedbackMatrix, ScarImpedanceTransformer, CANONICAL_SCARS, SCAR_REGISTRY, ScarRegistry
from .ageing import SSLBoardAgeingEngine, ChannelPatina
from .shaper import SSLMixingSession, ChannelPotentiometers, ChannelMeterBridge
from .modulator import SubstrateModulator, ModulatorDialSetting
from .adversary import (
    AdversarialDiscriminator,
    AdversarialMutator,
    ScarInjector,
    ConsoleAdversaryBridge,
    GoldenVector,
    AdversarialMutant,
    DiscriminationReport,
    MutationType,
    DiscriminationDisposition,
)
from .thermodynamics import (
    ThermodynamicReceipt,
    ThermodynamicProfiler,
    FreshProcessVerifier,
    ConsoleThermodynamicsBridge,
    ThermodynamicViolationError,
    MemoryCeilingExceededError,
    ProcessExitCodeError,
    DigestMismatchError,
)

__all__ = [
    "Patchbay",
    "ActiveConsole",
    "ChannelStripConfig",
    "MasterTape",
    "ChannelCircuit",
    "WaveformMetric",
    "SignalClippingError",
    "PhaseCancellationFault",
    "ScarFeedbackMatrix",
    "ScarImpedanceTransformer",
    "CANONICAL_SCARS",
    "SCAR_REGISTRY",
    "ScarRegistry",
    "SSLBoardAgeingEngine",
    "ChannelPatina",
    "SSLMixingSession",
    "ChannelPotentiometers",
    "ChannelMeterBridge",
    "SubstrateModulator",
    "ModulatorDialSetting",
    "AdversarialDiscriminator",
    "AdversarialMutator",
    "ScarInjector",
    "ConsoleAdversaryBridge",
    "GoldenVector",
    "AdversarialMutant",
    "DiscriminationReport",
    "MutationType",
    "DiscriminationDisposition",
    "ThermodynamicReceipt",
    "ThermodynamicProfiler",
    "FreshProcessVerifier",
    "ConsoleThermodynamicsBridge",
    "ThermodynamicViolationError",
    "MemoryCeilingExceededError",
    "ProcessExitCodeError",
    "DigestMismatchError",
]
