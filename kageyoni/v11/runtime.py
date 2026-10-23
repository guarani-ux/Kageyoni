from __future__ import annotations
import json, uuid
from ..engine import digest, encoded, require
from ..persistence.unit_of_work import UnitOfWork
from .enforcement import EnforcerRegistry

_ALLOWED={
 'DECLARED':{'PREPARED','BLOCKED'},'PREPARED':{'ASSESSED','BLOCKED'},'ASSESSED':{'AUTHORIZED','BLOCKED'},
 'AUTHORIZED':{'EXECUTED','BLOCKED'},'EXECUTED':{'OBSERVED','UNCERTAIN'},'OBSERVED':{'VERIFIED','UNCERTAIN'},
 'VERIFIED':{'COMPLETED','BLOCKED'},'UNCERTAIN':{'OBSERVED','BLOCKED'},'BLOCKED':{'PREPARED','ASSESSED'},'COMPLETED':set()
}

class ProtectedOperations:
    """Evidence-backed protected lifecycle with optimistic concurrency control."""
    def __init__(self, engine=None):
        if engine is None:
            from ..engine import Engine
            engine = Engine(":memory:")
        self.engine = engine
        self.db = engine.db
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS v11_operations(
              operation_id TEXT PRIMARY KEY,
              objective TEXT NOT NULL,
              requirement_version TEXT NOT NULL,
              scope TEXT NOT NULL,
              state TEXT NOT NULL CHECK(state IN ('DECLARED','PREPARED','ASSESSED','AUTHORIZED','EXECUTED','OBSERVED','VERIFIED','COMPLETED','BLOCKED','UNCERTAIN')),
              payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
              source_hash TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
    def declare(self,*,objective,requirement_version,scope,payload=None,operation_id=None):
        require(isinstance(objective,str) and objective.strip(),'objective required')
        require(isinstance(requirement_version,(str,int)) and not isinstance(requirement_version,bool) and str(requirement_version).strip(),'requirement version required')
        require(isinstance(scope,str) and scope.strip(),'scope required')
        oid=operation_id or 'operation:'+uuid.uuid4().hex
        data=dict(payload or {}); data.update(objective=objective,requirement_version=str(requirement_version),scope=scope,_state='DECLARED')
        with UnitOfWork(self.db):
            self.db.execute('INSERT INTO v11_operations VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)',(oid,objective,str(requirement_version),scope,'DECLARED',encoded(data),digest(data)))
        return self.read(oid)
    def read(self,oid):
        r=self.db.execute('SELECT * FROM v11_operations WHERE operation_id=?',(oid,)).fetchone(); require(r is not None,'unknown protected operation')
        o=dict(r); o['payload']=json.loads(o.pop('payload_json')); return o
    def _assessment(self,aid,oid):
        r=self.db.execute('SELECT * FROM v11_assessments WHERE assessment_id=?',(aid,)).fetchone(); require(r is not None,'assessment was not issued by engine')
        basis=json.loads(r['basis_json']); op=self.read(oid)
        require((basis.get('operation_id') or basis.get('operation'))==oid,'assessment is not bound to operation')
        require(r['protected_requirement']==op['requirement_version'],'assessment requirement mismatch')
        require(r['disposition']=='supported','blocking assessment cannot authorize operation')
        return dict(r)
    def _effective_authority(self,data,scope):
        qid=data.get('authorization_qualification_id'); require(qid,'operation has no authorization qualification')
        return EnforcerRegistry(self.engine).require_qualified(qid,scope)
    def _execution_receipt(self,rid,oid):
        r=self.db.execute('SELECT * FROM v11_execution_receipts WHERE receipt_id=? AND operation_id=?',(rid,oid)).fetchone(); require(r is not None,'execution receipt is not engine-held for operation'); return r
    def _observation(self,oid,obsid,rid=None):
        r=self.db.execute('SELECT * FROM v11_observations WHERE observation_id=? AND operation_id=?',(obsid,oid)).fetchone(); require(r is not None,'observation is not engine-held for operation')
        if rid: require(r['receipt_id']==rid,'observation does not derive from execution receipt')
        return r
    def _verification(self,oid,vid,obsid=None):
        r=self.db.execute('SELECT * FROM v11_verifications WHERE verification_id=? AND operation_id=?',(vid,oid)).fetchone(); require(r is not None,'verification is not engine-held for operation')
        if obsid: require(r['observation_id']==obsid,'verification does not inspect operation observation')
        require(r['disposition']=='passed','verification did not pass'); return r
    def transition(self, oid, state=None, *, patch=None, qualification_id=None):
        if isinstance(oid, dict):
            payload = oid
            if "state" not in payload and "oid" not in payload:
                objective = payload.get("objective", "governance_transition")
                req_ver = payload.get("requirement_version", "1.0")
                scope = payload.get("scope", "global")
                op_data = self.declare(objective=objective, requirement_version=req_ver, scope=scope, payload=payload)
                if state is None:
                    return op_data
                oid = op_data["operation_id"]
            else:
                oid = payload.get("oid") or payload.get("operation_id")
                state = state or payload.get("state")
                patch = patch or payload.get("patch")
                qualification_id = qualification_id or payload.get("qualification_id")

        cur=self.read(oid); require(state in _ALLOWED[cur['state']],f"invalid protected transition {cur['state']} -> {state}")
        data=dict(cur['payload']); patch=dict(patch or {})
        require(patch.get('objective',cur['objective'])==cur['objective'],'operation cannot silently replace objective')
        require(str(patch.get('requirement_version',cur['requirement_version']))==cur['requirement_version'],'operation cannot silently replace requirement version')
        require(patch.get('scope',cur['scope'])==cur['scope'],'operation cannot silently replace scope')
        merged=dict(data); merged.update(patch); merged.update(objective=cur['objective'],requirement_version=cur['requirement_version'],scope=cur['scope'])
        if state=='ASSESSED':
            aid=merged.get('assessment_id'); require(aid,'assessed state requires engine-held assessment')
            a=self._assessment(aid,oid); merged['assessment_disposition']=a['disposition']; merged['assessment_qualification_id']=a['qualification_id']
        if state=='AUTHORIZED':
            aid=merged.get('assessment_id'); a=self._assessment(aid,oid)
            require(qualification_id and qualification_id==a['qualification_id'],'authorization must use assessment qualification')
            q=EnforcerRegistry(self.engine).require_qualified(qualification_id,cur['scope']); require(q['enforcer_id']==a['enforcer_id'],'authorization enforcer mismatch')
            merged['authorization_qualification_id']=qualification_id
        if state=='EXECUTED':
            self._effective_authority(merged,cur['scope'])
            rid=merged.get('execution_receipt_id'); self._execution_receipt(rid,oid)
            dep=merged.get('dependency_basis')
            if isinstance(dep,dict) and dep.get('branch') is not None:
                require(dep.get('revision')==self.engine.branch(dep['branch'])['revision'],'operation dependency basis changed')
        if state=='OBSERVED':
            rid=merged.get('execution_receipt_id'); self._execution_receipt(rid,oid)
            obsid=merged.get('observation_id'); self._observation(oid,obsid,rid)
        if state=='VERIFIED':
            obsid=merged.get('observation_id'); self._observation(oid,obsid,merged.get('execution_receipt_id'))
            vid=merged.get('verification_id'); self._verification(oid,vid,obsid)
        if state=='COMPLETED':
            require(cur['state']=='VERIFIED','completion requires verified state')
            self._effective_authority(merged,cur['scope'])
            self._execution_receipt(merged.get('execution_receipt_id'),oid); self._observation(oid,merged.get('observation_id'),merged.get('execution_receipt_id')); self._verification(oid,merged.get('verification_id'),merged.get('observation_id'))
            require(merged.get('observed_outcome') not in (None,False,{},[],'',0),'completion requires substantive observed outcome')
            require(merged.get('verification_receipt') not in (None,False,{},[],'',0),'completion requires substantive verification receipt')
            for child in merged.get('required_children',[]) or []:
                row=self.db.execute('SELECT state FROM v11_operations WHERE operation_id=?',(child,)).fetchone(); require(row is not None and row['state']=='COMPLETED','required child incomplete')
        merged['_state']=state
        with UnitOfWork(self.db):
            cur2=self.db.execute('UPDATE v11_operations SET state=?,payload_json=?,source_hash=?,updated_at=CURRENT_TIMESTAMP WHERE operation_id=? AND source_hash=?',(state,encoded(merged),digest(merged),oid,cur['source_hash']))
            require(cur2.rowcount==1,'protected operation changed concurrently')
        return self.read(oid)
    def _issue_execution_record(self,oid,*,evidence_type,evidence_ref,payload=None):
        cur=self.read(oid); require(cur['state']=='AUTHORIZED','execution receipt requires authorized operation'); self._effective_authority(cur['payload'],cur['scope'])
        rid='execution:'+uuid.uuid4().hex; body={'operation_id':oid,'evidence_type':evidence_type,'evidence_ref':evidence_ref,'payload':dict(payload or {})}
        with UnitOfWork(self.db): self.db.execute('INSERT INTO v11_execution_receipts VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)',(rid,oid,evidence_type,evidence_ref,encoded(body['payload']),digest(body)))
        return self.transition(oid,'EXECUTED',patch={'execution_receipt_id':rid})
    def issue_execution(self,oid,*,evidence_type,evidence_ref,payload=None):
        require(isinstance(evidence_type,str) and evidence_type.strip(),'execution evidence type required'); require(isinstance(evidence_ref,str) and evidence_ref.strip(),'execution evidence ref required')
        body=dict(payload or {}); effect=body.get('domain_effect') if isinstance(body,dict) else None
        if evidence_type=='world-event':
            require(self.db.execute('SELECT 1 FROM events WHERE id=?',(evidence_ref,)).fetchone() is not None,'world execution evidence does not exist')
            require(isinstance(effect,dict) and effect.get('event_id')==evidence_ref,'world execution evidence binding mismatch')
        elif evidence_type=='pipeline-result':
            row=self.db.execute('SELECT payload_json FROM pipeline_runs WHERE pipeline_id=?',(evidence_ref,)).fetchone(); require(row is not None,'pipeline execution evidence does not exist')
            pipeline=json.loads(row['payload_json']); require(pipeline.get('phase')=='completed','pipeline execution evidence is not completed')
            require(isinstance(effect,dict) and effect.get('pipeline_id')==evidence_ref and effect.get('phase')=='completed','pipeline execution evidence binding mismatch')
        elif evidence_type=='artifact-result':
            row=self.db.execute('SELECT artifact_id,digest,size FROM artifacts WHERE artifact_id=?',(evidence_ref,)).fetchone()
            require(row is not None,'artifact execution evidence does not exist')
            require(isinstance(effect,dict) and effect.get('artifact_id')==evidence_ref,'artifact execution evidence binding mismatch')
            if effect.get('digest') is not None:
                require(effect.get('digest')==row['digest'],'artifact execution digest mismatch')
        else:
            require(False,'unsupported execution evidence type')
        return self._issue_execution_record(oid,evidence_type=evidence_type,evidence_ref=evidence_ref,payload=body)
    def _issue_fixture_execution(self,oid,*,evidence_ref='fixture:execution',payload=None):
        require(isinstance(evidence_ref,str) and evidence_ref.startswith('fixture:'),'fixture evidence ref required')
        return self._issue_execution_record(oid,evidence_type='fixture',evidence_ref=evidence_ref,payload=payload)
    def observe(self,oid,*,outcome):
        cur=self.read(oid); require(cur['state'] in {'EXECUTED','UNCERTAIN'},'observation requires executed or uncertain operation'); require(isinstance(outcome,dict) and outcome,'observed outcome required')
        rid=cur['payload'].get('execution_receipt_id'); self._execution_receipt(rid,oid); obs='observation:'+uuid.uuid4().hex; body={'operation_id':oid,'receipt_id':rid,'payload':outcome}
        with UnitOfWork(self.db): self.db.execute('INSERT INTO v11_observations VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)',(obs,oid,rid,encoded(outcome),digest(body)))
        return self.transition(oid,'OBSERVED',patch={'observation_id':obs,'observed_outcome':outcome})
    def verify_observation(self,oid,*,disposition='passed',receipt):
        cur=self.read(oid); require(cur['state']=='OBSERVED','verification requires observed operation'); require(disposition in {'passed','failed','unresolved'},'invalid verification disposition'); require(isinstance(receipt,dict) and receipt,'verification receipt required')
        obs=cur['payload'].get('observation_id'); self._observation(oid,obs,cur['payload'].get('execution_receipt_id')); vid='verification:'+uuid.uuid4().hex; body={'operation_id':oid,'observation_id':obs,'disposition':disposition,'payload':receipt}
        with UnitOfWork(self.db): self.db.execute('INSERT INTO v11_verifications VALUES(?,?,?,?,?, ?,CURRENT_TIMESTAMP)',(vid,oid,obs,disposition,encoded(receipt),digest(body)))
        if disposition=='passed': return self.transition(oid,'VERIFIED',patch={'verification_id':vid,'verification_receipt':receipt})
        return self.transition(oid,'UNCERTAIN',patch={'verification_id':vid,'verification_receipt':receipt})
    def complete(self,oid): return self.transition(oid,'COMPLETED')
