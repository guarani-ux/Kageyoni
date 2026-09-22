"""Directed-role correspondence and explicitly bounded destination trials."""
from copy import deepcopy
import json
from uuid import uuid4
from ..engine import require,digest,encoded
from ..persistence.unit_of_work import UnitOfWork
from ..persistence.artifacts import Artifacts
from ..workspaces.registry import Registry
from ..workspaces.contracts import text,finite
from ..execution.operations import validate_operation, run, pending_guards, failed_guards
from .methods import Methods

class Transfers:
    def __init__(self,engine):self.engine=engine;self.db=engine.db
    def propose(self,workspace_id,method_id,method_revision,request_id,mapping,viewer=None):
        text(request_id,'request id');finite(mapping)
        require(isinstance(mapping,dict) and set(mapping)=={'destination_domain','roles','destination_roles','destination_relationships','field_map'},'invalid transfer mapping')
        payload=dict(workspace_id=workspace_id,method_id=method_id,method_revision=method_revision,request_id=request_id,mapping=mapping,viewer=viewer)
        with UnitOfWork(self.db):
            workspace=Registry(self.engine).read(workspace_id,viewer=viewer)
            old=self.db.execute('SELECT transfer_id,payload_hash FROM method_transfers WHERE request_id=?',(request_id,)).fetchone()
            if old:require(old['payload_hash']==digest(payload),'transfer request conflict');return self.read(old['transfer_id'],viewer=viewer)
            method=Methods(self.engine).read(workspace['branch'],method_id,method_revision,viewer=viewer)
            require(method['node_id']==workspace['node_id'] and method['qualification']=='experimental' and method['source_fresh'],'source method unavailable for transfer')
            require(mapping['destination_domain']==workspace['kind'],'destination domain mismatch')
            roles=mapping['roles'];dest=mapping['destination_roles'];edges=mapping['destination_relationships'];fields=mapping['field_map']
            require(isinstance(roles,dict) and isinstance(dest,list) and len(dest)<=128 and all(isinstance(r,str) and r for r in dest) and len(set(dest))==len(dest),'invalid role mapping')
            require(isinstance(edges,list) and len(edges)<=256 and all(isinstance(e,dict) and set(e)=={'source','relation','target'} and e['source'] in dest and e['target'] in dest and isinstance(e['relation'],str) for e in edges),'invalid directed relationships')
            require(isinstance(fields,dict) and all(isinstance(k,str) and isinstance(v,str) and v for k,v in fields.items()),'invalid field map')
            mismatches=[]
            if set(roles)!=set(method['definition']['roles']) or len(set(roles.values()))!=len(roles) or not set(roles.values())<=set(dest):mismatches.append('roles_missing_collapsed_or_unmapped')
            if not mismatches:
                projected=sorted((roles[e['source']],e['relation'],roles[e['target']]) for e in method['definition']['relationships'])
                actual=sorted((e['source'],e['relation'],e['target']) for e in edges)
                if projected!=actual:mismatches.append('directed_relationship_topology_mismatch')
            operation=deepcopy(method['definition']['operation'])
            if operation['kind']=='constraint_rank':
                needed={c['field'] for c in operation['params']['criteria']}
                if set(fields)!=needed:mismatches.append('criterion_mapping_mismatch')
                else:
                    for criterion in operation['params']['criteria']:criterion['field']=fields[criterion['field']]
            elif operation['kind']=='counterexample_check':
                needed=set(operation['params']['fields'])
                if set(fields)!=needed:mismatches.append('field_mapping_mismatch')
                else:operation['params']['fields']=[fields[f] for f in operation['params']['fields']]
            validate_operation(operation)
            tid='transfer:'+uuid4().hex
            result=dict(transfer_id=tid,workspace_id=workspace_id,node_id=workspace['node_id'],branch=workspace['branch'],destination_domain=mapping['destination_domain'],
                status='blocked' if mismatches else 'candidate',mismatches=mismatches,mapping=deepcopy(mapping),method_id=method_id,method_revision=method_revision,method_digest=method['digest'],
                operation=operation,qualification_limit='A correspondence proposes a method; it does not establish destination competence.')
            result['method_guards']={key:deepcopy(method['definition'][key]) for key in ('preconditions','failure_conditions','checking_procedure')}
            self.db.execute('INSERT INTO method_transfers VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,workspace_id,request_id,digest(payload),method_id,method_revision,method['digest'],method['assignment_revision'],method['assignment_digest'],encoded(mapping),encoded(result)))
            return result
    def read(self,transfer_id,viewer=None):
        row=self.db.execute('SELECT * FROM method_transfers WHERE transfer_id=?',(transfer_id,)).fetchone();require(row is not None,'transfer unavailable')
        workspace=Registry(self.engine).read(row['workspace_id'],viewer=viewer)
        method=Methods(self.engine).read(workspace['branch'],row['method_id'],row['method_revision'],viewer=viewer)
        result=json.loads(row['result_json'])
        result['source_current']=bool(method['source_fresh'] and method['qualification']=='experimental' and method['digest']==row['method_digest'] and method['assignment_revision']==row['assignment_revision'] and method['assignment_digest']==row['assignment_digest'])
        trial=self.db.execute('SELECT result_json FROM transfer_trials WHERE transfer_id=? ORDER BY sequence DESC LIMIT 1',(transfer_id,)).fetchone()
        result['latest_trial']=json.loads(trial[0]) if trial else None
        if result['status']!='blocked' and trial:result['status']=result['latest_trial']['status']
        if not result['source_current']:result['status']='stale'
        return result
    def record_trial(self,transfer_id,request_id,artifact_id,checks,rationale,viewer=None):
        text(request_id,'request id');text(rationale,'trial rationale');finite(checks)
        require(isinstance(checks,list) and 1<=len(checks)<=64 and all(isinstance(c,dict) and set(c)=={'name','passed'} and isinstance(c['name'],str) and c['name'] and type(c['passed']) is bool for c in checks),'explicit destination checks required')
        payload=dict(transfer_id=transfer_id,request_id=request_id,artifact_id=artifact_id,checks=checks,rationale=rationale,viewer=viewer)
        with UnitOfWork(self.db):
            transfer=self.read(transfer_id,viewer=viewer);require(transfer['source_current'] and not transfer['mismatches'],'transfer unavailable for trial')
            old=self.db.execute('SELECT payload_hash,result_json FROM transfer_trials WHERE request_id=?',(request_id,)).fetchone()
            if old:require(old['payload_hash']==digest(payload),'trial request conflict');return json.loads(old['result_json'])
            artifact=Artifacts(self.engine).read(artifact_id,viewer=viewer);require(artifact['workspace_id']==transfer['workspace_id'] and artifact['media_type']=='application/json','trial artifact scope or media mismatch')
            try:report=json.loads(artifact['content'])
            except (ValueError,UnicodeDecodeError):require(False,'trial artifact requires JSON')
            require(isinstance(report,dict) and report.get('transfer_id')==transfer_id and report.get('destination_domain')==transfer['destination_domain'] and report.get('checks')==checks,'trial artifact does not bind declared checks')
            registered=self.db.execute('SELECT artifact_digest,report_json FROM transfer_check_runs WHERE transfer_id=? AND artifact_id=?',(transfer_id,artifact_id)).fetchone()
            if registered:
                require(registered['artifact_digest']==artifact['digest'] and json.loads(registered['report_json'])==report,'registered trial report mismatch')
            elif transfer['destination_domain']=='repository':
                from ..workspaces.repository import Repository
                require(Repository(self.engine).validate_trial(transfer['branch'],report),'repository trial check failed')
            else:require(False,'executed destination checks required; caller assertions cannot qualify')
            sequence=self.db.execute('SELECT coalesce(MAX(sequence),0)+1 FROM transfer_trials WHERE transfer_id=?',(transfer_id,)).fetchone()[0]
            result=dict(trial_id='trial:'+uuid4().hex,transfer_id=transfer_id,status='qualified' if all(c['passed'] for c in checks) else 'failed',artifact_id=artifact_id,artifact_digest=artifact['digest'],checks=checks,rationale=rationale,
                        method_digest=transfer['method_digest'],qualification_limit='Scoped executor/operator-attributed trial evidence; not verified general competence.')
            self.db.execute('INSERT INTO transfer_trials VALUES(?,?,?,?,?,?,?)',(result['trial_id'],transfer_id,request_id,digest(payload),artifact_id,encoded(result),sequence));return result
    def run_trial(self,transfer_id,request_id,cases,viewer=None):
        text(request_id,'request id');finite(cases)
        require(isinstance(cases,list) and 2<=len(cases)<=20,'destination trial needs positive and negative cases')
        require({case.get('expected_phase') for case in cases}=={'completed','blocked'},'trial needs independent success and blocked expectations')
        payload=dict(transfer_id=transfer_id,request_id=request_id,cases=cases,viewer=viewer)
        with UnitOfWork(self.db):
            transfer=self.read(transfer_id,viewer=viewer);require(transfer['source_current'] and not transfer['mismatches'],'transfer unavailable for trial')
            old=self.db.execute('SELECT * FROM transfer_check_runs WHERE request_id=?',(request_id,)).fetchone()
            if old:
                require(old['payload_hash']==digest(payload),'trial run request conflict')
                report=json.loads(old['report_json']);aid=old['artifact_id']
            else:
                from ..workspaces.documents import Documents
                checker=Documents(self.engine);checks=[];results=[]
                definition=dict(transfer['method_guards'],operation=transfer['operation'])
                require(not pending_guards(definition),'destination method requires unresolved judgment')
                for case in cases:
                    require(isinstance(case,dict) and set(case)=={'case_id','candidates','expected_phase','expected_order'},'invalid destination case')
                    text(case['case_id'],'case id',100)
                    candidates=checker.checked_candidates(transfer['workspace_id'],case['candidates'],viewer=viewer)
                    failures=failed_guards(definition,candidates)
                    result={'phase':'blocked'} if failures else run(transfer['operation'],candidates)
                    order=[row['candidate_id'] for row in result.get('ranked',[])]
                    matched=result['phase']==case['expected_phase'] and order==case['expected_order']
                    checks.append({'name':case['case_id'],'passed':matched});results.append({'case_id':case['case_id'],'input_digest':digest(case['candidates']),'actual':result,'expected_phase':case['expected_phase'],'expected_order':case['expected_order']})
                report=dict(transfer_id=transfer_id,destination_domain=transfer['destination_domain'],checks=checks,results=results,checker='registered-operation/v1')
                artifact=Artifacts(self.engine).put(encoded(report),'application/json',request_id+':checks',workspace_id=transfer['workspace_id'],viewer=viewer);aid=artifact['artifact_id']
                self.db.execute('INSERT INTO transfer_check_runs VALUES(?,?,?,?,?,?,?)',('check:'+uuid4().hex,transfer_id,request_id,digest(payload),aid,artifact['digest'],encoded(report)))
            return self.record_trial(transfer_id,request_id+':qualification',aid,report['checks'],'Executed mapped operation on source-bound destination cases; expected outcomes remain authored test oracles.',viewer=viewer)
    def require_qualified(self,transfer_id,workspace_id,destination_domain,viewer=None):
        result=self.read(transfer_id,viewer=viewer)
        require(result['workspace_id']==workspace_id and result['destination_domain']==destination_domain and result['status']=='qualified','qualified destination trial required')
        artifact=Artifacts(self.engine).read(result['latest_trial']['artifact_id'],viewer=viewer)
        require(artifact['digest']==result['latest_trial']['artifact_digest'],'trial artifact changed')
        return result
