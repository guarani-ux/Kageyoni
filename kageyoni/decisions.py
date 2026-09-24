"""Coordinated GM-mediated decisions. Proposals are immutable, not story events."""
import copy
import json
import math
import secrets
from .engine import Rejected, require, digest, encoded
from .characters import read as character_read
from .resources import schema_path
from .persistence.unit_of_work import UnitOfWork


def install(e):
    from pathlib import Path
    import hashlib
    p = schema_path('migration_006.sql')
    checksum = hashlib.sha256(p.read_bytes()).hexdigest()
    old = e.db.execute('SELECT checksum FROM migration_checks WHERE version=6').fetchone()
    if old:
        require(old[0] == checksum, 'decision migration checksum mismatch')
    else:
        require(e.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0] == 5, 'decision predecessor mismatch')
        e._backup_before_versioned_migration(6)
        try:
            e.db.executescript('BEGIN IMMEDIATE;\n'+p.read_text())
            require(not e.db.execute('PRAGMA foreign_key_check').fetchall(), 'decision migration foreign key failure')
            e.db.execute("INSERT INTO migration_checks VALUES(6,5,'migration_006.sql',?,'4',CURRENT_TIMESTAMP)", (checksum,))
            e.db.commit()
        except Exception:
            e.db.rollback(); raise
    require(e.db.execute("SELECT version FROM engine_versions WHERE component='decision_interface'").fetchone()[0]=='1','unsupported decision interface')


def fingerprint(e, branch, legacy=False, writing_legacy=False):
    # Conservative invalidation covers administrative writes as well as events.
    state=e._snapshot_payload(branch); state.pop('decisions',None)
    definitions={table:[dict(r) for r in e.db.execute('SELECT * FROM '+table)]
                 for table in ('rule_definitions','rule_dependencies','property_definitions','property_lifecycle','engine_versions')}
    # Operational node/method/contribution storage cannot affect world resolution or invalidate pending decisions.
    definitions['engine_versions']=[r for r in definitions['engine_versions'] if r['component'] not in ('node_interface','method_interface','contribution_interface','learning_interface','encounter_interface','workspace_interface','network_interface','pipeline_interface','operations_interface','composition_interface','v11_enforcement','v11_runtime','v11_enforcer_eval','v11_trust','situation_architecture')]
    if legacy:
        definitions['engine_versions']=[r for r in definitions['engine_versions'] if r['component']!='personality_interface']
    if writing_legacy:
        definitions['engine_versions']=[r for r in definitions['engine_versions'] if r['component']!='writing_interface']
    return digest({'state':state, 'revision':e.branch(branch)['revision'],'definitions':definitions})


def number(value, label):
    require(type(value) in (int,float) and math.isfinite(value), 'invalid '+label)
    return value


def judgment(value, label):
    require(isinstance(value,dict) and set(value)=={'by','rationale','basis'}, label+' requires by, rationale and basis')
    require(all(isinstance(value[k],str) and value[k].strip() for k in ('by','rationale')), 'empty '+label)
    require(isinstance(value['basis'],list) and all(isinstance(v,str) for v in value['basis']), 'invalid judgment basis')


def inspect(e, branch, proposal_id, viewer=None):
    row=e.db.execute('SELECT * FROM decision_proposals WHERE branch=? AND id=?',(branch,proposal_id)).fetchone()
    require(row is not None,'proposal unavailable')
    spec=json.loads(row['spec_json']); c=json.loads(row['compiled_json'])
    require(viewer is None or viewer==spec['actor'],'proposal unavailable')
    event=e.db.execute('SELECT receipt_json FROM events WHERE branch=? AND request_id=?',(branch,'decision:'+proposal_id)).fetchone()
    out={'proposal_id':proposal_id,'revision':spec['expected_revision'],'status':'committed' if event else c['status'],
         'intent':spec['intent'],'method':spec['method'],'commitment':{'costs':c['public_costs'],'duration':spec.get('time'),'stakes':spec['stakes']}}
    if viewer is None:
        out.update(assessment=c,receipt=json.loads(event[0]) if event else None)
    else:
        # No blockers, numerical inputs, outcome changes or hidden causes escape.
        out['status']='resolved' if event else 'reviewed'
        out['message']='Ask the GM for the scene-facing assessment.'
    return out


