"""Reproducible NONCANONICAL personality fixture; no API calls or subscriptions.

Run: python -m examples.personality_journey --db build/personality-fixture.sqlite
Refuses to overwrite an existing campaign. Numbers are illustrative design weights.
"""
import argparse
import copy
import json
from pathlib import Path
from kageyoni.engine import Engine
from kageyoni.workflows import Workflows
from kageyoni import personality as p

NOTE=[{'note':'NONCANONICAL personality integration fixture. Authored design assumptions, not psychological findings.'}]

def create(domain, rid, **data):
    return dict(op='create',domain=domain,id=rid,data=data,status='proposed',visibility='public',evidence=NOTE)

def private(change, actor):
    return dict(change, visibility='restricted',audience=[actor])

def change(e,rid,branch='main',**data):
    return dict(op='patch',id=rid,expected_version=e.get(branch,rid)['version'],data=data,evidence=NOTE)

def event(e,changes,branch='main',**extra):
    rev=e.branch(branch)['revision']
    return e.apply(dict(api_version=3,branch=branch,expected_revision=rev,request_id='fixture:'+str(rev),kind='action',actor='gm',narrative='NONCANONICAL fixture event',changes=changes,**extra))

def aspect(rid,actor,section,kind,statement,**extra):
    return private(create('character_aspect',rid,character=actor,section=section,kind=kind,value_status='known',statement=statement,phase='active',change_basis='established',**extra),actor)

def policy():
    def influence(rid,option,factor,**when):
        return dict(id=rid,option=option,factor=factor,when=[when],rationale='Noncanonical authored association: '+rid)
    return dict(kind='personality',schema_version='personality-policy/1',design_status='active',meaning='Fixture approach preferences across scenes; never success probabilities.',scopes=sorted(p.SCOPES),
        options=[dict(id=i,label=l,weight=1,guidance=g,tones=t) for i,l,g,t in [
            ('inspect','Inspect first','Seek concrete warning signs before committing.',['suspense','inquiry']),
            ('inquire','Ask and learn','Invite another perspective; ask what is still unknown.',['inquiry','purpose']),
            ('joke','Use gentle humor','Offer levity when appropriate without erasing the danger.',['lightheartedness']),
            ('reassure','Offer reassurance','Acknowledge another person’s concern.',['connection']),
            ('pause','Pause and reflect','Name uncertainty or rest before acting.',['introspection'])]],
        influences=[
            influence('type-intuition','inquire',1.5,source='mbti',axis='SN',value='N'),
            influence('shared-will','inquire',1.2,source='will',definition='will.inquiry',version=1),
            influence('fear','inspect',4,source='aspect',kind='emotion',value='fear'),
            influence('curiosity','inquire',2,source='aspect',kind='emotion',value='curiosity'),
            influence('safe-company','joke',6,source='aspect',kind='comfort',value='safe'),
            influence('trust','reassure',2,source='relationship',kind='companion',field='feeling',value='trust'),
            influence('learned-habit','inquire',3,source='aspect',kind='habit',value='ask_before_acting'),
            influence('fatigue','pause',2,source='aspect',kind='fatigue',value='tired'),
            influence('storm','inspect',1.5,source='perceived',domain='environment',field='feature',value='storm')])

