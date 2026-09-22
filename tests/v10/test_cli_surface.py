import shutil,tempfile,unittest
from pathlib import Path
from kageyoni.engine import Engine
from kageyoni.persistence.migrations import install_composition
from kageyoni.console import dispatch, SERVICES

ROOT=Path(__file__).resolve().parents[2]
class CLISurfaceTests(unittest.TestCase):
  def setUp(self):
    self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/'db.sqlite';shutil.copy2(ROOT/'build/kageyoni.sqlite',self.db)
    self.engine=Engine(self.db);install_composition(self.engine)
  def tearDown(self): self.engine.close();self.tmp.cleanup()
  def test_simulation_service_is_allowlisted(self):
    self.assertIn('simulation',SERVICES)
    result=dispatch(self.engine,{'service':'simulation','action':'frames','arguments':{}})
    self.assertEqual(len(result),2)

  def test_knowledge_service_is_allowlisted_and_ingest_does_not_become_truth(self):
    self.assertIn('knowledge',SERVICES)
    entry=dispatch(self.engine,{'service':'knowledge','action':'ingest','arguments':{'source_type':'report','source_ref':'report://cli','claims':[{'claim':'candidate'}]}})
    self.assertEqual(entry['evidence_status'],'unassessed')
    aspect=dispatch(self.engine,{'service':'knowledge','action':'to_aspect','arguments':{'entry_id':entry['entry_id'],'compatible_slots':['evidence.audience']}})
    self.assertEqual(aspect['authority'],'evidence')
    self.assertEqual(aspect['properties']['evidence_status'],'unassessed')

  def test_simulation_graph_is_available_through_shared_dispatch(self):
    graph=dispatch(self.engine,{'service':'simulation','action':'graph','arguments':{}})
    self.assertEqual(graph['counts']['frames'],2)
    self.assertGreaterEqual(graph['counts']['types'],100)

  def test_compile_scene_through_shared_dispatch(self):
    result=dispatch(self.engine,{'service':'simulation','action':'compile_scene','arguments':{'scene_id':'lucretia-voss-recall-scene','participant_ids':['sciel']}})
    self.assertTrue(result['result']['runnable'])
