"""AUTHOR_ONLY coupled API cases; explicit root DB-lane GO required.

No OS facts are produced here; trusted-owner metadata is synthetic. No native
terminal/process/registration/stop history is SQL-populated. Existing fixture's
binding/job producer metadata remains the disclosed unchanged native033 fixture.
"""
import os
if os.environ.get('SAMSARA_EXECUTE_CUSTODY_NATIVE_TESTS')!='1':
    raise RuntimeError('native DB lane requires explicit root GO; AUTHOR_ONLY coupling cases')
import importlib.util
from pathlib import Path
import copy
import hashlib

import pytest
from kageyoni.engine import Engine,Rejected
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.workspaces.worker_liveness import WorkerLiveness,verify_worker_liveness
from kageyoni.workspaces.worker_custody import WorkerCustody,terminal_absence,verify_worker_custody

spec=importlib.util.spec_from_file_location('exact_frozen034_api_fixture',Path(__file__).with_name('native_worker_custody_cases.py'))
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
fixture_factory=api.fixture_factory


def tables(f):
 names=['activity_queue','activity_queue_owners','activity_queue_roots','activity_worker_liveness',
        'activity_worker_stops','activity_worker_exits','activity_worker_registrations','activity_worker_absences']
 return {n:[dict(r) for r in f.engine.db.execute('SELECT * FROM '+n+' ORDER BY rowid')] for n in names}


def test_absence_blocks_new_process_heartbeat_stop_exit_but_knownstop_replays(fixture_factory):
 f=fixture_factory();j,k,w=api.start(f);r=api.reg();w.register(j,k,r,100)
 original=f.q.request_stop(j,k,'shutdown','first-stop',101)
 receipt=w.observe_absence(j,k,api.obs(r),101)
 before=tables(f);changes=f.engine.db.total_changes
 assert receipt['state']=='reconciling'
 assert f.q.request_stop(j,k,'shutdown','first-stop',999)==original
 assert tables(f)==before and f.engine.db.total_changes==changes
 operations=[lambda:WorkerLiveness(f.engine,f.workspace).process(j,k,api.PROCESS),
             lambda:f.q.process(j,k,api.PROCESS,102),
             lambda:f.q.heartbeat(j,k,1,102),
             lambda:f.q.request_stop(j,k,'cancel','new-cancel',102),
             lambda:f.q.observe_exit(j,k,{'process':api.PROCESS,'exited':True,'returncode':0,'method':'cooperative'},102)]
 for operation in operations:
  with pytest.raises(Rejected):operation()
  assert tables(f)==before and f.engine.db.total_changes==changes
 assert terminal_absence(f.engine,f.workspace,j,k)==receipt
 assert verify_worker_liveness(f.engine)['installed'] and verify_worker_custody(f.engine)['absences']==1
 assert f.engine.verify()['ok'] and f.engine.validate_registry()['ok']


def test_known_integer_exit_replay_still_exact_zerowrite_without_absence(fixture_factory):
 f=fixture_factory();j,k,w=api.start(f);w.register(j,k,api.reg(),100)
 f.q.request_stop(j,k,'pause','first-stop',101)
 observation={'process':copy.deepcopy(api.PROCESS),'exited':True,'returncode':21,'method':'cooperative'}
 receipt=f.q.observe_exit(j,k,observation,102)
 before=tables(f);changes=f.engine.db.total_changes
 assert f.q.observe_exit(j,k,observation,999)==receipt
 assert tables(f)==before and f.engine.db.total_changes==changes
 assert terminal_absence(f.engine,f.workspace,j,k) is None
 assert f.engine.verify()['ok'] and f.engine.validate_registry()['ok']


