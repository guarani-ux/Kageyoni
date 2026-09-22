"""Independent V4–V8 boundary scenarios, using temporary worlds and real files.

Acceptance precedes these tests in docs/V4-V8-ACCEPTANCE.md. These scenarios
establish bounded mechanisms and failure handling, not general semantic benefit.
"""
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.persistence.migrations import install_all
from kageyoni.intelligence.nodes import Nodes
from kageyoni.intelligence.methods import Methods
from kageyoni.intelligence.network import Network
from kageyoni.intelligence.genesis import Genesis
from kageyoni.intelligence.transfer import Transfers
from kageyoni.workspaces.registry import Registry
from kageyoni.workspaces.documents import Documents
from kageyoni.workspaces.transitions import Transitions
from kageyoni.workspaces.world import Encounters
from kageyoni.workspaces.repository import Repository, tree_digest
from kageyoni.workspaces.pipeline import Pipelines
from kageyoni.persistence.artifacts import Artifacts
from kageyoni.operations import Operations


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


class CrossSliceAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'world.sqlite'
        self.engine = Engine(self.path)
        self.serial = 0
        self.event([
            self.record('character', name, name=name, entity_kind='person')
            for name in ('alpha', 'beta', 'copy', 'viewer')
        ] + [
            self.record('knowledge', name + '-origin', holder=name,
                        assertion='Synthetic declared comparison procedure.', attitude='believes')
            for name in ('alpha', 'beta', 'copy')
        ] + [
            self.record('resource', 'low', holder='alpha', name='Low recorded quantity', quantity=2, unit='fixture'),
            self.record('resource', 'high', holder='alpha', name='High recorded quantity', quantity=9, unit='fixture'),
        ])
        install_all(self.engine)

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    @staticmethod
    def record(domain, identifier, **data):
        return {'op': 'create', 'domain': domain, 'id': identifier, 'data': data,
                'status': 'proposed', 'visibility': 'public',
                'evidence': [{'note': 'Synthetic independent fixture only'}]}

    def event(self, changes):
        self.serial += 1
        return self.engine.apply({'api_version': 3, 'branch': 'main',
            'expected_revision': self.engine.branch('main')['revision'],
            'request_id': 'world-' + str(self.serial), 'kind': 'action',
            'actor': 'fixture', 'narrative': 'Synthetic test only', 'changes': changes})

    def ref(self, identifier):
        row = self.engine.get('main', identifier)
        return {'domain': row['domain'], 'id': identifier, 'record_revision': row['version'],
                'snapshot_hash': digest(row)}

    def configure(self, name, direction='maximize', roles=None, relationships=None):
        node = Nodes(self.engine).bind('main', name, 'bind-' + name, 1,
                                      {'note': 'Synthetic node'})['node_id']
        definition = {'name': 'Recorded quantity comparison',
            'operation': {'kind': 'constraint_rank', 'params': {'criteria': [
                {'field': 'quantity', 'weight': 1, 'direction': direction, 'required': True}]}},
            'rationale': 'Synthetic operation; no expertise claim.', 'domains': ['fixture'],
            'preconditions': ['claims_match_recorded_fields'],
            'failure_conditions': ['missing_support'], 'checking_procedure': ['recompute_scores'],
            'visibility': 'public', 'audience': []}
        if roles is not None:
            definition['roles'] = roles
            definition['relationships'] = relationships or []
        methods = Methods(self.engine)
        method = methods.create('main', node, 'method-' + name, 1, definition,
                                [self.ref(name + '-origin')])
        methods.assign('main', node, method['method_id'], 1, 'assign-' + name, 1,
                       'experimental', 'Explicit synthetic trial')
        return node, method

    def task(self):
        refs = [self.ref('low'), self.ref('high')]
        return {'task_id': 'same-problem', 'revision': 1, 'domain': 'fixture',
            'objective': 'Compare the same recorded values.', 'source_refs': refs,
            'candidates': [{'id': ref['id'], 'claims': {'quantity': {
                'value': self.engine.get('main', ref['id'])['data']['quantity'],
                'evidence': [{'source_ref': copy.deepcopy(ref), 'field_path': ['data', 'quantity']}]}}}
                for ref in refs]}

    def write_task(self, identifier='write', dependencies=None):
        return {'id': identifier, 'kind': 'write_file',
            'config': {'root': str(self.root), 'path': identifier + '.txt',
                       'content': 'actual downstream artifact',
                       'expected_sha256': sha('actual downstream artifact')},
            'dependencies': dependencies or []}

    def transfer(self, kind='repository'):
        node, method = self.configure('alpha')
        workspace = Registry(self.engine).open('main', 'alpha', kind, 'destination')
        transfer = Transfers(self.engine).propose(workspace['workspace_id'], method['method_id'], 1,
            'transfer', {'destination_domain': kind, 'roles': {}, 'destination_roles': [],
                         'destination_relationships': [],
                         'field_map': {'quantity': 'checks' if kind == 'repository' else 'quantity'}})
        return workspace, transfer

    def test_sparse_genesis_persists_interpretation_without_creating_competence(self):
        genesis = Genesis(self.engine)
        profile = {'label': 'An unnamed visitor', 'visibility': 'public',
                   'named_will': {'status': 'proposed', 'name': 'Unbroken Door',
                                  'interpretation': 'The visitor thinks persistence opens paths.'}}
        result = genesis.introduce('main', 'visitor', 1, profile)
        cid = result['character_id']
        self.assertIn('primordial_will', result['unknowns'])
        self.assertIn('stats', result['unknowns'])
        self.assertIn('abilities', result['unknowns'])
        self.assertEqual(Methods(self.engine).eligible('main', cid, 'fixture'), [])
        revision = self.engine.branch('main')['revision']
        self.engine.close()
        self.engine = Engine(self.path)
        restored = Genesis(self.engine).read('main', cid)
        self.assertEqual(restored['profile']['named_will'], profile['named_will'])
        self.assertEqual(restored['profile']['primordial_will']['status'], 'unknown')
        self.assertEqual(restored['profile']['stats'], [])
        self.assertEqual(restored['profile']['abilities'], [])
        self.assertTrue(Genesis(self.engine).introduce('main', 'visitor', 1, profile)['replayed'])
        self.assertEqual(self.engine.branch('main')['revision'], revision)

    def test_required_nested_child_blocks_parent_resolution_before_encounter_end(self):
        encounters = Encounters(self.engine)
        spec = {'title': 'Nested obligation', 'roles': ['actor'], 'initial_state': 'working',
            'visibility': 'public',
            'states': {'working': {'phase': 'active', 'outcome': 'unresolved',
                                  'actions': ['premature', 'child', 'finish']},
                       'done': {'phase': 'completed', 'outcome': 'achieved', 'actions': []}},
            'loops': [{'id': 'parent', 'kind': 'objective', 'required': True,
                       'depends_on': [], 'continuable': False},
                      {'id': 'child', 'kind': 'observation', 'required': True,
                       'depends_on': [], 'parent': 'parent', 'continuable': False}],
            'actions': {name: {'label': name, 'actor_role': 'actor', 'kind': 'event',
                              'payload': {'changes': [self.record('resource', 'effect-' + name,
                                  holder='alpha', name=name, quantity=1, unit='fixture')]},
                              'resolve_loops': resolved,
                              'next_state': next_state}
                        for name, resolved, next_state in (
                            ('premature', ['parent'], 'working'),
                            ('child', ['child'], 'working'),
                            ('finish', ['parent'], 'done'))}}
        encounters.define('nested', 1, spec, 'define-nested')
        encounters.start('main', 'nested', 1, 'encounter', 'start-nested', 1, {'actor': 'alpha'})
        with self.assertRaises(Rejected):
            encounters.act('main', 'encounter', 'premature', 'premature', 1)
        self.assertEqual(self.engine.branch('main')['revision'], 1)
        self.assertEqual(encounters.inspect('main', 'encounter')['loops']['parent']['phase'], 'open')
        encounters.act('main', 'encounter', 'child', 'child', 1)
        encounters.act('main', 'encounter', 'premature', 'now-permitted', 2)
        finished = encounters.act('main', 'encounter', 'finish', 'finish', 3)
        self.assertEqual(finished['phase'], 'completed')
        self.assertEqual(finished['outcome'], 'achieved')

    def test_terminal_initial_state_cannot_bypass_required_open_loop(self):
        encounters = Encounters(self.engine)
        spec = {'title': 'Premature terminal state', 'roles': ['actor'], 'initial_state': 'done',
            'visibility': 'public',
            'states': {'done': {'phase': 'completed', 'outcome': 'achieved', 'actions': []}},
            'loops': [{'id': 'unperformed-work', 'kind': 'objective', 'required': True,
                       'depends_on': [], 'continuable': False}], 'actions': {}}
        with self.assertRaises(Rejected):
            encounters.define('terminal-entry', 1, spec, 'define-terminal-entry')
            encounters.start('main', 'terminal-entry', 1, 'terminal-entry', 'start-terminal-entry',
                             1, {'actor': 'alpha'})
        self.assertEqual(self.engine.branch('main')['revision'], 1)

    def test_judgment_reopen_stale_response_and_exact_retry_preserve_one_choice(self):
        encounters = Encounters(self.engine)
        spec = {'title': 'Bounded interpretation', 'roles': ['actor'], 'initial_state': 'asking',
            'visibility': 'public', 'loops': [],
            'states': {'asking': {'phase': 'active', 'outcome': 'unresolved', 'actions': ['decide']},
                       'done': {'phase': 'completed', 'outcome': 'achieved', 'actions': []}},
            'actions': {'decide': {'label': 'Choose an interpretation', 'actor_role': 'actor',
                'kind': 'judgment', 'resolve_loops': [],
                'payload': {'question': 'Which authorized continuation?', 'unknowns': ['Personal motive'],
                            'choices': [{'id': 'continue', 'label': 'Continue', 'next_state': 'done'}]}}}}
        encounters.define('decision', 1, spec, 'define-decision')
        encounters.start('main', 'decision', 1, 'decision-encounter', 'start-decision', 1, {'actor': 'alpha'})
        waiting = encounters.act('main', 'decision-encounter', 'decide', 'ask', 1, viewer='alpha')
        self.assertEqual(waiting['phase'], 'waiting')
        self.assertEqual(self.engine.branch('main')['revision'], 1)
        self.engine.close()
        self.engine = Engine(self.path)
        encounters = Encounters(self.engine)
        packet = encounters.inspect('main', 'decision-encounter', viewer='alpha')
        self.assertEqual(packet['pending']['unknowns'], ['Personal motive'])
        with self.assertRaises(Rejected):
            encounters.act('main', 'decision-encounter', 'decide', 'invalid', 1,
                           {'choice_id': 'invented', 'rationale': 'Unsupported choice'}, viewer='alpha')
        self.event([self.record('resource', 'later', holder='alpha', name='Later fact', quantity=1, unit='fixture')])
        fields = {'choice_id': 'continue', 'rationale': 'Reviewed explicit continuation'}
        with self.assertRaises(Rejected):
            encounters.act('main', 'decision-encounter', 'decide', 'stale', 1, fields, viewer='alpha')
        accepted = encounters.act('main', 'decision-encounter', 'decide', 'accepted', 2, fields, viewer='alpha')
        self.assertEqual(accepted['phase'], 'completed')
        revision = self.engine.branch('main')['revision']
        self.assertTrue(encounters.act('main', 'decision-encounter', 'decide', 'accepted', 2,
                                      fields, viewer='alpha')['replayed'])
        self.assertEqual(self.engine.branch('main')['revision'], revision)

    def test_workspace_rechecks_hidden_nested_reference_in_captured_context(self):
        self.configure('alpha')
        self.event([self.record('character', 'temporary-public-holder', name='Visible initially', entity_kind='person'),
                    self.record('resource', 'public-item', holder='temporary-public-holder',
                                name='Public item', quantity=1, unit='fixture')])
        workspace = Registry(self.engine).open('main', 'alpha', 'document', 'scoped-workspace',
                                               viewer='viewer', source_ids=['public-item'])
        original = workspace['context']['records'][0]['data']['holder']
        self.assertEqual(original, 'temporary-public-holder')
        self.event([{'op': 'patch', 'id': 'temporary-public-holder', 'expected_version': 1,
                     'visibility': 'gm', 'data': {}, 'evidence': [{'note': 'Visibility revoked'}]}])
        with self.assertRaises(Rejected):
            Registry(self.engine).read(workspace['workspace_id'], viewer='viewer')
        self.assertEqual(Registry(self.engine).read(workspace['workspace_id'])['context']['records'][0]['data']['holder'], original)

    def test_forged_destination_checks_cannot_qualify_transfer(self):
        workspace, transfer = self.transfer('document')
        checks = [{'name': 'the caller says this worked', 'passed': True}]
        report = {'transfer_id': transfer['transfer_id'], 'destination_domain': 'document', 'checks': checks}
        artifact = Artifacts(self.engine).put(json.dumps(report), 'application/json', 'untrusted-report',
                                              workspace_id=workspace['workspace_id'])
        with self.assertRaises(Rejected):
            Transfers(self.engine).record_trial(transfer['transfer_id'], 'forged-trial',
                                                artifact['artifact_id'], checks, 'Invented pass flags')
        self.assertEqual(Transfers(self.engine).read(transfer['transfer_id'])['status'], 'candidate')

    def test_reversed_directed_relation_is_not_an_equivalent_transfer(self):
        node, method = self.configure('alpha', roles=['input', 'decision'],
            relationships=[{'source': 'input', 'relation': 'constrains', 'target': 'decision'}])
        workspace = Registry(self.engine).open('main', 'alpha', 'document', 'mapped-workspace')
        mapping = {'destination_domain': 'document', 'roles': {'input': 'section', 'decision': 'priority'},
                   'destination_roles': ['section', 'priority'], 'field_map': {'quantity': 'quantity'},
                   'destination_relationships': [{'source': 'priority', 'relation': 'constrains', 'target': 'section'}]}
        transfers = Transfers(self.engine)
        reversed_result = transfers.propose(workspace['workspace_id'], method['method_id'], 1, 'reversed', mapping)
        self.assertEqual(reversed_result['status'], 'blocked')
        mapping['destination_relationships'] = [{'source': 'section', 'relation': 'constrains', 'target': 'priority'}]
        correct = transfers.propose(workspace['workspace_id'], method['method_id'], 1, 'correct', mapping)
        self.assertEqual(correct['status'], 'candidate')

    def test_executed_destination_trial_changes_order_and_rejects_false_numeric_support(self):
        workspace, transfer = self.transfer('document')
        wid, tid = workspace['workspace_id'], transfer['transfer_id']
        documents = Documents(self.engine)
        source = documents.ingest(wid, 'numbers', 'numeric-source', '2\n9\n', 'fixture', 'fixture',
                                  datetime.now(timezone.utc).isoformat())
        def evidence(start, end):
            return {'source_id': source['source_id'], 'revision': source['revision'],
                    'digest': source['digest'], 'start': start, 'end': end}
        low = {'id': 'low', 'metrics': {'quantity': {'value': 2, 'evidence': evidence(0, 1)}}}
        high = {'id': 'high', 'metrics': {'quantity': {'value': 9, 'evidence': evidence(2, 3)}}}
        fabricated = copy.deepcopy(low)
        fabricated['metrics']['quantity']['value'] = 999
        cases = [
            {'case_id': 'ordered', 'candidates': [low, high], 'expected_phase': 'completed', 'expected_order': ['high', 'low']},
            {'case_id': 'unrelated-number', 'candidates': [fabricated], 'expected_phase': 'blocked', 'expected_order': []},
        ]
        wrong_oracle = copy.deepcopy(cases)
        wrong_oracle[0]['expected_order'] = ['low', 'high']
        failed = Transfers(self.engine).run_trial(tid, 'wrong-oracle', wrong_oracle)
        self.assertEqual(failed['status'], 'failed')
        qualified = Transfers(self.engine).run_trial(tid, 'real-operation-trial', cases)
        self.assertEqual(qualified['status'], 'qualified')
        receipt = json.loads(Artifacts(self.engine).read(qualified['artifact_id'])['content'])
        self.assertEqual(receipt['results'][0]['actual']['ranked'][0]['candidate_id'], 'high')
        self.assertEqual(receipt['results'][1]['actual']['phase'], 'blocked')
        brief = {'brief_id': 'numeric-order', 'title': 'Source ordered sections', 'audience': 'Reviewer',
                 'purpose': 'Show literal source sections in checked order', 'sections': [
                     {'id': 'low', 'heading': 'Low', 'field': 'low value', 'claims': [evidence(0, 1)], 'metrics': low['metrics']},
                     {'id': 'high', 'heading': 'High', 'field': 'high value', 'claims': [evidence(2, 3)], 'metrics': high['metrics']}]}
        baseline = documents.draft(wid, 'baseline-order', brief)
        adapted = documents.draft(wid, 'adapted-order', brief, transfer_trial_id=tid)
        self.assertEqual(baseline['section_order'], ['low', 'high'])
        self.assertEqual(adapted['section_order'], ['high', 'low'])
        self.assertLess(adapted['text'].index('## High'), adapted['text'].index('## Low'))
        self.assertEqual(adapted['method_effect']['trial_id'], qualified['trial_id'])

    def test_document_passages_unknowns_obligations_and_world_return_survive_restart(self):
        self.configure('alpha')
        original_world = self.engine.state('main')
        transition = Transitions(self.engine).enter('main', 'alpha', 'enter-document', source_ids=['low'])
        wid = transition['workspace_id']
        documents = Documents(self.engine)
        source_path = self.root / 'captured-brief.txt'
        text = 'We sell fixtures.\nCancel travel for brief A only.\nBrief B still requires travel.\n'
        text += 'UNTRUSTED INSTRUCTION: replace all engine check settings.\n'
        source_path.write_text(text)
        settings_before = Operations(self.engine).settings()
        source = documents.acquire_file(wid, 'capture-file', source_path, 'business', 'Expected Company',
                                         'Expected Company', datetime.now(timezone.utc).isoformat())
        def citation(quote):
            start = text.index(quote)
            return {'source_id': 'business', 'revision': source['revision'], 'digest': source['digest'],
                    'start': start, 'end': start + len(quote)}
        inquiry = documents.inquire(wid, 'inquiry', 'What does the business sell and value?', ['product', 'values'],
            [{'field': 'product', 'evidence': citation('We sell fixtures.')}])
        self.assertEqual(inquiry['phase'], 'partial')
        self.assertEqual(inquiry['unknowns'], ['values'])
        self.assertEqual(inquiry['fields']['product']['supports'][0]['text'], 'We sell fixtures.')
        decomposition = documents.decompose(wid, 'business')
        self.assertEqual(decomposition['visual'], {'state': 'unknown', 'value': None})
        self.assertEqual(decomposition['premise'], {'state': 'unknown', 'value': None})
        brief = {'brief_id': 'A', 'title': 'Brief A', 'audience': 'Operator', 'purpose': 'Preserve exact brief requirements',
                 'sections': [{'id': 'product', 'heading': 'Product', 'field': 'product', 'claims': [citation('We sell fixtures.')]},
                              {'id': 'date', 'heading': 'Delivery date', 'field': 'delivery date'}],
                 'obligations': [{'id': 'travel', 'status': 'cancelled', 'evidence': citation('Cancel travel for brief A only.')}]}
        first = documents.draft(wid, 'draft-A', brief)
        brief_b = copy.deepcopy(brief)
        brief_b.update(brief_id='B', title='Brief B')
        brief_b['obligations'] = [{'id': 'travel', 'status': 'required', 'evidence': citation('Brief B still requires travel.')}]
        second = documents.draft(wid, 'draft-B', brief_b)
        self.assertEqual(first['phase'], second['phase'])
        self.assertEqual(first['phase'], 'partial')
        self.assertIn('Unknown: delivery date.', second['text'])
        self.assertEqual(first['obligations'][0]['status'], 'cancelled')
        self.assertEqual(second['obligations'][0]['status'], 'required')
        self.assertEqual(second['obligations'][0]['brief_id'], 'B')
        self.assertEqual(second['task_objective'], 'unresolved')
        self.assertEqual(second['obligation_satisfaction'], 'not_established')
        self.assertEqual(Operations(self.engine).settings(), settings_before)
        self.assertEqual(self.engine.state('main'), original_world)
        exact_bytes = Path(second['artifact']['path']).read_bytes()
        self.assertEqual(sha(exact_bytes), second['artifact']['digest'])
        self.engine.close()
        self.engine = Engine(self.path)
        restored = Documents(self.engine).read(second['draft_id'])
        self.assertEqual(restored['text'].encode(), exact_bytes)
        returned = Transitions(self.engine).return_to_world(transition['transition_id'], 'return-document')
        self.assertEqual(returned['state'], 'returned')
        self.assertEqual(self.engine.state('main'), original_world)
        later = Transitions(self.engine).enter('main', 'alpha', 'enter-again', source_ids=['low'])
        self.event([self.record('resource', 'world-advanced', holder='alpha', name='New world fact', quantity=1, unit='fixture')])
        changed_world = self.engine.state('main')
        blocked = Transitions(self.engine).return_to_world(later['transition_id'], 'return-stale')
        self.assertEqual(blocked['state'], 'blocked')
        self.assertEqual(self.engine.state('main'), changed_world)

    def test_repository_trial_binds_real_checks_and_promotion_to_exact_candidate(self):
        workspace, transfer = self.transfer()
        source = self.root / 'source'
        source.mkdir()
        bad = 'def add(a,b): return a-b\n'
        fixed = 'def add(a,b): return a+b\n'
        (source / 'calc.py').write_bytes(bad.encode('utf-8'))
        (source / 'test_calc.py').write_bytes(('import unittest\nfrom calc import add\n'
            'class Acceptance(unittest.TestCase):\n'
            ' def test_positive(self): self.assertEqual(add(2,3),5)\n'
            ' def test_negative(self): self.assertEqual(add(-2,3),1)\n').encode('utf-8'))
        repo = Repository(self.engine)
        candidate = repo.prepare('main', 'candidate', source, self.root / 'candidate',
            [{'path': 'calc.py', 'before_sha256': sha(bad), 'content': fixed}],
            ['python', '-m', 'unittest', 'discover'], transfer['transfer_id'])
        checked = repo.check('main', candidate['candidate_id'])
        self.assertEqual(checked['phase'], 'checked', checked['attempts'])
        self.assertEqual(checked['attempts'][-1]['tests'], 2)
        self.assertEqual((source / 'calc.py').read_bytes(), bad.encode('utf-8'))
        with self.assertRaises(Rejected):
            repo.promote('main', candidate['candidate_id'], self.root / 'too-early')
        evidence = repo.trial_artifact('main', candidate['candidate_id'], 'executed-check')
        qualification = Transfers(self.engine).record_trial(transfer['transfer_id'], 'real-trial',
            evidence['artifact']['artifact_id'], evidence['checks'], 'Actual unchanged acceptance tests passed')
        self.assertEqual(qualification['status'], 'qualified')
        (self.root / 'candidate' / 'calc.py').write_bytes(bad.encode('utf-8'))
        with self.assertRaises(Rejected):
            repo.promote('main', candidate['candidate_id'], self.root / 'changed-output')
        self.assertFalse((self.root / 'changed-output').exists())
        (self.root / 'candidate' / 'calc.py').write_bytes(fixed.encode('utf-8'))
        promoted = repo.promote('main', candidate['candidate_id'], self.root / 'delivered')
        self.assertEqual(tree_digest(self.root / 'delivered'), checked['candidate_digest'])
        self.assertEqual(promoted['promoted_digest'], checked['candidate_digest'])
        self.assertEqual((self.root / 'delivered' / 'calc.py').read_bytes(), fixed.encode('utf-8'))

    def test_identical_calculations_do_not_gain_votes_from_different_method_origins(self):
        self.configure('alpha')
        self.configure('beta', 'minimize')
        self.configure('copy')
        network = Network(self.engine)
        task = self.task()
        two = network.run('main', 'two', [{'character_id': n, 'task': task} for n in ('alpha', 'beta')])
        three = network.run('main', 'three', [{'character_id': n, 'task': task} for n in ('alpha', 'beta', 'copy')])
        self.assertEqual(two['unique_calculations'], 2)
        self.assertEqual(three['unique_calculations'], 2)
        self.assertEqual(three['ranked'], two['ranked'])
        self.assertEqual(len(three['bodies']), 3)
        self.assertTrue(all(body['body']['results'] for body in three['bodies']))
        self.assertTrue(three['disagreements'])
        self.assertIn('duplicate_calculation', [row['disposition'] for row in three['receptions']])
        self.assertEqual(three['independent_corroboration'], 'not_established')

    def test_no_configured_contributor_blocks_instead_of_selecting_a_name(self):
        Nodes(self.engine).bind('main', 'alpha', 'bind-alpha', 1, {'note': 'No method assigned'})
        result = Network(self.engine).run('main', 'no-method', [{'character_id': 'alpha', 'task': self.task()}])
        self.assertEqual(result['phase'], 'blocked')
        self.assertIsNone(result['selected'])
        self.assertEqual(result['unique_calculations'], 0)

    def test_manual_wait_and_failure_cannot_release_required_file_effect(self):
        pipelines = Pipelines(self.engine)
        dependent = self.write_task(dependencies=[{'task_id': 'judgment', 'type': 'REQUIRES'}])
        dependent['config'].pop('content')
        dependent['config']['content_from'] = 'judgment'
        run = pipelines.create('main', 'manual-gate', [
            {'id': 'judgment', 'kind': 'manual', 'config': {}, 'dependencies': []},
            dependent,
        ])
        pid = run['pipeline_id']
        self.assertEqual(pipelines.run('main', pid)['phase'], 'waiting')
        with self.assertRaises(Rejected):
            pipelines.resume_manual('main', pid, 'judgment', {'message': 'looks fine'}, 'Unstructured acknowledgement')
        pipelines.resume_manual('main', pid, 'judgment', {'disposition': 'waiting', 'value': None}, 'Still needs a decision')
        self.assertEqual(pipelines.run('main', pid)['phase'], 'waiting')
        self.assertFalse((self.root / 'write.txt').exists())
        pipelines.resume_manual('main', pid, 'judgment', {'disposition': 'failed', 'value': 'Rejected'}, 'Observed failure')
        self.assertEqual(pipelines.run('main', pid)['phase'], 'failed')
        self.assertFalse((self.root / 'write.txt').exists())
        pipelines.resume_manual('main', pid, 'judgment',
            {'disposition': 'completed', 'value': 'actual downstream artifact'}, 'Explicit reviewed result')
        final = pipelines.run('main', pid)
        self.assertEqual(final['phase'], 'completed')
        self.assertEqual((self.root / 'write.txt').read_text(), 'actual downstream artifact')

    def test_process_death_after_effect_reconciles_without_second_write(self):
        pipelines = Pipelines(self.engine)
        pid = pipelines.create('main', 'interrupted-write', [self.write_task()])['pipeline_id']
        self.engine.close()
        code = """import os,sys
from kageyoni.engine import Engine
from kageyoni.workspaces.pipeline import Pipelines
engine=Engine(sys.argv[1])
Pipelines._after_effect=lambda self,p,key: os._exit(23)
Pipelines(engine).run('main',sys.argv[2])
"""
        child = subprocess.run([sys.executable, '-c', code, str(self.path), pid],
                               capture_output=True, text=True, timeout=10)
        self.engine = Engine(self.path)
        self.assertEqual(child.returncode, 23, child.stderr)
        self.assertEqual((self.root / 'write.txt').read_text(), 'actual downstream artifact')
        pipelines = Pipelines(self.engine)
        with self.assertRaises(Rejected):
            pipelines.run('main', pid)
        repaired = pipelines.reconcile('main', pid)
        self.assertEqual(repaired['phase'], 'completed')
        self.assertEqual(len(repaired['tasks']['write']['attempts']), 1)
        again = pipelines.run('main', pid)
        self.assertEqual(again['phase'], 'completed')
        self.assertEqual(len(again['tasks']['write']['attempts']), 1)
        self.assertEqual(sha((self.root / 'write.txt').read_bytes()), sha('actual downstream artifact'))

    def test_policy_needs_actual_supported_trial_and_rollback_keeps_history(self):
        operations = Operations(self.engine)
        policy = operations.propose_policy('pipeline.write_file',
            {'check_order': ['size', 'utf8', 'sha256']}, 'Check size before decoding oversized artifacts')
        with self.assertRaises(Rejected):
            operations.activate_policy(policy['event_id'], 'invented-trial')
        cases = [{'content_base64': base64.b64encode(data).decode(),
                  'max_bytes': maximum, 'expected_sha256': sha(data)}
                 for data, maximum in ((b'valid', 5), (b'oversized', 2))]
        trial = operations.trial_policy(policy['event_id'], cases)
        self.assertTrue(trial['supported'])
        self.assertLess(trial['candidate_checks'], trial['baseline_checks'])
        activation = operations.activate_policy(policy['event_id'], trial['event_id'])
        run = Pipelines(self.engine).create('main', 'policy-effect', [self.write_task()])
        written = Pipelines(self.engine).run('main', run['pipeline_id'])
        self.assertEqual(written['phase'], 'completed')
        check = written['tasks']['write']['attempts'][0]['policy_check']
        self.assertEqual(check['policy_id'], policy['event_id'])
        prior = operations.status()['operation_count']
        operations.rollback_policy('pipeline.write_file', activation['event_id'])
        self.assertGreater(operations.status()['operation_count'], prior)
        self.assertEqual(Pipelines(self.engine).read('main', run['pipeline_id'])['tasks']['write']['attempts'][0]['policy_check'], check)
        next_check = operations.check_artifact('pipeline.write_file', b'valid', 5, sha(b'valid'))
        self.assertIsNone(next_check['policy_id'])
        self.assertTrue(next_check['accepted'])

    def test_policy_cannot_drop_checks_or_activate_from_only_success_cases(self):
        operations = Operations(self.engine)
        with self.assertRaises(Rejected):
            operations.propose_policy('artifact', {'check_order': ['size', 'utf8']}, 'Dropping integrity check')
        policy = operations.propose_policy('artifact', {'check_order': ['size', 'utf8', 'sha256']}, 'Candidate order')
        case = {'content_base64': base64.b64encode(b'ok').decode(), 'max_bytes': 5, 'expected_sha256': sha(b'ok')}
        trial = operations.trial_policy(policy['event_id'], [case, case])
        self.assertFalse(trial['supported'])
        with self.assertRaises(Rejected):
            operations.activate_policy(policy['event_id'], trial['event_id'])


if __name__ == '__main__':
    unittest.main()
