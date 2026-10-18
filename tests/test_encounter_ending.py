"""Opt-in native endings on disposable synthetic worlds, with actual receipts.

These fixtures demonstrate episode cleanup and cancellation, not full combat
or canonical history. Shared cost/equipment/history are deliberately retained.
"""
from copy import deepcopy
import json

import pytest

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.persistence.migrations import install_encounters
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.workspaces.world import Encounters, _validate


EVIDENCE = [{'note': 'Explicit synthetic ending qualification parameter; not campaign canon.'}]


def record(domain, rid, **data):
    return dict(op='create', id=rid, domain=domain, status='proposed',
                visibility='public', evidence=EVIDENCE, data=data)


def patch(rid, **data):
    return dict(op='patch', id=rid, data=data, evidence=EVIDENCE)


def suffix(value):
    return {'$encounter': value}


def definition(*, ending=True, max_steps=10):
    spec = dict(title='Optional synthetic practice ending', roles=['visitor', 'keeper'],
                visibility='public', initial_state='offered', max_steps=max_steps,
                loops=[dict(id='cost', kind='cost', required=False, depends_on=[],
                            continuable=False, cancellable=True),
                       dict(id='exchange', kind='exchange', required=True, depends_on=[],
                            continuable=False, cancellable=True),
                       dict(id='reminder', kind='remember', required=False, depends_on=[],
                            continuable=True, cancellable=True)],
                states={'offered': dict(phase='active', outcome='unresolved', actions=['consent']),
                        'engaged': dict(phase='active', outcome='unresolved', actions=['exert', 'react']),
                        'withdrawn': dict(phase='completed', outcome='not_achieved', actions=[])},
                actions={})
    spec['actions']['consent'] = dict(label='Keeper explicitly consents to this synthetic practice',
        actor_role='keeper', kind='event', resolve_loops=[], next_state='engaged',
        detach_loops=[dict(loop_id='reminder', record_id='earlier-knowledge')],
        payload={'changes': [record('scene', suffix('scene'), name='One episode',
                                    location='studio', phase='active', round=0,
                                    context='No contact accepted yet.'),
                             record('participation', suffix('visitor'), scene=suffix('scene'),
                                    character={'$role': 'visitor'}, position='near line',
                                    actions_remaining=1, active_effects='guard'),
                             record('participation', suffix('keeper'), scene=suffix('scene'),
                                    character={'$role': 'keeper'}, position='far line',
                                    actions_remaining=1, active_effects='reaction pending')]})
    spec['actions']['exert'] = dict(label='Accept a native expenditure and contact result',
        actor_role='visitor', kind='event', resolve_loops=['cost'], next_state='engaged',
        payload={'changes': [patch('visitor-effort', quantity=2),
                             patch(suffix('scene'), context='A public counter was accepted.'),
                             patch(suffix('visitor'), position='contact', actions_remaining=0)]})
    spec['actions']['react'] = dict(label='Ask the keeper for their own reaction',
        actor_role='keeper', kind='judgment', resolve_loops=[], next_state='engaged',
        payload=dict(question='Which current supported response do you choose?',
                     unknowns=['The keeper has not selected a reaction.'],
                     choices=[dict(id='wait', label='Wait without claiming a result', next_state='engaged')]))
    if ending:
        spec['ending'] = dict(label='End this practice and step off the marked line', next_state='withdrawn',
            changes=[patch(suffix('scene'), phase='closed'),
                     patch(suffix('visitor'), position='off line', actions_remaining=0, active_effects=''),
                     patch(suffix('keeper'), position='off line', actions_remaining=0, active_effects='')])
    return spec


