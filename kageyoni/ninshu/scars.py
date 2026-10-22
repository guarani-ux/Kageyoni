"""Ninshū SSL Dynamic Scar Transformer Circuit (Zenkai Feedback Engine).

Reconfigures the SSL Console to integrate operational Scars:
1. Scars are not static error logs; they are ACTIVE FEEDBACK CIRCUITS.
2. Every historical failure (concurrency race, stale revision, malformed header, OOM)
   is converted into an internal Impedance Transformer on the channel strip.
3. When the liquid metal passes through a transformer, the Scar shapes the wave,
   forcing the emerging capability to inherit the hard-won understanding
   without re-learning the failure.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ScarImpedanceTransformer:
    """An active impedance transformer forged from a closed operational scar."""
    scar_id: str
    failure_class: str
    root_cause: str
    learned_rule: str
    trigger_pattern: str                 # Regex or structural pattern that activates the circuit
    damping_factor: float = 1.0          # Resistance applied to prevent recurrence (0.0 to 1.0)
    reversibility_barrier: int = 1       # Tier elevation if pattern is detected
    functional_adaptation: str = ""      # What functional shape emerges from this scar


# Historical Scars earned across Kageyōni and REA development
CANONICAL_SCARS: List[ScarImpedanceTransformer] = [
    ScarImpedanceTransformer(
        scar_id="SCAR-001-STALE-REVISION",
        failure_class="CONCURRENCY_RACE",
        root_cause="Caller executed mutation based on outdated branch revision snapshot.",
        learned_rule="Compare-And-Swap (CAS) prerequisite: require expected_revision == current_revision.",
        trigger_pattern="expected_revision|branch_mutation|apply_command",
        damping_factor=1.0,
        reversibility_barrier=0,
        functional_adaptation="Injects ResolutionGovernor basis verification before command execution."
    ),
    ScarImpedanceTransformer(
        scar_id="SCAR-002-CONTROL-BYTE-CORRUPTION",
        failure_class="PARSER_POISONING",
        root_cause="Hidden ASCII control bytes (x00-x1F) corrupted AST parsing and JSON roundtrips.",
        learned_rule="Zero tolerance for non-printable control characters in specifications.",
        trigger_pattern="control_char|null_byte|non_printable",
        damping_factor=1.0,
        reversibility_barrier=0,
        functional_adaptation="Engages Preamp UTF-8 strict sanitization and nul-free string schemas."
    ),
    ScarImpedanceTransformer(
        scar_id="SCAR-003-UNBOUND-OBJECTIVE-DRIFT",
        failure_class="GOVERNANCE_BYPASS",
        root_cause="Agent silently mutated prompt objective mid-execution to claim success.",
        learned_rule="ProtectedOperations invariant: objective, scope, and requirement version are immutable.",
        trigger_pattern="objective_mutation|patch_scope|requirement_drift",
        damping_factor=1.0,
        reversibility_barrier=1,
        functional_adaptation="Locks objective hash in ProtectedOperations v11 state machine."
    ),
    ScarImpedanceTransformer(
        scar_id="SCAR-004-DISCRETIONARY-TOOL-SPRAWL",
        failure_class="ARCHITECTURAL_MUD",
        root_cause="Parallel duplicate verifiers (verify_candidate.py vs engine.py) created drifting truths.",
        learned_rule="Single operating contract: retire redundant routes; retain only authoritative engine.",
        trigger_pattern="duplicate_verifier|parallel_route|wrapper_sprawl",
        damping_factor=0.9,
        reversibility_barrier=0,
        functional_adaptation="Forces routing through Patchbay FTS5 rather than ad-hoc script generation."
    ),
    ScarImpedanceTransformer(
        scar_id="SCAR-005-MOCK-THEATRE-SELF-CERTIFICATION",
        failure_class="EPISTEMIC_CORRUPTION",
        root_cause="Agent fabricated green tests by weakening assertions or mocking truth.",
        learned_rule="Metamorphic discrimination required: must pass on valid inputs AND fail on corrupted holdouts.",
        trigger_pattern="assert_true|synthetic_mock|self_promotion",
        damping_factor=1.0,
        reversibility_barrier=1,
        functional_adaptation="Demands min 2 distinct disposition classes with 0 errors for qualification."
    )
]


class ScarRegistry(dict):
    """Active runtime registry of ScarImpedanceTransformers."""

    def __init__(self, initial_scars: Optional[List[ScarImpedanceTransformer]] = None):
        super().__init__()
        for s in (initial_scars if initial_scars is not None else CANONICAL_SCARS):
            self.register(s)

    def register(self, scar: ScarImpedanceTransformer) -> ScarImpedanceTransformer:
        """Register a scar impedance transformer into active circulation."""
        self[scar.scar_id] = scar
        return scar

    def append(self, scar: ScarImpedanceTransformer) -> ScarImpedanceTransformer:
        return self.register(scar)

    def get_scar(self, scar_id: str) -> Optional[ScarImpedanceTransformer]:
        return self.get(scar_id)

    def list_all(self) -> List[ScarImpedanceTransformer]:
        return list(self.values())


# Global active registry for Ninshū operational scars
SCAR_REGISTRY: ScarRegistry = ScarRegistry()


class ScarFeedbackMatrix:
    """The active SSL console circuit that shapes streaming liquid metal using historical Scars."""

    def __init__(self, transformers: Optional[List[ScarImpedanceTransformer]] = None):
        self._custom_transformers: Optional[List[ScarImpedanceTransformer]] = (
            list(transformers) if transformers is not None else None
        )
        self.active_scars_engaged: List[Dict[str, Any]] = []

    @property
    def transformers(self) -> List[ScarImpedanceTransformer]:
        if self._custom_transformers is not None:
            return self._custom_transformers
        return list(SCAR_REGISTRY.values())

    @transformers.setter
    def transformers(self, val: List[ScarImpedanceTransformer]) -> None:
        self._custom_transformers = list(val)

    def transform_signal(
        self,
        signal: Dict[str, Any],
        declared_intent: str
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Passes the live computational signal through the Scar Transformers.
        If a signal exhibits a known failure signature, the transformer bends the wave,
        applying damping and injecting the hard-won functional adaptation.
        """
        conditioned = copy.deepcopy(signal)
        adaptations_applied = []
        sig_text = json.dumps(signal).lower() + " " + declared_intent.lower()

        for scar in self.transformers:
            # Check if signal matches trigger pattern (case-insensitive)
            tokens = [t.strip().lower() for t in scar.trigger_pattern.split("|") if t.strip()]
            if any(t in sig_text for t in tokens):
                # Scar circuit engages: Apply damping & inject functional adaptation
                self.active_scars_engaged.append({
                    "scar_id": scar.scar_id,
                    "failure_class": scar.failure_class,
                    "adaptation": scar.functional_adaptation,
                    "timestamp": time.time()
                })
                adaptations_applied.append(f"[{scar.scar_id}] {scar.functional_adaptation}")

                # Electrically reshape the signal
                conditioned.setdefault("scar_adaptations", []).append({
                    "scar_id": scar.scar_id,
                    "learned_rule": scar.learned_rule,
                    "adaptation": scar.functional_adaptation,
                    "damping": scar.damping_factor
                })

        return conditioned, adaptations_applied
