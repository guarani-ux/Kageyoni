from __future__ import annotations
from dataclasses import dataclass
from .memory import SituationMemory, SituationMemoryStore

@dataclass(frozen=True)
class HorizonObservation:
    trajectory:str
    first_context:tuple[str,...]
    later_context:tuple[str,...]
    changed_start:bool

def run_horizon_trial(store:SituationMemoryStore, trajectory:str, template_id:str, dependency_key:str):
    before=tuple(m.memory_id for m in store.retrieve(template_id=template_id,dependency_keys=(dependency_key,)))
    store.remember(SituationMemory(f"{trajectory}:lesson",f"{trajectory}:1",template_id,f"{trajectory} objective",decisions=("retain consequential lesson",),outcome_refs=(f"{trajectory}:outcome",),dependency_keys=(dependency_key,)))
    after=tuple(m.memory_id for m in store.retrieve(template_id=template_id,dependency_keys=(dependency_key,)))
    return HorizonObservation(trajectory,before,after,before!=after and f"{trajectory}:lesson" in after)
