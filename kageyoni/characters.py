"""Character contract v1: normalized extensions, no inferred canon or scores."""
DOMAINS = {
    'character_identity': dict(character='ref:character', existence='enum:established|provisional|alleged', canonical_name='text', name_status='enum:known|unknown|absent|not_applicable', continuity='enum:established|disputed|unresolved|transformed'),
    'character_aspect': dict(character='ref:character', section='enum:nature|interiority|portrayal|condition|perspective|development', kind='enum:facet|embodiment|constituent|principle|drive|commitment|preference|boundary|conflict|description|voice|mannerism|habit|pleasure|attachment|injury|fatigue|memory_disruption|recognition_disruption|intention_impairment|agency_constraint|communication|memory|question', value_status='enum:known|unknown|absent|not_applicable', statement='text', related_character='ref:character', related_item='ref:item', clock='ref:clock', valid_from='number', valid_until='number', ending_condition='text', phase='enum:active|ended', change_basis='enum:established|voluntary|compelled|deceived|disrupted|recovered|unknown', supersedes='ref:character_aspect'),
    'character_presence': dict(character='ref:character', location='ref:location', embodiment='ref:character_aspect', mode='enum:physical|projected|distributed|unknown', phase='enum:present|departed|uncertain'),
    'character_lineage': dict(predecessor='ref:character', successor='ref:character', relation='enum:origin|split|merge|succession|copy|fragment|disputed', explanation='text'),
}
REQUIRED = {
    'character_identity': ['character','existence','name_status','continuity'],
    'character_aspect': ['character','section','kind','value_status','phase','change_basis'],
    'character_presence': ['character','location','mode','phase'],
    'character_lineage': ['predecessor','successor','relation','explanation'],
}
SECTIONS = {
    'nature': {'facet','embodiment','constituent'},
    'interiority': {'principle','drive','commitment','preference','boundary','conflict'},
    'portrayal': {'description','voice','mannerism','habit','pleasure','attachment'},
    'condition': {'injury','fatigue','memory_disruption','recognition_disruption','intention_impairment','agency_constraint','communication'},
    'perspective': {'memory'}, 'development': {'question'},
}

# Personality and affect reuse the existing event-sourced, independently visible
# aspect records. No numeric personality default or duplicate relationship store.
PERSONALITY_KINDS = {
    'interiority': {'self_concept'},
    'portrayal': {'attention_style','thinking_style','humor','regulation','verbal_style'},
    'condition': {'emotion','comfort','arousal','expression_state'},
    'perspective': {'appraisal','thought'},
}
for section, kinds in PERSONALITY_KINDS.items():
    SECTIONS[section].update(kinds)
DOMAINS['character_aspect']['kind'] += '|' + '|'.join(sorted(set().union(*PERSONALITY_KINDS.values())))

DOMAINS.update({
    'personality_profile': dict(character='ref:character', framework='enum:mbti-inspired', type_code='text', interpretation='enum:proposed|accepted|unknown', note='text', policy_id='text', policy_version='integer'),
    'dialogue_turn': dict(speaker='ref:character', listeners='json', scene='ref:scene', reply_to='ref:dialogue_turn', act='text', text='text', mode='enum:spoken|gesture|silence'),
})
REQUIRED.update({
    'personality_profile':['character','framework','interpretation','note'],
    'dialogue_turn':['speaker','listeners','act','text','mode'],
})

def validate(record, require):
    d = record['data']; domain = record['domain']
    if domain == 'character_identity':
        known = d['name_status'] == 'known'
        require(bool(d.get('canonical_name') and d['canonical_name'].strip()) if known else d.get('canonical_name') is None,
                'canonical name contradicts name status')
    elif domain == 'character_aspect':
        require(d['kind'] in SECTIONS[d['section']], 'aspect kind does not belong to section')
        known = d['value_status'] == 'known'
        require(bool(d.get('statement') and d['statement'].strip()) if known else d.get('statement') is None,
                'aspect statement contradicts value status')
        require(not (d.get('related_character') and d.get('related_item')), 'aspect has conflicting related subjects')
        require(d.get('supersedes') != record['id'], 'aspect cannot supersede itself')
        start, end = d.get('valid_from'), d.get('valid_until')
        require((start is None and end is None) or d.get('clock') is not None, 'validity interval requires clock')
        require(start is None or end is None or start <= end, 'invalid validity interval')
    elif domain == 'character_lineage':
        require(d['predecessor'] != d['successor'], 'lineage requires distinct identities')

def validate_world(records, require):
    identities = set(); edges = {}
    for r in records.values():
        d = r['data']
        if r['domain'] == 'character_identity':
            require(d['character'] not in identities, 'duplicate character identity extension')
            identities.add(d['character'])
        if r['domain'] == 'character_aspect' and d.get('supersedes'):
            old = records[d['supersedes']]['data']
            require(old['character'] == d['character'] and old['kind'] == d['kind'], 'incompatible superseded aspect')
            require(old['phase'] == 'ended', 'superseded aspect must be ended in the same event or earlier')
            edges[r['id']] = d['supersedes']
        if r['domain'] == 'character_presence' and d.get('embodiment'):
            body = records[d['embodiment']]['data']
            require(body['character'] == d['character'] and body['kind'] == 'embodiment', 'presence embodiment ownership mismatch')
    for node in edges:
        seen = set()
        while node in edges:
            require(node not in seen, 'character aspect supersession cycle')
            seen.add(node); node = edges[node]

