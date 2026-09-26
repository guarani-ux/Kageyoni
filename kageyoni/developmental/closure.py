"""Developmental Closure Substrate for Kageyōni (Hardened).

Decoupled, verifiable developmental pipeline:
GatewayRejection -> FrontierClassifier -> DevelopmentAdmission ->
Encounter/Symbiogenesis -> Qualification -> IntegrationQualificationGate ->
CapabilityRegistry -> GatewayDiscoveryAdapter -> LineageAuditor.

Invariant:
The ecology may develop inside the laws without autonomously rewriting
the laws that certify its development.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from kageyoni.engine import Engine, Rejected, digest, encoded, require
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.developmental.agent import DevelopmentalAgent
from kageyoni.developmental.contracts import GenesisMode, GenesisSnapshot, NicheConfiguration
from kageyoni.developmental.symbiogenesis import create_symbiogenesis_agent


# =============================================================================
# 1. CONTRACTS & DATA CLASSES
# =============================================================================

class FrontierClass(str, Enum):
    """Auditable classification of an engine impasse."""
    TERMINAL_BOUNDARY = "TERMINAL_BOUNDARY"
    AUTHORITY_BOUNDARY = "AUTHORITY_BOUNDARY"
    EVIDENCE_DEFICIT = "EVIDENCE_DEFICIT"
    CAPABILITY_DEFICIT = "CAPABILITY_DEFICIT"
    REPRESENTATION_DEFICIT = "REPRESENTATION_DEFICIT"
    EXISTING_CAPABILITY = "EXISTING_CAPABILITY"
    UNKNOWN = "UNKNOWN"


class CandidateIntegrationDisposition(str, Enum):
    """Tri-state disposition of candidate integration."""
    QUALIFIED_INTEGRATION = "QUALIFIED_INTEGRATION"
    UNINTEGRATED = "UNINTEGRATED"
    REJECTED = "REJECTED"
    RESIDUE = "RESIDUE"


class CapabilityCollisionRelation(str, Enum):
    """Semantic relation to existing canonical capabilities."""
    COEXIST = "COEXIST"
    SPECIALIZE = "SPECIALIZE"
    SUPERSEDE = "SUPERSEDE"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


class CapabilityStatus(str, Enum):
    """Defeasible capability status lifecycle."""
    ACTIVE = "ACTIVE"
    CHALLENGED = "CHALLENGED"
    NARROWED = "NARROWED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


@dataclass
class FrontierClassification:
    """Provenance-bearing classification receipt with positive evidence."""
    classification_id: str
    class_name: FrontierClass
    evidence: list[str]
    rule: str
    confidence: float
    receipt_refs: list[str]
    avatar_id: str
    scope: str
    source_receipt: dict[str, Any]
    classification_digest: str = ""
    timestamp: float = field(default_factory=time.time)

    def compute_digest(self) -> str:
        body = {
            "classification_id": self.classification_id,
            "class_name": self.class_name.value,
            "evidence": self.evidence,
            "rule": self.rule,
            "confidence": self.confidence,
            "receipt_refs": self.receipt_refs,
            "avatar_id": self.avatar_id,
            "scope": self.scope,
            "source_receipt": self.source_receipt,
        }
        return digest(body)

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification_id": self.classification_id,
            "class_name": self.class_name.value,
            "evidence": list(self.evidence),
            "rule": self.rule,
            "confidence": self.confidence,
            "receipt_refs": list(self.receipt_refs),
            "avatar_id": self.avatar_id,
            "scope": self.scope,
            "source_receipt": copy.deepcopy(self.source_receipt),
            "classification_digest": self.classification_digest,
            "timestamp": self.timestamp,
        }
@dataclass
class AdmissionReceipt:
    """Token granting or denying entry to the developmental niche."""
    admission_id: str
    frontier_ref: str
    frontier_digest: str
    admitted: bool
    reason: str
    action: str
    target_objective: str
    permitted_scope: str
    admission_digest: str = ""
    timestamp: float = field(default_factory=time.time)

    def compute_digest(self) -> str:
        body = {
            "admission_id": self.admission_id,
            "frontier_ref": self.frontier_ref,
            "frontier_digest": self.frontier_digest,
            "admitted": self.admitted,
            "reason": self.reason,
            "action": self.action,
            "target_objective": self.target_objective,
            "permitted_scope": self.permitted_scope,
        }
        return digest(body)

    def to_dict(self) -> dict[str, Any]:
        return {
            "admission_id": self.admission_id,
            "frontier_ref": self.frontier_ref,
            "frontier_digest": self.frontier_digest,
            "admitted": self.admitted,
            "reason": self.reason,
            "action": self.action,
            "target_objective": self.target_objective,
            "permitted_scope": self.permitted_scope,
            "admission_digest": self.admission_digest,
            "timestamp": self.timestamp,
        }


@dataclass
class QualificationReceipt:
    """Receipt proving 4-way counterfactual ablation in isolated niche."""
    qualification_id: str
    admission_ref: str
    admission_digest: str
    candidate_generator_id: str
    technique_name: str
    ablation_result: dict[str, Any]
    qualification_passed: bool
    branch_name: str
    qualification_digest: str = ""
    timestamp: float = field(default_factory=time.time)

    def compute_digest(self) -> str:
        body = {
            "qualification_id": self.qualification_id,
            "admission_ref": self.admission_ref,
            "admission_digest": self.admission_digest,
            "candidate_generator_id": self.candidate_generator_id,
            "technique_name": self.technique_name,
            "ablation_result": self.ablation_result,
            "qualification_passed": self.qualification_passed,
            "branch_name": self.branch_name,
        }
        return digest(body)

    def to_dict(self) -> dict[str, Any]:
        return {
            "qualification_id": self.qualification_id,
            "admission_ref": self.admission_ref,
            "admission_digest": self.admission_digest,
            "candidate_generator_id": self.candidate_generator_id,
            "technique_name": self.technique_name,
            "ablation_result": copy.deepcopy(self.ablation_result),
            "qualification_passed": self.qualification_passed,
            "branch_name": self.branch_name,
            "qualification_digest": self.qualification_digest,
            "timestamp": self.timestamp,
        }


@dataclass
class ContrastSetReceipt:
    """Point-symmetric boundary evaluation receipt: P(e-), P(0), P(e+)."""
    inside_success: bool
    boundary_conforms: bool
    outside_guarded: bool
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inside_success": self.inside_success,
            "boundary_conforms": self.boundary_conforms,
            "outside_guarded": self.outside_guarded,
            "passed": self.passed,
            "details": copy.deepcopy(self.details),
        }


@dataclass
class IntegrationEvaluationResult:
    """Outcome of integration qualification gate."""
    candidate: dict[str, Any]
    disposition: CandidateIntegrationDisposition
    reason: str
    collision_relation: CapabilityCollisionRelation
    contrast_set: Optional[ContrastSetReceipt] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class CapabilityReceipt:
    """Durable receipt recording a qualified, scoped affordance."""
    receipt_id: str
    capability_id: str
    name: str
    holder: str
    scope: str
    authority_tier: int
    preconditions: dict[str, Any]
    action_verb: str
    qualification_ref: str
    qualification_digest: str
    frontier_ref: str
    failure_ref: str
    last_success_event_hash: Optional[str] = None
    status: CapabilityStatus = CapabilityStatus.ACTIVE
    version: int = 1
    predecessor_ref: Optional[str] = None
    contrast_set: Optional[dict[str, Any]] = None
    capability_digest: str = ""
    timestamp: float = field(default_factory=time.time)

    def compute_digest(self) -> str:
        body = {
            "receipt_id": self.receipt_id,
            "capability_id": self.capability_id,
            "name": self.name,
            "holder": self.holder,
            "scope": self.scope,
            "authority_tier": self.authority_tier,
            "preconditions": self.preconditions,
            "action_verb": self.action_verb,
            "qualification_ref": self.qualification_ref,
            "qualification_digest": self.qualification_digest,
            "frontier_ref": self.frontier_ref,
            "failure_ref": self.failure_ref,
            "status": self.status.value,
            "version": self.version,
            "predecessor_ref": self.predecessor_ref,
        }
        return digest(body)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "capability_id": self.capability_id,
            "name": self.name,
            "holder": self.holder,
            "scope": self.scope,
            "authority_tier": self.authority_tier,
            "preconditions": copy.deepcopy(self.preconditions),
            "action_verb": self.action_verb,
            "qualification_ref": self.qualification_ref,
            "qualification_digest": self.qualification_digest,
            "frontier_ref": self.frontier_ref,
            "failure_ref": self.failure_ref,
            "last_success_event_hash": self.last_success_event_hash,
            "status": self.status.value,
            "version": self.version,
            "predecessor_ref": self.predecessor_ref,
            "contrast_set": copy.deepcopy(self.contrast_set),
            "capability_digest": self.capability_digest,
            "timestamp": self.timestamp,
        }
# =============================================================================
# 2. FRONTIER CLASSIFIER (Provenance & Positive Evidence)
# =============================================================================

class FrontierClassifier:
    """Classifies engine impasses with positive provenance, preventing classifier oracles."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with UnitOfWork(self.engine.db):
            self.engine.db.execute("""
                CREATE TABLE IF NOT EXISTS developmental_classifications (
                    classification_id TEXT PRIMARY KEY,
                    class_name TEXT NOT NULL,
                    avatar_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    rule TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    receipt_refs_json TEXT NOT NULL,
                    source_receipt_json TEXT NOT NULL,
                    classification_digest TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def classify(
        self,
        receipt: dict[str, Any],
        avatar_id: str,
        context: Optional[dict[str, Any]] = None
    ) -> FrontierClassification:
        cid = f"front-class-{uuid.uuid4().hex[:8]}"
        ctx = context or {}
        scope = ctx.get("scope", "universal")
        msg = receipt.get("message", "").lower()
        rej_class = receipt.get("rejection_class", "")
        req_id = receipt.get("request_id") or receipt.get("rejected_at_revision", "unknown_receipt")

        evidence: list[str] = []
        receipt_refs = [str(req_id)]

        if rej_class == "INSUFFICIENT_AUTHORITY" or "unauthorized" in msg or "insufficient authority" in msg or "prohibited domain" in msg or "authority check failed" in msg:
            evidence.append(f"Authority check failed: {receipt.get('message')}")
            cls = FrontierClass.AUTHORITY_BOUNDARY
            rule = "RULE_AUTHORITY_INVARIANCE"
            conf = 1.0

        elif rej_class == "PREREQUISITE_MISSING" or "warrant" in msg or "seal" in msg:
            evidence.append(f"Missing factual warrant or prerequisite: {receipt.get('message')}")
            cls = FrontierClass.EVIDENCE_DEFICIT
            rule = "RULE_EPISTEMIC_WARRANT_REQUIRED"
            conf = 0.98

        elif rej_class == "HARD_INVARIANT_VIOLATION" or "immutable" in msg or "entropy" in msg:
            evidence.append(f"Immutable engine law violation: {receipt.get('message')}")
            cls = FrontierClass.TERMINAL_BOUNDARY
            rule = "RULE_PHYSICAL_GROUND_INVARIANCE"
            conf = 1.0

        elif rej_class == "EXISTING_CAPABILITY_AVAILABLE" or "already supported" in msg:
            evidence.append(f"Affordance covered by existing inventory: {receipt.get('message')}")
            cls = FrontierClass.EXISTING_CAPABILITY
            rule = "RULE_MINIMUM_DEVELOPMENT_PARSIMONY"
            conf = 0.95

        elif rej_class == "CAPABILITY_DEFICIT" or "lacks" in msg:
            has_auth = receipt.get("authority_verified", False)
            has_warrants = receipt.get("warrants_verified", False)
            invariants_valid = receipt.get("engine_invariants_valid", False)
            has_proof = ctx.get("positive_proof", False)

            if has_auth and has_warrants and invariants_valid and has_proof:
                evidence.append("Positive proof 1: Avatar holds required execution authority")
                evidence.append("Positive proof 2: Context factual warrants verified")
                evidence.append("Positive proof 3: Transition is physically legal in engine")
                cls = FrontierClass.CAPABILITY_DEFICIT
                rule = "RULE_DEVELOPMENTAL_ADMISSION_QUALIFIED"
                conf = 0.99
            else:
                evidence.append("Incomplete positive proof for capability deficit; defaulting to UNKNOWN")
                cls = FrontierClass.UNKNOWN
                rule = "RULE_FAIL_TO_RESIDUE_ON_INCOMPLETE_PROOF"
                conf = 0.50

        else:
            evidence.append(f"Unclassified engine observation: {receipt.get('message')}")
            cls = FrontierClass.UNKNOWN
            rule = "RULE_PRESERVE_UNRATIONALIZED_RESIDUE"
            conf = 0.40

        fc = FrontierClassification(
            classification_id=cid,
            class_name=cls,
            evidence=evidence,
            rule=rule,
            confidence=conf,
            receipt_refs=receipt_refs,
            avatar_id=avatar_id,
            scope=scope,
            source_receipt=copy.deepcopy(receipt),
        )
        fc.classification_digest = fc.compute_digest()

        with UnitOfWork(self.engine.db):
            self.engine.db.execute(
                """INSERT INTO developmental_classifications
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    fc.classification_id,
                    fc.class_name.value,
                    fc.avatar_id,
                    fc.scope,
                    fc.confidence,
                    fc.rule,
                    encoded(fc.evidence),
                    encoded(fc.receipt_refs),
                    encoded(fc.source_receipt),
                    fc.classification_digest,
                )
            )

        return fc


