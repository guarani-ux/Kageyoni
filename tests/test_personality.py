"""Integrated NONCANONICAL behavior and failure cases, personality interface 1."""
import copy
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from kageyoni.engine import Engine, Rejected
from kageyoni.workflows import Workflows
from kageyoni import personality as p, decisions as d
from examples.personality_journey import setup, policy, event, create, change, aspect, spec, weights, private, run

ROOT=Path(__file__).resolve().parents[1]

class PersonalityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'fixture.sqlite'
        self.e=Engine(self.path); setup(self.e); self.w=Workflows(self.e)

    def tearDown(self):
        self.e.close(); self.tmp.cleanup()

    def evaluate(self,actor='mira',**context):
        return p.evaluate(self.e,'fixture.personality',1,'main',actor,dict(domain='dialogue',interlocutors=['oren'] if actor=='mira' else ['mira'],**context))

    def dialogue(self,claims=None,**overrides):
        turn=dict(id='speech',listeners=['oren'],act='ask',text='Could you help me understand?',mode='spoken',visibility='public',scene='scene')
        turn.update(overrides)
        return self.w.dialogue_propose(branch='main',spec=spec(self.e),turn=turn,claims=claims or [],review=dict(by='fixture-gm',rationale='Reviewed wording against speaker knowledge and intent.'))

    def commit(self,rid='conversation'):
        return d.commit(self.e,'main',rid,'mira',True,'NONCANONICAL scene')

    def test_same_type_and_will_different_people_no_fixed_behavior(self):
        a=weights(self.e); b=weights(self.e,'oren')
        self.assertEqual(max(a,key=a.get),'inspect'); self.assertEqual(max(b,key=b.get),'inquire')
        self.assertAlmostEqual(a['inquire'],1.8); self.assertAlmostEqual(b['inquire'],3.6)
        before=self.e.state(); self.evaluate(); self.assertEqual(before,self.e.state())
        self.assertEqual(self.e.get('main','mira.will')['data']['contract']['learned_techniques'],[])

    def test_mixed_feelings_context_expiry_and_relationship_specific_comfort(self):
        brief=p.brief(self.e,'main','mira',interlocutors=['oren'])
        self.assertEqual({r['data']['statement'] for r in brief['aspects'] if r['data']['kind']=='emotion'},{'fear','joy'})
        event(self.e,[change(self.e,'mira.comfort',statement='safe')])
        self.assertEqual(weights(self.e)['joke'],6)
        stranger=p.evaluate(self.e,'fixture.personality',1,'main','mira',{'domain':'dialogue','interlocutors':['guard']})
        self.assertEqual(next(o['weight'] for o in stranger['output']['options'] if o['id']=='joke'),1)
        self.e.advance_simulation('main','clock',2,'fixture-time','gm','NONCANONICAL time',expected_revision=self.e.branch('main')['revision'])
        self.assertEqual(weights(self.e)['inspect'],1)
        self.assertEqual(self.e.get('main','mira.fear')['data']['statement'],'fear')
        self.assertEqual(self.e.get('main','mira.comfort')['data']['phase'],'active')

    def test_unknown_and_provisional_type_are_not_neutral_defaults(self):
        event(self.e,[change(self.e,'mira.profile',interpretation='proposed'),change(self.e,'mira.fear',value_status='unknown',statement=None)])
        result=self.evaluate(); self.assertIn('type-intuition',result['output']['unresolved']); self.assertIn('fear',result['output']['unresolved'])
        self.assertAlmostEqual(weights(self.e)['inquire'],1.2)
        event(self.e,[change(self.e,'mira.fear',value_status='absent')])
        self.assertNotIn('fear',self.evaluate()['output']['unresolved'])
        event(self.e,[change(self.e,'mira.profile',interpretation='unknown',type_code=None)])
        self.assertIsNone(self.e.get('main','mira.profile')['data']['type_code'])

    def test_all_activity_modules_receive_model_without_roll_buffs(self):
        for module in ('combat','travel','discovery','training','social','downtime'):
            proposal=d.propose(self.e,'main',spec(self.e,module,modules=[module],personality={'selected':'joke','rationale':'A deliberate atypical response.'},uncertainty={'mode':'d20','difficulty':25}))
            self.assertEqual(proposal['assessment']['modifier'],0)
            self.assertEqual(proposal['assessment']['personality']['selection']['id'],'joke')
            self.assertEqual(proposal['status'],'available')
        with patch('kageyoni.decisions.secrets.randbelow',return_value=19):
            receipt=self.commit('combat')
        resolution=json.loads(self.e.db.execute('SELECT command_json FROM events WHERE id=?',(receipt['event_id'],)).fetchone()[0])['resolution']
        self.assertEqual(resolution['roll_result'],20); self.assertEqual(resolution['outcome'],'failure')
        with self.assertRaisesRegex(Rejected,'stale decision'): self.commit('training')

    def test_mixed_scope_influence_is_applied_once_without_extra_cost_or_time(self):
        scoped=policy(); scoped['influences'][2]['scopes']=['combat','relationship']
        self.e.add_rule('scoped',1,'Fixture combat/social policy',[],[],True,scoped)
        result=d.propose(self.e,'main',spec(self.e,modules=['combat','social'],personality={'policy':{'id':'scoped','version':1}},time={'clock':'clock','duration':1},costs=[dict(resource='stamina',amount=1,unit='effort')]))
        model=result['assessment']['personality']['evaluation']
        self.assertEqual(set(model['inputs']['domains']),{'combat','relationship'})
        self.assertEqual(next(o['weight'] for o in model['output']['options'] if o['id']=='inspect'),4)
        self.assertEqual(sum(x['id']=='fear' for x in model['output']['influences']),1)
        self.commit()
        self.assertEqual(self.e.get('main','clock')['data']['tick'],1)
        self.assertEqual(self.e.get('main','stamina')['data']['quantity'],4)

    def test_independent_response_uses_own_mind_and_can_refuse(self):
        response=dict(actor='oren',decision='refuse',judgment=dict(by='fixture-gm',rationale='Oren maintains his boundary.',basis=['oren.boundary']))
        proposal=d.propose(self.e,'main',spec(self.e,responses=[response]))
        self.assertEqual(proposal['status'],'blocked')
        self.assertEqual(proposal['assessment']['response_contexts'][0]['actor'],'oren')
        with self.assertRaises(Rejected): self.commit()
        response['judgment']['basis']=['mira.rumor']
        with self.assertRaisesRegex(Rejected,'unavailable knowledge'): d.propose(self.e,'main',spec(self.e,'omniscient',responses=[response]))

    def test_public_fact_elsewhere_does_not_enter_actor_knowledge(self):
        event(self.e,[create('environment','distant-storm',location='camp',kind='weather',feature='storm')])
        self.assertNotIn('distant-storm',json.dumps(p.brief(self.e,'main','mira')))
        self.assertEqual(weights(self.e)['inspect'],4)
        event(self.e,[create('environment','local-storm',location='shore',kind='weather',feature='storm')])
        self.assertEqual(weights(self.e)['inspect'],6)

    def test_dialogue_grounding_visibility_and_hearing_not_belief(self):
        claim=dict(mode='belief',assertion='The ferry may return at dusk',basis=[dict(kind='record',id='mira.rumor',version=1)])
        self.dialogue([claim],text='I heard the ferry may return at dusk.')
        receipt=self.commit()
        public=json.dumps(self.e.context('main',viewer='oren'))
        self.assertNotIn('mira.rumor',public); self.assertNotIn('SECRET_FACTION_ORDER',public)
        self.assertNotIn('The crossing reminds me of a loss',public)
        self.assertIn('I heard the ferry may return at dusk.',public)
        heard=[o for o in self.e.observations('main',viewer='oren') if o['observer_id']=='oren']
        self.assertEqual(len(heard),1); self.assertEqual(heard[0]['certainty'],'heard_utterance')
        self.assertFalse(any(r['domain']=='knowledge' and r['data']['holder']=='oren' for r in self.e.state()))
        self.assertEqual(self.e.get('main','mira.oren')['data']['feeling'],'uncertain')
        stored=json.loads(self.e.db.execute('SELECT command_json FROM events WHERE id=?',(receipt['event_id'],)).fetchone()[0])
        self.assertEqual(stored['judgment']['dialogue_grounding']['claims'][0]['mode'],'belief')
        self.assertNotIn('dialogue_grounding',json.dumps(d.inspect(self.e,'main','conversation',viewer='mira')))

    def test_unknown_claim_hidden_source_and_wrong_epistemic_mode_rejected(self):
        with self.assertRaisesRegex(Rejected,'co-location'): self.dialogue(listeners=['guard'])
        memory=aspect('mira.unknown-memory','mira','perspective','memory','temporary')
        memory['data'].update(value_status='unknown',statement=None)
        event(self.e,[memory])
        with self.assertRaisesRegex(Rejected,'unresolved memory'):
            self.dialogue([dict(mode='belief',assertion='I remember a route',basis=[dict(kind='record',id='mira.unknown-memory',version=1)])])
        for claim in [dict(mode='assertion',assertion='A claim',basis=[]),dict(mode='assertion',assertion='A claim',basis=[dict(kind='record',id='guard.secret',version=1)]),dict(mode='assertion',assertion='Ferry returns',basis=[dict(kind='record',id='mira.rumor',version=1)])]:
            before=self.e.branch('main')['revision']
            with self.assertRaises(Rejected): self.dialogue([claim])
            self.assertEqual(before,self.e.branch('main')['revision']); self.assertIsNone(self.e.get('main','speech'))
        self.dialogue([dict(mode='hypothesis',assertion='Maybe there is another crossing',basis=[])])
        self.commit()

    def test_invalid_records_policies_and_references_leave_no_partial_updates(self):
        changes=[change(self.e,'mira.profile',type_code='XYZ'),change(self.e,'mira.profile',type_code=8),change(self.e,'mira.profile',character='shore'),change(self.e,'mira.profile',policy_id='missing'),change(self.e,'mira.fear',valid_from=4,valid_until=3),create('personality_profile','duplicate',character='mira',framework='mbti-inspired',type_code='INFP',interpretation='accepted',note='duplicate'),create('dialogue_turn','bad-listener',speaker='mira',listeners=['shore'],act='ask',text='Hi',mode='spoken')]
        before=self.e.state()
        for bad in changes:
            with self.assertRaises((Rejected,sqlite3.Error)): event(self.e,[change(self.e,'mira',condition='changed'),bad])
            self.assertEqual(before,self.e.state())
        variants=[]
        bad=policy(); bad['influences'].append(copy.deepcopy(bad['influences'][0])); variants.append(bad)
        bad=policy(); new=copy.deepcopy(bad['influences'][0]); new['id']='same-source-new-id'; bad['influences'].append(new); variants.append(bad)
        bad=policy(); bad['influences'][0]['factor']=-1; variants.append(bad)
        bad=policy(); bad['influences'][1]['when'][0]['definition']='missing'; variants.append(bad)
        for bad in variants:
            with self.assertRaises(Rejected): self.e.add_rule('bad',1,'Invalid',[],[],True,bad)
            self.assertIsNone(self.e.db.execute("SELECT 1 FROM rule_definitions WHERE rule_id='bad'").fetchone())

    def test_property_input_units_lifecycle_applicability_and_dependencies(self):
        self.e.define_property('fixture.fatigue',1,'Fixture fatigue','Authored ordinal for one fixture','integer',['character'],{'min':0,'max':4},'active',unit='level')
        rule=policy(); rule['influences'].append(dict(id='measured-fatigue',option='pause',factor=3,when=[dict(source='property',id='fixture.fatigue',version=1,unit='level',operator='>=',value=2)],rationale='Fixture fatigue changes preferred approach, not skill.'))
        with self.assertRaises(Rejected): self.e.add_rule('fatigue-policy',1,'Missing declarations',[],[],True,rule)
        invalid=copy.deepcopy(rule); invalid['influences'][-1]['when'][0]['unit']='metre'
        with self.assertRaises(Rejected): self.e.add_rule('fatigue-policy',1,'Wrong units',['fixture.fatigue'],[],True,invalid,[('fixture.fatigue',1,'reads')])
        with self.assertRaises(Rejected): self.e.set_property('main','bridge','fixture.fatigue',1,'known',2,unit='level')
        with self.assertRaises(Rejected): self.e.set_property('main','mira','fixture.fatigue',1,'known','two',unit='level')
        self.e.add_rule('fatigue-policy',1,'Fatigue',['fixture.fatigue'],[],True,rule,[('fixture.fatigue',1,'reads')])
        self.assertIn('measured-fatigue',p.evaluate(self.e,'fatigue-policy',1,'main','mira')['output']['unresolved'])
        self.e.set_property('main','mira','fixture.fatigue',1,'known',2,unit='level')
        self.assertEqual(next(o['weight'] for o in p.evaluate(self.e,'fatigue-policy',1,'main','mira')['output']['options'] if o['id']=='pause'),3)
        proposal=d.propose(self.e,'main',spec(self.e,personality={'policy':{'id':'fatigue-policy','version':1}}))
        self.commit()
        self.assertIn('fatigue-policy',json.dumps(self.e.impact('property','fixture.fatigue','1')))
        self.assertIn('event_id',json.dumps(self.e.impact('rule','fatigue-policy','1')))
        self.assertIn('fixture.personality',json.dumps(self.e.impact('domain','character_aspect','1')))
        with self.assertRaisesRegex(Rejected,'depend'): self.e.retire_property('fixture.fatigue',1,'Unsafe removal')

    def test_incompatible_interface_before_mutation(self):
        before=self.e.state()
        with self.assertRaisesRegex(Rejected,'interface'): self.w.personality_record(interface_version='99',branch='main',request_id='bad',expected_revision=self.e.branch('main')['revision'],actor='gm',narrative='bad',changes=[change(self.e,'mira.fear',statement='anger')])
        self.assertEqual(before,self.e.state())

    def test_interrupted_commit_keeps_roll_and_atomic_speech(self):
        turn=dict(id='speech',listeners=['oren'],act='ask',text='Will you help?',mode='spoken',visibility='public')
        self.w.dialogue_propose(branch='main',spec=spec(self.e,uncertainty={'mode':'d20','difficulty':8},costs=[dict(resource='stamina',amount=1,unit='effort')]),turn=turn,claims=[],review={'by':'fixture-gm','rationale':'Review'})
        with patch('kageyoni.decisions.secrets.randbelow',return_value=4),patch.object(self.e,'apply',side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError): self.commit()
        self.assertEqual(self.e.get('main','stamina')['data']['quantity'],5); self.assertIsNone(self.e.get('main','speech'))
        self.e.close(); self.e=Engine(self.path)
        with patch('kageyoni.decisions.secrets.randbelow',side_effect=AssertionError('reroll')):
            receipt=self.commit(); again=self.commit()
        self.assertTrue(again['replayed']); self.assertEqual(receipt['event_id'],again['event_id'])
        self.assertEqual(self.e.get('main','stamina')['data']['quantity'],4)
        self.assertEqual(len(self.e.observations('main')),1)
        self.assertEqual(self.e.db.execute('SELECT roll FROM decision_proposals').fetchone()[0],5)

    def test_stale_personality_changes_and_concurrent_session(self):
        d.propose(self.e,'main',spec(self.e))
        second=Engine(self.path)
        try:
            event(second,[change(second,'mira.fear',statement='relief')])
            with self.assertRaisesRegex(Rejected,'stale decision'): self.commit()
        finally: second.close()
        self.assertIsNone(self.e.db.execute('SELECT roll FROM decision_proposals').fetchone()[0])

    def test_first_branch_decision_can_change_an_inherited_personality_input(self):
        self.e.fork('main','alternate',self.e.branch('main')['revision'])
        s=spec(self.e,'branch-growth',branch='alternate')
        s['outcomes']['success']['changes']=[change(self.e,'mira.fear',branch='alternate',phase='ended')]
        d.propose(self.e,'alternate',s)
        d.commit(self.e,'alternate','branch-growth','mira',True,'NONCANONICAL branch growth')
        self.assertEqual(self.e.get('main','mira.fear')['data']['phase'],'active')
        self.assertEqual(self.e.get('alternate','mira.fear')['data']['phase'],'ended')
        self.assertEqual(self.e.replay('alternate')['records'],self.e.state('alternate'))

    def test_hidden_listener_ids_and_private_appraisals_do_not_escape_context(self):
        hidden=change(self.e,'guard',location='shore'); hidden['visibility']='gm'
        event(self.e,[hidden])
        self.dialogue(listeners=['oren','guard'])
        self.commit()
        view=self.e.context('main',viewer='oren')
        speech=next(r for r in view['records'] if r['id']=='speech')
        self.assertEqual(speech['data']['listeners'],['oren'])
        self.assertNotIn('mira.appraisal',json.dumps(p.brief(self.e,'main','mira',viewer='oren')))
        result=subprocess.run([sys.executable,'-m','kageyoni','--db',str(self.path),'personality-evaluate','--viewer','oren','--input','-'],input=json.dumps(dict(rule_id='fixture.personality',version=1,character_id='mira')),cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,2); self.assertNotIn('SECRET_FACTION_ORDER',result.stderr)

    def test_branches_snapshots_replay_and_rule_evolution_preserve_old_explanation(self):
        self.dialogue(); receipt=self.commit()
        before=self.e.db.execute('SELECT command_json FROM events WHERE id=?',(receipt['event_id'],)).fetchone()[0]
        self.e.fork('main','alternate',self.e.branch('main')['revision']); snap=self.e.register_snapshot('main')
        policy2=policy(); policy2['influences'][2]['factor']=2
        self.e.add_rule('fixture.personality',2,'Revised fixture interpretation',[],[],True,policy2)
        event(self.e,[change(self.e,'mira.profile',policy_version=2),change(self.e,'mira.fear',phase='ended')])
        self.assertEqual(weights(self.e,branch='alternate')['inspect'],4)
        self.assertEqual(self.e.db.execute('SELECT command_json FROM events WHERE id=?',(receipt['event_id'],)).fetchone()[0],before)
        replay=self.e.replay('main'); self.assertTrue(replay['complete']); self.assertEqual(replay['records'],self.e.state())
        self.e.close(); self.e=Engine(self.path)
        self.assertEqual(self.e.get('alternate','mira.profile')['data']['policy_version'],1)
        self.assertTrue(self.e.verify()['ok'])

    def test_full_journey_options_relationship_learning_and_will_development(self):
        e=Engine(Path(self.tmp.name)/'journey.sqlite')
        try:
            report=run(e)
            self.assertEqual(report['before'],report['branch_without_exchange']); self.assertNotEqual(report['before'],report['after'])
            self.assertTrue(report['replay']['records_match']); self.assertEqual(report['stamina'],4); self.assertEqual(report['clock'],1)
            self.assertEqual(e.get('main','mira.development')['data']['contract']['mechanical_unlocks'],[])
            self.assertEqual(report['mastery'],'ordinary competence')
            self.assertIn('inquire',json.dumps(e.opportunities('main','mira')['personality']['guidance']))
            self.assertIsNone(e.opportunities('main','mira',viewer='oren')['personality']['guidance'])
        finally: e.close()

    def test_failed_migration_recovers_actual_previous_campaign(self):
        from kageyoni.resources import fixture_path
        old=Path(self.tmp.name)/'old.sqlite'; shutil.copy2(fixture_path('recovery/pre-personality-v1.sqlite'),old)
        read=Path.read_text
        def broken(path,*args,**kw):
            text=read(path,*args,**kw)
            return text+'\nINVALID SQL;' if path.name=='migration_007.sql' else text
        with patch.object(Path,'read_text',broken),self.assertRaises(sqlite3.Error): Engine(old)
        c=sqlite3.connect(old)
        self.assertEqual(c.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0],6)
        self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='personality_profile'").fetchone()); c.close()
        upgraded=Engine(old)
        try:
            self.assertTrue(upgraded.verify()['ok']); self.assertEqual(len(upgraded.state()),165)
            self.assertEqual(upgraded.branch('main')['revision'],1)
            self.assertEqual(upgraded.replay('main')['records'],upgraded.state())
        finally: upgraded.close()

    def test_real_v6_pending_decision_survives_supported_upgrade(self):
        # Create an authentic pending decision with the delivered older code.
        from kageyoni.resources import fixture_path
        archive=ROOT/'build/Kageyoni-Connected-Play-v6.zip'
        portable=fixture_path('recovery/legacy-personality-pending.sqlite')
        if archive.exists():
            with zipfile.ZipFile(archive) as z:
                for name in z.namelist():
                    if name.startswith('kageyoni-local-dev/kageyoni/') or name.endswith('.sql'):
                        z.extract(name,self.tmp.name)
            previous=Path(self.tmp.name)/'kageyoni-local-dev'
            dst=Path(self.tmp.name)/'pending.sqlite'; shutil.copy2(fixture_path('recovery/pre-personality-v1.sqlite'),dst)
            script="""from kageyoni.engine import Engine
from kageyoni import decisions as d
e=Engine(DST)
actor='legacy-fixture.actor'
e.apply(dict(api_version=3,branch='main',expected_revision=e.branch('main')['revision'],request_id='legacy-fixture.setup',actor='gm',kind='action',narrative='NONCANONICAL legacy fixture',changes=[dict(op='create',domain='character',id=actor,data=dict(name='Legacy fixture',entity_kind='person'),status='proposed',visibility='public',evidence=[dict(note='NONCANONICAL migration fixture')])]))
s=dict(id='legacy',expected_revision=e.branch('main')['revision'],actor=actor,intent='Reflect',method='Quiet thought',stakes='None',modules=['downtime'],agency_state='voluntary',adjudication=dict(by='fixture-gm',rationale='No change',basis=[]),uncertainty=dict(mode='none'),outcomes=dict(success={},failure={}))
d.propose(e,'main',s)
e.close()
""".replace('DST',repr(str(dst)))
            result=subprocess.run([sys.executable,'-c',script],cwd=previous,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
        else:
            self.assertTrue(portable.exists(),'Previous-engine pending proposal fixture must ship with the package')
            dst=Path(self.tmp.name)/'pending.sqlite'; shutil.copy2(portable,dst)
        newer=Engine(dst)
        try:
            row=newer.db.execute("SELECT spec_json FROM decision_proposals WHERE id='legacy'").fetchone(); actor=json.loads(row[0])['actor']
            receipt=d.commit(newer,'main','legacy',actor,True,'NONCANONICAL legacy fixture resumed')
            self.assertEqual(receipt['revision'],3); self.assertTrue(newer.verify()['ok'])
        finally: newer.close()

if __name__=='__main__': unittest.main()
