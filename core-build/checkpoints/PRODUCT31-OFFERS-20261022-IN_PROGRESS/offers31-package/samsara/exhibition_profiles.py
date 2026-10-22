"""Bounded NEW exhibition/repair authoring data over existing native equipment.

No Engine, database, process, installer or participant authority is created here.
Root supplies genuine selected native images and its trusted record validator;
these are internal equipment, never data callbacks. D6 region parsing is intact.
"""
from copy import deepcopy
import re

from kageyoni.engine import Rejected
from kageyoni.model import DOMAINS
from kageyoni.workspaces.world import _validate, _expand, _same_value
from kageyoni.contests import (BOUNDARY, validate_terms, validate_resource,
                               validate_conservation, ContestValidationError)
from kageyoni.characters import validate_world as validate_characters
from kageyoni.writing import validate_world as validate_writing
from .contentsets import ContentSets, parse, shape, integer, text, require
from .protocol import Fault, digest

FORMAT = 'samsara-authored-exhibition/1'
PREFIX = 'synthetic:f3a:'
EXHIBITION_PREFIX = PREFIX + 'exhibition:'
REPAIR_PREFIX = PREFIX + 'repair:'
CONTEST_DOMAINS = frozenset(('contest_terms', 'contest_consent', 'contest_settlement'))
TOP = ('format','id','version','canonical','provenance','existing_refs','native_records','exhibition','award','repairs')
ENCOUNTER = ('id','version','spec','binding','site_id','ordinary_alternative')
AWARD = ('amount','unit','pool_id','destinations','eligible_actions','boundary')
REPAIR = ('encounter','beneficiary_role','helper_role','target_id','target_loadout_id','award_id','incorporated_id','tool_id','tool_loadout_id','material_action','helper_accept_action','helper_decline_action')
IMAGE = frozenset(('branch','id','domain','version','status','visibility','audience','evidence','data','updated_event'))
PHYSICAL_EFFECTS = frozenset(('scene','participation','resource','item','historical_account','dialogue_turn'))


def _id(value, prefix=None):
    text(value, 128)
    require(value.strip() == value and (prefix is None or value.startswith(prefix)))
    return value


def _sha(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None)


def _native_check(function, *args):
    try:
        return function(*args)
    except (Rejected, ContestValidationError, KeyError, TypeError, ValueError, OverflowError):
        raise Fault('INVALID') from None


def _image(change, branch, version=1):
    domain=change['domain']
    return {'branch':branch,'id':change['id'],'domain':domain,'version':version,
            'status':change['status'],'visibility':change['visibility'],
            'audience':deepcopy(change.get('audience',[])), 'evidence':deepcopy(change['evidence']),
            'data':{key:deepcopy(change['data'].get(key)) for key in DOMAINS[domain]},
            'updated_event':'profile-validation-only'}


def _record(record, validate):
    require(record['domain'] not in CONTEST_DOMAINS and not record['domain'].startswith('will_'), 'UNSUPPORTED')
    # An external policy implementation cannot be established from record-only images.
    require(record['domain'] != 'personality_profile', 'UNSUPPORTED')
    _native_check(validate, deepcopy(record))


def _references(record, pool):
    require(record['domain'] in DOMAINS)
    for field,kind in DOMAINS[record['domain']].items():
        value=record['data'].get(field)
        if kind.startswith('ref:') and value is not None:
            require(type(value) is str and value in pool and pool[value]['domain'] in kind[4:].split('|'))
    require(all(type(a) is str and a in pool and pool[a]['domain']=='character' for a in record['audience']))
    if record['domain']=='dialogue_turn':
        listeners=record['data']['listeners']
        require(type(listeners) is list and len(listeners)==len(set(listeners))
                and all(type(a) is str and a in pool and pool[a]['domain']=='character' for a in listeners))
    if record['domain']=='location':
        seen={record['id']};parent=record['data'].get('parent')
        while parent:
            require(parent in pool and parent not in seen and pool[parent]['domain']=='location')
            seen.add(parent);parent=pool[parent]['data'].get('parent')


