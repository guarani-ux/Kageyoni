"""Explicit audited continuation into a new directory; never upgrades the source.

Policy contains data, not import paths or executable handlers. Only installed
code executes, through the one current engine. Same-user hostile code is outside
this local trust boundary, as in Owner.
"""
from contextlib import contextmanager
import ctypes
import errno
import fcntl
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

from kageyoni.engine import Engine
from kageyoni.persistence.artifacts import Artifacts
from .protocol import Fault, digest, encoded, runtime_fingerprint

TERMINAL = {'finished', 'failed', 'cancelled'}
RECEIPT = 'samsara:continuation:v1:'


def _policy():
    raw = files('samsara').joinpath('data/compatibility-policy.json').read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(ok, code='DEPENDENCY'):
    if not ok:
        raise Fault(code)


@contextmanager
def _locked(source):
    from .owner import private_root
    root = private_root(source)
    for name in ('owner.lock', 'world.sqlite', 'workspace.json'):
        _require(not (root / name).is_symlink(), 'UNAVAILABLE')
    fd = os.open(root / 'owner.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Fault('BUSY') from None
        # Do not cause even hot-journal recovery on the supplied source.
        _require(not any((root / ('world.sqlite' + x)).exists() for x in ('-journal', '-wal', '-shm')), 'RECONCILE_REQUIRED')
        yield root
    finally:
        os.close(fd)


def _pins(engine, metadata, predecessor, *, admission=False, namespace=None):
    policy, _ = _policy()
    _require(predecessor in policy['predecessors'])
    admitted = policy['predecessors'][predecessor]
    namespace = namespace or predecessor
    _require(namespace in policy['predecessors'])
    _require(hashlib.sha256(files('samsara').joinpath('properties.py').read_bytes()).hexdigest() == admitted['properties_sha256'])
    # Authenticate actual installed native readers/writers, including namespace
    # packages and SQL stored at the distribution root. No wheel claim alone.
    from kageyoni.resources import schema_path
    for name, checksum in admitted['engine_payloads'].items():
        if name.endswith('.sql'):
            path = schema_path(name.rsplit('/',1)[-1])
        else:
            package, relative = name.split('/', 1)
            path = files(package).joinpath(relative)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != checksum:
            # One explicit audited additive native transition. Historical
            # producer hashes remain historical, not relabelled as installed.
            transition = policy.get('native_transitions', {}).get(name)
            _require(name == 'kageyoni/workspaces/documents.py' and
                     isinstance(transition, dict) and
                     set(transition) == {'from_sha256', 'to_sha256'} and
                     transition['from_sha256'] == checksum and
                     transition['to_sha256'] == actual)
    for table, expected in admitted['native_definitions'].items():
        actual_rows = [dict(r) for r in engine.db.execute('SELECT * FROM '+table)]
        _require(all(row in actual_rows for row in expected))
        if admission: _require(sorted(actual_rows, key=encoded) == sorted(expected, key=encoded))
    checks = {str(r[0]): r[1] for r in engine.db.execute('SELECT version,checksum FROM migration_checks')}
    _require(checks == admitted['migrations'])
    from kageyoni.resources import schema_path
    for version, checksum in checks.items():
        _require(hashlib.sha256(schema_path('migration_%03d.sql' % int(version)).read_bytes()).hexdigest() == checksum)
    _require(engine.verify()['ok'])
    _require(engine.validate_registry()['ok'])
    _require(not engine.db.execute('PRAGMA foreign_key_check').fetchall())
    # Native activity/grant checks compare recorded digests. Authenticate the
    # authoritative bytes too, including unrelated earlier returned artifacts.
    # Read-only inspection must not instantiate a cache-materializing store.
    for row in engine.db.execute('SELECT content,digest,size FROM artifacts'):
        blob = bytes(row['content'])
        _require(len(blob) == row['size'] and hashlib.sha256(blob).hexdigest() == row['digest'])
    # Compare both stored specs and current installed definitions to the audited
    # predecessor; handler digests are deliberately NOT declared interchangeable.
    from .content import definitions
    current = {x['id']: x for x in definitions()}
    for row in engine.db.execute('SELECT spec_json FROM activity_runs WHERE workspace_id=?', (metadata['workspace_id'],)):
        spec = json.loads(row[0]); ref = spec['definition']
        current_ref = current.get(ref['id'], {}).get('reference')
        if admission: _require(ref == admitted['definitions'].get(ref['id']))
        _require(ref == current_ref)
    from .properties import Properties, CAPACITY
    from .extensions import Extensions, EXT, SOURCE, ENDING
    class ReadOnlyArtifacts:
        def read(self, artifact_id, viewer=None):
            row=engine.db.execute('SELECT * FROM artifacts WHERE artifact_id=?',(artifact_id,)).fetchone()
            _require(row is not None)
            blob=bytes(row['content'])
            _require(hashlib.sha256(blob).hexdigest()==row['digest'] and len(blob)==row['size'])
            return {'content':blob,'digest':row['digest']}
    app = SimpleNamespace(engine=engine, db=engine.db, workspace_id=metadata['workspace_id'],
                          branch=metadata['branch'], runtime_digest=namespace,
                          property_runtime_digest=namespace,
                          services=SimpleNamespace(artifacts=ReadOnlyArtifacts()))
    app.properties = Properties(app)
    ext = Extensions(app)
    operator = SimpleNamespace(role='operator')
    for row in engine.db.execute('SELECT * FROM extension_versions WHERE workspace_id=?', (metadata['workspace_id'],)):
        manifest = json.loads(row['manifest_json'])
        _require(digest(manifest) == row['manifest_digest'])
        _require(manifest['definition'] == ext.reference(row['version']))
        _require(manifest['consumer_refs'] == [app.properties.consumer_ref()])
        _require(manifest['ending_handler'] == app.properties.ref(ENDING))
        _require(manifest['check_refs'] == [app.properties.ref('fixture:support-extension:checks')])
        if admission: _require(manifest['source'] == ext.source(operator))
        _require(manifest['property_definition_digest'] == digest(dict(engine._definition(CAPACITY, 1))))
        ext.validate_ending(row['version'])
    for row in engine.db.execute('SELECT override_json FROM property_effects WHERE workspace_id=?', (metadata['workspace_id'],)):
        value = json.loads(row[0])
        for key, name in (('source_ref','fixture:source:support'), ('predicate_ref','fixture:eligible:studio'), ('ending_handler',ENDING)):
            _require(value[key] == app.properties.ref(name))
    return admitted


def _inspect(root):
    metadata = json.loads((root / 'workspace.json').read_text())
    producer = metadata['runtime_digest']
    namespace, ancestry = _validate_metadata(engine=None, metadata=metadata, source_root=root,
                                                seen={('prospective-transition', 'reserved')})
    engine = Engine(root / 'world.sqlite', read_only=True)
    try:
        _pins(engine, metadata, producer, admission=not bool(metadata.get('compatibility_receipt')), namespace=namespace)
        db = engine.db
        _require(not db.execute("SELECT 1 FROM activity_queue WHERE state NOT IN ('returned','cancelled','failed') LIMIT 1").fetchone(), 'RECONCILE_REQUIRED')
        _require(not db.execute('SELECT 1 FROM activity_staging WHERE consumed=0 LIMIT 1').fetchone(), 'RECONCILE_REQUIRED')
        _require(not db.execute("SELECT 1 FROM activity_runs WHERE state NOT IN ('ready','waiting','paused','finished','failed','cancelled') LIMIT 1").fetchone(), 'RECONCILE_REQUIRED')
        _require(not db.execute("SELECT 1 FROM activity_jobs WHERE state NOT IN ('waiting','finished','failed','cancelled') LIMIT 1").fetchone(), 'RECONCILE_REQUIRED')
        _require(not db.execute("SELECT 1 FROM activity_jobs j LEFT JOIN activity_runs a ON a.workspace_id=j.workspace_id AND a.activity_id=j.activity_id WHERE j.state='waiting' AND (a.state NOT IN ('waiting','paused') OR json_extract(a.native_json,'$.job_id')!=j.job_id) LIMIT 1").fetchone(), 'RECONCILE_REQUIRED')
        if metadata.get('compatibility_receipt'):
            _validate_control(engine, metadata, metadata['compatibility_receipt'],
                              seen={('prospective-carry', 'reserved')})
        jobs = []
        for row in db.execute('SELECT j.*,a.spec_json,a.native_json,a.version AS run_version,a.state AS run_state FROM activity_jobs j JOIN activity_runs a ON a.workspace_id=j.workspace_id AND a.activity_id=j.activity_id ORDER BY j.job_id'):
            prepared, spec = json.loads(row['prepared_json']), json.loads(row['spec_json'])
            _require(digest(prepared) == row['prepared_digest'])
            _require(prepared['activity_id'] == row['activity_id'])
            _require(prepared['definition'] == spec['definition'])
            permitted = {producer} if row['state'] == 'waiting' else ancestry
            matched = [runtime for runtime in permitted if prepared['handler'] ==
                       {'id':'samsara:handler:'+spec['kind'],'version':1,'digest':digest([runtime,spec['kind']])}]
            _require(len(matched) == 1)
            if row['state'] == 'waiting':
                native = json.loads(row['native_json'])
                _require(native.get('job_id') == row['job_id'], 'RECONCILE_REQUIRED')
                _require(prepared['attempt_generation'] == row['generation'] == native.get('generation'))
                _require(prepared['job_version'] == row['version'])
                if row['run_state'] == 'waiting':
                    _require(prepared['activity_version'] == row['run_version'])
            jobs.append({'job_id':row['job_id'],'activity_id':row['activity_id'],
                         'generation':row['generation'],'prepared_digest':row['prepared_digest'],
                         'state':row['state'],'observed_handler_runtime':matched[0]})
        rev = db.execute('SELECT revision FROM branches WHERE id=?', (metadata['branch'],)).fetchone()[0]
        pending = [dict(r) for r in db.execute("SELECT job_id,activity_id,generation,prepared_digest FROM activity_jobs WHERE state='waiting' ORDER BY job_id")]
        _, policy_hash = _policy()
        result = {'version':2, 'source_metadata':metadata, 'metadata_sha256':_sha(root/'workspace.json'),
                  'database_sha256':_sha(root/'world.sqlite'), 'revision':rev, 'pending_jobs':pending,
                  'policy_sha256':policy_hash, 'target_runtime':runtime_fingerprint(),
                  'property_runtime_digest':namespace, 'parent_receipt':metadata.get('compatibility_receipt'),
                  'source_job_manifest':jobs}
        result['preview_digest'] = digest(result)
        return result
    finally:
        engine.close()


def preview(source):
    with _locked(source) as root:
        return _inspect(root)


def _artifact(engine, reference, workspace):
    _require(isinstance(reference, dict) and reference.get('version') == 1)
    row = engine.db.execute('SELECT * FROM artifacts WHERE artifact_id=?', (reference.get('id'),)).fetchone()
    _require(row is not None and row['workspace_id'] == workspace)
    # These are native operator transition/control receipts, not participant
    # authored JSON that happens to have a compatible shape.
    _require(row['viewer'] == 'samsara:operator' and row['media_type'] == 'application/json')
    blob = bytes(row['content'])
    _require(len(blob) == row['size'] and hashlib.sha256(blob).hexdigest() == row['digest'] == reference.get('digest'))
    return row, json.loads(blob)


def _receipt_policy(receipt, target):
    policy, checksum = _policy()
    if receipt.get('policy_sha256') == checksum:
        _require(receipt.get('version') == 2 and target == runtime_fingerprint())
        return policy
    historical = policy.get('historical_policies', {}).get(receipt.get('policy_sha256'))
    _require(historical is not None and target == historical['target_runtime'])
    raw = files('samsara').joinpath('data/' + historical['file']).read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == receipt['policy_sha256'])
    _require(receipt.get('version') == historical['receipt_version'])
    return json.loads(raw)


