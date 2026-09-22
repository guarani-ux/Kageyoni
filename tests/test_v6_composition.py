"""Actual destination drafts, transfer checks, immutable bytes and receptions."""
import json
import tempfile
import unittest
from pathlib import Path
from examples.v6_demo import run, make_drafts
from kageyoni.engine import Engine, Rejected, encoded, digest
from kageyoni.application import Application
from kageyoni.intelligence.network import Network
from kageyoni.intelligence.transfer import Transfers
from kageyoni.workspaces.documents import Documents
from kageyoni.workspaces.registry import Registry
from kageyoni.persistence.artifacts import Artifacts




class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'fixture';run(self.root)
        self.e=Engine(self.root/'synthetic.sqlite');self.n=Network(self.e)
        self.drafts,self.workspaces,self.transfers=make_drafts(self.e)
        self.ids=[d['draft_id'] for d in self.drafts]
        self.synthesis={'text':'# Operator compilation\n\n'+'\n\n'.join(d['text'] for d in self.drafts),
                        'uses':[{'draft_id':d['draft_id'],'quote':d['text']} for d in self.drafts],
                        'rationale':'Retain both actual orderings and their differences; no independent quality claim.'}
    def tearDown(self):self.e.close();self.tmp.cleanup()
    def test_actual_destination_bodies_consumed_and_disagreement_preserved(self):
        result=self.n.compose('main','compose',self.workspaces[0],self.ids,self.synthesis)
        self.assertEqual(result['phase'],'completed');self.assertEqual(len(result['bodies']),2)
        self.assertTrue(result['disagreements']);self.assertTrue(all(x['disposition']=='consumed_verbatim' for x in result['receptions']))
        self.assertEqual(Artifacts(self.e).read(result['artifact']['artifact_id'])['content'].decode(),self.synthesis['text'])
        self.assertTrue(self.e.verify()['ok'])
    def test_waiting_packet_keeps_bodies(self):
        r=self.n.compose('main','waiting',self.workspaces[0],self.ids)
        self.assertEqual(r['phase'],'waiting');self.assertIsNone(r['artifact']);self.assertEqual(r['pending']['draft_ids'],self.ids)
    def test_fake_quote_rejected_and_not_committed(self):
        self.synthesis['uses'][0]['quote']='Invented source quotation'
        with self.assertRaises(Rejected):self.n.compose('main','fake',self.workspaces[0],self.ids,self.synthesis)
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM collective_compositions WHERE request_id='fake'").fetchone())
    def test_punctuation_is_not_accepted_as_body_consumption(self):
        self.synthesis['uses'][0]['quote']='.'
        with self.assertRaises(Rejected):self.n.compose('main','punctuation',self.workspaces[0],self.ids,self.synthesis)
    def test_body_omission_rejected(self):
        self.synthesis['uses']=self.synthesis['uses'][:1]
        with self.assertRaises(Rejected):self.n.compose('main','omit',self.workspaces[0],self.ids,self.synthesis)
    def test_same_node_is_not_collective(self):
        with self.assertRaises(Rejected):self.n.compose('main','one',self.workspaces[0],self.ids[:1])
    def test_hidden_draft_scope_rejected(self):
        with self.assertRaises(Rejected):self.n.compose('main','hidden',self.workspaces[0],self.ids,self.synthesis,viewer='speed')
    def test_requalification_requires_new_draft_but_history_survives(self):
        r=self.n.compose('main','before',self.workspaces[0],self.ids,self.synthesis)
        tid=self.transfers[0]
        # An actual completed calculation is expected to have an impossible
        # order; the registered checker records this contradiction as failure.
        source=self.e.db.execute('SELECT report_json FROM transfer_check_runs WHERE transfer_id=?',(tid,)).fetchone()
        self.assertIsNotNone(source)
        documents=Documents(self.e)
        source_value=documents.ingest(self.workspaces[0],'counter-source','counter-source','1 5','counter-fixture','counter-fixture','2026-09-20T00:00:00+00:00')
        def evidence(start):return {'source_id':source_value['source_id'],'revision':source_value['revision'],'digest':source_value['digest'],'start':start,'end':start+1}
        candidates=[{'id':'fast','metrics':{'metric':{'value':1,'evidence':evidence(0)}}},{'id':'careful','metrics':{'metric':{'value':5,'evidence':evidence(2)}}}]
        Transfers(self.e).run_trial(tid,'bad-trial',[{'case_id':'contrary','candidates':candidates,'expected_phase':'completed','expected_order':['careful','fast']},
                                                   {'case_id':'negative','candidates':[{'id':'missing','metrics':{}}],'expected_phase':'blocked','expected_order':[]}])
        with self.assertRaises(Rejected):self.n.compose('main','after',self.workspaces[0],self.ids,self.synthesis)
        self.assertEqual(r,self.n.read_composition('main',r['composition_id']))
    def test_removed_disagreement_detected_even_with_recomputed_hash(self):
        r=self.n.compose('main','tamper',self.workspaces[0],self.ids,self.synthesis)
        r['disagreements']=[]
        self.e.db.execute('DROP TRIGGER collective_compositions_no_update')
        self.e.db.execute('UPDATE collective_compositions SET result_json=?,result_hash=? WHERE composition_id=?',(encoded(r),digest(r),r['composition_id']))
        with self.assertRaises(Rejected):self.e.verify()
    def test_restore_materializes_same_artifact_at_new_location(self):
        r=self.n.compose('main','restore',self.workspaces[0],self.ids,self.synthesis)
        self.e.backup(self.root/'backup.sqlite');Engine.restore(self.root/'backup.sqlite',self.root/'restored.sqlite')
        restored=Engine(self.root/'restored.sqlite')
        try:
            actual=Network(restored).read_composition('main',r['composition_id'])
            self.assertEqual(actual['artifact']['digest'],r['artifact']['digest'])
            self.assertNotEqual(actual['artifact']['path'],r['artifact']['path'])
            self.assertEqual(Path(actual['artifact']['path']).read_text(encoding='utf-8'),self.synthesis['text'])
            self.assertTrue(restored.verify()['ok'])
        finally:restored.close()
    def test_restart_keeps_composition_and_exact_retry(self):
        r=self.n.compose('main','restart',self.workspaces[0],self.ids,self.synthesis)
        self.e.close();self.e=Engine(self.root/'synthetic.sqlite');self.n=Network(self.e)
        self.assertEqual(r,self.n.read_composition('main',r['composition_id']))
        self.assertTrue(self.n.compose('main','restart',self.workspaces[0],self.ids,self.synthesis)['replayed'])
