"""New corruption specimens for the complete033 pre-admission seam.

All terminal history is first produced by the real native API. Direct SQL below
is deliberate stored-receipt corruption after a checked backup, never OS proof.
"""
import copy
import json
import pytest
from kageyoni.engine import Rejected, encoded
from kageyoni.workspaces.worker_liveness import verify_worker_liveness
from native_worker_custody_cases import fixture_factory, start, PROCESS


@pytest.mark.parametrize('damage',['policy','state','disposition','extra','missing_observation','array','invalid_json','overflow'])
def test_complete_known_exit_validation_precedes_new_charge_and_fence(fixture_factory,damage):
    f=fixture_factory();j,k,_=start(f)
    f.q.request_stop(j,k,'pause','stop',101)
    receipt=f.q.observe_exit(j,k,{'process':copy.deepcopy(PROCESS),'exited':True,'returncode':21,'method':'cooperative'},102)
    f.q.transition(j,'queued','explicit test requeue',clear_process=True)
    assert f.engine.verify()['ok'] and f.engine.validate_registry()['ok']
    f.engine.backup(str(f.engine.path)+'.checked-before-'+damage+'.sqlite')
    corrupt=copy.deepcopy(receipt)
    if damage=='policy':corrupt['policy_digest']='0'*64
    elif damage=='state':corrupt['state']='cancelled'
    elif damage=='disposition':corrupt['disposition']='cancel'
    elif damage=='extra':corrupt['extra']=True
    elif damage=='missing_observation':del corrupt['observation']
    elif damage=='array':corrupt=[]
    elif damage=='overflow':corrupt['observed_at']=10**400
    raw='{' if damage=='invalid_json' else encoded(corrupt)
    # Retain exact API-generated history plus backup before intentional damage.
    f.engine.db.execute('DROP TRIGGER worker_exits_no_update')
    if damage=='invalid_json':f.engine.db.execute('PRAGMA ignore_check_constraints=ON')
    f.engine.db.execute('UPDATE activity_worker_exits SET receipt_json=?',(raw,))
    f.engine.db.execute('UPDATE activity_worker_liveness SET exit_json=?',(raw,))
    if damage=='invalid_json':f.engine.db.execute('PRAGMA ignore_check_constraints=OFF')
    before=[dict(r) for r in f.engine.db.execute('SELECT * FROM activity_queue')]
    owner=f.q.owner();budget=f.budget()
    with pytest.raises((Rejected,KeyError,TypeError,json.JSONDecodeError,OverflowError)) as original:
        verify_worker_liveness(f.engine)
    with pytest.raises(Rejected) as rejected:f.q.claim(103)
    if isinstance(original.value,Rejected):assert str(rejected.value)==str(original.value)
    else:assert str(rejected.value).startswith('malformed prior worker liveness: ')
    assert f.budget()==budget and f.q.owner()==owner
    assert [dict(r) for r in f.engine.db.execute('SELECT * FROM activity_queue')]==before
