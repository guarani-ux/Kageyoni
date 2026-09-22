import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from kageyoni.engine import Engine, Rejected, digest
from kageyoni.model import DOMAINS, REQUIRED
from kageyoni.seed import seed

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=[{'note':'Synthetic test fixture; not Kageyoni canon.'}]
def create(domain,id,**data): return dict(op='create',domain=domain,id=id,data=data,status='proposed',visibility='public',evidence=EVIDENCE)
def patch(id,version=1,**data): return dict(op='patch',id=id,expected_version=version,data=data,evidence=EVIDENCE)

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/'world.sqlite'; self.e=Engine(self.path)
        self.apply([
            create('location','island',name='Test Island',kind='island'),
            create('location','room',name='Test Room',kind='room',parent='island'),
            create('character','a',name='A',entity_kind='person',location='room',condition='injured'),
            create('character','b',name='B',entity_kind='person',location='room'),
            create('faction','f',name='Faction'),create('item','sword',name='Sword',condition='damaged'),
            create('loadout','custody',item='sword',holder='a',slot='hand',equipped=1),
            create('clock','clock',name='Local',tick=0,unit='day'),
            create('scene','scene',name='Test Scene',location='room',clock='clock',round=0,phase='active'),
            create('participation','present-a',scene='scene',character='a'),
            create('ability','ability',name='Ability',function='Test'),
            create('objective','objective',title='Objective',phase='active',progress=0),
        ])
    def tearDown(self): self.e.close(); self.temp.cleanup()
    def command(self,changes,**kw):
        c=dict(api_version=1,branch='main',expected_revision=self.e.branch('main')['revision'],request_id='request-'+str(self.e.branch('main')['revision']),kind='action',actor='test-gm',narrative='Synthetic test only.',changes=changes)
        c.update(kw); return c
    def apply(self,changes,**kw): return self.e.apply(self.command(changes,**kw))
    def reject(self,command):
        before=self.e.state(); count=self.e.db.execute('SELECT count(*) FROM events').fetchone()[0]
        with self.assertRaises((Rejected,sqlite3.IntegrityError)): self.e.apply(command)
        self.assertEqual(before,self.e.state()); self.assertEqual(count,self.e.db.execute('SELECT count(*) FROM events').fetchone()[0]); self.e.verify()
    def test_complete_domain_inventory(self):
        for domain in DOMAINS: self.assertIsNotNone(self.e.db.execute('SELECT name FROM sqlite_master WHERE name=?',(domain,)).fetchone())
        self.assertEqual(set(DOMAINS),set(REQUIRED))
    def test_all_domains_roundtrip(self):
        samples=[
            create('relationship','rel',subject='a',object='b',kind='trust',feeling='ambivalent'),
            create('capability','cap',character='a',ability='ability',mastery='learning'),
            create('will','will',name='Resolve',bearer='a',principles='Choose freely'),
            create('loot','loot',item='sword',location='room',discovery='discovered'),
            create('environment','env',location='island',feature='Storm',kind='weather'),
            create('route','route',origin='room',destination='island',access='conditional',conditions='Open door'),
            create('dependency','dep',objective='objective',prerequisite='other-objective',relation='supports'),
            create('objective','other-objective',title='Other',phase='available'),
            create('decision','decision',actor='a',objective='objective',choice='Wait',alternatives=['Leave'],rationale='Protect B'),
            create('arc','arc',name='Arc',phase='active'),create('thread','thread',arc='arc',question='Why?',phase='open'),
            create('progression','prog',character='a',ability='ability',experience='Survived encounter',phase='retained',demonstrated='Observed once',cost='Exhaustion'),
            create('political_claim','claim',claimant='f',territory='island',authority='Claimed sovereignty',phase='contested'),
            create('affiliation','aff',character='a',faction='f',allegiance='estranged'),
            create('law','law',issuer='f',jurisdiction='island',name='Law',provision='Provision',phase='active'),
            create('accord','accord',party_a='a',party_b='f',kind='truce',phase='active'),
            create('office','office',faction='f',holder='b',title='Governor',phase='occupied'),
            create('resource','resource',holder='f',name='Food',quantity=10,unit='ration'),
            create('knowledge','belief',holder='b',assertion='A trusts B',attitude='believes'),
            create('historical_account','account',author='f',assertion='We won',interpretation='Propaganda; disputed'),
            create('experience','exp',character='a',clock='clock',elapsed=14,unit='day',remembered='Loop',survives_rewind=1),
            create('schedule','schedule',clock='clock',due=5,trigger='Election',phase='pending'),
            create('world_rule','rule',name='Balance',scope='island',statement='No total suppression',resolution='gm_judgment'),
            create('consequence','cons',subject='a',effect='Scar',reversibility='unknown'),
        ]
        # The refined Will domains are intentionally exercised here as
        # ordinary records; their contract is version-bound and the fixture is
        # noncanonical.  The source event is the setup event already present in
        # the branch, so the effect remains causally reproducible.
        self.e.add_rule('fixture-will-resolution', 1, 'Fixture Will resolution', [], [], True, {'kind':'contextual','outcome':True})
        source_event = self.e.db.execute("SELECT id FROM events WHERE branch='main' ORDER BY revision LIMIT 1").fetchone()[0]
        ev = {'source':'fixture','assertion':'Synthetic fixture only','status':'proposed'}
        definition_contract = {'schema_version':'will-contract/0.1','id':'will-definition','version':1,'design_status':'accepted','evidence':[ev],'name':'Fixture Will','classification':'independent','nature':'chosen expression','ancestry':[],'generative_boundary':'fixture only','inherent_limits':['not canon'],'invariants':[]}
        expression_contract = {'schema_version':'will-contract/0.1','id':'will-expression','version':1,'design_status':'accepted','evidence':[ev],'definition':{'id':'will-definition','version':1},'bearer':'a','legacy_will_id':'will','interpretation':'fixture expression','channels':['voice'],'stat_bindings':[],'learned_techniques':[{'id':'will-technique','version':1}],'conditions':[],'awakening_access':'latent','awakening_mastery':'unknown','awakening_definition':{'id':'will-awakening','version':1}}
        technique_condition = {'id':'fixture-trigger','mode':'judgment','rule':None,'statement':'GM confirms scene access','missing_policy':'request_judgment'}
        technique_contract = {'schema_version':'will-contract/0.1','id':'will-technique','version':1,'design_status':'accepted','evidence':[ev],'expression':{'id':'will-expression','version':1},'name':'Fixture Technique','derivation':'fixture practice','practice_status':'demonstrated','activation':'deliberate','trigger':technique_condition,'channels':[{'medium':'voice','access':technique_condition,'break_conditions':[]}],'effects':[{'operation':'alter','target_role':'target','mechanism':'fixture only','preconditions':[],'scope':{'target_kinds':['person'],'range':None,'area':None,'duration':None,'unknowns':[]},'inputs':[],'resolver':None,'authority':'gm_judgment','resistance':[],'postconditions':[]}],'costs':[],'resolution_policy':{'id':'fixture-will-resolution','version':1},'termination':[]}
        awakening_contract = {'schema_version':'will-contract/0.1','id':'will-awakening','version':1,'design_status':'proposed','evidence':[ev],'expression':{'id':'will-expression','version':1},'qualitative_change':'fixture change','substrates':['fixture'],'eligibility':[],'activation_conditions':[],'transformed_techniques':[],'upkeep':[],'interruptions':[],'other_agency':'GM judgment','persistent_residue':['fixture residue'],'recovery_conditions':[]}
        development_contract = {'schema_version':'will-contract/0.1','id':'will-development','version':1,'design_status':'proposed','evidence':[ev],'expression':{'id':'will-expression','version':1},'dimension':'understanding','phase':'demonstrated','claim':'fixture claim','supporting_events':[source_event],'limitations':['fixture only'],'mechanical_unlocks':[]}
        effect_contract = {'schema_version':'will-contract/0.1','id':'will-effect','version':1,'design_status':'proposed','evidence':[ev],'expression':{'id':'will-expression','version':1},'technique':{'id':'will-technique','version':1},'source_event':source_event,'targets':['a'],'phase':'active','anchor_records':['a'],'start_clock':'clock','start_tick':0,'end_conditions':[],'process_ids':[],'consequence_ids':[],'residue_records':['a']}
        samples.extend([
            dict(create('writing_delivery','a.presentation',audience='a',form='description',text='Fixture scene'),visibility='restricted',audience=['a']),
            dict(create('dialogue_reception','b.interpretation',listener='b',turn='a.hello',interpretation='A greeting',certainty='tentative'),visibility='restricted',audience=['b']),
            create('personality_profile','a.personality',character='a',framework='mbti-inspired',interpretation='unknown',note='Noncanonical unknown interpretation'),
            create('dialogue_turn','a.hello',speaker='a',listeners=['b'],act='greet',text='Hello',mode='spoken'),
            create('character_identity','a.identity',character='a',existence='established',name_status='unknown',continuity='established'),
            create('character_aspect','a.drive',character='a',section='interiority',kind='drive',value_status='known',statement='Protect B',phase='active',change_basis='established'),
            create('character_presence','a.presence',character='a',location='island',mode='physical',phase='present'),
            create('character_lineage','a.lineage',predecessor='a',successor='b',relation='disputed',explanation='Synthetic disputed origin'),
            create('will_definition','will-definition',name='Fixture Will',classification='independent',contract=definition_contract),
            create('will_expression','will-expression',definition='will-definition',bearer='a',legacy_will='will',contract=expression_contract),
            create('will_technique','will-technique',expression='will-expression',ability='ability',name='Fixture Technique',contract=technique_contract),
            create('will_awakening','will-awakening',expression='will-expression',contract=awakening_contract),
            create('will_development','will-development',expression='will-expression',progression='prog',contract=development_contract),
            create('will_effect','will-effect',expression='will-expression',technique='will-technique',contract=effect_contract),
        ])
        self.apply(samples); self.assertEqual({r['domain'] for r in self.e.state()},set(DOMAINS)); self.e.verify()
    def test_atomic_cross_domain_and_reopen(self):
        receipt=self.apply([patch('a',condition='recovering'),patch('custody',holder='b'),create('relationship','rel',subject='a',object='b',kind='gratitude')]); self.e.close(); self.e=Engine(self.path)
        self.assertEqual(self.e.get('main','custody')['data']['holder'],'b'); self.assertEqual(len(receipt['changed']),3); self.e.verify()
    def test_failure_rolls_back_earlier_change(self): self.reject(self.command([patch('a',condition='healthy'),patch('custody',holder='missing')]))
    def test_idempotent_retry(self):
        c=self.command([patch('a',condition='recovering')]); first=self.e.apply(c); second=self.e.apply(c)
        self.assertEqual(first['event_id'],second['event_id']); self.assertTrue(second['replayed']); self.assertEqual(self.e.get('main','a')['version'],2)
    def test_request_id_collision(self):
        c=self.command([patch('a',condition='recovering')]); self.e.apply(c); c['narrative']='different'; self.reject(c)
    def test_stale_branch(self): self.reject(self.command([patch('a',condition='healthy')],expected_revision=0))
    def test_stale_record(self): self.reject(self.command([patch('a',version=99,condition='healthy')]))
    def test_unknown_domain(self): self.reject(self.command([create('invented','x',name='X')]))
    def test_unknown_field(self): self.reject(self.command([patch('a',unrecorded_power='omnipotence')]))
    def test_wrong_reference_type(self): self.reject(self.command([patch('a',location='sword')]))
    def test_duplicate_record(self): self.reject(self.command([create('character','a',name='Duplicate',entity_kind='person')]))
    def test_same_record_twice(self): self.reject(self.command([patch('a',condition='x'),patch('a',condition='y')]))
    def test_delete_disallowed(self): self.reject(self.command([dict(op='delete',id='a')]))
    def test_domain_change_disallowed(self):
        c=patch('a',name='A'); c['domain']='faction'; self.reject(self.command([c]))
    def test_location_cycle(self): self.reject(self.command([patch('island',parent='room')]))
    def test_reference_created_later_in_transaction(self):
        self.apply([create('relationship','rel',subject='a',object='new',kind='new'),create('character','new',name='New',entity_kind='person')]); self.e.verify()
    def test_invalid_enum(self): self.reject(self.command([patch('objective',phase='maybe-complete')]))
    def test_nonfinite(self): self.reject(self.command([patch('clock',tick=float('nan'))]))
    def test_missing_evidence(self):
        c=patch('a',condition='healed'); c.pop('evidence'); self.reject(self.command([c]))
    def test_wrong_source_quote(self):
        c=patch('a',condition='healed'); c['evidence']=[dict(source='missing',quote='invented',note='test')]; self.reject(self.command([c]))
    def test_double_ownership(self): self.reject(self.command([create('loadout','second',item='sword',holder='b',slot='hand',equipped=1)]))
    def test_slot_collision(self): self.reject(self.command([create('item','second-sword',name='Second',condition='ok'),create('loadout','second',item='second-sword',holder='a',slot='hand',equipped=1)]))
    def test_loot_discovery_does_not_transfer(self):
        self.apply([create('loot','loot',item='sword',location='room',discovery='discovered')]); self.assertEqual(self.e.get('main','custody')['data']['holder'],'a')
    def test_claim_requires_custody(self): self.reject(self.command([create('loot','loot',item='sword',location='room',discovery='claimed',claimant='b')]))
    def test_claim_and_transfer_together(self):
        self.apply([create('loot','loot',item='sword',location='room',discovery='claimed',claimant='b'),patch('custody',holder='b')]); self.e.verify()
    def test_progression_requires_demonstration(self): self.reject(self.command([create('progression','p',character='a',ability='ability',experience='Wished for mastery',phase='retained')]))
    def test_negative_duration(self): self.reject(self.command([create('experience','x',character='a',clock='clock',elapsed=-1,unit='day',survives_rewind=0)]))
    def test_negative_resource(self): self.reject(self.command([create('resource','x',holder='a',name='Food',quantity=-1,unit='ration')]))
    def test_progress_range(self): self.reject(self.command([patch('objective',progress=2)]))
    def test_scene_movement_requires_scene_update(self): self.reject(self.command([patch('a',location='island')]))
    def test_scene_transition_together(self): self.apply([patch('a',location='island'),patch('scene',location='island')]); self.e.verify()
    def test_correction_preserves_history(self):
        first=self.apply([patch('a',condition='tired')]); self.apply([patch('a',2,condition='injured')],kind='correction',causes=[first['event_id']]); self.assertEqual(self.e.db.execute('SELECT count(*) FROM changes WHERE record_id="a"').fetchone()[0],3); self.e.verify()
    def test_correction_without_cause(self): self.reject(self.command([patch('a',condition='healthy')],kind='correction'))
    def test_time_advance_and_rewind_with_memory(self):
        first=self.apply([patch('clock',tick=10)],kind='advance_time',clock_id='clock',tick=10)
        self.apply([patch('clock',2,tick=2),create('experience','exp',character='a',clock='clock',elapsed=10,unit='day',remembered='Retained',survives_rewind=1)],kind='rewind',clock_id='clock',tick=2,causes=[first['event_id']]); self.e.verify()
    def test_unmarked_rewind(self):
        self.apply([patch('clock',tick=10)]); self.reject(self.command([patch('clock',2,tick=2)]))
    def test_event_time_must_match_clock(self): self.reject(self.command([patch('a',condition='tired')],clock_id='clock',tick=10))
    def test_subjective_time_independent(self):
        self.apply([create('experience','x',character='a',clock='clock',elapsed=20,unit='day',survives_rewind=1)]); self.assertEqual(self.e.get('main','clock')['data']['tick'],0)
    def test_competing_claims_and_belief(self):
        self.apply([create('political_claim','p1',claimant='a',territory='island',authority='Sovereign',phase='asserted'),create('political_claim','p2',claimant='f',territory='island',authority='Sovereign',phase='asserted'),create('knowledge','k',holder='a',assertion='I rule',attitude='believes')]); self.assertEqual(len(self.e.context(domain='political_claim')['records']),2)
    def test_objective_dependency_cycle(self): self.reject(self.command([create('dependency','d',objective='objective',prerequisite='objective',relation='requires')]))
    def test_open_thread_cannot_be_answered_without_answer(self): self.reject(self.command([create('thread','t',question='Why?',phase='answered')]))
    def test_office_consistency(self): self.reject(self.command([create('office','o',faction='f',title='Ruler',phase='occupied')]))
    def test_preview_changes_nothing(self):
        before=self.e.state(); receipt=self.e.apply(self.command([patch('a',condition='tired')]),preview=True); self.assertFalse(receipt['committed']); self.assertEqual(before,self.e.state()); self.e.verify()
    def test_failed_action_recorded_without_state_change(self):
        before=self.e.state(); self.apply([],kind='failed_action'); self.assertEqual(before,self.e.state()); self.e.verify()
    def test_branch_isolation(self):
        before=self.e.state(); self.e.fork('main','alternate',1)
        c=self.command([patch('a',condition='tired')],branch='alternate',expected_revision=0); self.e.apply(c)
        self.assertEqual(before,self.e.state()); self.assertEqual(self.e.get('alternate','a')['data']['condition'],'tired'); self.e.verify()
    def test_cross_branch_reference_rejected(self):
        self.e.fork('main','alternate',1); self.e.apply(self.command([create('character','only-alt',name='Alt',entity_kind='person')],branch='alternate',expected_revision=0))
        self.reject(self.command([create('relationship','r',subject='a',object='only-alt',kind='trust')]))
    def test_stale_fork(self):
        with self.assertRaises(Rejected): self.e.fork('main','alternate',0)
    def test_hidden_information(self):
        c=create('knowledge','secret',holder='b',assertion='SECRET',attitude='knows'); c['visibility']='restricted'; c['audience']=['b']; self.apply([c])
        self.assertNotIn('SECRET',json.dumps(self.e.context(viewer='a'))); self.assertIn('SECRET',json.dumps(self.e.context(viewer='b')))
    def test_gm_hidden_records(self):
        c=create('knowledge','secret',holder='b',assertion='SECRET',attitude='knows'); c['visibility']='gm'; self.apply([c]); self.assertNotIn('SECRET',json.dumps(self.e.context(viewer='b')))
    def test_scene_context(self): self.assertIn('a',{r['id'] for r in self.e.context(scene='scene')['records']})
    def test_roll_once(self):
        a=self.e.roll('main','roll',20,12,2,'Declared strike'); b=self.e.roll('main','roll',20,12,2,'Declared strike'); self.assertEqual(a,b); self.assertTrue(1<=a['result']<=20)
        with self.assertRaises(Rejected): self.e.roll('main','roll',20,1,20,'Cheat')
    def test_roll_cannot_be_spent_twice(self):
        self.e.roll('main','r',20,12,2,'Strike')
        self.apply([patch('a',condition='tired')],roll_ids=['r'])
        self.reject(self.command([patch('a',2,condition='more tired')],roll_ids=['r']))
    def test_preview_does_not_consume_roll(self):
        self.e.roll('main','r',20,12,2,'Strike')
        c=self.command([patch('a',condition='tired')],roll_ids=['r'])
        self.e.apply(c,preview=True); self.e.apply(c); self.e.verify()
    def test_unknown_roll(self): self.reject(self.command([patch('a',condition='tired')],roll_ids=['missing']))
    def test_backup_restore(self):
        dest=Path(self.temp.name)/'backup.sqlite'; self.e.backup(dest); other=Engine(dest)
        self.assertEqual(self.e.state(),other.state()); other.verify(); other.close()
    def test_backup_never_overwrites(self):
        with self.assertRaises(Rejected): self.e.backup(self.path)
    def test_append_only_history(self):
        self.e.roll('main','roll',20,10,0,'Test immutable outcome')
        self.e.db.execute("INSERT INTO sources VALUES('test','test','unused','body')")
        self.e.db.execute("INSERT INTO excerpts VALUES('test:1','test',1,1,'test','body')")
        for table in ('events','changes','rolls','sources','excerpts'):
            self.assertGreater(self.e.db.execute(f'SELECT count(*) FROM {table}').fetchone()[0],0)
            with self.assertRaises(sqlite3.IntegrityError): self.e.db.execute(f'DELETE FROM {table}')
            column={'events':'narrative','changes':'after_json','rolls':'reason','sources':'content','excerpts':'text'}[table]
            with self.assertRaises(sqlite3.IntegrityError): self.e.db.execute(f'UPDATE {table} SET {column}={column}')
    def test_tampered_projection_detected(self):
        self.e.db.execute("UPDATE character SET condition='tampered' WHERE id='a'")
        with self.assertRaisesRegex(Rejected,'state differs'): self.e.verify()
    def test_two_writers_one_stale(self):
        command=self.command([patch('a',condition='tired')]); barrier=threading.Barrier(2); outcomes=[]
        def worker(i):
            e=Engine(self.path); c=copy.deepcopy(command); c['request_id']=f'writer-{i}'; barrier.wait()
            try: e.apply(c); outcomes.append('accepted')
            except Rejected: outcomes.append('stale')
            finally: e.close()
        threads=[threading.Thread(target=worker,args=(i,)) for i in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertCountEqual(outcomes,['accepted','stale']); self.e.verify()
    def test_cli_new_process(self):
        p=subprocess.run([sys.executable,'-m','kageyoni','--db',str(self.path),'verify'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr); self.assertTrue(json.loads(p.stdout)['ok'])

class SeedTests(unittest.TestCase):
    def test_seed_archive_and_identity(self):
        with tempfile.TemporaryDirectory() as t:
            e=Engine(Path(t)/'seed.sqlite')
            try:
                seed(e,ROOT/'sources'); e.verify()
                for p in (ROOT/'sources').glob('*'):
                    self.assertEqual(e.db.execute('SELECT content FROM sources WHERE id=?',(p.name,)).fetchone()[0],p.read_text(encoding='utf-8'))
                    parts=e.db.execute('SELECT text FROM excerpts WHERE source_id=? ORDER BY start_line',(p.name,)).fetchall()
                    self.assertEqual(''.join(r[0] for r in parts),p.read_text(encoding='utf-8'))
                self.assertNotEqual(e.get('main','levi')['id'],e.get('main','elijah')['id'])
                self.assertNotEqual(e.get('main','xandra-gaia')['id'],e.get('main','xandra-ichimonji')['id'])
                self.assertEqual(e.get('main','kenway')['data']['location'],'deitys-revenge')
                self.assertEqual(e.get('main','oracle')['domain'],'faction')
                self.assertEqual(e.get('main','mugen')['domain'],'environment')
                self.assertEqual(e.get('main','alexandra-blade')['data']['condition'],'damaged and unstable')
                self.assertIsNone(e.get('main','xandra-rewinds')['data']['elapsed'])
                with self.assertRaises(sqlite3.IntegrityError): e.db.execute("UPDATE sources SET content='changed'")
                with self.assertRaises(Rejected): seed(e,ROOT/'sources')
            finally:
                e.close()

if __name__=='__main__': unittest.main()
