"""Portable immutable byte artifacts, with recoverable content-addressed files."""
import hashlib
import os
from pathlib import Path
from uuid import uuid4
from ..engine import require, digest
from .unit_of_work import UnitOfWork

class Artifacts:
    def __init__(self, engine):
        self.engine=engine;self.db=engine.db;self.root=Path(engine.path).with_suffix('.artifacts')
    def _scope(self, workspace_id, viewer):
        row=self.db.execute('SELECT workspace_id FROM operational_workspaces WHERE workspace_id=?',(workspace_id,)).fetchone()
        if row:
            from ..workspaces.registry import Registry
            return Registry(self.engine).read(workspace_id,viewer=viewer)
        row=self.db.execute('SELECT branch FROM network_workspaces WHERE workspace_id=?',(workspace_id,)).fetchone()
        require(row is not None,'artifact workspace unavailable')
        self.engine.context(row[0],viewer=viewer)
    def _meta(self,row):
        return {**{k:row[k] for k in ('artifact_id','workspace_id','digest','media_type','size')},'path':str((self.root/'objects'/row['digest']).resolve()),'relative_path':'objects/'+row['digest']}
    @staticmethod
    def _audience(viewer, recipient):
        """Choose immutable audience without changing caller authorization."""
        if recipient is None:return viewer
        from ..workspaces.contracts import text
        text(recipient,'artifact recipient',1024)
        require(len(recipient)<=1024,'artifact recipient too long')
        require(viewer is None or viewer==recipient,'only owner may choose another artifact recipient')
        return recipient
    def _materialize(self,row,replace=False):
        blob=bytes(row['content']);require(hashlib.sha256(blob).hexdigest()==row['digest'] and len(blob)==row['size'],'artifact bytes corrupt')
        path=self.root/'objects'/row['digest']
        require(not self.root.is_symlink() and not path.parent.is_symlink(),'artifact root unsafe')
        if path.exists():
            require(path.is_file() and not path.is_symlink(),'artifact path unsafe')
            if hashlib.sha256(path.read_bytes()).hexdigest()==row['digest']:return
            require(replace,'artifact file corrupt; recover required')
        path.parent.mkdir(parents=True,exist_ok=True)
        require(not self.root.is_symlink() and not path.parent.is_symlink(),'artifact root unsafe')
        temporary=path.parent/('.stage-'+uuid4().hex)
        try:
            with temporary.open('xb') as handle:handle.write(blob);handle.flush();os.fsync(handle.fileno())
            os.replace(temporary,path)
        finally:
            if temporary.exists():temporary.unlink()
    def put(self, content, media_type, request_id, *, workspace_id, viewer=None, recipient=None):
        from ..workspaces.contracts import text
        text(media_type,'media type',200);text(request_id,'request id');require(type(content) in (bytes,str),'artifact must be bytes or text')
        audience=self._audience(viewer,recipient)
        blob=content.encode('utf-8') if isinstance(content,str) else content
        require(len(blob)<=10000000,'artifact exceeds 10 MB limit');sha=hashlib.sha256(blob).hexdigest()
        payload=dict(workspace_id=workspace_id,viewer=viewer,media_type=media_type,digest=sha,size=len(blob))
        # Omitted/None keeps historical request hashes exactly. An explicit
        # recipient is part of retry identity even when it equals the caller.
        if recipient is not None:payload['recipient']=recipient
        with UnitOfWork(self.db):
            self._scope(workspace_id,viewer)
            old=self.db.execute('SELECT * FROM artifacts WHERE request_id=?',(request_id,)).fetchone()
            if old:require(old['payload_hash']==digest(payload),'artifact request conflict');row=old
            else:
                aid='artifact:'+uuid4().hex
                self.db.execute('INSERT INTO artifacts(artifact_id,workspace_id,viewer,request_id,payload_hash,digest,media_type,size,content) VALUES(?,?,?,?,?,?,?,?,?)',(aid,workspace_id,audience,request_id,digest(payload),sha,media_type,len(blob),blob))
                row=self.db.execute('SELECT * FROM artifacts WHERE artifact_id=?',(aid,)).fetchone()
        self._materialize(row);return self._meta(row)
    def read(self, artifact_id, viewer=None):
        # Metadata and body stay in one existing/native UnitOfWork snapshot.
        # This does not yet implement Source36 control/derivation resolution.
        with UnitOfWork(self.db):
            metadata=self.db.execute('SELECT artifact_id,workspace_id,viewer,digest,media_type,size FROM artifacts WHERE artifact_id=?',(artifact_id,)).fetchone()
            require(metadata is not None,'artifact unavailable')
            self._scope(metadata['workspace_id'],viewer)
            if viewer is not None:require(metadata['viewer']==viewer,'artifact unavailable')
            # Future fixed control metadata guard belongs HERE, before content.
            row=self.db.execute('SELECT * FROM artifacts WHERE artifact_id=?',(artifact_id,)).fetchone()
            require(row is not None and all(row[key]==metadata[key] for key in metadata.keys()),'artifact metadata changed during read')
            self._materialize(row)
            return dict(self._meta(row),content=bytes(row['content']))
    def manifest(self):return [self._meta(row) for row in self.db.execute('SELECT * FROM artifacts ORDER BY artifact_id')]
    def verify(self):
        require(not self.root.is_symlink() and not (self.root/'objects').is_symlink(),'artifact root unsafe')
        count=missing=0
        for row in self.db.execute('SELECT * FROM artifacts'):
            blob=bytes(row['content']);require(len(blob)==row['size'] and hashlib.sha256(blob).hexdigest()==row['digest'],'artifact bytes corrupt')
            path=self.root/'objects'/row['digest']
            if path.exists():require(path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==row['digest'],'artifact file corrupt')
            else:missing+=1
            count+=1
        return {'artifacts':count,'pending_materialization':missing}
    def recover(self):
        rows=self.db.execute('SELECT * FROM artifacts').fetchall()
        for row in rows:self._materialize(row,replace=True)
        return self.verify()
