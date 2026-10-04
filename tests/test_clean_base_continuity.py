"""Synthetic boundary probes; no model cognition or campaign history claimed."""
from copy import deepcopy
import json
import sqlite3
import subprocess
import sys
from unittest.mock import patch
import pytest
from kageyoni.engine import Engine, Rejected
from kageyoni.application import Application
from kageyoni.emergence.causal_encounter import CausalEncounterHarness
from kageyoni.emergence.action_dispatcher import EncounterActionDispatcher
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.celestial import CelestialKernel
from kageyoni.console import dispatch as command

@pytest.fixture
def world(tmp_path):
    engine = Engine(tmp_path/'world.sqlite')
    harness = CausalEncounterHarness(engine)
    harness.define_clash_encounter()
    harness.start_encounter('constellation-clash',1,'trial')
    dispatcher = EncounterActionDispatcher(engine,harness.encounters)
    yield engine,harness,dispatcher
    engine.close()


def reply(request, action='voss_rupture'):
    return dict(encounter_id=request['encounter_id'], request_hash=request['request_hash'],
                action={'kind':'propose_action','action_id':action})


def test_receipt_failure_rolls_back_effect_and_retry(world):
    engine,harness,dispatcher=world
    request=dispatcher.prepare('main','trial','voss','rollback-probe')
    revision=engine.branch('main')['revision']
    state=harness.inspect('trial')
    with patch.object(dispatcher.ledger,'record',side_effect=RuntimeError('receipt unavailable')):
        with pytest.raises(RuntimeError): dispatcher.dispatch('main','trial',request,reply(request))
    assert engine.branch('main')['revision']==revision
    assert harness.inspect('trial')==state
    assert engine.db.execute('SELECT COUNT(*) FROM shinobi_action_dispatches').fetchone()[0]==0
    assert engine.db.execute('SELECT result_json FROM shinobi_action_requests').fetchone()[0] is None
    assert dispatcher.dispatch('main','trial',request,reply(request)).validation_status=='ACCEPTED'
    assert dispatcher.dispatch('main','trial',request,reply(request)).validation_status=='REPLAY_IDEMPOTENT'
    assert len(dispatcher.ledger.query())==1
    with pytest.raises(Rejected): dispatcher.dispatch('main','trial',request,reply(request,'voss_escalate'))


def test_issued_request_cannot_be_rewritten(world):
    engine,harness,dispatcher=world
    request=dispatcher.prepare('main','trial','voss')
    altered=deepcopy(request);altered['authority']['actions'].append('sciel_anchor')
    with pytest.raises(Rejected): dispatcher.dispatch('main','trial',altered,reply(altered))
    with pytest.raises(Rejected): dispatcher.dispatch('main','trial',request,reply(request),viewer='sciel')
    with pytest.raises(Rejected): dispatcher.dispatch('other','trial',request,reply(request))
    with pytest.raises(Rejected): dispatcher.dispatch('main','other',request,reply(request))
    assert not dispatcher.ledger.query()


def test_live_revision_is_not_silently_rebased(world):
    engine,harness,dispatcher=world
    request=dispatcher.prepare('main','trial','voss')
    harness.execute_action('trial','voss_rupture')
    revision=engine.branch('main')['revision']
    result=dispatcher.dispatch('main','trial',request,reply(request))
    assert result.validation_status=='REJECTED'
    assert 'stale branch revision' in result.rejection_reason
    assert engine.branch('main')['revision']==revision


def test_none_and_conflicting_field_aliases(world):
    engine,harness,dispatcher=world
    request=dispatcher.prepare('main','trial','voss')
    proposed=reply(request);proposed['action'].update(fields={},payload={})
    assert dispatcher.dispatch('main','trial',request,proposed).validation_status=='REJECTED'
    request=dispatcher.prepare('main','trial','voss');proposed=reply(request);proposed['action']={'kind':'none'}
    revision=engine.branch('main')['revision']
    assert dispatcher.dispatch('main','trial',request,proposed).validation_status=='SKIPPED_NONE'
    assert engine.branch('main')['revision']==revision


def test_dispatch_restart_and_opt_in_schema(world):
    engine,harness,dispatcher=world
    request=dispatcher.prepare('main','trial','voss','restart')
    result=dispatcher.dispatch('main','trial',request,reply(request))
    path=engine.path if hasattr(engine,'path') else engine.db_path
    code='''import json,sys
from kageyoni.engine import Engine
from kageyoni.emergence.action_dispatcher import EncounterActionDispatcher
from kageyoni.workspaces.world import Encounters
e=Engine(sys.argv[1]);d=EncounterActionDispatcher(e,Encounters(e))
r=d.prepare('main','trial','voss','restart')
out=d.dispatch('main','trial',r,dict(encounter_id='trial',request_hash=r['request_hash'],action=dict(kind='propose_action',action_id='voss_rupture')))
assert out.validation_status=='REPLAY_IDEMPOTENT'
assert len(d.ledger.query())==1
assert e.verify()['ok']
print(out.engine_receipt['world_receipt']['event_id']);e.close()
'''
    completed=subprocess.run([sys.executable,'-c',code,str(path)],text=True,capture_output=True)
    assert completed.returncode==0,completed.stderr
    assert completed.stdout.strip()==result.engine_receipt['world_receipt']['event_id']
    assert engine.db.execute('SELECT predecessor FROM migration_checks WHERE version=25').fetchone()[0]==24
    assert engine.db.execute('PRAGMA foreign_key_check').fetchall()==[]
    with pytest.raises(sqlite3.IntegrityError):
        engine.db.execute("UPDATE shinobi_action_requests SET request_hash='forged'")


