import json,unittest
from pathlib import Path
from kageyoni.composition.compiler import Compiler
DATA=Path(__file__).resolve().parents[2]/'kageyoni'/'composition'/'data'
class DeficitTests(unittest.TestCase):
  def test_missing_state_becomes_nonautomatic_deficit(self):
    frame=json.loads((DATA/'narrative_scene.json').read_text())
    result=Compiler(frame,[]).compile({})
    self.assertFalse(result['runnable'])
    self.assertTrue(result['deficits'])
    self.assertTrue(all(d['auto_resolve'] is False for d in result['deficits']))
    gov=next(d for d in result['deficits'] if d['target']=='governing.context')
    self.assertIn('acquire_or_validate_evidence',gov['allowed_resolution'])