def _validate_control(engine, metadata, receipt_ref, *, seen=None):
    enabled = metadata.get('continuation_new_activity_admission', True)
    _require(type(enabled) is bool)
    ref = metadata.get('continuation_admission_receipt')
    if ref is None:
        _require(enabled is True)
        return
    seen = set() if seen is None else seen
    key = (ref.get('id'), ref.get('digest'))
    _require(key not in seen and len(seen) < 32)
    seen.add(key)
    row, control = _artifact(engine, ref, metadata['workspace_id'])
    _require(control.get('kind') == 'continuation_admission' and control.get('version') in (1, 2))
    _require(control.get('enabled') is enabled and control.get('compatibility_receipt') == receipt_ref)
    _require(row['request_id'] == 'samsara:continuation-admission:' + digest(control))
    if control['version'] == 1:
        _require(type(control.get('previous_enabled')) is bool)
        previous = control.get('previous_control')
        if previous is None:
            _require(control['previous_enabled'] is True)
        else:
            prior_metadata = metadata | {'continuation_new_activity_admission':control['previous_enabled'],
                                         'continuation_admission_receipt':previous}
            _validate_control(engine, prior_metadata, receipt_ref, seen=seen)
    if control['version'] == 2:
        # Carry-forward is not an enable decision. Its source state is the
        # authenticated metadata of the new transition, not a caller claim.
        _, transition = _artifact(engine, receipt_ref, metadata['workspace_id'])
        source = transition['source_metadata']
        _require(control.get('carry_forward') is True)
        _require(source.get('continuation_new_activity_admission', True) is enabled)
        _require(control.get('previous_control') == source.get('continuation_admission_receipt'))
        _require(control.get('previous_compatibility_receipt') == source.get('compatibility_receipt'))
        if source.get('compatibility_receipt'):
            _validate_control(engine, source, source['compatibility_receipt'], seen=seen)


