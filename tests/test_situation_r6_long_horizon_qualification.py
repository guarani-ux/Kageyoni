import json
import tempfile
import unittest
from pathlib import Path

from kageyoni.situations.memory import SituationMemory, SituationMemoryStore
from kageyoni.situations.long_horizon import (
    EncounterStep,
    TrajectoryLedger,
    assess_trajectory,
    run_multi_turn_trajectory,
    export_long_horizon_evidence,
)


def _make_mock_encounter_executor(trajectory_id: str, *, template_id: str = "test", dependency_key: str = "test_key", exercise_capability: bool = True):
    """Deterministic encounter executor for testing trajectory distinction mechanics."""
    def executor(index: int, retrieved: tuple[str, ...], store: SituationMemoryStore) -> EncounterStep:
        if index == 1:
            mid = f"mem:{trajectory_id}:1"
            store.remember(SituationMemory(
                memory_id=mid,
                situation_id=f"sit:{trajectory_id}",
                template_id=template_id,
                objective="test",
                dependency_keys=(dependency_key,),
            ))
            return EncounterStep(
                encounter_index=1,
                context="initial encounter",
                retrieved_memory_ids=retrieved,
                decision="baseline_approach",
                stored_memory_id=mid,
                outcome_observed="baseline_outcome",
                capability_exercised=None,
                evidence_refs=("ev:baseline",),
            )
        elif index == 2:
            return EncounterStep(
                encounter_index=2,
                context="adapted encounter",
                retrieved_memory_ids=retrieved,
                decision="adapted_approach",
                stored_memory_id=None,
                outcome_observed="baseline_outcome",
                capability_exercised=None,
                evidence_refs=("ev:adapted",),
            )
        else:
            return EncounterStep(
                encounter_index=3,
                context="outcome encounter",
                retrieved_memory_ids=retrieved,
                decision="adapted_approach",
                stored_memory_id=None,
                outcome_observed="verified_changed_outcome" if exercise_capability else "baseline_outcome",
                capability_exercised="verified_engine_capability" if exercise_capability else None,
                evidence_refs=("ev:verified",) if exercise_capability else ("ev:baseline",),
            )
    return executor


class SituationR6LongHorizonQualificationTests(unittest.TestCase):
    """Stage R6: Long-Horizon Development Trials Qualification.

    Enforces the physical anti-self-certification invariant:
    - R6 cannot self-certify without an explicit encounter executor.
    - Exporting evidence without an executor factory raises RuntimeError.
    - Invariant: stored history != retrieved history != changed reasoning != changed capability != changed outcome.
    - Storage alone never claims development.
    """

    def setUp(self):
        self.store = SituationMemoryStore()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.evidence_path = Path(self.temp_dir.name) / "r6_long_horizon_trials.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_r6_cannot_self_certify_without_executor(self):
        """Calling run_multi_turn_trajectory without an executor fails closed."""
        with self.assertRaises(RuntimeError) as ctx:
            run_multi_turn_trajectory(self.store, "story", "living_world", "living_world", "relationship:promise", None)
        self.assertIn("R6 is unqualified until an encounter executor supplies observed evidence", str(ctx.exception))

    def test_r6_export_cannot_self_certify_without_executor_factory(self):
        """Calling export_long_horizon_evidence without an executor factory fails closed."""
        with self.assertRaises(RuntimeError) as ctx:
            export_long_horizon_evidence(self.evidence_path, None)
        self.assertIn("R6 is unqualified until real trajectory executors are supplied", str(ctx.exception))

    def test_four_repeated_developmental_trajectories_distinguish_levels(self):
        """All 4 domains distinguish stored history, retrieved history, reasoning, capability, and outcome."""
        trajectories = [
            ("story", "living_world", "living_world", "test_key"),
            ("research", "research", "research", "test_key"),
            ("production", "creative", "production_brief", "test_key"),
            ("technical", "repository", "repository_repair", "test_key"),
        ]
        for t_id, domain, tmpl, key in trajectories:
            with self.subTest(trajectory=t_id):
                store = SituationMemoryStore()
                executor = _make_mock_encounter_executor(t_id, template_id=tmpl, dependency_key=key, exercise_capability=True)
                ledger = run_multi_turn_trajectory(store, t_id, domain, tmpl, key, executor)
                self.assertEqual(len(ledger.encounters), 3)

                # Encounter 1: Empty prior retrieval, baseline decision
                e1 = ledger.encounters[0]
                self.assertEqual(len(e1.retrieved_memory_ids), 0)
                self.assertEqual(e1.decision, "baseline_approach")
                self.assertIsNone(e1.capability_exercised)

                # Encounter 2: Retrieved E1 memory, changed reasoning, but NO new capability
                e2 = ledger.encounters[1]
                self.assertGreater(len(e2.retrieved_memory_ids), 0)
                self.assertNotEqual(e2.decision, e1.decision)
                self.assertIsNone(e2.capability_exercised)

                # Encounter 3: Exercised verified engine capability, resulting in changed outcome
                e3 = ledger.encounters[2]
                self.assertIsNotNone(e3.capability_exercised)
                self.assertEqual(e3.outcome_observed, "verified_changed_outcome")

                # Verify all distinctions are explicitly captured
                d = ledger.distinctions
                self.assertTrue(d["stored_history"])
                self.assertTrue(d["retrieved_history"])
                self.assertTrue(d["changed_reasoning"])
                self.assertTrue(d["changed_capability"])
                self.assertTrue(d["changed_outcome"])
                self.assertTrue(ledger.development_supported)

    def test_storage_alone_does_not_claim_development(self):
        """Storing memories without capability exercise or changed outcome does not claim development."""
        store = SituationMemoryStore()
        executor = _make_mock_encounter_executor("control", template_id="research", dependency_key="test_key", exercise_capability=False)
        ledger = run_multi_turn_trajectory(store, "control", "research", "research", "test_key", executor)
        d = ledger.distinctions
        self.assertTrue(d["stored_history"])
        self.assertTrue(d["retrieved_history"])
        self.assertTrue(d["changed_reasoning"])
        self.assertFalse(d["changed_capability"])
        self.assertFalse(d["changed_outcome"])
        self.assertFalse(ledger.development_supported)
        self.assertTrue(any("Capability change is not established" in u for u in ledger.unqualified_claims))

    def test_export_long_horizon_evidence_package(self):
        """Exports the complete evidence artifact when executor factory is supplied."""
        def factory(t_id, domain, tmpl, key):
            return _make_mock_encounter_executor(t_id, template_id=tmpl, dependency_key=key, exercise_capability=True)

        data = export_long_horizon_evidence(self.evidence_path, factory)
        self.assertTrue(self.evidence_path.exists())
        self.assertEqual(data["summary"]["total_trajectories"], 4)
        self.assertTrue(data["summary"]["verified_development"])


if __name__ == "__main__":
    unittest.main()
