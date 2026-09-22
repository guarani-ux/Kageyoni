"""One connected V4–V8 journey on a new, explicitly synthetic database.

The document bodies come from this journey. Their compiled artifact becomes an
acceptance-test input for a real local repair and a pipeline output. Portable
recovery verifies database/artifact bytes, then explicitly relocates external
trees; an archive alone never grants authority over the old filesystem roots.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from examples.v4_demo import setup as setup_world
from kageyoni.application import Application
from kageyoni.engine import Engine, Rejected, digest
from kageyoni.intelligence.network import Network
from kageyoni.intelligence.transfer import Transfers
from kageyoni.operations import Operations
from kageyoni.persistence.artifacts import Artifacts
from kageyoni.persistence.migrations import install_all
from kageyoni.workspaces.contracts import checkpoint
from kageyoni.workspaces.documents import Documents
from kageyoni.workspaces.pipeline import Pipelines
from kageyoni.workspaces.repository import Repository, tree_digest


def _sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def _save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _rejected(call):
    try:
        call()
    except Rejected as error:
        return str(error)
    raise AssertionError('The negative control unexpectedly succeeded')


def _citation(source, substring=None):
    content = source['text']
    start = 0 if substring is None else content.index(substring)
    return dict(source_id=source['source_id'], revision=source['revision'], digest=source['digest'],
                start=start, end=len(content) if substring is None else start + len(substring))


def _document(engine, root, character, method, direction):
    """Transfer one existing node's procedure to actual recorded journey text."""
    app = Application(engine)
    transition = app.transitions.enter('main', character, 'document-enter-' + character,
        source_ids=[character, 'objective', 'promise', 'journey:turn:play-offer', 'journey:turn:play-accept'])
    wid = transition['workspace_id']
    documents = Documents(engine)
    captured = {}
    for source_id, record_id, field in (
        ('departure-title', 'objective', 'title'), ('departure-phase', 'objective', 'phase'),
        ('promise-question', 'promise', 'question'), ('promise-phase', 'promise', 'phase'),
        ('accepted-terms', 'journey:turn:play-accept', 'text')):
        captured[source_id] = documents.world_source(wid, character + ':' + source_id,
            record_id, ['data', field], source_id)
    metrics = documents.acquire_file(wid, character + ':priorities', str(root / 'priorities.txt'),
        'priorities', 'Synthetic priority fixture', 'Synthetic priority fixture',
        datetime.now(timezone.utc).isoformat())
    section_metrics = {
        'departure': {'priority': {'value': 2, 'evidence': _citation(metrics, '2')}},
        'promise': {'priority': {'value': 8, 'evidence': _citation(metrics, '8')}}}
    brief = dict(brief_id='journey-handoff-' + character, title='Recorded journey handoff',
        audience='The next operator', purpose='Preserve the completed departure and unresolved promise without inventing a meeting date.',
        sections=[
            dict(id='departure', heading='Completed departure', field='departure',
                 claims=[_citation(captured['departure-title']), _citation(captured['departure-phase'])],
                 metrics=section_metrics['departure']),
            dict(id='promise', heading='Open promise', field='promise',
                 claims=[_citation(captured['promise-question']), _citation(captured['promise-phase'])],
                 metrics=section_metrics['promise']),
            dict(id='date', heading='Meeting date', field='meeting_date', required=False, claims=[], metrics={})],
        obligations=[dict(id='preserve-promise', status='required', evidence=_citation(captured['accepted-terms']))])
    baseline = documents.draft(wid, 'baseline-draft-' + character, brief)
    mapping = dict(destination_domain='document', roles={'observer': 'editor', 'evidence': 'material'},
        destination_roles=['editor', 'material'],
        destination_relationships=[dict(source='editor', relation='attends_to', target='material')],
        field_map={'attention': 'priority'})
    transfers = Transfers(engine)
    transfer = transfers.propose(wid, method['method_id'], method['revision'], 'document-transfer-' + character, mapping)
    expected = ['departure', 'promise'] if direction == 'minimize' else ['promise', 'departure']
    trial = transfers.run_trial(transfer['transfer_id'], 'document-trial-' + character, [
        dict(case_id='supported-order', candidates=[dict(id=key, metrics=value) for key, value in section_metrics.items()],
             expected_phase='completed', expected_order=expected),
        dict(case_id='unsupported-value-blocks', candidates=[dict(id='missing', metrics={})],
             expected_phase='blocked', expected_order=[])])
    draft = documents.draft(wid, 'qualified-draft-' + character, brief, transfer_trial_id=transfer['transfer_id'])
    inquiry = documents.inquire(wid, 'journey-inquiry-' + character, 'What remains open, and when is the meeting?',
        ['promise', 'meeting_date'], [dict(field='promise', evidence=_citation(captured['promise-question']))])
    assert trial['status'] == 'qualified' and draft['section_order'][:2] == expected
    assert draft['unknowns'] == ['meeting_date'] and inquiry['unknowns'] == ['meeting_date']
    assert draft['obligations'][0]['status'] == 'required'
    return dict(character_id=character, node_id=draft['node_id'], transition=transition,
        workspace_id=wid, method=method, sources=captured, metric_source=metrics, baseline=baseline,
        transfer=transfer, trial=trial, draft=draft, inquiry=inquiry)