def setup(e):
    evidence=[dict(source='fixture',assertion='NONCANONICAL',status='proposed')]
    definition=dict(schema_version='will-contract/0.1',id='will.inquiry',version=1,design_status='accepted',evidence=evidence,name='Fixture Will of Inquiry',classification='independent',nature='Pursuit of understanding',ancestry=[],generative_boundary='Fixture only',inherent_limits=['No automatic truth or mastery'],invariants=[])
    rows=[create('location','shore',name='Fixture Riverbank',kind='region'),create('location','camp',name='Fixture Camp',kind='region'),create('clock','clock',name='Fixture time',tick=0,unit='hour'),
          create('character','mira',name='Mira (fixture)',entity_kind='person',location='shore',voice='Wry questions, concrete images',motives='Understand without endangering friends'),
          create('character','oren',name='Oren (fixture)',entity_kind='person',location='shore',voice='Patient questions, tentative suggestions',motives='Learn how the crossing works'),
          create('character','guard',name='Guard (fixture)',entity_kind='person',location='camp'),
          create('environment','water',location='shore',kind='hazard',feature='rising water',rule='Crossing requires a separate feasibility assessment'),
          create('item','bridge',name='Fixture bridge',condition='damaged'),
          create('route','route',origin='shore',destination='camp',access='blocked'),
          create('scene','scene',name='An uncertain crossing',location='shore',clock='clock',phase='active',round=0,context='A damaged bridge and a chance to ask for help'),
          create('resource','stamina',holder='mira',name='Stamina',quantity=5,unit='effort'),
          create('ability','observation',name='Observe structure',function='Look for visible structural damage'),
          create('capability','mira.observe',character='mira',ability='observation',mastery='ordinary competence'),
          create('will_definition','will.inquiry',name='Fixture Will of Inquiry',classification='independent',contract=definition),
          aspect('mira.fear','mira','condition','emotion','fear',clock='clock',valid_from=0,valid_until=2),
          aspect('mira.joy','mira','condition','emotion','joy'),
          aspect('mira.comfort','mira','condition','comfort','uneasy',related_character='oren'),
          aspect('mira.appraisal','mira','perspective','appraisal','The crossing reminds me of a loss'),
          aspect('mira.principle','mira','interiority','principle','Learn without treating people as tools'),
          aspect('oren.curiosity','oren','condition','emotion','curiosity'),
          aspect('oren.boundary','oren','interiority','boundary','No coerced demonstrations'),
          private(create('relationship','mira.oren',subject='mira',object='oren',kind='companion',feeling='uncertain'), 'mira'),
          private(create('knowledge','mira.rumor',holder='mira',assertion='Someone said the ferry returns at dusk',attitude='believes',basis='A traveler’s report'), 'mira'),
          private(create('knowledge','guard.secret',holder='guard',assertion='SECRET_FACTION_ORDER',attitude='knows'),'guard')]
    for actor in ('mira','oren'):
        rid=actor+'.will'
        contract=dict(schema_version='will-contract/0.1',id=rid,version=1,design_status='accepted',evidence=evidence,definition=dict(id='will.inquiry',version=1),bearer=actor,legacy_will_id=None,interpretation='Individual expression; no automatic ability',channels=['voice'],stat_bindings=[],learned_techniques=[],conditions=[],awakening_access='latent',awakening_mastery='unknown',awakening_definition=None)
        rows.append(create('will_expression',rid,definition='will.inquiry',bearer=actor,contract=contract))
    event(e,rows)
    e.add_rule('fixture.personality',1,'Fixture contextual approaches',[],[],True,policy())
    event(e,[private(create('personality_profile',actor+'.profile',character=actor,framework='mbti-inspired',type_code='INFP',interpretation='accepted',note='Same authored fixture interpretation for comparison; no diagnostic claim.',policy_id='fixture.personality',policy_version=1),actor) for actor in ('mira','oren')])

def spec(e,rid='conversation',actor='mira',branch='main',**extra):
    out=dict(id=rid,expected_revision=e.branch(branch)['revision'],actor=actor,intent='Ask for help understanding the crossing',method='A candid question with gentle humor',stakes='How this companion exchange shapes the next choice',modules=['social'],agency_state='voluntary',adjudication=dict(by='fixture-gm',rationale='An ordinary exchange; no compulsory roll. Reactions are explicitly authored consequences.',basis=[actor]),uncertainty={'mode':'none'},outcomes={'success':{},'failure':{}})
    out.update(extra); return out

