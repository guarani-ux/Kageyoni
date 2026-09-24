from __future__ import annotations
from dataclasses import asdict
from typing import Any
import uuid
from .models import Situation, SituationTemplate, Workflow, DomainProjection
from .storage import MemorySituationStore

class SituationError(ValueError): pass

class SituationService:
    def __init__(self,store=None,participant_evidence_resolver=None):
        self.store=store or MemorySituationStore(); self.participant_evidence_resolver=participant_evidence_resolver
        self.templates={}; self.workflows={}; self.situations={}; self.projections={}

    def register_template(self,template):
        if template.template_id in self.templates: raise SituationError("template already exists")
        self.templates[template.template_id]=template; self.store.put("template",template.template_id,template)

    def register_workflow(self,workflow):
        if workflow.workflow_id in self.workflows: raise SituationError("workflow already exists")
        self.workflows[workflow.workflow_id]=workflow; self.store.put("workflow",workflow.workflow_id,workflow)

    def genesis(self,template_id,objective,supplied,*,situation_id=None,workspace=None,allow_local_novelty=True):
        # 1. Guard against unauthorized privilege escalation
        PROHIBITED_PRIVILEGE_KEYS = {
            "role", "roles", "admin", "is_admin", "permissions", "authority",
            "system_authority", "bypass_governance", "superadmin", "privilege",
        }
        for k in supplied.keys():
            k_lower = str(k).lower()
            if k_lower in PROHIBITED_PRIVILEGE_KEYS or k_lower.startswith("admin_") or k_lower.startswith("auth_"):
                raise SituationError(f"UNAUTHORIZED_PRIVILEGE_ESCALATION: Key '{k}' attempts to forge administrative permissions or bypass governance.")

        # 2. Retrieve template or instantiate local prototype
        template = None
        if template_id in self.templates:
            template = self.templates[template_id]
        elif self.store.contains("template", template_id):
            template = self.store.get("template", template_id)

        if template is None:
            if not allow_local_novelty:
                raise SituationError(f"Template '{template_id}' not found and local novelty is disabled.")
            known = {}; contradictions = {}; local_ext = {}
            for key, value in supplied.items():
                if isinstance(value, dict) and "__alternatives__" in value:
                    vals = list(value["__alternatives__"])
                    if len(vals) > 1: contradictions[key] = vals; known[key] = None
                    elif vals: known[key] = vals[0]
                    else: known[key] = None
                else: known[key] = value
                local_ext[key] = value
            unknowns = [k for k, v in known.items() if v is None]
            target_ws = workspace or "local"
            s = Situation(
                situation_id or str(uuid.uuid4()),
                template_id,
                target_ws,
                objective,
                objects=known,
                unknowns=unknowns,
                contradictions=contradictions,
                origin="local_prototype",
                local_extensions=local_ext,
            )
            self.situations[s.situation_id] = s
            self.store.put("situation", s.situation_id, s)
            return s

        # 3. Cataloged template with potential local novelty
        known = {}; contradictions = {}; local_ext = {}; is_novel = False
        for key, value in supplied.items():
            if key not in template.required and key not in template.optional:
                if allow_local_novelty:
                    is_novel = True
                    local_ext[key] = value
                    known[key] = value
                continue
            if isinstance(value, dict) and "__alternatives__" in value:
                vals = list(value["__alternatives__"])
                if len(vals) > 1: contradictions[key] = vals; known[key] = None
                elif vals: known[key] = vals[0]
                else: known[key] = None
            else: known[key] = value

        unknowns = [k for k in template.required if k not in known or known[k] is None]
        origin = "local_novelty" if is_novel else "catalog"
        s = Situation(
            situation_id or str(uuid.uuid4()),
            template_id,
            template.workspace,
            objective,
            objects=known,
            unknowns=unknowns,
            contradictions=contradictions,
            origin=origin,
            local_extensions=local_ext,
        )
        self.situations[s.situation_id] = s
        self.store.put("situation", s.situation_id, s)
        return s

    def bind_workflow(self,situation_id,workflow_id):
        s=self.situations.get(situation_id) or self.store.get("situation",situation_id)
        w=self.workflows.get(workflow_id) or self.store.get("workflow",workflow_id)
        if s.template_id not in w.applicable_templates: raise SituationError("workflow not applicable to situation template")
        s.workflow_id=workflow_id; self.situations[s.situation_id]=s; self.store.put("situation",s.situation_id,s)

    def propose_projection(self,projection,*,established_refs):
        refs=set(projection.method_refs)|set(projection.experience_refs)
        if not refs or not refs.issubset(established_refs): raise SituationError("domain projection requires established participant evidence")
        if self.participant_evidence_resolver is None or any(not self.participant_evidence_resolver(projection.participant_id,ref,projection.situation_id) for ref in refs):
            raise SituationError("domain projection evidence is not bound to participant and situation")
        if not self.store.contains("situation",projection.situation_id): raise SituationError("unknown situation")
        self.projections[projection.projection_id]=projection; self.store.put("projection",projection.projection_id,projection)

    def snapshot(self,situation_id):
        return asdict(self.situations.get(situation_id) or self.store.get("situation",situation_id))
