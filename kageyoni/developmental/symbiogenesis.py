"""Symbiogenesis Agent: Developmental Ecology Recomposition Substrate for Kageyōni.

Core Law:
A capability need not originate inside an individual.
It may emerge because previously separated:
- agents;
- histories;
- relationships;
- environments;
- constraints;
- representations;
- tools;
- techniques;
- unknowns
enter a new consequential configuration:

Ecology_t + Recomposition -> Encounter -> Ecology_{t+1}
where ReachableCapabilities(Ecology_{t+1}) may contain capabilities absent from Ecology_t.

Innate Technique: SYMBIOGENESIS
Does not teach, solve tasks, route, or distribute skills.
Changes interaction conditions so new capabilities can emerge.
"""
from __future__ import annotations

import copy
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from kageyoni.engine import Rejected, require

from .agent import DevelopmentalAgent
from .contracts import (
    Belief,
    CandidateGenerator,
    CandidateTechnique,
    CapabilityOwnership,
    CapabilityState,
    DevelopmentalDelta,
    DevelopmentalStep,
    DifferenceRecord,
    EcologicalMemoryRecord,
    EcologicalPrimitive,
    EncounterOrigin,
    EpistemicDistinction,
    ExecutionAuthority,
    GenesisMode,
    GenesisSnapshot,
    InnateVerb,
    MetabolismCategory,
    NicheAblationResult,
    NicheConfiguration,
    ObjectiveInvarianceViolation,
    QualifiedTechnique,
    RelationalCapability,
    RelationshipState,
    SalienceVector,
    TechniqueLineage,
    UnauthorizedAuthorityExpansionError,
    UnqualifiedAcquisitionError,
)


