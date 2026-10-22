"""AUTHOR_ONLY integration cases until root GO; modeled native metadata, no OS proof.

No old fixture/assertions are rewritten. Existing fixture seeds binding/job
producer metadata ONLY; every new process/stop/registration/absence is native API.
"""
import os
if os.environ.get('SAMSARA_EXECUTE_CUSTODY_NATIVE_TESTS')!='1':
    raise RuntimeError('native DB lane requires explicit root GO; this test file is AUTHOR_ONLY')
import copy
import importlib.util
from pathlib import Path
import sqlite3
import hashlib

import pytest
from kageyoni.engine import Engine,Rejected
from kageyoni.persistence.migration_034 import install_worker_custody
from kageyoni.workspaces.worker_custody import WorkerCustody,terminal_absence,verify_worker_custody
from kageyoni.workspaces.custody_schema import _digest,PROVIDER

PROCESS={'pid':2,'proc_pid':100,'pid_namespace':'pid:[123]','start_ticks':'999'}
DOMAIN={'boot_id':'6f0d0296-5225-41af-8e97-4ff2f05b26be','reader_pid_namespace':'pid:[123]',
 'mount_namespace':'mnt:[124]','proc_root_device':30,'proc_root_inode':1,
 'proc_mountinfo':'94 93 0:30 / /proc rw,nosuid,nodev,noexec,relatime - proc proc rw','proc_submounts':[]}


def reg(process=None):
 b={'schema_version':2,'process':copy.deepcopy(process or PROCESS),'domain':copy.deepcopy(DOMAIN),'domain_digest':_digest(DOMAIN)}
 return {**b,'registration_digest':_digest(b)}


def obs(r):
 return {'schema_version':2,'provider':PROVIDER,'method':'procfs_enoent_twice','registration_digest':r['registration_digest'],
 'domain_digest':r['domain_digest'],'process':copy.deepcopy(r['process']),'domain':copy.deepcopy(r['domain']),'returncode':None,
 'samples':[{'status':'directory_enoent','observed_monotonic_ns':0},{'status':'directory_enoent','observed_monotonic_ns':50_000_000}]}


