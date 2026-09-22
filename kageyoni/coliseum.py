"""Opt-in, deterministic arena prototype. Synthetic fixtures, not campaign balance."""
from .engine import require
RULE='coliseum-prototype/1'
RULE_TEXT='Opt-in deterministic prototype: strike costs 1, finisher costs 2 and adds 2 power; reach 1; dodge costs 1 stamina and requires mobility and reaction >= speed; guard costs 1 and needs intact guard; absorbed guard damage uses guard value; penetrating guard damage disables guard. Health 0 ends participation. No automatic killing or undefined Will.'
FIELDS=('health','stamina','power','speed','reaction','guard','mobile','guard_intact')

def open_match(e,branch,request_id,match,stats):
    require(branch!='main','coliseum prototype requires an isolated branch')
    require(len(stats)==2,'exactly two fighters required')
    changes=[];ev=[{'note':'Explicit synthetic coliseum prototype configuration; not canonical character scaling.'}]
    def create(i,d,data):changes.append(dict(op='create',id=i,domain=d,status='confirmed',visibility='public',data=data,evidence=ev))
    create(match,'location',dict(name='Prototype coliseum',kind='room'))
    for fighter,values in stats.items():
        require(set(values)==set(FIELDS),'all arena fields must be explicitly provided')
        require(all(type(x) is int and 0<=x<=100 for x in values.values()),'arena values require bounded nonnegative integers')
        require(values['mobile'] in (0,1) and values['guard_intact'] in (0,1),'mobility/guard flags must be 0 or 1')
        create(fighter,'character',dict(name=fighter,entity_kind='person',location=match,identity='Synthetic arena fighter'))
        for field,value in values.items():create(fighter+':'+field,'resource',dict(holder=fighter,name=field,quantity=value,unit='arena-prototype',availability='explicit fixture'))
    create(match+':distance','resource',dict(holder=match,name='distance',quantity=1,unit='arena-step',availability='explicit fixture'))
    create(match+':rules','world_rule',dict(name=RULE,scope=match,statement=RULE_TEXT,resolution='mechanical'))
    command=dict(api_version=2,branch=branch,expected_revision=e.branch(branch)['revision'],request_id=request_id,kind='action',actor='arena-gm',narrative='Initialize isolated synthetic coliseum match',changes=changes)
    e.apply(command,preview=True);return e.apply(command)

def exchange(e,branch,request_id,match,attacker,defender,intent,defense,expected_revision):
    from .workflows import Workflows
    require(branch!='main','coliseum prototype requires an isolated branch')
    require(e.branch(branch)['revision']==expected_revision,'stale arena turn; reread state')
    require(attacker!=defender,'distinct opponents required')
    require(intent in ('strike','finisher'),'unregistered action or Will: needs an explicit technique contract')
    require(defense in ('guard','dodge','none'),'unknown defense')
    rule=e.get(branch,match+':rules');require(rule and rule['data']['name']==RULE and rule['data']['statement']==RULE_TEXT,'arena rules not installed')
    chars=[e.get(branch,x) for x in (attacker,defender)]
    require(all(x and x['domain']=='character' and x['data']['location']==match for x in chars),'fighters must be present in match')
    def get(i):
        rec=e.get(branch,i);require(rec is not None and rec['domain']=='resource','missing arena state: '+i)
        value=rec["data"]["quantity"]
        require(type(value) in (int,float) and 0<=value<=100 and int(value)==value,"invalid arena quantity")
        return rec
    states={x:{field:get(x+':'+field) for field in FIELDS} for x in (attacker,defender)}
    def val(x,f):return states[x][f]['data']['quantity']
    require(val(attacker,'health')>0 and val(defender,'health')>0,'incapacitated fighter; exchange closed')
    require(get(match+':distance')['data']['quantity']<=1,'target out of reach')
    cost=2 if intent=='finisher' else 1
    require(val(attacker,'stamina')>=cost,'insufficient attack stamina')
    if defense!='none':require(val(defender,'stamina')>=1,'insufficient defensive stamina')
    if defense=='dodge':require(val(defender,'mobile')==1,'restraint prevents dodge')
    if defense=='guard':require(val(defender,'guard_intact')==1,'injured guard unavailable')
    avoided=defense=='dodge' and val(defender,'reaction')>=val(attacker,'speed')
    power=val(attacker,'power')+(2 if intent=='finisher' else 0)
    damage=0 if avoided else max(0,power-(val(defender,'guard') if defense=='guard' else 0))
    health=max(0,val(defender,'health')-damage)
    ev=[{'note':'Deterministic result of opt-in coliseum prototype/1; no campaign power claims.'}];changes=[]
    def change(rec,value):changes.append(dict(op='patch',id=rec['id'],expected_version=rec['version'],data={'quantity':value},evidence=ev))
    change(states[attacker]['stamina'],val(attacker,'stamina')-cost)
    if defense!='none':change(states[defender]['stamina'],val(defender,'stamina')-1)
    change(states[defender]['health'],health)
    if damage>0 and defense=='guard':change(states[defender]['guard_intact'],0)
    outcome='incapacitated' if health==0 else 'evaded' if avoided else 'blocked' if damage==0 else 'hit'
    resolution={'feasible':True,'mechanical':True,'outcome':outcome,'magnitude':{'damage':damage},'cost':[{'holder':attacker,'stamina':cost}]+([{'holder':defender,'stamina':1}] if defense!='none' else []),'rules':[],'inputs':[{'rule':RULE,'rule_record':rule['id'],'version':rule['version']}],'judgment':{'by':'arena-prototype','rationale':'Explicit opt-in fixtures; no semantic inference or random roll'}}
    p=Workflows(e).prepare('combat',branch,request_id,attacker,f'{intent} versus {defense}: {outcome}',action_spec=resolution,changes=changes)
    return {'outcome':outcome,'damage':damage,'receipt':e.apply(p['command'])}
