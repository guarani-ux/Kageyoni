from __future__ import annotations
from dataclasses import dataclass
from .models import Workflow, WorkflowStage

SCAR_WORKFLOW=Workflow("scar.default",1,"Probe, repair, reprobe and learn from demonstrated failure",("repository_repair","research","production_brief","campaign","writing","living_world"),(
 WorkflowStage("probe",next_stages=("classify",)), WorkflowStage("classify",("probe",),("repair",)), WorkflowStage("repair",("classify",),("reprobe",)), WorkflowStage("reprobe",("repair",),("learn",)), WorkflowStage("learn",("reprobe",),completion_requires=("probe","repair","reprobe")),
))

@dataclass(frozen=True)
class Scar:
 scar_id:str; failure_class:str; root_cause:str; probe_refs:tuple[str,...]; repair_ref:str|None=None; learned_rule:str|None=None; status:str="open"

def close_scar(s:Scar,*,reprobe_passed:bool,positive_control_passed:bool):
 if not s.repair_ref or not reprobe_passed or not positive_control_passed: return s
 return Scar(**{**s.__dict__,"status":"closed"})