def _world(pool):
    for image in pool.values(): _references(image,pool)
    def native_require(ok,message): require(ok)
    _native_check(validate_characters,pool,native_require)
    _native_check(validate_writing,pool)
    for domain,fields,equipped in [('loadout',('item',),False),('loadout',('holder','slot'),True),
                                   ('participation',('scene','character'),False),('capability',('character','ability'),False)]:
        seen=set()
        for image in pool.values():
            if image['domain']!=domain or equipped and image['data'].get('equipped')!=1:continue
            key=tuple(image['data'].get(field) for field in fields)
            if None in key:continue
            require(key not in seen);seen.add(key)


def _field_requirement(requirement,pool):
    shape(requirement,('record_id','field','equals'))
    row=pool.get(requirement['record_id']);require(row is not None)
    kind=DOMAINS[row['domain']].get(requirement['field']);require(kind is not None)
    value=requirement['equals']
    if value is None:return
    if kind in ('number','integer'):
        require(type(value) in ((int,float) if kind=='number' else (int,)))
    elif kind=='json':require(type(value) in (dict,list))
    else:
        require(type(value) is str)
        if kind.startswith('enum:'):require(value in kind[5:].split('|'))
        if kind.startswith('ref:'):require(value in pool and pool[value]['domain'] in kind[4:].split('|'))


def _requires(action, rid, field, expected):
    return any(r['record_id']==rid and r['field']==field and _same_value(r['equals'],expected) for r in action['requirements'])


def _reachable(spec, blocked_action=None):
    seen=set();todo=[spec['initial_state']]
    while todo:
        state=todo.pop()
        if state in seen:continue
        seen.add(state)
        for aid in spec['states'][state]['actions']:
            if aid!=blocked_action:todo.append(spec['actions'][aid]['next_state'])
    return seen


def _free_exit(action,spec,actor,ending):
    state=spec['states'][action['next_state']]
    if state['phase'] not in ('completed','failed') or state['outcome'] not in ('not_achieved','partly_achieved'):
        return False
    if action['payload'].get('observations') or any(action.get(key) for key in ('resolve_loops','detach_loops','cancel_loops')):return False
    for change in action['payload'].get('changes',[]):
        report=(change['op']=='create' and change['domain'] in ('historical_account','dialogue_turn')
                and change['data'].get('author',change['data'].get('speaker'))==actor)
        cleanup=change['op']=='patch' and change in ending
        if not (report or cleanup):return False
    return True


def _physical_effect(change,pool,ending):
    """A testimony/maintenance-only terminal is never an eligible result."""
    image=pool[change['id']]
    cleanup=change['op']=='patch' and any(
        c['id']==change['id'] and _same_value(c['data'],change['data'])
        for c in ending)
    if image['domain'] not in ('scene','participation','resource','item') or cleanup:return False
    if change['op']=='create':
        if image['domain']=='scene':return image['data']['phase']!='closed'
        if image['domain']=='participation':return bool(image['data'].get('actions_remaining') or image['data'].get('active_effects'))
        return True
    return any(not _same_value(image['data'].get(field),value) for field,value in change['data'].items())


