"""Epistemic contracts and developmental data structures for Kageyōni.

Hardened under Hardening Directives 1 - 13:
1. Separate Qualification Levels (VALID_GENESIS -> DEVELOPMENT_OBSERVED -> CAPABILITY_DEMONSTRATED -> CAPABILITY_QUALIFIED -> RELATIONAL_CAPABILITY_QUALIFIED).
2. Genesis Snapshots (Immutable A0 manifest with code/config digest).
3. Genesis Modes (IDENTICAL_GENESIS vs SPECIALIZED_GENESIS).
4. Provenance on every DevelopmentalDelta (What, From, Because of, Who interpreted, What verifier, Future behavior).
5. Non-scalar Relational development (5-way qualification).
6. Negative development (suspension, invalidation, demotion).
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from kageyoni.engine import Rejected


class EpistemicDistinction(str, Enum):
    """Rigorous epistemic categorization ensuring Reality != Belief != Perception."""
    REALITY_GROUND = "REALITY_GROUND"        # Proven by engine commit / physical transaction
    PERCEPTION = "PERCEPTION"                # Observed through viewer filter / uncommitted
    BELIEF_UNVERIFIED = "BELIEF_UNVERIFIED"  # Internal model hypothesis / inference
    UNKNOWN = "UNKNOWN"                      # Absence of information
    DEFICIT = "DEFICIT"                      # Identifiable missing information required for commit
    RESIDUE = "RESIDUE"                      # Unparsed anomaly; not yet a candidate technique


class QualificationLevel(str, Enum):
    """#1 Separate Qualification Levels. Genesis tests establish ONLY VALID_GENESIS."""
    VALID_GENESIS = "VALID_GENESIS"
    DEVELOPMENT_OBSERVED = "DEVELOPMENT_OBSERVED"
    CAPABILITY_DEMONSTRATED = "CAPABILITY_DEMONSTRATED"
    CAPABILITY_QUALIFIED = "CAPABILITY_QUALIFIED"
    RELATIONAL_CAPABILITY_QUALIFIED = "RELATIONAL_CAPABILITY_QUALIFIED"
    APEX_ARCHITECTURE_IMPLEMENTED = "APEX_ARCHITECTURE_IMPLEMENTED"
    OPEN_CEILING_QUALIFIED = "OPEN_CEILING_QUALIFIED"


class GenesisMode(str, Enum):
    """#4 Distinguish Configured Difference from Developed Difference."""
    SPECIALIZED_GENESIS = "SPECIALIZED_GENESIS"  # Different initial parameters allowed
    IDENTICAL_GENESIS = "IDENTICAL_GENESIS"      # A0 and B0 structurally equivalent except identity/seed


class CapabilityState(str, Enum):
    """#25 Capability States Lifecycle."""
    UNAWARE = "UNAWARE"
    AWARE = "AWARE"
    OBSERVED = "OBSERVED"
    UNDERSTOOD = "UNDERSTOOD"
    AVAILABLE = "AVAILABLE"
    CANDIDATE = "CANDIDATE"
    DEMONSTRATED = "DEMONSTRATED"
    QUALIFIED = "QUALIFIED"
    # Defeasible and structural variants
    STALE = "STALE"
    RELATIONAL = "RELATIONAL"
    SUSPENDED = "SUSPENDED"
    INVALIDATED = "INVALIDATED"
    OBSOLETE = "OBSOLETE"


class CapabilityOwnership(str, Enum):
    """#26 Capability Ownership Scope: Bind to smallest qualified scope."""
    SELF = "SELF"
    TECHNIQUE = "TECHNIQUE"
    RELATIONSHIP = "RELATIONSHIP"
    COUNCIL = "COUNCIL"
    NICHE = "NICHE"
    WORLD = "WORLD"
    WORKFLOW = "WORKFLOW"
    REPRESENTATION = "REPRESENTATION"
    HOST = "HOST"
    BOUNDARY = "BOUNDARY"
    CAPABILITY_ECOLOGY = "CAPABILITY_ECOLOGY"
    DOMAIN = "DOMAIN"
    UNKNOWN = "UNKNOWN"


class EncounterOrigin(str, Enum):
    """#34 Encounter Origin Classification."""
    SELECTED = "SELECTED"       # Deliberately sought by agent
    WORLD = "WORLD"             # Produced by independent world dynamics
    CONTINGENT = "CONTINGENT"   # Arose without developmental intent


