from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class SituationTemplate:
    template_id: str
    workspace: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    relations: tuple[tuple[str,str,str], ...] = ()
    recommended_workflows: tuple[str, ...] = ()

@dataclass
class Situation:
    situation_id: str
    template_id: str
    workspace: str
    objective: str
    objects: dict[str, Any] = field(default_factory=dict)
    relations: list[dict[str, Any]] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    workflow_id: str | None = None
    status: str = "active"

@dataclass(frozen=True)
class WorkflowStage:
    stage_id: str
    requires: tuple[str, ...] = ()
    next_stages: tuple[str, ...] = ()
    completion_requires: tuple[str, ...] = ()

@dataclass(frozen=True)
class Workflow:
    workflow_id: str
    version: int
    purpose: str
    applicable_templates: tuple[str, ...]
    stages: tuple[WorkflowStage, ...]

@dataclass(frozen=True)
class DomainProjection:
    projection_id: str
    participant_id: str
    situation_id: str
    foreground: tuple[str, ...]
    questions: tuple[str, ...]
    method_refs: tuple[str, ...] = ()
    experience_refs: tuple[str, ...] = ()