def _compile(encounter,pool,validate,*,prefix,binding=None):
    shape(encounter,ENCOUNTER);_id(encounter['id'],prefix);integer(encounter['version'],1,1000)
    text(encounter['ordinary_alternative'],4000)
    require(type(encounter['binding']) is dict and len(encounter['binding'])==2)
    bound=encounter['binding'];require(len(set(bound.values()))==2)
    require(all(type(role) is str and role and actor in pool and pool[actor]['domain']=='character' for role,actor in bound.items()))
    if binding is not None:require(bound==binding)
    site=pool.get(encounter['site_id']);require(site is not None and site['domain']=='location')
    spec=_native_check(ContentSets.compiled_spec,encounter)
    require(set(spec['roles'])==set(bound) and spec['visibility']=='public' and 'ending' in spec)
    require(all(action['kind']=='event' and 'next_state' in action for action in spec['actions'].values()), 'UNSUPPORTED')
    eid=PREFIX+'validation:'+digest([encounter['id'],encounter['version']])[:32]
    expanded=_native_check(_expand,spec,bound,eid)
    prototypes=deepcopy(pool);creators={};actions=expanded['actions']
    for aid,action in actions.items():
        shape(action['payload'],(),('changes','observations'))
        changes=action['payload'].get('changes',[]);require(type(changes) is list and len(changes)<=128)
        for change in changes:
            require(type(change) is dict and change.get('op') in ('create','patch'))
            _id(change.get('id'))
            if change['op']=='create':
                shape(change,('op','id','domain','data','status','visibility','evidence'),('audience',))
                require(change['id'].startswith(eid+':') and change['id'] not in pool and change['domain'] in DOMAINS)
                require(type(change['data']) is dict and set(change['data'])<=set(DOMAINS[change['domain']]))
                require(change['domain'] in PHYSICAL_EFFECTS and change['domain']!='resource', 'UNSUPPORTED')
                prototype=_image(change,next(iter(pool.values()))['branch']);_record(prototype,validate)
                require(change['id'] not in creators or creators[change['id']]==prototype)
                creators[change['id']]=prototype;prototypes[change['id']]=prototype
    reachable=_reachable(expanded);require(set(expanded['states'])==reachable)
    require(set(actions)=={a for state in reachable for a in expanded['states'][state]['actions']})
    # Definite/maybe created sets across all authored paths, including cycles.
    universe=set(prototypes);initial=set(pool)
    definite={s:(initial.copy() if s==expanded['initial_state'] else universe.copy()) for s in reachable}
    maybe={s:(initial.copy() if s==expanded['initial_state'] else set()) for s in reachable}
    incoming={s:[] for s in reachable}
    for state in reachable:
        for aid in expanded['states'][state]['actions']:
            adds={x['id'] for x in actions[aid]['payload'].get('changes',[]) if x['op']=='create'}
            incoming[actions[aid]['next_state']].append((state,adds))
    for _ in range(len(reachable)*len(reachable)+1):
        changed=False
        for state in reachable:
            paths=[definite[s]|add for s,add in incoming[state]]
            possibilities=[maybe[s]|add for s,add in incoming[state]]
            if state==expanded['initial_state']:paths.append(initial);possibilities.append(initial)
            new=set.intersection(*paths) if paths else initial.copy();may=set.union(*possibilities) if possibilities else set()
            if new!=definite[state] or may!=maybe[state]:changed=True;definite[state]=new;maybe[state]=may
        if not changed:break
    else:require(False)
    for state in reachable:
        for aid in expanded['states'][state]['actions']:
            action=actions[aid];post=deepcopy(prototypes);seen=set()
            requirements={}
            for requirement in action['requirements']:
                _field_requirement(requirement,prototypes);require(requirement['record_id'] in definite[state])
                key=(requirement['record_id'],requirement['field'])
                require(key not in requirements or _same_value(requirements[key],requirement['equals']))
                requirements[key]=requirement['equals']
            for change in action['payload'].get('changes',[]):
                require(change['id'] not in seen);seen.add(change['id'])
                if change['op']=='create':require(change['id'] not in maybe[state])
                else:
                    shape(change,('op','id','data','evidence'),('domain','expected_version'))
                    require(change['id'] in definite[state] and type(change['data']) is dict)
                    image=deepcopy(prototypes[change['id']]);require(change.get('domain',image['domain'])==image['domain'])
                    require(image['domain'] in PHYSICAL_EFFECTS and image['domain'] not in CONTEST_DOMAINS, 'UNSUPPORTED')
                    if image['domain'] in ('scene','participation'):require(change['id'] in creators)
                    if 'expected_version' in change:integer(change['expected_version'])
                    image['data'].update(deepcopy(change['data']));image['evidence']=deepcopy(change['evidence']);image['version']+=1
                    _record(image,validate);post[image['id']]=image
            for change in action['payload'].get('changes',[]):
                image=post[change['id']]
                # A future/alternative creator in the prototype catalog is not
                # a current native reference. Same-event creates are available.
                available=definite[state]|seen
                _references(image,{rid:post[rid] for rid in available})
                if image['domain']=='historical_account':require(image['data'].get('author')==bound[action['actor_role']])
                if image['domain']=='dialogue_turn':require(image['data']['speaker']==bound[action['actor_role']])
            observations=action['payload'].get('observations',[]);require(type(observations) is list and len(observations)<=128)
            for obs in observations:
                shape(obs,('id','observer_id','subject_id','assertion','certainty','visibility'),('audience',))
                require(type(obs['id']) is str and obs['id'].startswith(eid+':'))
                text(obs['assertion'],64000);text(obs['certainty'],128)
                available=definite[state]|seen
                require(obs['observer_id'] in available and post[obs['observer_id']]['domain']=='character' and obs['subject_id'] in available)
                require(obs['visibility'] in ('public','restricted','gm') and type(obs.get('audience',[])) is list)
                require(obs['visibility']!='restricted' or bool(obs.get('audience')))
                require(all(a in available and post[a]['domain']=='character' for a in obs.get('audience',[])))
            _world(post)
            if expanded['states'][action['next_state']]['phase'] in ('completed','failed'):
                cleanup={c['id']:c for c in expanded['ending']['changes']}
                changed={c['id']:c for c in action['payload'].get('changes',[])}
                for rid in maybe[state]|seen:
                    if rid in creators and creators[rid]['domain'] in ('scene','participation'):
                        require(rid in changed and rid in cleanup)
                        if changed[rid]['op']=='create':
                            require(all(_same_value(post[rid]['data'].get(field),value)
                                        for field,value in cleanup[rid]['data'].items()))
                        else:
                            require(_same_value(changed[rid]['data'],cleanup[rid]['data']))
    ending=expanded['ending']['changes']
    for change in ending:
        require(change['id'] in creators and creators[change['id']]['domain'] in ('scene','participation'))
        image=deepcopy(creators[change['id']]);image['data'].update(change['data']);image['evidence']=change['evidence'];_record(image,validate);_references(image,prototypes)
    for state in reachable:
        offered=expanded['states'][state]['actions']
        if not offered:continue
        substantive={actions[a]['actor_role'] for a in offered if not _free_exit(actions[a],expanded,bound[actions[a]['actor_role']],ending)}
        require(len(substantive)==1 or not substantive and len({actions[a]['actor_role'] for a in offered})==1)
    return spec,expanded,prototypes,creators


