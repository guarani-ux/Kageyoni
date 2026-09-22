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
    authority: tuple[str, ...] = ()
    completed_stages: list[str] = field(default_factory=list)
    status: str = "active"\n    resume_condition: str | None = None\n    failure_reason: str | None = None

@dataclass(frozen=True)
class ExtensionProposal:
    extension_id: str
    situation_id: str
    kind: str
    payload: dict[str, Any]
    evidence_refs: tuple[str, ...] = ()
    scope: str = "local"

@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: str
    target_type: str
    target_id: str
    change: dict[str, Any]
    outcome_refs: tuple[str, ...]
    status: str = "candidate"

class SituationRuntime:
    def __init__(self, service: SituationService, evidence_resolver=None):
        self.service = service
        self.runs = {}
        self.extensions = {}
        self.evolution = {}
        self.evidence_resolver = evidence_resolver

    def start(self, run: WorkflowRun):
        s = self.service.situations.get(run.situation_id) or self.service.store.get("situation", run.situation_id)
        if s.workflow_id != run.workflow_id:
            raise SituationError("workflow not bound to situation")
        if run.parent_run_id:
            p = self.runs.get(run.parent_run_id) or self.service.store.get("workflow_run", run.parent_run_id)
            if run.objective != p.objective:
                raise SituationError("child workflow cannot replace parent objective")
            if not set(run.authority).issubset(p.authority):
                raise SituationError("child workflow cannot expand authority")
        self.runs[run.run_id] = run
        self.service.store.put("workflow_run", run.run_id, run)

    def wait(self,run_id:str,resume_condition:str):
        if not resume_condition: raise SituationError("waiting requires resume condition")
        run=self.runs.get(run_id) or self.service.store.get("workflow_run",run_id)
        run.status="waiting"; run.resume_condition=resume_condition; self.service.store.put("workflow_run",run.run_id,run)

    def fail(self,run_id:str,reason:str):
        if not reason: raise SituationError("failure requires reason")
        run=self.runs.get(run_id) or self.service.store.get("workflow_run",run_id)
        run.status="failed"; run.failure_reason=reason; self.service.store.put("workflow_run",run.run_id,run)

    def resume(self,run_id:str,*,condition_satisfied:bool):
        run=self.runs.get(run_id) or self.service.store.get("workflow_run",run_id)
        if run.status!="waiting": raise SituationError("only waiting workflow can resume")
        if not condition_satisfied: raise SituationError("resume condition not satisfied")
        run.status="active"; run.resume_condition=None; self.runs[run.run_id]=run; self.service.store.put("workflow_run",run.run_id,run)

    def complete_stage(self, run_id: str, stage_id: str, evidence_ref: str):
        run = self.runs.get(run_id) or self.service.store.get("workflow_run", run_id)
        workflow = self.service.workflows.get(run.workflow_id) or self.service.store.get("workflow", run.workflow_id)
        stage = next(x for x in workflow.stages if x.stage_id == stage_id)
        if any(req not in run.completed_stages for req in stage.requires):
            raise SituationError("stage dependency incomplete")
        if not evidence_ref or self.evidence_resolver is None or not self.evidence_resolver(evidence_ref, run):
            raise SituationError("stage completion requires engine-resolved evidence")
        if stage_id not in run.completed_stages:
            run.completed_stages.append(stage_id)
        self.service.store.put("workflow_run", run.run_id, run)

    def propose_extension(self, proposal: ExtensionProposal):
        if proposal.scope != "local":
            raise SituationError("extensions begin local")
        if not self.service.store.contains("situation", proposal.situation_id):
            raise SituationError("unknown situation")
        self.extensions[proposal.extension_id] = proposal
        self.service.store.put("extension", proposal.extension_id, proposal)

    def promote_extension(self, extension_id: str, repeated_outcome_refs: tuple[str, ...]):
        proposal = self.extensions.get(extension_id) or self.service.store.get("extension", extension_id)
        if len(set(repeated_outcome_refs)) < 2:
            raise SituationError("promotion requires repeated consequential evidence")
        if self.evidence_resolver is None or any(not self.evidence_resolver(ref, None) for ref in repeated_outcome_refs):
            raise SituationError("promotion evidence must resolve through engine custody")
        situation = self.service.situations.get(proposal.situation_id) or self.service.store.get("situation", proposal.situation_id)
        return EvolutionProposal("promote:" + extension_id, "template", situation.template_id, proposal.payload, repeated_outcome_refs, "qualified")

    def propose_evolution(self, proposal: EvolutionProposal):
        if not proposal.outcome_refs:
            raise SituationError("evolution requires observed outcomes")
        if self.evidence_resolver is None or any(not self.evidence_resolver(ref, None) for ref in proposal.outcome_refs):
            raise SituationError("evolution evidence must resolve through engine custody")
        self.evolution[proposal.proposal_id] = proposal
        self.service.store.put("evolution", proposal.proposal_id, proposal)

    def recruit(self, situation_id: str, candidates: list[dict[str, Any]], unresolved: list[str]):
        if not unresolved:
            return []
        useful = []
        for candidate in candidates:
            covers = set(candidate.get("covers", ())) & set(unresolved)
            refs = candidate.get("evidence_refs", ())
            if covers and refs and self.evidence_resolver is not None and all(self.evidence_resolver(ref, None) for ref in refs):
                useful.append(candidate["participant_id"])
        return useful

    def collide(self, projection_ids: list[str]):
        projections = [self.service.projections.get(x) or self.service.store.get("projection", x) for x in projection_ids]
        foreground = [set(p.foreground) for p in projections]
        shared = set.intersection(*foreground) if foreground else set()
        distinct = [sorted(f - shared) for f in foreground]
        return {"shared": sorted(shared), "distinct": distinct, "redundant": bool(projections) and all(f == foreground[0] for f in foreground)}
