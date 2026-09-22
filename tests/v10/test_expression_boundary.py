import unittest
from kageyoni.composition.effects import ExpressionVerifier
class ExpressionBoundaryTests(unittest.TestCase):
 def compilation(self): return {'slots':[{'slot_id':'actor.epistemic','status':'FILLED','aspect_ids':['knowledge:1']}]}
 def test_canonical_claim_requires_compiled_support(self):
  v=ExpressionVerifier();self.assertFalse(v.verify(self.compilation(),[{'kind':'canonical','text':'past abandonment'}])['passed'])
  self.assertFalse(v.verify(self.compilation(),[{'kind':'canonical','evidence_refs':['knowledge:other']}])['passed'])
  self.assertTrue(v.verify(self.compilation(),[{'kind':'canonical','evidence_refs':['knowledge:1']}])['passed'])
 def test_expression_remains_open_and_scope_is_honest(self):
  r=ExpressionVerifier().verify(self.compilation(),[{'kind':'expressive','text':'she hesitates'}]);self.assertTrue(r['passed']);self.assertIn('does not certify',r['scope'])
