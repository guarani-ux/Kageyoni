from __future__ import annotations
import json
from dataclasses import asdict, is_dataclass

class MemorySituationStore:
    """Test double only. Production should use SQLiteSituationStore."""
    def __init__(self): self.data={}
    def put(self,kind,key,value): self.data.setdefault(kind,{})[key]=value
    def get(self,kind,key): return self.data[kind][key]
    def contains(self,kind,key): return key in self.data.get(kind,{})
    def values(self,kind): return list(self.data.get(kind,{}).values())

def default_decoders():
    from .models import Situation, SituationTemplate, Workflow, WorkflowStage, DomainProjection
    from .runtime import WorkflowRun, ExtensionProposal, EvolutionProposal
    from .memory import SituationMemory
    return {
        "situation": lambda p: Situation(**p),
        "template": lambda p: SituationTemplate(**{**p,"required":tuple(p.get("required",())), "optional":tuple(p.get("optional",())), "relations":tuple(tuple(x) for x in p.get("relations",())), "recommended_workflows":tuple(p.get("recommended_workflows",()))}),
        "workflow": lambda p: Workflow(p["workflow_id"],p["version"],p["purpose"],tuple(p["applicable_templates"]),tuple(WorkflowStage(x["stage_id"],tuple(x.get("requires",())),tuple(x.get("next_stages",())),tuple(x.get("completion_requires",()))) for x in p["stages"])),
        "projection": lambda p: DomainProjection(p["projection_id"],p["participant_id"],p["situation_id"],tuple(p["foreground"]),tuple(p["questions"]),tuple(p.get("method_refs",())),tuple(p.get("experience_refs",()))),
        "workflow_run": lambda p: WorkflowRun(**{**p,"authority":tuple(p.get("authority",()))}),
        "extension": lambda p: ExtensionProposal(**{**p,"evidence_refs":tuple(p.get("evidence_refs",()))}),
        "evolution": lambda p: EvolutionProposal(**{**p,"outcome_refs":tuple(p.get("outcome_refs",()))}),
        "memory": lambda p: SituationMemory(**{k: tuple(v) if isinstance(v, list) else v for k, v in p.items()}),
    }

class SQLiteSituationStore:
    """Adapter over Kageyoni's existing migrated SQLite connection."""
    def __init__(self,conn,decoders=None):
        self.conn=conn
        self.decoders=decoders or default_decoders()
        if self.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='situation_records'").fetchone() is None:
            raise RuntimeError("Situation migration not applied: missing situation_records")

    def put(self,kind,key,value):
        payload=asdict(value) if is_dataclass(value) else value
        self.conn.execute("INSERT INTO situation_records(kind,record_key,payload_json) VALUES(?,?,?) ON CONFLICT(kind,record_key) DO UPDATE SET payload_json=excluded.payload_json",(kind,key,json.dumps(payload,sort_keys=True)))

    def get(self,kind,key):
        row=self.conn.execute("SELECT payload_json FROM situation_records WHERE kind=? AND record_key=?",(kind,key)).fetchone()
        if not row: raise KeyError((kind,key))
        payload=json.loads(row[0]); decoder=self.decoders.get(kind)
        return decoder(payload) if decoder else payload

    def contains(self,kind,key):
        return self.conn.execute("SELECT 1 FROM situation_records WHERE kind=? AND record_key=?",(kind,key)).fetchone() is not None

    def values(self,kind):
        rows=self.conn.execute("SELECT payload_json FROM situation_records WHERE kind=? ORDER BY record_key",(kind,)).fetchall()
        decoder=self.decoders.get(kind); vals=[json.loads(r[0]) for r in rows]
        return [decoder(v) for v in vals] if decoder else vals
