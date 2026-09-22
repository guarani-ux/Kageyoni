from __future__ import annotations
import hashlib, json, uuid
from ..engine import digest, encoded, require
from ..persistence.unit_of_work import UnitOfWork

_POLICY={'min_cases':2,'max_errors':0,'min_disposition_classes':2}

class EnforcerRegistry:
    """Qualification is engine-evaluated, scoped, current and revocable."""
    def __init__(self,engine): self.engine=engine; self.db=engine.db
    def create_case(self,*,scope,protected_requirement,expected_disposition,basis,case_id=None):
        require(isinstance(scope,str) and scope.strip(),'case scope required')
        require(isinstance(protected_requirement,str) and protected_requirement.strip(),'protected requirement required')
        require(expected_disposition in {'supported','contradicted','unresolved'},'invalid expected disposition')
        require(isinstance(basis,dict) and basis,'case basis required')
        cid=case_id or 'enforcer-case:'+uuid.uuid4().hex
        payload={'scope':scope,'protected_requirement':protected_requirement,'expected_disposition':expected_disposition,'basis':basis}
        with UnitOfWork(self.db):
            self.db.execute('INSERT INTO v11_enforcer_cases VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)',(cid,scope,protected_requirement,expected_disposition,encoded(basis),digest(payload)))
        return {'case_id':cid,**payload}
    def record_trial(self,*,case_id,enforcer_id,version,observed_disposition,result=None,trial_id=None):
        require(isinstance(enforcer_id,str) and enforcer_id.strip(),'enforcer id required')
        require(observed_disposition in {'supported','contradicted','unresolved'},'invalid observed disposition')
        row=self.db.execute('SELECT * FROM v11_enforcer_cases WHERE case_id=?',(case_id,)).fetchone(); require(row is not None,'unknown evaluation case')
        correct=int(observed_disposition==row['expected_disposition']); tid=trial_id or 'enforcer-trial:'+uuid.uuid4().hex
        payload={'case_id':case_id,'enforcer_id':enforcer_id,'version':str(version),'observed_disposition':observed_disposition,'correct':bool(correct),'result':result or {}}
        with UnitOfWork(self.db):
            self.db.execute('INSERT INTO v11_enforcer_trials VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',(tid,case_id,enforcer_id,str(version),observed_disposition,correct,encoded(result or {}),digest(payload)))
        return {'trial_id':tid,**payload}
    def _trials(self,enforcer_id,version,scope):
        return list(self.db.execute('''SELECT t.*,c.scope,c.expected_disposition FROM v11_enforcer_trials t
            JOIN v11_enforcer_cases c ON c.case_id=t.case_id
            WHERE t.enforcer_id=? AND t.enforcer_version=? AND (c.scope=? OR c.scope='*') ORDER BY t.rowid''',(enforcer_id,str(version),scope)))
    def qualify(self,*,enforcer_id,version,scope,status='candidate',evidence=None,metrics=None,qualification_id=None,min_cases=2,max_errors=0):
        require(status in {'candidate','shadow','qualified','restricted','suspended'},'invalid qualification status')
        require(isinstance(scope,str) and scope.strip(),'qualification scope required')
        # Callers may not weaken the qualification policy at the point of requesting authority.
        require(type(min_cases) is int and min_cases==_POLICY['min_cases'],'qualification minimum is engine policy')
        require(type(max_errors) is int and max_errors==_POLICY['max_errors'],'qualification error budget is engine policy')
        qid=qualification_id or 'qualification:'+uuid.uuid4().hex
        if status=='qualified':
            rows=self._trials(enforcer_id,version,scope)
            require(len(rows)>=_POLICY['min_cases'],'insufficient engine-held evaluation cases')
            errors=sum(1 for r in rows if not r['correct'])
            require(errors<=_POLICY['max_errors'],'enforcer evaluation error budget exceeded')
            classes={r['expected_disposition'] for r in rows}
            require(len(classes)>=_POLICY['min_disposition_classes'],'qualification requires discriminating reference cases')
            metrics={'total_cases':len(rows),'errors':errors,'correct':len(rows)-errors,'max_errors':_POLICY['max_errors'],'disposition_classes':sorted(classes),'policy':'v11/default-1'}
            evidence=['trial:'+r['trial_id'] for r in rows]
        else:
            evidence=list(evidence or ['status:'+status]); metrics=dict(metrics or {})
        payload={'enforcer_id':enforcer_id,'version':str(version),'scope':scope,'status':status,'evidence':evidence,'metrics':metrics}
        with UnitOfWork(self.db):
            self.db.execute('INSERT INTO v11_enforcer_qualifications VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',(qid,enforcer_id,str(version),scope,status,encoded(evidence),encoded(metrics),digest(payload)))
        return self.read(qid)
    def read(self,qid):
        r=self.db.execute('SELECT rowid,* FROM v11_enforcer_qualifications WHERE qualification_id=?',(qid,)).fetchone(); require(r is not None,'unknown qualification')
        o=dict(r); o['evidence']=json.loads(o.pop('evidence_json')); o['metrics']=json.loads(o.pop('metrics_json')); return o
    def require_qualified(self,qid,scope):
        q=self.read(qid)
        require(q['status']=='qualified','enforcer is not qualified')
        require(q['scope']==scope or q['scope']=='*','enforcer qualification scope mismatch')
        # Latest qualification status for this exact enforcer/configuration/scope controls effective authority.
        latest=self.db.execute('''SELECT rowid,* FROM v11_enforcer_qualifications
            WHERE enforcer_id=? AND version=? AND scope=? ORDER BY rowid DESC LIMIT 1''',(q['enforcer_id'],q['version'],q['scope'])).fetchone()
        require(latest is not None and latest['qualification_id']==qid and latest['status']=='qualified','qualification has been superseded or suspended')
        rows=self._trials(q['enforcer_id'],q['version'],q['scope'])
        require(len(rows)>=_POLICY['min_cases'],'qualification evidence no longer exists')
        errors=sum(1 for r in rows if not r['correct']); classes={r['expected_disposition'] for r in rows}
        require(errors<=_POLICY['max_errors'],'new adverse trial invalidates qualification')
        require(len(classes)>=_POLICY['min_disposition_classes'],'qualification no longer demonstrates discrimination')
        require(q['metrics'].get('total_cases')==len(rows) and q['metrics'].get('errors')==errors,'qualification metrics are stale')
        return q

