import unittest
from kageyoni.situations.comparative import *
class ComparativeTests(unittest.TestCase):
 def row(self,c,failure=None):
  return ComparativeObservation("t",c,{m:0 for m in METRICS},failure)
 def test_requires_all_metrics(self):
  with self.assertRaises(ValueError): ComparativeLedger().record(ComparativeObservation("t","A",{}))
 def test_preserves_serious_failure_instead_of_averaging_it_away(self):
  l=ComparativeLedger(); l.record(self.row("A","unsupported claim")); self.assertEqual("unsupported claim",l.task("t")[0].serious_failure)
 def test_completeness_requires_all_five_conditions(self):
  l=ComparativeLedger()
  for c in CONDITIONS[:-1]: l.record(self.row(c))
  self.assertFalse(l.completeness("t")); l.record(self.row("E")); self.assertTrue(l.completeness("t"))
if __name__=="__main__": unittest.main()
