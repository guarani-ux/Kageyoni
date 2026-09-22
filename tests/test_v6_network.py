import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from examples.v6_demo import run
from kageyoni.engine import Engine, Rejected
from kageyoni.intelligence.network import Network
from kageyoni.persistence.unit_of_work import UnitOfWork

class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'v6';self.summary=run(self.root)
        self.e=Engine(self.root/'synthetic.sqlite');self.n=Network(self.e)
        self.task=json.loads((self.root/'task.json').read_text())
    def tearDown(self):self.e.close();self.tmp.cleanup()
    def participants(self,*names):return [{'character_id':name,'task':copy.deepcopy(self.task)} for name in names]
    def test_actual_output_and_negative_control(self):self.assertTrue(all(self.summary['controls'].values()))
    def test_source_repetition_is_not_corroboration(self):
        a=self.summary['single'];b=self.summary['repeated']
        self.assertEqual(a['source_ancestry'],b['source_ancestry']);self.assertEqual(b['unique_calculations'],1)
        self.assertEqual(b['independent_corroboration'],'not_established')
        self.assertEqual(b['receptions'][1]['disposition'],'duplicate_calculation')
    def test_idempotency_and_mismatched_retry(self):
        r=self.n.run('main','again',self.participants('speed','checks'))
        self.assertTrue(self.n.run('main','again',self.participants('speed','checks'))['replayed'])
        with self.assertRaises(Rejected):self.n.run('main','again',self.participants('speed'))
    def test_hidden_body_not_returned(self):
        with self.assertRaises(Rejected):self.n.read('main',self.summary['network']['run_id'],viewer='speed')
        self.assertEqual(self.n.list('main',viewer='speed'),[])
    def test_no_participants_is_explicit_block(self):
        r=self.n.run('main','zero',[]);self.assertEqual(r['phase'],'blocked');self.assertIsNone(r['selected'])
    def test_mixed_tasks_rejected(self):
        p=self.participants('speed','checks');p[1]['task']['objective']='different task'
        with self.assertRaises(Rejected):self.n.run('main','different',p)
    def test_duplicate_node_rejected(self):
        with self.assertRaises(Rejected):self.n.run('main','dup',self.participants('speed','speed'))
    def test_atomic_reception_and_contributions(self):
        before=self.e.db.execute('SELECT count(*) FROM contributions').fetchone()[0]
        with self.assertRaises(RuntimeError):
            with UnitOfWork(self.e.db):
                self.n.run('main','abort',self.participants('speed','checks'));raise RuntimeError('crash')
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM collective_runs WHERE request_id='abort'").fetchone())
        self.assertEqual(before,self.e.db.execute('SELECT count(*) FROM contributions').fetchone()[0])
    def test_reopen_and_restore_preserve_receptions(self):
        saved=self.summary['network'];self.e.close();self.e=Engine(self.root/'synthetic.sqlite');self.n=Network(self.e)
        self.assertEqual(saved,self.n.read('main',saved['run_id']))
        self.e.backup(self.root/'backup.sqlite');Engine.restore(self.root/'backup.sqlite',self.root/'restored.sqlite')
        restored=Engine(self.root/'restored.sqlite')
        try:self.assertEqual(saved,Network(restored).read('main',saved['run_id']))
        finally:restored.close()
    def test_immutable_runs_and_tamper_detected(self):
        with self.assertRaises(sqlite3.IntegrityError):self.e.db.execute("UPDATE collective_runs SET result_hash='bad'")
        self.e.db.execute('DROP TRIGGER collective_runs_no_update');self.e.db.execute("UPDATE collective_runs SET result_hash='bad'")
        with self.assertRaises(Rejected):self.e.verify()
    def test_bad_coordination_qualification_rejected(self):
        with self.assertRaises(Rejected):self.n.record_coordination_lesson('main','bad-lesson',self.summary['single']['run_id'],self.summary['network']['run_id'],['z-fast'],'No evidence of benefit','qualified')
    def test_comparison_requires_exact_baseline(self):
        changed=copy.deepcopy(self.task);changed['objective']='Different objective'
        r=self.n.run('main','different-run',[{'character_id':'speed','task':changed}])
        with self.assertRaises(Rejected):self.n.compare('main',r['run_id'],self.summary['network']['run_id'],['a-careful'])
