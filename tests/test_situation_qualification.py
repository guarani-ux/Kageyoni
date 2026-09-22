import unittest
from kageyoni.situations.scar import Scar,close_scar
from kageyoni.situations.qualification import connected_family_check,incomplete_genesis_check,contradiction_check

class QualificationTests(unittest.TestCase):
 def test_scar_does_not_close_without_repair_and_controls(self):
  s=Scar("1","x","root",("p",)); self.assertEqual("open",close_scar(s,reprobe_passed=True,positive_control_passed=True).status)
  s=Scar("1","x","root",("p",),"commit:1"); self.assertEqual("open",close_scar(s,reprobe_passed=True,positive_control_passed=False).status)
  self.assertEqual("closed",close_scar(s,reprobe_passed=True,positive_control_passed=True).status)
 def test_all_required_families_connect(self):
  x=connected_family_check(); self.assertEqual({"research","production_brief","campaign","writing","repository_repair","living_world"},set(x)); self.assertTrue(all(not v["unknowns"] for v in x.values()))\n def test_all_required_families_preserve_incomplete_genesis(self):\n  x=incomplete_genesis_check(); self.assertEqual(6,len(x)); self.assertTrue(all(v for v in x.values()))\n def test_connected_contradiction_is_preserved(self):\n  x=contradiction_check(); self.assertTrue(x["contradictions"])

if __name__=="__main__": unittest.main()
