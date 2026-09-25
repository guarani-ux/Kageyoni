"""4. CONTINUITY Nature Transformation

Purpose:
Preserve relevant intelligence through change without preserving obsolete state merely because it existed previously.

Core transformation:
S_t + Δ → S_(t+1)

Continuity maintains causal lineage, carries forward still-valid constraints, preserves
unresolved uncertainty, recognizes contradiction, invalidates obsolete knowledge,
and reconciles prior state with authoritative new state.

Strict Categorization:
Every tracked item is categorized as:
- PERSIST: Valid unchanged knowledge with intact provenance.
- UPDATE: Authoritatively altered by new state/event.
- INVALIDATE: Contradicted by new empirical evidence.
- OBSOLETE: Prerequisites or contextual relevance no longer hold.
- UNRESOLVED: Genuine uncertainty preserved without manufactured resolution.

Anti-Dogma Law:
Continuity never treats memory as truth merely because something was previously recorded.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set

from .core import (
    CognitiveDelta,
    CognitiveHypothesis,
    CognitiveState,
    DeficitType,
    KnowledgeDeficit,
    NatureType,
)


class ContinuityDisposition(str, Enum):
    PERSIST = "PERSIST"
    UPDATE = "UPDATE"
    INVALIDATE = "INVALIDATE"
    OBSOLETE = "OBSOLETE"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class ContinuityItem:
    """An item of cognitive state evaluated through state transition."""
    item_id: str
    item_type: str  # constraint | hypothesis | invariant | observation | uncertainty
    content: Any
    disposition: ContinuityDisposition
    lineage: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "content": self.content,
            "disposition": self.disposition.value,
            "lineage": list(self.lineage),
            "reason": self.reason,
        }


@dataclass
class ContinuityResult:
    """The formal, audited output of a Continuity reconciliation."""
    source_revision: int
    target_revision: int
    categorized_items: dict[ContinuityDisposition, list[ContinuityItem]]
    persisted_count: int
    updated_count: int
    invalidated_count: int
    obsoleted_count: int
    unresolved_count: int
    deficits: list[KnowledgeDeficit]
    delta: CognitiveDelta

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_revision": self.source_revision,
            "target_revision": self.target_revision,
            "persisted_count": self.persisted_count,
            "updated_count": self.updated_count,
            "invalidated_count": self.invalidated_count,
            "obsoleted_count": self.obsoleted_count,
            "unresolved_count": self.unresolved_count,
            "items": {
                disp.value: [it.to_dict() for it in items]
                for disp, items in self.categorized_items.items()
            },
            "deficits": [d.to_dict() for d in self.deficits],
        }


class Continuity:
    """The Continuity Nature Transformation engine."""

    def reconcile(
        self,
        current_state: CognitiveState,
        world_transition_receipt: dict[str, Any],
        source_revision: int = 0,
        target_revision: int = 1,
    ) -> ContinuityResult:
        """Reconciles cognitive state across a world-state transition Δ.

        Guarantees:
        1. Classifies all active constraints, hypotheses, and uncertainties into
           PERSIST, UPDATE, INVALIDATE, OBSOLETE, or UNRESOLVED.
        2. Maintains explicit provenance and lineage for every persisted or updated item.
        3. Never assumes a past hypothesis remains valid if contradicted or obsoleted by Δ.
        """
        deficits: list[KnowledgeDeficit] = []
        buckets: dict[ContinuityDisposition, list[ContinuityItem]] = {
            ContinuityDisposition.PERSIST: [],
            ContinuityDisposition.UPDATE: [],
            ContinuityDisposition.INVALIDATE: [],
            ContinuityDisposition.OBSOLETE: [],
            ContinuityDisposition.UNRESOLVED: [],
        }

        events = world_transition_receipt.get("events", [])
        modified_entities = set(world_transition_receipt.get("modified_ids", []))
        cleared_conditions = set(world_transition_receipt.get("cleared_conditions", []))
        new_facts = world_transition_receipt.get("new_facts", [])

        # 1. Reconcile Constraints
        surviving_constraints: list[str] = []
        for idx, constraint in enumerate(current_state.active_constraints):
            cid = f"constraint-{idx}"
            # Check if this constraint depended on a condition that was cleared
            is_obsolete = False
            for cond in cleared_conditions:
                if cond.lower() in constraint.lower():
                    is_obsolete = True
                    break

            if is_obsolete:
                item = ContinuityItem(
                    item_id=cid,
                    item_type="constraint",
                    content=constraint,
                    disposition=ContinuityDisposition.OBSOLETE,
                    lineage=[f"rev:{source_revision} -> rev:{target_revision}"],
                    reason="Prerequisite condition cleared by world transition Δ.",
                )
                buckets[ContinuityDisposition.OBSOLETE].append(item)
            else:
                surviving_constraints.append(constraint)
                item = ContinuityItem(
                    item_id=cid,
                    item_type="constraint",
                    content=constraint,
                    disposition=ContinuityDisposition.PERSIST,
                    lineage=[f"rev:{source_revision} -> rev:{target_revision}"],
                    reason="Constraint condition remains active and unbroken.",
                )
                buckets[ContinuityDisposition.PERSIST].append(item)

        # 2. Reconcile Hypotheses
        surviving_hypotheses: list[CognitiveHypothesis] = []
        for hyp in current_state.hypotheses:
            # Check for contradiction against new facts
            contradicted = False
            contradicting_fact = None
            hyp_words = set(hyp.statement.lower().split())
            for fact in new_facts:
                fact_stmt = fact.get("statement", str(fact)).lower()
                fact_words = set(fact_stmt.split())
                is_invalidated_status = fact.get("status") == "invalidated"
                overlap = len(hyp_words & fact_words)
                
                # If fact directly falsifies hypothesis
                if (hyp.statement.lower() in fact_stmt or overlap >= 2) and (
                    "not" in fact_stmt or "failed" in fact_stmt or is_invalidated_status
                ):
                    contradicted = True
                    contradicting_fact = fact_stmt
                    break
                # Or if entity was modified in a way impacting hypothesis
                for eid in modified_entities:
                    if eid.lower() in hyp.statement.lower() and fact.get("entity_id") == eid:
                        if is_invalidated_status:
                            contradicted = True
                            contradicting_fact = str(fact)
                            break

            if contradicted:
                hyp.is_invalidated = True
                hyp.invalidation_reason = f"Contradicted in rev {target_revision} by: {contradicting_fact}"
                item = ContinuityItem(
                    item_id=hyp.hypothesis_id,
                    item_type="hypothesis",
                    content=hyp.to_dict(),
                    disposition=ContinuityDisposition.INVALIDATE,
                    lineage=list(hyp.provenance_sources) + [f"rev:{target_revision}"],
                    reason=hyp.invalidation_reason,
                )
                buckets[ContinuityDisposition.INVALIDATE].append(item)
            elif hyp.is_invalidated:
                # Already invalidated previously
                item = ContinuityItem(
                    item_id=hyp.hypothesis_id,
                    item_type="hypothesis",
                    content=hyp.to_dict(),
                    disposition=ContinuityDisposition.INVALIDATE,
                    lineage=list(hyp.provenance_sources),
                    reason=hyp.invalidation_reason or "Previously invalidated.",
                )
                buckets[ContinuityDisposition.INVALIDATE].append(item)
            else:
                # Check if updated by new evidence
                matched_fact = False
                for fact in new_facts:
                    if hyp.hypothesis_id in fact.get("corroborates", []):
                        matched_fact = True
                        break

                if matched_fact:
                    hyp.provenance_sources.append(f"rev:{target_revision}")
                    surviving_hypotheses.append(hyp)
                    item = ContinuityItem(
                        item_id=hyp.hypothesis_id,
                        item_type="hypothesis",
                        content=hyp.to_dict(),
                        disposition=ContinuityDisposition.UPDATE,
                        lineage=list(hyp.provenance_sources),
                        reason="Corroborated by transition event.",
                    )
                    buckets[ContinuityDisposition.UPDATE].append(item)
                else:
                    surviving_hypotheses.append(hyp)
                    item = ContinuityItem(
                        item_id=hyp.hypothesis_id,
                        item_type="hypothesis",
                        content=hyp.to_dict(),
                        disposition=ContinuityDisposition.PERSIST,
                        lineage=list(hyp.provenance_sources) + [f"rev:{target_revision}"],
                        reason="Hypothesis unaffected by transition.",
                    )
                    buckets[ContinuityDisposition.PERSIST].append(item)

        # 3. Reconcile Unresolved Uncertainties
        surviving_uncertainties: list[str] = []
        for idx, unc in enumerate(current_state.unresolved_uncertainties):
            uid = f"unc-{idx}"
            # Check if resolved by new facts
            resolved = any(unc.lower() in str(f).lower() for f in new_facts)
            if resolved:
                item = ContinuityItem(
                    item_id=uid,
                    item_type="uncertainty",
                    content=unc,
                    disposition=ContinuityDisposition.UPDATE,
                    lineage=[f"rev:{source_revision} -> rev:{target_revision}"],
                    reason="Uncertainty resolved by newly observed world facts.",
                )
                buckets[ContinuityDisposition.UPDATE].append(item)
            else:
                surviving_uncertainties.append(unc)
                item = ContinuityItem(
                    item_id=uid,
                    item_type="uncertainty",
                    content=unc,
                    disposition=ContinuityDisposition.UNRESOLVED,
                    lineage=[f"rev:{source_revision} -> rev:{target_revision}"],
                    reason="Uncertainty remains unresolved without sufficient discriminating evidence.",
                )
                buckets[ContinuityDisposition.UNRESOLVED].append(item)

        # Check if unresolved items exceed safe boundary
        if len(buckets[ContinuityDisposition.UNRESOLVED]) > 0:
            deficits.append(
                KnowledgeDeficit(
                    deficit_type=DeficitType.INPUT_DEFICIT,
                    description=f"{len(buckets[ContinuityDisposition.UNRESOLVED])} uncertainties remain unresolved through transition.",
                    impacted_representation=f"rev:{target_revision}",
                    required_to_resolve="Future empirical observations targeting specific unresolved uncertainties.",
                )
            )

        # Mutate CognitiveState into S_(t+1)
        current_state.active_constraints = surviving_constraints
        current_state.hypotheses = surviving_hypotheses
        current_state.unresolved_uncertainties = surviving_uncertainties
        current_state.provenance_log.append({
            "nature": "CONTINUITY",
            "source_revision": source_revision,
            "target_revision": target_revision,
            "persisted": len(buckets[ContinuityDisposition.PERSIST]),
            "updated": len(buckets[ContinuityDisposition.UPDATE]),
            "invalidated": len(buckets[ContinuityDisposition.INVALIDATE]),
            "obsoleted": len(buckets[ContinuityDisposition.OBSOLETE]),
            "unresolved": len(buckets[ContinuityDisposition.UNRESOLVED]),
        })

        delta = CognitiveDelta(
            delta_id=f"delta-{uuid.uuid4().hex[:8]}",
            nature=NatureType.CONTINUITY,
            input_summary={"source_rev": source_revision, "target_rev": target_revision},
            output_summary={
                "persisted": len(buckets[ContinuityDisposition.PERSIST]),
                "updated": len(buckets[ContinuityDisposition.UPDATE]),
                "invalidated": len(buckets[ContinuityDisposition.INVALIDATE]),
                "obsoleted": len(buckets[ContinuityDisposition.OBSOLETE]),
                "unresolved": len(buckets[ContinuityDisposition.UNRESOLVED]),
            },
            objective_preserved=True,
            deficits_identified=deficits,
            authoritative_world_mutated=False,
        )

        return ContinuityResult(
            source_revision=source_revision,
            target_revision=target_revision,
            categorized_items=buckets,
            persisted_count=len(buckets[ContinuityDisposition.PERSIST]),
            updated_count=len(buckets[ContinuityDisposition.UPDATE]),
            invalidated_count=len(buckets[ContinuityDisposition.INVALIDATE]),
            obsoleted_count=len(buckets[ContinuityDisposition.OBSOLETE]),
            unresolved_count=len(buckets[ContinuityDisposition.UNRESOLVED]),
            deficits=deficits,
            delta=delta,
        )
