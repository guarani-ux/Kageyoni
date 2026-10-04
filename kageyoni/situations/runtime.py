from __future__ import annotations
from .storage import StoreView
from dataclasses import dataclass, field
from typing import Any
from .service import SituationError, SituationService

@dataclass
class WorkflowRun:
    run_id:str
    situation_id:str
    workflow_id:str
    parent_run_id:str|None=None
    objective:str=""
    authority:tuple[str,...]=()
    completed_stages:list[str]=field(default_factory=list)
    status:str="active"
    resume_condition:str|None=None
    failure_reason:str|None=None

@dataclass(frozen=True)
class ExtensionProposal:
    extension_id:str; situation_id:str; kind:str; payload:dict[str,Any]
    evidence_refs:tuple[str,...]=(); scope:str="local"

@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id:str; target_type:str; target_id:str; change:dict[str,Any]
    outcome_refs:tuple[str,...]; status:str="candidate"

class SituationRuntime:
    def __init__(self,service:SituationService,evidence_resolver=None,mediator=None,*,test_mode=False):
        self.service=service; self.runs=StoreView(service.store,"workflow_run"); self.extensions=StoreView(service.store,"extension"); self.evolution=StoreView(service.store,"evolution"); self.evidence_resolver=evidence_resolver; self.mediator=mediator; self.test_mode=test_mode
        if not test_mode and mediator is None: raise SituationError("production SituationRuntime requires v11 mediator")

    def _run(self,run_id):
        return self.runs[run_id]

    def start(self,run:WorkflowRun):
        # Negative constraint check: block start if active open scar matches authority
        if hasattr(self.service.store, "values"):
            try:
                open_scars = self.service.store.values("scar")
                for sc in open_scars:
                    if getattr(sc, "status", None) == "open":
                        scopes = getattr(sc, "affected_scopes", ())
                        if run.authority and any(scope in scopes for scope in run.authority):
                            raise SituationError(f"NEGATIVE_CONSTRAINT_VIOLATION: Active scar '{sc.scar_id}' blocks execution pattern for authority.")
            except SituationError:
                raise
            except Exception:
                pass

        s=self.service.situations[run.situation_id]
        if s.workflow_id!=run.workflow_id: raise SituationError("workflow not bound to situation")
        if run.parent_run_id:
            p=self._run(run.parent_run_id)
            if run.objective!=p.objective: raise SituationError("child workflow cannot replace parent objective")
            if not set(run.authority).issubset(p.authority): raise SituationError("child workflow cannot expand authority")
        self.runs[run.run_id]=run

    def wait(self,run_id,resume_condition):
        if not resume_condition: raise SituationError("waiting requires resume condition")
        run=self._run(run_id); run.status="waiting"; run.resume_condition=resume_condition; self.service.store.put("workflow_run",run.run_id,run)

    def fail(self,run_id,reason,*,failure_class="runtime_failure",trigger_condition=""):
        if not reason: raise SituationError("failure requires reason")
        run=self._run(run_id); run.status="failed"; run.failure_reason=reason; self.service.store.put("workflow_run",run.run_id,run)
        from .scar import Scar
        scar = Scar(
            scar_id=f"scar:{run.situation_id}:{run.run_id}",
            failure_class=failure_class,
            root_cause=reason,
            probe_refs=(f"workflow_run:{run.run_id}",),
            trigger_condition=trigger_condition,
            affected_scopes=tuple(run.authority) if run.authority else (run.workflow_id,),
            status="open",
        )
        self.service.store.put("scar", scar.scar_id, scar)
        return scar

    def complete_workflow(self,run_id,*,outcome_refs=()):
        run=self._run(run_id); run.status="completed"; self.service.store.put("workflow_run",run.run_id,run)
        from .memory import SituationMemory
        s=self.service.situations[run.situation_id]
        mem=SituationMemory(
            memory_id=f"exp:{run.situation_id}:{run.run_id}",
            situation_id=run.situation_id,
            template_id=s.template_id,
            objective=run.objective or s.objective,
            outcome_refs=tuple(outcome_refs),
            decisions=tuple(run.completed_stages),
            workspace_id=s.workspace,
        )
        self.service.store.put("memory",mem.memory_id,mem)
        return mem

    def resume(self,run_id,*,condition_satisfied):
        run=self._run(run_id)
        if run.status!="waiting": raise SituationError("only waiting workflow can resume")
        if not condition_satisfied: raise SituationError("resume condition not satisfied")
        run.status="active"; run.resume_condition=None; self.runs[run.run_id]=run

    def begin_effectful_stage(self,run_id,stage_id,*,requirement_version="situation.v1"):
        if self.mediator is None: raise SituationError("effectful stage requires v11 mediator")
        run=self._run(run_id)
        return self.mediator.begin(situation_id=run.situation_id,workflow_id=run.workflow_id,stage_id=stage_id,objective=run.objective,requirement_version=requirement_version)

    def complete_effectful_stage(self,run_id,stage_id,mediation,*,evidence_type,evidence_ref,outcome,verification):
        if self.mediator is None: raise SituationError("effectful stage requires v11 mediator")
        completed=self.mediator.complete(mediation,evidence_type=evidence_type,evidence_ref=evidence_ref,outcome=outcome,verification=verification)
        if completed.get("state")!="COMPLETED": raise SituationError("v11 mediated effect did not complete")
        run=self._run(run_id)
        if stage_id not in run.completed_stages: run.completed_stages.append(stage_id)
        self.service.store.put("workflow_run",run.run_id,run)
        return completed

    def complete_stage(self,run_id,stage_id,evidence_ref):
        run=self._run(run_id); workflow=self.service.workflows[run.workflow_id]
        stage=next(x for x in workflow.stages if x.stage_id==stage_id)
        if any(req not in run.completed_stages for req in stage.requires): raise SituationError("stage dependency incomplete")
        if not evidence_ref or self.evidence_resolver is None or not self.evidence_resolver(evidence_ref,run): raise SituationError("stage completion requires engine-resolved evidence")
        if stage_id not in run.completed_stages: run.completed_stages.append(stage_id)
        self.service.store.put("workflow_run",run.run_id,run)

    def propose_extension(self,p):
        if p.scope!="local": raise SituationError("extensions begin local")
        if not self.service.store.contains("situation",p.situation_id): raise SituationError("unknown situation")
        self.extensions[p.extension_id]=p

    def promote_extension(self,extension_id,repeated_outcome_refs):
        p=self.extensions[extension_id]
        if len(set(repeated_outcome_refs))<2: raise SituationError("promotion requires repeated consequential evidence")
        if self.evidence_resolver is None or any(not self.evidence_resolver(ref,None) for ref in repeated_outcome_refs): raise SituationError("promotion evidence must resolve through engine custody")
        s=self.service.situations[p.situation_id]
        return EvolutionProposal("promote:"+extension_id,"template",s.template_id,p.payload,repeated_outcome_refs,"qualified")

    def propose_evolution(self,p):
        if not p.outcome_refs: raise SituationError("evolution requires observed outcomes")
        if self.evidence_resolver is None or any(not self.evidence_resolver(ref,None) for ref in p.outcome_refs): raise SituationError("evolution evidence must resolve through engine custody")
        self.evolution[p.proposal_id]=p

    def recruit(self,situation_id,candidates,unresolved):
        if not unresolved: return []
        useful=[]
        for candidate in candidates:
            covers=set(candidate.get("covers",()))&set(unresolved); refs=candidate.get("evidence_refs",())
            if covers and refs and self.evidence_resolver is not None and all(self.evidence_resolver(ref,None) for ref in refs): useful.append(candidate["participant_id"])
        return useful

    def collide(self,projection_ids):
        ps=[self.service.projections[x] for x in projection_ids]
        fg=[set(p.foreground) for p in ps]; shared=set.intersection(*fg) if fg else set()
        return {"shared":sorted(shared),"distinct":[sorted(x-shared) for x in fg],"redundant":bool(ps) and all(x==fg[0] for x in fg)}