class AssessmentLedger:
    def __init__(self,engine): self.engine=engine; self.db=engine.db; self.registry=EnforcerRegistry(engine)
    def record(self,*,enforcer_id,qualification_id,scope,protected_requirement,basis,disposition,result,assessment_id=None):
        q=self.registry.require_qualified(qualification_id,scope)
        require(q['enforcer_id']==enforcer_id,'assessment enforcer does not own qualification')
        require(disposition in {'supported','contradicted','unresolved'},'invalid disposition')
        require(isinstance(basis,dict) and basis,'assessment basis required'); require(isinstance(result,dict),'assessment result required')
        op_id=basis.get('operation_id') or basis.get('operation')
        if op_id:
            op=self.db.execute('SELECT * FROM v11_operations WHERE operation_id=?',(op_id,)).fetchone(); require(op is not None,'assessment operation does not exist')
            require(op['scope']==scope,'assessment operation scope mismatch')
            require(protected_requirement==op['requirement_version'],'assessment requirement does not match operation contract')
            require(str(basis.get('requirement_version',op['requirement_version']))==op['requirement_version'],'assessment basis requirement is stale')
            branch=basis.get('branch')
            if branch is not None:
                current=self.engine.branch(branch)['revision']; require(basis.get('revision')==current,'assessment basis revision is stale')
        aid=assessment_id or 'assessment:'+uuid.uuid4().hex
        payload={'enforcer_id':enforcer_id,'qualification_id':qualification_id,'protected_requirement':protected_requirement,'basis':basis,'disposition':disposition,'result':result}
        with UnitOfWork(self.db):
            self.db.execute('INSERT INTO v11_assessments VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',(aid,enforcer_id,qualification_id,protected_requirement,encoded(basis),disposition,encoded(result),digest(payload)))
        return {'assessment_id':aid,**payload}

