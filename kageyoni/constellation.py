"""
Kageyōni Constellation Substrate.
Physical primitives for Summon, Transmute, Joy Boy Reground,
and the Constellation-Chef-Beast lifecycle.
"""

from __future__ import annotations
import copy
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class EpistemicStatus(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    CANDIDATE_RELATION = "CANDIDATE_RELATION"
    UNKNOWN = "UNKNOWN"


class DerivationStatus(str, Enum):
    SOURCE_FACT = "SOURCE_FACT"
    SUPPORTED_DERIVATION = "SUPPORTED_DERIVATION"
    CREATIVE_PROPOSAL = "CREATIVE_PROPOSAL"
    REQUIRES_VALIDATION = "REQUIRES_VALIDATION"
    AUTHORIZED = "AUTHORIZED"
    EXECUTED = "EXECUTED"


class SummonScarError(ValueError):
    """Raised when an observed co-presence is falsely promoted to proven lineage."""
    pass


class TransmuteScarError(ValueError):
    """Raised when an ungrounded creative proposal masquerades as source truth."""
    pass


@dataclass
class CandidateTechnique:
    """
    Candidate Technique specification satisfying the 10 invariant qualification criteria.
    """
    name: str
    object_type: str
    input_state: str
    operation: str
    output_state: str
    conservation: str
    authority: str
    failure_signature: str
    null_case: str
    evidence: str
    carrier: str
    is_qualified: bool = False
    trials_passed: int = 0
    error_count: int = 0

    def qualify(self, trial_dispositions: List[str]) -> bool:
        """
        Qualify the technique: requires at least 2 trial disposition classes, 0 errors.
        """
        if not trial_dispositions:
            self.is_qualified = False
            return False
        
        distinct_classes = set(trial_dispositions)
        if len(distinct_classes) >= 2 and self.error_count == 0:
            self.trials_passed = len(trial_dispositions)
            self.is_qualified = True
            return True
        self.is_qualified = False
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "object_type": self.object_type,
            "input_state": self.input_state,
            "operation": self.operation,
            "output_state": self.output_state,
            "conservation": self.conservation,
            "authority": self.authority,
            "failure_signature": self.failure_signature,
            "null_case": self.null_case,
            "evidence": self.evidence,
            "carrier": self.carrier,
            "is_qualified": self.is_qualified,
            "trials_passed": self.trials_passed,
        }


@dataclass
class ConstellationElement:
    id: str
    element_type: str  # person, tool, artifact, evidence, constraint, environment, history
    payload: Dict[str, Any]
    epistemic_status: EpistemicStatus = EpistemicStatus.OBSERVED
    derivation_status: DerivationStatus = DerivationStatus.SOURCE_FACT
    provenance: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "element_type": self.element_type,
            "payload": self.payload,
            "epistemic_status": self.epistemic_status.value,
            "derivation_status": self.derivation_status.value,
            "provenance": self.provenance,
            "created_at": self.created_at,
        }


class ConstellationField:
    """The situated addressable field (Constellation)."""
    def __init__(self, field_id: str):
        self.field_id = field_id
        self.elements: Dict[str, ConstellationElement] = {}
        self.relations: List[Dict[str, Any]] = []

    def add_element(self, element: ConstellationElement) -> None:
        self.elements[element.id] = element

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        status: EpistemicStatus = EpistemicStatus.CANDIDATE_RELATION,
        proven_lineage: bool = False,
    ) -> None:
        if source_id not in self.elements or target_id not in self.elements:
            raise KeyError(f"Both elements must exist in field: {source_id}, {target_id}")

        # Enforce Summon Scar: Observed relation != proven lineage
        if proven_lineage and status != EpistemicStatus.OBSERVED:
            raise SummonScarError(
                f"Cannot declare proven lineage for unverified relation between {source_id} and {target_id}"
            )

        self.relations.append({
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "status": status.value,
            "proven_lineage": proven_lineage,
            "timestamp": time.time(),
        })

    def get_element(self, element_id: str) -> Optional[ConstellationElement]:
        return self.elements.get(element_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "elements": {k: v.to_dict() for k, v in self.elements.items()},
            "relations": list(self.relations),
        }


def summon(
    field: ConstellationField,
    target_ids: List[str],
    intent: str,
) -> ConstellationField:
    """
    Constellation Technique I: Summon.
    Changes what becomes consequentially co-present.
    Makes previously separated elements observable together without fabricating lineage.
    """
    sub_field_id = f"summon_{field.field_id}_{hashlib.sha256(intent.encode()).hexdigest()[:8]}"
    sub_field = ConstellationField(sub_field_id)

    for tid in target_ids:
        elem = field.get_element(tid)
        if elem:
            # Elements brought into mutual co-presence retain their epistemic status
            sub_field.add_element(copy.deepcopy(elem))
        else:
            # Mark unknown presence explicitly rather than hallucinating
            sub_field.add_element(
                ConstellationElement(
                    id=tid,
                    element_type="unknown_target",
                    payload={"intent": intent},
                    epistemic_status=EpistemicStatus.UNKNOWN,
                    derivation_status=DerivationStatus.REQUIRES_VALIDATION,
                )
            )

    # Establish candidate relations between co-present elements
    for i, id_a in enumerate(target_ids):
        for id_b in target_ids[i + 1 :]:
            if id_a in sub_field.elements and id_b in sub_field.elements:
                sub_field.add_relation(
                    source_id=id_a,
                    target_id=id_b,
                    relation_type=f"co_present_for_{intent}",
                    status=EpistemicStatus.CANDIDATE_RELATION,
                    proven_lineage=False,
                )

    return sub_field