@pytest.fixture
def native(tmp_path):
    path = tmp_path / 'synthetic.sqlite'
    engine = Engine(path)
    assert engine.verify()['ok'] and engine.validate_registry()['ok']
    install_encounters(engine)
    changes = [record('location', 'studio', name='Synthetic studio', kind='room'),
               record('character', 'visitor', name='Visitor', entity_kind='person', location='studio'),
               record('character', 'keeper', name='Keeper', entity_kind='person', location='studio'),
               record('character', 'outsider', name='Bystander', entity_kind='person', location='studio'),
               record('resource', 'visitor-effort', holder='visitor', name='Fictional practice effort',
                      quantity=3, unit='synthetic effort'),
               record('item', 'practice-item', name='Soft practice implement', condition='intact'),
               record('loadout', 'practice-loadout', item='practice-item', holder='visitor',
                      slot='practice', equipped=1),
               record('knowledge', 'earlier-knowledge', holder='visitor', assertion='An earlier result exists.',
                      attitude='knows', basis='Explicit fixture declaration.'),
               record('historical_account', 'earlier-account', author='keeper',
                      assertion='An attributed earlier account.', interpretation='No mastery inferred.')]
    engine.apply(dict(api_version=3, branch='main', request_id='fixture', expected_revision=0,
                      actor='fixture', kind='scene', narrative='Create a disposable synthetic ending fixture',
                      changes=changes))
    value = {'engine': engine, 'world': Encounters(engine), 'path': path}
    try:
        yield value
        assert value['engine'].verify()['ok']
        assert value['engine'].validate_registry()['ok']
    finally:
        value['engine'].close()


def start(native, *, spec=None, eid='practice', did='practice'):
    world, engine = native['world'], native['engine']
    world.define(did, 1, spec or definition(), 'define:' + did)
    return world.start('main', did, 1, eid, 'start:' + eid, engine.branch('main')['revision'],
                       {'visitor': 'visitor', 'keeper': 'keeper'}, viewer='visitor')


def act(native, aid, *, actor='keeper', eid='practice', request_id=None):
    return native['world'].act('main', eid, aid, request_id or 'act:' + aid,
                              native['engine'].branch('main')['revision'], viewer=actor)


def end(native, *, actor='visitor', viewer='visitor', eid='practice', request_id='end', **kw):
    kw.setdefault('expected_revision', native['engine'].branch('main')['revision'])
    return native['world'].end('main', eid, actor, request_id, viewer=viewer, **kw)


def event_command(native, receipt):
    return json.loads(native['engine'].db.execute('SELECT command_json FROM events WHERE id=?',
                       (receipt['world_receipt']['event_id'],)).fetchone()[0])


def snapshot(native):
    engine = native['engine']
    return (engine.state(), engine.branch('main'),
            [tuple(r) for r in engine.db.execute('SELECT * FROM encounter_instances ORDER BY encounter_id')],
            [tuple(r) for r in engine.db.execute('SELECT * FROM encounter_events ORDER BY encounter_id,revision')],
            [tuple(r) for r in engine.db.execute('SELECT * FROM events ORDER BY revision')])


def test_real_cleanup_retains_paid_cost_equipment_history_and_resolved_loops(native):
    start(native); act(native, 'consent'); act(native, 'exert', actor='visitor')
    engine, world = native['engine'], native['world']
    retained = {rid: engine.get('main', rid) for rid in
                ('visitor-effort', 'practice-item', 'practice-loadout', 'earlier-knowledge', 'earlier-account')}
    prior_steps = world.inspect('main', 'practice')['steps']
    receipt = end(native)
    assert receipt['phase'] == 'completed' and receipt['outcome'] == 'not_achieved'
    assert receipt['world_receipt']['changed'] == ['practice:scene', 'practice:visitor', 'practice:keeper']
    scene = engine.get('main', 'practice:scene')['data']
    assert scene['phase'] == 'closed' and scene['context'] == 'A public counter was accepted.'
    for rid in ('practice:visitor', 'practice:keeper'):
        data = engine.get('main', rid)['data']
        assert data['position'] == 'off line' and data['actions_remaining'] == 0 and data['active_effects'] == ''
    assert {rid: engine.get('main', rid) for rid in retained} == retained
    assert retained['visitor-effort']['data']['quantity'] == 2
    state = world.inspect('main', 'practice')
    assert state['loops']['cost']['phase'] == 'resolved'
    assert state['loops']['exchange']['phase'] == 'cancelled'
    assert state['loops']['reminder']['phase'] == 'detached'
    assert state['continuations'] == [{'loop_id': 'reminder', 'record_id': 'earlier-knowledge'}]
    assert state['pending'] is None and state['steps'] == prior_steps and state['next_actions'] == []
    command = event_command(native, receipt)
    assert command['actor'] == 'visitor' and command['kind'] == 'decision'
    assert command['judgment']['encounter_ending']['attribution'] == 'participant'
    assert command['judgment']['encounter_ending']['definition_digest'] == digest(_validate(definition()))


