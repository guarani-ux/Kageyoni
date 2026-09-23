from __future__ import annotations
from ..engine import require
from ..persistence.unit_of_work import UnitOfWork
from .runtime import ProtectedOperations
from .context import ContextPackets
from .frontier import FrontierManager
from .enforcement import AssessmentLedger

class AdaptiveLoop:
    """Bounded adaptive control plane. A frontier can change route, never the parent contract.

    Physical implementation: Procedural finite state machine transitioning operations through
    PREPARED, BLOCKED, ASSESSED, and COMMITTED states. Confers zero autonomous adaptation,
    online learning, or neural adjustment.
    """
    def __init__(self,engine):
        self.engine=engine; self.ops=ProtectedOperations(engine); self.contexts=ContextPackets(engine); self.frontiers=FrontierManager(engine); self.assessments=AssessmentLedger(engine)
    def begin(self,*,objective,requirement_version,scope,basis,included,unresolved=None,payload=None):
        with UnitOfWork(self.engine.db):
            op=self.ops.declare(objective=objective,requirement_version=requirement_version,scope=scope,payload=payload)
            ctx=self.contexts.create(scope=scope,basis=basis,included=included,unresolved=unresolved or [],operation_id=op['operation_id'])
            op=self.ops.transition(op['operation_id'],'PREPARED',patch={'context_id':ctx['context_id']})
            if not ctx['sufficient_for_commit']: op=self.ops.transition(op['operation_id'],'BLOCKED',patch={'blocking_context_id':ctx['context_id']})
        return {'operation':op,'context':ctx}
    def open_frontier(self,operation_id,*,kind,payload):
        op=self.ops.read(operation_id); require(op['state']=='BLOCKED','frontier requires blocked operation')
        return self.frontiers.open(objective=op['objective'],kind=kind,payload=payload,parent_ref=operation_id)
    def investigate(self,frontier_id,*,patch): return self.frontiers.transition(frontier_id,'investigating',patch=patch)
    def observe_frontier(self,frontier_id,*,refs,payload=None): return self.frontiers.observe(frontier_id,refs=refs,payload=payload)
    def resolve_frontier(self,frontier_id,*,evidence,remaining_unknowns=None):
        f=self.frontiers.read(frontier_id); require(f['state']=='investigating','frontier must be investigating'); remaining_unknowns=list(remaining_unknowns or [])
        # Evidence is a list of engine-issued frontier observation IDs, never arbitrary strings.
        self.frontiers._check_observations(frontier_id,evidence)
        state='blocked' if any(bool(x.get('blocking',True)) if isinstance(x,dict) else True for x in remaining_unknowns) else 'resolved'
        if state=='blocked': return self.frontiers.transition(frontier_id,'blocked',patch={'resolution_observation_ids':evidence,'remaining_unknowns':remaining_unknowns})
        return self.frontiers.transition(frontier_id,'resolved',patch={'resolution_observation_ids':evidence,'remaining_unknowns':remaining_unknowns})
    def resume(self,operation_id,frontier_id,*,basis,included,unresolved=None):
        op=self.ops.read(operation_id); f=self.frontiers.read(frontier_id); require(f['parent_ref']==operation_id,'frontier parent mismatch'); require(f['state']=='resolved','frontier is not resolved'); require(op['state']=='BLOCKED','operation is not blocked')
        # Every sibling frontier must be terminally resolved/abandoned before the parent can continue.
        siblings=list(self.engine.db.execute("SELECT frontier_id,state FROM v11_frontiers WHERE parent_ref=? AND frontier_id<>?",(operation_id,frontier_id)))
        require(all(r['state'] in {'resolved','abandoned'} for r in siblings),'another required frontier remains unresolved')
        # Original blocking refs cannot disappear: they must be represented in new context or resolution observation refs.
        original=[]
        cid=op['payload'].get('blocking_context_id')
        if cid:
            row=self.engine.db.execute('SELECT unresolved_json FROM v11_context_packets WHERE context_id=?',(cid,)).fetchone()
            if row:
                import json
                original=[x.get('ref') if isinstance(x,dict) else x for x in json.loads(row['unresolved_json']) if (bool(x.get('blocking',True)) if isinstance(x,dict) else True)]
        resolved_refs=set()
        for obsid in f['payload'].get('resolution_observation_ids',[]) or []:
            row=self.engine.db.execute('SELECT refs_json FROM v11_frontier_observations WHERE observation_id=?',(obsid,)).fetchone()
            if row:
                import json
                resolved_refs.update(json.loads(row['refs_json']))
        represented={x.get('ref') if isinstance(x,dict) else x for x in included}
        require(all(ref in represented or ref in resolved_refs for ref in original),'resumed context dropped unresolved dependency without evidence')
        with UnitOfWork(self.engine.db):
            before=self.engine.db.execute('SELECT COUNT(*) FROM v11_context_packets').fetchone()[0]
            ctx=self.contexts.create(scope=op['scope'],basis=basis,included=included,unresolved=unresolved or [],operation_id=operation_id)
            require(ctx['sufficient_for_commit'],'resumed context still has blocking unknowns')
            op=self.ops.transition(operation_id,'PREPARED',patch={'resumed_from_frontier':frontier_id,'context_id':ctx['context_id']})
        return {'operation':op,'context':ctx}
    def assess(self,operation_id,*,enforcer_id,qualification_id,protected_requirement,basis,disposition,result):
        op=self.ops.read(operation_id); require(op['state']=='PREPARED','assessment requires prepared operation')
        basis=dict(basis or {}); supplied=basis.get('operation_id') or basis.get('operation'); require(supplied in (None,operation_id),'assessment basis belongs to another operation'); basis['operation_id']=operation_id; basis['requirement_version']=op['requirement_version']
        a=self.assessments.record(enforcer_id=enforcer_id,qualification_id=qualification_id,scope=op['scope'],protected_requirement=protected_requirement,basis=basis,disposition=disposition,result=result)
        state='ASSESSED' if disposition=='supported' else 'BLOCKED'
        op=self.ops.transition(operation_id,state,patch={'assessment_id':a['assessment_id'],'assessment_disposition':disposition})
        return {'operation':op,'assessment':a}
