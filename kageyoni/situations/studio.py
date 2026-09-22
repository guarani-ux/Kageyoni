from __future__ import annotations
from .service import SituationService
from .catalog import install_defaults
from .runtime import SituationRuntime
from .memory import SituationMemoryStore

class SituationStudio:
    """Thin operator surface over the shared Situation services."""
    def __init__(self, service=None):
        self.service=install_defaults(service or SituationService()); self.runtime=SituationRuntime(self.service); self.memory=SituationMemoryStore(self.service.store)
    def new(self,template_id,objective,**supplied): return self.service.genesis(template_id,objective,supplied)
    def save_workflow(self,workflow): self.service.register_workflow(workflow)
    def snapshot(self,situation_id): return self.service.snapshot(situation_id)
