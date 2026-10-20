"""Three contract countercases; antecedent22PASS remains frozen separately.

Native metadata/process observations only. No process is launched/signalled.
Run once against frozen original source to preserve actual failures, then use
unchanged acceptance assertions for the repaired source under a later root GO.
"""
import json
from pathlib import Path
from test_worker_liveness import make, PROCESS
import pytest
from kageyoni.engine import Rejected
from kageyoni.workspaces.worker_liveness import verify_worker_liveness


def test_preregistered_stop_cannot_return(make):
    f=make();j=f.job();row=f.q.claim(100);k=f.q.fence(row)
    assert row['process_json'] is None
    f.q.request_stop(j,k,'pause','stop-before-registration',110)
    with pytest.raises(Rejected):
        f.q.transition(j,'returned',clear_process=True)
    assert f.q.row(j)['state']=='reconciling'
    assert verify_worker_liveness(f.engine)['installed']


def test_stop_and_exit_advance_cross_attempt_clock_floor(make):
    f=make();a,ka=f.start(aid='a');b,kb=f.start(aid='b')
    stop=f.q.request_stop(a,ka,'pause','first',110)
    stop_floor=f.q.owner()['last_wall']
    try:f.q.heartbeat(b,kb,1,105);stop_rollback_refused=False
    except Rejected:stop_rollback_refused=True
    repeat=f.q.request_stop(a,ka,'pause','new-backward-observation',104)
    # A third actual owner observation must also advance the shared floor.
    exited=f.exit(a,ka,now=112)
    exit_floor=f.q.owner()['last_wall']
    # If rollback already reconciled B, native stale rejection remains required.
    try:f.q.heartbeat(b,kb,2,111);exit_rollback_refused=False
    except Rejected:exit_rollback_refused=True
    observed={'stop_floor':stop_floor,'stop_rollback_refused':stop_rollback_refused,
              'new_backward_stop_uncertain':repeat['clock_rollback'],'exit_floor':exit_floor,
              'exit_rollback_refused':exit_rollback_refused,'stop':stop,'exit':exited}
    (Path(f.engine.path).parent/'cross-clock-observation.json').write_text(json.dumps(observed,indent=2)+'\n')
    assert stop_floor==110 and stop_rollback_refused
    assert repeat['clock_rollback'] is True and repeat['stop_deadline']==115
    assert exit_floor==112 and exit_rollback_refused


def test_known_older_receipt_is_exact_zero_write_replay_after_validation(make):
    f=make();j,k=f.start();one=f.q.heartbeat(j,k,1,110);f.q.heartbeat(j,k,2,120)
    before=f.q.row(j);owner=f.q.owner();changes=f.engine.db.total_changes
    assert f.q.heartbeat(j,k,1,121)==one
    assert f.q.row(j)==before and f.q.owner()==owner and f.engine.db.total_changes==changes
    # NEW sequence remains contiguous: correction does not loosen the1→4 gap.
    with pytest.raises(Rejected,match='sequence gap'):f.q.heartbeat(j,k,4,121)
    f.q.request_stop(j,k,'pause','stop',122)
    with pytest.raises(Rejected):f.q.heartbeat(j,k,1,123)


@pytest.mark.parametrize('disposition,settled',[('pause','paused'),('cancel','cancelled'),('shutdown','reconciling')])
def test_never_registered_stop_settles_without_invented_exit(make,disposition,settled):
    f=make();j=f.job();row=f.q.claim(100);k=f.q.fence(row);budget=f.budget()
    f.q.request_stop(j,k,disposition,'stop-unregistered',110)
    f.q.transition(j,settled,clear_process=True)
    assert f.q.row(j)['state']==settled and f.q.row(j)['process_json'] is None
    with pytest.raises(Rejected):f.q.process(j,k,PROCESS,111)
    for illegal in ['returned','queued','failed']:
        with pytest.raises(Rejected):f.q.transition(j,illegal,clear_process=True)
    assert f.budget()==budget;f.verify()
    # Deliberate damaged specimen proves verifier also sees missing registration.
    f.engine.db.execute("UPDATE activity_queue SET state='returned' WHERE job_id=?",(j,))
    with pytest.raises(Rejected,match='returned or revived'):verify_worker_liveness(f.engine)