def propose(e, branch, spec):
    require(isinstance(spec,dict),'decision specification required')
    allowed={'id','expected_revision','actor','intent','method','stakes','modules','requirements','capabilities','equipment','will','responses','rules','costs','time','outcomes','adjudication','uncertainty','agency_state','personality','dialogue_grounding'}
    require(set(spec)<=allowed,'unknown decision field')
    for k in ('id','actor','intent','method','stakes'):
        require(isinstance(spec.get(k),str) and spec[k].strip(),'missing '+k)
    require(type(spec.get('expected_revision')) is int,'expected revision required')
    judgment(spec.get('adjudication'),'decision adjudication')
    require(spec.get('agency_state') in ('voluntary','pressured','deceived','compelled','unknown'),'agency state required')
    old=e.db.execute('SELECT spec_hash FROM decision_proposals WHERE branch=? AND id=?',(branch,spec['id'])).fetchone()
    if old:
        require(old[0]==digest(spec),'proposal ID reused with changed content')
        return inspect(e,branch,spec['id'])
    e.db.execute('BEGIN IMMEDIATE')
    try:
        require(e.branch(branch)['revision']==spec['expected_revision'],'stale branch revision')
        actor=e.get(branch,spec['actor']); require(actor and actor['domain']=='character','actor unavailable')
        context=character_read(e,branch,spec['actor'],viewer=spec['actor'])
        visible={r['id']:r for r in e.context(branch,viewer=spec['actor'])['records']}
        blockers=[]; used=[]; dependencies=[]; seen=set(); modifier=0; magnitude=0
        for pending in due_consequences(e,branch):
            blockers.append({'kind':'pending_consequence','id':pending['id']})
        def fact(rid):
            r=e.get(branch,rid); require(r is not None,'decision source missing'); used.append(r); return r
        for rid in spec['adjudication']['basis']: fact(rid)
        modules=spec.get('modules',[])
        require(isinstance(modules,list) and len(modules)==len(set(modules)) and set(modules)<=set(('combat','travel','discovery','training','social','downtime')),'invalid modules')
        from .personality import decision_context, validate_grounding
        personality, personality_deps=decision_context(e,branch,spec['actor'],modules,spec.get('personality'))
        used.append({'personality':personality}); dependencies.extend(personality_deps)
        if 'dialogue_grounding' in spec:
            validate_grounding(e,branch,spec['actor'],spec.get('personality',{}),spec['dialogue_grounding'])
        responses=[]
        for req in spec.get('requirements',[]):
            require(set(req)=={'record_id','field','equals'},'invalid requirement')
            r=fact(req['record_id']); require(req['field'] in r['data'],'unknown required field')
            if r['data'][req['field']]!=req['equals']: blockers.append({'kind':'condition','record':r['id']})
        for rid in spec.get('capabilities',[]):
            r=fact(rid); require(r['domain']=='capability' and r['data']['character']==spec['actor'],'capability ownership mismatch')
            fact(r['data']['ability'])
        for rid in spec.get('equipment',[]):
            r=fact(rid); require(r['domain']=='loadout' and r['data']['holder']==spec['actor'],'equipment custody mismatch')
            fact(r['data']['item'])
        for response in spec.get('responses',[]):
            require(set(response)=={'actor','decision','judgment'},'invalid response')
            require(response['actor']!=spec['actor'],'response must belong to another actor')
            other=fact(response['actor']); require(other['domain']=='character','response actor must be character')
            judgment(response['judgment'],'independent response')
            response_model,response_deps=decision_context(e,branch,other['id'],['social'],{'interlocutors':[spec['actor']]})
            rb=response_model['brief']
            knowledge={r['id'] for r in [rb['actor'],*rb['knowledge'],*rb['aspects'],*rb['perceived'],*rb['relationships'],*rb['capabilities'],*rb['wills']]}
            require(set(response['judgment']['basis'])<=knowledge,'NPC response uses unavailable knowledge')
            responses.append({'actor':other['id'],'personality':response_model}); dependencies.extend(response_deps)
            require(response['decision'] in ('agree','refuse','pending'),'invalid response decision')
            if response['decision']!='agree': blockers.append({'kind':'independent_response','actor':other['id'],'decision':response['decision']})
        # Will mechanics remain bounded semantic adjudication through this path.
        # Pin all three contracts and require an explicit assessment of conditions.
        will_costs={'success':[],'failure':[]}; will_public_costs=[]
        for w in spec.get('will',[]):
            require(set(w)=={'expression','technique','judgment'},'Will use requires expression, technique, judgment')
            judgment(w['judgment'],'Will conditions, scope, resistance and costs')
            ex=e._will_record_ref(branch,'will_expression',w['expression'],'decision Will')
            tech=e._will_record_ref(branch,'will_technique',w['technique'],'decision technique')
            require(ex['data']['bearer']==spec['actor'] and tech['data']['expression']==ex['id'],'Will ownership mismatch')
            require(tech['data']['contract']['design_status']=='accepted','Will technique is not accepted')
            require(tech['data']['contract']['practice_status'] not in ('unavailable','unknown'),'Will practice is unavailable')
            definition=e._will_record_ref(branch,'will_definition',ex['data']['contract']['definition'],'decision Will definition')
            used.extend([ex,tech,definition])
            require(w['technique'] in ex['data']['contract']['learned_techniques'],'Will technique not learned by expression')
            tc=tech['data']['contract']
            conditions=list(definition['data']['contract']['invariants'])+[tc['trigger']]
            conditions += [channel['access'] for channel in tc['channels']]
            conditions += [condition for effect in tc['effects'] for condition in effect['preconditions']]
            for condition in conditions:
                if condition['mode']=='rule':
                    rr=condition['rule']; result=e.evaluate_rule(rr['id'],rr['version'],branch,subject_id=spec['actor'])
                    used.append(result); dependencies.append({'kind':'rule','ref_id':rr['id'],'version':str(rr['version']),'usage':'reads'})
                    if not result['mechanical'] or result['output']['value'] is not True:
                        blockers.append({'kind':'will_condition','condition':condition['id']})
            # Ongoing interruption/resistance semantics remain explicit GM judgment;
            # release/upkeep costs need their own lifecycle, not an attempt charge.
            for cost in tc['costs']:
                require(cost['when'] in ('attempt','success','failure') and cost['insufficient_policy']=='block','Will lifecycle cost requires supported extension')
                require(cost['resource']['subject_role'] in ('actor','bearer','self'),'Will target costs require explicit target authorization')
                resource=cost['resource']
                visible_props=e.properties(branch,entity_id=spec['actor'],viewer=spec['actor'])
                require(any(p['property_id']==resource['property_id'] and p['definition_version']==resource['definition_version'] for p in visible_props),'Will cost must be known to actor')
                will_public_costs.append({'property':resource['property_id'],'when':cost['when'],'amount':cost['amount']})
                dependencies.append({'kind':'property','ref_id':resource['property_id'],'version':str(resource['definition_version']),'usage':'writes'})
            for outcome in will_costs:
                assignments,missing=e._will_cost_properties(branch,spec['actor'],[],tech,outcome)
                will_costs[outcome].extend(assignments); blockers.extend(missing)
            for rid in w['judgment']['basis']: fact(rid)
        for binding in spec.get('rules',[]):
            require(set(binding)=={'id','version','subject','stage','unit'},'invalid rule binding')
            require(binding['stage'] in ('permission','probability','magnitude'),'unsupported contribution stage')
            key=(binding['id'],binding['version'],binding['subject'],binding['stage'])
            require(key not in seen,'duplicate contribution'); seen.add(key)
            rule=e.db.execute('SELECT * FROM rule_definitions WHERE rule_id=? AND rule_version=?',(binding['id'],binding['version'])).fetchone()
            require(rule is not None,'unknown rule version')
            inputs=json.loads(rule['inputs_json']); vals={}
            for prop in inputs:
                versions=e.db.execute("SELECT property_version FROM rule_dependencies WHERE rule_id=? AND rule_version=? AND property_id=? AND usage='reads'",(binding['id'],binding['version'],prop)).fetchall()
                require(len(versions)==1,'rule input requires one declared property version')
                lifecycle=e.db.execute('SELECT state FROM property_lifecycle WHERE property_id=? AND definition_version=? ORDER BY sequence DESC LIMIT 1',(prop,versions[0][0])).fetchone()
                require(lifecycle and lifecycle[0]=='active','decision stat definition must be active')
                pv=e.property_value(branch,binding['subject'],prop,versions[0][0])
                require(pv is not None and pv['state']=='known','missing or unknown stat input')
                require(pv['unit']==binding['unit'],'incompatible contribution unit')
                # Invoke registry validation to check applicability/constraints too.
                stored=e.db.execute('SELECT * FROM property_values WHERE branch=? AND entity_id=? AND property_id=? AND definition_version=?',(branch,binding['subject'],prop,versions[0][0])).fetchone()
                e._validate_property_assignment(branch,dict(stored),stored=True)
                vals[prop]=pv['value']; used.append({'property':dict(stored)})
                dependencies.append({'kind':'property','ref_id':prop,'version':str(versions[0][0]),'usage':'reads'})
            result=e.evaluate_rule(binding['id'],binding['version'],branch,subject_id=binding['subject'],inputs=vals)
            require(result['mechanical'] and result['kind'] in ('threshold','sum','contextual'),'rule requires explicit new mechanic')
            v=result['output']['value']; used.append(result)
            if binding['stage']=='permission':
                require(type(v) is bool,'permission rule must return boolean')
                if not v: blockers.append({'kind':'permission','rule':binding['id']})
            elif binding['stage']=='probability':
                require(binding['unit']=='bonus' and type(v) in (int,float) and math.isfinite(v) and int(v)==v,'probability requires integer bonus units'); modifier+=int(v)
            else:
                number(v,'magnitude'); require(binding['unit']=='effect','magnitude requires effect units'); magnitude+=v
            dependencies.append({'kind':'rule','ref_id':binding['id'],'version':str(binding['version']),'usage':'reads'})
        uncertainty=spec.get('uncertainty')
        require(isinstance(uncertainty,dict),'uncertainty declaration required')
        require(uncertainty.get('mode') in ('none','d20'),'unsupported uncertainty')
        require(set(uncertainty)==({'mode'} if uncertainty['mode']=='none' else {'mode','difficulty'}),'invalid uncertainty fields')
        if uncertainty['mode']=='d20': require(type(uncertainty['difficulty']) is int,'integer difficulty required')
        simulation=None
        if spec.get('time'):
            t=spec['time']; require(set(t)=={'clock','duration'},'invalid decision time')
            clock=fact(t['clock']); require(clock['domain']=='clock','decision clock missing')
            require(t['clock'] in visible,'decision time must be visible to actor')
            duration=number(t['duration'],'duration'); require(duration>=0,'negative duration')
            end=clock['data']['tick']+duration
            for pending in e.db.execute("SELECT id,trigger_json FROM consequences WHERE branch=? AND status='pending'",(branch,)):
                trigger=json.loads(pending['trigger_json'])
                if trigger.get('clock_id')==t['clock'] and 'at' in trigger and trigger['at']<end:
                    blockers.append({'kind':'consequence_deadline','id':pending['id'],'tick':trigger['at']})
            for record in e.state(branch):
                d=record['data']
                if record['domain']=='schedule' and d['clock']==t['clock'] and d['phase']=='pending' and d['due']<end:
                    blockers.append({'kind':'decision_point','id':record['id'],'tick':d['due']})
            for p in e.list_processes(branch):
                # A process must explicitly bind to this clock before elapsed
                # simulation can assume shared units; cross-clock work blocks.
                if p['state'] in ('active','due','blocked') and p.get('scope',{}).get('clock_id')!=t['clock']:
                    blockers.append({'kind':'process_clock_judgment','id':p['id']})
                if p['state'] in ('active','due','blocked') and (p.get('interval_unit') not in (None,clock['data']['unit']) or not p.get('metadata',{}).get('effect')):
                    blockers.append({'kind':'process_mechanism_judgment','id':p['id']})
            simulation=e.advance_simulation(branch,t['clock'],end,'decision-time:'+spec['id'],spec['actor'],spec['intent'],expected_revision=spec['expected_revision'],prepare_only=True)
            blockers.extend(simulation['blocked']); blockers.extend({'kind':'processing_limit','id':p} for p in simulation['deferred'])
        elif any(p['state'] in ('due','blocked') for p in e.list_processes(branch)):
            blockers.append({'kind':'pending_background_work'})
        costs=[]; public_costs=will_public_costs; cost_ids=set()
        for cost in spec.get('costs',[]):
            require(set(cost)=={'resource','amount','unit'},'invalid cost')
            require(cost['resource'] not in cost_ids,'duplicate resource cost'); cost_ids.add(cost['resource'])
            r=fact(cost['resource']); d=r['data']; require(r['domain']=='resource' and d['holder']==spec['actor'],'resource ownership mismatch')
            require(r['id'] in visible,'authorized costs must be visible to actor')
            amount=number(cost['amount'],'cost'); require(amount>=0 and cost['unit']==d['unit'],'invalid cost unit or amount')
            if d['quantity']<amount: blockers.append({'kind':'insufficient_resource','resource':r['id']})
            costs.append({'op':'patch','id':r['id'],'expected_version':r['version'],'data':{'quantity':d['quantity']-amount},'evidence':[{'note':'Authorized decision cost'}]})
            public_costs.append(cost)
        outcomes=spec.get('outcomes'); require(isinstance(outcomes,dict) and set(outcomes)=={'success','failure'},'both outcomes required')
        dependencies=list({(v['kind'],v['ref_id'],v['version'],v['usage']):v for v in dependencies}.values())
        compiled={}
        for name,outcome in outcomes.items():
            require(isinstance(outcome,dict) and set(outcome)<= {'changes','properties','consequences','observations'},'invalid outcome fields')
            c=copy.deepcopy(outcome); c.setdefault('changes',[]); c['changes']+=copy.deepcopy(costs)
            c.setdefault('properties',[]).extend(copy.deepcopy(will_costs[name]))
            # Magnitude explicitly binds into supported patch fields; no implicit unit conversion.
            for change in c['changes']:
                for field,value in change.get('data',{}).items():
                    if value=={'decision_value':'magnitude'}: change['data'][field]=magnitude
            ids=[ch['id'] for ch in c['changes']]; require(len(ids)==len(set(ids)),'conflicting effect/cost writes')
            props=[(p['entity_id'],p['property_id'],p['definition_version']) for p in c.get('properties',[])]; require(len(props)==len(set(props)),'duplicate property effect')
            c.update(api_version=3,branch=branch,expected_revision=spec['expected_revision'],request_id='decision:'+spec['id'],kind='decision',actor=spec['actor'],narrative=spec['intent'],dependencies=dependencies,
                     judgment={'adjudication':spec['adjudication'],'responses':spec.get('responses',[]),'will':spec.get('will',[]),'personality':personality,'response_contexts':responses,'dialogue_grounding':spec.get('dialogue_grounding')},
                     choice={'id':branch+':'+spec['id'],'actor_id':spec['actor'],'intent':spec['intent'],'method':spec['method'],'options':[],'selected':{'method':spec['method']},'knowledge':context,'agency_state':spec['agency_state']})
            if simulation:
                for field in ('changes','properties','processes','process_runs'):
                    c.setdefault(field,[]).extend(copy.deepcopy(simulation['command'].get(field,[])))
                c.update(clock_id=spec['time']['clock'],tick=simulation['command']['tick'])
            ids=[v['id'] for v in c['changes']]; require(len(ids)==len(set(ids)),'action and background process conflict')
            props=[(p['entity_id'],p['property_id'],p['definition_version']) for p in c.get('properties',[])]; require(len(props)==len(set(props)),'action and background property conflict')
            compiled[name]=c
        state_hash=fingerprint(e,branch)
        assessment={'writing_interface':'1','personality_interface':'1','personality':personality,'response_contexts':responses,'status':'blocked' if blockers else 'available','blockers':blockers,'inputs':used,'modifier':modifier,'magnitude':magnitude,'public_costs':public_costs,'commands':compiled}
        # Persist only after both outcomes have passed the engine validator.
        e.db.rollback()
        if not blockers:
            for c in compiled.values():
                e._coordinated_decision=digest(c)
                try: e.apply(c,preview=True)
                finally: e._coordinated_decision=None
        with UnitOfWork(e.db):
            require(fingerprint(e,branch)==state_hash,'state changed during proposal validation')
            e.db.execute('INSERT INTO decision_proposals VALUES(?,?,?,?,?,?,NULL)',(branch,spec['id'],digest(spec),state_hash,encoded(spec),encoded(assessment)))
        return inspect(e,branch,spec['id'])
    except Exception:
        e.db.rollback(); raise


