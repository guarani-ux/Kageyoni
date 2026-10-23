"""Optional direct-source service proposal; not yet built or API-qualified.

One native typed history is authoritative. No second permission ledger,
implicit installation, legacy adoption, derivation, regrant or physical recall.
"""
from copy import deepcopy
import hashlib
from ..engine import Rejected, require
from ..persistence.unit_of_work import UnitOfWork
from .source_authority_schema import PROFILE, SourceAuthorityError, _identifier, validate_creation
from .source_authority_installation import DOMAINS, REQUIRED, installation_state
from .source_authority_history import collect_source_authority_metadata, resolve_source, resolve_artifact
from .source_authority_operations import canonical, digest, command_for, source_metadata_hash
from .source_authority_scope import _authorized_host_scope, _current, _arm_command


class SourceAuthorityUnavailable(Rejected):
    pass


class SourceAuthorityWithdrawn(SourceAuthorityUnavailable):
    pass


class SourceAuthorityDependency(Rejected):
    pass


def _metadata(engine, *, allow_pristine=True):
    try:
        return collect_source_authority_metadata(engine, allow_pristine=allow_pristine)
    except (ValueError, RuntimeError) as error:
        raise SourceAuthorityUnavailable('source authority metadata unavailable') from error


def reject_subscriptions(engine, branch):
    """Actual Engine.apply matching semantics, never suppress subscriptions."""
    rows = engine.db.execute(
        'SELECT p.id FROM processes p JOIN process_subscriptions s '
        'ON s.branch=p.branch AND s.process_id=p.id '
        "WHERE p.branch=? AND p.state='active' AND s.event_kind='maintenance'",
        (branch,)).fetchall()
    if rows:
        raise SourceAuthorityDependency('source operation with active maintenance subscriptions unsupported')


def guard_source(engine, workspace_id, source_id):
    try:
        item = resolve_source(engine, workspace_id, source_id)
        if item is not None and item['image']['phase'] != 'active':
            raise SourceAuthorityWithdrawn('source unavailable')
        return item
    except (SourceAuthorityError, RuntimeError) as error:
        raise SourceAuthorityUnavailable('source unavailable') from error


def guard_artifact(engine, artifact_id):
    try:
        item = resolve_artifact(engine, artifact_id)
        if item is not None and item['image']['phase'] != 'active':
            raise SourceAuthorityWithdrawn('artifact unavailable')
        return item
    except (SourceAuthorityError, RuntimeError) as error:
        raise SourceAuthorityUnavailable('artifact unavailable') from error


def guard_ingest(engine, workspace_id, source_id):
    # Registry authorization belongs before this diagnostic at the caller.
    try:
        item = resolve_source(engine, workspace_id, source_id)
    except (SourceAuthorityError, RuntimeError) as error:
        raise SourceAuthorityUnavailable('source unavailable') from error
    if item is not None:
        raise SourceAuthorityDependency('controlled source append/reingest unsupported')


def refuse_unsupported_derivation(engine, workspace_id, values):
    """No controlled cached/derived bodies until immutable lineage exists.

    While this first profile has no derivation producer, *any* controlled
    family in this workspace blocks unsupported document interpretation paths.
    This conservative refusal includes empty/tampered mutable source_refs;
    it does not infer lineage from content or silently authorize a copied row.
    Uncontrolled workspace behavior stays on its existing path.
    """
    resolved = _metadata(engine)
    if any(wid == workspace_id for wid, sid in resolved['families']):
        raise SourceAuthorityDependency('controlled workspace derivation requires immutable complete lineage')


def verify_source_authorities(engine, *, allow_pristine=True):
    """Trusted maintenance body verification, no consuming-viewer exemption.

    Does not materialize files or return bytes. Ordinary guards never call
    this BLOB path merely to decide availability.
    """
    with UnitOfWork(engine.db):
        resolved = _metadata(engine, allow_pristine=allow_pristine)
        for item in resolved['families'].values():
            expected = item['artifact']
            row = engine.db.execute('SELECT artifact_id,workspace_id,viewer,request_id,payload_hash,digest,media_type,size,content '
                                    'FROM artifacts WHERE artifact_id=?', (expected['artifact_id'],)).fetchone()
            require(row is not None and all(row[key] == expected[key] for key in expected), 'controlled artifact metadata changed during verification')
            blob = bytes(row['content'])
            require(len(blob) == expected['size'] and hashlib.sha256(blob).hexdigest() == expected['digest'], 'controlled artifact body corrupt')
        return {'installed': resolved['installed'], 'state': resolved['state'],
                'families': len(resolved['families']),
                'withdrawn': sum(item['image']['phase'] == 'withdrawn' for item in resolved['families'].values())}