def test_registration_outer_rollback_preserves_native033_process_and_budgets(fixture_factory):
 f=fixture_factory();j,k,w=api.start(f);before=tables(f)
 with pytest.raises(RuntimeError,match='deliberate outer rollback'):
  with UnitOfWork(f.engine.db):
   w.register(j,k,api.reg(),101)
   assert w.row(j,k)['registration_digest']==api.reg()['registration_digest']
   raise RuntimeError('deliberate outer rollback')
 assert tables(f)==before
 assert f.engine.verify()['ok'] and f.engine.validate_registry()['ok']


def test_absence_outer_rollback_keeps_process_slot_and_stopped_disposition(fixture_factory):
 f=fixture_factory();j,k,w=api.start(f);r=api.reg();w.register(j,k,r,100)
 f.q.request_stop(j,k,'pause','stop',101);before=tables(f)
 with pytest.raises(RuntimeError,match='deliberate absence rollback'):
  with UnitOfWork(f.engine.db):
   w.observe_absence(j,k,api.obs(r),102)
   assert f.q.row(j)['process_json'] is None
   raise RuntimeError('deliberate absence rollback')
 assert tables(f)==before and f.q.row(j)['process_json'] is not None
 assert terminal_absence(f.engine,f.workspace,j,k) is None
 assert f.engine.verify()['ok'] and f.engine.validate_registry()['ok']


def test_explicit_requeue_then_charged_newgeneration_retains_old_absence(fixture_factory):
 f=fixture_factory();j,k,w=api.start(f);receipt,_=api.stop_absent(f,j,k,w);budget=f.budget()
 with pytest.raises(Rejected,match='cannot return'):f.q.transition(j,'returned','must not accept absence',clear_process=True)
 f.q.transition(j,'queued','explicit metadata-only native operator discard',clear_process=True)
 assert terminal_absence(f.engine,f.workspace,j,k)==receipt
 assert f.engine.verify()['ok']
 new=f.q.claim(102);newk=f.q.fence(new)
 assert newk['generation']==k['generation']+1 and f.budget()[0]['starts']==budget[0]['starts']+1
 assert f.budget()[0]['reserved_seconds']==budget[0]['reserved_seconds']+new['max_seconds']
 assert terminal_absence(f.engine,f.workspace,j,k)==receipt
 assert f.engine.verify()['ok'] and f.engine.validate_registry()['ok']


def test_old033_missing_companion_stays_unresolved_and_cannot_requeue(fixture_factory):
 f=fixture_factory();j,k,w=api.start(f);f.q.request_stop(j,k,'pause','stop',101);before=tables(f)
 assert terminal_absence(f.engine,f.workspace,j,k) is None
 with pytest.raises(Rejected):f.q.transition(j,'queued','no stop proof',clear_process=True)
 with pytest.raises(Rejected):f.q.transition(j,'paused','no stop proof',clear_process=True)
 assert tables(f)==before and f.q.row(j)['process_json'] is not None
 assert f.engine.verify()['ok'] and f.engine.validate_registry()['ok']


def test_readonly_reopen_verifies_absence_without_mutating_database(fixture_factory):
 f=fixture_factory();j,k,w=api.start(f);receipt,_=api.stop_absent(f,j,k,w)
 path=Path(f.engine.path);f.engine.close();before=hashlib.sha256(path.read_bytes()).hexdigest()
 engine=Engine(path,read_only=True)
 try:
  assert verify_worker_liveness(engine)['installed']
  assert verify_worker_custody(engine)['absences']==1
  assert terminal_absence(engine,f.workspace,j,k)==receipt
  assert engine.verify()['ok'] and engine.validate_registry()['ok']
 finally:engine.close()
 assert hashlib.sha256(path.read_bytes()).hexdigest()==before


def test_global_verifier_rejects_partial034_even_when_no_attempts(fixture_factory):
 f=fixture_factory()
 # Deliberate empty-interface structural negative only, no fabricated history.
 f.engine.db.execute('DROP TABLE activity_worker_absences')
 with pytest.raises(Rejected,match='incomplete worker custody interface'):f.engine.verify()
