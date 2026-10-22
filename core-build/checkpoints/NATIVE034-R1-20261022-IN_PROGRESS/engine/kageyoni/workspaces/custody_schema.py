"""Authoritative pure worker-custody schema2. No procfs reader or process control.

Derived from root-accepted R4 provider 138ce899; product must import these validators
rather than retaining a second schema implementation. Hashes identify bytes,
not authenticity of owner-supplied observations.
"""
import hashlib
import json
import os
import re
import uuid

SCHEMA_VERSION = 2


REGISTRATION_LIMIT = 32768


FIELD_LIMIT = 65536


MOUNTINFO_LIMIT = 1048576


MIN_INTERVAL_NS = 50_000_000


_PROCESS_KEYS = {'pid', 'proc_pid', 'pid_namespace', 'start_ticks'}


_DOMAIN_KEYS = {'boot_id', 'reader_pid_namespace', 'mount_namespace',
                'proc_root_device', 'proc_root_inode', 'proc_mountinfo', 'proc_submounts'}


_REGISTRATION_KEYS = {'schema_version', 'process', 'domain', 'domain_digest',
                      'registration_digest'}


_STATES = {'R', 'S', 'D', 'Z', 'T', 't', 'W', 'K', 'P', 'I'}


_HASH = re.compile(r'[0-9a-f]{64}\Z')


_POSITIVE = re.compile(r'[1-9][0-9]*\Z')


_PID_NS = re.compile(r'pid:\[[1-9][0-9]*\]\Z')


_MOUNT_NS = re.compile(r'mnt:\[[1-9][0-9]*\]\Z')


_MOUNT_FLAGS = {'rw', 'ro', 'nosuid', 'nodev', 'noexec', 'relatime',
                'noatime', 'strictatime', 'nodiratime', 'lazytime', 'hidepid=0'}


_SUPER_FLAGS = {'rw', 'ro', 'hidepid=0'}


class CustodySchemaError(ValueError):
    """Registration could not obtain an authentic complete positive observation."""
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _fail(reason):
    raise CustodySchemaError(reason)


def _positive(value):
    return type(value) is int and 0 < value <= 2**63 - 1


def _canonical(value):
    data = json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')
    if len(data) > REGISTRATION_LIMIT:
        _fail('registration_too_large')
    return data


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _validate_process(value):
    if type(value) is not dict or set(value) != _PROCESS_KEYS:
        _fail('invalid_process_shape')
    if not _positive(value['pid']) or not _positive(value['proc_pid']):
        _fail('invalid_process_pid')
    if (type(value['pid_namespace']) is not str or
            len(value['pid_namespace']) > 64 or not _PID_NS.fullmatch(value['pid_namespace'])):
        _fail('invalid_process_namespace')
    if (type(value['start_ticks']) is not str or
            len(value['start_ticks']) > 24 or not _POSITIVE.fullmatch(value['start_ticks'])):
        _fail('invalid_process_start_ticks')
    return dict(value)


def _parse_mount(line):
    # Parse EVERY mount line, including unrelated filesystems, before selecting
    # proc descendants. Escaped/ambiguous names cannot conceal a relevant path.
    if (type(line) is not str or not line or len(line) > 8192 or
            any(ord(c) < 32 or ord(c) == 127 for c in line) or chr(92) in line):
        _fail('invalid_or_escaped_mountinfo')
    fields = line.split(' ')
    if '' in fields or fields.count('-') != 1:
        _fail('invalid_mountinfo_fields')
    sep = fields.index('-')
    if sep < 6 or len(fields) != sep + 4:
        _fail('unsupported_mountinfo_fields')
    if not all(_POSITIVE.fullmatch(x) for x in fields[:2]):
        _fail('invalid_mount_ids')
    device = fields[2].split(':')
    if len(device) != 2 or any(not re.fullmatch(r'0|[1-9][0-9]*', x) for x in device):
        _fail('invalid_mount_device')
    for path in fields[3:5]:
        if (not path.startswith('/') or (path != '/' and
                (path.endswith('/') or any(x in ('', '.', '..') for x in path.split('/')[1:])))):
            _fail('ambiguous_mount_path')
    if not re.fullmatch(r'[A-Za-z0-9_.+-]+', fields[sep+1]) or not fields[sep+2]:
        _fail('invalid_mount_filesystem_or_source')
    for options in (fields[5], fields[sep+3]):
        opts = options.split(',')
        if (not opts or '' in opts or len(set(opts)) != len(opts) or
                len(set(opts) & {'rw', 'ro'}) != 1):
            _fail('invalid_or_ambiguous_mount_options')
    optional = fields[6:sep]
    for item in optional:
        if item != 'unbindable' and not re.fullmatch(r'(shared|master|propagate_from):[1-9][0-9]*', item):
            _fail('unsupported_mount_optional')
    if len({item.split(':', 1)[0] for item in optional}) != len(optional):
        _fail('ambiguous_mount_optional')
    return {'id': fields[0], 'parent': fields[1],
            'device': os.makedev(int(device[0]), int(device[1])),
            'root': fields[3], 'point': fields[4], 'mount_options': fields[5],
            'fstype': fields[sep+1], 'source': fields[sep+2],
            'super_options': fields[sep+3]}