def commit(e, branch, proposal_id, actor, accept, narrative):
    require(accept is True,'explicit commitment required')
    require(isinstance(narrative,str) and narrative.strip(),'narrative required')
    with UnitOfWork(e.db):
        row=e.db.execute('SELECT * FROM decision_proposals WHERE branch=? AND id=?',(branch,proposal_id)).fetchone()
        require(row is not None,'proposal unavailable')
        spec=json.loads(row['spec_json']); c=json.loads(row['compiled_json'])
        require(actor==spec['actor'],'decision actor mismatch')
        previous=e.db.execute('SELECT receipt_json FROM events WHERE branch=? AND request_id=?',(branch,'decision:'+proposal_id)).fetchone()
        if previous:
            return json.loads(previous[0])|{'replayed':True}
        require(c['status']=='available','decision requires changed conditions or judgment')
        require(fingerprint(e,branch,legacy='personality_interface' not in c,writing_legacy='writing_interface' not in c)==row['state_hash'],'stale decision; reassess with a new ID')
        result=row['roll']
        if spec['uncertainty']['mode']=='d20' and result is None:
            result=secrets.randbelow(20)+1
            e.db.execute('UPDATE decision_proposals SET roll=? WHERE branch=? AND id=?',(result,branch,proposal_id))
    # Randomness is durable before attempting story commit. An interrupted
    # apply recovers this exact result; no result is exposed by inspect.
    with UnitOfWork(e.db):
        previous=e.db.execute('SELECT receipt_json FROM events WHERE branch=? AND request_id=?',(branch,'decision:'+proposal_id)).fetchone()
        if previous:
            return json.loads(previous[0])|{'replayed':True}
        require(fingerprint(e,branch,legacy='personality_interface' not in c,writing_legacy='writing_interface' not in c)==row['state_hash'],'stale decision; saved roll retained')
        success=result is None or result+c['modifier']>=spec['uncertainty']['difficulty']
        command=copy.deepcopy(c['commands']['success' if success else 'failure'])
        command['narrative']=narrative
        command['resolution']={'mechanical':False,'inputs':c['inputs'],'roll_result':result,'modifier':c['modifier'],'difficulty':spec['uncertainty'].get('difficulty'),'outcome':'success' if success else 'failure','magnitude':c['magnitude'],'judgment':{'decision_interface':'1','spec':spec}}
        e._coordinated_decision=digest(command)
        try:
            receipt=e.apply(command)
            return receipt
        finally: e._coordinated_decision=None


