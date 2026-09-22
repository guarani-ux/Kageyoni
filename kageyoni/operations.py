"""Portable daily operation and evaluated, scoped artifact-check ordering.

No model provider or network connection is configured by this module.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import sqlite3
from functools import wraps
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from .engine import Engine, digest, encoded, require
from .persistence.unit_of_work import UnitOfWork

CHECKS = ['utf8', 'size', 'sha256']
DEFAULTS = {'max_artifact_bytes': 10485760, 'max_checks': 300, 'host_available': False}

def _hash(data): return hashlib.sha256(data).hexdigest()

def _check(content, maximum, expected, order):
    require(isinstance(content, bytes), 'artifact must be bytes')
    require(type(maximum) is int and maximum >= 0, 'invalid size limit')
    require(isinstance(expected, str) and len(expected) == 64, 'invalid expected digest')
    count = 0
    for check in order:
        count += 1
        if check == 'utf8':
            try: content.decode('utf-8'); okay = True
            except UnicodeDecodeError: okay = False
        elif check == 'size': okay = len(content) <= maximum
        else: okay = _hash(content) == expected
        if not okay: return {'accepted': False, 'checks': count}
    return {'accepted': True, 'checks': count}

def _external_dependencies(db):
    """Describe saved external paths without opening, copying or authorizing them."""
    dependencies=[]
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='repository_candidates'").fetchone():
        for row in db.execute('SELECT payload_json FROM repository_candidates ORDER BY candidate_id'):
            candidate=json.loads(row[0]); request=candidate['request']
            dependencies.append({'service':'repository','id':candidate['candidate_id'],'branch':candidate['branch'],'phase':candidate['phase'],
                                 'paths':{**{key:request[key] for key in ('source_dir','workspace_dir')},**({'destination':candidate['destination']} if candidate.get('destination') else {})},
                                 'candidate_digest':candidate.get('candidate_digest'),'recovery':'external trees not bundled; validate relocated copies and explicitly rebind'})
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='pipeline_runs'").fetchone():
        for row in db.execute('SELECT payload_json FROM pipeline_runs ORDER BY pipeline_id'):
            pipeline=json.loads(row[0])
            for task_id,task in sorted(pipeline['tasks'].items()):
                if task['kind']=='write_file':
                    config=task.get('resolved_config',task['config'])
                    dependencies.append({'service':'pipelines','id':pipeline['pipeline_id'],'task_id':task_id,'branch':pipeline['branch'],'phase':task['phase'],
                                         'paths':{'root':config['root'],'relative_path':config['path']},'expected_sha256':config['expected_sha256'],
                                         'recovery':'external effects not bundled; explicitly rebind root and reconcile recorded effects'})
    return dependencies

def _atomic(function):
    @wraps(function)
    def call(self, *args, **kwargs):
        with UnitOfWork(self.engine.db):return function(self, *args, **kwargs)
    return call

class Operations:
    def __init__(self, engine, artifact_root=None):
        self.engine = engine
        self.artifact_root = Path(engine.path).with_suffix('.artifacts')
        require(artifact_root is None or Path(artifact_root).resolve()==self.artifact_root.resolve(),'artifact root must match the database content store')
        require(engine.db.execute("SELECT 1 FROM engine_versions WHERE component='operations_interface' AND version='1'").fetchone(), 'operations interface not installed')

    def _events(self, kind=None, scope=None):
        rows = self.engine.db.execute('SELECT * FROM operation_events ORDER BY seq').fetchall()
        return [dict(event_id=r['event_id'], kind=r['kind'], scope=r['scope'], **json.loads(r['payload_json'])) for r in rows if (kind is None or r['kind']==kind) and (scope is None or r['scope']==scope)]

    def _append(self, kind, scope, payload):
        event_id = 'operation:'+uuid.uuid4().hex
        with UnitOfWork(self.engine.db):
            self.engine.db.execute('INSERT INTO operation_events(event_id,kind,scope,payload_json,digest) VALUES(?,?,?,?,?)', (event_id, kind, scope, encoded(payload), digest([event_id,kind,scope,payload])))
        return dict(event_id=event_id, kind=kind, scope=scope, **payload)

    @_atomic
    def settings(self, values=None):
        current = dict(DEFAULTS)
        for row in self._events('settings'): current.update(row['values'])
        if values is not None:
            require(type(values) is dict and set(values)<=set(DEFAULTS), 'unknown settings')
            for key,value in values.items():
                if key=='host_available': require(type(value) is bool, 'host availability must be boolean')
                else: require(type(value) is int and 1<=value<=100000000, 'invalid budget')
            self._append('settings','local',{'values':values}); current.update(values)
        return current

    def status(self):
        settings=self.settings()
        return {'versions':dict(self.engine.db.execute('SELECT component,version FROM engine_versions')),
                'branches':[dict(r) for r in self.engine.db.execute('SELECT * FROM branches')],
                'settings':settings,'model_api':'none','host': 'manual handoff' if not settings['host_available'] else 'authorized host supplied externally',
                'next_actions':['inspect saved state','continue a saved workflow','export portable bundle'],
                'policies':self._events('activation'), 'operation_count':len(self._events())}

    @_atomic
    def propose_policy(self, scope, parameters, rationale):
        require(isinstance(scope,str) and 0<len(scope)<=200,'exact policy scope required')
        require(type(parameters) is dict and set(parameters)=={'check_order'} and type(parameters['check_order']) is list and sorted(parameters['check_order'])==sorted(CHECKS),'policy must preserve every check exactly once')
        require(isinstance(rationale,str) and rationale.strip(),'policy rationale required')
        return self._append('proposal',scope,{'parameters':parameters,'rationale':rationale})

    def _find(self, kind, event_id):
        rows=[x for x in self._events(kind) if x['event_id']==event_id]
        require(len(rows)==1,'operation record unavailable'); return rows[0]

    def _active(self, scope):
        history=self._events('activation',scope)
        return history[-1]['policy_id'] if history else None

    def _order(self, policy_id):
        return self._find('proposal',policy_id)['parameters']['check_order'] if policy_id else CHECKS

    @_atomic
    def trial_policy(self, policy_id, cases):
        proposal=self._find('proposal',policy_id)
        require(type(cases) is list and 2<=len(cases)<=100,'trial needs 2 to 100 actual artifact cases')
        baseline=self._active(proposal['scope']); records=[]; total_bytes=0
        require(len(cases)*6<=self.settings()['max_checks'],'trial exceeds check budget')
        for case in cases:
            require(type(case) is dict and set(case)=={'content_base64','max_bytes','expected_sha256'},'invalid artifact trial case')
            try: content=base64.b64decode(case['content_base64'],validate=True)
            except Exception: raise ValueError('invalid base64 artifact')
            total_bytes+=len(content)
            require(total_bytes<=self.settings()['max_artifact_bytes'],'trial artifact corpus exceeds budget')
            before=_check(content,case['max_bytes'],case['expected_sha256'],self._order(baseline))
            after=_check(content,case['max_bytes'],case['expected_sha256'],self._order(policy_id))
            records.append({'case':case,'baseline':before,'candidate':after})
        equal=all(r['baseline']['accepted']==r['candidate']['accepted'] for r in records)
        coverage={r['baseline']['accepted'] for r in records}=={True,False}
        before=sum(r['baseline']['checks'] for r in records); after=sum(r['candidate']['checks'] for r in records)
        return self._append('trial',proposal['scope'],{'policy_id':policy_id,'baseline_policy_id':baseline,'cases':records,'baseline_checks':before,'candidate_checks':after,'supported':equal and coverage and after<before,'limit':'Operator-selected cases support only this exact artifact-check scope; practical task benefit is unmeasured.'})

    @_atomic
    def activate_policy(self, policy_id, trial_id):
        proposal=self._find('proposal',policy_id); trial=self._find('trial',trial_id)
        require(trial['policy_id']==policy_id and trial['supported'],'policy lacks supporting comparison trial')
        require(trial['baseline_policy_id']==self._active(proposal['scope']),'trial baseline changed')
        return self._append('activation',proposal['scope'],{'policy_id':policy_id,'previous_policy_id':self._active(proposal['scope']),'trial_id':trial_id,'action':'activate'})

    @_atomic
    def rollback_policy(self, scope, activation_id):
        old=self._find('activation',activation_id)
        require(old['scope']==scope and self._events('activation',scope)[-1]['event_id']==activation_id,'rollback must target current activation')
        return self._append('activation',scope,{'policy_id':old['previous_policy_id'],'previous_policy_id':old['policy_id'],'trial_id':old['trial_id'],'action':'rollback'})

    @_atomic
    def check_artifact(self, scope, content, max_bytes, expected_sha256):
        settings=self.settings(); policy_id=self._active(scope); start=time.monotonic()
        if len(content)>settings['max_artifact_bytes'] or settings['max_checks']<3:
            result={'accepted':False,'checks':0,'disposition':'blocked','reason':'artifact check budget exhausted'}
        else:
            result=_check(content,max_bytes,expected_sha256,self._order(policy_id)); result['disposition']='completed' if result['accepted'] else 'failed'
        return self._append('artifact_check',scope,{'policy_id':policy_id,'artifact_digest':_hash(content),'bytes':len(content),'elapsed_seconds':time.monotonic()-start,**result})

    def export_bundle(self, path):
        target=Path(path); require(not target.exists() and not target.is_symlink(),'bundle destination already exists')
        require(not self.engine.db.in_transaction,'finish transaction before export')
        require(self.engine.verify()['ok'],'database verification failed')
        if self.engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='artifacts'").fetchone():
            from .persistence.artifacts import Artifacts
            store=Artifacts(self.engine)
            store.verify()
            for item in store.manifest():
                require((store.root/item['relative_path']).is_file(),'referenced artifact missing; recover before export')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); database=root/'engine.sqlite'; self.engine.backup(database)
            files={'engine.sqlite':database.read_bytes()}
            snapshot=sqlite3.connect(database)
            try:
                revisions=dict(snapshot.execute('SELECT id,revision FROM branches'))
                external_dependencies=_external_dependencies(snapshot)
                if snapshot.execute("SELECT 1 FROM sqlite_master WHERE name='artifacts'").fetchone():
                    require(not self.artifact_root.is_symlink() and not (self.artifact_root/'objects').is_symlink(),'artifact root unsafe')
                    for sha,size in snapshot.execute('SELECT digest,size FROM artifacts'):
                        source=self.artifact_root/'objects'/sha
                        require(source.is_file() and not source.is_symlink(),'referenced artifact missing or unsafe')
                        data=source.read_bytes();require(_hash(data)==sha and len(data)==size,'referenced artifact corrupt')
                        files['engine.artifacts/objects/'+sha]=data
            finally:snapshot.close()
            manifest={'format':'kageyoni-portable-1','files':{name:_hash(data) for name,data in files.items()},'world_revisions':revisions,'external_dependencies':external_dependencies}
            target.parent.mkdir(parents=True,exist_ok=True)
            created=False
            try:
                archive=zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED); created=True
                with archive:
                    for name,data in files.items(): archive.writestr(name,data)
                    archive.writestr('manifest.json',encoded(manifest))
            except Exception:
                if created:target.unlink(missing_ok=True)
                raise
        return {'path':str(target),'sha256':_hash(target.read_bytes()),'files':len(files),'world_revisions':manifest['world_revisions'],'external_dependencies':external_dependencies,'external_state':'not included; explicit rebind required' if external_dependencies else 'none'}

    @staticmethod
    def import_bundle(bundle, destination):
        target=Path(destination); require(not target.exists(),'destination exists; newer saves are never replaced')
        target.parent.mkdir(parents=True,exist_ok=True)
        staging=Path(tempfile.mkdtemp(prefix='.kageyoni-import-',dir=target.parent))
        try:
            with zipfile.ZipFile(bundle) as archive:
                entries=archive.infolist(); names=[x.filename for x in entries]
                require(len(names)==len(set(names)) and 'manifest.json' in names,'duplicate or missing bundle members')
                require(sum(x.file_size for x in entries)<=256*1024*1024,'bundle exceeds import limit')
                for entry in entries:
                    p=PurePosixPath(entry.filename)
                    require(not p.is_absolute() and '..' not in p.parts and '\\' not in entry.filename and ':' not in entry.filename and p.as_posix()==entry.filename and not entry.is_dir(),'unsafe bundle path')
                    require((entry.external_attr>>16)&0o170000 != 0o120000,'bundle symlink rejected')
                manifest=json.loads(archive.read('manifest.json'))
                require(manifest['format']=='kageyoni-portable-1' and set(names)==set(manifest['files'])|{'manifest.json'} and 'engine.sqlite' in manifest['files'],'bundle manifest mismatch')
                for name,expected in manifest['files'].items():
                    data=archive.read(name); require(_hash(data)==expected,'bundle checksum mismatch')
                    output=staging/name; output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(data)
            engine=Engine(staging/'engine.sqlite')
            try:
                if engine.db.execute("SELECT 1 FROM sqlite_master WHERE name='artifacts'").fetchone():
                    from .persistence.artifacts import Artifacts
                    store=Artifacts(engine)
                    for item in store.manifest():
                        require((store.root/item['relative_path']).is_file(),'bundle lacks referenced artifact')
                    store.verify()
                require(engine.verify()['ok'],'imported database verification failed')
                external_dependencies=_external_dependencies(engine.db)
                require(external_dependencies==manifest.get('external_dependencies',[]),'external dependency manifest mismatch')
                require({r['id']:r['revision'] for r in engine.db.execute('SELECT id,revision FROM branches')}==manifest['world_revisions'],'world revision manifest mismatch')
            finally: engine.close()
            require(not target.exists(),'destination appeared during import'); os.rename(staging,target)
            return {'path':str(target/'engine.sqlite'),'artifacts':str(target/'engine.artifacts'),'verified':True,'external_dependencies':external_dependencies,'external_state':'unresolved; explicit rebind required' if external_dependencies else 'none'}
        except Exception:
            shutil.rmtree(staging,ignore_errors=True); raise

    @staticmethod
    def migrate_copy(source, destination):
        import sqlite3
        target=Path(destination); require(not target.exists(),'migration destination exists')
        target.parent.mkdir(parents=True,exist_ok=True)
        source_db=sqlite3.connect('file:'+str(Path(source).resolve())+'?mode=ro',uri=True)
        try:
            output=sqlite3.connect(target)
            try: source_db.backup(output)
            finally: output.close()
        finally: source_db.close()
        engine=Engine(target)
        try:
            from .persistence.migrations import install_all
            install_all(engine); require(engine.verify()['ok'],'migrated copy verification failed')
        finally: engine.close()
        return {'path':str(target),'source_preserved':True}

def verify_operations(engine):
    from .resources import schema_path
    migration=schema_path('migration_017.sql')
    row=engine.db.execute('SELECT checksum FROM migration_checks WHERE version=17').fetchone()
    require(row and row[0]==_hash(migration.read_bytes()),'operations migration checksum mismatch')
    require(engine.db.execute("SELECT version FROM engine_versions WHERE component='operations_interface'").fetchone()[0]=='1','unsupported operations interface')
    rows=engine.db.execute('SELECT * FROM operation_events ORDER BY seq').fetchall()
    proposals={}
    trials={}
    active={}
    activations={}
    for row in rows:
        payload=json.loads(row['payload_json'])
        require(row['digest']==digest([row['event_id'],row['kind'],row['scope'],payload]),'operation history digest mismatch')
        kind=row['kind']; scope=row['scope']
        if kind=='proposal':
            require(sorted(payload['parameters']['check_order'])==sorted(CHECKS),'invalid policy checks')
            proposals[row['event_id']]=(scope,payload['parameters']['check_order'])
        elif kind=='trial':
            policy=payload['policy_id']; baseline=payload['baseline_policy_id']
            require(policy in proposals and proposals[policy][0]==scope,'trial policy unavailable')
            require(baseline==active.get(scope),'trial baseline ancestry mismatch')
            expected=[]
            for record in payload['cases']:
                case=record['case']; content=base64.b64decode(case['content_base64'],validate=True)
                before=_check(content,case['max_bytes'],case['expected_sha256'],proposals[baseline][1] if baseline else CHECKS)
                after=_check(content,case['max_bytes'],case['expected_sha256'],proposals[policy][1])
                require(record['baseline']==before and record['candidate']==after,'trial result mismatch')
                expected.append((before,after))
            before=sum(a['checks'] for a,b in expected); after=sum(b['checks'] for a,b in expected)
            supported=all(a['accepted']==b['accepted'] for a,b in expected) and {a['accepted'] for a,b in expected}=={True,False} and after<before
            require(payload['baseline_checks']==before and payload['candidate_checks']==after and payload['supported']==supported,'trial comparison mismatch')
            trials[row['event_id']]=payload
        elif kind=='activation':
            require(payload['previous_policy_id']==active.get(scope),'activation ancestry mismatch')
            trial=trials.get(payload['trial_id'])
            require(trial and trial['supported'],'activation missing evaluated trial')
            if payload['action']=='activate':
                require(payload['policy_id']==trial['policy_id'] and trial['baseline_policy_id']==active.get(scope),'activation trial mismatch')
            else:
                require(payload['action']=='rollback','unknown activation action')
                prior=activations.get(scope)
                require(prior and payload['policy_id']==prior['previous_policy_id'] and payload['trial_id']==prior['trial_id'],'rollback ancestry mismatch')
            active[scope]=payload['policy_id']
            activations[scope]=payload
        elif kind=='artifact_check':
            require(payload['policy_id']==active.get(scope),'artifact policy ancestry mismatch')
    return {'ok':True,'events':len(rows)}