def create(engine, *, branch, request_id, expected_revision, actor, narrative,
           character_id, label, existence, evidence, visibility, audience=None,
           canonical_name=None, name_status='unknown', continuity='unresolved',
           entity_kind='unknown', aspects=None, profile=None):
    """Create identity and separately visible details in one existing transaction."""
    from .engine import require
    require(isinstance(label,str) and bool(label.strip()), 'character working label required')
    require(aspects is None or isinstance(aspects,list), 'aspects must be a list')
    common = dict(op='create', status={'established':'confirmed','provisional':'proposed','alleged':'reported'}.get(existence, 'unknown'),
                  evidence=evidence, visibility=visibility, audience=audience or [])
    changes = [dict(common, domain='character', id=character_id, data=dict(name=label,entity_kind=entity_kind)),
               dict(common, domain='character_identity', id=character_id+'.identity', data=dict(character=character_id,existence=existence,canonical_name=canonical_name,name_status=name_status,continuity=continuity))]
    for aspect in aspects or []:
        allowed = {'id','data','visibility','audience','evidence','status'}
        if not isinstance(aspect, dict) or not set(aspect) <= allowed:
            from .engine import Rejected
            raise Rejected('invalid character aspect fields')
        data = dict(aspect['data'])
        if 'character' in data and data['character'] != character_id:
            from .engine import Rejected
            raise Rejected('aspect belongs to another character')
        data['character'] = character_id
        changes.append({**common, **aspect, 'domain':'character_aspect', 'data':data})
    profiles = []
    if profile is not None:
        from .engine import require
        require(isinstance(profile,dict) and 'entity_id' not in profile, 'profile subject is assigned by character-create')
        profiles.append(dict(profile,entity_id=character_id))
    return engine.apply(dict(api_version=3,branch=branch,request_id=request_id,expected_revision=expected_revision,
                             actor=actor,narrative=narrative,kind='action',changes=changes,profiles=profiles))

def read(engine, branch, character_id, viewer=None):
    from .engine import require
    # Filter visibility before joining. Neither hidden rows nor their counts escape.
    ctx = engine.context(branch, viewer=viewer)
    records = ctx['records']
    character = next((r for r in records if r['id'] == character_id and r['domain'] == 'character'), None)
    require(character is not None, 'character unavailable')
    linked = []
    from .model import DOMAINS as ALL_DOMAINS
    for r in records:
        if r['id'] == character_id:
            continue
        if any(kind.startswith('ref:') and r['data'].get(key) == character_id for key,kind in ALL_DOMAINS[r['domain']].items()):
            linked.append(r)
    profiles = [p for p in ctx['entity_profiles'] if p['entity_id']==character_id]
    if viewer is not None:
        # Existing profile JSON may contain unscoped identifiers. Expose only
        # the explicit scalar agency/control fields through this interface.
        profiles = [{k:p[k] for k in ('entity_id','agency_mode','control_mode','nature')} for p in profiles]
    claims = [dict(r) for r in engine.db.execute('SELECT * FROM classification_claims WHERE branch=? AND subject_id=?',(branch,character_id))] if viewer is None else []
    return dict(character_schema='1', branch=branch, revision=engine.branch(branch)['revision'], character=character, linked_records=linked,
                profiles=profiles, classification_claims=claims,
                properties=[p for p in ctx['properties'] if p.get('entity_id')==character_id],
                observations=[o for o in ctx['observations'] if o.get('subject_id')==character_id and (viewer is None or o.get('observer_id')==viewer)])

def readiness(engine, branch, character_id, level='existence', viewer=None, requirements=None):
    from .engine import require
    require(level in ('existence','scene','action'), 'invalid readiness level')
    view = read(engine, branch, character_id, viewer)
    linked = view['linked_records']; missing = []
    identity = next((r for r in linked if r['domain'] == 'character_identity'), None)
    if identity is None:
        missing.append('explicit existence and continuity assessment')
    if level in ('scene','action'):
        if identity and identity['data']['existence'] != 'established':
            missing.append('established existence for objective scene participation')
        if not view['character']['data'].get('location') and not any(r['domain']=='character_presence' and r['data']['phase']=='present' for r in linked):
            missing.append('relevant presence')
        for section, kinds, label in [('interiority',{'drive','principle'},'motivation'), ('condition',{'communication'},'communication')]:
            if not any(r['domain']=='character_aspect' and r['data']['section']==section and r['data']['kind'] in kinds and r['data']['value_status']=='known' and active(engine,branch,r['data'],viewer) for r in linked):
                missing.append(label)
    if level == 'action':
        require(isinstance(requirements,list) and bool(requirements), 'action readiness requires explicit requirements')
        candidates = {r['id']:r for r in linked+[view['character']]}
        for item in requirements:
            require(isinstance(item,dict) and set(item)=={'record_id','field','equals'}, 'requirement needs record_id, field and equals')
            r = candidates.get(item['record_id'])
            satisfied = bool(r and item['field'] in r['data'] and r['data'][item['field']] == item['equals'])
            if not satisfied:
                missing.append('declared action input unavailable or unsatisfied')
    return dict(character_schema='1',level=level,ready=not missing,missing=missing,
                scope='Visible context completeness only; feasibility and outcomes require action rules or recorded GM judgment.',
                revision=view['revision'])

def active(engine, branch, data, viewer=None):
    if data['phase'] != 'active':
        return False
    if data.get('clock'):
        clock = engine.get(branch, data['clock'])
        if clock is None or (viewer is not None and not engine._visible(clock,viewer)):
            return False
        tick = clock['data']['tick']
        return (data.get('valid_from') is None or tick >= data['valid_from']) and (data.get('valid_until') is None or tick < data['valid_until'])
    return data.get('valid_from') is None and data.get('valid_until') is None
