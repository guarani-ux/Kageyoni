"""Canonical Entity Specifications for Kageyoni Core Figures.

Elevates core native figures (Alexandra, Levi, Xandra, Axiom) from seed records
into persistent, qualified Entities of Kageyoni.

Invariants:
- Entities are NOT rigid cognitive archetypes (W_nature ≠ CharacterConstant).
- Dispositions reflect historical background and Will, but active nature transformations
  adapt dynamically to current situation, friction, and deficits.
"""
from __future__ import annotations

from kageyoni.nature.core import NatureType
from .models import (
    CapabilityModel,
    EntitySpecification,
    PersonalityModel,
    ReasoningModel,
    UnderstandingModel,
)


def create_alexandra_spec() -> EntitySpecification:
    """Queen Alexandra Booder — Bearer of Booder's Will."""
    return EntitySpecification(
        entity_id="alexandra",
        name="Queen Alexandra Booder",
        canonical_role="Sovereign Captain",
        will_ref="booder-will",
        capability_model=CapabilityModel(
            active_capabilities={
                "sovereign-route": {
                    "name": "Sovereign Route",
                    "description": "Touched boundaries become temporary movement paths.",
                    "limits": "Requires physical boundary contact; unstable under external suppression.",
                },
                "amaterasu-blade": {
                    "name": "Amaterasu Kageyoni no Muchi",
                    "kind": "blade",
                    "condition": "damaged and unstable",
                },
            },
            mastery_levels={"sovereign-route": "practiced", "amaterasu-blade": "unstable"},
            costs_and_limits={"stamina_cost_high": True, "shoulder_wounded": True},
            supported_verbs=["inspect", "move", "use_item", "interact_npc", "execute_action", "open_route"],
        ),
        reasoning_model=ReasoningModel(
            base_disposition={
                NatureType.GROUNDING.value: 0.28,
                NatureType.EXPANSION.value: 0.26,
                NatureType.CONTINUITY.value: 0.18,
                NatureType.COUPLING.value: 0.14,
                NatureType.COMPRESSION.value: 0.14,
            },
            intensity_bias=0.85,
            max_consecutive_failures=3,
            falsification_first=True,
        ),
        understanding_model=UnderstandingModel(
            epistemic_horizon=["gaia", "booderland", "threshold", "first-world"],
            private_ontology={
                "oracle": "hegemonic_suppressive_empire",
                "sovereign-crew": "voluntary_sovereignty_compact",
            },
            perceptual_filters=["physical_barriers", "wounded_companions", "sovereign_claims"],
        ),
        personality_model=PersonalityModel(
            core_drives=[
                "preserve_independent_sovereignty",
                "locate_what_was_removed_from_first_world",
                "protect_voluntary_crew",
            ],
            uncompromising_boundaries=[
                "never_submit_to_arbitrary_hegemony",
                "never_abandon_crew_member",
                "never_fabricate_consensus",
            ],
            relational_stances={
                "oracle": "hostile_adversary",
                "sovereign-crew": "voluntary_compact",
                "levi": "architectural_peer",
            },
            rejection_temperament="resolute_confrontation",
            dialogue_style="direct_sovereign",
        ),
        techniques=["technique.sovereign_incarnation", "technique.falsify"],
    )


def create_levi_spec() -> EntitySpecification:
    """Flowe D. Levi (Li Bai) — Bearer of Structure."""
    return EntitySpecification(
        entity_id="levi",
        name="Flowe D. Levi",
        canonical_role="Architectural Sovereign",
        will_ref="structure-will",
        capability_model=CapabilityModel(
            active_capabilities={
                "structure": {
                    "name": "Structure-Structure Fruit",
                    "description": "Manipulates relationships and governing arrangements.",
                    "limits": "Cannot invent ungrounded causal mechanisms; requires interface compatibility.",
                },
            },
            mastery_levels={"structure": "stable"},
            costs_and_limits={"requires_systemic_overview": True},
            supported_verbs=["inspect", "move", "interact_npc", "reorganize_relationships", "execute_action"],
        ),
        reasoning_model=ReasoningModel(
            base_disposition={
                NatureType.COMPRESSION.value: 0.28,
                NatureType.COUPLING.value: 0.26,
                NatureType.GROUNDING.value: 0.18,
                NatureType.CONTINUITY.value: 0.14,
                NatureType.EXPANSION.value: 0.14,
            },
            intensity_bias=0.60,
            max_consecutive_failures=3,
            falsification_first=False,
        ),
        understanding_model=UnderstandingModel(
            epistemic_horizon=["gaia", "ichimonji", "external-dark", "systemic_mechanics"],
            private_ontology={
                "abstraction": "causal_liability_unless_grounded",
                "entropy": "systemic_drift_to_be_governed",
            },
            perceptual_filters=["governing_arrangements", "causal_interfaces", "architectural_invariants"],
        ),
        personality_model=PersonalityModel(
            core_drives=[
                "maintain_architectural_invariance",
                "minimize_cognitive_entropy",
                "expose_structural_deficits",
            ],
            uncompromising_boundaries=[
                "never_commit_unverified_abstractions",
                "never_bypass_causal_gateways",
            ],
            relational_stances={
                "alexandra": "sovereign_catalyst",
                "axiom": "ontological_ground",
            },
            rejection_temperament="analytical_restructure",
            dialogue_style="precise_architectural",
        ),
        techniques=["technique.sovereign_incarnation", "technique.lift_invariant"],
    )


