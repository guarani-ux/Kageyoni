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
from kageyoni.situations.memory import SituationMemory, SituationMemoryStore, TransferCandidate, qualify_transfer
from kageyoni.situations.models import SituationTemplate, Workflow, WorkflowStage
from kageyoni.situations.runtime import EvolutionProposal, ExtensionProposal, SituationRuntime, WorkflowRun
from kageyoni.situations.service import SituationError
from kageyoni.situations.v11_adapter import V11SituationMediator


class SituationR3IntegrationTests(unittest.TestCase):
    """Stage R3 Integration: Full qualification of the 6 Situation families
    and 22 connected lifecycle requirements against real Kageyoni services.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'situation_r3.sqlite'
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

    def _create_real_event(self, actor: str = 'tester') -> str:
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

    def _insert_method_for_character(self, character_id: str, method_id: str, node_id: str = 'node-1'):
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
    # 1. Complete & Incomplete Genesis across All 6 Families
    # -------------------------------------------------------------------------

    def test_all_six_families_complete_genesis(self):
        """All 6 families succeed at complete Genesis when required fields are supplied."""
        cases = {
            'research': {'question': 'How does deity steel awaken?'},
            'production_brief': {'objective': 'Produce chapter animatic', 'audience': 'fans', 'deliverables': ['storyboard'], 'constraints': ['budget-capped']},
            'campaign': {'objective': 'Promote Blackbeard infiltration', 'audience': 'crews'},
            'writing': {'purpose': 'Draft prologue confrontation', 'audience': 'readers'},
            'repository_repair': {'objective': 'Fix pipeline artifact hash check', 'repository': 'main'},
            'living_world': {'scene': 'Levi parley with Captain Kenway', 'participants': ['levi', 'kenway']},
        }
        for family, supplied in cases.items():
            with self.subTest(family=family):
                sit = self.service.genesis(family, f'Objective for {family}', supplied)
                self.assertEqual(sit.status, 'active')
                self.assertEqual(len(sit.unknowns), 0, f'Unexpected unknowns in complete genesis for {family}: {sit.unknowns}')
                self.assertIsNone(sit.workflow_id)
                rec_wf = self.service.templates[family].recommended_workflows[0]
                self.service.bind_workflow(sit.situation_id, rec_wf)
                updated_sit = self.service.store.get('situation', sit.situation_id)
                self.assertEqual(updated_sit.workflow_id, rec_wf)

    def test_all_six_families_incomplete_genesis_and_unknown_preservation(self):
        """All 6 families preserve missing required fields as explicit unknowns."""
        for template in TEMPLATES:
            family = template.template_id
            with self.subTest(family=family):
                sit = self.service.genesis(family, f'Incomplete {family}', {})
                self.assertEqual(sit.status, 'active')
                for req in template.required:
                    self.assertIn(req, sit.unknowns, f'Missing required field {req} was not preserved in unknowns for {family}')

    def test_contradiction_preservation_without_hallucinatory_collapse(self):
        """Alternative contradictory values are strictly preserved without collapsing."""
        for template in TEMPLATES:
            family = template.template_id
            req_field = template.required[0]
            contradiction_payload = {'__alternatives__': ['hypothesis_A', 'hypothesis_B']}
            sit = self.service.genesis(family, f'Contradiction {family}', {req_field: contradiction_payload})
            self.assertIn(req_field, sit.contradictions)
            self.assertEqual(sit.contradictions[req_field], ['hypothesis_A', 'hypothesis_B'])
            self.assertIsNone(sit.objects.get(req_field))
            self.assertIn(req_field, sit.unknowns)

    # -------------------------------------------------------------------------
    # 2. Durable SQLite Storage & Save / Reopen / Resume
    # -------------------------------------------------------------------------

    def test_durable_save_reopen_and_resume_across_engine_lifecycles(self):
        """Situations, workflow runs, and memories survive database reopen from disk."""
        sit = self.service.genesis('research', 'Inquire Will Limits', {'question': 'Will exhaustion threshold'})
        self.service.bind_workflow(sit.situation_id, 'research.default')
        run = WorkflowRun('run-persist', sit.situation_id, 'research.default', objective='Inquire Will Limits', authority=('read',))
        self.runtime.start(run)
        self.runtime.wait('run-persist', 'awaiting observation data')

        mem = SituationMemory('mem-persist', sit.situation_id, 'research', 'Inquire Will Limits', dependency_keys=('will', 'exhaustion'))
        self.memory.remember(mem)

        # Close and reopen the database connection
        self.engine.close()
        reopened_engine = Engine(self.db_path)
        try:
            adapter = KageyoniSituationAdapter(reopened_engine)
            service = install_defaults(adapter.service())
            runtime = SituationRuntime(service, adapter.evidence, mediator=V11SituationMediator(reopened_engine))
            memory = SituationMemoryStore(service.store)

            # Re-read situation from persistent disk
            loaded_sit = service.store.get('situation', sit.situation_id)
            self.assertEqual(loaded_sit.situation_id, sit.situation_id)
            self.assertEqual(loaded_sit.template_id, 'research')

            # Re-read and resume workflow run
            loaded_run = service.store.get('workflow_run', 'run-persist')
            self.assertEqual(loaded_run.status, 'waiting')
            self.assertEqual(loaded_run.resume_condition, 'awaiting observation data')

            runtime.resume('run-persist', condition_satisfied=True)
            resumed_run = service.store.get('workflow_run', 'run-persist')
            self.assertEqual(resumed_run.status, 'active')
            self.assertIsNone(resumed_run.resume_condition)

            # Re-read memory
            retrieved = memory.retrieve(dependency_keys=('will',))
            self.assertTrue(any(m.memory_id == 'mem-persist' for m in retrieved))
        finally:
            reopened_engine.close()
            # Reconnect self.engine for tearDown
            self.engine = Engine(self.db_path)

    # -------------------------------------------------------------------------
    # 3. Nested Workflows, Authority Scoping & Failure Recovery
    # -------------------------------------------------------------------------

    def test_nested_workflows_enforce_objective_and_authority_subset(self):
        """Child workflows cannot rewrite parent objective or expand authority."""
        sit = self.service.genesis('campaign', 'Global Campaign', {'objective': 'Mobilize fleet', 'audience': 'navy'})
        self.service.bind_workflow(sit.situation_id, 'campaign.default')
        parent = WorkflowRun('parent-run', sit.situation_id, 'campaign.default', objective='Mobilize fleet', authority=('read', 'write'))
        self.runtime.start(parent)

        # 1. Child attempting to change objective -> rejected
        child_bad_obj = WorkflowRun('child-bad-obj', sit.situation_id, 'campaign.default', parent_run_id='parent-run', objective='Mutated Goal', authority=('read',))
        with self.assertRaisesRegex(SituationError, 'child workflow cannot replace parent objective'):
            self.runtime.start(child_bad_obj)

        # 2. Child attempting to expand authority -> rejected
        child_bad_auth = WorkflowRun('child-bad-auth', sit.situation_id, 'campaign.default', parent_run_id='parent-run', objective='Mobilize fleet', authority=('read', 'write', 'admin_execute'))
        with self.assertRaisesRegex(SituationError, 'child workflow cannot expand authority'):
            self.runtime.start(child_bad_auth)

        # 3. Valid nested child with same objective and authority subset -> accepted
        child_valid = WorkflowRun('child-valid', sit.situation_id, 'campaign.default', parent_run_id='parent-run', objective='Mobilize fleet', authority=('read',))
        self.runtime.start(child_valid)
        self.assertEqual(self.runtime._run('child-valid').status, 'active')

    def test_workflow_failure_and_state_recovery(self):
        """Failing a workflow run captures root reason; wait/resume gate verifies condition."""
        sit = self.service.genesis('writing', 'Write Scene', {'purpose': 'Scene 1', 'audience': 'readers'})
        self.service.bind_workflow(sit.situation_id, 'writing.default')
        run = WorkflowRun('run-fail', sit.situation_id, 'writing.default', objective='Scene 1', authority=('read', 'write'))
        self.runtime.start(run)

        # Failure marks failed with reason
        self.runtime.fail('run-fail', 'unresolved continuity contradiction')
        failed_run = self.runtime._run('run-fail')
        self.assertEqual(failed_run.status, 'failed')
        self.assertEqual(failed_run.failure_reason, 'unresolved continuity contradiction')

        # Cannot resume a non-waiting run
        with self.assertRaisesRegex(SituationError, 'only waiting workflow can resume'):
            self.runtime.resume('run-fail', condition_satisfied=True)

    # -------------------------------------------------------------------------
    # 4. Participant Recruitment & Domain Projections
    # -------------------------------------------------------------------------

    def test_participant_recruitment_useful_and_correct_no_recruitment(self):
        """Recruitment selectively recruits only when candidates cover unresolved needs with real evidence."""
        sit = self.service.genesis('production_brief', 'Video Brief', {'objective': 'Film teaser', 'audience': 'public', 'deliverables': ['teaser'], 'constraints': []})

        self._insert_method_for_character('sciel', 'cinematics', 'node-sciel')

        candidates = [
            {'participant_id': 'sciel', 'covers': ['cinematics'], 'evidence_refs': ['method:cinematics']},
            {'participant_id': 'cloud', 'covers': ['combat'], 'evidence_refs': ['method:combat_missing']},
        ]

        # 1. No unresolved gaps -> nobody recruited
        self.assertEqual(self.runtime.recruit(sit.situation_id, candidates, unresolved=[]), [])

        # 2. Unresolved gap matches verified candidate -> recruited
        recruited = self.runtime.recruit(sit.situation_id, candidates, unresolved=['cinematics'])
        self.assertEqual(recruited, ['sciel'])

        # 3. Candidate lacks valid engine evidence -> not recruited
        unverified_recruited = self.runtime.recruit(sit.situation_id, candidates, unresolved=['combat'])
        self.assertEqual(unverified_recruited, [])

    def test_domain_projection_evidence_binding_and_borrowing_rejection(self):
        """Domain projections accept verified participant methods and reject borrowed identity evidence."""
        sit = self.service.genesis('living_world', 'Port Arrival', {'scene': 'Arrival', 'participants': ['sciel', 'alexandra']})

        self._insert_method_for_character('sciel', 'writing', 'node-sciel')

        # 1. Sciel uses own method -> accepted
        proj_sciel = DomainProjection('proj-sciel', 'sciel', sit.situation_id, ('relationships',), ('intent',), method_refs=('method:writing',))
        self.service.propose_projection(proj_sciel, established_refs={'method:writing'})
        self.assertIn('proj-sciel', self.service.projections)

        # 2. Alexandra attempts to borrow sciel's method -> rejected
        proj_borrowed = DomainProjection('proj-borrowed', 'alexandra', sit.situation_id, ('relationships',), ('intent',), method_refs=('method:writing',))
        with self.assertRaises(SituationError):
            self.service.propose_projection(proj_borrowed, established_refs={'method:writing'})

    def test_domain_projection_collision_and_redundancy_detection(self):
        """Domain collisions detect shared attention and flag redundant projections."""
        sit = self.service.genesis('living_world', 'Council Meeting', {'scene': 'Council', 'participants': ['sciel', 'kenway']})
        p1 = DomainProjection('p1', 'sciel', sit.situation_id, ('factions', 'strategy'), ('q1',))
        p2 = DomainProjection('p2', 'kenway', sit.situation_id, ('factions', 'weapons'), ('q2',))
        p3 = DomainProjection('p3', 'sciel', sit.situation_id, ('factions', 'strategy'), ('q3',))

        self.service.store.put('projection', 'p1', p1)
        self.service.store.put('projection', 'p2', p2)
        self.service.store.put('projection', 'p3', p3)

        # p1 vs p2: shared 'factions', distinct elements, non-redundant
        c1 = self.runtime.collide(['p1', 'p2'])
        self.assertEqual(c1['shared'], ['factions'])
        self.assertFalse(c1['redundant'])

        # p1 vs p3: identical foreground -> redundant
        c2 = self.runtime.collide(['p1', 'p3'])
        self.assertTrue(c2['redundant'])

    # -------------------------------------------------------------------------
    # 5. Local Extensions & Justified vs Unsupported Promotion
    # -------------------------------------------------------------------------

    def test_local_extension_and_justified_promotion(self):
        """Extensions begin local; promotion requires >= 2 engine-verified outcome references."""
        sit = self.service.genesis('repository_repair', 'Repair Loop', {'objective': 'Fix test', 'repository': 'main'})

        ev1 = self._create_real_event('tester')
        ev2 = self._create_real_event('tester')

        ext = ExtensionProposal('ext-rep', sit.situation_id, 'tooling', {'tool': 'fast_test'}, scope='local')
        self.runtime.propose_extension(ext)

        # Promotion with 1 outcome ref -> rejected (< 2)
        with self.assertRaisesRegex(SituationError, 'promotion requires repeated consequential evidence'):
            self.runtime.promote_extension('ext-rep', (f'event:{ev1}',))

        # Promotion with unverified outcome refs -> rejected
        with self.assertRaisesRegex(SituationError, 'promotion evidence must resolve through engine custody'):
            self.runtime.promote_extension('ext-rep', (f'event:{ev1}', 'event:fake_outcome'))

        # Promotion with 2 verified outcome refs -> qualified evolution proposal
        evolution = self.runtime.promote_extension('ext-rep', (f'event:{ev1}', f'event:{ev2}'))
        self.assertEqual(evolution.status, 'qualified')
        self.assertEqual(evolution.target_type, 'template')

    # -------------------------------------------------------------------------
    # 6. Workflow Evolution & Memory Retrieval
    # -------------------------------------------------------------------------

    def test_workflow_evolution_requires_observed_outcomes(self):
        """Proposing workflow evolution requires verified engine outcomes."""
        ev1 = self._create_real_event('system')

        # 1. No outcome refs -> rejected
        with self.assertRaisesRegex(SituationError, 'evolution requires observed outcomes'):
            self.runtime.propose_evolution(EvolutionProposal('evo-bad', 'workflow', 'research.default', {'add': 'peer_review'}, ()))

        # 2. Fake outcome refs -> rejected
        with self.assertRaisesRegex(SituationError, 'evolution evidence must resolve through engine custody'):
            self.runtime.propose_evolution(EvolutionProposal('evo-fake', 'workflow', 'research.default', {'add': 'peer_review'}, ('event:fake',)))

        # 3. Authentic outcome ref -> stored
        self.runtime.propose_evolution(EvolutionProposal('evo-good', 'workflow', 'research.default', {'add': 'peer_review'}, (f'event:{ev1}',)))
        self.assertTrue(self.service.store.contains('evolution', 'evo-good'))

    def test_causal_dependency_aware_situation_memory_retrieval(self):
        """Situation memory ranks results by template affinity and shared dependency keys."""
        m1 = SituationMemory('m1', 'sit-1', 'research', 'Investigation 1', dependency_keys=('deity_steel', 'forge'))
        m2 = SituationMemory('m2', 'sit-2', 'research', 'Investigation 2', dependency_keys=('weather',))
        m3 = SituationMemory('m3', 'sit-3', 'campaign', 'Campaign 1', dependency_keys=('deity_steel',))

        self.memory.remember(m1)
        self.memory.remember(m2)
        self.memory.remember(m3)

        # Retrieve for research template with dependency 'deity_steel'
        results = self.memory.retrieve(template_id='research', dependency_keys=('deity_steel',))
        self.assertGreater(len(results), 0)
        # m1 has both template match (+4) and dependency match (+3) -> highest score (7)
        self.assertEqual(results[0].memory_id, 'm1')

    def test_transfer_candidate_rejects_fictional_evidence(self):
        """Cross-situation transfer candidate requires real destination evidence."""
        cand = TransferCandidate('c1', 'm1', 'sit-dst', 'direct_mapping', destination_evidence_refs=('event:real',))

        # Resolver fails -> status untested
        untested = qualify_transfer(cand, evidence_resolver=lambda ref, sid: False)
        self.assertEqual(untested.status, 'untested')

        # Resolver passes -> supported_in_destination
        supported = qualify_transfer(cand, evidence_resolver=lambda ref, sid: True)
        self.assertEqual(supported.status, 'supported_in_destination')

    # -------------------------------------------------------------------------
    # 7. Exact Mediated Effectful Stage Execution (V11 Mediation)
    # -------------------------------------------------------------------------

    def test_effectful_stage_execution_with_v11_mediation(self):
        """Effectful stage in a situation workflow mediates directly through v11 protected operations."""
        sit = self.service.genesis('writing', 'Draft Chapter Scene', {'purpose': 'Scene Draft', 'audience': 'readers'})
        self.service.bind_workflow(sit.situation_id, 'writing.default')
        run = WorkflowRun('run-effect', sit.situation_id, 'writing.default', objective='Draft Chapter Scene', authority=('read', 'write'))
        self.runtime.start(run)

        # Begin effectful stage through v11 mediator
        mediation = self.runtime.begin_effectful_stage('run-effect', 'draft')
        self.assertIsNotNone(mediation.operation_id)
        self.assertIsNotNone(mediation.qualification_id)

        # Create authentic engine-committed event as evidence
        event_id = self._create_real_event('sciel')

        # Complete effectful stage
        completed = self.runtime.complete_effectful_stage(
            'run-effect',
            'draft',
            mediation,
            evidence_type='world-event',
            evidence_ref=event_id,
            outcome={'event_id': event_id, 'draft_status': 'written'},
            verification={'check': 'pass', 'author': 'sciel'},
        )
        self.assertEqual(completed['state'], 'COMPLETED')
        self.assertIn('draft', self.runtime._run('run-effect').completed_stages)
        self.assertTrue(self.engine.verify()['ok'])


if __name__ == '__main__':
    unittest.main()
