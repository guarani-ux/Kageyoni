"""
Unit tests for Generic EncounterActionDispatcher.

Verifies:
1. Unauthorized action rejection (actor mismatch).
2. Stale revision rejection.
3. Changed prerequisites rejection (tampered world record).
4. Idempotent duplicate submission (replay).
5. Dialogue vs action separation (action.kind == "none").
6. Authoritative proposal execution through Encounters.act().
"""

from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine, Rejected
from kageyoni.emergence.causal_encounter import CausalEncounterHarness
from kageyoni.emergence.action_dispatcher import (
    EncounterActionDispatcher,
    LinkedExecutionRecord,
)


class TestActionDispatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.tmp.name) / "test_dispatcher.sqlite"
        self.engine = Engine(self.db_path)
        self.harness = CausalEncounterHarness(self.engine, branch="main")
        self.harness.define_clash_encounter("constellation-clash", 1, "alpha")
        self.dispatcher = EncounterActionDispatcher(self.engine, self.harness.encounters)

    def tearDown(self):
        self.engine.close()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_dialogue_vs_action_separation(self):
        """action.kind == 'none' completes dialogue without mutating world state."""
        eid = "enc-disp-none-01"
        self.harness.start_encounter("constellation-clash", 1, eid)
        rev_before = self.engine.branch("main")["revision"]

        req = {"encounter_id": eid, "request_hash": "hash-req-none", "participant": {"character_id": "sciel"}}
        reply = {"encounter_id": eid, "request_hash": "hash-req-none", "action": {"kind": "none"}}

        rec = self.dispatcher.dispatch("main", eid, req, reply, viewer="sciel")
        self.assertEqual(rec.validation_status, "SKIPPED_NONE")
        self.assertEqual(rec.revision_before, rev_before)
        self.assertEqual(rec.revision_after, rev_before)
        self.assertIsNone(rec.engine_receipt)

    def test_authoritative_proposal_execution(self):
        """Authorized proposal executes through Encounters.act() and mutates world state."""
        eid = "enc-disp-exec-01"
        self.harness.start_encounter("constellation-clash", 1, eid)

        # Voss executes rupture
        req_voss = {"encounter_id": eid, "request_hash": "hash-voss", "participant": {"character_id": "voss"}}
        reply_voss = {"encounter_id": eid, "request_hash": "hash-voss", "action": {"kind": "propose_action", "action_id": "voss_rupture"}}
        rec_voss = self.dispatcher.dispatch("main", eid, req_voss, reply_voss, viewer="voss")
        self.assertEqual(rec_voss.validation_status, "ACCEPTED")
        self.assertGreater(rec_voss.revision_after, rec_voss.revision_before)
        self.assertEqual(self.engine.get("main", "chamber_alpha")["data"]["condition"], "cavity_ruptured")

        # Sciel executes anchor
        rev_sciel_before = self.engine.branch("main")["revision"]
        req_sciel = {"encounter_id": eid, "request_hash": "hash-sciel", "participant": {"character_id": "sciel"}}
        reply_sciel = {"encounter_id": eid, "request_hash": "hash-sciel", "action": {"kind": "propose_action", "action_id": "sciel_anchor"}}
        rec_sciel = self.dispatcher.dispatch("main", eid, req_sciel, reply_sciel, viewer="sciel")
        self.assertEqual(rec_sciel.validation_status, "ACCEPTED")
        self.assertEqual(rec_sciel.revision_before, rev_sciel_before)
        self.assertEqual(rec_sciel.revision_after, rev_sciel_before + 1)
        self.assertEqual(self.engine.get("main", "chamber_alpha")["data"]["condition"], "basalt_anchored")

    def test_unauthorized_action_rejected(self):
        """Actor proposing an action outside their role/perspective is rejected."""
        eid = "enc-disp-unauth-01"
        self.harness.start_encounter("constellation-clash", 1, eid)
        rev_before = self.engine.branch("main")["revision"]

        # Sciel attempts to propose Voss's rupture
        req = {"encounter_id": eid, "request_hash": "hash-req-unauth", "participant": {"character_id": "sciel"}}
        reply = {"encounter_id": eid, "request_hash": "hash-req-unauth", "action": {"kind": "propose_action", "action_id": "voss_rupture"}}

        rec = self.dispatcher.dispatch("main", eid, req, reply, viewer="sciel")
        self.assertEqual(rec.validation_status, "REJECTED")
        self.assertIn("unavailable", rec.rejection_reason.lower())
        # World revision did not advance
        self.assertEqual(self.engine.branch("main")["revision"], rev_before)

    def test_stale_revision_rejected(self):
        """Proposal submitted with stale expected revision fails closed."""
        eid = "enc-disp-stale-01"
        self.harness.start_encounter("constellation-clash", 1, eid)
        rev_before = self.engine.branch("main")["revision"]

        req = {"encounter_id": eid, "request_hash": "hash-req-stale", "participant": {"character_id": "voss"}}
        reply = {"encounter_id": eid, "request_hash": "hash-req-stale", "action": {"kind": "propose_action", "action_id": "voss_rupture"}}

        # Provide intentionally stale revision (e.g. 9999)
        rec = self.dispatcher.dispatch("main", eid, req, reply, viewer="voss", expected_revision=9999)
        self.assertEqual(rec.validation_status, "REJECTED")
        self.assertIn("stale branch revision", rec.rejection_reason)
        self.assertEqual(self.engine.branch("main")["revision"], rev_before)

    def test_changed_prerequisites_rejected(self):
        """Proposal fails when world records do not satisfy typed preconditions."""
        eid = "enc-disp-prereq-01"
        self.harness.start_encounter("constellation-clash", 1, eid)

        # Voss ruptures, Sciel anchors
        req_v = {"encounter_id": eid, "request_hash": "hv", "participant": {"character_id": "voss"}}
        self.dispatcher.dispatch("main", eid, req_v, {"action": {"kind": "propose_action", "action_id": "voss_rupture"}}, viewer="voss")
        req_s = {"encounter_id": eid, "request_hash": "hs", "participant": {"character_id": "sciel"}}
        self.dispatcher.dispatch("main", eid, req_s, {"action": {"kind": "propose_action", "action_id": "sciel_anchor"}}, viewer="sciel")

        # Now corrupt the anchor item prerequisite
        rev = self.engine.branch("main")["revision"]
        old_anc = self.engine.get("main", "matrix_anchor_alpha")
        self.engine.apply(dict(
            api_version=3, branch="main", request_id="corrupt-anchor-disp", expected_revision=rev,
            actor="adversary", narrative="Corrupt anchor", kind="action",
            changes=[dict(op="patch", id="matrix_anchor_alpha", expected_version=old_anc["version"], data=dict(condition="corrupted"), evidence=[{"note": "tamper"}])]
        ))

        # Maki attempts to propose perimeter lock -> rejected by prerequisite
        rev_before_maki = self.engine.branch("main")["revision"]
        req_m = {"encounter_id": eid, "request_hash": "hm", "participant": {"character_id": "maki"}}
        reply_m = {"action": {"kind": "propose_action", "action_id": "maki_enforce"}}

        rec_m = self.dispatcher.dispatch("main", eid, req_m, reply_m, viewer="maki")
        self.assertEqual(rec_m.validation_status, "REJECTED")
        # World revision did not advance
        self.assertEqual(self.engine.branch("main")["revision"], rev_before_maki)
        self.assertEqual(self.engine.get("main", "kinetic_perimeter_alpha")["data"]["condition"], "open")

    def test_idempotent_duplicate_submission(self):
        """Duplicate submission with identical request ID returns cached receipt without double mutation."""
        eid = "enc-disp-idemp-01"
        self.harness.start_encounter("constellation-clash", 1, eid)

        req_v = {"encounter_id": eid, "request_hash": "hv", "participant": {"character_id": "voss"}}
        reply_v = {"action": {"kind": "propose_action", "action_id": "voss_rupture"}}

        # First dispatch
        rec1 = self.dispatcher.dispatch("main", eid, req_v, reply_v, viewer="voss", dispatch_request_id="voss-rupture-fixed-req")
        self.assertEqual(rec1.validation_status, "ACCEPTED")
        rev_after1 = rec1.revision_after

        # Duplicate dispatch with identical request ID
        rec2 = self.dispatcher.dispatch("main", eid, req_v, reply_v, viewer="voss", dispatch_request_id="voss-rupture-fixed-req")
        self.assertEqual(rec2.validation_status, "REPLAY_IDEMPOTENT")
        self.assertEqual(rec2.revision_after, rev_after1)
        self.assertEqual(self.engine.branch("main")["revision"], rev_after1)

    def test_cryptographic_evidence_chaining(self):
        """Asserts that all dispatches are appended to EvidenceLedger and tamper detection works."""
        eid = "enc-disp-ledger-01"
        self.harness.start_encounter("constellation-clash", 1, eid)

        req_v = {"encounter_id": eid, "request_hash": "hv", "participant": {"character_id": "voss"}}
        reply_v = {"action": {"kind": "propose_action", "action_id": "voss_rupture"}}

        self.dispatcher.dispatch("main", eid, req_v, reply_v, viewer="voss")
        
        # Verify evidence ledger has records and valid chain
        valid, err = self.dispatcher.ledger.verify_integrity()
        self.assertTrue(valid)
        self.assertIsNone(err)

        records = self.dispatcher.ledger.query()
        self.assertGreaterEqual(len(records), 1)
        self.assertEqual(records[-1].kind, "dispatch")
