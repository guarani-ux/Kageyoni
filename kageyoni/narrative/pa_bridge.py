"""Tactical-to-Relational Bridge & Morning Camp Private Action Scheduler.

Implements:
- Contact Ledger Ingestion: records high-friction tactical combat events
  (heavy damage, critical hits, lethal blows, friendly fire, near-death rescues).
- Morning Camp Private Action (PA) Queue:
  Translates tactical contact events into directional conversational agendas for
  the morning Camp phase.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CombatContactType(str, Enum):
    HEAVY_DAMAGE = "heavy_damage"
    CRITICAL_HIT = "critical_hit"
    LETHAL_BLOW = "lethal_blow"
    FRIENDLY_FIRE = "friendly_fire"
    SAVING_INTERVENTION = "saving_intervention"


@dataclass
class ContactEvent:
    """Record of an impactful relational combat interaction on the field."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: CombatContactType = CombatContactType.HEAVY_DAMAGE
    source_id: str = "actor_1"
    target_id: str = "actor_2"
    severity: float = 50.0
    turn: int = 1
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "severity": self.severity,
            "turn": self.turn,
            "details": self.details,
        }


@dataclass
class PrivateAction:
    """Relational Camp conversation item queued for the morning phase."""
    action_id: str
    initiator_id: str
    target_id: str
    agenda: str
    context_trigger: str
    priority: int = 1
    dialogue_seed_prompt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "initiator_id": self.initiator_id,
            "target_id": self.target_id,
            "agenda": self.agenda,
            "context_trigger": self.context_trigger,
            "priority": self.priority,
            "dialogue_seed_prompt": self.dialogue_seed_prompt,
        }


class TacticalRelationalBridge:
    """Bridges battlefield kinetic contact to campfire relational agendas."""

    def __init__(self) -> None:
        self.contact_ledger: List[ContactEvent] = []
        self.private_action_queue: List[PrivateAction] = []

    def record_contact(
        self,
        event_type: CombatContactType | str,
        source_id: str,
        target_id: str,
        severity: float = 50.0,
        turn: int = 1,
        details: str = "",
    ) -> ContactEvent:
        """Record an impactful combat event into the contact ledger."""
        if isinstance(event_type, str):
            clean_type = CombatContactType(event_type.lower())
        else:
            clean_type = event_type

        event = ContactEvent(
            event_type=clean_type,
            source_id=source_id,
            target_id=target_id,
            severity=severity,
            turn=turn,
            details=details,
        )
        self.contact_ledger.append(event)
        return event

    def generate_morning_actions(self) -> List[PrivateAction]:
        """Translate accumulated contact ledger events into queued Morning Camp PAs."""
        new_actions: List[PrivateAction] = []

        for event in self.contact_ledger:
            action_id = f"pa_{event.event_id}"

            if event.event_type == CombatContactType.FRIENDLY_FIRE:
                agenda = f"Confront {event.source_id} over dangerous battlefield reckless crossfire."
                priority = 3
                prompt = f"Austere Camp confrontation: {event.target_id} demands accounting from {event.source_id} after suffering {event.severity:.1f} recoil friendly fire."
            elif event.event_type == CombatContactType.SAVING_INTERVENTION:
                agenda = f"Acknowledge {event.source_id}'s decisive defense during crisis."
                priority = 2
                prompt = f"Camp reconciliation: {event.target_id} speaks plainly with {event.source_id} about an intervention that averted death."
            elif event.event_type == CombatContactType.LETHAL_BLOW:
                agenda = f"Debrief fatal dispatch executed by {event.source_id}."
                priority = 2
                prompt = f"Camp vigil: {event.target_id} observes {event.source_id} cleaning weapons after a lethal blow."
            elif event.event_type == CombatContactType.CRITICAL_HIT:
                agenda = f"Review high-impact strike delivered against tactical threat."
                priority = 1
                prompt = f"Tactical debrief: discussing martial momentum following a devastating critical strike."
            else:
                agenda = f"Check physical wounds and fatigue following severe combat trauma."
                priority = 1
                prompt = f"Camp field-dressing: {event.target_id} tending wounds with {event.source_id}."

            pa = PrivateAction(
                action_id=action_id,
                initiator_id=event.target_id,
                target_id=event.source_id,
                agenda=agenda,
                context_trigger=event.event_type.value,
                priority=priority,
                dialogue_seed_prompt=prompt,
            )
            new_actions.append(pa)

        # Sort by priority descending
        new_actions.sort(key=lambda x: x.priority, reverse=True)
        self.private_action_queue.extend(new_actions)
        self.contact_ledger.clear()
        return new_actions

    def dequeue_next_action(self) -> Optional[PrivateAction]:
        """Pop the highest-priority pending Camp Private Action."""
        if self.private_action_queue:
            return self.private_action_queue.pop(0)
        return None

    def clear_queue(self) -> None:
        """Clear pending actions."""
        self.private_action_queue.clear()
        self.contact_ledger.clear()
