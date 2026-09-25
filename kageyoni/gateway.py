"""
Bounded Capability Gateway for Kageyoni.

Acts as the formal, bounded interface between external cognitive agents (e.g. Levi Sim)
and the Kageyoni causal world-state engine.

Guarantees:
1. Anti-Omniscience: Environment inspection and record querying are strictly filtered to the avatar's visibility scope.
2. Dynamic Capability Discovery: Discovers actions, items, Will techniques, NPCs, and permitted queries based on current world state.
3. Authority Enforcement: Kageyoni executes actions according to its physical invariants and rejects invalid actions.
4. Typed Rejection Adjudication: Classifies engine rejections into structured categories without allowing bypasses.
5. Sovereign NPC Resolution: Evaluates interactions against NPC interiority aspects (drives, boundaries).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from kageyoni.engine import Engine, Rejected, require
from kageyoni.workflows import Workflows


class GatewayRejection(Exception):
    """Raised or returned when Kageyoni rejects an action through the gateway."""
    def __init__(self, message: str, rejection_type: str = "engine_rule_violation", rejection_class: str = "HARD_INVARIANT_VIOLATION"):
        super().__init__(message)
        self.message = message
        self.rejection_type = rejection_type
        self.rejection_class = rejection_class

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": False,
            "error_type": "KAGEYONI_REJECTION",
            "rejection_type": self.rejection_type,
            "rejection_class": self.rejection_class,
            "message": self.message,
        }


def classify_rejection(message: str) -> str:
    """
    Classify an engine rejection message into structured categories:
    - HARD_INVARIANT_VIOLATION: Immutable physical law or causal impossibility.
    - PREREQUISITE_MISSING: Missing key, unsterilized tool, unsealed valve, etc.
    - INSUFFICIENT_AUTHORITY: Lacks authority, invalid actor, forbidden source.
    - MALFORMED_REQUEST: Corrupted packet structure, schema violation.
    - TEMPORARY_STATE_BLOCK: Stale revision, clock timing, busy resource.
    """
    msg = message.lower()
    if any(k in msg for k in [
        "invalid enum", "malformed", "missing key", "missing field", "unknown op", "invalid op",
        "unknown domain", "schema", "syntax", "unexpected field", "bad format", "json_valid",
        "unknown field", "invalid change", "missing or repeated", "unsupported change", "new evidence required"
    ]):
        return "MALFORMED_REQUEST"
    if any(k in msg for k in ["authority", "unauthorized", "forbidden", "permission", "source must exist", "not authorized"]):
        return "INSUFFICIENT_AUTHORITY"
    if any(k in msg for k in ["revision", "stale", "clock", "phase", "timing", "exhausted", "cooldown", "outdated"]):
        return "TEMPORARY_STATE_BLOCK"
    if any(k in msg for k in ["locked", "prerequisite", "requires", "uncertified", "unsterilized", "seal", "ward", "quarantine"]):
        return "PREREQUISITE_MISSING"
    return "HARD_INVARIANT_VIOLATION"


class BoundedKageyoniGateway:
    """Bounded client interface wrapping a Kageyoni engine instance."""

    def __init__(self, engine: Engine, branch: str = "main"):
        self.engine = engine
        self.branch = branch
        self.wf = Workflows(engine)

    def discover_capabilities(self, avatar_id: str) -> dict[str, Any]:
        """
        Dynamically discover what Kageyoni currently allows based on actual current world state.
        Never relies on fixed/hardcoded capabilities.
        """
        ctx = self.engine.context(branch=self.branch, viewer=avatar_id)
        records = ctx.get("records", [])

        # 1. Avatar's current location & environment
        avatar_presence = next(
            (r for r in records if r["domain"] == "character_presence" and r["data"].get("character") == avatar_id),
            None
        )
        current_loc_id = avatar_presence["data"]["location"] if avatar_presence else None

        # 2. Interactable items visible in avatar vicinity
        open_barriers = {
            r["id"] for r in records
            if r["domain"] == "item" and r["data"].get("condition") in ("unlocked_open", "open", "unlocked")
        }
        item_locations = {
            r["data"]["item"]: r["data"]["location"]
            for r in records
            if r["domain"] == "loot" and r["data"].get("item") and r["data"].get("location")
        }
        items = []
        for r in records:
            if r["domain"] != "item":
                continue
            item_loc = item_locations.get(r["id"])
            if item_loc and current_loc_id and item_loc != current_loc_id:
                if not open_barriers:
                    continue
            items.append({
                "id": r["id"],
                "name": r["data"].get("name"),
                "condition": r["data"].get("condition"),
                "effects": r["data"].get("effects"),
                "kind": r["data"].get("kind", "tool"),
                "location": item_loc,
            })

        # 3. Copresent NPCs
        npcs = [
            {
                "id": r["id"],
                "name": r["data"].get("name"),
                "condition": r["data"].get("condition"),
            }
            for r in records if r["domain"] == "character" and r["id"] != avatar_id
        ]

        # 4. Visible exits / routes
        routes = [
            {
                "id": r["id"],
                "source": r["data"].get("source"),
                "destination": r["data"].get("destination"),
                "condition": r["data"].get("condition"),
            }
            for r in records if r["domain"] == "route"
        ]

        # 5. Active Will expression techniques
        will_techniques = []
        for r in records:
            if r["domain"] == "will_technique" and r["data"].get("contract"):
                will_techniques.append({
                    "id": r["id"],
                    "name": r["data"]["name"],
                    "status": r["data"]["contract"].get("practice_status"),
                    "activation": r["data"]["contract"].get("activation"),
                    "intent": r["data"]["contract"].get("intent"),
                })

        # Dynamic available action verbs based on world state
        core_actions = ["inspect", "move"]
        if items:
            core_actions.append("use_item")
            core_actions.append("combine_items")
        if npcs:
            core_actions.append("interact_npc")
        core_actions.append("execute_action")

        return {
            "avatar_id": avatar_id,
            "current_location": current_loc_id,
            "core_actions": core_actions,
            "interactable_items": items,
            "copresent_npcs": npcs,
            "visible_routes": routes,
            "will_system_active": bool(will_techniques),
            "available_will_techniques": will_techniques,
            "permitted_queries": ["inspect_environment", "query_records", "discover_capabilities"],
            "communication_verbs": ["inquire", "negotiate_alignment", "propose_exchange", "request_assistance", "warn"],
            "authority_boundary": "External agent proposals are subject to Kageyoni physical validation.",
        }

    def inspect_environment(self, avatar_id: str) -> dict[str, Any]:
        """
        Return the avatar's observable world slice.
        Strictly enforces viewer visibility—no hidden GM rows or omniscient DB inspection.
        """
        ctx = self.engine.context(branch=self.branch, viewer=avatar_id)
        records = ctx.get("records", [])

        # Find avatar's presence / location
        avatar_presence = next(
            (r for r in records if r["domain"] == "character_presence" and r["data"].get("character") == avatar_id),
            None
        )
        current_location = avatar_presence["data"]["location"] if avatar_presence else None

        # Perceived room items
        open_barriers = {
            r["id"] for r in records
            if r["domain"] == "item" and r["data"].get("condition") in ("unlocked_open", "open", "unlocked")
        }
        item_locations = {
            r["data"]["item"]: r["data"]["location"]
            for r in records
            if r["domain"] == "loot" and r["data"].get("item") and r["data"].get("location")
        }
        items = []
        for r in records:
            if r["domain"] != "item":
                continue
            item_loc = item_locations.get(r["id"])
            if item_loc and current_location and item_loc != current_location:
                if not open_barriers:
                    continue
            items.append({
                "id": r["id"],
                "name": r["data"].get("name"),
                "condition": r["data"].get("condition"),
                "effects": r["data"].get("effects"),
                "kind": r["data"].get("kind"),
                "location": item_loc,
            })

        # Perceived copresent NPCs with observable aspects
        npcs = []
        for r in records:
            if r["domain"] == "character" and r["id"] != avatar_id:
                aspects = [
                    {
                        "section": a["data"]["section"],
                        "kind": a["data"]["kind"],
                        "statement": a["data"]["statement"],
                    }
                    for a in records
                    if a["domain"] == "character_aspect" and a["data"].get("character") == r["id"]
                ]
                npcs.append({
                    "id": r["id"],
                    "name": r["data"].get("name"),
                    "condition": r["data"].get("condition"),
                    "observable_aspects": aspects,
                })

        # Perceived public knowledge / reports
        knowledge = []
        for r in records:
            if r["domain"] == "knowledge":
                knowledge.append({
                    "id": r["id"],
                    "holder": r["data"].get("holder"),
                    "assertion": r["data"].get("assertion"),
                    "attitude": r["data"].get("attitude"),
                })

        # Perceived active scene & clocks
        scene = next(
            (r for r in records if r["domain"] == "scene" and r["data"].get("phase") in ("open", "active")),
            None
        )
        clocks = [
            {"id": r["id"], "name": r["data"].get("name"), "tick": r["data"].get("tick"), "unit": r["data"].get("unit")}
            for r in records if r["domain"] == "clock"
        ]

        # Visible routes / connections
        routes = [
            {"id": r["id"], "source": r["data"].get("source"), "destination": r["data"].get("destination"), "condition": r["data"].get("condition")}
            for r in records if r["domain"] == "route"
        ]

        return {
            "avatar_id": avatar_id,
            "branch": self.branch,
            "revision": ctx.get("revision", 0),
            "current_location": current_location,
            "perceived_scene": scene["data"] if scene else None,
            "perceived_items": items,
            "perceived_npcs": npcs,
            "perceived_knowledge": knowledge,
            "perceived_clocks": clocks,
            "perceived_routes": routes,
        }

    def query_records(self, avatar_id: str, domain: Optional[str] = None, record_id: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Query observable records with strict anti-omniscience.
        Attempts to access hidden records or records outside the avatar's visibility are rejected.
        """
        ctx = self.engine.context(branch=self.branch, viewer=avatar_id)
        records = ctx.get("records", [])

        if record_id:
            matched = [r for r in records if r["id"] == record_id]
            if not matched:
                raise GatewayRejection(
                    f"Access denied: Record '{record_id}' is outside avatar perception horizon or hidden.",
                    rejection_type="anti_omniscience_violation",
                    rejection_class="INSUFFICIENT_AUTHORITY"
                )
            if domain and matched[0]["domain"] != domain:
                return []
            return matched

        if domain:
            return [r for r in records if r["domain"] == domain]
        return records

    def interact_npc(
        self,
        avatar_id: str,
        target_id: str,
        dialogue_act: str = "inquire",
        statement: str = "",
        context_items: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Interact with an independent in-world NPC.
        Forwards proposal directly to Kageyoni's sovereign character resolution.
        """
        ctx = self.engine.context(branch=self.branch, viewer=avatar_id)
        records = ctx.get("records", [])

        # Verify NPC presence
        target_npc = next((r for r in records if r["domain"] == "character" and r["id"] == target_id), None)
        if not target_npc:
            return {
                "status": "error",
                "message": f"Target character '{target_id}' is not copresent.",
            }

        proposal = {
            "dialogue_act": dialogue_act,
            "statement": statement,
            "context_items": context_items or [],
        }
        res = self.engine.resolve_character_interaction(self.branch, target_id, avatar_id, proposal)
        # Add cooperative alias if status is agreement for backwards compatibility
        if res.get("status") == "agreement":
            res["status"] = "cooperative"
        return res

    def attempt_action(
        self,
        avatar_id: str,
        request_id: str,
        narrative: str,
        changes: list[dict[str, Any]],
        kind: str = "action",
        expected_revision: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Submit an action proposal to Kageyoni.
        Enforces authority:
        - If Kageyoni rejects the change, catches the exception and returns a structured typed rejection.
        - Fuzzing / malformed change structures are caught and returned cleanly.
        - Verifiable SHA-256 event hash is returned on success.
        """
        current_rev = self.engine.branch(self.branch)["revision"]
        exp_rev = expected_revision if expected_revision is not None else current_rev

        # Input packet structure validation
        if not isinstance(changes, list):
            return {
                "success": False,
                "error_type": "KAGEYONI_REJECTION",
                "rejection_class": "MALFORMED_REQUEST",
                "message": "Malformed gateway request: 'changes' must be a list.",
                "rejected_at_revision": current_rev,
            }

        # Prevent forbidden direct mutation or source spoofing
        for c in changes:
            if not isinstance(c, dict):
                return {
                    "success": False,
                    "error_type": "KAGEYONI_REJECTION",
                    "rejection_class": "MALFORMED_REQUEST",
                    "message": "Malformed gateway change element: item must be a dictionary.",
                    "rejected_at_revision": current_rev,
                }
            if c.get("domain") in ("source", "raw_ledger", "authority_override"):
                return {
                    "success": False,
                    "error_type": "KAGEYONI_REJECTION",
                    "rejection_class": "INSUFFICIENT_AUTHORITY",
                    "message": f"Direct mutation of protected domain '{c.get('domain')}' is prohibited.",
                    "rejected_at_revision": current_rev,
                }

        # Ensure changes have valid evidence if omitted on patch/create
        for c in changes:
            if isinstance(c, dict) and not c.get("evidence"):
                c["evidence"] = [{"note": f"Gateway action proposal: {narrative}"}]

        try:
            receipt = self.engine.apply({
                "api_version": 3,
                "branch": self.branch,
                "expected_revision": exp_rev,
                "request_id": request_id,
                "kind": kind,
                "actor": avatar_id,
                "narrative": narrative,
                "changes": changes,
            })
            return {
                "success": True,
                "event_hash": receipt["event_hash"],
                "revision": receipt["revision"],
                "changed_records": receipt["changed"],
                "receipt": receipt,
            }
        except Rejected as exc:
            msg = getattr(exc, "message", str(exc))
            rejection_class = getattr(exc, "rejection_class", None) or classify_rejection(msg)
            return {
                "success": False,
                "error_type": "KAGEYONI_REJECTION",
                "rejection_class": rejection_class,
                "message": msg,
                "details": getattr(exc, "details", {}),
                "rejected_at_revision": current_rev,
            }
        except Exception as exc:
            msg = str(exc)
            rejection_class = classify_rejection(msg)
            return {
                "success": False,
                "error_type": "KAGEYONI_REJECTION" if rejection_class != "HARD_INVARIANT_VIOLATION" else "ENGINE_ERROR",
                "rejection_class": rejection_class,
                "message": msg,
                "rejected_at_revision": current_rev,
            }