def test_retained_registered_identity_guards_illicitly_cleared_queue_process(make):
    f=make();j,k=f.start();f.q.request_stop(j,k,'pause','stop',110)
    f.engine.db.execute('UPDATE activity_queue SET process_json=NULL WHERE job_id=?',(j,))
    with pytest.raises(Rejected):f.q.transition(j,'paused',clear_process=True)
    with pytest.raises(Rejected,match='without observed exit'):verify_worker_liveness(f.engine)


def test_backward_exit_uncertain_highwater_survives_boot_and_replay(make):
    f=make();j,k=f.start();f.q.request_stop(j,k,'pause','stop',110)
    receipt=f.exit(j,k,now=105)
    assert receipt['clock_rollback'] is True and receipt['time_status']=='uncertain'
    assert receipt['owner_wall_before']==receipt['owner_wall_after']==110
    assert f.q.owner()['last_wall']==110
    changes=f.engine.db.total_changes
    assert f.exit(j,k,now=200)==receipt and f.engine.db.total_changes==changes
    f.q.boot(90);assert f.q.owner()['last_wall']==110;f.verify()


@pytest.mark.parametrize('damage',['cleared','mutated','never_registered'])
def test_normal_return_cannot_erase_missing_or_changed_registered_identity(make,damage):
    f=make()
    if damage=='never_registered':
        j=f.job();row=f.q.claim(100);k=f.q.fence(row)
    else:
        j,k=f.start()
        value=None if damage=='cleared' else json.dumps(dict(PROCESS,start_ticks='999'))
        f.engine.db.execute('UPDATE activity_queue SET process_json=? WHERE job_id=?',(value,j))
    before=f.q.row(j)
    with pytest.raises(Rejected):f.q.transition(j,'returned',clear_process=True)
    assert f.q.row(j)==before
    if damage=='never_registered':
        f.verify()  # Still valid running pre-registration, no false exit needed.
        f.engine.db.execute("UPDATE activity_queue SET state='returned' WHERE job_id=?",(j,))
        with pytest.raises(Rejected,match='invalid unobserved normal'):verify_worker_liveness(f.engine)
    else:
        with pytest.raises(Rejected,match='without observed exit'):verify_worker_liveness(f.engine)


def test_matching_registered_identity_normal_return_remains_free_of_exit_receipt(make):
    f=make();j,k=f.start();f.q.assert_lease(j,k,110)
    f.q.transition(j,'returned',clear_process=True)
    assert not f.engine.db.execute('SELECT 1 FROM activity_worker_exits WHERE job_id=?',(j,)).fetchone()
    f.verify()



def test_current_unregistered_attempt_rejects_queue_only_process_identity(make):
    f=make();j=f.job();row=f.q.claim(100)
    assert row['process_json'] is None
    f.verify()  # Genuine pre-registration claim remains valid.
    f.engine.db.execute('UPDATE activity_queue SET process_json=? WHERE job_id=?',(json.dumps(PROCESS),j))
    with pytest.raises(Rejected,match='unregistered worker queue process correspondence'):
        verify_worker_liveness(f.engine)


@pytest.mark.parametrize('initial',['shutdown','protocol_error'])
def test_explicit_cancel_dominates_nonpause_unregistered_stop_without_fake_exit(make,initial):
    f=make();j=f.job();row=f.q.claim(100);k=f.q.fence(row);budget=f.budget()
    original=f.q.request_stop(j,k,initial,'initial-stop',110)
    cancel=f.q.request_stop(j,k,'cancel','explicit-cancel',112)
    assert cancel['disposition']=='cancel' and cancel['stop_requested_at']==110 and cancel['stop_deadline']==115
    later=f.q.request_stop(j,k,'pause','later-noncancel',113)
    assert later['disposition']=='cancel' and later['stop_deadline']==115
    changes=f.engine.db.total_changes;clock=f.q.owner()
    assert f.q.request_stop(j,k,initial,'initial-stop',120)==original
    assert f.engine.db.total_changes==changes and f.q.owner()==clock
    f.q.transition(j,'cancelled',clear_process=True)
    assert f.q.row(j)['state']=='cancelled' and f.q.row(j)['process_json'] is None
    assert f.budget()==budget
    assert not f.engine.db.execute('SELECT 1 FROM activity_worker_exits WHERE job_id=?',(j,)).fetchone()
    with pytest.raises(Rejected):f.q.process(j,k,PROCESS,114)
    with pytest.raises(Rejected):f.q.transition(j,'returned',clear_process=True)
    f.verify()