@pytest.fixture
def fixture_factory(tmp_path):
 path=Path(os.environ['SAMSARA_033_FIXTURE_SOURCE'])
 expected=os.environ['SAMSARA_033_FIXTURE_SHA256']
 assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
 spec=importlib.util.spec_from_file_location('unchanged_native033_metadata_fixture',path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 fixtures=[]
 def make(install=True):
  f=module.Fixture(tmp_path/('world-'+str(len(fixtures))+'.sqlite'));fixtures.append(f)
  if install:install_worker_custody(f.engine)
  return f
 yield make
 for f in fixtures:f.engine.close()
 # Root harness must preserve this explicit basetemp/raw evidence directory.


def start(f,aid='work',process=None):
 j=f.job(aid=aid);q=f.q.claim(100);k=f.q.fence(q)
 assert q['job_id']==j
 f.q.process(j,k,copy.deepcopy(process or PROCESS),100)
 return j,k,WorkerCustody(f.engine,f.workspace)


def stop_absent(f,j,k,w,disposition='pause',at=101):
 r=reg();w.register(j,k,r,100)
 f.q.request_stop(j,k,disposition,'synthetic-current-stop',101)
 return w.observe_absence(j,k,obs(r),at),r


def test_new_registration_and_distinct_absence_exact_replay_noexit_norefund(fixture_factory):
 f=fixture_factory();j,k,w=start(f);budget=f.budget();r=reg();first=w.register(j,k,r,100)
 before=f.engine.db.total_changes;owner=f.q.owner()
 assert w.register(j,k,r,100)==first
 assert f.engine.db.total_changes==before and f.q.owner()==owner
 f.q.request_stop(j,k,'pause','stop',101);receipt=w.observe_absence(j,k,obs(r),101)
 assert receipt['kind']=='worker_identity_absent' and receipt['returncode'] is None and receipt['state']=='paused'
 assert f.q.row(j)['process_json'] is None and f.q.row(j)['state']=='paused' and f.budget()==budget
 a=f.engine.db.execute('SELECT * FROM activity_worker_liveness WHERE job_id=?',(j,)).fetchone()
 assert a['process_json'] is not None and a['exit_json'] is None
 assert not f.engine.db.execute('SELECT * FROM activity_worker_exits').fetchall()
 before=f.engine.db.total_changes;owner=f.q.owner();row=f.q.row(j)
 assert w.observe_absence(j,k,obs(r),999)==receipt and f.engine.db.total_changes==before
 assert f.q.owner()==owner and f.q.row(j)==row
 changed=obs(r);changed['samples'][1]['observed_monotonic_ns']+=1
 with pytest.raises(Rejected,match='conflict'):w.observe_absence(j,k,changed,102)
 assert terminal_absence(f.engine,f.workspace,j,k)==receipt
 assert verify_worker_custody(f.engine)['absences']==1


@pytest.mark.parametrize('disposition,state',[('pause','paused'),('cancel','cancelled'),('shutdown','reconciling')])
def test_stop_selected_state_and_clockrollback_not_elapsed_grace(fixture_factory,disposition,state):
 f=fixture_factory();j,k,w=start(f);receipt,_=stop_absent(f,j,k,w,disposition,at=99)
 assert receipt['state']==state and f.q.row(j)['state']==state
 assert receipt['clock_rollback'] is True and receipt['time_status']=='uncertain'
 assert receipt['owner_wall_before']==receipt['owner_wall_after']==101
 assert receipt['observed_at']==99 and receipt['returncode'] is None
 assert verify_worker_custody(f.engine)['absences']==1


def test_absence_needs_companion_stop_and_same_fence(fixture_factory):
 f=fixture_factory();j,k,w=start(f);r=reg()
 with pytest.raises(Rejected):w.observe_absence(j,k,obs(r),101)
 assert terminal_absence(f.engine,f.workspace,j,k) is None
 w.register(j,k,r,100)
 with pytest.raises(Rejected):w.observe_absence(j,k,obs(r),101)
 with pytest.raises(Rejected):w.register(j,{**k,'token':'wrong'},r,100)
 f.q.request_stop(j,k,'pause','stop',101)
 with pytest.raises(Rejected):w.observe_absence(j,{**k,'token':'wrong'},obs(r),101)
 assert f.q.row(j)['process_json'] is not None


@pytest.mark.parametrize('block',['owner','binding','ancestor','lease'])
def test_registration_checks_current_authority_before_replay(fixture_factory,block):
 f=fixture_factory();j,k,w=start(f);r=reg();w.register(j,k,r,100)
 if block=='owner':f.q.boot(101)
 elif block=='binding':f.engine.db.execute('UPDATE activity_bindings SET active=0')  # Explicit live authority-negative fixture.
 elif block=='ancestor':f.activity_state('work','paused')
 with pytest.raises(Rejected):w.register(j,k,r,130 if block=='lease' else 101)


def test_owner_reboot_allows_oldattempt_stop_observation_not_reregistration(fixture_factory):
 f=fixture_factory();j,k,w=start(f);r=reg();w.register(j,k,r,100);f.q.boot(101)
 with pytest.raises(Rejected):w.register(j,k,r,101)
 f.q.request_stop(j,k,'pause','new-owner-stop',102)
 receipt=w.observe_absence(j,k,obs(r),102)
 assert receipt['fence']==k and receipt['kind']=='worker_identity_absent'
 assert f.q.owner()['epoch']!=k['epoch']


def test_known_exit_and_absence_cannot_both_be_terminal(fixture_factory):
 f=fixture_factory();j,k,w=start(f);r=reg();w.register(j,k,r,100);f.q.request_stop(j,k,'pause','stop',101)
 f.q.observe_exit(j,k,{'process':PROCESS,'exited':True,'returncode':0,'method':'cooperative'},102)
 with pytest.raises(Rejected):w.observe_absence(j,k,obs(r),102)
 g=fixture_factory();j,k,w=start(g);stop_absent(g,j,k,w)
 with pytest.raises(Rejected):g.q.observe_exit(j,k,{'process':PROCESS,'exited':True,'returncode':0,'method':'cooperative'},102)


def test_queued_before_newclaim_and_historical_receipt_after_generation(fixture_factory):
 f=fixture_factory();j,k,w=start(f);receipt,r=stop_absent(f,j,k,w)
 f.q.transition(j,'queued','explicit synthetic native operator disposition',clear_process=True)
 assert terminal_absence(f.engine,f.workspace,j,k)==receipt
 new=f.q.claim(102);newk=f.q.fence(new)
 assert newk['generation']==k['generation']+1
 assert terminal_absence(f.engine,f.workspace,j,k)==receipt
 with pytest.raises(Rejected):w.observe_absence(j,k,obs(r),102)
 assert verify_worker_custody(f.engine)['registrations']==1


def test_append_only_and_schema_tamper_readonly_verifier(fixture_factory):
 f=fixture_factory();j,k,w=start(f);w.register(j,k,reg(),100)
 for statement in ['UPDATE activity_worker_registrations SET registered_at=101','DELETE FROM activity_worker_registrations']:
  with pytest.raises(sqlite3.IntegrityError):f.engine.db.execute(statement)
 before=f.engine.db.total_changes
 assert verify_worker_custody(f.engine)['registrations']==1 and f.engine.db.total_changes==before
 # Explicit structural negative specimen, no forged process/history rows.
 f.engine.db.execute('DROP TRIGGER worker_registrations_no_delete')
 with pytest.raises(Rejected,match='schema object'):verify_worker_custody(f.engine)


def test_genuine033_predecessor_migration_no_backfill_and_backup_reopen(fixture_factory,tmp_path):
 f=fixture_factory(install=False);j,k,_=start(f);before=f.budget()
 old=[dict(r) for r in f.engine.db.execute('SELECT * FROM activity_worker_liveness')]
 assert terminal_absence(f.engine,f.workspace,j,k) is None
 install_worker_custody(f.engine)
 assert [dict(r) for r in f.engine.db.execute('SELECT * FROM activity_worker_liveness')]==old
 assert verify_worker_custody(f.engine)=={'installed':True,'interface':'1','registrations':0,'absences':0}
 assert f.budget()==before and f.q.row(j)['process_json'] is not None
 backups=list(Path(f.engine.path).parent.glob(Path(f.engine.path).name+'.pre-v34-*.bak'))
 assert len(backups)==1
 oldengine=Engine(backups[0],read_only=True)
 try:
  assert oldengine.db.execute('SELECT max(version) FROM migration_checks').fetchone()[0]==33
  assert verify_worker_custody(oldengine)=={'installed':False}
 finally:oldengine.close()
 current=Path(f.engine.path);f.engine.close();e=Engine(current,read_only=True)
 try:assert verify_worker_custody(e)['registrations']==0
 finally:e.close()
