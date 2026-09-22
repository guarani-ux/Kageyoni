from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class SituationMemory:
    memory_id:str; situation_id:str; template_id:str; objective:str
    decisions:tuple[str,...]=(); artifacts:tuple[str,...]=(); unresolved:tuple[str,...]=(); outcome_refs:tuple[str,...]=(); dependency_keys:tuple[str,...]=()

class SituationMemoryStore:
    def __init__(self, store=None):
        from .storage import MemorySituationStore
        self.store=store or MemorySituationStore()
    def remember(self,m:SituationMemory): self.store.put("memory",m.memory_id,m)
    def retrieve(self,*,template_id:str|None=None,dependency_keys:tuple[str,...]=(),limit:int=10):
        keys=set(dependency_keys); scored=[]
        for m in self.store.values("memory"):
            score=(4 if template_id and m.template_id==template_id else 0)+3*len(keys & set(m.dependency_keys))+len(keys & set(m.unresolved))
            if score: scored.append((score,m.memory_id,m))
        return [m for _,_,m in sorted(scored,key=lambda x:(-x[0],x[1]))[:limit]]

@dataclass(frozen=True)
class TransferCandidate:
    candidate_id:str; source_memory_id:str; destination_situation_id:str; mapping:str; assumptions:tuple[str,...]=(); destination_evidence_refs:tuple[str,...]=(); status:str="candidate"

def qualify_transfer(c:TransferCandidate, evidence_resolver=None):
    if not c.destination_evidence_refs:
        return TransferCandidate(**{**c.__dict__,"status":"untested"})
    if evidence_resolver is None or any(not evidence_resolver(ref,c.destination_situation_id) for ref in c.destination_evidence_refs):
        return TransferCandidate(**{**c.__dict__,"status":"untested"})
    return TransferCandidate(**{**c.__dict__,"status":"supported_in_destination"})
