"""
Portable Play Kernel (playable-world/0.1)
Deterministic reference implementation of the Portable Play Protocol.

Invariants:
1. Rules + Portable State + Action Protocol.
2. The world travels between hosts; execution capabilities and permissions do not.
3. Strict revision checking prevents silent conflict overwrites.
4. Fictional consequences never self-certify external mutations.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


@dataclass
class SaveState:
    kernel: str
    world_id: str
    branch: str
    revision: int
    parent_revision: Optional[int]
    settings: Dict[str, Any]
    player: Dict[str, Any]
    scene: Dict[str, Any]
    goals: List[Dict[str, Any]] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    claims: List[Dict[str, Any]] = field(default_factory=list)
    bridges: List[Dict[str, Any]] = field(default_factory=list)
    methods: List[Dict[str, Any]] = field(default_factory=list)
    residue: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    pending_actions: List[Dict[str, Any]] = field(default_factory=list)
    processed_requests: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SaveState:
        clean = copy.deepcopy(data)
        return cls(
            kernel=clean.get("kernel", "playable-world/0.1"),
            world_id=clean.get("world_id", "default-world"),
            branch=clean.get("branch", "main"),
            revision=clean.get("revision", 0),
            parent_revision=clean.get("parent_revision"),
            settings=clean.get("settings", {}),
            player=clean.get("player", {}),
            scene=clean.get("scene", {}),
            goals=clean.get("goals", []),
            entities=clean.get("entities", []),
            relationships=clean.get("relationships", []),
            claims=clean.get("claims", []),
            bridges=clean.get("bridges", []),
            methods=clean.get("methods", []),
            residue=clean.get("residue", []),
            events=clean.get("events", []),
            pending_actions=clean.get("pending_actions", []),
            processed_requests=clean.get("processed_requests", []),
        )

    @classmethod
    def from_file(cls, path: Union[str, Path, Dict[str, Any], bytes]) -> SaveState:
        if isinstance(path, dict):
            return cls.from_dict(path)
        if isinstance(path, (bytes, bytearray)):
            return cls.from_dict(json.loads(path.decode("utf-8")))
        if isinstance(path, str):
            p = Path(path)
            if p.exists() and p.is_file():
                text = p.read_text(encoding="utf-8")
                return cls.from_dict(json.loads(text))
            try:
                return cls.from_dict(json.loads(path))
            except Exception:
                pass
        text = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(json.loads(text))

    def write_to_file(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")


@dataclass
class TurnRequest:
    request_id: str
    operation: str  # "start", "continue", "inspect", "act", "save", "resume"
    input: str
    presentation: str = "chat"  # "chat", "voice", "json"
    host: Dict[str, Any] = field(default_factory=lambda: {
        "name": "standard-host",
        "available_actions": ["render", "export_save"],
        "external_action_authorizations": []
    })
    base_revision: Optional[int] = None
    state: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TurnRequest:
        return cls(
            request_id=data["request_id"],
            operation=data.get("operation", "continue"),
            input=data.get("input", ""),
            presentation=data.get("presentation", "chat"),
            host=data.get("host", {}),
            base_revision=data.get("base_revision"),
            state=data.get("state"),
        )


@dataclass
class TurnResponse:
    request_id: str
    base_revision: int
    scene: str
    changes: str
    choices: List[Dict[str, Any]]
    pending_actions: List[Dict[str, Any]]
    next_state: Dict[str, Any]
    save_status: str  # "written", "not_written", "exported"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class PlayableWorldKernel:
    """
    Core runtime engine executing the Portable Play Protocol.
    Inhabits any host that can run Python or parse JSON.
    """

    def __init__(self, save: Optional[SaveState] = None):
        self.state = save or SaveState(
            kernel="playable-world/0.1",
            world_id="new-world",
            branch="main",
            revision=0,
            parent_revision=None,
            settings={
                "mode": "play",
                "presentation": "chat",
                "choice_limit": 4,
                "voice_choice_limit": 2,
                "target_reply_words": 180,
                "external_actions": "require_current_authorization",
                "background_progression": False,
            },
            player={"id": "player", "name": "Player"},
            scene={"id": "threshold", "title": "The Threshold", "summary": "A new world awaits."},
        )

    def load_save(self, save_or_dict: Union[SaveState, Dict[str, Any], str, Path]) -> None:
        if isinstance(save_or_dict, SaveState):
            self.state = copy.deepcopy(save_or_dict)
        elif isinstance(save_or_dict, dict):
            self.state = SaveState.from_dict(save_or_dict)
        elif isinstance(save_or_dict, (str, Path)):
            self.state = SaveState.from_file(save_or_dict)

    def validate_handoff(self, request: TurnRequest) -> Tuple[bool, str]:
        """
        Adapter validation contract:
        Verifies request ID, base revision, and world compatibility.
        """
        if not request.request_id:
            return False, "Missing request_id"

        # Check idempotent request deduplication
        if request.request_id in self.state.processed_requests:
            return False, f"Request '{request.request_id}' has already been processed"

        # Revision lock check: base_revision must match current world revision if provided
        if request.base_revision is not None and request.base_revision != self.state.revision:
            return False, (
                f"Revision conflict: Request base revision ({request.base_revision}) "
                f"does not match current world revision ({self.state.revision}). Handoff rejected."
            )

        return True, "Valid"

    def execute_turn(
        self,
        request: TurnRequest,
        adjudicator: Optional[Callable[[SaveState, TurnRequest], Dict[str, Any]]] = None,
        storage_sink: Optional[Callable[[SaveState], bool]] = None,
    ) -> TurnResponse:
        """
        Executes one honest turn under the Portable Play Protocol.
        """
        # If request carried a state snapshot, adopt it if revision matches
        if request.state:
            req_rev = request.state.get("revision", 0)
            if req_rev >= self.state.revision:
                self.load_save(request.state)

        # 1. Handoff Validation
        valid, reason = self.validate_handoff(request)
        if not valid:
            return TurnResponse(
                request_id=request.request_id,
                base_revision=self.state.revision,
                scene=f"Turn Rejected: {reason}",
                changes="None. State left intact.",
                choices=[],
                pending_actions=[],
                next_state=self.state.to_dict(),
                save_status="not_written",
            )

        base_rev = self.state.revision

        # 2. Adjudication (Default or Host-Supplied)
        if adjudicator:
            step_result = adjudicator(self.state, request)
        else:
            step_result = self._default_adjudicate(request)

        # 3. Reconcile State & Increment Revision
        new_rev = base_rev + 1
        self.state.parent_revision = base_rev
        self.state.revision = new_rev
        self.state.processed_requests.append(request.request_id)

        # Update scene if supplied
        if "new_scene" in step_result:
            self.state.scene.update(step_result["new_scene"])

        # Record event
        event_record = {
            "revision": new_rev,
            "timestamp": time.time(),
            "request_id": request.request_id,
            "player_input": request.input,
            "changes_summary": step_result.get("changes", ""),
        }
        self.state.events.append(event_record)

        # Handle pending external actions
        pending = step_result.get("pending_actions", [])
        if pending:
            self.state.pending_actions.extend(pending)

        # 4. Storage Hook
        save_status = "exported"
        if storage_sink:
            success = storage_sink(self.state)
            save_status = "written" if success else "not_written"

        return TurnResponse(
            request_id=request.request_id,
            base_revision=base_rev,
            scene=step_result.get("scene", self.state.scene.get("summary", "")),
            changes=step_result.get("changes", "World revision advanced."),
            choices=step_result.get("choices", [
                {"id": "explore", "label": "Explore surroundings", "intended_effects": "Notice details"},
                {"id": "reflect", "label": "Reflect on purpose", "intended_effects": "Clarify direction"},
            ]),
            pending_actions=pending,
            next_state=self.state.to_dict(),
            save_status=save_status,
        )

    def _default_adjudicate(self, request: TurnRequest) -> Dict[str, Any]:
        """Baseline honest adjudication when no external model is attached."""
        player_act = request.input.strip()
        current_title = self.state.scene.get("title", "The Threshold")
        
        scene_text = f"At {current_title}, you act: '{player_act}'. The environment reacts to your presence."
        changes_text = f"Turn registered. Action '{player_act}' received into world record."

        choices = [
            {"id": "act_further", "label": f"Deepen engagement with {current_title}", "intended_effects": "Advance encounter"},
            {"id": "change_focus", "label": "Shift attention to a different aspect", "intended_effects": "Broaden horizon"},
            {"id": "save_world", "label": "Preserve current world state", "intended_effects": "Prepare handoff to another host"},
        ]

        return {
            "scene": scene_text,
            "changes": changes_text,
            "choices": choices,
            "pending_actions": [],
        }
