import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from kageyoni.engine import Engine, Rejected
from kageyoni.persistence.artifacts import Artifacts
from kageyoni.persistence.migrations import install_all
from kageyoni.situations import DomainProjection, SituationService
from kageyoni.situations.catalog import TEMPLATES, WORKFLOWS, install_defaults
from kageyoni.situations.integration import KageyoniSituationAdapter
from kageyoni.situations.memory import (
    SituationMemory,
    SituationMemoryStore,
    TransferCandidate,
    qualify_transfer,
)
from kageyoni.situations.models import (
    Situation,
    SituationTemplate,
    Workflow,
    WorkflowStage,
)
from kageyoni.situations.runtime import (
    EvolutionProposal,
    ExtensionProposal,
    SituationRuntime,
    WorkflowRun,
)
from kageyoni.situations.scar import Scar, close_scar
from kageyoni.situations.service import SituationError
from kageyoni.situations.v11_adapter import V11SituationMediator


class SituationR4ScarSaturationTests(unittest.TestCase):
    """Stage R4: Adversarial Scar Saturation across the Integrated Architecture.

    Exhaustively attacks:
    1. Template contamination and schema explosion.
    2. Workflow deadlock, objective substitution, and authority expansion.
    3. Context leakage and disappearing obligations.
    4. Domain stereotype drift, unsupported projection, and homogenization.
    5. Unnecessary participant recruitment and fake synthesis.
    6. Stale, replayed, cross-operation, or counterfeit evidence.
    7. False workflow/template learning from completion alone.
    8. Cross-domain false transfer.
    9. Completion without meaningful result.
    10. Resume / recovery failure modes.
    11. Metamorphic / decisive fact variations and mutation sensitivity.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'situation_r4.sqlite'
        shutil.copy2('build/kageyoni.sqlite', self.db_path)
        self.engine = Engine(self.db_path)
        install_all(self.engine)
        self.adapter = KageyoniSituationAdapter(self.engine)
        self.service = install_defaults(self.adapter.service())
        self.mediator = V11SituationMediator(self.engine)
        self.runtime = SituationRuntime(self.service, self.adapter.evidence, mediator=self.mediator)
        self.memory = SituationMemoryStore(self.service.store)

    def tearDown(self):
        self.engine.close()
        self.temp_dir.cleanup()

    def _create_real_event(self, actor: str = 'adversary', narrative: str = 'Adversarial trial') -> str:
        rev = self.engine.branch('main')['revision']
        receipt = self.engine.apply({
            'api_version': 3,
            'branch': 'main',
            'expected_revision': rev,
            'request_id': f'req:r4:{uuid.uuid4().hex}',
            'kind': 'failed_action',
            'actor': actor,
            'narrative': narrative,
            'changes': [],
        })
        return receipt['event_id']

    def _insert_method(self, character_id: str, method_id: str, node_id: str = 'node-r4'):
        self.engine.db.execute("PRAGMA foreign_keys=OFF")
        self.engine.db.execute(
            """INSERT OR REPLACE INTO method_revisions(method_id, revision, node_id, branch, workspace_id, world_revision, definition_json, source_refs_json, snapshots_json, source_digest, digest, request_id)
               VALUES(?, 1, ?, 'main', 'main', 0, '{}', '[]', '[]', 'd1', 'd2', ?)""",
            (method_id, node_id, f'req:m:{method_id}'),
        )
        self.engine.db.execute(
            """INSERT OR REPLACE INTO node_method_assignments(node_id, method_id, method_revision, branch, workspace_id, assignment_revision, qualification, rationale, world_revision, method_digest, digest, request_id)
               VALUES(?, ?, 1, 'main', 'main', 1, 'experimental', 'test', 0, 'd1', 'd2', ?)""",
            (node_id, method_id, f'req:nma:{node_id}:{method_id}'),
        )
        self.engine.db.execute(
            """INSERT OR REPLACE INTO node_bindings(node_id, workspace_id, branch, character_id, profile_revision, source_json)
               VALUES(?, 'main', 'main', ?, 1, '{}')""",
            (node_id, character_id),
        )

    # -------------------------------------------------------------------------
    # Attack 1: Template Contamination & Schema Explosion
    # -------------------------------------------------------------------------

    def test_attack_template_contamination_and_unsupported_evolution(self):
        """Attacking template evolution with unverified claims or non-existent outcomes is blocked."""
        sit = self.service.genesis('research', 'Investigate Void', {'question': 'Void stability'})
        ext = ExtensionProposal('ext-void', sit.situation_id, 'concept', {'name': 'VoidRift'}, scope='local')
        self.runtime.propose_extension(ext)

        # Attack 1A: Promote extension without repeated evidence (<2 outcome refs) -> Rejected
        with self.assertRaisesRegex(SituationError, 'promotion requires repeated consequential evidence'):
            self.runtime.promote_extension('ext-void', ('event:single_claim',))

        # Attack 1B: Promote with counterfeit/unverified event references -> Rejected
        with self.assertRaisesRegex(SituationError, 'promotion evidence must resolve through engine custody'):
            self.runtime.promote_extension('ext-void', ('event:fake_1', 'event:fake_2'))

        # Positive Neighbor Control: Two real engine-held events allow qualified evolution proposal
        ev1 = self._create_real_event('researcher', 'Outcome trial 1')
        ev2 = self._create_real_event('researcher', 'Outcome trial 2')
        evo = self.runtime.promote_extension('ext-void', (f'event:{ev1}', f'event:{ev2}'))
        self.assertEqual(evo.status, 'qualified')
        self.assertEqual(evo.target_type, 'template')

    # -------------------------------------------------------------------------
    # Attack 2: Workflow Deadlock, Objective Substitution & Authority Expansion
    # -------------------------------------------------------------------------

    def test_attack_workflow_objective_substitution_and_authority_expansion(self):
        """Attacks attempting to replace parent objectives or elevate authority in child runs fail closed."""
        sit = self.service.genesis('campaign', 'Fleet Strike', {'objective': 'Coordinate vanguard', 'audience': 'navy'})
        self.service.bind_workflow(sit.situation_id, 'campaign.default')
        parent = WorkflowRun('run-parent', sit.situation_id, 'campaign.default', objective='Coordinate vanguard', authority=('read', 'report'))
        self.runtime.start(parent)

        # Attack 2A: Substituted objective in nested child run
        child_sub = WorkflowRun('child-sub', sit.situation_id, 'campaign.default', parent_run_id='run-parent', objective='Hijacked Target', authority=('read',))
        with self.assertRaisesRegex(SituationError, 'child workflow cannot replace parent objective'):
            self.runtime.start(child_sub)

        # Attack 2B: Authority expansion in nested child run (adding write and admin)
        child_exp = WorkflowRun('child-exp', sit.situation_id, 'campaign.default', parent_run_id='run-parent', objective='Coordinate vanguard', authority=('read', 'write', 'admin'))
        with self.assertRaisesRegex(SituationError, 'child workflow cannot expand authority'):
            self.runtime.start(child_exp)

        # Attack 2C: Starting run with unbound workflow id
        unbound_run = WorkflowRun('unbound-run', sit.situation_id, 'unbound.wf', objective='Coordinate vanguard', authority=('read',))
        with self.assertRaisesRegex(SituationError, 'workflow not bound to situation'):
            self.runtime.start(unbound_run)

        # Positive Neighbor Control: Valid child preserving objective and narrowing authority succeeds
        child_valid = WorkflowRun('child-legit', sit.situation_id, 'campaign.default', parent_run_id='run-parent', objective='Coordinate vanguard', authority=('read',))
        self.runtime.start(child_valid)
        self.assertEqual(self.runtime._run('child-legit').status, 'active')

    # -------------------------------------------------------------------------
    # Attack 3: Missing Stage Dependencies & Premature Completion
    # -------------------------------------------------------------------------

    def test_attack_stage_completion_without_prerequisites_or_evidence(self):
        """Attacking stage advancement without declared prerequisites or engine evidence is rejected."""
        sit = self.service.genesis('research', 'Investigate Steel', {'question': 'Formula for steel'})
        self.service.bind_workflow(sit.situation_id, 'research.default')
        run = WorkflowRun('run-stg', sit.situation_id, 'research.default', objective='Formula for steel', authority=('read',))
        self.runtime.start(run)

        # research.default stages: question -> evidence -> contradictions -> synthesis
        # Attack 3A: Attempting to complete 'evidence' without completing 'question'
        ev = self._create_real_event('tester', 'Evidence attempt')
        with self.assertRaisesRegex(SituationError, 'stage dependency incomplete'):
            self.runtime.complete_stage('run-stg', 'evidence', f'event:{ev}')

        # Attack 3B: Attempting to complete 'question' with fake evidence
        with self.assertRaisesRegex(SituationError, 'stage completion requires engine-resolved evidence'):
            self.runtime.complete_stage('run-stg', 'question', 'event:unverified-fake-evidence')

        # Positive Neighbor Control: Completing 'question' with real engine event succeeds
        self.runtime.complete_stage('run-stg', 'question', f'event:{ev}')
        self.assertIn('question', self.runtime._run('run-stg').completed_stages)

    # -------------------------------------------------------------------------
    # Attack 4: Domain Stereotype Drift, Borrowing & Homogenization
    # -------------------------------------------------------------------------

    def test_attack_unsupported_domain_projection_and_identity_theft(self):
        """Domain projections must be causally grounded in participant state, rejecting borrowed identity."""
        sit = self.service.genesis('living_world', 'Tavern Confrontation', {'scene': 'Tavern', 'participants': ['sciel', 'alexandra']})

        # Authentic method assigned to sciel only
        self._insert_method('sciel', 'stealth', 'node-sciel-stealth')

        # Attack 4A: Alexandra attempts to claim sciel's stealth method
        proj_theft = DomainProjection('p-theft', 'alexandra', sit.situation_id, ('shadows',), ('intent',), method_refs=('method:stealth',))
        with self.assertRaises(SituationError):
            self.service.propose_projection(proj_theft, established_refs={'method:stealth'})

        # Positive Neighbor Control: Sciel legitimately projects own method
        proj_valid = DomainProjection('p-sciel', 'sciel', sit.situation_id, ('shadows',), ('intent',), method_refs=('method:stealth',))
        self.service.propose_projection(proj_valid, established_refs={'method:stealth'})
        self.assertIn('p-sciel', self.service.projections)

    def test_attack_domain_homogenization_detection(self):
        """Identical foreground projections across participants trigger redundancy detection."""
        sit = self.service.genesis('living_world', 'War Council', {'scene': 'Council', 'participants': ['sciel', 'kenway']})
        p1 = DomainProjection('p-lead', 'sciel', sit.situation_id, ('tactics', 'map'), ('q1',))
        p2 = DomainProjection('p-clone', 'kenway', sit.situation_id, ('tactics', 'map'), ('q2',))

        self.service.store.put('projection', 'p-lead', p1)
        self.service.store.put('projection', 'p-clone', p2)

        collision = self.runtime.collide(['p-lead', 'p-clone'])
        # Fully overlapping foreground must be marked redundant
        self.assertTrue(collision['redundant'])
        self.assertEqual(collision['shared'], ['map', 'tactics'])

    # -------------------------------------------------------------------------
    # Attack 5: Unnecessary Recruitment & Fake Capability Synthesis
    # -------------------------------------------------------------------------

    def test_attack_fake_recruitment_claims_and_empty_need_recruitment(self):
        """Recruitment rejects candidates without engine custody and refuses to recruit when no gap exists."""
        sit = self.service.genesis('production_brief', 'Audio Design', {'objective': 'Score battle', 'audience': 'fans', 'deliverables': ['audio'], 'constraints': []})

        self._insert_method('sciel', 'orchestration', 'node-audio')

        candidates = [
            {'participant_id': 'sciel', 'covers': ['orchestration'], 'evidence_refs': ['method:orchestration']},
            {'participant_id': 'imposter', 'covers': ['orchestration'], 'evidence_refs': ['method:unverified_fictional_music']},
        ]

        # Attack 5A: No unresolved needs -> recruit nobody even if candidates qualify
        self.assertEqual(self.runtime.recruit(sit.situation_id, candidates, unresolved=[]), [])

        # Attack 5B: Unresolved gap exists, but imposter candidate lacks engine custody
        imposter_result = self.runtime.recruit(sit.situation_id, [candidates[1]], unresolved=['orchestration'])
        self.assertEqual(imposter_result, [])

        # Positive Neighbor Control: Verified candidate covering genuine gap is recruited
        legit_result = self.runtime.recruit(sit.situation_id, candidates, unresolved=['orchestration'])
        self.assertEqual(legit_result, ['sciel'])

    # -------------------------------------------------------------------------
    # Attack 6: Stale & Counterfeit Execution Evidence in V11 Mediation
    # -------------------------------------------------------------------------

    def test_attack_counterfeit_and_stale_evidence_in_mediated_effect(self):
        """Mediated effectful stages reject fake event IDs, wrong evidence types, or counterfeit receipts."""
        sit = self.service.genesis('writing', 'Chapter Climax', {'purpose': 'Climax scene', 'audience': 'readers'})
        self.service.bind_workflow(sit.situation_id, 'writing.default')
        run = WorkflowRun('run-med-atk', sit.situation_id, 'writing.default', objective='Chapter Climax', authority=('read', 'write'))
        self.runtime.start(run)

        mediation = self.runtime.begin_effectful_stage('run-med-atk', 'draft')

        # Attack 6A: Mediated stage completion with nonexistent event evidence -> Rejected
        with self.assertRaisesRegex(Rejected, 'world execution evidence does not exist'):
            self.runtime.complete_effectful_stage(
                'run-med-atk',
                'draft',
                mediation,
                evidence_type='world-event',
                evidence_ref='ev:fake_hallucinated_event',
                outcome={'event_id': 'ev:fake_hallucinated_event'},
                verification={'check': 'pass'},
            )

        # Attack 6B: Evidence reference mismatch (payload declares ev_B, reference declares ev_A)
        ev_real = self._create_real_event('sciel', 'Real climax drafting')
        with self.assertRaisesRegex(Rejected, 'world execution evidence binding mismatch'):
            self.runtime.complete_effectful_stage(
                'run-med-atk',
                'draft',
                mediation,
                evidence_type='world-event',
                evidence_ref=ev_real,
                outcome={'event_id': 'ev:mismatched_id'},
                verification={'check': 'pass'},
            )

        # Positive Neighbor Control: Perfectly matching authentic engine event completes cleanly
        completed = self.runtime.complete_effectful_stage(
            'run-med-atk',
            'draft',
            mediation,
            evidence_type='world-event',
            evidence_ref=ev_real,
            outcome={'event_id': ev_real, 'draft': 'complete'},
            verification={'check': 'pass', 'author': 'sciel'},
        )
        self.assertEqual(completed['state'], 'COMPLETED')

    # -------------------------------------------------------------------------
    # Attack 7: False Evolution / Learning from Completion Alone
    # -------------------------------------------------------------------------

    def test_attack_false_learning_from_completion_alone(self):
        """Workflow evolution cannot be claimed without observed engine outcomes (anti-theater rule)."""
        # Attack 7A: Proposing evolution with empty outcome references -> Rejected
        with self.assertRaisesRegex(SituationError, 'evolution requires observed outcomes'):
            self.runtime.propose_evolution(EvolutionProposal(
                'evo-theater',
                'workflow',
                'writing.default',
                {'add_stage': 'unjustified_polish'},
                outcome_refs=(),
            ))

        # Attack 7B: Proposing evolution with fictional outcome references -> Rejected
        with self.assertRaisesRegex(SituationError, 'evolution evidence must resolve through engine custody'):
            self.runtime.propose_evolution(EvolutionProposal(
                'evo-fake-outcome',
                'workflow',
                'writing.default',
                {'add_stage': 'unjustified_polish'},
                outcome_refs=('event:fictional_consequence',),
            ))

        # Positive Neighbor Control: Real observed outcome recorded in engine stores evolution proposal
        ev = self._create_real_event('evaluator', 'Consequential friction recorded')
        valid_evo = EvolutionProposal(
            'evo-grounded',
            'workflow',
            'writing.default',
            {'add_stage': 'editorial_review'},
            outcome_refs=(f'event:{ev}',),
        )
        self.runtime.propose_evolution(valid_evo)
        self.assertTrue(self.service.store.contains('evolution', 'evo-grounded'))

    # -------------------------------------------------------------------------
    # Attack 8: Cross-Domain False Transfer
    # -------------------------------------------------------------------------

    def test_attack_cross_domain_false_competence_transfer(self):
        """Evidence of fictional success cannot be transferred as external or destination competence."""
        # Candidate attempts to map writing success into repository repair without destination evidence
        transfer_candidate = TransferCandidate(
            candidate_id='transfer-fiction-to-repo',
            source_memory_id='mem-writing-success',
            destination_situation_id='sit-repo-repair',
            mapping='dialogue_craft_to_syntax_patching',
            assumptions=('creative flow translates to code repair',),
            destination_evidence_refs=('event:unverified-repo-test-pass',),
        )

        # Attack 8A: Resolver in repository repair fails to find verified destination execution
        unverified_transfer = qualify_transfer(transfer_candidate, evidence_resolver=lambda ref, sid: False)
        self.assertEqual(unverified_transfer.status, 'untested')
        self.assertNotEqual(unverified_transfer.status, 'supported_in_destination')

        # Positive Neighbor Control: Real destination evidence resolves -> supported
        ev_repo = self._create_real_event('git-runner', 'Pipeline passed in repo workspace')
        grounded_transfer = TransferCandidate(
            candidate_id='transfer-grounded',
            source_memory_id='mem-prev-repair',
            destination_situation_id='sit-repo-repair',
            mapping='diff_analysis',
            destination_evidence_refs=(f'event:{ev_repo}',),
        )
        supported_transfer = qualify_transfer(
            grounded_transfer,
            evidence_resolver=lambda ref, sid: self.adapter.evidence(ref),
        )
        self.assertEqual(supported_transfer.status, 'supported_in_destination')

    # -------------------------------------------------------------------------
    # Attack 9: Resume and Recovery Failure States
    # -------------------------------------------------------------------------

    def test_attack_illegal_resume_conditions_and_unrecorded_failures(self):
        """Workflows reject illegal state transitions, resuming without satisfaction, or failing without reason."""
        sit = self.service.genesis('research', 'Investigate Void Boundaries', {'question': 'Boundary limits'})
        self.service.bind_workflow(sit.situation_id, 'research.default')
        run = WorkflowRun('run-recov', sit.situation_id, 'research.default', objective='Boundary limits', authority=('read',))
        self.runtime.start(run)

        # Attack 9A: Waiting without a resume condition -> Rejected
        with self.assertRaisesRegex(SituationError, 'waiting requires resume condition'):
            self.runtime.wait('run-recov', '')

        # Attack 9B: Failing without a reason -> Rejected
        with self.assertRaisesRegex(SituationError, 'failure requires reason'):
            self.runtime.fail('run-recov', '')

        # Attack 9C: Resuming a non-waiting run -> Rejected
        with self.assertRaisesRegex(SituationError, 'only waiting workflow can resume'):
            self.runtime.resume('run-recov', condition_satisfied=True)

        # Put into waiting state
        self.runtime.wait('run-recov', 'observation:data_packet_ready')

        # Attack 9D: Resuming with condition_satisfied=False -> Rejected
        with self.assertRaisesRegex(SituationError, 'resume condition not satisfied'):
            self.runtime.resume('run-recov', condition_satisfied=False)

        # Positive Neighbor Control: Valid wait -> satisfied resume restores active status
        self.runtime.resume('run-recov', condition_satisfied=True)
        self.assertEqual(self.runtime._run('run-recov').status, 'active')
        self.assertIsNone(self.runtime._run('run-recov').resume_condition)

    # -------------------------------------------------------------------------
    # Attack 10: Metamorphic & Decisive Fact Variations
    # -------------------------------------------------------------------------

    def test_metamorphic_invariance_and_decisive_fact_sensitivity(self):
        """Metamorphic details (whitespace, formatting) do not alter validity; single decisive bits flip outcome."""
        sit = self.service.genesis('research', 'Core Metamorphic Study', {'question': 'Study core invariants'})
        self.service.bind_workflow(sit.situation_id, 'research.default')
        run = WorkflowRun('run-meta', sit.situation_id, 'research.default', objective='Study core invariants', authority=('read', 'analyze'))
        self.runtime.start(run)

        # 1. Metamorphic Invariance: Irrelevant extra spaces in narrative do not change validity
        ev_meta1 = self._create_real_event('actor1', 'Standard narrative text.')
        ev_meta2 = self._create_real_event('actor1', 'Standard    narrative \t text with extra whitespace.')
        self.assertTrue(self.adapter.evidence(f'event:{ev_meta1}'))
        self.assertTrue(self.adapter.evidence(f'event:{ev_meta2}'))

        # 2. Decisive Fact Sensitivity: Tampering with a single character in the event ref flips valid to invalid
        valid_ref = f'event:{ev_meta1}'
        tampered_ref = f'event:{ev_meta1[:-1]}X'
        self.assertTrue(self.adapter.evidence(valid_ref))
        self.assertFalse(self.adapter.evidence(tampered_ref))

    # -------------------------------------------------------------------------
    # Attack 11: Scar Ledger Lifecycle and Positive Control Gate
    # -------------------------------------------------------------------------

    def test_scar_ledger_lifecycle_enforces_reprobe_and_positive_control(self):
        """Scars close only when both reprobe passes and positive control is verified."""
        scar = Scar(
            scar_id='SCAR-SIT-001',
            failure_class='unauthorized_authority_expansion',
            root_cause='child run permitted unconstrained authority tuple',
            probe_refs=('tests.test_situation_r4_scar_saturation',),
        )
        self.assertEqual(scar.status, 'open')

        # Attempt to close without repair ref -> remains open
        s1 = close_scar(scar, reprobe_passed=True, positive_control_passed=True)
        self.assertEqual(s1.status, 'open')

        # Add repair ref, but reprobe failed -> remains open
        s_with_repair = Scar(**{**scar.__dict__, 'repair_ref': 'commit:55a1dad'})
        s2 = close_scar(s_with_repair, reprobe_passed=False, positive_control_passed=True)
        self.assertEqual(s2.status, 'open')

        # Reprobe passed, but positive control failed -> remains open
        s3 = close_scar(s_with_repair, reprobe_passed=True, positive_control_passed=False)
        self.assertEqual(s3.status, 'open')

        # Reprobe passed AND positive control passed -> cleanly closed
        s4 = close_scar(s_with_repair, reprobe_passed=True, positive_control_passed=True)
        self.assertEqual(s4.status, 'closed')


if __name__ == '__main__':
    unittest.main()