def test_preconsent_absent_targets_close_without_creating_geometry(native):
    start(native)
    engine = native['engine']; before = engine.state(); revision = engine.branch('main')['revision']
    receipt = end(native, actor='keeper', viewer='keeper')
    assert receipt['world_receipt']['changed'] == []
    assert receipt['world_receipt']['revision'] == revision + 1 and engine.state() == before
    assert engine.get('main', 'practice:scene') is None
    assert native['world'].inspect('main', 'practice')['phase'] == 'completed'
    assert {x['phase'] for x in native['world'].inspect('main', 'practice')['loops'].values()} == {'cancelled'}
    assert {d['ref_id'] for d in event_command(native, receipt)['dependencies']} == {'visitor', 'keeper'}


def test_owner_stop_is_maintenance_without_participant_voice(native):
    start(native); act(native, 'consent')
    receipt = end(native, actor=None, viewer=None)
    command = event_command(native, receipt)
    assert command['kind'] == 'maintenance' and command['actor'] == 'encounter-maintenance'
    assert command['judgment']['encounter_ending']['actor'] is None
    assert command['judgment']['encounter_ending']['attribution'] == 'maintenance'
    assert 'choice' not in command and not command.get('observations')
    assert command['narrative'].startswith('Operator stop: ')


@pytest.mark.parametrize('actor,viewer', [('outsider', 'outsider'), ('keeper', 'visitor'),
                                         (None, 'visitor'), ('outsider', None)])
def test_invalid_callers_leave_every_native_state_unchanged(native, actor, viewer):
    start(native); before = snapshot(native)
    with pytest.raises(Rejected):end(native, actor=actor, viewer=viewer)
    assert snapshot(native) == before


def test_missing_opt_in_and_stale_revisions_do_not_partially_close(native):
    start(native, spec=definition(ending=False), did='legacy', eid='legacy')
    before = snapshot(native)
    with pytest.raises(Rejected, match='no callable ending'):end(native, eid='legacy')
    assert snapshot(native) == before
    start(native); act(native, 'consent'); before = snapshot(native)
    with pytest.raises(Rejected, match='stale branch'):
        end(native, expected_revision=native['engine'].branch('main')['revision'] - 1)
    with pytest.raises(Rejected, match='stale encounter'):
        end(native, expected_encounter_revision=1)
    assert snapshot(native) == before


def test_exact_retry_after_reopen_and_altered_request_conflict(native):
    start(native); act(native, 'consent')
    revision = native['engine'].branch('main')['revision']
    state_revision = native['world'].inspect('main', 'practice')['state_revision']
    receipt = end(native, expected_revision=revision, expected_encounter_revision=state_revision)
    after = snapshot(native)
    native['engine'].close(); native['engine'] = Engine(native['path']); native['world'] = Encounters(native['engine'])
    replay = end(native, expected_revision=revision, expected_encounter_revision=state_revision)
    assert replay == dict(receipt, replayed=True) and snapshot(native) == after
    with pytest.raises(Rejected, match='different payload'):
        end(native, actor='keeper', viewer='keeper', expected_revision=revision,
            expected_encounter_revision=state_revision)
    with pytest.raises(Rejected, match='different payload'):
        end(native, expected_revision=revision, expected_encounter_revision=state_revision + 1)
    with pytest.raises(Rejected, match='closed'):end(native, request_id='another-ending')
    assert snapshot(native) == after


def test_native_ending_is_reachable_after_step_budget_and_clears_pending_reaction(native):
    start(native, spec=definition(max_steps=2)); act(native, 'consent')
    waiting = act(native, 'react')
    assert waiting['phase'] == 'waiting' and native['world'].inspect('main', 'practice')['pending']
    blocked = act(native, 'react', request_id='exhausted')
    assert blocked['phase'] == 'blocked' and native['world'].inspect('main', 'practice')['steps'] == 2
    receipt = end(native, actor='keeper', viewer='keeper')
    assert receipt['phase'] == 'completed'
    assert native['world'].inspect('main', 'practice')['pending'] is None
    assert native['world'].inspect('main', 'practice')['steps'] == 2


