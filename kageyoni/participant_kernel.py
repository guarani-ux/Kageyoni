"""Persistent Participant Kernel: integrating Kageyoni's authoritative surfaces.

Connects:
- characters.py and intelligence.nodes (Persistent Identity)
- personality.py and writing.py (Participant-Specific Context / Briefs)
- intelligence.learning and intelligence.methods (Durable Experience, Methods, Outcomes)
- persistence.contributions and intelligence.expression (Bounded Execution)
- engine.py (Transactional ACID SQLite Persistence)
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence
from uuid import uuid4

from . import characters
from .engine import Engine, require, digest, encoded, Rejected
from .intelligence.nodes import Nodes
from .intelligence.learning import Learning
from .intelligence.methods import Methods
from .persistence.contributions import Contributions
from .persistence.unit_of_work import UnitOfWork
from .personality import brief as personality_brief
from .processes.outcomes import Disposition, Objective, Result


class PersistentParticipant:
    """A durable, situated participant served by replaceable model cognition."""

    def __init__(self, engine: Engine, character_id: str, branch: str = "main"):
        self.engine = engine
        self.db = engine.db
        self.character_id = character_id
        self.branch = branch

        # Ensure node binding exists
        self.nodes = Nodes(engine)
        self.learning = Learning(engine)
        self.methods = Methods(engine)
        self.contributions = Contributions(engine)

        node_data = self.nodes.read(branch, character_id, viewer=None)
        self.node_id = node_data["node_id"]
        self.workspace_id = node_data["workspace_id"]

    @classmethod
    def open_or_create(
        cls,
        engine: Engine,
        character_id: str,
        label: str,
        branch: str = "main",
        objective: str = "Autonomous bounded investigation",
        existence: str = "established",
        visibility: str = "public",
        actor: str = "owner",
        source_note: str = "Persistent participant genesis",
    ) -> PersistentParticipant:
        """Loads an existing participant or creates and binds one if absent."""
        current_rev = engine.branch(branch)["revision"]
        # Check if character already exists in this branch
        try:
            characters.read(engine, branch, character_id, viewer=None)
            exists = True
        except Rejected:
            exists = False

        if not exists:
            # Create character identity in Engine.db
            req_id = f"create-character:{character_id}:{uuid4().hex[:8]}"
            characters.create(
                engine,
                branch=branch,
                request_id=req_id,
                expected_revision=current_rev,
                actor=actor,
                narrative=f"Introduce persistent participant {label}",
                character_id=character_id,
                label=label,
                existence=existence,
                evidence=[{"note": source_note}],
                visibility=visibility,
            )

        # Check if node binding exists
        current_rev = engine.branch(branch)["revision"]
        node_row = engine.db.execute(
            "SELECT node_id FROM node_bindings WHERE branch=? AND character_id=?",
            (branch, character_id),
        ).fetchone()

        if not node_row:
            bind_req = f"bind-node:{character_id}:{uuid4().hex[:8]}"
            Nodes(engine).bind(
                branch=branch,
                character_id=character_id,
                request_id=bind_req,
                expected_revision=current_rev,
                source={"note": source_note},
            )

        return cls(engine, character_id, branch=branch)

    def prepare_turn(
        self,
        domain: str = "options",
        task_domain: Optional[str] = None,
        interlocutors: Optional[List[str]] = None,
        scene: Optional[str] = None,
        viewer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prepares turn context without invoking model cognition."""
        personality_scope = domain if domain in {"dialogue", "combat", "relationship", "growth", "options", "decision", "training", "will"} else "options"
        b = personality_brief(
            self.engine,
            self.branch,
            self.character_id,
            domain=personality_scope,
            interlocutors=interlocutors,
            scene=scene,
            viewer=viewer,
        )

        query_domain = task_domain or domain
        # Fetch qualified lessons and methods
        current_methods = self.methods.eligible(
            self.branch,
            self.character_id,
            query_domain,
            viewer=viewer,
            workspace_id=self.workspace_id,
        )
        recent_outcomes = self.learning.list_outcomes(self.branch, self.character_id, viewer=viewer)
        lessons = self.learning.list(self.branch, self.character_id, viewer=viewer)

        turn_packet = {
            "participant_id": self.character_id,
            "node_id": self.node_id,
            "branch": self.branch,
            "workspace_id": self.workspace_id,
            "world_revision": self.engine.branch(self.branch)["revision"],
            "brief": b,
            "eligible_methods": [
                {
                    "method_id": m["method_id"],
                    "name": m["definition"]["name"],
                    "revision": m["revision"],
                    "qualification": m["qualification"],
                }
                for m in current_methods
            ],
            "retained_experience": {
                "outcomes_count": len(recent_outcomes),
                "recent_outcomes": recent_outcomes[:5],
                "lessons": [
                    {
                        "lesson_id": l["lesson_id"],
                        "name": l["definition"]["name"],
                        "status": l.get("review_status", "proposed"),
                        "rationale": l["definition"]["rationale"],
                    }
                    for l in lessons
                ],
            },
            "operating_instructions": (
                "You are the Kageyoni participant identified by the runtime's current turn binding.\n"
                "Before responding or acting, obtain your current authorized context. Use relevant retained experience, "
                "but treat it as scoped evidence or guidance, not unquestionable truth.\n"
                "Read and investigate when needed. Communicate directly. Propose actions through the provided action interface. "
                "Do not perform effects outside its authorization.\n"
                "Distinguish what you observed, inferred, attempted, and verified. Report unresolved outcomes honestly.\n"
                "After an encounter, preserve useful observations and outstanding commitments. Propose a lesson only when the evidence supports one; "
                "do not certify your own general competence.\n"
                "When the supplied context is insufficient, request the missing permitted information. When prior experience conflicts with current evidence, surface the conflict.\n"
                "Your model context may end. Your continuity is recovered through Kageyoni's persisted identity and state, not claimed from conversational familiarity."
            ),
        }
        turn_packet["turn_digest"] = digest(turn_packet)
        return turn_packet

    def execute_task(
        self,
        task: Dict[str, Any],
        request_id: Optional[str] = None,
        viewer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes a bounded operation task through Contributions & Expression."""
        req = request_id or f"task-exec:{self.character_id}:{uuid4().hex[:8]}"
        receipt = self.contributions.run(
            self.branch,
            self.character_id,
            request_id=req,
            task=task,
            viewer=viewer,
            workspace_id=self.workspace_id,
        )
        contribution = self.contributions.read(self.branch, receipt["contribution_id"], viewer=viewer)
        return contribution

    def record_observation(
        self,
        contribution_id: str,
        status: str,
        rationale: str,
        measurements: Sequence[Dict[str, Any]],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Records an attributed empirical outcome into Learning."""
        req = request_id or f"outcome-rec:{self.character_id}:{uuid4().hex[:8]}"
        obs = {
            "status": status,
            "rationale": rationale,
            "measurements": list(measurements),
        }
        current_rev = self.engine.branch(self.branch)["revision"]
        outcome = self.learning.record_outcome(
            self.branch,
            contribution_id=contribution_id,
            request_id=req,
            expected_world_revision=current_rev,
            observation=obs,
        )
        return outcome

    def propose_lesson(
        self,
        name: str,
        rationale: str,
        method_id: str,
        method_revision: int,
        task_domain: str,
        operation_params: Dict[str, Any],
        context_conditions: Sequence[Dict[str, Any]],
        outcome_ids: Sequence[str],
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Proposes a candidate lesson from observed outcomes."""
        req = request_id or f"propose-lesson:{self.character_id}:{uuid4().hex[:8]}"
        lesson = {
            "name": name,
            "rationale": rationale,
            "method_id": method_id,
            "method_revision": method_revision,
            "task_domain": task_domain,
            "context_conditions": list(context_conditions),
            "operation_params": operation_params,
            "visibility": "gm",
            "audience": [],
        }
        current_rev = self.engine.branch(self.branch)["revision"]
        proposed = self.learning.propose(
            self.branch,
            node_id=self.node_id,
            request_id=req,
            expected_world_revision=current_rev,
            lesson=lesson,
            outcome_ids=list(outcome_ids),
        )
        return proposed

    def review_lesson(
        self,
        lesson_id: str,
        lesson_revision: int,
        status: str,
        rationale: str,
        expected_review_revision: int = 0,
        counter_outcome_ids: Sequence[str] = (),
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reviews and activates/suspends a lesson with explicit qualification."""
        req = request_id or f"review-lesson:{self.character_id}:{uuid4().hex[:8]}"
        current_rev = self.engine.branch(self.branch)["revision"]
        review = self.learning.review(
            self.branch,
            lesson_id=lesson_id,
            lesson_revision=lesson_revision,
            request_id=req,
            expected_world_revision=current_rev,
            status=status,
            rationale=rationale,
            expected_review_revision=expected_review_revision,
            counter_outcome_ids=list(counter_outcome_ids),
        )
        return review

    def send_dialogue(
        self,
        text: str,
        act: str = "speak",
        mode: str = "spoken",
        listeners: Optional[List[str]] = None,
        scene: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sends dialogue using Engine.apply() and records a dialogue_turn record."""
        req = request_id or f"dialogue:{self.character_id}:{uuid4().hex[:8]}"
        turn_id = f"turn:{self.character_id}:{uuid4().hex[:8]}"
        current_rev = self.engine.branch(self.branch)["revision"]
        listeners_list = listeners or []

        common = {
            "op": "create",
            "domain": "dialogue_turn",
            "id": turn_id,
            "status": "confirmed",
            "visibility": "public",
            "audience": listeners_list,
            "evidence": [{"note": "Direct participant dialogue turn."}],
            "data": {
                "speaker": self.character_id,
                "listeners": listeners_list,
                "scene": scene,
                "reply_to": None,
                "act": act,
                "text": text,
                "mode": mode,
            },
        }
        observations = [
            {
                "id": f"{turn_id}:heard:{listener}",
                "observer_id": listener,
                "subject_id": self.character_id,
                "assertion": text,
                "certainty": "heard",
                "visibility": "restricted",
                "audience": [listener],
            }
            for listener in listeners_list
        ]

        command = {
            "api_version": 3,
            "branch": self.branch,
            "request_id": req,
            "expected_revision": current_rev,
            "kind": "action",
            "actor": self.character_id,
            "narrative": f"{self.character_id} communicates: {text[:50]}",
            "changes": [common],
            "observations": observations,
        }
        return self.engine.apply(command)

    def status(self) -> Dict[str, Any]:
        """Provides an auditable status summary without mutating state."""
        current_rev = self.engine.branch(self.branch)["revision"]
        char_data = characters.read(self.engine, self.branch, self.character_id)
        node_data = self.nodes.read(self.branch, self.character_id)
        lessons = self.learning.list(self.branch, self.character_id)
        outcomes = self.learning.list_outcomes(self.branch, self.character_id)
        methods = self.methods.list(self.branch, self.character_id)
        assigned_rows = self.db.execute(
            "SELECT DISTINCT method_id FROM node_method_assignments WHERE branch=? AND node_id=? AND qualification='experimental'",
            (self.branch, self.node_id),
        ).fetchall()
        assigned_methods = [r[0] for r in assigned_rows]

        return {
            "character_id": self.character_id,
            "node_id": self.node_id,
            "branch": self.branch,
            "workspace_id": self.workspace_id,
            "world_revision": current_rev,
            "profile_revision": node_data["profile_revision"],
            "character_label": char_data["character"]["data"]["name"],
            "active_methods_count": len(assigned_methods),
            "assigned_methods": assigned_methods,
            "recorded_outcomes_count": len(outcomes),
            "lessons_count": len(lessons),
            "reviewed_qualified_lessons": [
                l["lesson_id"] for l in lessons if l.get("status") == "qualified"
            ],
            "operational_history_events": len(node_data.get("operational_history", [])),
        }
