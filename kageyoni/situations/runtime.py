from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .service import SituationError, SituationService

@dataclass
class WorkflowRun:
    run_id: str
    situation_id: str
    workflow_id: str
    parent_run_id: str | None = None
    objective: str = ""
    authority: tuple[str,...] = ()
    completed_stages: list[str] = field(default_factory=list)
    status: str = "active"

@dataclass(frozen=True)
class ExtensionProposal:
    extension_id: str
    situation_id: str
    kind: str
    payload: dict[str, Any]
    evidence_refs: tuple[str,...] = ()
    scope: str = "local"

@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: str
    target_type: str
    target_id: str
    change: dict[str, Any]
    outcome_refs: tuple[str,...]
    status: str = "candidate"

class SituationRuntime:
    def __init__(self, service: SituationService):
        self.service=service; self.runs={}; self.extensions={}; self.evolution={}

    def start(self, run: WorkflowRun):
        s=self.service.situations[run.situation_id]
        if s.workflow_id != run.workflow_id: raise SituationError("workflow not bound to situation")
        if run.parent_run_id:
            p=self.runs[run.parent_run_id]
            if run.objective != p.objective: raise SituationError("child workflow cannot replace parent objective")
            if not set(run.authority).issubset(p.authority): raise SituationError("child workflow cannot expand authority")
        self.runs[run.run_id]=run

    def complete_stage(self, run_id:str, stage_id:str, observed:dict[str,Any]):
        run=self.runs[run_id]; workflow=self.service.workflows[run.workflow_id]
        stage=next(x for x in workflow.stages if x.stage_id==stage_id)
        if any(r not in run.completed_stages for r in stage.requires): raise SituationError("stage dependency incomplete")
        if not observed: raise SituationError("stage completion requires an observation")
        if stage_id not in run.completed_stages: run.completed_stages.append(stage_id)

    def propose_extension(self, p:ExtensionProposal):
        if p.scope!="local": raise SituationError("extensions begin local")
        if p.situation_id not in self.service.situations: raise SituationError("unknown situation")
        self.extensions[p.extension_id]=p

    def promote_extension(self, extension_id:str, repeated_outcome_refs:tuple[str,...]):
        p=self.extensions[extension_id]
        if len(set(repeated_outcome_refs)) < 2: raise SituationError("promotion requires repeated consequential evidence")
        return EvolutionProposal("promote:"+extension_id,"template",self.service.situations[p.situation_id].template_id,p.payload,repeated_outcome_refs,"qualified")

    def propose_evolution(self,p:EvolutionProposal):
        if not p.outcome_refs: raise SituationError("evolution requires observed outcomes")
        self.evolution[p.proposal_id]=p

    def recruit(self,situation_id:str,candidates:list[dict[str,Any]],unresolved:list[str]):
        if not unresolved: return []
        useful=[]
        for c in candidates:
            covers=set(c.get("covers",())) & set(unresolved)
            if covers and c.get("evidence_refs"): useful.append(c["participant_id"])
        return useful

    def collide(self, projection_ids:list[str]):
        ps=[self.service.projections[x] for x in projection_ids]
        foreground=[set(p.foreground) for p in ps]
        shared=set.intersection(*foreground) if foreground else set()
        distinct=[sorted(f-shared) for f in foreground]
        return {"shared":sorted(shared),"distinct":distinct,"redundant":bool(ps) and all(f==foreground[0] for f in foreground)}
