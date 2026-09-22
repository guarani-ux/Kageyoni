from __future__ import annotations
import json, uuid
from ..engine import digest, encoded, require
from ..persistence.unit_of_work import UnitOfWork

KINDS={'unknown_variable','unknown_relation','unknown_representation','contradiction','hidden_dependency','missing_capability','misallocated_capability','poor_coupling','unverified_claim','missing_reality_contact','false_invariance','obsolete_objective','unexploited_affordance'}
STATES={'open','investigating','resolved','blocked','abandoned'}
_ALLOWED={'open':{'investigating','blocked','abandoned'},'investigating':{'investigating','resolved','blocked','abandoned'},'blocked':{'investigating','abandoned'},'resolved':set(),'abandoned':set()}

class FrontierManager:
    """Bounded unresolved frontier whose closure requires engine-held observation evidence."""
    def __init__(self,engine): self.engine=engine; self.db=engine.db
    def open(self,*,objective,kind,payload,parent_ref=None,frontier_id=None):
        require(kind in KINDS,'unknown frontier kind'); require(isinstance(objective,str) and objective.strip(),'objective required'); require(isinstance(payload,dict),'frontier payload required')
        require(payload.get('objective_or_direction',objective)==objective,'frontier cannot silently replace objective')
        if parent_ref is not None:
            parent=self.db.execute('SELECT objective FROM v11_operations WHERE operation_id=?',(parent_ref,)).fetchone(); require(parent is not None,'frontier parent does not exist'); require(parent['objective']==objective,'frontier objective differs from parent')
        fid=frontier_id or 'frontier:'+uuid.uuid4().hex
        data=dict(payload,objective_or_direction=objective,_state='open',_parent_ref=parent_ref,_attempts=0)
        with UnitOfWork(self.db):
            self.db.execute('INSERT INTO v11_frontiers VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)',(fid,parent_ref,objective,kind,'open',encoded(data),digest(data)))
        return self.read(fid)
    def read(self,fid):
        r=self.db.execute('SELECT * FROM v11_frontiers WHERE frontier_id=?',(fid,)).fetchone(); require(r is not None,'unknown frontier'); o=dict(r); o['payload']=json.loads(o.pop('payload_json')); return o
    def observe(self,fid,*,refs,payload=None):
        f=self.read(fid); require(f['state']=='investigating','frontier observation requires active investigation'); require(isinstance(refs,list) and refs,'frontier observation refs required'); require(all(isinstance(x,str) and x.strip() for x in refs),'frontier observation refs must be nonempty strings')
        oid='frontier-observation:'+uuid.uuid4().hex; body={'frontier_id':fid,'refs':refs,'payload':dict(payload or {})}
        with UnitOfWork(self.db): self.db.execute('INSERT INTO v11_frontier_observations VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)',(oid,fid,encoded(refs),encoded(body['payload']),digest(body)))
        return {'observation_id':oid,**body}
    def _check_observations(self,fid,ids):
        require(isinstance(ids,list) and ids,'frontier resolution evidence required')
        for oid in ids:
            row=self.db.execute('SELECT * FROM v11_frontier_observations WHERE observation_id=? AND frontier_id=?',(oid,fid)).fetchone(); require(row is not None,'frontier evidence was not issued for this frontier')
    def transition(self,fid,state,*,patch=None):
        require(state in STATES,'invalid frontier state'); cur=self.read(fid); require(state in _ALLOWED[cur['state']],f"invalid frontier transition {cur['state']} -> {state}")
        data=dict(cur['payload']); patch=dict(patch or {}); require(patch.get('objective_or_direction',cur['objective'])==cur['objective'],'frontier cannot silently replace objective')
        if state=='investigating':
            attempts=int(data.get('_attempts',0))+1; budget=data.get('attempt_budget')
            if budget is not None: require(type(budget) is int and budget>0,'invalid frontier attempt budget'); require(attempts<=budget,'frontier investigation budget exhausted')
            data['_attempts']=attempts
        if state=='resolved':
            ids=patch.get('resolution_observation_ids'); self._check_observations(fid,ids)
            remaining=patch.get('remaining_unknowns',[]) or []
            require(not any(bool(x.get('blocking',True)) if isinstance(x,dict) else True for x in remaining),'frontier still has blocking unknowns')
        data.update(patch); data['objective_or_direction']=cur['objective']; data['_state']=state; data['_parent_ref']=cur['parent_ref']
        with UnitOfWork(self.db):
            res=self.db.execute('UPDATE v11_frontiers SET state=?,payload_json=?,source_hash=?,updated_at=CURRENT_TIMESTAMP WHERE frontier_id=? AND source_hash=?',(state,encoded(data),digest(data),fid,cur['source_hash']))
            require(res.rowcount==1,'frontier changed concurrently')
        return self.read(fid)
