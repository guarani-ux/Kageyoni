"""Synthetic minimal SQLite adapters, not Native fixture/event execution."""
from pathlib import Path
from copy import deepcopy
import sqlite3,unittest
from test_facts import Facts
from source_derivation_facts import *

class Projection(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('CREATE TABLE records(branch TEXT,id TEXT,domain TEXT,version INTEGER,status TEXT,visibility TEXT,audience_json TEXT,evidence_json TEXT,updated_event TEXT,PRIMARY KEY(branch,id))')
        self.db.executescript((Path(__file__).parent/'migration_037.sql').read_text())
        factory=Facts();self.v=factory.make(*factory.sample());self.rid=derivation_id(self.v)
    def tearDown(self):self.db.rollback();self.db.close()
    def record(self,rid=None,domain=DOMAIN):
        self.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)',('main',rid or self.rid,domain,1,'confirmed','restricted','["visitor"]','[]','synthetic:model-event'))
    def project(self,v=None,rid=None):self.db.execute('INSERT INTO source_derivation VALUES(?,?,?)',('main',rid or self.rid,canonical(v or self.v)))
    def test_01_model_insert_and_FK_clean(self):
        self.record();self.project();self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(),[])
    def test_02_update_delete_creation_refused(self):
        self.record();self.project()
        for sql in ['UPDATE source_derivation SET contract=contract','DELETE FROM source_derivation','UPDATE records SET version=2','DELETE FROM records']:
            with self.assertRaises(sqlite3.IntegrityError):self.db.execute(sql)
    def test_03_no_unmatched_or_wrong_domain_wrapper(self):
        with self.assertRaises(sqlite3.IntegrityError):self.project()
        with self.assertRaises(sqlite3.IntegrityError):self.record(domain='SOURCE_DERIVATION')
    def test_04_NUL_digest_and_bool_revision_refused(self):
        self.record()
        for mutate in [lambda v:v.update(result_digest=v['result_digest']+'\0x'),lambda v:v.update(revision=True),lambda v:v.update(extra='x')]:
            v=deepcopy(self.v);mutate(v)
            with self.assertRaises(sqlite3.IntegrityError):self.project(v)
    def test_05_missing_output_scope_refused(self):
        self.record()
        for field in ['workspace_id','viewer','artifact_id','media_type','digest','size']:
            v=deepcopy(self.v);del v['output'][field]
            with self.assertRaises(sqlite3.IntegrityError):self.project(v)
    def test_06_wrong_branch_and_audience_refused(self):
        self.record()
        for mutate in [lambda v:v.update(branch='other'),lambda v:v.update(recipient='keeper'),lambda v:v['output'].update(viewer='keeper')]:
            v=deepcopy(self.v);mutate(v)
            with self.assertRaises(sqlite3.IntegrityError):self.project(v)
    def test_07_duplicate_output_and_request_refused(self):
        self.record();self.project();rid='source-derivation:'+'a'*64;self.record(rid=rid)
        v=deepcopy(self.v);v['request_id']='different'
        with self.assertRaises(sqlite3.IntegrityError):self.project(v,rid)
        v=deepcopy(self.v);v['output']['artifact_id']='artifact:different'
        with self.assertRaises(sqlite3.IntegrityError):self.project(v,rid)
    def test_08_alias_prefix_and_extra_projection_refused(self):
        with self.assertRaises(sqlite3.IntegrityError):self.record(rid='SOURCE-DERIVATION:'+'a'*64)
        with self.assertRaises(sqlite3.IntegrityError):self.record(rid=self.rid+'\0x')

if __name__=='__main__':unittest.main(verbosity=2)
