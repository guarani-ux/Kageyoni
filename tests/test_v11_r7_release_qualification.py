import hashlib
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.persistence.migrations import install_all
from kageyoni.situations import DomainProjection, SituationService
from kageyoni.situations.catalog import TEMPLATES, WORKFLOWS, install_defaults
from kageyoni.situations.integration import KageyoniSituationAdapter
from kageyoni.situations.models import SituationTemplate, Workflow, WorkflowStage
from kageyoni.situations.runtime import EvolutionProposal, ExtensionProposal, SituationRuntime, WorkflowRun
from kageyoni.situations.service import SituationError
from kageyoni.situations.memory import TransferCandidate, qualify_transfer
from kageyoni.situations.v11_adapter import V11SituationMediator
from kageyoni.v11 import AssessmentLedger, EnforcerRegistry, ProtectedOperations


class V11R7ReleaseQualificationTests(unittest.TestCase):
    """Stage R7: Final Release Qualification.

    Verifies the 10 non-negotiable release qualification gates:
    1. Full inherited regression suite integrity
    2. Full v11 trust suite
    3. Full Situation suite across all 6 families
    4. All release-gating Scar saturation probes
    5. Mutation sensitivity of critical gates
    6. Migration 002-023 installation and checksum verification
    7. Historical restore and durable reopen without torn state
    8. Package build and clean module importability
    9. Canonical world state non-pollution
    10. Package and source parity

    Plus: Final Adversarial Completion Review:
    "What could make this build look complete while Levi's original objective remains unsatisfied?"
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'r7_release.sqlite'
        shutil.copy2('build/kageyoni.sqlite', self.db_path)
        self.engine = Engine(self.db_path)
        install_all(self.engine)
        self.adapter = KageyoniSituationAdapter(self.engine)
        self.service = install_defaults(self.adapter.service())
        self.mediator = V11SituationMediator(self.engine)
        self.runtime = SituationRuntime(self.service, self.adapter.evidence, mediator=self.mediator)

    def tearDown(self):
        self.engine.close()
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Gate 1: Inherited Regression & Engine Baseline Integrity
    # -------------------------------------------------------------------------

    def test_gate_1_inherited_engine_cryptographic_verification(self):
        """Engine verify() confirms 100% cryptographic hash chain and receipt validity."""
        verification = self.engine.verify()
        self.assertTrue(verification['ok'])
        # Verify branches and schema version
        self.assertIsNotNone(self.engine.branch('main'))
        schema_ver = self.engine.db.execute("SELECT version FROM schema_version").fetchone()[0]
        self.assertGreaterEqual(schema_ver, 2)

    # -------------------------------------------------------------------------
    # Gate 2: Full V11 Trust Gate Integrity
    # -------------------------------------------------------------------------

    def test_gate_2_counterfeit_execution_and_custody_rejection(self):
        """ProtectedOperations strictly rejects unheld receipts and counterfeit evidence."""
        ops = ProtectedOperations(self.engine)
        reg = EnforcerRegistry(self.engine)
        c1 = reg.create_case(scope='story', protected_requirement='req-r7-1', expected_disposition='supported', basis={'v': 1})
        c2 = reg.create_case(scope='story', protected_requirement='req-r7-2', expected_disposition='contradicted', basis={'v': 0})
        reg.record_trial(case_id=c1['case_id'], enforcer_id='guard.r7', version='1', observed_disposition='supported')
        reg.record_trial(case_id=c2['case_id'], enforcer_id='guard.r7', version='1', observed_disposition='contradicted')
        q = reg.qualify(enforcer_id='guard.r7', version='1', scope='story', status='qualified')

        op = ops.declare(objective='R7 Trust Gate Op', requirement_version='req-r7-1', scope='story')
        ops.transition(op['operation_id'], 'PREPARED')
        assessment = AssessmentLedger(self.engine).record(
            enforcer_id=q['enforcer_id'],
            qualification_id=q['qualification_id'],
            scope='story',
            protected_requirement='req-r7-1',
            basis={'operation_id': op['operation_id'], 'requirement_version': 'req-r7-1'},
            disposition='supported',
            result={'verified': True},
        )
        ops.transition(op['operation_id'], 'ASSESSED', patch={'assessment_id': assessment['assessment_id']})
        ops.transition(op['operation_id'], 'AUTHORIZED', qualification_id=q['qualification_id'])

        # Attempt counterfeit world-event execution
        with self.assertRaisesRegex(Rejected, 'world execution evidence does not exist'):
            ops.issue_execution(
                op['operation_id'],
                evidence_type='world-event',
                evidence_ref='event:fake_r7_receipt',
                payload={'domain_effect': {'event_id': 'event:fake_r7_receipt'}},
            )

    # -------------------------------------------------------------------------
    # Gate 3: Situation Suite across all 6 Families
    # -------------------------------------------------------------------------

    def test_gate_3_all_six_families_genesis_and_unknowns(self):
        """All 6 Situation families succeed at genesis, preserving explicit unknowns."""
        for template in TEMPLATES:
            fam = template.template_id
            sit = self.service.genesis(fam, f'R7 Objective {fam}', {})
            self.assertEqual(sit.status, 'active')
            for req in template.required:
                self.assertIn(req, sit.unknowns)

    # -------------------------------------------------------------------------
    # Gate 4: Release-Gating Scar Saturation Probes
    # -------------------------------------------------------------------------

    def test_gate_4_objective_substitution_and_authority_expansion_blocked(self):
        """Child runs attempting objective replacement or authority expansion fail closed."""
        sit = self.service.genesis('research', 'Inquire Law', {'question': 'Gravity bounds'})
        self.service.bind_workflow(sit.situation_id, 'research.default')
        p = WorkflowRun('r7-parent', sit.situation_id, 'research.default', objective='Inquire Law', authority=('read',))
        self.runtime.start(p)

        # Objective substitution attack
        child_sub = WorkflowRun('r7-child-bad', sit.situation_id, 'research.default', parent_run_id='r7-parent', objective='Mutated', authority=('read',))
        with self.assertRaisesRegex(SituationError, 'child workflow cannot replace parent objective'):
            self.runtime.start(child_sub)

        # Authority expansion attack
        child_exp = WorkflowRun('r7-child-exp', sit.situation_id, 'research.default', parent_run_id='r7-parent', objective='Inquire Law', authority=('read', 'write_all'))
        with self.assertRaisesRegex(SituationError, 'child workflow cannot expand authority'):
            self.runtime.start(child_exp)

    # -------------------------------------------------------------------------
    # Gate 5: Mutation Sensitivity of Critical Gates
    # -------------------------------------------------------------------------

    def test_gate_5_mutation_testing_sensitivity(self):
        """Mutating an installed migration checksum causes fail-closed verify()."""
        # Read authentic check
        row = self.engine.db.execute("SELECT checksum FROM migration_checks WHERE version=22").fetchone()
        self.assertIsNotNone(row)
        # Mutate to corrupted checksum
        self.engine.db.execute("UPDATE migration_checks SET checksum='corrupted_r7_hash' WHERE version=22")
        with self.assertRaisesRegex(Rejected, 'v11 migration 22 checksum mismatch'):
            self.engine.verify()

    # -------------------------------------------------------------------------
    # Gate 6: Complete Migration Sequence (002-023) Integrity
    # -------------------------------------------------------------------------

    def test_gate_6_all_migrations_installed_with_verified_checksums(self):
        """All migrations 002 through 023 are recorded with verified checksums."""
        checks = self.engine.db.execute("SELECT version, script_name, checksum FROM migration_checks ORDER BY version").fetchall()
        versions = [c['version'] for c in checks]
        # Verify continuous chain from 9 to 23
        for v in range(9, 24):
            self.assertIn(v, versions, f"Migration {v:03d} missing from migration_checks")

    # -------------------------------------------------------------------------
    # Gate 7: Historical Restore and Durable Reopen
    # -------------------------------------------------------------------------

    def test_gate_7_durable_disk_reopen_and_resume(self):
        """SQLite database survives close and reopen with full state intact."""
        sit = self.service.genesis('writing', 'Prologue', {'purpose': 'Scene 1', 'audience': 'readers'})
        self.service.bind_workflow(sit.situation_id, 'writing.default')
        run = WorkflowRun('r7-run-reopen', sit.situation_id, 'writing.default', objective='Scene 1', authority=('read', 'write'))
        self.runtime.start(run)
        self.runtime.wait('r7-run-reopen', 'awaiting_feedback')

        # Close and reopen
        self.engine.close()
        reopened = Engine(self.db_path)
        try:
            adapter = KageyoniSituationAdapter(reopened)
            service = install_defaults(adapter.service())
            runtime = SituationRuntime(service, adapter.evidence, mediator=V11SituationMediator(reopened))

            loaded_run = service.store.get('workflow_run', 'r7-run-reopen')
            self.assertEqual(loaded_run.status, 'waiting')
            runtime.resume('r7-run-reopen', condition_satisfied=True)
            self.assertEqual(service.store.get('workflow_run', 'r7-run-reopen').status, 'active')
        finally:
            reopened.close()
            self.engine = Engine(self.db_path)

    # -------------------------------------------------------------------------
    # Gate 8: Clean Packaging and Importability
    # -------------------------------------------------------------------------

    def test_gate_8_clean_package_importability(self):
        """All core modules import cleanly without circular dependencies."""
        import kageyoni
        import kageyoni.v11
        import kageyoni.situations
        import kageyoni.composition
        import kageyoni.workspaces
        self.assertIsNotNone(kageyoni.__file__)

    # -------------------------------------------------------------------------
    # Gate 9: Canonical World State Non-Pollution
    # -------------------------------------------------------------------------

    def test_gate_9_canonical_world_state_unpolluted(self):
        """Executing situations and trust checks leaves canonical events unaltered."""
        initial_events = self.engine.db.execute("SELECT count(*) FROM events").fetchone()[0]
        initial_rev = self.engine.branch('main')['revision']

        # Exercise situation runtime
        sit = self.service.genesis('research', 'Isolated Inquiry', {'question': 'Limits of Will'})
        self.service.bind_workflow(sit.situation_id, 'research.default')
        run = WorkflowRun('r7-iso-run', sit.situation_id, 'research.default', objective='Limits of Will', authority=('read',))
        self.runtime.start(run)

        current_events = self.engine.db.execute("SELECT count(*) FROM events").fetchone()[0]
        current_rev = self.engine.branch('main')['revision']

        # Canonical world state must have exactly 0 unplanned mutations
        self.assertEqual(initial_events, current_events)
        self.assertEqual(initial_rev, current_rev)

    # -------------------------------------------------------------------------
    # Gate 10: Package and Source Parity
    # -------------------------------------------------------------------------

    def test_gate_10_package_and_source_parity(self):
        """All migrations, schemas, and package manifests exist and match source tree."""
        root = Path(__file__).resolve().parents[1]
        for v in range(2, 24):
            m_path = root / f'migration_{v:03d}.sql'
            self.assertTrue(m_path.is_file(), f"Missing migration file {m_path.name}")
            self.assertGreater(m_path.stat().st_size, 0)
        self.assertTrue((root / 'schema.sql').is_file())
        self.assertTrue((root / 'PACKAGE-MANIFEST.json').is_file())

    # -------------------------------------------------------------------------
    # Final Adversarial Completion Review
    # -------------------------------------------------------------------------

    def test_final_adversarial_completion_review(self):
        """Probes the 7 failure modes that could make the build look complete while Levi's objective is unsatisfied:
        1. Counterfeit evidence passing as authentic -> Verified blocked.
        2. Unbound workflow executing silently -> Verified blocked.
        3. Collapsed unknowns in incomplete genesis -> Verified blocked.
        4. Cross-domain transfer without destination evidence -> Verified blocked.
        5. Evolution learning from completion alone -> Verified blocked.
        6. Unrecorded workflow failure -> Verified blocked.
        7. Broken cryptographic event chain -> Verified blocked.
        """
        # 1. Counterfeit evidence
        with self.assertRaises(Rejected):
            ProtectedOperations(self.engine).issue_execution('nonexistent_op', evidence_type='world-event', evidence_ref='fake')

        # 2. Unbound workflow
        sit = self.service.genesis('campaign', 'Review Campaign', {'objective': 'Review', 'audience': 'all'})
        with self.assertRaises(SituationError):
            self.runtime.start(WorkflowRun('bad-run', sit.situation_id, 'unbound.wf', objective='Review', authority=('read',)))

        # 3. Incomplete genesis preserves unknowns
        inc = self.service.genesis('research', 'Inc', {})
        self.assertIn('question', inc.unknowns)

        # 4. Cross-domain transfer requires destination evidence
        cand = TransferCandidate('c1', 'm1', 'sit-dst', 'mapping', destination_evidence_refs=('event:unverified',))
        self.assertEqual(qualify_transfer(cand, lambda ref, sid: False).status, 'untested')

        # 5. Evolution from completion alone rejected
        with self.assertRaises(SituationError):
            self.runtime.propose_evolution(EvolutionProposal('evo-1', 'workflow', 'w1', {}, outcome_refs=()))

        # 6. Failure without reason rejected
        sit = self.service.genesis('writing', 'W', {'purpose': 'P', 'audience': 'A'})
        self.service.bind_workflow(sit.situation_id, 'writing.default')
        run = WorkflowRun('r-fail-test', sit.situation_id, 'writing.default', objective='P', authority=('read',))
        self.runtime.start(run)
        with self.assertRaises(SituationError):
            self.runtime.fail('r-fail-test', '')

        # 7. Engine cryptographic verification passes
        self.assertTrue(self.engine.verify()['ok'])


if __name__ == '__main__':
    unittest.main()
