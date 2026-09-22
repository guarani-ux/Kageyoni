import json, unittest
from copy import deepcopy
from pathlib import Path
from kageyoni.composition.compiler import Compiler
DATA=Path(__file__).resolve().parents[2]/'kageyoni'/'composition'/'data'

class CompilerMetamorphicTests(unittest.TestCase):
    def fixture(self):
        frame=json.loads((DATA/'narrative_scene.json').read_text());aspects=[];bindings={}
        for slot in frame['slots']:
            if slot['requirement']!='required': continue
            aid='m:'+slot['slot_id'];aspects.append({'aspect_id':aid,'type':slot['accepts'][0],'family':slot['family'],'authority':slot['authority_policy'][0],
                'compatible_slots':[slot['slot_id']],'provenance':[{'kind':'fixture','ref':aid}]});bindings[slot['slot_id']]=[aid]
        for z in aspects:
            if z['aspect_id'].endswith('governing.context'): z['semantic_key']=z['aspect_id']
            if z.get('type') in {'orientation','capability','trait','knowledge_state','internal_pressure'}: z['lineage']={'entity_id':'fixture-actor'}
            if z['aspect_id'].endswith('scene.participants'): z.setdefault('properties',{})['record_id']='fixture-actor'
        return frame,aspects,bindings
    @staticmethod
    def semantic(result):
        return {'runnable':result['runnable'],'slots':{s['slot_id']:s['status'] for s in result['slots']},
                'gates':{g['gate']:g['status'] for g in result['verification']['gates']}}
    def test_aspect_and_binding_order_do_not_change_semantics(self):
        f,a,b=self.fixture();base=self.semantic(Compiler(f,a).compile(b))
        a=list(reversed(a)); b={k:list(reversed(v)) for k,v in reversed(list(b.items()))}
        self.assertEqual(self.semantic(Compiler(f,a).compile(b)),base)
    def test_valid_optional_pressure_is_neutral_to_runnability(self):
        f,a,b=self.fixture();base=Compiler(f,a).compile(b);self.assertTrue(base['runnable'])
        a=deepcopy(a);b=deepcopy(b)
        a.append({'aspect_id':'m:pressure','type':'internal_pressure','family':'internal_state','authority':'derived',
                  'compatible_slots':['actor.internal_state'],'lineage':{'entity_id':'fixture-actor'},'provenance':[{'kind':'fixture','ref':'pressure'}]})
        b['actor.internal_state']=['m:pressure']
        enriched=Compiler(f,a).compile(b)
        self.assertTrue(enriched['runnable'])
        self.assertEqual(next(s for s in enriched['slots'] if s['slot_id']=='actor.internal_state')['status'],'FILLED')
    def test_json_roundtrip_does_not_change_semantics(self):
        f,a,b=self.fixture();base=self.semantic(Compiler(f,a).compile(b))
        f2=json.loads(json.dumps(f));a2=json.loads(json.dumps(a));b2=json.loads(json.dumps(b))
        self.assertEqual(self.semantic(Compiler(f2,a2).compile(b2)),base)