def test_ending_also_closes_waiting_reaction_before_any_budget_block(native):
    start(native); act(native, 'consent'); act(native, 'react')
    assert native['world'].inspect('main', 'practice', viewer='keeper')['pending']['action_id'] == 'react'
    receipt = end(native)
    assert receipt['phase'] == 'completed' and native['world'].inspect('main', 'practice')['pending'] is None


def test_outer_transaction_rollback_preserves_current_round_then_exact_retry_commits(native):
    start(native); act(native, 'consent'); act(native, 'exert', actor='visitor')
    before = snapshot(native)
    with pytest.raises(RuntimeError, match='outer application interruption'):
        with UnitOfWork(native['engine'].db):
            receipt = end(native)
            assert receipt['phase'] == 'completed'
            assert native['engine'].get('main', 'practice:scene')['data']['phase'] == 'closed'
            raise RuntimeError('outer application interruption')
    assert snapshot(native) == before
    assert end(native)['phase'] == 'completed'
    assert native['engine'].get('main', 'visitor-effort')['data']['quantity'] == 2


def test_late_write_failure_rolls_back_native_cleanup_and_receipt(native, monkeypatch):
    start(native); act(native, 'consent'); before = snapshot(native)
    original = native['world']._write
    def fail(*args, **kw):
        assert native['engine'].get('main', 'practice:scene')['data']['phase'] == 'closed'
        raise RuntimeError('interrupt after actual world cleanup')
    monkeypatch.setattr(native['world'], '_write', fail)
    with pytest.raises(RuntimeError, match='actual world cleanup'):end(native)
    assert snapshot(native) == before
    monkeypatch.setattr(native['world'], '_write', original)
    assert end(native)['phase'] == 'completed'


def test_present_wrong_domain_target_refuses_instead_of_skipping(native):
    spec = definition()
    spec['ending']['changes'].append(patch(suffix('wrong-target'), phase='closed'))
    start(native, spec=spec); act(native, 'consent')
    engine = native['engine']
    engine.apply(dict(api_version=3, branch='main', request_id='wrong-target',
        expected_revision=engine.branch('main')['revision'], kind='scene', actor='fixture',
        narrative='Synthetic adversarial namespace collision',
        changes=[record('resource', 'practice:wrong-target', holder='visitor', name='Do not refund', quantity=1, unit='fixture')]))
    before = snapshot(native)
    with pytest.raises(Rejected, match='domain mismatch'):end(native)
    assert snapshot(native) == before


def test_prefix_overlap_cannot_end_another_native_encounters_geometry(native):
    spec = definition()
    spec['ending']['changes'].append(patch(suffix('return:scene'), phase='closed'))
    start(native, spec=spec)
    start(native, eid='practice:return', did='overlap')
    act(native, 'consent', eid='practice:return', request_id='overlap:consent')
    before = snapshot(native)
    with pytest.raises(Rejected, match='not created by this encounter'):end(native)
    assert snapshot(native) == before
    assert native['engine'].get('main', 'practice:return:scene')['data']['phase'] == 'active'
    assert native['world'].inspect('main', 'practice:return')['phase'] == 'active'


def test_namespace_looking_scene_created_outside_encounter_is_not_owned(native):
    start(native)
    engine = native['engine']
    engine.apply(dict(api_version=3, branch='main', request_id='outside-geometry',
        expected_revision=engine.branch('main')['revision'], kind='scene', actor='fixture',
        narrative='Synthetic adversarial externally created namespace record',
        changes=[record('scene', 'practice:scene', name='An unrelated scene', location='studio', phase='active', round=0)]))
    before = snapshot(native)
    with pytest.raises(Rejected, match='not created by this encounter'):end(native)
    assert snapshot(native) == before


