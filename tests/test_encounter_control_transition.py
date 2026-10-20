"""Actual authored control transitions have provenance, not fictional effects."""
import json

import pytest

from kageyoni.engine import Engine, Rejected
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.workspaces.world import Encounters
from test_encounter_ending import native, snapshot, event_command


def start_control(native):
    spec = dict(title='Leave an optional synthetic rest without recovery',
        roles=['visitor'], visibility='public', initial_state='offered', max_steps=2,
        loops=[], states={
            'offered': dict(phase='active', outcome='unresolved', actions=['leave']),
            'stopped': dict(phase='completed', outcome='not_achieved', actions=[])},
        actions={'leave': dict(label='Leave without recovery or refund', actor_role='visitor',
            kind='event', resolve_loops=[], next_state='stopped', payload={'changes':[]})},
        ending=dict(label='Stop', next_state='stopped', changes=[]))
    e,w=native['engine'],native['world']
    w.define('control',1,spec,'define-control')
    w.start('main','control',1,'control','start-control',e.branch('main')['revision'],
        {'visitor':'visitor'},viewer='visitor')
    return e.branch('main')['revision']


def leave(native, revision, actor='visitor'):
    return native['world'].act('main','control','leave','leave-control',revision,viewer=actor)


def test_empty_authored_control_is_native_exact_replay_after_reopen(native):
    revision=start_control(native);e=native['engine'];before=e.state()
    receipt=leave(native,revision)
    assert receipt['phase']=='completed' and receipt['outcome']=='not_achieved'
    assert e.state()==before and e.branch('main')['revision']==revision+1
    command=event_command(native,receipt)
    assert command['changes']==[] and command['actor']=='visitor'
    assert command['dependencies']==[dict(kind='record',ref_id='visitor',
        version=e.get('main','visitor')['version'],usage='encounter_transition')]
    assert command['judgment']['encounter_transition']['action_id']=='leave'
    assert not command.get('observations') and not command.get('choice')
    after=snapshot(native)
    e.close();native['engine']=Engine(native['path']);native['world']=Encounters(native['engine'])
    assert leave(native,revision)==dict(receipt,replayed=True)
    assert snapshot(native)==after


def test_empty_control_wrong_actor_stale_and_outer_rollback_preserve_state(native):
    revision=start_control(native);before=snapshot(native)
    for actor,rev in [('keeper',revision),('visitor',revision-1)]:
        with pytest.raises(Rejected):leave(native,rev,actor)
        assert snapshot(native)==before
    with pytest.raises(RuntimeError,match='synthetic interruption'):
        with UnitOfWork(native['engine'].db):
            assert leave(native,revision)['phase']=='completed'
            raise RuntimeError('synthetic interruption')
    assert snapshot(native)==before
    assert leave(native,revision)['phase']=='completed'


def test_direct_ungrounded_empty_engine_event_still_refused(native):
    e=native['engine'];before=snapshot(native)
    with pytest.raises(Rejected,match='empty event'):
        e.apply(dict(api_version=3,branch='main',request_id='empty-direct',
            expected_revision=e.branch('main')['revision'],kind='action',actor='visitor',
            narrative='This command carries no actual transition or dependencies.',changes=[]))
    assert snapshot(native)==before
