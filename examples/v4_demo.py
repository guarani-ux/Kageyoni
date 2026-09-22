"""An authored, AI-disabled journey in a fresh synthetic world.

python3 -m examples.v4_demo --output NEW_DIRECTORY
No campaign characters, historical events or measured competence are implied.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from kageyoni.application import Application
from kageyoni.engine import Engine
from kageyoni.persistence.migrations import install_encounters


EVIDENCE=[{'note':'Synthetic V4 authored game parameter; never campaign canon.'}]


def record(domain,rid,**data):
    return dict(op='create',domain=domain,id=rid,data=data,status='proposed',visibility='public',evidence=EVIDENCE)


def setup(engine):
    install_encounters(engine);app=Application(engine)
    def event(request,changes,**extra):
        return engine.apply(dict(api_version=3,branch='main',request_id=request,expected_revision=engine.branch('main')['revision'],
            actor='fixture',narrative='Synthetic authored encounter setup',kind='action',changes=changes,**extra))
    engine.define_property('fixture.focus',1,'Focus','Explicit resource for the synthetic shield technique','number',['character'],{'min':0,'max':10},lifecycle='active',unit='points')
    profile=dict(character_id='traveler',label='Éloïse・旅人',canonical_name='Éloïse・旅人',existence='established',entity_kind='person',visibility='public',
        motivation={'status':'known','statement':'Find a safe way home without abandoning another traveler.'},
        communication={'status':'known','statement':'Speaks clearly; silence is also a possible choice.'},
        stats=[dict(property_id='fixture.focus',definition_version=1,status='known',value=3,unit='points',basis='Authored resource budget for this fixture.')],
        named_will={'status':'proposed','name':'The Unbroken Road','interpretation':'The bearer thinks their Will is chiefly about finding safe passage.'})
    introduction=app.genesis.introduce('main','introduce-traveler',0,profile)
    app.genesis.introduce('main','introduce-guard',engine.branch('main')['revision'],dict(character_id='guard',label='Road Warden',existence='established',entity_kind='person',visibility='public'))
    event('places',[record('location','crossroads',name='Crossroads',kind='route'),record('location','bridge',name='Old Bridge',kind='route'),
        record('location','ferry',name='River Ferry',kind='route'),record('clock','clock',name='Journey',tick=0,unit='turn'),
        record('scene','scene',name='Shared passage',location='bridge',clock='clock',phase='open',round=0),
        record('route','bridge-route',origin='crossroads',destination='bridge',access='open',duration='one turn'),
        record('route','ferry-route',origin='crossroads',destination='ferry',access='open',duration='two turns'),
        record('objective','objective',title='Leave the confrontation safely',holder='traveler',phase='active',stakes='Safe passage',success='Both leave',failure='Departure blocked'),
        record('thread','promise',question='Will the travelers keep their promised meeting?',phase='open'),
        record('ability','shield-ability',name='Sheltering Line',function='Authored defense around a willing subject')])
    engine.add_rule('fixture-permit',1,'Authored permission',[],[],True,{'kind':'contextual','outcome':True})
    engine.add_rule('fixture-shield',1,'Authored shield effect',[],[],True,{'kind':'will_patch','template':{'target_role':'target','data':{'condition':'sheltered'}}})
    cond={'id':'permit','mode':'rule','rule':{'id':'fixture-permit','version':1},'statement':'Authored permission','missing_policy':'block'}
    definition=dict(schema_version='will-contract/0.1',id='root-will',version=1,design_status='accepted',evidence=[{'source':'fixture','assertion':'Authored world rule','status':'proposed'}],
        name='Primordial Preservation',classification='primordial',nature='Preserve continuity',ancestry=[],generative_boundary='Only fixture effects',inherent_limits=['No implied mastery'],invariants=[])
    expression=dict(schema_version='will-contract/0.1',id='expression',version=1,design_status='accepted',evidence=definition['evidence'],
        definition={'id':'root-will','version':1},bearer='traveler',legacy_will_id='traveler.named-will',interpretation='The bearer calls this The Unbroken Road.',
        channels=['gesture'],stat_bindings=[],learned_techniques=[{'id':'shield-technique','version':1}],conditions=[],awakening_access='unknown',awakening_mastery='unknown',awakening_definition=None)
    cost=dict(id='focus-cost',resource=dict(property_id='fixture.focus',definition_version=1,subject_role='actor',stage='cost',contribution_id='shield-focus'),
        amount={'value':1,'unit':'points'},when='attempt',insufficient_policy='block')
    technique=dict(schema_version='will-contract/0.1',id='shield-technique',version=1,design_status='accepted',evidence=definition['evidence'],expression={'id':'expression','version':1},
        name='Sheltering Line',derivation='Authored fixture training',practice_status='demonstrated',activation='deliberate',trigger=cond,
        channels=[{'medium':'gesture','access':cond,'break_conditions':[]}],
        effects=[dict(operation='preserve',target_role='target',mechanism='Authored shield',preconditions=[],scope={'target_kinds':['person'],'range':None,'area':None,'duration':None,'unknowns':[]},
            inputs=[],resolver={'id':'fixture-shield','version':1},authority='mechanical',resistance=[],postconditions=[])],
        costs=[cost],resolution_policy={'id':'fixture-permit','version':1},termination=[])
    event('will-contracts',[record('will_definition','root-will',name=definition['name'],classification='primordial',contract=definition),
        record('will_expression','expression',definition='root-will',bearer='traveler',legacy_will='traveler.named-will',contract=expression),
        record('will_technique','shield-technique',expression='expression',ability='shield-ability',name='Sheltering Line',contract=technique)])
    def patch(rid,**data):return dict(op='patch',id=rid,data=data,evidence=EVIDENCE)
    def action(label,role,kind,payload,next_state,resolve=()):
        return dict(label=label,actor_role=role,kind=kind,payload=payload,next_state=next_state,resolve_loops=list(resolve))
    spec=dict(title='A passage and a promise',roles=['traveler','warden'],visibility='public',scene_id='scene',max_steps=20,initial_state='route',
        loops=[dict(id='dialogue',kind='offer',required=True,depends_on=[],continuable=False),
               dict(id='ability',kind='defense',required=True,depends_on=[],continuable=False),
               dict(id='consequence',kind='departure',required=True,depends_on=['dialogue','ability'],continuable=False),
               dict(id='promise',kind='relationship',required=True,depends_on=[],continuable=True)],
        states={name:dict(phase='active',outcome='unresolved',actions=acts) for name,acts in {
            'route':['bridge','ferry'],'offer':['offer'],'defend':['shield'],'reply':['accept','refuse'],'clarify':['judge'],'settle':['depart']}.items()},
        actions={})
    spec['states']['closed']=dict(phase='completed',outcome='achieved',actions=[])
    spec['actions']['bridge']=action('Take the bridge','traveler','event',{'changes':[patch('traveler',location='bridge'),patch('clock',tick=1),patch('scene',phase='active')]},'offer')
    spec['actions']['ferry']=action('Take the ferry','traveler','event',{'changes':[patch('traveler',location='ferry'),patch('clock',tick=2),patch('scene',phase='active')]},'offer')
    spec['actions']['offer']=action('Offer safe withdrawal','traveler','dialogue',{'text':'We can both leave safely. Let me shelter the road while you decide.','act':'offer','mode':'spoken','listener_roles':['warden']},'defend')
    attempt=dict(expression={'id':'expression','version':1},technique={'id':'shield-technique','version':1},intent='Shelter the road warden while the offer remains open.',
        targets=[{'$role':'warden'}],randomness={'mode':'d20','roll_id':{'$encounter':'shield-roll'},'difficulty':1,'modifier':0},
        outcome_bindings=[{'outcome':'success','effect_indexes':[0],'cost_ids':['focus-cost']},{'outcome':'failure','effect_indexes':[],'cost_ids':['focus-cost']}],judgments=[])
    spec['actions']['shield']=action('Use Sheltering Line','traveler','will',attempt,'reply',['ability'])
    spec['actions']['accept']=action('Accept the offer','warden','dialogue',{'text':'Agreed. I will leave the road clear. We still have a meeting to keep.','act':'accept','mode':'spoken','listener_roles':['traveler']},'settle',['dialogue'])
    spec['actions']['refuse']=action('Ask for different terms','warden','dialogue',{'text':'I need the terms clarified before I agree.','act':'counteroffer','mode':'spoken','listener_roles':['traveler']},'clarify',['dialogue'])
    spec['actions']['judge']=action('Clarify the terms','traveler','judgment',{'question':'Which authored continuation follows this ambiguous counteroffer?',
        'choices':[{'id':'withdraw','label':'Withdraw together without claiming trust','next_state':'settle'}],'unknowns':['Whether trust improved; the engine does not infer it.']},'settle')
    spec['actions']['depart']=action('Settle the departure','traveler','event',{'changes':[patch('objective',phase='completed'),patch('scene',phase='closed')]},'closed',['consequence'])
    spec['actions']['depart']['detach_loops']=[{'loop_id':'promise','record_id':'promise'}]
    app.encounters.define('passage',1,spec,'define-passage')
    return dict(app=app,profile=profile,spec=spec,participants={'traveler':'traveler','warden':'guard'},introduction=introduction)


def run(destination):
    root=Path(destination);root.mkdir(parents=True,exist_ok=False)
    engine=Engine(root/'synthetic.sqlite');receipts=[]
    try:
        fixture=setup(engine);world=fixture['app'].encounters
        world.start('main','passage',1,'journey','start-journey',engine.branch('main')['revision'],fixture['participants'])
        for aid in ('bridge','offer','shield'):
            receipts.append(world.act('main','journey',aid,'play-'+aid,engine.branch('main')['revision']))
        interrupted=world.inspect('main','journey')
        engine.close();engine=Engine(root/'synthetic.sqlite');world=Application(engine).encounters
        assert world.inspect('main','journey')==interrupted
        for aid in ('accept','depart'):
            receipts.append(world.act('main','journey',aid,'play-'+aid,engine.branch('main')['revision']))
        done=world.inspect('main','journey');props=engine.properties('main',entity_id='traveler')
        focus=next(p['value'] for p in props if p['property_id']=='fixture.focus')
        assert done['phase']=='completed' and done['next_actions']==[] and focus==2
        assert engine.get('main','guard')['data']['condition']=='sheltered'
        assert engine.get('main','objective')['data']['phase']=='completed'
        assert engine.get('main','promise')['data']['phase']=='open'
        replay=world.act('main','journey','shield','play-shield',receipts[1]['world_revision'])
        assert replay['replayed'] and next(p['value'] for p in engine.properties('main',entity_id='traveler') if p['property_id']=='fixture.focus')==2
        report=dict(synthetic=True,ai_calls=0,interrupted=interrupted,final=done,focus_remaining=focus,receipts=receipts,verification=engine.verify(),
                    boundary='Authored choices and world rules, not autonomous character judgment or inferred trust.')
        (root/'encounter-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        (root/'definition.json').write_text(json.dumps(fixture['spec'],ensure_ascii=False,indent=2)+'\n')
        return report
    finally:engine.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();report=run(args.output)
    print(json.dumps({'phase':report['final']['phase'],'ai_calls':0,'focus_remaining':report['focus_remaining'],'verified':report['verification']['ok']},indent=2))
