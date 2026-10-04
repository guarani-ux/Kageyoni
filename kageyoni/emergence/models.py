"""
Domain models for Constellation Emergence Architecture.
Implements preflight configuration, round-and-cycle contract,
evidence weighting, manipulation provenance, and terminal synthesis.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AvailabilitySetting(str, Enum):
    LIVE_INSPECTABLE = "LIVE_INSPECTABLE"
    EXECUTABLE = "EXECUTABLE"
    ASSUMED = "ASSUMED"
    UNAVAILABLE = "UNAVAILABLE"


class HorizonMode(str, Enum):
    ONE_ROUND = "ONE_ROUND"
    TEN_ROUND_CYCLE = "TEN_ROUND_CYCLE"
    N_CYCLES = "N_CYCLES"
    CONTINUOUS = "CONTINUOUS"


class TestStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    PENDING = "PENDING"


class RoundStatus(str, Enum):
    LOCKED = "LOCKED"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    TERMINAL = "TERMINAL"


class QualificationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    TESTED_IN_SCOPE = "TESTED_IN_SCOPE"
    QUALIFIED = "QUALIFIED"
    ACCEPTED = "ACCEPTED"
    UNKNOWN = "UNKNOWN"


class ManipulationType(str, Enum):
    CONNECT = "CONNECT"
    SEPARATE = "SEPARATE"
    REORDER = "REORDER"
    RECONTEXTUALIZE = "RECONTEXTUALIZE"
    RECRUIT = "RECRUIT"
    AMPLIFY = "AMPLIFY"
    SUPPRESS = "SUPPRESS"
    ABLATE = "ABLATE"
    RESTORE = "RESTORE"
    TRACE = "TRACE"
    TEST = "TEST"
    PRESERVE = "PRESERVE"


@dataclass
class ParticipantConfig:
    character_id: str
    name: str
    source_state: str
    role: str
    constraints: List[str] = field(default_factory=list)
    bandwidth: int = 85
    causal_memory: int = 90
    antigravity_leverage: int = 90
    will_density: int = 85


@dataclass
class EncounterConfig:
    opponents: List[str]
    objective: str
    encounter_type: str
    starting_state: str
    stakes: str
    constraints: List[str] = field(default_factory=list)


@dataclass
class EnvironmentAffordance:
    name: str
    category: str
    path: str
    carrier: str
    availability: AvailabilitySetting
    intensity: str
    observable_features: List[str] = field(default_factory=list)


@dataclass
class RunHorizon:
    mode: HorizonMode
    n_cycles: int = 1
    current_cycle: int = 1
    current_round: int = 1
    total_rounds: int = 10


@dataclass
class EvidencePolicy:
    required_tests: List[str] = field(default_factory=list)
    adversarial_tests: List[str] = field(default_factory=list)
    pass_fail_criteria: Dict[str, Any] = field(default_factory=dict)
    evidence_minimum: int = 1
    stop_conditions: List[str] = field(default_factory=list)


@dataclass
class TestSpec:
    test_id: str
    name: str
    test_type: str  # DIRECT, ADVERSARIAL, EDGE_CASE, INVARIANT_CHECK
    target: str
    assertion: str
    resistance_level: float = 0.5  # 0.0 to 1.0
    assigned_actor: Optional[str] = None
    required_metric: Optional[str] = None
    minimum_metric_threshold: int = 0


@dataclass
class TestResult:
    test_id: str
    status: TestStatus
    measurement: Dict[str, Any] = field(default_factory=dict)
    evidence_ref: str = ""
    duration_ms: float = 0.0
    error_message: Optional[str] = None


@dataclass
class EvidenceDimension:
    relevance: float = 0.0
    directness: float = 0.0
    repeatability: float = 0.0
    test_coverage: float = 0.0
    resistance_encountered: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "relevance": round(self.relevance, 3),
            "directness": round(self.directness, 3),
            "repeatability": round(self.repeatability, 3),
            "test_coverage": round(self.test_coverage, 3),
            "resistance_encountered": round(self.resistance_encountered, 3),
        }


@dataclass
class RoundRecord:
    round_num: int
    cycle_num: int
    hypothesis: str
    procedure: str
    planned_tests: List[TestSpec] = field(default_factory=list)
    adversarial_tests: List[TestSpec] = field(default_factory=list)
    executed_results: List[TestResult] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    status: RoundStatus = RoundStatus.LOCKED
    remediation_notes: List[str] = field(default_factory=list)
    remediation_attempts: int = 0
    max_remediation_attempts: int = 3
    round_result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateDescendant:
    descendant_id: str
    name: str
    ancestor_technique: str
    carrier: str
    operation: str
    input_state: str
    output_state: str
    conservation: str
    authority: str
    failure_signature: str
    null_case: str
    evidence_ref: str
    status: QualificationStatus = QualificationStatus.PROPOSED
    dimensions: Optional[EvidenceDimension] = None
    test_ids: List[str] = field(default_factory=list)


@dataclass
class ConstellationManipulationRecord:
    manipulation_type: ManipulationType
    target: str
    observed_change: str
    gain: str
    loss: str
    new_reachability: str
    closed_reachability: str
    residue: str
    uncertainty: str
    attribution: str


@dataclass
class SynthesisOutcome:
    ancestor_proposals: List[Dict[str, Any]] = field(default_factory=list)
    technique_outcomes: List[CandidateDescendant] = field(default_factory=list)
    unresolved_map: Dict[str, Any] = field(default_factory=dict)
    manipulations: List[ConstellationManipulationRecord] = field(default_factory=list)
    synthesis_hash: str = ""
    timestamp: float = 0.0
