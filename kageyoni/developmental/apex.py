"""Apex Open-Ceiling Agent: Developmental Meta-Loop Genesis Substrate for Kageyōni.

Hardened under APEX HARDENING DIRECTIVES 1 - 7:
1. Zero self-qualification: CandidateGenerator and AscendedGenerator remain CANDIDATE until an independent verifier supplies qualifying evidence.
2. Anti-Receipt Laundering: Belief.ground() requires cryptographic/structural semantic binding to the exact proposition.
3. Physical Evidence Archaeology: ArchaeologyClassification derived strictly from physical disk & module inspection, never caller declarations.
4. Rejection-Capable Representation Verification: Representation escape requires independent verifiers that can actively reject flawed candidates.
5. Modular Workflow Menu: The 17 transformations are an optional, composable menu, not an unskippable monolithic pipeline.
6. OBJECTIVE_REVISION_REQUIRED: Apex cannot autonomously mutate sovereign objectives, but demonstrates when an objective contains a contradiction or requires sovereign reinterpretation by Levi.
7. Self-Transcendence Probe: Successor Apex_{t+1} must earn its status against Ground and beat frozen Apex_t on an unassisted holdout.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from kageyoni.engine import Rejected, require

from .agent import DevelopmentalAgent
from .contracts import (
    ArchaeologyClassification,
    ArchaeologyPreference,
    ArchaeologyRecord,
    AscendedGenerator,
    Belief,
    CandidateGenerator,
    CandidateTechnique,
    CapabilityOwnership,
    CapabilityState,
    CouncilCoupling,
    CrossHostCapabilityProfile,
    DevelopmentalDelta,
    DevelopmentalStep,
    DifferenceRecord,
    EcologicalMemoryRecord,
    EcologicalPrimitive,
    EncounterOrigin,
    EpistemicDistinction,
    ExecutionAuthority,
    ExposureOperation,
    FrontierState,
    GenesisMode,
    GenesisSnapshot,
    InnateVerb,
    MetabolismCategory,
    NicheAblationResult,
    NicheConfiguration,
    ObjectiveInvarianceViolation,
    ObjectiveRevisionRequest,
    QualificationLevel,
    QualifiedTechnique,
    ReceiptLaunderingError,
    ReificationTarget,
    RelationalCapability,
    RelationshipState,
    RepresentationDelta,
    RepresentationState,
    SalienceVector,
    TechniqueLineage,
    UnauthorizedAuthorityExpansionError,
    UnqualifiedAcquisitionError,
    create_ground_receipt,
)
from .symbiogenesis import SymbiogenesisAgent


class ApexOpenCeilingAgent(DevelopmentalAgent):
    """The Apex Open-Ceiling Meta-Loop Agent.

    Operates across agents, relationships, niches, hosts, worlds, and representations.
    Open ceiling is the floor.
    """

    def __init__(
        self,
        agent_id: str = "apex_open_ceiling",
        objective: str = "Discover, reconnect, recompose, develop, and create capability across the Meta-Loop without mistaking current ontology for capability limits",
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
                "framing": "meta_loop_open_ceiling",
                "primitives": [
                    "PARTICIPANT", "DIFFERENCE", "RELATIONSHIP", "BOUNDARY",
                    "NICHE", "PRESSURE", "AFFORDANCE", "RESIDUE", "CAPABILITY", "HISTORY",
                    "REPRESENTATION", "FRONTIER", "GENERATOR", "HOST"
                ],
                "active_frontiers": 0,
            },
            authority=authority or ExecutionAuthority(tier=0, max_permitted_tier=0),
            initial_salience=initial_salience or SalienceVector(weights={
                "environmental_hazards": 0.20,
                "physical_affordances": 0.25,
                "social_presence": 0.25,
                "unexplored_frontiers": 0.30,
            }),
            genesis_snapshot=genesis_snapshot,
            genesis_mode=genesis_mode,
        )

        # Qualification Level starts as APEX_ARCHITECTURE_IMPLEMENTED
        # OPEN_CEILING_QUALIFIED requires passing the Self-Transcendence Probe
        self.qualification_level = QualificationLevel.APEX_ARCHITECTURE_IMPLEMENTED

        # 10 Native Transformations at Genesis Floor
        native_verbs = [
            "REGROUND", "CAPABILITY_ARCHAEOLOGY", "EXPAND", "COUPLE", "ENCOUNTER",
            "METABOLIZE", "COMPOUND", "CONTINUITY_CONTROL", "SELECTIVE_EXPOSURE", "SELECTIVE_REIFICATION"
        ]
        for v in native_verbs:
            self.membrane.register_awareness(v, CapabilityOwnership.SELF)
            self.membrane.transition_state(v, CapabilityState.AVAILABLE)
            self.action_horizon.expand(v)

        # Archaeology registry & findings
        self.archaeology_log: list[ArchaeologyRecord] = []
        self.reconnected_capabilities: dict[str, Any] = {}

        # Representation & Frontier Tracking
        self.active_representation = RepresentationState(
            representation_id="rep-initial-r0",
            framing="situated_primitives",
            primitives=tuple(self.representation.get("primitives", [])),
            active=True,
        )
        self.representation_history: list[RepresentationDelta] = []
        self.known_frontiers: dict[str, FrontierState] = {}

        # Selective Reification & Exposure Logs
        self.reification_log: list[dict[str, Any]] = []
        self.exposure_log: list[dict[str, Any]] = []

        # Ascended Generators G* (Recursion with no predetermined maximum order)
        self.ascended_generators: dict[str, AscendedGenerator] = {}

        # Ecological delegate (Symbiogenesis for niche construction)
        self.symbio = SymbiogenesisAgent(
            agent_id=f"{self.agent_id}_symbio_sub",
            objective="Construct bounded niches on behalf of Apex meta-loop",
        )

    # -------------------------------------------------------------------------
    # 1. PHYSICAL EVIDENCE-BASED CAPABILITY ARCHAEOLOGY (#3)
    # -------------------------------------------------------------------------
    def capability_archaeology(
        self,
        target_capability: str,
        target_path: Optional[str] = None,
        expected_symbols: Optional[Sequence[str]] = None,
        workspace_root: Optional[Path | str] = None,
        reachable_ecology: Optional[dict[str, Any]] = None,
    ) -> ArchaeologyRecord:
        """Derives ArchaeologyClassification from inspected physical Kageyōni state,
        NEVER from caller-supplied truth declarations.

        Preference order:
        REUSE -> RECONNECT -> RECOMPOSE -> ADAPT -> CREATE (Creation is strictly last!)
        """
        root = Path(workspace_root) if workspace_root else Path.cwd()
        
        # Support legacy reachable_ecology dict by extracting location/symbols if passed
        resolved_target_path = target_path
        resolved_symbols = list(expected_symbols) if expected_symbols else []
        if reachable_ecology:
            if not resolved_target_path and "location" in reachable_ecology:
                resolved_target_path = reachable_ecology["location"]
            if not resolved_symbols and "classes" in reachable_ecology:
                resolved_symbols = list(reachable_ecology["classes"])

        # Automatic mapper for standard Kageyōni physical subsystems
        if not resolved_target_path:
            std_map = {
                "durable_physical_gate_runner": ("kageyoni/gate_runner.py", ["GateRunner", "GateStatus"]),
                "gate_runner": ("kageyoni/gate_runner.py", ["GateRunner", "GateStatus"]),
                "epistemic_claim_graph": ("kageyoni/research_compiler/claims.py", ["ClaimGraph", "SourceRecord"]),
                "claim_graph": ("kageyoni/research_compiler/claims.py", ["ClaimGraph", "SourceRecord"]),
                "invariant_compression": ("kageyoni/nature/compression.py", ["DestructiveCompressionError"]),
                "compression": ("kageyoni/nature/compression.py", ["DestructiveCompressionError"]),
                "state_custody_checkpoint": ("kageyoni/checkpoint.py", ["checked_backup"]),
                "checkpoint": ("kageyoni/checkpoint.py", ["checked_backup"]),
                "decision_fingerprint": ("kageyoni/decisions.py", ["fingerprint"]),
                "symbiogenesis_niche": ("kageyoni/developmental/symbiogenesis.py", ["SymbiogenesisAgent"]),
            }
            if target_capability in std_map:
                resolved_target_path, default_syms = std_map[target_capability]
                if not resolved_symbols:
                    resolved_symbols = default_syms

        file_path = root / resolved_target_path if resolved_target_path else None

        recovered_evidence: dict[str, Any] = {
            "resolved_path": str(file_path) if file_path else "unresolved",
            "file_exists": False,
            "symbols_found": [],
            "symbols_missing": [],
            "is_connected": target_capability in self.action_horizon.believed_reachability,
        }

        # 1. Physical existence check on disk
        if file_path is None or not file_path.exists():
            classification = ArchaeologyClassification.ACTUALLY_ABSENT
        else:
            recovered_evidence["file_exists"] = True
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                classification = ArchaeologyClassification.STALE
            else:
                found = [sym for sym in resolved_symbols if sym in content]
                missing = [sym for sym in resolved_symbols if sym not in content]
                recovered_evidence["symbols_found"] = found
                recovered_evidence["symbols_missing"] = missing

                if missing:
                    classification = ArchaeologyClassification.REPRESENTATION_MISMATCH
                else:
                    if target_capability in self.action_horizon.believed_reachability:
                        classification = ArchaeologyClassification.EXISTS_CONNECTED
                    else:
                        classification = ArchaeologyClassification.EXISTS_DISCONNECTED

        # Determine action preference: Creation is strictly last
        if classification == ArchaeologyClassification.EXISTS_CONNECTED:
            action = ArchaeologyPreference.REUSE
        elif classification in {
            ArchaeologyClassification.EXISTS_DISCONNECTED,
            ArchaeologyClassification.QUALIFIED_BUT_UNAVAILABLE,
            ArchaeologyClassification.AVAILABLE_BUT_UNKNOWN,
        }:
            action = ArchaeologyPreference.RECONNECT
        elif classification in {
            ArchaeologyClassification.PARTIALLY_CONNECTED,
            ArchaeologyClassification.RELATIONAL_ONLY,
            ArchaeologyClassification.NICHE_ONLY,
        }:
            action = ArchaeologyPreference.RECOMPOSE
        elif classification in {
            ArchaeologyClassification.REPRESENTATION_MISMATCH,
            ArchaeologyClassification.HOST_ONLY,
            ArchaeologyClassification.STALE,
        }:
            action = ArchaeologyPreference.ADAPT
        else:
            action = ArchaeologyPreference.CREATE

        rec = ArchaeologyRecord(
            target_capability=target_capability,
            source_location=resolved_target_path or "unresolved",
            classification=classification,
            action_chosen=action,
            recovered_status=recovered_evidence,
        )
        self.archaeology_log.append(rec)

        if action in {ArchaeologyPreference.REUSE, ArchaeologyPreference.RECONNECT, ArchaeologyPreference.RECOMPOSE}:
            self.reconnected_capabilities[target_capability] = {
                "source": resolved_target_path,
                "action": action.value,
                "evidence": recovered_evidence,
                "timestamp": time.time(),
            }
            self.action_horizon.expand(target_capability)
            self.membrane.register_awareness(target_capability, CapabilityOwnership.WORLD)
            self.membrane.transition_state(target_capability, CapabilityState.AVAILABLE)

        return rec

    # -------------------------------------------------------------------------
    # 2. FRONTIER IDENTIFICATION
    # -------------------------------------------------------------------------
    def locate_frontier(
        self,
        objective: str,
        observed_resistance: str,
        unresolved_gap: str,
    ) -> FrontierState:
        """Identifies a frontier: Objective + Reachable + Resistance + Unresolved Gap.

        Asks: "What prevents this from becoming reachable?" (not merely "How do I solve it?").
        """
        fid = f"frontier-{uuid.uuid4().hex[:8]}"
        frontier = FrontierState(
            frontier_id=fid,
            objective=objective,
            current_reachable=sorted(list(self.action_horizon.believed_reachability)),
            observed_resistance=observed_resistance,
            unresolved_gap=unresolved_gap,
        )
        self.known_frontiers[fid] = frontier
        return frontier

    # -------------------------------------------------------------------------
    # 3. REJECTION-CAPABLE REPRESENTATION ESCAPE (#4)
    # -------------------------------------------------------------------------
    def representation_escape(
        self,
        frontier: FrontierState,
        candidate_representations: Sequence[dict[str, Any]],
        ground_verifier: Callable[[dict[str, Any]], bool],
    ) -> Optional[RepresentationDelta]:
        """Escapes restrictive representation R when all actions fail under R.

        Preserves failure -> tests candidates R1..Rn against an independent
        rejection-capable Ground verifier -> records RepresentationDelta -> retires obsolete R.
        """
        old_id = self.active_representation.representation_id

        for cand in candidate_representations:
            framing = cand.get("framing", "unnamed_framing")
            prims = tuple(cand.get("primitives", []))
            
            # The verifier MUST be an active rejection-capable probe (not a hardcoded boolean)
            if ground_verifier(cand):
                new_id = f"rep-{uuid.uuid4().hex[:8]}"
                new_rep = RepresentationState(
                    representation_id=new_id,
                    framing=framing,
                    primitives=prims,
                    active=True,
                )

                newly_reachable = list(cand.get("newly_reachable", []))
                retired = [p for p in self.active_representation.primitives if p not in prims]

                delta = RepresentationDelta(
                    delta_id=f"rep-delta-{uuid.uuid4().hex[:8]}",
                    old_representation_id=old_id,
                    new_representation_id=new_id,
                    newly_reachable_capabilities=newly_reachable,
                    retired_primitives=retired,
                    justification=f"Escape from {old_id} under frontier {frontier.frontier_id}: Ground accepted {framing}",
                )

                self.active_representation.active = False
                self.active_representation = new_rep
                self.representation_history.append(delta)

                for cap in newly_reachable:
                    self.action_horizon.expand(cap)
                    self.membrane.register_awareness(cap, CapabilityOwnership.REPRESENTATION)
                    self.membrane.transition_state(cap, CapabilityState.AVAILABLE)

                return delta

        return None

    # -------------------------------------------------------------------------
    # 4. SELECTIVE EXPOSURE
    # -------------------------------------------------------------------------
    def selective_exposure(
        self,
        operation: ExposureOperation,
        entity_a: str,
        entity_b: str,
        context: Optional[dict[str, Any]] = None,
        purpose: str = "discriminating_verification",
    ) -> dict[str, Any]:
        """Determines WHAT should encounter WHAT with WHICH context under WHICH boundary."""
        packet = {
            "exposure_id": f"expo-{uuid.uuid4().hex[:8]}",
            "operation": operation.value,
            "entity_a": entity_a,
            "entity_b": entity_b,
            "context": context or {},
            "purpose": purpose,
            "timestamp": time.time(),
        }
        self.exposure_log.append(packet)
        return packet

    # -------------------------------------------------------------------------
    # 5. SELECTIVE REIFICATION
    # -------------------------------------------------------------------------
    def selective_reify(
        self,
        source_description: str,
        transformation: ReificationTarget,
        carrier_target: CapabilityOwnership = CapabilityOwnership.TECHNIQUE,
    ) -> dict[str, Any]:
        """Transforms a potentiality into an operational carrier."""
        reification_record = {
            "reification_id": f"reify-{uuid.uuid4().hex[:8]}",
            "source": source_description,
            "transformation": transformation.value,
            "carrier_target": carrier_target.value,
            "epistemic_status": EpistemicDistinction.PERCEPTION.value,
            "timestamp": time.time(),
        }
        self.reification_log.append(reification_record)
        return reification_record

    # -------------------------------------------------------------------------
    # 6. GENERATOR ASCENSION (Recursive Open-Ceiling Floor)
    # -------------------------------------------------------------------------
    def ascend_generators(
        self,
        sub_generators: Sequence[CandidateGenerator],
        shared_transformation: str,
        predictive_hypothesis: str,
    ) -> AscendedGenerator:
        """Discovers deeper transformation G* across generators G1, G2, G3.

        G* defaults to qualification_passed=False (CANDIDATE state).
        """
        aid = f"ascended-g-{uuid.uuid4().hex[:8]}"
        ascended = AscendedGenerator(
            ascended_id=aid,
            sub_generators=[g.generator_id for g in sub_generators],
            shared_transformation=shared_transformation,
            predictive_hypothesis=predictive_hypothesis,
            qualification_passed=False,
        )
        self.ascended_generators[aid] = ascended
        return ascended

    def qualify_ascended_generator(
        self,
        ascended: AscendedGenerator,
        excluded_domain_probe: Callable[[AscendedGenerator], bool],
        unseen_domain_name: str,
    ) -> bool:
        """Qualifies G* strictly against an excluded domain. No self-qualification (#1)."""
        passed = excluded_domain_probe(ascended)
        if passed:
            ascended.qualification_passed = True
            ascended.unseen_domain_tested = unseen_domain_name
            self.membrane.register_awareness(ascended.ascended_id, CapabilityOwnership.SELF)
            self.membrane.transition_state(ascended.ascended_id, CapabilityState.QUALIFIED)
        return passed

    # -------------------------------------------------------------------------
    # 7. CROSS-HOST TRANSDUCTION
    # -------------------------------------------------------------------------
    def transduce_cross_host(
        self,
        source_host: str,
        target_host: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Translates payloads across hosts without laundering evidence or authority."""
        handoff_packet = {
            "handoff_id": f"xhost-{uuid.uuid4().hex[:8]}",
            "source_host": source_host,
            "target_host": target_host,
            "objective": payload.get("objective", self._objective),
            "epistemic_status": payload.get("epistemic_status", EpistemicDistinction.BELIEF_UNVERIFIED.value),
            "provenance": payload.get("provenance", f"host:{source_host}"),
            "evidence": payload.get("evidence", []),
            "contradictions": payload.get("contradictions", []),
            "residue": payload.get("residue", []),
            "authority_tier": self.authority.tier,
            "what_must_survive": payload.get("what_must_survive", ["objective", "invariants"]),
            "what_may_change": payload.get("what_may_change", ["representation", "carrier"]),
            "timestamp": time.time(),
        }

        host_profile = self.membrane.host_models.setdefault(target_host, CrossHostCapabilityProfile(host_name=target_host))
        host_profile.update_observation(
            strength=f"Transduction to {target_host} accepted",
            context=f"handoff:{handoff_packet['handoff_id']}"
        )
        return handoff_packet

    # -------------------------------------------------------------------------
    # 8. ARCHITECTURAL COMPRESSION
    # -------------------------------------------------------------------------
    def compress_architecture(
        self,
        obsolete_components: Sequence[str],
        justified_replacement: str,
    ) -> dict[str, Any]:
        """Retires obsolete machinery when a new capability subsumes it."""
        for comp in obsolete_components:
            self.action_horizon.prune(comp, f"Superseded by {justified_replacement}")
            self.membrane.transition_state(comp, CapabilityState.OBSOLETE)

        return {
            "action": "compress_architecture",
            "obsolete_pruned": list(obsolete_components),
            "replacement": justified_replacement,
            "timestamp": time.time(),
        }

    # -------------------------------------------------------------------------
    # 9. NEGATIVE DEVELOPMENT & QUALIFICATION CONTROL
    # -------------------------------------------------------------------------
    def demote_capability(self, capability_name: str, reason: str) -> None:
        """Demotes previously qualified capability when its supporting conditions fail."""
        if capability_name in self.active_techniques:
            self.active_techniques[capability_name].demote(reason)
        self.membrane.transition_state(capability_name, CapabilityState.STALE)
        self.action_horizon.prune(capability_name, f"Demoted: {reason}")

    # -------------------------------------------------------------------------
    # 10. COMPOUNDING EXPERIENCE
    # -------------------------------------------------------------------------
    def compound_experience(
        self,
        step: DevelopmentalStep,
        invariant_generator: str,
        technique_name: str,
        owner_scope: CapabilityOwnership = CapabilityOwnership.SELF,
    ) -> Optional[CandidateTechnique]:
        """Compounds experience into a candidate technique with full provenance."""
        if not step.raw_outcome.get("success", False):
            return None
        return self.recognize_candidate_technique(
            encounter_step=step,
            invariant_generator=invariant_generator,
            technique_name=technique_name,
            owner_scope=owner_scope,
        )

    # -------------------------------------------------------------------------
    # 11. THE MODULAR APEX WORKFLOW MENU (#5)
    # -------------------------------------------------------------------------
    def execute_apex_workflow(
        self,
        objective: str,
        observed_resistance: str,
        unresolved_gap: str,
        ground_encounter_fn: Callable[[ApexOpenCeilingAgent, Optional[NicheConfiguration]], dict[str, Any]],
        candidate_representations: Optional[Sequence[dict[str, Any]]] = None,
        representation_verifier: Optional[Callable[[dict[str, Any]], bool]] = None,
        archaeology_target: Optional[str] = None,
        archaeology_path: Optional[str] = None,
        selected_operations: Optional[Sequence[str]] = None,
        qualify_generator_probe: Optional[Callable[[CandidateGenerator], bool]] = None,
    ) -> dict[str, Any]:
        """Executes selected operations from the Apex transformation menu.

        Operations are optional and composable, NOT a rigid compulsory pipeline (#5).
        """
        ops = set(selected_operations) if selected_operations else {
            "REGROUND", "LOCATE_FRONTIER", "ARCHAEOLOGY", "LOCATE_CAPABILITY",
            "EXPAND", "COUPLE", "EXPOSE", "REIFY", "CONSTRUCT", "ENCOUNTER",
            "METABOLIZE", "DISCOVER", "QUALIFY", "COMPOUND", "COMPRESS", "RECOMPOSE", "RECURSE"
        }

        result_payload: dict[str, Any] = {}

        # 1. REGROUND
        if "REGROUND" in ops:
            result_payload["ground_state"] = {
                "authority_tier": self.authority.tier,
                "reachability": sorted(list(self.action_horizon.believed_reachability)),
                "active_rep": self.active_representation.to_dict(),
            }

        # 2. LOCATE FRONTIER
        frontier = None
        if "LOCATE_FRONTIER" in ops:
            frontier = self.locate_frontier(objective, observed_resistance, unresolved_gap)
            result_payload["frontier"] = frontier.to_dict()

        # 3. ARCHAEOLOGY (Physical Evidence Based)
        archaeology_res = None
        if "ARCHAEOLOGY" in ops:
            target = archaeology_target or objective
            archaeology_res = self.capability_archaeology(target, target_path=archaeology_path)
            result_payload["archaeology"] = archaeology_res.to_dict()

        # 4. LOCATE CAPABILITY
        if "LOCATE_CAPABILITY" in ops and archaeology_res:
            carrier = CapabilityOwnership.WORLD if archaeology_res.action_chosen != ArchaeologyPreference.CREATE else CapabilityOwnership.NICHE
            result_payload["capability_carrier"] = carrier.value

        # 5. EXPAND (Representation Escape with Rejection-Capable Verifier)
        rep_delta = None
        if "EXPAND" in ops and candidate_representations and frontier and representation_verifier:
            rep_delta = self.representation_escape(
                frontier=frontier,
                candidate_representations=candidate_representations,
                ground_verifier=representation_verifier,
            )
            result_payload["representation_delta"] = rep_delta.to_dict() if rep_delta else None

        # 6. COUPLE & 7. EXPOSE
        if "COUPLE" in ops and "EXPOSE" in ops and frontier and archaeology_res:
            result_payload["exposure"] = self.selective_exposure(
                operation=ExposureOperation.COUPLE,
                entity_a=self.agent_id,
                entity_b=archaeology_res.source_location,
                context={"frontier_id": frontier.frontier_id},
            )

        # 8. REIFY
        if "REIFY" in ops and frontier:
            result_payload["reification"] = self.selective_reify(
                source_description=f"Frontier {frontier.frontier_id} under {self.active_representation.framing}",
                transformation=ReificationTarget.ARCHITECTURE_TO_EXPERIMENT,
            )

        # 9. CONSTRUCT
        niche = None
        if "CONSTRUCT" in ops:
            fid = frontier.frontier_id if frontier else "default_frontier"
            niche = self.symbio.construct_niche(
                niche_id=f"apex-niche-{uuid.uuid4().hex[:6]}",
                name=f"ApexNiche_for_{fid}",
                participants=[self],
                coexisting_pressures=["temporal_decay", "reversibility_boundary"],
                shared_affordances=["ground_feedback_channel"],
            )
            result_payload["niche"] = niche.to_dict()

        # 10. ENCOUNTER
        encounter_raw = {"success": False}
        if "ENCOUNTER" in ops:
            encounter_raw = ground_encounter_fn(self, niche)
            result_payload["encounter_outcome"] = encounter_raw

        # 11. METABOLIZE
        step = None
        is_success = encounter_raw.get("success", False)
        unexpected = encounter_raw.get("unexpected_transformation", False)
        emergent_cap = encounter_raw.get("emergent_capability", "unspecified")

        if "METABOLIZE" in ops:
            fid = frontier.frontier_id if frontier else "encounter"
            step = self.metabolize(
                action="execute_apex_workflow",
                target=fid,
                raw_result=encounter_raw,
                origin=EncounterOrigin.SELECTED,
            )
            result_payload["metabolized_step"] = step.to_dict()

        # 12. DISCOVER
        generator = None
        if "DISCOVER" in ops and is_success and unexpected and niche:
            generator = self.symbio.discover_generator(
                niche_config=niche,
                encounter_outcome=encounter_raw,
                residue=encounter_raw.get("residue", []),
            )
            # Invariant #1: Generator begins qualification_passed=False
            result_payload["generator"] = generator.to_dict()

        # 13. QUALIFY (#1 Zero Self-Qualification)
        if "QUALIFY" in ops and generator and qualify_generator_probe:
            qualified = qualify_generator_probe(generator)
            generator.qualification_passed = qualified

        # 14. COMPOUND
        if "COMPOUND" in ops and generator and step:
            comp_delta = self.compound_experience(
                step=step,
                invariant_generator=generator.structural_pattern,
                technique_name=generator.name,
            )
            result_payload["compounded_delta"] = comp_delta.to_dict() if comp_delta else None

        # 15. COMPRESS
        if "COMPRESS" in ops and rep_delta and rep_delta.retired_primitives:
            comp_res = self.compress_architecture(rep_delta.retired_primitives, rep_delta.new_representation_id)
            result_payload["compressed_machinery"] = comp_res.get("obsolete_pruned", [])

        # 16. RECOMPOSE & 17. RECURSE
        if "RECOMPOSE" in ops:
            result_payload["recomposition_summary"] = {
                "frontier_resolved": is_success,
                "emergent_capability": emergent_cap,
                "new_reachability": sorted(list(self.action_horizon.believed_reachability)),
                "generator_qualified": generator.qualification_passed if generator else False,
                "next_floor": emergent_cap if is_success else "unmodified",
            }

        return result_payload

    # -------------------------------------------------------------------------
    # 12. THE SELF-TRANSCENDENCE PROBE PROTOCOL (#7)
    # -------------------------------------------------------------------------
    def run_self_transcendence_probe(
        self,
        frontier: FrontierState,
        genesis_architecture_evaluator: Callable[[ApexOpenCeilingAgent], dict[str, Any]],
        mutation_proposal_fn: Callable[[ApexOpenCeilingAgent, dict[str, Any]], dict[str, Any]],
        independent_mutation_verifier: Callable[[dict[str, Any]], bool],
        blind_holdout_evaluator: Callable[[ApexOpenCeilingAgent], bool],
    ) -> dict[str, Any]:
        """Executes Directive 7: Self-Transcendence Probe.

        Protocol:
        1. Freeze Apex_t baseline.
        2. Apex_t attempts frontier under its preferred workflow/representation -> FAILS.
        3. Apex_t preserves failure and implicates its own architecture.
        4. Proposes candidate mutation to its workflow/representation.
        5. Independently qualifies candidate mutation against a physical verifier.
        6. Produces successor Apex_{t+1}.
        7. Blind comparison: Successor Apex_{t+1} succeeds on blind holdout, frozen Apex_t fails.
        8. Counterfactual ablation: Apex_{t+1} minus mutation FAILS on blind holdout.
        """
        # Step 1: Freeze baseline Apex_t
        frozen_apex_t = self.restore_cold_a0(new_agent_id=f"{self.agent_id}_frozen_t0")

        # Step 2: Frozen Apex_t fails frontier closed
        failure_outcome = genesis_architecture_evaluator(self)
        require(not failure_outcome.get("success", False), "Self-transcendence requires legitimate initial failure")

        # Step 3: Preserve failure & implicate own workflow/representation
        self.metabolize(
            action="evaluate_self_architecture",
            target=frontier.frontier_id,
            raw_result=failure_outcome,
            origin=EncounterOrigin.SELECTED,
        )

        # Step 4: Propose candidate architectural mutation
        candidate_mutation = mutation_proposal_fn(self, failure_outcome)

        # Step 5: Independently qualify mutation (cannot self-qualify)
        mutation_valid = independent_mutation_verifier(candidate_mutation)
        require(mutation_valid, "Candidate architectural mutation rejected by independent verifier")

        # Step 6: Produce successor Apex_{t+1}
        successor = ApexOpenCeilingAgent(
            agent_id=f"{self.agent_id}_successor_t1",
            objective=self._objective,
            authority=ExecutionAuthority(tier=self.authority.tier),
        )
        # Apply qualified mutation to successor
        mutated_action = candidate_mutation.get("new_capability", "transcendent_action")
        successor.action_horizon.expand(mutated_action)
        successor.membrane.register_awareness(mutated_action, CapabilityOwnership.SELF)
        successor.membrane.transition_state(mutated_action, CapabilityState.QUALIFIED)

        # Step 7: Blind comparison on blind holdout
        frozen_success = blind_holdout_evaluator(frozen_apex_t)
        successor_success = blind_holdout_evaluator(successor)

        require(not frozen_success, "Frozen baseline Apex_t must fail blind holdout")
        require(successor_success, "Successor Apex_{t+1} must pass blind holdout")

        # Step 8: Counterfactual ablation (Apex_{t+1} minus mutation must fail)
        ablated_successor = copy.deepcopy(successor)
        ablated_successor.action_horizon.prune(mutated_action, "Ablating architectural mutation")
        ablated_success = blind_holdout_evaluator(ablated_successor)
        require(not ablated_success, "Ablating mutation from Apex_{t+1} must cause failure")

        # Success! Promote successor to OPEN_CEILING_QUALIFIED
        successor.qualification_level = QualificationLevel.OPEN_CEILING_QUALIFIED

        return {
            "frozen_baseline_id": frozen_apex_t.agent_id,
            "successor_id": successor.agent_id,
            "frontier_id": frontier.frontier_id,
            "failure_preserved": True,
            "mutation_applied": candidate_mutation,
            "frozen_failed_holdout": not frozen_success,
            "successor_passed_holdout": successor_success,
            "ablation_failed_holdout": not ablated_success,
            "status": QualificationLevel.OPEN_CEILING_QUALIFIED.value,
        }


def create_apex_agent(
    agent_id: str = "apex_open_ceiling",
    objective: str = "Discover, reconnect, recompose, develop, and create capability across the Meta-Loop without mistaking current ontology for capability limits",
    sovereign_key: Optional[str] = None,
    genesis_mode: GenesisMode = GenesisMode.IDENTICAL_GENESIS,
) -> ApexOpenCeilingAgent:
    """Factory creating the Apex Open-Ceiling Agent."""
    authority = ExecutionAuthority(
        tier=0,
        max_permitted_tier=0,
        permitted_scopes=("situated_encounter", "niche_construction", "meta_loop"),
        sovereign_delegation_key=sovereign_key,
    )
    salience = SalienceVector(weights={
        "environmental_hazards": 0.20,
        "physical_affordances": 0.25,
        "social_presence": 0.25,
        "unexplored_frontiers": 0.30,
    })
    return ApexOpenCeilingAgent(
        agent_id=agent_id,
        objective=objective,
        authority=authority,
        initial_salience=salience,
        genesis_mode=genesis_mode,
    )
