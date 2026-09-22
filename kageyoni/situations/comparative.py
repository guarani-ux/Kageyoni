from __future__ import annotations
from dataclasses import dataclass,asdict

CONDITIONS=("A","B","C","D","E")
METRICS=("requirement_satisfaction","source_fidelity","continuity","useful_novelty","correction_burden","reconstruction_burden","execution_overhead","recovery")

@dataclass(frozen=True)
class ComparativeObservation:
 task_id:str; condition:str; metrics:dict; serious_failure:str|None=None; evidence_refs:tuple[str,...]=()

class ComparativeLedger:
 def __init__(self): self.rows=[]
 def record(self,row:ComparativeObservation):
  if row.condition not in CONDITIONS: raise ValueError("unknown comparison condition")
  missing=set(METRICS)-set(row.metrics)
  if missing: raise ValueError(f"missing metrics: {sorted(missing)}")
  self.rows.append(row)
 def task(self,task_id): return [r for r in self.rows if r.task_id==task_id]
 def export(self): return [asdict(r) for r in self.rows]
 def completeness(self,task_id):
  rows=self.task(task_id); return set(r.condition for r in rows)==set(CONDITIONS)
