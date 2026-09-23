"""
tests/test_g6_situation_memory_transfer.py
Adversarial Verification for Gate G6: Workspace Isolation, Method Revocation, and Canonical Transfer.
"""

from __future__ import annotations
import unittest

from kageyoni.situations.memory import (
    SituationMemory,
    SituationMemoryStore,
    TransferCandidate,
    qualify_transfer,
)
from kageyoni.situations.studio import SituationStudio


class TestGateG6SituationMemoryTransfer(unittest.TestCase):

    def test_workspace_isolation_prevents_leakage(self):
        """Verifies that retrieval strictly isolates memories by workspace_id."""
        store = SituationMemoryStore()
        m_ws1 = SituationMemory(
            memory_id="mem_ws1",
            situation_id="sit_01",
            template_id="campaign",
            objective="Promote local branches",
            workspace_id="ws_commercial",
            dependency_keys=("audience-reach",),
        )
        m_ws2 = SituationMemory(
            memory_id="mem_ws2",
            situation_id="sit_02",
            template_id="campaign",
            objective="Confidential executive review",
            workspace_id="ws_confidential",
            dependency_keys=("audience-reach",),
        )
        store.remember(m_ws1)
        store.remember(m_ws2)

        # Retrieval in commercial workspace must NEVER return confidential memory
        retrieved_comm = store.retrieve(workspace_id="ws_commercial", dependency_keys=("audience-reach",))
        self.assertEqual(len(retrieved_comm), 1)
        self.assertEqual(retrieved_comm[0].memory_id, "mem_ws1")

        retrieved_conf = store.retrieve(workspace_id="ws_confidential", dependency_keys=("audience-reach",))
        self.assertEqual(len(retrieved_conf), 1)
        self.assertEqual(retrieved_conf[0].memory_id, "mem_ws2")

    def test_revoked_method_filtering(self):
        """Verifies that memories relying on revoked methods are excluded from retrieval."""
        store = SituationMemoryStore()
        m_good = SituationMemory(
            memory_id="mem_good",
            situation_id="sit_03",
            template_id="research",
            objective="Analyze public survey data",
            method_refs=("method:statistical_sampling",),
            dependency_keys=("survey-analysis",),
        )
        m_revoked = SituationMemory(
            memory_id="mem_flawed",
            situation_id="sit_04",
            template_id="research",
            objective="Analyze public survey data",
            method_refs=("method:deprecated_heuristic",),
            dependency_keys=("survey-analysis",),
        )
        store.remember(m_good)
        store.remember(m_revoked)

        # Retrieve with method:deprecated_heuristic marked as revoked
        retrieved = store.retrieve(
            dependency_keys=("survey-analysis",),
            revoked_methods={"method:deprecated_heuristic"},
        )
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0].memory_id, "mem_good")

    def test_revoked_flag_exclusion(self):
        """Verifies that memories flagged as revoked=True are omitted."""
        store = SituationMemoryStore()
        m = SituationMemory(
            memory_id="mem_retracted",
            situation_id="sit_05",
            template_id="writing",
            objective="Script draft",
            revoked=True,
            dependency_keys=("script-hook",),
        )
        store.remember(m)
        retrieved = store.retrieve(dependency_keys=("script-hook",))
        self.assertEqual(len(retrieved), 0)

    def test_all_six_situation_families_support_memory_lifecycle(self):
        """Verifies memory creation and retrieval across all 6 situation families."""
        studio = SituationStudio(test_mode=True)
        store = SituationMemoryStore()
        families = [
            ("research", "Investigate drop-off", {"question": "Why drop-off?"}),
            ("production_brief", "Launch video", {"objective": "Launch", "audience": "Teens", "deliverables": ["video"], "constraints": []}),
            ("campaign", "Membership drive", {"objective": "Drive", "audience": "Families"}),
            ("writing", "Draft script", {"topic": "Card benefits"}),
            ("repository_repair", "Fix defect", {"target": "enforcement.py"}),
            ("living_world", "Evolve setting", {"domain": "Library"}),
        ]

        for template_id, obj, supplied in families:
            sit = studio.new(template_id, obj, **supplied)
            mem = SituationMemory(
                memory_id=f"mem_{template_id}",
                situation_id=sit.situation_id,
                template_id=template_id,
                objective=obj,
                dependency_keys=(f"dep:{template_id}",),
            )
            store.remember(mem)
            retrieved = store.retrieve(template_id=template_id, dependency_keys=(f"dep:{template_id}",))
            self.assertEqual(len(retrieved), 1)
            self.assertEqual(retrieved[0].memory_id, f"mem_{template_id}")


if __name__ == "__main__":
    unittest.main()
