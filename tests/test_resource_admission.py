"""Native API metadata fixtures, no SQL-generated dormant population or workers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest
from kageyoni.engine import Engine, Rejected, digest, encoded
from kageyoni.intelligence.nodes import Nodes
from kageyoni.workspaces.registry import Registry
from kageyoni.workspaces.activities import Activities, verify_activities
from kageyoni.workspaces.resource_profiles import ResourceProfiles
from kageyoni.workspaces.resource_admission import ResourceAdmission, verify_resource_admission
from kageyoni.persistence.migrations import install_resource_profiles,install_resource_admission


class NativeFixture:
    def __init__(self,path,calibration=True,install=True):
        self.engine=Engine(path);install_resource_profiles(self.engine)
        self.engine.apply({'api_version':3,'branch':'main','request_id':'synthetic-persons','expected_revision':0,
            'actor':'fixture','kind':'action','narrative':'Explicit disposable native admission fixture.',
            'changes':[{'op':'create','domain':'character','id':name,'data':{'name':name,'entity_kind':'person'},
                        'visibility':'public','status':'proposed','evidence':[{'note':'Synthetic test, no campaign history.'}]} for name in ('alice','bob','charlie')]})
        Nodes(self.engine).bind('main','alice','bind-fixture',1,{'note':'Disposable operational test.'})
        self.workspace=Registry(self.engine).open('main','alice','document','native-fixture',source_ids=['alice'])['workspace_id']
        if calibration:
            profiles=ResourceProfiles(self.engine,self.workspace)
            profiles.configure({'profile_id':'calibration-1000','active_jobs':2},'capacity',profiles.get()['digest'])
        if install:install_resource_admission(self.engine)
        self.store=Activities(self.engine);self.admission=ResourceAdmission(self.engine,self.workspace)

    def create(self,aid,state='waiting',participants=('alice',),parent=None,native=None):
        spec={'activity_id':aid,'kind':'real_work','definition':{'id':'synthetic:native-admission-fixture','version':1,'digest':digest({'synthetic':'native-admission-fixture'})},
              'parent_id':parent,'participants':list(participants),'purpose':'Explicit native operational fixture.',
              'source_refs':[],'acceptance_ref':'native:fixture'}
        cp={'activity_id':aid,'activity_version':1,'state':state,'outcome':'unresolved'}
        return self.store.create(self.workspace,'main',spec,cp,native or {})

    def update(self,aid,state):
        row=self.store.get(self.workspace,aid);cp=deepcopy(row['checkpoint'])
        cp.update(state=state,activity_version=row['version']+1)
        return self.store.update(self.workspace,aid,row['version'],cp,row['native'])

    def close(self):self.engine.close()


@pytest.fixture
def make(tmp_path):
    fixtures=[]
    def factory(**kw):
        f=NativeFixture(tmp_path/('world-'+str(len(fixtures))+'.sqlite'),**kw);fixtures.append(f);return f
    yield factory
    for f in fixtures:f.close()


def capacity(exc):
    assert type(exc.value) is Rejected
    assert str(exc.value)=='resource activity capacity exceeded'
    assert exc.value.rejection_class=='TEMPORARY_STATE_BLOCK'
    assert exc.value.details=={'resource_capacity':True}


def test_origin_and_exact_usage_shape(make):
    import kageyoni.engine as engine
    import kageyoni.workspaces.resource_admission as admission
    assert Path(admission.__file__).resolve()==Path(engine.__file__).resolve().parent/'workspaces/resource_admission.py'
    f=make();u=f.admission.usage()
    assert set(u)=={'profile_digest','total_nonterminal','active','dormant','paused_capacity_reserved'}
    assert [u[k] for k in ('total_nonterminal','active','dormant','paused_capacity_reserved')]==[0,0,0,0]


def test_legacy_defaults_and_uncapped_native_semantics_recovery(make):
    f=make(calibration=False)
    with f.engine.transaction():
        for i in range(33):f.create('legacy-'+str(i),'paused' if i==0 else 'waiting')
    u=f.admission.usage();assert (u['total_nonterminal'],u['active'],u['dormant'],u['paused_capacity_reserved'])==(33,33,0,1)
    with pytest.raises(Rejected) as exc:f.admission.check_start()
    capacity(exc)
    with pytest.raises(Rejected) as exc:f.admission.check_resume('legacy-0')
    capacity(exc)
    assert f.admission.check_pause('legacy-1')['active']==33
    assert f.update('legacy-1','paused')['state']=='paused'  # Old native API deliberately remains uncapped.
    assert verify_resource_admission(f.engine)['installed']


def test_32_active_native_create_refusal_is_atomic(make):
    f=make()
    with f.engine.transaction():
        for i in range(32):f.create('active-'+str(i))
    rows=f.engine.db.execute('SELECT count(*) FROM activity_participants').fetchone()[0]
    with pytest.raises(Rejected) as exc:f.admission.check_start()
    capacity(exc)
    with pytest.raises(Rejected) as exc:f.create('over-limit')
    capacity(exc)
    assert f.engine.db.execute('SELECT 1 FROM activity_runs WHERE activity_id=?',('over-limit',)).fetchone() is None
    assert f.engine.db.execute('SELECT count(*) FROM activity_participants').fetchone()[0]==rows
    assert f.admission.usage()['active']==32
    assert verify_activities(f.engine)['activities']==32


def test_resume_pause_projection_and_update_rollback(make):
    f=make()
    with f.engine.transaction():
        for i in range(32):f.create('active-'+str(i))
        f.create('dormant','paused')
    original=f.store.get(f.workspace,'dormant');before=f.admission.usage()
    with pytest.raises(Rejected) as exc:f.admission.check_resume('dormant')
    capacity(exc)
    assert f.admission.usage()==before
    with pytest.raises(Rejected) as exc:f.update('dormant','waiting')
    capacity(exc)
    assert f.store.get(f.workspace,'dormant')==original
    projected=f.admission.check_pause('active-0');assert (projected['active'],projected['dormant'])==(31,2)
    f.update('active-0','paused');f.admission.check_resume('dormant');f.update('dormant','waiting')
    assert f.admission.usage()['active']==32
    assert verify_resource_admission(f.engine)['installed']


@pytest.mark.parametrize('marker',['',False,{},None])
def test_paused_encounter_marker_is_conservative(make,marker):
    f=make();f.create('physical','paused',native={'encounter_id':marker})
    u=f.admission.usage()
    expected=(0,1,1) if marker is None else (1,0,0)
    assert (u['active'],u['dormant'],u['paused_capacity_reserved'])==expected


def test_actual_1000_native_paused_reservations_and_1032_total_boundary(make):
    f=make();state=f.engine.state();revision=f.engine.branch('main')['revision']
    # Every row/spec/membership is created by the real native API in one outer
    # transaction. This is a native boundary fixture, not product load calibration.
    with f.engine.transaction():
        for i in range(1000):f.create('paused-'+str(i),'paused')
        for i in range(32):f.create('active-'+str(i))
    u=f.admission.usage()
    assert (u['total_nonterminal'],u['active'],u['dormant'],u['paused_capacity_reserved'])==(1032,32,1000,1000)
    assert f.engine.state()==state and f.engine.branch('main')['revision']==revision
    before=f.store.get(f.workspace,'active-0')
    with pytest.raises(Rejected) as exc:f.admission.check_pause('active-0')
    capacity(exc)
    with pytest.raises(Rejected) as exc:f.update('active-0','paused')
    capacity(exc)
    assert f.store.get(f.workspace,'active-0')==before
    with pytest.raises(Rejected) as exc:f.create('paused-over','paused')
    capacity(exc)
    with pytest.raises(Rejected) as exc:f.create('active-over')
    capacity(exc)
    f.update('active-0','finished');f.admission.check_resume('paused-0');f.update('paused-0','waiting')
    f.admission.check_pause('active-1');f.update('active-1','paused')
    assert f.admission.usage()['paused_capacity_reserved']==1000
    assert verify_resource_admission(f.engine)['installed'] and f.engine.verify()['ok']


def test_terminal_update_remains_reachable_during_explicit_negative_overage(make):
    f=make()
    with f.engine.transaction():
        for i in range(32):f.create('active-'+str(i))
        for i in range(2):f.create('paused-'+str(i),'paused')
    # Negative specimen: corrupt existing native reservation markers, not SQL
    # fabrication of activities or dormant population/history.
    f.engine.db.execute("UPDATE activity_runs SET native_json=? WHERE state='paused'",(encoded({'encounter_id':''}),))
    assert f.admission.usage()['active']==34
    with pytest.raises(Rejected) as exc:verify_resource_admission(f.engine)
    capacity(exc)
    f.update('active-0','cancelled')
    assert f.admission.usage()['active']==33  # Still over, cancellation was not blocked.
    with pytest.raises(Rejected):verify_resource_admission(f.engine)
    f.update('active-1','finished')
    assert verify_resource_admission(f.engine)['installed']


def test_live_paused_work_reserves_dormant_slot_until_actual_queue_clear(tmp_path):
    # Real existing product producer supplies issued jobs; no direct SQL job rows.
    from samsara.owner import Owner
    from samsara.content import definitions
    from samsara.protocol import PROTOCOL
    import tempfile,time
    root=Path(tempfile.mkdtemp(prefix='d14b-live-'))/'w'
    owner=Owner(root,True,listen=False)
    try:
        e=owner.engine;install_resource_admission(e);app=owner.app;ctx,_=app.bind('operator')
        p=ResourceProfiles(e,app.workspace_id);p.configure({'profile_id':'calibration-1000','active_jobs':1},'one',p.get()['digest'])
        source=app.handle(ctx,{'protocol':PROTOCOL,'request_id':'source','workspace_id':app.workspace_id,'branch':'main','expected_revision':app.revision(),'operation':{'name':'workspace.view','limit':32,'cursor':None}})['return']['source_refs'][0]
        d=next(d for d in definitions() if d['id']=='synthetic:real_work')
        response=app.handle(ctx,{'protocol':PROTOCOL,'request_id':'start','workspace_id':app.workspace_id,'branch':'main','expected_revision':app.revision(),'operation':{'name':'activity.start','activity_id':'live','kind':'real_work','definition':d['reference'],'parent_id':None,'participants':['visitor'],'purpose':'Native slot fixture.','source_refs':[source],'acceptance_ref':'native:text_work/1'}})
        assert 'error' not in response,response
        a=app.store.get(app.workspace_id,'live');q=app.runner.queue
        q.enqueue(a['native']['job_id'],ctx.binding_id,ctx.authority_epoch,'source_index',{'delay_seconds':0,'cpu_iterations':0},10)
        row=q.claim(time.time())
        cp=deepcopy(a['checkpoint']);cp.update(state='paused',activity_version=a['version']+1)
        app.store.update(app.workspace_id,'live',a['version'],cp,a['native'])
        admission=ResourceAdmission(e,app.workspace_id)
        assert tuple(admission.usage()[k] for k in ('active','dormant','paused_capacity_reserved'))==(1,0,1)
        # An explicit queue-unit process observation, not a claim a job ran.
        q.process(row['job_id'],q.fence(row),{'fixture':'current unit-test process; no child launched'},time.time())
        q.transition(row['job_id'],'reconciling','stop pending')
        assert tuple(admission.usage()[k] for k in ('active','dormant','paused_capacity_reserved'))==(1,0,1)
        q.transition(row['job_id'],'reconciling','observed stopped',clear_process=True)
        assert tuple(admission.usage()[k] for k in ('active','dormant','paused_capacity_reserved'))==(0,1,1)
        assert verify_resource_admission(e)['installed']
    finally:owner.close()
    import shutil
    shutil.copytree(root,tmp_path/'preserved-live-world')


def test_scoped_keyset_paging_hidden_foreign_and_missing_anchors(make):
    f=make()
    for aid,people in [('a',('alice',)),('b',('bob',)),('c',('alice','bob')),('d',('charlie',)),('e',('alice',))]:
        f.create(aid,participants=people)
    assert [a['activity_id'] for a in f.store.page(f.workspace,character_id='alice',limit=2)]==['a','c']
    assert [a['activity_id'] for a in f.store.page(f.workspace,character_id='alice',after='c',limit=2)]==['e']
    with pytest.raises(Rejected,match='activity cursor unavailable'):f.store.page(f.workspace,character_id='alice',after='b')
    with pytest.raises(Rejected,match='activity cursor unavailable'):f.store.page(f.workspace,character_id='alice',after='gone')
    f.create('bb-hidden',participants=('bob',))
    assert [a['activity_id'] for a in f.store.page(f.workspace,character_id='alice',after='a',limit=2)]==['c','e']
    with patch.object(f.store,'get',wraps=f.store.get) as decoded:
        page=f.store.page(f.workspace,limit=2)
        assert len(page)==2 and decoded.call_count==2
    assert verify_activities(f.engine)['activities']==6


def test_worker_descendants_are_membership_scoped_and_depth_bounded(make):
    f=make();f.create('root');parent='root'
    for i in range(1,7):
        f.create('level-'+str(i),parent=parent,participants=('bob',) if i==2 else ('alice',));parent='level-'+str(i)
    f.create('foreign-root');f.create('foreign-child',parent='foreign-root')
    ids={a['activity_id'] for a in f.store.page(f.workspace,character_id='alice',root_activity_id='root')}
    assert ids=={'root','level-1','level-3','level-4'}
    with pytest.raises(Rejected,match='activity cursor unavailable'):
        f.store.page(f.workspace,character_id='alice',root_activity_id='root',after='foreign-child')
    with pytest.raises(Rejected,match='worker activity scope requires character'):f.store.page(f.workspace,root_activity_id='root')


@pytest.mark.parametrize('kind',['missing','extra'])
def test_exact_membership_corruption_rejects_global_and_direct_verification(make,kind):
    f=make();f.create('private',participants=('alice',))
    if kind=='missing':f.engine.db.execute('DELETE FROM activity_participants')
    else:f.engine.db.execute('INSERT INTO activity_participants VALUES(?,?,?)',(f.workspace,'bob','private'))
    with pytest.raises(Rejected,match='participant membership mismatch'):verify_resource_admission(f.engine)
    with pytest.raises(Rejected,match='participant membership mismatch'):f.engine.verify()
    if kind=='extra':
        with pytest.raises(Rejected,match='activity unavailable'):f.store.page(f.workspace,character_id='bob')


def test_target_and_page_input_errors_never_claim_capacity(make):
    f=make();f.create('done','finished')
    for aid in ['absent','done']:
        for fn in [f.admission.check_resume,f.admission.check_pause]:
            with pytest.raises(Rejected) as exc:fn(aid)
            assert not exc.value.details.get('resource_capacity')
    for kwargs in [{'limit':0},{'limit':102},{'limit':True},{'after':''},{'character_id':''},{'root_activity_id':''}]:
        with pytest.raises(Rejected):f.store.page(f.workspace,**kwargs)


def test_actual_predecessor_membership_backfill_backup_restore_and_reopen(make,tmp_path):
    f=make(install=False);f.create('a',participants=('alice','bob'));f.create('b','paused',participants=('bob',))
    original={aid:f.store.get(f.workspace,aid) for aid in ['a','b']};world=f.engine.state()
    install_resource_admission(f.engine)
    assert {aid:f.store.get(f.workspace,aid) for aid in ['a','b']}==original and f.engine.state()==world
    assert [tuple(r) for r in f.engine.db.execute('SELECT character_id,activity_id FROM activity_participants ORDER BY character_id,activity_id')]==[('alice','a'),('bob','a'),('bob','b')]
    backup=next(Path(f.engine.path).parent.glob('*.pre-v32-*.bak'))
    e=Engine(backup,read_only=True);assert e.verify()['ok']
    assert e.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==31
    assert not e.db.execute("SELECT 1 FROM sqlite_master WHERE name='activity_participants'").fetchone();e.close()
    restored=tmp_path/'restored.sqlite';Engine.restore(backup,restored)
    e=Engine(restored);install_resource_admission(e)
    assert verify_resource_admission(e)['installed']
    assert [a['activity_id'] for a in Activities(e).page(f.workspace,character_id='bob')]==['a','b'];e.close()
    current=tmp_path/'current.backup.sqlite';f.engine.backup(current)
    before=hashlib.sha256(current.read_bytes()).hexdigest();e=Engine(current,read_only=True)
    assert verify_resource_admission(e)['installed'] and e.verify()['ok'] and e.validate_registry()['ok']
    assert ResourceAdmission(e,f.workspace).usage()==f.admission.usage();assert e.db.total_changes==0
    e.close();assert hashlib.sha256(current.read_bytes()).hexdigest()==before


def test_overcapacity_real_v31_predecessor_refuses_before_schema_commit(make):
    f=make(install=False)
    with f.engine.transaction():
        for i in range(33):f.create('antecedent-'+str(i))
    state=f.engine.state();revision=f.engine.branch('main')['revision']
    with pytest.raises(Rejected) as exc:install_resource_admission(f.engine)
    capacity(exc)
    assert f.engine.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==31
    assert not f.engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='activity_participants'").fetchone()
    assert not f.engine.db.execute("SELECT 1 FROM engine_versions WHERE component='resource_admission_interface'").fetchone()
    assert f.engine.db.execute('SELECT count(*) FROM activity_runs').fetchone()[0]==33
    assert f.engine.state()==state and f.engine.branch('main')['revision']==revision
    # Explicit real native cancellation on the genuine predecessor, not SQL repair.
    f.update('antecedent-0','cancelled');install_resource_admission(f.engine)
    assert f.admission.usage()['active']==32
    assert verify_resource_admission(f.engine)['installed']
