"""
Causal Encounter Substrate for Constellation Emergence.

Implements consequential participant interaction using native Kageyoni Encounters:
1. Participants observe permitted state via Encounters.inspect(viewer=actor).
2. Participants propose actions based on continuity and role constraints.
3. A declared scheduling policy selects and executes admissible actions.
4. Engine laws enforce typed preconditions; partial writes are strictly prevented.
5. Prior databases are preserved durably across runs without deletion.
"""

from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.persistence.migrations import install_encounters
from kageyoni.workspaces.world import Encounters
from .technique import ExecutableTechnique, TechniqueStep, derive_technique_from_trace
from .hydration import HydratedCharacterPacket, hydrate_character_from_disk

EVIDENCE = [{"note": "Constellation Emergence causal encounter receipt"}]

def record(domain: str, rid: str, **data: Any) -> Dict[str, Any]:
    return dict(op="create", domain=domain, id=rid, data=data, status="confirmed", visibility="public", evidence=EVIDENCE)

def patch(rid: str, **data: Any) -> Dict[str, Any]:
    return dict(op="patch", id=rid, data=data, evidence=EVIDENCE)

@dataclass
class ParticipantDecisionInterface:
    character_id: str
    role: str
    intent: str
    priority: int = 10
    disabled_actions: List[str] = field(default_factory=list)
    hydrated_state: Optional[HydratedCharacterPacket] = None

    @classmethod
    def from_character_id(cls, character_id: str, role: Optional[str] = None, intent: str = "", priority: int = 10) -> ParticipantDecisionInterface:
        """Deterministically hydrates participant directly from their persistent SQLite character database."""
        try:
            pkt = hydrate_character_from_disk(character_id)
        except Exception:
            pkt = None
        role = role or character_id
        if not intent and pkt:
            if character_id == "sciel":
                intent = f"Transmute substrate using {pkt.get_manifestation() or 'Domain of the Painteress'}"
            elif character_id == "voss":
                intent = "Rupture cavity coordinates via remote conduit transmission"
            elif character_id == "maki":
                intent = "Enforce zero-bypass kinetic perimeter"
            elif character_id == "sebastian":
                intent = "Execute Tomoe graph inversion seal"
            else:
                intent = f"Sovereign action for {pkt.name}"
        return cls(
            character_id=character_id,
            role=role,
            intent=intent or f"Role {role} action",
            priority=priority,
            hydrated_state=pkt
        )

    def observe(self, encounters: Encounters, branch: str, encounter_id: str) -> Dict[str, Any]:
        """Observes the world strictly through the actor's permitted view."""
        return encounters.inspect(branch, encounter_id, viewer=self.character_id)

    def propose(self, observation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Proposes an action from available actions matching role and continuity."""
        avail = observation.get("next_actions", [])
        candidates = [a for a in avail if a.get("actor_id") == self.character_id or a.get("actor_role") == self.role]
        candidates = [a for a in candidates if a.get("action_id") not in self.disabled_actions]

        if not candidates:
            return None

        # Sort candidate by action definition priority or return highest
        chosen = candidates[0]
        return {
            "action_id": chosen["action_id"],
            "actor_id": self.character_id,
            "role": self.role,
            "label": chosen.get("label", chosen["action_id"]),
            "rationale": f"Role '{self.role}' responding to state '{observation.get('current_state')}' with intent '{self.intent}'" + (f" [Hydrated: {self.hydrated_state.get_manifestation() or ''} (digest: {self.hydrated_state.state_digest[:8]})]" if self.hydrated_state else ""),
        }

    def act(self, encounters: Encounters, branch: str, encounter_id: str, action_id: str, request_id: str, expected_rev: int) -> Dict[str, Any]:
        """Dispatches authorized action through the engine boundary."""
        return encounters.act(
            branch=branch,
            encounter_id=encounter_id,
            action_id=action_id,
            request_id=request_id,
            expected_revision=expected_rev,
            viewer=self.character_id
        )

class DeclaredSchedulingPolicy:
    """
    Declared, unscripted scheduling policy governing participant turn progression.
    In each turn, participants observe state; responders have initiative to counter disturbances;
    if responders cannot act, adversarial escalation proceeds.
    """
    def __init__(self, participants: List[ParticipantDecisionInterface]):
        self.participants = sorted(participants, key=lambda p: p.priority)

    def execute_next_cycle(self, encounters: Encounters, branch: str, encounter_id: str, request_prefix: str) -> Optional[Dict[str, Any]]:
        ins = encounters.inspect(branch, encounter_id)
        if ins.get("phase") in ("completed", "failed", "blocked"):
            return None

        current_rev = encounters.engine.branch(branch)["revision"]

        # Each participant inspects from their permitted perspective
        for p in self.participants:
            obs = p.observe(encounters, branch, encounter_id)
            proposal = p.propose(obs)
            if proposal:
                action_id = proposal["action_id"]
                req_id = f"{request_prefix}-{p.character_id}-{action_id}-{uuid.uuid4().hex[:6]}"
                receipt = p.act(encounters, branch, encounter_id, action_id, req_id, current_rev)
                return {
                    "actor": p.character_id,
                    "role": p.role,
                    "action_id": action_id,
                    "observation": {
                        "state": obs.get("current_state"),
                        "available_actions": [a["action_id"] for a in obs.get("next_actions", [])],
                    },
                    "proposal": proposal,
                    "receipt": receipt,
                }
        return None

class CausalEncounterHarness:
    """
    Sets up and executes physically grounded causal encounters using native Kageyoni Encounters.
    Preserves durable state databases and executes via declared participant interfaces.
    """
    def __init__(self, engine: Engine, branch: str = "main"):
        self.engine = engine
        self.branch = branch
        install_encounters(self.engine)
        self.encounters = Encounters(self.engine)
        self._seed_world()

    def _seed_world(self) -> None:
        rev = self.engine.branch(self.branch)["revision"]
        # Characters (strictly adhering to character domain schema)
        chars = ["voss", "sciel", "sebastian", "maki", "alexandra", "elijah"]
        char_records = []
        for cid in chars:
            if not self.engine.get(self.branch, cid):
                char_records.append(record("character", cid, name=cid.capitalize(), entity_kind="person", condition="active"))
        
        # Environmental items (strictly adhering to item domain schema)
        item_records = []
        # Alpha Chamber (Discovery)
        if not self.engine.get(self.branch, "chamber_alpha"):
            item_records.append(record("item", "chamber_alpha", name="Workspace Cavity Alpha", kind="cavity", condition="stable", effects="none"))
        if not self.engine.get(self.branch, "matrix_anchor_alpha"):
            item_records.append(record("item", "matrix_anchor_alpha", name="Basalt Anchor Alpha", kind="foundation", condition="absent", effects="none"))
        if not self.engine.get(self.branch, "kinetic_perimeter_alpha"):
            item_records.append(record("item", "kinetic_perimeter_alpha", name="Kinetic Perimeter Alpha", kind="barrier", condition="open", effects="none"))

        # Beta Chamber (Same-Template Instance Reuse)
        if not self.engine.get(self.branch, "chamber_beta"):
            item_records.append(record("item", "chamber_beta", name="Workspace Cavity Beta", kind="cavity", condition="stable", effects="none"))
        if not self.engine.get(self.branch, "matrix_anchor_beta"):
            item_records.append(record("item", "matrix_anchor_beta", name="Basalt Anchor Beta", kind="foundation", condition="absent", effects="none"))
        if not self.engine.get(self.branch, "kinetic_perimeter_beta"):
            item_records.append(record("item", "kinetic_perimeter_beta", name="Kinetic Perimeter Beta", kind="barrier", condition="open", effects="none"))

        # Gamma Multi-Zone Topology (Structurally Changed Encounter for Transfer Testing)
        if not self.engine.get(self.branch, "chamber_gamma_outer"):
            item_records.append(record("item", "chamber_gamma_outer", name="Gamma Outer Vault", kind="cavity", condition="stable", effects="none"))
        if not self.engine.get(self.branch, "chamber_gamma_inner"):
            item_records.append(record("item", "chamber_gamma_inner", name="Gamma Inner Sanctum", kind="cavity", condition="stable", effects="none"))
        if not self.engine.get(self.branch, "bifurcated_ward_gamma"):
            item_records.append(record("item", "bifurcated_ward_gamma", name="Bifurcated Dual Ward", kind="barrier", condition="dual_locked", effects="none"))

        # Explicit Location entities
        loc_records = []
        for sfx in ["alpha", "beta"]:
            lid = f"loc_chamber_{sfx}"
            if not self.engine.get(self.branch, lid):
                loc_records.append(record("location", lid, name=f"Chamber {sfx.capitalize()} Bedrock", kind="room", geography="pale_seam_strata"))
        if not self.engine.get(self.branch, "loc_chamber_gamma"):
            loc_records.append(record("location", "loc_chamber_gamma", name="Bifurcated Gamma Sanctum", kind="room", geography="dual_vault_bedrock"))

        # Explicit Environment entities
        env_records = []
        for sfx in ["alpha", "beta"]:
            eid_env = f"env_matrix_{sfx}"
            if not self.engine.get(self.branch, eid_env):
                env_records.append(record("environment", eid_env, location=f"loc_chamber_{sfx}", feature="bedrock_strata", kind="metaphysical", rule="cavity_stability_requires_basalt_anchor"))
        if not self.engine.get(self.branch, "env_matrix_gamma"):
            env_records.append(record("environment", "env_matrix_gamma", location="loc_chamber_gamma", feature="bifurcated_strata", kind="metaphysical", rule="dual_zone_containment_required"))

        all_changes = char_records + loc_records + env_records + item_records
        if all_changes:
            self.engine.apply(dict(
                api_version=3,
                branch=self.branch,
                request_id=f"seed-causal-env-{uuid.uuid4().hex[:6]}",
                expected_revision=rev,
                actor="system",
                narrative="Seed causal encounter participants and topology",
                kind="action",
                changes=all_changes
            ))

    def define_clash_encounter(self, definition_id: str = "constellation-clash", version: int = 1, chamber_suffix: str = "alpha") -> Dict[str, Any]:
        chamber_id = f"chamber_{chamber_suffix}"
        anchor_id = f"matrix_anchor_{chamber_suffix}"
        perimeter_id = f"kinetic_perimeter_{chamber_suffix}"

        def action(label: str, role: str, kind: str, payload: Dict[str, Any], next_state: str,
                   requirements: Optional[List[Dict[str, Any]]] = None,
                   resolve: Tuple[str, ...] = (),
                   cancel: Optional[List[Dict[str, str]]] = None):
            return dict(
                label=label,
                actor_role=role,
                kind=kind,
                payload=payload,
                next_state=next_state,
                requirements=requirements or [],
                resolve_loops=list(resolve),
                cancel_loops=cancel or [],
                detach_loops=[]
            )

        spec = dict(
            title=f"Constellation Emergence Causal Clash ({chamber_suffix})",
            roles=["voss", "sciel", "sebastian", "maki"],
            visibility="public",
            max_steps=15,
            initial_state="init",
            loops=[
                dict(id="stabilization", kind="containment", required=True, depends_on=[], continuable=False, cancellable=True),
                dict(id="perimeter", kind="enforcement", required=True, depends_on=["stabilization"], continuable=False, cancellable=True),
                dict(id="closure", kind="inversion", required=True, depends_on=["perimeter"], continuable=False, cancellable=True)
            ],
            states={
                "init": dict(phase="active", outcome="unresolved", actions=["voss_rupture"]),
                "ruptured": dict(phase="active", outcome="unresolved", actions=["sciel_anchor", "voss_escalate"]),
                "anchored": dict(phase="active", outcome="unresolved", actions=["maki_enforce", "voss_counter_probe"]),
                "locked": dict(phase="active", outcome="unresolved", actions=["sebastian_seal"]),
                "resolved": dict(phase="completed", outcome="achieved", actions=[]),
                "collapsed": dict(phase="failed", outcome="not_achieved", actions=[])
            },
            actions={}
        )

        spec["actions"]["voss_rupture"] = action(
            "Voss deploys cavity rupture disturbance",
            "voss", "event",
            {"changes": [
                patch(chamber_id, condition="cavity_ruptured"),
                patch(anchor_id, condition="absent"),
                patch(perimeter_id, condition="open")
            ]},
            "ruptured"
        )

        cancel_on_collapse = [
            {"loop_id": "stabilization", "reason": "Cavity collapsed by Voss disruption"},
            {"loop_id": "perimeter", "reason": "Cavity collapsed by Voss disruption"},
            {"loop_id": "closure", "reason": "Cavity collapsed by Voss disruption"}
        ]

        spec["actions"]["voss_escalate"] = action(
            "Voss collapses unanchored cavity",
            "voss", "event",
            {"changes": [patch(chamber_id, condition="collapsed")]},
            "collapsed",
            requirements=[{"record_id": anchor_id, "field": "condition", "equals": "absent"}],
            cancel=cancel_on_collapse
        )

        spec["actions"]["sciel_anchor"] = action(
            "Sciel transmutes narrative fluid into dense basalt foundation",
            "sciel", "event",
            {"changes": [
                patch(anchor_id, condition="anchored", effects="dense_basalt"),
                patch(chamber_id, condition="basalt_anchored")
            ]},
            "anchored",
            requirements=[{"record_id": chamber_id, "field": "condition", "equals": "cavity_ruptured"}],
            resolve=("stabilization",)
        )

        spec["actions"]["voss_counter_probe"] = action(
            "Voss exploits unlocked kinetic perimeter to shatter matrix",
            "voss", "event",
            {"changes": [patch(chamber_id, condition="collapsed")]},
            "collapsed",
            requirements=[{"record_id": perimeter_id, "field": "condition", "equals": "open"}],
            cancel=cancel_on_collapse
        )

        spec["actions"]["maki_enforce"] = action(
            "Maki locks zero-bypass kinetic perimeter",
            "maki", "event",
            {"changes": [patch(perimeter_id, condition="locked", effects="zero_bypass")]},
            "locked",
            requirements=[
                {"record_id": anchor_id, "field": "condition", "equals": "anchored"},
                {"record_id": chamber_id, "field": "condition", "equals": "basalt_anchored"}
            ],
            resolve=("perimeter",)
        )

        spec["actions"]["sebastian_seal"] = action(
            "Sebastian executes tomoe graph inversion to seal node",
            "sebastian", "event",
            {"changes": [patch(chamber_id, condition="sealed", effects="tomoe_inverted")]},
            "resolved",
            requirements=[{"record_id": perimeter_id, "field": "condition", "equals": "locked"}],
            resolve=("closure",)
        )

        req_id = f"def-{definition_id}-v{version}-{uuid.uuid4().hex[:6]}"
        return self.encounters.define(definition_id, version, spec, req_id)

    def define_structural_transfer_encounter(self, definition_id: str = "constellation-structural-clash", version: int = 1) -> Dict[str, Any]:
        """
        Defines a structurally altered encounter with bifurcated dual-zone topology.
        Tests whether candidate techniques transfer across structurally divergent invariants.
        """
        spec = dict(
            title="Constellation Emergence Structurally Altered Dual-Zone Clash",
            roles=["voss", "sciel", "sebastian", "maki"],
            visibility="public",
            max_steps=20,
            initial_state="init",
            loops=[
                dict(id="outer_containment", kind="containment", required=True, depends_on=[], continuable=False, cancellable=True),
                dict(id="inner_reinforcement", kind="containment", required=True, depends_on=["outer_containment"], continuable=False, cancellable=True),
                dict(id="bifurcated_seal", kind="inversion", required=True, depends_on=["inner_reinforcement"], continuable=False, cancellable=True)
            ],
            states={
                "init": dict(phase="active", outcome="unresolved", actions=["voss_bifurcated_strike"]),
                "bifurcated_breach": dict(phase="active", outcome="unresolved", actions=["sciel_outer_anchor", "voss_dual_shatter"]),
                "outer_held": dict(phase="active", outcome="unresolved", actions=["sciel_inner_anchor", "voss_dual_shatter"]),
                "dual_anchored": dict(phase="active", outcome="unresolved", actions=["maki_bifurcated_lock", "voss_dual_shatter"]),
                "bifurcated_locked": dict(phase="active", outcome="unresolved", actions=["sebastian_bifurcated_seal"]),
                "resolved": dict(phase="completed", outcome="achieved", actions=[]),
                "collapsed": dict(phase="failed", outcome="not_achieved", actions=[])
            },
            actions={}
        )

        def action(label: str, role: str, kind: str, payload: Dict[str, Any], next_state: str,
                   requirements: Optional[List[Dict[str, Any]]] = None,
                   resolve: Tuple[str, ...] = (),
                   cancel: Optional[List[Dict[str, str]]] = None):
            return dict(
                label=label, actor_role=role, kind=kind, payload=payload, next_state=next_state,
                requirements=requirements or [], resolve_loops=list(resolve), cancel_loops=cancel or [], detach_loops=[]
            )

        cancel_dual = [
            {"loop_id": "outer_containment", "reason": "Dual zones collapsed"},
            {"loop_id": "inner_reinforcement", "reason": "Dual zones collapsed"},
            {"loop_id": "bifurcated_seal", "reason": "Dual zones collapsed"}
        ]

        spec["actions"]["voss_bifurcated_strike"] = action(
            "Voss launches bifurcated strike breaching outer and inner chambers",
            "voss", "event",
            {"changes": [
                patch("chamber_gamma_outer", condition="cavity_ruptured"),
                patch("chamber_gamma_inner", condition="cavity_ruptured"),
                patch("bifurcated_ward_gamma", condition="dual_breached")
            ]},
            "bifurcated_breach"
        )
        spec["actions"]["voss_dual_shatter"] = action(
            "Voss collapses unsealed bifurcated chambers",
            "voss", "event",
            {"changes": [patch("chamber_gamma_outer", condition="collapsed"), patch("chamber_gamma_inner", condition="collapsed")]},
            "collapsed", cancel=cancel_dual
        )
        spec["actions"]["sciel_outer_anchor"] = action(
            "Sciel anchors outer basalt ward",
            "sciel", "event",
            {"changes": [patch("chamber_gamma_outer", condition="basalt_anchored")]},
            "outer_held",
            requirements=[{"record_id": "chamber_gamma_outer", "field": "condition", "equals": "cavity_ruptured"}],
            resolve=("outer_containment",)
        )
        spec["actions"]["sciel_inner_anchor"] = action(
            "Sciel anchors inner sanctum ward",
            "sciel", "event",
            {"changes": [patch("chamber_gamma_inner", condition="basalt_anchored")]},
            "dual_anchored",
            requirements=[{"record_id": "chamber_gamma_inner", "field": "condition", "equals": "cavity_ruptured"}],
            resolve=("inner_reinforcement",)
        )
        spec["actions"]["maki_bifurcated_lock"] = action(
            "Maki locks bifurcated perimeter across both zones",
            "maki", "event",
            {"changes": [patch("bifurcated_ward_gamma", condition="dual_locked")]},
            "bifurcated_locked",
            requirements=[
                {"record_id": "chamber_gamma_outer", "field": "condition", "equals": "basalt_anchored"},
                {"record_id": "chamber_gamma_inner", "field": "condition", "equals": "basalt_anchored"}
            ]
        )
        spec["actions"]["sebastian_bifurcated_seal"] = action(
            "Sebastian executes dual tomoe inversion sealing both chambers",
            "sebastian", "event",
            {"changes": [patch("chamber_gamma_outer", condition="sealed"), patch("chamber_gamma_inner", condition="sealed")]},
            "resolved",
            requirements=[{"record_id": "bifurcated_ward_gamma", "field": "condition", "equals": "dual_locked"}],
            resolve=("bifurcated_seal",)
        )

        req_id = f"def-{definition_id}-v{version}-{uuid.uuid4().hex[:6]}"
        return self.encounters.define(definition_id, version, spec, req_id)

    def start_encounter(self, definition_id: str, version: int, encounter_id: str, participants: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        parts = participants or {"voss": "voss", "sciel": "sciel", "sebastian": "sebastian", "maki": "maki"}
        rev = self.engine.branch(self.branch)["revision"]
        req_id = f"start-{encounter_id}-{uuid.uuid4().hex[:6]}"
        return self.encounters.start(
            branch=self.branch,
            definition_id=definition_id,
            definition_version=version,
            encounter_id=encounter_id,
            request_id=req_id,
            expected_revision=rev,
            participants=parts
        )

    def execute_action(self, encounter_id: str, action_id: str, request_id: Optional[str] = None, viewer: Optional[str] = None) -> Dict[str, Any]:
        rev = self.engine.branch(self.branch)["revision"]
        req = request_id or f"act-{encounter_id}-{action_id}-{uuid.uuid4().hex[:6]}"
        return self.encounters.act(
            branch=self.branch,
            encounter_id=encounter_id,
            action_id=action_id,
            request_id=req,
            expected_revision=rev,
            viewer=viewer
        )

    def inspect(self, encounter_id: str, viewer: Optional[str] = None) -> Dict[str, Any]:
        return self.encounters.inspect(self.branch, encounter_id, viewer=viewer)

    def run_autonomous_schedule(self, encounter_id: str, scheduler: DeclaredSchedulingPolicy, max_cycles: int = 10, request_prefix: str = "auto") -> List[Dict[str, Any]]:
        """Executes the encounter via declared participant decisions without hardcoded workflows."""
        trace = []
        for i in range(max_cycles):
            entry = scheduler.execute_next_cycle(self.encounters, self.branch, encounter_id, f"{request_prefix}-c{i+1}")
            if not entry:
                break
            trace.append(entry)
        return trace

    def derive_candidate(self, encounter_id: str, trace: List[Dict[str, Any]], definition_id: str = "constellation-clash", version: int = 1) -> Optional[ExecutableTechnique]:
        spec_row = self.engine.db.execute("SELECT spec_json FROM encounter_definitions WHERE definition_id=? AND version=?", (definition_id, version)).fetchone()
        if not spec_row:
            return None
        spec = json.loads(spec_row["spec_json"])
        return derive_technique_from_trace(trace, spec, encounter_id, self.branch)
