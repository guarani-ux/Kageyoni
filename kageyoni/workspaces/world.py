"""Authored encounter routing over existing world, dialogue and Will mechanics.

An encounter is operational orchestration. Only Engine.apply commits fiction.
Unknown semantics suspend into an explicit bounded choice; no model is needed
for authored paths. Existing Will preparation retains its durable randomness.
"""
from copy import deepcopy
import hashlib
import json

from ..engine import require, digest, encoded, Rejected
from ..persistence.unit_of_work import UnitOfWork
from ..intelligence.contracts import text, integer


def _validate(spec):
    required={'title','roles','initial_state','states','loops','actions'}
    require(isinstance(spec,dict) and required <= set(spec) <= required|{'visibility','scene_id','max_steps'},'invalid encounter definition fields')
    result=deepcopy(spec);text(result['title'],'encounter title')
    result.setdefault('visibility','gm');result.setdefault('max_steps',100)
    require(result['visibility'] in ('gm','public'),'invalid encounter visibility')
    integer(result['max_steps'],'max steps');require(result['max_steps']<=1000,'encounter budget too large')
    roles=result['roles'];require(isinstance(roles,list) and roles and len(roles)==len(set(roles)) and all(isinstance(x,str) and x for x in roles),'invalid participant roles')
    states=result['states'];actions=result['actions'];loops=result['loops']
    require(isinstance(states,dict) and 1<=len(states)<=128 and result['initial_state'] in states,'invalid states')
    require(isinstance(actions,dict) and len(actions)<=256,'invalid actions')
    require(isinstance(loops,list) and len(loops)<=64,'invalid loops')
    loopmap={}
    for loop in loops:
        require(isinstance(loop,dict) and {'id','kind','required','depends_on','continuable'} <= set(loop) <= {'id','kind','required','depends_on','continuable','parent','cancellable'},'invalid loop contract')
        text(loop['id'],'loop id');text(loop['kind'],'loop kind')
        require(loop['id'] not in loopmap and type(loop['required']) is bool and type(loop['continuable']) is bool,'invalid or duplicate loop')
        loop.setdefault('cancellable',False);require(type(loop['cancellable']) is bool,'invalid cancellation rule')
        require(isinstance(loop['depends_on'],list) and len(set(loop['depends_on']))==len(loop['depends_on']),'invalid dependencies')
        loopmap[loop['id']]=loop
    def walk(lid,trail,parent_only=False):
        require(lid in loopmap and lid not in trail,'unknown or cyclic encounter dependency')
        edges=[loopmap[lid]['parent']] if parent_only and loopmap[lid].get('parent') else [] if parent_only else loopmap[lid]['depends_on']
        for dep in edges:walk(dep,trail|{lid},parent_only)
    for lid in loopmap:
        walk(lid,set());walk(lid,set(),True)
    for sid,state in states.items():
        require(isinstance(sid,str) and sid and isinstance(state,dict) and set(state)=={'phase','outcome','actions'},'invalid state contract')
        require(state['phase'] in ('active','completed','failed') and state['outcome'] in ('unresolved','achieved','partly_achieved','not_achieved'),'invalid state disposition')
        require((state['phase']=='active')==(state['outcome']=='unresolved'),'active state cannot claim objective completion')
        require(isinstance(state['actions'],list) and len(state['actions'])==len(set(state['actions'])) and all(a in actions for a in state['actions']),'unknown or duplicate state action')
        require(state['phase']=='active' or not state['actions'],'terminal state cannot offer already-settled choices')
    require(states[result['initial_state']]['phase']=='active','encounter must begin in an active state')
    for aid,action in actions.items():
        required_action={'label','actor_role','kind','payload','resolve_loops'}
        allowed=required_action|{'next_state','next_by_outcome','requirements','detach_loops','cancel_loops'}
        require(isinstance(aid,str) and aid and isinstance(action,dict) and required_action <= set(action) <= allowed,'invalid action contract')
        text(action['label'],'action label');require(action['actor_role'] in roles,'action actor role unavailable')
        require(action['kind'] in ('dialogue','will','event','judgment'),'unsupported encounter action')
        require(isinstance(action['payload'],dict),'action payload required')
        for name in ('resolve_loops','requirements','detach_loops','cancel_loops'):
            action.setdefault(name,[]);require(isinstance(action[name],list),'invalid '+name)
        require(len(set(action['resolve_loops']))==len(action['resolve_loops']) and all(l in loopmap for l in action['resolve_loops']),'invalid resolved loops')
        for req in action['requirements']:
            require(isinstance(req,dict) and set(req)=={'record_id','field','equals'},'invalid requirement')
        for item in action['detach_loops']:
            require(isinstance(item,dict) and set(item)=={'loop_id','record_id'} and item['loop_id'] in loopmap and loopmap[item['loop_id']]['continuable'],'loop cannot continue independently')
        for item in action['cancel_loops']:
            require(isinstance(item,dict) and set(item)=={'loop_id','reason'} and item['loop_id'] in loopmap and loopmap[item['loop_id']]['cancellable'],'loop cannot be cancelled')
            text(item['reason'],'loop cancellation reason')
        targets=[action['next_state']] if 'next_state' in action else list(action.get('next_by_outcome',{}).values())
        if action['kind']=='judgment':
            p=action['payload'];require(set(p)=={'question','choices','unknowns'},'invalid judgment packet')
            text(p['question'],'judgment question');require(isinstance(p['unknowns'],list),'judgment unknowns required')
            require(isinstance(p['choices'],list) and 1<=len(p['choices'])<=12,'judgment needs bounded choices')
            seen=set()
            for choice in p['choices']:
                require(isinstance(choice,dict) and set(choice)=={'id','label','next_state'},'invalid judgment choice')
                text(choice['id'],'choice id');text(choice['label'],'choice label');require(choice['id'] not in seen,'duplicate choice')
                seen.add(choice['id']);targets.append(choice['next_state'])
        require(targets and all(s in states for s in targets),'action has unknown continuation state')
    require(len(encoded(result))<=500000,'encounter definition too large')
    return result


