import unittest
from kageyoni.situations.memory import SituationMemoryStore,SituationMemory
from kageyoni.situations.long_horizon import run_horizon_trial

class LongHorizonTests(unittest.TestCase):
 def test_four_trajectories_begin_later_from_changed_relevant_state(self):
  for name,template,key in [
   ("story","living_world","relationship:promise"),
   ("research","research","claim:source-gap"),
   ("production","production_brief","audience:ambiguity"),
   ("technical","repository_repair","failure:replay"),
  ]:
   with self.subTest(name=name):
    s=SituationMemoryStore(); obs=run_horizon_trial(s,name,template,key); self.assertTrue(obs.changed_start)
 def test_unrelated_history_does_not_create_false_development(self):
  s=SituationMemoryStore(); s.remember(SituationMemory("other","x","research","x",dependency_keys=("unrelated",)))
  obs=run_horizon_trial(s,"technical","repository_repair","failure:replay")
  self.assertEqual((),obs.first_context); self.assertTrue(obs.changed_start)

if __name__=="__main__": unittest.main()