def _ordinary_proc(mount):
    if mount['fstype'] != 'proc' or mount['source'] != 'proc':
        _fail('unsupported_proc_filesystem')
    for options, allowed in [(mount['mount_options'], _MOUNT_FLAGS),
                             (mount['super_options'], _SUPER_FLAGS)]:
        if not set(options.split(',')) <= allowed:
            _fail('restricted_or_unsupported_proc_mount')


def _validate_proc_view(root_line, submounts):
    root = _parse_mount(root_line); _ordinary_proc(root)
    if root['root'] != '/' or root['point'] != '/proc':
        _fail('unsupported_proc_mount')
    if type(submounts) is not list or any(type(x) is not str for x in submounts):
        _fail('invalid_proc_submounts')
    if len(submounts) > 6:
        _fail('unsupported_proc_submount')
    if submounts != sorted(submounts):
        _fail('unsorted_proc_submounts')
    ids = {root['id']}; points = {root['point']}; mask_device = None
    for line in submounts:
        mount = _parse_mount(line)
        if mount['id'] in ids or mount['point'] in points:
            _fail('ambiguous_proc_submount')
        ids.add(mount['id']); points.add(mount['point'])
        if mount['parent'] != root['id']:
            _fail('unsupported_proc_submount_parent')
        if mount['point'] in {'/proc/keys', '/proc/timer_list'}:
            # These exact sibling file masks cannot cover a numeric PID,
            # self mapping or the boot-id subtree. Pin every raw line anyway.
            if (mount['root'] != '/null' or mount['fstype'] != 'tmpfs' or
                    mount['source'] != 'tmpfs' or mount['device'] == root['device'] or
                    not set(mount['mount_options'].split(',')) <= (_MOUNT_FLAGS - {'hidepid=0'})):
                _fail('unsupported_noncritical_proc_mask')
            if mask_device is not None and mask_device != mount['device']:
                _fail('inconsistent_noncritical_proc_masks')
            mask_device = mount['device']
        else:
            if (mount['point'] not in {'/proc/bus', '/proc/fs', '/proc/irq', '/proc/sys'} or
                    mount['root'] != mount['point'][len('/proc'):] or
                    mount['device'] != root['device'] or
                    mount['fstype'] != 'proc' or mount['source'] != 'proc'):
                _fail('unsupported_proc_submount')
            _ordinary_proc(mount)
    return root['device']


def _validate_domain(value):
    if type(value) is not dict or set(value) != _DOMAIN_KEYS:
        _fail('invalid_domain_shape')
    boot = value['boot_id']
    if type(boot) is not str or len(boot) != 36:
        _fail('invalid_boot_id')
    try:
        parsed = uuid.UUID(boot)
    except ValueError:
        _fail('invalid_boot_id')
    if str(parsed) != boot or parsed.int == 0:
        _fail('invalid_boot_id')
    if type(value['reader_pid_namespace']) is not str or len(value['reader_pid_namespace']) > 64 or not _PID_NS.fullmatch(value['reader_pid_namespace']):
        _fail('invalid_reader_namespace')
    if type(value['mount_namespace']) is not str or len(value['mount_namespace']) > 64 or not _MOUNT_NS.fullmatch(value['mount_namespace']):
        _fail('invalid_mount_namespace')
    if (type(value['proc_root_device']) is not int or value['proc_root_device'] < 0 or
            not _positive(value['proc_root_inode'])):
        _fail('invalid_proc_root_stat')
    if _validate_proc_view(value['proc_mountinfo'], value['proc_submounts']) != value['proc_root_device']:
        _fail('proc_root_mount_device_mismatch')
    _canonical(value)
    return {**value, 'proc_submounts': list(value['proc_submounts'])}


