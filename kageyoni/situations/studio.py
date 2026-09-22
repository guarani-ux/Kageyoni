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
