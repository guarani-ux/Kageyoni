from __future__ import annotations
from dataclasses import dataclass
import json
from typing import Any

@dataclass(frozen=True)
class SituationMemory:
    memory_id:str; situation_id:str; template_id:str; objective:str
    decisions:tuple[str,...]=(); artifacts:tuple[str,...]=(); unresolved:tuple[str,...]=(); outcome_refs:tuple[str,...]=(); dependency_keys:tuple[str,...]=()
    workspace_id:str="default"; method_refs:tuple[str,...]=(); revoked:bool=False

class SituationMemoryStore:
    def __init__(self, store=None):
        from .storage import MemorySituationStore
        self.store=store or MemorySituationStore()
    def remember(self,m:SituationMemory): self.store.put("memory",m.memory_id,m)
    def retrieve(self,*,template_id:str|None=None,dependency_keys:tuple[str,...]=(),limit:int=10,workspace_id:str|None=None,revoked_methods:set[str]|None=None):
        keys=set(dependency_keys); scored=[]
        revoked = revoked_methods or set()
        candidates = None
        if hasattr(self.store, "conn"):
            try:
                query = "SELECT payload_json FROM situation_records WHERE kind='memory'"
                params = []
                query += " AND (json_extract(payload_json, '$.revoked') IS NULL OR json_extract(payload_json, '$.revoked') = 0)"
                if workspace_id is not None:
                    query += " AND (json_extract(payload_json, '$.workspace_id') = ? OR (? = 'default' AND json_extract(payload_json, '$.workspace_id') IS NULL))"
                    params.extend([workspace_id, workspace_id])
                query += " ORDER BY record_key"
                rows = self.store.conn.execute(query, params).fetchall()
                decoder = getattr(self.store, "decoders", {}).get("memory")
                raw_vals = [json.loads(r[0]) for r in rows]
                candidates = [decoder(v) for v in raw_vals] if decoder else raw_vals
            except Exception:
                candidates = None

        if candidates is None:
            candidates = self.store.values("memory")

        for m in candidates:
            if getattr(m, "revoked", False): continue
            if workspace_id is not None and getattr(m, "workspace_id", "default") != workspace_id: continue
            if any(r in revoked for r in getattr(m, "method_refs", ())): continue
            score=(4 if template_id and m.template_id==template_id else 0)+3*len(keys & set(m.dependency_keys))+len(keys & set(m.unresolved))
            if score: scored.append((score,m.memory_id,m))
        return [m for _,_,m in sorted(scored,key=lambda x:(-x[0],x[1]))[:limit]]

@dataclass(frozen=True)
class TransferCandidate:
    candidate_id: str
    source_memory_id: str
    destination_situation_id: str
    mapping: str
    assumptions: tuple[str, ...] = ()
    destination_evidence_refs: tuple[str, ...] = ()
    status: str = "candidate"
    source_workspace_id: str = "default"
    destination_workspace_id: str = "default"
    method_id: str | None = None
    method_revision: int | None = None
    method_digest: str | None = None
    source_world_revision: int | None = None


def create_transfer_from_memory(
    candidate_id: str,
    source_memory: SituationMemory,
    destination_situation_id: str,
    mapping: str,
    destination_workspace_id: str = "default",
    assumptions: tuple[str, ...] = (),
    destination_evidence_refs: tuple[str, ...] = (),
    method_id: str | None = None,
    method_revision: int | None = None,
    method_digest: str | None = None,
) -> TransferCandidate:
    """Binds situation memory directly to a destination transfer candidate with provenance."""
    m_id = method_id or (
        source_memory.method_refs[0].replace("method:", "")
        if source_memory.method_refs and ":" in source_memory.method_refs[0]
        else (source_memory.method_refs[0] if source_memory.method_refs else None)
    )
    return TransferCandidate(
        candidate_id=candidate_id,
        source_memory_id=source_memory.memory_id,
        destination_situation_id=destination_situation_id,
        mapping=mapping,
        assumptions=assumptions,
        destination_evidence_refs=destination_evidence_refs,
        status="candidate",
        source_workspace_id=source_memory.workspace_id,
        destination_workspace_id=destination_workspace_id,
        method_id=m_id,
        method_revision=method_revision,
        method_digest=method_digest,
    )


def qualify_transfer(c: TransferCandidate, evidence_resolver=None, engine=None, target_workspace_checker=None):
    if not c.destination_evidence_refs:
        return TransferCandidate(**{**c.__dict__, "status": "untested"})
    if evidence_resolver is None or any(not evidence_resolver(ref, c.destination_situation_id) for ref in c.destination_evidence_refs):
        return TransferCandidate(**{**c.__dict__, "status": "untested"})

    # Target workspace validation
    if target_workspace_checker is not None:
        target_ws = c.destination_workspace_id or "default"
        if not target_workspace_checker(target_ws):
            return TransferCandidate(**{**c.__dict__, "status": "blocked"})

    if engine is not None:
        # Check target workspace in engine registry if provided
        if c.destination_workspace_id and c.destination_workspace_id != "default":
            try:
                from ..workspaces.registry import Registry
                Registry(engine).read(c.destination_workspace_id)
            except Exception:
                return TransferCandidate(**{**c.__dict__, "status": "blocked"})

        # Prevent phantom learning: verify authentic method backing if method is transferred
        if c.method_id is not None:
            if not c.method_digest:
                return TransferCandidate(**{**c.__dict__, "status": "blocked"})
            try:
                row = engine.db.execute(
                    "SELECT digest FROM method_revisions WHERE method_id=? ORDER BY revision DESC LIMIT 1",
                    (c.method_id,)
                ).fetchone()
                if not row:
                    return TransferCandidate(**{**c.__dict__, "status": "blocked"})
                actual_digest = row[0] if isinstance(row, tuple) else (row['digest'] if hasattr(row, '__getitem__') else None)
                if actual_digest != c.method_digest:
                    return TransferCandidate(**{**c.__dict__, "status": "blocked"})
            except Exception:
                pass

        try:
            from ..intelligence.transfer import Transfers
            t = Transfers(engine)
            transfer_rec = t.read(c.candidate_id)
            if transfer_rec.get("status") == "blocked":
                return TransferCandidate(**{**c.__dict__, "status": "blocked"})
        except Exception:
            try:
                row = engine.db.execute("SELECT status FROM method_transfers WHERE transfer_id=?", (c.candidate_id,)).fetchone()
                if row and row["status"] == "blocked":
                    return TransferCandidate(**{**c.__dict__, "status": "blocked"})
            except Exception:
                pass

    return TransferCandidate(**{**c.__dict__, "status": "supported_in_destination"})
