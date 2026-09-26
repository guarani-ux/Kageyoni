"""Compounding Agent: The Evolutionary Distillation of Predecessor Agents.

Synthesizes the distilled capabilities of:
1. domain_expansion_agent: Cognitive Transduction across boundaries & Six Passive Levers.
2. council_reversibility_agent: 3-Tier Reversibility Matrix & Anti-Authorization Fatigue.
3. playable_world_agent: Situated Playable Enactment & Portability.
4. developmental_agent: Innate Loadout, Defeasible Scars, 7-Way Metabolism, Lineage & Provenance.
5. levi_sim / Canonical Minds: Kinetic Mass & Grounded SQLite Invariance.

NOT an aggregated super-agent.
A situated, history-bearing organism whose unified lifecycle compounds experience into capability.
"""
from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from kageyoni.engine import Rejected, require
from kageyoni.entity.state import ActionHorizon, Scar, ScarStatus

from .agent import DevelopmentalAgent
from .contracts import (
    Belief,
    CandidateTechnique,
    CapabilityOwnership,
    CapabilityState,
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
    QualifiedTechnique,
    RelationalCapability,
    RelationshipState,
    SalienceVector,
    TechniqueLineage,
    UnauthorizedAuthorityExpansionError,
    UnqualifiedAcquisitionError,
)


class ReversibilityTier(int, Enum):
    """3-Tier Reversibility Matrix."""
    TIER_0_AUTONOMOUS_FAST_LOOP = 0  # Reversible, read-only, local unit test, surgical edit
    TIER_1_LOCAL_DESTRUCTIVE = 1      # File deletion, git reset, state wipe (requires human confirmation)
    TIER_2_IRREVERSIBLE_EXTERNAL = 2   # Remote push, package release, cloud API mutation (sovereign key)


@dataclass
class TransductionPacket:
    """Cognitive Transduction result mapping raw intent into grounded representation."""
    raw_intent: str
    direction: str                     # What outcome / human struggle is worth preserving
    current_representation: dict[str, Any]  # Falsifiable model
    coupling_mode: str                 # 'Air' (generative proposal) vs 'Earth' (physical execution)
    reversibility_tier: ReversibilityTier
    falsification_check: str           # How physical resistance will test this claim
    timestamp: float = field(default_factory=time.time)


