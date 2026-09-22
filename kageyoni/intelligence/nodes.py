"""Character bindings reference current permitted world records; no copied canon."""
from uuid import uuid4
import json
from .. import characters
from ..engine import require, digest, encoded
from ..persistence.unit_of_work import UnitOfWork

class Nodes:
    def __init__(self, engine):self.engine=engine;self.db=engine.db
    def bind(self, branch, character_id, request_id, expected_revision, source, viewer=None, node_id=None):
        require(viewer is None,'owner view required to bind nodes')
        require(isinstance(request_id,str) and request_id.strip(),'request_id required')
        require(type(expected_revision) is int,'expected_revision must be an integer')
        require(isinstance(source,dict) and isinstance(source.get('note'),str) and source['note'].strip(),'source note required')
        payload=dict(branch=branch,character_id=character_id,request_id=request_id,
                     expected_revision=expected_revision,source=source,node_id=node_id)
        fingerprint=digest(payload)
        with UnitOfWork(self.db):
            old=self.db.execute('SELECT payload_hash,receipt_json FROM network_events WHERE request_id=?',(request_id,)).fetchone()
            if old:
                require(old[0]==fingerprint,'request key reused with different payload')
                return dict(json.loads(old[1]),replayed=True)
            require(self.engine.branch(branch)['revision']==expected_revision,'stale branch revision')
            characters.read(self.engine,branch,character_id,viewer=None)
            require(not self.db.execute('SELECT 1 FROM node_bindings WHERE branch=? AND character_id=?',(branch,character_id)).fetchone(),'character already bound; read existing node')
            if node_id is None:
                node_id='node:'+uuid4().hex
                self.db.execute("INSERT INTO network_nodes(node_id,kind,identity_revision) VALUES(?,'character',1)",(node_id,))
            else:
                oldnode=self.db.execute('SELECT kind FROM network_nodes WHERE node_id=?',(node_id,)).fetchone()
                require(oldnode and oldnode[0]=='character','character node unavailable')
                # Explicit branch inheritance only for the same world character.
                bindings=self.db.execute('SELECT branch,character_id FROM node_bindings WHERE node_id=?',(node_id,)).fetchall()
                require(bindings and all(r['character_id']==character_id for r in bindings),'node belongs to another character')
                ancestors=set();cur=branch
                while cur is not None:
                    ancestors.add(cur);cur=self.engine.branch(cur)['parent']
                require(any(r['branch'] in ancestors for r in bindings),'binding requires an ancestor branch')
            workspace='world:'+branch
            self.db.execute("INSERT OR IGNORE INTO network_workspaces VALUES(?,'world',?,'1')",(workspace,branch))
            self.db.execute('INSERT INTO node_bindings VALUES(?,?,?,?,1,?)',(node_id,workspace,branch,character_id,encoded(source)))
            receipt=dict(node_interface='1',node_id=node_id,branch=branch,character_id=character_id,
                         workspace_id=workspace,profile_revision=1,world_revision=expected_revision,replayed=False)
            self.db.execute('INSERT INTO network_events(request_id,payload_hash,node_id,branch,kind,profile_revision,payload_json,receipt_json) VALUES(?,?,?,?,?,1,?,?)',
                            (request_id,fingerprint,node_id,branch,'node_bound',encoded(payload),encoded(receipt)))
            return receipt
    def read(self, branch, character_id, viewer=None):
        # Establish visibility before node lookup; hidden versus nonexistent returns the same world error.
        world=characters.read(self.engine,branch,character_id,viewer=viewer)
        row=self.db.execute('SELECT * FROM node_bindings WHERE branch=? AND character_id=?',(branch,character_id)).fetchone()
        require(row is not None,'character has no node in this branch')
        result=dict(node_interface='1',node_id=row['node_id'],branch=branch,workspace_id=row['workspace_id'],
                    profile_revision=row['profile_revision'],world=world)
        if viewer is None:
            result['source']=json.loads(row['source_json'])
            result['operational_history']=[dict(sequence=r['sequence'],kind=r['kind'],profile_revision=r['profile_revision'],receipt=json.loads(r['receipt_json']))
                for r in self.db.execute('SELECT * FROM network_events WHERE node_id=? AND branch=? ORDER BY sequence',(row['node_id'],branch))]
        return result
    def list(self, branch, viewer=None):
        visible={r['id']:r for r in self.engine.context(branch,viewer=viewer)['records'] if r['domain']=='character'}
        return [dict(node_id=r['node_id'],character_id=r['character_id'],name=visible[r['character_id']]['data']['name'],profile_revision=r['profile_revision'])
                for r in self.db.execute('SELECT * FROM node_bindings WHERE branch=? ORDER BY character_id',(branch,)) if r['character_id'] in visible]

def verify_nodes(engine):
    """Validate operational provenance independently of the world event ledger."""
    db=engine.db
    if not db.execute("SELECT 1 FROM engine_versions WHERE component='node_interface'").fetchone():
        return {'installed':False}
    import hashlib
    from ..persistence.migrations import MIGRATION
    row=db.execute('SELECT checksum FROM migration_checks WHERE version=9').fetchone()
    require(row and row[0]==hashlib.sha256(MIGRATION.read_bytes()).hexdigest(),'node migration checksum mismatch')
    require(db.execute("SELECT version FROM engine_versions WHERE component='node_interface'").fetchone()[0]=='1','unsupported node interface')
    require(not db.execute('PRAGMA foreign_key_check').fetchall(),'node foreign key failure')
    count=0
    for row in db.execute('SELECT b.*,w.branch AS workspace_branch FROM node_bindings b JOIN network_workspaces w USING(workspace_id)'):
        require(row['branch']==row['workspace_branch'],'node workspace branch mismatch')
        require(row['profile_revision']==1,'unsupported node profile revision')
        history=db.execute('SELECT * FROM network_events WHERE node_id=? AND branch=? ORDER BY sequence',(row['node_id'],row['branch'])).fetchall()
        require(len(history)==1,'binding history mismatch')
        event=history[0];payload=json.loads(event['payload_json']);receipt=json.loads(event['receipt_json'])
        require(event['kind']=='node_bound' and event['profile_revision']==1,'node event kind or revision mismatch')
        require(digest(payload)==event['payload_hash'],'node event payload hash mismatch')
        require(payload['request_id']==event['request_id'] and payload['character_id']==row['character_id'] and payload['branch']==row['branch'],'node event identity mismatch')
        require(encoded(payload['source'])==row['source_json'],'node source mismatch')
        expected=dict(node_interface='1',node_id=row['node_id'],branch=row['branch'],character_id=row['character_id'],workspace_id=row['workspace_id'],profile_revision=1,world_revision=payload['expected_revision'],replayed=False)
        require(receipt==expected,'node receipt mismatch')
        count+=1
    require(count==db.execute('SELECT count(*) FROM network_events').fetchone()[0],'orphan node history')
    return {'installed':True,'bindings':count,'interface':'1'}
