"""Actual procfs provider with the one authoritative native custody schema.

Facts only: no signal, wait, invented exit code or native custody release.
Only a trusted owner may use actual provider returns. Digests bind bytes and
never authenticate a participant-supplied observation. All provider I/O must
run outside a native UnitOfWork; normalizing an absence performs no I/O.
"""
import errno
import os
import stat
import time

from kageyoni.workspaces.custody_schema import (
    SCHEMA_VERSION, REGISTRATION_LIMIT, FIELD_LIMIT, MOUNTINFO_LIMIT,
    MIN_INTERVAL_NS, PROVIDER, CustodySchemaError, validate_absence,
    validate_registration, decode_registration, _PROCESS_KEYS, _DOMAIN_KEYS,
    _REGISTRATION_KEYS, _STATES, _HASH, _POSITIVE, _PID_NS, _MOUNT_NS,
    _MOUNT_FLAGS, _SUPER_FLAGS, _fail, _positive, _canonical, _digest,
    _validate_process, _parse_mount, _ordinary_proc, _validate_proc_view,
    _validate_domain, _validated_registration,
)

# One rich error type across pure validation and actual provider I/O.
ObservationUnavailable = CustodySchemaError

def _mount_table(text):
    if type(text) is not str or len(text.encode('utf-8')) > MOUNTINFO_LIMIT:
        _fail('mountinfo_read_limit')
    # Kernel mountinfo uses LF; splitlines would silently normalize malformed
    # CR/vertical separators before the strict per-line parser could see them.
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    if not lines or len(lines) > 16384:
        _fail('invalid_mountinfo_count')
    ids = set(); points = set(); selected = []; descendants = []
    for line in lines:
        mount = _parse_mount(line)
        # Structurally valid stacked sibling mounts (e.g. /dev) cannot
        # mask the canonical /proc view. Keep globally unique IDs and reject
        # every ambiguous root/proc/descendant path before any observation.
        relevant = (mount['point'] == '/' or mount['point'] == '/proc' or
                    mount['point'].startswith('/proc/'))
        if mount['id'] in ids or (relevant and mount['point'] in points):
            _fail('duplicate_or_ambiguous_mount')
        ids.add(mount['id']); points.add(mount['point'])
        if mount['point'] == '/proc':
            selected.append(line)
        elif mount['point'].startswith('/proc/'):
            descendants.append(line)
    if len(selected) != 1:
        _fail('missing_or_ambiguous_proc_mount')
    descendants.sort()
    _validate_proc_view(selected[0], descendants)
    return selected[0], descendants