def _summary(item, receipt, operation):
    # Metadata/historical fact only. Current body access is a separate read.
    return {'profile': PROFILE, 'source_id': item['creation']['source_id'],
            'source_reference': deepcopy(item['creation']['source_pin']),
            'artifact_reference': deepcopy(item['creation']['artifact_pin']),
            'authority_reference': {'id': item['record']['id'], 'version': 1 if operation == 'capture' else 2},
            'native_receipt': deepcopy(receipt),
            'limit': 'Selected-world source fact; current byte availability requires a fresh authorized read. No recall of delivered bytes.'}


class SourceAuthorities:
    def __init__(self, engine):
        self.engine, self.db = engine, engine.db

    def _ready(self, app):
        from .registry import Registry
        # Actual operator binding was checked by the fixed host scope first.
        Registry(self.engine).read(app.workspace_id, viewer=None)
        resolved = _metadata(self.engine)
        if not resolved['installed']:
            raise SourceAuthorityDependency('source authority interface requires explicit checked installation')
        return resolved

    def _finalize(self, operation):
        command = command_for(operation)
        old = self.db.execute('SELECT payload_hash FROM events WHERE branch=? AND request_id=?',
                              (command['branch'],command['request_id'])).fetchone()
        if old is None:
            reject_subscriptions(self.engine, command['branch'])
        else:
            require(old[0] == digest(command), 'source native request conflict')
        _arm_command(self.engine, command)
        receipt = self.engine.apply(command)
        resolved = _metadata(self.engine)
        creation = operation['creation']
        item = resolved['families'].get((creation['workspace_id'], creation['source_id']))
        require(item is not None and item['creation'] == creation, 'controlled source finalizer correspondence missing')
        return _summary(item, receipt, operation['operation'])

    def _capture_host(self, app, context, unit, request):
        # Only this fixed bridge may use the private insertion/finalizer pair.
        from .documents import Documents
        from samsara.source_authority_host import _authorize_current
        _authorize_current(app, context, request, unit)
        detached = deepcopy(request)
        op = detached['operation']
        _identifier(op['source_id'], 'source'); _identifier(op['recipient'], 'recipient')
        with _authorized_host_scope(app, context, unit, detached, workspace_id=app.workspace_id,
                                    source_id=op['source_id'], recipient=op['recipient']):
            scope = _current(self.engine)
            # All content comes from the detached command actually in scope.
            op = deepcopy(scope.request['operation'])
            docs = Documents(self.engine)
            document_request = 'source-capture:' + digest({'binding': context.binding_id, 'request': scope.request})
            args = dict(workspace_id=app.workspace_id, request_id=document_request,
                        source_id=op['source_id'], text=op['text'], identity=op['identity'],
                        expected_identity=op['expected_identity'], captured_at=op['captured_at'],
                        expires_at=op.get('expires_at'), viewer=None,
                        locator=op.get('locator', 'subscription-host supplied'), recipient=op['recipient'])
            payload = docs._validated_ingest_payload(**args)
            resolved = self._ready(app)
            old = resolved['families'].get((app.workspace_id, op['source_id']))
            if old is not None:
                require(old['creation']['controller_principal'] == context.principal_id
                        and old['creation']['recipient'] == op['recipient']
                        and old['source']['payload_hash'] == digest(payload)
                        and old['source']['request_id'] == document_request,
                        'controlled capture request conflict')
                operation = dict(profile=PROFILE, operation='capture', request_id=scope.request['request_id'],
                                 expected_revision=scope.request['expected_revision'], creation=old['creation'])
                return self._finalize(operation)  # exact accepted history; never source()/regrant
            require(not self.db.execute('SELECT 1 FROM document_sources WHERE workspace_id=? AND source_id=?',
                                       (app.workspace_id,op['source_id'])).fetchone(), 'controlled capture cannot adopt legacy source')
            require(not self.db.execute('SELECT 1 FROM document_sources WHERE request_id=?', (document_request,)).fetchone(), 'controlled source request already exists')
            require(app.content_sets.actor_admitted(op['recipient'])
                    and op['recipient'] in {row['id'] for row in self.engine.context(app.branch,viewer=op['recipient'])['records']},
                    'controlled recipient not admitted/permitted')
            reject_subscriptions(self.engine, app.branch)  # before Artifacts.put
            from samsara.source_authority_host import _capture_capacity
            _capture_capacity(app,context,scope.request,unit)
            inserted = docs._insert_source_row(app.workspace_id,document_request,op['source_id'],1,
                                              op['text'],op['identity'],op['expected_identity'],op['captured_at'],
                                              op.get('expires_at'),None,op.get('locator','subscription-host supplied'),
                                              op['recipient'],digest(payload))
            row = self.db.execute('SELECT workspace_id,source_id,revision,request_id,payload_hash,artifact_id,metadata_json '
                                  'FROM document_sources WHERE workspace_id=? AND source_id=? AND revision=1',
                                  (app.workspace_id,op['source_id'])).fetchone()
            artifact = inserted['artifact']
            creation = validate_creation(dict(profile=PROFILE,branch=app.branch,workspace_id=app.workspace_id,
                source_id=op['source_id'],controller_principal=context.principal_id,recipient=op['recipient'],
                source_payload_hash=row['payload_hash'],source_metadata_hash=source_metadata_hash(dict(row)),
                source_pin={'id':op['source_id'],'version':1,'digest':artifact['digest']},
                artifact_pin={'id':artifact['artifact_id'],'version':1,'digest':artifact['digest']},phase='active',revision=1))
            return self._finalize(dict(profile=PROFILE,operation='capture',request_id=scope.request['request_id'],
                                       expected_revision=scope.request['expected_revision'],creation=creation))

    def _withdraw_host(self, app, context, unit, request):
        from samsara.source_authority_host import _authorize_current
        _authorize_current(app, context, request, unit)
        detached = deepcopy(request)
        from .registry import Registry
        Registry(self.engine).read(app.workspace_id, viewer=None)
        resolved = _metadata(self.engine)
        item = resolved['families'].get((app.workspace_id,detached['operation']['source_id']))
        if item is None or item['creation']['controller_principal'] != context.principal_id:
            raise SourceAuthorityUnavailable('source unavailable')
        creation = item['creation']
        with _authorized_host_scope(app,context,unit,detached,workspace_id=app.workspace_id,
                                    source_id=creation['source_id'],recipient=creation['recipient']):
            self._ready(app)
            operation = dict(profile=PROFILE,operation='withdraw',request_id=detached['request_id'],
                             expected_revision=detached['expected_revision'],creation=creation)
            if item['image']['phase'] == 'withdrawn':
                history = resolved['histories'][item['record']['branch'],item['record']['id']]
                require(history[-1]['operation'] == operation, 'source already withdrawn')
            return self._finalize(operation)

    def _reauthorize_host(self, app, context, unit, request, returned):
        from samsara.source_authority_host import _authorize_current
        from .registry import Registry
        from .source_authority_installation import strict_json
        _authorize_current(app,context,request,unit)
        Registry(self.engine).read(app.workspace_id,viewer=None)
        detached=deepcopy(request)
        resolved=_metadata(self.engine)
        item=resolved['families'].get((app.workspace_id,detached['operation']['source_id']))
        if item is None or item['creation']['controller_principal'] != context.principal_id:
            raise SourceAuthorityUnavailable('source unavailable')
        kind='capture' if detached['operation']['name']=='source.capture' else 'withdraw'
        with _authorized_host_scope(app,context,unit,detached,workspace_id=app.workspace_id,
                                    source_id=item['creation']['source_id'],recipient=item['creation']['recipient']):
            operation=dict(profile=PROFILE,operation=kind,request_id=detached['request_id'],
                           expected_revision=detached['expected_revision'],creation=item['creation'])
            chain=resolved['histories'][item['record']['branch'],item['record']['id']]
            fact=next((fact for fact in chain if fact['operation']==operation),None)
            if fact is None:
                raise SourceAuthorityUnavailable('source history unavailable')
            row=self.db.execute('SELECT receipt_json FROM events WHERE id=?',(fact['event_id'],)).fetchone()
            receipt=strict_json(row[0])
            require(canonical(returned)==canonical(_summary(item,receipt,kind)),'source cached historical fact mismatch')