def _chain(engine, metadata, target, *, seen=None):
    seen = set() if seen is None else seen
    ref = metadata.get('compatibility_receipt')
    producer = metadata['runtime_digest']
    _require(producer == target)
    namespace = metadata.get('property_runtime_digest', producer)
    policy, _ = _policy()
    if ref is None:
        _require(namespace == producer and producer in policy['predecessors'])
        _require(not any(k in metadata for k in ('continuation_new_activity_admission','continuation_admission_receipt')))
        return namespace, {producer}
    key = (ref.get('id'), ref.get('digest'))
    _require(key not in seen and len(seen) < 8)
    seen.add(key)
    row, receipt = _artifact(engine, ref, metadata['workspace_id'])
    admitted = _receipt_policy(receipt, target)
    _require(receipt.get('target_runtime') == target and receipt.get('property_runtime_digest') == namespace)
    source = receipt['source_metadata']
    _require(source['workspace_id'] == metadata['workspace_id'] and source['branch'] == metadata['branch'])
    _require(source['runtime_digest'] in admitted['predecessors'])
    _require(row['request_id'] == RECEIPT + receipt['preview_digest'])
    preview = {k:v for k,v in receipt.items() if k not in ('preview_digest','transition')}
    # v1 added namespace only after computing preview; v2 includes it already.
    if receipt['version'] == 1: preview.pop('property_runtime_digest', None)
    _require(digest(preview) == receipt['preview_digest'])
    if receipt['version'] == 1:
        _require(not source.get('compatibility_receipt') and not source.get('property_runtime_digest'))
        _require(source['runtime_digest'] == namespace)
    else:
        _require(receipt.get('parent_receipt') == source.get('compatibility_receipt'))
        _require(isinstance(receipt.get('source_job_manifest'), list))
    parent_namespace, ancestors = _chain(engine, source, source['runtime_digest'], seen=seen)
    _require(parent_namespace == namespace)
    # Earlier waiting results remain permanently fenced, even after a current
    # explicit resume creates another generation on the same activity.
    for old in receipt['pending_jobs']:
        job = engine.db.execute('SELECT * FROM activity_jobs WHERE job_id=?', (old['job_id'],)).fetchone()
        _require(job is not None and job['state'] == 'cancelled')
        _require(job['prepared_digest'] == old['prepared_digest'] and job['generation'] == old['generation'])
    if receipt['version'] == 2:
        observed = receipt['source_job_manifest']
        _require(len({j['job_id'] for j in observed}) == len(observed))
        for old in observed:
            job = engine.db.execute('SELECT * FROM activity_jobs WHERE job_id=?', (old['job_id'],)).fetchone()
            _require(job is not None and job['prepared_digest'] == old['prepared_digest'])
            _require(job['generation'] == old['generation'] and job['activity_id'] == old['activity_id'])
            _require(old['observed_handler_runtime'] in ancestors)
            prepared = json.loads(job['prepared_json'])
            run = engine.db.execute('SELECT spec_json FROM activity_runs WHERE workspace_id=? AND activity_id=?',
                                    (metadata['workspace_id'],job['activity_id'])).fetchone()
            spec = json.loads(run['spec_json'])
            _require(prepared['handler'] == {'id':'samsara:handler:'+spec['kind'],'version':1,
                         'digest':digest([old['observed_handler_runtime'],spec['kind']])})
            _require(job['state'] == ('cancelled' if old['state'] == 'waiting' else old['state']))
    _validate_control(engine, metadata, ref)
    # Each link's actual semantic pins are checked without treating old
    # source visibility as permission to admit a new dependency now.
    _pins(engine, source, source['runtime_digest'], namespace=namespace)
    return namespace, ancestors | {producer}


