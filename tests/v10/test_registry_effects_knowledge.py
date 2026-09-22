import shutil,tempfile,unittest
from pathlib import Path
from kageyoni.engine import Engine, Rejected
from kageyoni.persistence.migrations import install_composition
from kageyoni.composition import CompositionRegistry, EffectResolver, ExpressionContract, KnowledgeLedger
from kageyoni.composition.service import CompositionService

ROOT=Path(__file__).resolve().parents[2]

class RegistryEffectsKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/'db.sqlite'
        shutil.copy2(ROOT/'build/kageyoni.sqlite',self.db)
        self.engine=Engine(self.db); install_composition(self.engine)
        self.registry=CompositionRegistry(self.engine)
    def tearDown(self): self.engine.close(); self.tmp.cleanup()

    def test_builtin_type_graph_is_installed_and_frames_remain_distinct(self):
        types=self.registry.list_types()
        self.assertGreaterEqual(len(types),100)
        self.assertEqual(self.registry.type('orientation')['family'],'configuration')
        self.assertEqual({x['frame_id'] for x in self.registry.list_frames()},{'narrative_scene.v1','content_development.v1'})

    def test_registered_aspect_is_typed_and_versioned(self):
        one=self.registry.register_aspect({'aspect_id':'test:guarded-trust','type':'internal_pressure','family':'internal_state',
            'compatible_slots':['actor.internal_state'],'effects':[{'operation':'pressure','target':'expression.disclosure','direction':'decrease','strength':'high'}]})
        two=self.registry.register_aspect({'aspect_id':'test:guarded-trust','type':'internal_pressure','family':'internal_state',
            'compatible_slots':['actor.internal_state'],'effects':[{'operation':'pressure','target':'expression.disclosure','direction':'decrease','strength':'moderate'}]})
        self.assertEqual(one['version'],1); self.assertEqual(two['version'],2)
        with self.assertRaises(Rejected):
            self.registry.register_aspect({'aspect_id':'bad','type':'orientation','family':'evidence'})

    def test_effect_resolver_preserves_opposition_instead_of_averaging(self):
        aspects=[
          {'aspect_id':'trust','provenance':[{'ref':'r1'}],'effects':[{'operation':'pressure','target':'expression.disclosure','direction':'increase','strength':'high'}]},
          {'aspect_id':'betrayal','provenance':[{'ref':'e1'}],'effects':[{'operation':'pressure','target':'expression.disclosure','direction':'decrease','strength':'high'}]},
        ]
        result=EffectResolver().resolve(aspects)
        self.assertEqual(len(result['contributions']),2)
        self.assertEqual(result['conflicts'][0]['target'],'expression.disclosure')
        self.assertEqual(set(result['conflicts'][0]['contributors']),{'trust','betrayal'})

    def test_knowledge_ingestion_remains_evidence_and_route_has_explicit_lifecycle(self):
        ledger=KnowledgeLedger(self.engine)
        entry=ledger.ingest(source_type='report',source_ref='report://one',claims=[{'claim':'X'}],metadata={'title':'One'})
        self.assertEqual(entry['evidence_status'],'unassessed')
        aspect=ledger.to_aspect(entry_id=entry['entry_id'],compatible_slots=['evidence.sources'])
        self.assertEqual(aspect['authority'],'evidence')
        self.assertEqual(aspect['type'],'evidence')
        self.assertNotIn('belief',aspect['properties'])
        route=ledger.route(entry_id=entry['entry_id'],target_ref='sciel',reason='relevant to perception')
        self.assertEqual(route['status'],'ROUTED')
        route=ledger.advance(route_id=route['route_id'],status='ENCOUNTERED',note='read source')
        self.assertEqual(route['status'],'ENCOUNTERED')
        with self.assertRaises(Rejected): ledger.advance(route_id=route['route_id'],status='TRANSFERRED')


    def test_ontology_graph_connects_types_frames_and_slots(self):
        graph=self.registry.graph()
        self.assertGreaterEqual(graph['counts']['types'],100)
        self.assertEqual(graph['counts']['frames'],2)
        self.assertTrue(any(e['kind']=='can_fill' and e['source']=='type:orientation' for e in graph['edges']))

    def test_self_description_exposes_types_and_gates(self):
        cap=CompositionService(self.engine).capabilities()
        self.assertEqual(cap['interface'],'composition/1')
        self.assertGreaterEqual(len(cap['types']),100)
        self.assertIn('required_slots_covered',cap['verification_gates'])

if __name__=='__main__': unittest.main()
