from __future__ import annotations
import json
from dataclasses import dataclass,asdict
from pathlib import Path
from typing import Callable
from .memory import SituationMemoryStore

@dataclass(frozen=True)
class EncounterStep:
    encounter_index:int
    context:str
    retrieved_memory_ids:tuple[str,...]
    decision:str
    stored_memory_id:str|None
    outcome_observed:str|None
    capability_exercised:str|None
    evidence_refs:tuple[str,...]=()

@dataclass(frozen=True)
class TrajectoryLedger:
    trajectory_id:str
    domain:str
    template_id:str
    encounters:list[EncounterStep]
    distinctions:dict[str,bool]
    development_supported:bool
    unqualified_claims:list[str]

def assess_trajectory(trajectory_id:str,domain:str,template_id:str,encounters:list[EncounterStep])->TrajectoryLedger:
    if len(encounters)<2: raise ValueError("long-horizon qualification requires repeated encounters")
    stored=any(e.stored_memory_id for e in encounters)
    retrieved=any(e.retrieved_memory_ids for e in encounters[1:])
    reasoning=len({e.decision for e in encounters})>1
    capability_steps=[e for e in encounters if e.capability_exercised]
    changed_capability=bool(capability_steps) and all(e.evidence_refs for e in capability_steps)
    observed=[e.outcome_observed for e in encounters if e.outcome_observed is not None]
    changed_outcome=len(set(observed))>1 and all(e.evidence_refs for e in encounters if e.outcome_observed is not None)
    distinctions={"stored_history":stored,"retrieved_history":retrieved,"changed_reasoning":reasoning,"changed_capability":changed_capability,"changed_outcome":changed_outcome}
    supported=changed_capability and changed_outcome
    unknown=[]
    if not changed_capability: unknown.append("Capability change is not established by the observed encounters.")
    if not changed_outcome: unknown.append("Outcome change is not established by the observed encounters.")
    unknown.append("Cross-domain transfer remains unsupported without destination evidence.")
    return TrajectoryLedger(trajectory_id,domain,template_id,encounters,distinctions,supported,unknown)

def run_multi_turn_trajectory(store:SituationMemoryStore,trajectory_id:str,domain:str,template_id:str,key:str,executor:Callable|None=None)->TrajectoryLedger:
    """Execute repeated real encounters. This module does not invent capability or outcome evidence."""
    if executor is None: raise RuntimeError("R6 is unqualified until an encounter executor supplies observed evidence")
    encounters=[]
    for index in range(1,4):
        retrieved=tuple(m.memory_id for m in store.retrieve(template_id=template_id,dependency_keys=(key,)))
        step=executor(index,retrieved,store)
        if not isinstance(step,EncounterStep): raise TypeError("encounter executor must return EncounterStep")
        if step.encounter_index!=index: raise ValueError("encounter index mismatch")
        encounters.append(step)
    return assess_trajectory(trajectory_id,domain,template_id,encounters)

def export_long_horizon_evidence(output_path:Path,executor_factory:Callable|None=None)->dict:
    if executor_factory is None: raise RuntimeError("R6 is unqualified until real trajectory executors are supplied")
    store=SituationMemoryStore(); specs=[("story","living_world","living_world","relationship:promise"),("research","research","research","claim:source-gap"),("production","creative","production_brief","audience:ambiguity"),("technical","repository","repository_repair","failure:replay")]
    ledgers=[run_multi_turn_trajectory(store,t,d,tmpl,key,executor_factory(t,d,tmpl,key)) for t,d,tmpl,key in specs]
    data={"stage":"R6 - Long-Horizon Development Trials","qualification":"observed-execution","trajectories":[asdict(x) for x in ledgers],"summary":{"total_trajectories":len(ledgers),"verified_development":all(x.development_supported for x in ledgers)}}
    output_path.parent.mkdir(parents=True,exist_ok=True);output_path.write_text(json.dumps(data,indent=2,sort_keys=True),encoding="utf-8");return data
