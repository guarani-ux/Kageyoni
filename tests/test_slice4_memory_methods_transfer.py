"""
tests/test_slice4_memory_methods_transfer.py
Adversarial Verification for Slice 4: Memory, Methods, and Destination Transfer.
"""

from __future__ import annotations
import sqlite3
import unittest

from kageyoni.situations.memory import (
    SituationMemory,
    TransferCandidate,
    create_transfer_from_memory,
    qualify_transfer,
)


class FakeEngineWithDB:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE method_revisions(method_id TEXT, revision INTEGER, digest TEXT)")
        self.db.execute("CREATE TABLE method_transfers(transfer_id TEXT PRIMARY KEY, status TEXT)")


class Slice4MemoryMethodsTransferTests(unittest.TestCase):

    def test_create_transfer_from_memory_provenance(self):
        """Verifies create_transfer_from_memory propagates memory provenance and method references."""
        memory = SituationMemory(
            memory_id="mem_01",
            situation_id="sit_01",
            template_id="research",
            objective="Study literacy",
            workspace_id="ws_origin",
            method_refs=("method:comp_reading",),
        )
        cand = create_transfer_from_memory(
            candidate_id="cand_01",
            source_memory=memory,
            destination_situation_id="sit_dest",
            mapping="direct",
            destination_workspace_id="ws_dest",
            destination_evidence_refs=("event:test_01",),
            method_digest="sha256_legit_digest",
        )
        self.assertEqual(cand.source_memory_id, "mem_01")
        self.assertEqual(cand.source_workspace_id, "ws_origin")
        self.assertEqual(cand.destination_workspace_id, "ws_dest")
        self.assertEqual(cand.method_id, "comp_reading")
        self.assertEqual(cand.method_digest, "sha256_legit_digest")

    def test_target_workspace_checker_blocks_incompatible_destination(self):
        """Verifies qualify_transfer blocks transfer if destination workspace checker rejects target."""
        memory = SituationMemory("mem_02", "sit_02", "research", "Obj", workspace_id="ws_1")
        cand = create_transfer_from_memory(
            candidate_id="cand_02",
            source_memory=memory,
            destination_situation_id="sit_dest",
            mapping="direct",
            destination_workspace_id="restricted_ws",
            destination_evidence_refs=("event:dest_ev",),
        )

        # Target checker returns False for restricted_ws
        res = qualify_transfer(
            cand,
            evidence_resolver=lambda ref, sid: True,
            target_workspace_checker=lambda ws: ws != "restricted_ws",
        )
        self.assertEqual(res.status, "blocked")

    def test_anti_phantom_learning_blocks_fabricated_digest(self):
        """Verifies qualify_transfer blocks transferred methods with fabricated digests or missing authentic backing."""
        engine = FakeEngineWithDB()
        # Insert authentic method into method_revisions
        engine.db.execute("INSERT INTO method_revisions VALUES('m_authentic', 1, 'sha256_valid_digest')")

        memory = SituationMemory("mem_03", "sit_03", "research", "Obj", method_refs=("method:m_authentic",))

        # Case 1: Fabricated digest
        forged_cand = create_transfer_from_memory(
            candidate_id="cand_forged",
            source_memory=memory,
            destination_situation_id="sit_dest",
            mapping="direct",
            destination_evidence_refs=("event:ev1",),
            method_id="m_authentic",
            method_digest="sha256_counterfeit_digest",
        )
        res_forged = qualify_transfer(forged_cand, evidence_resolver=lambda ref, sid: True, engine=engine)
        self.assertEqual(res_forged.status, "blocked")

        # Case 2: Authentic digest matching method_revisions
        valid_cand = create_transfer_from_memory(
            candidate_id="cand_valid",
            source_memory=memory,
            destination_situation_id="sit_dest",
            mapping="direct",
            destination_evidence_refs=("event:ev1",),
            method_id="m_authentic",
            method_digest="sha256_valid_digest",
        )
        res_valid = qualify_transfer(valid_cand, evidence_resolver=lambda ref, sid: True, engine=engine)
        self.assertEqual(res_valid.status, "supported_in_destination")


if __name__ == "__main__":
    unittest.main()