def _validate_metadata(engine, metadata, *, source_root=None, seen=None):
    if engine is None:
        engine = Engine(source_root / 'world.sqlite', read_only=True)
        try: return _chain(engine, metadata, metadata['runtime_digest'], seen=seen)
        finally: engine.close()
    return _chain(engine, metadata, metadata['runtime_digest'], seen=seen)


def validate_continuation(engine, metadata):
    """Authenticate immutable bounded ancestry; return semantic namespace."""
    actual = runtime_fingerprint()
    _require(metadata.get('runtime_digest') == actual)
    if metadata.get('compatibility_receipt') is None:
        _require(metadata.get('property_runtime_digest', actual) == actual)
        _require(not any(k in metadata for k in ('continuation_new_activity_admission','continuation_admission_receipt')))
        return actual
    namespace, _ = _validate_metadata(engine, metadata)
    return namespace


def _publish(stage, destination):
    # Linux renameat2(RENAME_NOREPLACE) gives directory publication a real
    # no-replacement atomic boundary. A check-then-os.rename is insufficient.
    libc = ctypes.CDLL(None, use_errno=True)
    fn = getattr(libc, 'renameat2', None)
    _require(fn is not None, 'UNSUPPORTED')
    result = fn(-100, os.fsencode(stage), -100, os.fsencode(destination), 1)
    if result:
        err = ctypes.get_errno()
        if err == errno.EEXIST:
            raise Fault('CONFLICT')
        if err in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
            raise Fault('UNSUPPORTED')
        raise OSError(err, os.strerror(err))


