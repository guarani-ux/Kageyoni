"""Bounded delivery of two installed native processes, with durable returns.

Native events/processes/subscriptions/runs own fictional facts. This service
routes their pending work; it does not infer physics or run arbitrary handlers.
"""
from copy import deepcopy
import json,time
from kageyoni.engine import Rejected
from kageyoni.persistence.unit_of_work import UnitOfWork
from .content import EVIDENCE
from .protocol import Fault,digest,encoded

CLOSE='fixture:close-garden-path'
SHELTER='fixture:shelter-tea'
PROCESSES={
 CLOSE:{'process_kind':'synthetic_weather_route','subjects':['garden-path'],
    'scope':{'clock_id':'fixture:clock'},'subscriptions':['world_event'],'visibility':'public',
    'metadata':{'effect':{'kind':'record_patch','record_id':'garden-path','data':{'access':'blocked'}}}},
 SHELTER:{'process_kind':'synthetic_keeper_response','subjects':['keeper'],
    'scope':{'clock_id':'fixture:clock'},'subscriptions':['consequence'],'visibility':'public','conditions':{'source_process_id':CLOSE},
    'metadata':{'effect':{'kind':'record_patch','record_id':'keeper','data':{'condition':'The keeper moved the tea indoors after the synthetic garden-path closure.'}}}}
}


def install_fixture(engine):
    processes=[dict(value,id=pid,op='create') for pid,value in PROCESSES.items()]
    engine.apply({'api_version':3,'branch':'main','request_id':'samsara:causal-fixture',
        'expected_revision':engine.branch('main')['revision'],'actor':'fixture','kind':'scene',
        'narrative':'Install two public synthetic causal processes; no source cue has occurred.',
        'changes':[],'processes':processes})
    for pid in PROCESSES:
        engine.register_component('process',pid,'1','process:'+pid,status='verified',
            readers=['Samsara.causality'],writers=['Engine.apply'],compatibility={'runtime_schema':'4'},declared_by='synthetic-fixture')