def _read(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    try:
        chunks = []; size = 0
        while True:
            part = os.read(fd, min(65536, limit + 1 - size))
            if not part:
                break
            chunks.append(part); size += len(part)
            if size > limit:
                _fail('proc_read_limit')
        data = b''.join(chunks)
    finally:
        os.close(fd)
    try:
        return data.decode('utf-8', errors='strict')
    except UnicodeError:
        _fail('proc_decode_error')

def _status(text):
    result = {}
    for line in text.splitlines():
        if ':' not in line:
            _fail('proc_status_parse_error')
        key, value = line.split(':', 1)
        if not key or key in result:
            _fail('proc_status_duplicate_or_empty_key')
        result[key] = value.strip()
    if not {'Pid', 'NSpid', 'State'} <= set(result):
        _fail('proc_status_missing_fields')
    return result

def _parse_process(proc_pid, text, status, namespace):
    # comm may contain ')' or spaces. The final ')' precedes Linux fixed fields.
    end = text.rfind(')')
    if end < 0 or not text.startswith(str(proc_pid) + ' ('):
        _fail('proc_stat_parse_error')
    fields = text[end+1:].split()
    if len(fields) < 20 or fields[0] not in _STATES or not _POSITIVE.fullmatch(fields[19]):
        _fail('proc_stat_fields_error')
    values = _status(status)
    if not _POSITIVE.fullmatch(values['Pid']) or int(values['Pid']) != proc_pid:
        _fail('proc_pid_mapping_mismatch')
    chain = values['NSpid'].split()
    if not chain or any(not _POSITIVE.fullmatch(x) for x in chain):
        _fail('proc_nspid_parse_error')
    chain = [int(x) for x in chain]
    if chain[0] != proc_pid:
        _fail('proc_pid_mapping_mismatch')
    if not values['State'] or values['State'].split()[0] != fields[0]:
        _fail('proc_state_disagreement')
    if not _PID_NS.fullmatch(namespace):
        _fail('proc_namespace_parse_error')
    return {'process': {'pid': chain[-1], 'proc_pid': proc_pid,
                        'pid_namespace': namespace, 'start_ticks': fields[19]},
            'state': fields[0]}

def _read_process(proc_pid):
    root = '/proc/' + str(proc_pid)
    return _parse_process(proc_pid, _read(root+'/stat', FIELD_LIMIT),
                          _read(root+'/status', FIELD_LIMIT), os.readlink(root+'/ns/pid'))

def _capture_domain():
    # Validate actual self mapping every capture; do not compare reader PID across Owners.
    raw_self = os.readlink('/proc/self')
    if not _POSITIVE.fullmatch(raw_self):
        _fail('reader_proc_pid_parse_error')
    reader = _read_process(int(raw_self))
    if reader['process']['pid'] != os.getpid() or reader['state'] == 'Z':
        _fail('reader_pid_mapping_mismatch')
    pid_ns = os.readlink('/proc/self/ns/pid')
    if pid_ns != reader['process']['pid_namespace']:
        _fail('reader_namespace_race')
    root = os.stat('/proc')
    if not stat.S_ISDIR(root.st_mode):
        _fail('proc_root_not_directory')
    root_line, descendants = _mount_table(_read('/proc/self/mountinfo', MOUNTINFO_LIMIT))
    return _validate_domain({'boot_id': _read('/proc/sys/kernel/random/boot_id', 128).strip(),
        'reader_pid_namespace': pid_ns, 'mount_namespace': os.readlink('/proc/self/ns/mnt'),
        'proc_root_device': root.st_dev, 'proc_root_inode': root.st_ino,
        'proc_mountinfo': root_line, 'proc_submounts': descendants})

def _error_reason(error, context):
    if isinstance(error, ObservationUnavailable):
        return error.reason
    if isinstance(error, PermissionError):
        return context + '_permission_denied'
    if isinstance(error, FileNotFoundError):
        return context + '_file_disappearance'
    if isinstance(error, OSError):
        return context + '_oserror_' + str(error.errno)
    return context + '_parse_error'

def register_observation(process_identity):
    """Bind only a positively present, non-zombie identity to a complete domain.

    Raises ObservationUnavailable on uncertainty; an absent old identity cannot
    be retroactively registered. No process control or native state is changed.
    """
    process = _validate_process(process_identity)
    try:
        domain_before = _capture_domain()
        first = _read_process(process['proc_pid'])
        domain_middle = _capture_domain()
        second = _read_process(process['proc_pid'])
        domain_after = _capture_domain()
        if domain_before != domain_middle or domain_middle != domain_after:
            _fail('domain_changed_during_registration')
        if process['pid_namespace'] != domain_before['reader_pid_namespace']:
            _fail('registration_namespace_mismatch')
        if first['process'] != process or second['process'] != process:
            _fail('registration_identity_mismatch')
        if first['state'] == 'Z' or second['state'] == 'Z':
            _fail('registration_zombie')
        base = {'schema_version': SCHEMA_VERSION, 'process': process, 'domain': domain_before,
                'domain_digest': _digest(domain_before)}
        return {**base, 'registration_digest': _digest(base)}
    except (OSError, ValueError, IndexError, KeyError, TypeError, OverflowError) as error:
        if isinstance(error, ObservationUnavailable):
            raise
        raise ObservationUnavailable(_error_reason(error, 'registration')) from error

def _clock():
    value = time.monotonic_ns()
    if type(value) is not int or value < 0:
        _fail('invalid_local_monotonic')
    return value

def _sample(process):
    path = '/proc/' + str(process['proc_pid'])
    try:
        directory = os.stat(path)
    except FileNotFoundError as error:
        # Only this exact operation, not stat/status/ns reads, can establish a sample.
        if error.errno == errno.ENOENT:
            return {'status': 'directory_enoent', 'observed_monotonic_ns': _clock()}
        raise
    if not stat.S_ISDIR(directory.st_mode):
        _fail('pid_path_not_directory')
    current = _read_process(process['proc_pid'])
    timestamp = _clock()
    if current['process'] != process:
        return {'status': 'identity_changed', 'observed_monotonic_ns': timestamp,
                'observed_process': current['process'], 'state': current['state']}
    return {'status': 'zombie' if current['state'] == 'Z' else 'present',
            'observed_monotonic_ns': timestamp, 'state': current['state']}

def observe_registration(registration):
    """Return present/zombie/identity_changed/identity_absent/unknown facts only.

    identity_absent means two same-domain PID-directory ENOENT observations.
    It never means an integer exit code, accepted work, or elapsed stop grace.
    """
    result = {'status': 'unknown', 'reason': None, 'registration_digest': None,
              'returncode': None, 'samples': []}
    context = 'registration'
    try:
        record = _validated_registration(registration)
        result['registration_digest'] = record['registration_digest']
        domain = record['domain']; process = record['process']
        def same_domain():
            if _capture_domain() != domain:
                _fail('domain_mismatch')
        context = 'domain'; same_domain()
        context = 'process'; first = _sample(process); result['samples'].append(first)
        context = 'domain'; same_domain()
        if first['status'] != 'directory_enoent':
            result.update(status=first['status'], reason='positive_process_observation')
            return result
        context = 'local_interval'; time.sleep(MIN_INTERVAL_NS / 1_000_000_000)
        context = 'domain'; same_domain()
        context = 'process'; second = _sample(process); result['samples'].append(second)
        context = 'domain'; same_domain()
        if second['observed_monotonic_ns'] - first['observed_monotonic_ns'] < MIN_INTERVAL_NS:
            _fail('insufficient_local_sample_interval')
        if second['status'] == 'directory_enoent':
            result.update(status='identity_absent', reason='two_same_domain_pid_directory_enoent')
        elif second['status'] == 'identity_changed':
            result.update(status='identity_changed', reason='positive_replacement_observation')
        else:
            result.update(status='unknown', reason='transient_directory_absence')
        return result
    except (OSError, ValueError, IndexError, KeyError, TypeError, OverflowError) as error:
        result['reason'] = _error_reason(error, context)
        return result


def normalize_identity_absence(observation, registration):
    """Normalize ONLY an actual approved-provider absence under exact custody.

    The trusted owner must pass its own observe_registration return and the
    exact genuine positive registration. This pure function cannot establish
    reporter provenance and must never be exposed as participant JSON input.
    Present/zombie/replacement/error/uncertain facts never become absence.
    Identity absence has unknown returncode and proves no elapsed stop grace.
    """
    registered = validate_registration(registration)
    keys = {'status', 'reason', 'registration_digest', 'returncode', 'samples'}
    if (type(observation) is not dict or set(observation) != keys or
            type(observation['status']) is not str or
            observation['status'] != 'identity_absent' or
            type(observation['reason']) is not str or
            observation['reason'] != 'two_same_domain_pid_directory_enoent' or
            type(observation['registration_digest']) is not str or
            observation['registration_digest'] != registered['registration_digest'] or
            observation['returncode'] is not None):
        _fail('not_exact_provider_identity_absence')
    return validate_absence({
        'schema_version': SCHEMA_VERSION, 'provider': PROVIDER,
        'method': 'procfs_enoent_twice',
        'registration_digest': registered['registration_digest'],
        'domain_digest': registered['domain_digest'],
        'process': registered['process'], 'domain': registered['domain'],
        'returncode': None, 'samples': observation['samples'],
    }, registered)