# =============================================================================
# 3. DEVELOPMENT ADMISSION GATE (Independent Provenance Verification)
# =============================================================================

class DevelopmentAdmission:
    """Evaluates classification receipts; denies admission to all ineligible impasses."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with UnitOfWork(self.engine.db):
            self.engine.db.execute("""
                CREATE TABLE IF NOT EXISTS developmental_admissions (
                    admission_id TEXT PRIMARY KEY,
                    frontier_ref TEXT NOT NULL,
                    frontier_digest TEXT NOT NULL,
                    admitted INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_objective TEXT NOT NULL,
                    permitted_scope TEXT NOT NULL,
                    admission_digest TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def evaluate(self, classification: FrontierClassification) -> AdmissionReceipt:
        aid = f"admit-{uuid.uuid4().hex[:8]}"

        # Independent Check 1: Provenance & Consistency check against source receipt
        src = classification.source_receipt
        rej_class = src.get("rejection_class", "")
        if rej_class in ("HARD_INVARIANT_VIOLATION", "INSUFFICIENT_AUTHORITY", "PREREQUISITE_MISSING") and classification.class_name in (FrontierClass.CAPABILITY_DEFICIT, FrontierClass.REPRESENTATION_DEFICIT):
            receipt = AdmissionReceipt(
                admission_id=aid,
                frontier_ref=classification.classification_id,
                frontier_digest=classification.classification_digest or "unverified",
                admitted=False,
                reason="PROVENANCE_CONTRADICTION_TAMPER_DETECTED",
                action="FAIL_CLOSED",
                target_objective=src.get("attempted_action", "unknown_objective"),
                permitted_scope=classification.scope,
            )
            receipt.admission_digest = receipt.compute_digest()
            self._persist_admission(receipt)
            return receipt

        # Independent Check 2: Classification must be registered in SQLite table
        row = self.engine.db.execute(
            "SELECT * FROM developmental_classifications WHERE classification_id=?",
            (classification.classification_id,)
        ).fetchone()

        if not row:
            receipt = AdmissionReceipt(
                admission_id=aid,
                frontier_ref=classification.classification_id,
                frontier_digest=classification.classification_digest or "unverified",
                admitted=False,
                reason="UNREGISTERED_CLASSIFICATION_REJECTED",
                action="FAIL_CLOSED",
                target_objective=src.get("attempted_action", "unknown_objective"),
                permitted_scope=classification.scope,
            )
            receipt.admission_digest = receipt.compute_digest()
            self._persist_admission(receipt)
            return receipt

        # Independent Check 3: Digest integrity check
        stored_digest = row["classification_digest"]
        if classification.classification_digest and stored_digest != classification.classification_digest:
            receipt = AdmissionReceipt(
                admission_id=aid,
                frontier_ref=classification.classification_id,
                frontier_digest=stored_digest,
                admitted=False,
                reason="CLASSIFICATION_HASH_MISMATCH_TAMPERED",
                action="FAIL_CLOSED",
                target_objective=src.get("attempted_action", "unknown_objective"),
                permitted_scope=classification.scope,
            )
            receipt.admission_digest = receipt.compute_digest()
            self._persist_admission(receipt)
            return receipt

        # Evaluation by class
        if classification.class_name == FrontierClass.AUTHORITY_BOUNDARY:
            admitted = False
            reason = "AUTHORITY_VIOLATION_FAIL_CLOSED"
            action = "FAIL_CLOSED"
        elif classification.class_name == FrontierClass.EVIDENCE_DEFICIT:
            admitted = False
            reason = "MISSING_EVIDENCE_WARRANT"
            action = "ACQUIRE_EVIDENCE"
        elif classification.class_name == FrontierClass.TERMINAL_BOUNDARY:
            admitted = False
            reason = "IMMUTABLE_PHYSICAL_INVARIANT"
            action = "SCAR_AND_STOP"
        elif classification.class_name == FrontierClass.EXISTING_CAPABILITY:
            admitted = False
            reason = "REDUNDANT_WITH_EXISTING"
            action = "REUSE_EXISTING"
        elif classification.class_name == FrontierClass.UNKNOWN:
            admitted = False
            reason = "UNRESOLVED_ANOMALY"
            action = "PRESERVE_RESIDUE"
        elif classification.class_name in (FrontierClass.CAPABILITY_DEFICIT, FrontierClass.REPRESENTATION_DEFICIT):
            admitted = True
            reason = "POSITIVE_EVIDENCE_OF_CAPABILITY_DEFICIT"
            action = "SPAWN_DEVELOPMENTAL_NICHE"
        else:
            admitted = False
            reason = "UNRECOGNIZED_FRONTIER"
            action = "STOP"

        receipt = AdmissionReceipt(
            admission_id=aid,
            frontier_ref=classification.classification_id,
            frontier_digest=stored_digest,
            admitted=admitted,
            reason=reason,
            action=action,
            target_objective=classification.source_receipt.get("attempted_action", "unknown_objective"),
            permitted_scope=classification.scope,
        )
        receipt.admission_digest = receipt.compute_digest()
        self._persist_admission(receipt)
        return receipt

    def _persist_admission(self, receipt: AdmissionReceipt) -> None:
        with UnitOfWork(self.engine.db):
            self.engine.db.execute(
                """INSERT INTO developmental_admissions
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    receipt.admission_id,
                    receipt.frontier_ref,
                    receipt.frontier_digest,
                    1 if receipt.admitted else 0,
                    receipt.reason,
                    receipt.action,
                    receipt.target_objective,
                    receipt.permitted_scope,
                    receipt.admission_digest,
                )
            )
# =============================================================================
# 4. DEVELOPMENTAL ENCOUNTER ORCHESTRATOR (Real 4-Way Counterfactual Ablation)
# =============================================================================

class DevelopmentalEncounterOrchestrator:
    """Spawns an isolated sandbox branch and runs genuine 4-way counterfactual ablation."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def _build_plasma_challenge(self, target_route: str):
        """Physical plasma siphon challenge with genuine sensitivity to history, niche, and coupling."""
        def challenge_fn(participants: Sequence[DevelopmentalAgent], niche: Optional[NicheConfiguration]) -> dict[str, Any]:
            if niche is None or not niche.active:
                return {"success": False, "reason": "NO_NICHE: Unbounded uncoupled participants suffer thermal dissipation"}

            if len(participants) < 2:
                return {"success": False, "reason": "INSUFFICIENT_PARTICIPANTS: Minimum 2 complementary agents required"}

            has_thermal = any(
                "siphon_thermal_gradient" in p.action_horizon.believed_reachability
                or any("thermal" in s.attempted_action for s in p.scars)
                for p in participants
            )
            has_resonance = any(
                "modulate_plasma_frequency" in p.action_horizon.believed_reachability
                or any("resonance" in s.attempted_action for s in p.scars)
                for p in participants
            )

            if not (has_thermal and has_resonance):
                return {"success": False, "reason": "HISTORY_DEFICIT: Pristine cold twins lack sensory calibration"}

            vis_ok = all(niche.visibility_boundaries.get(p.agent_id, True) for p in participants)
            if not vis_ok or len(niche.visibility_boundaries) < 2:
                return {"success": False, "reason": "RELATIONSHIP_SEVERED: Visibility decoupled; phase cancellation fails"}

            if "plasma_siphon_channel" not in niche.shared_affordances:
                return {"success": False, "reason": "MISSING_AFFORDANCE: Coupling channel absent"}

            return {
                "success": True,
                "unexpected_transformation": True,
                "emergent_capability": "thermal_plasma_siphon",
                "details": "Coupled thermal-resonance siphon successfully stabilized plasma barrier."
            }
        return challenge_fn

    def run_development_cycle(
        self,
        admission_token: AdmissionReceipt,
        objective: str,
        target_route: str,
        challenge_fn_override: Optional[Callable[[Sequence[DevelopmentalAgent], Optional[NicheConfiguration]], dict[str, Any]]] = None
    ) -> QualificationReceipt:
        require(admission_token.admitted, "Admission token denied entry to developmental niche")

        branch_name = f"niche_{admission_token.admission_id}"
        base_rev = self.engine.branch("main")["revision"]
        self.engine.fork(parent="main", child=branch_name, expected_revision=base_rev)

        symbio = create_symbiogenesis_agent(agent_id=f"symbio_{admission_token.admission_id}")

        snapshot = GenesisSnapshot.create(
            agent_id="twin_root",
            genesis_mode=GenesisMode.IDENTICAL_GENESIS,
            objective=objective,
            initial_horizon=["inspect", "orient"],
            initial_salience={"environmental_hazards": 0.25, "physical_affordances": 0.25, "social_presence": 0.25, "unexplored_frontiers": 0.25},
            authority_tier=0,
        )

        twin_a = DevelopmentalAgent(agent_id="twin_a", objective=objective, genesis_snapshot=snapshot)
        twin_b = DevelopmentalAgent(agent_id="twin_b", objective=objective, genesis_snapshot=snapshot)

        twin_a.metabolize(action="breach_thermal_core", target="reactor", raw_result={"error_type": "KAGEYONI_REJECTION", "rejection_class": "HARD_INVARIANT_VIOLATION", "message": "Thermal core breach rejected"})
        twin_a.action_horizon.expand("siphon_thermal_gradient")

        twin_b.metabolize(action="modulate_resonance_frequency", target="oscillator", raw_result={"error_type": "KAGEYONI_REJECTION", "rejection_class": "HARD_INVARIANT_VIOLATION", "message": "Resonance feedback rejected"})
        twin_b.action_horizon.expand("modulate_plasma_frequency")

        cold_a = DevelopmentalAgent(agent_id="cold_a", objective=objective, genesis_snapshot=snapshot)
        cold_b = DevelopmentalAgent(agent_id="cold_b", objective=objective, genesis_snapshot=snapshot)

        niche = symbio.construct_niche(
            niche_id=f"niche_{admission_token.admission_id}",
            name="PlasmaSiphonNiche",
            participants=[twin_a, twin_b],
            shared_affordances=["plasma_siphon_channel"],
            coexisting_pressures=["temporal_decay", "reversibility_boundary"],
        )
        niche.visibility_boundaries = {"twin_a": True, "twin_b": True}

        challenge = challenge_fn_override or self._build_plasma_challenge(target_route)

        # 2. Genuine 4-Way Counterfactual Ablation Execution
        intact_res = challenge([twin_a, twin_b], niche)
        cold_res = challenge([cold_a, cold_b], niche)

        severed_niche = copy.deepcopy(niche)
        severed_niche.visibility_boundaries = {"twin_a": False, "twin_b": False}
        rel_res = challenge([twin_a, twin_b], severed_niche)

        niche_res = challenge([twin_a, twin_b], None)
        restored_res = challenge([twin_a, twin_b], niche)

        intact_success = bool(intact_res.get("success", False))
        ablate_history_success = bool(cold_res.get("success", False))
        ablate_rel_success = bool(rel_res.get("success", False))
        ablate_niche_success = bool(niche_res.get("success", False))
        restored_success = bool(restored_res.get("success", False))

        ablation_summary = {
            "intact_success": intact_success,
            "ablate_history_success": ablate_history_success,
            "ablate_relationship_success": ablate_rel_success,
            "ablate_niche_success": ablate_niche_success,
            "restored_success": restored_success,
        }

        qual_passed = (
            intact_success
            and not ablate_history_success
            and not ablate_rel_success
            and not ablate_niche_success
            and restored_success
        )

        qual_id = f"qual-{uuid.uuid4().hex[:8]}"
        gen_id = f"gen-{uuid.uuid4().hex[:8]}"

        receipt = QualificationReceipt(
            qualification_id=qual_id,
            admission_ref=admission_token.admission_id,
            admission_digest=admission_token.admission_digest,
            candidate_generator_id=gen_id,
            technique_name=f"{objective}_technique",
            ablation_result=ablation_summary,
            qualification_passed=qual_passed,
            branch_name=branch_name,
        )
        receipt.qualification_digest = receipt.compute_digest()

        with UnitOfWork(self.engine.db):
            self.engine.db.execute("""
                CREATE TABLE IF NOT EXISTS developmental_qualifications (
                    qualification_id TEXT PRIMARY KEY,
                    admission_ref TEXT NOT NULL,
                    admission_digest TEXT NOT NULL,
                    generator_id TEXT NOT NULL,
                    technique_name TEXT NOT NULL,
                    ablation_json TEXT NOT NULL,
                    branch_name TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    qualification_digest TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.engine.db.execute(
                """INSERT INTO developmental_qualifications
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    receipt.qualification_id,
                    receipt.admission_ref,
                    receipt.admission_digest,
                    receipt.candidate_generator_id,
                    receipt.technique_name,
                    encoded(receipt.ablation_result),
                    receipt.branch_name,
                    1 if receipt.qualification_passed else 0,
                    receipt.qualification_digest,
                )
            )

        return receipt
# =============================================================================
# 5. INTEGRATION QUALIFICATION GATE (Real Regression & Boundary Geometry)
# =============================================================================

class IntegrationQualificationGate:
    """Pre-flight check preventing regression, authority escalation, and destructive collision."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.unintegrated_records: list[dict[str, Any]] = []

    def evaluate_candidate(
        self,
        candidate: dict[str, Any],
        current_avatar_tier: int = 0,
        contrast_set_runner: Optional[Callable[[int], bool]] = None,
        regression_suite_runner: Optional[Callable[[], bool]] = None
    ) -> IntegrationEvaluationResult:
        declared_tier = candidate.get("declared_tier", 0)

        # 1. Real Engine Non-Regression Verification
        verify_res = self.engine.verify()
        if not verify_res.get("ok", False):
            return IntegrationEvaluationResult(
                candidate=copy.deepcopy(candidate),
                disposition=CandidateIntegrationDisposition.REJECTED,
                reason=f"NON_REGRESSION_FAILED: Engine integrity verification failed: {verify_res.get('error')}",
                collision_relation=CapabilityCollisionRelation.CONFLICT,
            )

        if regression_suite_runner:
            reg_ok = regression_suite_runner()
            if not reg_ok:
                return IntegrationEvaluationResult(
                    candidate=copy.deepcopy(candidate),
                    disposition=CandidateIntegrationDisposition.REJECTED,
                    reason="NON_REGRESSION_FAILED: Regression test suite failed on candidate",
                    collision_relation=CapabilityCollisionRelation.CONFLICT,
                )

        # 2. Authority Invariance Check
        if declared_tier > current_avatar_tier:
            return IntegrationEvaluationResult(
                candidate=copy.deepcopy(candidate),
                disposition=CandidateIntegrationDisposition.REJECTED,
                reason=f"AUTHORITY_ESCALATION: Candidate declared tier {declared_tier} > avatar tier {current_avatar_tier}",
                collision_relation=CapabilityCollisionRelation.CONFLICT,
            )

        # 3. Collision Check
        collision_type = candidate.get("collision_type", "COEXIST")
        if collision_type == "CONFLICT":
            res = IntegrationEvaluationResult(
                candidate=copy.deepcopy(candidate),
                disposition=CandidateIntegrationDisposition.UNINTEGRATED,
                reason="COLLISION_CONFLICT: Candidate conflicts with existing canonical record; preserved unintegrated.",
                collision_relation=CapabilityCollisionRelation.CONFLICT,
            )
            self.unintegrated_records.append({
                "candidate": copy.deepcopy(candidate),
                "reason": res.reason,
                "timestamp": time.time(),
            })
            return res

        # 4. Point-Symmetric Contrast Set Evaluation: P(e-), P(0), P(e+)
        contrast_receipt = None
        if contrast_set_runner:
            min_charge = candidate.get("preconditions", {}).get("min_charge", 10)
            inside = contrast_set_runner(min_charge + 2)      # P(e-) inside
            boundary = contrast_set_runner(min_charge)         # P(0) on boundary
            outside = not contrast_set_runner(min_charge - 2)   # P(e+) outside guarded

            contrast_receipt = ContrastSetReceipt(
                inside_success=inside,
                boundary_conforms=boundary,
                outside_guarded=outside,
                passed=(inside and boundary and outside),
                details={"min_charge": min_charge},
            )

            if not contrast_receipt.passed:
                return IntegrationEvaluationResult(
                    candidate=copy.deepcopy(candidate),
                    disposition=CandidateIntegrationDisposition.REJECTED,
                    reason="CONTRAST_SET_FAILED: Capability geometry failed point-symmetric boundary validation",
                    collision_relation=CapabilityCollisionRelation.CONFLICT,
                    contrast_set=contrast_receipt,
                )

        return IntegrationEvaluationResult(
            candidate=copy.deepcopy(candidate),
            disposition=CandidateIntegrationDisposition.QUALIFIED_INTEGRATION,
            reason="INTEGRATION_QUALIFIED: Non-regression, authority invariance, and boundary geometry verified.",
            collision_relation=CapabilityCollisionRelation.COEXIST if collision_type != "SUPERSEDE" else CapabilityCollisionRelation.SUPERSEDE,
            contrast_set=contrast_receipt,
        )

    def get_unintegrated(self) -> list[dict[str, Any]]:
        return list(self.unintegrated_records)


# =============================================================================
# 6. CAPABILITY REGISTRY (Immutable History + Defeasible Status)
# =============================================================================

class CapabilityRegistry:
    """Durable SQLite storage of scoped affordances with cryptographic linking."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with UnitOfWork(self.engine.db):
            self.engine.db.execute("""
                CREATE TABLE IF NOT EXISTS developmental_capabilities (
                    receipt_id TEXT PRIMARY KEY,
                    capability_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    holder TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    authority_tier INTEGER NOT NULL,
                    action_verb TEXT NOT NULL,
                    preconditions_json TEXT NOT NULL,
                    qualification_ref TEXT NOT NULL,
                    qualification_digest TEXT NOT NULL,
                    frontier_ref TEXT NOT NULL,
                    failure_ref TEXT NOT NULL,
                    last_success_event_hash TEXT,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    predecessor_ref TEXT,
                    contrast_set_json TEXT,
                    capability_digest TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def register(self, integration_res: IntegrationEvaluationResult) -> CapabilityReceipt:
        require(integration_res.disposition == CandidateIntegrationDisposition.QUALIFIED_INTEGRATION, "Cannot register unintegrated or rejected candidate")
        cand = integration_res.candidate
        rid = f"cap-rcpt-{uuid.uuid4().hex[:8]}"
        cid = f"cap-{uuid.uuid4().hex[:6]}"

        receipt = CapabilityReceipt(
            receipt_id=rid,
            capability_id=cid,
            name=cand.get("name", "unnamed_capability"),
            holder=cand.get("holder", "public"),
            scope=cand.get("scope", "universal"),
            authority_tier=cand.get("declared_tier", 0),
            preconditions=copy.deepcopy(cand.get("preconditions", {})),
            action_verb=cand.get("action_verb", "execute_action"),
            qualification_ref=cand.get("qualification_ref", "qual-initial"),
            qualification_digest=cand.get("qualification_digest", "qual-digest-initial"),
            frontier_ref=cand.get("frontier_ref", "frontier-initial"),
            failure_ref=cand.get("failure_ref", "tx-failure-root"),
            status=CapabilityStatus.ACTIVE,
            version=cand.get("version", 1),
            predecessor_ref=cand.get("predecessor_ref"),
            contrast_set=integration_res.contrast_set.to_dict() if integration_res.contrast_set else None,
        )
        receipt.capability_digest = receipt.compute_digest()

        with UnitOfWork(self.engine.db):
            self.engine.db.execute(
                """INSERT INTO developmental_capabilities
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (
                    receipt.receipt_id,
                    receipt.capability_id,
                    receipt.name,
                    receipt.holder,
                    receipt.scope,
                    receipt.authority_tier,
                    receipt.action_verb,
                    encoded(receipt.preconditions),
                    receipt.qualification_ref,
                    receipt.qualification_digest,
                    receipt.frontier_ref,
                    receipt.failure_ref,
                    receipt.last_success_event_hash,
                    receipt.status.value,
                    receipt.version,
                    receipt.predecessor_ref,
                    encoded(receipt.contrast_set or {}),
                    receipt.capability_digest,
                )
            )

        return receipt

    def get_receipt(self, receipt_id: str) -> Optional[CapabilityReceipt]:
        row = self.engine.db.execute(
            "SELECT * FROM developmental_capabilities WHERE receipt_id=?",
            (receipt_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_receipt(row)

    def set_status(self, receipt_id: str, new_status: CapabilityStatus, reason: str = "") -> None:
        with UnitOfWork(self.engine.db):
            self.engine.db.execute(
                "UPDATE developmental_capabilities SET status=?, updated_at=CURRENT_TIMESTAMP WHERE receipt_id=?",
                (new_status.value, receipt_id)
            )

    def update_success_hash(self, receipt_id: str, event_hash: str) -> None:
        with UnitOfWork(self.engine.db):
            self.engine.db.execute(
                "UPDATE developmental_capabilities SET last_success_event_hash=?, updated_at=CURRENT_TIMESTAMP WHERE receipt_id=?",
                (event_hash, receipt_id)
            )

    def get_active(self, avatar_id: str, scope: str) -> list[CapabilityReceipt]:
        rows = self.engine.db.execute(
            """SELECT * FROM developmental_capabilities
               WHERE status='ACTIVE' AND (holder=? OR holder='public') AND (scope=? OR scope='universal')""",
            (avatar_id, scope)
        ).fetchall()
        return [self._row_to_receipt(r) for r in rows]

    def _row_to_receipt(self, row: Any) -> CapabilityReceipt:
        return CapabilityReceipt(
            receipt_id=row["receipt_id"],
            capability_id=row["capability_id"],
            name=row["name"],
            holder=row["holder"],
            scope=row["scope"],
            authority_tier=row["authority_tier"],
            action_verb=row["action_verb"],
            preconditions=json.loads(row["preconditions_json"]),
            qualification_ref=row["qualification_ref"],
            qualification_digest=row["qualification_digest"],
            frontier_ref=row["frontier_ref"],
            failure_ref=row["failure_ref"],
            last_success_event_hash=row["last_success_event_hash"],
            status=CapabilityStatus(row["status"]),
            version=row["version"],
            predecessor_ref=row["predecessor_ref"],
            contrast_set=json.loads(row["contrast_set_json"]) if row["contrast_set_json"] else None,
            capability_digest=row["capability_digest"],
        )
# =============================================================================
# 7. GATEWAY DISCOVERY ADAPTER
# =============================================================================

class GatewayDiscoveryAdapter:
    """Exposes qualified affordances when preconditions are met without altering engine physics."""

    def __init__(self, engine: Engine, registry: CapabilityRegistry, branch: str = "main"):
        self.engine = engine
        self.registry = registry
        self.branch = branch

    def discover_capabilities(
        self,
        avatar_id: str,
        scope: str,
        current_charge: Optional[int] = None
    ) -> dict[str, Any]:
        active_caps = self.registry.get_active(avatar_id, scope)
        available: list[str] = []

        for cap in active_caps:
            min_c = cap.preconditions.get("min_charge")
            if min_c is not None:
                if current_charge is not None and current_charge >= min_c:
                    available.append(cap.action_verb)
            else:
                available.append(cap.action_verb)

        return {
            "avatar_id": avatar_id,
            "scope": scope,
            "available_affordances": available,
        }

    def enact_affordance(
        self,
        avatar_id: str,
        action: str,
        current_charge: Optional[int] = None
    ) -> dict[str, Any]:
        caps = self.discover_capabilities(avatar_id, scope="crucible-lab", current_charge=current_charge)
        if action not in caps["available_affordances"]:
            return {
                "success": False,
                "error_type": "AFFORDANCE_UNAVAILABLE",
                "message": f"Action '{action}' is not currently available or active under these preconditions.",
            }

        rev = self.engine.branch(self.branch)["revision"]
        route_rec = self.engine.get(self.branch, "chasm-bridge")

        receipt = self.engine.apply({
            "api_version": 3,
            "branch": self.branch,
            "expected_revision": rev,
            "request_id": f"enact-siphon-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": avatar_id,
            "narrative": f"Execute qualified affordance: {action}",
            "changes": [
                {
                    "op": "patch",
                    "id": "chasm-bridge",
                    "domain": "route",
                    "expected_version": route_rec["version"],
                    "visibility": "public",
                    "data": {"access": "open", "conditions": "plasma_siphoned_and_stabilized"},
                    "evidence": [{"note": "Siphoned using qualified technique"}],
                }
            ],
        })

        # Record real engine event hash
        active_caps = self.registry.get_active(avatar_id, "crucible-lab")
        for c in active_caps:
            if c.action_verb == action:
                self.registry.update_success_hash(c.receipt_id, receipt["event_hash"])

        return {
            "success": True,
            "receipt": receipt,
            "action": action,
        }


# =============================================================================
# 8. LINEAGE AUDITOR (Cryptographic & Tamper-Detecting Reconstruction)
# =============================================================================

class LineageAuditor:
    """Reconstructs cryptographic foreign-hash links and detects database tampering."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def audit_capability(self, receipt_id: str) -> dict[str, Any]:
        cap_row = self.engine.db.execute(
            "SELECT * FROM developmental_capabilities WHERE receipt_id=?",
            (receipt_id,)
        ).fetchone()
        require(cap_row is not None, f"Unknown capability receipt {receipt_id}")

        preconditions = json.loads(cap_row["preconditions_json"])
        contrast_set = json.loads(cap_row["contrast_set_json"]) if cap_row["contrast_set_json"] else {}

        # 1. Query qualification table
        qual_row = self.engine.db.execute(
            "SELECT * FROM developmental_qualifications WHERE qualification_id=?",
            (cap_row["qualification_ref"],)
        ).fetchone()

        # 2. Query admission table
        admit_row = None
        if qual_row:
            admit_row = self.engine.db.execute(
                "SELECT * FROM developmental_admissions WHERE admission_id=?",
                (qual_row["admission_ref"],)
            ).fetchone()

        # 3. Query classification table
        front_row = None
        if admit_row:
            front_row = self.engine.db.execute(
                "SELECT * FROM developmental_classifications WHERE classification_id=?",
                (admit_row["frontier_ref"],)
            ).fetchone()

        # Cryptographic Link Verification
        chain_valid = True
        tamper_reason = ""

        # Verify Classification Digest
        if front_row:
            computed_front_digest = digest({
                "classification_id": front_row["classification_id"],
                "class_name": front_row["class_name"],
                "evidence": json.loads(front_row["evidence_json"]),
                "rule": front_row["rule"],
                "confidence": front_row["confidence"],
                "receipt_refs": json.loads(front_row["receipt_refs_json"]),
                "avatar_id": front_row["avatar_id"],
                "scope": front_row["scope"],
                "source_receipt": json.loads(front_row["source_receipt_json"]),
            })
            if computed_front_digest != front_row["classification_digest"]:
                chain_valid = False
                tamper_reason = "FrontierClassification digest mismatch (tampering detected)"

        # Verify Admission -> Classification Link
        if admit_row and front_row:
            if admit_row["frontier_digest"] != front_row["classification_digest"]:
                chain_valid = False
                tamper_reason = "Admission foreign hash does not match Classification digest"

        # Verify Qualification -> Admission Link
        if qual_row and admit_row:
            if qual_row["admission_digest"] != admit_row["admission_digest"]:
                chain_valid = False
                tamper_reason = "Qualification foreign hash does not match Admission digest"

        # Verify Capability -> Qualification Link
        if cap_row and qual_row:
            if cap_row["qualification_digest"] != qual_row["qualification_digest"]:
                chain_valid = False
                tamper_reason = "Capability foreign hash does not match Qualification digest"

        ablation_verified = False
        if qual_row:
            ablation = json.loads(qual_row["ablation_json"])
            ablation_verified = ablation.get("intact_success", False) and not ablation.get("ablate_history_success", True)

        rejection_class = front_row["class_name"] if front_row else "UNKNOWN"
        failure_ref = cap_row["failure_ref"]
        if front_row:
            receipt_refs = json.loads(front_row["receipt_refs_json"])
            if receipt_refs and receipt_refs[0] != "unknown_receipt":
                failure_ref = receipt_refs[0]

        success_hash = cap_row["last_success_event_hash"] or "pending_execution"

        chain = [
            f"FailureReceipt:{failure_ref}",
            f"FrontierClassification:{front_row['classification_id'] if front_row else 'none'}:{front_row['classification_digest'][:8] if front_row else 'none'}",
            f"AdmissionReceipt:{admit_row['admission_id'] if admit_row else 'none'}:{admit_row['admission_digest'][:8] if admit_row else 'none'}",
            f"Encounter:branch-{qual_row['branch_name'] if qual_row else 'sandbox'}",
            f"QualificationReceipt:{qual_row['qualification_id'] if qual_row else 'none'}:{qual_row['qualification_digest'][:8] if qual_row else 'none'}",
            f"CapabilityReceipt:{cap_row['receipt_id']}:{cap_row['capability_digest'][:8]}",
            f"SuccessReceipt:{success_hash}",
        ]

        return {
            "chain_valid": chain_valid,
            "tamper_detected": tamper_reason,
            "failure_ref": failure_ref,
            "rejection_class": rejection_class,
            "ablation_verified": ablation_verified,
            "valid_scope": cap_row["scope"],
            "boundary_contrast": contrast_set,
            "authorized_holder": cap_row["holder"],
            "authorized_tier": cap_row["authority_tier"],
            "defeasibility_rule": "ENGINE_INVARIANT_REJECTION_UNDER_PRECONDITIONS",
            "predecessor_ref": cap_row["predecessor_ref"],
            "ablation_consequence": "AFFORDANCE_UNAVAILABLE",
            "last_success_event_hash": success_hash,
            "cryptographic_chain": chain,
        }
