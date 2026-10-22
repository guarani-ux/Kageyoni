"""Ninshū Module Package Initialization."""
from .patchbay import Patchbay
from .console import ActiveConsole, ChannelStripConfig, MasterTape
from .circuits import ChannelCircuit, WaveformMetric, SignalClippingError, PhaseCancellationFault
from .scars import ScarFeedbackMatrix, ScarImpedanceTransformer, CANONICAL_SCARS
from .ageing import SSLBoardAgeingEngine, ChannelPatina
from .shaper import SSLMixingSession, ChannelPotentiometers, ChannelMeterBridge

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
    "SSLBoardAgeingEngine",
    "ChannelPatina",
    "SSLMixingSession",
    "ChannelPotentiometers",
    "ChannelMeterBridge",
]
