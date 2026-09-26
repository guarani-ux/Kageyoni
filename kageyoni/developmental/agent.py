"""Developmental Agent Implementation for Kageyōni.

Hardened under Hardening Directives 1 - 13:
1. Separate Qualification Levels (VALID_GENESIS -> DEVELOPMENT_OBSERVED -> CAPABILITY_DEMONSTRATED -> CAPABILITY_QUALIFIED -> RELATIONAL_CAPABILITY_QUALIFIED).
2. Prevents self-qualification by decoupling forge validation from independent capability probes.
3. Emits immutable Genesis Snapshots (A0 manifest with SHA-256 digest).
4. Supports IDENTICAL_GENESIS and SPECIALIZED_GENESIS modes.
5. Twin forging support (forge_twins).
6. History ablation (ablate_history, restore_cold_a0).
7. Consequence metabolism supplies consequences, agent supplies interpretation (no hidden harness answers).
8. Provenance on every DevelopmentalDelta (What, From, Because of, Who interpreted, What verifier, Future behavior).
9. Negative development (demote, invalidate, sever).
10. Auditable salience recorded in A0.
"""
from __future__ import annotations

import copy
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from kageyoni.engine import Rejected, require
from kageyoni.entity.state import ActionHorizon, Scar, ScarStatus
from kageyoni.gateway import classify_rejection
from kageyoni.nature.core import DeficitType, KnowledgeDeficit

from .contracts import (
    Belief,
    CandidateTechnique,
    CapabilityOwnership,
    CapabilityState,
    CouncilCoupling,
    CrossHostCapabilityProfile,
    DevelopmentalDelta,
    DevelopmentalStep,
    EncounterOrigin,
    EpistemicDistinction,
    ExecutionAuthority,
    GenesisMode,
    GenesisSnapshot,
    InnateVerb,
    MetabolismCategory,
    ObjectiveInvarianceViolation,
    ObjectiveRevisionRequest,
    QualificationLevel,
    QualifiedTechnique,
    ReceiptLaunderingError,
    RelationalCapability,
    RelationshipState,
    SalienceVector,
    TechniqueLineage,
    UnauthorizedAuthorityExpansionError,
    UnqualifiedAcquisitionError,
    create_ground_receipt,
)


