"""Noncanonical acceptance fixtures for the character component."""
import copy
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kageyoni.engine import Engine, Rejected
from kageyoni import characters
from test_engine import create, patch as change

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = [{'note':'Noncanonical character fixture.'}]

class CharacterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'campaign.sqlite'
        self.e = Engine(self.path)

    def tearDown(self):
        self.e.close(); self.temp.cleanup()

    def request(self, **kw):
        data = dict(branch='main',request_id='introduce',expected_revision=0,actor='gm',narrative='Noncanonical unnamed visitor.',character_id='visitor',label='Unnamed visitor',existence='established',evidence=EVIDENCE,visibility='public')
        data.update(kw); return data

    def event(self, changes, **kw):
        rev = self.e.branch('main')['revision']
        command = dict(api_version=3,branch='main',request_id='event-'+str(rev),expected_revision=rev,actor='gm',narrative='Noncanonical fixture.',kind='action',changes=changes)
        command.update(kw); return self.e.apply(command)

    def aspect(self, id='drive', kind='drive', section='interiority', **kw):
        d = dict(character='visitor',section=section,kind=kind,value_status='known',statement='Protect the ferry passengers',phase='active',change_basis='established')
        d.update(kw); return create('character_aspect',id,**d)

    def test_minimal_create_retry_and_no_invented_power(self):
        first = characters.create(self.e, **self.request())
        again = characters.create(self.e, **self.request())
        self.assertEqual(first['event_id'],again['event_id']); self.assertTrue(again['replayed'])
        view = characters.read(self.e,'main','visitor')
        self.assertEqual(len(view['linked_records']),1)
        self.assertIsNone(view['character']['data']['motives'])
        self.assertEqual(view['properties'],[])
        self.assertTrue(characters.readiness(self.e,'main','visitor')['ready'])
        self.assertFalse(characters.readiness(self.e,'main','visitor','scene')['ready'])

    def test_hidden_details_and_hidden_subject_errors(self):
        characters.create(self.e, **self.request(aspects=[dict(id='secret',data={k:v for k,v in self.aspect()['data'].items() if k!='character'},visibility='gm')]))
        self.assertIn('secret',json.dumps(characters.read(self.e,'main','visitor')))
        self.assertNotIn('secret',json.dumps(characters.read(self.e,'main','visitor',viewer='visitor')))
        self.assertNotIn('ferry',json.dumps(characters.read(self.e,'main','visitor',viewer='visitor')))
        self.event([dict(create('character','hidden',name='Hidden',entity_kind='person'),visibility='gm')])
        for rid in ('hidden','nonexistent'):
            with self.assertRaisesRegex(Rejected,'character unavailable'):
                characters.read(self.e,'main',rid,viewer='visitor')

    def test_rumor_remains_alleged(self):
        characters.create(self.e, **self.request(existence='alleged'))
        self.assertEqual(self.e.get('main','visitor')['status'],'reported')
        result=characters.readiness(self.e,'main','visitor','scene')
        self.assertIn('established existence for objective scene participation',result['missing'])

    def test_scene_and_explicit_action_inputs(self):
        characters.create(self.e,**self.request())
        self.event([create('location','shore',name='Shore',kind='region'),create('character_presence','present',character='visitor',location='shore',mode='physical',phase='present'),self.aspect(),self.aspect('speech','communication','condition',statement='Can speak'),create('ability','swim',name='Swim',function='Traverse calm water'),create('capability','swimmer',character='visitor',ability='swim',mastery='practiced')])
        self.assertTrue(characters.readiness(self.e,'main','visitor','scene')['ready'])
        req=[dict(record_id='swimmer',field='mastery',equals='practiced')]
        self.assertTrue(characters.readiness(self.e,'main','visitor','action',requirements=req)['ready'])
        req[0]['equals']='expert'
        self.assertFalse(characters.readiness(self.e,'main','visitor','action',requirements=req)['ready'])
        with self.assertRaisesRegex(Rejected,'explicit requirements'):
            characters.readiness(self.e,'main','visitor','action')

    def test_invalid_assignments_are_atomic(self):
        characters.create(self.e,**self.request())
        invalid = [self.aspect(kind='injury'),self.aspect(value_status='unknown'),self.aspect(valid_from=4,valid_until=2),self.aspect(character='missing'),self.aspect(statement=3),create('character_lineage','loop',predecessor='visitor',successor='visitor',relation='split',explanation='invalid')]
        for record in invalid:
            with self.subTest(record=record):
                before=self.e.state(); rev=self.e.branch('main')['revision']
                with self.assertRaises((Rejected,sqlite3.IntegrityError)):
                    self.event([change('visitor',name='Must roll back'),record])
                self.assertEqual(self.e.state(),before); self.assertEqual(self.e.branch('main')['revision'],rev)

    def test_name_status_and_duplicate_identity(self):
        with self.assertRaisesRegex(Rejected,'name status'):
            characters.create(self.e,**self.request(canonical_name='Invented'))
        self.assertEqual(self.e.branch('main')['revision'],0)
        characters.create(self.e,**self.request())
        with self.assertRaises((Rejected,sqlite3.IntegrityError)):
            self.event([create('character_identity','duplicate',character='visitor',existence='established',name_status='unknown',continuity='unresolved')])

    def test_voluntary_change_preserves_original_and_supersession(self):
        characters.create(self.e,**self.request()); self.event([self.aspect()])
        replacement=self.aspect('new-drive',statement='Choose my own journey',change_basis='voluntary',supersedes='drive')
        with self.assertRaisesRegex(Rejected,'must be ended'):
            self.event([replacement])
        self.event([change('drive',phase='ended'),replacement,change('visitor',name='Traveler')])
        old=json.loads(self.e.db.execute("SELECT before_json FROM changes WHERE record_id='drive' AND before_json IS NOT NULL").fetchone()[0])
        self.assertEqual(old['data']['phase'],'active')
        self.assertEqual(self.e.get('main','new-drive')['data']['change_basis'],'voluntary')
        self.assertEqual(self.e.get('main','visitor')['id'],'visitor')

    def test_concurrent_stale_session(self):
        second=Engine(self.path)
        try:
            characters.create(self.e,**self.request())
            with self.assertRaisesRegex(Rejected,'stale branch'):
                characters.create(second,**self.request(character_id='other',request_id='other'))
            self.assertIsNone(second.get('main','other'))
        finally: second.close()

    def test_branch_snapshot_replay_and_reload(self):
        characters.create(self.e,**self.request()); self.event([self.aspect()])
        self.e.register_snapshot('main','character-fixture')
        self.e.fork('main','alternate',self.e.branch('main')['revision'])
        self.event([change('visitor',name='Traveler')])
        self.assertEqual(self.e.get('alternate','visitor')['data']['name'],'Unnamed visitor')
        for branch in ('main','alternate'):
            self.assertEqual(self.e.replay(branch)['records'],sorted(self.e.state(branch),key=lambda r:r['id']))
        self.e.close(); self.e=Engine(self.path)
        self.assertEqual(self.e.get('main','visitor')['data']['name'],'Traveler'); self.assertTrue(self.e.verify()['ok'])

    def test_upgrade_actual_previous_campaign_and_backup(self):
        from kageyoni.resources import fixture_path
        src=fixture_path('recovery/pre-character-v1.sqlite')
        dst=Path(self.temp.name)/'upgrade.sqlite'; shutil.copy2(src,dst)
        old=sqlite3.connect(src); before=old.execute('SELECT id,revision,event_hash FROM events ORDER BY id').fetchall(); old.close()
        e=Engine(dst)
        try:
            self.assertEqual([tuple(r) for r in e.db.execute('SELECT id,revision,event_hash FROM events ORDER BY id')],before)
            self.assertEqual(len(e.state()),165); self.assertTrue(e.verify()['ok'])
            self.assertTrue(Path(str(dst)+'.pre-v5.bak').exists())
        finally: e.close()

    def test_interrupted_migration_rolls_back_and_can_retry(self):
        from kageyoni.resources import fixture_path
        dst=Path(self.temp.name)/'interrupted.sqlite'; shutil.copy2(fixture_path('recovery/pre-character-v1.sqlite'),dst)
        original=Path.read_text
        def broken(path,*args,**kw):
            content=original(path,*args,**kw)
            return content+'\nTHIS IS INVALID SQL;' if path.name=='migration_005.sql' else content
        with patch.object(Path,'read_text',broken):
            with self.assertRaises(sqlite3.Error): Engine(dst)
        c=sqlite3.connect(dst)
        self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='character_identity'").fetchone())
        self.assertIsNone(c.execute('SELECT version FROM migration_checks WHERE version=5').fetchone()); c.close()
        e=Engine(dst); self.assertTrue(e.verify()['ok']); e.close()

    def test_cli_create_read_and_readiness(self):
        request=Path(self.temp.name)/'request.json'; request.write_text(json.dumps(self.request()))
        def cli(operation,data):
            request.write_text(json.dumps(data))
            p=subprocess.run([sys.executable,'-m','kageyoni','--db',str(self.path),operation,'--input',str(request)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr); return json.loads(p.stdout)
        self.assertTrue(cli('character-create',self.request())['committed'])
        self.assertEqual(cli('character-read',dict(character_id='visitor'))['character']['id'],'visitor')
        self.assertTrue(cli('character-readiness',dict(character_id='visitor'))['ready'])

    def test_supersession_cycle_rejected(self):
        characters.create(self.e,**self.request())
        with self.assertRaisesRegex(Rejected,'supersession cycle'):
            self.event([self.aspect('one',phase='ended',supersedes='two'),self.aspect('two',phase='ended',supersedes='one')])
        self.assertIsNone(self.e.get('main','one'))

    def test_temporal_aspect_expiry_and_hidden_clock(self):
        characters.create(self.e,**self.request())
        self.event([create('clock','clock',name='Local',tick=0,unit='hour'),create('location','shore',name='Shore',kind='region'),change('visitor',location='shore'),self.aspect(clock='clock',valid_from=0,valid_until=1),self.aspect('speech','communication','condition',statement='Speaks')])
        self.assertTrue(characters.readiness(self.e,'main','visitor','scene',viewer='visitor')['ready'])
        self.event([change('clock',tick=1)])
        self.assertFalse(characters.readiness(self.e,'main','visitor','scene')['ready'])
        self.event([change('drive',valid_until=3),dict(change('clock',version=2),visibility='gm')])
        self.assertTrue(characters.readiness(self.e,'main','visitor','scene')['ready'])
        self.assertFalse(characters.readiness(self.e,'main','visitor','scene',viewer='visitor')['ready'])

    def test_checksum_mismatch_rejected(self):
        self.e.db.execute("UPDATE migration_checks SET checksum='tampered' WHERE version=5")
        with self.assertRaisesRegex(Rejected,'checksum mismatch'):
            Engine(self.path)

if __name__=='__main__': unittest.main()