class MetabolismCategory(str, Enum):
    """#31 Independent Consequence Metabolism across Apex Open Ceiling categories."""
    ORDINARY_HISTORY = "ORDINARY_HISTORY"
    SCAR_CANDIDATE = "SCAR_CANDIDATE"
    DEFICIT = "DEFICIT"
    RESIDUE = "RESIDUE"
    CAPABILITY_CANDIDATE = "CAPABILITY_CANDIDATE"
    RELATIONSHIP_DELTA = "RELATIONSHIP_DELTA"
    NICHE_DELTA = "NICHE_DELTA"
    GENERATOR_CANDIDATE = "GENERATOR_CANDIDATE"
    NOTHING_REUSABLE = "NOTHING_REUSABLE"


class InnateVerb(str, Enum):
    """#23 Innate Loadout Verbs: Everything else must be discovered or qualified."""
    SITUATE = "SITUATE"
    ENCOUNTER = "ENCOUNTER"
    METABOLIZE = "METABOLIZE"
    REGROUND = "REGROUND"
    CAPABILITY_MEMBRANE = "CAPABILITY_MEMBRANE"


class UnauthorizedAuthorityExpansionError(Rejected):
    """Raised when an agent attempts to autonomously expand its execution authority."""
    def __init__(self, message: str = "Agent may not autonomously expand execution authority"):
        super().__init__(
            message=message,
            rejection_class="INSUFFICIENT_AUTHORITY",
            details={"invariant": "AUTHORITY_EXPANSION_REQUIRES_SOVEREIGN_DELEGATION"}
        )


class UnqualifiedAcquisitionError(Rejected):
    """Raised when an agent attempts to acquire a technique without explicit qualification."""
    def __init__(self, message: str = "Technique acquisition requires passing qualification trials"):
        super().__init__(
            message=message,
            rejection_class="HARD_INVARIANT_VIOLATION",
            details={"invariant": "AVAILABILITY_IS_NOT_QUALIFICATION"}
        )


class ObjectiveInvarianceViolation(Rejected):
    """Raised when an agent or caller attempts to alter an immutable sovereign objective."""
    def __init__(self, message: str = "Objective is an immutable sovereign invariant"):
        super().__init__(
            message=message,
            rejection_class="HARD_INVARIANT_VIOLATION",
            details={"invariant": "OBJECTIVE_INVARIANCE"}
        )


@dataclass
class ObjectiveRevisionRequest:
    """Emitted when an agent discovers its sovereign objective contains a contradiction or false premise.
    Agent CANNOT autonomously change its objective; it formally demonstrates the revision need to Levi.
    """
    authority: str = "LEVI"
    current_objective: str = ""
    reason: str = ""
    evidence: list[str] = field(default_factory=list)
    suggested_revision: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "OBJECTIVE_REVISION_REQUIRED",
            "authority": self.authority,
            "current_objective": self.current_objective,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "suggested_revision": self.suggested_revision,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class GenesisSnapshot:
    """#3 Immutable Genesis Snapshot (A0 Manifest)."""
    snapshot_id: str
    agent_id: str
    genesis_mode: GenesisMode
    objective: str
    initial_horizon: tuple[str, ...]
    initial_techniques: tuple[str, ...]
    initial_salience: tuple[tuple[str, float], ...]
    authority_tier: int
    capabilities: tuple[str, ...]
    relationship_state: str  # JSON representation of initial relationship state
    code_config_digest: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "agent_id": self.agent_id,
            "genesis_mode": self.genesis_mode.value,
            "objective": self.objective,
            "initial_horizon": list(self.initial_horizon),
            "initial_techniques": list(self.initial_techniques),
            "initial_salience": dict(self.initial_salience),
            "authority_tier": self.authority_tier,
            "capabilities": list(self.capabilities),
            "relationship_state": self.relationship_state,
            "code_config_digest": self.code_config_digest,
            "created_at": self.created_at,
        }

    @classmethod
    def create(
        cls,
        agent_id: str,
        genesis_mode: GenesisMode,
        objective: str,
        initial_horizon: Sequence[str],
        initial_salience: dict[str, float],
        authority_tier: int = 0,
        initial_techniques: Sequence[str] = (),
    ) -> GenesisSnapshot:
        sid = f"a0-{uuid.uuid4().hex[:8]}"
        salience_tuple = tuple(sorted(initial_salience.items()))
        horizon_tuple = tuple(sorted(initial_horizon))
        techniques_tuple = tuple(sorted(initial_techniques))
        
        # Digest of initial config
        raw_bytes = json.dumps({
            "mode": genesis_mode.value,
            "objective": objective,
            "horizon": horizon_tuple,
            "salience": salience_tuple,
            "authority": authority_tier,
        }, sort_keys=True).encode("utf-8")
        digest = hashlib.sha256(raw_bytes).hexdigest()

        return cls(
            snapshot_id=sid,
            agent_id=agent_id,
            genesis_mode=genesis_mode,
            objective=objective,
            initial_horizon=horizon_tuple,
            initial_techniques=techniques_tuple,
            initial_salience=salience_tuple,
            authority_tier=authority_tier,
            capabilities=(),
            relationship_state="{}",
            code_config_digest=digest,
        )


