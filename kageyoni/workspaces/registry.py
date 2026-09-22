"""Separate operational destinations reuse node identities without copying canon."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from ..engine import require, digest, encoded
from ..intelligence.nodes import Nodes
from ..persistence.unit_of_work import UnitOfWork
from .contracts import KINDS, text, finite, checkpoint

class Registry:
    def __init__(self, engine):self.engine=engine;self.db=engine.db
    def _installed(self):
        require(self.db.execute("SELECT 1 FROM engine_versions WHERE component='workspace_interface' AND version='1'").fetchone(),'workspace interface not installed')
    def open(self, branch, character_id, kind, request_id, config=None, viewer=None, source_ids=None):
        self._installed();text(request_id,'request id');require(kind in KINDS,'unsupported workspace kind')
        config={} if config is None else config;require(isinstance(config,dict),'workspace config must be an object');finite(config)
        require(source_ids is None or (isinstance(source_ids,list) and len(source_ids)<=500 and all(isinstance(v,str) for v in source_ids)),'invalid workspace source IDs')
        payload=dict(branch=branch,character_id=character_id,kind=kind,request_id=request_id,config=config,viewer=viewer,source_ids=source_ids)
        with UnitOfWork(self.db):
            old=self.db.execute('SELECT workspace_id,payload_hash FROM operational_workspaces WHERE request_id=?',(request_id,)).fetchone()
            if old:
                result=self.read(old['workspace_id'],viewer=viewer);require(old['payload_hash']==digest(payload),'workspace request conflict');return result
            node=Nodes(self.engine).read(branch,character_id,viewer=viewer)
            projected=self.engine.context(branch,viewer=viewer)['records']
            records={r['id']:r for r in projected}
            if source_ids is not None:require(set(source_ids)<=set(records),'workspace source unavailable')
            selected=[deepcopy(r) for r in projected if source_ids is None or r['id'] in source_ids]
            refs=[]
            for row in selected:
                full=self.engine.get(branch,row['id']);refs.append(dict(domain=row['domain'],id=row['id'],record_revision=full['version'],snapshot_hash=digest(full)))
                for key in ('evidence','audience','updated_event'):row.pop(key,None)
            wid='workspace:'+uuid4().hex
            self.db.execute('INSERT INTO operational_workspaces(workspace_id,request_id,payload_hash,node_id,character_id,branch,kind,viewer,config_json,checkpoint_json,context_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (wid,request_id,digest(payload),node['node_id'],character_id,branch,kind,viewer,encoded(config),encoded(checkpoint(self.engine,branch)),encoded({'records':selected,'source_refs':refs})))
            return self.read(wid,viewer=viewer)
    def read(self, workspace_id, viewer=None):
        self._installed()
        row=self.db.execute('SELECT * FROM operational_workspaces WHERE workspace_id=?',(workspace_id,)).fetchone();require(row is not None,'workspace unavailable')
        value=dict(row)
        Nodes(self.engine).read(value['branch'],value['character_id'],viewer=viewer)
        if viewer is not None:
            require(value['viewer']==viewer,'workspace unavailable')
            visible={r['id']:r for r in self.engine.context(value['branch'],viewer=viewer)['records']}
            saved=json.loads(value['context_json'])
            require(all(ref['id'] in visible and ref['domain']==visible[ref['id']]['domain'] for ref in saved['source_refs']),'workspace source unavailable')
            for original in saved['records']:
                projected=deepcopy(visible[original['id']])
                for key in ('evidence','audience','updated_event'):projected.pop(key,None)
                require(projected==original,'workspace context requires explicit revalidation')
        for field in ('config','checkpoint','context'):value[field]=json.loads(value.pop(field+'_json'))
        value.pop('payload_hash');return value
    def list(self, branch, viewer=None):
        from ..engine import Rejected
        result=[]
        for row in self.db.execute('SELECT workspace_id FROM operational_workspaces WHERE branch=? ORDER BY created_at,workspace_id',(branch,)):
            try:result.append(self.read(row[0],viewer=viewer))
            except Rejected:continue
        return result

def verify_workspaces(engine):
    if not engine.db.execute("SELECT 1 FROM engine_versions WHERE component='workspace_interface'").fetchone():return {'installed':False}
    from ..resources import schema_path
    migration=schema_path('migration_014.sql')
    row=engine.db.execute('SELECT checksum FROM migration_checks WHERE version=14').fetchone()
    require(row and row[0]==hashlib.sha256(migration.read_bytes()).hexdigest(),'workspace migration checksum mismatch')
    require(not engine.db.execute('PRAGMA foreign_key_check').fetchall(),'workspace foreign key failure')
    from ..persistence.artifacts import Artifacts
    artifacts=Artifacts(engine).verify()
    for row in engine.db.execute('SELECT * FROM document_drafts'):
        result=json.loads(row['result_json']);a=engine.db.execute('SELECT digest FROM artifacts WHERE artifact_id=?',(row['artifact_id'],)).fetchone()
        require(a and a[0]==result['artifact']['digest'],'draft artifact mismatch')
    return {'installed':True,'workspaces':engine.db.execute('SELECT count(*) FROM operational_workspaces').fetchone()[0], 'artifacts':artifacts,'interface':'1'}
