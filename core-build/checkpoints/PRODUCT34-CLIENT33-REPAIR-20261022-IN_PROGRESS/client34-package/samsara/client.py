"""Client adapters construct commands; they do not own world state."""
import array
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import select
import time
from uuid import uuid4
from .content import definitions
from .protocol import PROTOCOL, Fault, MAX_FRAME, decode, frame, validate


class PipeTransport:
    def __init__(self, process):
        self.process = process
    def settimeout(self, seconds):
        self.timeout = seconds
    def sendall(self, data):
        self.process.stdin.write(data); self.process.stdin.flush()
    def recv(self, size):
        if not select.select([self.process.stdout], [], [], getattr(self, 'timeout', 10))[0]:
            raise Fault('BUSY')
        return self.process.stdout.read1(size)
    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            try:
                self.process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=5)
        if self.process.stdout:
            self.process.stdout.close()


def exchange(sock, value, fd=None):
    data = frame(value)
    if fd is None:
        sock.sendall(data)
    else:
        fds = array.array('i', [fd])
        sent = sock.sendmsg([data], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, fds)])
        if sent < len(data):
            sock.sendall(data[sent:])
    result = bytearray()
    while b'\n' not in result:
        part = sock.recv(65536)
        if not part:
            raise Fault('UNAVAILABLE')
        result.extend(part)
        if len(result) > MAX_FRAME:
            raise Fault('BUDGET')
    packet, _, extra = result.partition(b'\n')
    if extra:
        raise Fault('INVALID')
    return decode(packet)


