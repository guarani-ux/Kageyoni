from __future__ import annotations
from .service import SituationService
from .catalog import install_defaults
from .runtime import SituationRuntime
from .memory import SituationMemoryStore

class SituationStudio:
    """Thin operator surface over shared Situation services."""
    def __init__(self,service=None,*,mediator=None,evidence_resolver=None,test_mode=False):
        self.service=install_defaults(service or SituationService())
        self.runtime=SituationRuntime(self.service,evidence_resolver,mediator,test_mode=test_mode)
        self.memory=SituationMemoryStore(self.service.store)
    def new(self,template_id,situation_objective,**supplied): return self.service.genesis(template_id,situation_objective,supplied)
    def save_workflow(self,workflow): self.service.register_workflow(workflow)
    def snapshot(self,situation_id): return self.service.snapshot(situation_id)

    def bind_recommended(self, situation_id: str) -> str:
        """Binds the template's primary recommended workflow to the situation."""
        s = self.service.situations.get(situation_id) or self.service.store.get("situation", situation_id)
        template = self.service.templates[s.template_id]
        if not template.recommended_workflows:
            from .service import SituationError
            raise SituationError(f"No recommended workflows for template {s.template_id}")
        recommended = template.recommended_workflows[0]
        self.service.bind_workflow(situation_id, recommended)
        return recommended

    def create_and_bind(self, template_id: str, situation_objective: str, **supplied):
        """Creates situation and immediately binds its recommended workflow."""
        s = self.new(template_id, situation_objective, **supplied)
        self.bind_recommended(s.situation_id)
        return self.service.situations.get(s.situation_id) or self.service.store.get("situation", s.situation_id)

    def summary(self, situation_id: str) -> dict:
        """Standardized caller summary across all 6 situation families."""
        s = self.service.situations.get(situation_id) or self.service.store.get("situation", situation_id)
        return {
            "situation_id": s.situation_id,
            "template_id": s.template_id,
            "objective": s.objective,
            "workflow_id": s.workflow_id,
            "workspace": getattr(s, "workspace", "default"),
            "unknowns": list(getattr(s, "unknowns", ())),
            "contradictions": list(getattr(s, "contradictions", ())),
        }