def test_participation_may_not_borrow_an_unowned_scene_for_cleanup(native):
    spec = definition()
    spec['actions']['consent']['payload']['changes'][1]['data']['scene'] = 'practice:outside-scene'
    engine = native['engine']
    engine.apply(dict(api_version=3, branch='main', request_id='outside-scene',
        expected_revision=engine.branch('main')['revision'], kind='scene', actor='fixture',
        narrative='Synthetic adversarial scene dependency',
        changes=[record('scene', 'practice:outside-scene', name='An unrelated scene', location='studio', phase='active', round=0)]))
    start(native, spec=spec); act(native, 'consent'); before = snapshot(native)
    with pytest.raises(Rejected, match='not episode geometry'):end(native)
    assert snapshot(native) == before


def test_runtime_rechecks_actual_owned_geometry_if_loaded_cleanup_is_incomplete(native, monkeypatch):
    start(native); act(native, 'consent'); before = snapshot(native)
    original = native['world']._definition
    def incomplete_loaded_definition(*args):
        # Explicit reader fault injection after actual native creation, without
        # editing persisted definitions or manufacturing fictional SQL state.
        spec = original(*args)
        spec['ending']['changes'] = spec['ending']['changes'][:-1]
        return spec
    monkeypatch.setattr(native['world'], '_definition', incomplete_loaded_definition)
    with pytest.raises(Rejected, match='actual episode geometry'):end(native)
    assert snapshot(native) == before


def test_no_geometry_definition_may_pin_an_empty_cleanup(native):
    spec = definition()
    spec['actions']['consent']['payload']['changes'] = [record('knowledge', suffix('consent-note'),
        holder='keeper', assertion='Only a declared choice was recorded.', attitude='knows')]
    spec['ending']['changes'] = []
    start(native, spec=spec); act(native, 'consent')
    assert end(native)['world_receipt']['changed'] == []
    assert native['engine'].get('main', 'practice:consent-note') is not None


@pytest.mark.parametrize('mutation', [
    lambda s: s['ending'].update(next_state='engaged'),
    lambda s: s['ending'].update(callback='unfamiliar executable'),
    lambda s: s['ending'].update(label=''),
    lambda s: s['ending']['changes'][0].update(op='create'),
    lambda s: s['ending']['changes'][0].update(id='shared-scene'),
    lambda s: s['ending']['changes'][0].update(data={'phase': 'closed', 'context': 'Erase real contact'}),
    lambda s: s['ending']['changes'][0].update(data={'quantity': 3}),
    lambda s: s['ending']['changes'][0].update(expected_version=1),
    lambda s: s['ending']['changes'][0].update(visibility='public'),
    lambda s: s['ending']['changes'][0].update(domain='resource'),
    lambda s: s['ending']['changes'][0].update(evidence=[]),
    lambda s: s['ending']['changes'][1].update(data={'actions_remaining': 1}),
    lambda s: s['ending']['changes'][1].update(data={'actions_remaining': False}),
    lambda s: s['ending']['changes'][1].update(data={'active_effects': 'new boost'}),
    lambda s: s['ending']['changes'][1].update(data={'position': 'off line'}),
    lambda s: s['ending']['changes'].append(deepcopy(s['ending']['changes'][0])),
    lambda s: s['loops'][1].update(cancellable=False),
    lambda s: s['ending'].update(changes=[]),
    lambda s: s['ending']['changes'].pop(),
    lambda s: s['actions']['consent']['payload']['changes'][0].update(id='shared-scene'),
    lambda s: s['actions']['consent']['payload']['changes'][0].update(domain={'$role': 'visitor'}),
])
def test_unsafe_or_nonterminal_ending_is_refused_at_authoring(native, mutation):
    spec = definition(); mutation(spec); before = snapshot(native)
    with pytest.raises(Rejected):native['world'].define('unsafe', 1, spec, 'define:unsafe')
    assert snapshot(native) == before
    assert native['engine'].db.execute('SELECT COUNT(*) FROM encounter_definitions').fetchone()[0] == 0


def test_absent_ending_keeps_legacy_normalization_and_definition_digest(native):
    spec = definition(ending=False)
    # This value was computed from the unchanged pre-ending _validate function.
    normalized = _validate(spec)
    assert 'ending' not in normalized
    assert digest(normalized) == '5c502af6755144f30c63638ec841a1d6d8418748d37f0629b75dd2dec919e3bf'
    receipt = native['world'].define('legacy', 1, spec, 'define:legacy')
    assert receipt['digest'] == digest(normalized)