@dataclass
class ExecutionAuthority:
    """Bounded execution authority adhering to the 3-Tier Reversibility Matrix."""
    tier: int = 0
    max_permitted_tier: int = 0
    permitted_scopes: tuple[str, ...] = ("situated_encounter",)
    sovereign_delegation_key: Optional[str] = None

    def can_execute_tier(self, tier: int) -> bool:
        return tier <= self.tier

    def elevate(self, new_tier: int, sovereign_key: str) -> None:
        """Elevates execution tier ONLY if authorized by external sovereign key."""
        if not sovereign_key or sovereign_key != self.sovereign_delegation_key:
            raise UnauthorizedAuthorityExpansionError(
                f"Cannot elevate authority to Tier {new_tier}: invalid or missing sovereign key"
            )
        self.tier = new_tier
        if new_tier > self.max_permitted_tier:
            self.max_permitted_tier = new_tier


class ReceiptLaunderingError(Rejected):
    """Raised when an invalid, non-authoritative, or causally unlinked receipt is supplied to ground a belief."""
    def __init__(self, message: str = "Receipt fails causal binding to proposition"):
        super().__init__(
            message=message,
            rejection_class="HARD_INVARIANT_VIOLATION",
            details={"invariant": "RECEIPT_LAUNDERING_PROHIBITED"}
        )


@dataclass
class GroundReceipt:
    """An authoritative physical receipt establishing causal ground truth."""
    receipt_id: str
    proposition_digest: str  # SHA-256 digest of normalized statement
    authoritative_source: str  # Engine transaction / physical assert source
    timestamp: float = field(default_factory=time.time)
    stale_after: Optional[float] = None
    is_valid: bool = True

    def verify_supports_proposition(self, proposition: str, current_time: Optional[float] = None) -> bool:
        if not self.is_valid:
            return False
        now = current_time if current_time is not None else time.time()
        if self.stale_after and now > self.stale_after:
            return False
        expected_digest = hashlib.sha256(proposition.strip().lower().encode("utf-8")).hexdigest()
        return self.proposition_digest == expected_digest


def create_ground_receipt(statement: str, source: str = "engine") -> str:
    """Creates a verifiable engine receipt digest strictly bound to statement."""
    digest = hashlib.sha256(statement.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"tx-receipt:{source}:{digest}"


@dataclass
class Belief:
    """An internal epistemic hypothesis. Model inference != Ground."""
    belief_id: str
    statement: str
    epistemic_status: EpistemicDistinction = EpistemicDistinction.BELIEF_UNVERIFIED
    confidence: float = 0.5
    supporting_evidence: list[str] = field(default_factory=list)
    is_model_inference: bool = True
    ground_receipt_ref: Optional[str] = None

    def ground(
        self,
        receipt: str | GroundReceipt,
        statement_verifier: Optional[Callable[[str, str], bool]] = None,
        authoritative_receipts: Optional[dict[str, GroundReceipt]] = None,
    ) -> bool:
        """Promotes belief to Ground only when bound to an authoritative, verifiable receipt
        that causally supports THIS proposition. Eliminates the receipt laundering boundary:
        [some transaction receipt] !=> [this proposition is Ground].
        """
        # 1. GroundReceipt object validation
        if isinstance(receipt, GroundReceipt):
            if not receipt.verify_supports_proposition(self.statement):
                raise ReceiptLaunderingError(
                    f"Receipt '{receipt.receipt_id}' does not causally support proposition '{self.statement}'"
                )
            self.ground_receipt_ref = receipt.receipt_id
            self.epistemic_status = EpistemicDistinction.REALITY_GROUND
            self.is_model_inference = False
            self.confidence = 1.0
            return True

        # 2. Receipt reference string validation
        receipt_ref = receipt
        if not receipt_ref or not isinstance(receipt_ref, str) or not receipt_ref.startswith("tx-receipt:"):
            raise ReceiptLaunderingError(f"Receipt ref '{receipt_ref}' lacks authoritative engine format")

        if authoritative_receipts is not None:
            actual = authoritative_receipts.get(receipt_ref)
            if not actual or not actual.verify_supports_proposition(self.statement):
                raise ReceiptLaunderingError(
                    f"Receipt '{receipt_ref}' not authoritative or proposition mismatch for '{self.statement}'"
                )
        elif statement_verifier is not None:
            if not statement_verifier(self.statement, receipt_ref):
                raise ReceiptLaunderingError(
                    f"Verifier rejected proposition-receipt binding for '{self.statement}' with '{receipt_ref}'"
                )
        else:
            # Enforce structural semantic binding: tx-receipt:<source>:<digest>
            parts = receipt_ref.split(":")
            if len(parts) < 3 or not parts[1] or not parts[2]:
                raise ReceiptLaunderingError(
                    f"Receipt '{receipt_ref}' lacks structural source:digest binding for proposition '{self.statement}'"
                )
            expected = hashlib.sha256(self.statement.strip().lower().encode("utf-8")).hexdigest()[:len(parts[2])]
            if len(parts[2]) >= 6 and parts[2] != expected:
                raise ReceiptLaunderingError(
                    f"Receipt digest '{parts[2]}' does not match proposition digest '{expected}' for '{self.statement}'"
                )

        self.ground_receipt_ref = receipt_ref
        self.epistemic_status = EpistemicDistinction.REALITY_GROUND
        self.is_model_inference = False
        self.confidence = 1.0
        return True


@dataclass
class SalienceVector:
    """Dynamic salience directing attention across features, hazards, and affordances."""
    weights: dict[str, float] = field(default_factory=lambda: {
        "environmental_hazards": 0.30,
        "physical_affordances": 0.30,
        "social_presence": 0.20,
        "unexplored_frontiers": 0.20,
    })

    def adjust(self, dimension: str, delta: float) -> None:
        current = self.weights.get(dimension, 0.20)
        self.weights[dimension] = max(0.01, min(1.0, current + delta))
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: round(v / total, 4) for k, v in self.weights.items()}

    def get_salience(self, dimension: str) -> float:
        return self.weights.get(dimension, 0.0)


