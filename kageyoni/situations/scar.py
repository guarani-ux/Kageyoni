from __future__ import annotations
from dataclasses import dataclass
from .models import Workflow, WorkflowStage

SCAR_WORKFLOW=Workflow("scar.default",1,"Probe, repair, reprobe and learn from demonstrated failure",("repository_repair","research","production_brief","campaign","writing","living_world"),(
 WorkflowStage("probe",next_stages=("classify",)), WorkflowStage("classify",("probe",),("repair",)), WorkflowStage("repair",("classify",),("reprobe",)), WorkflowStage("reprobe",("repair",),("learn",)), WorkflowStage("learn",("reprobe",),completion_requires=("probe","repair","reprobe")),
))

@dataclass(frozen=True)
class Scar:
    scar_id: str
    failure_class: str
    root_cause: str
    probe_refs: tuple[str, ...]
    repair_ref: str | None = None
    learned_rule: str | None = None
    status: str = "open"
    trigger_condition: str = ""
    affected_scopes: tuple[str, ...] = ()
    positive_control_ref: str | None = None
    resolution_criteria: str = ""


def close_scar(s: Scar, *, reprobe_passed: bool, positive_control_passed: bool):
    if not s.repair_ref or not reprobe_passed or not positive_control_passed:
        return s
    return Scar(**{**s.__dict__, "status": "closed"})


class ScarLedger:
    """Manages the lifecycle of operational scars and negative constraint enforcement."""
    def __init__(self, store=None):
        self.store = store
        self._scars: dict[str, Scar] = {}

    def record_scar(self, scar: Scar) -> Scar:
        self._scars[scar.scar_id] = scar
        if self.store is not None:
            self.store.put("scar", scar.scar_id, scar)
        return scar

    def get_scar(self, scar_id: str) -> Scar | None:
        if scar_id in self._scars:
            return self._scars[scar_id]
        if self.store is not None and self.store.contains("scar", scar_id):
            return self.store.get("scar", scar_id)
        return None

    def close(self, scar_id: str, *, reprobe_passed: bool, positive_control_passed: bool) -> Scar:
        scar = self.get_scar(scar_id)
        if not scar:
            raise KeyError(f"Scar '{scar_id}' not found in ledger.")
        closed = close_scar(scar, reprobe_passed=reprobe_passed, positive_control_passed=positive_control_passed)
        return self.record_scar(closed)

    def check_negative_constraints(self, failure_class: str, scope: str | None = None) -> bool:
        """
        Mechanically enforces negative constraints: returns True if an active (open)
        scar exists matching failure_class and scope, preventing repeating demonstrated failures.
        """
        scars = list(self._scars.values())
        if self.store is not None:
            for s in self.store.values("scar"):
                if s.scar_id not in self._scars:
                    scars.append(s)
        for s in scars:
            if s.status == "open" and s.failure_class == failure_class:
                if scope is None or not s.affected_scopes or scope in s.affected_scopes:
                    return True
        return False
