import unittest
from kageyoni.situations.memory import SituationMemoryStore, SituationMemory
from kageyoni.situations.long_horizon import (
    EncounterStep,
    assess_trajectory,
    run_multi_turn_trajectory,
)

class LongHorizonTests(unittest.TestCase):
    def test_four_trajectories_change_later_decision_without_claiming_new_capability(self):
        for name,template,key in [
            ("story","living_world","relationship:promise"),
            ("research","research","claim:source-gap"),
            ("production","production_brief","audience:ambiguity"),
            ("technical","repository_repair","failure:replay"),
        ]:
            with self.subTest(name=name):
                store = SituationMemoryStore()
                def executor(index: int, retrieved: tuple[str,...], s: SituationMemoryStore) -> EncounterStep:
                    if index == 1:
                        mid = f"{name}:lesson"
                        s.remember(SituationMemory(mid, "exp", template, name, dependency_keys=(key,)))
                        return EncounterStep(
                            encounter_index=1,
                            context="first",
                            retrieved_memory_ids=retrieved,
                            decision="baseline",
                            stored_memory_id=mid,
                            outcome_observed="outcome-1",
                            capability_exercised=None,
                            evidence_refs=("ev1",),
                        )
                    elif index == 2:
                        return EncounterStep(
                            encounter_index=2,
                            context="second",
                            retrieved_memory_ids=retrieved,
                            decision="adapted",
                            stored_memory_id=None,
                            outcome_observed="outcome-1",
                            capability_exercised=None,
                            evidence_refs=("ev2",),
                        )
                    else:
                        return EncounterStep(
                            encounter_index=3,
                            context="third",
                            retrieved_memory_ids=retrieved,
                            decision="adapted",
                            stored_memory_id=None,
                            outcome_observed="outcome-1",
                            capability_exercised=None,
                            evidence_refs=("ev3",),
                        )

                ledger = run_multi_turn_trajectory(store, name, name, template, key, executor)
                self.assertTrue(ledger.distinctions["stored_history"])
                self.assertEqual((), ledger.encounters[0].retrieved_memory_ids)
                self.assertIn(f"{name}:lesson", ledger.encounters[1].retrieved_memory_ids)
                self.assertTrue(ledger.distinctions["changed_reasoning"])
                self.assertFalse(ledger.distinctions["changed_outcome"])
                self.assertFalse(ledger.distinctions["changed_capability"])

    def test_unrelated_history_does_not_drive_the_initial_decision(self):
        store = SituationMemoryStore()
        store.remember(SituationMemory("other","x","research","x",dependency_keys=("unrelated",)))
        def executor(index: int, retrieved: tuple[str,...], s: SituationMemoryStore) -> EncounterStep:
            return EncounterStep(
                encounter_index=index,
                context="test",
                retrieved_memory_ids=retrieved,
                decision="baseline" if index == 1 else "other",
                stored_memory_id=None,
                outcome_observed="none",
                capability_exercised=None,
            )
        ledger = run_multi_turn_trajectory(store, "technical", "repository", "repository_repair", "failure:replay", executor)
        self.assertEqual((), ledger.encounters[0].retrieved_memory_ids)
        self.assertEqual("baseline", ledger.encounters[0].decision)

if __name__=="__main__":
    unittest.main()
