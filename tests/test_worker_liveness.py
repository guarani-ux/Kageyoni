"""Portable native metadata fixtures; NO child process or OS control is executed.

Activities use native APIs. Only trusted-producer job/binding metadata is
explicitly seeded: these tables have no public native creation API. Process
identities and exit observations are labeled synthetic and never signal a PID.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3

import pytest
from kageyoni.engine import Engine, Rejected, digest, encoded
from kageyoni.intelligence.nodes import Nodes
from kageyoni.workspaces.registry import Registry
from kageyoni.workspaces.activities import Activities
from kageyoni.workspaces.job_queue import JobQueue
from kageyoni.workspaces.resource_profiles import ResourceProfiles
from kageyoni.workspaces.worker_liveness import WorkerLiveness, verify_worker_liveness, POLICY_DIGEST
from kageyoni.persistence.migrations import install_resource_profiles, install_resource_admission, install_worker_liveness, _install_component

PROCESS = {'pid':43210,'proc_pid':43210,'pid_namespace':'synthetic:no-process-executed','start_ticks':'100'}


class Fixture:
    def __init__(self, path, install=True, capacity=2):
        self.engine=Engine(path); install_resource_profiles(self.engine)
        self.engine.apply({'api_version':3,'branch':'main','request_id':'synthetic-person','expected_revision':0,
            'actor':'fixture','kind':'action','narrative':'Disposable native metadata fixture, no host process.',
            'changes':[{'op':'create','domain':'character','id':'alice','data':{'name':'Alice','entity_kind':'person'},
                        'visibility':'public','status':'proposed','evidence':[{'note':'Synthetic test only.'}]}]})
        Nodes(self.engine).bind('main','alice','fixture-bind',1,{'note':'Disposable operational fixture.'})
        self.workspace=Registry(self.engine).open('main','alice','document','liveness-fixture',source_ids=['alice'])['workspace_id']
        p=ResourceProfiles(self.engine,self.workspace)
        p.configure({'profile_id':'calibration-1000','active_jobs':capacity},'capacity',p.get()['digest'])
        install_resource_admission(self.engine)  # Genuine native32 predecessor.
        self.store=Activities(self.engine)
        self.engine.db.execute('INSERT INTO activity_bindings VALUES(?,?,?,?,?,?,?,?,?)',
            ('fixture-binding',self.workspace,'fixture','worker','alice',1,1,encoded({}),None))
        self.q=JobQueue(self.engine,self.workspace); self.q.boot(100)
        if install: install_worker_liveness(self.engine)

    def job(self, aid='work', max_seconds=120, heavy=False, parent=None):
        spec={'activity_id':aid,'kind':'real_work','definition':{'id':'synthetic:liveness','version':1,'digest':digest({'synthetic':'liveness'})},
              'parent_id':parent,'participants':['alice'],'purpose':'Native liveness metadata fixture.',
              'source_refs':[],'acceptance_ref':'native:fixture'}
        cp={'activity_id':aid,'activity_version':1,'state':'waiting','outcome':'unresolved'}
        self.store.create(self.workspace,'main',spec,cp,{})
        jid='synthetic-job:'+aid; prepared={'job_id':jid,'attempt_generation':1}
        self.engine.db.execute('INSERT INTO activity_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (jid,self.workspace,aid,1,1,'waiting','alice',encoded(prepared),digest(prepared),None,None))
        self.q.enqueue(jid,'fixture-binding',1,'bounded_probe',{'cpu_iterations':1 if heavy else 0},max_seconds)
        return jid

    def start(self, **kwargs):
        jid=self.job(**kwargs); row=self.q.claim(100)
        assert row and row['job_id']==jid
        self.q.process(jid,self.q.fence(row),deepcopy(PROCESS),100)
        return jid,self.q.fence(row)

    def activity_state(self, aid, state):
        a=self.store.get(self.workspace,aid); cp=deepcopy(a['checkpoint'])
        cp.update(state=state,activity_version=a['version']+1)
        self.store.update(self.workspace,aid,a['version'],cp,a['native'])

    def budget(self):
        return [dict(r) for r in self.engine.db.execute('SELECT * FROM activity_queue_roots ORDER BY root_id')]

    def exit(self,jid,fence,method='cooperative',now=106,returncode=0):
        return self.q.observe_exit(jid,fence,{'process':deepcopy(PROCESS),'exited':True,'returncode':returncode,'method':method},now)

    def verify(self):
        assert verify_worker_liveness(self.engine)['installed']
        assert self.engine.verify()['ok'] and self.engine.validate_registry()['ok']


@pytest.fixture
def make(tmp_path,request):
    fixtures=[]
    def factory(**kwargs):
        f=Fixture(tmp_path/('world-'+str(len(fixtures))+'.sqlite'),**kwargs);fixtures.append(f);return f
    yield factory
    for f in fixtures:f.engine.close()
    # Preserve closed native specimens even on failure. This includes checked
    # migration backups; no automatic rerun/cleanup hides an uncertain effect.
    base=Path(os.environ.get('D15_NATIVE_EVIDENCE',str(Path(__file__).resolve().parents[1]/'evidence'/'specimens')))
    destination=base/request.node.name
    if destination.exists(): raise RuntimeError('refusing to overwrite prior native evidence: '+str(destination))
    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(tmp_path,destination)


def test_renew_duplicate_reorder_ceiling_accounting(make):
    f=make();j,k=f.start();assert f.q.row(j)['lease_until']==130
    budget=f.budget();first=f.q.heartbeat(j,k,1,110)
    assert first['lease_until']==140 and first['execution_until']==220 and first['policy_digest']==POLICY_DIGEST
    assert f.q.heartbeat(j,k,1,115)==first and f.q.row(j)['lease_until']==140
    f.q.heartbeat(j,k,2,120)
    # Root-adopted known-receipt correction; antecedent rejection is frozen.
    before_replay=f.q.row(j);clock_before=f.q.owner();changes=f.engine.db.total_changes
    assert f.q.heartbeat(j,k,1,121)==first
    assert f.q.row(j)==before_replay and f.q.owner()==clock_before and f.engine.db.total_changes==changes
    with pytest.raises(Rejected,match='sequence gap'): f.q.heartbeat(j,k,4,121)
    for seq,t in enumerate(range(130,220,10),3):f.q.heartbeat(j,k,seq,t)
    assert f.q.row(j)['lease_until']==220
    with pytest.raises(Rejected,match='expired'):f.q.heartbeat(j,k,12,220)
    assert f.budget()==budget;f.verify()


@pytest.mark.parametrize('sequence,now',[(True,110),(0,110),(1,True),(1,float('nan')),(1,float('inf'))])
def test_invalid_heartbeat_inputs_atomic(make,sequence,now):
    f=make();j,k=f.start();before=f.q.row(j)
    with pytest.raises(Rejected):f.q.heartbeat(j,k,sequence,now)
    assert f.q.row(j)==before;f.verify()


def test_expiry_fence_and_clock_rollback(make):
    f=make();j,k=f.start()
    with pytest.raises(Rejected):f.q.heartbeat(j,dict(k,token='wrong'),1,110)
    with pytest.raises(Rejected,match='expired'):f.q.heartbeat(j,k,1,130)
    with pytest.raises(Rejected,match='clock rollback'):f.q.heartbeat(j,k,1,99)
    assert f.q.row(j)['state']=='reconciling' and f.q.row(j)['lease_until']==130
    with pytest.raises(Rejected):f.q.assert_lease(j,k,100)
    stop=f.q.request_stop(j,k,'protocol_error','rollback',99)
    assert stop['clock_rollback'] is True and stop['time_status']=='uncertain' and stop['stop_deadline']==104
    assert f.q.request_stop(j,k,'protocol_error','rollback',120)==stop
    f.exit(j,k,now=105);f.verify()


@pytest.mark.parametrize('block',['binding','epoch','ancestor','profile'])
def test_heartbeat_rechecks_actual_authority_ancestors_and_profile(make,block):
    f=make();j,k=f.start()
    if block=='binding':f.engine.db.execute('UPDATE activity_bindings SET active=0')
    elif block=='epoch':f.engine.db.execute('UPDATE activity_bindings SET authority_epoch=2')
    elif block=='ancestor':f.activity_state('work','paused')
    else:f.engine.db.execute("UPDATE activity_queue SET profile_digest=? WHERE job_id=?",('0'*64,j))
    before=f.q.row(j)
    with pytest.raises(Rejected):f.q.heartbeat(j,k,1,110)
    assert f.q.row(j)==before
    if block!='profile':f.verify()  # Deliberately damaged profile specimen stays damaged.


def test_stop_exact_replay_cancel_dominance_and_observation(make):
    f=make();j,k=f.start();budget=f.budget()
    a=f.q.request_stop(j,k,'pause','pause-one',110)
    assert a['stop_requested_at']==110 and a['stop_deadline']==115 and f.q.row(j)['process_json']
    assert f.q.request_stop(j,k,'pause','pause-one',200)==a
    with pytest.raises(Rejected,match='conflict'):f.q.request_stop(j,k,'cancel','pause-one',200)
    b=f.q.request_stop(j,k,'cancel','cancel-two',200)
    assert b['stop_deadline']==115 and b['disposition']=='cancel'
    with pytest.raises(Rejected):f.q.heartbeat(j,k,1,111)
    with pytest.raises(Rejected,match='observe stopped'):f.q.transition(j,'cancelled',clear_process=True)
    obs={'process':dict(PROCESS,start_ticks='999'),'exited':True,'returncode':0,'method':'forced'}
    with pytest.raises(Rejected,match='identity mismatch'):f.q.observe_exit(j,k,obs,201)
    obs['process']=deepcopy(PROCESS);obs['exited']=False
    with pytest.raises(Rejected):f.q.observe_exit(j,k,obs,201)
    obs['exited']=True;obs['returncode']=True
    with pytest.raises(Rejected):f.q.observe_exit(j,k,obs,201)
    x=f.exit(j,k,'forced',201,-9)
    assert x['state']=='cancelled' and f.q.row(j)['process_json'] is None
    assert f.exit(j,k,'forced',202,-9)==x
    with pytest.raises(Rejected,match='conflict'):f.exit(j,k,'forced',202,0)
    assert f.budget()==budget;f.verify()


@pytest.mark.parametrize('capacity',[1,2])
def test_reconciling_process_keeps_configured_and_heavy_slot(make,capacity):
    f=make(capacity=capacity);j,k=f.start(heavy=True)
    f.job('second',heavy=True)
    f.q.request_stop(j,k,'pause','stop',105)
    assert f.q.claim(106) is None
    assert f.q.row(j)['process_json'] is not None
    f.exit(j,k,now=107)
    assert f.q.row(j)['state']=='paused' and f.q.claim(108)['job_id']=='synthetic-job:second'
    f.verify()


def test_old_epoch_stop_exit_but_no_renew_or_acceptance(make):
    f=make();j,k=f.start();f.q.boot(105)
    with pytest.raises(Rejected):f.q.assert_lease(j,k,106)
    with pytest.raises(Rejected):f.q.heartbeat(j,k,1,106)
    with pytest.raises(Rejected,match='observe stopped'):f.q.transition(j,'returned',clear_process=True)
    f.q.request_stop(j,k,'shutdown','owner-restart',106)
    x=f.exit(j,k,'exited_before_stop',107)
    assert x['state']=='reconciling' and f.q.row(j)['process_json'] is None
    assert f.q.claim(108) is None;f.verify()


def test_normal_running_finish_boundary_and_explicit_exit(make):
    f=make();j,k=f.start()
    f.q.assert_lease(j,k,110)
    # This does not claim actual completion/Popen evidence: trusted product
    # acceptance owns that observation and remains unchanged by this seam.
    f.q.transition(j,'returned',clear_process=True)
    assert verify_worker_liveness(f.engine)['attempts']==1;f.verify()
    g=make();j,k=g.start();x=g.exit(j,k,'exited_before_stop',110)
    assert x['state']=='reconciling' and x['disposition'] is None;g.verify()


def test_genuine32_predecessor_backup_preservation_restore_and_readonly(make,tmp_path):
    f=make(install=False);j,k=f.start(max_seconds=80)
    assert f.q.row(j)['lease_until']==180 and verify_worker_liveness(f.engine)=={'installed':False}
    old=f.q.row(j);world=f.engine.state();install_worker_liveness(f.engine)
    assert f.q.row(j)==old and f.engine.state()==world
    assert verify_worker_liveness(f.engine)['attempts']==0
    # Historical process metadata remains untouched and its API remains legacy.
    f.q.process(j,k,{'fixture':'legacy process observation'},105)
    assert json.loads(f.q.row(j)['process_json'])=={'fixture':'legacy process observation'}
    backup=next(Path(f.engine.path).parent.glob('*.pre-v33-*.bak'))
    e=Engine(backup,read_only=True)
    assert e.db.execute('SELECT max(version) FROM migration_checks').fetchone()[0]==32
    assert verify_worker_liveness(e)=={'installed':False} and e.verify()['ok'];e.close()
    target=tmp_path/'restored.sqlite';Engine.restore(backup,target)
    e=Engine(target);install_worker_liveness(e)
    assert verify_worker_liveness(e)['attempts']==0 and e.verify()['ok'];e.close()
    f.q.transition(j,'returned',clear_process=True);f.job('new');row=f.q.claim(110)
    assert row['lease_until']==140 and verify_worker_liveness(f.engine)['attempts']==1
    current=tmp_path/'closed.backup';f.engine.backup(current)
    before=hashlib.sha256(current.read_bytes()).hexdigest();e=Engine(current,read_only=True)
    assert verify_worker_liveness(e)['installed'] and e.verify()['ok'] and e.validate_registry()['ok']
    assert e.db.total_changes==0;e.close();assert hashlib.sha256(current.read_bytes()).hexdigest()==before;f.verify()


def test_checked33_install_rollback_and_checksum_failure(make,tmp_path):
    f=make(install=False);world=f.engine.state()
    broken=tmp_path/'broken033.sql';broken.write_text('CREATE TABLE must_rollback(x);\nSELECT nonexistent_function();\n')
    with pytest.raises(sqlite3.OperationalError):_install_component(f.engine,broken,33,32,'worker_liveness_interface')
    assert f.engine.db.execute('SELECT max(version) FROM migration_checks').fetchone()[0]==32
    assert not f.engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='must_rollback'").fetchone()
    assert f.engine.state()==world
    install_worker_liveness(f.engine);f.verify()
    f.engine.db.execute('UPDATE migration_checks SET checksum=? WHERE version=33',('0'*64,))
    with pytest.raises(Rejected,match='checksum mismatch'):verify_worker_liveness(f.engine)


def test_receipt_immutability_and_correspondence_tamper(make):
    f=make();j,k=f.start();f.q.heartbeat(j,k,1,110)
    with pytest.raises(sqlite3.IntegrityError):f.engine.db.execute('UPDATE activity_worker_heartbeats SET sequence=2')
    with pytest.raises(sqlite3.IntegrityError):f.engine.db.execute('DELETE FROM activity_worker_liveness')
    f.engine.db.execute('UPDATE activity_worker_liveness SET lease_until=999')
    with pytest.raises(Rejected,match='correspondence mismatch'):verify_worker_liveness(f.engine)


@pytest.mark.parametrize('capacity',[1,2])
def test_configured_light_slot_retention_and_release(make,capacity):
    f=make(capacity=capacity);j,k=f.start();f.job('second')
    f.q.request_stop(j,k,'pause','stop',105)
    second=f.q.claim(106)
    if capacity==1:
        assert second is None
        f.exit(j,k,now=107)
        assert f.q.claim(108)['job_id']=='synthetic-job:second'
    else:
        assert second['job_id']=='synthetic-job:second'
        f.job('third');assert f.q.claim(107) is None
        f.exit(j,k,now=108)
        assert f.q.claim(109)['job_id']=='synthetic-job:third'
    f.verify()


def test_terminal_parent_rejects_heartbeat_and_attempt_history_retained(make):
    f=make();parent_job=f.job('parent');f.q.transition(parent_job,'returned','fixture parent has no worker');j,k=f.start(aid='child',parent='parent')
    f.activity_state('parent','paused')
    with pytest.raises(Rejected,match='ancestor stopped'):f.q.heartbeat(j,k,1,110)
    f.q.request_stop(j,k,'pause','parent-paused',110);f.exit(j,k,now=111)
    first=WorkerLiveness(f.engine,f.workspace).row(j,k)
    f.activity_state('parent','waiting');f.q.transition(j,'queued','explicit fixture reissue after observed exit')
    nextrow=f.q.claim(112)
    assert nextrow['job_id']==j and nextrow['generation']==2
    assert WorkerLiveness(f.engine,f.workspace).row(j,k)==first
    assert f.budget()[0]['starts']==2 and f.budget()[0]['reserved_seconds']==240
    f.verify()


# Root integrated global-hook and truthful post-stop observation checks, unexecuted.
def test_unforced_exit_after_stop_is_truthful_not_cooperative_claim(make):
    f=make();j,k=f.start();f.q.request_stop(j,k,'cancel','cancel-known',105)
    receipt=f.exit(j,k,method='exited_after_stop',now=106,returncode=22)
    assert receipt['observation']['method']=='exited_after_stop'
    assert receipt['observation']['returncode']==22 and receipt['state']=='cancelled'
    assert f.q.row(j)['process_json'] is None;f.verify()

def test_post_stop_observation_label_requires_real_stop_record(make):
    f=make();j,k=f.start();before=f.q.row(j)
    with pytest.raises(Rejected,match='stop intent missing'):
        f.exit(j,k,method='exited_after_stop',now=106,returncode=22)
    assert f.q.row(j)==before;f.verify()

@pytest.mark.parametrize('remaining',['migration','component','tables'])
def test_global_verify_rejects_orphaned_033_marker(make,tmp_path,remaining):
    f=make();f.verify();f.engine.backup(tmp_path/('checked-before-damage-'+remaining+'.sqlite'))
    if remaining!='tables':
        for table in ['activity_worker_heartbeats','activity_worker_stops','activity_worker_exits','activity_worker_liveness']:
            f.engine.db.execute('DROP TABLE '+table)
    if remaining!='component':f.engine.db.execute("DELETE FROM engine_versions WHERE component='worker_liveness_interface'")
    if remaining!='migration':f.engine.db.execute('DELETE FROM migration_checks WHERE version=33')
    with pytest.raises(Rejected):f.engine.verify()
