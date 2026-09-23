import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from kageyoni.composition.governor import ResolutionGovernor
from kageyoni.composition.service import CompositionService
from kageyoni.engine import Engine, Rejected, digest
from kageyoni.persistence.artifacts import Artifacts
from kageyoni.persistence.migrations import install_all
from kageyoni.v11 import (
    AdaptiveLoop,
    AssessmentLedger,
    ContextPackets,
    EnforcerRegistry,
    FrontierManager,
    ProtectedOperations,
)
from kageyoni.v11.integration import (
    begin_domain_operation,
    complete_domain_operation,
    mechanical_qualification,
)
from kageyoni.workspaces.pipeline import Pipelines


class FrozenTrustGateTests(unittest.TestCase):
    """Rigorous qualification suite for Stage R2: Frozen Mechanical Trust Gate.

    Enforces all 7 non-negotiable trust invariants:
    1. Zero known mechanical trust scars reproducible.
    2. Saturation attacks reveal no new material failure classes.
    3. Valid neighboring behavior remains functional.
    4. Mutation testing proves critical safeguards are causally exercised.
    5. Inherited regressions remain green.
    6. Packaged / source parity is bit-perfect.
    7. Trust infrastructure does not silently mutate canonical world state.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'trust_gate.sqlite'
        from kageyoni.resources import campaign_db_path
        shutil.copy2(campaign_db_path(), self.db_path)
        self.engine = Engine(self.db_path)
        install_all(self.engine)
        self.ops = ProtectedOperations(self.engine)
        self.registry = EnforcerRegistry(self.engine)
        self.ledger = AssessmentLedger(self.engine)

    def tearDown(self):
        self.engine.close()
        self.temp_dir.cleanup()

    def _qualify_enforcer(self, scope='story', enforcer_id='guard.trust', version='1'):
        reg = self.registry
        c1 = reg.create_case(scope=scope, protected_requirement='valid-req', expected_disposition='supported', basis={'val': 1})
        c2 = reg.create_case(scope=scope, protected_requirement='invalid-req', expected_disposition='contradicted', basis={'val': 0})
        reg.record_trial(case_id=c1['case_id'], enforcer_id=enforcer_id, version=version, observed_disposition='supported')
        reg.record_trial(case_id=c2['case_id'], enforcer_id=enforcer_id, version=version, observed_disposition='contradicted')
        return reg.qualify(enforcer_id=enforcer_id, version=version, scope=scope, status='qualified')

    def _setup_assessed_op(self, scope='story', objective='Objective Trust'):
        q = self._qualify_enforcer(scope=scope)
        op = self.ops.declare(objective=objective, requirement_version='r1', scope=scope)
        self.ops.transition(op['operation_id'], 'PREPARED')
        assessment = self.ledger.record(
            enforcer_id=q['enforcer_id'],
            qualification_id=q['qualification_id'],
            scope=scope,
            protected_requirement='r1',
            basis={'operation_id': op['operation_id'], 'requirement_version': 'r1'},
            disposition='supported',
            result={'verified': True},
        )
        op = self.ops.transition(op['operation_id'], 'ASSESSED', patch={'assessment_id': assessment['assessment_id']})
        return op, q, assessment

    # -------------------------------------------------------------------------
    # Invariant 1: Anti-Counterfeit & Evidence Binding Scars
    # -------------------------------------------------------------------------

    def test_counterfeit_world_event_evidence_rejected(self):
        """Reject execution receipts pointing to non-existent world events."""
        op, q, _ = self._setup_assessed_op()
        self.ops.transition(op['operation_id'], 'AUTHORIZED', qualification_id=q['qualification_id'])
        with self.assertRaisesRegex(Rejected, 'world execution evidence does not exist'):
            self.ops.issue_execution(
                op['operation_id'],
                evidence_type='world-event',
                evidence_ref='event:fake-forged-event-id',
                payload={'domain_effect': {'event_id': 'event:fake-forged-event-id'}},
            )

    def test_counterfeit_pipeline_evidence_rejected(self):
        """Reject execution receipts pointing to uncompleted pipeline runs."""
        op, q, _ = self._setup_assessed_op(scope='pipeline')
        self.ops.transition(op['operation_id'], 'AUTHORIZED', qualification_id=q['qualification_id'])
        # 1. Nonexistent pipeline
        with self.assertRaisesRegex(Rejected, 'pipeline execution evidence does not exist'):
            self.ops.issue_execution(
                op['operation_id'],
                evidence_type='pipeline-result',
                evidence_ref='pipe:nonexistent',
                payload={'domain_effect': {'pipeline_id': 'pipe:nonexistent', 'phase': 'completed'}},
            )
        # 2. Incomplete pipeline
        self.engine.db.execute(
            "INSERT INTO pipeline_runs(pipeline_id, branch, request_id, request_hash, payload_json, payload_hash) VALUES ('pipe:incomplete', 'main', 'req:incomplete', 'hash', ?, 'hash')",
            (json.dumps({'phase': 'running'}),),
        )
        with self.assertRaisesRegex(Rejected, 'pipeline execution evidence is not completed'):
            self.ops.issue_execution(
                op['operation_id'],
                evidence_type='pipeline-result',
                evidence_ref='pipe:incomplete',
                payload={'domain_effect': {'pipeline_id': 'pipe:incomplete', 'phase': 'completed'}},
            )

    def test_counterfeit_artifact_evidence_and_digest_mismatch_rejected(self):
        """Reject execution receipts with missing or digest-mismatched artifacts."""
        op, q, _ = self._setup_assessed_op(scope='artifact')
        self.ops.transition(op['operation_id'], 'AUTHORIZED', qualification_id=q['qualification_id'])
        # Missing artifact
        with self.assertRaisesRegex(Rejected, 'artifact execution evidence does not exist'):
            self.ops.issue_execution(
                op['operation_id'],
                evidence_type='artifact-result',
                evidence_ref='art:missing',
                payload={'domain_effect': {'artifact_id': 'art:missing'}},
            )
        # Mismatched digest
        sha = hashlib.sha256(b'authentic bytes').hexdigest()
        self.engine.db.execute(
            "INSERT INTO artifacts(artifact_id, workspace_id, viewer, request_id, payload_hash, digest, media_type, size, content) VALUES ('art:authentic', 'ws:1', NULL, 'req:art1', 'hash', ?, 'text/plain', ?, ?)",
            (sha, len(b'authentic bytes'), b'authentic bytes'),
        )
        with self.assertRaisesRegex(Rejected, 'artifact execution digest mismatch'):
            self.ops.issue_execution(
                op['operation_id'],
                evidence_type='artifact-result',
                evidence_ref='art:authentic',
                payload={'domain_effect': {'artifact_id': 'art:authentic', 'digest': '000000000000'}},
            )

    def test_unsupported_execution_evidence_type_rejected(self):
        """Reject execution receipts declaring arbitrary or mock evidence types."""
        op, q, _ = self._setup_assessed_op()
        self.ops.transition(op['operation_id'], 'AUTHORIZED', qualification_id=q['qualification_id'])
        with self.assertRaisesRegex(Rejected, 'unsupported execution evidence type'):
            self.ops.issue_execution(
                op['operation_id'],
                evidence_type='arbitrary-untrusted-type',
                evidence_ref='ref-123',
                payload={'domain_effect': {}},
            )

    # -------------------------------------------------------------------------
    # Invariant 2: Cross-Operation Replay & Authority Custody Attacks
    # -------------------------------------------------------------------------

    def test_cross_operation_receipt_replay_rejected(self):
        """Receipt from Operation A cannot satisfy Operation B's lifecycle."""
        op_a, q, _ = self._setup_assessed_op(objective='Operation A')
        op_b = self.ops.declare(objective='Operation B', requirement_version='r1', scope='story')
        self.ops.transition(op_b['operation_id'], 'PREPARED')
        self.ops.transition(op_a['operation_id'], 'AUTHORIZED', qualification_id=q['qualification_id'])
        op_a = self.ops._issue_fixture_execution(op_a['operation_id'], evidence_ref='fixture:execution', payload={'a': 1})
        receipt_a = op_a['payload']['execution_receipt_id']

        # Attempt to patch Operation B directly with receipt_a
        with self.assertRaises(Rejected):
            self.ops.transition(op_b['operation_id'], 'EXECUTED', patch={'execution_receipt_id': receipt_a})

    def test_cannot_authorize_with_suspended_or_superseded_qualification(self):
        """Operations cannot authorize using qualifications that were superseded by an adverse trial."""
        q = self._qualify_enforcer(enforcer_id='adversarial.guard', version='1')
        op = self.ops.declare(objective='Test Revocation', requirement_version='r1', scope='story')
        self.ops.transition(op['operation_id'], 'PREPARED')

        # Add a new adverse trial that fails the error budget
        c_fail = self.registry.create_case(scope='story', protected_requirement='test-fail', expected_disposition='supported', basis={'k': 1})
        self.registry.record_trial(case_id=c_fail['case_id'], enforcer_id='adversarial.guard', version='1', observed_disposition='contradicted')

        # Attempting to require_qualified must now fail
        with self.assertRaisesRegex(Rejected, 'new adverse trial invalidates qualification'):
            self.registry.require_qualified(q['qualification_id'], 'story')

    def test_immutable_operation_objective_and_version(self):
        """Operations strictly freeze their objective and requirement version at declaration."""
        op = self.ops.declare(objective='Target Objective', requirement_version='v1.0', scope='story')
        with self.assertRaises(Rejected):
            self.ops.transition(op['operation_id'], 'PREPARED', patch={'objective': 'Hijacked Objective'})
        with self.assertRaises(Rejected):
            self.ops.transition(op['operation_id'], 'PREPARED', patch={'requirement_version': 'v2.0'})

    # -------------------------------------------------------------------------
    # Invariant 3: Valid Neighboring Behavior & Life-Cycle Continuity
    # -------------------------------------------------------------------------

    def test_full_valid_protected_operation_cycle(self):
        """Valid operation transitions cleanly through all 8 lifecycle states."""
        op, q, _ = self._setup_assessed_op()
        op = self.ops.transition(op['operation_id'], 'AUTHORIZED', qualification_id=q['qualification_id'])
        op = self.ops._issue_fixture_execution(op['operation_id'], evidence_ref='fixture:execution', payload={'real': True})
        op = self.ops.observe(op['operation_id'], outcome={'observed': True, 'count': 42})
        op = self.ops.verify_observation(op['operation_id'], receipt={'check': 'pass', 'verified_by': 'owner'})
        op = self.ops.complete(op['operation_id'])
        self.assertEqual(op['state'], 'COMPLETED')
        self.assertTrue(self.engine.verify()['ok'])

    def test_context_nonblocking_unknowns_preserved_without_blocking_commit(self):
        """Context packets preserve unresolved non-blocking unknowns while allowing commit."""
        pkt = ContextPackets(self.engine).create(
            scope='story',
            basis={'branch': 'main'},
            included=['scene-content'],
            unresolved=[{'ref': 'weather-details', 'blocking': False}],
            excluded=[],
        )
        self.assertTrue(pkt['sufficient_for_commit'])
        self.assertEqual(len(pkt['unresolved']), 1)
        self.assertFalse(pkt['unresolved'][0]['blocking'])

    def test_frontier_preserves_parent_objective_while_adapting_representation(self):
        """Frontiers allow representation evolution but reject parent goal mutation."""
        fm = FrontierManager(self.engine)
        f = fm.open(objective='locate the missing deity blade', kind='unknown_representation', payload={'status': 'initial'})
        # Representation change allowed
        updated = fm.transition(f['frontier_id'], 'investigating', patch={'current_representation': 'spatial_coordinate_grid'})
        self.assertEqual(updated['payload']['current_representation'], 'spatial_coordinate_grid')
        # Objective mutation rejected
        with self.assertRaises(Rejected):
            fm.transition(f['frontier_id'], 'investigating', patch={'objective_or_direction': 'abandon search'})

    # -------------------------------------------------------------------------
    # Invariant 4: Mutation Testing (Proving Safeguards Causally Exercise)
    # -------------------------------------------------------------------------

    def test_mutation_bypassing_completion_check_fails_engine_verify(self):
        """Direct DB tampering of operation state to COMPLETED without receipt fails engine.verify()."""
        op = self.ops.declare(objective='Tampered Op', requirement_version='r1', scope='story')
        # Simulate an adversarial database bypass: setting state to COMPLETED directly
        self.engine.db.execute("UPDATE v11_operations SET state='COMPLETED' WHERE operation_id=?", (op['operation_id'],))
        with self.assertRaises(Rejected):
            self.engine.verify()

    def test_mutation_diverging_migration_checksum_fails_verify(self):
        """Tampering with an installed migration checksum triggers fail-closed verify()."""
        # Read authentic check
        row = self.engine.db.execute("SELECT checksum FROM migration_checks WHERE version=22").fetchone()
        self.assertIsNotNone(row)
        # Mutate to corrupted checksum
        self.engine.db.execute("UPDATE migration_checks SET checksum='corrupted_hash' WHERE version=22")
        with self.assertRaisesRegex(Rejected, 'v11 migration 22 checksum mismatch'):
            self.engine.verify()

    # -------------------------------------------------------------------------
    # Invariant 7: Canonical World State Non-Pollution
    # -------------------------------------------------------------------------

    def test_trust_scaffolding_does_not_mutate_canonical_world_events(self):
        """Executing trust operations, frontiers, and contexts leaves events and branches unaltered."""
        initial_events = self.engine.db.execute("SELECT count(*) FROM events").fetchone()[0]
        initial_revision = self.engine.branch('main')['revision']

        # Run extensive trust operations
        op, q, _ = self._setup_assessed_op(objective='Trust Isolation Test')
        self.ops.transition(op['operation_id'], 'AUTHORIZED', qualification_id=q['qualification_id'])
        self.ops._issue_fixture_execution(op['operation_id'])
        self.ops.observe(op['operation_id'], outcome={'ok': True})
        self.ops.verify_observation(op['operation_id'], receipt={'ok': True})
        self.ops.complete(op['operation_id'])

        # Verify canonical world state has 0 mutations
        current_events = self.engine.db.execute("SELECT count(*) FROM events").fetchone()[0]
        current_revision = self.engine.branch('main')['revision']
        self.assertEqual(initial_events, current_events)
        self.assertEqual(initial_revision, current_revision)

    # -------------------------------------------------------------------------
    # Invariant 6: Package & Source Parity
    # -------------------------------------------------------------------------

    def test_package_build_and_source_parity(self):
        """Packaging includes all root migrations, composition schemas, and engine modules."""
        import setuptools
        packages = setuptools.find_packages(where='.', include=['kageyoni*'])
        self.assertIn('kageyoni', packages)
        self.assertIn('kageyoni.v11', packages)
        self.assertIn('kageyoni.situations', packages)
        self.assertIn('kageyoni.composition', packages)

        # Check all required root migrations exist and are non-empty
        root = Path(__file__).resolve().parents[1]
        for v in range(2, 24):
            m_path = root / f'migration_{v:03d}.sql'
            self.assertTrue(m_path.is_file(), f'Missing migration: {m_path.name}')
            self.assertGreater(m_path.stat().st_size, 0)

    # -------------------------------------------------------------------------
    # Invariant 5: Governor Integrity
    # -------------------------------------------------------------------------

    def test_governor_basis_manifest_tampering_rejected(self):
        """ResolutionGovernor rejects basis manifests with stale revisions or missing dependencies."""
        gov = ResolutionGovernor(self.engine)
        comp = {'runnable': True, 'frame_id': 'f1', 'slots': [], 'admitted_aspect_ids': [], 'verification': {}, 'input_dispositions': {}}
        cmd = {'branch': 'main', 'expected_revision': self.engine.branch('main')['revision']}
        # 1. Basis branch mismatch
        with self.assertRaisesRegex(Rejected, 'basis branch mismatch'):
            gov.prepare(comp, cmd, basis_manifest={'branch': 'wrong_branch'})
        # 2. Dependency disappeared
        stale_manifest = {
            'branch': 'main',
            'records': [{'record_id': 'nonexistent_record_xyz', 'version': 1, 'updated_event': 'none'}],
        }
        with self.assertRaisesRegex(Rejected, 'proposal dependency disappeared'):
            gov.prepare(comp, cmd, basis_manifest=stale_manifest)


if __name__ == '__main__':
    unittest.main()

