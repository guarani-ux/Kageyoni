"""Ninshū 8-Knob Power System & Polyphonic Will Compiler for Kageyōni.

Fuses Ninshū's 8-Knob Shape Manipulation (Sasuke's Chidori finesse) and
Polyphonic Clash Resolution (CH 43 EffectResolver + CH 40 ProvenanceMapper +
ActiveConsole) directly into Kageyōni's Will & Ability engine (`kageyoni.will`
and `kageyoni.engine.Engine`) without d20 number bloat.

Core Architectural Laws:
1. Base Will / Ability = Carrier (`WillCarrier`); Technique = 8-Knob Modulation (`NinshuKnobVector`).
2. World Law `gaia-balance` ("No Will may completely suppress another Will inside Gaia")
   is enforced mechanically via Polyphonic Interference: opposing Wills preserve
   both pressures (`opposing_pressures`), generating bounded blocks, partial leaks
   (unverified stone impressions), and persistent physical residue.
3. Zero d20 bloat: `Engine.prepare_will_attempt` and `Engine.apply_will_attempt`
   execute with `randomness={"mode": "none"}` driven by deterministic clash physics.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from kageyoni.composition.effects import EffectResolver
from kageyoni.engine import Engine, digest, require
from kageyoni.will import CONTRACT_VERSION, validate_contract
from .console import ActiveConsole, ChannelStripConfig
from .provenance_mapper import ArtifactNode, ProvenanceGraph


VALID_SHAPES = ("senbon", "spear", "current", "domain", "unbounded_domain")
VALID_SUBSTRATES = (
    "stone",
    "earth",
    "conduit_link",
    "avatar_vessel",
    "boundary_seam",
    "underlying_value",
    "temporal_consequence",
    "structure_lattice",
    "causal_graph",
)
VALID_POLARITIES = ("polyphonic", "monophonic")
VALID_DEFICIT_GAINS = ("wet", "dry")


@dataclass(frozen=True)
class NinshuKnobVector:
    """The 8 Ninshū Modulation Knobs that shape a base Will Carrier into a specific technique."""

    # Knob 1: Substrate Select (S_dial) - What matter/reality is touched
    substrate: str = "stone"
    # Knob 2: Inspection/Strike Bandwidth & Shape (B_dial) - senbon | spear | current | domain | unbounded_domain
    bandwidth_shape: str = "domain"
    # Knob 3: Acoustic Authority / Epistemic Grounding (A_dial in [0.0, 1.0])
    authority_gain: float = 1.0
    # Knob 4: Dynamic Damping / Primordial Density (D_dial in [0.0, 1.0])
    # Controls whether the effect calcifies into persistent residue against link severance
    damping_density: float = 0.95
    # Knob 5: Thermal / Energy Ceiling (Phi_dial in {0, 1, 2})
    thermal_tier: int = 1
    # Knob 6: Polarity Tension (T_dial) - polyphonic enforces gaia-balance
    polarity: str = "polyphonic"
    # Knob 7: Sidechain Coupling (R_dial) - upstream technique_id feeding this technique
    sidechain_from: Optional[str] = None
    # Knob 8: Topological Deficit Gain (G_dial) - wet surfaces unverified impressions/unknowns
    deficit_gain: str = "wet"

    def validate(self) -> None:
        if self.substrate not in VALID_SUBSTRATES:
            raise ValueError(f"Unsupported substrate {self.substrate!r}; expected one of {VALID_SUBSTRATES}")
        if self.bandwidth_shape not in VALID_SHAPES:
            raise ValueError(f"Unsupported bandwidth_shape {self.bandwidth_shape!r}; expected one of {VALID_SHAPES}")
        if not (0.0 <= float(self.authority_gain) <= 1.0):
            raise ValueError("authority_gain must be between 0.0 and 1.0")
        if not (0.0 <= float(self.damping_density) <= 1.0):
            raise ValueError("damping_density must be between 0.0 and 1.0")
        if self.thermal_tier not in (0, 1, 2):
            raise ValueError("thermal_tier must be 0, 1, or 2")
        if self.polarity not in VALID_POLARITIES:
            raise ValueError(f"Unsupported polarity {self.polarity!r}")
        if self.deficit_gain not in VALID_DEFICIT_GAINS:
            raise ValueError(f"Unsupported deficit_gain {self.deficit_gain!r}")

    def scope_geometry(self, target_kinds: List[str], unknowns: Optional[List[str]] = None) -> Dict[str, Any]:
        """Derives Kageyōni Will effect scope geometry directly from Knob 2 (Bandwidth Shape)."""
        shape_map = {
            "senbon": {
                "range": {"value": 10, "unit": "meter"},
                "area": {"value": 0.1, "unit": "meter"},
                "duration": {"value": 1, "unit": "round"},
            },
            "spear": {
                "range": {"value": 25, "unit": "meter"},
                "area": {"value": 1.5, "unit": "meter"},
                "duration": {"value": 2, "unit": "round"},
            },
            "current": {
                "range": {"value": 8, "unit": "meter"},
                "area": {"value": 6.0, "unit": "meter"},
                "duration": {"value": 2, "unit": "round"},
            },
            "domain": {
                "range": {"value": 0, "unit": "meter"},
                "area": {"value": 15.0, "unit": "meter"},
                "duration": {"value": 5, "unit": "round"},
            },
            "unbounded_domain": {
                "range": {"value": 0, "unit": "meter"},
                "area": None,
                "duration": {"value": 3, "unit": "round"},
            },
        }
        geom = copy.deepcopy(shape_map[self.bandwidth_shape])
        return {
            "target_kinds": list(target_kinds),
            "range": geom["range"],
            "area": geom["area"],
            "duration": geom["duration"],
            "unknowns": list(unknowns or []),
        }


@dataclass(frozen=True)
class WillCarrier:
    """Canonical Base Power / Will Identity in Kageyōni before 8-Knob Shape Modulation."""

    carrier_id: str
    bearer_id: str
    name: str
    classification: str  # primordial | derivative | independent | false | unknown
    nature: str
    aspect: str
    generative_boundary: str
    inherent_limits: List[str]
    channels: List[str]
    legacy_ability_id: Optional[str] = None
    legacy_will_id: Optional[str] = None
    awakening_qualitative_change: Optional[str] = None
    default_damping: float = 0.85


# Canonical Roster of Kageyōni Will & Ability Carriers (Grounded in build/kageyoni.sqlite & LATEST-SCENE.md)
CANONICAL_WILL_CARRIERS: Dict[str, WillCarrier] = {
    "sciel_painteress": WillCarrier(
        carrier_id="sciel_painteress",
        bearer_id="sciel",
        name="Domain of the Painteress",
        classification="primordial",
        nature="Dense primordial core with Twilight aspect alongside Will complexity; manifests physical space through Will, perceiving and temporarily affecting underlying values of occupants and calcifying impressions into stone.",
        aspect="Twilight",
        generative_boundary="Perceives and temporarily modulates underlying values of occupants within the manifested domain; anchors residual Will impressions onto physical stone.",
        inherent_limits=[
            "Categorical rarity does not grant automatic combat superiority",
            "Does not establish automatic control of every occupant value",
            "Cannot erase realized prior damage or violate gaia-balance",
        ],
        channels=["twilight_pigment", "stone_substrate", "domain_space"],
        awakening_qualitative_change="Manifests Domain of the Painteress: dense primordial core + Twilight aspect binds spatial chamber boundaries and calcifies transient conduit traces into stone.",
        default_damping=0.98,
    ),
    "lucretia_trace": WillCarrier(
        carrier_id="lucretia_trace",
        bearer_id="lucretia",
        name="Sovereign Avatar Trace",
        classification="independent",
        nature="Experimental cooperative resonance trace across active and slack avatar conduits, extracting spatial and structural impressions from the remote link.",
        aspect="Resonance Trace",
        generative_boundary="Traces remote conduit links held in earth to surface provisional spatial impressions without assuming their authenticity.",
        inherent_limits=[
            "Surfaced stone impressions do not establish exact physical coordinates or authenticity without independent verification",
            "Cannot prevent target from intentionally severing its own remote link",
        ],
        channels=["avatar_conduit", "earthen_hold", "cooperative_triad"],
        default_damping=0.88,
    ),
    "voss_conduit": WillCarrier(
        carrier_id="voss_conduit",
        bearer_id="voss",
        name="Remote Avatar Conduit & Severance",
        classification="derivative",
        nature="Projects force and grab attempts through an earthen avatar vessel across subterranean seams, with intentional link severance to protect the true body.",
        aspect="Conduit Transmission",
        generative_boundary="Transmits kinetic grab vectors and severs active remote link at the cost of abandoning the avatar vessel slack in earth.",
        inherent_limits=[
            "Pinned earthen avatar cannot bypass active domain barrier without leverage",
            "Intentional link severance leaves avatar slack with prior damage and leaks conduit impressions into high-density stone domains",
        ],
        channels=["earthen_avatar", "pale_seam_conduit", "ringbolt_dial"],
        default_damping=0.35,
    ),
    "sebastian_tomoe": WillCarrier(
        carrier_id="sebastian_tomoe",
        bearer_id="sebastian",
        name="Unbounded Domain & Tomoe Topology",
        classification="derivative",
        nature="Precedent unbounded environmental domain combined with Lucretia-trained topological horizon mapping and causal dependency severance.",
        aspect="Topological Tomoe",
        generative_boundary="Maps situational dependencies and inverts hostile tether preconditions into originator backlash.",
        inherent_limits=[
            "Unbounded domain precedent does not define Sciel's boundedness",
            "Requires observed vector alignment before severing hidden conduit dependencies",
        ],
        channels=["existing_environment", "causal_dependency_graph"],
        default_damping=0.90,
    ),
    "alexandra_booder": WillCarrier(
        carrier_id="alexandra_booder",
        bearer_id="alexandra",
        name="Booder's Will & Sovereign Route",
        classification="primordial",
        nature="Booder's Will paired with Sovereign Route: touched boundaries become temporary movement paths and geometric conduit dials become legible.",
        aspect="Boundary Geometry",
        generative_boundary="Converts touched physical boundaries into movement paths and reads angular wear vectors on structural hardware.",
        inherent_limits=[
            "Requires physical contact or line-of-sight inspection of the boundary/ringbolt",
            "Unresolved principles of Booder's Will remain bounded by confirmed canon",
        ],
        channels=["touched_boundary", "geometric_horizon"],
        legacy_ability_id="sovereign-route",
        legacy_will_id="booder-will",
        default_damping=0.91,
    ),
    "levi_structure": WillCarrier(
        carrier_id="levi_structure",
        bearer_id="levi",
        name="Structure-Structure Will",
        classification="primordial",
        nature="Structure-Structure Fruit capability: perceives, decomposes, and re-architects load-bearing structural lattices.",
        aspect="Structural Lattice",
        generative_boundary="Reconfigures structural load paths and exposes hidden architectural joints.",
        inherent_limits=["Subject to gaia-balance against opposing Wills"],
        channels=["structural_seam", "load_lattice"],
        legacy_ability_id="structure",
        default_damping=0.94,
    ),
    "xandra_consequence": WillCarrier(
        carrier_id="xandra_consequence",
        bearer_id="xandra-gaia",
        name="Coherent Consequence Reversal",
        classification="primordial",
        nature="Her coherent intent can force a consequence through temporal reversal.",
        aspect="Temporal Consequence",
        generative_boundary="Forces an established causal consequence across temporal reversal boundaries when intent is coherent.",
        inherent_limits=["Requires coherent intent; cannot erase experience records marked survives_rewind=1"],
        channels=["temporal_seam", "coherent_intent"],
        legacy_ability_id="consequence",
        default_damping=0.95,
    ),
    "kenway_erosion": WillCarrier(
        carrier_id="kenway_erosion",
        bearer_id="kenway",
        name="Erosion-Erosion Will",
        classification="independent",
        nature="Erosion-Erosion Fruit capability: wears down barriers, seals, and structural resistance over contact cycles.",
        aspect="Entropic Weathering",
        generative_boundary="Progressively degrades target structural integrity and resistance thresholds.",
        inherent_limits=["Requires sustained contact or repeated cycles against high-density primordial cores"],
        channels=["surface_contact", "particulate_abrasion"],
        legacy_ability_id="erosion",
        default_damping=0.82,
    ),
    "kurogane_preservation": WillCarrier(
        carrier_id="kurogane_preservation",
        bearer_id="kurogane",
        name="Compiled Status Preservation",
        classification="independent",
        nature="Compiled Status Preservation: locks a verified state configuration against external degradation or forced overwrite.",
        aspect="State Lock",
        generative_boundary="Preserves target condition state against unauthorized mutation.",
        inherent_limits=["Cannot fabricate state that was not already verified at lock time"],
        channels=["status_seal", "invariant_anchor"],
        legacy_ability_id="status-preservation",
        default_damping=0.93,
    ),
}


@dataclass
class ModulatedTechniquePackage:
    """The complete executable output of shaping a WillCarrier with an 8-Knob Vector."""

    technique_id: str
    technique_name: str
    carrier: WillCarrier
    knobs: NinshuKnobVector
    effect_operation: str  # create | alter | connect | sever | reveal | preserve | transfer | suppress
    pressure_direction: str  # increase | decrease | activate | suppress
    pressure_target: str
    gated_action: Optional[ Tuple[str, str] ]  # (action_name, "allow" | "block")
    will_definition_contract: Dict[str, Any]
    will_expression_contract: Dict[str, Any]
    will_technique_contract: Dict[str, Any]
    will_awakening_contract: Optional[Dict[str, Any]]
    composition_aspect: Dict[str, Any]
    artifact_digest: str


class NinshuPowerConsole:
    """
    The Ninshū 8-Knob Power Console.
    Modulates base Kageyōni Wills/Abilities into shaped techniques, validates them
    against `kageyoni.will`, resolves multi-actor clashes under `gaia-balance` via
    `EffectResolver` + `ActiveConsole`, and commits durable state into `Engine`.
    """

    def __init__(self) -> None:
        self.provenance = ProvenanceGraph()
        self.effect_resolver = EffectResolver()

    def modulate(
        self,
        carrier: WillCarrier,
        knobs: NinshuKnobVector,
        *,
        technique_id: str,
        technique_name: str,
        effect_operation: str,
        pressure_target: str,
        pressure_direction: str,
        target_kinds: Optional[List[str]] = None,
        unknowns: Optional[List[str]] = None,
        gated_action: Optional[Tuple[str, str]] = None,
        claimed_assertion: Optional[str] = None,
        resolver_rule_id: str = "ninshu_clash_resolver",
        resolver_rule_version: int = 1,
        evidence_source: str = "LATEST-SCENE.md",
    ) -> ModulatedTechniquePackage:
        """
        Shapes a base `WillCarrier` using the 8 `NinshuKnobVector` settings into:
        1. Validated Kageyōni `will_definition`, `will_expression`, `will_technique`, `will_awakening` contracts.
        2. A slottable Kageyōni Composition `Aspect` for `EffectResolver`.
        3. A Provenance DAG node (CH 40) with deterministic SHA-256 digest.
        """
        knobs.validate()
        t_kinds = target_kinds or ["character", "location", "item"]
        unk = list(unknowns or [])
        if knobs.deficit_gain == "wet" and knobs.authority_gain < 1.0 and not unk:
            unk.append("exact_physical_coordinates_and_authenticity_unverified")

        evidence_status = "confirmed" if knobs.authority_gain >= 0.9 else "inferred"
        evidence_list = [
            {
                "source": evidence_source,
                "assertion": f"{carrier.name} modulated via Ninshū [{knobs.bandwidth_shape} on {knobs.substrate}]",
                "status": evidence_status,
            }
        ]

        def_id = f"wdef_{carrier.carrier_id}"
        exp_id = f"wexp_{carrier.carrier_id}"
        awk_id = f"wawk_{carrier.carrier_id}"

        # 1. Build & validate will_definition contract
        will_def_contract = {
            "schema_version": CONTRACT_VERSION,
            "id": def_id,
            "version": 1,
            "design_status": "accepted",
            "evidence": evidence_list,
            "name": carrier.name,
            "classification": carrier.classification,
            "nature": carrier.nature,
            "ancestry": [],
            "generative_boundary": carrier.generative_boundary,
            "inherent_limits": list(carrier.inherent_limits),
            "invariants": [
                {
                    "id": f"inv_{carrier.carrier_id}_gaia_balance",
                    "mode": "judgment",
                    "rule": None,
                    "statement": "No Will may completely suppress another Will inside Gaia; opposing pressures are preserved.",
                    "missing_policy": "request_judgment",
                }
            ],
        }
        validate_contract("will_definition", will_def_contract, def_id, 1)

        # 2. Build & validate will_expression contract
        will_exp_contract = {
            "schema_version": CONTRACT_VERSION,
            "id": exp_id,
            "version": 1,
            "design_status": "accepted",
            "evidence": evidence_list,
            "definition": {"id": def_id, "version": 1},
            "bearer": carrier.bearer_id,
            "legacy_will_id": carrier.legacy_will_id,
            "interpretation": f"{carrier.aspect} expression modulated at damping={knobs.damping_density:.2f}",
            "channels": list(carrier.channels),
            "stat_bindings": [
                {
                    "property_id": "will_density",
                    "definition_version": 1,
                    "subject_role": "actor",
                    "stage": "magnitude",
                    "contribution_id": f"contrib_{technique_id}_density",
                }
            ],
            "learned_techniques": [{"id": technique_id, "version": 1}],
            "conditions": [f"substrate:{knobs.substrate}", f"shape:{knobs.bandwidth_shape}"],
            "awakening_access": "accessed" if knobs.bandwidth_shape in ("domain", "unbounded_domain") else "latent",
            "awakening_mastery": "practiced" if knobs.damping_density >= 0.9 else "unstable",
            "awakening_definition": {"id": awk_id, "version": 1} if carrier.awakening_qualitative_change else None,
        }
        validate_contract("will_expression", will_exp_contract, exp_id, 1)

        # 3. Build & validate will_technique contract
        derivation_desc = (
            f"Ninshū 8-Knob Shape Transformation: substrate={knobs.substrate}, "
            f"shape={knobs.bandwidth_shape}, damping={knobs.damping_density}, "
            f"sidechain={knobs.sidechain_from or 'independent'}"
        )
        activation_mode = "sustained" if knobs.bandwidth_shape in ("domain", "unbounded_domain") else (
            "reactive" if knobs.sidechain_from else "deliberate"
        )
        will_tech_contract = {
            "schema_version": CONTRACT_VERSION,
            "id": technique_id,
            "version": 1,
            "design_status": "accepted",
            "evidence": evidence_list,
            "expression": {"id": exp_id, "version": 1},
            "name": technique_name,
            "derivation": derivation_desc,
            "practice_status": "demonstrated",
            "activation": activation_mode,
            "trigger": {
                "id": f"trig_{technique_id}",
                "mode": "judgment",
                "rule": None,
                "statement": f"Actor {carrier.bearer_id} engages {knobs.substrate} via {knobs.bandwidth_shape}",
                "missing_policy": "request_judgment",
            },
            "channels": [
                {
                    "medium": carrier.channels[0] if carrier.channels else knobs.substrate,
                    "access": {
                        "id": f"acc_{technique_id}",
                        "mode": "judgment",
                        "rule": None,
                        "statement": f"Channel {knobs.substrate} is reachable within scene",
                        "missing_policy": "request_judgment",
                    },
                    "break_conditions": [
                        {
                            "id": f"brk_{technique_id}",
                            "mode": "judgment",
                            "rule": None,
                            "statement": "Conduit severed or domain boundary voluntarily released",
                            "missing_policy": "request_judgment",
                        }
                    ],
                }
            ],
            "effects": [
                {
                    "operation": effect_operation,
                    "target_role": "target",
                    "mechanism": f"{technique_name} ({knobs.bandwidth_shape} on {knobs.substrate})",
                    "preconditions": [],
                    "scope": knobs.scope_geometry(t_kinds, unk),
                    "inputs": [
                        {
                            "property_id": "will_density",
                            "definition_version": 1,
                            "subject_role": "actor",
                            "stage": "magnitude",
                            "contribution_id": f"eff_in_{technique_id}",
                        }
                    ],
                    "resolver": {"id": resolver_rule_id, "version": resolver_rule_version},
                    "authority": "mechanical",
                    "resistance": [
                        {
                            "id": f"res_{technique_id}",
                            "mode": "judgment",
                            "rule": None,
                            "statement": "Opposing Will resists complete suppression under gaia-balance",
                            "missing_policy": "request_judgment",
                        }
                    ],
                    "postconditions": [
                        {
                            "id": f"post_{technique_id}",
                            "mode": "judgment",
                            "rule": None,
                            "statement": "Physical residue and calcified impressions persist after active link ends",
                            "missing_policy": "request_judgment",
                        }
                    ],
                }
            ],
            "costs": [],
            "resolution_policy": {"id": resolver_rule_id, "version": resolver_rule_version},
            "termination": [
                {
                    "id": f"term_{technique_id}",
                    "mode": "judgment",
                    "rule": None,
                    "statement": "Terminates upon link severance or domain release while preserving stone/earth residue",
                    "missing_policy": "request_judgment",
                }
            ],
        }
        validate_contract("will_technique", will_tech_contract, technique_id, 1)

        # 4. Optional will_awakening contract (e.g. Sciel's Domain of the Painteress)
        will_awk_contract = None
        if carrier.awakening_qualitative_change:
            will_awk_contract = {
                "schema_version": CONTRACT_VERSION,
                "id": awk_id,
                "version": 1,
                "design_status": "accepted",
                "evidence": evidence_list,
                "expression": {"id": exp_id, "version": 1},
                "qualitative_change": carrier.awakening_qualitative_change,
                "substrates": [knobs.substrate, "stone", "earth"],
                "eligibility": [
                    {
                        "id": f"elig_{awk_id}",
                        "mode": "judgment",
                        "rule": None,
                        "statement": "Dense primordial core with Twilight aspect manifested",
                        "missing_policy": "request_judgment",
                    }
                ],
                "activation_conditions": [
                    {
                        "id": f"act_{awk_id}",
                        "mode": "judgment",
                        "rule": None,
                        "statement": "Bearer projects Will into surrounding stone chamber",
                        "missing_policy": "request_judgment",
                    }
                ],
                "transformed_techniques": [{"id": technique_id, "version": 1}],
                "upkeep": [{"amount": {"value": float(knobs.thermal_tier), "unit": "stamina_tick"}}],
                "interruptions": [
                    {
                        "id": f"int_{awk_id}",
                        "mode": "judgment",
                        "rule": None,
                        "statement": "Target severs remote conduit link, leaving slack vessel and stone impressions",
                        "missing_policy": "request_judgment",
                    }
                ],
                "other_agency": "Occupants retain agency and resistance under gaia-balance; underlying values are perceived and temporarily affected without total suppression.",
                "persistent_residue": [
                    "provisional_g7_chamber_stone_painting",
                    "dark_vessel_stone_painting",
                    "gaia_three_rib_cave_ringbolt_pale_seam_impression",
                ],
                "recovery_conditions": [
                    {
                        "id": f"rec_{awk_id}",
                        "mode": "judgment",
                        "rule": None,
                        "statement": "Domain release restores ambient space while stone-painted residue endures",
                        "missing_policy": "request_judgment",
                    }
                ],
            }
            validate_contract("will_awakening", will_awk_contract, awk_id, 1)

        # 5. Build slottable Kageyōni Composition Aspect for EffectResolver (CH 43)
        aspect_effects: List[Dict[str, Any]] = [
            {
                "operation": "pressure",
                "target": pressure_target,
                "direction": pressure_direction,
                "strength": f"{knobs.bandwidth_shape}:damping={knobs.damping_density:.2f}",
                "conditions": [],
            }
        ]
        if gated_action is not None:
            act_name, disposition = gated_action
            aspect_effects.append(
                {
                    "operation": "gate",
                    "target": pressure_target,
                    "action": act_name,
                    "disposition": disposition,
                    "reason": f"{technique_name} ({carrier.name}) enforces {disposition} on {act_name}",
                    "conditions": [],
                }
            )
        if claimed_assertion:
            aspect_effects.append(
                {
                    "operation": "assert",
                    "target": pressure_target,
                    "value": claimed_assertion,
                    "status": "confirmed" if knobs.authority_gain >= 0.9 else "proposed",
                    "conditions": [],
                }
            )

        composition_aspect = {
            "aspect_id": f"aspect.{technique_id}",
            "family": "will_resonance",
            "type": "will_technique_modulation",
            "authority": "evidence" if knobs.authority_gain >= 0.9 else "derived",
            "provenance": [{"source": evidence_source, "technique_id": technique_id, "bearer": carrier.bearer_id}],
            "effects": aspect_effects,
            "explanation_edges": (
                [{"from": f"aspect.{knobs.sidechain_from}", "to": f"aspect.{technique_id}", "kind": "sidechain_resonance"}]
                if knobs.sidechain_from
                else []
            ),
        }

        payload_bytes = json.dumps(
            {
                "will_definition": will_def_contract,
                "will_expression": will_exp_contract,
                "will_technique": will_tech_contract,
                "composition_aspect": composition_aspect,
            },
            sort_keys=True,
        ).encode("utf-8")
        artifact_digest = hashlib.sha256(payload_bytes).hexdigest()

        node = ArtifactNode.from_bytes(
            artifact_id=technique_id,
            data=payload_bytes,
            mime_type="application/vnd.kageyoni.ninshu-technique+json",
            metadata={
                "bearer": carrier.bearer_id,
                "shape": knobs.bandwidth_shape,
                "substrate": knobs.substrate,
                "damping": knobs.damping_density,
            },
        )
        self.provenance.add_node(node)
        if knobs.sidechain_from and self.provenance.has_node(knobs.sidechain_from):
            self.provenance.add_derivation(
                source_id=knobs.sidechain_from,
                target_id=technique_id,
                transform_name="ninshu_sidechain_coupling",
                timestamp=167.0,
                parameters={"substrate": knobs.substrate, "shape": knobs.bandwidth_shape},
            )

        return ModulatedTechniquePackage(
            technique_id=technique_id,
            technique_name=technique_name,
            carrier=carrier,
            knobs=knobs,
            effect_operation=effect_operation,
            pressure_direction=pressure_direction,
            pressure_target=pressure_target,
            gated_action=gated_action,
            will_definition_contract=will_def_contract,
            will_expression_contract=will_exp_contract,
            will_technique_contract=will_tech_contract,
            will_awakening_contract=will_awk_contract,
            composition_aspect=composition_aspect,
            artifact_digest=artifact_digest,
        )

    def resolve_polyphonic_clash(
        self,
        packages: List[ModulatedTechniquePackage],
        *,
        world_rule_id: str = "gaia-balance",
    ) -> Dict[str, Any]:
        """
        Resolves a multi-character Will clash under `gaia-balance` without d20 rolls.
        Uses Kageyōni's `EffectResolver` (CH 43) and Ninshū's `ActiveConsole` (Bus E)
        to preserve opposing pressures, determine blocked vs. allowed gates, and
        compute persistent stone/earthen residue from damping differentials.
        """
        require(bool(packages), "At least one modulated technique package is required")
        aspects = [p.composition_aspect for p in packages]
        resolution = self.effect_resolver.resolve(aspects)

        # Stream every modulated technique onto the ActiveConsole
        patch_manifest = {
            "patch_id": f"ninshu_clash_{world_rule_id}",
            "reversibility_tier": max((p.knobs.thermal_tier for p in packages), default=0),
            "channel_strips": [
                {
                    "ch": 41 + (idx % 8),
                    "name": pkg.technique_name[:28],
                    "carrier": "kageyoni/ninshu/power_system.py",
                    "entrypoint": "NinshuPowerConsole.modulate",
                    "tier": pkg.knobs.thermal_tier,
                }
                for idx, pkg in enumerate(packages)
            ],
        }
        console = ActiveConsole(patch_manifest)
        conditioned_signals: List[Dict[str, Any]] = []
        for idx, pkg in enumerate(packages):
            ch_num = 41 + (idx % 8)
            console.set_fader(ch_num, round((pkg.knobs.damping_density - 0.5) * 12.0, 2))
            # Confidence of observation is 1.0 so contested/severed actions are never muted by the noise gate
            conditioned_signals.extend(
                console.stream_track(
                    ch_num,
                    [
                        {
                            "technique_id": pkg.technique_id,
                            "bearer": pkg.carrier.bearer_id,
                            "shape": pkg.knobs.bandwidth_shape,
                            "substrate": pkg.knobs.substrate,
                            "damping_density": pkg.knobs.damping_density,
                            "authority_gain": pkg.knobs.authority_gain,
                            "pressure_target": pkg.pressure_target,
                            "pressure_direction": pkg.pressure_direction,
                            "confidence_score": 1.0,
                        }
                    ],
                )
            )
        master_tape = console.print_master(
            session_id="ninshu_will_clash_session",
            active_signals=conditioned_signals,
            compiled_aspects=aspects,
        )

        # Compute damping-driven residue and deterministic outcome per technique (no d20 rolls)
        max_domain_damping = max(
            (p.knobs.damping_density for p in packages if p.knobs.bandwidth_shape in ("domain", "unbounded_domain")),
            default=0.0,
        )
        outcomes_by_technique: Dict[str, str] = {}
        calcified_residues: List[Dict[str, Any]] = []
        unverified_deficits: List[Dict[str, Any]] = []

        blocked_actions = {
            g["action"]
            for g in resolution.get("action_gates", [])
            if g.get("state") in ("BLOCKED", "CONFLICTED")
        }

        for pkg in packages:
            if pkg.gated_action and pkg.gated_action[1] == "allow" and pkg.gated_action[0] in blocked_actions:
                # Technique's primary offensive gate was blocked by higher-damping domain/hold,
                # or converted into a partial severance
                outcomes_by_technique[pkg.technique_id] = (
                    "partial" if pkg.effect_operation == "sever" else "interrupted"
                )
            else:
                outcomes_by_technique[pkg.technique_id] = "success"

            # If a conduit/trace interacts inside a high-damping domain (like Sciel's 0.98 Twilight Core),
            # its transient signal calcifies into persistent physical stone residue
            if max_domain_damping >= 0.90 and pkg.knobs.substrate in ("conduit_link", "avatar_vessel", "stone"):
                calcified_residues.append(
                    {
                        "source_technique": pkg.technique_id,
                        "bearer": pkg.carrier.bearer_id,
                        "substrate": pkg.knobs.substrate,
                        "calcified_by_damping": max_domain_damping,
                        "epistemic_status": "confirmed" if pkg.knobs.authority_gain >= 0.9 else "inferred",
                    }
                )

            if pkg.knobs.deficit_gain == "wet" and pkg.knobs.authority_gain < 1.0:
                for unk in pkg.will_technique_contract["effects"][0]["scope"]["unknowns"]:
                    unverified_deficits.append(
                        {
                            "technique_id": pkg.technique_id,
                            "bearer": pkg.carrier.bearer_id,
                            "deficit_kind": "UNVERIFIED_CONDUIT_IMPRESSION",
                            "unknown": unk,
                        }
                    )

        return {
            "world_rule_enforced": world_rule_id,
            "gaia_balance_preserved": len(resolution.get("conflicts", [])) > 0,
            "effect_resolution": resolution,
            "outcomes_by_technique": outcomes_by_technique,
            "calcified_residues": calcified_residues,
            "unverified_deficits": unverified_deficits,
            "provenance_execution_order": self.provenance.topological_sort(),
            "master_tape_digest": master_tape.master_sha256,
        }

    def shape_channel_to_knobs(
        self,
        channel: Dict[str, Any] | int,
        overrides: Optional[Dict[str, Any]] = None,
        patchbay: Optional[Any] = None,
    ) -> NinshuKnobVector:
        """Derives a calibrated NinshuKnobVector from channel strip metadata."""
        ch_dict = self._resolve_channel_dict(channel, patchbay)
        ovr = overrides or {}

        # 1. Map substrate
        lens = ch_dict.get("lens_family", "").lower()
        formats = [f.lower() for f in ch_dict.get("subject_formats", [])]
        cat = ch_dict.get("category", "").lower()

        if "stone" in lens or "stone" in formats:
            sub = "stone"
        elif "earth" in lens or "earth" in formats:
            sub = "earth"
        elif "conduit" in lens or "network" in cat or "pcap" in formats or "tls" in formats:
            sub = "conduit_link"
        elif "avatar" in lens or "process" in cat:
            sub = "avatar_vessel"
        elif "seam" in lens or "boundary" in lens:
            sub = "boundary_seam"
        elif "graph" in lens or "causal" in cat:
            sub = "causal_graph"
        elif "value" in lens:
            sub = "underlying_value"
        elif "temporal" in lens:
            sub = "temporal_consequence"
        else:
            sub = "structure_lattice"

        # 2. Epistemic authority
        confidence = ch_dict.get("epistemic_confidence", "inferred")
        authority = 1.0 if confidence in ("observed", "verified") else (0.85 if confidence == "derived" else 0.70)

        # 3. Thermal tier
        tier = int(ch_dict.get("reversibility_tier", 0))

        # 4. Deficit gain
        status = ch_dict.get("coverage_status", "complete")
        deficit = "dry" if status == "complete" else "wet"

        params = {
            "substrate": sub,
            "bandwidth_shape": "domain",
            "authority_gain": authority,
            "damping_density": 0.95,
            "thermal_tier": tier,
            "polarity": "polyphonic",
            "sidechain_from": None,
            "deficit_gain": deficit,
        }
        params.update(ovr)
        return NinshuKnobVector(**params)

    def carrier_from_channel(
        self,
        channel: Dict[str, Any] | int,
        patchbay: Optional[Any] = None,
    ) -> WillCarrier:
        """Constructs a validated WillCarrier from channel metadata."""
        ch_dict = self._resolve_channel_dict(channel, patchbay)
        ch_num = ch_dict["channel_number"]
        ch_name = ch_dict["name"]

        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", ch_name.lower().strip()).strip("_")
        carrier_id = f"carrier_ch{ch_num}_{clean_name}"

        return WillCarrier(
            carrier_id=carrier_id,
            bearer_id="ninshu_console",
            name=f"Channel {ch_num} ({ch_name}) Carrier",
            classification="independent",
            nature=ch_dict.get("description", f"Capability carrier for CH {ch_num}"),
            aspect=ch_dict.get("category", "smelted_capability"),
            generative_boundary=f"Mechanical inspection and transformation bound to {ch_name}",
            inherent_limits=["Requires valid input adhering to channel structural invariants"],
            channels=list(ch_dict.get("subject_formats", ["binary"])),
            legacy_ability_id=f"ninshu_ch_{ch_num}",
            default_damping=0.95,
        )

    def modulate_channel(
        self,
        channel: Dict[str, Any] | int,
        knobs: Optional[NinshuKnobVector] = None,
        patchbay: Optional[Any] = None,
        console: Optional[ActiveConsole] = None,
        technique_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[ModulatedTechniquePackage, ActiveConsole]:
        """Modulates a channel's carrier through 8-Knob transformation and mounts onto ActiveConsole."""
        ch_dict = self._resolve_channel_dict(channel, patchbay)
        ch_num = ch_dict["channel_number"]
        carrier = self.carrier_from_channel(ch_dict)
        knob_vec = knobs or self.shape_channel_to_knobs(ch_dict)

        tech_id = f"tech_ch{ch_num}_{re.sub(r'[^a-zA-Z0-9_]', '_', ch_dict['name'].lower())}"
        tech_name = technique_name or f"Ninshū CH {ch_num} Modulation"

        mod_pkg = self.modulate(
            carrier=carrier,
            knobs=knob_vec,
            technique_id=tech_id,
            technique_name=tech_name,
            effect_operation=kwargs.get("effect_operation", "reveal"),
            pressure_target=f"ch_{ch_num}_substrate",
            pressure_direction=kwargs.get("pressure_direction", "activate"),
            target_kinds=kwargs.get("target_kinds", ["item", "location"]),
            unknowns=kwargs.get("unknowns"),
            gated_action=kwargs.get("gated_action"),
            claimed_assertion=kwargs.get("claimed_assertion", f"CH {ch_num} active signal"),
            evidence_source=kwargs.get("evidence_source", "ninshu_codex.sqlite"),
        )

        manifest = {
            "patch_id": f"patch:ch{ch_num}",
            "reversibility_tier": knob_vec.thermal_tier,
            "channel_strips": [
                {
                    "ch": ch_num,
                    "name": ch_dict["name"],
                    "carrier": ch_dict.get("carrier_path", "unknown"),
                    "entrypoint": ch_dict.get("entrypoint", "parse"),
                    "tier": knob_vec.thermal_tier,
                }
            ],
        }
        active_console = console or ActiveConsole(manifest)
        if ch_num not in active_console.channels:
            active_console.channels[ch_num] = ChannelStripConfig(
                channel_number=ch_num,
                name=ch_dict["name"],
                carrier_path=ch_dict.get("carrier_path", "unknown"),
                entrypoint=ch_dict.get("entrypoint", "parse"),
                thermal_ceiling=knob_vec.thermal_tier,
            )

        active_console.set_fader(ch_num, round((knob_vec.damping_density - 0.5) * 12.0, 2))
        return mod_pkg, active_console

    def _resolve_channel_dict(self, channel: Dict[str, Any] | int, patchbay: Optional[Any] = None) -> Dict[str, Any]:
        if isinstance(channel, dict):
            return channel
        from .patchbay import Patchbay
        pbay = patchbay or Patchbay()
        ch_dict = pbay.get_channel(channel)
        if not ch_dict:
            raise ValueError(f"Channel {channel} not found in Patchbay")
        return ch_dict