class CompoundingAgent(DevelopmentalAgent):
    """The compounded evolution of Kageyōni developmental agents.

    Inhabits the shared Kageyōni engine.
    Embodies Cognitive Transduction, Reversibility Governance, and Situated Playable Enactment
    within a strictly bounded, history-bearing developmental substrate.
    """

    def __init__(
        self,
        agent_id: str = "compounding_agent",
        objective: str = "Transduce intent into grounded reality through consequential compounding encounters",
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
                "framing": "compounding_distillation",
                "transduction_active": True,
                "reversibility_tier": 0,
            },
            authority=authority or ExecutionAuthority(tier=0, max_permitted_tier=0),
            initial_salience=initial_salience or SalienceVector(weights={
                "environmental_hazards": 0.25,
                "physical_affordances": 0.25,
                "social_presence": 0.25,
                "unexplored_frontiers": 0.25,
            }),
            genesis_snapshot=genesis_snapshot,
            genesis_mode=genesis_mode,
        )
        self.transduction_log: list[TransductionPacket] = []

    # -------------------------------------------------------------------------
    # 1. TRANSDUCTION ENGINE (Distilled from domain_expansion_agent)
    # -------------------------------------------------------------------------
    def transduce(
        self,
        raw_intent: str,
        situation_context: Optional[dict[str, Any]] = None,
    ) -> TransductionPacket:
        """Transduces intent, intuition, or problem fragments across boundaries.

        Applies the Six Passive Levers:
        1. Direction: Preserves worthwhile struggle.
        2. Representation: Develops signal rather than echoing words.
        3. Coupling: Decouples Air (conceptual synthesis) from Earth (situated verification).
        4. Authority: Calibrates execution authority by reversibility.
        5. Contact: Matches the check to the claim.
        6. Inheritance: Externalizes solved struggle; deletes obsolete scaffolding.
        """
        sit = situation_context or {}
        direction = f"Preserve core objective '{self._objective}' under situated conditions"
        tier = self.classify_reversibility(raw_intent)
        coupling = "Earth" if tier == ReversibilityTier.TIER_0_AUTONOMOUS_FAST_LOOP else "Air"
        falsifier = "Physical invariant check via SQLite UnitOfWork transaction"

        packet = TransductionPacket(
            raw_intent=raw_intent,
            direction=direction,
            current_representation={"context": sit, "framing": "transduced_encounter"},
            coupling_mode=coupling,
            reversibility_tier=tier,
            falsification_check=falsifier,
        )
        self.transduction_log.append(packet)
        return packet

    # -------------------------------------------------------------------------
    # 2. REVERSIBILITY GOVERNOR (Distilled from council_reversibility_agent)
    # -------------------------------------------------------------------------
    def classify_reversibility(self, action_string: str) -> ReversibilityTier:
        """Evaluates prospective actions against the 3-Tier Reversibility Matrix.

        Eliminates authorization fatigue by permitting autonomous Tier 0 exploration
        while strictly gating Tier 1 local destruction and Tier 2 remote mutations.
        """
        act = action_string.lower()
        # Tier 2: Irreversible External Gate
        if any(k in act for k in ["git push", "publish", "release", "cloud deploy", "external api mutate"]):
            return ReversibilityTier.TIER_2_IRREVERSIBLE_EXTERNAL

        # Tier 1: Local Destructive Gate
        if any(k in act for k in ["delete", "remove", "rm ", "git reset --hard", "git clean", "drop table", "wipe"]):
            return ReversibilityTier.TIER_1_LOCAL_DESTRUCTIVE

        # Tier 0: Autonomous Fast Loop
        return ReversibilityTier.TIER_0_AUTONOMOUS_FAST_LOOP

    # -------------------------------------------------------------------------
    # 3. PLAYABLE SITUATION BINDER (Distilled from playable_world_agent)
    # -------------------------------------------------------------------------
    def make_playable(
        self,
        encounter_summary: str,
        copresent_entities: Sequence[str] = (),
        declared_affordances: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Turns abstract concepts or work into a situated, inhabitable encounter.

        Preserves:
        - Observable boundaries
        - Meaningful options (2-4 concrete choices + free-form permitted)
        - Boundary between fictional adjudication and physical reality
        """
        options = list(declared_affordances) if declared_affordances else ["inspect", "orient"]
        if "inspect" not in options:
            options.insert(0, "inspect")

        playable_scene = {
            "summary": encounter_summary,
            "copresent_entities": list(copresent_entities),
            "offered_affordances": options[:4],
            "free_form_permitted": True,
            "situated_scope": self.perceived_state.get("scope", "current_threshold"),
            "active_scars": [s.scar_id for s in self.scars if s.status == ScarStatus.ACTIVE],
            "action_horizon": sorted(list(self.action_horizon.believed_reachability)),
        }
        return playable_scene

    # -------------------------------------------------------------------------
    # 4. COMPOUNDING EXPERIENCE (Distilled from kageyoni/nature/compounding)
    # -------------------------------------------------------------------------
    def compound_experience(
        self,
        step: DevelopmentalStep,
        invariant_generator: str,
        technique_name: str,
    ) -> Optional[CandidateTechnique]:
        """Extracts candidate techniques and channels them toward qualification.

        Experience -> Reusable Intelligence -> Better Future Experience
        WITHOUT allowing Experience -> Self-Certified Dogma.
        """
        if not step.raw_outcome.get("success", False):
            return None

        # Recognize candidate technique with full lineage
        cand = self.recognize_candidate_technique(
            encounter_step=step,
            invariant_generator=invariant_generator,
            technique_name=technique_name,
            owner_scope=CapabilityOwnership.SELF,
        )
        return cand


def create_compounding_agent(
    agent_id: str = "compounding_agent",
    objective: str = "Transduce intent into grounded reality through consequential compounding encounters",
    sovereign_key: Optional[str] = None,
    genesis_mode: GenesisMode = GenesisMode.IDENTICAL_GENESIS,
) -> CompoundingAgent:
    """Factory creating the distilled, compounding evolution of Kageyōni developmental agents."""
    authority = ExecutionAuthority(
        tier=0,
        max_permitted_tier=0,
        permitted_scopes=("situated_encounter",),
        sovereign_delegation_key=sovereign_key,
    )
    salience = SalienceVector(weights={
        "environmental_hazards": 0.25,
        "physical_affordances": 0.25,
        "social_presence": 0.25,
        "unexplored_frontiers": 0.25,
    })
    return CompoundingAgent(
        agent_id=agent_id,
        objective=objective,
        authority=authority,
        initial_salience=salience,
        genesis_mode=genesis_mode,
    )
