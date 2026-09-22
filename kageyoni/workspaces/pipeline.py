"""Durable bounded DAG with intent-before-effect and explicit recovery.

The owner authorizes filesystem roots. Writes create new files only. After an
interruption, reconciliation inspects exact bytes before any possible retry.
"""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from ..engine import require, digest, encoded
from ..persistence.unit_of_work import UnitOfWork
from .repository import Repository, safe_path


class Pipelines:
    def __init__(self,engine):self.engine=engine;self.db=engine.db
    def _owner(self,viewer):Repository(self.engine)._owner(viewer)
    def _save(self,p,event):
        with UnitOfWork(self.db):
            self.db.execute('UPDATE pipeline_runs SET payload_json=?,payload_hash=? WHERE pipeline_id=?',(encoded(p),digest(p),p['pipeline_id']))
            self.db.execute('INSERT INTO pipeline_events(pipeline_id,payload_json,payload_hash) VALUES(?,?,?)',(p['pipeline_id'],encoded(event),digest(event)))
    def read(self,branch,pipeline_id,viewer=None):
        self._owner(viewer)
        r=self.db.execute('SELECT * FROM pipeline_runs WHERE branch=? AND pipeline_id=?',(branch,pipeline_id)).fetchone()
        require(r is not None,'pipeline unavailable');p=json.loads(r['payload_json'])
        require(digest(p)==r['payload_hash'],'pipeline integrity failure');return p
    def create(self,branch,request_id,tasks,viewer=None):
        self._owner(viewer);self.engine.branch(branch)
        require(isinstance(tasks,list) and 0<len(tasks)<=50,'bounded tasks required')
        require(isinstance(request_id,str) and request_id,'request_id required')
        ids=[t['id'] for t in tasks];require(len(set(ids))==len(ids),'duplicate task')
        graph={}
        for t in tasks:
            require(t['kind'] in ('repository_check','write_file','manual','artifact_read'),'unknown task kind')
            deps=t.get('dependencies',[]);graph[t['id']]=[]
            for dep in deps:
                require(dep['task_id'] in ids and dep['task_id']!=t['id'],'dependency missing')
                require(dep['type'] in ('DEPENDS_ON','REQUIRES','AFTER','USES'),'unknown dependency type')
                graph[t['id']].append(dep['task_id'])
            if t['kind']=='write_file':
                c=t['config'];safe_path(c['root'],c['path'])
                if 'content_from' in c:
                    require('content' not in c and c['content_from'] in graph[t['id']],'content source must be a declared blocking dependency')
                    require(isinstance(c.get('expected_sha256'),str) and len(c['expected_sha256'])==64,'expected output digest required')
                else:
                    require(isinstance(c['content'],str) and len(c['content'])<=1_000_000,'bounded content required')
                    require(hashlib.sha256(c['content'].encode()).hexdigest()==c['expected_sha256'],'invalid artifact digest')
        visited=set()
        def visit(node,trail):
            require(node not in trail,'dependency cycle')
            if node in visited:return
            for dep in graph[node]:visit(dep,trail+[node])
            visited.add(node)
        for key in graph:visit(key,[])
        request=dict(tasks=tasks)
        old=self.db.execute('SELECT * FROM pipeline_runs WHERE request_id=?',(request_id,)).fetchone()
        if old:
            require(old['branch']==branch and old['request_hash']==digest(request),'request conflict');return self.read(branch,old['pipeline_id'])
        p=dict(pipeline_id='pipeline:'+uuid4().hex,branch=branch,phase='ready',origin_database=str(Path(self.engine.path).resolve()),versions={r['component']:r['version'] for r in self.db.execute('SELECT component,version FROM engine_versions')},tasks={t['id']:dict(t,phase='pending',attempts=[]) for t in tasks})
        with UnitOfWork(self.db):self.db.execute('INSERT INTO pipeline_runs VALUES(?,?,?,?,?,?)',(p['pipeline_id'],branch,request_id,digest(request),encoded(p),digest(p)))
        return p
    def _phase(self,p):
        states=[t['phase'] for t in p['tasks'].values()]
        if 'executing' in states: return 'reconcile_required'
        if 'recoverable' in states: return 'waiting'
        if any(t.get('current_verification',{}).get('status')=='diverged' for t in p['tasks'].values()):
            return 'reconcile_required'
        return 'completed' if all(s=='completed' for s in states) else 'failed' if 'failed' in states else 'waiting'
    def _audit_completed_outputs(self,p):
        """Recheck present external bytes without erasing historical completion."""
        changed=False
        for key,t in p['tasks'].items():
            if t['kind']!='write_file' or t['phase']!='completed': continue
            c=t.get('resolved_config',t['config']);path=safe_path(c['root'],c['path'])
            status='verified' if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==c['expected_sha256'] else 'diverged'
            detail={'status':status,'path':str(path),'expected_sha256':c['expected_sha256']}
            if status=='diverged': detail['reason']='completed output is missing or differs from recorded bytes'
            if t.get('current_verification')!=detail: t['current_verification']=detail;changed=True
        return changed
    def run(self,branch,pipeline_id,max_steps=10,timeout_seconds=30,viewer=None):
        p=self.read(branch,pipeline_id,viewer)
        from ..persistence.migrations import install_v11
        from ..v11.integration import begin_domain_operation
        install_v11(self.engine)
        mediation=begin_domain_operation(self.engine,scope='pipeline',objective='Run pipeline '+pipeline_id,requirement_version='pipeline-run/1',basis={'branch':branch,'revision':self.engine.branch(branch)['revision'],'pipeline_id':pipeline_id,'pipeline_phase':p.get('phase')})
        current_versions={r['component']:r['version'] for r in self.db.execute('SELECT component,version FROM engine_versions') if not r['component'].startswith('v11_')}
        recorded_versions={k:v for k,v in p['versions'].items() if not k.startswith('v11_')}
        require(recorded_versions==current_versions,'workflow component versions changed; migration/review required')
        require(type(max_steps) is int and 0<max_steps<=50,'step budget out of range')
        require(0<timeout_seconds<=60,'timeout out of range')
        require(not any(t['phase'] in ('executing','recoverable') for t in p['tasks'].values()),'reconcile interrupted effects before resuming')
        require(p.get('origin_database')==str(Path(self.engine.path).resolve()),'relocated pipeline requires explicit root rebind')
        if self._audit_completed_outputs(p):
            p['phase']=self._phase(p);self._save(p,dict(event='current_output_audit',phase=p['phase']))
        if p['phase']=='reconcile_required': return p
        # v11 liveness: pre-intent destination waits are re-evaluated on every run.
        revived=[]
        for key,t in p['tasks'].items():
            if t['kind']=='write_file' and t['phase']=='waiting' and not t.get('attempts') and 'destination exists before intent' in t.get('resume_condition',''):
                c=t.get('resolved_config',t['config']);path=safe_path(c['root'],c['path'])
                if not path.exists():
                    t['phase']='pending';t.pop('resume_condition',None);revived.append(key)
        if revived:
            p['phase']=self._phase(p);self._save(p,dict(event='pre_intent_wait_released',tasks=revived))
        count=0;order=[];seen=set()
        def ordered(key):
            if key in seen:return
            seen.add(key)
            for dep in p['tasks'][key].get('dependencies',[]):ordered(dep['task_id'])
            order.append(key)
        for key in p['tasks']:ordered(key)
        for key in order:
            t=p['tasks'][key]
            if count>=max_steps:break
            if t['phase'] not in ('pending','failed'):continue
            if any(p['tasks'][d['task_id']]['phase']!='completed' for d in t.get('dependencies',[])):continue
            if t['kind']=='manual':
                if t['phase']=='pending':t['phase']='waiting';t['resume_condition']='owner supplies observed result'
                continue
            if t['kind']=='write_file':
                c=dict(t['config'])
                if 'content_from' in c:
                    value=p['tasks'][c['content_from']].get('result')
                    if not isinstance(value,str) or len(value)>1_000_000 or hashlib.sha256(value.encode()).hexdigest()!=c['expected_sha256']:
                        t['phase']='failed';t['failure_reason']='upstream output does not match declared artifact';continue
                    c['content']=value
                t['resolved_config']=c
                path=safe_path(c['root'],c['path'])
                if path.exists():
                    t['phase']='waiting';t['resume_condition']='destination exists before intent; choose a new destination';continue
            count+=1;attempt=dict(number=len(t['attempts'])+1,phase='intent');t['attempts'].append(attempt)
            t['phase']='executing';p['phase']='running';self._save(p,dict(task_id=key,event='intent',attempt=attempt['number'],config_digest=digest(t['config'])))
            try:
                if t['kind']=='repository_check':
                    result=Repository(self.engine).check(branch,t['config']['candidate_id'],timeout_seconds=timeout_seconds)
                    require(result['phase']=='checked','repository checks failed')
                    value=dict(candidate_id=result['candidate_id'],digest=result['candidate_digest'])
                elif t['kind']=='artifact_read':
                    from ..persistence.artifacts import Artifacts
                    artifact=Artifacts(self.engine).read(t['config']['artifact_id'])
                    if t['config'].get('composition_id'):
                        from ..intelligence.network import Network
                        composition=Network(self.engine).read_composition(branch,t['config']['composition_id'])
                        require(composition['artifact']['artifact_id']==artifact['artifact_id'] and composition['artifact']['digest']==artifact['digest'],'collective artifact identity mismatch')
                        attempt['composition_id']=t['config']['composition_id']
                    require(artifact['digest']==t['config']['expected_sha256'],'upstream artifact changed')
                    value=artifact['content'].decode('utf-8')
                else:
                    c=t['resolved_config'];path=safe_path(c['root'],c['path']);require(Path(c['root']).is_dir(),'authorized root missing')
                    if self.db.execute("SELECT 1 FROM engine_versions WHERE component='operations_interface'").fetchone():
                        from ..operations import Operations
                        check=Operations(self.engine).check_artifact('pipeline.write_file',c['content'].encode(),c.get('max_bytes',1_000_000),c['expected_sha256'])
                        require(check['accepted'],'active artifact policy rejected output')
                        attempt['policy_check']=check
                    else:require(len(c['content'].encode())<=c.get('max_bytes',1_000_000),'artifact size limit')
                    path.parent.mkdir(parents=True,exist_ok=True)
                    # O_EXCL makes a preexisting effect an explicit conflict, never overwrite.
                    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                    with os.fdopen(fd,'wb') as stream:stream.write(c['content'].encode());stream.flush();os.fsync(stream.fileno())
                    self._after_effect(p,key)
                    require(hashlib.sha256(path.read_bytes()).hexdigest()==c['expected_sha256'],'written artifact differs')
                    value=dict(path=str(path),sha256=c['expected_sha256'])
                t.update(phase='completed',result=value);attempt.update(phase='completed',result=value)
                if t['kind']=='write_file':
                    t['current_verification']={'status':'verified','path':value['path'],'expected_sha256':value['sha256']}
            except Exception as error:
                # A write may have happened before the exception: force reconciliation.
                if t['kind']=='write_file' and safe_path(t['config']['root'],t['config']['path']).exists():
                    t['phase']='executing';attempt.update(phase='uncertain',error=str(error))
                else:t['phase']='failed';attempt.update(phase='failed',error=str(error))
            p['phase']=self._phase(p);self._save(p,dict(task_id=key,event=t['phase'],attempt=attempt['number']))
            if t['phase']=='executing':break
        p['phase']=self._phase(p)
        if count>=max_steps and p['phase']!='completed':p['stop_reason']='step budget exhausted; resume run'
        self._save(p,dict(event='run_stopped',phase=p['phase'],executed=count))
        if p['phase']=='completed':
            from ..v11.integration import complete_domain_operation
            complete_domain_operation(self.engine,mediation,evidence_type='pipeline-result',evidence_ref=pipeline_id,outcome={'pipeline_id':pipeline_id,'phase':'completed','tasks':sorted(p['tasks'])},verification={'pipeline_phase':'completed','outputs_audited':True})
        return p
    def _after_effect(self,p,key):
        """Fault-injection seam, called after fsync and before the DB receipt."""
    def reconcile(self,branch,pipeline_id,viewer=None):
        p=self.read(branch,pipeline_id,viewer)
        require(p.get('origin_database')==str(Path(self.engine.path).resolve()),'relocated pipeline requires explicit root rebind')
        for key,t in p['tasks'].items():
            historical_completed=t['phase']=='completed'
            divergent=t.get('current_verification',{}).get('status')=='diverged'
            if t['phase'] not in ('executing','recoverable') and not (historical_completed and divergent): continue
            if t['kind']=='write_file':
                c=t.get('resolved_config',t['config']);path=safe_path(c['root'],c['path'])
                exact=path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==c['expected_sha256']
                if exact:
                    t.update(phase='completed',result=dict(path=str(path),sha256=c['expected_sha256']),
                             current_verification={'status':'verified','path':str(path),'expected_sha256':c['expected_sha256']})
                    t.pop('resume_condition',None)
                    if t.get('attempts'): t['attempts'][-1].update(phase='reconciled',result=t['result'])
                elif historical_completed:
                    t['current_verification']={'status':'diverged','path':str(path),'expected_sha256':c['expected_sha256'],
                                               'reason':'historically completed output is not currently exact'}
                    t['resume_condition']='restore or replace external output with the recorded exact bytes, then reconcile'
                elif not path.exists():
                    t['phase']='failed';t['attempts'][-1].update(phase='failed',error='effect absent; retry permitted')
                else:
                    t['phase']='recoverable';t['current_verification']={'status':'diverged','path':str(path),'expected_sha256':c['expected_sha256'],
                                                                       'reason':'conflicting partial effect'}
                    t['resume_condition']='owner resolves conflicting partial effect, then reconcile again'
            else:
                if t['kind']=='repository_check':Repository(self.engine).reconcile(branch,t['config']['candidate_id'])
                t['phase']='failed';t['attempts'][-1].update(phase='failed',error='interrupted check; retry required')
        p['phase']=self._phase(p);self._save(p,dict(event='reconciled',phase=p['phase']));return p
    def rebind(self,branch,pipeline_id,roots,viewer=None):
        p=self.read(branch,pipeline_id,viewer)
        require(isinstance(roots,dict) and roots,'explicit old to new roots required')
        changes=[]
        for key,t in p['tasks'].items():
            if t['kind']=='repository_check':
                candidate=Repository(self.engine).read(branch,t['config']['candidate_id'])
                require(candidate.get('origin_database')==str(Path(self.engine.path).resolve()),'rebind referenced repository first')
            if t['kind']!='write_file':continue
            old=t['config']['root'];require(old in roots,'every write root needs explicit mapping')
            new=str(Path(roots[old]).absolute());require(Path(new).is_dir(),'new authorized root missing')
            path=safe_path(new,t['config']['path'])
            if t['phase'] in ('completed','executing'):
                require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==t['config']['expected_sha256'],'completed or uncertain effect must be present and exact at new root')
            else:require(not path.exists(),'pending destination must be absent at new root')
            changes.append((key,old,new))
        previous=p.get('origin_database')
        for key,old,new in changes:
            t=p['tasks'][key];t['config']['root']=new
            if 'resolved_config' in t:t['resolved_config']['root']=new
            if t['phase']=='waiting' and not t.get('attempts') and 'destination exists before intent' in t.get('resume_condition',''):
                t['phase']='pending';t.pop('resume_condition',None)
        p['origin_database']=str(Path(self.engine.path).resolve())
        event=dict(event='explicit_root_rebind',previous_database=previous,new_database=p['origin_database'],roots=roots)
        p.setdefault('rebindings',[]).append(event);self._save(p,event);return p
    def resume_manual(self,branch,pipeline_id,task_id,result,rationale,viewer=None):
        p=self.read(branch,pipeline_id,viewer)
        require(p.get('origin_database')==str(Path(self.engine.path).resolve()),'relocated pipeline requires explicit root rebind')
        t=p['tasks'].get(task_id)
        require(t and t['kind']=='manual' and t['phase'] in ('waiting','failed'),'manual task unavailable')
        require(isinstance(rationale,str) and rationale.strip(),'observation rationale required')
        require(len(encoded(result))<100000,'bounded result required')
        require(isinstance(result,dict) and result.get('disposition') in ('completed','waiting','failed'),'explicit manual disposition required')
        t.update(phase=result['disposition'],result=result.get('value'),judgment=dict(actor='owner',rationale=rationale))
        if t['phase']=='waiting':t['resume_condition']=result.get('resume_condition','owner supplies observed result')
        p['phase']=self._phase(p);self._save(p,dict(event='manual_observation',task_id=task_id));return p


def verify_pipelines(engine):
    from ..resources import schema_path
    row=engine.db.execute("SELECT version FROM engine_versions WHERE component='pipeline_interface'").fetchone()
    require(row and row[0]=='1','unsupported pipeline interface')
    check=engine.db.execute('SELECT checksum FROM migration_checks WHERE version=16').fetchone()
    require(check and check[0]==hashlib.sha256(schema_path('migration_016.sql').read_bytes()).hexdigest(),'pipeline migration checksum mismatch')
    for table in ('pipeline_runs','pipeline_events','repository_candidates'):
        for row in engine.db.execute('SELECT * FROM '+table):
            require(digest(json.loads(row['payload_json']))==row['payload_hash'],table+' integrity failure')
    return True
