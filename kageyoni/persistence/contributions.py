"""Immutable bounded execution receipts and JSON artifacts in the same database.

V2 has no external effects. Keeping these small JSON artifacts in SQLite gives
an atomic receipt/artifact boundary. General filesystem artifacts remain V5.
"""
from uuid import uuid4
import json
from ..engine import require, digest, encoded, Rejected
from .unit_of_work import UnitOfWork

class Contributions:
    def __init__(self, engine):
        self.engine=engine
        self.db=engine.db
    def _installed(self):
        require(self.db.execute("SELECT 1 FROM engine_versions WHERE component='contribution_interface' AND version='1'").fetchone(),
                'contribution interface not installed; run methods-init')
    def run(self, branch, character_id, request_id, task, viewer=None, workspace_id=None, prepared=None):
        self._installed()
        require(isinstance(request_id,str) and request_id.strip(),'request_id required')
        from ..intelligence.expression import Expression
        from ..intelligence.nodes import Nodes
        payload=dict(branch=branch,character_id=character_id,request_id=request_id,task=task,viewer=viewer,workspace_id=workspace_id,prepared=prepared)
        try:
            serialized=encoded(payload)
        except (ValueError,TypeError,RecursionError,OverflowError):
            raise Rejected('contribution request must be finite JSON') from None
        require(len(serialized)<=2000000,'contribution request exceeds bounded size')
        fingerprint=digest(payload)
        with UnitOfWork(self.db):
            old=self.db.execute('SELECT contribution_id,request_hash FROM contributions WHERE request_id=?',(request_id,)).fetchone()
            if old:
                # Visibility is checked before returning an old receipt or request conflict.
                visible=self.read(branch,old['contribution_id'],viewer=viewer)
                require(old['request_hash']==fingerprint,'request key reused with different payload')
                return dict(visible['receipt'],replayed=True)
            node=Nodes(self.engine).read(branch,character_id,viewer=viewer)
            workspace_id=workspace_id or node['workspace_id']
            require(workspace_id==node['workspace_id'],'workspace unavailable')
            result=Expression(self.engine).execute(branch,character_id,task,viewer=viewer,workspace_id=workspace_id,prepared=prepared)
            require(result.get('phase') in ('completed','waiting','blocked'),'invalid expression disposition')
            artifact=result.get('artifact')
            if result['phase']=='completed':
                require(result.get('checks_passed') is True and result.get('objective_scope')=='registered_operation' and result.get('task_objective')=='unresolved','completion requires checked operation and bounded objective')
                require(isinstance(artifact,dict) and artifact.get('digest')==digest(artifact.get('content')),'completed expression requires exact artifact')
            elif artifact is not None:
                require(isinstance(artifact,dict) and artifact.get('digest')==digest(artifact.get('content')),'invalid partial artifact')
            cid='contribution:'+uuid4().hex
            receipt=dict(contribution_interface='1',contribution_id=cid,request_id=request_id,node_id=node['node_id'],branch=branch,
                         workspace_id=workspace_id,phase=result['phase'],outcome=result['outcome'],result_digest=digest(result),
                         artifact_digest=artifact['digest'] if artifact is not None else None,
                         storage='sqlite-json',execution_mode='code' if result['phase']=='completed' else 'not_executed',replayed=False)
            self.db.execute('INSERT INTO contributions(contribution_id,request_id,branch,node_id,workspace_id,viewer,request_json,request_hash,result_json,result_hash,receipt_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (cid,request_id,branch,node['node_id'],workspace_id,viewer,encoded(payload),fingerprint,encoded(result),digest(result),encoded(receipt)))
            return receipt
    def read(self, branch, contribution_id, viewer=None):
        with UnitOfWork(self.db):
            return self._read(branch, contribution_id, viewer=viewer)
    def _read(self, branch, contribution_id, viewer=None):
        self._installed()
        row=self.db.execute('SELECT * FROM contributions WHERE branch=? AND contribution_id=?',(branch,contribution_id)).fetchone()
        require(row is not None,'contribution unavailable')
        request=json.loads(row['request_json']);result=json.loads(row['result_json'])
        from ..intelligence.nodes import Nodes
        Nodes(self.engine).read(branch,request['character_id'],viewer=viewer)
        if viewer is not None:
            require(row['viewer']==viewer,'contribution unavailable')
            # Fail closed if any input is now hidden/stale. Owner inspection
            # preserves historical results regardless of applicability today.
            from ..intelligence.expression import Expression
            try:
                current=Expression(self.engine).prepare(branch,request['character_id'],request['task'],viewer=viewer,workspace_id=row['workspace_id'])
                old_binding=result.get('binding',{})
                new_binding=current.get('binding',{})
                if old_binding.get('sources'):
                    require(old_binding.get('sources')==new_binding.get('sources'),'contribution unavailable')
                if old_binding.get('methods'):
                    require(old_binding.get('methods')==new_binding.get('methods'),'contribution unavailable')
                require(old_binding.get('lessons',[])==new_binding.get('lessons',[]),'contribution unavailable')
                require(old_binding.get('historical_sources',[])==new_binding.get('historical_sources',[]),'contribution unavailable')
                # Direct visible-ID check also covers preparation that returns a blocked packet.
                visible={r['id']:r for r in self.engine.context(branch,viewer=viewer)['records']}
                for ref in old_binding.get('sources',[])+old_binding.get('historical_sources',[]):
                    current_record=visible.get(ref.get('id'))
                    require(current_record and current_record['domain']==ref.get('domain'),'contribution unavailable')
                expected_phase='ready' if result.get('phase')=='completed' else result.get('phase')
                require(current.get('phase')==expected_phase,'contribution unavailable')
            except (Rejected,KeyError,TypeError):
                raise Rejected('contribution unavailable') from None
        _check_row(row)
        return {'receipt':json.loads(row['receipt_json']),'result':result}
    def list(self, branch, viewer=None):
        self._installed()
        result=[]
        for row in self.db.execute('SELECT contribution_id FROM contributions WHERE branch=? ORDER BY created_at,contribution_id',(branch,)):
            try:result.append(self.read(branch,row[0],viewer=viewer)['receipt'])
            except Rejected:continue
        return result

def _check_row(row):
    request=json.loads(row['request_json']);result=json.loads(row['result_json']);receipt=json.loads(row['receipt_json'])
    require(digest(request)==row['request_hash'],'contribution request hash mismatch')
    require(digest(result)==row['result_hash'],'contribution result hash mismatch')
    require(receipt['contribution_id']==row['contribution_id'] and receipt['request_id']==row['request_id'] and request['request_id']==row['request_id'],'contribution identity mismatch')
    require(receipt['branch']==row['branch']==request['branch'] and receipt['node_id']==row['node_id'] and receipt['workspace_id']==row['workspace_id'],'contribution scope mismatch')
    require(row['viewer']==request['viewer'],'contribution viewer mismatch')
    binding=result.get('binding',{})
    require(binding.get('node_id')==row['node_id'] and binding.get('branch')==row['branch'] and binding.get('workspace_id')==row['workspace_id'] and binding.get('viewer')==row['viewer'],'contribution binding mismatch')
    require(binding.get('character_id')==request['character_id'] and binding.get('task_digest')==digest(request['task']),'contribution task binding mismatch')
    require(receipt['phase']==result['phase'] and receipt['outcome']==result['outcome'],'contribution disposition mismatch')
    require(receipt['result_digest']==row['result_hash'],'contribution receipt digest mismatch')
    artifact=result.get('artifact')
    require(artifact is None or artifact.get('digest')==digest(artifact.get('content')),'contribution artifact mismatch')
    require(receipt['artifact_digest']==(artifact['digest'] if artifact is not None else None),'contribution artifact receipt mismatch')
    require(result['phase']!='completed' or (artifact is not None and result.get('checks_passed') is True and result.get('objective_scope')=='registered_operation' and result.get('task_objective')=='unresolved'),'invalid completed operation')

def verify_contributions(engine):
    db=engine.db
    if not db.execute("SELECT 1 FROM engine_versions WHERE component='contribution_interface'").fetchone():return {'installed':False}
    import hashlib
    from .migrations import CONTRIBUTION_MIGRATION
    row=db.execute('SELECT checksum FROM migration_checks WHERE version=11').fetchone()
    require(row and row[0]==hashlib.sha256(CONTRIBUTION_MIGRATION.read_bytes()).hexdigest(),'contribution migration checksum mismatch')
    require(db.execute("SELECT version FROM engine_versions WHERE component='contribution_interface'").fetchone()[0]=='1','unsupported contribution interface')
    rows=db.execute('SELECT * FROM contributions').fetchall()
    for row in rows:_check_row(row)
    return {'installed':True,'contributions':len(rows),'interface':'1'}
