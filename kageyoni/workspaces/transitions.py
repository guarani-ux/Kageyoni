"""World checkpoint -> destination -> verified exact world return, never rewind."""
import json
from uuid import uuid4
from ..engine import require, digest, encoded
from ..persistence.unit_of_work import UnitOfWork
from .registry import Registry
from .contracts import checkpoint, text

class Transitions:
    def __init__(self,engine):self.engine=engine;self.db=engine.db
    def enter(self,branch,character_id,request_id,kind='document',viewer=None,source_ids=None,config=None):
        with UnitOfWork(self.db):
            workspace=Registry(self.engine).open(branch,character_id,kind,request_id,config=config,viewer=viewer,source_ids=source_ids)
            row=self.db.execute('SELECT receipt_json FROM workspace_transitions WHERE workspace_id=?',(workspace['workspace_id'],)).fetchone()
            if row:return json.loads(row[0])
            receipt=dict(transition_id='transition:'+uuid4().hex,workspace_id=workspace['workspace_id'],state='active',checkpoint=workspace['checkpoint'])
            self.db.execute('INSERT INTO workspace_transitions(transition_id,workspace_id,state,receipt_json) VALUES(?,?,?,?)',(receipt['transition_id'],workspace['workspace_id'],'active',encoded(receipt)))
            return receipt
    def read(self,transition_id,viewer=None):
        row=self.db.execute('SELECT * FROM workspace_transitions WHERE transition_id=?',(transition_id,)).fetchone();require(row is not None,'transition unavailable')
        Registry(self.engine).read(row['workspace_id'],viewer=viewer);return json.loads(row['receipt_json'])
    def return_to_world(self,transition_id,request_id,viewer=None):
        text(request_id,'request id')
        payload=dict(transition_id=transition_id,request_id=request_id,viewer=viewer)
        with UnitOfWork(self.db):
            row=self.db.execute('SELECT * FROM workspace_transitions WHERE transition_id=?',(transition_id,)).fetchone();require(row is not None,'transition unavailable')
            workspace=Registry(self.engine).read(row['workspace_id'],viewer=viewer)
            if row['return_request_id'] is not None:
                require(row['return_request_id']==request_id and row['return_hash']==digest(payload),'return already recorded under another request');return json.loads(row['receipt_json'])
            current=checkpoint(self.engine,workspace['branch']);matched=current==workspace['checkpoint']
            result=dict(transition_id=transition_id,workspace_id=workspace['workspace_id'],state='returned' if matched else 'blocked',checkpoint=workspace['checkpoint'],current=current,world_unchanged=matched,
                        reason='Exact world checkpoint preserved.' if matched else 'World changed during destination work; preserve newer world and reconcile explicitly.')
            self.db.execute('UPDATE workspace_transitions SET state=?,return_request_id=?,return_hash=?,receipt_json=? WHERE transition_id=?',(result['state'],request_id,digest(payload),encoded(result),transition_id))
            return result
    def recover(self,viewer=None):
        from ..persistence.artifacts import Artifacts
        from ..engine import Rejected
        artifacts=Artifacts(self.engine).recover();pending=[]
        for row in self.db.execute("SELECT transition_id FROM workspace_transitions WHERE state<>'returned'"):
            try:pending.append(self.read(row[0],viewer=viewer))
            except Rejected:continue
        return {'artifacts':artifacts,'pending':pending}