class NinshuPowerSystem(NinshuPowerConsole):
    """Ninshū Power System: Unified engine connecting the 8-Knob Console and Molten Smelter."""

    def __init__(self, smelter: Optional[Any] = None) -> None:
        super().__init__()
        from .smelter import MoltenSmelter
        self.smelter = smelter or MoltenSmelter()

    def smelt_and_modulate(
        self,
        samples: List[Any],
        channel_number: int,
        name: str,
        bus: str,
        patchbay: Optional[Any] = None,
        knobs: Optional[NinshuKnobVector] = None,
        console: Optional[ActiveConsole] = None,
    ) -> Tuple[Any, Dict[str, Any], ModulatedTechniquePackage, ActiveConsole]:
        """Probes raw specimen, casts channel, mechanically audits, mounts, shapes into knobs, and modulates."""
        from .patchbay import Patchbay
        pbay = patchbay or Patchbay()
        blueprint = self.smelter.probe_specimen(samples)
        artifact = self.smelter.cast_channel(blueprint, channel_number, name, bus)
        mount_res = self.smelter.quench_and_mount(artifact, pbay, console=console)
        if mount_res.get("verdict") != "ACCEPT":
            raise RuntimeError(f"Smelted channel rejected by MechanicalAuditorGate: {mount_res.get('reasons')}")
        knob_vec = knobs or self.shape_channel_to_knobs(channel_number, patchbay=pbay)
        pkg, active_console = self.modulate_channel(channel_number, knobs=knob_vec, patchbay=pbay, console=mount_res.get("console"))
        return artifact, mount_res, pkg, active_console


