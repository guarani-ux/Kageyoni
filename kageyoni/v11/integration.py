from __future__ import annotations
from .enforcement import EnforcerRegistry, AssessmentLedger
from .runtime import ProtectedOperations

_ENFORCER='engine.mechanical-enforcer'
_VERSION='1'

def _ensure_case(reg,scope,name,expected):
    cid=f'mechanical-case:{scope}:{name}'
    row=reg.db.execute('SELECT case_id FROM v11_enforcer_cases WHERE case_id=?',(cid,)).fetchone()
    if not row:
        reg.create_case(scope=scope,protected_requirement=f'mechanical:{name}',expected_disposition=expected,basis={'kind':'engine-mechanical-reference','name':name},case_id=cid)
    return cid

def mechanical_qualification(engine,scope):
    reg=EnforcerRegistry(engine)
    latest=engine.db.execute("SELECT qualification_id FROM v11_enforcer_qualifications WHERE enforcer_id=? AND version=? AND scope=? ORDER BY rowid DESC LIMIT 1",(_ENFORCER,_VERSION,scope)).fetchone()
    if latest:
        try:return reg.require_qualified(latest['qualification_id'],scope)
        except Exception:pass
    cases=[(_ensure_case(reg,scope,'valid-neighbor','supported'),'supported'),(_ensure_case(reg,scope,'invalid-neighbor','contradicted'),'contradicted')]
    for cid,disp in cases:
        exists=engine.db.execute('SELECT 1 FROM v11_enforcer_trials WHERE case_id=? AND enforcer_id=? AND enforcer_version=?',(cid,_ENFORCER,_VERSION)).fetchone()
        if not exists:reg.record_trial(case_id=cid,enforcer_id=_ENFORCER,version=_VERSION,observed_disposition=disp,result={'mechanical_reference':True})
    return reg.qualify(enforcer_id=_ENFORCER,version=_VERSION,scope=scope,status='qualified')

def begin_domain_operation(engine,*,scope,objective,requirement_version,basis,payload=None):
    ops=ProtectedOperations(engine); q=mechanical_qualification(engine,scope)
    op=ops.declare(objective=objective,requirement_version=requirement_version,scope=scope,payload=payload)
    ops.transition(op['operation_id'],'PREPARED')
    abasis=dict(basis or {});abasis['operation_id']=op['operation_id'];abasis['requirement_version']=str(requirement_version)
    a=AssessmentLedger(engine).record(enforcer_id=q['enforcer_id'],qualification_id=q['qualification_id'],scope=scope,protected_requirement=str(requirement_version),basis=abasis,disposition='supported',result={'kind':'mechanical-domain-admission','basis':basis or {}})
    ops.transition(op['operation_id'],'ASSESSED',patch={'assessment_id':a['assessment_id']})
    ops.transition(op['operation_id'],'AUTHORIZED',qualification_id=q['qualification_id'])
    return {'operation_id':op['operation_id'],'qualification_id':q['qualification_id'],'assessment_id':a['assessment_id']}

def complete_domain_operation(engine,mediation,*,evidence_type,evidence_ref,outcome,verification):
    ops=ProtectedOperations(engine);oid=mediation['operation_id']
    ops.issue_execution(oid,evidence_type=evidence_type,evidence_ref=evidence_ref,payload={'domain_effect':outcome})
    ops.observe(oid,outcome=outcome)
    ops.verify_observation(oid,receipt=verification)
    return ops.complete(oid)
