"""Real native metadata with genuine installed-product issued-work producers.

No worker launches, forged jobs, dormant row fabrication or canonical history.
Queue transitions below are explicit low-level scheduling observations, not
claims that a worker/result was executed or accepted by the product.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import time
import shutil
import subprocess

import pytest
from kageyoni.engine import Engine, Rejected, digest
from kageyoni.persistence.migrations import install_resource_profiles, _install_component
from kageyoni.workspaces.job_queue import JobQueue, verify_queue
from kageyoni.workspaces.resource_profiles import ResourceProfiles, legacy_profile, verify_resource_profiles
from samsara.owner import Owner
from samsara.content import definitions
from samsara.protocol import PROTOCOL

# Disclosed immutable antecedent reference for the scheduler-negative case.
# This is test data only; no application or product imports/uses this module.
ANTECEDENT_QUEUE_SHA256 = '6d2890999a14d2a1bd75c259ab8835d180f0e3aab36f69dad4ded6eaee16e134'
ANTECEDENT_QUEUE_SOURCE = '"""Engine-owned durable admission, fair selection and fenced lease state.\n\nThe sole application owner supplies process observations. No process, model or\nfile IO runs inside these transactions. Charged starts/ceilings are never\nrefunded by nesting, cancellation, a crash, or manual reconciliation.\n"""\nimport hashlib\nimport json\nfrom uuid import uuid4\nfrom ..engine import require, encoded\nfrom ..persistence.unit_of_work import UnitOfWork\nfrom ..resources import schema_path\n\n\nclass JobQueue:\n    def __init__(self, engine, workspace_id):\n        self.engine, self.db, self.workspace_id = engine, engine.db, workspace_id\n        require(self.db.execute("SELECT 1 FROM engine_versions WHERE component=\'activity_queue_interface\' AND version=\'1\'").fetchone(), \'queue not installed\')\n\n    def boot(self, now):\n        with UnitOfWork(self.db):\n            self.db.execute(\'\'\'INSERT INTO activity_queue_owners VALUES(?,1,?)\n                ON CONFLICT(workspace_id) DO UPDATE SET epoch=epoch+1,last_wall=excluded.last_wall\'\'\', (self.workspace_id, now))\n            self.db.execute("UPDATE activity_queue SET state=\'reconciling\',reason=\'owner restarted; observe process before disposition\' WHERE workspace_id=? AND state=\'running\'", (self.workspace_id,))\n        return self.owner()[\'epoch\']\n\n    def owner(self):\n        return dict(self.db.execute(\'SELECT * FROM activity_queue_owners WHERE workspace_id=?\', (self.workspace_id,)).fetchone())\n\n    def row(self, job_id):\n        row = self.db.execute(\'SELECT * FROM activity_queue WHERE workspace_id=? AND job_id=?\', (self.workspace_id, job_id)).fetchone()\n        return dict(row) if row else None\n\n    def rows(self):\n        return [dict(r) for r in self.db.execute(\'SELECT * FROM activity_queue WHERE workspace_id=? ORDER BY sequence\', (self.workspace_id,))]\n\n    def root(self, activity_id):\n        seen = set()\n        while True:\n            require(activity_id not in seen, \'activity parent cycle\')\n            seen.add(activity_id)\n            row = self.db.execute(\'SELECT parent_id FROM activity_runs WHERE workspace_id=? AND activity_id=?\', (self.workspace_id, activity_id)).fetchone()\n            require(row is not None, \'activity unavailable\')\n            if not row[0]: return activity_id\n            activity_id = row[0]\n\n    def manual_starts(self, root_id):\n        return self.db.execute(\'\'\'WITH RECURSIVE tree(activity_id) AS (\n            SELECT activity_id FROM activity_runs WHERE workspace_id=? AND activity_id=?\n            UNION ALL SELECT a.activity_id FROM activity_runs a JOIN tree t ON a.parent_id=t.activity_id WHERE a.workspace_id=?)\n            SELECT count(*) FROM activity_jobs j JOIN tree t ON j.activity_id=t.activity_id\n            LEFT JOIN activity_queue q ON q.job_id=j.job_id\n            WHERE j.workspace_id=? AND j.result_json IS NOT NULL AND j.returned_by=\'worker\' AND q.job_id IS NULL\'\'\',\n            (self.workspace_id,root_id,self.workspace_id,self.workspace_id)).fetchone()[0]\n\n    def enqueue(self, job_id, binding_id, authority_epoch, recipe, parameters, max_seconds):\n        require(0 < max_seconds <= 120, \'invalid work ceiling\')\n        with UnitOfWork(self.db):\n            old = self.row(job_id)\n            if old:\n                require((old[\'binding_id\'],old[\'authority_epoch\'],old[\'recipe\'],old[\'parameters_json\'],old[\'max_seconds\']) ==\n                    (binding_id,authority_epoch,recipe,encoded(parameters),max_seconds), \'queue identity conflict\')\n                return old\n            job = self.db.execute(\'SELECT activity_id,state FROM activity_jobs WHERE workspace_id=? AND job_id=?\', (self.workspace_id,job_id)).fetchone()\n            require(job and job[\'state\']==\'waiting\', \'job unavailable\')\n            require(self.db.execute("SELECT count(*) FROM activity_queue WHERE workspace_id=? AND state IN (\'queued\',\'running\',\'paused\',\'reconciling\')", (self.workspace_id,)).fetchone()[0] < 32, \'queue full\')\n            root = self.root(job[\'activity_id\'])\n            self.db.execute(\'INSERT OR IGNORE INTO activity_queue_roots(workspace_id,root_id) VALUES(?,?)\', (self.workspace_id,root))\n            self.db.execute(\'\'\'INSERT INTO activity_queue(job_id,workspace_id,root_id,binding_id,authority_epoch,recipe,parameters_json,state,max_seconds)\n                VALUES(?,?,?,?,?,?,?,\'queued\',?)\'\'\', (job_id,self.workspace_id,root,binding_id,authority_epoch,recipe,encoded(parameters),max_seconds))\n        return self.row(job_id)\n\n    def claim(self, now):\n        with UnitOfWork(self.db):\n            owner = self.owner()\n            if now < owner[\'last_wall\']:\n                self.db.execute("UPDATE activity_queue SET state=\'reconciling\',reason=\'wall clock rollback\' WHERE workspace_id=? AND state IN (\'running\',\'queued\')", (self.workspace_id,))\n                return None\n            self.db.execute(\'UPDATE activity_queue_owners SET last_wall=? WHERE workspace_id=?\', (now,self.workspace_id))\n            # Reconciling processes retain their slot until observed stopped.\n            active = self.db.execute("SELECT count(*) FROM activity_queue WHERE workspace_id=? AND (state=\'running\' OR (state=\'reconciling\' AND process_json IS NOT NULL))", (self.workspace_id,)).fetchone()[0]\n            if active >= 2: return None\n            heavy = any(json.loads(r[\'parameters_json\']).get(\'cpu_iterations\',0)>0 for r in\n                self.db.execute("SELECT parameters_json FROM activity_queue WHERE workspace_id=? AND (state=\'running\' OR (state=\'reconciling\' AND process_json IS NOT NULL))", (self.workspace_id,)))\n            rows = self.db.execute(\'\'\'SELECT q.* FROM activity_queue q JOIN activity_queue_roots r\n                ON q.workspace_id=r.workspace_id AND q.root_id=r.root_id\n                WHERE q.workspace_id=? AND q.state=\'queued\' ORDER BY r.last_dispatch,q.sequence\'\'\', (self.workspace_id,)).fetchall()\n            for raw in rows:\n                row = dict(raw)\n                if heavy and json.loads(row[\'parameters_json\']).get(\'cpu_iterations\',0)>0:\n                    continue\n                binding = self.db.execute(\'SELECT active,authority_epoch FROM activity_bindings WHERE binding_id=?\', (row[\'binding_id\'],)).fetchone()\n                if not binding or not binding[\'active\'] or binding[\'authority_epoch\'] != row[\'authority_epoch\']:\n                    self.db.execute("UPDATE activity_queue SET state=\'paused\',reason=\'authority changed\' WHERE job_id=?", (row[\'job_id\'],)); continue\n                job = self.db.execute(\'SELECT activity_id,state FROM activity_jobs WHERE job_id=?\', (row[\'job_id\'],)).fetchone()\n                aid = job[\'activity_id\']; blocked = job[\'state\']!=\'waiting\'\n                while aid:\n                    a = self.db.execute(\'SELECT state,parent_id FROM activity_runs WHERE workspace_id=? AND activity_id=?\', (self.workspace_id,aid)).fetchone()\n                    if a[\'state\'] in (\'paused\',\'cancelled\',\'failed\',\'finished\'): blocked=True\n                    aid=a[\'parent_id\']\n                if blocked: continue\n                budget = self.db.execute(\'SELECT * FROM activity_queue_roots WHERE workspace_id=? AND root_id=?\', (self.workspace_id,row[\'root_id\'])).fetchone()\n                if budget[\'starts\']+self.manual_starts(row[\'root_id\']) >= 4 or budget[\'reserved_seconds\']+row[\'max_seconds\']>900:\n                    self.db.execute("UPDATE activity_queue SET state=\'paused\',reason=\'parent budget exhausted\' WHERE job_id=?", (row[\'job_id\'],));continue\n                serial = self.db.execute(\'SELECT coalesce(max(last_dispatch),0)+1 FROM activity_queue_roots WHERE workspace_id=?\', (self.workspace_id,)).fetchone()[0]\n                self.db.execute(\'UPDATE activity_queue_roots SET starts=starts+1,reserved_seconds=reserved_seconds+?,last_dispatch=? WHERE workspace_id=? AND root_id=?\',\n                    (row[\'max_seconds\'],serial,self.workspace_id,row[\'root_id\']))\n                self.db.execute("UPDATE activity_queue SET state=\'running\',generation=generation+1,owner_epoch=?,lease_token=?,lease_until=?,reason=\'\' WHERE job_id=? AND state=\'queued\'",\n                    (owner[\'epoch\'],uuid4().hex,now+row[\'max_seconds\'],row[\'job_id\']))\n                return self.row(row[\'job_id\'])\n        return None\n\n    def assert_lease(self, job_id, fence, now):\n        row=self.row(job_id)\n        require(row and row[\'state\']==\'running\' and row[\'owner_epoch\']==self.owner()[\'epoch\'] and\n            fence=={\'epoch\':row[\'owner_epoch\'],\'generation\':row[\'generation\'],\'token\':row[\'lease_token\']} and\n            now>=self.owner()[\'last_wall\'] and now<row[\'lease_until\'], \'stale queue lease\')\n        return row\n\n    @staticmethod\n    def fence(row):\n        return {\'epoch\':row[\'owner_epoch\'],\'generation\':row[\'generation\'],\'token\':row[\'lease_token\']}\n\n    def process(self, job_id, fence, observation, now):\n        with UnitOfWork(self.db):\n            self.assert_lease(job_id,fence,now)\n            self.db.execute(\'UPDATE activity_queue SET process_json=? WHERE job_id=?\', (encoded(observation),job_id))\n\n    def transition(self, job_id, state, reason=\'\', output_ref=None, clear_process=False):\n        require(state in (\'queued\',\'paused\',\'reconciling\',\'returned\',\'cancelled\',\'failed\'), \'invalid queue transition\')\n        with UnitOfWork(self.db):\n            require(self.row(job_id), \'queue job unavailable\')\n            self.db.execute(\'\'\'UPDATE activity_queue SET state=?,reason=?,output_ref_json=coalesce(?,output_ref_json),\n                process_json=CASE WHEN ? THEN NULL ELSE process_json END WHERE job_id=?\'\'\',\n                (state,reason,encoded(output_ref) if output_ref else None,clear_process,job_id))\n\n\ndef verify_queue(engine):\n    db=engine.db\n    check=db.execute(\'SELECT checksum FROM migration_checks WHERE version=27\').fetchone()\n    require(check and check[0]==hashlib.sha256(schema_path(\'migration_027.sql\').read_bytes()).hexdigest(), \'queue migration checksum mismatch\')\n    require(not db.execute(\'PRAGMA foreign_key_check\').fetchall(), \'queue foreign key failure\')\n    require(not db.execute("SELECT workspace_id FROM activity_queue WHERE state=\'running\' GROUP BY workspace_id HAVING count(*)>2").fetchall(), \'queue capacity exceeded\')\n    for row in db.execute("SELECT * FROM activity_queue WHERE state=\'running\'"):\n        owner=db.execute(\'SELECT epoch FROM activity_queue_owners WHERE workspace_id=?\',(row[\'workspace_id\'],)).fetchone()\n        require(owner and row[\'owner_epoch\']==owner[0] and row[\'lease_token\'] and row[\'lease_until\'] is not None,\'invalid live lease\')\n    return {\'installed\':True,\'interface\':\'1\'}\n'


class Fixture:
    def __init__(self, path, capacity=None, install=True):
        self.owner = Owner(path, True, listen=False)
        self.app = self.owner.app
        self.engine = self.owner.engine
        self.queue = self.app.runner.queue
        self.context, _ = self.app.bind('operator')
        self.serial = 0
        self.profiles = ResourceProfiles(self.engine, self.app.workspace_id)
        self.source = self.call({'name': 'workspace.view', 'limit': 32, 'cursor': None})['return']['source_refs'][0]
        if install:
            install_resource_profiles(self.engine)
        if capacity:
            self.configure(capacity)

    def configure(self, capacity, request='select', expected=None):
        return self.profiles.configure({'profile_id':'calibration-1000','active_jobs':capacity}, request,
                                       expected or self.profiles.get()['digest'])

    def call(self, operation):
        self.serial += 1
        result = self.app.handle(self.context, {'protocol':PROTOCOL,'request_id':'native-fixture:'+str(self.serial),
            'workspace_id':self.app.workspace_id,'branch':'main','expected_revision':self.app.revision(),'operation':operation})
        assert 'error' not in result, result
        return result

    def start(self, aid, parent=None, enqueue=True, heavy=False):
        definition = next(d for d in definitions() if d['id']=='synthetic:real_work')
        self.call({'name':'activity.start','activity_id':aid,'kind':'real_work','definition':definition['reference'],
            'parent_id':parent,'participants':['visitor'],'purpose':'Explicit synthetic native admission fixture.',
            'source_refs':[self.source],'acceptance_ref':'native:text_work/1'})
        job = self.app.store.get(self.app.workspace_id, aid)['native']['job_id']
        if enqueue:
            self.queue.enqueue(job,self.context.binding_id,self.context.authority_epoch,'bounded_probe',
                               {'delay_seconds':0,'cpu_iterations':1 if heavy else 0},10)
        return job

    def observe_stopped_return(self, row):
        self.queue.transition(row['job_id'],'returned',clear_process=True)

    def close(self):
        # No fixture ever launches a child. Clear synthetic process metadata
        # before Owner.close so no OS signal can target a fixture observation.
        for row in self.queue.rows():
            if row['process_json']:
                self.queue.transition(row['job_id'],'reconciling','fixture observation ended',clear_process=True)
        self.owner.close()


class ClosedV30Fixture:
    """Preserved old installed producer, then future-native migration of a copy.

    `app` is only this fixture's readonly workspace/revision adapter for old
    assertions; no future Owner opens or silently upgrades the predecessor.
    """
    def __init__(self,path,queued=False):
        python=os.environ.get('SAMSARA_V30_PRODUCER_PYTHON')
        expected=os.environ.get('SAMSARA_V30_EXPECTED_RUNTIME')
        if not python or not expected:
            pytest.fail('Genuine v30 prerequisite: set SAMSARA_V30_PRODUCER_PYTHON and SAMSARA_V30_EXPECTED_RUNTIME to the separately installed trusted predecessor; never substitute the future Owner.')
        # Preserve the explicit venv launcher path: resolving its symlink to
        # the base interpreter would discard that installed predecessor.
        python=Path(python).absolute()
        assert python.is_file(),'Explicit v30 producer Python unavailable'
        producer=Path(__file__).with_name('_produce_v30_profile_world.py')
        original=path/'original-v30'
        args=[str(python),'-I',str(producer),'--world',str(original),'--expected-runtime',expected]
        if queued:args.append('--queued-job')
        path.mkdir(mode=0o700,parents=True,exist_ok=False)
        env={'PATH':str(python.parent)+':/usr/bin:/bin','LC_ALL':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
        produced=subprocess.run(args,cwd=path,env=env,capture_output=True,text=True,timeout=30)
        (path/'producer.stdout.log').write_text(produced.stdout)
        (path/'producer.stderr.log').write_text(produced.stderr)
        assert produced.returncode==0,produced.stderr
        self.receipt=json.loads(produced.stdout)
        assert self.receipt['migration_max']==30 and self.receipt['producer_closed']
        assert self.receipt['runtime_digest']==expected and self.receipt['worker_launches']==0
        self.original=original
        self.path=path/'future-native-copy.sqlite'
        shutil.copy2(original/'world.sqlite',self.path)
        self.engine=Engine(self.path)
        assert self.engine.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==30
        assert 'profile_digest' not in [r['name'] for r in self.engine.db.execute('PRAGMA table_info(activity_queue)')]
        self.workspace_id=self.receipt['workspace_id']
        self.app=self
        self.queue=JobQueue(self.engine,self.workspace_id)
        self.profiles=ResourceProfiles(self.engine,self.workspace_id)
        self.job_id=self.receipt['job_id']
        if queued:assert self.queue.row(self.job_id)==self.receipt['queue_row']

    def revision(self):return self.engine.branch('main')['revision']

    def configure(self,capacity,request='select',expected=None):
        return self.profiles.configure({'profile_id':'calibration-1000','active_jobs':capacity},request,
                                       expected or self.profiles.get()['digest'])

    def close(self):
        self.engine.close()
        assert hashlib.sha256((self.original/'world.sqlite').read_bytes()).hexdigest()==self.receipt['database_sha256']
        assert hashlib.sha256((self.original/'workspace.json').read_bytes()).hexdigest()==self.receipt['metadata_sha256']


@pytest.fixture
def legacy(tmp_path):
    fixtures=[]
    def factory(queued=False):
        f=ClosedV30Fixture(tmp_path/('legacy'+str(len(fixtures))),queued);fixtures.append(f);return f
    yield factory
    for f in fixtures:f.close()


@pytest.fixture
def make(tmp_path):
    fixtures=[]
    def factory(**kw):
        f=Fixture(tmp_path/('world'+str(len(fixtures))),**kw);fixtures.append(f);return f
    yield factory
    for f in fixtures:f.close()


def test_candidate_native_import_origin():
    import kageyoni.workspaces.resource_profiles as module
    import kageyoni.engine as engine
    package = Path(engine.__file__).resolve().parent
    assert Path(module.__file__).resolve() == package/'workspaces/resource_profiles.py'
    import kageyoni.workspaces.job_queue as queue
    assert Path(queue.__file__).resolve() == package/'workspaces/job_queue.py'


def test_legacy_get_read_only_absent_table_and_row(legacy):
    f=legacy()
    assert f.profiles.get()==legacy_profile()
    before=f.engine.db.total_changes
    assert f.profiles.get()==legacy_profile()
    assert f.engine.db.total_changes==before
    assert verify_resource_profiles(f.engine)=={'installed':False}
    assert verify_queue(f.engine)=={'installed':True,'interface':'1'}
    install_resource_profiles(f.engine)
    assert f.profiles.get()==legacy_profile()
    before=f.engine.db.total_changes
    assert f.profiles.get()==legacy_profile()
    assert f.engine.db.total_changes==before


def test_configure_cas_replay_conflict_noop_after_work_and_history(make):
    f=make();state=f.engine.state();revision=f.app.revision()
    legacy=f.profiles.get();one=f.configure(1,'first')
    assert one==f.profiles.get() and one['active_jobs']==1 and one['inactive_activity_limit']==1000
    assert one['total_nonterminal_limit']==1032 and one['queue_backlog']==32
    changes=f.engine.db.total_changes
    assert f.configure(1,'first',legacy['digest'])==one
    assert f.engine.db.total_changes==changes
    with pytest.raises(Rejected,match='identity conflict'):f.configure(2,'first',legacy['digest'])
    with pytest.raises(Rejected,match='stale resource'):f.configure(2,'stale',legacy['digest'])
    two=f.configure(2,'second')
    assert f.configure(1,'first',legacy['digest'])==one  # Historical replay before current CAS.
    assert f.profiles.get()==two
    assert f.engine.state()==state and f.app.revision()==revision
    f.start('issued')
    profile_row=dict(f.engine.db.execute('SELECT * FROM activity_resource_profiles').fetchone())
    roots=[dict(r) for r in f.engine.db.execute('SELECT * FROM activity_queue_roots')]
    state=f.engine.state();revision=f.app.revision()
    assert f.configure(2,'noop')==two
    assert dict(f.engine.db.execute('SELECT * FROM activity_resource_profiles').fetchone())==profile_row
    assert [dict(r) for r in f.engine.db.execute('SELECT * FROM activity_queue_roots')]==roots
    assert f.engine.state()==state and f.app.revision()==revision
    changes=f.engine.db.total_changes
    assert f.configure(2,'noop',two['digest'])==two
    assert f.engine.db.total_changes==changes
    with pytest.raises(Rejected,match='identity conflict'):f.configure(1,'noop',two['digest'])
    with pytest.raises(Rejected,match='before issued work'):f.configure(1,'after-issued')
    assert verify_resource_profiles(f.engine)['profiles']==1


@pytest.mark.parametrize('bad',[{}, {'profile_id':'legacy','active_jobs':2}, {'profile_id':'calibration-1000','active_jobs':True},
    {'profile_id':'calibration-1000','active_jobs':3}, {'profile_id':'calibration-1000','active_jobs':1,'extra':0}])
def test_strict_profile_input_no_mutation(make,bad):
    f=make();before=f.engine.db.total_changes
    with pytest.raises(Rejected):f.profiles.configure(bad,'bad',f.profiles.get()['digest'])
    assert f.engine.db.total_changes==before
    assert f.profiles.get()==legacy_profile()


@pytest.mark.parametrize('capacity',[1,2])
def test_actual_claim_limit_and_reconciling_slot(make,capacity):
    f=make(capacity=capacity)
    for i in range(capacity+1):f.start('a'+str(i))
    rows=[f.queue.claim(time.time()) for _ in range(capacity)]
    assert all(rows) and f.queue.claim(time.time()) is None
    first=rows[0]
    # Truthful current process observation, never a claim it executed the job.
    observation={'fixture':'current test process; no worker launched','pid':os.getpid()}
    f.queue.process(first['job_id'],f.queue.fence(first),observation,time.time())
    f.queue.transition(first['job_id'],'reconciling','explicit synthetic live-process slot observation')
    assert f.queue.claim(time.time()) is None
    assert verify_queue(f.engine)=={'installed':True,'interface':'1'}
    assert verify_resource_profiles(f.engine)['profiles']==1
    f.queue.transition(first['job_id'],'reconciling','observed stopped',clear_process=True)
    assert f.queue.claim(time.time()) is not None
    assert len(f.queue.rows(live_only=True))==capacity+1
    assert all(r['state'] in ('running','queued','reconciling') for r in f.queue.rows(live_only=True))


def test_heavy_lane_root_charges_and_fifo_remain(make):
    f=make(capacity=2)
    for aid,heavy in [('cpu1',True),('cpu2',True),('io',False)]:f.start(aid,heavy=heavy)
    one=f.queue.claim(time.time());two=f.queue.claim(time.time())
    assert one['job_id']==f.app.store.get(f.app.workspace_id,'cpu1')['native']['job_id']
    assert two['job_id']==f.app.store.get(f.app.workspace_id,'io')['native']['job_id']
    assert f.queue.claim(time.time()) is None
    f.observe_stopped_return(one);f.observe_stopped_return(two)
    third=f.queue.claim(time.time());assert third['job_id']==f.app.store.get(f.app.workspace_id,'cpu2')['native']['job_id']
    f.observe_stopped_return(third)
    f.start('parent',enqueue=False)
    jobs=[f.start('child'+str(i),'parent') for i in range(6)]
    for i in range(4):
        row=f.queue.claim(time.time());assert row['job_id']==jobs[i];f.observe_stopped_return(row)
    assert f.queue.claim(time.time()) is None
    assert all(f.queue.row(j)['state']=='paused' for j in jobs[4:])
    budget=f.engine.db.execute('SELECT starts,reserved_seconds FROM activity_queue_roots WHERE root_id=?',('parent',)).fetchone()
    assert tuple(budget)==(4,40)
    assert verify_resource_profiles(f.engine)['profiles']==1


def test_continuous_new_roots_cannot_overtake_older_second_job(make):
    f=make(capacity=1)
    f.start('root-a',enqueue=False);f.start('a1','root-a');a2=f.start('a2','root-a')
    first=f.queue.claim(time.time());f.observe_stopped_return(first)
    f.start('new-root-0')
    assert f.queue.claim(time.time())['job_id']==a2


def test_wrong_profile_binding_refuses_claim_and_direct_verifier(make):
    f=make(capacity=1);job=f.start('a')
    # Explicit negative corruption specimen, not fictional history or a fixture shortcut.
    f.engine.db.execute('UPDATE activity_queue SET profile_digest=? WHERE job_id=?',('0'*64,job))
    with pytest.raises(Rejected,match='profile binding mismatch'):f.queue.claim(time.time())
    with pytest.raises(Rejected,match='profile binding mismatch'):verify_resource_profiles(f.engine)
    assert f.queue.row(job)['state']=='queued'


def test_genuine_predecessor_migration_backup_reopen_restore_and_pin(legacy,tmp_path):
    f=legacy(queued=True);job=f.job_id
    assert f.receipt['queued_admission_replayed_without_writes']
    state=f.engine.state();revision=f.app.revision();oldrow=f.queue.row(job)
    install_resource_profiles(f.engine)
    assert f.profiles.get()==legacy_profile()
    assert f.queue.row(job)==dict(oldrow,profile_digest=legacy_profile()['digest'])
    changes=f.engine.db.total_changes
    assert f.queue.enqueue(job,oldrow['binding_id'],oldrow['authority_epoch'],oldrow['recipe'],
        json.loads(oldrow['parameters_json']),oldrow['max_seconds'])==dict(oldrow,profile_digest=legacy_profile()['digest'])
    assert f.engine.db.total_changes==changes
    assert f.engine.state()==state and f.app.revision()==revision
    with pytest.raises(Rejected,match='before issued work'):f.configure(1)
    backup=next(Path(f.engine.path).parent.glob('*.pre-v31-*.bak'))
    read=Engine(backup,read_only=True)
    assert read.verify()['ok'] and read.validate_registry()['ok']
    assert read.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==30
    assert 'profile_digest' not in [r['name'] for r in read.db.execute('PRAGMA table_info(activity_queue)')]
    read.close()
    restored=tmp_path/'restored-v30.sqlite'
    Engine.restore(backup,restored)
    e=Engine(restored);install_resource_profiles(e)
    assert JobQueue(e,f.app.workspace_id).row(job)==dict(oldrow,profile_digest=legacy_profile()['digest'])
    assert verify_resource_profiles(e)['profiles']==0
    assert e.verify()['ok'] and e.validate_registry()['ok'];e.close()
    healthy=tmp_path/'configured.backup.sqlite'
    f.engine.backup(healthy)
    e=Engine(healthy,read_only=True)
    before=hashlib.sha256(healthy.read_bytes()).hexdigest()
    assert ResourceProfiles(e,f.app.workspace_id).get()==legacy_profile()
    assert verify_resource_profiles(e)['installed'] and e.verify()['ok'];e.close()
    assert hashlib.sha256(healthy.read_bytes()).hexdigest()==before
    count=len(list(Path(f.engine.path).parent.glob('*.pre-v31-*.bak')))
    install_resource_profiles(f.engine)
    assert len(list(Path(f.engine.path).parent.glob('*.pre-v31-*.bak')))==count


def test_failed_migration_rolls_back_actual_predecessor(legacy,tmp_path):
    f=legacy()
    bad=tmp_path/'intentional-negative.sql'
    bad.write_text('CREATE TABLE must_rollback_d14(id);\nINSERT INTO absent_table VALUES(1);\n')
    with pytest.raises(sqlite3.OperationalError):_install_component(f.engine,bad,31,30,'resource_profile_interface')
    assert f.engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='must_rollback_d14'").fetchone() is None
    assert f.engine.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==30
    assert f.engine.verify()['ok'] and f.engine.validate_registry()['ok']


def test_selected_profile_backup_reopen_and_read_only_replay(make,tmp_path):
    f=make();legacy=f.profiles.get();selected=f.configure(1,'retain')
    f.configure(1,'noop-before-work')
    f.start('issued')
    f.configure(1,'noop-after-work')
    backup=tmp_path/'selected.backup.sqlite';f.engine.backup(backup)
    e=Engine(backup,read_only=True);profiles=ResourceProfiles(e,f.app.workspace_id)
    before=hashlib.sha256(backup.read_bytes()).hexdigest()
    assert profiles.get()==selected
    assert profiles.configure({'profile_id':'calibration-1000','active_jobs':1},'retain',legacy['digest'])==selected
    assert e.db.total_changes==0
    assert verify_resource_profiles(e)['profiles']==1 and e.verify()['ok'] and e.validate_registry()['ok']
    e.close();assert hashlib.sha256(backup.read_bytes()).hexdigest()==before
    e=Engine(backup)
    assert ResourceProfiles(e,f.app.workspace_id).get()==selected
    assert verify_resource_profiles(e)['profiles']==1
    assert JobQueue(e,f.app.workspace_id).claim(time.time())['profile_digest']==selected['digest']
    e.close()


def test_noop_receipt_immutability_and_terminal_activity_still_blocks_change(make):
    f=make(capacity=1);f.start('old',enqueue=False)
    f.call({'name':'activity.cancel','activity_id':'old'})
    assert f.app.store.get(f.app.workspace_id,'old')['state']=='cancelled'
    with pytest.raises(Rejected,match='before issued work'):f.configure(2,'terminal-does-not-erase-issued')
    old=dict(f.engine.db.execute('SELECT * FROM activity_resource_profiles').fetchone())
    f.configure(1,'allowed-noop')
    assert dict(f.engine.db.execute('SELECT * FROM activity_resource_profiles').fetchone())==old
    with pytest.raises(sqlite3.IntegrityError,match='immutable'):
        f.engine.db.execute('UPDATE activity_resource_profile_receipts SET request_id=? WHERE request_id=?',('altered','allowed-noop'))
    with pytest.raises(sqlite3.IntegrityError,match='immutable'):
        f.engine.db.execute('DELETE FROM activity_resource_profile_receipts WHERE request_id=?',('allowed-noop',))
    assert verify_resource_profiles(f.engine)['profiles']==1


def test_current_starting_queue_reproduces_zero_serial_starvation(make,tmp_path):
    # Exact disclosed antecedent source as negative comparison, not product authority.
    raw=ANTECEDENT_QUEUE_SOURCE.encode('utf-8')
    assert hashlib.sha256(raw).hexdigest()==ANTECEDENT_QUEUE_SHA256
    namespace={'__name__':'kageyoni.workspaces.d14a_antecedent_negative','__package__':'kageyoni.workspaces'}
    exec(compile(raw,'<disclosed D14a antecedent queue test reference>','exec'),namespace)
    f=make();f.queue=namespace['JobQueue'](f.engine,f.app.workspace_id)
    f.start('root-a',enqueue=False);f.start('a1','root-a');a2=f.start('a2','root-a')
    first=f.queue.claim(time.time());f.observe_stopped_return(first)
    observed=[]
    for i in range(8):
        new=f.start('continual-'+str(i));chosen=f.queue.claim(time.time())
        assert chosen['job_id']==new
        observed.append(chosen['job_id']);f.observe_stopped_return(chosen)
    assert f.queue.row(a2)['state']=='queued'
    (tmp_path/'antecedent-starvation.json').write_text(json.dumps({'source_sha256':hashlib.sha256(raw).hexdigest(),
        'overtaking_starts':observed,'older_job':a2,'older_state':'queued','limit':'Eight actual scheduling overtakes; no worker/model/result acceptance.'},indent=2)+'\n')


def test_false_numeric_equivalence_cannot_bypass_stored_profile_digest(make):
    f=make(capacity=1)
    row=f.engine.db.execute('SELECT * FROM activity_resource_profiles').fetchone()
    body=json.loads(row['profile_json']);body['version']=True
    # Explicit negative metadata-corruption specimen: Python True==1 must not
    # stand in for an exact canonical native digest. No history is invented.
    f.engine.db.execute('UPDATE activity_resource_profiles SET profile_json=?', (json.dumps(body),))
    with pytest.raises(Rejected,match='profile digest mismatch'):f.profiles.get()
    with pytest.raises(Rejected,match='profile digest mismatch'):verify_resource_profiles(f.engine)