def run(destination):
    root = Path(destination).absolute()
    root.mkdir(parents=True, exist_ok=False)
    evidence = root / 'evidence'
    evidence.mkdir()
    engine = Engine(root / 'synthetic.sqlite')
    restored = None
    try:
        install_all(engine)
        fixture = setup_world(engine)
        app = Application(engine)
        app.encounters.start('main', 'passage', 1, 'journey', 'start-journey',
                             engine.branch('main')['revision'], fixture['participants'])
        journey = []
        for action in ('bridge', 'offer', 'shield', 'accept', 'depart'):
            journey.append(app.encounters.act('main', 'journey', action, 'play-' + action,
                                             engine.branch('main')['revision']))
        world = app.encounters.inspect('main', 'journey')
        frozen = checkpoint(engine, 'main')
        focus = next(p['value'] for p in engine.properties('main', entity_id='traveler')
                     if p['property_id'] == 'fixture.focus')
        assert world['phase'] == 'completed' and focus == 2
        assert engine.get('main', 'promise')['data']['phase'] == 'open'
        _save(evidence / 'world-checkpoint.json', dict(checkpoint=frozen, world=world,
            records=engine.state('main'), context=engine.context('main')))

        methods = {}
        for character, direction, source_id in (
            ('traveler', 'minimize', 'journey:turn:play-offer'),
            ('guard', 'maximize', 'journey:turn:play-accept')):
            node = app.nodes.read('main', character)['node_id']
            source = engine.get('main', source_id)
            definition = dict(name='Explicit ' + character + ' ordering procedure',
                rationale='An owner-authored synthetic experiment linked to the exact recorded dialogue. The dialogue alone does not prove this method or expertise.',
                domains=['journey-handoff'], operation={'kind': 'constraint_rank', 'params': {
                    'criteria': [{'field': 'attention', 'weight': 1, 'direction': direction, 'required': True}]}},
                preconditions=['sources_current'], failure_conditions=['stale_source'],
                checking_procedure=['check_source_fields', 'recompute_scores'], visibility='public',
                roles=['observer', 'evidence'],
                relationships=[{'source': 'observer', 'relation': 'attends_to', 'target': 'evidence'}])
            method = app.methods.create('main', node, 'method-' + character, frozen['revision'], definition,
                [dict(domain=source['domain'], id=source_id, record_revision=source['version'], snapshot_hash=digest(source))])
            app.methods.assign('main', node, method['method_id'], method['revision'], 'assign-' + character,
                frozen['revision'], 'experimental', 'Authorize only this declared procedure for bounded synthetic trials; no mastery claim.')
            methods[character] = method
        (root / 'priorities.txt').write_text('Synthetic supplied priority values, not inferred character stats.\nDeparture priority: 2\nPromise priority: 8\n', encoding='utf-8')
        documents = [_document(engine, root, c, methods[c], direction)
                     for c, direction in (('traveler', 'minimize'), ('guard', 'maximize'))]
        assert checkpoint(engine, 'main') == frozen
        assert documents[0]['node_id'] != documents[1]['node_id']
        assert documents[1]['baseline']['section_order'] != documents[1]['draft']['section_order']
        for item in documents:
            (evidence / (item['character_id'] + '-draft.md')).write_text(item['draft']['text'], encoding='utf-8')

        network = Network(engine)
        draft_ids = [item['draft']['draft_id'] for item in documents]
        waiting = network.compose('main', 'collective-waiting', documents[0]['workspace_id'], draft_ids)
        assert waiting['phase'] == 'waiting' and waiting['artifact'] is None
        synthesis = dict(text='# Synthetic journey operator handoff\n\n'
            'Both configured orderings are retained. Their difference remains an unresolved editorial judgment.\n\n'
            + '\n\n'.join(item['draft']['text'] for item in documents),
            uses=[dict(draft_id=item['draft']['draft_id'], quote=item['draft']['text']) for item in documents],
            rationale='Explicitly authored compilation of both actual bodies. This demonstrates consumption, not autonomous synthesis or reader benefit.')
        composition = network.compose('main', 'collective-authored', documents[0]['workspace_id'], draft_ids, synthesis)
        composition_artifact = Artifacts(engine).read(composition['artifact']['artifact_id'])
        assert composition_artifact['content'].decode() == synthesis['text']
        assert all(r['disposition'] == 'consumed_verbatim' for r in composition['receptions'])
        assert composition['disagreements']
        (evidence / 'collective-handoff.md').write_bytes(composition_artifact['content'])

        repository_transition = app.transitions.enter('main', 'guard', 'repository-enter', kind='repository',
            source_ids=['guard', 'promise', 'journey:turn:play-accept'])
        repo_transfer = Transfers(engine).propose(repository_transition['workspace_id'],
            methods['guard']['method_id'], methods['guard']['revision'], 'repository-transfer',
            dict(destination_domain='repository', roles={'observer': 'checker', 'evidence': 'candidate'},
                destination_roles=['checker', 'candidate'],
                destination_relationships=[dict(source='checker', relation='attends_to', target='candidate')],
                field_map={'attention': 'checks'}))
        source_dir = root / 'repository-source'
        source_dir.mkdir()
        source_code = "def unknown_fields(text):\n    return sorted({line.split(':', 1)[1].split('.', 1)[0].strip() for line in text.splitlines() if line.startswith('UNKNOWN: ')})\n"
        fixed_code = source_code.replace("'UNKNOWN: '", "'Unknown: '")
        (source_dir / 'handoff.py').write_bytes(source_code.encode('utf-8'))
        (source_dir / 'handoff.md').write_bytes(composition_artifact['content'])
        tests = ("import hashlib\nfrom pathlib import Path\nimport unittest\nfrom handoff import unknown_fields\n"
                 "class HandoffAcceptance(unittest.TestCase):\n"
                 "    def test_exact_collective_body_and_unknown(self):\n"
                 "        text = Path('handoff.md').read_bytes()\n"
                 f"        self.assertEqual(hashlib.sha256(text).hexdigest(), {composition_artifact['digest']!r})\n"
                 "        self.assertEqual(unknown_fields(text.decode('utf-8')), ['meeting_date'])\n"
                 "    def test_no_unknown_is_not_invented(self):\n"
                 "        self.assertEqual(unknown_fields('The departure is completed.'), [])\n"
                 "    def test_repeated_unknown_is_not_two_facts(self):\n"
                 "        self.assertEqual(unknown_fields('Unknown: meeting_date.\\nUnknown: meeting_date.'), ['meeting_date'])\n")
        (source_dir / 'test_handoff.py').write_bytes(tests.encode('utf-8'))
        baseline = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover'], cwd=source_dir,
                                  capture_output=True, text=True, timeout=30)
        assert baseline.returncode != 0 and 'FAIL:' in baseline.stderr
        baseline_result = dict(returncode=baseline.returncode, output=(baseline.stdout + baseline.stderr)[-50000:],
                               source_digest=tree_digest(source_dir), composition_id=composition['composition_id'],
                               artifact_digest=composition_artifact['digest'])
        _save(evidence / 'repository-baseline.json', baseline_result)

        repository = Repository(engine)
        candidate = repository.prepare('main', 'repair-handoff-parser', source_dir, root / 'repository-candidate',
            [dict(path='handoff.py', before_sha256=_sha(source_code), content=fixed_code)],
            ['python', '-m', 'unittest', 'discover'], repo_transfer['transfer_id'])
        output_root = root / 'pipeline-output'
        output_root.mkdir()
        pipelines = Pipelines(engine)
        pipeline = pipelines.create('main', 'checked-collective-delivery', [
            dict(id='check-repair', kind='repository_check', config=dict(candidate_id=candidate['candidate_id'])),
            dict(id='read-synthesis', kind='artifact_read', dependencies=[dict(task_id='check-repair', type='REQUIRES')],
                 config=dict(artifact_id=composition_artifact['artifact_id'], expected_sha256=composition_artifact['digest'],
                             composition_id=composition['composition_id'])),
            dict(id='write-handoff', kind='write_file', dependencies=[dict(task_id='read-synthesis', type='USES')],
                 config=dict(root=str(output_root), path='handoff.md', content_from='read-synthesis',
                             expected_sha256=composition_artifact['digest']))])
        checked_flow = pipelines.run('main', pipeline['pipeline_id'], max_steps=1)
        checked = repository.read('main', candidate['candidate_id'])
        assert checked['phase'] == 'checked' and checked['attempts'][-1]['tests'] == 3
        assert checked_flow['tasks']['read-synthesis']['phase'] == 'pending'
        promotion_block = _rejected(lambda: repository.promote('main', candidate['candidate_id'], root / 'premature-promotion'))
        trial_artifact = repository.trial_artifact('main', candidate['candidate_id'], 'repair-trial-evidence')
        repo_trial = Transfers(engine).record_trial(repo_transfer['transfer_id'], 'repair-qualified',
            trial_artifact['artifact']['artifact_id'], trial_artifact['checks'],
            'Three actual acceptance tests passed against this exact candidate and collective body. No general coding competence is inferred.')
        promoted = repository.promote('main', candidate['candidate_id'], root / 'repository-promoted')
        finished_flow = pipelines.run('main', pipeline['pipeline_id'])
        assert finished_flow['phase'] == 'completed'
        assert (output_root / 'handoff.md').read_bytes() == composition_artifact['content']
        assert (root / 'repository-promoted' / 'handoff.md').read_bytes() == composition_artifact['content']
        assert checkpoint(engine, 'main') == frozen

        returns = [app.transitions.return_to_world(item['transition']['transition_id'], 'return-' + item['character_id'])
                   for item in documents]
        returns.append(app.transitions.return_to_world(repository_transition['transition_id'], 'return-repository'))
        assert all(result['world_unchanged'] for result in returns)
        before_artifacts = {item['artifact_id']: item['digest'] for item in Artifacts(engine).manifest()}
        original_verification = engine.verify()
        exported = Operations(engine).export_bundle(root / 'portable.zip')
        imported = Operations.import_bundle(root / 'portable.zip', root / 'reopened')
        restored = Engine(imported['path'])
        restored_app = Application(restored)
        assert checkpoint(restored, 'main') == frozen
        assert restored_app.encounters.inspect('main', 'journey') == world
        assert {item['artifact_id']: item['digest'] for item in Artifacts(restored).manifest()} == before_artifacts
        for artifact_id, expected in before_artifacts.items():
            assert _sha(Artifacts(restored).read(artifact_id)['content']) == expected
        restored_composition = Network(restored).read_composition('main', composition['composition_id'])
        assert restored_composition['artifact']['digest'] == composition_artifact['digest']
        relocation_block = _rejected(lambda: Pipelines(restored).run('main', pipeline['pipeline_id']))

        # External effects are intentionally outside the archive. The demo
        # separately copies known fixture roots, validates them, and authorizes
        # the relocated paths through the normal rebind APIs.
        relocated = root / 'reopened' / 'external'
        relocated.mkdir()
        paths = {}
        for name in ('repository-source', 'repository-candidate', 'repository-promoted', 'pipeline-output'):
            paths[name] = relocated / name
            shutil.copytree(root / name, paths[name], ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        rebound_candidate = Repository(restored).rebind('main', candidate['candidate_id'], paths['repository-source'],
            paths['repository-candidate'], paths['repository-promoted'])
        rebound_pipeline = Pipelines(restored).rebind('main', pipeline['pipeline_id'], {str(output_root): str(paths['pipeline-output'])})
        attempts_before = {key: len(value['attempts']) for key, value in rebound_pipeline['tasks'].items()}
        replayed_flow = Pipelines(restored).run('main', pipeline['pipeline_id'])
        assert attempts_before == {key: len(value['attempts']) for key, value in replayed_flow['tasks'].items()}
        assert replayed_flow['phase'] == 'completed'
        assert tree_digest(paths['repository-promoted']) == promoted['promoted_digest']
        assert (paths['pipeline-output'] / 'handoff.md').read_bytes() == composition_artifact['content']
        restored_verification = restored.verify()
        assert checkpoint(restored, 'main') == frozen

        checks = dict(journey_uses_actual_will_cost=focus == 2,
            required_continuation_preserved=world['continuations'] == [dict(loop_id='promise', record_id='promise')],
            stable_character_nodes=all(restored_app.nodes.read('main', item['character_id'])['node_id'] == item['node_id'] for item in documents),
            source_records_from_completed_journey=all(item['transition']['checkpoint'] == frozen for item in documents),
            actual_destination_trials=all(item['trial']['status'] == 'qualified' for item in documents),
            differentiated_document_order=documents[0]['draft']['section_order'] != documents[1]['draft']['section_order'],
            unknowns_and_obligations_retained=all(item['draft']['unknowns'] == ['meeting_date'] and item['draft']['obligations'][0]['status'] == 'required' for item in documents),
            actual_contribution_bodies_consumed=all(item['draft']['text'] in synthesis['text'] for item in documents),
            unresolved_disagreement_retained=bool(composition['disagreements']),
            real_repository_baseline_fails=baseline.returncode != 0,
            real_repair_tests_pass=checked['attempts'][-1]['phase'] == 'completed' and checked['attempts'][-1]['tests'] == 3,
            repository_trial_binds_exact_candidate=repo_trial['status'] == 'qualified' and promoted['promoted_digest'] == checked['candidate_digest'],
            unqualified_promotion_blocked=bool(promotion_block),
            pipeline_consumes_collective_artifact=finished_flow['tasks']['read-synthesis']['result'] == synthesis['text'],
            exact_world_return=all(item['world_unchanged'] for item in returns),
            export_import_preserves_artifact_bytes=len(before_artifacts) == len(Artifacts(restored).manifest()),
            external_roots_require_explicit_rebind=bool(relocation_block) and bool(imported['external_dependencies']),
            completed_effect_not_repeated=attempts_before == {key: len(value['attempts']) for key, value in replayed_flow['tasks'].items()},
            reopened_world_checkpoint_exact=checkpoint(restored, 'main') == frozen,
            both_databases_verify=original_verification['ok'] and restored_verification['ok'])
        assert all(checks.values()), checks
        report = dict(synthetic=True, campaign_writes=0, ai_api_calls=0, checks=checks,
            paths=dict(original_database=str(engine.path), reopened_database=str(restored.path),
                       synthesis=str(evidence / 'collective-handoff.md'), pipeline_output=str(output_root / 'handoff.md'),
                       relocated_output=str(paths['pipeline-output'] / 'handoff.md'),
                       promoted_repository=str(root / 'repository-promoted'), relocated_repository=str(paths['repository-promoted'])),
            checkpoint=frozen, journey=dict(receipts=journey, final=world, focus_remaining=focus),
            documents=documents, composition_waiting=waiting, composition=composition,
            repository=dict(transition=repository_transition, transfer=repo_transfer, trial=repo_trial,
                            baseline=baseline_result, checked=checked, promoted=promoted,
                            rebound=rebound_candidate, unqualified_promotion_rejection=promotion_block),
            pipeline=finished_flow, replayed_pipeline=replayed_flow, world_returns=returns,
            export=exported, imported=imported, relocation_rejection=relocation_block,
            artifact_manifest=Artifacts(restored).manifest(),
            verification=dict(original=original_verification, reopened=restored_verification),
            limits=['All world events are disposable synthetic fixtures; no campaign was opened.',
                    'Compilation is explicitly authored and consumes exact bodies; no live model comparison or autonomous semantic synthesis is claimed.',
                    'Recorded order differences and passing local tests do not establish general expertise or practical advantage.',
                    'The portable bundle includes database and registered artifacts. External repository trees/effects were copied separately and explicitly rebound.'])
        _save(evidence / 'full-chain-report.json', report)
        return report
    finally:
        if restored is not None:
            restored.close()
        engine.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()
    result = run(arguments.output)
    print(json.dumps(dict(checks=result['checks'], report=str(Path(arguments.output).absolute() / 'evidence' / 'full-chain-report.json')), indent=2))
