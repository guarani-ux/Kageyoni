from __future__ import annotations
import uuid
from ..engine import digest, encoded, require
from ..persistence.unit_of_work import UnitOfWork

MAX_INCLUDED=2048

class ContextPackets:
    """Bounded, operation-scoped context. Missing required context remains explicit."""
    def __init__(self,engine): self.engine=engine; self.db=engine.db
    def create(self,*,scope,basis,included,unresolved=None,excluded=None,operation_id=None,context_id=None):
        require(isinstance(scope,str) and scope.strip(),'context scope required')
        require(isinstance(basis,dict) and basis,'context basis required')
        require(isinstance(included,list),'included context must be a list')
        require(unresolved is None or isinstance(unresolved,list),'unresolved must be a list')
        require(excluded is None or isinstance(excluded,list),'excluded must be a list')
        unresolved=list(unresolved or []); excluded=list(excluded or [])
        op=None
        if operation_id is not None:
            op=self.db.execute('SELECT * FROM v11_operations WHERE operation_id=?',(operation_id,)).fetchone(); require(op is not None,'context operation does not exist')
            require(op['scope']==scope,'context scope differs from operation scope')
        if 'branch' in basis:
            require(isinstance(basis['branch'],str) and basis['branch'],'context branch required')
            current=self.engine.branch(basis['branch'])['revision']
            if 'revision' in basis: require(basis['revision']==current,'context basis revision is stale')
            else: basis=dict(basis,revision=current)
        clean=[]
        for item in unresolved:
            if isinstance(item,dict):
                require(type(item.get('blocking',True)) is bool,'blocking flag must be boolean')
            clean.append(item)
        unresolved=clean
        # Explicitly excluded private material may not also enter the active context.
        excluded_refs={x.get('ref') for x in excluded if isinstance(x,dict) and x.get('ref')}
        included_refs={x.get('ref') if isinstance(x,dict) else x for x in included}
        require(not (excluded_refs & included_refs),'excluded context cannot also be included')
        # Required references come from the parent contract. Omission is converted into a blocker.
        if op is not None:
            import json
            payload=json.loads(op['payload_json'])
            for ref in payload.get('required_context_refs',[]) or []:
                represented = ref in included_refs or any((x.get('ref') if isinstance(x,dict) else x)==ref for x in unresolved)
                if not represented: unresolved.append({'ref':ref,'blocking':True,'reason':'required context omitted'})
        budget_exceeded=len(included)>MAX_INCLUDED
        if budget_exceeded: unresolved.append({'ref':'context-budget','blocking':True,'reason':f'included context exceeds {MAX_INCLUDED}'})
        cid=context_id or 'context:'+uuid.uuid4().hex
        payload={'scope':scope,'basis':basis,'included':included,'unresolved':unresolved,'excluded':excluded,'operation_id':operation_id}
        with UnitOfWork(self.db):
            self.db.execute('INSERT INTO v11_context_packets VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',(cid,operation_id,scope,encoded(basis),encoded(included),encoded(unresolved),encoded(excluded),digest(payload)))
        sufficient=not any(bool(x.get('blocking',True)) if isinstance(x,dict) else True for x in unresolved)
        return {'context_id':cid,**payload,'sufficient_for_commit':sufficient}