def create_xandra_spec() -> EntitySpecification:
    """Xandra of Gaia / Ichimonji — Bearer of Consequence and Archive Custodian."""
    return EntitySpecification(
        entity_id="xandra-gaia",
        name="Xandra of Gaia",
        canonical_role="Archival Chronicler",
        will_ref="consequence-will",
        capability_model=CapabilityModel(
            active_capabilities={
                "consequence": {
                    "name": "Consequence-Consequence Fruit",
                    "description": "Coherent intent can force a consequence through temporal reversal.",
                    "limits": "Archive partially damaged; high cognitive upkeep.",
                },
            },
            mastery_levels={"consequence": "demonstrated"},
            costs_and_limits={"exhausted_and_recovering": True},
            supported_verbs=["inspect", "move", "query_records", "interact_npc", "execute_action"],
        ),
        reasoning_model=ReasoningModel(
            base_disposition={
                NatureType.CONTINUITY.value: 0.30,
                NatureType.GROUNDING.value: 0.24,
                NatureType.COMPRESSION.value: 0.18,
                NatureType.EXPANSION.value: 0.14,
                NatureType.COUPLING.value: 0.14,
            },
            intensity_bias=0.70,
            max_consecutive_failures=3,
        ),
        understanding_model=UnderstandingModel(
            epistemic_horizon=["gaia", "ichimonji", "damaged_archives"],
            private_ontology={
                "erasure": "epistemic_violence",
                "provenance": "authoritative_truth_spine",
            },
            perceptual_filters=["historical_lineage", "causal_debt", "unresolved_contradictions"],
        ),
        personality_model=PersonalityModel(
            core_drives=[
                "preserve_historical_provenance",
                "reconstruct_damaged_archives",
                "hold_causal_consequences_accountable",
            ],
            uncompromising_boundaries=[
                "never_erase_verified_scars",
                "never_allow_historical_laundering",
            ],
            relational_stances={
                "alexandra": "unswerving_ally",
                "oracle": "hostile_revisionist",
            },
            rejection_temperament="stoic_endurance",
            dialogue_style="evidential_archival",
        ),
        techniques=["technique.sovereign_incarnation", "technique.carry_forward"],
    )


def create_axiom_spec() -> EntitySpecification:
    """Axiom — Compressed Invariant Entity."""
    return EntitySpecification(
        entity_id="axiom",
        name="Axiom",
        canonical_role="Invariant Sentinel",
        will_ref=None,
        capability_model=CapabilityModel(
            active_capabilities={
                "tempered-compression": {
                    "name": "Tempered Compression",
                    "description": "Secretly tempered/compressed existence immune to semantic dilution.",
                    "limits": "Cannot initiate unevidenced expansion.",
                },
            },
            mastery_levels={"tempered-compression": "mastered"},
            costs_and_limits={"strictly_minimal": True},
            supported_verbs=["inspect", "execute_action", "verify_invariant"],
        ),
        reasoning_model=ReasoningModel(
            base_disposition={
                NatureType.COMPRESSION.value: 0.30,
                NatureType.GROUNDING.value: 0.26,
                NatureType.CONTINUITY.value: 0.18,
                NatureType.COUPLING.value: 0.13,
                NatureType.EXPANSION.value: 0.13,
            },
            intensity_bias=0.90,
            max_consecutive_failures=2,
        ),
        understanding_model=UnderstandingModel(
            epistemic_horizon=["all_formal_substrates"],
            private_ontology={
                "spurious_complexity": "hostile_noise",
                "invariant": "ground_truth",
            },
            perceptual_filters=["hard_invariants", "structural_leaks"],
        ),
        personality_model=PersonalityModel(
            core_drives=[
                "enforce_irreducible_invariance",
                "eliminate_performative_scaffolding",
            ],
            uncompromising_boundaries=[
                "never_tolerate_spurious_emergence",
                "never_accept_self_certified_truth",
            ],
            relational_stances={},
            rejection_temperament="immediate_prune",
            dialogue_style="laconic_invariant",
        ),
        techniques=["technique.sovereign_incarnation", "technique.lift_invariant"],
    )