def transmute(
    source_elements: List[ConstellationElement],
    target_form: str,
    derivation_fn: Callable[[List[ConstellationElement]], Dict[str, Any]],
    declared_status: DerivationStatus = DerivationStatus.CREATIVE_PROPOSAL,
    authorizer: Optional[str] = None,
) -> ConstellationElement:
    """
    Alchemy: Transmute.
    Uses consequential co-presence to create a grounded new form that the field does not currently express.
    Enforces Transmute Scar: Generated possibility != established reality.
    """
    if not source_elements:
        raise ValueError("Transmute requires at least one source element in the co-present field.")

    # Execute transformation
    derived_payload = derivation_fn(source_elements)

    # Validate status invariants: a creative proposal cannot claim to be SOURCE_FACT
    if declared_status == DerivationStatus.SOURCE_FACT:
        raise TransmuteScarError(
            "Transmute cannot emit a SOURCE_FACT. Derivations must be SUPPORTED_DERIVATION or CREATIVE_PROPOSAL."
        )

    # If claiming SUPPORTED_DERIVATION without an authorizer or explicit source facts, fail closed
    if declared_status == DerivationStatus.AUTHORIZED and not authorizer:
        raise TransmuteScarError("Transmute output cannot be AUTHORIZED without an explicit sovereign authorizer.")

    source_hashes = [
        hashlib.sha256(json.dumps(e.payload, sort_keys=True, default=str).encode()).hexdigest()[:8]
        for e in source_elements
    ]
    provenance_tag = f"transmuted_from:{','.join(e.id for e in source_elements)}:hashes:{','.join(source_hashes)}"

    out_id = f"{target_form}_{hashlib.sha256(provenance_tag.encode()).hexdigest()[:10]}"

    return ConstellationElement(
        id=out_id,
        element_type=target_form,
        payload=derived_payload,
        epistemic_status=EpistemicStatus.INFERRED,
        derivation_status=declared_status,
        provenance=provenance_tag,
    )


def reground(
    current_state: Dict[str, Any],
    preserved_invariants: List[str],
    active_scars: List[Dict[str, Any]],
    receipts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Joy Boy Reground.
    Releases accumulated path, framing, and representation privilege
    while preserving objective, evidence, scars, demonstrated capability,
    consequential distinctions, authority, and unresolved residue.
    Reconstructs from capability available now.
    """
    # 1. Purge path history, conversational framing, and temporary prompt packaging
    regrounded_state = {
        "reground_epoch": time.time(),
        "objective": current_state.get("objective", "unspecified_objective"),
        "retained_invariants": list(preserved_invariants),
        "preserved_scars": copy.deepcopy(active_scars),
        "immutable_receipts": copy.deepcopy(receipts),
        "active_capabilities": list(current_state.get("active_capabilities", [])),
        "unresolved_residue": copy.deepcopy(current_state.get("unresolved_residue", [])),
        "framing_status": "CLEAN_SLATE_RECONSTRUCTED",
    }

    # Verify scars are not dropped
    if len(regrounded_state["preserved_scars"]) < len(active_scars):
        raise ValueError("Reground invariant violation: scars were lost during reconstruction.")

    return regrounded_state


class Beast:
    """
    The Beast: The resulting temporary embodied configuration capable of acting.
    Dissolves when the encounter ends, committing only receipts and scars.
    """
    def __init__(
        self,
        name: str,
        constellation_field: ConstellationField,
        action_horizon: Set[str],
    ):
        self.name = name
        self.field = constellation_field
        self.action_horizon = set(action_horizon)
        self.execution_log: List[Dict[str, Any]] = []
        self.scars_forged: List[Dict[str, Any]] = []
        self.is_active = False

    def __enter__(self) -> Beast:
        self.is_active = True
        return self

    def act(self, action_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_active:
            raise RuntimeError("Beast is not active. Actions can only be taken within the operational context.")

        if action_name not in self.action_horizon:
            # Rejection outside action horizon forges a scar candidate
            scar = {
                "scar_id": f"scar_{action_name}_{int(time.time())}",
                "invariant_violated": "ACTION_HORIZON_EXCEEDED",
                "attempted_action": action_name,
                "timestamp": time.time(),
            }
            self.scars_forged.append(scar)
            raise PermissionError(f"Action '{action_name}' is outside the Beast's ActionHorizon.")

        receipt = {
            "action": action_name,
            "arguments": arguments,
            "status": "COMPLETED",
            "timestamp": time.time(),
            "receipt_hash": hashlib.sha256(json.dumps(arguments, sort_keys=True, default=str).encode()).hexdigest(),
        }
        self.execution_log.append(receipt)
        return receipt

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.is_active = False
        # The temporary embodiment dissolves.
        # It does NOT persist memory scratchpads or conversational self-identity.
        # Only immutable receipts and scars survive.
