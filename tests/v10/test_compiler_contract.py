import json, unittest
from copy import deepcopy
from pathlib import Path
from kageyoni.composition.compiler import Compiler
from kageyoni.composition.registry import CompositionRegistry

DATA=Path(__file__).resolve().parents[2]/'kageyoni'/'composition'/'data'

class CompilerContractTests(unittest.TestCase):
    def frame(self): return json.loads((DATA/'narrative_scene.json').read_text())
    def fixture(self):
        frame=self.frame();aspects=[];bindings={}
        for slot in frame['slots']:
            if slot['requirement']!='required': continue
            aid='synthetic:'+slot['slot_id'];aspects.append({'aspect_id':aid,'type':slot['accepts'][0],'family':slot['family'],
                'authority':slot['authority_policy'][0],'compatible_slots':[slot['slot_id']], 'properties':{}, 'semantic_key':aid, 'lineage':{'entity_id':'fixture-actor'}, 'provenance':[{'kind':'fixture','ref':slot['slot_id']}]})
            bindings[slot['slot_id']]=[aid]
        
        for z in aspects:
            if z['aspect_id'].endswith('scene.participants'):
                z.setdefault('properties',{})['record_id']='fixture-actor'
        for z in aspects:
            if z['aspect_id'].endswith('governing.context'): z['semantic_key']=z['aspect_id']
            if z.get('type') in {'orientation','capability','trait','knowledge_state','internal_pressure'}: z['lineage']={'entity_id':'fixture-actor'}
            if z['aspect_id'].endswith('scene.participants'): z.setdefault('properties',{})['record_id']='fixture-actor'
        return frame,aspects,bindings
    def test_false_approval_regressions(self):
        frame,aspects,bindings=self.fixture()
        self.assertTrue(Compiler(frame,aspects).compile(bindings)['runnable'])
        a=deepcopy(aspects);b=deepcopy(bindings)
        a.append({'aspect_id':'second','type':'actor','family':'entity','authority':'mechanical','compatible_slots':['scene.participants'],'provenance':[{'kind':'fixture','ref':'second'}]});b['scene.participants'].append('second')
        self.assertFalse(Compiler(frame,a).compile(b)['runnable'])
        a=deepcopy(aspects);b=deepcopy(bindings)
        a.append({'aspect_id':'sit2','type':'situation','family':'situational','authority':'mechanical','compatible_slots':['scene.situation'],'provenance':[{'kind':'fixture','ref':'sit2'}]});b['scene.situation'].append('sit2')
        self.assertFalse(Compiler(frame,a).compile(b)['runnable'])
        a=deepcopy(aspects);b=deepcopy(bindings); next(x for x in a if x['aspect_id']=='synthetic:governing.context')['authority']='host_judgment'
        self.assertFalse(Compiler(frame,a).compile(b)['runnable'])
