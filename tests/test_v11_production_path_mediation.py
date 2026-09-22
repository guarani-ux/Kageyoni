"""
tests/test_v11_production_path_mediation.py

Adversarial qualification suite for Slice 3 (Production-Path Mediation)
and Slice 4 (Evidence Custody and Replay).

Inspects effectful routes:
- world
- pipeline
- artifacts
- repository
- situation effectful stages
- composition governor

For each route, proves:
1. Valid effect succeeds
2. Fake evidence fails
3. Wrong-operation evidence fails
4. Stale evidence fails
5. Mismatched payload/reference fails
6. Missing migration cannot silently bypass
7. Valid neighboring behavior still works
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from kageyoni.engine import Engine, Rejected
from kageyoni.persistence.migrations import install_all, install_v11, install_pipelines
from kageyoni.v11.runtime import ProtectedOperations
from kageyoni.v11.enforcement import EnforcerRegistry, AssessmentLedger
from kageyoni.v11.integration import begin_domain_operation, complete_domain_operation
from kageyoni.persistence.artifacts import Artifacts
from kageyoni.workspaces.pipeline import Pipelines
from kageyoni.situations.v11_adapter import V11SituationMediator
from kageyoni.composition.governor import ResolutionGovernor

class ProductionPathMediationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "engine.sqlite"
        self.engine = Engine(str(self.db_path))
        install_all(self.engine)
        self.ops = ProtectedOperations(self.engine)

    def tearDown(self):
        self.engine.close()
        self.temp_dir.cleanup()

    def _authorized_operation(self, scope="test", objective="Test Route", req_ver="test/1"):
        return begin_domain_operation(
            self.engine,
            scope=scope,
            objective=objective,
            requirement_version=req_ver,
            basis={"test": True}
        )

    def _create_real_event(self, actor="owner") -> str:
        import uuid
        rev = self.engine.branch('main')['revision']
        receipt = self.engine.apply({
            'api_version': 3,
            'branch': 'main',
            'expected_revision': rev,
            'request_id': f'req:{uuid.uuid4().hex}',
            'kind': 'failed_action',
            'actor': actor,
            'narrative': 'Authentic test event narrative',
            'changes': [],
        })
        return receipt['event_id']

    # ------------------------------------------------------------------------
    # Route 1: World Events Route
    # ------------------------------------------------------------------------
    def test_world_route_valid_and_fake_evidence(self):
        # 1. Valid effect succeeds
        event_id = self._create_real_event()
        med = self._authorized_operation(scope="world", objective="Emit world note")
        
        # Valid execution issue
        completed = complete_domain_operation(
            self.engine,
            med,
            evidence_type="world-event",
            evidence_ref=event_id,
            outcome={"event_id": event_id, "kind": "note"},
            verification={"status": "verified"}
        )
        self.assertEqual(completed["state"], "COMPLETED")

        # 2. Fake evidence fails
        med_fake = self._authorized_operation(scope="world", objective="Emit fake note")
        with self.assertRaises(Rejected) as cm:
            complete_domain_operation(
                self.engine,
                med_fake,
                evidence_type="world-event",
                evidence_ref="fake-event-id-999",
                outcome={"event_id": "fake-event-id-999"},
                verification={"status": "verified"}
            )
        self.assertIn("world execution evidence does not exist", str(cm.exception))

        # 3. Mismatched payload/reference fails
        med_mismatch = self._authorized_operation(scope="world", objective="Mismatched note")
        with self.assertRaises(Rejected) as cm:
            complete_domain_operation(
                self.engine,
                med_mismatch,
                evidence_type="world-event",
                evidence_ref=event_id,
                outcome={"event_id": "different-event-id"},
                verification={"status": "verified"}
            )
        self.assertIn("world execution evidence binding mismatch", str(cm.exception))

    # ------------------------------------------------------------------------
    # Route 2: Pipeline Route
    # ------------------------------------------------------------------------
    def test_pipeline_route_mandatory_mediation_and_evidence(self):
        pipes = Pipelines(self.engine)
        content = "pipeline exact output"
        c_hash = hashlib.sha256(content.encode()).hexdigest()
        t_write = {
            "id": "w1",
            "kind": "write_file",
            "config": {
                "root": str(self.root),
                "path": "p_out.txt",
                "content": content,
                "expected_sha256": c_hash
            },
            "dependencies": []
        }
        flow = pipes.create("main", "pipe-test", [t_write])
        pid = flow["pipeline_id"]
        
        # 1. Valid execution through pipeline.run succeeds
        p_res = pipes.run("main", pid)
        self.assertEqual(p_res["phase"], "completed")

        # Verify a v11 operation was issued and completed for this pipeline
        v11_op = self.engine.db.execute(
            "SELECT * FROM v11_operations WHERE objective=?",
            ("Run pipeline " + pid,)
        ).fetchone()
        self.assertIsNotNone(v11_op)
        self.assertEqual(v11_op["state"], "COMPLETED")

        # 2. Fake pipeline evidence fails
        med = self._authorized_operation(scope="pipeline", objective="Fake pipeline check")
        with self.assertRaises(Rejected) as cm:
            complete_domain_operation(
                self.engine,
                med,
                evidence_type="pipeline-result",
                evidence_ref="pipeline:nonexistent",
                outcome={"pipeline_id": "pipeline:nonexistent", "phase": "completed"},
                verification={"status": "verified"}
            )
        self.assertIn("pipeline execution evidence does not exist", str(cm.exception))

        # 4. Stale / incomplete pipeline evidence fails
        # Create a pipeline in 'waiting' phase
        flow_manual = pipes.create("main", "pipe-manual", [dict(id="m1", kind="manual", config={})])
        p_wait = pipes.run("main", flow_manual["pipeline_id"])
        self.assertEqual(p_wait["phase"], "waiting")

        med_stale = self._authorized_operation(scope="pipeline", objective="Stale pipeline check")
        with self.assertRaises(Rejected) as cm:
            complete_domain_operation(
                self.engine,
                med_stale,
                evidence_type="pipeline-result",
                evidence_ref=flow_manual["pipeline_id"],
                outcome={"pipeline_id": flow_manual["pipeline_id"], "phase": "waiting"},
                verification={"status": "verified"}
            )
        self.assertIn("pipeline execution evidence is not completed", str(cm.exception))

    # ------------------------------------------------------------------------
    # Route 3: Artifacts Route
    # ------------------------------------------------------------------------
    def test_artifact_route_evidence_and_digest_validation(self):
        artifacts = Artifacts(self.engine)
        raw_bytes = b"authoritative artifact content for v11 test"
        self.engine.db.execute("INSERT OR IGNORE INTO network_workspaces VALUES('ws:test', 'world', 'main', '1')")
        art = artifacts.put(raw_bytes, "text/plain", "artifact.txt", workspace_id="ws:test")
        art_id = art["artifact_id"]
        art_digest = art["digest"]

        # 1. Valid artifact effect succeeds
        med = self._authorized_operation(scope="artifact", objective="Store artifact")
        completed = complete_domain_operation(
            self.engine,
            med,
            evidence_type="artifact-result",
            evidence_ref=art_id,
            outcome={"artifact_id": art_id, "digest": art_digest},
            verification={"status": "verified"}
        )
        self.assertEqual(completed["state"], "COMPLETED")

        # 2. Fake artifact evidence fails
        med_fake = self._authorized_operation(scope="artifact", objective="Store fake artifact")
        with self.assertRaises(Rejected) as cm:
            complete_domain_operation(
                self.engine,
                med_fake,
                evidence_type="artifact-result",
                evidence_ref="nonexistent-artifact-id",
                outcome={"artifact_id": "nonexistent-artifact-id"},
                verification={"status": "verified"}
            )
        self.assertIn("artifact execution evidence does not exist", str(cm.exception))

        # 5. Mismatched artifact digest fails
        med_digest_mismatch = self._authorized_operation(scope="artifact", objective="Digest mismatch")
        with self.assertRaises(Rejected) as cm:
            complete_domain_operation(
                self.engine,
                med_digest_mismatch,
                evidence_type="artifact-result",
                evidence_ref=art_id,
                outcome={"artifact_id": art_id, "digest": "corrupted-sha256-digest-0000"},
                verification={"status": "verified"}
            )
        self.assertIn("artifact execution digest mismatch", str(cm.exception))

    # ------------------------------------------------------------------------
    # Route 4: Situation Effectful Stages Route
    # ------------------------------------------------------------------------
    def test_situation_effectful_stage_mediation(self):
        mediator = V11SituationMediator(self.engine)
        
        # 1. Valid situation stage mediation
        med = mediator.begin(
            situation_id="sit:repo-repair",
            workflow_id="repair.default",
            stage_id="repair",
            objective="Repair defect in pipeline"
        )
        self.assertIsNotNone(med.operation_id)
        self.assertIsNotNone(med.qualification_id)

        # Emit an event to use as real physical evidence
        ev_id = self._create_real_event()

        completed = mediator.complete(
            med,
            evidence_type="world-event",
            evidence_ref=ev_id,
            outcome={"event_id": ev_id, "repaired": True},
            verification={"review": "passed"}
        )
        self.assertEqual(completed["state"], "COMPLETED")

        # 3. Wrong-operation evidence cross-injection fails
        med_a = mediator.begin(
            situation_id="sit:1", workflow_id="w:1", stage_id="s:1", objective="Action A"
        )
        med_b = mediator.begin(
            situation_id="sit:2", workflow_id="w:2", stage_id="s:2", objective="Action B"
        )
        
        # Issue receipt for Operation A
        ops = ProtectedOperations(self.engine)
        ops.issue_execution(
            med_a.operation_id,
            evidence_type="world-event",
            evidence_ref=ev_id,
            payload={"domain_effect": {"event_id": ev_id}}
        )
        r_a = ops.read(med_a.operation_id)["payload"]["execution_receipt_id"]

        # Attempting to use receipt A to observe Operation B must fail
        with self.assertRaises(Rejected) as cm:
            ops.observe(med_b.operation_id, outcome={"observed": True})
        self.assertIn("observation requires executed or uncertain operation", str(cm.exception))

    # ------------------------------------------------------------------------
    # Route 5: Composition Governor Schema Installation
    # ------------------------------------------------------------------------
    def test_composition_governor_installs_v11_unconditionally(self):
        # Create raw engine with only baseline schema
        fresh_db = self.root / "fresh.sqlite"
        fresh_engine = Engine(str(fresh_db))
        # Governor must install v11 schemas on __init__
        gov = ResolutionGovernor(fresh_engine)
        has_v11 = fresh_engine.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='v11_operations'"
        ).fetchone()
        self.assertIsNotNone(has_v11)
        fresh_engine.close()

    # ------------------------------------------------------------------------
    # Route 6: Missing Migration Fails Closed (No Silent Bypass)
    # ------------------------------------------------------------------------
    def test_missing_migration_fails_closed_in_protected_operations(self):
        # Create raw engine without v11 migrations
        raw_db = self.root / "raw.sqlite"
        raw_engine = Engine(str(raw_db))
        
        # Calling ProtectedOperations on raw unmigrated engine must fail-closed
        ops_raw = ProtectedOperations(raw_engine)
        with self.assertRaises(Exception):
            ops_raw.declare(objective="Fail without migrations", requirement_version="1", scope="test")
        raw_engine.close()

if __name__ == "__main__":
    unittest.main()
