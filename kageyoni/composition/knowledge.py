from __future__ import annotations
import hashlib, uuid
from datetime import datetime, timezone
from typing import Any
from ..engine import encoded, require
from ..persistence.unit_of_work import UnitOfWork

_ROUTE_STATES=['AVAILABLE','ROUTED','ENCOUNTERED','INTERPRETED','TESTED','INTEGRATED','REJECTED','UNRESOLVED','TRANSFERRED']
_ALLOWED={
 'AVAILABLE':{'ROUTED','REJECTED','UNRESOLVED'},
 'ROUTED':{'ENCOUNTERED','REJECTED','UNRESOLVED'},
 'ENCOUNTERED':{'INTERPRETED','REJECTED','UNRESOLVED'},
 'INTERPRETED':{'TESTED','INTEGRATED','REJECTED','UNRESOLVED'},
 'TESTED':{'INTEGRATED','REJECTED','UNRESOLVED','TRANSFERRED'},
 'INTEGRATED':{'TESTED','TRANSFERRED','REJECTED'},
 'UNRESOLVED':{'ROUTED','ENCOUNTERED','INTERPRETED','REJECTED'},
 'REJECTED':set(), 'TRANSFERRED':set(),
}

def _now(): return datetime.now(timezone.utc).isoformat()

class KnowledgeLedger:
    """External information ledger. Ingestion creates evidence, never truth."""
    def __init__(self, engine): self.engine=engine; self.db=engine.db
    def ingest(self, *, source_type, source_ref, claims, metadata=None, captured_at=None, evidence_status='unassessed', entry_id=None):
        require(evidence_status in {'unassessed','source_verified','contested','retracted'},'invalid evidence status')
        require(isinstance(claims,list),'claims must be a list')
        require(isinstance(source_ref,str) and source_ref,'source_ref required')
        payload={'source_type':source_type,'source_ref':source_ref,'claims':claims,'metadata':metadata or {},'captured_at':captured_at or _now()}
        content_hash=hashlib.sha256(encoded(payload).encode()).hexdigest(); entry_id=entry_id or 'knowledge:'+uuid.uuid4().hex
        self.db.execute('INSERT INTO knowledge_ledger(entry_id,source_type,source_ref,content_hash,claims_json,evidence_status,metadata_json,captured_at) VALUES(?,?,?,?,?,?,?,?)',
                        (entry_id,source_type,source_ref,content_hash,encoded(claims),evidence_status,encoded(metadata or {}),payload['captured_at']))
        return self.read(entry_id)
    def read(self, entry_id):
        row=self.db.execute('SELECT * FROM knowledge_ledger WHERE entry_id=?',(entry_id,)).fetchone();require(row is not None,'unknown knowledge entry')
        out=dict(row);out['claims']=__import__('json').loads(out.pop('claims_json'));out['metadata']=__import__('json').loads(out.pop('metadata_json'));return out
    def list(self, evidence_status=None):
        rows=self.db.execute('SELECT entry_id,source_type,source_ref,content_hash,evidence_status,captured_at,created_at FROM knowledge_ledger'+(' WHERE evidence_status=?' if evidence_status else '')+' ORDER BY created_at,entry_id', (() if not evidence_status else (evidence_status,)))
        return [dict(r) for r in rows]
    def route(self, *, entry_id, target_ref, reason, route_id=None):
        self.read(entry_id); require(target_ref and reason,'target_ref and reason required'); route_id=route_id or 'route:'+uuid.uuid4().hex
        history=[{'status':'ROUTED','at':_now(),'reason':reason}]
        self.db.execute('INSERT INTO knowledge_routes(route_id,entry_id,target_ref,reason,status,history_json) VALUES(?,?,?,?,?,?)',(route_id,entry_id,target_ref,reason,'ROUTED',encoded(history)))
        return self.read_route(route_id)
    def read_route(self, route_id):
        import json
        row=self.db.execute('SELECT * FROM knowledge_routes WHERE route_id=?',(route_id,)).fetchone();require(row is not None,'unknown knowledge route')
        out=dict(row);out['history']=json.loads(out.pop('history_json'));return out
    def advance(self, *, route_id, status, note=''):
        import json
        require(status in _ROUTE_STATES,'invalid route status')
        with UnitOfWork(self.db):
            row=self.db.execute('SELECT * FROM knowledge_routes WHERE route_id=?',(route_id,)).fetchone();require(row is not None,'unknown knowledge route')
            cur=dict(row);old_status=cur['status'];history=json.loads(cur['history_json'])
            require(status in _ALLOWED[old_status],f"invalid knowledge transition {old_status} -> {status}")
            history=history+[{'status':status,'at':_now(),'note':note}]
            result=self.db.execute('UPDATE knowledge_routes SET status=?,history_json=?,updated_at=CURRENT_TIMESTAMP WHERE route_id=? AND status=?',(status,encoded(history),route_id,old_status))
            require(result.rowcount==1,'concurrent knowledge transition detected; reload and retry')
        return self.read_route(route_id)
    def to_aspect(self, *, entry_id, aspect_id=None, compatible_slots=None):
        entry=self.read(entry_id)
        return {
          'aspect_id':aspect_id or 'evidence:'+entry_id,
          'type':'evidence','family':'evidence','purpose_type':'evidence',
          'authority':'evidence','compatible_slots':compatible_slots or [],
          'properties':{'entry_id':entry_id,'source_type':entry['source_type'],'claims':entry['claims'],'evidence_status':entry['evidence_status']},
          'provenance':[{'kind':'knowledge_ledger','ref':entry_id,'content_hash':entry['content_hash']}],
          'effects':[],
        }
