from __future__ import annotations
from dataclasses import asdict
from typing import Any
import uuid
from .models import Situation, SituationTemplate, Workflow, DomainProjection
from .storage import MemorySituationStore

class SituationError(ValueError): pass

class SituationService:
    """Shared Situation layer. It does not create domain-specific engines."""
    def __init__(self, store=None, participant_evidence_resolver=None):
        self.store = store or MemorySituationStore()
        self.participant_evidence_resolver = participant_evidence_resolver
        self.templates = {}
        self.workflows = {}
        self.situations = {}
        self.projections = {}

    def register_template(self, template: SituationTemplate) -> None:
        if template.template_id in self.templates: raise SituationError("template already exists")
        self.templates[template.template_id] = template
        self.store.put("template", template.template_id, template)

    def register_workflow(self, workflow: Workflow) -> None:
        if workflow.workflow_id in self.workflows: raise SituationError("workflow already exists")
        self.workflows[workflow.workflow_id] = workflow
        self.store.put("workflow", workflow.workflow_id, workflow)

    def genesis(self, template_id: str, objective: str, supplied: dict[str, Any], *, situation_id: str | None=None) -> Situation:
        template = self.templates.get(template_id) or self.store.get("template", template_id)
        known, contradictions = {}, {}
        for key, value in supplied.items():
            if key not in template.required and key not in template.optional: continue
            if isinstance(value, dict) and "__alternatives__" in value:
                values=list(value["__alternatives__"])
                if len(values)>1:
                    contradictions[key]=values
                    known[key]=None
                elif values:
                    known[key]=values[0]
                else:
                    known[key]=None
            else:
                known[key]=value
        unknowns=[key for key in template.required if key not in known or known[key] is None]
        s=Situation(situation_id or str(uuid.uuid4()),template_id,template.workspace,objective,objects=known,unknowns=unknowns,contradictions=contradictions)
        self.situations[s.situation_id]=s
        self.store.put("situation",s.situation_id,s)
        return s

    def bind_workflow(self, situation_id: str, workflow_id: str) -> None:
        s=self.situations.get(situation_id) or self.store.get("situation",situation_id)
        w=self.workflows.get(workflow_id) or self.store.get("workflow",workflow_id)
        if s.template_id not in w.applicable_templates: raise SituationError("workflow not applicable to situation template")
        s.workflow_id=workflow_id
        self.situations[s.situation_id]=s
        self.store.put("situation",s.situation_id,s)

    def propose_projection(self, projection: DomainProjection, *, established_refs: set[str]) -> None:
        refs=set(projection.method_refs)|set(projection.experience_refs)
        if not refs or not refs.issubset(established_refs): raise SituationError("domain projection requires established participant evidence")
        if self.participant_evidence_resolver is None or any(not self.participant_evidence_resolver(projection.participant_id,ref,projection.situation_id) for ref in refs):
            raise SituationError("domain projection evidence is not bound to participant and situation")
        if not self.store.contains("situation",projection.situation_id): raise SituationError("unknown situation")
        self.projections[projection.projection_id]=projection
        self.store.put("projection",projection.projection_id,projection)

    def snapshot(self, situation_id: str) -> dict[str, Any]:
        s=self.situations.get(situation_id) or self.store.get("situation",situation_id)
        return asdict(s)
