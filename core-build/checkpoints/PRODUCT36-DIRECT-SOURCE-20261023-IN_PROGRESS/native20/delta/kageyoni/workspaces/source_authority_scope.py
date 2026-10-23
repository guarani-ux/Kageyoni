"""Opaque once-use host scope; not a producer, grant, or public token API.

The fixed facade/finalizer remains to be implemented. This private mechanism
alone does not make a Native command authenticated or an interface runnable.
"""
from contextlib import contextmanager
from copy import deepcopy
from ..persistence.unit_of_work import _lexical_generation
from .source_authority_schema import _identifier, _require
from .source_authority_operations import digest, validate_command


class _HostScope:
    __slots__ = ('engine', 'db', 'unit', 'generation', 'app', 'context',
                 'request', 'request_digest', 'identity', 'workspace_id',
                 'source_id', 'recipient', 'operation', 'active', 'armed', 'spent')

    def __reduce__(self):
        raise TypeError('source host scope cannot be serialized')

    def __copy__(self):
        raise TypeError('source host scope cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('source host scope cannot be copied')


def _current(engine):
    scope = getattr(engine, '_source_authority_host_scope', None)
    _require(type(scope) is _HostScope and scope.active and scope.engine is engine
             and scope.db is engine.db and not scope.spent,
             'current unused source host scope required')
    _require(_lexical_generation(scope.db, scope.unit) is scope.generation,
             'source host scope lexical generation expired')
    _require(scope.app.engine is engine and scope.app.db is scope.db
             and digest(scope.request) == scope.request_digest,
             'source host scope identity changed')
    # Fixed import, not an arbitrary callback or actor-text assertion.
    from samsara.source_authority_host import _authorize_current
    _require(_authorize_current(scope.app, scope.context, scope.request, scope.unit) == scope.identity,
             'source host authority changed')
    return scope


@contextmanager
def _authorized_host_scope(app, context, unit, request, *, workspace_id, source_id, recipient):
    from samsara.source_authority_host import _authorize_current
    # Authorization precedes controlled identity diagnostics and source access.
    identity = _authorize_current(app, context, request, unit)
    engine = app.engine
    _require(getattr(engine, '_source_authority_host_scope', None) is None,
             'source host scope cannot be reentered')
    for value, label in ((workspace_id, 'workspace'), (source_id, 'source'), (recipient, 'recipient')):
        _identifier(value, label)
    _identifier(identity[1], 'controller principal')
    _require(workspace_id == app.workspace_id
             and request['operation'].get('source_id') == source_id,
             'source host family differs from whole product request')
    if identity[-1] == 'source.capture':
        _require(request['operation'].get('recipient') == recipient,
                 'source host recipient differs from whole product request')
    scope = _HostScope()
    scope.engine, scope.db, scope.unit = engine, engine.db, unit
    scope.generation = _lexical_generation(engine.db, unit)
    scope.app, scope.context = app, context
    scope.request, scope.request_digest = deepcopy(request), digest(request)
    scope.identity = identity
    scope.workspace_id, scope.source_id, scope.recipient = workspace_id, source_id, recipient
    scope.operation = 'capture' if identity[-1] == 'source.capture' else 'withdraw'
    scope.active, scope.armed, scope.spent = True, None, False
    engine._source_authority_host_scope = scope
    try:
        # No opaque object leaves this internal lexical block.
        yield
    finally:
        scope.active, scope.armed, scope.spent = False, None, True
        if getattr(engine, '_source_authority_host_scope', None) is scope:
            engine._source_authority_host_scope = None


def _check_operation(scope, operation):
    creation = operation['creation']
    _require(operation['operation'] == scope.operation
             and operation['request_id'] == scope.request['request_id']
             and operation['expected_revision'] == scope.request['expected_revision']
             and creation['branch'] == scope.identity[-2]
             and creation['workspace_id'] == scope.workspace_id
             and creation['source_id'] == scope.source_id
             and creation['recipient'] == scope.recipient
             and creation['controller_principal'] == scope.identity[1],
             'source native command differs from authorized host operation')


def _arm_command(engine, command):
    scope = _current(engine)
    _require(scope.armed is None, 'source host command already armed')
    _check_operation(scope, validate_command(command))
    scope.armed = digest(command)


def _consume_command(engine, command, *, preview=False):
    scope = _current(engine)
    _require(type(preview) is bool and not preview, 'source host preview forbidden')
    _check_operation(scope, validate_command(command))
    _require(scope.armed is not None and digest(command) == scope.armed,
             'exact armed source native command required')
    # Consumed before generic replay/effects, including a subsequent rejection.
    scope.spent, scope.armed = True, None


def _command_signal(value, parent=None):
    """Detect reserved aliases before canonical validation, including Python
    dict/string subclasses and tuple coercions. Ordinary prose is not a key.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            name = key.casefold() if isinstance(key, str) else ''
            if name.startswith(('source_authority', 'source-authority')):
                return True
            if isinstance(child, str):
                word = child.casefold()
                if name == 'domain' and word.startswith('source_authority'):
                    return True
                if name == 'profile' and word.startswith('samsara-source-authority/'):
                    return True
                if name in ('id', 'record_id') and word.startswith('source-authority:'):
                    return True
                if name in ('request_id', 'kind') and word.startswith(('source-authority-operation:', 'source_authority')):
                    return True
            if _command_signal(child, name):
                return True
    elif isinstance(value, (list, tuple)):
        for child in value:
            if parent in ('changed', 'record_ids') and isinstance(child, str) and child.casefold().startswith('source-authority:'):
                return True
            if _command_signal(child, parent):
                return True
    return False


def _guard_command(engine, command, *, preview=False):
    if _command_signal(command):
        _consume_command(engine, command, preview=preview)
