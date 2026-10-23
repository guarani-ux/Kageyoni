"""Unit verification suite for the Ninshū Definitive Guide Worked Encounters.

Ensures every operational claim and recipe in docs/NINSHU_DEFINITIVE_GUIDE.md
and tools/ninshu_worked_encounters.py remains reproducible by a cold-start agent.
"""
from __future__ import annotations

import unittest

from tools.ninshu_worked_encounters import (
    encounter_1_single_channel_and_entrypoint_check,
    encounter_2_multi_channel_composition,
    encounter_3_opposing_pressures_and_console,
    encounter_4_refusal_and_deficit_classification,
    encounter_5_cold_process_persistence_and_recovery,
)


class TestNinshuWorkedEncounters(unittest.TestCase):
    def test_encounter_1_single_channel_and_entrypoint_check(self) -> None:
        res = encounter_1_single_channel_and_entrypoint_check()
        self.assertEqual(res["executed_entrypoint"], "ElfBinaryParser.parse_bytes")
        self.assertEqual(res["elf_machine"], "x86-64")
        self.assertTrue(res["elf_is_64_bit"])
        self.assertEqual(res["elf_entry"], "0x401000")
        self.assertTrue(res["thermodynamic_passed"])
        self.assertLessEqual(res["peak_memory_bytes"], 64 * 1024)

    def test_encounter_2_multi_channel_composition(self) -> None:
        res = encounter_2_multi_channel_composition()
        self.assertEqual(res["asar_files_extracted"], ["main.js", "preload.js"])
        self.assertEqual(len(res["ipc_findings"]), 2)
        self.assertEqual(res["ipc_findings"][0]["risk_level"], "CRITICAL")
        self.assertEqual(len(res["secrets_detected"]), 1)
        self.assertEqual(res["secrets_detected"][0]["rule_id"], "SEC003_GITHUB_PAT_CLASSIC")
        self.assertTrue(res["provenance_digests_valid"])
        self.assertEqual(res["provenance_topological_order"][0], "bundle.asar")

    def test_encounter_3_opposing_pressures_and_console(self) -> None:
        res = encounter_3_opposing_pressures_and_console()
        self.assertEqual(res["static_call_target"], "0x401100")
        self.assertEqual(res["dynamic_call_target"], "0x409990")
        self.assertEqual(res["conflicts_preserved_count"], 1)
        conflict = res["conflicts_preserved"][0]
        self.assertEqual(conflict["target"], "direct_call_assumption_0x401000")
        self.assertEqual(conflict["directions"], ["activate", "suppress"])
        self.assertEqual(len(res["master_sha256"]), 64)

    def test_encounter_4_refusal_and_deficit_classification(self) -> None:
        res = encounter_4_refusal_and_deficit_classification()
        self.assertTrue(res["tier1_requires_human_gate"])
        self.assertEqual(res["tier1_reversibility_tier"], 1)
        self.assertFalse(res["naive_zero_confidence_failure_survived"])
        self.assertTrue(res["properly_scored_failure_survived"])
        self.assertFalse(res["compilation_runnable"])
        self.assertEqual(len(res["compiler_emitted_deficits"]), 2)

    def test_encounter_5_cold_process_persistence_and_recovery(self) -> None:
        res = encounter_5_cold_process_persistence_and_recovery()
        self.assertTrue(res["parent_pid_differs_from_child"])
        self.assertEqual(res["writer_revision"], 1)
        fresh = res["fresh_process_receipt"]
        self.assertTrue(fresh["engine_verified_ok"])
        self.assertEqual(fresh["persisted_record_id"], "auditor_daimon")
        self.assertEqual(fresh["save_state_world_id"], "ninshu_audit_world")
        self.assertEqual(fresh["save_state_revision"], 1)


if __name__ == "__main__":
    unittest.main()
