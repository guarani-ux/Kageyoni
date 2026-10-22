"""Bounded owner-only subprocess lane with checkpoint-derived liveness.

Native methods own fences, stop intent, budgets and settlement. Every process,
file, channel and signal observation occurs outside a DB transaction. Unknown
historical exit codes remain uncertainty; no observation is synthesized.
"""
import hashlib
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import signal
import select
import stat
import subprocess
import sys
import time

from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.workspaces.job_queue import JobQueue
from kageyoni.workspaces.resource_profiles import ResourceProfiles
from kageyoni.workspaces.worker_liveness import verify_worker_liveness
from kageyoni.workspaces.worker_custody import WorkerCustody, terminal_absence
from kageyoni.workspaces.custody_schema import validate_registration
from . import process_custody
from .application import CallerContext
from .protocol import Fault, encoded

TASK_LIMIT = 800000  # Includes LF.
EVENT_LIMIT = 256   # Includes LF.
IDENTITY_LIMIT = 1024
WRITE_QUANTUM = 65536
STOP_GRACE = 5.0
POLL_QUANTUM = 0.05


@dataclass(frozen=True)
class _ReconciliationPreflight:
    """Private owner memory, never accepted from the participant wire."""
    pin_json: str
    disposition: str
    observed_at: float
    registration_json: str | None = None
    observation_json: str | None = None
    recovered: bytes | None = None

    def __post_init__(self):
        if (type(self.pin_json) is not str or len(self.pin_json.encode()) > 32768 or
                self.disposition not in ('recover', 'discard') or
                type(self.observed_at) not in (int, float) or
                not -2**63 <= self.observed_at <= 2**63 - 1 or not math.isfinite(self.observed_at) or
                any(x is not None and (type(x) is not str or len(x.encode()) > 131072)
                    for x in (self.registration_json, self.observation_json)) or
                (self.observation_json is not None and self.registration_json is None) or
                (self.disposition == 'discard' and self.recovered is not None) or
                (self.disposition == 'recover' and
                    (type(self.recovered) is not bytes or len(self.recovered) > 1000000))):
            raise Fault('RECONCILE_REQUIRED')


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON key')
        value[key] = item
    return value


def _constant(_value):
    raise ValueError('nonfinite JSON')


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('nonfinite JSON')
    return result


def strict_object(frame, limit):
    if (not isinstance(frame, bytes) or len(frame) > limit or
            not frame.endswith(b'\n') or b'\n' in frame[:-1]):
        raise ValueError('invalid JSON frame')
    value = json.loads(frame[:-1].decode('utf-8'), object_pairs_hook=_pairs,
                       parse_constant=_constant, parse_float=_float)
    if not isinstance(value, dict):
        raise ValueError('JSON object required')
    return value


def process_identity(pid, proc_pid=None, namespace=None):
    try:
        proc_pid = pid if proc_pid is None else proc_pid
        root = Path(f'/proc/{proc_pid}')
        fields = (root / 'stat').read_text().rsplit(')', 1)[1].split()
        status = dict(line.split(':', 1) for line in (root / 'status').read_text().splitlines() if ':' in line)
        actual_namespace = os.readlink(root / 'ns/pid')
        if int(status['NSpid'].split()[-1]) != pid or (namespace and namespace != actual_namespace):
            return None
        return {'pid': pid, 'proc_pid': proc_pid, 'pid_namespace': actual_namespace,
                'start_ticks': fields[19], 'state': fields[0],
                'parent_proc_pid': int(status['PPid'])}
    except (OSError, IndexError, KeyError, ValueError):
        return None


def alive(observation):
    if not observation:
        return False
    current = process_identity(observation['pid'], observation.get('proc_pid'), observation.get('pid_namespace'))
    return bool(current and current['start_ticks'] == observation['start_ticks'] and current['state'] != 'Z')


def launched_identity(process, timeout=.2):
    """The existing bounded startup handshake, now strict and nonblocking."""
    deadline = time.monotonic() + timeout
    blob = bytearray()
    while b'\n' not in blob:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([process.stderr], [], [], remaining)[0]:
            raise RuntimeError('worker identity timeout')
        try:
            part = os.read(process.stderr.fileno(), IDENTITY_LIMIT - len(blob))
        except BlockingIOError:
            continue
        if not part:
            raise RuntimeError('invalid worker identity handshake')
        blob.extend(part)
        if len(blob) >= IDENTITY_LIMIT and b'\n' not in blob:
            raise RuntimeError('invalid worker identity handshake')
    split = blob.find(b'\n') + 1
    value = strict_object(bytes(blob[:split]), IDENTITY_LIMIT)
    if (set(value) != {'pid', 'proc_pid', 'pid_namespace'} or
            type(value['pid']) is not int or type(value['proc_pid']) is not int or
            value['pid'] != process.pid or value['proc_pid'] <= 0 or
            value['pid_namespace'] != os.readlink('/proc/self/ns/pid')):
        raise RuntimeError('worker namespace mismatch')
    identity = process_identity(process.pid, value['proc_pid'], value['pid_namespace'])
    parent_proc_pid = int(os.readlink('/proc/self'))
    if (not identity or identity['parent_proc_pid'] != parent_proc_pid or
            os.getpgid(process.pid) != process.pid):
        raise RuntimeError('worker process identity mismatch')
    identity.pop('state'); identity.pop('parent_proc_pid')
    tail = bytes(blob[split:])
    if len(tail) > EVENT_LIMIT:
        raise RuntimeError('worker startup event overflow')
    return identity, tail