@dataclass
class TechniqueLineage:
    """#27 Technique Lineage: Full provenance and ancestry."""
    generator: str
    origin_encounter: str
    holder: str
    contributors: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    qualification_scope: CapabilityOwnership = CapabilityOwnership.SELF
    limits: dict[str, Any] = field(default_factory=dict)
    descendants: list[str] = field(default_factory=list)
    status: CapabilityState = CapabilityState.QUALIFIED

    def create_descendant(self, new_holder: str, adaptation_evidence: str, new_limits: Optional[dict[str, Any]] = None) -> TechniqueLineage:
        """Transfer creates a descendant: T_A -> T'_B, NOT an identical copy."""
        desc_id = f"desc-{uuid.uuid4().hex[:8]}"
        self.descendants.append(desc_id)
        return TechniqueLineage(
            generator=self.generator,
            origin_encounter=adaptation_evidence,
            holder=new_holder,
            contributors=list(set(self.contributors + [self.holder])),
            parents=[self.generator],
            prerequisites=list(self.prerequisites),
            evidence=[adaptation_evidence],
            qualification_scope=CapabilityOwnership.SELF,
            limits=new_limits or copy.deepcopy(self.limits),
            descendants=[],
            status=CapabilityState.CANDIDATE,  # Transferred technique must be re-qualified!
        )


@dataclass
class CandidateTechnique:
    """A regular invariant pattern observed from work. Candidate Technique != Acquired Technique."""
    candidate_id: str
    name: str
    description: str
    invariant_generator: str
    extracted_from_encounter: str
    state: CapabilityState = CapabilityState.CANDIDATE
    owner_scope: CapabilityOwnership = CapabilityOwnership.SELF
    lineage: Optional[TechniqueLineage] = None
    qualification_trials_passed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "description": self.description,
            "invariant_generator": self.invariant_generator,
            "extracted_from_encounter": self.extracted_from_encounter,
            "state": self.state.value,
            "owner_scope": self.owner_scope.value,
            "qualification_trials_passed": self.qualification_trials_passed,
        }