def _expand(value,participants,encounter_id):
    if isinstance(value,dict):
        if set(value)=={'$role'}:
            require(value['$role'] in participants,'unknown participant placeholder');return participants[value['$role']]
        if set(value)=={'$encounter'}:
            text(value['$encounter'],'encounter record suffix');return encounter_id+':'+value['$encounter']
        return {k:_expand(v,participants,encounter_id) for k,v in value.items()}
    if isinstance(value,list):return [_expand(v,participants,encounter_id) for v in value]
    return deepcopy(value)


def _same_value(left,right):
    if type(left) is bool or type(right) is bool:return type(left) is type(right) and left==right
    if type(left) in (int,float) and type(right) in (int,float):return left==right
    if type(left) is not type(right):return False
    if isinstance(left,dict):return set(left)==set(right) and all(_same_value(left[k],right[k]) for k in left)
    if isinstance(left,list):return len(left)==len(right) and all(_same_value(a,b) for a,b in zip(left,right))
    return left==right


class Encounters:
    def __init__(self,engine):self.engine=engine;self.db=engine.db

    def _installed(self):
        require(self.db.execute("SELECT 1 FROM engine_versions WHERE component='encounter_interface' AND version='1'").fetchone(),'encounter interface not installed')

    def define(self,definition_id,version,spec,request_id,viewer=None):
        self._installed();require(viewer is None,'owner view required to author encounters')
        text(definition_id,'definition id');integer(version,'definition version');text(request_id,'request id');spec=_validate(spec)
        with UnitOfWork(self.db):
            old=self.db.execute('SELECT * FROM encounter_definitions WHERE request_id=?',(request_id,)).fetchone()
            if old:
                require(old['definition_id']==definition_id and old['version']==version and old['digest']==digest(spec),'definition request conflict')
                return dict(definition_id=definition_id,version=version,digest=old['digest'],replayed=True)
            maximum=self.db.execute('SELECT MAX(version) FROM encounter_definitions WHERE definition_id=?',(definition_id,)).fetchone()[0] or 0
            require(version==maximum+1,'definition versions must be contiguous')
            self.db.execute('INSERT INTO encounter_definitions VALUES(?,?,?,?,?)',(definition_id,version,encoded(spec),digest(spec),request_id))
            return dict(definition_id=definition_id,version=version,digest=digest(spec),replayed=False)

    def _definition(self,did,version):
        row=self.db.execute('SELECT * FROM encounter_definitions WHERE definition_id=? AND version=?',(did,version)).fetchone()
        require(row is not None,'encounter definition unavailable');return json.loads(row['spec_json'])

    def _instance(self,branch,eid,viewer=None):
        self._installed();row=self.db.execute('SELECT * FROM encounter_instances WHERE branch=? AND encounter_id=?',(branch,eid)).fetchone()
        require(row is not None,'encounter unavailable')
        initial=self.db.execute('SELECT payload_json FROM encounter_events WHERE branch=? AND encounter_id=? AND revision=1',(branch,eid)).fetchone()
        require(initial is not None,'encounter start history unavailable')
        pinned=json.loads(initial['payload_json'])
        require(row['definition_id']==pinned['definition_id'] and row['definition_version']==pinned['definition_version']
                and json.loads(row['participants_json'])==pinned['participants'],'encounter identity differs from pinned start')
        spec=self._definition(row['definition_id'],row['definition_version']);participants=json.loads(row['participants_json'])
        permitted={r['id']:r for r in self.engine.context(branch,viewer=viewer)['records']}
        require(viewer is None or spec['visibility']=='public','encounter unavailable')
        require(all(cid in permitted and permitted[cid]['domain']=='character' for cid in participants.values()),'encounter unavailable')
        if spec.get('scene_id'):require(spec['scene_id'] in permitted,'encounter scene unavailable')
        return row,spec,participants,permitted

    def _replay(self,request_id,payload,branch,eid,viewer):
        old=self.db.execute('SELECT * FROM encounter_events WHERE request_id=?',(request_id,)).fetchone()
        if old:
            require(old['branch']==branch and old['encounter_id']==eid,'encounter request conflict')
            self._instance(branch,eid,viewer)
            require(old['payload_hash']==digest(payload),'encounter request reused with different payload')
            return dict(json.loads(old['receipt_json']),replayed=True)
        return None

    def _write(self,row,before,after,payload,world_receipt=None):
        revision=row['revision']+1
        after['world_revision']=self.engine.branch(row['branch'])['revision']
        receipt=dict(encounter_interface='1',branch=row['branch'],encounter_id=row['encounter_id'],
            definition_id=row['definition_id'],definition_version=row['definition_version'],state_revision=revision,
            phase=after['phase'],outcome=after['outcome'],state=after['current_state'],world_revision=after['world_revision'],
            world_receipt=world_receipt,state_digest=digest(after),replayed=False)
        self.db.execute('UPDATE encounter_instances SET revision=?,state_json=? WHERE branch=? AND encounter_id=?',
            (revision,encoded(after),row['branch'],row['encounter_id']))
        self.db.execute('INSERT INTO encounter_events(branch,encounter_id,request_id,revision,payload_json,payload_hash,before_json,after_json,receipt_json) VALUES(?,?,?,?,?,?,?,?,?)',
            (row['branch'],row['encounter_id'],payload['request_id'],revision,encoded(payload),digest(payload),encoded(before) if before is not None else None,encoded(after),encoded(receipt)))
        return receipt

    def start(self,branch,definition_id,definition_version,encounter_id,request_id,expected_revision,participants,
              viewer=None,continuation_of=None,evidence_refs=None):
        self._installed();text(encounter_id,'encounter id');text(request_id,'request id');integer(expected_revision,'expected revision',0)
        require(isinstance(participants,dict),'participants must map roles to stable character IDs')
        payload=dict(branch=branch,definition_id=definition_id,definition_version=definition_version,encounter_id=encounter_id,
            request_id=request_id,expected_revision=expected_revision,participants=participants,viewer=viewer,
            continuation_of=continuation_of,evidence_refs=evidence_refs or [])
        with UnitOfWork(self.db):
            prior=self._replay(request_id,payload,branch,encounter_id,viewer)
            if prior:return prior
            require(self.engine.branch(branch)['revision']==expected_revision,'stale branch revision')
            spec=self._definition(definition_id,definition_version)
            require(set(participants)==set(spec['roles']),'participant roles differ from definition')
            visible={r['id']:r for r in self.engine.context(branch,viewer=viewer)['records']}
            require(all(cid in visible and visible[cid]['domain']=='character' for cid in participants.values()),'participant unavailable')
            require(viewer is None or spec['visibility']=='public','encounter unavailable')
            require(not self.db.execute('SELECT 1 FROM encounter_instances WHERE branch=? AND encounter_id=?',(branch,encounter_id)).fetchone(),'encounter already exists')
            if continuation_of:
                old,_,_,_=self._instance(branch,continuation_of,viewer);oldstate=json.loads(old['state_json'])
                require(oldstate['phase'] in ('completed','failed'),'continuation requires a concluded encounter')
                require(isinstance(evidence_refs,list) and evidence_refs,'new episode requires new evidence')
                for ref in evidence_refs:
                    require(isinstance(ref,dict) and set(ref)=={'domain','id','record_revision','snapshot_hash'},'invalid continuation evidence')
                    r=visible.get(ref['id']);require(r and r['domain']==ref['domain'],'continuation source unavailable')
                    full=self.engine.get(branch,ref['id']);require(full['version']==ref['record_revision'] and digest(full)==ref['snapshot_hash'],'stale continuation evidence')
                    ev=self.db.execute('SELECT branch,revision FROM events WHERE id=?',(full['updated_event'],)).fetchone()
                    require(ev['branch']==branch and ev['revision']>oldstate['world_revision'],'continuation needs evidence after prior closure')
            state=spec['states'][spec['initial_state']]
            after=dict(current_state=spec['initial_state'],phase=state['phase'],outcome=state['outcome'],steps=0,
                loops={l['id']:{'phase':'open','kind':l['kind'],'parent':l.get('parent'),'depends_on':l['depends_on']} for l in spec['loops']},
                continuations=[],pending=None,continuation_of=continuation_of,evidence_refs=evidence_refs or [],world_revision=expected_revision)
            self.db.execute('INSERT INTO encounter_instances VALUES(?,?,?,?,?,0,?)',(branch,encounter_id,definition_id,definition_version,encoded(participants),encoded(after)))
            row=self.db.execute('SELECT * FROM encounter_instances WHERE branch=? AND encounter_id=?',(branch,encounter_id)).fetchone()
            return self._write(row,None,after,payload)

    def _available(self,spec,state,participants,permitted,eid,viewer):
        if state['phase'] in ('completed','failed') or (state['phase']=='blocked' and not state['pending']):return []
        result=[]
        for aid in spec['states'][state['current_state']]['actions']:
            a=spec['actions'][aid];actor=participants[a['actor_role']]
            if viewer is not None and viewer!=actor:continue
            if state['pending'] and state['pending']['action_id'] and state['pending']['action_id']!=aid:continue
            good=True
            for req in _expand(a['requirements'],participants,eid):
                r=permitted.get(req['record_id'])
                if not r or req['field'] not in r['data']:
                    good=False;continue
                value=r['data'][req['field']]
                # Typed equality keeps false distinct from zero, including
                # inside nested values. A redacted reference is not a known
                # null merely because its permitted projection contains null.
                if not _same_value(value,req['equals']):good=False
                full=self.engine.get(r['branch'],r['id'])
                if not full or not _same_value(full['data'].get(req['field']),value):good=False
            if a['kind']=='will':
                p=_expand(a['payload'],participants,eid)
                for ref in (p.get('expression',{}),p.get('technique',{})):
                    if ref.get('id') not in permitted:good=False
                if any(target not in permitted for target in p.get('targets',[])):good=False
            if a['kind']=='event' and viewer is not None:
                effects=_expand(a['payload'],participants,eid)
                def hidden_reference(value):
                    if isinstance(value,dict):return any(hidden_reference(v) for v in value.values())
                    if isinstance(value,list):return any(hidden_reference(v) for v in value)
                    if isinstance(value,str):
                        record=self.engine.get(next(iter(permitted.values()))['branch'],value) if permitted else None
                        return bool(record and value not in permitted)
                    return False
                if hidden_reference(effects):good=False
            if good:
                result.append(dict(action_id=aid,label=a['label'],kind=a['kind'],actor_id=actor,
                    fields={'choice_id':'one of the pending choice IDs','rationale':'nonempty owner/actor judgment'} if a['kind']=='judgment' and state['pending'] else {}))
        return result

    def inspect(self,branch,encounter_id,viewer=None):
        with UnitOfWork(self.db):
            row,spec,participants,visible=self._instance(branch,encounter_id,viewer);state=json.loads(row['state_json'])
            pending=deepcopy(state['pending'])
            if viewer is not None and pending and pending['actor_id']!=viewer:pending=None
            return dict(encounter_interface='1',branch=branch,encounter_id=encounter_id,title=spec['title'],
                definition_id=row['definition_id'],definition_version=row['definition_version'],state_revision=row['revision'],
                current_state=state['current_state'],phase=state['phase'],outcome=state['outcome'],world_revision=self.engine.branch(branch)['revision'],
                participants=participants,loops=state['loops'],continuations=[c for c in state['continuations'] if c['record_id'] in visible],
                pending=pending,steps=state['steps'],max_steps=spec['max_steps'],
                next_actions=self._available(spec,state,participants,visible,encounter_id,viewer),
                continuation_of=state['continuation_of'],reason=state.get('reason'))

    def act(self,branch,encounter_id,action_id,request_id,expected_revision,fields=None,viewer=None,expected_encounter_revision=None):
        require(not self.db.in_transaction,'encounter act owns Will preparation boundary; finish outer work first')
        fields={} if fields is None else fields;require(isinstance(fields,dict),'action fields must be an object')
        text(action_id,'action id');text(request_id,'request id');integer(expected_revision,'expected revision',0)
        if expected_encounter_revision is not None:integer(expected_encounter_revision,'expected encounter revision')
        payload=dict(branch=branch,encounter_id=encounter_id,action_id=action_id,request_id=request_id,expected_revision=expected_revision,
            fields=fields,viewer=viewer,expected_encounter_revision=expected_encounter_revision)
        with UnitOfWork(self.db):
            replay=self._replay(request_id,payload,branch,encounter_id,viewer)
            if replay:return replay
            row,spec,participants,visible=self._instance(branch,encounter_id,viewer);before=json.loads(row['state_json'])
            require(self.engine.branch(branch)['revision']==expected_revision,'stale branch revision')
            if expected_encounter_revision is not None:require(row['revision']==expected_encounter_revision,'stale encounter revision')
            require(before['phase'] not in ('completed','failed'),'encounter is closed')
            if before['steps']>=spec['max_steps']:
                after=deepcopy(before);after.update(phase='blocked',pending=None,reason='Authored step budget exhausted; unresolved loops retained.')
                return self._write(row,before,after,payload)
            available=self._available(spec,before,participants,visible,encounter_id,viewer)
            if action_id not in {a['action_id'] for a in available}:
                # Unknown free-form actions remain a bounded inquiry, not a new world fact.
                require(before['phase'] not in ('completed','failed','blocked'),'encounter is closed or blocked')
                if action_id not in spec['actions']:
                    after=deepcopy(before);after.update(phase='waiting',steps=before['steps']+1,pending=dict(action_id=action_id,actor_id=viewer,
                        question='Choose a supported authored action or author a new compatible policy.',choices=available,unknowns=['Meaning and legal effects of the requested action'],resume_condition='Select an existing authored action with a new request ID.'))
                    # Unknown input does not lock out every known action.
                    after['pending']['action_id']=None
                    return self._write(row,before,after,payload)
                raise Rejected('action unavailable in current state or perspective')
            action=deepcopy(spec['actions'][action_id]);actor=participants[action['actor_role']]
            if action['kind']=='judgment' and not fields:
                after=deepcopy(before);after.update(phase='waiting',steps=before['steps']+1,pending=dict(action_id=action_id,actor_id=actor,
                    question=action['payload']['question'],choices=action['payload']['choices'],unknowns=action['payload']['unknowns'],
                    resume_condition='Submit one listed choice ID and an attributed rationale at the current revisions.'))
                return self._write(row,before,after,payload)
            if action['kind']=='judgment':
                require(before['pending'] and before['pending']['action_id']==action_id,'judgment must first be requested')
                require(set(fields)=={'choice_id','rationale'},'judgment response needs choice_id and rationale');text(fields['rationale'],'judgment rationale')
                choices={c['id']:c for c in action['payload']['choices']};require(fields['choice_id'] in choices,'unknown judgment choice')
                target=choices[fields['choice_id']]['next_state']
            else:
                require(not fields,'authored action takes no caller-injected effects')
                target=action.get('next_state')
            start_revision=row['revision']
        # Legacy Will prepare owns its transaction. It changes execution metadata
        # only. World effects and encounter advancement below share one commit.
        prepared=None
        if action['kind']=='will':
            attempt=_expand(action['payload'],participants,encounter_id)
            require(not ({'request_id','attempt_id','expected_revision','actor'} & set(attempt)),'Will action cannot override its execution identity')
            attempt.update(request_id='encounter-prepare:'+request_id,attempt_id='encounter-attempt:'+request_id,
                           expected_revision=expected_revision,actor=actor)
            prepared=self.engine.prepare_will_attempt(branch,attempt)
            if prepared['status']=='prepared':target=action.get('next_by_outcome',{}).get(prepared['outcome'],target)
        with UnitOfWork(self.db):
            row,spec,participants,visible=self._instance(branch,encounter_id,viewer)
            replay=self._replay(request_id,payload,branch,encounter_id,viewer)
            if replay:return replay
            require(row['revision']==start_revision and self.engine.branch(branch)['revision']==expected_revision,'encounter or world changed during preparation')
            before=json.loads(row['state_json']);after=deepcopy(before)
            if prepared and prepared['status']!='prepared':
                after.update(phase='waiting' if prepared.get('judgment_required') else 'blocked',
                    steps=before['steps']+1,reason=prepared.get('reason','Will preparation blocked'),pending=dict(action_id=action_id,actor_id=actor,
                    question='Resolve the stated Will precondition through existing Will/world APIs.',choices=[],unknowns=[prepared.get('reason','permission')],resume_condition='Change or clarify the governing world condition; retry with a fresh request.'))
                return self._write(row,before,after,payload)
            require(target in spec['states'],'action has no continuation for this outcome')
            loopmap={l['id']:l for l in spec['loops']}
            for lid in action['resolve_loops']:
                require(all(after['loops'][d]['phase'] in ('resolved','cancelled','detached') for d in loopmap[lid]['depends_on']),'required child dependency unresolved')
                require(all(not child['required'] or after['loops'][child['id']]['phase'] in ('resolved','cancelled','detached')
                            for child in spec['loops'] if child.get('parent')==lid),'required nested child remains unresolved')
                after['loops'][lid]['phase']='resolved'
            for item in action['cancel_loops']:
                after['loops'][item['loop_id']].update(phase='cancelled',reason=item['reason'])
            for item in _expand(action['detach_loops'],participants,encounter_id):
                require(item['record_id'] in visible,'continuation record unavailable')
                after['loops'][item['loop_id']]['phase']='detached';after['continuations'].append(item)
            target_state=spec['states'][target]
            if target_state['phase'] in ('completed','failed'):
                require(all(not l['required'] or after['loops'][l['id']]['phase'] in ('resolved','cancelled','detached') for l in spec['loops']),'required encounter loop remains unresolved')
            world_request='encounter-action:'+request_id
            if action['kind']=='will':
                world=self.engine.apply_will_attempt(branch,'encounter-attempt:'+request_id,world_request,actor,action['label'],expected_revision)
            elif action['kind']=='dialogue':
                p=action['payload'];require(set(p)=={'text','act','mode','listener_roles'},'invalid dialogue payload')
                text(p['text'],'dialogue text');require(all(r in participants for r in p['listener_roles']),'unknown listener role')
                turn_id=encounter_id+':turn:'+request_id;listeners=[participants[r] for r in p['listener_roles']]
                common=dict(op='create',domain='dialogue_turn',id=turn_id,status='reported',visibility=spec['visibility'],evidence=[{'note':'Explicit authored encounter dialogue; speaker linked by ID.'}],
                    data=dict(speaker=actor,listeners=listeners,scene=spec.get('scene_id'),act=p['act'],text=p['text'],mode=p['mode']))
                observations=[dict(id=turn_id+':heard:'+listener,observer_id=listener,subject_id=actor,assertion=p['text'],certainty='heard',visibility='restricted',audience=[listener]) for listener in listeners]
                from ..writing import brief
                writing_brief=brief(self.engine,branch,'dialogue',listeners[0] if listeners else actor,action['label'],perspective=actor,scene=spec.get('scene_id'))
                world=self.engine.apply(dict(api_version=3,branch=branch,request_id=world_request,expected_revision=expected_revision,
                    kind='action',actor=actor,narrative=action['label'],changes=[common],observations=observations,
                    judgment={'authored_dialogue':{'definition_id':row['definition_id'],'version':row['definition_version'],
                        'writing_brief_hash':writing_brief['brief_hash'],'scope':'Authored text and recorded hearing; no inferred listener belief.'}}))
            elif action['kind']=='judgment':
                world=self.engine.apply(dict(api_version=3,branch=branch,request_id=world_request,expected_revision=expected_revision,
                    kind='decision',actor=actor,narrative='Record selected authored continuation',changes=[],
                    choice=dict(id=encounter_id+':choice:'+request_id,actor_id=actor,intent=action['payload']['question'],method='bounded authored choice',
                        options=action['payload']['choices'],selected={'choice_id':fields['choice_id']},knowledge={},agency_state='voluntary'),
                    judgment={'by':actor,'rationale':fields['rationale'],'scope':'Selected continuation; no inferred motive.'}))
            else:
                effects=_expand(action['payload'],participants,encounter_id)
                require(set(effects)<= {'changes','properties','consequences','observations','processes','consequence_runs','clock_id','tick'},'event action cannot replace execution identity')
                # A patch version is resolved under the same transaction; an
                # authored condition still has to hold before this point.
                for change in effects.get('changes',[]):
                    if change.get('op')=='patch' and 'expected_version' not in change:
                        record=self.engine.get(branch,change['id']);require(record is not None,'effect target unavailable');change['expected_version']=record['version']
                world=self.engine.apply(dict(api_version=3,branch=branch,request_id=world_request,expected_revision=expected_revision,
                    kind='action',actor=actor,narrative=action['label'],**effects))
            after.update(current_state=target,phase=target_state['phase'],outcome=target_state['outcome'],pending=None,steps=before['steps']+1)
            after.pop('reason',None)
            return self._write(row,before,after,payload,world)


