"""Linux/Unix owner with lifetime lock and descriptor-bound host transports.

Same-user hostile code is outside this local trust model. Inherited worker
transports never become operator just because their OS UID matches. There is
no TCP listener, model API, or automatic host/worker execution.
"""
import array
from dataclasses import dataclass, field
import fcntl
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import stat
import struct
import traceback
import sys
import sqlite3
import select
import hashlib

from kageyoni.engine import Engine
from .application import SamsaraApplication
from .content import initialize
from .protocol import Fault, MAX_FRAME, decode, error, frame, runtime_fingerprint


def private_root(root, create=False):
    root = Path(root).absolute()
    if root.is_symlink():
        raise Fault('UNAVAILABLE')
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
    info = root.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise Fault('UNAVAILABLE')
    if any(p.is_symlink() for p in root.parents):
        raise Fault('UNAVAILABLE')
    if len(str(root / 'control.sock').encode()) > 104:
        raise Fault('BUDGET')
    return root.resolve()


@dataclass
class Endpoint:
    socket: socket.socket
    context: object = None
    output_root: Path | None = None
    control: bool = False
    incoming: bytearray = field(default_factory=bytearray)
    outgoing: bytearray = field(default_factory=bytearray)
    descriptors: list = field(default_factory=list)


class Owner:
    def __init__(self, root, initialize_synthetic=False, listen=True):
        os.umask(0o077)
        self.root = private_root(root, create=initialize_synthetic)
        self.lock = os.open(self.root / 'owner.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.lock)
            raise Fault('BUSY') from None
        self.engine = None
        self.selector = selectors.DefaultSelector()
        self.listeners, self.endpoints = [], []
        self.running = False
        try:
            db_path = self.root / 'world.sqlite'
            if db_path.is_symlink() or (self.root / 'workspace.json').is_symlink():
                raise Fault('UNAVAILABLE')
            if not initialize_synthetic:
                metadata = json.loads((self.root / 'workspace.json').read_text())
                if metadata.get('runtime_digest') != runtime_fingerprint():
                    raise Fault('RECONCILE_REQUIRED')
                from kageyoni.resources import schema_path
                # SQLite may need to roll back a hot journal after SIGKILL.
                # Do this under the exclusive owner lock, using mode=rw (no
                # creation) and SQLite alone, before query_only verification.
                # No Engine constructor/schema installer runs here.
                if (self.root / 'world.sqlite-journal').exists():
                    recovery = sqlite3.connect(db_path.resolve().as_uri() + '?mode=rw', uri=True)
                    try:
                        recovery.execute('SELECT count(*) FROM sqlite_master').fetchone()
                    finally:
                        recovery.close()
                # A participant read cannot be the occasion to upgrade an old
                # save. Preflight the exact installed interface read-only.
                db = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)
                try:
                    db.execute('PRAGMA query_only=ON')
                    version = db.execute("SELECT version FROM engine_versions WHERE component='activity_interface'").fetchone()
                    check = db.execute('SELECT checksum FROM migration_checks WHERE version=26').fetchone()
                    queue_version = db.execute("SELECT version FROM engine_versions WHERE component='activity_queue_interface'").fetchone()
                    queue_check = db.execute('SELECT checksum FROM migration_checks WHERE version=27').fetchone()
                    causal_version=db.execute("SELECT version FROM engine_versions WHERE component='causal_delivery_interface'").fetchone()
                    causal_check=db.execute('SELECT checksum FROM migration_checks WHERE version=29').fetchone()
                    for migration, component in ((31, 'resource_profile_interface'), (32, 'resource_admission_interface'), (33, 'worker_liveness_interface'), (34, 'worker_custody_interface')):
                        interface = db.execute('SELECT version FROM engine_versions WHERE component=?', (component,)).fetchone()
                        checksum = db.execute('SELECT checksum FROM migration_checks WHERE version=?', (migration,)).fetchone()
                        if (not interface or interface[0] != '1' or not checksum
                                or checksum[0] != hashlib.sha256(schema_path(f'migration_{migration:03}.sql').read_bytes()).hexdigest()):
                            raise Fault('DEPENDENCY')
                    extension_version=db.execute("SELECT version FROM engine_versions WHERE component='extension_lifecycle_interface'").fetchone()
                    extension_check=db.execute('SELECT checksum FROM migration_checks WHERE version=30').fetchone()
                    if not extension_version or extension_version[0]!='1' or not extension_check or extension_check[0]!=hashlib.sha256(schema_path('migration_030.sql').read_bytes()).hexdigest():raise Fault('DEPENDENCY')
                    if not causal_version or causal_version[0]!='1' or not causal_check or causal_check[0]!=hashlib.sha256(schema_path('migration_029.sql').read_bytes()).hexdigest():raise Fault('DEPENDENCY')
                    prop_version = db.execute("SELECT version FROM engine_versions WHERE component='property_change_interface'").fetchone()
                    prop_check = db.execute('SELECT checksum FROM migration_checks WHERE version=28').fetchone()
                    if not prop_version or prop_version[0] != '1' or not prop_check or prop_check[0] != hashlib.sha256(schema_path('migration_028.sql').read_bytes()).hexdigest():
                        raise Fault('DEPENDENCY')
                    if not queue_version or queue_version[0] != '1' or not queue_check or queue_check[0] != hashlib.sha256(schema_path('migration_027.sql').read_bytes()).hexdigest():
                        raise Fault('DEPENDENCY')
                    if not version or version[0] != '1' or not check or check[0] != hashlib.sha256(schema_path('migration_026.sql').read_bytes()).hexdigest():
                        raise Fault('DEPENDENCY')
                finally:
                    db.close()
                readonly = Engine(db_path, read_only=True)
                try:
                    if not readonly.verify()['ok'] or not readonly.validate_registry()['ok']:
                        raise Fault('DEPENDENCY')
                finally:
                    readonly.close()
            self.engine = Engine(db_path)
            if not initialize_synthetic:
                from .compatibility import validate_continuation
                validate_continuation(self.engine, metadata)
            if initialize_synthetic:
                workspace_id = initialize(self.engine)
                metadata = {'workspace_id': workspace_id, 'branch': 'main', 'synthetic': True, 'runtime_digest': runtime_fingerprint()}
                (self.root / 'workspace.json').write_text(json.dumps(metadata) + '\n')
            else:
                metadata = json.loads((self.root / 'workspace.json').read_text())
                workspace_id = metadata['workspace_id']
                # Opening an unsupported schema fails; never silently migrates.
                if not self.engine.db.execute("SELECT 1 FROM engine_versions WHERE component='activity_interface' AND version='1'").fetchone():
                    raise Fault('DEPENDENCY')
            self.app = SamsaraApplication(self.engine, workspace_id, self.root)
            from .runner import BoundedRunner
            self.app.runner = BoundedRunner(self.app)
            self.operator, _ = self.app.bind()
            if initialize_synthetic:
                from importlib.resources import files
                with self.engine.transaction():
                    self.app.put(files('samsara').joinpath('data/initial-source.md').read_bytes(), 'text/markdown',
                        'samsara:initial-source', ['character:visitor', 'character:keeper', self.operator.principal_id])
                    self.app.extensions.initialize(self.operator)
            for name, control in ([('owner.sock', False), ('control.sock', True)] if listen else []):
                path = self.root / name
                if path.exists():
                    if not path.is_socket() or path.is_symlink():
                        raise Fault('UNAVAILABLE')
                    path.unlink()  # Lifetime lock proves no supported live owner.
                listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                listener.bind(str(path)); os.chmod(path, 0o600)
                listener.listen(16); listener.setblocking(False)
                self.selector.register(listener, selectors.EVENT_READ, ('listen', control))
                self.listeners.append(listener)
        except Exception:
            with (self.root / 'owner-errors.log').open('a') as log:
                traceback.print_exc(file=log)
            self.close()
            raise

    def close_endpoint(self, endpoint):
        for fd in endpoint.descriptors:
            os.close(fd)
        endpoint.descriptors.clear()
        try:
            self.selector.unregister(endpoint.socket)
        except Exception:
            pass
        endpoint.socket.close()
        if endpoint in self.endpoints:
            self.endpoints.remove(endpoint)

    def close(self):
        self.running = False
        for endpoint in self.endpoints[:]:
            self.close_endpoint(endpoint)
        for listener in self.listeners:
            try:
                self.selector.unregister(listener)
            except Exception:
                pass
            listener.close()
        self.listeners.clear()
        self.selector.close()
        if self.engine:
            if hasattr(self, 'app') and hasattr(self.app, 'runner'):
                self.app.runner.close()
            self.engine.close(); self.engine = None
        for name in ('owner.sock', 'control.sock'):
            path = self.root / name
            if path.is_socket() and not path.is_symlink():
                path.unlink()
        if self.lock is not None:
            os.close(self.lock); self.lock = None

    def _accept(self, listener, control):
        sock, _ = listener.accept()
        _, uid, _ = struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i')))
        if uid != os.getuid() or len(self.endpoints) >= 32:
            sock.close(); return
        endpoint = Endpoint(sock, control=control, context=None if control else self.operator)
        sock.setblocking(False)
        self.selector.register(sock, selectors.EVENT_READ, ('client', endpoint))
        self.endpoints.append(endpoint)

    def _adapter(self, endpoint, value):
        if endpoint.control:
            if set(value) == {'adapter', 'role', 'character_id', 'activity_id'} and value['adapter'] == 'bind' and len(endpoint.descriptors) == 1:
                if value['role'] not in ('player', 'worker') or not isinstance(value['character_id'], str) or not self.app.content_sets.actor_admitted(value['character_id']) or (value['activity_id'] is not None and (not isinstance(value['activity_id'], str) or not 0 < len(value['activity_id']) <= 128)):
                    raise Fault('INVALID')
                fd = endpoint.descriptors.pop()
                try:
                    transport = socket.socket(fileno=fd)
                    if transport.family != socket.AF_UNIX or transport.type != socket.SOCK_STREAM:
                        raise Fault('INVALID')
                    context, output_root = self.app.bind(value['role'], value['character_id'], value['activity_id'])
                    if context.role == 'operator':
                        raise Fault('UNAVAILABLE')
                    attached = Endpoint(transport, context, output_root)
                    transport.setblocking(False)
                    self.selector.register(transport, selectors.EVENT_READ, ('client', attached))
                    self.endpoints.append(attached)
                    return {'bound': True, 'workspace_id': self.app.workspace_id, 'branch': 'main',
                            'binding_id': context.binding_id, 'output_root': str(output_root)}
                except Exception:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    raise
            if set(value) == {'adapter', 'binding_id'} and value['adapter'] == 'revoke' and not endpoint.descriptors:
                self.app.revoke(value['binding_id']); return {'revoked': True}
            raise Fault('INVALID')
        if set(value) == {'adapter', 'job_id', 'media_type'} and value['adapter'] == 'stage' and len(endpoint.descriptors) == 1 and endpoint.output_root:
            fd = endpoint.descriptors.pop()
            try:
                return self.app.register_stage(endpoint.context, fd, value['job_id'], value['media_type'], endpoint.output_root)
            finally:
                os.close(fd)
        raise Fault('INVALID')

    def _read(self, endpoint):
        try:
            data, ancillary, flags, _ = endpoint.socket.recvmsg(65536, socket.CMSG_SPACE(array.array('i').itemsize))
            if not data:
                self.close_endpoint(endpoint); return
            for level, kind, content in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    fds = array.array('i'); fds.frombytes(content[:len(content) - len(content) % fds.itemsize])
                    endpoint.descriptors.extend(fds)
                    for descriptor in fds:
                        os.set_inheritable(descriptor, False)
            if flags & socket.MSG_CTRUNC or len(endpoint.descriptors) > 1:
                raise Fault('INVALID')
            endpoint.incoming.extend(data)
            if len(endpoint.incoming) > MAX_FRAME:
                raise Fault('INVALID')
            if b'\n' not in endpoint.incoming:
                return
            # Synchronous one-request-at-a-time clients. Backpressure does not
            # let one client enqueue an unbounded batch or pin the writer.
            packet, _, remainder = endpoint.incoming.partition(b'\n')
            if remainder or endpoint.outgoing:
                raise Fault('INVALID')
            endpoint.incoming.clear()
            try:
                value = decode(packet)
                if isinstance(value, dict) and 'adapter' in value:
                    result = self._adapter(endpoint, value)
                else:
                    if endpoint.control or endpoint.descriptors:
                        raise Fault('INVALID')
                    result = self.app.handle(endpoint.context, value)
            except Fault as exc:
                result = error('invalid', exc.code)
            except Exception:
                with (self.root / 'owner-errors.log').open('a') as log:
                    traceback.print_exc(file=log)
                result = error('invalid', 'INVALID')
            for descriptor in endpoint.descriptors:
                os.close(descriptor)
            endpoint.descriptors.clear()
            endpoint.outgoing.extend(frame(result))
            self.selector.modify(endpoint.socket, selectors.EVENT_WRITE, ('client', endpoint))
        except (Fault, OSError):
            self.close_endpoint(endpoint)

    def _write(self, endpoint):
        try:
            size = endpoint.socket.send(endpoint.outgoing)
            del endpoint.outgoing[:size]
            if not endpoint.outgoing:
                self.selector.modify(endpoint.socket, selectors.EVENT_READ, ('client', endpoint))
        except OSError:
            self.close_endpoint(endpoint)

    def run(self):
        self.running = True
        while self.running:
            self.app.runner.tick()
            for key, events in self.selector.select(0.1):
                kind, target = key.data
                if kind == 'listen':
                    self._accept(key.fileobj, target)
                elif events & selectors.EVENT_READ:
                    self._read(target)
                elif events & selectors.EVENT_WRITE:
                    self._write(target)

    def run_stdio(self, context, output_root):
        """One inherited pipe, one launcher-bound caller. No fake concurrency."""
        print(json.dumps({'bound': True, 'workspace_id': self.app.workspace_id, 'branch': 'main',
            'binding_id': context.binding_id, 'output_root': str(output_root)}), flush=True)
        self.running = True
        incoming = bytearray()
        while self.running:
            self.app.runner.tick()
            if b'\n' not in incoming:
                if not select.select([sys.stdin.buffer], [], [], 0.05)[0]:
                    continue
                data = os.read(sys.stdin.fileno(), 65536)
                if not data: break
                incoming.extend(data)
                if len(incoming) > MAX_FRAME: break
                if b'\n' not in incoming: continue
            packet, _, rest = incoming.partition(b'\n')
            incoming = bytearray(rest)
            packet += b'\n'
            if not packet:
                break
            if len(packet) > MAX_FRAME or not packet.endswith(b'\n'):
                break
            try:
                value = decode(packet)
                if isinstance(value, dict) and 'adapter' in value:
                    if set(value) != {'adapter', 'job_id', 'media_type', 'filename'} or value['adapter'] != 'stage':
                        raise Fault('INVALID')
                    filename = value['filename']
                    if not isinstance(filename, str) or not filename or '/' in filename or '\\' in filename or filename in ('.', '..') or '\x00' in filename:
                        raise Fault('INVALID')
                    fd = os.open(output_root / filename, os.O_RDONLY | os.O_NOFOLLOW)
                    try:
                        result = self.app.register_stage(context, fd, value['job_id'], value['media_type'], output_root)
                    finally:
                        os.close(fd)
                else:
                    result = self.app.handle(context, value)
            except Fault as exc:
                result = error('invalid', exc.code)
            except Exception:
                with (self.root / 'owner-errors.log').open('a') as log:
                    traceback.print_exc(file=log)
                result = error('invalid', 'INVALID')
            sys.stdout.buffer.write(frame(result)); sys.stdout.buffer.flush()