def validate_recipe(role, recipe, parameters, max_seconds):
    if recipe not in ('source_index', 'bounded_probe', 'liveness_probe'):
        raise Fault('UNSUPPORTED')
    if recipe in ('bounded_probe', 'liveness_probe') and role != 'operator':
        raise Fault('UNAVAILABLE')
    if not isinstance(parameters, dict):
        raise Fault('INVALID')
    keys = {'delay_seconds', 'cpu_iterations'}
    if recipe == 'liveness_probe':
        keys |= {'heartbeats', 'cooperative_stop'}
    if set(parameters) != keys:
        raise Fault('INVALID')
    delay, count = parameters['delay_seconds'], parameters['cpu_iterations']
    maximum = 90 if recipe == 'liveness_probe' else 3
    if (type(delay) not in (int, float) or not 0 <= delay <= maximum or not math.isfinite(delay) or
            type(count) is not int or not 0 <= count <= 1000000):
        raise Fault('INVALID')
    if recipe == 'liveness_probe' and any(type(parameters[k]) is not bool for k in ('heartbeats', 'cooperative_stop')):
        raise Fault('INVALID')
    if recipe == 'source_index' and any(parameters.values()):
        raise Fault('INVALID')
    if (type(max_seconds) not in (int, float) or not 0 < max_seconds <= 120 or
            not math.isfinite(max_seconds) or delay + 1 > max_seconds):
        raise Fault('BUDGET')