class Client:
    def __init__(self, sock, workspace_id, output_root=None):
        self.sock, self.workspace_id, self.output_root = sock, workspace_id, Path(output_root) if output_root else None
        self.revision = 0
        sock.settimeout(5)

    @classmethod
    def session(cls, root, character='visitor', role='player', activity_id=None, new=False):
        """Serialized pipe owner selected explicitly by the trusted launcher."""
        root = Path(root).absolute()
        command = [sys.executable, '-m', 'samsara', 'stdio', '--workspace', str(root), '--role', role]
        if character:
            command += ['--actor', character]
        if activity_id:
            command += ['--activity', activity_id]
        if new:
            command += ['--new-synthetic']
        env = {'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin', 'HOME': str(root.parent),
               'PYTHONPATH': str(Path(__file__).resolve().parent.parent), 'PYTHONDONTWRITEBYTECODE': '1',
               'PYTHONUNBUFFERED': '1', 'LC_ALL': 'C.UTF-8'}
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, cwd=root.parent)
        transport = PipeTransport(process)
        try:
            packet = bytearray()
            while b'\n' not in packet:
                data = transport.recv(65536)
                if not data:
                    raise Fault('BUSY' if (root / 'workspace.json').exists() else 'UNAVAILABLE')
                packet.extend(data)
                if len(packet) > MAX_FRAME:
                    raise Fault('INVALID')
            reply = decode(packet.rstrip(b'\n'))
            if not reply.get('bound'):
                raise Fault(reply.get('error', 'UNAVAILABLE'))
            client = cls(transport, reply['workspace_id'], reply['output_root'])
            client.binding_id = reply['binding_id']
            return client
        except Exception:
            transport.close(); raise

    @classmethod
    def operator(cls, root):
        root = Path(root)
        metadata = json.loads((root / 'workspace.json').read_text())
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); sock.connect(str(root / 'owner.sock'))
        return cls(sock, metadata['workspace_id'])

    @classmethod
    def participant(cls, root, character='visitor', role='player', activity_id=None):
        """Trusted local launcher binds a separate restricted stream."""
        root = Path(root)
        local, remote = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        control = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); control.settimeout(5)
        try:
            control.connect(str(root / 'control.sock'))
            reply = exchange(control, {'adapter': 'bind', 'role': role, 'character_id': character, 'activity_id': activity_id}, remote.fileno())
            if not reply.get('bound'):
                raise Fault(reply.get('error', 'UNAVAILABLE'))
            client = cls(local, reply['workspace_id'], reply['output_root'])
            client.binding_id = reply['binding_id']
            return client
        except Exception:
            local.close(); raise
        finally:
            remote.close(); control.close()

    def close(self):
        self.sock.close()

    def command(self, operation, request_id=None, expected_revision=None):
        request = {'protocol': PROTOCOL, 'request_id': request_id or 'request:' + uuid4().hex,
            'workspace_id': self.workspace_id, 'branch': 'main',
            'expected_revision': self.revision if expected_revision is None else expected_revision, 'operation': operation}
        return self.call(request)

    def call(self, request):
        validate(request, 'Command')
        result = exchange(self.sock, request)
        validate(result, 'Error' if 'error' in result else 'Result')
        if 'revision_after' in result:
            # An exact historical receipt is not a newer observation of the head.
            if not result.get('replayed') or result['revision_after'] >= self.revision:
                self.revision = result['revision_after']
        return result

    def checked(self, operation, **kwargs):
        result = self.command(operation, **kwargs)
        if 'error' in result:
            raise Fault(result['error'])
        return result

    def view(self):
        return self.checked({'name': 'workspace.view', 'limit': 32, 'cursor': None})['return']

    def status(self, activity_id):
        return self.checked({'name': 'activity.status', 'activity_id': activity_id})['return']['checkpoint']

    def causal(self,root_id,action='status',limit=32):
        operation={'name':'world.'+action,'root_id':root_id}
        if action=='step':operation['limit']=limit
        return self.checked(operation)['return']

    def property(self, entity_id='visitor'):
        return self.checked({'name':'property.inspect','entity_id':entity_id,
            'property_id':'fixture:load_capacity','definition_version':1})['return']

    def extension_catalog(self,version=1):
        return self.checked({'name':'extension.catalog','version':version})['return']

    def prepare_extension(self,version=2,pending_policy='cancel_and_reconcile'):
        catalog=self.extension_catalog(version)
        op={k:catalog[k] for k in ('definition','class','consumer_refs','ending_handler','check_refs','boundary')}
        return self.checked(dict(op,name='extension.prepare',pending_policy=pending_policy))['return']

    def extension(self,candidate,action='preview'):
        return self.checked({'name':'extension.'+action,'definition':candidate['definition'],
            'candidate_digest':candidate['candidate_digest'],'replacement':None})['return']

    def select(self, **filters):
        return self.checked({'name':'property.select','selector':{'limit':32,'cursor':None,**filters}})['return']

    def prepare_boost(self, entity_id='visitor', value=15, duration=2, priority=0):
        catalog=self.checked({'name':'property.catalog'})['return']
        selection=self.select(ids=[entity_id])
        override={'effect_id':'boost:'+uuid4().hex,'version':1,'property_id':catalog['property_id'],
            'definition_version':catalog['definition_version'],'operation':'replace','value':value,'unit':catalog['unit'],
            'priority':priority,'source_ref':catalog['source_ref'],'predicate_ref':catalog['predicate_ref'],
            'ending_handler':catalog['ending_handler'],
            'starts_at':{'kind':'fictional','clock_id':catalog['clock_id'],'tick':catalog['tick']},
            'ends_at':{'kind':'fictional','clock_id':catalog['clock_id'],'tick':catalog['tick']+duration}}
        return self.checked({'name':'change.prepare','snapshot_id':selection['snapshot_id'],
            'reason':'Try the public synthetic capacity expression.','assignments':[],
            'overrides':[override],'ending_policy':'cancel_and_reconcile'})['return']

    def change(self, change, action='apply'):
        return self.checked({'name':'change.'+action,'change_id':change['change_id'],
            'digest':change['digest'],'boundary':'checkpoint'})['return']

    def support(self, support_id, entity_id='visitor'):
        return self.checked({'name':'support.use','entity_id':entity_id,'support_id':support_id})['return']

    def support_status(self, support_id):
        return self.checked({'name':'support.status','support_id':support_id})['return']

    def advance_clock(self, ticks=1):
        return self.checked({'name':'clock.advance','clock_id':'fixture:clock','ticks':ticks})['return']

    def intake_status(self, assignment_id, revision=None):
        return self.checked({'name': 'intake.status', 'assignment_id': assignment_id, 'revision': revision})['return']

    def admit(self, operation, source_directory):
        """Trusted local launcher stages a declared manifest, then calls the owner.

        This method cannot grant its stream operator authority. Only the explicit
        intake CLI/trusted launcher obtains that role. Source files are data.
        """
        from .intake import _read_at, MAX_TOTAL, STABLE_SECONDS
        validate(operation, 'Intake')
        if self.output_root is None:
            raise Fault('UNAVAILABLE')
        source_directory = Path(source_directory).absolute()
        total = 0
        for entry in operation['files']:
            blob = _read_at(source_directory, entry['relative_path'])
            total += len(blob)
            if total > MAX_TOTAL:
                raise Fault('BUDGET')
            if len(blob) != entry['bytes'] or hashlib.sha256(blob).hexdigest() != entry['digest']:
                raise Fault('RECONCILE_REQUIRED')
            destination = self.output_root / entry['relative_path']
            for parent in reversed(destination.parents):
                if parent == self.output_root or parent.is_relative_to(self.output_root):
                    if parent.is_symlink():
                        raise Fault('UNAVAILABLE')
                    parent.mkdir(exist_ok=True, mode=0o700)
            temporary = destination.parent / ('intake-' + uuid4().hex + '.partial')
            try:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(blob); stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        time.sleep(STABLE_SECONDS + 0.01)  # No owner/database transaction held.
        return self.checked(operation)['return']

    def enqueue(self, activity_id, recipe='source_index', max_seconds=10, delay_seconds=0, cpu_iterations=0,
                *, heartbeats=True, cooperative_stop=True):
        parameters={'delay_seconds':delay_seconds,'cpu_iterations':cpu_iterations}
        if recipe=='liveness_probe':parameters.update(heartbeats=heartbeats,cooperative_stop=cooperative_stop)
        return self.checked({'name':'job.enqueue','activity_id':activity_id,'recipe':recipe,
            'parameters':parameters,'max_seconds':max_seconds})['return']

    def job(self, activity_id):
        return self.checked({'name':'job.status','activity_id':activity_id})['return']

    def start_assignment(self, assignment_id, activity_id, actor='visitor', kind=None, purpose=None, parent_id=None):
        admitted = self.intake_status(assignment_id)
        kind = kind or ('research' if admitted['purpose'] != 'assignment' else 'real_work')
        purpose = purpose or ('Recover an attributed noncanonical dossier from the admitted character material.' if admitted['purpose'] == 'character_recovery'
            else 'Prepare a researched job assessment and preparation package; do not submit an application.' if admitted['purpose'] == 'job_preparation'
            else 'Produce a source-grounded component for assignment ' + assignment_id + '.')
        return self.start(kind, activity_id, actor, purpose, parent_id, admitted['source_refs'] + [admitted['manifest_ref']])

    def start_source_assignment(self, assignment_id, activity_id, mode, purpose, actor='visitor', parent_id=None, prior_refs=()):
        """Choose a native source-work component from a current admitted manifest."""
        if mode not in ('study', 'research', 'script'):
            raise Fault('INVALID')
        admitted = self.intake_status(assignment_id)
        return self.start('source_' + mode, activity_id, actor, purpose, parent_id,
                          [admitted['manifest_ref']] + list(prior_refs))

    def start(self, name, activity_id, actor='visitor', purpose=None, parent_id=None, source_refs=()):
        definition = next(x for x in definitions() if x['id'] == 'synthetic:' + name)
        return self.checked({'name': 'activity.start', 'activity_id': activity_id, 'kind': definition['kind'],
            'definition': definition['reference'], 'parent_id': parent_id, 'participants': definition['participants'] or [actor],
            'purpose': purpose, 'source_refs': list(source_refs), 'acceptance_ref': 'native:' + definition['handler'] + '/1'})

    def practice_account(self, activity_id, interpretation='unchanged'):
        return self.checked({'name': 'practice.account', 'activity_id': activity_id,
            'interpretation': interpretation})['return']

    def read(self, ref):
        view = self.checked({'name': 'artifact.read', 'reference': ref})['return']
        if view['text'] is not None:
            blob = view['text'].encode('utf-8')
        else:
            output, offset = [], 0
            while True:
                chunk = self.checked({'name': 'artifact.fetch', 'transfer_ref': view['transfer_ref'], 'reference': ref,
                                      'offset': offset, 'max_bytes': 262144})['return']
                raw = base64.b64decode(chunk['content_base64'], validate=True)
                if len(raw) != chunk['bytes'] or hashlib.sha256(raw).hexdigest() != chunk['chunk_digest'] or chunk['offset'] != offset:
                    raise Fault('INVALID')
                output.append(raw); offset += len(raw)
                if chunk['eof']:
                    break
                if not raw:
                    raise Fault('INVALID')
            blob = b''.join(output)
        if len(blob) != view['total_bytes'] or hashlib.sha256(blob).hexdigest() != ref['digest']:
            raise Fault('INVALID')
        return blob

    def prepared(self, activity_id):
        cp = self.status(activity_id)
        for ref in cp['result_refs']:
            try:
                value = json.loads(self.read(ref))
            except (ValueError, UnicodeError):
                continue
            if isinstance(value, dict) and value.get('activity_id') == activity_id and 'input' in value and 'job_id' in value:
                return value, ref
        raise Fault('UNAVAILABLE')

    def submit_file(self, packet, path, media_type='text/markdown'):
        path = Path(path)
        if self.output_root is None or not path.is_relative_to(self.output_root):
            raise Fault('UNAVAILABLE')
        if isinstance(self.sock, PipeTransport):
            if path.parent != self.output_root:
                raise Fault('UNAVAILABLE')
            staged = exchange(self.sock, {'adapter': 'stage', 'job_id': packet['job_id'], 'media_type': media_type, 'filename': path.name})
        else:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                staged = exchange(self.sock, {'adapter': 'stage', 'job_id': packet['job_id'], 'media_type': media_type}, fd)
            finally:
                os.close(fd)
        if 'error' in staged:
            raise Fault(staged['error'])
        result = self.checked({'name': 'artifact.submit', **staged})
        return result['return']['reference']

    def receive(self, packet, input_ref, output_refs, checks=()):
        result = {'dispatch_id': 'samsara:' + __import__('samsara.protocol', fromlist=['digest']).digest([packet['job_id'], 'dispatch']),
            'job_id': packet['job_id'], 'attempt_generation': packet['attempt_generation'], 'input_digest': input_ref['digest'],
            'status': 'returned', 'output_refs': list(output_refs), 'check_results': list(checks), 'effect_refs': [],
            'tool_receipt_refs': [], 'failure_code': None}
        return self.checked({'name': 'activity.receive', 'result': result})

    def return_source_work(self, activity_id, authored_path, inquiry, *, attribution, limit,
                           draft=None, disposition='returned', media_type='text/markdown', checks=()):
        """Admit actual authored bytes and a source-bound native operation proposal.

        The owner validates citations and performs the native document calls.
        This helper makes no substantive or quality judgment about the work.
        """
        packet, input_ref = self.prepared(activity_id)
        if packet['input'].get('source_work', {}).get('version') != 1:
            raise Fault('UNSUPPORTED')
        authored = self.submit_file(packet, authored_path, media_type)
        envelope = {'version': 1, 'job_id': packet['job_id'],
                    'attempt_generation': packet['attempt_generation'], 'input_digest': input_ref['digest'],
                    'disposition': disposition, 'authored_ref': authored,
                    'assessment': {'attribution': attribution, 'limit': limit},
                    'inquiry': inquiry, 'draft': draft}
        path = self.output_root / ('source-work-' + uuid4().hex + '.json')
        path.write_text(json.dumps(envelope, ensure_ascii=False, allow_nan=False) + '\n')
        proposal = self.submit_file(packet, path, 'application/json')
        return self.receive(packet, input_ref, [proposal, authored], checks)

    def act(self, activity_id, action_id, fields=None):
        packet, input_ref = self.prepared(activity_id)
        issued = packet['input']['issued']
        reply = {'request_hash': issued['request_hash'], 'encounter_id': issued['encounter_id'],
            'action': {'kind': 'none'} if action_id == 'none' else {'kind': 'propose_action', 'action_id': action_id, 'fields': fields or {}}}
        path = self.output_root / ('reply-' + uuid4().hex + '.json')
        path.write_text(json.dumps(reply, ensure_ascii=False) + '\n')
        ref = self.submit_file(packet, path, 'application/json')
        return self.receive(packet, input_ref, [ref])
