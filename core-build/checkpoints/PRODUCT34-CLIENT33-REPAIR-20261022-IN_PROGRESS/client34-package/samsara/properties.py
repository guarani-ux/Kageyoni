"""Visibility-safe property changes and one concrete, ending-aware consumer.

Native definitions, bases, rules, resources and events remain authoritative.
This first resolver admits the registered synthetic replacement expression.
Other merge rules and operational timers refuse explicitly until implemented.
"""
from copy import deepcopy
from datetime import datetime,timezone
import json
import time
from uuid import uuid4

from kageyoni.engine import Rejected
from .protocol import Fault,digest,encoded

CAPACITY='fixture:load_capacity'
CLOCK='fixture:clock'
RULE='fixture:support'
WEIGHT=12


class Properties:
    def __init__(self,app):
        self.app,self.engine,self.db,self.ws=app,app.engine,app.db,app.workspace_id

    def ref(self,name):return {'id':name,'version':1,'digest':digest([self.app.runtime_digest,name])}

    def consumer_ref(self):
        row=self.db.execute('SELECT * FROM rule_definitions WHERE rule_id=? AND rule_version=1',(RULE,)).fetchone()
        if not row:raise Fault('DEPENDENCY')
        expected={'kind':'threshold','property':CAPACITY,'threshold':WEIGHT}
        if json.loads(row['definition_json'])!=expected or not row['mechanical'] or json.loads(row['inputs_json'])!=[CAPACITY]:raise Fault('DEPENDENCY')
        dependencies=[tuple(r) for r in self.db.execute('SELECT property_id,property_version,usage FROM rule_dependencies WHERE rule_id=? AND rule_version=1 ORDER BY property_id,property_version,usage',(RULE,))]
        if dependencies!=[(CAPACITY,1,'reads')]:raise Fault('DEPENDENCY')
        return {'id':RULE,'version':1,'digest':digest([dict(row),dependencies])}

    def catalog(self,context):
        clock=self.entity(context,CLOCK)
        return {'kind':'property_catalog','property_id':CAPACITY,'definition_version':1,'unit':'kg',
            'source_ref':self.ref('fixture:source:support'),'predicate_ref':self.ref('fixture:eligible:studio'),
            'ending_handler':self.ref('fixture:ending:lower-load'),'consumer_ref':self.consumer_ref(),
            'clock_id':CLOCK,'tick':clock['data']['tick'],
            'source':{'classification':'authored synthetic fixture','base_kg':10,'test_load_kg':WEIGHT,
                'ending':'Lower each dependent load to the studio floor. Prior accepted events remain.'}}

    def entity(self,context,eid):
        row=self.engine.get(self.app.branch,eid)
        if not row or (context.role!='operator' and not self.engine._visible(row,context.character_id)):
            raise Fault('UNAVAILABLE')
        return row

    def definition(self,pid,version):
        try:return dict(self.engine._definition(pid,version))
        except Rejected:raise Fault('UNAVAILABLE') from None

    def visible_base(self,context,eid,pid,version):
        raw=self.engine.property_value(self.app.branch,eid,pid,version)
        if raw and context.role!='operator':
            audience=json.loads(raw.get('context_json') or '{}').get('audience',[])
            if raw['visibility']!='public' and not (raw['visibility']=='restricted' and context.character_id in audience):
                return None
        return raw

    def require_property_access(self,context,eid,pid,version):
        self.entity(context,eid)
        raw=self.engine.property_value(self.app.branch,eid,pid,version)
        if raw is not None and self.visible_base(context,eid,pid,version) is None:raise Fault('UNAVAILABLE')

    def write_access(self,context,targets,pids):
        if context.role=='worker':raise Fault('UNAVAILABLE')
        for eid in targets:
            self.entity(context,eid)
            if context.role!='operator' and (eid!=context.character_id or any((p,v)!=(CAPACITY,1) for p,v in pids)):
                raise Fault('UNAVAILABLE')
            for pid,version in pids:self.require_property_access(context,eid,pid,version)

    def copy_grant(self,ref,principal):
        rows=self.db.execute('SELECT scope_json FROM property_read_grants WHERE workspace_id=? AND artifact_id=?',(self.ws,ref['id'])).fetchall()
        if not rows:return
        scopes=sorted({tuple(x) for row in rows for x in json.loads(row['scope_json'])},key=encoded)
        epoch=self.db.execute('SELECT max(authority_epoch) FROM activity_bindings WHERE workspace_id=? AND principal_id=?',(self.ws,principal)).fetchone()[0] or 1
        self.db.execute('INSERT OR REPLACE INTO property_read_grants VALUES(?,?,?,?,?)',(self.ws,principal,epoch,ref['id'],encoded(scopes)))

    def inherit(self,ref,principals,sources):
        self.app.causality.inherit(ref,sources)
        scopes=set()
        for source in sources:
            for row in self.db.execute('SELECT scope_json FROM property_read_grants WHERE workspace_id=? AND artifact_id=?',(self.ws,source['id'])):
                scopes.update(tuple(x) for x in json.loads(row['scope_json']))
        if not scopes:return
        for principal in principals:
            existing=self.db.execute('SELECT scope_json FROM property_read_grants WHERE workspace_id=? AND principal_id=? AND artifact_id=?',(self.ws,principal,ref['id'])).fetchone()
            merged=scopes | ({tuple(x) for x in json.loads(existing[0])} if existing else set())
            epoch=self.db.execute('SELECT max(authority_epoch) FROM activity_bindings WHERE workspace_id=? AND principal_id=?',(self.ws,principal)).fetchone()[0] or 1
            self.db.execute('INSERT OR REPLACE INTO property_read_grants VALUES(?,?,?,?,?)',(self.ws,principal,epoch,ref['id'],encoded(sorted(merged,key=encoded))))

    def attach_entities(self,ref,principals,entities):
        """Track disclosed native subjects without inventing property effects."""
        scope={(eid,None,None) for eid in entities}
        if not scope:return
        for principal in set(principals):
            prior=self.db.execute('SELECT scope_json FROM property_read_grants WHERE workspace_id=? AND principal_id=? AND artifact_id=?',
                (self.ws,principal,ref['id'])).fetchone()
            merged=scope|({tuple(x) for x in json.loads(prior[0])} if prior else set())
            epoch=self.db.execute('SELECT max(authority_epoch) FROM activity_bindings WHERE workspace_id=? AND principal_id=?',(self.ws,principal)).fetchone()[0] or 1
            self.db.execute('INSERT OR REPLACE INTO property_read_grants VALUES(?,?,?,?,?)',
                (self.ws,principal,epoch,ref['id'],encoded(sorted(merged,key=encoded))))

    def artifact(self,context,value,key,scope,recipient=None):
        principals=[context.principal_id]
        if recipient:principals.append('character:'+recipient)
        ref=self.app.put_json(value,self.app.key('property',key),principals=principals)
        for principal in principals:
            epoch=context.authority_epoch
            if principal!=context.principal_id:
                row=self.db.execute('SELECT max(authority_epoch) FROM activity_bindings WHERE workspace_id=? AND principal_id=?',(self.ws,principal)).fetchone()
                epoch=row[0] or 1
            self.db.execute('INSERT OR REPLACE INTO property_read_grants VALUES(?,?,?,?,?)',
                (self.ws,principal,epoch,ref['id'],encoded(scope)))
        return ref

    def authorize_artifact(self,context,ref):
        if context.role=='operator':return
        rows=self.db.execute('SELECT * FROM property_read_grants WHERE workspace_id=? AND artifact_id=?',(self.ws,ref['id'])).fetchall()
        if not rows:return
        row=next((r for r in rows if r['principal_id']==context.principal_id),None)
        if not row:raise Fault('UNAVAILABLE')
        # Artifact epochs record grant provenance. Live binding authorization
        # and current entity/property scopes govern each read; revoking an
        # unrelated binding must not revoke this still-authorized principal.
        for eid,pid,version in json.loads(row['scope_json']):
            self.entity(context,eid)
            if pid is not None:self.require_property_access(context,eid,pid,version)

    @staticmethod
    def assignment(base):
        if base is None:return None
        value=base['value']
        if base['state']=='known' and base['definition_type']=='integer':value=int(value)
        return {k:base[k] for k in ('entity_id','property_id','definition_version','state','unit','epistemic_status','visibility')}|{
            'value':value,'context':json.loads(base['context_json'])}

    def effects(self,eid,pid,version):
        return [dict(r) for r in self.db.execute('''SELECT * FROM property_effects WHERE workspace_id=? AND entity_id=?
            AND property_id=? AND definition_version=? AND state='active' ORDER BY effect_id,version''',(self.ws,eid,pid,version))]

    def interval(self,override):
        start,end=override['starts_at'],override['ends_at']
        if start['kind']!=end['kind']:raise Fault('INVALID')
        if start['kind']=='operational':
            try:
                a=datetime.strptime(start['utc'],'%Y-%m-%dT%H:%M:%SZ');b=datetime.strptime(end['utc'],'%Y-%m-%dT%H:%M:%SZ')
            except ValueError:raise Fault('INVALID') from None
            if b<=a:raise Fault('INVALID')
            raise Fault('UNSUPPORTED')  # Retained operational due-job work, not fake timers.
        if start['clock_id']!=end['clock_id'] or end['tick']<=start['tick']:raise Fault('INVALID')
        clock=self.engine.get(self.app.branch,start['clock_id'])
        if not clock or clock['domain']!='clock':raise Fault('UNAVAILABLE')
        return start,end,clock

    def current_effects(self,context,eid,pid,version,extra=(),excluding=()):
        rows=self.effects(eid,pid,version)
        values=[(json.loads(r['override_json']),self.ref('effect:'+digest([r['effect_id'],r['version'],eid]))) for r in rows if r['change_id'] not in excluding]
        values.extend((x,self.ref('effect:'+digest([x['effect_id'],x['version'],eid]))) for x in extra)
        eligible=[]
        for value,ref in values:
            start,end,clock=self.interval(value)
            self.entity(context,start['clock_id'])
            if start['tick']<=clock['data']['tick']<end['tick']:
                if value['predicate_ref']!=self.ref('fixture:eligible:studio'):raise Fault('DEPENDENCY')
                subject=self.entity(context,eid)
                if subject['data'].get('location')=='studio':eligible.append((value,ref))
        return eligible

    def resolve(self,context,eid,pid,version,extra=(),excluding=()):
        self.entity(context,eid);definition=self.definition(pid,version)
        base=self.visible_base(context,eid,pid,version);stored=self.assignment(base)
        effective={'state':base['state'],'value':stored['value']} if base else {'state':'unknown','value':None}
        hidden=self.engine.property_value(self.app.branch,eid,pid,version) is not None and base is None
        active=[] if hidden else self.current_effects(context,eid,pid,version,extra,excluding)
        refs=[]
        if active:
            constraints=json.loads(definition['constraints_json'])
            if constraints.get('resolver')!='replace':raise Fault('DEPENDENCY')
            if effective['state']!='known' and (effective['state'] not in ('unknown','disputed') or not constraints.get('allow_unknown_replace')):raise Fault('DEPENDENCY')
            if pid!=CAPACITY or version!=1:raise Fault('UNSUPPORTED')
            if any(x['operation']!='replace' for x,_ in active):raise Fault('UNSUPPORTED')
            priority=max(x['priority'] for x,_ in active);chosen=[(x,r) for x,r in active if x['priority']==priority]
            if len({digest([x['value'],x['unit']]) for x,_ in chosen})!=1:raise Fault('CONFLICT')
            effective={'state':'known','value':chosen[0][0]['value']};refs=[r for _,r in chosen]
        return definition,stored,effective,refs

    def inspect(self,context,eid,pid,version):
        d,stored,effective,refs=self.resolve(context,eid,pid,version)
        # No hidden assignment/effect/source bytes appear in this read record.
        # A property read needs the subject's identity and version, not its
        # entire native record (including internal event IDs and unrelated
        # narrative fields). Selection freshness still hashes the full row.
        subject=self.entity(context,eid)
        visible={'entity':{k:subject[k] for k in ('id','domain','version')},'stored':stored,'effective':effective,'overrides':refs,
            'definition':{'id':pid,'version':version,'type':d['value_type'],'unit':d['unit']}}
        ref=self.artifact(context,visible,('read',context.principal_id,context.authority_epoch,digest(visible)),[(eid,pid,version)] if self.engine.property_value(self.app.branch,eid,pid,version) is None or stored else [(eid,None,None)])
        return {'kind':'property','entity_id':eid,'property_id':pid,'definition_version':version,'value_type':d['value_type'],
            'unit':d['unit'],'stored':stored,'effective':effective,'applicable_override_refs':refs,
            'consumer_refs':[self.consumer_ref()] if (pid,version)==(CAPACITY,1) else [],'read_set_ref':ref}

    def matches(self,context,selector):
        if selector.get('dependency') and selector['dependency']!=self.consumer_ref():raise Fault('UNSUPPORTED')
        rows=[]
        for row in self.engine.state(self.app.branch):
            if context.role!='operator' and not self.engine._visible(row,context.character_id):continue
            eid=row['id'];data=row['data']
            if 'ids' in selector and eid not in selector['ids']:continue
            if 'facet' in selector and selector['facet'] not in self.engine._entity_facets(self.app.branch,eid):continue
            if 'location' in selector and data.get('location')!=selector['location']:continue
            if 'affiliation' in selector:
                affiliations=[r for r in self.engine.state(self.app.branch) if r['domain']=='affiliation' and r['data'].get('character')==eid and r['data'].get('faction')==selector['affiliation'] and (context.role=='operator' or self.engine._visible(r,context.character_id))]
                if not affiliations:continue
            props=[p for p in self.engine.properties(self.app.branch,eid,viewer=None if context.role=='operator' else context.character_id)]
            if 'property_id' in selector:props=[p for p in props if p['property_id']==selector['property_id']]
            if 'property_id' in selector and not props:continue
            if 'state' in selector and not any(p['state']==selector['state'] for p in props):continue
            if selector.get('dependency') and not any(p['property_id']==CAPACITY for p in props):continue
            rows.append({'id':eid,'version':row['version'],'digest':digest(row)})
        return sorted(rows,key=lambda x:x['id'])

    def signature(self,context,selector):
        members=self.matches(context,selector);details=[]
        for ref in members:
            eid=ref['id'];props=self.engine.properties(self.app.branch,eid,viewer=None if context.role=='operator' else context.character_id)
            effects=[r for r in self.db.execute("SELECT effect_id,version,override_digest,state FROM property_effects WHERE workspace_id=? AND entity_id=? ORDER BY effect_id,version",(self.ws,eid))]
            details.append([ref,props,[tuple(r) for r in effects]])
        definitions=[tuple(r) for r in self.db.execute('SELECT * FROM property_definitions ORDER BY property_id,definition_version')]
        lifecycles=[tuple(r) for r in self.db.execute('SELECT * FROM property_lifecycle ORDER BY sequence')]
        rules=[tuple(r) for r in self.db.execute('SELECT * FROM rule_definitions ORDER BY rule_id,rule_version')]
        dependencies=[tuple(r) for r in self.db.execute('SELECT * FROM rule_dependencies ORDER BY rule_id,rule_version,property_id,property_version')]
        registry=[tuple(r) for r in self.db.execute('SELECT * FROM registry_dependencies ORDER BY rowid')]
        return members,digest([details,definitions,lifecycles,rules,dependencies,registry])

    def snapshot(self,context,sid,fresh=True,historical=False):
        row=self.db.execute('SELECT * FROM property_selections WHERE workspace_id=? AND snapshot_id=?',(self.ws,sid)).fetchone()
        if not row or row['principal_id']!=context.principal_id or row['authority_epoch']!=context.authority_epoch or (not historical and row['expires']<=time.time()):raise Fault('UNAVAILABLE')
        frozen=json.loads(row['frozen_json'])
        if digest(frozen)!=row['frozen_digest']:raise Fault('RECONCILE_REQUIRED')
        for ref in frozen['targets']:self.entity(context,ref['id'])
        for eid,pid,version in frozen.get('scope',[]):self.require_property_access(context,eid,pid,version)
        if fresh:
            _,signature=self.signature(context,frozen['selector'])
            if row['revision']!=self.app.revision() or signature!=frozen['signature']:raise Fault('STALE')
        return dict(row),frozen

    def select(self,context,selector):
        query=deepcopy(selector);cursor=query.pop('cursor');query['cursor']=None
        if 'state' in query and 'property_id' not in query:raise Fault('INVALID')
        offset=0;deadline=time.time()+300
        if cursor:
            c=self.db.execute('SELECT * FROM property_selection_cursors WHERE cursor_id=?',(cursor,)).fetchone()
            if not c:raise Fault('UNAVAILABLE')
            old,frozen=self.snapshot(context,c['snapshot_id'])
            if query!=frozen['selector']:raise Fault('UNAVAILABLE')
            offset=c['offset'];deadline=old['expires']
        members,signature=self.signature(context,query)
        if len(members)>512:raise Fault('BUDGET')
        if self.db.execute('SELECT count(*) FROM property_selections WHERE workspace_id=? AND principal_id=? AND expires>?',(self.ws,context.principal_id,time.time())).fetchone()[0]>=128:raise Fault('BUDGET')
        page=members[offset:offset+query['limit']];sid='selection:'+uuid4().hex
        scope=[]
        for target in page:
            for prop in self.engine.properties(self.app.branch,target['id'],viewer=None if context.role=='operator' else context.character_id):
                if prop['property_id']==query.get('property_id') or (query.get('dependency') and prop['property_id']==CAPACITY):
                    scope.append((target['id'],prop['property_id'],prop['definition_version']))
        frozen={'selector':query,'signature':signature,'targets':page,'membership':members,'scope':scope}
        self.db.execute('INSERT INTO property_selections VALUES(?,?,?,?,?,?,?,?,?)',(sid,self.ws,context.principal_id,context.authority_epoch,self.app.branch,self.app.revision(),deadline,encoded(frozen),digest(frozen)))
        following=None
        if offset+len(page)<len(members):
            following='selection-cursor:'+uuid4().hex
            self.db.execute('INSERT INTO property_selection_cursors VALUES(?,?,?)',(following,sid,offset+len(page)))
        return {'kind':'selection','snapshot_id':sid,'selector_digest':digest(query),'authority_epoch':context.authority_epoch,
            'expires_at':datetime.fromtimestamp(deadline,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'selected_refs':page,'cursor':following}

    def validate_change(self,context,proposal):
        if proposal['ending_policy']!='cancel_and_reconcile':raise Fault('UNSUPPORTED')
        targets=proposal['targets'];pids={(a['property_id'],a['definition_version']) for a in proposal['assignments']+proposal['overrides']}
        if not targets or not pids:raise Fault('INVALID')
        if len(targets)>16:raise Fault('BUDGET')
        self.write_access(context,targets,pids)
        seen=set()
        for a in proposal['assignments']:
            key=(a['entity_id'],a['property_id'],a['definition_version'])
            if a['entity_id'] not in targets or key in seen:raise Fault('INVALID')
            seen.add(key)
            if context.role!='operator' and a['visibility']!='public':raise Fault('UNAVAILABLE')
            definition=self.definition(a['property_id'],a['definition_version'])
            if a['unit']!=definition['unit']:raise Fault('INVALID')
            self.engine._validate_property_assignment(self.app.branch,a)
        def candidate_state(eid):
            proposed=next((a for a in proposal['assignments'] if (a['entity_id'],a['property_id'],a['definition_version'])==(eid,CAPACITY,1)),None)
            base=proposed if proposed is not None else self.visible_base(context,eid,CAPACITY,1)
            return base['state'] if base else 'unknown'
        for eid in targets:
            if self.effects(eid,CAPACITY,1) or proposal['overrides']:
                constraints=json.loads(self.definition(CAPACITY,1)['constraints_json'])
                state=candidate_state(eid)
                if constraints.get('resolver')!='replace' or (state!='known' and (state not in ('unknown','disputed') or not constraints.get('allow_unknown_replace'))):raise Fault('DEPENDENCY')
        for x in proposal['overrides']:
            self.app.extensions.require_new_use(context)
            if (x['property_id'],x['definition_version'],x['operation'])!=(CAPACITY,1,'replace'):raise Fault('UNSUPPORTED')
            if x['source_ref']!=self.ref('fixture:source:support') or x['predicate_ref']!=self.ref('fixture:eligible:studio') or x['ending_handler']!=self.ref('fixture:ending:lower-load'):raise Fault('DEPENDENCY')
            start,end,clock=self.interval(x)
            if start['clock_id']!=CLOCK:raise Fault('UNSUPPORTED')
            self.entity(context,CLOCK)
            if end['tick']<=clock['data']['tick']:raise Fault('STALE')
            if self.db.execute('SELECT 1 FROM property_effects WHERE workspace_id=? AND effect_id=? AND version=?',(self.ws,x['effect_id'],x['version'])).fetchone():raise Fault('CONFLICT')
            for eid in targets:
                value={'entity_id':eid,'property_id':CAPACITY,'definition_version':1,'state':'known','value':x['value'],'unit':x['unit'],'context':{},'epistemic_status':'proposed','visibility':'public'}
                self.engine._validate_property_assignment(self.app.branch,value)
                definition=self.definition(CAPACITY,1);constraints=json.loads(definition['constraints_json'])
                state=candidate_state(eid)
                if constraints.get('resolver')!='replace' or (state!='known' and (state not in ('unknown','disputed') or not constraints.get('allow_unknown_replace'))):raise Fault('DEPENDENCY')
        if len({(x['effect_id'],x['version']) for x in proposal['overrides']})!=len(proposal['overrides']):raise Fault('INVALID')
        active=self.db.execute("SELECT count(*) FROM property_effects WHERE workspace_id=? AND state='active'",(self.ws,)).fetchone()[0]
        if active+len(targets)*len(proposal['overrides'])>32:raise Fault('BUDGET')
        # Evaluate conflicts even for future intervals: incompatible coexisting
        # replacements may not be admitted just because their clock is early.
        for eid in targets:
            candidates=[json.loads(r['override_json']) for r in self.effects(eid,CAPACITY,1)]+proposal['overrides']
            for i,a in enumerate(candidates):
                sa,ea,_=self.interval(a)
                for b in candidates[i+1:]:
                    sb,eb,_=self.interval(b)
                    if sa['clock_id']==sb['clock_id'] and max(sa['tick'],sb['tick'])<min(ea['tick'],eb['tick']) and a['priority']==b['priority'] and digest([a['value'],a['unit']])!=digest([b['value'],b['unit']]):raise Fault('CONFLICT')

    def prepare(self,context,op):
        _,frozen=self.snapshot(context,op['snapshot_id'])
        proposal={k:deepcopy(op[k]) for k in ('snapshot_id','assignments','overrides','ending_policy','reason')}
        proposal['targets']=[r['id'] for r in frozen['targets']]
        self.validate_change(context,proposal)
        cid='change:'+uuid4().hex;sha=digest(proposal)
        scope=[(eid,pid,ver) for eid in proposal['targets'] for pid,ver in {(x['property_id'],x['definition_version']) for x in proposal['assignments']+proposal['overrides']}]
        diff={'change_id':cid,'reason':proposal['reason'],'targets':proposal['targets'],'assignments':proposal['assignments'],'overrides':proposal['overrides'],
            'before':[self.inspect(context,eid,pid,ver) for eid,pid,ver in scope],'ending_policy':proposal['ending_policy'],
            'ending':'Dependent supported loads are lowered to the studio floor before this replacement stops being used.'}
        ref=self.artifact(context,diff,('diff',cid),scope)
        self.db.execute('INSERT INTO property_change_sets VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (cid,self.ws,op['snapshot_id'],context.principal_id,context.authority_epoch,encoded(proposal),sha,'prepared',encoded(ref),None,None))
        if proposal['overrides']:self.app.extensions.pin(context,'change',cid)
        return self.change_view(context,cid,sha)

    def change(self,context,cid,sha):
        row=self.db.execute('SELECT * FROM property_change_sets WHERE workspace_id=? AND change_id=?',(self.ws,cid)).fetchone()
        if not row or (context.role!='operator' and row['principal_id']!=context.principal_id):raise Fault('UNAVAILABLE')
        if row['proposal_digest']!=sha:raise Fault('CONFLICT')
        proposal=json.loads(row['proposal_json'])
        if digest(proposal)!=sha:raise Fault('RECONCILE_REQUIRED')
        for eid in proposal['targets']:self.entity(context,eid)
        return dict(row),proposal

    def change_view(self,context,cid,sha):
        row,p=self.change(context,cid,sha)
        self.app.artifact_bytes(context,json.loads(row['diff_ref_json']))
        return {'kind':'change','change_id':cid,'digest':sha,'snapshot_id':row['snapshot_id'],'visible_diff_ref':json.loads(row['diff_ref_json']),
            'consumer_refs':(self.app.extensions.captured_consumers(cid) or [self.consumer_ref()]) if any(x['property_id']==CAPACITY for x in p['assignments']+p['overrides']) else [],
            'boundary':'checkpoint','status':row['status']}

    def emit(self,context,identity,description,changes=(),assignments=()):
        if not changes:
            changes=[{'op':'create','domain':'consequence','id':self.app.key('property-audit',identity),
                'data':{'subject':'synthetic property operation','effect':description,'duration':'recorded boundary','ending_condition':'history retained','reversibility':'conditional'},
                'status':'proposed','visibility':'gm','evidence':[{'note':'Actual local operation on an authored synthetic fixture.'}]}]
        return self.engine.apply({'api_version':3,'branch':self.app.branch,'request_id':self.app.key('property-event',identity),
            'expected_revision':self.app.revision(),'actor':context.character_id or 'fixture','kind':'property_assignment','narrative':description,
            'changes':list(changes),'properties':list(assignments)})

    def persist_status(self,cid,status,event):
        self.db.execute('UPDATE property_change_sets SET status=?,applied_event=coalesce(applied_event,?) WHERE change_id=?',(status,event,cid))

    def apply(self,context,op):
        row,p=self.change(context,op['change_id'],op['digest'])
        if op['boundary']!='checkpoint':raise Fault('DEPENDENCY')
        if row['status']!='prepared':return self.change_view(context,op['change_id'],op['digest'])
        self.snapshot(context,p['snapshot_id']);self.validate_change(context,p)
        self.app.extensions.apply_pin(context,row['change_id'])
        event=self.emit(context,('apply',row['change_id']),'Admit an atomic typed property change.',assignments=p['assignments'])
        for eid in p['targets']:
            for x in p['overrides']:
                self.db.execute('INSERT INTO property_effects VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (self.ws,x['effect_id'],x['version'],eid,row['change_id'],x['property_id'],x['definition_version'],encoded(x),digest(x),'active',None))
        self.persist_status(row['change_id'],'active',event['event_id'])
        return self.change_view(context,op['change_id'],op['digest'])

    def lower_changes(self,rows):
        changes=[]
        for row in rows:
            self.app.extensions.ending_for('support',row['support_id'])
            record=self.engine.get(self.app.branch,row['resource_id'])
            changes.append({'op':'patch','id':row['resource_id'],'expected_version':record['version'],
                'data':{'holder':'studio','availability':'on the studio floor'},'evidence':[{'note':'Pinned synthetic lower-load ending.'}]})
        return changes

    def end(self,context,row,p,identity,effect_keys=None):
        self.app.extensions.ending_for('change',row['change_id'])
        effects=self.db.execute("SELECT * FROM property_effects WHERE workspace_id=? AND change_id=? AND state='active'",(self.ws,row['change_id'])).fetchall()
        if effect_keys is not None:effects=[r for r in effects if (r['effect_id'],r['version'],r['entity_id']) in effect_keys]
        ended={self.ref('effect:'+digest([r['effect_id'],r['version'],r['entity_id']]))['id'] for r in effects}
        supports=[dict(r) for r in self.db.execute('SELECT * FROM property_support_bindings WHERE workspace_id=? AND active=1',(self.ws,))
            if ended & {x['id'] for x in json.loads(r['dependency_json'])['effect_refs']}]
        event=self.emit(context,identity,'End a typed replacement and lower its dependent loads.',self.lower_changes(supports))
        for effect in effects:
            self.db.execute("UPDATE property_effects SET state='ended',ended_event=? WHERE workspace_id=? AND effect_id=? AND version=? AND entity_id=?",(event['event_id'],self.ws,effect['effect_id'],effect['version'],effect['entity_id']))
        for support in supports:
            self.db.execute('UPDATE property_support_bindings SET active=0 WHERE workspace_id=? AND support_id=?',(self.ws,support['support_id']))
        remaining=self.db.execute("SELECT 1 FROM property_effects WHERE workspace_id=? AND change_id=? AND state='active'",(self.ws,row['change_id'])).fetchone()
        self.db.execute("UPDATE property_change_sets SET status=?,ended_event=? WHERE change_id=?",('active' if remaining else 'withdrawn',event['event_id'],row['change_id']))

    def withdraw(self,context,op):
        row,p=self.change(context,op['change_id'],op['digest'])
        if op['boundary']!='checkpoint':raise Fault('DEPENDENCY')
        if row['status']=='prepared':
            self.db.execute("UPDATE property_change_sets SET status='withdrawn' WHERE change_id=?",(row['change_id'],))
        elif row['status']=='active':
            self.end(context,row,p,('withdraw',row['change_id']))
        return self.change_view(context,op['change_id'],op['digest'])

    def advance(self,context,op,request_id):
        if context.role=='worker' or op['clock_id']!=CLOCK:raise Fault('UNAVAILABLE')
        clock=self.entity(context,CLOCK)
        self.emit(context,('advance',context.principal_id,request_id),'Advance only the selected synthetic fictional clock.',
            [{'op':'patch','id':CLOCK,'expected_version':clock['version'],'data':{'tick':clock['data']['tick']+op['ticks']},'evidence':[{'note':'Explicit fictional clock command.'}]}])
        self.expire(context)
        return self.catalog(context)

    def expire(self,context):
        due={}
        for row in self.db.execute("SELECT * FROM property_effects WHERE workspace_id=? AND state='active'",(self.ws,)):
            start,end,clock=self.interval(json.loads(row['override_json']))
            if clock['data']['tick']>=end['tick']:due.setdefault(row['change_id'],set()).add((row['effect_id'],row['version'],row['entity_id']))
        for cid in sorted(due):
            row=self.db.execute('SELECT * FROM property_change_sets WHERE change_id=?',(cid,)).fetchone()
            self.end(context,dict(row),json.loads(row['proposal_json']),('expire',cid,sorted(due[cid])),due[cid])

    def support(self,context,op,request_id):
        eid=op['entity_id'];self.write_access(context,[eid],{(CAPACITY,1)})
        if self.entity(context,eid)['data'].get('location')!='studio':raise Fault('DEPENDENCY')
        existing=self.db.execute('SELECT * FROM property_support_bindings WHERE workspace_id=? AND support_id=?',(self.ws,op['support_id'])).fetchone()
        if existing:
            if existing['entity_id']!=eid:raise Fault('CONFLICT')
            return self.support_view(context,op['support_id'])
        self.app.extensions.require_new_use(context)
        if self.db.execute('SELECT 1 FROM property_support_bindings WHERE workspace_id=? AND entity_id=? AND active=1',(self.ws,eid)).fetchone():raise Fault('CONFLICT')
        lifecycle=self.db.execute('SELECT state FROM property_lifecycle WHERE property_id=? AND definition_version=1 ORDER BY sequence DESC LIMIT 1',(CAPACITY,)).fetchone()
        if not lifecycle or lifecycle[0]!='active':raise Fault('DEPENDENCY')
        self.consumer_ref()
        d,stored,effective,refs=self.resolve(context,eid,CAPACITY,1)
        if effective['state']!='known':raise Fault('DEPENDENCY')
        evaluated=self.engine.evaluate_rule(RULE,1,self.app.branch,eid,inputs={CAPACITY:effective['value']})
        supported=evaluated['output']['value'] is True
        trace={'source_ref':self.ref('fixture:source:support'),'subject':eid,'stored':stored,'effective':effective,
            'definition_ref':{'id':CAPACITY,'version':1,'digest':digest(d)},'rule_ref':self.consumer_ref(),'rule_evaluation':evaluated,
            'effect_refs':refs,'operation':'support 12 kg','state':'supported' if supported else 'refused','event':None}
        if supported:
            rid=self.app.key('supported-resource',op['support_id'])
            event=self.emit(context,('support',op['support_id']),'Support the admitted 12 kg synthetic load.',
                [{'op':'create','domain':'resource','id':rid,'data':{'holder':eid,'name':'Synthetic 12 kg support load','quantity':WEIGHT,'unit':'kg','availability':'supported'},
                    'visibility':'public','status':'proposed','evidence':[{'note':'Authored fixture; actual consumer read the resolved capacity.'}]}])
            trace['event']=event
        ref=self.artifact(context,trace,('support-trace',context.principal_id,request_id),[(eid,CAPACITY,1)],recipient=eid)
        if supported:self.db.execute('INSERT INTO property_support_bindings VALUES(?,?,?,?,?,?,?,?)',
            (self.ws,op['support_id'],self.app.branch,eid,rid,encoded(trace),encoded(ref),1))
        if supported:self.app.extensions.pin(context,'support',op['support_id'])
        return {'kind':'support','support_id':op['support_id'],'entity_id':eid,'state':trace['state'],'trace_ref':ref}

    def support_view(self,context,sid):
        row=self.db.execute('SELECT * FROM property_support_bindings WHERE workspace_id=? AND support_id=?',(self.ws,sid)).fetchone()
        if not row:raise Fault('UNAVAILABLE')
        self.require_property_access(context,row['entity_id'],CAPACITY,1)
        ref=json.loads(row['trace_ref_json']);self.app.artifact_bytes(context,ref)
        return {'kind':'support','support_id':sid,'entity_id':row['entity_id'],'state':'supported' if row['active'] else 'released','trace_ref':ref}

    def release(self,context,sid):
        view=self.support_view(context,sid);self.write_access(context,[view['entity_id']],{(CAPACITY,1)})
        if view['state']=='supported':
            row=self.db.execute('SELECT * FROM property_support_bindings WHERE workspace_id=? AND support_id=?',(self.ws,sid)).fetchone()
            self.emit(context,('release',sid),'Explicitly lower the supported synthetic load.',self.lower_changes([dict(row)]))
            self.db.execute('UPDATE property_support_bindings SET active=0 WHERE workspace_id=? AND support_id=?',(self.ws,sid))
        return self.support_view(context,sid)

    def reconcile_supports(self,context,request_id):
        from dataclasses import replace
        trusted=replace(context,role='operator')
        rows=[]
        for row in self.db.execute('SELECT * FROM property_support_bindings WHERE workspace_id=? AND active=1',(self.ws,)):
            subject=self.engine.get(self.app.branch,row['entity_id'])
            _,_,effective,_=self.resolve(trusted,row['entity_id'],CAPACITY,1)
            if not subject or subject['data'].get('location')!='studio' or effective['state']!='known' or effective['value']<WEIGHT:
                rows.append(dict(row))
        if rows:
            self.emit(context,('reconcile-support',context.principal_id,request_id),'Lower supported loads whose current capacity or eligibility no longer suffices.',self.lower_changes(rows))
            for row in rows:self.db.execute('UPDATE property_support_bindings SET active=0 WHERE workspace_id=? AND support_id=?',(self.ws,row['support_id']))

    def reauthorize_replay(self,context,operation,view):
        if operation['name']=='property.select':self.snapshot(context,view['snapshot_id'],fresh=False,historical=True)
        elif view and view['kind']=='property_catalog':self.entity(context,CLOCK)
        elif view and view['kind']=='property':self.require_property_access(context,view['entity_id'],view['property_id'],view['definition_version'])
        elif view and view['kind']=='change':self.change(context,view['change_id'],view['digest'])
        elif view and view['kind']=='support':self.require_property_access(context,view['entity_id'],CAPACITY,1)