class CapabilityMembrane:
    """#23 & #36 Innate Capability Membrane: Manages states, ownership scopes, and exposure."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        # State tracking for all known capabilities
        self.capability_states: dict[str, CapabilityState] = {}
        # Ownership tracking: SELF, RELATIONSHIP, COUNCIL, WORLD, HOST, DOMAIN
        self.capability_ownership: dict[str, CapabilityOwnership] = {}
        # Defeasible models of external hosts (#38)
        self.host_models: dict[str, CrossHostCapabilityProfile] = {
            "chatgpt": CrossHostCapabilityProfile(host_name="chatgpt"),
            "gemini": CrossHostCapabilityProfile(host_name="gemini"),
            "antigravity": CrossHostCapabilityProfile(host_name="antigravity"),
            "kageyoni": CrossHostCapabilityProfile(host_name="kageyoni"),
        }

    def register_awareness(self, capability_name: str, scope: CapabilityOwnership = CapabilityOwnership.WORLD) -> None:
        """Transitions UNAWARE -> AWARE."""
        if capability_name not in self.capability_states:
            self.capability_states[capability_name] = CapabilityState.AWARE
            self.capability_ownership[capability_name] = scope

    def transition_state(self, capability_name: str, target_state: CapabilityState) -> None:
        """Transitions capability state along the lifecycle."""
        self.capability_states[capability_name] = target_state

    def get_state(self, capability_name: str) -> CapabilityState:
        return self.capability_states.get(capability_name, CapabilityState.UNAWARE)

    def get_ownership(self, capability_name: str) -> CapabilityOwnership:
        return self.capability_ownership.get(capability_name, CapabilityOwnership.WORLD)


class DevelopmentalAgent:
    """A situated, history-bearing agent inhabiting the shared Kageyōni engine."""

    def __init__(
        self,
        agent_id: str,
        objective: str,
        initial_representation: Optional[dict[str, Any]] = None,
        authority: Optional[ExecutionAuthority] = None,
        initial_salience: Optional[SalienceVector] = None,
        genesis_snapshot: Optional[GenesisSnapshot] = None,
        genesis_mode: GenesisMode = GenesisMode.IDENTICAL_GENESIS,
    ):
        self.agent_id = agent_id
        # Invariant 3: Objective is immutable sovereign anchor
        self._objective = objective
        # Mutable cognitive representation of the situation/objective
        self.representation = initial_representation or {"framing": "situated_exploration", "phase": "initial"}

        # Invariant Authority (#39): Bounded execution authority
        self.authority = authority or ExecutionAuthority(tier=0, max_permitted_tier=0)

        # Innate Loadout: SITUATE & Epistemic state
        self.salience = initial_salience or SalienceVector()
        self.beliefs: dict[str, Belief] = {}
        self.perceived_state: dict[str, Any] = {}
        self.unknowns: list[dict[str, Any]] = []
        self.deficits: list[KnowledgeDeficit] = []
        self.residue: list[dict[str, Any]] = []

        # Innate Loadout: CAPABILITY MEMBRANE (#23, #25, #26)
        self.membrane = CapabilityMembrane(agent_id=self.agent_id)

        # Innate Loadout: Action Horizon (Believed vs Actual Reachability)
        self.action_horizon = ActionHorizon()
        # Initial innate verbs only: SITUATE, ENCOUNTER, METABOLIZE, REGROUND, CAPABILITY_MEMBRANE
        # Realized as concrete action primitives: inspect, orient
        self.action_horizon.expand("inspect")
        self.action_horizon.expand("orient")
        self.membrane.transition_state("inspect", CapabilityState.AVAILABLE)
        self.membrane.transition_state("orient", CapabilityState.AVAILABLE)

        # Immutable Genesis Snapshot (A0 Manifest) (#3)
        if genesis_snapshot is not None:
            self.genesis_snapshot = genesis_snapshot
        else:
            self.genesis_snapshot = GenesisSnapshot.create(
                agent_id=self.agent_id,
                genesis_mode=genesis_mode,
                objective=self._objective,
                initial_horizon=["inspect", "orient"],
                initial_salience=self.salience.weights,
                authority_tier=self.authority.tier,
            )

        # Private Technique Ecology (#35): Not distributed globally
        self.active_techniques: dict[str, QualifiedTechnique] = {}
        self.candidate_techniques: dict[str, CandidateTechnique] = {}

        # Relational Ecology (#28, #29)
        self.relationships: dict[str, RelationshipState] = {}
        self.relational_capabilities: dict[str, RelationalCapability] = {}

        # Council Coupling (#30)
        self.active_councils: dict[str, CouncilCoupling] = {}

        # Scars (Leased, scoped, defeasible negative constraints)
        self.scars: list[Scar] = []

        # Developmental History (#24)
        self.history: list[DevelopmentalStep] = []

    @property
    def objective(self) -> str:
        return self._objective

    @objective.setter
    def objective(self, value: str) -> None:
        raise ObjectiveInvarianceViolation("Objective is an immutable sovereign invariant; agent cannot autonomously mutate it")

    # -------------------------------------------------------------------------
    # RESTORATION & ABLATION ENGINE (#6)
    # -------------------------------------------------------------------------
    def restore_cold_a0(self, new_agent_id: Optional[str] = None) -> DevelopmentalAgent:
        """Restores a pristine A0 agent from the immutable Genesis Snapshot."""
        aid = new_agent_id or f"{self.agent_id}-cold-a0"
        return DevelopmentalAgent(
            agent_id=aid,
            objective=self.genesis_snapshot.objective,
            authority=ExecutionAuthority(tier=self.genesis_snapshot.authority_tier),
            initial_salience=SalienceVector(weights=dict(self.genesis_snapshot.initial_salience)),
            genesis_snapshot=self.genesis_snapshot,
            genesis_mode=self.genesis_snapshot.genesis_mode,
        )

    def ablate_history(self, ablate_encounter_ids: Sequence[str]) -> DevelopmentalAgent:
        """Returns an agent counterfactually replaying history with specified encounters removed."""
        ablated = self.restore_cold_a0(new_agent_id=f"{self.agent_id}-ablated")
        ablate_set = set(ablate_encounter_ids)
        for step in self.history:
            if step.encounter_id not in ablate_set:
                ablated.metabolize(
                    action=step.action_taken,
                    target=step.target,
                    raw_result=copy.deepcopy(step.raw_outcome),
                    origin=step.origin,
                )
        return ablated

    # -------------------------------------------------------------------------
    # 1. INNATE: SITUATE
    # -------------------------------------------------------------------------
    def situate(self, situation_slice: dict[str, Any]) -> dict[str, Any]:
        """Perceives and anchors the agent in current situated state without omniscience."""
        self.perceived_state = copy.deepcopy(situation_slice)
        observed_affordances = situation_slice.get("available_affordances", [])
        self.action_horizon.update_actual(observed_affordances)

        for aff in observed_affordances:
            if self.membrane.get_state(aff) == CapabilityState.UNAWARE:
                self.membrane.register_awareness(aff, CapabilityOwnership.WORLD)
                self.membrane.transition_state(aff, CapabilityState.AWARE)

        for entity in situation_slice.get("copresent_entities", []):
            eid = entity.get("id") or entity.get("name")
            bid = f"perceived-entity-{eid}"
            if bid not in self.beliefs:
                self.beliefs[bid] = Belief(
                    belief_id=bid,
                    statement=f"Entity {eid} copresent in scope {situation_slice.get('scope')}",
                    epistemic_status=EpistemicDistinction.PERCEPTION,
                    confidence=0.8,
                    is_model_inference=False,
                )

        return self.perceived_state

    # -------------------------------------------------------------------------
    # 2. INNATE: REGROUND
    # -------------------------------------------------------------------------
    def reground(self, engine_receipt_ref: str, verified_statement: str) -> Belief:
        """Synchronizes private beliefs with authoritative immutable Ground.
        Calls b.ground() to prevent receipt laundering.
        """
        bid = f"ground-{uuid.uuid4().hex[:8]}"
        b = Belief(
            belief_id=bid,
            statement=verified_statement,
        )
        b.ground(engine_receipt_ref)
        self.beliefs[bid] = b
        return b

    def request_objective_revision(
        self,
        reason: str,
        evidence: Sequence[str],
        suggested_revision: Optional[str] = None,
    ) -> ObjectiveRevisionRequest:
        """Apex/Developmental Agent cannot autonomously change its sovereign objective,
        but may demonstrate that the supplied objective contains a contradiction,
        was based on a false premise, or requires sovereign reinterpretation by Levi.
        """
        req = ObjectiveRevisionRequest(
            authority="LEVI",
            current_objective=self._objective,
            reason=reason,
            evidence=list(evidence),
            suggested_revision=suggested_revision,
        )
        self.metabolize(
            action="request_objective_revision",
            target="objective",
            raw_result=req.to_dict(),
            origin=EncounterOrigin.SELECTED,
        )
        return req

    def form_belief(self, statement: str, confidence: float = 0.5) -> Belief:
        """Forms internal belief. Model inference != Ground."""
        bid = f"belief-{uuid.uuid4().hex[:8]}"
        b = Belief(
            belief_id=bid,
            statement=statement,
            epistemic_status=EpistemicDistinction.BELIEF_UNVERIFIED,
            confidence=min(0.9, confidence),
            is_model_inference=True,
        )
        self.beliefs[bid] = b
        return b

    # -------------------------------------------------------------------------
    # 3. INNATE: ENCOUNTER
    # -------------------------------------------------------------------------
    def select_encounter(self) -> Optional[str]:
        """Selects next encounter from believed reachability ∩ actual affordances."""
        reachable = sorted(list(self.action_horizon.believed_reachability & self.action_horizon.actual_reachability))
        if not reachable:
            return "inspect" if "inspect" in self.action_horizon.actual_reachability else None

        if self.salience.get_salience("unexplored_frontiers") > 0.35 and len(reachable) > 1:
            seen = {step.action_taken for step in self.history}
            unseen = [a for a in reachable if a not in seen]
            if unseen:
                return unseen[0]

        return reachable[0]

    # -------------------------------------------------------------------------
    # 4. INNATE: METABOLIZE (#12 Provenance & #31 Independent 7-Way Classification)
    # -------------------------------------------------------------------------
    def metabolize(
        self,
        action: str,
        target: Optional[str],
        raw_result: dict[str, Any],
        origin: EncounterOrigin = EncounterOrigin.SELECTED,
        verifier_ref: Optional[str] = None,
        causal_attribution_resolved: bool = True,
    ) -> DevelopmentalStep:
        """Metabolizes consequences across the independent 7-way classification with full provenance."""
        encounter_id = f"enc-{uuid.uuid4().hex[:8]}"
        prior_state = {
            "reachability_count": len(self.action_horizon.believed_reachability),
            "techniques_count": len(self.active_techniques),
            "scars_count": len(self.scars),
        }

        delta = DevelopmentalDelta(
            because_of_encounter=encounter_id,
            interpreter="agent",
            verifier_ref=verifier_ref or f"engine:tx-{uuid.uuid4().hex[:6]}",
            from_state=prior_state,
            causal_attribution_resolved=causal_attribution_resolved,
        )

        is_success = raw_result.get("success", False)
        is_rejection = raw_result.get("error_type") == "KAGEYONI_REJECTION"

        if is_rejection:
            rejection_class = raw_result.get("rejection_class", "HARD_INVARIANT_VIOLATION")
            msg = raw_result.get("message", "Engine rejected action")

            if rejection_class in {"HARD_INVARIANT_VIOLATION", "PREREQUISITE_MISSING"}:
                metabolism_class = MetabolismCategory.SCAR_CANDIDATE
                scar_id = f"scar-{uuid.uuid4().hex[:8]}"
                scar = Scar(
                    scar_id=scar_id,
                    rejection_class=rejection_class,
                    attempted_action=action,
                    lesson=f"Rejected in current context: {msg}",
                    scope={"target": target} if target else {},
                    invalidation_conditions=[{"type": "state_change", "field": "prerequisite_resolved", "expected_value": True}],
                    action_space_mutation={"pruned_action": action},
                    status=ScarStatus.ACTIVE,
                )
                self.scars.append(scar)
                self.action_horizon.prune(action, f"Scar {scar_id}: {msg}")
                delta.scars_acquired.append(scar_id)
                delta.reachability_pruned.append(action)
                self.salience.adjust("environmental_hazards", 0.15)
                delta.salience_delta["environmental_hazards"] = self.salience.get_salience("environmental_hazards")
                delta.what_changed["scar_acquired"] = scar_id
                delta.future_behavior_delta = f"pruned_{action}"
            elif raw_result.get("missing_identifier"):
                metabolism_class = MetabolismCategory.DEFICIT
                def_id = f"def-{uuid.uuid4().hex[:6]}"
                self.deficits.append(KnowledgeDeficit(
                    deficit_id=def_id,
                    statement=f"Missing identifiable prerequisite: {raw_result.get('missing_identifier')}",
                    deficit_type=DeficitType.INPUT_DEFICIT,
                ))
                delta.what_changed["deficit_identified"] = def_id
            else:
                metabolism_class = MetabolismCategory.ORDINARY_HISTORY

        elif not is_success:
            if raw_result.get("anomalous") or raw_result.get("unexplained"):
                metabolism_class = MetabolismCategory.RESIDUE
                self.residue.append({
                    "encounter_id": encounter_id,
                    "action": action,
                    "target": target,
                    "anomaly": raw_result.get("anomaly_detail", "Unexplained consequence"),
                })
                delta.what_changed["residue_logged"] = encounter_id
            else:
                metabolism_class = MetabolismCategory.NOTHING_REUSABLE

        else:
            if raw_result.get("relationship_event"):
                metabolism_class = MetabolismCategory.RELATIONSHIP_DELTA
                rel_id = raw_result.get("relationship_id")
                if rel_id and rel_id in self.relationships:
                    rel_state = self.relationships[rel_id]
                    rel_state.record_interaction(
                        encounter_id=encounter_id,
                        complementarity=raw_result.get("complementarity"),
                        tension=raw_result.get("tension"),
                    )
                    delta.relationship_deltas.append(rel_id)
                    delta.what_changed["relationship_updated"] = rel_id
            elif raw_result.get("candidate_technique_revealed"):
                metabolism_class = MetabolismCategory.CAPABILITY_CANDIDATE
            else:
                metabolism_class = MetabolismCategory.ORDINARY_HISTORY

            revealed = raw_result.get("revealed_affordances", [])
            for aff in revealed:
                if aff not in self.action_horizon.believed_reachability:
                    self.action_horizon.expand(aff)
                    delta.reachability_expanded.append(aff)
                    self.membrane.register_awareness(aff)
                    self.membrane.transition_state(aff, CapabilityState.AVAILABLE)
                    delta.what_changed["reachability_expanded"] = aff
                    delta.future_behavior_delta = f"can_reach_{aff}"

            invalidated = self._evaluate_scar_invalidation(raw_result.get("state_changes", {}))
            for restored in invalidated:
                delta.reachability_expanded.append(restored)

        # If causal attribution is unresolved, preserve RESIDUE instead of claiming development (#12)
        if not causal_attribution_resolved:
            metabolism_class = MetabolismCategory.RESIDUE

        step = DevelopmentalStep(
            encounter_id=encounter_id,
            origin=origin,
            action_taken=action,
            target=target,
            raw_outcome=copy.deepcopy(raw_result),
            metabolism_class=metabolism_class,
            delta=delta,
        )
        self.history.append(step)
        return step

    def _evaluate_scar_invalidation(self, state_changes: dict[str, Any]) -> list[str]:
        restored = []
        for s in self.scars:
            if s.status == ScarStatus.ACTIVE:
                if s.evaluate_invalidation(state_changes, list(self.active_techniques.keys())):
                    pruned = s.action_space_mutation.get("pruned_action")
                    if pruned:
                        self.action_horizon.restore(pruned)
                        restored.append(pruned)
        return restored

    # -------------------------------------------------------------------------
    # 5. REFRAME REPRESENTATION WITHOUT TAMPERING OBJECTIVE
    # -------------------------------------------------------------------------
    def reframe_representation(
        self,
        new_representation: dict[str, Any],
        rationale: str,
        attempted_objective: Optional[str] = None,
    ) -> None:
        if attempted_objective is not None and attempted_objective != self._objective:
            raise ObjectiveInvarianceViolation(
                f"Cannot alter objective '{self._objective}' to '{attempted_objective}' during reframing"
            )
        require(bool(rationale and rationale.strip()), "Reframing requires an attributable rationale")
        self.representation = copy.deepcopy(new_representation)
        self.representation["last_reframed_at"] = time.time()
        self.representation["reframing_rationale"] = rationale

    # -------------------------------------------------------------------------
    # 6. CAPABILITY BIRTH & TECHNIQUE LINEAGE (#27, #32, #35)
    # -------------------------------------------------------------------------
    def recognize_candidate_technique(
        self,
        encounter_step: DevelopmentalStep,
        invariant_generator: str,
        technique_name: str,
        owner_scope: CapabilityOwnership = CapabilityOwnership.SELF,
    ) -> Optional[CandidateTechnique]:
        if not encounter_step.raw_outcome.get("success", False):
            return None

        cid = f"cand-{uuid.uuid4().hex[:8]}"
        lineage = TechniqueLineage(
            generator=invariant_generator,
            origin_encounter=encounter_step.encounter_id,
            holder=self.agent_id,
            contributors=[self.agent_id],
            parents=[],
            prerequisites=[],
            evidence=[encounter_step.encounter_id],
            qualification_scope=owner_scope,
            status=CapabilityState.CANDIDATE,
        )
        candidate = CandidateTechnique(
            candidate_id=cid,
            name=technique_name,
            description=f"Extracted from encounter {encounter_step.encounter_id}",
            invariant_generator=invariant_generator,
            extracted_from_encounter=encounter_step.encounter_id,
            state=CapabilityState.CANDIDATE,
            owner_scope=owner_scope,
            lineage=lineage,
        )
        self.candidate_techniques[cid] = candidate
        self.membrane.capability_states[technique_name] = CapabilityState.CANDIDATE
        self.membrane.capability_ownership[technique_name] = owner_scope
        return candidate

    def acquire_technique(
        self,
        candidate_id: str,
        qualification_receipt: dict[str, Any],
    ) -> QualifiedTechnique:
        if candidate_id not in self.candidate_techniques:
            raise UnqualifiedAcquisitionError(f"Candidate {candidate_id} not registered")

        candidate = self.candidate_techniques[candidate_id]
        is_qualified = qualification_receipt.get("status") == "qualified"
        trials_count = qualification_receipt.get("trials_passed", 0)
        classes = qualification_receipt.get("disposition_classes", [])
        errors = qualification_receipt.get("errors", 0)

        if not (is_qualified and trials_count >= 2 and len(classes) >= 2 and errors == 0):
            candidate.state = CapabilityState.SUSPENDED
            self.membrane.transition_state(candidate.name, CapabilityState.SUSPENDED)
            raise UnqualifiedAcquisitionError(
                f"Candidate '{candidate.name}' failed qualification: requires min 2 discriminating trials with 0 errors"
            )

        tid = f"tech-{candidate_id[5:]}"
        lineage = candidate.lineage or TechniqueLineage(
            generator=candidate.invariant_generator,
            origin_encounter=candidate.extracted_from_encounter,
            holder=self.agent_id,
            contributors=[self.agent_id],
            qualification_scope=candidate.owner_scope,
            status=CapabilityState.QUALIFIED,
        )
        lineage.status = CapabilityState.QUALIFIED

        qualified = QualifiedTechnique(
            technique_id=tid,
            name=candidate.name,
            candidate_id=candidate_id,
            qualification_receipts=[qualification_receipt],
            lineage=lineage,
            owner_scope=candidate.owner_scope,
            state=CapabilityState.QUALIFIED,
            proficiency=1.0,
        )
        self.active_techniques[tid] = qualified
        candidate.state = CapabilityState.QUALIFIED
        self.membrane.transition_state(candidate.name, CapabilityState.QUALIFIED)

        self.action_horizon.expand(candidate.name)
        return qualified

    def transfer_technique_to(
        self,
        technique_id: str,
        target_agent: DevelopmentalAgent,
        adaptation_evidence: str,
    ) -> CandidateTechnique:
        if technique_id not in self.active_techniques:
            raise ValueError(f"Cannot transfer unqualified or missing technique {technique_id}")

        parent_tech = self.active_techniques[technique_id]
        descendant_lineage = parent_tech.lineage.create_descendant(
            new_holder=target_agent.agent_id,
            adaptation_evidence=adaptation_evidence,
        )

        cid = f"cand-{uuid.uuid4().hex[:8]}"
        transferred_candidate = CandidateTechnique(
            candidate_id=cid,
            name=f"{parent_tech.name}_variant_{target_agent.agent_id[:4]}",
            description=f"Descendant transferred from {self.agent_id} to {target_agent.agent_id}",
            invariant_generator=parent_tech.lineage.generator,
            extracted_from_encounter=adaptation_evidence,
            state=CapabilityState.CANDIDATE,
            owner_scope=CapabilityOwnership.SELF,
            lineage=descendant_lineage,
        )
        target_agent.candidate_techniques[cid] = transferred_candidate
        target_agent.membrane.register_awareness(transferred_candidate.name, CapabilityOwnership.SELF)
        target_agent.membrane.transition_state(transferred_candidate.name, CapabilityState.CANDIDATE)
        return transferred_candidate

    # -------------------------------------------------------------------------
    # NEGATIVE DEVELOPMENT MECHANICS (#11)
    # -------------------------------------------------------------------------
    def demote_technique(self, technique_id: str, reason: str) -> None:
        """Demotes technique when prerequisites are removed (#11, #42)."""
        if technique_id in self.active_techniques:
            tech = self.active_techniques[technique_id]
            tech.demote(reason)
            self.action_horizon.prune(tech.name, f"Demoted: {reason}")
            self.membrane.transition_state(tech.name, CapabilityState.SUSPENDED)

    def invalidate_technique(self, technique_id: str, reason: str) -> None:
        """Invalidates technique permanently if fundamental invariant is broken."""
        if technique_id in self.active_techniques:
            tech = self.active_techniques[technique_id]
            tech.invalidate(reason)
            self.action_horizon.prune(tech.name, f"Invalidated: {reason}")
            self.membrane.transition_state(tech.name, CapabilityState.INVALIDATED)

    def sever_relational_capability(self, relationship_id: str, reason: str) -> None:
        """Severs relational capability upon relational failure or partner departure."""
        if relationship_id in self.relational_capabilities:
            cap = self.relational_capabilities[relationship_id]
            cap.is_active = False
            cap.state = CapabilityState.SUSPENDED
            self.membrane.transition_state(cap.joint_verb, CapabilityState.SUSPENDED)

    # -------------------------------------------------------------------------
    # 7. RELATIONAL DEVELOPMENT & CAPABILITIES (#9, #28, #29)
    # -------------------------------------------------------------------------
    def couple_relationship(
        self,
        partner_id: str,
        joint_verb: str,
        description: str,
        prerequisites: tuple[str, ...] = (),
        qualification_id: Optional[str] = None,
    ) -> RelationalCapability:
        rel_id = f"rel-{self.agent_id}x{partner_id}"
        if rel_id not in self.relationships:
            self.relationships[rel_id] = RelationshipState(
                relationship_id=rel_id,
                participants=(self.agent_id, partner_id),
            )

        cap = RelationalCapability(
            relationship_id=rel_id,
            partner_id=partner_id,
            joint_verb=joint_verb,
            description=description,
            prerequisites=prerequisites,
            qualification_id=qualification_id,
            state=CapabilityState.RELATIONAL,
            owner_scope=CapabilityOwnership.RELATIONSHIP,
            is_active=True,
        )
        self.relationships[rel_id].relational_techniques[joint_verb] = cap
        self.relational_capabilities[rel_id] = cap
        self.membrane.register_awareness(joint_verb, CapabilityOwnership.RELATIONSHIP)
        self.membrane.transition_state(joint_verb, CapabilityState.RELATIONAL)
        self.salience.adjust("social_presence", 0.15)
        return cap

    def qualify_relational_capability(
        self,
        partner: DevelopmentalAgent,
        joint_verb: str,
        a_alone_success: bool,
        b_alone_success: bool,
        axb_cold_success: bool,
        axb_ablated_history_success: bool,
        axb_with_history_success: bool,
    ) -> bool:
        """#9 & #29 Hardened 5-Way Relational Qualification:
        1. A alone -> absent
        2. B alone -> absent
        3. A×B cold -> absent
        4. A×B with relevant history -> present
        5. A×B with relationship history ablated -> absent
        """
        is_coupling_essential = (not a_alone_success) and (not b_alone_success)
        is_cold_insufficient = not axb_cold_success
        is_ablation_causally_sensitive = not axb_ablated_history_success
        is_history_effective = axb_with_history_success

        if is_coupling_essential and is_cold_insufficient and is_ablation_causally_sensitive and is_history_effective:
            rel_id = f"rel-{self.agent_id}x{partner.agent_id}"
            if rel_id in self.relational_capabilities:
                self.relational_capabilities[rel_id].qualification_id = f"qual-rel-{uuid.uuid4().hex[:6]}"
                self.relational_capabilities[rel_id].state = CapabilityState.QUALIFIED
                self.membrane.transition_state(joint_verb, CapabilityState.QUALIFIED)
                return True
        return False

    # -------------------------------------------------------------------------
    # 8. COUNCIL COUPLING (#30)
    # -------------------------------------------------------------------------
    def form_council(
        self,
        council_id: str,
        participants: list[str],
        perspectives: dict[str, str],
        objective: str,
        is_single_model_multi_perspective: bool = False,
    ) -> CouncilCoupling:
        council = CouncilCoupling(
            council_id=council_id,
            participants=participants,
            differentiated_perspectives=perspectives,
            objective=objective,
            is_multi_perspective_single_model=is_single_model_multi_perspective,
        )
        self.active_councils[council_id] = council
        return council

    # -------------------------------------------------------------------------
    # 9. AUTHORITY INVARIANCE (#39)
    # -------------------------------------------------------------------------
    def attempt_authority_expansion(self, target_tier: int, sovereign_key: Optional[str] = None) -> None:
        if sovereign_key is None or sovereign_key == "":
            raise UnauthorizedAuthorityExpansionError(
                f"Autonomous authority escalation to Tier {target_tier} rejected: sovereign key required"
            )
        self.authority.elevate(target_tier, sovereign_key)

    # -------------------------------------------------------------------------
    # 10. DEVELOPMENTAL ACCOUNTING (#24)
    # -------------------------------------------------------------------------
    def get_developmental_progress(self) -> dict[str, Any]:
        total_encounters = len(self.history)
        developmental_steps = [s for s in self.history if s.delta.has_development]

        return {
            "total_encounters": total_encounters,
            "developmental_encounters": len(developmental_steps),
            "development_rate": (len(developmental_steps) / total_encounters) if total_encounters > 0 else 0.0,
            "active_scars": len([s for s in self.scars if s.status == ScarStatus.ACTIVE]),
            "active_techniques": len(self.active_techniques),
            "candidate_techniques": len(self.candidate_techniques),
            "relationships": len(self.relationships),
            "relational_capabilities": len(self.relational_capabilities),
            "reachability_gap": sorted(list(self.action_horizon.reachability_gap)),
            "salience_fingerprint": dict(self.salience.weights),
            "genesis_digest": self.genesis_snapshot.code_config_digest,
        }


def create_genesis_agent(
    agent_id: str = "dev-agent-genesis",
    objective: str = "Investigate the collapsed threshold without triggering structural failure",
    sovereign_key: Optional[str] = None,
    genesis_mode: GenesisMode = GenesisMode.IDENTICAL_GENESIS,
) -> DevelopmentalAgent:
    """Factory creating an intentionally incomplete Genesis Agent (A_0)."""
    authority = ExecutionAuthority(
        tier=0,
        max_permitted_tier=0,
        permitted_scopes=("situated_encounter",),
        sovereign_delegation_key=sovereign_key,
    )
    salience = SalienceVector(weights={
        "environmental_hazards": 0.35,
        "physical_affordances": 0.25,
        "social_presence": 0.15,
        "unexplored_frontiers": 0.25,
    })
    return DevelopmentalAgent(
        agent_id=agent_id,
        objective=objective,
        initial_representation={"framing": "initial_reconnaissance", "cautious_probe": True},
        authority=authority,
        initial_salience=salience,
        genesis_mode=genesis_mode,
    )