class BoundedRunner:
    def __init__(self, app):
        self.app, self.db = app, app.db
        self.queue = JobQueue(app.engine, app.workspace_id)
        self.epoch = self.queue.boot(time.time())
        self.live = {}
        self.historical_stops = {}
        self.closing = False
        self.root = app.root / 'jobs'
        self._external()
        self.root.mkdir(mode=0o700, exist_ok=True)

    def _external(self):
        if self.db.in_transaction:
            raise RuntimeError('worker IO inside transaction')

    def _attempt(self, row):
        # A real table AND exact per-attempt row are needed. Old history is not
        # backfilled or reinterpreted merely because a new interface exists.
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='activity_worker_liveness'").fetchone():
            return None
        found = self.db.execute('''SELECT * FROM activity_worker_liveness
            WHERE workspace_id=? AND job_id=? AND owner_epoch=? AND generation=?''',
            (self.app.workspace_id, row['job_id'], row['owner_epoch'], row['generation'])).fetchone()
        if found is None:
            return None
        value = dict(found)
        if value['lease_token'] != row['lease_token']:
            raise Fault('RECONCILE_REQUIRED')
        return value

    def context(self, row):
        binding = self.db.execute('SELECT * FROM activity_bindings WHERE binding_id=?', (row['binding_id'],)).fetchone()
        if not binding:
            raise Fault('UNAVAILABLE')
        context = CallerContext(binding['binding_id'], binding['principal_id'], binding['workspace_id'],
            binding['role'], binding['character_id'], row['authority_epoch'], binding['activity_id'])
        self.app.authorize(context)
        return context

    def path(self, row):
        return self.root / (hashlib.sha256(row['job_id'].encode()).hexdigest() +
                           f"-{row['owner_epoch']}-{row['generation']}.json")

    def enqueue(self, context, activity, recipe, parameters, max_seconds):
        validate_recipe(context.role, recipe, parameters, max_seconds)
        if self.app.media_work.enabled(activity):
            raise Fault('UNSUPPORTED')
        if self.app.source_work.enabled(activity):
            raise Fault('UNSUPPORTED')
        if activity['spec']['kind'] not in ('study', 'research', 'real_work') or activity['state'] != 'waiting':
            raise Fault('DEPENDENCY')
        job_id = activity['native']['job_id']
        prepared = json.loads(self.db.execute('SELECT prepared_json FROM activity_jobs WHERE job_id=?', (job_id,)).fetchone()[0])
        value = {'recipe': recipe, 'parameters': parameters, 'packet': self.app.packet(prepared),
                 'input_digest': prepared['input_ref']['digest']}
        if len(encoded(value).encode() + b'\n') > TASK_LIMIT:
            raise Fault('BUDGET')
        try:
            self.queue.enqueue(job_id, context.binding_id, context.authority_epoch, recipe, parameters, max_seconds)
        except __import__('kageyoni.engine', fromlist=['Rejected']).Rejected as exc:
            raise Fault('BUSY' if 'queue full' in str(exc) else 'CONFLICT') from None
        return self.view(context, activity)

    def view(self, context, activity):
        row = self.queue.row(activity['native'].get('job_id'))
        if not row:
            raise Fault('UNAVAILABLE')
        budget = self.db.execute('SELECT starts,reserved_seconds FROM activity_queue_roots WHERE workspace_id=? AND root_id=?',
                                 (self.app.workspace_id, row['root_id'])).fetchone()
        ref = json.loads(row['output_ref_json']) if row['output_ref_json'] else None
        if ref:
            self.app.artifact_bytes(context, ref)
        return {'kind': 'job', 'activity_id': activity['activity_id'], 'job_id': row['job_id'],
                'state': row['state'], 'reason': row['reason'], 'generation': row['generation'],
                'owner_epoch': row['owner_epoch'], 'reserved_seconds': budget['reserved_seconds'],
                'charged_starts': budget['starts'], 'output_ref': ref}

    def _stop_id(self, row, disposition):
        return 'runner-stop:' + hashlib.sha256(encoded([row['job_id'], self.queue.fence(row), disposition]).encode()).hexdigest()

    def _request_stop(self, row, disposition, now=None, mono=None):
        attempt = self._attempt(row)
        if attempt is not None and self._absence(row) is not None:
            return self.queue.row(row['job_id'])
        first_mono = time.monotonic() if mono is None else mono
        if attempt is not None:
            if attempt['exit_json'] is None:
                # This is deliberately permitted inside product control UoW;
                # there is NO process/channel IO or speculative local cache.
                receipt = self.queue.request_stop(row['job_id'], self.queue.fence(row), disposition,
                    self._stop_id(row, disposition), time.time() if now is None else now)
                if attempt['stop_requested_at'] is None and row['job_id'] in self.live:
                    # Pending until _cache_stop reads the COMMITTED matching
                    # row. A later first request after rollback replaces this
                    # candidate; repeated committed requests never reset it.
                    self.live[row['job_id']]['stop_candidate'] = (
                        receipt['stop_requested_at'], receipt['request_id'], first_mono)
            return self.queue.row(row['job_id'])
        reason = disposition + '_requested'
        if row['state'] == 'reconciling' and disposition != 'cancel' and row['reason'].endswith('_requested'):
            reason = row['reason']
        self.queue.transition(row['job_id'], 'reconciling', reason)
        if row['state'] != 'reconciling' and row['job_id'] in self.live:
            self.live[row['job_id']]['stop_candidate'] = (None, None, first_mono)
        return self.queue.row(row['job_id'])

    def control(self, activity_id, action):
        descendants = self.db.execute('''WITH RECURSIVE tree(activity_id) AS (
            SELECT activity_id FROM activity_runs WHERE workspace_id=? AND activity_id=?
            UNION ALL SELECT a.activity_id FROM activity_runs a JOIN tree t ON a.parent_id=t.activity_id WHERE a.workspace_id=?)
            SELECT q.* FROM activity_queue q JOIN activity_jobs j ON q.job_id=j.job_id JOIN tree t ON j.activity_id=t.activity_id
            WHERE q.workspace_id=? AND q.state IN ('running','queued','paused','reconciling')''',
            (self.app.workspace_id, activity_id, self.app.workspace_id, self.app.workspace_id)).fetchall()
        for raw in descendants:
            row = dict(raw)
            attempt = self._attempt(row)
            if self._absence(row) is not None:
                self._reconcilable(row)
                self.queue.transition(row['job_id'], 'paused' if action == 'pause' else 'cancelled', action + '_requested')
                continue
            if row['state'] in ('running', 'reconciling') and (row['process_json'] or
                    (attempt is not None and attempt['exit_json'] is None)):
                updated = self._request_stop(row, action)
                selected = self._attempt(updated)
                local = self.live.get(row['job_id'])
                if (selected is not None and selected['process_json'] is None and
                        updated['process_json'] is None and (local is None or local.get('settled'))):
                    # A genuinely never-registered/no-current-child stop may
                    # settle immediately; an unobserved local Popen may NOT.
                    state = 'paused' if selected['stop_disposition'] == 'pause' else 'cancelled' if selected['stop_disposition'] == 'cancel' else None
                    if state:
                        self.queue.transition(row['job_id'], state, action + '_requested; no registered process')
            elif action == 'cancel' and row['state'] in ('queued', 'paused'):
                self.discard_prepared(row['job_id'], 'cancel_requested')
            else:
                self.queue.transition(row['job_id'], 'paused' if action == 'pause' else 'cancelled', action + '_requested')

    def discard_prepared(self, job_id, reason='explicit reprepare'):
        """Trusted product helper for paused/queued reprepare, with no OS IO.

        Root's activity.resume must call this instead of a bare cancelled
        queue transition. A pre-registration pause stop needs NEW cancel
        dominance before its paused row may settle cancelled.
        """
        row = self.queue.row(job_id)
        if not row or row['state'] not in ('queued', 'paused'):
            raise Fault('RECONCILE_REQUIRED')
        attempt = self._reconcilable(row)
        if (self._absence(row) is None and attempt is not None and
                attempt['exit_json'] is None and attempt['stop_requested_at'] is not None):
            self.queue.transition(job_id, 'reconciling', reason)
            self._request_stop(self.queue.row(job_id), 'cancel')
        self.queue.transition(job_id, 'cancelled', reason)

    def _absence(self, row):
        if self._attempt(row) is None:
            return None
        return terminal_absence(self.app.engine, self.app.workspace_id,
                                row['job_id'], self.queue.fence(row))

    def _reconcilable(self, row):
        # Called inside or outside a product UoW. It performs ONLY DB/cache
        # reads, never procfs, poll, signal or file IO.
        live = self.live.get(row['job_id'])
        if live is not None and not live.get('settled'):
            raise Fault('BUSY')
        verify_worker_liveness(self.app.engine)
        attempt = self._attempt(row)
        if self._absence(row) is not None:
            return attempt
        if row['process_json'] or (attempt is not None and attempt['process_json'] is not None and attempt['exit_json'] is None):
            raise Fault('BUSY')
        return attempt

    def _output(self, row):
        self._external()
        fd = os.open(self.path(row), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 1000000:
                raise Fault('BUDGET')
            blob = stream.read(1000001)
            after = os.fstat(stream.fileno())
        if ((before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or
                len(blob) != before.st_size):
            raise Fault('RECONCILE_REQUIRED')
        value = strict_object(blob, 1000000)
        if set(value) != {'job_id', 'attempt_generation', 'input_digest', 'text', 'digest'} or not isinstance(value['text'], str):
            raise Fault('RECONCILE_REQUIRED')
        job = self.db.execute('SELECT * FROM activity_jobs WHERE job_id=?', (row['job_id'],)).fetchone()
        prepared = json.loads(job['prepared_json'])
        raw = value['text'].encode('utf-8')
        if (type(value['attempt_generation']) is not int or
                (value['job_id'], value['attempt_generation'], value['input_digest']) !=
                (row['job_id'], job['generation'], prepared['input_ref']['digest']) or
                hashlib.sha256(raw).hexdigest() != value['digest']):
            raise Fault('RECONCILE_REQUIRED')
        return raw, job, prepared

    def _reconciliation_pin(self, context, activity, row):
        job = self.db.execute('SELECT * FROM activity_jobs WHERE job_id=? AND workspace_id=?',
                              (row['job_id'], self.app.workspace_id)).fetchone()
        binding = self.db.execute('SELECT * FROM activity_bindings WHERE binding_id=? AND workspace_id=?',
                                  (row['binding_id'], self.app.workspace_id)).fetchone()
        if job is None or binding is None or job['activity_id'] != activity['activity_id']:
            raise Fault('RECONCILE_REQUIRED')
        registration_digest = None
        registered = self.db.execute('''SELECT 1 FROM activity_worker_registrations
            WHERE workspace_id=? AND job_id=? AND owner_epoch=? AND generation=?''',
            (self.app.workspace_id, row['job_id'], row['owner_epoch'], row['generation'])).fetchone()
        if registered:
            registration_digest = WorkerCustody(self.app.engine, self.app.workspace_id).row(
                row['job_id'], self.queue.fence(row))['registration_digest']
        return encoded({'workspace_id': self.app.workspace_id, 'activity_id': activity['activity_id'],
            'activity_version': activity['version'], 'job_id': row['job_id'],
            'fence': self.queue.fence(row), 'queue_binding': row['binding_id'],
            'queue_authority_epoch': row['authority_epoch'], 'process_json': row['process_json'],
            'queue_state': row['state'], 'binding': dict(binding),
            'registration_digest': registration_digest,
            'operator_binding_record': dict(self.app.authorize(context)),
            'job_digest': hashlib.sha256(encoded(dict(job)).encode()).hexdigest(),
            'operator_binding': context.binding_id, 'operator_principal': context.principal_id,
            'operator_authority_epoch': context.authority_epoch})

    def _registered_custody(self, row):
        stored = WorkerCustody(self.app.engine, self.app.workspace_id).row(
            row['job_id'], self.queue.fence(row))
        registration = validate_registration(json.loads(stored['registration_json']))
        attempt = self._attempt(row)
        if (attempt is None or attempt['process_json'] is None or
                registration['process'] != json.loads(attempt['process_json']) or
                row['process_json'] != attempt['process_json'] or
                registration['registration_digest'] != stored['registration_digest']):
            raise Fault('RECONCILE_REQUIRED')
        return registration

    def prepare_reconciliation(self, context, activity, disposition='discard'):
        """Observe/read outside UoW; return private, exact-fence owner memory."""
        self._external()
        binding = self.app.authorize(context)
        if context.role != 'operator':
            raise Fault('UNAVAILABLE')
        if 'job.reconcile' not in json.loads(binding['grants_json']):
            raise Fault('UNAVAILABLE')
        if disposition not in ('recover', 'discard'):
            raise Fault('INVALID')
        activity = self.app.activity(context, activity['activity_id'])
        row = self.queue.row(activity['native']['job_id'])
        if not row or row['state'] != 'reconciling':
            raise Fault('DEPENDENCY')
        live = self.live.get(row['job_id'])
        if live is not None and not live.get('settled'):
            raise Fault('BUSY')
        verify_worker_liveness(self.app.engine)
        pin = self._reconciliation_pin(context, activity, row)
        registration = observation = None
        attempt = self._attempt(row)
        if (self._absence(row) is None and attempt is not None and
                attempt['process_json'] is not None and attempt['exit_json'] is None):
            # No old033 companion means unresolved, never registration backfill.
            try:
                registration = self._registered_custody(row)
                self._external()
                actual = process_custody.observe_registration(registration)
                observation = process_custody.normalize_identity_absence(actual, registration)
            except (ValueError, KeyError, TypeError, OverflowError):
                raise Fault('RECONCILE_REQUIRED') from None
        else:
            self._reconcilable(row)
        recovered = None
        if disposition == 'recover':
            try:
                recovered = self._output(row)[0]
            except (OSError, ValueError, KeyError, TypeError, UnicodeError):
                raise Fault('RECONCILE_REQUIRED') from None
        # Pin reads again after the actual provider/output operations; there is
        # no queue/process mutation in this preparation phase.
        if self._reconciliation_pin(context, self.app.activity(context, activity['activity_id']),
                                    self.queue.row(row['job_id'])) != pin:
            raise Fault('RECONCILE_REQUIRED')
        return _ReconciliationPreflight(pin, disposition, time.time(),
            encoded(registration) if registration is not None else None,
            encoded(observation) if observation is not None else None, recovered)

    def prepare_recovery(self, context, activity):
        """Legacy trusted helper now returns the same pinned private bundle."""
        return self.prepare_reconciliation(context, activity, 'recover')

    def reconcile(self, context, activity, disposition='discard', prepared=None):
        if not self.db.in_transaction:
            raise RuntimeError('reconciliation requires command transaction')
        binding = self.app.authorize(context)
        if context.role != 'operator':
            raise Fault('UNAVAILABLE')
        if 'job.reconcile' not in json.loads(binding['grants_json']):
            raise Fault('UNAVAILABLE')
        if disposition not in ('recover', 'discard'):
            raise Fault('INVALID')
        if type(prepared) is not _ReconciliationPreflight or prepared.disposition != disposition:
            raise Fault('RECONCILE_REQUIRED')
        activity = self.app.activity(context, activity['activity_id'])
        row = self.queue.row(activity['native']['job_id'])
        if not row or row['state'] != 'reconciling':
            raise Fault('DEPENDENCY')
        if self._reconciliation_pin(context, activity, row) != prepared.pin_json:
            raise Fault('RECONCILE_REQUIRED')
        live = self.live.get(row['job_id'])
        if live is not None and not live.get('settled'):
            raise Fault('BUSY')
        verify_worker_liveness(self.app.engine)
        absence = self._absence(row)
        if prepared.registration_json is not None:
            # This exact companion is immutable; re-read and compare before
            # consuming a provider fact pinned to its registration digest.
            registration = self._registered_custody(row) if absence is None else validate_registration(
                json.loads(WorkerCustody(self.app.engine, self.app.workspace_id).row(
                    row['job_id'], self.queue.fence(row))['registration_json']))
            if encoded(registration) != prepared.registration_json:
                raise Fault('RECONCILE_REQUIRED')
        if prepared.observation_json is not None and absence is None:
            attempt = self._attempt(row)
            if attempt is None or attempt['exit_json'] is not None:
                raise Fault('RECONCILE_REQUIRED')
            if attempt['stop_requested_at'] is None:
                self.queue.request_stop(row['job_id'], self.queue.fence(row), 'shutdown',
                    self._stop_id(row, 'shutdown'), prepared.observed_at)
            WorkerCustody(self.app.engine, self.app.workspace_id).observe_absence(
                row['job_id'], self.queue.fence(row), json.loads(prepared.observation_json), prepared.observed_at)
            row = self.queue.row(row['job_id'])
            absence = self._absence(row)
        attempt = self._reconcilable(row)
        if absence is None and attempt is not None and attempt['exit_json'] is None:
            # Preserve the truthful never-registered/no-current-child route.
            # A terminal absence's first stop disposition is never amended.
            row = self._request_stop(row, 'cancel', now=prepared.observed_at)
        ref = None
        if disposition == 'recover':
            job = self.db.execute('SELECT prepared_json FROM activity_jobs WHERE job_id=?', (row['job_id'],)).fetchone()
            source = json.loads(job['prepared_json'])
            ref = self.app.put(prepared.recovered, 'text/markdown', self.app.key(row['job_id'], 'queue-output'),
                principals=[context.principal_id], activity=activity, source_refs_override=[source['input_ref']])
            cp, version = activity['checkpoint'], activity['version']
            if ref not in cp['result_refs']:
                cp['result_refs'].append(ref)
            cp.update(activity_version=version + 1, resume_condition='Recovered output is unaccepted; explicitly continue or reprepare.')
            activity['native'].setdefault('reconciled_returns', []).append(ref)
            self.app.store.update(self.app.workspace_id, activity['activity_id'], version, cp, activity['native'])
        self.queue.transition(row['job_id'], 'cancelled',
            'explicitly reconciled: stopped pure local recipe; ' + disposition + '; no result acceptance or automatic retry', ref)
        verify_worker_liveness(self.app.engine)
        return self.view(context, activity)

    def _launch(self, row):
        self._external()
        process = output = None
        live = None
        try:
            context = self.context(row)
            validate_recipe(context.role, row['recipe'], json.loads(row['parameters_json']), row['max_seconds'])
            job = self.db.execute('SELECT * FROM activity_jobs WHERE job_id=?', (row['job_id'],)).fetchone()
            prepared = json.loads(job['prepared_json'])
            if prepared['expected_revision'] != self.app.revision():
                # No process was created/registered or task byte delivered.
                # Retain original explicit-reprepare semantics, no fake exit.
                self.queue.transition(row['job_id'], 'paused', 'stale branch; explicitly reprepare')
                return
            self.app.artifact_bytes(context, prepared['input_ref'])
            payload = encoded({'recipe': row['recipe'], 'parameters': json.loads(row['parameters_json']),
                'packet': self.app.packet(prepared), 'input_digest': prepared['input_ref']['digest']}).encode() + b'\n'
            if len(payload) > TASK_LIMIT:
                raise Fault('BUDGET')
            output = self.path(row).open('xb')
            env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8',
                   'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1'}
            process = subprocess.Popen([sys.executable, '-I', str(Path(__file__).with_name('local_worker.py'))],
                stdin=subprocess.PIPE, stdout=output, stderr=subprocess.PIPE,
                env=env, cwd=self.root, start_new_session=True)
            live = {'process': process, 'stream': output, 'started': time.monotonic(),
                'fence': self.queue.fence(row), 'identity': None, 'registered': False,
                'task': payload, 'task_offset': 0, 'events': bytearray(), 'event_eof': False,
                'sequence': 0, 'stop_frame': None, 'stop_sent': False,
                'input_error': False,
                'stop_mono': None, 'forced': False, 'settled': False,
                'stop_candidate': None,
                'returncode': None, 'poll_before_stop': False, 'channel_error': None}
            self.live[row['job_id']] = live
            os.set_blocking(process.stdin.fileno(), False)
            os.set_blocking(process.stderr.fileno(), False)
            identity, tail = launched_identity(process)
            live['identity'] = identity
            registration = process_custody.register_observation(identity)
            observed_at = time.time()
            with UnitOfWork(self.db):
                self.queue.process(row['job_id'], live['fence'], identity, observed_at)
                WorkerCustody(self.app.engine, self.app.workspace_id).register(
                    row['job_id'], live['fence'], registration, observed_at)
            live['registered'] = True
            live['events'].extend(tail)
            # A bounded suffix write, never a potentially blocking .write of
            # the whole task. Registration ALWAYS precedes any task bytes.
            self._pump_input(row, live)
        except Exception as exc:
            if live is not None:
                live['channel_error'] = 'launch interrupted: ' + type(exc).__name__
                # Before durable registration no task bytes were sent. EOF is
                # safe, but actual Popen.poll is still required before releasing
                # the local child charge; no guessed PID kill/exit is used.
                if not live['registered'] and process.stdin and not process.stdin.closed:
                    process.stdin.close()
            elif output is not None:
                output.close()
            self._request_stop(self.queue.row(row['job_id']), 'protocol_error')
            self._drain_unfed_exit(row, live)

    def _drain_unfed_exit(self, row, live):
        self._external()
        if (live is None or live['registered'] or live['task_offset'] != 0
                or not live['process'].stdin.closed):
            return
        # EOF was sent without a task. Observe this owned child's natural
        # exit for at most 100 ms; never signal or shorten first-stop grace.
        # Timeout keeps the local child and its capacity charge untouched.
        try:
            live['process'].wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            return
        self._service_live(self.queue.row(row['job_id']), live)

    def _cache_stop(self, row, live):
        attempt = self._attempt(row)
        if attempt is not None:
            if attempt['stop_requested_at'] is None:
                live['stop_candidate'] = None
                return False
            request_id = attempt['stop_request_id']
            pending = live['stop_candidate']
            if pending is not None and pending[:2] == (attempt['stop_requested_at'], request_id):
                candidate = pending[2] + STOP_GRACE
            else:
                # Restart/no cached first observation: honor persisted wall
                # deadline/floor, never start a fresh five seconds from now.
                wall_floor = max(time.time(), self.queue.owner()['last_wall'])
                remaining = max(0.0, min(STOP_GRACE, attempt['stop_deadline'] - wall_floor))
                candidate = time.monotonic() + remaining
        elif row['state'] == 'reconciling':
            request_id = self._stop_id(row, 'shutdown')
            pending = live['stop_candidate']
            candidate = pending[2] + STOP_GRACE if pending else time.monotonic() + STOP_GRACE
        else:
            live['stop_candidate'] = None
            return False
        live['stop_mono'] = candidate if live['stop_mono'] is None else min(live['stop_mono'], candidate)
        if live['stop_frame'] is None:
            live['stop_frame'] = encoded({'kind': 'stop', 'request_id': request_id}).encode() + b'\n'
            if len(live['stop_frame']) > EVENT_LIMIT:
                raise RuntimeError('stop control exceeds channel bound')
        return True

    def _pump_input(self, row, live):
        self._external()
        process = live['process']
        if not live['registered'] or live['input_error'] or process.stdin.closed:
            return
        stopping = self._cache_stop(row, live)
        try:
            offset = live['task_offset']
            if offset < len(live['task']):
                sent = os.write(process.stdin.fileno(), live['task'][offset:offset + WRITE_QUANTUM])
                if sent <= 0:
                    raise BrokenPipeError('task channel made no progress')
                live['task_offset'] += sent
            if (stopping and not live['stop_sent'] and live['task_offset'] == len(live['task'])):
                frame = live['stop_frame']
                if os.write(process.stdin.fileno(), frame) != len(frame):
                    raise BrokenPipeError('partial atomic stop frame')
                live['stop_sent'] = True
        except BlockingIOError:
            return
        except OSError as exc:
            live['input_error'] = True
            live['channel_error'] = 'input channel: ' + type(exc).__name__
            self._request_stop(self.queue.row(row['job_id']), 'protocol_error')

    def _pump_events(self, row, live):
        self._external()
        if live['channel_error']:
            return
        try:
            if not live['event_eof']:
                try:
                    chunk = os.read(live['process'].stderr.fileno(), EVENT_LIMIT + 1 - len(live['events']))
                except BlockingIOError:
                    chunk = None
                if chunk == b'':
                    live['event_eof'] = True
                elif chunk is not None:
                    live['events'].extend(chunk)
            while b'\n' in live['events']:
                split = live['events'].find(b'\n') + 1
                frame = bytes(live['events'][:split])
                value = strict_object(frame, EVENT_LIMIT)
                if (set(value) != {'kind', 'sequence'} or value['kind'] != 'heartbeat' or
                        type(value['sequence']) is not int or value['sequence'] != live['sequence'] + 1):
                    raise ValueError('worker event sequence/shape')
                current = self.queue.row(row['job_id'])
                attempt = self._attempt(current)
                if current['state'] == 'running' and attempt is not None and attempt['stop_requested_at'] is None:
                    # NO enclosing UoW: native rollback reconciliation must
                    # remain committed even when this heartbeat raises.
                    self.queue.heartbeat(row['job_id'], live['fence'], value['sequence'], time.time())
                # Full framed event consumed. In stopped/legacy paths this is
                # only channel sequence tracking, NEVER lease authority. Read
                # current queue/attempt again; old receipts cannot lower lease.
                live['sequence'] = value['sequence']
                del live['events'][:split]
            if len(live['events']) >= EVENT_LIMIT or (live['event_eof'] and live['events']):
                raise ValueError('worker event overflow/partial EOF')
        except Exception as exc:
            live['channel_error'] = 'event channel: ' + type(exc).__name__
            self._request_stop(self.queue.row(row['job_id']), 'protocol_error')

    def _guarded_kill(self, observation):
        self._external()
        if not observation or not alive(observation):
            return False
        if observation['pid_namespace'] != os.readlink('/proc/self/ns/pid'):
            return False
        try:
            if os.getpgid(observation['pid']) != observation['pid']:
                return False
            descriptor = os.pidfd_open(observation['pid'])
        except (AttributeError, OSError):
            return False
        try:
            info = dict(line.split(':', 1) for line in Path(f'/proc/self/fdinfo/{descriptor}').read_text().splitlines() if ':' in line)
            if (int(info['Pid']) != observation['proc_pid'] or
                    int(info['NSpid'].split()[-1]) != observation['pid'] or not alive(observation)):
                return False
            signal.pidfd_send_signal(descriptor, signal.SIGKILL)
            return True
        except (AttributeError, KeyError, ValueError, OSError):
            return False
        finally:
            os.close(descriptor)

    def _observe_terminal(self, row, live):
        self._external()
        if live['returncode'] is None:
            raise RuntimeError('terminal observation without actual Popen.poll')
        attempt = self._attempt(row)
        if attempt is not None and attempt['process_json'] is not None:
            if live['identity'] != json.loads(attempt['process_json']):
                raise Fault('RECONCILE_REQUIRED')
            if live['poll_before_stop']:
                method = 'exited_before_stop'
            elif live['forced'] and live['returncode'] == -signal.SIGKILL:
                method = 'forced'
            elif live['stop_sent'] and live['returncode'] == 20:
                method = 'cooperative'
            else:
                # Root-adopted method; final native integration must add it.
                method = 'exited_after_stop'
            self.queue.observe_exit(row['job_id'], live['fence'],
                {'process': live['identity'], 'exited': True,
                 'returncode': live['returncode'], 'method': method}, time.time())
        elif attempt is not None:
            if row['process_json'] is not None:
                raise Fault('RECONCILE_REQUIRED')
            # Native pre-registration exception, AFTER the actual local child
            # has exited. Never fabricate an identity or an exit receipt.
            if attempt['stop_requested_at'] is None:
                row = self._request_stop(row, 'protocol_error')
                attempt = self._attempt(row)
            state = 'paused' if attempt['stop_disposition'] == 'pause' else 'cancelled' if attempt['stop_disposition'] == 'cancel' else 'reconciling'
            self.queue.transition(row['job_id'], state, 'unregistered child exited; no native exit identity invented')
        else:
            # True legacy attempt: retain old fixed lease semantics, but only
            # this actual local Popen observation permits process clearing.
            state = 'paused' if row['reason'] == 'pause_requested' else 'cancelled' if row['reason'] == 'cancel_requested' else 'reconciling'
            self.queue.transition(row['job_id'], state, row['reason'], clear_process=True)
        live['settled'] = True

    def _close_handles(self, live):
        self._external()
        for stream in (live['process'].stdin, live['process'].stderr, live['stream']):
            if stream and not stream.closed:
                stream.close()

    def _finish(self, row, live):
        self._external()
        ref = None
        try:
            if live['returncode'] != 0 or live['channel_error']:
                raise Fault('DEPENDENCY')
            self.queue.assert_lease(row['job_id'], live['fence'], time.time())
            context = self.context(row)
            raw, job, prepared = self._output(row)
            activity = self.app.activity(context, job['activity_id'])
            with UnitOfWork(self.db):
                self.queue.assert_lease(row['job_id'], live['fence'], time.time())
                ref = self.app.put(raw, 'text/markdown', self.app.key(row['job_id'], 'queue-output'),
                    principals=[context.principal_id], activity=activity, source_refs_override=[prepared['input_ref']])
            with UnitOfWork(self.db):
                self.queue.assert_lease(row['job_id'], live['fence'], time.time())
                result = {'dispatch_id': prepared['dispatch_id'], 'job_id': row['job_id'],
                    'attempt_generation': job['generation'], 'input_digest': prepared['input_ref']['digest'],
                    'status': 'returned', 'output_refs': [ref], 'check_results': [],
                    'effect_refs': [], 'tool_receipt_refs': [], 'failure_code': None}
                self.app._receive(context, result, queue_fence=live['fence'])
                # Narrow native033 no-stop, identical registered identity
                # exception. Stop/reconciling cleanup NEVER uses this path.
                self.queue.transition(row['job_id'], 'returned', 'component returned; purpose unresolved', ref, clear_process=True)
            live['settled'] = True
        except Exception as exc:
            reason = getattr(exc, 'code', type(exc).__name__) + ('; output retained' if ref else '; explicit disposition required')
            self.queue.transition(row['job_id'], 'reconciling', reason, ref)
            self._observe_terminal(self.queue.row(row['job_id']), live)
            # Native exit records truthful process settlement. Keep the
            # already established result diagnostic/retained-output reason;
            # an exit observation must not erase STALE or its useful cause.
            if self.queue.row(row['job_id'])['state'] == 'reconciling':
                self.queue.transition(row['job_id'], 'reconciling', reason, ref)

    def _service_live(self, row, live):
        self._external()
        if live.get('settlement_error'):
            return
        attempt = self._attempt(row)
        if (row['state'] == 'reconciling' and attempt is not None and
                attempt['stop_requested_at'] is None and attempt['exit_json'] is None):
            # Native clock-rollback reconciliation (for example from claim)
            # can precede a product stop. Never let that state bypass both
            # heartbeat acceptance and monotonic stop/ceiling supervision.
            row = self._request_stop(row, 'protocol_error')
        self._pump_events(row, live)
        row = self.queue.row(row['job_id'])
        attempt = self._attempt(row)
        if row['state'] == 'running':
            revoked = False
            try:
                self.context(row)
            except Fault:
                revoked = True
            wall, mono = time.time(), time.monotonic()
            reason = ('authority_revoked' if revoked else
                'execution_expired' if ((attempt is not None and wall >= attempt['execution_until']) or
                                        mono - live['started'] >= row['max_seconds']) else
                'lease_expired' if wall >= row['lease_until'] else None)
            if reason:
                row = self._request_stop(row, reason)
        self._pump_input(row, live)
        row = self.queue.row(row['job_id'])
        stopping = self._cache_stop(row, live)
        code = live['process'].poll()
        if code is None:
            if stopping and live['stop_mono'] is not None and time.monotonic() >= live['stop_mono']:
                if not live['forced']:
                    live['forced'] = self._guarded_kill(live['identity'])
            return
        if live['returncode'] is None:
            live['returncode'] = code
            current_attempt = self._attempt(row)
            live['poll_before_stop'] = (current_attempt is not None and current_attempt['stop_requested_at'] is None)
        if not live['stream'].closed:
            live['stream'].close()
        # Drain bounded residual stderr over ticks before successful acceptance.
        if not live['event_eof'] and not live['channel_error']:
            self._pump_events(row, live)
            if not live['event_eof']:
                return
        row = self.queue.row(row['job_id'])
        attempt = self._attempt(row)
        try:
            if (row['state'] == 'running' and not live['channel_error'] and
                    (attempt is None or attempt['stop_requested_at'] is None)):
                self._finish(row, live)
            else:
                self._observe_terminal(row, live)
        except Exception as exc:
            # Preserve the exact Popen observation and native/process charge;
            # never invent a second settlement or clear an unknown process.
            live['settlement_error'] = getattr(exc, 'code', type(exc).__name__)
        if live['settled']:
            self._close_handles(live)
            del self.live[row['job_id']]

    def _service_historical(self, row):
        self._external()
        if not row['process_json']:
            return
        attempt = self._attempt(row)
        first_here = False
        observed_mono = time.monotonic()
        if attempt is not None and attempt['stop_requested_at'] is None:
            row = self._request_stop(row, 'shutdown')
            attempt = self._attempt(row)
            first_here = True
        if attempt is not None:
            key = (row['job_id'], row['owner_epoch'], row['generation'], row['lease_token'])
            if key not in self.historical_stops:
                wall = time.time()
                first = self.db.execute('''SELECT receipt_json FROM activity_worker_stops
                    WHERE job_id=? AND owner_epoch=? AND generation=? AND request_id=?''',
                    (row['job_id'], row['owner_epoch'], row['generation'], attempt['stop_request_id'])).fetchone()
                if first is None:
                    raise Fault('RECONCILE_REQUIRED')
                first_receipt = json.loads(first['receipt_json'])
                uncertain_clock = (first_receipt['clock_rollback'] or
                    wall < self.queue.owner()['last_wall'] or wall < attempt['stop_requested_at'])
                # An ahead durable floor is a fencing high-water, NOT proof
                # that five actual seconds elapsed after this new stop.
                remaining = STOP_GRACE if first_here or uncertain_clock else max(0.0, min(STOP_GRACE, attempt['stop_deadline'] - wall))
                self.historical_stops[key] = observed_mono + remaining
            # Even an elapsed local safety observation is NOT host custody.
            # Four historical PID/ns/start fields carry no boot/host proof
            # after relocation. Without a PRESENT owned Popen, do not signal.
        # No current Popen/wait result: even absent procfs or a stopped PID is
        # NOT a known exit code. Retain native identity/slot and uncertainty.

    def _service(self):
        self._external()
        rows = {r['job_id']: r for r in self.queue.rows(live_only=True)}
        # Include pre-registration local children whose product control moved
        # their native row out of the live query. They still cost a local slot.
        for job_id in self.live:
            rows.setdefault(job_id, self.queue.row(job_id))
        for row in rows.values():
            if row['job_id'] in self.live:
                self._service_live(row, self.live[row['job_id']])
            elif row['state'] == 'running':
                self._request_stop(row, 'shutdown')
                self._service_historical(self.queue.row(row['job_id']))
            elif row['state'] == 'reconciling':
                self._service_historical(row)

    def tick(self):
        self._external()
        self._service()
        if self.closing:
            return
        # An actual unregistered/illicitly uncharged local child must not allow
        # a native pre-registration exception to multiply OS process capacity.
        if any(not x['registered'] or self.queue.row(job)['process_json'] is None
               for job, x in self.live.items()):
            return
        for _ in range(ResourceProfiles(self.app.engine, self.app.workspace_id).get()['active_jobs']):
            row = self.queue.claim(time.time())
            if not row:
                break
            self._launch(row)
            if any(not x['registered'] for x in self.live.values()):
                break

    def close(self):
        self._external()
        self.closing = True
        wall, mono = time.time(), time.monotonic()
        shared_deadline = mono + STOP_GRACE
        for row in self.queue.rows(live_only=True):
            if row['state'] in ('running', 'reconciling'):
                self._request_stop(row, 'shutdown', now=wall, mono=mono)
        # One shared drain deadline for ALL children, never five per child.
        while self.live and time.monotonic() < shared_deadline:
            self._service()
            remaining = shared_deadline - time.monotonic()
            if remaining > 0 and self.live:
                time.sleep(min(POLL_QUANTUM, remaining))
        # Guarded escalation uses each attempt's first fixed grace, then a
        # final nonblocking observation. No wait(timeout=5) multiplication.
        self._service()
        for job_id, live in list(self.live.items()):
            row = self.queue.row(job_id)
            if (live['returncode'] is None and live['process'].poll() is None and
                    live['stop_mono'] is not None and time.monotonic() >= live['stop_mono']):
                if not live['forced']:
                    live['forced'] = self._guarded_kill(live['identity'])
            self._service_live(row, live)
        # One shared scheduler yield and bounded final observation, not a new
        # per-child grace/wait. A child not actually reaped remains uncertain.
        if self.live:
            time.sleep(0)
            self._service()
        # Closing owned descriptors does not fabricate an exit or native
        # release. Known durable process/attempt uncertainty remains retained.
        for live in self.live.values():
            self._close_handles(live)
