"""NONCANONICAL connected writing fixture. Run only against a new database."""
import argparse,json
from pathlib import Path
from kageyoni.engine import Engine
from kageyoni import writing as w,personality as p,decisions as d
from examples.personality_journey import setup,spec,event,change

def review():
 return dict(by='fixture-gm',rationale='Checked source fidelity, distinct voice, private perspective, agency and pacing. This is an authored example, not proof of literary quality.',checks={k:True for k in w.CONTRACT['review']})

def run(e):
 setup(e)
 rhetoric=dict(purpose='Offer companionship',strategy='A wry question',subtext='I would rather you were not alone',listener_assumptions=[dict(listener='oren',interpretation='He may welcome company',basis=[])])
 p.dialogue_propose(e,'main',spec(e),dict(id='invitation',listeners=['oren'],act='invite',text='Want company for the third inspection?',mode='spoken',visibility='public'),[],dict(by='fixture-gm',rationale='No uncertain execution; a gentle invitation.'),rhetoric=rhetoric)
 d.commit(e,'main','conversation','mira',True,'NONCANONICAL: Mira offers company.')
 e.fork('main','without-interpretation',e.branch('main')['revision'])
 w.receive(e,'main','oren-reading',e.branch('main')['revision'],'oren','invitation','Oren wonders whether she is mocking his caution','tentative','He considers asking what she means',review())
 before=w.brief(e,'main','dialogue','mira','Let Oren seek clarification without dictating Mira’s answer',perspective='oren',scene='scene',focus=['water'])
 alternate=w.brief(e,'without-interpretation','dialogue','mira','The exchange remains unexamined',perspective='oren',scene='scene',focus=['water'])
 reply=spec(e,'clarify',actor='oren',method='Ask rather than assume')
 p.dialogue_propose(e,'main',reply,dict(id='clarification',listeners=['mira'],act='clarify',text='Is that an offer, or a count of my mistakes?',mode='spoken',visibility='public'),[],dict(by='fixture-gm',rationale='A question makes uncertainty explicit; it does not assert Mira’s motive.'),rhetoric=dict(purpose='Understand the invitation',strategy='Ask directly with dry humor',subtext='I am unsure whether I am being judged',listener_assumptions=[dict(listener='mira',interpretation='She can clarify her intent',basis=[])]))
 d.commit(e,'main','clarify','oren',True,'NONCANONICAL: Oren asks what Mira means.')
 b=w.brief(e,'main','narration','mira','Present the resolved exchange and return the choice',scene='scene',focus=['clarification'])
 prose='Oren: “Is that an offer, or a count of my mistakes?”\n\nThe question leaves room for your answer.'
 w.publish(e,'main','exchange',b['revision'],b['request'],b['brief_hash'],prose,[dict(status='fact',statement='Oren asked for clarification',basis=[dict(id='clarification',version=1)])],review())
 storm=event(e,[change(e,'water',feature='storm-driven water')])
 history=w.brief(e,'main','history','mira','Keep the changing river separate from interpretations of the exchange',focus=['water'],event_ids=[storm['event_id']])
 history_text='The recorded conditions changed to storm-driven water. Oren’s suspicion remains an interpretation; Mira’s invitation has not established trust or compelled a crossing.'
 w.publish(e,'main','history',history['revision'],history['request'],history['brief_hash'],history_text,[dict(status='belief',statement='The fixture record describes changed water',basis=[dict(id='water',version=2)])],review())
 resume=w.brief(e,'main','recap','mira','Recall the unresolved question and leave the next decision open',focus=['clarification','water'])
 request=dict(branch='main',request_id='resume-writing',expected_revision=resume['revision'],brief_spec=resume['request'],brief_hash=resume['brief_hash'],text='Oren’s question is still yours to answer. The crossing remains unresolved.',claims=[],review=review())
 return {'noncanonical':True,'main_receptions':len(before['character_context']['receptions']),'alternate_receptions':len(alternate['character_context']['receptions']),'presented_text':prose,'history_text':history_text,'clock':e.get('main','clock')['data']['tick'],'trust':e.get('main','mira.oren')['data']['feeling'],'replay_matches':e.replay('main')['records']==e.state('main'),'verify':e.verify()},request

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('--report',required=True);parser.add_argument('--resume',required=True);args=parser.parse_args()
 if Path(args.db).exists():raise SystemExit('Use a new noncanonical fixture path; refusing overwrite.')
 e=Engine(args.db)
 try:
  result,resume=run(e);Path(args.report).write_text(json.dumps(result,indent=2)+'\n');Path(args.resume).write_text(json.dumps(resume,indent=2)+'\n');print(json.dumps(result,indent=2))
 finally:e.close()