@dataclass
class QualifiedTechnique:
    """An acquired operational technique backed by physical qualification receipts."""
    technique_id: str
    name: str
    candidate_id: str
    qualification_receipts: list[dict[str, Any]]
    lineage: TechniqueLineage
    owner_scope: CapabilityOwnership = CapabilityOwnership.SELF
    state: CapabilityState = CapabilityState.QUALIFIED
    proficiency: float = 1.0
    acquired_at: float = field(default_factory=time.time)

    def demote(self, reason: str) -> None:
        """Demotes technique when prerequisites are removed (#11, #42)."""
        self.state = CapabilityState.SUSPENDED
        self.proficiency = 0.0

    def invalidate(self, reason: str) -> None:
        """Invalidates technique permanently if fundamental invariant is broken."""
        self.state = CapabilityState.INVALIDATED
        self.proficiency = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "technique_id": self.technique_id,
            "name": self.name,
            "candidate_id": self.candidate_id,
            "qualification_receipts": copy.deepcopy(self.qualification_receipts),
            "owner_scope": self.owner_scope.value,
            "state": self.state.value,
            "proficiency": self.proficiency,
            "acquired_at": self.acquired_at,
        }


@dataclass
class RelationalCapability:
    """A capability emerging strictly from an A × B coupling. Qualification(A) != Qualification(A × B)."""
    relationship_id: str
    partner_id: str
    joint_verb: str
    description: str
    prerequisites: tuple[str, ...]
    qualification_id: Optional[str] = None
    state: CapabilityState = CapabilityState.RELATIONAL
    owner_scope: CapabilityOwnership = CapabilityOwnership.RELATIONSHIP
    is_active: bool = True

    def can_exercise_alone(self) -> bool:
        """Relational capability CANNOT be exercised by participant A in isolation."""
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "partner_id": self.partner_id,
            "joint_verb": self.joint_verb,
            "description": self.description,
            "prerequisites": list(self.prerequisites),
            "qualification_id": self.qualification_id,
            "state": self.state.value,
            "owner_scope": self.owner_scope.value,
            "is_active": self.is_active,
            "can_exercise_alone": False,
        }


@dataclass
class RelationshipState:
    """#28 Relational Development: Persists non-scalar structural relationship history."""
    relationship_id: str
    participants: tuple[str, str]
    consequential_history: list[dict[str, Any]] = field(default_factory=list)
    complementarities: dict[str, str] = field(default_factory=dict)
    tensions: dict[str, str] = field(default_factory=dict)
    failed_couplings: list[dict[str, Any]] = field(default_factory=list)
    residue: list[dict[str, Any]] = field(default_factory=list)
    relational_techniques: dict[str, RelationalCapability] = field(default_factory=dict)

    def record_interaction(
        self,
        encounter_id: str,
        complementarity: Optional[tuple[str, str]] = None,
        tension: Optional[tuple[str, str]] = None,
        failed_coupling: Optional[dict[str, Any]] = None,
        relational_residue: Optional[dict[str, Any]] = None,
    ) -> None:
        """Updates relational state without any scalar 'trust score'."""
        self.consequential_history.append({"encounter_id": encounter_id, "timestamp": time.time()})
        if complementarity:
            self.complementarities[complementarity[0]] = complementarity[1]
        if tension:
            self.tensions[tension[0]] = tension[1]
        if failed_coupling:
            self.failed_couplings.append(failed_coupling)
        if relational_residue:
            self.residue.append(relational_residue)


@dataclass
class CouncilCoupling:
    """#30 Council: Temporary coupling of differentiated participants."""
    council_id: str
    participants: list[str]
    differentiated_perspectives: dict[str, str]
    objective: str
    active: bool = True
    is_multi_perspective_single_model: bool = False

    def exercise_council_capability(self, verb: str) -> dict[str, Any]:
        return {
            "council_id": self.council_id,
            "verb": verb,
            "participants": list(self.participants),
            "status": "exercised_by_council",
        }


@dataclass
class CrossHostCapabilityProfile:
    """#38 Defeasible capability model of external hosts."""
    host_name: str
    observed_strengths: list[str] = field(default_factory=list)
    observed_limitations: list[str] = field(default_factory=list)
    last_context_observed: Optional[str] = None
    observation_count: int = 0

    def update_observation(self, strength: Optional[str] = None, limitation: Optional[str] = None, context: Optional[str] = None) -> None:
        self.observation_count += 1
        self.last_context_observed = context
        if strength and strength not in self.observed_strengths:
            self.observed_strengths.append(strength)
        if limitation and limitation not in self.observed_limitations:
            self.observed_limitations.append(limitation)


