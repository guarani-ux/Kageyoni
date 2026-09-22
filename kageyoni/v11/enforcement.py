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
        with UnitOfWork(self.db): self.db.execute('INSERT INTO v11_enforcer_cases VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)',(cid,scope,protected_requirement,expected_disposition,encoded(basis),digest(payload)))
        return {'case_id':cid,**payload}
    def record_trial(self,*,case_id,enforcer_id,version,observed_disposition,result=None,trial_id=None):
        require(isinstance(enforcer_id,str) and enforcer_id.strip(),'enforcer id required')
        require(observed_disposition in {'supported','contradicted','unresolved'},'invalid observed disposition')
        row=self.db.execute('SELECT * FROM v11_enforcer_cases WHERE case_id=?',(case_id,)).fetchone(); require(row is not None,'unknown evaluation case')
        correct=int(observed_disposition==row['expected_disposition']); tid=trial_id or 'enforcer-trial:'+uuid.uuid4().hex
        payload={'case_id':case_id,'enforcer_id':enforcer_id,'version':str(version),'observed_disposition':observed_disposition,'correct':bool(correct),'result':result or {}}
        with UnitOfWork(self.db): self.db.execute('INSERT INTO v11_enforcer_trials VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',(tid,case_id,enforcer_id,str(version),observed_disposition,correct,encoded(result or {}),digest(payload)))
        return {'trial_id':tid,**payload}
    def _trials(self,enforcer_id,version,scope):
        return list(self.db.execute('''SELECT t.*,c.scope,c.expected_disposition FROM v11_enforcer_trials t JOIN v11_enforcer_cases c ON c.case_id=t.case_id WHERE t.enforcer_id=? AND t.enforcer_version=? AND (c.scope=? OR c.scope='*') ORDER BY t.rowid''',(enforcer_id,str(version),scope)))
    def qualify(self,*,enforcer_id,version,scope,status='candidate',evidence=None,metrics=None,qualification_id=None,min_cases=2,max_errors=0):
        require(status in {'candidate','shadow','qualified','restricted','suspended'},'invalid qualification status')
        require(isinstance(scope,str) and scope.strip(),'qualification scope required')
        require(type(min_cases) is int and min_cases==_POLICY['min_cases'],'qualification minimum is engine policy')
        require(type(max_errors) is int and max_errors==_POLICY['max_errors'],'qualification error budget is engine policy')
        qid=qualification_id or 'qualification:'+uuid.uuid4().hex
        if status=='qualified':
            rows=self._trials(enforcer_id,version,scope); require(len(rows)>=_POLICY['min_cases'],'insufficient engine-held evaluation cases')
            errors=sum(1 for r in rows if not r['correct']); require(errors<=_POLICY['max_errors'],'enforcer evaluation error budget exceeded')
            classes={r['expected_disposition'] for r in rows}; require(len(classes)>=_POLICY['min_disposition_classes'],'qualification requires discriminating reference cases')
            metrics={'total_cases':len(rows),'errors':errors,'correct':len(rows)-errors,'max_errors':_POLICY['max_errors'],'disposition_classes':sorted(classes),'policy':'v11/default-1'}
            evidence=['trial:'+r['trial_id'] for r in rows]
        else: evidence=list(evidence or ['status:'+status]); metrics=dict(metrics or {})
        payload={'enforcer_id':enforcer_id,'version':str(version),'scope':scope,'status':status,'evidence':evidence,'metrics':metrics}
        with UnitOfWork(self.db): self.db.execute('INSERT INTO v11_enforcer_qualifications VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',(qid,enforcer_id,str(version),scope,status,encoded(evidence),encoded(metrics),digest(payload)))
        return self.read(qid)
    def read(self,qid):
        r=self.db.execute('SELECT rowid,* FROM v11_enforcer_qualifications WHERE qualification_id=?',(qid,)).fetchone(); require(r is not None,'unknown qualification')
        o=dict(r); o['evidence']=json.loads(o.pop('evidence_json')); o['metrics']=json.loads(o.pop('metrics_json')); return o
    def require_qualified(self,qid,scope):
        q=self.read(qid); require(q['status']=='qualified','enforcer is not qualified'); require(q['scope']==scope or q['scope']=='*','enforcer qualification scope mismatch')
        latest=self.db.execute('''SELECT rowid,* FROM v11_enforcer_qualifications WHERE enforcer_id=? AND version=? AND scope=? ORDER BY rowid DESC LIMIT 1''',(q['enforcer_id'],q['version'],q['scope'])).fetchone()
        require(latest is not None and latest['qualification_id']==qid and latest['status']=='qualified','qualification has been superseded or suspended')
        rows=self._trials(q['enforcer_id'],q['version'],q['scope']); require(len(rows)>=_POLICY['min_cases'],'qualification evidence no longer exists')
        errors=sum(1 for r in rows if not r['correct']); classes={r['expected_disposition'] for r in rows}
        require(errors<=_POLICY['max_errors'],'new adverse trial invalidates qualification'); require(len(classes)>=_POLICY['min_disposition_classes'],'qualification no longer demonstrates discrimination')
        require(q['metrics'].get('total_cases')==len(rows) and q['metrics'].get('errors')==errors,'qualification metrics are stale')
        return q

class AssessmentLedger:
    def __init__(self,engine): self.engine=engine; self.db=engine.db; self.registry=EnforcerRegistry(engine)
    def record(self,*,enforcer_id,qualification_id,scope,protected_requirement,basis,disposition,result,assessment_id=None):
        q=self.registry.require_qualified(qualification_id,scope); require(q['enforcer_id']==enforcer_id,'assessment enforcer does not own qualification')
        require(disposition in {'supported','contradicted','unresolved'},'invalid disposition'); require(isinstance(basis,dict) and basis,'assessment basis required'); require(isinstance(result,dict),'assessment result required')
        op_id=basis.get('operation_id') or basis.get('operation')
        if op_id:
            op=self.db.execute('SELECT * FROM v11_operations WHERE operation_id=?',(op_id,)).fetchone(); require(op is not None,'assessment operation does not exist')
            require(op['scope']==scope,'assessment operation scope mismatch'); require(protected_requirement==op['requirement_version'],'assessment requirement does not match operation contract')
            require(str(basis.get('requirement_version',op['requirement_version']))==op['requirement_version'],'assessment basis requirement is stale')
            branch=basis.get('branch')
            if branch is not None: require(basis.get('revision')==self.engine.branch(branch)['revision'],'assessment basis revision is stale')
        aid=assessment_id or 'assessment:'+uuid.uuid4().hex
        payload={'enforcer_id':enforcer_id,'qualification_id':qualification_id,'protected_requirement':protected_requirement,'basis':basis,'disposition':disposition,'result':result}
        with UnitOfWork(self.db): self.db.execute('INSERT INTO v11_assessments VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)',(aid,enforcer_id,qualification_id,protected_requirement,encoded(basis),disposition,encoded(result),digest(payload)))
        return {'assessment_id':aid,**payload}