class Causality:
    def __init__(self,app):self.app,self.engine,self.db,self.ws=app,app.engine,app.db,app.workspace_id

    def visible(self,context,eid):return self.app.properties.entity(context,eid)

    def visible_process(self,context,pid):
        p=self.engine._current_process(self.app.branch,pid)
        if not p or (context.role!='operator' and p['visibility']!='public'):raise Fault('UNAVAILABLE')
        for eid in p['subjects']:self.visible(context,eid)
        return p

    def process(self,context,pid):
        p=self.visible_process(context,pid)
        spec=PROCESSES.get(pid)
        if not spec:raise Fault('DEPENDENCY')
        for key,value in spec.items():
            if p.get(key)!=value:raise Fault('DEPENDENCY')
        return p

    def root(self,context,rid):
        row=self.db.execute('SELECT * FROM causal_roots WHERE workspace_id=? AND root_id=?',(self.ws,rid)).fetchone()
        if not row:raise Fault('UNAVAILABLE')
        self.visible(context,row['source_record'])
        return dict(row)

    def artifact(self,context,value,key,scope):
        ref=self.app.put_json(value,self.app.key('causal-trace',key),principals=[context.principal_id,'character:visitor','character:keeper'])
        self.db.execute('INSERT INTO causal_read_grants VALUES(?,?,?)',(self.ws,ref['id'],encoded(sorted(set(scope)))))
        return ref

    def authorize_artifact(self,context,ref):
        if context.role=='operator':return
        row=self.db.execute('SELECT scope_json FROM causal_read_grants WHERE workspace_id=? AND artifact_id=?',(self.ws,ref['id'])).fetchone()
        if row:
            for eid in json.loads(row[0]):
                if eid.startswith('process:'):self.visible_process(context,eid[len('process:'):])
                else:self.visible(context,eid)

    def inherit(self,ref,sources):
        existing=self.db.execute('SELECT scope_json FROM causal_read_grants WHERE workspace_id=? AND artifact_id=?',(self.ws,ref['id'])).fetchone()
        scope=set(json.loads(existing[0])) if existing else set()
        for source in sources:
            row=self.db.execute('SELECT scope_json FROM causal_read_grants WHERE workspace_id=? AND artifact_id=?',(self.ws,source['id'])).fetchone()
            if row:scope.update(json.loads(row[0]))
        if scope:self.db.execute('INSERT OR REPLACE INTO causal_read_grants VALUES(?,?,?)',(self.ws,ref['id'],encoded(sorted(scope))))

    def ingest(self,root,receipt,depth,parent=None,ancestry=()):
        # Engine.apply already committed its event and due-state into our UoW.
        # The same outer transaction stores each indexed delivery once.
        event=self.db.execute('SELECT kind FROM events WHERE id=?',(receipt['event_id'],)).fetchone()
        explicit=set(receipt['changed_processes'])
        targets=[r[0] for r in self.db.execute("SELECT p.id FROM processes p JOIN process_subscriptions s ON s.branch=p.branch AND s.process_id=p.id WHERE p.branch=? AND p.state IN ('active','due') AND s.event_kind=? ORDER BY p.id",(self.app.branch,event['kind'])) if r[0] not in explicit]
        for pid in targets:
            if pid==SHELTER and parent!=CLOSE:continue
            if pid not in PROCESSES:continue  # Other native consumers own their own work.
            state='queued';reason='Native subscription matched; awaiting explicit bounded delivery.'
            if pid in ancestry:state,reason='parked','Cycle detected; explicit operator reconciliation is required.'
            if depth>=16:state,reason='parked','Causal depth budget exhausted.'
            count=self.db.execute('SELECT count(*) FROM causal_deliveries WHERE workspace_id=? AND root_id=?',(self.ws,root['root_id'])).fetchone()[0]
            if count>=256:state,reason='parked','Causal root wake budget exhausted.'
            self.db.execute('INSERT OR IGNORE INTO causal_deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (self.ws,root['root_id'],receipt['event_id'],pid,1,parent,depth,state,reason,None,None))

    def signal(self,context,op):
        if context.role!='operator':raise Fault('UNAVAILABLE')
        old=self.db.execute('SELECT * FROM causal_roots WHERE workspace_id=? AND root_id=?',(self.ws,op['root_id'])).fetchone()
        if old:return self.view(context,op['root_id'])
        if self.db.execute('SELECT count(*) FROM causal_roots WHERE workspace_id=?',(self.ws,)).fetchone()[0]>=128:raise Fault('BUDGET')
        # A declared source cue is distinct from its later downstream effects.
        for pid in PROCESSES:self.process(context,pid)
        source_record=self.app.key('causal-source',op['root_id'])
        command={'api_version':3,'branch':self.app.branch,'request_id':self.app.key('causal-source-event',op['root_id']),
            'expected_revision':self.app.revision(),'actor':'fixture','kind':'world_event',
            'narrative':'Emit an explicitly authored synthetic rainfall cue; route and keeper effects await delivery.',
            'changes':[{'op':'create','domain':'consequence','id':source_record,'visibility':'public','status':'proposed','evidence':EVIDENCE,
                'data':{'subject':'The synthetic studio garden','effect':'An authored rain cue occurred.','duration':'one causal episode',
                    'ending_condition':'Explicit source episode ends.','reversibility':'conditional'}}]}
        receipt=self.engine.apply(command)
        self.db.execute('INSERT INTO causal_roots VALUES(?,?,?,?,?)',(self.ws,op['root_id'],receipt['event_id'],source_record,digest(command)))
        root=self.root(context,op['root_id']);self.ingest(root,receipt,0)
        return self.view(context,op['root_id'])

    def persist_delivery(self,row,event,ref):
        self.db.execute("UPDATE causal_deliveries SET state='delivered',reason='Native consequence delivered; history retained.',result_event=?,trace_ref_json=? WHERE workspace_id=? AND process_id=? AND process_version=? AND source_event=?",
            (event,encoded(ref),self.ws,row['process_id'],row['process_version'],row['source_event']))

    def deliver(self,context,row):
        root=self.root(context,row['root_id']);p=self.process(context,row['process_id'])
        if p['state'] not in ('active','due'):raise Fault('DEPENDENCY')
        clock=self.visible(context,'fixture:clock');tick=clock['data']['tick']
        changes,properties,judgment=self.engine._due_process_effect(self.app.branch,p,tick,tick)
        if judgment or properties:raise Fault('DEPENDENCY')
        before={c['id']:self.visible(context,c['id']) for c in changes}
        # Repeated unchanged predicate output does not wake downstream targets.
        actual=[c for c in changes if any(before[c['id']]['data'].get(k)!=v for k,v in c['data'].items())]
        outcome={'source_event':row['source_event'],'root_id':root['root_id'],'changed':bool(actual),
            'before':before,'changes':actual,'process_definition_digest':digest(PROCESSES[p['id']])}
        receipt=self.engine.apply({'api_version':3,'branch':self.app.branch,'request_id':self.app.key('causal-delivery',p['id'],row['source_event']),
            'expected_revision':self.app.revision(),'actor':'fixture','kind':('consequence' if p['id']==CLOSE else 'process') if actual else 'maintenance',
            'narrative':'Resolve only the installed native process consequence.','changes':actual,
            'causes':[row['source_event']],
            'processes':[{'op':'update','id':p['id'],'state':'active','last_tick':tick,'pending_judgment':None}],
            'process_runs':[{'process_id':p['id'],'run_key':'source:'+row['source_event'],'outcome':outcome,'status':'resolved'}]})
        trace={'root_id':root['root_id'],'root_event':root['source_event'],'source_event':row['source_event'],
            'parent_process':row['parent_id'],'depth':row['depth'],'native_process':p['id'],
            'native_event':receipt,'outcome':outcome,'after':{eid:self.visible(context,eid) for eid in before},
            'limit':'Authored synthetic process chain; not a physical weather model or participant judgment.'}
        ref=self.artifact(context,trace,[p['id'],row['source_event']],[root['source_record'],*before,'process:'+p['id']])
        if row['parent_id']:
            parent=self.db.execute('SELECT trace_ref_json FROM causal_deliveries WHERE workspace_id=? AND root_id=? AND process_id=? AND result_event=?',
                (self.ws,root['root_id'],row['parent_id'],row['source_event'])).fetchone()
            if not parent or not parent[0]:raise Fault('RECONCILE_REQUIRED')
            self.inherit(ref,[json.loads(parent[0])])
        self.persist_delivery(row,receipt['event_id'],ref)
        ancestors=[];cursor=row
        while cursor:
            if cursor['process_id'] in ancestors or len(ancestors)>=16:raise Fault('RECONCILE_REQUIRED')
            ancestors.append(cursor['process_id'])
            if not cursor['parent_id']:break
            cursor=self.db.execute('SELECT * FROM causal_deliveries WHERE workspace_id=? AND root_id=? AND process_id=? ORDER BY depth DESC LIMIT 1',(self.ws,root['root_id'],cursor['parent_id'])).fetchone()
        self.ingest(root,receipt,row['depth']+1,p['id'],ancestors)

    def step(self,context,op):
        if context.role!='operator':raise Fault('UNAVAILABLE')
        self.root(context,op['root_id']);deadline=time.monotonic()+.05;count=0
        while count<op['limit'] and time.monotonic()<deadline:
            row=self.db.execute("SELECT * FROM causal_deliveries WHERE workspace_id=? AND root_id=? AND state='queued' ORDER BY depth,process_id,source_event LIMIT 1",(self.ws,op['root_id'])).fetchone()
            if not row:break
            # A failed target's savepoint leaves earlier accepted deliveries and
            # unrelated roots usable; unexpected failures roll back the command.
            try:
                with UnitOfWork(self.db):self.deliver(context,dict(row))
            except (Fault,Rejected) as exc:
                self.db.execute("UPDATE causal_deliveries SET state='blocked',reason=? WHERE workspace_id=? AND process_id=? AND process_version=? AND source_event=?",
                    ('Dependency unavailable; inspect and explicitly resume this delivery.',self.ws,row['process_id'],row['process_version'],row['source_event']))
            count+=1
        return self.view(context,op['root_id'])

    def resume(self,context,op):
        if context.role!='operator':raise Fault('UNAVAILABLE')
        self.root(context,op['root_id'])
        self.db.execute("UPDATE causal_deliveries SET state='queued',reason='Explicit operator retry after dependency inspection.' WHERE workspace_id=? AND root_id=? AND state='blocked'",(self.ws,op['root_id']))
        return self.view(context,op['root_id'])

    def view(self,context,rid):
        root=self.root(context,rid);items=[]
        for row in self.db.execute('SELECT * FROM causal_deliveries WHERE workspace_id=? AND root_id=? ORDER BY depth,process_id,source_event',(self.ws,rid)):
            # Every installed target remains visible before any count/projection.
            if context.role!='operator':self.visible_process(context,row['process_id'])
            ref=json.loads(row['trace_ref_json']) if row['trace_ref_json'] else None
            if ref:self.app.artifact_bytes(context,ref)
            items.append({'process_id':row['process_id'],'state':row['state'],'reason':row['reason'],
                'source_event':row['source_event'],'result_event':row['result_event'],'trace_ref':ref,'depth':row['depth']})
        return {'kind':'causal','root_id':rid,'source_event':root['source_event'],'deliveries':items,
            'pending':sum(x['state']=='queued' for x in items),'blocked':sum(x['state'] in ('blocked','parked') for x in items)}