def _flush(root):
    for path in root.rglob('*'):
        _require(not path.is_symlink(), 'UNAVAILABLE')
        if path.is_file():
            fd = os.open(path, os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def continue_copy(source, destination, expected_preview, *, seam=None):
    """Publish one verified continuation. seam(name,stage) is a test hook."""
    from .owner import private_root
    destination = Path(destination).absolute()
    _require(destination.parent.is_dir() and not destination.parent.is_symlink(), 'UNAVAILABLE')
    _require(not any(p.is_symlink() for p in destination.parents), 'UNAVAILABLE')
    _require(len(str(destination/'control.sock').encode()) <= 104, 'BUDGET')
    _require(not destination.is_symlink(), 'UNAVAILABLE')
    with _locked(source) as root:
        _require(destination != root and root not in destination.parents, 'CONFLICT')
        if destination.exists():
            with _locked(destination):
                metadata = json.loads((destination/'workspace.json').read_text())
                engine = Engine(destination/'world.sqlite', read_only=True)
                try:
                    validate_continuation(engine, metadata)
                    row = engine.db.execute('SELECT content FROM artifacts WHERE artifact_id=?', (metadata['compatibility_receipt']['id'],)).fetchone()
                    receipt = json.loads(bytes(row[0]))
                    _require(receipt['preview_digest'] == expected_preview, 'CONFLICT')
                    return {'destination':str(destination),'receipt':metadata['compatibility_receipt'],'replayed':True}
                finally: engine.close()
        inspected = _inspect(root)
        _require(inspected['preview_digest'] == expected_preview, 'STALE')
        stage = destination.parent / ('.' + destination.name + '.continuation-' + uuid4().hex)
        stage.mkdir(mode=0o700)
        (stage/'continuation-stage.json').write_text(encoded({'preview_digest':expected_preview,'destination':str(destination),'status':'IN_PROGRESS'})+'\n')
        if seam: seam('stage_created', stage)
        # Native SQLite backup; historical BLOBs are authoritative and native
        # artifact materialization recovers their content-addressed files.
        old = sqlite3.connect((root/'world.sqlite').as_uri()+'?mode=ro', uri=True)
        new = sqlite3.connect(stage/'world.sqlite')
        try: old.backup(new)
        finally: old.close(); new.close()
        if seam: seam('backed_up', stage)
        engine = Engine(stage/'world.sqlite')
        try:
            with engine.transaction():
                for pending in inspected['pending_jobs']:
                    row = engine.db.execute('SELECT * FROM activity_runs WHERE workspace_id=? AND activity_id=?', (inspected['source_metadata']['workspace_id'],pending['activity_id'])).fetchone()
                    cp = json.loads(row['checkpoint_json'])
                    cp.update(state='paused',activity_version=row['version']+1,
                              next={'actor':'operator','operation':'activity.resume','condition':'Explicitly prepare a new current handler generation; old issued result remains fenced.'})
                    engine.db.execute('UPDATE activity_runs SET state=?,version=?,checkpoint_json=? WHERE workspace_id=? AND activity_id=?', ('paused',row['version']+1,encoded(cp),row['workspace_id'],row['activity_id']))
                    engine.db.execute("UPDATE activity_jobs SET state='cancelled',version=version+1 WHERE job_id=? AND state='waiting'", (pending['job_id'],))
                engine.db.execute("UPDATE activity_bindings SET active=0,authority_epoch=authority_epoch+1 WHERE role='worker' AND active=1")
                receipt = inspected | {
                    'transition':'Fence old waiting manual jobs, pause activities, revoke workers; preserve historical/native state. No fictional event or cost refund.'}
                artifact = Artifacts(engine).put(encoded(receipt),'application/json',RECEIPT+expected_preview,
                    workspace_id=inspected['source_metadata']['workspace_id'],recipient='samsara:operator')
                reference = {'id':artifact['artifact_id'],'version':1,'digest':artifact['digest']}
                source_metadata = inspected['source_metadata']
                enabled = source_metadata.get('continuation_new_activity_admission', True)
                control_reference = None
                if source_metadata.get('compatibility_receipt'):
                    control = {'version':2,'kind':'continuation_admission','enabled':enabled,
                               'carry_forward':True,'compatibility_receipt':reference,
                               'previous_control':source_metadata.get('continuation_admission_receipt'),
                               'previous_compatibility_receipt':source_metadata['compatibility_receipt']}
                    control_artifact = Artifacts(engine).put(encoded(control),'application/json',
                        'samsara:continuation-admission:'+digest(control),
                        workspace_id=source_metadata['workspace_id'],recipient='samsara:operator')
                    control_reference = {'id':control_artifact['artifact_id'],'version':1,'digest':control_artifact['digest']}
            metadata = inspected['source_metadata'] | {'runtime_digest':runtime_fingerprint(),
                'property_runtime_digest':inspected['property_runtime_digest'],'compatibility_receipt':reference,
                'continuation_new_activity_admission':enabled}
            metadata.pop('continuation_admission_receipt', None)
            if control_reference: metadata['continuation_admission_receipt'] = control_reference
            (stage/'workspace.json').write_text(encoded(metadata)+'\n')
            validate_continuation(engine, metadata)
            _require(_sha(root/'world.sqlite') == inspected['database_sha256'], 'STALE')
            (stage/'continuation-stage.json').write_text(encoded({'preview_digest':expected_preview,'destination':str(destination),'status':'COMPLETE','receipt':reference})+'\n')
        finally:
            engine.close()
        if seam: seam('transition_committed', stage)
        _flush(stage)
        if seam: seam('before_publish', stage)
        _publish(stage,destination)
        fd=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
        if seam: seam('published', destination)
        return {'destination':str(destination),'receipt':reference,'replayed':False}


def set_admission(workspace, enabled):
    """Operator host control: stop new admissions, retain existing continuations.

    Validate and reserve bounded history while the DB is still read-only. Even
    constructing a writable Owner can update native registration bookkeeping;
    a refused control must not perform that effect first.
    """
    _require(type(enabled) is bool, 'INVALID')
    with _locked(workspace) as root:
        path = root / 'workspace.json'
        metadata = json.loads(path.read_text())
        _require(metadata.get('compatibility_receipt') is not None, 'UNSUPPORTED')
        engine = Engine(root / 'world.sqlite', read_only=True)
        try:
            validate_continuation(engine, metadata)
            old = metadata.get('continuation_new_activity_admission', True)
            control = {'version':1,'kind':'continuation_admission','enabled':enabled,
                'previous_enabled':old,'compatibility_receipt':metadata['compatibility_receipt'],
                'previous_control':metadata.get('continuation_admission_receipt'),
                'scope':'New activity admission only; existing activities, history and endings remain callable.'}
            # A repeated identical control is a read, not a duplicate effect.
            if old == enabled and metadata.get('continuation_admission_receipt'):
                return {'enabled':enabled,'receipt':metadata['continuation_admission_receipt'],'replayed':True}
            if metadata.get('continuation_admission_receipt'):
                _validate_control(engine, metadata, metadata['compatibility_receipt'],
                                  seen={('prospective-toggle', 'reserved')})
        finally:
            engine.close()
        # The same lifetime lock spans read-only preflight through publication.
        engine = Engine(root / 'world.sqlite')
        try:
            artifact = Artifacts(engine).put(encoded(control),'application/json',
                'samsara:continuation-admission:'+digest(control),
                workspace_id=metadata['workspace_id'],recipient='samsara:operator')
            ref = {'id':artifact['artifact_id'],'version':1,'digest':artifact['digest']}
            metadata.update(continuation_new_activity_admission=enabled,continuation_admission_receipt=ref)
            validate_continuation(engine, metadata)
            temporary = root / ('.workspace-'+uuid4().hex)
            try:
                with temporary.open('x') as stream:
                    stream.write(encoded(metadata)+'\n');stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,path)
                fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
                try: os.fsync(fd)
                finally: os.close(fd)
            finally:
                if temporary.exists(): temporary.unlink()
            return {'enabled':enabled,'receipt':ref,'replayed':False}
        finally:
            engine.close()