def _repair_requirements(action,repair,pool,binding,amount):
    checks=[(repair['award_id'],'quantity',amount),(repair['incorporated_id'],'quantity',0),
            (repair['target_id'],'condition','split')]
    for rid in (repair['target_loadout_id'],repair['tool_loadout_id']):
        image=pool[rid];checks.extend([(rid,'item',image['data']['item']),(rid,'holder',image['data']['holder'])])
    checks.extend([(repair['tool_loadout_id'],'equipped',1),
                   (repair['tool_id'],'condition',pool[repair['tool_id']]['data']['condition'])])
    require(all(_requires(action,*check) for check in checks))


def _validate_profile(blob, *, anchor_images, validate_native_record):
    """Validate trusted operator bytes using genuine root-supplied equipment."""
    profile=parse(blob);shape(profile,TOP)
    require(profile['format']==FORMAT and profile['canonical'] is False)
    _id(profile['id'],PREFIX);integer(profile['version'],1,1000)
    provenance=profile['provenance'];require(type(provenance) is dict and provenance.get('not_recovered_history') is True and provenance.get('participant_authorlore') is False)
    require(type(anchor_images) is dict and callable(validate_native_record))
    refs=profile['existing_refs'];require(type(refs) is list and len(refs)<=128)
    pool={};allids={profile['id']};branches=set()
    for ref in refs:
        shape(ref,('id','domain','record_revision','snapshot_hash'));_id(ref['id']);integer(ref['record_revision']);_sha(ref['snapshot_hash'])
        require(ref['id'] not in allids);allids.add(ref['id'])
        image=anchor_images.get(ref['id']);require(type(image) is dict and set(image)==IMAGE)
        require(image['id']==ref['id'] and image['domain']==ref['domain'] and image['version']==ref['record_revision'] and digest(image)==ref['snapshot_hash'])
        _record(image,validate_native_record);pool[image['id']]=deepcopy(image);branches.add(image['branch'])
    require(len(branches)<=1);branch=next(iter(branches),'profile-validation-only')
    records=profile['native_records'];require(type(records) is list and 1<=len(records)<=512)
    new=set()
    for record in records:
        shape(record,('op','id','domain','data','status','visibility','evidence'),('audience',))
        _id(record['id'],PREFIX);require(record['id'] not in allids and record['op']=='create' and record['domain'] in DOMAINS and type(record['data']) is dict)
        allids.add(record['id']);new.add(record['id'])
        # Preserve authored command shape. _image supplies optional native
        # defaults for validation only; raw carrier history must stay exact.
        # Check unknown fields before normalization to canonical native columns.
        require(set(record['data'])<=set(DOMAINS[record['domain']]))
        image=_image(record,branch);_record(image,validate_native_record);pool[image['id']]=image
    _world(pool)
    exhibition=profile['exhibition'];_id(exhibition.get('id') if type(exhibition) is dict else None,EXHIBITION_PREFIX)
    award=profile['award'];shape(award,AWARD)
    require(type(award['destinations']) is dict and type(award['eligible_actions']) is dict)
    repairs=profile['repairs'];require(type(repairs) is list and 1<=len(repairs)<=2)
    spec,expanded,prototypes,creators=_compile(exhibition,pool,validate_native_record,prefix=EXHIBITION_PREFIX)
    binding=exhibition['binding'];require(set(award['destinations'])==set(binding))
    prizeids=[award['pool_id'],*award['destinations'].values()]
    require(len(set(prizeids))==3 and all(rid in new and pool[rid]['domain']=='resource' for rid in prizeids))
    terms={'version':1,'contest_id':profile['id'],'new_synthetic_exhibition':True,
           'encounter':{'id':PREFIX+'validation:terms','definition_id':exhibition['id'],'definition_version':exhibition['version'],'definition_digest':digest(spec),'participants':binding},
           'pool':{'id':award['pool_id'],'version':1},'destinations':{role:{'id':rid,'version':1} for role,rid in award['destinations'].items()},
           'amount':award['amount'],'unit':award['unit'],'eligible_actions':award['eligible_actions'],'boundary':award['boundary']}
    _native_check(validate_terms,terms,spec)
    _native_check(validate_resource,pool[award['pool_id']],award['unit'])
    require(pool[award['pool_id']]['data']['quantity']>=award['amount'])
    for role,rid in award['destinations'].items():
        _native_check(validate_resource,pool[rid],award['unit'],binding[role]);require(type(pool[rid]['data']['quantity']) is not bool and pool[rid]['data']['quantity']==0)
    possible=set(award['eligible_actions'].values());require(len(repairs)==len(possible))
    targets=set();incorporated=set();seen_roles=set();repair_compiled=[];definitionids={exhibition['id']}
    for repair in repairs:
        shape(repair,REPAIR);role=repair['beneficiary_role'];helper=repair['helper_role']
        require(role in possible and role not in seen_roles and helper in binding and helper!=role);seen_roles.add(role)
        require(repair['award_id']==award['destinations'][role])
        for key,domain in [('target_id','item'),('target_loadout_id','loadout'),('incorporated_id','resource'),('tool_id','item'),('tool_loadout_id','loadout')]:
            require(repair[key] in pool and pool[repair[key]]['domain']==domain)
        require(repair['target_id']!=repair['tool_id'] and repair['target_loadout_id']!=repair['tool_loadout_id'])
        require(pool[repair['target_loadout_id']]['data']['item']==repair['target_id'] and pool[repair['tool_loadout_id']]['data']['item']==repair['tool_id'])
        require(pool[repair['target_id']]['data']['condition']=='split' and pool[repair['tool_loadout_id']]['data']['equipped']==1)
        require(pool[repair['tool_loadout_id']]['data']['holder'] in binding.values())
        # First-profile access is explicit beneficiary possession or this site;
        # broader faction access needs separately qualified native equipment.
        target_holder=pool[repair['target_loadout_id']]['data']['holder']
        require(target_holder in (binding[role],repair['encounter']['site_id'])
                and pool[repair['incorporated_id']]['data']['holder']==target_holder)
        require(repair['incorporated_id'] not in prizeids and repair['incorporated_id'] not in incorporated and repair['target_id'] not in targets)
        targets.add(repair['target_id']);incorporated.add(repair['incorporated_id'])
        _native_check(validate_resource,pool[repair['incorporated_id']],award['unit']);require(pool[repair['incorporated_id']]['data']['quantity']==0)
        enc=repair['encounter'];require(type(enc) is dict and enc.get('id') not in definitionids);definitionids.add(enc.get('id'))
        compiled=_compile(enc,pool,validate_native_record,prefix=REPAIR_PREFIX,binding=binding)
        repair_compiled.append((repair,compiled))
    require(not definitionids & allids)
    protected=set(prizeids)|incorporated|targets
    for action in expanded['actions'].values():
        for change in action['payload'].get('changes',[]):
            require(change['id'] not in protected)
            image=prototypes[change['id']]
            if image['domain']=='resource':
                require(change['op']=='patch' and set(change['data'])=={'quantity'})
                _native_check(validate_resource,image,image['data']['unit'],binding[action['actor_role']])
                before=[r['equals'] for r in action['requirements'] if r['record_id']==image['id'] and r['field']=='quantity']
                require(len(before)==1 and type(before[0]) is int and type(change['data']['quantity']) is int and 0<=change['data']['quantity']<before[0])
    # Both people have real authored physical actions and a choice, not testimony-only wins.
    for role in binding:
        actual=[aid for aid,a in expanded['actions'].items() if a['actor_role']==role and any(_physical_effect(c,prototypes,expanded['ending']['changes']) for c in a['payload'].get('changes',[]))]
        require(actual and any(sum(expanded['actions'][a]['actor_role']==role for a in state['actions'])>=2 for state in expanded['states'].values()))
    for aid in award['eligible_actions']:
        require(any(_physical_effect(c,prototypes,expanded['ending']['changes'])
                    for c in expanded['actions'][aid]['payload'].get('changes',[])))
    exits={a['next_state'] for aid,a in expanded['actions'].items() if aid not in award['eligible_actions'] and expanded['states'][a['next_state']]['phase'] in ('completed','failed')}
    require(any(expanded['states'][s]['outcome']=='not_achieved' for s in exits) and any(expanded['states'][s]['outcome']=='partly_achieved' for s in exits))
    for repair,(raw,expanded_repair,repair_pool,created) in repair_compiled:
        actions=expanded_repair['actions'];material=repair['material_action'];accept=repair['helper_accept_action'];decline=repair['helper_decline_action']
        require(len({material,accept,decline})==3 and all(a in actions for a in (material,accept,decline)))
        require(actions[material]['actor_role']==repair['beneficiary_role'] and actions[accept]['actor_role']==actions[decline]['actor_role']==repair['helper_role'])
        require(expanded_repair['states'][actions[material]['next_state']]['phase']=='completed' and expanded_repair['states'][actions[material]['next_state']]['outcome']=='achieved')
        require(expanded_repair['states'][actions[decline]['next_state']]['phase'] in ('completed','failed') and expanded_repair['states'][actions[decline]['next_state']]['outcome']=='not_achieved')
        initial=expanded_repair['states'][expanded_repair['initial_state']]
        require(len(initial['actions'])==2 and set(initial['actions'])=={accept,decline})
        require(expanded_repair['states'][actions[accept]['next_state']]['phase']=='active')
        # This free helper decision precedes ordinary activity reservation.
        # Only a bounded personal report may accompany it; geometry, tools,
        # material and loop effects belong to later ordinary native actions.
        for aid in (accept,decline):
            action=actions[aid]
            require(not action['payload'].get('observations') and not any(
                action.get(key) for key in ('resolve_loops','detach_loops','cancel_loops')))
            changes=action['payload'].get('changes',[]);require(len(changes)<=1)
            for change in changes:
                require(change['op']=='create' and change['domain']=='historical_account'
                        and change['status'] in ('reported','proposed')
                        and change['data'].get('author')==binding[repair['helper_role']])
        # Remove helper acceptance: no state offering material may remain reachable.
        without=_reachable(expanded_repair,accept)
        require(all(material not in expanded_repair['states'][s]['actions'] for s in without))
        _repair_requirements(actions[material],repair,pool,binding,award['amount'])
        required={repair['award_id']:{'quantity':0},repair['incorporated_id']:{'quantity':award['amount']},repair['target_id']:{'condition':'repaired'}}
        found={}
        for aid,action in actions.items():
            for change in action['payload'].get('changes',[]):
                image=repair_pool[change['id']]
                if change['id'] in protected:
                    require(aid==material and change['id'] in required and change['op']=='patch' and _same_value(change['data'],required[change['id']]))
                    found[change['id']]=change['data']
                elif change['op']=='patch':require(image['domain'] in ('scene','participation'))
            if aid in (accept,decline):require(all(repair_pool[c['id']]['domain']!='resource' for c in action['payload'].get('changes',[])))
        require(found==required)
        before={'pool':deepcopy(pool[repair['award_id']]),'destination':deepcopy(pool[repair['incorporated_id']])}
        before['pool']['data']['quantity']=award['amount'] # hypothetical real settlement preimage; runtime must prove it.
        after={key:{field:deepcopy(image[field]) for field in ('branch','id','domain','version','data')} for key,image in before.items()}
        for key,quantity in [('pool',0),('destination',award['amount'])]:after[key]['version']+=1;after[key]['data']['quantity']=quantity
        _native_check(validate_conservation,before,after,award['amount'])
    return deepcopy(profile)


def validate_profile(blob, *, anchor_images, validate_native_record):
    """Public strict boundary. Internal equipment exceptions are not success."""
    try:
        return _validate_profile(blob,anchor_images=anchor_images,validate_native_record=validate_native_record)
    except Fault:
        raise
    except (Rejected,ContestValidationError,KeyError,TypeError,ValueError,OverflowError,RecursionError):
        raise Fault('INVALID') from None


def authored_encounters(profile):
    """Only root-validated profiles enter this projection; no runtime authority."""
    shape(profile,TOP);shape(profile['exhibition'],ENCOUNTER)
    for repair in profile['repairs']:shape(repair,REPAIR);shape(repair['encounter'],ENCOUNTER)
    result=[dict(deepcopy(profile['exhibition']),kind='battle')]
    result.extend(dict(deepcopy(r['encounter']),kind='life') for r in sorted(profile['repairs'],key=lambda r:r['beneficiary_role']))
    return result
