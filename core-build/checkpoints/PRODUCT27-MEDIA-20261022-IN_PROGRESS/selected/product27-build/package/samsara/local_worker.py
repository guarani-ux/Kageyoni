"""Trusted built-in local work with a checkpoint-only worker channel.

No user code, network, engine access, credentials or model API. This producer
alone establishes no host isolation, lease renewal, graceful stop or release.
The owner must retain stdin/stderr and fence every observed event/result.
"""
import hashlib
import json
import math
import os
import resource
import select
import sys
import time

MAX_TASK_FRAME = 800000  # Entire JSON line, INCLUDING LF.
MAX_CHANNEL_FRAME = 256  # Entire control/heartbeat line, INCLUDING LF.
READ_QUANTUM = 65536
CHECKPOINT_SECONDS = 0.05
HASH_QUANTUM = 4096
HEARTBEAT_SECONDS = 10.0

EXIT_STOP = 20
EXIT_DETACHED = 21
EXIT_PROTOCOL = 22
EXIT_UNCERTAIN = 23


class WorkerExit(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _invalid():
    raise WorkerExit(EXIT_PROTOCOL)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def _constant(_value):
    _invalid()


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        _invalid()
    return number


def decode_frame(frame, maximum):
    """One strictly decoded object, bounded including its sole trailing LF."""
    if (not isinstance(frame, bytes) or not frame.endswith(b'\n') or
            len(frame) > maximum or b'\n' in frame[:-1]):
        _invalid()
    try:
        value = json.loads(frame[:-1].decode('utf-8'),
                           object_pairs_hook=_unique_object, parse_constant=_constant,
                           parse_float=_finite_float)
    except (ValueError, UnicodeError, RecursionError):
        _invalid()
    if not isinstance(value, dict):
        _invalid()
    return value


def read_task(fd, *, reader=os.read, poll=select.select):
    """Read one task line without waiting for EOF; retain a bounded control tail."""
    buffer = bytearray()
    while True:
        try:
            ready = poll([fd], [], [], CHECKPOINT_SECONDS)[0]
            if not ready:
                continue
            chunk = reader(fd, min(READ_QUANTUM, MAX_TASK_FRAME + 1 - len(buffer)))
        except BlockingIOError:
            continue
        except OSError:
            raise WorkerExit(EXIT_UNCERTAIN) from None
        if not chunk:
            raise WorkerExit(EXIT_DETACHED)
        buffer.extend(chunk)
        split = buffer.find(b'\n')
        if split >= 0:
            frame = bytes(buffer[:split + 1])
            tail = bytes(buffer[split + 1:])
            if len(tail) > MAX_CHANNEL_FRAME:
                _invalid()
            return decode_frame(frame, MAX_TASK_FRAME), tail
        if len(buffer) >= MAX_TASK_FRAME:
            _invalid()


def _bounded_number(value, maximum):
    return (type(value) in (int, float) and 0 <= value <= maximum and
            math.isfinite(value))


def _bounded_count(value):
    return type(value) is int and 0 <= value <= 1000000


def validate_task(value):
    """Defense in depth; operator authority/max_seconds remain owner-owned."""
    if not isinstance(value, dict) or set(value) != {'recipe', 'parameters', 'packet', 'input_digest'}:
        _invalid()
    recipe, parameters, packet = value['recipe'], value['parameters'], value['packet']
    if not isinstance(parameters, dict) or not isinstance(packet, dict):
        _invalid()
    if recipe in ('source_index', 'bounded_probe'):
        if (set(parameters) != {'delay_seconds', 'cpu_iterations'} or
                not _bounded_number(parameters['delay_seconds'], 3) or
                not _bounded_count(parameters['cpu_iterations'])):
            _invalid()
        if recipe == 'source_index' and any(parameters.values()):
            _invalid()
        heartbeats, cooperative_stop = True, True
    elif recipe == 'liveness_probe':
        if (set(parameters) != {'delay_seconds', 'cpu_iterations', 'heartbeats', 'cooperative_stop'} or
                not _bounded_number(parameters['delay_seconds'], 90) or
                not _bounded_count(parameters['cpu_iterations']) or
                type(parameters['heartbeats']) is not bool or
                type(parameters['cooperative_stop']) is not bool):
            _invalid()
        heartbeats = parameters['heartbeats']
        cooperative_stop = parameters['cooperative_stop']
    else:
        _invalid()
    digest = value['input_digest']
    if (not isinstance(digest, str) or len(digest) != 64 or
            any(c not in '0123456789abcdef' for c in digest)):
        _invalid()
    if (not isinstance(packet.get('job_id'), str) or not packet['job_id'].strip() or
            type(packet.get('attempt_generation')) is not int or packet['attempt_generation'] <= 0 or
            not isinstance(packet.get('input'), dict) or
            not isinstance(packet['input'].get('sources'), list) or
            not isinstance(packet['input'].get('objective'), str)):
        _invalid()
    return heartbeats, cooperative_stop


def decode_stop(frame):
    value = decode_frame(frame, MAX_CHANNEL_FRAME)
    if (set(value) != {'kind', 'request_id'} or value['kind'] != 'stop' or
            not isinstance(value['request_id'], str) or not value['request_id'].strip()):
        _invalid()
    return value['request_id']


class WorkerChannel:
    """Nonblocking bounded IO at actual checkpoints; no timer thread or ACK."""
    def __init__(self, input_fd, event_fd, *, initial_control=b'', clock=time.monotonic,
                 reader=os.read, writer=os.write, poll=select.select):
        if len(initial_control) > MAX_CHANNEL_FRAME:
            _invalid()
        self.input_fd, self.event_fd = input_fd, event_fd
        self.clock, self.reader, self.writer, self.poll = clock, reader, writer, poll
        self.buffer = bytearray(initial_control)
        self.sequence = 0
        self.last_heartbeat = clock()
        self.heartbeats = True
        self.cooperative_stop = True
        self.ignored_stop = False
        self.stop_request_id = None
        self.uncertain = False

    def _controls(self):
        while b'\n' in self.buffer:
            split = self.buffer.find(b'\n')
            frame = bytes(self.buffer[:split + 1])
            del self.buffer[:split + 1]
            request_id = decode_stop(frame)
            self.stop_request_id = request_id
            if self.cooperative_stop:
                raise WorkerExit(EXIT_STOP)
            # Known adverse diagnostic only. Silence liveness once ignoring a
            # stop, never emit a successful result or an acknowledgment for it.
            self.ignored_stop = True
        if len(self.buffer) >= MAX_CHANNEL_FRAME:
            _invalid()

    def _read_controls(self):
        self._controls()
        try:
            if not self.poll([self.input_fd], [], [], 0)[0]:
                return
            chunk = self.reader(self.input_fd, MAX_CHANNEL_FRAME + 1 - len(self.buffer))
        except BlockingIOError:
            return
        except OSError:
            self.uncertain = True
            raise WorkerExit(EXIT_UNCERTAIN) from None
        if not chunk:
            raise WorkerExit(EXIT_DETACHED)
        self.buffer.extend(chunk)
        self._controls()

    def _heartbeat(self, now):
        sequence = self.sequence + 1
        frame = json.dumps({'kind': 'heartbeat', 'sequence': sequence},
                           separators=(',', ':')).encode('ascii') + b'\n'
        if len(frame) > MAX_CHANNEL_FRAME:
            _invalid()
        try:
            # <=256 bytes on the pipe, below POSIX PIPE_BUF. Nonblocking pipe
            # writes are whole-frame or EAGAIN; a short result is terminal too.
            sent = self.writer(self.event_fd, frame)
        except OSError:
            self.uncertain = True
            raise WorkerExit(EXIT_UNCERTAIN) from None
        if sent != len(frame):
            self.uncertain = True
            raise WorkerExit(EXIT_UNCERTAIN)
        self.sequence = sequence  # Advance ONLY after the complete frame.
        self.last_heartbeat = now  # Never manufacture catch-up heartbeats.

    def checkpoint(self):
        if self.uncertain:
            raise WorkerExit(EXIT_UNCERTAIN)
        self._read_controls()  # Observed EOF/stop wins over liveness emission.
        now = self.clock()
        if now < self.last_heartbeat:
            _invalid()
        if self.heartbeats and not self.ignored_stop and now - self.last_heartbeat >= HEARTBEAT_SECONDS:
            self._heartbeat(now)

    def sleep(self, seconds):
        deadline = self.clock() + seconds
        while True:
            self.checkpoint()
            remaining = deadline - self.clock()
            if remaining <= 0:
                return
            try:
                self.poll([self.input_fd], [], [], min(CHECKPOINT_SECONDS, remaining))
            except OSError:
                self.uncertain = True
                raise WorkerExit(EXIT_UNCERTAIN) from None

    def before_result(self):
        self.checkpoint()
        while self.ignored_stop:
            # Intentional adverse worker: no output/heartbeat after ignored
            # stop. Owner retains its pipe and enforces the immutable <=120s
            # attempt ceiling and guarded escalation. EOF STILL detaches.
            self.sleep(CHECKPOINT_SECONDS)


def produce_result(value, channel):
    heartbeats, cooperative_stop = validate_task(value)
    channel.heartbeats = heartbeats
    channel.cooperative_stop = cooperative_stop
    packet = value['packet']
    sources = packet['input']['sources']
    channel.checkpoint()
    if value['recipe'] in ('bounded_probe', 'liveness_probe'):
        channel.sleep(value['parameters']['delay_seconds'])
        count = value['parameters']['cpu_iterations']
        v = b'synthetic bounded load'
        for start in range(0, count, HASH_QUANTUM):
            channel.checkpoint()
            for _ in range(min(HASH_QUANTUM, count - start)):
                v = hashlib.sha256(v).digest()
        channel.checkpoint()
    lines = ['# Admitted source index', '', packet['input']['objective'], '',
        'This index identifies the exact supplied sources for recipient review. It does not corroborate their claims.', '']
    for i, source in enumerate(sources, 1):
        channel.checkpoint()
        if (not isinstance(source, dict) or not isinstance(source.get('reference'), dict) or
                not isinstance(source.get('text'), str)):
            _invalid()
        ref = source['reference']
        raw = source['text'].encode('utf-8')
        # Matches the existing text-work producer's bounded-source contract.
        if len(raw) > 100000 or hashlib.sha256(raw).hexdigest() != ref.get('digest'):
            _invalid()
        lines += [f"{i}. {ref['id']} (version {ref['version']})", f"   SHA256: {ref['digest']}",
                  f"   UTF-8 bytes: {len(raw)}; lines: {len(source['text'].splitlines())}", '']
    lines += ['Limit: deterministic source inventory only; interpretation and native acceptance remain open.',
              'Next action: retrieve each cited source and evaluate what the parent assignment still needs.', '']
    text = '\n'.join(lines)
    channel.before_result()
    return {'job_id': packet['job_id'], 'attempt_generation': packet['attempt_generation'],
        'input_digest': value['input_digest'], 'text': text,
        'digest': hashlib.sha256(text.encode()).hexdigest()}


def main():
    try:
        # EXACT existing first identity shape, before task bytes or work.
        print(json.dumps({'pid': os.getpid(), 'proc_pid': int(os.readlink('/proc/self')),
            'pid_namespace': os.readlink('/proc/self/ns/pid')}), file=sys.stderr, flush=True)
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1000000, 1000000))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        input_fd, event_fd = sys.stdin.fileno(), sys.stderr.fileno()
        os.set_blocking(input_fd, False)
        os.set_blocking(event_fd, False)
        value, tail = read_task(input_fd)
        channel = WorkerChannel(input_fd, event_fd, initial_control=tail)
        result = produce_result(value, channel)
        channel.before_result()
        # Stdout is one existing-format final object, never channel events.
        frame = (json.dumps(result, ensure_ascii=False) + '\n').encode('utf-8')
        if len(frame) > 1000000:
            _invalid()
        if os.write(sys.stdout.fileno(), frame) != len(frame):
            return EXIT_UNCERTAIN
        return 0
    except WorkerExit as exc:
        return exc.code
    except OSError:
        return EXIT_UNCERTAIN
    except (Exception, KeyboardInterrupt):
        # No generic stderr logs or traceback/data leaks on the event stream.
        return EXIT_PROTOCOL


if __name__ == '__main__':
    raise SystemExit(main())
