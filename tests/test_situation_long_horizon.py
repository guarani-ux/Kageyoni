import unittest
from kageyoni.situations.memory import SituationMemoryStore, SituationMemory
from kageyoni.situations.long_horizon import run_horizon_trial

class LongHorizonTests(unittest.TestCase):
    def test_four_trajectories_change_later_decision_without_claiming_new_capability(self):
        for name,template,key in [
            ("story","living_world","relationship:promise"),
            ("research","research","claim:source-gap"),
            ("production","production_brief","audience:ambiguity"),
            ("technical","repository_repair","failure:replay"),
        ]:
            with self.subTest(name=name):
                store=SituationMemoryStore()
                obs=run_horizon_trial(store,name,template,key)
                self.assertTrue(obs.stored_history)
                self.assertEqual((),obs.first_retrieval)
                self.assertIn(f"{name}:lesson",obs.later_retrieval)
                self.assertTrue(obs.changed_reasoning)
                self.assertTrue(obs.changed_outcome)
                self.assertFalse(obs.changed_capability)

    def test_unrelated_history_does_not_drive_the_initial_decision(self):
        store=SituationMemoryStore()
        store.remember(SituationMemory("other","x","research","x",dependency_keys=("unrelated",)))
        obs=run_horizon_trial(store,"technical","repository_repair","failure:replay")
        self.assertEqual((),obs.first_retrieval)
        self.assertEqual("baseline",obs.first_decision)

if __name__=="__main__":
    unittest.main()