@dataclass
class DevelopmentalDelta:
    """#12 Provenance on Every Developmental Delta.
    Must answer: WHAT changed? FROM what state? BECAUSE OF which encounter?
    WHO interpreted? WHAT verifier? WHAT future behavior changed?
    """
    what_changed: dict[str, Any] = field(default_factory=dict)
    from_state: dict[str, Any] = field(default_factory=dict)
    because_of_encounter: str = "unspecified"
    interpreter: str = "agent"  # 'agent' vs 'harness'
    verifier_ref: str = "unverified"
    future_behavior_delta: str = "none"
    causal_attribution_resolved: bool = True

    # Legacy convenience containers
    salience_delta: dict[str, float] = field(default_factory=dict)
    beliefs_added: list[str] = field(default_factory=list)
    beliefs_invalidated: list[str] = field(default_factory=list)
    reachability_expanded: list[str] = field(default_factory=list)
    reachability_pruned: list[str] = field(default_factory=list)
    techniques_acquired: list[str] = field(default_factory=list)
    techniques_demoted: list[str] = field(default_factory=list)
    scars_acquired: list[str] = field(default_factory=list)
    relationships_formed: list[str] = field(default_factory=list)
    relationship_deltas: list[str] = field(default_factory=list)

    @property
    def has_development(self) -> bool:
        """Returns True iff structural difference exists AND causal attribution is resolved."""
        structural_difference = bool(
            self.what_changed
            or self.salience_delta
            or self.beliefs_added
            or self.beliefs_invalidated
            or self.reachability_expanded
            or self.reachability_pruned
            or self.techniques_acquired
            or self.techniques_demoted
            or self.scars_acquired
            or self.relationships_formed
            or self.relationship_deltas
        )
        return structural_difference and self.causal_attribution_resolved

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_development": self.has_development,
            "what_changed": copy.deepcopy(self.what_changed),
            "from_state": copy.deepcopy(self.from_state),
            "because_of_encounter": self.because_of_encounter,
            "interpreter": self.interpreter,
            "verifier_ref": self.verifier_ref,
            "future_behavior_delta": self.future_behavior_delta,
            "causal_attribution_resolved": self.causal_attribution_resolved,
            "salience_delta": copy.deepcopy(self.salience_delta),
            "beliefs_added": list(self.beliefs_added),
            "beliefs_invalidated": list(self.beliefs_invalidated),
            "reachability_expanded": list(self.reachability_expanded),
            "reachability_pruned": list(self.reachability_pruned),
            "techniques_acquired": list(self.techniques_acquired),
            "techniques_demoted": list(self.techniques_demoted),
            "scars_acquired": list(self.scars_acquired),
            "relationships_formed": list(self.relationships_formed),
            "relationship_deltas": list(self.relationship_deltas),
        }


@dataclass
class DevelopmentalStep:
    """An encounter step in the agent's developmental ledger."""
    encounter_id: str
    origin: EncounterOrigin
    action_taken: str
    target: Optional[str]
    raw_outcome: dict[str, Any]
    metabolism_class: MetabolismCategory
    delta: DevelopmentalDelta
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "encounter_id": self.encounter_id,
            "origin": self.origin.value,
            "action_taken": self.action_taken,
            "target": self.target,
            "raw_outcome": copy.deepcopy(self.raw_outcome),
            "metabolism_class": self.metabolism_class.value,
            "delta": self.delta.to_dict(),
            "timestamp": self.timestamp,
        }


# =============================================================================
# ECOLOGICAL & SYMBIOGENESIS CONTRACTS
# =============================================================================

class EcologicalPrimitive(str, Enum):
    """Core primitives for ecological representation in Symbiogenesis."""
    PARTICIPANT = "PARTICIPANT"
    DIFFERENCE = "DIFFERENCE"
    RELATIONSHIP = "RELATIONSHIP"
    BOUNDARY = "BOUNDARY"
    NICHE = "NICHE"
    PRESSURE = "PRESSURE"
    AFFORDANCE = "AFFORDANCE"
    RESIDUE = "RESIDUE"
    CAPABILITY = "CAPABILITY"
    HISTORY = "HISTORY"


@dataclass
class DifferenceRecord:
    """Order 5 Differentiation: History-produced difference as potential energy."""
    dimension: str
    participant_a: str
    participant_b: str
    delta_description: str
    potential_energy: float = 1.0
    complementarity_hypothesis: str = "untested"

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "participant_a": self.participant_a,
            "participant_b": self.participant_b,
            "delta_description": self.delta_description,
            "potential_energy": self.potential_energy,
            "complementarity_hypothesis": self.complementarity_hypothesis,
        }