def execute_revision_167_painteress_encounter(engine: Engine, branch: str = "main") -> Dict[str, Any]:
    """
    Executes the exact paused Revision 165-167 encounter on an isolated or live Kageyōni Engine:
    - Player: Lucretia (Trio experimental cooperation -> Avatar Trace)
    - Companion: Sciel (Domain of the Painteress: dense primordial core + Twilight aspect)
    - Opponent: Voss (Avatar held in earth -> attempted grab blocked without injury -> ended live link)
    - Outcomes & Residue committed to SQLite Engine without d20 rolls:
      1. `will_definition`, `will_expression`, `will_technique`, `will_awakening`, `will_effect`
         validated and committed for Sciel, Lucretia, and Voss.
      2. Provisional stone-painted impressions (`g7-chamber-impression`, `dark-vessel-impression`,
         `three-rib-cave-ringbolt-seam`) recorded with `status='proposed'` (exact locations/authenticity unknown).
      3. Voss's avatar state patched to `slack_prior_damage_remains` while real Voss position remains unknown.
      4. `Engine.prepare_will_attempt` + `Engine.apply_will_attempt` executed with `mode="none"` (no d20 bloat).
    """
    console = NinshuPowerConsole()

    # 1. Ensure required property & mechanical resolver rule exist in Engine
    try:
        engine.define_property(
            "will_density",
            1,
            "Will Density",
            "Primordial core density and invariance resistance under Ninshū modulation",
            "number",
            ["character"],
            {"min": 0.0, "max": 1.0},
            lifecycle="active",
            unit="density_ratio",
        )
    except Exception:
        pass

    try:
        engine.add_rule(
            "ninshu_clash_resolver",
            1,
            "Ninshū Polyphonic Clash & Stone Calcification Resolver",
            [{"property_id": "will_density", "version": 1}],
            [{"domain": "item", "field": "condition"}],
            True,
            {
                "kind": "will_patch",
                "template": {
                    "target_role": "target",
                    "data": {
                        "condition": "slack_in_earth_prior_damage_remains",
                        "effects": "live_link_severed_impressions_calcified_on_stone",
                    },
                },
            },
            dependencies=[("will_density", 1, "reads")],
        )
    except Exception:
        pass

    # 2.Modulate the 3 clashing/chained techniques via the 8 Ninshū Knobs
    # Track 1: Lucretia's Trio Experimental Avatar Trace (Authority = 0.65 because impressions are unverified!)
    lucretia_pkg = console.modulate(
        CANONICAL_WILL_CARRIERS["lucretia_trace"],
        NinshuKnobVector(
            substrate="conduit_link",
            bandwidth_shape="spear",
            authority_gain=0.65,
            damping_density=0.88,
            thermal_tier=1,
            polarity="polyphonic",
            sidechain_from=None,
            deficit_gain="wet",
        ),
        technique_id="tech_lucretia_avatar_trace",
        technique_name="Trio Experimental Avatar Conduit Trace",
        effect_operation="reveal",
        pressure_target="voss_conduit_link",
        pressure_direction="activate",
        target_kinds=["item", "character"],
        unknowns=[
            "exact_location_of_g7_chamber_unknown",
            "exact_location_of_dark_vessel_unknown",
            "authenticity_of_three_rib_cave_ringbolt_pale_seam_unknown",
            "real_voss_position_unknown",
        ],
        claimed_assertion="Surfaced provisional G-7 chamber, dark vessel, and Gaia three-rib cave/right-wall ringbolt/pale seam impressions painted on stone",
    )

    # Track 2: Sciel's Domain of the Painteress (Sidechained from Lucretia's trace, Damping = 0.98 Twilight Core)
    sciel_pkg = console.modulate(
        CANONICAL_WILL_CARRIERS["sciel_painteress"],
        NinshuKnobVector(
            substrate="stone",
            bandwidth_shape="domain",
            authority_gain=1.0,
            damping_density=0.98,
            thermal_tier=1,
            polarity="polyphonic",
            sidechain_from="tech_lucretia_avatar_trace",
            deficit_gain="wet",
        ),
        technique_id="tech_sciel_painteress_domain",
        technique_name="Domain of the Painteress: Twilight Stone Calcification",
        effect_operation="preserve",
        pressure_target="voss_conduit_link",
        pressure_direction="suppress",
        target_kinds=["item", "character", "location"],
        unknowns=["boundedness_and_full_stat_control_limits_unestablished"],
        gated_action=("voss_avatar_grab", "block"),
        claimed_assertion="Avatar held in earth within Domain of the Painteress; Voss grab blocked without injury; conduit impressions calcified onto stone",
    )

    # Track 3: Voss's Attempted Grab & Intentional Link Severance (Damping = 0.35 disposable avatar)
    voss_pkg = console.modulate(
        CANONICAL_WILL_CARRIERS["voss_conduit"],
        NinshuKnobVector(
            substrate="avatar_vessel",
            bandwidth_shape="senbon",
            authority_gain=0.95,
            damping_density=0.35,
            thermal_tier=1,
            polarity="polyphonic",
            sidechain_from="tech_sciel_painteress_domain",
            deficit_gain="wet",
        ),
        technique_id="tech_voss_grab_and_sever",
        technique_name="Avatar Grab Attempt & Live Link Severance",
        effect_operation="sever",
        pressure_target="voss_conduit_link",
        pressure_direction="decrease",
        target_kinds=["item", "character"],
        unknowns=["real_voss_position_unknown"],
        gated_action=("voss_avatar_grab", "allow"),
        claimed_assertion="Attempted grab blocked without injury; live link intentionally severed leaving slack damaged avatar",
    )

    # 3. Resolve the 3-way clash through the Ninshū Polyphonic Console
    clash_report = console.resolve_polyphonic_clash([lucretia_pkg, sciel_pkg, voss_pkg])

    # 4. Seed/bind the Revision 167 scene entities and Will contracts in the SQLite Engine
    rev = engine.branch(branch)["revision"]
    changes: List[Dict[str, Any]] = []
    evidence_rev167 = [{"note": "LATEST-SCENE.md revision 165-167 Ninshū execution"}]

    def ensure_record(domain: str, rid: str, status: str, **data: Any) -> None:
        existing = engine.get(branch, rid)
        if not existing:
            changes.append(
                {
                    "op": "create",
                    "domain": domain,
                    "id": rid,
                    "data": data,
                    "status": status,
                    "visibility": "public",
                    "evidence": evidence_rev167,
                }
            )

    ensure_record("location", "loc_painteress_stone_site", "confirmed", name="Stone Domain Encounter Site", kind="room")
    ensure_record("clock", "clock_rev167_encounter", "confirmed", name="Avatar Trace Encounter Clock", location="loc_painteress_stone_site", tick=167, unit="revision")
    ensure_record("character", "lucretia", "confirmed", name="Lucretia", entity_kind="person", condition="uninjured", location="loc_painteress_stone_site")
    ensure_record("character", "sciel", "confirmed", name="Sciel", entity_kind="person", condition="domain_active", location="loc_painteress_stone_site")
    ensure_record("character", "voss", "confirmed", name="Voss", entity_kind="person", condition="unknown_position")
    ensure_record(
        "item",
        "voss_avatar_vessel",
        "confirmed",
        name="Voss Earthen Avatar",
        kind="avatar_vessel",
        condition="held_in_earth_prior_damage",
        effects="live_link_active",
    )
    # The 3 stone-painted impressions from Revision 165-167 (status='proposed' because authenticity/exact location unknown!)
    ensure_record(
        "item",
        "impression_g7_chamber",
        "proposed",
        name="Stone Painting: Provisional G-7 Chamber",
        kind="stone_impression",
        condition="painted_on_stone_authenticity_unknown",
        effects="captured_by_painteress_domain",
    )
    ensure_record(
        "item",
        "impression_dark_vessel",
        "proposed",
        name="Stone Painting: Dark Vessel",
        kind="stone_impression",
        condition="painted_on_stone_authenticity_unknown",
        effects="captured_by_painteress_domain",
    )
    ensure_record(
        "item",
        "impression_three_rib_cave",
        "proposed",
        name="Stone Painting: Gaia Three-Rib Cave / Right-Wall Ringbolt / Pale Seam",
        kind="stone_impression",
        condition="painted_on_stone_authenticity_unknown",
        effects="captured_by_painteress_domain",
    )

    # Add Will Definitions, Expressions, Techniques, and Sciel's Awakening
    for pkg in (lucretia_pkg, sciel_pkg, voss_pkg):
        wdef = pkg.will_definition_contract
        wexp = pkg.will_expression_contract
        wtech = pkg.will_technique_contract
        ensure_record(
            "will_definition",
            wdef["id"],
            "confirmed",
            name=wdef["name"],
            classification=wdef["classification"],
            contract=wdef,
        )
        ensure_record(
            "will_expression",
            wexp["id"],
            "confirmed",
            definition=wdef["id"],
            bearer=wexp["bearer"],
            legacy_will=wexp["legacy_will_id"],
            contract=wexp,
        )
        ensure_record(
            "will_technique",
            wtech["id"],
            "confirmed",
            expression=wexp["id"],
            ability=pkg.carrier.legacy_ability_id if (pkg.carrier.legacy_ability_id and engine.get(branch, pkg.carrier.legacy_ability_id)) else None,
            name=wtech["name"],
            contract=wtech,
        )
        if pkg.will_awakening_contract:
            wawk = pkg.will_awakening_contract
            ensure_record(
                "will_awakening",
                wawk["id"],
                "confirmed",
                expression=wexp["id"],
                contract=wawk,
            )

    if changes:
        seed_receipt = engine.apply(
            {
                "api_version": 3,
                "branch": branch,
                "expected_revision": rev,
                "request_id": "ninshu-rev167-seed-contracts",
                "kind": "action",
                "actor": "lucretia",
                "narrative": "Install Ninshū 8-Knob modulated Will contracts for Revision 167 Painteress encounter",
                "changes": changes,
                "properties": [
                    {
                        "entity_id": "sciel",
                        "property_id": "will_density",
                        "definition_version": 1,
                        "state": "known",
                        "value": 0.98,
                        "unit": "density_ratio",
                        "context": {"aspect": "Twilight", "core": "dense_primordial_core"},
                        "epistemic_status": "confirmed",
                        "visibility": "public",
                    }
                ],
            }
        )
    else:
        seed_receipt = {"event_id": engine.branch(branch).get("head_event")}

    # 5. Execute Sciel's Will Attempt via Engine.prepare_will_attempt + Engine.apply_will_attempt (mode="none", zero d20!)
    current_rev = engine.branch(branch)["revision"]
    prep_result = engine.prepare_will_attempt(
        branch,
        {
            "request_id": "ninshu-rev167-sciel-prepare",
            "attempt_id": "attempt_rev167_sciel_painteress",
            "expected_revision": current_rev,
            "actor": "sciel",
            "expression": {"id": "wexp_sciel_painteress", "version": 1},
            "technique": {"id": "tech_sciel_painteress_domain", "version": 1},
            "intent": "Hold Voss's avatar in earth within Domain of the Painteress, block grab without injury, and calcify traced impressions onto stone as Voss severs live link",
            "targets": ["voss_avatar_vessel"],
            "permission_checks": [],
            "randomness": {"mode": "none", "roll_id": None, "difficulty": None, "modifier": 0},
            "outcome_bindings": [
                {
                    "outcome": "success",
                    "effect_indexes": [0],
                    "cost_ids": [],
                }
            ],
            "judgments": [
                {"scope": "trig_tech_sciel_painteress_domain", "decision": "allow", "reason": "Domain of the Painteress active"},
                {"scope": "outcome", "decision": clash_report["outcomes_by_technique"]["tech_sciel_painteress_domain"], "reason": "Polyphonic clash resolved under gaia-balance"},
            ],
        },
    )

    commit_receipt = engine.apply_will_attempt(
        branch=branch,
        attempt_id="attempt_rev167_sciel_painteress",
        request_id="ninshu-rev167-sciel-commit",
        actor="sciel",
        narrative="Sciel's Domain of the Painteress blocks Voss's grab and calcifies the trio trace impressions onto stone as Voss severs the live link",
        expected_revision=current_rev,
    )

    # 6. Record the active `will_effect` capturing the persistent stone residue
    eff_rev = engine.branch(branch)["revision"]
    will_effect_contract = {
        "schema_version": CONTRACT_VERSION,
        "id": "weff_rev167_painteress_residue",
        "version": 1,
        "design_status": "accepted",
        "evidence": [
            {
                "source": "LATEST-SCENE.md",
                "assertion": "Domain of the Painteress active; stone impressions retained after Voss link severance",
                "status": "confirmed",
            }
        ],
        "expression": {"id": "wexp_sciel_painteress", "version": 1},
        "technique": {"id": "tech_sciel_painteress_domain", "version": 1},
        "source_event": commit_receipt["event_id"],
        "targets": ["voss_avatar_vessel", "lucretia"],
        "phase": "active",
        "anchor_records": ["loc_painteress_stone_site", "voss_avatar_vessel"],
        "start_clock": "clock_rev167_encounter",
        "start_tick": 167,
        "end_conditions": [
            {
                "id": "end_painteress_domain_release",
                "mode": "judgment",
                "rule": None,
                "statement": "Sciel voluntarily releases Domain of the Painteress; stone paintings remain",
                "missing_policy": "request_judgment",
            }
        ],
        "process_ids": [],
        "consequence_ids": [],
        "residue_records": [
            "impression_g7_chamber",
            "impression_dark_vessel",
            "impression_three_rib_cave",
            "voss_avatar_vessel",
        ],
    }
    validate_contract("will_effect", will_effect_contract, "weff_rev167_painteress_residue", 1)

    effect_receipt = engine.apply(
        {
            "api_version": 3,
            "branch": branch,
            "expected_revision": eff_rev,
            "request_id": "ninshu-rev167-record-will-effect",
            "kind": "action",
            "actor": "sciel",
            "narrative": "Bind Domain of the Painteress active Will effect and stone-painted residue records",
            "changes": [
                {
                    "op": "create",
                    "domain": "will_effect",
                    "id": "weff_rev167_painteress_residue",
                    "data": {
                        "expression": "wexp_sciel_painteress",
                        "technique": "tech_sciel_painteress_domain",
                        "contract": will_effect_contract,
                    },
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": evidence_rev167,
                }
            ],
        }
    )

    return {
        "clash_report": clash_report,
        "prep_result": prep_result,
        "commit_receipt": commit_receipt,
        "effect_receipt": effect_receipt,
        "avatar_final_state": engine.get(branch, "voss_avatar_vessel"),
        "stone_impressions": [
            engine.get(branch, "impression_g7_chamber"),
            engine.get(branch, "impression_dark_vessel"),
            engine.get(branch, "impression_three_rib_cave"),
        ],
        "sciel_will_effect": engine.get(branch, "weff_rev167_painteress_residue"),
    }
