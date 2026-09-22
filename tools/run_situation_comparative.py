from __future__ import annotations
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from kageyoni.situations.comparative import ComparativeLedger, ComparativeObservation, CONDITIONS, METRICS

TASKS=("creative","research","technical","living_world")

def metrics(condition):
    structured=condition in ("B","C","D","E")
    workflow=condition in ("C","D","E")
    persistent=condition in ("D","E")
    selective=condition=="E"
    return {
        "requirement_satisfaction": None,
        "source_fidelity": None,
        "continuity": 1 if persistent else 0,
        "useful_novelty": None,
        "correction_burden": None,
        "reconstruction_burden": 0 if persistent else 1,
        "execution_overhead": {"A":0,"B":1,"C":2,"D":3,"E":4}[condition],
        "recovery": 1 if workflow else 0,
    }

def run():
    ledger=ComparativeLedger()
    for task in TASKS:
        for condition in CONDITIONS:
            ledger.record(ComparativeObservation(
                task,condition,metrics(condition),
                serious_failure="semantic output quality not evaluated in deterministic comparison",
                evidence_refs=("mechanical-structure-only",),
            ))
    assert all(ledger.completeness(task) for task in TASKS)
    return {"scope":"mechanical comparison only; no model-quality advantage claim","rows":ledger.export()}

if __name__=="__main__":
    print(json.dumps(run(),indent=2,sort_keys=True))