def _table_exists(db,name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None

def verify_v11(engine):
    from ..resources import schema_path
    # Every installed v11 migration remains part of the trust root, not only the first one.
    for version,name in ((19,'migration_019.sql'),(20,'migration_020.sql'),(21,'migration_021.sql'),(22,'migration_022.sql')):
        if engine.db.execute('SELECT 1 FROM migration_checks WHERE version=?',(version,)).fetchone():
            check=engine.db.execute('SELECT checksum FROM migration_checks WHERE version=?',(version,)).fetchone()
            require(check and check[0]==hashlib.sha256(schema_path(name).read_bytes()).hexdigest(),f'v11 migration {version} checksum mismatch')
    if _table_exists(engine.db,'v11_preparations'):
        for row in engine.db.execute('SELECT * FROM v11_preparations'):
            p=json.loads(row['payload_json']); require(row['payload_hash'] and digest(p)==row['payload_hash'],'preparation payload hash mismatch'); require(p['proposal_id']==row['proposal_id'],'preparation identity mismatch')
            require(p['command_hash']==row['command_hash'] and p['compilation_hash']==row['compilation_hash'] and p['basis_hash']==row['basis_hash'],'preparation binding mismatch')
            require(p.get('status')==row['status'],'preparation lifecycle mismatch')
            if row['status']=='consumed':
                receipt=p.get('engine_receipt'); require(isinstance(receipt,dict) and receipt.get('committed') is True,'consumed preparation lacks effect receipt')
                require(engine.db.execute('SELECT 1 FROM events WHERE request_id=?',(receipt.get('request_id'),)).fetchone(),'consumed preparation effect is missing')
    if _table_exists(engine.db,'v11_enforcer_cases'):
        for row in engine.db.execute('SELECT * FROM v11_enforcer_cases'):
            payload={'scope':row['scope'],'protected_requirement':row['protected_requirement'],'expected_disposition':row['expected_disposition'],'basis':json.loads(row['basis_json'])}; require(digest(payload)==row['source_hash'],'enforcer case hash mismatch')
        for row in engine.db.execute('SELECT * FROM v11_enforcer_trials'):
            payload={'case_id':row['case_id'],'enforcer_id':row['enforcer_id'],'version':row['enforcer_version'],'observed_disposition':row['observed_disposition'],'correct':bool(row['correct']),'result':json.loads(row['result_json'])}; require(digest(payload)==row['source_hash'],'enforcer trial hash mismatch')
            case=engine.db.execute('SELECT expected_disposition FROM v11_enforcer_cases WHERE case_id=?',(row['case_id'],)).fetchone(); require(case is not None,'enforcer trial case missing')
            require(bool(row['correct'])==(row['observed_disposition']==case['expected_disposition']),'enforcer trial correctness mismatch')
    if _table_exists(engine.db,'v11_enforcer_qualifications'):
        for row in engine.db.execute('SELECT * FROM v11_enforcer_qualifications'):
            payload={'enforcer_id':row['enforcer_id'],'version':row['version'],'scope':row['scope'],'status':row['status'],'evidence':json.loads(row['evidence_json']),'metrics':json.loads(row['metrics_json'])}; require(digest(payload)==row['source_hash'],'qualification hash mismatch')
            if row['status']=='qualified':
                refs=json.loads(row['evidence_json']); require(refs and all(str(x).startswith('trial:') for x in refs),'qualified enforcer evidence is not trial-bound')
                for ref in refs: require(engine.db.execute('SELECT 1 FROM v11_enforcer_trials WHERE trial_id=?',(ref.split(':',1)[1],)).fetchone(),'qualification trial missing')
    if _table_exists(engine.db,'v11_assessments'):
        for row in engine.db.execute('SELECT * FROM v11_assessments'):
            payload={'enforcer_id':row['enforcer_id'],'qualification_id':row['qualification_id'],'protected_requirement':row['protected_requirement'],'basis':json.loads(row['basis_json']),'disposition':row['disposition'],'result':json.loads(row['result_json'])}; require(digest(payload)==row['source_hash'],'assessment hash mismatch')
            q=engine.db.execute('SELECT enforcer_id FROM v11_enforcer_qualifications WHERE qualification_id=?',(row['qualification_id'],)).fetchone(); require(q is not None and q['enforcer_id']==row['enforcer_id'],'assessment qualification ownership mismatch')
    if _table_exists(engine.db,'v11_frontiers'):
        for row in engine.db.execute('SELECT * FROM v11_frontiers'):
            payload=json.loads(row['payload_json']); require(digest(payload)==row['source_hash'],'frontier hash mismatch')
            require(payload.get('_state')==row['state'] and payload.get('_parent_ref')==row['parent_ref'] and payload.get('objective_or_direction')==row['objective'],'frontier lifecycle binding mismatch')
            if row['parent_ref']:
                parent=engine.db.execute('SELECT objective FROM v11_operations WHERE operation_id=?',(row['parent_ref'],)).fetchone(); require(parent is not None and parent['objective']==row['objective'],'frontier parent/objective mismatch')
    if _table_exists(engine.db,'v11_operations'):
        for row in engine.db.execute('SELECT * FROM v11_operations'):
            payload=json.loads(row['payload_json']); require(digest(payload)==row['source_hash'],'protected operation hash mismatch')
            require(payload.get('objective')==row['objective'] and str(payload.get('requirement_version'))==row['requirement_version'] and payload.get('scope')==row['scope'] and payload.get('_state')==row['state'],'protected operation contract/lifecycle mismatch')
            if row['state']=='COMPLETED':
                for key,table,col in (('execution_receipt_id','v11_execution_receipts','receipt_id'),('observation_id','v11_observations','observation_id'),('verification_id','v11_verifications','verification_id')):
                    require(payload.get(key) and engine.db.execute(f'SELECT 1 FROM {table} WHERE {col}=? AND operation_id=?',(payload[key],row['operation_id'])).fetchone(),f'completed operation missing {key}')
                require(not payload.get('required_children') or all(engine.db.execute("SELECT state FROM v11_operations WHERE operation_id=?",(child,)).fetchone() and engine.db.execute("SELECT state FROM v11_operations WHERE operation_id=?",(child,)).fetchone()[0]=='COMPLETED' for child in payload['required_children']),'required child incomplete')
    if _table_exists(engine.db,'v11_context_packets'):
        for row in engine.db.execute('SELECT * FROM v11_context_packets'):
            payload={'scope':row['scope'],'basis':json.loads(row['basis_json']),'included':json.loads(row['included_json']),'unresolved':json.loads(row['unresolved_json']),'excluded':json.loads(row['excluded_json']),'operation_id':row['operation_id']}; require(digest(payload)==row['source_hash'],'context packet hash mismatch')
            if row['operation_id']:
                op=engine.db.execute('SELECT scope FROM v11_operations WHERE operation_id=?',(row['operation_id'],)).fetchone(); require(op is not None and op['scope']==row['scope'],'context operation/scope mismatch')
    for table,idcol,payload_fn in (
        ('v11_execution_receipts','receipt_id',lambda r:{'operation_id':r['operation_id'],'evidence_type':r['evidence_type'],'evidence_ref':r['evidence_ref'],'payload':json.loads(r['payload_json'])}),
        ('v11_observations','observation_id',lambda r:{'operation_id':r['operation_id'],'receipt_id':r['receipt_id'],'payload':json.loads(r['payload_json'])}),
        ('v11_verifications','verification_id',lambda r:{'operation_id':r['operation_id'],'observation_id':r['observation_id'],'disposition':r['disposition'],'payload':json.loads(r['payload_json'])}),
        ('v11_frontier_observations','observation_id',lambda r:{'frontier_id':r['frontier_id'],'refs':json.loads(r['refs_json']),'payload':json.loads(r['payload_json'])}),
    ):
        if _table_exists(engine.db,table):
            for row in engine.db.execute('SELECT * FROM '+table): require(digest(payload_fn(row))==row['source_hash'],table+' integrity mismatch')
    return True