def weights(e,actor='mira',branch='main',domain='dialogue',version=1):
    out=p.evaluate(e,'fixture.personality',version,branch,actor,dict(domain=domain,interlocutors=['oren'] if actor=='mira' else ['mira'],scene='scene'))
    return {o['id']:o['weight'] for o in out['output']['options']}

def run(e):
    setup(e); w=Workflows(e)
    before=weights(e); comparison=weights(e,'oren')
    e.fork('main','without-conversation',e.branch('main')['revision'])
    turn=dict(id='mira.turn1',listeners=['oren'],scene='scene',act='inquire_with_humor',mode='spoken',text='Could you show me where it holds? I would prefer to learn without becoming part of the river.',visibility='public')
    s=spec(e,personality=dict(selected='inquire',rationale='She chooses learning despite fear.'))
    updates=[change(e,'mira.comfort',statement='safe',change_basis='voluntary'),change(e,'mira.oren',feeling='trust'),aspect('mira.habit','mira','portrayal','habit','ask_before_acting')]
    s['outcomes']['success']['changes']=updates
    proposal=w.dialogue_propose(branch='main',spec=s,turn=turn,claims=[],review=dict(by='fixture-gm',rationale='A question and figurative humor; does not assert knowledge of a safe route. The relationship change is this fixture’s explicit adjudication.'))
    receipt=w.decision_commit(branch='main',proposal_id=s['id'],actor='mira',accept=True,narrative='NONCANONICAL: Mira asks; Oren responds patiently. She feels safer with him.')
    after=weights(e); unchanged=weights(e,branch='without-conversation')
    learning=spec(e,'practice',modules=['training'],personality=dict(domain='training',interlocutors=['oren'],selected='inquire',rationale='Practice through questions and attention.'),time={'clock':'clock','duration':1},costs=[dict(resource='stamina',amount=1,unit='effort')])
    development=dict(schema_version='will-contract/0.1',id='mira.development',version=1,design_status='proposed',evidence=[dict(source='fixture',assertion='NONCANONICAL',status='proposed')],expression=dict(id='mira.will',version=1),dimension='understanding',phase='attempted',claim='Begins reflecting on how inquiry shapes her expression',supporting_events=[receipt['event_id']],limitations=['No new mastery or technique granted'],mechanical_unlocks=[])
    learning['outcomes']['success']['changes']=[create('progression','mira.practice',character='mira',ability='observation',practice='Look for damage with Oren',experience='The conversation made asking easier',cost='One hour and one effort',phase='attempted'),create('will_development','mira.development',expression='mira.will',progression='mira.practice',contract=development)]
    w.decision_propose(branch='main',spec=learning)
    w.decision_commit(branch='main',proposal_id='practice',actor='mira',accept=True,narrative='NONCANONICAL: A shared hour of practice; no mastery assumed.')
    # Save an ordinary future exchange for extraction/reopening verification.
    w.decision_propose(branch='main',spec=spec(e,'resume-fixture',personality={'interlocutors':['oren']}))
    replay=e.replay('main')
    return dict(noncanonical=True,before=before,same_type_same_will_other_person=comparison,after=after,branch_without_exchange=unchanged,
                speech=e.get('main','mira.turn1')['data']['text'],clock=e.get('main','clock')['data']['tick'],stamina=e.get('main','stamina')['data']['quantity'],
                mastery=e.get('main','mira.observe')['data']['mastery'],pending_decision='resume-fixture',replay={'complete':replay['complete'],'records_match':replay['records']==e.state('main')},verify=e.verify())

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--db',default='build/personality-fixture.sqlite'); parser.add_argument('--report')
    args=parser.parse_args(); path=Path(args.db)
    if path.exists(): raise SystemExit('Refusing to overwrite existing campaign; use a new fixture path.')
    engine=Engine(path)
    try:
        report=json.dumps(run(engine),ensure_ascii=False,indent=2)
        if args.report: Path(args.report).write_text(report+'\n')
        print(report)
    finally: engine.close()