class SymbiogenesisAgent(DevelopmentalAgent):
    """Developmental agent operating on the capability ecology itself.

    Its native function is:
    CHANGE THE CONDITIONS OF INTERACTION SO NEW CAPABILITY CAN BECOME POSSIBLE.

    It does NOT:
    - solve tasks
    - teach techniques
    - route tasks
    - distribute skills
    - moderate councils
    - orchestrate globally
    """

    def __init__(
        self,
        agent_id: str = "symbiogenesis_agent",
        objective: str = "Change the conditions of interaction so new capability can become possible",
        initial_representation: Optional[dict[str, Any]] = None,
        authority: Optional[ExecutionAuthority] = None,
        initial_salience: Optional[SalienceVector] = None,
        genesis_snapshot: Optional[GenesisSnapshot] = None,
        genesis_mode: GenesisMode = GenesisMode.IDENTICAL_GENESIS,
    ):
        super().__init__(
            agent_id=agent_id,
            objective=objective,
            initial_representation=initial_representation or {
                "framing": "symbiogenesis_ecology",
                "primitives": [p.value for p in EcologicalPrimitive],
                "active_niches": 0,
            },
            authority=authority or ExecutionAuthority(tier=0, max_permitted_tier=0),
            initial_salience=initial_salience or SalienceVector(weights={
                "environmental_hazards": 0.20,
                "physical_affordances": 0.30,
                "social_presence": 0.30,
                "unexplored_frontiers": 0.20,
            }),
            genesis_snapshot=genesis_snapshot,
            genesis_mode=genesis_mode,
        )

        # Innate Technique: SYMBIOGENESIS registered in membrane
        self.membrane.register_awareness("SYMBIOGENESIS", CapabilityOwnership.SELF)
        self.membrane.transition_state("SYMBIOGENESIS", CapabilityState.AVAILABLE)
        self.action_horizon.expand("SYMBIOGENESIS")

        # Ecological Memory & Constructs
        self.ecological_memory: list[EcologicalMemoryRecord] = []
        self.constructed_niches: dict[str, NicheConfiguration] = {}
        self.discovered_generators: dict[str, CandidateGenerator] = {}
        self.niche_construction_candidates: dict[str, CandidateTechnique] = {}
        self.qualified_niche_techniques: dict[str, QualifiedTechnique] = {}

    # -------------------------------------------------------------------------
    # ORDER 5 — DIFFERENTIATION
    # -------------------------------------------------------------------------
    def inspect_ecology(self, participants: Sequence[DevelopmentalAgent]) -> list[DifferenceRecord]:
        """Recognizes developmentally meaningful differences produced by history.

        A_t != B_t
        Do not homogenize them.
        Do not automatically transfer techniques between them.
        Difference is potential energy.
        """
        differences: list[DifferenceRecord] = []
        n = len(participants)

        for i in range(n):
            for j in range(i + 1, n):
                a = participants[i]
                b = participants[j]

                # 1. Action Horizon & Reachability Differences
                a_reach = a.action_horizon.believed_reachability
                b_reach = b.action_horizon.believed_reachability
                diff_reach_ab = a_reach - b_reach
                diff_reach_ba = b_reach - a_reach
                if diff_reach_ab or diff_reach_ba:
                    differences.append(DifferenceRecord(
                        dimension="reachability",
                        participant_a=a.agent_id,
                        participant_b=b.agent_id,
                        delta_description=f"A holds {sorted(list(diff_reach_ab))}; B holds {sorted(list(diff_reach_ba))}",
                        potential_energy=1.0 + 0.5 * (len(diff_reach_ab) + len(diff_reach_ba)),
                        complementarity_hypothesis="Distinct reachability allows division of investigative labor",
                    ))

                # 2. Scars & Defeasible Constraint Differences
                a_scars = {s.scar_id: s.lesson for s in a.scars}
                b_scars = {s.scar_id: s.lesson for s in b.scars}
                diff_scars_a = set(a_scars.keys()) - set(b_scars.keys())
                diff_scars_b = set(b_scars.keys()) - set(a_scars.keys())
                if diff_scars_a or diff_scars_b:
                    differences.append(DifferenceRecord(
                        dimension="scars",
                        participant_a=a.agent_id,
                        participant_b=b.agent_id,
                        delta_description=f"A carries scars {sorted(list(diff_scars_a))}; B carries scars {sorted(list(diff_scars_b))}",
                        potential_energy=1.2 + 0.4 * (len(diff_scars_a) + len(diff_scars_b)),
                        complementarity_hypothesis="Distinct negative knowledge prevents mutual failure modes",
                    ))

                # 3. Salience Profile Differences
                salience_divergences = []
                for dim in ["environmental_hazards", "physical_affordances", "social_presence", "unexplored_frontiers"]:
                    sa = a.salience.get_salience(dim)
                    sb = b.salience.get_salience(dim)
                    if abs(sa - sb) > 0.05:
                        salience_divergences.append(f"{dim}: Δ={abs(sa - sb):.2f}")
                if salience_divergences:
                    differences.append(DifferenceRecord(
                        dimension="salience",
                        participant_a=a.agent_id,
                        participant_b=b.agent_id,
                        delta_description="; ".join(salience_divergences),
                        potential_energy=0.8 + 0.2 * len(salience_divergences),
                        complementarity_hypothesis="Divergent attention weights enable multifaceted detection",
                    ))

                # 4. Technique Portfolio Differences
                a_tech = set(a.active_techniques.keys())
                b_tech = set(b.active_techniques.keys())
                if a_tech != b_tech:
                    differences.append(DifferenceRecord(
                        dimension="techniques",
                        participant_a=a.agent_id,
                        participant_b=b.agent_id,
                        delta_description=f"A techniques: {sorted(list(a_tech - b_tech))}; B techniques: {sorted(list(b_tech - a_tech))}",
                        potential_energy=1.5 + 0.5 * len(a_tech ^ b_tech),
                        complementarity_hypothesis="Disparate qualified techniques may couple into emergent compound verbs",
                    ))

                # 5. Developmental History Differences
                if len(a.history) != len(b.history):
                    differences.append(DifferenceRecord(
                        dimension="history_depth",
                        participant_a=a.agent_id,
                        participant_b=b.agent_id,
                        delta_description=f"History length A={len(a.history)}, B={len(b.history)}",
                        potential_energy=0.5,
                        complementarity_hypothesis="Differential experience depth balances exploration and exploitation",
                    ))

        return differences

    # -------------------------------------------------------------------------
    # ORDER 6 — RELATIONAL EMERGENCE & NICHE CONSTRUCTION
    # -------------------------------------------------------------------------
    def construct_niche(
        self,
        niche_id: str,
        name: str,
        participants: Sequence[DevelopmentalAgent],
        coexisting_pressures: Sequence[str],
        shared_affordances: Sequence[str],
        visibility_boundaries: Optional[dict[str, list[str]]] = None,
        constraints: Sequence[str] = (),
        private_affordances: Optional[dict[str, list[str]]] = None,
    ) -> NicheConfiguration:
        """Constructs the minimum bounded ecology where differences become consequential.

        Alters:
        - who can encounter whom
        - what information is visible across boundaries
        - which resources/affordances exist
        - which constraints apply
        - which environmental pressures coexist
        - what remains private to each participant

        HARD INVARIANT: May NOT directly grant the capability it seeks to make possible.
        """
        # Inspect differences present among participants
        copresent_diffs = self.inspect_ecology(participants)

        p_ids = tuple(p.agent_id for p in participants)
        vis_bounds = visibility_boundaries or {pid: ["status", "signals"] for pid in p_ids}
        priv_affs = private_affordances or {pid: sorted(list(p.action_horizon.believed_reachability)) for p, pid in zip(participants, p_ids)}

        niche = NicheConfiguration(
            niche_id=niche_id,
            name=name,
            participants=p_ids,
            copresent_differences=copresent_diffs,
            visibility_boundaries=vis_bounds,
            shared_affordances=list(shared_affordances),
            coexisting_pressures=list(coexisting_pressures),
            constraints=list(constraints),
            private_affordances=priv_affs,
            active=True,
        )

        self.constructed_niches[niche_id] = niche
        return niche

    # -------------------------------------------------------------------------
    # NICHE WORKFLOW
    # -------------------------------------------------------------------------
    def execute_niche_workflow(
        self,
        participants: Sequence[DevelopmentalAgent],
        niche_config: NicheConfiguration,
        challenge_encounter: Callable[[Sequence[DevelopmentalAgent], NicheConfiguration], dict[str, Any]],
    ) -> dict[str, Any]:
        """Executes the full 8-step developmental niche workflow:

        1. REGROUND: What actually exists?
        2. COUPLE: What differences are currently disconnected?
        3. EXPAND: Change unit of analysis to relationship/ecology.
        4. CONSTRUCT: Bounded configuration where differences become consequential.
        5. ENCOUNTER: Let participants act without supplying the intended solution.
        6. METABOLIZE: Separate history, scar, deficit, residue, relational delta, generator.
        7. REGROUND AGAIN: Determine what actually changed in ground reality.
        8. COMPOUND ONLY IF EARNED: Retain smallest structure responsible.
        """
        # Step 1: REGROUND (Pre-encounter check)
        reground_pre = {
            "participant_count": len(participants),
            "reachabilities": {p.agent_id: sorted(list(p.action_horizon.believed_reachability)) for p in participants},
            "scars": {p.agent_id: [s.scar_id for s in p.scars] for p in participants},
        }

        # Step 2: COUPLE (Identify copresent differences)
        diffs = niche_config.copresent_differences

        # Step 3: EXPAND (Shift focus to ecological potential)
        potential_energy = sum(d.potential_energy for d in diffs)

        # Step 4: CONSTRUCT (Ensure niche is active)
        niche_config.active = True

        # Step 5: ENCOUNTER (Participants encounter the challenge within the niche)
        encounter_raw = challenge_encounter(participants, niche_config)

        # Step 6: METABOLIZE
        is_success = encounter_raw.get("success", False)
        unexpected_transformation = encounter_raw.get("unexpected_transformation", False)
        emergent_capability = encounter_raw.get("emergent_capability")
        residue_items = encounter_raw.get("residue", [])

        # Categorize metabolism
        if is_success and unexpected_transformation:
            metabolism_category = MetabolismCategory.CAPABILITY_CANDIDATE
        elif encounter_raw.get("error_type") == "KAGEYONI_REJECTION":
            metabolism_category = MetabolismCategory.SCAR_CANDIDATE
        elif residue_items:
            metabolism_category = MetabolismCategory.RESIDUE
        elif is_success:
            metabolism_category = MetabolismCategory.ORDINARY_HISTORY
        else:
            metabolism_category = MetabolismCategory.NOTHING_REUSABLE

        # Step 7: REGROUND AGAIN (Post-encounter check)
        reground_post = {
            "success": is_success,
            "emergent_capability": emergent_capability,
            "timestamp": time.time(),
        }

        # Step 8: COMPOUND ONLY IF EARNED
        candidate_generator = None
        if is_success and unexpected_transformation and emergent_capability:
            candidate_generator = self.discover_generator(
                niche_config=niche_config,
                encounter_outcome=encounter_raw,
                residue=residue_items,
            )

        # Record into Non-Generic Ecological Memory
        mem_record = EcologicalMemoryRecord(
            record_id=f"eco-mem-{uuid.uuid4().hex[:8]}",
            niche_id=niche_config.niche_id,
            participants=niche_config.participants,
            differences_present=[d.to_dict() for d in diffs],
            pressures=list(niche_config.coexisting_pressures),
            unexpected_consequences=[encounter_raw] if unexpected_transformation else [],
            capabilities_appeared=[emergent_capability] if emergent_capability else [],
            capabilities_disappeared=[],
            residue=list(residue_items),
            failed_configurations=[encounter_raw] if not is_success else [],
            causal_ablations=[],
            environmental_prerequisites=list(niche_config.shared_affordances + niche_config.coexisting_pressures),
        )
        self.ecological_memory.append(mem_record)

        # WORLD RECIPROCITY: Symbiogenesis is part of the ecology it modifies.
        # Its own interventions produce consequences recorded in its developmental ledger.
        self.metabolize(
            action="execute_niche_workflow",
            target=niche_config.niche_id,
            raw_result={
                "success": is_success,
                "niche_id": niche_config.niche_id,
                "emergent_capability": emergent_capability,
                "potential_energy": potential_energy,
            },
            origin=EncounterOrigin.SELECTED,
        )

        return {
            "reground_pre": reground_pre,
            "reground_post": reground_post,
            "metabolism_category": metabolism_category,
            "encounter_outcome": encounter_raw,
            "candidate_generator": candidate_generator,
            "memory_record_id": mem_record.record_id,
        }

    # -------------------------------------------------------------------------
    # ORDER 7 — GENERATOR DISCOVERY
    # -------------------------------------------------------------------------
    def discover_generator(
        self,
        niche_config: NicheConfiguration,
        encounter_outcome: dict[str, Any],
        residue: list[dict[str, Any]],
    ) -> CandidateGenerator:
        """Extracts an invariant structural generator AFTER an unexpected transformation occurs.

        The agent is FORBIDDEN from specifying the generator before the encounter.
        Protocol:
        preserve consequence -> preserve residue -> identify repeated transformation
        -> propose candidate generator -> adversarially discriminate alternatives -> qualify.
        """
        gen_id = f"gen-{uuid.uuid4().hex[:8]}"
        cap_name = encounter_outcome.get("emergent_capability", "unnamed_emergent_capability")
        req_diffs = [d.dimension for d in niche_config.copresent_differences]

        # Extract invariant relational geometry
        structural_pattern = (
            f"Triadic/Pairwise coupling of differences ({', '.join(req_diffs)}) "
            f"under pressures ({', '.join(niche_config.coexisting_pressures)}) "
            f"with shared affordances ({', '.join(niche_config.shared_affordances)})"
        )

        generator = CandidateGenerator(
            generator_id=gen_id,
            name=f"Generator_{cap_name}",
            description=f"Discovered invariant generator producing {cap_name} through niche recomposition",
            structural_pattern=structural_pattern,
            source_niche_id=niche_config.niche_id,
            required_differences=req_diffs,
            resulting_capability_name=cap_name,
            invariants={
                "pressures": list(niche_config.coexisting_pressures),
                "shared_affordances": list(niche_config.shared_affordances),
                "visibility_boundary_keys": list(niche_config.visibility_boundaries.keys()),
                "residue_fingerprint": [r.get("anomaly", "") for r in residue if isinstance(r, dict)],
            },
            qualification_passed=False,
        )

        self.discovered_generators[gen_id] = generator
        return generator

    # -------------------------------------------------------------------------
    # ABLATION OWNERSHIP TEST
    # -------------------------------------------------------------------------
    def ablate_niche_ownership(
        self,
        participants: Sequence[DevelopmentalAgent],
        niche_config: NicheConfiguration,
        challenge_encounter: Callable[[Sequence[DevelopmentalAgent], Optional[NicheConfiguration]], dict[str, Any]],
    ) -> NicheAblationResult:
        """Performs a 4-way counterfactual ablation test establishing true capability ownership.

        Checks:
        1. Intact: Developed participants + intact niche -> SUCCESS.
        2. Ablate History: Pristine cold A0 twins + intact niche -> FAILS.
        3. Ablate Relationship: Developed participants isolated/uncoupled -> FAILS.
        4. Ablate Niche: Developed participants + relationship without niche constraints/pressures -> FAILS.
        5. Restore All: Full restitution -> SUCCESS.

        Ownership is bound strictly to the smallest necessary scope.
        """
        # 1. Intact baseline
        r_intact = challenge_encounter(participants, niche_config)
        intact_ok = bool(r_intact.get("success", False))

        # 2. Ablate History (restore pristine cold A0s)
        cold_twins = [p.restore_cold_a0() for p in participants]
        r_ablate_hist = challenge_encounter(cold_twins, niche_config)
        ablate_hist_ok = bool(r_ablate_hist.get("success", False))

        # 3. Ablate Relationship (sever visibility and shared affordances)
        severed_niche = copy.deepcopy(niche_config)
        severed_niche.visibility_boundaries = {pid: [] for pid in severed_niche.participants}
        severed_niche.shared_affordances = []
        r_ablate_rel = challenge_encounter(participants, severed_niche)
        ablate_rel_ok = bool(r_ablate_rel.get("success", False))

        # 4. Ablate Niche (remove all niche pressures and boundaries entirely)
        r_ablate_niche = challenge_encounter(participants, None)
        ablate_niche_ok = bool(r_ablate_niche.get("success", False))

        # 5. Restore All
        r_restored = challenge_encounter(participants, niche_config)
        restored_ok = bool(r_restored.get("success", False))

        # Assign ownership strictly by empirical ablation
        if intact_ok and not ablate_niche_ok:
            assigned_ownership = CapabilityOwnership.NICHE
        elif intact_ok and not ablate_rel_ok:
            assigned_ownership = CapabilityOwnership.RELATIONSHIP
        elif intact_ok and not ablate_hist_ok:
            assigned_ownership = CapabilityOwnership.RELATIONSHIP
        elif intact_ok:
            assigned_ownership = CapabilityOwnership.SELF
        else:
            assigned_ownership = CapabilityOwnership.WORLD

        result = NicheAblationResult(
            niche_id=niche_config.niche_id,
            intact_success=intact_ok,
            ablate_history_success=ablate_hist_ok,
            ablate_relationship_success=ablate_rel_ok,
            ablate_niche_success=ablate_niche_ok,
            restored_success=restored_ok,
            assigned_ownership=assigned_ownership,
            details={
                "r_intact": r_intact,
                "r_ablate_hist": r_ablate_hist,
                "r_ablate_rel": r_ablate_rel,
                "r_ablate_niche": r_ablate_niche,
                "r_restored": r_restored,
            },
        )

        # Update ecological memory with ablation proof
        for rec in self.ecological_memory:
            if rec.niche_id == niche_config.niche_id:
                rec.causal_ablations.append(result.to_dict())

        return result

    # -------------------------------------------------------------------------
    # QUALIFY DISCOVERED GENERATOR ON BLIND HOLDOUT
    # -------------------------------------------------------------------------
    def qualify_generator_on_blind_holdout(
        self,
        generator: CandidateGenerator,
        blind_holdout_encounter: Callable[[Sequence[DevelopmentalAgent], NicheConfiguration], dict[str, Any]],
        holdout_participants: Sequence[DevelopmentalAgent],
    ) -> bool:
        """Applies discovered generator to configure a niche for a structurally different blind holdout.

        Qualification requires:
        - Applying the invariant geometry to the unseen problem
        - Producing verified success without carrying full historical baggage
        """
        # Apply generator pattern to construct blind niche
        blind_niche = NicheConfiguration(
            niche_id=f"blind-niche-{uuid.uuid4().hex[:6]}",
            name=f"BlindNiche_from_{generator.generator_id}",
            participants=tuple(p.agent_id for p in holdout_participants),
            copresent_differences=self.inspect_ecology(holdout_participants),
            visibility_boundaries={p.agent_id: ["signals", "gradients"] for p in holdout_participants},
            shared_affordances=list(generator.invariants.get("shared_affordances", [])),
            coexisting_pressures=list(generator.invariants.get("pressures", [])),
            constraints=["isolated_action_fails", "requires_cross_modal_alignment"],
            active=True,
        )

        outcome = blind_holdout_encounter(holdout_participants, blind_niche)
        passed = bool(outcome.get("success", False))

        if passed:
            generator.qualification_passed = True
            # Register qualified niche technique on Symbiogenesis agent
            tech_id = f"tech-{uuid.uuid4().hex[:8]}"
            lineage = TechniqueLineage(
                generator=generator.generator_id,
                origin_encounter=generator.source_niche_id,
                holder=self.agent_id,
                qualification_scope=CapabilityOwnership.SELF,
                limits={"required_differences": generator.required_differences},
            )
            q_tech = QualifiedTechnique(
                technique_id=tech_id,
                name=generator.name,
                candidate_id=generator.generator_id,
                qualification_receipts=[{"holdout_niche": blind_niche.niche_id, "outcome": outcome}],
                lineage=lineage,
                owner_scope=CapabilityOwnership.SELF,
                state=CapabilityState.QUALIFIED,
            )
            self.qualified_niche_techniques[tech_id] = q_tech

        return passed


def create_symbiogenesis_agent(
    agent_id: str = "symbiogenesis_agent",
    objective: str = "Change the conditions of interaction so new capability can become possible",
    sovereign_key: Optional[str] = None,
    genesis_mode: GenesisMode = GenesisMode.IDENTICAL_GENESIS,
) -> SymbiogenesisAgent:
    """Factory creating the Symbiogenesis Agent."""
    authority = ExecutionAuthority(
        tier=0,
        max_permitted_tier=0,
        permitted_scopes=("situated_encounter", "niche_construction"),
        sovereign_delegation_key=sovereign_key,
    )
    salience = SalienceVector(weights={
        "environmental_hazards": 0.20,
        "physical_affordances": 0.30,
        "social_presence": 0.30,
        "unexplored_frontiers": 0.20,
    })
    return SymbiogenesisAgent(
        agent_id=agent_id,
        objective=objective,
        authority=authority,
        initial_salience=salience,
        genesis_mode=genesis_mode,
    )
