"""Contextual character interpretation; weights govern suggestions, not success.

No model calls, diagnostic claims, inferred MBTI assignments or automatic Will
grants. Existing records remain authoritative; exact input images are recorded
with decisions. The GM supplies semantic interpretation and the actual prose.

Physical implementation: Regex validation for MBTI type codes ([EI][SN][TF][JP])
and relational SQLite storage for GM character notes. Confers zero psychological
AI modeling, mental simulation, or persona generation.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import re
from pathlib import Path
from .resources import schema_path

VERSION='1'
SCOPES={'dialogue','combat','relationship','growth','options','decision','training','will'}

def check(ok, message):
    from .engine import require
    require(ok, message)

def install(e):
    p=schema_path('migration_007.sql')
    checksum=hashlib.sha256(p.read_bytes()).hexdigest()
    row=e.db.execute('SELECT checksum FROM migration_checks WHERE version=7').fetchone()
    if row:
        check(row[0]==checksum,'personality migration checksum mismatch')
    else:
        check(e.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==6,'personality migration predecessor mismatch')
        e._backup_before_versioned_migration(7)
        try:
            e.db.executescript('BEGIN IMMEDIATE;\n'+p.read_text())
            check(not e.db.execute('PRAGMA foreign_key_check').fetchall(),'personality migration foreign key failure')
            check(e.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','personality migration integrity failure')
            e.db.execute("INSERT INTO migration_checks(version,predecessor,script_name,checksum,engine_min) VALUES(7,6,'migration_007.sql',?,'4')",(checksum,))
            e.db.commit()
        except Exception:
            e.db.rollback(); raise
    check(e.db.execute("SELECT version FROM engine_versions WHERE component='personality_interface'").fetchone()[0]==VERSION,'unsupported personality interface')
    # Navigation metadata names real entry points. The installed skill text is
    # deliberately separate from the versioned engine/project workflow source.
    commands={'personality_context':'brief','personality_evaluate':'evaluate','personality_record':'record','dialogue_propose':'dialogue_propose'}
    for command,function in commands.items():
        e.register_component('command',command,'3','kageyoni/personality.py:'+function,status='verified',readers=['Workflows','agent'],writers=['Engine.apply'] if command in ('personality_record','dialogue_propose') else [],compatibility={'runtime_schema':'4','workflow_api':'3','personality_interface':'1'},declared_by='engine')
    links=[('personality_context','domain',x,'1') for x in ('character','character_aspect','personality_profile','relationship','knowledge','location','environment','scene','dialogue_turn','will','will_expression','will_development','progression','capability')]
    links += [('personality_evaluate','command','personality_context','3'),('dialogue_propose','command','decision_propose','3'),('dialogue_propose','domain','dialogue_turn','1'),('decision_propose','command','personality_context','3'),('opportunities','command','personality_context','3')]
    links += [('personality_record','domain',x,'1') for x in ('personality_profile','character_aspect','relationship','knowledge')]
    for command,kind,rid,version in links:
        e.db.execute('INSERT OR IGNORE INTO registry_dependencies VALUES(?,?,?,?,?,?,?)',('command',command,'3',kind,rid,version,'verified engine access'))

def validate_record(r):
    d=r['data']
    if r['domain']=='personality_profile':
        code=d.get('type_code')
        check(code is None or (isinstance(code,str) and re.fullmatch('[EI][SN][TF][JP]',code)),'invalid MBTI-inspired type code')
        check((d['interpretation']=='unknown' and code is None) or (d['interpretation']!='unknown' and code is not None),'type code contradicts interpretation status')
        check(bool(d['note'].strip()),'personality interpretation note required')
        check((d.get('policy_id') is None)==(d.get('policy_version') is None),'personality policy needs ID and version')
        check(d.get('policy_version') is None or d['policy_version']>0,'invalid personality policy version')
    elif r['domain']=='dialogue_turn':
        check(isinstance(d['listeners'],list) and all(isinstance(x,str) and x for x in d['listeners']) and len(d['listeners'])==len(set(d['listeners'])),'invalid dialogue listeners')
        check(d['speaker'] not in d['listeners'],'speaker is not their own listener')
        check(bool(d['act'].strip()) and bool(d['text'].strip()),'dialogue act and text required')
        check(d.get('reply_to')!=r['id'],'dialogue cannot reply to itself')

def validate_world(e,branch,records):
    subjects=set()
    for r in records.values():
        d=r['data']
        if r['domain']=='personality_profile':
            check(d['character'] not in subjects,'duplicate personality profile')
            subjects.add(d['character'])
            if d.get('policy_id'):
                row=e.db.execute('SELECT definition_json FROM rule_definitions WHERE rule_id=? AND rule_version=?',(d['policy_id'],d['policy_version'])).fetchone()
                check(row is not None and json.loads(row[0]).get('kind')=='personality','profile policy reference unavailable')
        elif r['domain']=='dialogue_turn':
            for rid in d['listeners']:
                check(rid in records and records[rid]['domain']=='character','dialogue listener unavailable')
            if d.get('reply_to'):
                earlier=records[d['reply_to']]
                check(d['speaker'] in earlier['data']['listeners'] or d['speaker']==earlier['data']['speaker'],'speaker did not participate in referenced dialogue')
                seen={r['id']}; parent=d['reply_to']
                while parent:
                    check(parent not in seen,'dialogue reply cycle'); seen.add(parent)
                    parent=records[parent]['data'].get('reply_to')

def _shape(obj, required, optional=()):
    check(isinstance(obj,dict) and set(required)<=set(obj) and set(obj)<=set(required)|set(optional),'invalid personality fields')

def _weight(v,positive=False):
    check(type(v) in (int,float) and math.isfinite(v) and (v>0 if positive else v>=0) and v<=100,'invalid personality design weight')

def validate_policy(definition,inputs,outputs,dependencies):
    from .characters import SECTIONS
    _shape(definition,('kind','schema_version','design_status','meaning','scopes','options','influences'))
    check(definition['kind']=='personality' and definition['schema_version']=='personality-policy/1','unsupported personality policy')
    check(definition['design_status'] in ('proposed','active'),'invalid personality policy status')
    check(isinstance(definition['meaning'],str) and bool(definition['meaning'].strip()),'personality policy meaning required')
    scopes=definition['scopes']
    check(isinstance(scopes,list) and scopes and all(isinstance(x,str) for x in scopes) and set(scopes)<=SCOPES and len(scopes)==len(set(scopes)),'invalid personality scopes')
    options=definition['options']; influences=definition['influences']
    check(isinstance(options,list) and 1<=len(options)<=128,'personality options required')
    check(isinstance(influences,list) and len(influences)<=128,'invalid personality influences')
    ids=set()
    for opt in options:
        _shape(opt,('id','label','weight','guidance'),('tones',))
        check(isinstance(opt['id'],str) and opt['id'] and opt['id'] not in ids,'duplicate or invalid personality option'); ids.add(opt['id'])
        check(all(isinstance(opt[k],str) for k in ('label','guidance')),'invalid personality guidance')
        _weight(opt['weight'],True)
        check(isinstance(opt.get('tones',[]),list) and all(isinstance(t,str) for t in opt.get('tones',[])),'invalid tone labels')
    seen=set(); contributions=set(); properties=set(); prop_versions=set()
    for influence in influences:
        _shape(influence,('id','option','factor','when','rationale'),('scopes',))
        if 'scopes' in influence:
            check(isinstance(influence['scopes'],list) and influence['scopes'] and all(isinstance(x,str) for x in influence['scopes']) and set(influence['scopes'])<=set(scopes),'invalid influence scopes')
        check(isinstance(influence['id'],str) and influence['id'] and influence['id'] not in seen,'duplicate influence ID'); seen.add(influence['id'])
        check(isinstance(influence['option'],str) and influence['option'] in ids,'influence option unavailable'); _weight(influence['factor'])
        check(isinstance(influence['rationale'],str) and influence['rationale'].strip(),'influence rationale required')
        check(isinstance(influence['when'],list) and influence['when'],'influence conditions required')
        conditions=[json.dumps(c,sort_keys=True,allow_nan=False) for c in influence['when']]
        check(len(conditions)==len(set(conditions)),'duplicate personality condition')
        contribution=(influence['option'],tuple(sorted(conditions)))
        check(contribution not in contributions,'duplicate personality contribution'); contributions.add(contribution)
        for c in influence['when']:
            check(isinstance(c,dict),'invalid personality condition')
            source=c.get('source')
            if source=='aspect':
                _shape(c,('source','kind','value'))
                check(isinstance(c['kind'],str) and c['kind'] in set().union(*SECTIONS.values()) and isinstance(c['value'],str),'invalid aspect condition')
            elif source=='mbti':
                _shape(c,('source','axis','value'))
                check(c['axis'] in ('EI','SN','TF','JP') and isinstance(c['value'],str) and c['value'] in list(c['axis']),'invalid MBTI preference')
            elif source=='will':
                _shape(c,('source','definition','version'))
                check(isinstance(c['definition'],str) and type(c['version']) is int and c['version']>0,'invalid Will association')
            elif source=='relationship':
                _shape(c,('source','kind','field','value'))
                check(c['field'] in ('feeling','obligation','tension','shared_history') and isinstance(c['kind'],str),'invalid relationship condition')
            elif source=='property':
                _shape(c,('source','id','version','unit','operator','value'))
                check(isinstance(c['id'],str) and type(c['version']) is int and c['version']>0,'invalid personality property dependency')
                check(c['operator'] in ('==','>=','<=','>','<'),'invalid property comparison')
                check(c['unit'] is None or isinstance(c['unit'],str),'invalid property unit')
                check(type(c['value']) in (int,float,str,bool) and (type(c['value']) not in (int,float) or math.isfinite(c['value'])),'invalid property comparison value')
                properties.add(c['id']); prop_versions.add((c['id'],c['version'],'reads'))
            elif source=='character':
                _shape(c,('source','field','value'))
                check(c['field'] in ('condition','identity','motives','personality','voice'),'invalid character condition')
            elif source=='perceived':
                _shape(c,('source','domain','field','value'))
                from .model import DOMAINS
                check(c['domain'] in ('environment','location','scene','dialogue_turn') and c['field'] in DOMAINS[c['domain']],'invalid perceived condition')
            else: check(False,'unsupported personality condition source')
    check(isinstance(inputs,list) and all(isinstance(p,str) for p in inputs) and len(inputs)==len(set(inputs)) and set(inputs)==properties,'personality property inputs must be declared exactly')
    check(not outputs,'personality policies cannot write properties or success bonuses')
    check(all(isinstance(d,(tuple,list)) and len(d)==3 and isinstance(d[0],str) and type(d[1]) is int and d[2]=='reads' for d in dependencies),'invalid personality dependency')
    check(len(dependencies)==len(prop_versions) and set(tuple(d) for d in dependencies)==prop_versions,'personality property dependencies must be declared exactly')

def policy_domains(policy):
    domains={'character','personality_profile'}
    mapping={'aspect':'character_aspect','relationship':'relationship','will':'will_expression','mbti':'personality_profile'}
    for i in policy['influences']:
        for c in i['when']:
            if c['source'] in mapping: domains.add(mapping[c['source']])
            if c['source']=='perceived': domains.add(c['domain'])
            if c['source']=='will': domains.add('will_definition')
    return sorted(domains)

def validate_policy_references(e,policy):
    for i in policy['influences']:
        for c in i['when']:
            if c['source']=='property':
                definition=e._definition(c['id'],c['version'])
                e._property_value_parts(definition,'known',c['value'],c['unit'])
                check(c['unit']==definition['unit'],'personality property unit mismatch')
                check(c['operator']=='==' or definition['value_type'] in ('number','integer'),'ordered condition needs a numeric property')
            if c['source']=='will':
                found=[e._record_at_version(b['id'],c['definition'],c['version']) for b in e.db.execute('SELECT id FROM branches')]
                check(any(r and r['domain']=='will_definition' for r in found),'personality Will definition unavailable')

def _ref(r):
    return {'id':r['id'],'version':r['version'],'domain':r['domain']}

def brief(e, branch, character_id, domain='dialogue', interlocutors=None, scene=None, viewer=None, domains=None):
    from .characters import active
    check(domain in SCOPES,'invalid personality scope')
    domains=[domain] if domains is None else domains
    check(isinstance(domains,list) and all(isinstance(x,str) for x in domains) and domain in domains and set(domains)<=SCOPES and len(domains)==len(set(domains)),'invalid mixed personality scopes')
    actor=e.get(branch,character_id)
    check(actor and actor['domain']=='character' and (viewer is None or e._visible(actor,viewer)),'character unavailable')
    interlocutors=[] if interlocutors is None else interlocutors
    check(isinstance(interlocutors,list) and all(isinstance(i,str) for i in interlocutors) and len(interlocutors)==len(set(interlocutors)),'invalid interlocutors')
    for rid in interlocutors:
        r=e.get(branch,rid); check(r and r['domain']=='character' and (viewer is None or e._visible(r,viewer)),'interlocutor unavailable')
    if scene:
        sr=e.get(branch,scene); check(sr and sr['domain']=='scene' and (viewer is None or e._visible(sr,viewer)),'scene unavailable')
    all_records=e.state(branch)
    own=[r for r in all_records if r['data'].get('character')==character_id]
    if viewer is not None: own=[r for r in own if e._visible(r,viewer)]
    profile=next((r for r in own if r['domain']=='personality_profile'),None)
    aspects=[r for r in own if r['domain']=='character_aspect' and active(e,branch,r['data'],viewer) and (not r['data'].get('related_character') or r['data']['related_character'] in interlocutors)]
    relationships=[r for r in all_records if r['domain']=='relationship' and r['data']['subject']==character_id and r['data']['object'] in interlocutors and (viewer is None or e._visible(r,viewer))]
    # Actual holder/observer determines knowledge. Public visibility alone is
    # insufficient to put arbitrary world records into an NPC's consciousness.
    knowledge=[r for r in all_records if (r['domain']=='knowledge' and r['data'].get('holder')==character_id or r['domain']=='character_aspect' and r['data'].get('character')==character_id and r['data']['kind']=='memory' and active(e,branch,r['data'],viewer)) and (viewer is None or e._visible(r,viewer))]
    observations=[o for o in e.observations(branch,viewer=viewer) if o['observer_id']==character_id]
    location=actor['data'].get('location')
    perceived=[r for r in all_records if e._visible(r,character_id) and (viewer is None or e._visible(r,viewer)) and (
        r['domain']=='location' and r['id']==location or
        r['domain']=='environment' and r['data'].get('location')==location or
        r['domain']=='scene' and r['id']==scene and r['data'].get('location')==location or
        r['domain']=='dialogue_turn' and (character_id in r['data']['listeners'] or r['data']['speaker']==character_id))]
    wills=[r for r in all_records if r['domain'] in ('will','will_expression') and r['data'].get('bearer')==character_id and (viewer is None or e._visible(r,viewer))]
    expression_ids={r['id'] for r in wills if r['domain']=='will_expression'}
    development=[r for r in all_records if (r['domain']=='progression' and r['data'].get('character')==character_id or r['domain']=='will_development' and r['data'].get('expression') in expression_ids) and (viewer is None or e._visible(r,viewer))]
    receptions=[r for r in all_records if r['domain']=='dialogue_reception' and r['data']['listener']==character_id and (viewer is None or e._visible(r,viewer))]
    superseded={r['data'].get('supersedes') for r in receptions}
    receptions=[r for r in receptions if r['id'] not in superseded]
    # Participant views expose no private evidence, clocks, audiences or hidden
    # reference IDs. Use the existing sanitized world projection, not raw rows.
    if viewer is not None:
        safe={r['id']:r for r in e.context(branch,viewer=viewer)['records']}
        project=lambda rows:[safe[r['id']] for r in rows if r['id'] in safe]
        actor=safe.get(character_id); profile=safe.get(profile['id']) if profile else None
        aspects=project(aspects); relationships=project(relationships); knowledge=project(knowledge); perceived=project(perceived); wills=project(wills); development=project(development); receptions=project(receptions)
        observations=[{k:o[k] for k in ('id','observer_id','assertion','certainty')} for o in observations]
    return {'interface':VERSION,'branch':branch,'revision':e.branch(branch)['revision'],'actor':actor,'domain':domain,'domains':domains,'interlocutors':interlocutors,'scene':scene,
            'profile':profile,'aspects':aspects,'relationships':relationships,'knowledge':knowledge,'observations':observations,'perceived':perceived,'development':development,'receptions':receptions,
            'wills':wills,'capabilities':[r for r in (e.context(branch,viewer=viewer)['records'] if viewer else own) if r['domain']=='capability' and r['data']['character']==character_id],
            'limitations':['Interpretive character model; no automatic speech, consent, mastery or numerical freedom score.']}

def _match(e,branch,actor,b,c):
    source=c['source']; hits=[]; known=True
    if source=='mbti':
        p=b['profile']; known=bool(p and p['data']['interpretation']=='accepted')
        if known and p['data']['type_code'][('EI','SN','TF','JP').index(c['axis'])]==c['value']: hits=[_ref(p)]
    elif source=='aspect':
        candidates=[r for r in b['aspects'] if r['data']['kind']==c['kind']]
        hits=[_ref(r) for r in candidates if r['data']['value_status']=='known' and r['data']['statement']==c['value']]
        known=bool(hits) or bool(candidates) and all(r['data']['value_status']!='unknown' for r in candidates)
    elif source=='relationship':
        candidates=[r for r in b['relationships'] if r['data']['kind']==c['kind']]; known=any(r['data'].get(c['field']) is not None for r in candidates)
        hits=[_ref(r) for r in candidates if r['data'].get(c['field'])==c['value']]
    elif source=='will':
        for r in b['wills']:
            if r['domain']=='will_expression' and r['data']['contract']['definition']=={'id':c['definition'],'version':c['version']}:
                hits.append(_ref(r))
        known=bool(b['wills'])
    elif source=='character':
        value=b['actor']['data'].get(c['field']); known=value is not None
        if known and value==c['value']: hits=[_ref(b['actor'])]
    elif source=='perceived':
        candidates=[r for r in b['perceived'] if r['domain']==c['domain']]; known=bool(candidates)
        hits=[_ref(r) for r in candidates if r['data'].get(c['field'])==c['value']]
    elif source=='property':
        pv=e.property_value(branch,actor,c['id'],c['version'])
        if pv is None or pv['state'] in ('unknown','disputed'): return False,[],False
        if pv['state'] in ('absent','not_applicable'): return False,[],True
        check(pv['unit']==c['unit'],'personality property unit mismatch')
        stored=e.db.execute('SELECT * FROM property_values WHERE branch=? AND entity_id=? AND property_id=? AND definition_version=?',(branch,actor,c['id'],c['version'])).fetchone()
        e._validate_property_assignment(branch,dict(stored),stored=True)
        life=e.db.execute('SELECT state FROM property_lifecycle WHERE property_id=? AND definition_version=? ORDER BY sequence DESC LIMIT 1',(c['id'],c['version'])).fetchone()
        check(life and life[0]=='active','personality property must be active')
        v=pv['value']; target=c['value']; op=c['operator']
        if op=='==': result=type(v)==type(target) and v==target or type(v) in (int,float) and type(target) in (int,float) and v==target
        else:
            check(type(v) in (int,float) and type(target) in (int,float),'personality ordered comparison requires numbers')
            result={'>=':v>=target,'<=':v<=target,'>':v>target,'<':v<target}[op]
        return result,[{'property_id':c['id'],'version':c['version'],'subject':actor,'value':v,'unit':pv['unit']}],True
    return bool(hits),hits,known

def evaluate(e,rule_id,version,branch,character_id,context=None):
    context={} if context is None else context
    _shape(context,(),('domain','domains','interlocutors','scene'))
    row=e.db.execute('SELECT * FROM rule_definitions WHERE rule_id=? AND rule_version=?',(rule_id,version)).fetchone()
    check(row is not None,'personality policy unavailable')
    policy=json.loads(row['definition_json']); deps=[(r['property_id'],r['property_version'],r['usage']) for r in e.db.execute('SELECT * FROM rule_dependencies WHERE rule_id=? AND rule_version=?',(rule_id,version))]
    validate_policy(policy,json.loads(row['inputs_json']),json.loads(row['outputs_json']),deps)
    check(policy['design_status']=='active','personality policy remains proposed')
    b=brief(e,branch,character_id,**context); check(set(b['domains'])<=set(policy['scopes']),'personality policy does not cover every requested scope')
    options={o['id']:copy.deepcopy(o) for o in policy['options']}; explanations=[]; unknown=[]
    for influence in policy['influences']:
        if not set(influence.get('scopes',policy['scopes'])).intersection(b['domains']): continue
        results=[_match(e,branch,character_id,b,c) for c in influence['when']]
        if any(not v[2] for v in results): unknown.append(influence['id'])
        if all(v[0] for v in results):
            opt=options[influence['option']]; opt['weight']*=influence['factor']
            explanations.append({'id':influence['id'],'option':influence['option'],'factor':influence['factor'],'rationale':influence['rationale'],'sources':[s for v in results for s in v[1]]})
    total=sum(o['weight'] for o in options.values())
    check(math.isfinite(total),'personality weight overflow')
    for o in options.values(): o['relative_share']=o['weight']/total if total else None
    return {'rule_id':rule_id,'rule_version':version,'mechanical':True,'kind':'personality','inputs':b,
            'output':{'options':sorted(options.values(),key=lambda o:(-o['weight'],o['id'])),'influences':explanations,'unresolved':unknown,
                      'interpretation':'Authored relative selection weights, not empirical personality probabilities or action success modifiers.','open_actions':True}}

def decision_context(e,branch,actor,modules,request=None):
    request={} if request is None else request
    _shape(request,(),('domain','interlocutors','scene','policy','selected','rationale'))
    domain=request.get('domain',{'social':'relationship','discovery':'options','travel':'options','downtime':'growth'}.get(next(iter(modules or []),'decision'),next(iter(modules or []),'decision')))
    ctx={k:request[k] for k in ('interlocutors','scene') if k in request}; ctx['domain']=domain
    mapped=[{'social':'relationship','discovery':'options','travel':'options','downtime':'growth'}.get(m,m) for m in modules]
    ctx['domains']=list(dict.fromkeys([domain,*mapped]))
    b=brief(e,branch,actor,**ctx)
    policy=request.get('policy')
    if policy is None and b['profile'] and b['profile']['data'].get('policy_id'):
        p=b['profile']['data']; policy={'id':p['policy_id'],'version':p['policy_version']}
    result={'brief':b,'selection':None}; dependencies=[]
    if policy:
        _shape(policy,('id','version'))
        evaluation=e.evaluate_rule(policy['id'],policy['version'],branch,subject_id=actor,inputs=ctx)
        check(evaluation.get('kind')=='personality','decision personality policy has wrong kind')
        result['evaluation']=evaluation
        dependencies.append({'kind':'rule','ref_id':policy['id'],'version':str(policy['version']),'usage':'personality'})
        for prop in e.db.execute('SELECT property_id,property_version FROM rule_dependencies WHERE rule_id=? AND rule_version=?',(policy['id'],policy['version'])):
            dependencies.append({'kind':'property','ref_id':prop[0],'version':str(prop[1]),'usage':'personality'})
    if 'selected' in request:
        check(policy is not None,'selected personality option requires policy')
        check(request['selected'] in {o['id'] for o in result['evaluation']['output']['options']},'selected personality option unavailable')
        check(isinstance(request.get('rationale'),str) and request['rationale'].strip(),'personality selection rationale required')
        result['selection']={'id':request['selected'],'rationale':request['rationale']}
    records=[b['actor'],*b['aspects'],*b['relationships'],*b['knowledge'],*b['perceived'],*b['wills'],*b['capabilities'],*b['development'],*b['receptions']]
    if b['profile']: records.append(b['profile'])
    for r in {r['id']:r for r in records}.values(): dependencies.append({'kind':'record','ref_id':r['id'],'version':str(r['version']),'usage':'personality'})
    return result,dependencies

def record(e,branch,request_id,expected_revision,actor,narrative,changes):
    check(isinstance(changes,list) and changes,'personality changes required')
    for c in changes:
        old=e.get(branch,c.get('id'))
        domain=c.get('domain',old['domain'] if old else None)
        check(domain in ('personality_profile','character_aspect','relationship','knowledge'),'use decision outcomes for capability or world changes')
    return e.apply({'api_version':3,'branch':branch,'request_id':request_id,'expected_revision':expected_revision,'actor':actor,'narrative':narrative,'kind':'observation','changes':changes})

def opportunity_context(e,branch,actor,viewer=None,scene=None):
    b=brief(e,branch,actor,domain='options',scene=scene,viewer=viewer)
    result={'brief':b,'guidance':None}
    if viewer is None and b['profile'] and b['profile']['data'].get('policy_id'):
        p=b['profile']['data']
        row=e.db.execute('SELECT definition_json FROM rule_definitions WHERE rule_id=? AND rule_version=?',(p['policy_id'],p['policy_version'])).fetchone()
        policy=json.loads(row[0])
        if policy['design_status']=='active' and 'options' in policy['scopes']:
            result['guidance']=evaluate(e,p['policy_id'],p['policy_version'],branch,actor,{'domain':'options','scene':scene})
        else:
            result['judgment_required']='Profile policy does not implement current opportunity guidance.'
    return result

def validate_grounding(e,branch,actor,request,grounding):
    _shape(grounding,('claims','review'),('rhetoric',))
    if 'rhetoric' in grounding:
        from .writing import validate_rhetoric
        validate_rhetoric(e,branch,actor,request,grounding['rhetoric'])
    claims=grounding['claims']; review=grounding['review']
    _shape(review,('by','rationale'))
    check(all(isinstance(review[k],str) and review[k].strip() for k in review),'dialogue semantic review required')
    b=brief(e,branch,actor,domain='dialogue',interlocutors=request.get('interlocutors'),scene=request.get('scene'))
    location=b['actor']['data'].get('location')
    check(location is not None,'dialogue delivery needs an established location or a supported communication extension')
    check(all(e.get(branch,rid)['data'].get('location')==location for rid in b['interlocutors']),'dialogue delivery requires co-location; remote communication needs an extension')
    if request.get('scene'):
        check(e.get(branch,request['scene'])['data']['location']==location,'dialogue scene does not match speaker location')
    knowledge={r['id']:r for r in b['knowledge']}; observed={o['id']:o for o in b['observations']}
    perceived={r['id']:r for r in b['perceived']}
    check(isinstance(claims,list),'dialogue claims must be a list')
    for claim in claims:
        _shape(claim,('mode','assertion','basis'))
        check(claim['mode'] in ('assertion','belief','hypothesis','lie') and isinstance(claim['assertion'],str) and claim['assertion'].strip(),'invalid dialogue claim')
        check(isinstance(claim['basis'],list),'invalid claim basis')
        check(claim['mode'] in ('hypothesis','lie') or claim['basis'],'assertion or belief needs speaker evidence')
        for ref in claim['basis']:
            _shape(ref,('kind','id'),('version',))
            if ref['kind']=='record':
                r=knowledge.get(ref['id']) or perceived.get(ref['id'])
                check(r is not None and ref.get('version')==r['version'],'dialogue claim source unavailable to speaker')
                if r['domain']=='knowledge' and claim['mode']=='assertion':
                    check(r['data']['attitude']=='knows','unverified knowledge needs belief or hypothesis framing')
                if r['domain']=='knowledge' and claim['mode']=='belief':
                    check(r['data']['attitude'] in ('knows','believes','suspects'),'unknown knowledge cannot ground a belief claim')
                if r['domain']=='character_aspect' and claim['mode'] in ('assertion','belief'):
                    check(r['data']['value_status']=='known','unresolved memory cannot ground a claim')
            else:
                check(ref['kind']=='observation' and ref['id'] in observed,'dialogue observation unavailable to speaker')

def dialogue_propose(e,branch,spec,turn,claims,review,rhetoric=None):
    """Drafting is external; this compiles a grounded turn into the same decision."""
    from .decisions import propose
    _shape(turn,('id','listeners','act','text','mode','visibility'),('scene','reply_to','audience'))
    p=copy.deepcopy(spec); actor=p['actor']
    p.setdefault('personality',{}); p['personality'].update(domain='dialogue',interlocutors=turn['listeners'])
    if turn.get('scene'): p['personality']['scene']=turn['scene']
    check(isinstance(turn['listeners'],list) and all(isinstance(i,str) for i in turn['listeners']),'invalid dialogue listeners')
    data={k:turn[k] for k in ('listeners','act','text','mode','scene','reply_to') if k in turn}; data['speaker']=actor
    speech={'op':'create','domain':'dialogue_turn','id':turn['id'],'data':data,'status':'confirmed','visibility':turn['visibility'],'audience':turn.get('audience',[]),'evidence':[{'note':'Authored speech, with private pre-commit grounding in the decision judgment.'}]}
    for outcome in ('success','failure'):
        p['outcomes'][outcome].setdefault('changes',[]).append(copy.deepcopy(speech))
        for listener in turn['listeners']:
            p['outcomes'][outcome].setdefault('observations',[]).append({'id':branch+':heard:'+turn['id']+':'+listener,'observer_id':listener,'subject_id':actor,'assertion':turn['text'],'certainty':'heard_utterance' if turn['mode']=='spoken' else 'observed_gesture','visibility':'restricted','audience':[listener]})
    p['dialogue_grounding']={'claims':claims,'review':review}
    if rhetoric is not None:p['dialogue_grounding']['rhetoric']=rhetoric
    return propose(e,branch,p)
