import json, unittest
from copy import deepcopy
from pathlib import Path
from kageyoni.composition.compiler import Compiler
from kageyoni.composition.gates import run_gate
DATA=Path(__file__).resolve().parents[2]/'kageyoni'/'composition'/'data'

class GateRegistryTests(unittest.TestCase):
  def fixture(self):
    frame=json.loads((DATA/'narrative_scene.json').read_text());aspects=[];bindings={}
    for slot in frame['slots']:
      if slot['requirement']!='required': continue
      aid='x:'+slot['slot_id'];aspects.append({'aspect_id':aid,'type':slot['accepts'][0],'family':slot['family'],'authority':slot['authority_policy'][0],'compatible_slots':[slot['slot_id']],'provenance':[{'kind':'fixture','ref':aid}]});bindings[slot['slot_id']]=[aid]
    return frame,aspects,bindings
  def test_unknown_declared_gate_fails_closed(self):
    f,a,b=self.fixture();f=deepcopy(f);f['verification'].append('unimplemented_verifier')
    result=Compiler(f,a).compile(b)
    self.assertFalse(result['runnable'])
    self.assertTrue(any(x['slot_id']=='verification:unimplemented_verifier' for x in result['blockers']))
  def test_gate_exception_is_failure(self):
    result=run_gate('does-not-exist',{'slots':[],'unplaced':[]})
    self.assertEqual(result['status'],'fail')
