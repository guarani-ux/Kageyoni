from __future__ import annotations
from dataclasses import dataclass

@dataclass
class SituationMediation:
    operation_id:str
    qualification_id:str
    assessment_id:str

class V11SituationMediator:
    """Adapter: Situation actions use the shared v11 ProtectedOperations path."""
    def __init__(self,engine):
        self.engine=engine
        from kageyoni.v11.integration import begin_domain_operation, complete_domain_operation
        self._begin=begin_domain_operation; self._complete=complete_domain_operation

    def begin(self,*,situation_id,workflow_id,stage_id,objective,requirement_version="situation.v1"):
        m=self._begin(self.engine,scope="situation",objective=objective,requirement_version=requirement_version,basis={"situation_id":situation_id,"workflow_id":workflow_id,"stage_id":stage_id},payload={"situation_id":situation_id,"workflow_id":workflow_id,"stage_id":stage_id})
        return SituationMediation(m["operation_id"],m["qualification_id"],m["assessment_id"])

    def complete(self,mediation,*,evidence_type,evidence_ref,outcome,verification):
        return self._complete(self.engine,mediation.__dict__,evidence_type=evidence_type,evidence_ref=evidence_ref,outcome=outcome,verification=verification)