def test_persistent_participant_on_non_main_branch(world):
    engine,harness,dispatcher=world
    app=Application(engine)
    app.participant('voss',label='Voss')
    engine.fork('main','alternate',engine.branch('main')['revision'])
    alternative=CausalEncounterHarness(engine,'alternate')
    alternative.start_encounter('constellation-clash',1,'branch-trial')
    participant=app.participant('voss',label='Voss',branch='alternate')
    kernel=CelestialKernel.from_participant(participant)
    assert kernel.observe(alternative.encounters,'branch-trial')['branch']=='alternate'
    request=participant.prepare_action('branch-trial')
    proposed=kernel.propose_action('branch-trial','voss_rupture','Declared fixture choice',request=request)
    assert participant.dispatch_reply('branch-trial',request,proposed).validation_status=='ACCEPTED'
    assert engine.get('alternate','chamber_alpha')['data']['condition']=='cavity_ruptured'
    assert engine.get('main','chamber_alpha')['data']['condition']=='stable'
    kernel.close(); assert engine.branch('main')


def test_menu_and_direct_dispatch_agree(world):
    engine,harness,dispatcher=world
    request=command(engine,dict(service='encounter_actions',action='prepare',arguments=dict(branch='main',encounter_id='trial',participant_id='voss')))
    result=command(engine,dict(service='encounter_actions',action='dispatch',arguments=dict(branch='main',encounter_id='trial',request=request,reply=reply(request))))
    assert result['validation_status']=='ACCEPTED'
    assert harness.inspect('trial')['current_state']=='ruptured'


def test_will_preparation_also_rolls_back_with_outer_operation(tmp_path):
    from examples.v4_demo import setup
    engine=Engine(tmp_path/'will.sqlite');fixture=setup(engine);encounters=fixture['app'].encounters
    encounters.start('main','passage',1,'journey','start',engine.branch('main')['revision'],fixture['participants'])
    for action in ('bridge','offer'):
        encounters.act('main','journey',action,action,engine.branch('main')['revision'])
    dispatcher=EncounterActionDispatcher(engine,encounters)
    request=dispatcher.prepare('main','journey','traveler')
    before=engine.branch('main')['revision'];state=engine.state()
    with patch.object(dispatcher.ledger,'record',side_effect=RuntimeError('receipt unavailable')):
        with pytest.raises(RuntimeError):dispatcher.dispatch('main','journey',request,reply(request,'shield'))
    assert engine.branch('main')['revision']==before and engine.state()==state
    assert engine.db.execute("SELECT COUNT(*) FROM will_attempts WHERE attempt_id LIKE '%dispatch:%'").fetchone()[0]==0
    assert dispatcher.dispatch('main','journey',request,reply(request,'shield')).validation_status=='ACCEPTED'
    engine.close()


def test_situations_one_store_and_process_continuation(tmp_path):
    from kageyoni.situations.catalog import install_defaults
    from kageyoni.situations.runtime import SituationRuntime,WorkflowRun
    path=tmp_path/'situations.sqlite';engine=Engine(path);app=Application(engine,migrate_all=True)
    service=install_defaults(app.situations)
    situation=service.genesis('campaign','launch',{'objective':'launch','audience':'members'},situation_id='continuation')
    service.bind_workflow(situation.situation_id,'campaign.default')
    runtime=SituationRuntime(service,test_mode=True)
    runtime.start(WorkflowRun('pending',situation.situation_id,'campaign.default',objective='launch'))
    runtime.wait('pending','human approval')
    assert app.situations.snapshot('continuation')['workflow_id']=='campaign.default'
    with pytest.raises(RuntimeError):
        with UnitOfWork(engine.db):
            changed=service.situations['continuation'];changed.objective='must roll back'
            service.situations['continuation']=changed
            raise RuntimeError('interruption')
    assert service.snapshot('continuation')['objective']=='launch'
    engine.close()
    code='''import sys
from kageyoni.engine import Engine
from kageyoni.application import Application
from kageyoni.situations.runtime import SituationRuntime
e=Engine(sys.argv[1]);s=Application(e).situations;r=SituationRuntime(s,test_mode=True)
assert s.snapshot('continuation')['objective']=='launch'
assert r.runs['pending'].status=='waiting'
assert r.runs['pending'].resume_condition=='human approval'
r.resume('pending',condition_satisfied=True)
assert r.runs['pending'].status=='active';e.close()
'''
    result=subprocess.run([sys.executable,'-c',code,str(path)],text=True,capture_output=True)
    assert result.returncode==0,result.stderr


def test_concurrent_exact_retry_commits_once(world):
    from concurrent.futures import ThreadPoolExecutor
    from kageyoni.workspaces.world import Encounters
    engine,harness,dispatcher=world
    request=dispatcher.prepare('main','trial','voss','concurrent')
    def submit():
        connection=Engine(engine.path)
        try:
            service=EncounterActionDispatcher(connection,Encounters(connection))
            return service.dispatch('main','trial',request,reply(request)).validation_status
        finally:connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda _:submit(),range(2)))
    assert sorted(statuses)==['ACCEPTED','REPLAY_IDEMPOTENT']
    assert len(dispatcher.ledger.query())==1


def test_same_action_distinct_turns_are_not_deduplicated(world):
    engine,harness,dispatcher=world
    harness.start_encounter('constellation-clash',1,'second')
    for encounter in ('trial','second'):
        request=dispatcher.prepare('main',encounter,'voss')
        assert dispatcher.dispatch('main',encounter,request,reply(request)).validation_status=='ACCEPTED'
    assert len(dispatcher.ledger.query())==2
