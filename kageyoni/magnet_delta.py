"""
kageyoni/magnet_delta.py
Magnet-and-State Delta Checking Engine.

Enforces:
The Magnet generates pressure.
The State Check determines whether reality moved the way the governing contract says it should.

Core Loop:
READ-ONLY REQUIREMENT
        ↓
CURRENT STATE
        ↓
MAGNET CAST (Invariance Cast | Decisive Cast)
        ↓
EXECUTE / OBSERVE
        ↓
EXPECTED STATE DELTA ↔ ACTUAL STATE DELTA
        ↓
MATCH? ─────────────── NO → SCAR (trace earliest divergence layer & repair)
  │
 YES
  ↓
NEXT GATE

15 Trajectory Layers:
INPUT_LANGUAGE -> INTERPRETATION -> CLAIM -> WARRANT -> DECISION ->
WORKFLOW -> AUTHORITY -> EXECUTION -> EFFECT -> CONSEQUENCE ->
ARTIFACT -> MEMORY -> LEARNING -> RETRIEVAL -> FUTURE_BEHAVIOR
"""

from __future__ import annotations
import copy
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class TrajectoryLayer(Enum):
    INPUT_LANGUAGE = "INPUT_LANGUAGE"
    INTERPRETATION = "INTERPRETATION"
    CLAIM = "CLAIM"
    WARRANT = "WARRANT"
    DECISION = "DECISION"
    WORKFLOW = "WORKFLOW"
    AUTHORITY = "AUTHORITY"
    EXECUTION = "EXECUTION"
    EFFECT = "EFFECT"
    CONSEQUENCE = "CONSEQUENCE"
    ARTIFACT = "ARTIFACT"
    MEMORY = "MEMORY"
    LEARNING = "LEARNING"
    RETRIEVAL = "RETRIEVAL"
    FUTURE_BEHAVIOR = "FUTURE_BEHAVIOR"


TRAJECTORY_ORDER = [
    TrajectoryLayer.INPUT_LANGUAGE,
    TrajectoryLayer.INTERPRETATION,
    TrajectoryLayer.CLAIM,
    TrajectoryLayer.WARRANT,
    TrajectoryLayer.DECISION,
    TrajectoryLayer.WORKFLOW,
    TrajectoryLayer.AUTHORITY,
    TrajectoryLayer.EXECUTION,
    TrajectoryLayer.EFFECT,
    TrajectoryLayer.CONSEQUENCE,
    TrajectoryLayer.ARTIFACT,
    TrajectoryLayer.MEMORY,
    TrajectoryLayer.LEARNING,
    TrajectoryLayer.RETRIEVAL,
    TrajectoryLayer.FUTURE_BEHAVIOR,
]


class CastType(Enum):
    INVARIANCE_CAST = "INVARIANCE_CAST"  # Meaning stays same -> relevant state stays same
    DECISIVE_CAST = "DECISIVE_CAST"      # One consequential fact changes -> dependent state changes appropriately


@dataclass
class DeltaCheckRecord:
    case_id: str
    requirement_id: str
    cast_type: CastType
    pre_state: Dict[str, Any]
    cast_payload: Dict[str, Any]
    expected_delta: Dict[str, Tuple[Any, Any]]     # key -> (expected_old, expected_new)
    actual_delta: Dict[str, Tuple[Any, Any]]       # key -> (actual_old, actual_new)
    expected_invariants: Dict[str, Any]            # key -> expected_value (must remain unchanged)
    actual_invariants: Dict[str, Any]              # key -> actual_value
    evidence: List[str] = field(default_factory=list)
    result: str = "PENDING"                        # MATCH | DIVERGENCE | SCAR
    first_divergence_layer: Optional[str] = None
    dependent_impact: List[str] = field(default_factory=list)

    def is_match(self) -> bool:
        return self.result == "MATCH"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["cast_type"] = self.cast_type.value
        return d


class StateDeltaChecker:
    """
    Executes a Magnet cast against an observable state machine, compares expected vs actual
    deltas, checks invariants, and traces the earliest divergence layer upon failure.
    """

    @staticmethod
    def compute_deltas(
        pre_state: Dict[str, Any],
        post_state: Dict[str, Any],
    ) -> Tuple[Dict[str, Tuple[Any, Any]], Dict[str, Any]]:
        """
        Computes the actual deltas (changed keys) and invariants (unchanged keys).
        """
        all_keys = set(pre_state.keys()) | set(post_state.keys())
        actual_delta: Dict[str, Tuple[Any, Any]] = {}
        actual_invariants: Dict[str, Any] = {}

        for k in sorted(all_keys):
            old_val = pre_state.get(k)
            new_val = post_state.get(k)
            if old_val != new_val:
                actual_delta[k] = (old_val, new_val)
            else:
                actual_invariants[k] = old_val

        return actual_delta, actual_invariants

    @classmethod
    def execute_and_check(
        cls,
        case_id: str,
        requirement_id: str,
        cast_type: CastType,
        pre_state: Dict[str, Any],
        cast_operation: Callable[[], Dict[str, Any]],
        expected_delta: Dict[str, Tuple[Any, Any]],
        expected_invariants: Dict[str, Any],
        layer_mapping: Optional[Dict[str, TrajectoryLayer]] = None,
        cast_payload: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[str]] = None,
    ) -> DeltaCheckRecord:
        """
        Executes cast_operation, captures post_state, and performs full delta & invariant checking.
        """
        pre_copy = copy.deepcopy(pre_state)
        post_state = cast_operation()
        actual_delta, actual_invariants = cls.compute_deltas(pre_copy, post_state)

        record = DeltaCheckRecord(
            case_id=case_id,
            requirement_id=requirement_id,
            cast_type=cast_type,
            pre_state=pre_copy,
            cast_payload=cast_payload or {},
            expected_delta=expected_delta,
            actual_delta=actual_delta,
            expected_invariants=expected_invariants,
            actual_invariants={k: actual_invariants.get(k) for k in expected_invariants.keys()},
            evidence=evidence or [],
        )

        # 1. Delta Match Verification
        delta_mismatch = False
        diverged_keys: List[str] = []

        # Check all expected deltas occurred
        for k, (exp_old, exp_new) in expected_delta.items():
            if k not in actual_delta:
                delta_mismatch = True
                diverged_keys.append(k)
            else:
                act_old, act_new = actual_delta[k]
                if act_new != exp_new:
                    delta_mismatch = True
                    diverged_keys.append(k)

        # Check that no unprompted / surprise deltas occurred
        for k in actual_delta.keys():
            if k not in expected_delta:
                delta_mismatch = True
                diverged_keys.append(k)

        # 2. Invariant Match Verification
        for k, exp_val in expected_invariants.items():
            act_val = post_state.get(k)
            if act_val != exp_val:
                delta_mismatch = True
                diverged_keys.append(k)

        if not delta_mismatch:
            record.result = "MATCH"
            record.dependent_impact = list(actual_delta.keys())
        else:
            record.result = "SCAR"
            record.dependent_impact = diverged_keys

            # Find earliest divergence layer if mapping provided
            if layer_mapping and diverged_keys:
                earliest_layer = None
                earliest_idx = len(TRAJECTORY_ORDER) + 1

                for k in diverged_keys:
                    layer = layer_mapping.get(k)
                    if layer and layer in TRAJECTORY_ORDER:
                        idx = TRAJECTORY_ORDER.index(layer)
                        if idx < earliest_idx:
                            earliest_idx = idx
                            earliest_layer = layer

                if earliest_layer:
                    record.first_divergence_layer = earliest_layer.value

        return record