WorldWorkspace=Encounters


def verify_encounters(engine):
    db=engine.db
    row=db.execute("SELECT version FROM engine_versions WHERE component='encounter_interface'").fetchone()
    if not row:return {'installed':False}
    require(row[0]=='1','unsupported encounter interface')
    from ..resources import schema_path
    migration=schema_path('migration_013.sql')
    check=db.execute('SELECT checksum FROM migration_checks WHERE version=13').fetchone()
    require(check and check[0]==hashlib.sha256(migration.read_bytes()).hexdigest(),'encounter migration checksum mismatch')
    for row in db.execute('SELECT * FROM encounter_definitions'):
        spec=json.loads(row['spec_json']);require(_validate(spec)==spec and digest(spec)==row['digest'],'encounter definition mismatch')
    count=0
    for instance in db.execute('SELECT * FROM encounter_instances'):
        prior=None;revision=0
        for event in db.execute('SELECT * FROM encounter_events WHERE branch=? AND encounter_id=? ORDER BY revision',(instance['branch'],instance['encounter_id'])):
            payload=json.loads(event['payload_json']);after=json.loads(event['after_json']);receipt=json.loads(event['receipt_json'])
            before=json.loads(event['before_json']) if event['before_json'] else None
            require(digest(payload)==event['payload_hash'] and payload['request_id']==event['request_id'],'encounter request hash mismatch')
            require(before==prior and event['revision']==revision+1,'encounter history discontinuity')
            require(payload['branch']==instance['branch'] and payload['encounter_id']==instance['encounter_id'],'encounter event identity mismatch')
            if revision==0:
                require(payload['definition_id']==instance['definition_id'] and payload['definition_version']==instance['definition_version']
                    and payload['participants']==json.loads(instance['participants_json']),'encounter identity differs from pinned start')
            require(receipt['state_digest']==digest(after) and receipt['state_revision']==event['revision']
                and receipt['branch']==instance['branch'] and receipt['encounter_id']==instance['encounter_id']
                and receipt['definition_id']==instance['definition_id'] and receipt['definition_version']==instance['definition_version'],'encounter receipt mismatch')
            if receipt['world_receipt']:
                world=db.execute('SELECT receipt_json FROM events WHERE id=?',(receipt['world_receipt']['event_id'],)).fetchone()
                require(world and json.loads(world[0])==receipt['world_receipt'],'encounter world receipt mismatch')
            prior=after;revision+=1
        require(revision==instance['revision'] and prior==json.loads(instance['state_json']),'encounter projection differs from history')
        count+=1
    from ..intelligence.genesis import _profile
    for row in db.execute('SELECT * FROM genesis_profiles'):
        profile=json.loads(row['profile_json']);receipt=json.loads(row['receipt_json'])
        require(_profile(profile)==profile,'genesis profile mismatch')
        source=db.execute('SELECT command_json FROM events WHERE branch=? AND request_id=?',(row['branch'],'genesis-character:'+row['request_id'])).fetchone()
        require(source is not None,'genesis source event missing')
        command=json.loads(source[0]);payload=dict(branch=row['branch'],request_id=row['request_id'],expected_revision=command['expected_revision'],profile=profile)
        require(digest(payload)==row['payload_hash'] and receipt['character_id']==row['character_id'] and receipt['node_id']==row['node_id'],'genesis provenance mismatch')
    return {'installed':True,'interface':'1','encounters':count,'profiles':db.execute('SELECT count(*) FROM genesis_profiles').fetchone()[0]}
