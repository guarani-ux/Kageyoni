"""Noncanonical integrated journey and adversarial decision cases."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from kageyoni.engine import Engine, Rejected
from kageyoni import decisions as d
from test_engine import create, patch as change

ROOT=Path(__file__).resolve().parents[1]

class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.path=Path(self.t.name)/'fixture.sqlite'; self.e=Engine(self.path)
        self.event([create('location','shore',name='Shore',kind='region'),create('location','bank',name='Other bank',kind='region'),create('character','a',name='Specialist',entity_kind='person',location='shore'),create('character','parent',name='Parent',entity_kind='person',location='shore'),create('character','sibling',name='Sibling',entity_kind='person',location='shore'),create('faction','family',name='Family'),create('affiliation','member1',character='parent',faction='family',allegiance='member'),create('affiliation','member2',character='sibling',faction='family',allegiance='member'),create('item','bridge',name='Bridge',condition='damaged'),create('route','route',origin='shore',destination='bank',access='blocked'),create('environment','water',location='shore',feature='low water',kind='hazard'),create('resource','stamina',holder='a',name='Stamina',quantity=10,unit='effort'),create('clock','clock',name='Local',tick=0,unit='hour'),create('ability','repair',name='Repair',function='Repair bounded structural damage'),create('capability','skill',character='a',ability='repair',mastery='specialist'),create('item','kit',name='Repair kit',condition='working'),create('loadout','tools',item='kit',holder='a',slot='carried',equipped=0),create('character_aspect','parent.drive',character='parent',section='interiority',kind='drive',value_status='known',statement='Keep children safe',phase='active',change_basis='established')])
        self.e.define_property('repair.bonus',1,'Repair bonus','Fixture contextual repair advantage','integer',['person'],{},'active',unit='bonus')
        self.event([],properties=[dict(entity_id='a',property_id='repair.bonus',definition_version=1,state='known',value=4,unit='bonus',visibility='public',epistemic_status='proposed')])
        self.e.add_rule('repair-roll',1,'Fixture repair',['repair.bonus'],[],True,{'kind':'sum'},[('repair.bonus',1,'reads')])

    def tearDown(self): self.e.close(); self.t.cleanup()

    def event(self,changes,**kw):
        rev=self.e.branch('main')['revision']
        return self.e.apply(dict(api_version=3,branch='main',request_id='setup:'+str(rev),expected_revision=rev,kind='action',actor='gm',narrative='NONCANONICAL fixture',changes=changes,**kw))

    def spec(self,id='repair',**kw):
        s=dict(id=id,expected_revision=self.e.branch('main')['revision'],actor='a',intent='Repair the bridge',method='Use repair skill and tools',stakes='Effort and the crossing opportunity',modules=['travel','social'],agency_state='voluntary',adjudication={'by':'fixture-gm','rationale':'Tools and demonstrated repair practice support this attempt. Repair opens this route.','basis':['skill','tools','bridge']},capabilities=['skill'],equipment=['tools'],requirements=[{'record_id':'bridge','field':'condition','equals':'damaged'}],rules=[dict(id='repair-roll',version=1,subject='a',stage='probability',unit='bonus')],uncertainty={'mode':'d20','difficulty':12},costs=[{'resource':'stamina','amount':2,'unit':'effort'}],outcomes={'success':{'changes':[change('bridge',condition='repaired'),change('route',access='open')]},'failure':{'changes':[change('bridge',condition='damaged')]}})
        s.update(kw); return s

    def commit(self,id='repair'): return d.commit(self.e,'main',id,'a',True,'NONCANONICAL repair attempt')

    def test_proposal_no_roll_cost_or_time_then_mixed_journey(self):
        self.e.fork('main','without-repair',self.e.branch('main')['revision'])
        s=self.spec(time={'clock':'clock','duration':1})
        rev=self.e.branch('main')['revision']; d.propose(self.e,'main',s)
        self.assertEqual(self.e.branch('main')['revision'],rev); self.assertEqual(self.e.get('main','stamina')['data']['quantity'],10)
        self.assertIsNone(self.e.db.execute('SELECT roll FROM decision_proposals').fetchone()[0])
        with patch('kageyoni.decisions.secrets.randbelow',return_value=9): receipt=self.commit()
        self.assertEqual(self.e.get('main','route')['data']['access'],'open')
        self.assertEqual(self.e.get('without-repair','route')['data']['access'],'blocked')
        self.assertEqual(self.e.get('main','stamina')['data']['quantity'],8); self.assertEqual(self.e.get('main','clock')['data']['tick'],1)
        res=json.loads(self.e.db.execute('SELECT resolution_json FROM event_resolutions WHERE event_id=?',(receipt['event_id'],)).fetchone()[0])
        self.assertEqual(res['modifier'],4); self.assertEqual(res['roll_result'],10)
        # Later travel depends on the actual route changed by the earlier choice.
        later=self.spec('cross',requirements=[dict(record_id='route',field='access',equals='open')],uncertainty={'mode':'none'},rules=[],costs=[],outcomes={'success':{'changes':[change('a',location='bank')]},'failure':{'changes':[]}})
        d.propose(self.e,'main',later); self.commit('cross'); self.assertEqual(self.e.get('main','a')['data']['location'],'bank')
        self.assertTrue(self.e.verify()['ok'])

    def test_independent_refusal_and_unknown_npc_knowledge(self):
        response=dict(actor='parent',decision='refuse',judgment={'by':'gm','rationale':'Parent does not accept this risk','basis':['parent.drive']})
        p=d.propose(self.e,'main',self.spec(responses=[response])); self.assertEqual(p['status'],'blocked')
        with self.assertRaises(Rejected): self.commit()
        self.event([dict(create('item','secret',name='Secret',condition='hidden'),visibility='gm')])
        response['judgment']['basis']=['secret']
        with self.assertRaisesRegex(Rejected,'unavailable knowledge'): d.propose(self.e,'main',self.spec('omniscient',responses=[response]))

    def test_failure_cost_once_retry_and_reopen(self):
        s=self.spec(); d.propose(self.e,'main',s)
        with patch('kageyoni.decisions.secrets.randbelow',return_value=0): first=self.commit()
        self.e.close(); self.e=Engine(self.path)
        self.assertEqual(first['event_id'],self.commit()['event_id'])
        self.assertEqual(self.e.get('main','stamina')['data']['quantity'],8)
        self.assertEqual(self.e.get('main','route')['data']['access'],'blocked')
        self.assertEqual(d.propose(self.e,'main',s)['status'],'committed')

    def test_interrupted_commit_keeps_roll(self):
        d.propose(self.e,'main',self.spec())
        with patch('kageyoni.decisions.secrets.randbelow',return_value=7),patch.object(self.e,'apply',side_effect=Rejected('interrupted')):
            with self.assertRaisesRegex(Rejected,'interrupted'): self.commit()
        self.assertEqual(self.e.db.execute('SELECT roll FROM decision_proposals').fetchone()[0],8)
        self.assertEqual(self.e.get('main','stamina')['data']['quantity'],10)
        with patch('kageyoni.decisions.secrets.randbelow',side_effect=AssertionError('reroll')): self.commit()
        self.assertEqual(self.e.get('main','stamina')['data']['quantity'],8)

    def test_stale_and_mutated_proposals(self):
        s=self.spec(); d.propose(self.e,'main',s)
        s['method']='Different';
        with self.assertRaisesRegex(Rejected,'changed content'): d.propose(self.e,'main',s)
        self.event([change('water',feature='high water')])
        with self.assertRaisesRegex(Rejected,'stale decision'): self.commit()
        self.assertIsNone(self.e.db.execute('SELECT roll FROM decision_proposals').fetchone()[0])

    def test_duplicate_units_ownership_and_hidden_view(self):
        for key,s in [('duplicate',self.spec()),('units',self.spec()),('owner',self.spec())]:
            if key=='duplicate': s['rules']*=2
            elif key=='units': s['rules'][0]['unit']='kg'
            else: s['actor']='parent'
            with self.subTest(key=key),self.assertRaises(Rejected): d.propose(self.e,'main',s)
        s=self.spec(); s['adjudication']['rationale']='SECRET GM REASON'; d.propose(self.e,'main',s)
        public=json.dumps(d.inspect(self.e,'main','repair',viewer='a'))
        self.assertNotIn('SECRET',public); self.assertNotIn('modifier',public)
        with self.assertRaisesRegex(Rejected,'unavailable'): d.inspect(self.e,'main','repair',viewer='parent')

    def test_no_natural_twenty_override(self):
        d.propose(self.e,'main',self.spec(uncertainty={'mode':'d20','difficulty':99}))
        with patch('kageyoni.decisions.secrets.randbelow',return_value=19): self.commit()
        self.assertEqual(self.e.get('main','bridge')['data']['condition'],'damaged')

    def test_consequence_changes_later_state_and_blocks_until_settled(self):
        s=self.spec(uncertainty={'mode':'none'},rules=[])
        s['outcomes']['success']['consequences']=[dict(id='water-rise',subject_id='water',effect={'changes':[change('water',feature='rising water')]},trigger={'kind':'immediate'})]
        d.propose(self.e,'main',s); self.commit()
        p=d.propose(self.e,'main',self.spec('later')); self.assertEqual(p['status'],'blocked')
        result=d.settle(self.e,'main'); self.assertEqual(len(result['applied']),1)
        self.assertEqual(self.e.get('main','water')['data']['feature'],'rising water'); self.assertFalse(d.settle(self.e,'main')['applied'])

    def test_replay_snapshot_and_actual_upgrade(self):
        d.propose(self.e,'main',self.spec()); self.commit(); self.e.register_snapshot('main','decision-snapshot')
        self.assertEqual(self.e.replay('main')['records'],sorted(self.e.state(),key=lambda r:r['id']))
        from kageyoni.resources import fixture_path
        dst=Path(self.t.name)/'upgrade.sqlite'; shutil.copy2(fixture_path('recovery/pre-decisions-v1.sqlite'),dst)
        e=Engine(dst)
        try: self.assertTrue(e.verify()['ok']); self.assertEqual(len(e.state()),165); self.assertEqual(e.branch('main')['revision'],1)
        finally: e.close()

    def test_cannot_bypass_commit_with_edited_command(self):
        p=d.propose(self.e,'main',self.spec())
        command=p['assessment']['commands']['success']
        with self.assertRaisesRegex(Rejected,'decision-commit'): self.e.apply(command)

    def test_will_and_background_in_one_event(self):
        from test_will_system import WillFixture
        helper=WillFixture()
        self.e.add_rule('will-allow',1,'Fixture permission',[],[],True,{'kind':'contextual','outcome':True})
        definition=helper._definition(); expression=helper._expression(techniques=[{'id':'technique','version':1}]); expression['legacy_will_id']=None
        technique=helper._technique(target_kinds=['structure'])
        self.event([create('will_definition','definition',name='Fixture Will',classification='independent',contract=definition),create('will_expression','expression',definition='definition',bearer='a',contract=expression),create('will_technique','technique',expression='expression',name='Fixture support',contract=technique)])
        self.e.create_process('main',{'id':'water-process','process_kind':'weather','state':'active','subjects':['water'],'scope':{'clock_id':'clock'},'next_tick':1,'granularity':'exact','metadata':{'effect':{'kind':'record_patch','record_id':'water','data':{'feature':'high water'}}}},'water-process','gm','NONCANONICAL water process')
        s=self.spec(time={'clock':'clock','duration':1},will=[{'expression':{'id':'expression','version':1},'technique':{'id':'technique','version':1},'judgment':{'by':'fixture-gm','rationale':'Fixture support holds bridge during repair; no extra costs or resistance.','basis':['bridge','skill']}}])
        d.propose(self.e,'main',s)
        with patch('kageyoni.decisions.secrets.randbelow',return_value=10): r=self.commit()
        self.assertEqual(self.e.get('main','water')['data']['feature'],'high water')
        self.assertEqual(self.e.get('main','bridge')['updated_event'],self.e.get('main','water')['updated_event'])
        self.assertEqual(self.e.get('main','water')['updated_event'],r['event_id'])
        self.assertEqual(self.e.list_processes('main')[0]['state'],'completed')

    def test_background_judgment_and_deadline_block_before_roll(self):
        self.e.create_process('main',{'id':'patrol','process_kind':'patrol','state':'active','scope':{'clock_id':'clock'},'next_tick':1,'metadata':{'effect':{'kind':'judgment','reason':'Patrol response needed'}}},'patrol','gm','NONCANONICAL patrol')
        p=d.propose(self.e,'main',self.spec(time={'clock':'clock','duration':2}))
        self.assertEqual(p['status'],'blocked'); self.assertEqual(self.e.get('main','clock')['data']['tick'],0)
        with self.assertRaises(Rejected): self.commit()
        self.assertIsNone(self.e.db.execute('SELECT roll FROM decision_proposals').fetchone()[0])

    def test_simultaneous_sessions_and_admin_stat_change(self):
        d.propose(self.e,'main',self.spec())
        second=Engine(self.path)
        try:
            self.commit()
            self.assertTrue(d.commit(second,'main','repair','a',True,'Retry')['replayed'])
        finally: second.close()
        s=self.spec('another',requirements=[]); s['outcomes']={'success':{'changes':[]},'failure':{'changes':[]}}
        d.propose(self.e,'main',s)
        self.e.set_property('main','a','repair.bonus',1,'known',8,unit='bonus')
        with self.assertRaisesRegex(Rejected,'stale decision'): self.commit('another')

    def test_deadline_and_branch_pending_proposal(self):
        self.event([create('schedule','deadline',clock='clock',due=1,trigger='Ferry departs',phase='pending')])
        p=d.propose(self.e,'main',self.spec(time={'clock':'clock','duration':2}))
        self.assertEqual(p['status'],'blocked')
        self.e.fork('main','alternative',self.e.branch('main')['revision'])
        self.assertIsNotNone(self.e.db.execute("SELECT id FROM decision_proposals WHERE branch='alternative'").fetchone())
        snap=json.loads(self.e.db.execute("SELECT state_json FROM snapshots WHERE id='fork:alternative'").fetchone()[0])
        self.assertEqual(snap['decisions'][0]['id'],'repair')

    def test_interrupted_decision_migration(self):
        import sqlite3
        from kageyoni.resources import fixture_path
        dst=Path(self.t.name)/'interrupted.sqlite'; shutil.copy2(fixture_path('recovery/pre-decisions-v1.sqlite'),dst)
        original=Path.read_text
        def bad(path,*args,**kw):
            content=original(path,*args,**kw)
            return content+'\nINVALID SQL;' if path.name=='migration_006.sql' else content
        with patch.object(Path,'read_text',bad),self.assertRaises(sqlite3.Error): Engine(dst)
        c=sqlite3.connect(dst)
        self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='decision_proposals'").fetchone()); c.close()
        e=Engine(dst); self.assertTrue(e.verify()['ok']); e.close()

if __name__=='__main__': unittest.main()