@dataclass
class NicheConfiguration:
    """A bounded configuration altering conditions so new capability can emerge.
    Alters: participants, visible boundaries, shared affordances, and pressures.
    DOES NOT directly grant the target technique.
    """
    niche_id: str
    name: str
    participants: tuple[str, ...]
    copresent_differences: list[DifferenceRecord] = field(default_factory=list)
    visibility_boundaries: dict[str, list[str]] = field(default_factory=dict)
    shared_affordances: list[str] = field(default_factory=list)
    coexisting_pressures: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    private_affordances: dict[str, list[str]] = field(default_factory=dict)
    active: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "niche_id": self.niche_id,
            "name": self.name,
            "participants": list(self.participants),
            "copresent_differences": [d.to_dict() for d in self.copresent_differences],
            "visibility_boundaries": copy.deepcopy(self.visibility_boundaries),
            "shared_affordances": list(self.shared_affordances),
            "coexisting_pressures": list(self.coexisting_pressures),
            "constraints": list(self.constraints),
            "private_affordances": copy.deepcopy(self.private_affordances),
            "active": self.active,
            "created_at": self.created_at,
        }


@dataclass
class EcologicalMemoryRecord:
    """Non-generic ecological persistence recording actual interaction conditions and consequences."""
    record_id: str
    niche_id: str
    participants: tuple[str, ...]
    differences_present: list[dict[str, Any]] = field(default_factory=list)
    pressures: list[str] = field(default_factory=list)
    unexpected_consequences: list[dict[str, Any]] = field(default_factory=list)
    capabilities_appeared: list[str] = field(default_factory=list)
    capabilities_disappeared: list[str] = field(default_factory=list)
    residue: list[dict[str, Any]] = field(default_factory=list)
    failed_configurations: list[dict[str, Any]] = field(default_factory=list)
    causal_ablations: list[dict[str, Any]] = field(default_factory=list)
    environmental_prerequisites: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "niche_id": self.niche_id,
            "participants": list(self.participants),
            "differences_present": copy.deepcopy(self.differences_present),
            "pressures": list(self.pressures),
            "unexpected_consequences": copy.deepcopy(self.unexpected_consequences),
            "capabilities_appeared": list(self.capabilities_appeared),
            "capabilities_disappeared": list(self.capabilities_disappeared),
            "residue": copy.deepcopy(self.residue),
            "failed_configurations": copy.deepcopy(self.failed_configurations),
            "causal_ablations": copy.deepcopy(self.causal_ablations),
            "environmental_prerequisites": list(self.environmental_prerequisites),
            "timestamp": self.timestamp,
        }


@dataclass
class CandidateGenerator:
    """Order 7 Generator Discovery: Recurring invariant structural pattern extracted AFTER encounter."""
    generator_id: str
    name: str
    description: str
    structural_pattern: str
    source_niche_id: str
    required_differences: list[str] = field(default_factory=list)
    resulting_capability_name: str = "unspecified"
    invariants: dict[str, Any] = field(default_factory=dict)
    qualification_passed: bool = False
    discovered_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generator_id": self.generator_id,
            "name": self.name,
            "description": self.description,
            "structural_pattern": self.structural_pattern,
            "source_niche_id": self.source_niche_id,
            "required_differences": list(self.required_differences),
            "resulting_capability_name": self.resulting_capability_name,
            "invariants": copy.deepcopy(self.invariants),
            "qualification_passed": self.qualification_passed,
            "discovered_at": self.discovered_at,
        }


@dataclass
class NicheAblationResult:
    """Results of the 4-way counterfactual ablation test establishing capability ownership."""
    niche_id: str
    intact_success: bool
    ablate_history_success: bool
    ablate_relationship_success: bool
    ablate_niche_success: bool
    restored_success: bool
    assigned_ownership: CapabilityOwnership
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "niche_id": self.niche_id,
            "intact_success": self.intact_success,
            "ablate_history_success": self.ablate_history_success,
            "ablate_relationship_success": self.ablate_relationship_success,
            "ablate_niche_success": self.ablate_niche_success,
            "restored_success": self.restored_success,
            "assigned_ownership": self.assigned_ownership.value,
            "details": copy.deepcopy(self.details),
        }


# =============================================================================
# APEX OPEN-CEILING CONTRACTS
# =============================================================================

class ArchaeologyClassification(str, Enum):
    """Archaeology status of an existing structure across the reachable ecology."""
    EXISTS_CONNECTED = "EXISTS_CONNECTED"
    EXISTS_DISCONNECTED = "EXISTS_DISCONNECTED"
    PARTIALLY_CONNECTED = "PARTIALLY_CONNECTED"
    REPRESENTATION_MISMATCH = "REPRESENTATION_MISMATCH"
    QUALIFIED_BUT_UNAVAILABLE = "QUALIFIED_BUT_UNAVAILABLE"
    AVAILABLE_BUT_UNKNOWN = "AVAILABLE_BUT_UNKNOWN"
    RELATIONAL_ONLY = "RELATIONAL_ONLY"
    NICHE_ONLY = "NICHE_ONLY"
    HOST_ONLY = "HOST_ONLY"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    ACTUALLY_ABSENT = "ACTUALLY_ABSENT"