def _validated_registration(value):
    if type(value) is not dict or set(value) != _REGISTRATION_KEYS or type(value['schema_version']) is not int or value['schema_version'] != SCHEMA_VERSION:
        _fail('invalid_registration_shape')
    process = _validate_process(value['process']); domain = _validate_domain(value['domain'])
    if process['pid_namespace'] != domain['reader_pid_namespace']:
        _fail('registration_namespace_mismatch')
    for key in ('domain_digest', 'registration_digest'):
        if type(value[key]) is not str or not _HASH.fullmatch(value[key]):
            _fail('invalid_registration_digest')
    if value['domain_digest'] != _digest(domain):
        _fail('domain_digest_mismatch')
    base = {'schema_version': SCHEMA_VERSION, 'process': process, 'domain': domain,
            'domain_digest': value['domain_digest']}
    if value['registration_digest'] != _digest(base):
        _fail('registration_digest_mismatch')
    return {**base, 'registration_digest': value['registration_digest']}


def decode_registration(blob):
    """Strict optional persistence decoder; duplicate keys never normalize away."""
    if type(blob) is not bytes or len(blob) > REGISTRATION_LIMIT:
        _fail('invalid_registration_encoding')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail('duplicate_registration_key')
            result[key] = value
        return result
    try:
        value = json.loads(blob.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=lambda _value: _fail('nonfinite_registration'))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail('invalid_registration_encoding')
    return _validated_registration(value)

PROVIDER = 'samsara.procfs-directory-v2'
ABSENCE_KEYS = {'schema_version', 'provider', 'method', 'registration_digest',
                'domain_digest', 'process', 'domain', 'returncode', 'samples'}


def validate_registration(value):
    """Return a detached exact record; public digests are not caller authentication."""
    return _validated_registration(value)


def validate_absence(value, registration):
    """Validate only a trusted-owner fact envelope, never establish OS truth."""
    registered = validate_registration(registration)
    if type(value) is not dict or set(value) != ABSENCE_KEYS:
        _fail('invalid_absence_shape')
    if (any(type(value[key]) is not str for key in ('provider','method','registration_digest','domain_digest')) or
            type(value['schema_version']) is not int or value['schema_version'] != 2 or
            value['provider'] != PROVIDER or value['method'] != 'procfs_enoent_twice' or
            value['returncode'] is not None):
        _fail('invalid_absence_provider_or_method')
    if (value['registration_digest'] != registered['registration_digest'] or
            value['domain_digest'] != registered['domain_digest'] or
            _validate_process(value['process']) != registered['process'] or
            _validate_domain(value['domain']) != registered['domain']):
        _fail('absence_registration_correspondence_mismatch')
    samples = value['samples']
    if type(samples) is not list or len(samples) != 2:
        _fail('invalid_absence_samples')
    result = []
    for sample in samples:
        if (type(sample) is not dict or set(sample) != {'status', 'observed_monotonic_ns'} or
                type(sample['status']) is not str or sample['status'] != 'directory_enoent' or
                type(sample['observed_monotonic_ns']) is not int or sample['observed_monotonic_ns'] < 0):
            _fail('invalid_absence_sample')
        result.append(dict(sample))
    if result[1]['observed_monotonic_ns'] - result[0]['observed_monotonic_ns'] < MIN_INTERVAL_NS:
        _fail('insufficient_local_sample_interval')
    detached = {**value, 'process': dict(registered['process']),
                'domain': {**registered['domain'], 'proc_submounts': list(registered['domain']['proc_submounts'])},
                'samples': result}
    _canonical(detached)
    return detached
