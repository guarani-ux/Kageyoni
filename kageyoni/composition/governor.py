from __future__ import annotations
import json, uuid
from copy import deepcopy
from datetime import datetime, timezone
from ..engine import digest, encoded, require, Rejected
from ..persistence.unit_of_work import UnitOfWork
class ProposalError(Rejected):pass

def _now():return datetime.now(timezone.utc).isoformat()
class ResolutionGovernor:
    """Engine-custodied prepare -> exact consume -> commit -> explicit observation."""
    def __init__(self,engine):
        from ..persistence.migrations import install_v11
        install_v11(engine)
        self.engine=engine;self.db=engine.db
    def _basis_hash(self,manifest):
        require(isinstance(manifest,dict) and manifest.get('branch'),'basis manifest required');branch=manifest['branch'];current=[]
        for expected in manifest.get('records',[]):
            row=self.engine.get(branch,expected['record_id']);require(row is not None,'proposal dependency disappeared');require(row['version']==expected['version'],'proposal dependency version changed');require(row.get('updated_event')==expected.get('updated_event'),'proposal dependency event changed');current.append({'record_id':row['id'],'version':row['version'],'updated_event':row.get('updated_event')})
        return digest({'branch':branch,'records':sorted(current,key=lambda r:r['record_id']),'contracts':sorted(manifest.get('contracts',[]),key=lambda x:(x.get('kind',''),x.get('ref','')))})
    def prepare(self,compilation,command,*,basis_manifest):
        require(isinstance(compilation,dict) and compilation.get('runnable') is True,'simulation compilation is not runnable'); require(isinstance(compilation.get('frame_id'),str) and isinstance(compilation.get('slots'),list) and 'admitted_aspect_ids' in compilation and isinstance(compilation.get('verification'),dict) and isinstance(compilation.get('input_dispositions'),dict),'compilation was not produced by the admitted compiler contract'); branch=command.get('branch');require(isinstance(branch,str),'proposal branch required');require(basis_manifest.get('branch')==branch,'basis branch mismatch');current=self.engine.branch(branch)['revision'];require(command.get('expected_revision')==current,'proposal is based on stale branch revision')
        payload={'proposal_id':str(uuid.uuid4()),'branch':branch,'expected_revision':current,'basis_manifest':deepcopy(basis_manifest),'basis_hash':self._basis_hash(basis_manifest),'command_hash':digest(command),'compilation_hash':digest(compilation),'preview':self.engine.apply(deepcopy(command),preview=True),'status':'prepared'}
        require(payload['preview'].get('committed') is False,'preview unexpectedly committed')
        with UnitOfWork(self.db):self.db.execute('INSERT INTO v11_preparations(proposal_id,branch,expected_revision,command_hash,compilation_hash,basis_hash,payload_json,status,payload_hash) VALUES(?,?,?,?,?,?,?,?,?)',(payload['proposal_id'],branch,current,payload['command_hash'],payload['compilation_hash'],payload['basis_hash'],encoded(payload),'prepared',digest(payload)))
        return payload
    def _issued(self,pid):
        row=self.db.execute('SELECT * FROM v11_preparations WHERE proposal_id=?',(pid,)).fetchone();require(row is not None,'proposal was not issued by this engine');return dict(row)
    def commit(self,prepared,compilation,command):
        require(isinstance(prepared,dict) and prepared.get('proposal_id'),'proposal identity required');row=self._issued(prepared['proposal_id']);require(row['status']=='prepared','proposal is not prepared or was already consumed')
        issued=json.loads(row['payload_json']);require(prepared==issued,'caller-supplied preparation differs from engine-custodied preparation');require(digest(command)==row['command_hash'],'proposal command changed after preview');require(digest(compilation)==row['compilation_hash'],'compiled state changed after preview');require(self._basis_hash(issued['basis_manifest'])==row['basis_hash'],'proposal basis changed after preview');branch=row['branch'];require(self.engine.branch(branch)['revision']==row['expected_revision'],'branch changed after preview')
        receipt=self.engine.apply(deepcopy(command),preview=False);require(receipt.get('committed') is True,'engine did not commit proposal');require(receipt['request_id']==command['request_id'],'receipt request mismatch')
        consumed=dict(issued,status='consumed',engine_receipt=receipt)
        try:
            with UnitOfWork(self.db):
                result=self.db.execute("UPDATE v11_preparations SET status='consumed',payload_json=?,payload_hash=?,consumed_at=? WHERE proposal_id=? AND status='prepared'",(encoded(consumed),digest(consumed),_now(),row['proposal_id']))
                require(result.rowcount==1,'preparation consumption lost race')
        except Exception as exc:
            return {'proposal_id':row['proposal_id'],'status':'committed_unverified','engine_receipt':receipt,'verification':{'ok':False,'error':type(exc).__name__,'message':str(exc)},'recovery_required':True,'committed_on_failure':True,'custody_uncertain':True}
        try:
            verification=self.engine.verify()
            if not isinstance(verification,dict) or verification.get('ok') is not True:
                return {'proposal_id':row['proposal_id'],'status':'committed_unverified','engine_receipt':receipt,'verification':verification,'recovery_required':True,'committed_on_failure':True}
        except Exception as exc:
            return {'proposal_id':row['proposal_id'],'status':'committed_unverified','engine_receipt':receipt,'verification':{'ok':False,'error':type(exc).__name__,'message':str(exc)},'recovery_required':True,'committed_on_failure':True}
        return {'proposal_id':row['proposal_id'],'status':'committed','engine_receipt':receipt,'verification':verification}