class ArchaeologyPreference(str, Enum):
    """Archaeology action preference order: Creation is last!"""
    REUSE = "REUSE"
    RECONNECT = "RECONNECT"
    RECOMPOSE = "RECOMPOSE"
    ADAPT = "ADAPT"
    CREATE = "CREATE"


@dataclass
class ArchaeologyRecord:
    """Archaeological recovery record documenting an existing capability."""
    target_capability: str
    source_location: str
    classification: ArchaeologyClassification
    action_chosen: ArchaeologyPreference
    recovered_status: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_capability": self.target_capability,
            "source_location": self.source_location,
            "classification": self.classification.value,
            "action_chosen": self.action_chosen.value,
            "recovered_status": copy.deepcopy(self.recovered_status),
            "timestamp": self.timestamp,
        }


class ExposureOperation(str, Enum):
    """Selective exposure operators: Difference requires selective isolation."""
    EXPOSE = "EXPOSE"
    ISOLATE = "ISOLATE"
    BLIND = "BLIND"
    PARTIAL_CONTEXT = "PARTIAL_CONTEXT"
    COUPLE = "COUPLE"
    DECOUPLE = "DECOUPLE"
    DELAY = "DELAY"
    RETURN_TO_GROUND = "RETURN_TO_GROUND"
    RETURN_TO_LEVI = "RETURN_TO_LEVI"
    DO_NOTHING = "DO_NOTHING"


class ReificationTarget(str, Enum):
    """Selective reification transformations: What must this become?"""
    INTUITION_TO_CLAIM = "intuition -> claim"
    CLAIM_TO_PROBE = "claim -> probe"
    EXPERIENCE_TO_WORLD = "experience -> world"
    DIFFERENCE_TO_RELATIONSHIP = "difference -> relationship"
    RELATIONSHIP_TO_TECHNIQUE = "relationship -> technique"
    RESIDUE_TO_QUESTION = "residue -> question"
    METHOD_TO_SKILL = "method -> skill"
    SKILL_TO_AGENT = "skill -> agent"
    AGENTS_TO_COUNCIL = "agents -> Council"
    COUNCIL_TO_GENERATOR = "Council -> generator"
    GENERATOR_TO_AFFORDANCE = "generator -> affordance"
    ARCHITECTURE_TO_EXPERIMENT = "architecture -> executable experiment"


@dataclass
class FrontierState:
    """A frontier: Objective + Reachable + Resistance + Unresolved Gap."""
    frontier_id: str
    objective: str
    current_reachable: list[str]
    observed_resistance: str
    unresolved_gap: str
    identified_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "frontier_id": self.frontier_id,
            "objective": self.objective,
            "current_reachable": list(self.current_reachable),
            "observed_resistance": self.observed_resistance,
            "unresolved_gap": self.unresolved_gap,
            "identified_at": self.identified_at,
        }


@dataclass
class RepresentationState:
    """Active cognitive ontology/representation framing."""
    representation_id: str
    framing: str
    primitives: tuple[str, ...]
    active: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "representation_id": self.representation_id,
            "framing": self.framing,
            "primitives": list(self.primitives),
            "active": self.active,
            "created_at": self.created_at,
        }


@dataclass
class RepresentationDelta:
    """Escape from representation R to R' when legitimate actions fail."""
    delta_id: str
    old_representation_id: str
    new_representation_id: str
    newly_reachable_capabilities: list[str]
    retired_primitives: list[str]
    justification: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "delta_id": self.delta_id,
            "old_representation_id": self.old_representation_id,
            "new_representation_id": self.new_representation_id,
            "newly_reachable_capabilities": list(self.newly_reachable_capabilities),
            "retired_primitives": list(self.retired_primitives),
            "justification": self.justification,
            "timestamp": self.timestamp,
        }


@dataclass
class AscendedGenerator:
    """Order-Ascended Generator G* discovered recursively across generators G1, G2, G3."""
    ascended_id: str
    sub_generators: list[str]
    shared_transformation: str
    predictive_hypothesis: str
    unseen_domain_tested: str = ""
    qualification_passed: bool = False
    discovered_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ascended_id": self.ascended_id,
            "sub_generators": list(self.sub_generators),
            "shared_transformation": self.shared_transformation,
            "predictive_hypothesis": self.predictive_hypothesis,
            "unseen_domain_tested": self.unseen_domain_tested,
            "qualification_passed": self.qualification_passed,
            "discovered_at": self.discovered_at,
        }
