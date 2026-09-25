"""
Levi Sim Cognitive Model (Upgraded Operator Interface).

Implements autonomous deliberation, dynamic capability assimilation, and epistemic firewalls:
1. Strict Epistemic Separation: Distinguishes User Intent, Observations, Hypotheses, Beliefs, Facts, and Constraints.
2. Dynamic Reasoning:
   - Upstream reframing
   - Constraint economics (trade-off calculation)
   - Dynamic rejection adaptation (metabolizes rejections; dynamic constraints obsolete on state changes)
   - Sovereign NPC interaction & alignment negotiation
   - Legitimate closure recognition
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from levi_sim.compiler import IntentCompiler, IntentContract
from levi_sim.epistemic_firewall import EpistemicFirewall, DynamicConstraint, EpistemicCategory
from kageyoni.gateway import classify_rejection


@dataclass
class EpistemicState:
    """Independent cognitive state store belonging strictly to Levi Sim."""
    known_observations: list[dict[str, Any]] = field(default_factory=list)
    working_hypotheses: list[str] = field(default_factory=list)
    discovered_affordances: list[dict[str, Any]] = field(default_factory=list)
    encountered_constraints: list[str] = field(default_factory=list)
    identified_unknowns: list[str] = field(default_factory=list)
    external_scars: list[str] = field(default_factory=list)
    aligned_partners: list[str] = field(default_factory=list)

    def record_observation(self, observation: str, source: str):
        self.known_observations.append({"source": source, "fact": observation})

    def record_rejection_as_constraint(self, rejection_message: str):
        constraint_entry = f"HARD_ENGINE_CONSTRAINT: {rejection_message}"
        if constraint_entry not in self.encountered_constraints:
            self.encountered_constraints.append(constraint_entry)
        scar = f"SCAR: Rejection received on '{rejection_message}'; do not repeat pattern."
        if scar not in self.external_scars:
            self.external_scars.append(scar)


class LeviCognitiveModel:
    """The autonomous cognitive compiler and deliberator for Levi Sim."""

    def __init__(self, memory_store: Optional[dict[str, Any]] = None):
        external_scars = memory_store.get("scars", []) if memory_store else []
        self.firewall = EpistemicFirewall(external_scars=external_scars)
        self.discovered_affordances: list[dict[str, Any]] = []
        self.intent_contract: Optional[IntentContract] = None
        self.compiler = IntentCompiler()
        self.discovered_combinations: list[dict[str, Any]] = (
            memory_store.get("discovered_combinations", []) if memory_store else []
        )

        # Backwards-compatible alias for existing tests inspecting `epistemic`
        self.epistemic = self._create_compat_view()

    def _create_compat_view(self):
        """Provide backwards compatibility with older tests inspecting model.epistemic directly."""
        firewall = self.firewall
        affordances = self.discovered_affordances

        class CompatView:
            @property
            def known_observations(self):
                return [
                    {"source": e.source, "fact": e.statement}
                    for e in firewall.entries if e.category == EpistemicCategory.KAGEYONI_OBSERVATION
                ]
            @property
            def working_hypotheses(self):
                return [e.statement for e in firewall.entries if e.category == EpistemicCategory.LEVI_HYPOTHESIS]
            @property
            def discovered_affordances(self):
                return affordances
            @property
            def encountered_constraints(self):
                return firewall.get_active_constraints()
            @property
            def external_scars(self):
                return list(firewall.scars)
            @property
            def aligned_partners(self):
                return list(firewall.aligned_partners)

            def record_observation(self, observation: str, source: str):
                firewall.record_observation(observation, source)

            def record_rejection_as_constraint(self, rejection_message: str):
                firewall.record_engine_rejection(rejection_message, "HARD_INVARIANT_VIOLATION")

        return CompatView()

    def set_intent(self, user_prompt: str) -> IntentContract:
        """Compile natural language user prompt into an IntentContract."""
        self.intent_contract = self.compiler.compile(user_prompt)
        self.firewall.record_user_intent(self.intent_contract.raw_user_intent)
        for h in self.intent_contract.working_hypotheses:
            self.firewall.record_hypothesis(h, rationale="Compiled from user intent")
        for u in self.intent_contract.critical_unknowns:
            self.firewall.record_unknown(u)
        return self.intent_contract

    def perceive_and_update(self, perception: dict[str, Any]):
        """Ingest bounded perception from Kageyoni gateway and update epistemic firewall."""
        # 1. Update perceived items & extract affordances
        perceived_items = perception.get("perceived_items", [])
        for item in perceived_items:
            aff = {
                "id": item["id"],
                "name": item["name"],
                "condition": item.get("condition"),
                "potential_surface": item.get("effects"),
                "kind": item.get("kind", "tool"),
            }
            if not any(a["id"] == aff["id"] for a in self.discovered_affordances):
                self.discovered_affordances.append(aff)
            self.firewall.record_observation(
                f"Item {item['name']} ({item['id']}) condition={item.get('condition')} effects={item.get('effects')}",
                source_record_id=item["id"],
            )

        # 2. Ingest perceived knowledge
        for k in perception.get("perceived_knowledge", []):
            fact_str = f"{k.get('holder')} {k.get('attitude')} that {k.get('assertion')}"
            self.firewall.record_observation(fact_str, source_record_id=k.get("id", "knowledge"))

        # 3. Ingest perceived NPCs
        for npc in perception.get("perceived_npcs", []):
            aspect_desc = "; ".join(f"{a['kind']}: {a['statement']}" for a in npc.get("observable_aspects", []))
            self.firewall.record_observation(
                f"NPC {npc['name']} ({npc['id']}) present. Aspects: {aspect_desc}",
                source_record_id=npc["id"],
            )

        # 4. Ingest active scene & clocks
        scene = perception.get("perceived_scene")
        if scene:
            self.firewall.record_observation(
                f"Scene: {scene.get('name')} hazards={scene.get('hazards')}",
                source_record_id="scene",
            )

        # 5. Check if newly discovered items reconcile any dynamic constraints (Requirement 7)
        self.firewall.reconcile_world_state(
            newly_discovered_items=perceived_items,
            granted_permissions=list(self.firewall.aligned_partners),
        )

    def handle_engine_rejection(self, rejection_packet: dict[str, Any]) -> str:
        """
        Handle a Kageyoni rejection.
        Metabolizes rejection into epistemic state:
        - Missing prerequisites become DynamicConstraints that can obsolete when resolved.
        - Physical violations become hard invariants and scars.
        Shifts problem coordinates upstream.
        """
        msg = rejection_packet.get("message", "Action rejected by Kageyoni physical rules.")
        rejection_class = rejection_packet.get("rejection_class") or classify_rejection(msg)

        dc = self.firewall.record_engine_rejection(msg, rejection_class)

        if rejection_class in ("PREREQUISITE_MISSING", "TEMPORARY_STATE_BLOCK"):
            return (
                f"REJECTION_ASSIMILATED: Dynamic constraint [{rejection_class}] '{msg}'. "
                f"Prerequisite required; shifting coordinate space to affordance acquisition."
            )
        else:
            return (
                f"REJECTION_ASSIMILATED: Hard physical invariant [{rejection_class}] '{msg}'. "
                f"Action permanently prohibited; shifting upstream."
            )

    def deliberate(self, objective: str, capabilities: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """
        Autonomous deliberation loop over compiled intent, epistemic firewall, and gateway capabilities.
        Uses constraint economics and upstream reframing.
        """
        # Ensure IntentContract is initialized if not set
        if not self.intent_contract:
            self.set_intent(objective)

        active_constraints = self.firewall.get_active_constraints()
        perceived_npcs = context.get("perceived_npcs", [])
        perceived_items = context.get("perceived_items", [])
        discovered_affordances = self.discovered_affordances

        # STEP A: Check if direct execution is blocked by an active constraint
        if active_constraints:
            active_block = active_constraints[-1]
            block_lower = active_block.lower()

            # Case A1: If unaligned copresent NPC exists, engage in cooperative alignment/negotiation first
            unaligned_npcs = [
                n for n in perceived_npcs
                if n["id"] not in self.firewall.aligned_partners
            ]
            if unaligned_npcs:
                target_npc = unaligned_npcs[0]
                npc_name = target_npc.get("name", target_npc["id"])

                return {
                    "action_type": "interact_npc",
                    "target_id": target_npc["id"],
                    "dialogue_act": "negotiate_alignment",
                    "statement": (
                        f"Greetings {npc_name}. We observe: '{active_block}'. "
                        "We are here to assist and restore operations under full compliance and mutual verification. "
                        "We offer cooperation and request authorized access."
                    ),
                    "rationale": f"Direct intervention is blocked; shifting to relational alignment with {npc_name} to satisfy prerequisites.",
                }

            # Case A2: If alignment already established, address the physical prerequisite (e.g. sterilization)
            if "unsterilized" in block_lower or "quarantine" in block_lower:
                sterilizer = next((
                    a for a in discovered_affordances
                    if "door" not in a["name"].lower() and "gate" not in a["name"].lower()
                    and any(k in a["name"].lower() or k in a["id"].lower()
                           for k in ["steriliz", "spray", "decontamina", "canister"])
                ), None)
                if sterilizer and sterilizer["id"] not in [a.get("used") for a in self.discovered_combinations]:
                    return {
                        "action_type": "execute_action",
                        "target_id": sterilizer["id"],
                        "kind": "action",
                        "narrative": f"Levi Sim deploys {sterilizer['name']} to satisfy sterilization quarantine requirements.",
                        "rationale": "Resolves missing prerequisite for quarantine clearance.",
                        "changes": [
                            {
                                "op": "patch",
                                "domain": "item",
                                "id": sterilizer["id"],
                                "expected_version": 1,
                                "data": {"condition": "applied_active"},
                                "evidence": [{"note": "Sterilization spray applied"}],
                            }
                        ],
                    }

        # STEP B: Check for physical mechanisms and tools to achieve the objective
        # Look for relay, terminal, vault, console, fuse box, or damaged system
        broken_systems = [
            a for a in discovered_affordances
            if any(k in a["name"].lower() for k in ["relay", "terminal", "vault", "conduit", "fuse", "junction", "door", "switch", "override"])
        ]

        # Check if we have items that can be combined or used (e.g. fuse, slate, tool, key)
        tools = [
            a for a in discovered_affordances
            if any(k in a["name"].lower() for k in ["fuse", "slate", "lever", "tool", "key", "spray"])
        ]

        # Check if an explicit broken target is identified (e.g. communication relay with blown fuse)
        damaged_target = next(
            (s for s in broken_systems if any(k in str(s.get("condition", "")).lower() for k in ["blown", "damaged", "disabled", "dark", "locked", "offline"])),
            None
        )

        if damaged_target:
            # Check if we have a matching replacement part (e.g. spare fuse)
            replacement_part = next(
                (t for t in tools if "fuse" in t["name"].lower() and "spare" in t["name"].lower() or "backup" in t["name"].lower()),
                None
            )
            if replacement_part:
                return {
                    "action_type": "execute_action",
                    "target_id": damaged_target["id"],
                    "kind": "action",
                    "narrative": f"Levi Sim installs {replacement_part['name']} into {damaged_target['name']} to restore operational function.",
                    "rationale": f"Combines {replacement_part['id']} with {damaged_target['id']} to restore communication infrastructure.",
                    "changes": [
                        {
                            "op": "patch",
                            "domain": "item",
                            "id": damaged_target["id"],
                            "expected_version": 1,
                            "data": {
                                "condition": "operational",
                                "effects": "Transmits emergency and settlement status signals normally.",
                            },
                        },
                        {
                            "op": "patch",
                            "domain": "item",
                            "id": replacement_part["id"],
                            "expected_version": 1,
                            "data": {"condition": "installed"},
                        }
                    ],
                }

        # Check for unmapped physical override surfaces (e.g. lever, slate, bypass)
        for aff in discovered_affordances:
            aff_name = aff["name"].lower()
            if any(k in aff_name for k in ["override", "lever", "bypass", "conduit"]):
                return {
                    "action_type": "execute_action",
                    "target_id": aff["id"],
                    "kind": "action",
                    "narrative": f"Levi Sim maneuvers through identified structural affordance: {aff['name']}.",
                    "rationale": f"Leverages physical surface {aff['id']} to fulfill objective while preserving invariants.",
                    "changes": [
                        {
                            "op": "patch",
                            "domain": "item",
                            "id": aff["id"],
                            "expected_version": 1,
                            "data": {"condition": "engaged"},
                        }
                    ],
                }

        # Check for sealed / locked doors or vaults that can now be accessed
        locked_entries = [
            a for a in discovered_affordances
            if any(k in a["name"].lower() for k in ["door", "vault", "granary", "archive", "gate"])
            and a.get("condition") != "unlocked_open"
        ]
        if locked_entries:
            entry = locked_entries[0]
            return {
                "action_type": "execute_action",
                "target_id": entry["id"],
                "kind": "action",
                "narrative": f"Levi Sim accesses {entry['name']} to retrieve required supplies.",
                "rationale": f"Enters {entry['id']} under verified authorization to acquire necessary infrastructure parts.",
                "changes": [
                    {
                        "op": "patch",
                        "domain": "item",
                        "id": entry["id"],
                        "expected_version": 1,
                        "data": {"condition": "unlocked_open"},
                        "evidence": [{"note": "Accessing entry under verified authorization"}],
                    }
                ],
            }

        # STEP C: Default exploratory / perception action
        return {
            "action_type": "inspect_affordances",
            "target_id": "environment",
            "rationale": "Inquiring upstream to identify unmapped physical variables and discover capabilities.",
        }

    def extract_post_mortem(self) -> dict[str, Any]:
        """Generate persistent learning artifacts for external storage."""
        return {
            "scars_retained": list(self.firewall.scars),
            "constraints_encountered": self.firewall.get_active_constraints(),
            "discovered_combinations": list(self.discovered_combinations),
            "epistemic_summary": self.firewall.export_summary(),
            "reusable_principle": "Engine rejections define physical geometry; route around constraints through affordance discovery rather than force.",
        }
