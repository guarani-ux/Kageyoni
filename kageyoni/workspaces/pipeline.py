"""Durable bounded DAG with intent-before-effect and explicit recovery."""
import hashlib,json,os
from pathlib import Path
from uuid import uuid4
from ..engine import require,digest,encoded
from ..persistence.unit_of_work import UnitOfWork
from .repository import Repository,safe_path

class Pipelines:
    def __init__(self,engine):self.engine=engine;self.db=engine.db
    def _owner(self,viewer):Repository(self.engine)._owner(viewer)
    def _save(self,p,event):
        with UnitOfWork(self.db):
            self.db.execute('UPDATE pipeline_runs SET payload_json=?,payload_hash=? WHERE pipeline_id=?',(encoded(p),digest(p),p['pipeline_id']))
            self.db.execute('INSERT INTO pipeline_events(pipeline_id,payload_json,payload_hash) VALUES(?,?,?)',(p['pipeline_id'],encoded(event),digest(event)))
    def read(self,branch,pipeline_id,viewer=None):
        self._owner(viewer);r=self.db.execute('SELECT * FROM pipeline_runs WHERE branch=? AND pipeline_id=?',(branch,pipeline_id)).fetchone();require(r is not None,'pipeline unavailable');p=json.loads(r['payload_json']);require(digest(p)==r['payload_hash'],'pipeline integrity failure');return p
    def _phase(self,p):
        states=[t['phase'] for t in p['tasks'].values()]
        if 'executing' in states:return 'reconcile_required'
        if 'recoverable' in states:return 'waiting'
        if any(t.get('current_verification',{}).get('status')=='diverged' for t in p['tasks'].values()):return 'reconcile_required'
        return 'completed' if all(s=='completed' for s in states) else 'failed' if 'failed' in states else 'waiting'
    def run(self,branch,pipeline_id,max_steps=10,timeout_seconds=30,viewer=None):
        p=self.read(branch,pipeline_id,viewer)
        mediation=None
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v11_operations'").fetchone():
            from ..v11.integration import begin_domain_operation
            mediation=begin_domain_operation(self.engine,scope='pipeline',objective='Run pipeline '+pipeline_id,requirement_version='pipeline-run/1',basis={'branch':branch,'revision':self.engine.branch(branch)['revision'],'pipeline_id':pipeline_id,'pipeline_phase':p.get('phase')})
        return self._run_existing(branch,p,max_steps,timeout_seconds,mediation)
    def _run_existing(self,branch,p,max_steps,timeout_seconds,mediation):
        # The complete inherited pipeline implementation remains supplied by the preserved v11 baseline.
        # This method is intentionally not a replacement implementation; the release assembly overlays
        # the compatibility guard above onto that exact baseline source.
        raise RuntimeError('release assembly must overlay this compatibility guard onto preserved pipeline source')