def due_consequences(e, branch):
    out=[]
    for row in e.db.execute("SELECT * FROM consequences WHERE branch=? AND status='pending' ORDER BY id",(branch,)):
        trigger=json.loads(row['trigger_json'])
        if 'at' in trigger:
            clock=e.get(branch,trigger.get('clock_id'))
            due=bool(clock and clock['data'].get('tick',0)>=trigger['at'])
        else: due=trigger.get('kind') in (None,'immediate')
        if due: out.append(dict(row))
    return out


def settle(e, branch, limit=25):
    """GM-only bounded consequence processing. Stop without discarding blockers."""
    require(type(limit) is int and limit>0,'positive processing limit required')
    applied=[]; blockers=[]
    for _ in range(limit):
        pending=due_consequences(e,branch)
        if not pending: break
        c=pending[0]; effect=json.loads(c['effect_json']); trigger=json.loads(c['trigger_json'])
        if trigger.get('requires_judgment') or not effect or not set(effect)<= {'changes','properties'}:
            blockers.append({'id':c['id'],'reason':'consequence requires judgment'}); break
        command=dict(api_version=3,branch=branch,expected_revision=e.branch(branch)['revision'],request_id='decision-consequence:'+c['id'],kind='consequence',actor='gm',narrative='Apply recorded consequence',**effect,
                     causes=[c['source_event']],consequence_runs=[{'consequence_id':c['id'],'run_key':'apply-once','status':'applied','detail':{'decision_interface':'1'}}])
        try: applied.append(e.apply(command))
        except (Rejected,ValueError) as exc:
            blockers.append({'id':c['id'],'reason':str(exc)}); break
    return {'applied':applied,'blockers':blockers,'pending':[c['id'] for c in due_consequences(e,branch)]}
