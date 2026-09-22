from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Iterable
from .comparative import ComparativeLedger, ComparativeObservation, CONDITIONS, METRICS

TASKS=("creative","research","technical","living_world")

@dataclass(frozen=True)
class TrialResult:
    task_id:str
    condition:str
    metrics:dict[str,Any]
    evidence_refs:tuple[str,...]
    serious_failure:str|None=None

def validate_trial(result:TrialResult)->None:
    if result.task_id not in TASKS: raise ValueError("unknown comparative task")
    if result.condition not in CONDITIONS: raise ValueError("unknown comparative condition")
    missing=[m for m in METRICS if m not in result.metrics]
    if missing: raise ValueError("missing comparative metrics: "+",".join(missing))
    if not result.evidence_refs: raise ValueError("comparative trial requires execution evidence")

def run_comparative_suite(executor:Callable[[str,str],TrialResult]|None=None)->ComparativeLedger:
    """Run actual A-E trials. No built-in scores or expected winner exist."""
    if executor is None:
        raise RuntimeError("R5 is unqualified until an external/real task executor is supplied")
    ledger=ComparativeLedger()
    for task_id in TASKS:
        for condition in CONDITIONS:
            result=executor(task_id,condition)
            validate_trial(result)
            ledger.record(ComparativeObservation(task_id=result.task_id,condition=result.condition,metrics=result.metrics,serious_failure=result.serious_failure,evidence_refs=result.evidence_refs))
    return ledger

def export_comparative_evidence(output_path:Path,executor:Callable[[str,str],TrialResult]|None=None)->dict:
    ledger=run_comparative_suite(executor)
    data={"stage":"R5 - Comparative Qualification","qualification":"observed-execution","tasks":list(TASKS),"conditions":list(CONDITIONS),"metrics_evaluated":list(METRICS),"observations":ledger.export(),"summary":{"total_trials":len(ledger.rows),"complete_tasks":[t for t in TASKS if ledger.completeness(t)]}}
    output_path.parent.mkdir(parents=True,exist_ok=True); output_path.write_text(json.dumps(data,indent=2,sort_keys=True),encoding="utf-8"); return data
